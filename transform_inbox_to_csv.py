#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Clean transformer for iCloud inbox -> Anki CSV and AnkiConnect push.

- Input:  ~/Library/CloudStorage/iCloud Drive/Portuguese/Anki/inbox/quick.jsonl
  Each line is JSON, e.g.: {"ts":"2025-10-16 09:30:00","src":"quick","entries":"window, door, coffee"}
  Also supports entries: [ ... ] or {"word":"..."}.

- Output CSV (append): sayings.csv with columns:
  word_en,word_pt,sentence_pt,sentence_en,date_added

- Snapshot of just-added rows: last_import.csv (same columns)

- Anki push: addNotes to "Portuguese (pt-PT)" / "GPT Vocabulary Automater"

Exit codes:
  0 -> success (even if no work)
  1 -> error (pipeline should keep quick.jsonl intact for retry)
"""

from __future__ import annotations
from _openai_compat import compat_chat as _compat_chat
import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import urllib.request, urllib.error
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# =========
# PATHS
# =========
BASE = Path("/Users/koossimons/Library/CloudStorage/iCloud Drive/Portuguese/Anki")
INBOX_FILE  = BASE / "inbox" / "quick.jsonl"
MASTER_CSV  = BASE / "sayings.csv"
LAST_IMPORT = BASE / "last_import.csv"

DEFAULT_DECK  = "Portuguese (pt-PT)"
DEFAULT_MODEL = "GPT Vocabulary Automater"

# =========
# OPENAI
# =========
# If you want hardcoded key, put it here:
HARDCODED_OPENAI_KEY = "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"  # <- your real key here
if HARDCODED_OPENAI_KEY and "sk-" in HARDCODED_OPENAI_KEY:
    os.environ["OPENAI_API_KEY"] = HARDCODED_OPENAI_KEY

LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")

def ask_llm(word_en: str) -> Dict[str, str]:
    """Return dict {word_en, word_pt, sentence_pt, sentence_en} for pt-PT (C1)."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("Missing OPENAI_API_KEY (set or hardcode in script).")

    system = (
        "You are a meticulous European Portuguese (pt-PT) language expert. "
        "For each English lemma, produce (JSON only): word_en, word_pt, sentence_pt, sentence_en. "
        "Sentence_pt must be idiomatic pt-PT (Lisbon context ok), 12–22 words, C1 level. "
        "Sentence_en is a natural English gloss."
    )
    user = f"""
Return ONLY valid JSON, no code fences. Keys: word_en, word_pt, sentence_pt, sentence_en.
Target word: {word_en.strip()}

Example:
{{"word_en":"rent","word_pt":"renda","sentence_pt":"A renda aumentou este ano e estou a negociar um novo contrato.","sentence_en":"The rent went up this year and I am negotiating a new contract."}}
""".strip()

    resp = _compat_chat(
        model=LLM_MODEL,
        messages=[{"role":"system","content":system},{"role":"user","content":user}],
        temperature=0.2,
        top_p=0.95,
        max_tokens=300,
    )
    text = resp["choices"][0]["message"]["content"].strip()
    data = _extract_json(text)

    for k in ("word_en","word_pt","sentence_pt","sentence_en"):
        if k not in data or not str(data[k]).strip():
            raise ValueError(f"Model response missing '{k}': {text}")

    return {
        "word_en": data["word_en"].strip(),
        "word_pt": data["word_pt"].strip(),
        "sentence_pt": _clean_spaces(data["sentence_pt"]),
        "sentence_en": _clean_spaces(data["sentence_en"]),
    }

FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$")
def _extract_json(raw: str) -> Dict[str,str]:
    s = FENCE_RE.sub("", raw.strip())
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s, flags=re.S)
        if m:
            return json.loads(m.group(0))
        raise

def _clean_spaces(s: str) -> str:
    return re.sub(r"\s+"," ", s).strip()

# =========
# JSONL INPUT
# =========
def read_quick_entries(path: Path) -> List[str]:
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
                # skip invalid lines
                continue
            if "entries" in obj:
                e = obj["entries"]
                if isinstance(e, str):
                    out.extend(_split_terms(e))
                elif isinstance(e, list):
                    for item in e:
                        if isinstance(item, str):
                            out.extend(_split_terms(item))
            elif "word" in obj and isinstance(obj["word"], str):
                out.append(obj["word"])
    # normalize
    out = [w.strip() for w in out if w and w.strip()]
    return out

