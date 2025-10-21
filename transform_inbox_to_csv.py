#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Transform iCloud inbox quick.jsonl -> sayings.csv and push to Anki via AnkiConnect.
- Reads /Portuguese/Anki/inbox/quick.jsonl
- For each entry (words/phrases), asks LLM for pt-PT card JSON
- Appends to sayings.csv and writes last_import.csv snapshot
- Adds notes to Anki (deck/model must exist)
- Robust against smart quotes and encoding issues; continues on per-item errors
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

# ---- OpenAI compat (prefer new SDK, guarded fallback only if legacy is installed) ----

from typing import Dict, List, Optional, Tuple
from _openai_compat import chat as _compat_chat

# --- force UTF-8 for all prints/logs to avoid UnicodeEncodeError ---
import io
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
# -------------------------------------------------------------------

# --- utilities: normalize curly quotes & safe stderr printing -------
_SMART_MAP = {
    "“": '"', "”": '"',        # smart double quotes -> ASCII "
    "‘": "'", "’": "'",        # smart single quotes -> ASCII '
    "\u00A0": " ", "\u2009": " ", "\u200A": " ", "\u202F": " ",  # non-breaking/thin spaces
}
def _normalize_ascii_quotes(s: str) -> str:
    if not isinstance(s, str):
        return s
    for k, v in _SMART_MAP.items():
        s = s.replace(k, v)
    return s

def _safe_printerr(msg: str):
    try:
        print(msg, file=sys.stderr)
    except UnicodeEncodeError:
        try:
            sys.stderr.buffer.write((msg + "\n").encode("utf-8", "replace"))
        except Exception:
            print(msg.encode("ascii", "ignore").decode("ascii"), file=sys.stderr)
# -------------------------------------------------------------------

FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$")
def _extract_json_sanitized(raw: str) -> Dict[str, str]:
    """Strip code fences, normalize quotes, then parse JSON. Also tries first {...} block if needed."""
    s2 = FENCE_RE.sub("", raw.strip())
    s2 = _normalize_ascii_quotes(s2)
    try:
        return json.loads(s2)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s2, flags=re.S)
        if m:
            frag = _normalize_ascii_quotes(m.group(0))
            return json.loads(frag)
        raise

def _clean_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()

# ---- OpenAI compat (new SDK preferred, legacy fallback) ----

# ===== PATHS / DEFAULTS =====
BASE        = Path("/Users/koossimons/Library/CloudStorage/iCloud Drive/Portuguese/Anki")
INBOX_DIR   = BASE / "inbox"
INBOX_FILE  = INBOX_DIR / "quick.jsonl"     # single 'l' (jsonl)
MASTER_CSV  = BASE / "sayings.csv"
LAST_IMPORT = BASE / "last_import.csv"
DEFAULT_DECK  = "Portuguese (pt-PT)"
DEFAULT_MODEL = "GPT Vocabulary Automater"

# ===== OPENAI =====
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")

# ===== READ JSONL =====
def read_quick_entries(path: Path) -> List[str]:
    """Lines are JSON objects. Accepts:
       {"entries":"w1, w2"} or {"entries":["w1","w2"]} or {"word":"w1"}"""
    if not path.exists() or path.stat().st_size == 0:
        return []
    out: List[str] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "entries" in obj:
                e = obj["entries"]
                if isinstance(e, str):
                    out.extend([p.strip() for p in re.split(r"[,\n;]+", e) if p.strip()])
                elif isinstance(e, list):
                    for item in e:
                        if isinstance(item, str):
                            out.extend([p.strip() for p in re.split(r"[,\n;]+", item) if p.strip()])
            elif isinstance(obj.get("word"), str):
                out.append(obj["word"])
    # strip empties and duplicates while preserving order
    seen = set()
    uniq: List[str] = []
    for s in out:
        w = s.strip()
        if not w:
            continue
        k = w.lower()
        if k in seen:
            continue
        seen.add(k)
        uniq.append(w)
    return uniq

# ===== CSV =====
def ensure_header(csv_path: Path) -> None:
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow(["word_en", "word_pt", "sentence_pt", "sentence_en", "date_added"])

def load_existing_words(csv_path: Path) -> set:
    seen = set()
    if csv_path.exists() and csv_path.stat().st_size > 0:
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            r = csv.reader(f)
            header = True
            for row in r:
                if not row:
                    continue
                if header and row[:1] == ["word_en"]:
                    header = False
                    continue
                seen.add(row[0].strip().lower())
    return seen

def append_rows(csv_path: Path, rows: List[List[str]]) -> None:
    ensure_header(csv_path)
    with csv_path.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        for row in rows:
            w.writerow(row)

