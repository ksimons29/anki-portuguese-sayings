#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Transform iCloud inbox quick.jsonl -> sayings.csv and push to Anki via AnkiConnect.

- Reads /Portuguese/Anki/inbox/quick.jsonl
- Normalizes each entry to a target lemma/short phrase (e.g., "I have to print this page." -> "print")
- Asks LLM for pt-PT translation + example sentence
- Appends to sayings.csv, writes last_import.csv snapshot, adds to Anki
- UTF-8 safe logging; continues past per-item errors

Note: Dynamic image fetching/uploading has been removed. Card visuals are now handled
statically in the Anki note template (e.g., a fixed logo/brand image).
"""
from __future__ import annotations

# ---- stdlib imports (order matters so sys is available before use) ----
import argparse
import csv
import datetime as dt
import io
import json
import os
import re
import sys
import errno
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# local
from _openai_compat import chat as _compat_chat

# ===== PATHS / DEFAULTS =====
ANKI_BASE = os.environ.get(
    "ANKI_BASE",
    "/Users/koossimons/Library/Mobile Documents/com~apple~CloudDocs/Portuguese/Anki",
)
BASE = Path(ANKI_BASE)
INBOX_DIR = BASE / "inbox"
INBOX_FILE = INBOX_DIR / "quick.jsonl"  # canonical inbox
MASTER_CSV = BASE / "sayings.csv"
LAST_IMPORT = BASE / "last_import.csv"
LOG_DIR = BASE / "logs"  # usage logs live here

DEFAULT_DECK = "Portuguese Mastery (pt-PT)"
DEFAULT_MODEL = "GPT Vocabulary Automater"
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
ANKI_URL = os.environ.get("ANKI_URL", "http://127.0.0.1:8765")

# --- UTF-8 stdout/stderr ---
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding="utf-8", errors="replace"
        )

# --- sanitize smart quotes & safe stderr ---
_SMART_MAP = {
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
    "\u00a0": " ",
    "\u2009": " ",
    "\u200a": " ",
    "\u202f": " ",
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


# --- JSON helpers ---
FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$")


def _extract_json_sanitized(raw: str) -> Dict[str, str]:
    s2 = FENCE_RE.sub("", raw.strip())
    s2 = _normalize_ascii_quotes(s2)
    try:
        return json.loads(s2)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s2, flags=re.S)
        if m:
            return json.loads(_normalize_ascii_quotes(m.group(0)))
        raise


def _clean_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()

# Robust open with retry to handle iCloud Drive transient locks
def _open_with_retry(path: Path, tries: int = 8, base: float = 0.25):
    for i in range(tries):
        try:
            return path.open("r", encoding="utf-8", errors="replace")
        except OSError as e:
            if getattr(e, "errno", None) in (errno.EDEADLK, errno.EBUSY, errno.EAGAIN):
                time.sleep(base * (2 ** i))
                continue
            raise
    raise RuntimeError(f"Could not open {path}; it remained locked")
    
# ===== READ JSONL =====
def read_quick_entries(path: Path) -> List[str]:
    """Accepts lines like:
    {"entries":"w1, w2"} or {"entries":["w1","w2"]} or {"word":"w1"}"""
    if not path.exists() or path.stat().st_size == 0:
        return []
    out: List[str] = []
    with _open_with_retry(path) as f:
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
                    out.extend(
                        [p.strip() for p in re.split(r"[,\n;]+", e) if p.strip()]
                    )
                elif isinstance(e, list):
                    for item in e:
                        if isinstance(item, str):
                            out.extend(
                                [
                                    p.strip()
                                    for p in re.split(r"[,\n;]+", item)
                                    if p.strip()
                                ]
                            )
            elif isinstance(obj.get("word"), str):
                out.append(obj["word"])
    return out


# ===== NORMALIZATION / LEMMA EXTRACTION =====
_STOPWORDS = {
    "i",
    "you",
    "he",
    "she",
    "it",
    "we",
    "they",
    "me",
    "him",
    "her",
    "us",
    "them",
    "a",
    "an",
    "the",
    "this",
    "that",
    "these",
    "those",
    "to",
    "of",
    "in",
    "on",
    "at",
    "for",
    "from",
    "with",
    "by",
    "as",
    "about",
    "into",
    "through",
    "over",
    "after",
    "before",
    "between",
    "without",
    "within",
    "against",
    "and",
    "or",
    "but",
    "if",
    "because",
    "so",
    "though",
    "although",
    "while",
    "be",
    "am",
    "is",
    "are",
    "was",
    "were",
    "been",
    "being",
    "have",
    "has",
    "had",
    "having",
    "do",
    "does",
    "did",
    "doing",
    "can",
    "could",
    "should",
    "would",
    "will",
    "must",
    "may",
    "might",
    "my",
    "your",
    "his",
    "her",
    "our",
    "their",
    "mine",
    "yours",
    "hers",
    "ours",
    "theirs",
    "page",
    "pages",
}
_PUNCT_RE = re.compile(r"^[^\w]+|[^\w]+$")  # trim leading/trailing punctuation


def _tokens(s: str) -> List[str]:
    return [
        _PUNCT_RE.sub("", t) for t in _clean_spaces(s).split() if _PUNCT_RE.sub("", t)
    ]


def extract_lemma(raw: str) -> Optional[Tuple[str, str]]:
    """
    Return (lemma, rule) or None if we want to skip it.
    Rules:
      - keep if 1–3 tokens (e.g., "romantic date")
      - sentence heuristic: if pattern 'to VERB' exists, pick that verb
      - else remove stopwords; if any tokens left, pick:
         • 'print' if present
         • else the longest remaining token
      - else if 4+ tokens and ends with sentence punctuation, skip (too long)
    """
    s = _normalize_ascii_quotes(raw).strip()
    if not s:
        return None

    toks = _tokens(s)
    if not toks:
        return None

    # preserve short phrases (1–3 tokens)
    if len(toks) <= 3:
        lemma = _clean_spaces(" ".join(toks))
        return (lemma, "short-phrase")

    # try "to VERB" pattern (e.g., "I have to print this page.")
    m = re.search(r"\bto\s+([a-zA-Z]+)\b", s)
    if m:
        lemma = m.group(1).lower()
        return (lemma, "to-VERB")

    # remove stopwords, prefer a content token
    remaining = [t for t in toks if t.lower() not in _STOPWORDS]
    if remaining:
        if any(t.lower() == "print" for t in remaining):
            return ("print", "content-print")
        lemma = max(remaining, key=len)
        return (lemma.lower(), "content-longest")

    # If looks like a long sentence with terminal punctuation, skip
    if len(toks) >= 4 and re.search(r"[.!?]$", s):
        return None

    # fallback: shrink to first 3 tokens
    lemma = " ".join(toks[:3]).lower()
    return (lemma, "fallback-top3")


# ===== CSV =====
def ensure_header(csv_path: Path) -> None:
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow(
                ["word_en", "word_pt", "sentence_pt", "sentence_en", "date_added"]
            )


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
def anki_invoke(payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ANKI_URL, data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def add_notes_to_anki(
    deck: str, model: str, rows: List[List[str]]
) -> Tuple[int, List[Optional[int]]]:
    """
    rows = [word_en, word_pt, sentence_pt, sentence_en, date_added]
    Builds Anki notes with text-only fields. Static images are handled in the note template.
    """
    if not rows:
        return 0, []
    tag = dt.datetime.now().strftime("auto_ptPT_%Y%m%d")

    notes: List[dict] = []
    for r in rows:
        word_en, word_pt, sentence_pt, sentence_en, date_added = r

        notes.append(
            {
                "deckName": deck,
                "modelName": model,
                "fields": {
                    "word_en": word_en,
                    "word_pt": word_pt,
                    "sentence_pt": sentence_pt,
                    "sentence_en": sentence_en,
                    "date_added": date_added,
                },
                "tags": ["auto", "pt-PT", tag],
                "options": {"allowDuplicate": False, "duplicateScope": "deck"},
            }
        )

    can = anki_invoke(
        {"action": "canAddNotes", "version": 6, "params": {"notes": notes}}
    )
    if can.get("error"):
        raise RuntimeError(f"AnkiConnect canAddNotes error: {can['error']}")
    flags = can.get("result", [])
    addable = [n for n, ok in zip(notes, flags) if ok]
    if not addable:
        print("[INFO] All candidate notes already exist in Anki (nothing to add).")
        return 0, []
    res = anki_invoke(
        {"action": "addNotes", "version": 6, "params": {"notes": addable}}
    )
    if res.get("error"):
        raise RuntimeError(f"AnkiConnect error: {res['error']}")
    gids = res.get("result", [])
    added = sum(1 for nid in gids if isinstance(nid, int))
    return added, gids


# ===== LLM CALL =====
def ask_llm(word_en: str) -> Tuple[Dict[str, str], Dict[str, int], Dict[str, object]]:
    """
    Returns: (pack, usage, meta)
      - pack: dict with word_en/word_pt/sentence_pt/sentence_en
      - usage: {'prompt_tokens','completion_tokens','total_tokens'} if available, else {}
      - meta:  {'model','id','created','request_id',...} if available, else {}
    """
    if not (
        os.getenv("OPENAI_API_KEY")
        or os.getenv("AZURE_OPENAI_API_KEY")
        or os.getenv("MOCK_LLM") == "1"
    ):
        raise RuntimeError("Missing OPENAI/AZURE key (or set MOCK_LLM=1).")

    # --- Improved prompts (paste here) ---
    system = """You are a bilingual lexicographer and European Portuguese (pt-PT) teacher.