def _split_terms(s: str) -> List[str]:
    return [p.strip() for p in re.split(r"[,\n;]+", s) if p.strip()]

# =========
# CSV HELPERS
# =========
def ensure_header(csv_path: Path) -> None:
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow(["word_en","word_pt","sentence_pt","sentence_en","date_added"])

def load_existing_wordens(csv_path: Path) -> set:
    seen = set()
    if csv_path.exists() and csv_path.stat().st_size > 0:
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            r = csv.reader(f)
            header_skipped = False
            for row in r:
                if not row:
                    continue
                if not header_skipped and row[:1] == ["word_en"]:
                    header_skipped = True
                    continue
                seen.add(row[0].strip().lower())
    return seen

def append_rows(csv_path: Path, rows: List[List[str]]) -> None:
    ensure_header(csv_path)
    with csv_path.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        for row in rows:
            w.writerow(row)

# =========
# ANKICONNECT
# =========
ANKI_URL = os.environ.get("ANKI_URL","http://127.0.0.1:8765")

def anki_invoke(payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(ANKI_URL, data, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def add_notes_to_anki(deck: str, model: str, rows: List[List[str]]) -> Tuple[int, List[Optional[int]]]:
    if not rows:
        return 0, []
    today_tag = dt.datetime.now().strftime("auto_ptPT_%Y%m%d")

    notes = []
    for word_en, word_pt, sentence_pt, sentence_en, date_added in rows:
        notes.append({
            "deckName": deck,
            "modelName": model,
            "fields": {
                "word_en": word_en,
                "word_pt": word_pt,
                "sentence_pt": sentence_pt,
                "sentence_en": sentence_en,
                "date_added": date_added,
            },
            "tags": ["auto","pt-PT", today_tag],
            "options": {"allowDuplicate": False, "duplicateScope": "deck"},
        })

    payload = {"action":"addNotes","version":6,"params":{"notes": notes}}
    result = anki_invoke(payload)
    if "error" in result and result["error"]:
        raise RuntimeError(f"AnkiConnect error: {result['error']}")
    note_ids = result.get("result", [])
    added = sum(1 for nid in note_ids if isinstance(nid, int))
    return added, note_ids

# =========
# MAIN
# =========
def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--deck", default=DEFAULT_DECK)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args(argv)

    # Ensure folders
    (BASE/"inbox").mkdir(parents=True, exist_ok=True)
    BASE.mkdir(parents=True, exist_ok=True)

    words = read_quick_entries(INBOX_FILE)
    if not words:
        print(f"[INFO] No entries to process in {INBOX_FILE}")
        return 0

    existing = load_existing_wordens(MASTER_CSV)
    session_seen = set()
    todo = []
    for w in words:
        k = w.strip().lower()
        if not k or k in session_seen or k in existing:
            continue
        session_seen.add(k)
        todo.append(w)

    if args.limit > 0:
        todo = todo[:args.limit]

    if not todo:
        print("[INFO] Nothing new after duplicate filtering.")
        return 0

    print(f"[INFO] Will process {len(todo)} item(s).")

    today = dt.datetime.now().strftime("%Y-%m-%d")
    new_rows: List[List[str]] = []

    for idx, w in enumerate(todo, 1):
        try:
            pack = ask_llm(w)
            row = [pack["word_en"], pack["word_pt"], pack["sentence_pt"], pack["sentence_en"], today]
            new_rows.append(row)
            print(f"[OK] {idx}/{len(todo)}  {row[0]} -> {row[1]}")
        except Exception as e:
            print(f"ERROR: LLM failed on '{w}': {e}", file=sys.stderr)
            return 1   # fail fast; pipeline will keep quick.jsonl

    try:
        append_rows(MASTER_CSV, new_rows)
        with LAST_IMPORT.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f); w.writerow(["word_en","word_pt","sentence_pt","sentence_en","date_added"]); w.writerows(new_rows)
        print(f"[INFO] Appended {len(new_rows)} row(s) to {MASTER_CSV}")
        print(f"[INFO] Snapshot written to {LAST_IMPORT}")
    except Exception as e:
        print(f"ERROR: Writing CSV failed: {e}", file=sys.stderr)
        return 1

    try:
        added, _ = add_notes_to_anki(args.deck, args.model, new_rows)
        print(f"[INFO] Anki addNotes added {added}/{len(new_rows)}")
    except Exception as e:
        print(f"ERROR: Anki addNotes failed: {e}", file=sys.stderr)
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