# ===== ANKICONNECT =====
ANKI_URL = os.environ.get("ANKI_URL", "http://127.0.0.1:8765")
def anki_invoke(payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(ANKI_URL, data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def add_notes_to_anki(deck: str, model: str, rows: List[List[str]]) -> Tuple[int, List[Optional[int]]]:
    """Skip duplicates gracefully using canAddNotes."""
    if not rows:
        return 0, []
    tag = dt.datetime.now().strftime("auto_ptPT_%Y%m%d")
    notes = [{
        "deckName": deck,
        "modelName": model,
        "fields": {
            "word_en": r[0], "word_pt": r[1], "sentence_pt": r[2], "sentence_en": r[3], "date_added": r[4]
        },
        "tags": ["auto", "pt-PT", tag],
        "options": {"allowDuplicate": False, "duplicateScope": "deck"},
    } for r in rows]

    can = anki_invoke({"action": "canAddNotes", "version": 6, "params": {"notes": notes}})
    if can.get("error"):
        raise RuntimeError(f"AnkiConnect canAddNotes error: {can['error']}")
    flags = can.get("result", [])
    addable = [n for n, ok in zip(notes, flags) if ok]
    if not addable:
        print("[INFO] All candidate notes already exist in Anki (nothing to add).")
        return 0, []
    res = anki_invoke({"action": "addNotes", "version": 6, "params": {"notes": addable}})
    if res.get("error"):
        err = res["error"]
        if isinstance(err, str) and "duplicate" in err.lower():
            print("[INFO] Some notes were duplicates and were skipped by Anki.")
        else:
            raise RuntimeError(f"AnkiConnect error: {err}")
    gids = res.get("result", [])
    added = sum(1 for nid in gids if isinstance(nid, int))
    return added, gids

# ===== OPENAI CALL =====
def ask_llm(word_en: str) -> Dict[str, str]:
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("Missing OPENAI_API_KEY")

    system = (
        "You are a meticulous European Portuguese (pt-PT) language expert. "
        'Return JSON only and use plain ASCII double quotes (") for all keys/strings; '
        "do not use smart quotes. "
        "Fields: word_en, word_pt, sentence_pt, sentence_en. "
        "sentence_pt must be idiomatic pt-PT, 12-22 words, C1 level. "
        "sentence_en is a natural English gloss."
    )
    user = (
        "Return ONLY valid JSON, no code fences. "
        "Keys: word_en, word_pt, sentence_pt, sentence_en.\n"
        f"Target word: {word_en.strip()}"
    )

    r = _compat_chat(
        model=LLM_MODEL,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=0.2, top_p=0.95, max_tokens=300
    )

    # Normalize output BEFORE parsing
    text = _normalize_ascii_quotes(r["choices"][0]["message"]["content"].strip())

    try:
        data = _extract_json_sanitized(text)
    except Exception as e:
        # Short, ASCII-safe error message; do not include raw model text
        raise ValueError("Bad JSON from LLM (after sanitization)") from e

    # Validate required fields but DO NOT echo raw text back
    for k in ("word_en", "word_pt", "sentence_pt", "sentence_en"):
        v = str(data.get(k, "")).strip()
        if not v:
            raise ValueError(f"Missing required field: {k}")

    return {
        "word_en": data["word_en"].strip(),
        "word_pt": data["word_pt"].strip(),
        "sentence_pt": _clean_spaces(data["sentence_pt"]),
        "sentence_en": _clean_spaces(data["sentence_en"]),
    }

# ===== MAIN =====
def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deck", default=DEFAULT_DECK)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args(argv)

    # Encodings (one-time log)
    print(f"[enc] stdout={getattr(sys.stdout, 'encoding', None)} "
          f"stderr={getattr(sys.stderr, 'encoding', None)}")

    BASE.mkdir(parents=True, exist_ok=True)
    INBOX_DIR.mkdir(parents=True, exist_ok=True)

    words = read_quick_entries(INBOX_FILE)
    if not words:
        print(f"[INFO] No entries to process in {INBOX_FILE}")
        return 0

    existing = load_existing_words(MASTER_CSV)
    seen, todo = set(), []
    for w in words:
        k = w.strip().lower()
        if not k or k in seen or k in existing:
            continue
        seen.add(k)
        todo.append(w)
    if args.limit > 0:
        todo = todo[:args.limit]
    if not todo:
        print("[INFO] Nothing new after duplicate filtering.")
        return 0

    print(f"[INFO] Will process {len(todo)} item(s).")
    today = dt.datetime.now().strftime("%Y-%m-%d")
    new_rows: List[List[str]] = []
    failures: List[Tuple[str, str]] = []

    for i, w in enumerate(todo, 1):
        try:
            pack = ask_llm(w)
            row = [pack["word_en"], pack["word_pt"], pack["sentence_pt"], pack["sentence_en"], today]
            new_rows.append(row)
            print(f"[OK] {i}/{len(todo)}  {row[0]} -> {row[1]}")
        except Exception as e:
            _safe_printerr(f"ERROR: LLM failed on '{w}': {e}")
            failures.append((w, str(e)))
            continue

    if not new_rows and failures:
        _safe_printerr("[ERROR] All items failed; nothing to write/add.")
        # still write an empty snapshot to make state explicit
        with LAST_IMPORT.open("w", encoding="utf-8", newline="") as f:
            wcsv = csv.writer(f)
            wcsv.writerow(["word_en", "word_pt", "sentence_pt", "sentence_en", "date_added"])
        return 1

    # Persist CSVs
    try:
        append_rows(MASTER_CSV, new_rows)
        with LAST_IMPORT.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["word_en", "word_pt", "sentence_pt", "sentence_en", "date_added"])
            w.writerows(new_rows)
        print(f"[INFO] Appended {len(new_rows)} row(s) to {MASTER_CSV}")
        print(f"[INFO] Snapshot written to {LAST_IMPORT}")
    except Exception as e:
        _safe_printerr(f"ERROR: Writing CSV failed: {e}")
        return 1

    # Push to Anki
    try:
        added, _ = add_notes_to_anki(args.deck, args.model, new_rows)
        print(f"[INFO] Anki addNotes added {added}/{len(new_rows)}")
    except Exception as e:
        _safe_printerr(f"ERROR: Anki addNotes failed: {e}")
        return 1

    # Optionally surface failures summary
    if failures:
        _safe_printerr(f"[WARN] {len(failures)} item(s) failed and were skipped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ---- OpenAI (new SDK only) ----
def _compat_chat(model, messages, temperature=0.2, top_p=0.95, max_tokens=300):
    from openai import OpenAI  # requires openai>=1.0
    import os as _os
    client = OpenAI(api_key=_os.getenv("OPENAI_API_KEY"))
    r = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
    )
    return {"choices":[{"message":{"content": r.choices[0].message.content}}]}

