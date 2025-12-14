#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Transform iCloud inbox quick.jsonl -> Google Sheets (or CSV) and push to Anki via AnkiConnect.

- Reads /Portuguese/Anki/inbox/quick.jsonl
- Normalizes each entry to a target lemma/short phrase (e.g., "I have to print this page." -> "print")
- Asks LLM for pt-PT translation + example sentence
- Appends to Google Sheets (primary) or sayings.csv (fallback), writes last_import.csv snapshot, adds to Anki
- UTF-8 safe logging; continues past per-item errors

Storage backends:
- Google Sheets (default): Set GOOGLE_SHEETS_CREDENTIALS env var or use --use-csv to disable
- CSV fallback: Use --use-csv flag or set USE_CSV=1

Note: Dynamic image fetching/uploading has been removed. Card visuals are now handled
statically in the Anki note template (e.g., a fixed logo/brand image).
"""
from __future__ import annotations

# ---- stdlib imports (order matters so sys is available before use) ----
import argparse
import csv
import datetime as dt
import errno
import io
import json
import html
import os
import re
import subprocess
import sys
import time
import urllib.request
from urllib.error import URLError
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# local
from _openai_compat import chat as _compat_chat

# Google Sheets integration (optional)
_google_sheets_available = False
_google_sheets_storage = None
try:
    import google_sheets
    _google_sheets_available = google_sheets.is_available()
except ImportError:
    pass

# ===== PATHS / DEFAULTS =====
# Force Mobile Documents path; honor ANKI_BASE env; fallback to CloudStorage
from pathlib import Path
import os
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")  # default for logging/mock
ANKI_URL = os.environ.get("ANKI_URL", "http://127.0.0.1:8765")

def get_anki_base() -> Path:
    # 1) Honor env from run_pipeline.sh
    env = os.environ.get("ANKI_BASE")
    if env:
        return Path(env)

    # 2) Prefer Mobile Documents (works on iPhone/iPad & Mac)
    mobile = (
        Path.home()
        / "Library"
        / "Mobile Documents"
        / "com~apple~CloudDocs"
        / "Portuguese"
        / "Anki"
    )
    if mobile.exists():
        return mobile

    # 3) Fallback to CloudStorage mount on newer macOS
    cloud = (
        Path.home()
        / "Library"
        / "CloudStorage"
        / "iCloud Drive"
        / "Portuguese"
        / "Anki"
    )
    return cloud

BASE = get_anki_base()
INBOX_DIR = BASE / "inbox"
INBOX_FILE = INBOX_DIR / "quick.jsonl"   # canonical inbox
MASTER_CSV = BASE / "sayings.csv"
LAST_IMPORT = BASE / "last_import.csv"
LOG_DIR = BASE / "logs"                  # usage logs live here

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

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _normalize_ascii_quotes(s: str) -> str:
    if not isinstance(s, str):
        return s
    for k, v in _SMART_MAP.items():
        s = s.replace(k, v)
    return s


def _normalize_sentence_for_key(value: str) -> str:
    """
    Normalize sentence text for duplicate comparison. Strips HTML wrappers,
    unescapes entities, and collapses whitespace.
    """
    if not isinstance(value, str):
        return ""
    text = html.unescape(value)
    text = (
        text.replace("<br />", "\n")
        .replace("<br>", "\n")
        .replace("</div>", "\n")
        .replace("<div>", "\n")
    )
    text = _HTML_TAG_RE.sub(" ", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return " ".join(text.split()).strip()


def _sentence_duplicate_key(word_en: str, sentence_pt: str, sentence_en: str) -> Tuple[str, str, str]:
    return (
        (word_en or "").strip().lower(),
        _normalize_sentence_for_key(sentence_pt),
        _normalize_sentence_for_key(sentence_en),
    )


def _safe_printerr(msg: str):
    try:
        print(msg, file=sys.stderr)
    except UnicodeEncodeError:
        try:
            sys.stderr.buffer.write((msg + "\n").encode("utf-8", "replace"))
        except Exception:
            print(msg.encode("ascii", "ignore").decode("ascii"), file=sys.stderr)


_LOG_LEVEL_RANK = {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40, "SILENT": 50}
_CURRENT_LOG_LEVEL = _LOG_LEVEL_RANK["INFO"]


def _set_log_level(level: str) -> None:
    global _CURRENT_LOG_LEVEL
    level = (level or "INFO").upper()
    _CURRENT_LOG_LEVEL = _LOG_LEVEL_RANK.get(level, _LOG_LEVEL_RANK["INFO"])


def _log(level: str, msg: str) -> None:
    lvl = _LOG_LEVEL_RANK.get((level or "INFO").upper(), _LOG_LEVEL_RANK["INFO"])
    if lvl < _CURRENT_LOG_LEVEL:
        return
    print(msg)


def _coerce_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return True
    if isinstance(value, (int, float)):
        return value != 0
    s = str(value).strip().lower()
    if s in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if s in {"0", "false", "f", "no", "n", "off", ""}:
        return False
    raise ValueError(f"Invalid boolean value: {value!r}")


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
            payload = None
            if "entries" in obj:
                payload = obj["entries"]
            elif isinstance(obj.get("word"), str):
                payload = obj["word"]
            else:
                for key in ("text", "entry", "term", "phrase"):
                    candidate = obj.get(key)
                    if isinstance(candidate, (str, list)):
                        payload = candidate
                        break

            if payload is None:
                continue

            if isinstance(payload, str):
                values = [payload]
            elif isinstance(payload, list):
                values = [item for item in payload if isinstance(item, str)]
            else:
                continue

            for item in values:
                out.extend(
                    [p.strip() for p in re.split(r"[,\n;]+", item) if p.strip()]
                )
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

    # Allow slightly longer conversational requests (<=8 tokens) to pass through intact.
    if 5 <= len(toks) <= 8 and any(t.lower() not in _STOPWORDS for t in toks):
        trimmed = _clean_spaces(re.sub(r"[.!?]+$", "", s))
        return (trimmed, "phrase-extended")

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


def _detect_csv_format(csv_path: Path) -> Tuple[bool, str]:
    """
    Detect CSV format by checking first line.
    Returns (has_header, format_type) where format_type is:
      - 'new': word_en, word_pt, sentence_pt, sentence_en, date_added
      - 'old': date_added, word_pt, word_en, sentence_pt, sentence_en
    """
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return (False, 'new')

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        first_line = f.readline().strip()

    if not first_line:
        return (False, 'new')

    # Check for header
    if "word_en" in first_line.lower():
        return (True, 'new')

    # No header - check if first field is a date (old format)
    first_field = first_line.split(',')[0].strip()
    if re.match(r'^\d{4}-\d{2}-\d{2}$', first_field):
        return (False, 'old')

    return (False, 'new')


def load_existing_words(csv_path: Path) -> set:
    """
    Load existing word_en values from CSV for deduplication.
    Handles both old format (date_added first) and new format (word_en first).
    """
    seen = set()
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return seen

    has_header, fmt = _detect_csv_format(csv_path)

    # Determine which column contains word_en
    word_en_col = 0 if fmt == 'new' else 2

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        r = csv.reader(f)
        first_row = True
        for row in r:
            if not row:
                continue
            if first_row:
                first_row = False
                if has_header:
                    continue  # Skip header row
            if len(row) > word_en_col:
                word = row[word_en_col].strip().lower()
                if word:
                    seen.add(word)
    return seen


def load_existing_sentence_pairs(csv_path: Path) -> set:
    """
    Return a set of (word_en, sentence_pt, sentence_en) keys to detect exact duplicates.
    Handles both old format (date_added first) and new format (word_en first).
    """
    pairs = set()
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return pairs

    has_header, fmt = _detect_csv_format(csv_path)

    # Column indices based on format
    if fmt == 'new':
        # word_en, word_pt, sentence_pt, sentence_en, date_added
        word_en_col, sentence_pt_col, sentence_en_col = 0, 2, 3
    else:
        # date_added, word_pt, word_en, sentence_pt, sentence_en
        word_en_col, sentence_pt_col, sentence_en_col = 2, 3, 4

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        r = csv.reader(f)
        first_row = True
        for row in r:
            if not row:
                continue
            if first_row:
                first_row = False
                if has_header:
                    continue  # Skip header row
            if len(row) <= max(word_en_col, sentence_pt_col, sentence_en_col):
                continue
            pairs.add(_sentence_duplicate_key(
                row[word_en_col],
                row[sentence_pt_col],
                row[sentence_en_col]
            ))
    return pairs


def append_rows(csv_path: Path, rows: List[List[str]]) -> None:
    """
    Append rows to CSV. Rows come in as [word_en, word_pt, sentence_pt, sentence_en, date_added].
    If the existing file uses old format, convert to match.
    """
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        # New file - use new format with header
        ensure_header(csv_path)
        with csv_path.open("a", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            for row in rows:
                w.writerow(row)
    else:
        has_header, fmt = _detect_csv_format(csv_path)
        with csv_path.open("a", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            for row in rows:
                if fmt == 'old':
                    # Convert from [word_en, word_pt, sentence_pt, sentence_en, date_added]
                    # to [date_added, word_pt, word_en, sentence_pt, sentence_en]
                    word_en, word_pt, sentence_pt, sentence_en, date_added = row
                    w.writerow([date_added, word_pt, word_en, sentence_pt, sentence_en])
                else:
                    w.writerow(row)


# ===== ANKICONNECT =====
_anki_launch_attempted = False
_last_launch_ts: Optional[float] = None


def _escape_for_anki_query(value: str) -> str:
    return (value or "").replace('"', '\\"')


def _get_anki_sentence_pairs(deck: str, word_en: str) -> set:
    """
    Return a set of normalized (sentence_pt, sentence_en) tuples already stored in Anki
    for the given word.
    """
    query = f'deck:"{_escape_for_anki_query(deck)}" word_en:"{_escape_for_anki_query(word_en)}"'
    res = anki_invoke({"action": "findNotes", "version": 6, "params": {"query": query}})
    if res.get("error"):
        raise RuntimeError(f"AnkiConnect findNotes error: {res['error']}")
    note_ids = res.get("result") or []
    if not note_ids:
        return set()

    info = anki_invoke({"action": "notesInfo", "version": 6, "params": {"notes": note_ids}})
    if info.get("error"):
        raise RuntimeError(f"AnkiConnect notesInfo error: {info['error']}")
    pairs = set()
    for note in info.get("result") or []:
        fields = note.get("fields") or {}
        existing_pt = _normalize_sentence_for_key(
            (fields.get("sentence_pt") or {}).get("value", "")
        )
        existing_en = _normalize_sentence_for_key(
            (fields.get("sentence_en") or {}).get("value", "")
        )
        if existing_pt or existing_en:
            pairs.add((existing_pt, existing_en))
    return pairs


def _should_retry_connection(err: URLError) -> bool:
    """
    Return True if the URLError looks like a connection refused situation.
    """
    reason = getattr(err, "reason", err)
    if isinstance(reason, ConnectionRefusedError):
        return True
    err_no = getattr(reason, "errno", None)
    if err_no in (errno.ECONNREFUSED, 61):  # macOS uses 61
        return True
    return False


def _launch_anki() -> bool:
    """
    Attempt to launch Anki once. Returns True if launch was attempted.
    """
    global _anki_launch_attempted, _last_launch_ts
    if _anki_launch_attempted:
        return False
    cmd = os.environ.get("ANKI_LAUNCH_CMD")
    if cmd:
        parts = cmd.strip().split()
    else:
        app = os.environ.get("ANKI_APP", "Anki")
        parts = ["open", "-g", "-a", app]
    try:
        subprocess.Popen(parts)
        _anki_launch_attempted = True
        _last_launch_ts = time.time()
        _log("INFO", "[INFO] Autostarting Anki after connection refusal.")
        return True
    except Exception as exc:
        _safe_printerr(f"[WARN] Failed to auto-launch Anki: {exc}")
        _anki_launch_attempted = True  # avoid repeated attempts
        return False


def anki_invoke(payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ANKI_URL, data, headers={"Content-Type": "application/json"}
    )
    attempts = 0
    while True:
        attempts += 1
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except URLError as exc:
            if attempts == 1 and _should_retry_connection(exc) and _launch_anki():
                # give AnkiConnect a moment to come up, retry once
                time.sleep(3)
                continue
            raise


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
    seen_pairs = set()
    skipped_batch_duplicates = 0
    skipped_existing_duplicates = 0
    anki_sentence_cache: Dict[str, set] = {}
    for r in rows:
        word_en, word_pt, sentence_pt, sentence_en, date_added = r
        key = _sentence_duplicate_key(word_en, sentence_pt, sentence_en)
        if key in seen_pairs:
            skipped_batch_duplicates += 1
            _log(
                "INFO",
                f"[dup] Skipping {word_en} (identical sentences already in this batch).",
            )
            continue

        cache_key = word_en.strip().lower()
        if cache_key not in anki_sentence_cache:
            anki_sentence_cache[cache_key] = _get_anki_sentence_pairs(deck, word_en)
        if (key[1], key[2]) in anki_sentence_cache[cache_key]:
            skipped_existing_duplicates += 1
            _log(
                "INFO",
                f"[dup] Skipping {word_en} (identical sentences already in Anki).",
            )
            continue
        seen_pairs.add(key)

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
                "options": {"allowDuplicate": True, "duplicateScope": "deck"},
            }
        )

    if skipped_batch_duplicates:
        _log(
            "INFO",
            f"[dup] Skipped {skipped_batch_duplicates} in-batch duplicate sentence(s).",
        )
    if skipped_existing_duplicates:
        _log(
            "INFO",
            f"[dup] Skipped {skipped_existing_duplicates} sentence duplicate(s) already present in Anki.",
        )

    if not notes:
        return 0, []

    can = anki_invoke(
        {"action": "canAddNotes", "version": 6, "params": {"notes": notes}}
    )
    if can.get("error"):
        raise RuntimeError(f"AnkiConnect canAddNotes error: {can['error']}")
    flags = can.get("result", [])
    addable = [n for n, ok in zip(notes, flags) if ok]
    if not addable:
        _log("INFO", "[INFO] All candidate notes already exist in Anki (nothing to add).")
        return 0, []
    res = anki_invoke(
        {"action": "addNotes", "version": 6, "params": {"notes": addable}}
    )
    if res.get("error"):
        raise RuntimeError(f"AnkiConnect error: {res['error']}")
    gids = res.get("result", [])
    added = sum(1 for nid in gids if isinstance(nid, int))
    return added, gids


def refresh_anki_ui() -> None:
    """
    Ask AnkiConnect to refresh the collection UI so new notes are visible.
    """
    anki_invoke({"action": "gui.refreshAll", "version": 6})


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
    ap.add_argument("--deck", default="Portuguese Mastery (pt-PT)")
    ap.add_argument("--model", default="GPT Vocabulary Automater")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--inbox-file", default=None, help="Path to inbox file to read (override).")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="If set, skip any entry with >3 tokens or ending in sentence punctuation.",
    )
    ap.add_argument(
        "--out",
        default=None,
        help="Override output CSV path (defaults to iCloud sayings.csv).",
    )
    ap.add_argument(
        "--dry-run",
        nargs="?",
        const="1",
        default="0",
        help="Process entries but skip CSV writes and Anki addNotes (accepts 0/1/true/false).",
    )
    ap.add_argument(
        "--log-level",
        default="INFO",
        type=str.upper,
        choices=list(_LOG_LEVEL_RANK.keys()),
        help="Logging verbosity for stdout (default: INFO).",
    )
    ap.add_argument(
        "--use-csv",
        action="store_true",
        default=False,
        help="Force using local CSV file instead of Google Sheets.",
    )
    ap.add_argument(
        "--spreadsheet-id",
        default=None,
        help="Google Sheets spreadsheet ID (default: from google_sheets module).",
    )
    args = ap.parse_args(argv)

    try:
        args.dry_run = _coerce_bool(args.dry_run)
    except ValueError as exc:
        ap.error(str(exc))

    _set_log_level(args.log_level)

    # Determine storage backend
    use_csv = args.use_csv or os.environ.get("USE_CSV", "").lower() in ("1", "true", "yes")
    use_google_sheets = False
    gsheets_storage = None

    if not use_csv and _google_sheets_available:
        try:
            spreadsheet_id = args.spreadsheet_id or google_sheets.SPREADSHEET_ID
            gsheets_storage = google_sheets.GoogleSheetsStorage(spreadsheet_id=spreadsheet_id)
            # Test connection
            _ = gsheets_storage.get_all_rows(use_cache=False)
            use_google_sheets = True
            _log("INFO", f"[storage] Using Google Sheets (ID: {spreadsheet_id})")
        except Exception as e:
            _safe_printerr(f"[WARN] Google Sheets unavailable: {e}")
            _log("INFO", "[storage] Falling back to CSV")
    else:
        if use_csv:
            _log("INFO", "[storage] Using CSV (--use-csv flag)")
        else:
            _log("INFO", "[storage] Using CSV (Google Sheets not configured)")

    master_csv = Path(args.out).expanduser() if args.out else MASTER_CSV
    last_import = (
        master_csv.with_name("last_import.csv") if args.out else LAST_IMPORT
    )
    if args.out and not args.dry_run:
        master_csv.parent.mkdir(parents=True, exist_ok=True)

    _log(
        "INFO",
        f"[enc] stdout={getattr(sys.stdout, 'encoding', None)} "
        f"stderr={getattr(sys.stderr, 'encoding', None)}",
    )

    for path in (BASE, INBOX_DIR, LOG_DIR):
        try:
            path.mkdir(parents=True, exist_ok=True)
        except PermissionError as exc:
            if args.dry_run:
                _safe_printerr(f"[WARN] Could not ensure directory {path}: {exc}")
                continue
            raise

    inbox_path = Path(args.inbox_file) if args.inbox_file else INBOX_FILE
    raw_items = read_quick_entries(inbox_path)
    if not raw_items:
        _log("INFO", f"[INFO] No entries to process in {inbox_path}")
        return 0

    # Normalize/lemma-ize
    normalized: List[Tuple[str, str, str]] = []  # (lemma, rule, original)
    for raw in raw_items:
        if args.strict:
            toks = _tokens(raw)
            if len(toks) > 3 or re.search(r"[.!?]$", raw.strip()):
                _log("INFO", f"[norm-skip] strict: '{raw}'")
                continue
        res = extract_lemma(raw)
        if res is None:
            _log("INFO", f"[norm-skip] '{raw}' (no lemma)")
            continue
        lemma, rule = res
        _log("INFO", f"[norm] '{raw}' -> '{lemma}' (rule: {rule})")
        normalized.append((lemma, rule, raw))

    if not normalized:
        _log("INFO", "[INFO] Nothing left after normalization.")
        return 0

    # Dedupe against storage + within this batch
    if use_google_sheets:
        existing_words = gsheets_storage.load_existing_words()
        _log("INFO", f"[dedup] Loaded {len(existing_words)} existing words from Google Sheets")
    else:
        existing_words = load_existing_words(master_csv)
        _log("INFO", f"[dedup] Loaded {len(existing_words)} existing words from CSV")
    seen, todo = set(), []
    for lemma, rule, original in normalized:
        k = lemma.strip().lower()
        if not k or k in seen:
            continue
        if " " not in k and k in existing_words:
            _log("INFO", f"[dup-word] Skipping '{lemma}' (single-word already stored).")
            continue
        seen.add(k)
        todo.append((lemma, original))
    if args.limit > 0:
        todo = todo[: args.limit]
    if not todo:
        _log("INFO", "[INFO] Nothing new after duplicate filtering.")
        return 0

    _log("INFO", f"[INFO] Will process {len(todo)} item(s).")
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
            _log(
                "INFO",
                f"[OK] {i}/{len(todo)}  {row[0]} -> {row[1]}  "
                f"(tokens p/c/t={p}/{c}/{t}, id={mid}, rid={rid})",
            )
        except Exception as e:
            _safe_printerr(f"ERROR: LLM failed on '{lemma}' (from '{original}'): {e}")
            failures.append((lemma, str(e)))
            continue

    if not new_rows and failures:
        _safe_printerr("[ERROR] All items failed; nothing to write/add.")
        if not args.dry_run:
            with last_import.open("w", encoding="utf-8", newline="") as f:
                wcsv = csv.writer(f)
                wcsv.writerow(
                    ["word_en", "word_pt", "sentence_pt", "sentence_en", "date_added"]
                )
        return 1

    if new_rows:
        if use_google_sheets:
            existing_pairs = gsheets_storage.load_existing_sentence_pairs()
        else:
            existing_pairs = load_existing_sentence_pairs(master_csv)
        seen_pairs = set(existing_pairs)
        filtered_rows: List[List[str]] = []
        skipped_duplicates = 0
        for row in new_rows:
            key = _sentence_duplicate_key(row[0], row[2], row[3])
            if key in seen_pairs:
                skipped_duplicates += 1
                _log(
                    "INFO",
                    f"[dup] Skipping {row[0]} (identical sentences already stored).",
                )
                continue
            seen_pairs.add(key)
            filtered_rows.append(row)
        if skipped_duplicates:
            _log(
                "INFO",
                f"[dup] Skipped {skipped_duplicates} row(s) due to identical sentences.",
            )
        new_rows = filtered_rows

    # print and log usage summary for this run
    _log(
        "INFO",
        f"[USAGE] calls={calls} prompt={prompt_sum} completion={completion_sum} total={total_sum}",
    )
    if not args.dry_run:
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
            if use_google_sheets:
                count = gsheets_storage.append_rows(new_rows)
                _log("INFO", f"[INFO] Appended {count} row(s) to Google Sheets")
            else:
                append_rows(master_csv, new_rows)
                _log("INFO", f"[INFO] Appended {len(new_rows)} row(s) to {master_csv}")

            # Always write local snapshot for reference
            with last_import.open("w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(
                    ["word_en", "word_pt", "sentence_pt", "sentence_en", "date_added"]
                )
                w.writerows(new_rows)
            _log("INFO", f"[INFO] Snapshot written to {last_import}")
        except Exception as e:
            storage_name = "Google Sheets" if use_google_sheets else "CSV"
            _safe_printerr(f"ERROR: Writing to {storage_name} failed: {e}")
            return 1

        try:
            added, _ = add_notes_to_anki(args.deck, args.model, new_rows)
            _log("INFO", f"[INFO] Anki addNotes added {added}/{len(new_rows)}")
            if added > 0:
                try:
                    refresh_anki_ui()
                    _log("INFO", "[INFO] Requested Anki UI refresh.")
                except Exception as exc:
                    _safe_printerr(f"[WARN] Could not refresh Anki UI: {exc}")
        except Exception as e:
            _safe_printerr(f"ERROR: Anki addNotes failed: {e}")
            return 1
    else:
        _log("INFO", "[dry-run] Skipped writing CSVs, usage logs, and Anki addNotes.")

    if failures:
        _safe_printerr(f"[WARN] {len(failures)} item(s) failed and were skipped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