Return EXACTLY ONE valid UTF-8 JSON object (single line) with these keys (and only these keys):
- "word_en": an English lemma or concise short phrase
- "word_pt": a European Portuguese lemma or concise short phrase (pt-PT)
- "sentence_pt": a natural example sentence in European Portuguese (pt-PT)
- "sentence_en": an accurate English translation of sentence_pt

Rules (strict):
- Direction: if the input is English, translate to pt-PT; if the input is pt-PT, provide the English equivalent.
- If the input is a sentence or long phrase, choose the best concise lemma/short phrase for "word_pt" and its EN counterpart for "word_en".
- sentence_pt: 12–22 words, everyday adult context, idiomatic, C1 naturalness; use the lemma/phrase naturally once; no quotes or brackets.
- Use a neutral, informal European Portuguese register (tu) with correct conjugation.
- Prefer Portugal usage and spelling; use slang only if it is the most natural/common choice.
- Keep all Portuguese diacritics. Do not add phonetics/IPA.

Formatting:
- JSON only, ONE LINE, double quotes for all strings, no trailing commas, no code fences, no commentary.
- Use straight ASCII double quotes (") not smart quotes."""

    user = (
        "Produce ONLY the single JSON object described above.\n"
        f"Target: {word_en.strip()}"
    )
    # --- end improved prompts ---

    r = _compat_chat(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
        top_p=0.95,
        max_tokens=300,
    )

    usage = r.get("usage") or {}
    meta = r.get("meta") or {}

    text = _normalize_ascii_quotes(r["choices"][0]["message"]["content"].strip())
    try:
        data = _extract_json_sanitized(text)
    except Exception as e:
        raise ValueError("Bad JSON from LLM (after sanitization)") from e

    for k in ("word_en", "word_pt", "sentence_pt", "sentence_en"):
        v = str(data.get(k, "")).strip()
        if not v:
            raise ValueError(f"Missing required field: {k}")

    pack = {
        "word_en": data["word_en"].strip(),
        "word_pt": data["word_pt"].strip(),
        "sentence_pt": _clean_spaces(data["sentence_pt"]),
        "sentence_en": _clean_spaces(data["sentence_en"]),
    }
    return pack, usage, meta
    
# ===== MAIN =====
def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deck", default=DEFAULT_DECK)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--inbox-file", default=None, help="Path to inbox file to read (override).")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="If set, skip any entry with >3 tokens or ending in sentence punctuation.",
    )
    args = ap.parse_args(argv)

    print(
        f"[enc] stdout={getattr(sys.stdout, 'encoding', None)} "
        f"stderr={getattr(sys.stderr, 'encoding', None)}"
    )

    BASE.mkdir(parents=True, exist_ok=True)
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    inbox_path = Path(args.inbox_file) if args.inbox_file else INBOX_FILE
    raw_items = read_quick_entries(inbox_path)
    if not raw_items:
        print(f"[INFO] No entries to process in {inbox_path}")
        return 0

    # Normalize/lemma-ize
    normalized: List[Tuple[str, str, str]] = []  # (lemma, rule, original)
    for raw in raw_items:
        if args.strict:
            toks = _tokens(raw)
            if len(toks) > 3 or re.search(r"[.!?]$", raw.strip()):
                print(f"[norm-skip] strict: '{raw}'")
                continue
        res = extract_lemma(raw)
        if res is None:
            print(f"[norm-skip] '{raw}' (no lemma)")
            continue
        lemma, rule = res
        print(f"[norm] '{raw}' -> '{lemma}' (rule: {rule})")
        normalized.append((lemma, rule, raw))

    if not normalized:
        print("[INFO] Nothing left after normalization.")
        return 0

    # Dedupe against CSV + within this batch
    existing = load_existing_words(MASTER_CSV)
    seen, todo = set(), []
    for lemma, rule, original in normalized:
        k = lemma.strip().lower()
        if not k or k in seen or k in existing:
            continue
        seen.add(k)
        todo.append((lemma, original))
    if args.limit > 0:
        todo = todo[: args.limit]
    if not todo:
        print("[INFO] Nothing new after duplicate filtering.")
        return 0

    print(f"[INFO] Will process {len(todo)} item(s).")
    today = dt.datetime.now().strftime("%Y-%m-%d")
    new_rows: List[List[str]] = []
    failures: List[Tuple[str, str]] = []

    # token usage counters
    calls = 0
    prompt_sum = completion_sum = total_sum = 0

    for i, (lemma, original) in enumerate(todo, 1):
        try:
            pack, usage, meta = ask_llm(lemma)
            row = [
                pack["word_en"],
                pack["word_pt"],
                pack["sentence_pt"],
                pack["sentence_en"],
                today,
            ]
            new_rows.append(row)

            # accumulate usage (works even if usage is {})
            calls += 1
            p = usage.get("prompt_tokens") or 0
            c = usage.get("completion_tokens") or 0
            t = usage.get("total_tokens") or (p + c if (p or c) else 0)
            prompt_sum += p
            completion_sum += c
            total_sum += t

            rid = meta.get("request_id")
            mid = meta.get("id")
            print(
                f"[OK] {i}/{len(todo)}  {row[0]} -> {row[1]}  "
                f"(tokens p/c/t={p}/{c}/{t}, id={mid}, rid={rid})"
            )
        except Exception as e:
            _safe_printerr(f"ERROR: LLM failed on '{lemma}' (from '{original}'): {e}")
            failures.append((lemma, str(e)))
            continue

    if not new_rows and failures:
        _safe_printerr("[ERROR] All items failed; nothing to write/add.")
        with LAST_IMPORT.open("w", encoding="utf-8", newline="") as f:
            wcsv = csv.writer(f)
            wcsv.writerow(
                ["word_en", "word_pt", "sentence_pt", "sentence_en", "date_added"]
            )
        return 1

    # print and log usage summary for this run
    print(
        f"[USAGE] calls={calls} prompt={prompt_sum} completion={completion_sum} total={total_sum}"
    )
    ulog = LOG_DIR / f"tokens_{dt.datetime.now():%Y-%m}.csv"
    try:
        new_file = not ulog.exists()
        with ulog.open("a", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(
                    [
                        "timestamp",
                        "model",
                        "calls",
                        "prompt_tokens",
                        "completion_tokens",
                        "total_tokens",
                    ]
                )
            w.writerow(
                [
                    dt.datetime.now().isoformat(timespec="seconds"),
                    LLM_MODEL,
                    calls,
                    prompt_sum,
                    completion_sum,
                    total_sum,
                ]
            )
    except Exception as e:
        _safe_printerr(f"[WARN] Could not write usage log: {e}")

    try:
        append_rows(MASTER_CSV, new_rows)
        with LAST_IMPORT.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(
                ["word_en", "word_pt", "sentence_pt", "sentence_en", "date_added"]
            )
            w.writerows(new_rows)
        print(f"[INFO] Appended {len(new_rows)} row(s) to {MASTER_CSV}")
        print(f"[INFO] Snapshot written to {LAST_IMPORT}")
    except Exception as e:
        _safe_printerr(f"ERROR: Writing CSV failed: {e}")
        return 1

    try:
        added, _ = add_notes_to_anki(args.deck, args.model, new_rows)
        print(f"[INFO] Anki addNotes added {added}/{len(new_rows)}")
    except Exception as e:
        _safe_printerr(f"ERROR: Anki addNotes failed: {e}")
        return 1

    if failures:
        _safe_printerr(f"[WARN] {len(failures)} item(s) failed and were skipped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
