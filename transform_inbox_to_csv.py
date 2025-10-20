#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, json, csv, glob, datetime
from pathlib import Path
import urllib.request, urllib.error, argparse

# ==== Inject fallback OPENAI_API_KEY ====
os.environ["OPENAI_API_KEY"] = "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"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# ==== Paths ====
ICLOUD_BASE = Path("/Users/koossimons/Library/Mobile Documents/com~apple~CloudDocs/Portuguese/Anki")
INBOX  = ICLOUD_BASE / "inbox"
LOGS   = ICLOUD_BASE / "logs"
MASTER = ICLOUD_BASE / "sayings.csv"

# ==== Defaults, with env + CLI overrides ====
DECK_NAME_DEFAULT  = "Portuguese (pt-PT)"
MODEL_NAME_DEFAULT = "GPT Vocabulary Automater"
DECK_NAME  = os.environ.get("ANKI_DECK",  DECK_NAME_DEFAULT)
MODEL_NAME = os.environ.get("ANKI_MODEL", MODEL_NAME_DEFAULT)

# ==== OpenAI ====
OPENAI_MODEL   = "gpt-4o-mini"  # cheap + good

def log(msg: str) -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with (LOGS / f"{datetime.date.today()}.log").open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")

def read_jsonl():
    items = []
    for path in glob.glob(str(INBOX / "*.jsonl")):
        with open(path, "r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    items.append((path, json.loads(ln)))
                except Exception as e:
                    log(f"ERROR bad json in {path}: {e}")
    return items

SPEC = """ROLE
- Take a user's word/phrase list (EN or PT) and output Anki-import-ready CSV rows.
SCHEMA (DO NOT CHANGE)
date_added,word_pt,word_en,sentence_pt,sentence_en
OUTPUT RULES
- Reply with CSV rows ONLY (no header). Wrap EVERY field in double quotes; escape internal " as "".
- One word = one row. Multiple words = multiple rows, one per line.
LANGUAGE
- European Portuguese (pt-PT), AO90, avoid “você”; prefer neutral or tu.
FIELDS
- date_added: today's date YYYY-MM-DD (Europe/Lisbon).
- sentence_pt: 12–20 words, A2–B1, natural pt-PT.
DUPLICATES
- If duplicates within this request, include only once.
"""

def parse_cli():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--deck",  default=None)
    p.add_argument("--model", default=None)
    args, _ = p.parse_known_args()
    return args

def resolve_targets():
    args = parse_cli()
    deck  = args.deck  or DECK_NAME
    model = args.model or MODEL_NAME
    return deck, model

def gpt_rows(words: str) -> str:
    parts = [w.strip() for w in words.split(",") if w.strip()]
    if len(parts) > 100:
        parts = parts[:100]  # cost guardrail
    words = ", ".join(parts)

    body = json.dumps({
        "model": OPENAI_MODEL,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": SPEC},
            {"role": "user",   "content": f"add batch: {words}"}
        ]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    return data["choices"][0]["message"]["content"].strip()

def parse_csv_block(block: str):
    rdr = csv.reader(block.splitlines())
    rows = []
    for r in rdr:
        if not r: continue
        if len(r) != 5:
            raise ValueError(f"Bad CSV row (need 5 fields): {r}")
        rows.append(tuple(r))
    return rows

def load_master_pairs():
    pairs = set()
    if MASTER.exists():
        with open(MASTER, "r", encoding="utf-8") as f:
            for r in csv.reader(f):
                if len(r) == 5:
                    pairs.add((r[1].strip().lower(), r[2].strip().lower()))
    return pairs

# ===== Anki helpers =====
def anki_list_decks():
    try:
        payload={"action":"deckNames","version":6}
        req=urllib.request.Request("http://127.0.0.1:8765", data=json.dumps(payload).encode("utf-8"))
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.load(r).get("result") or []
    except Exception:
        return []

def anki_ensure_deck(deck_name: str) -> bool:
    if deck_name in anki_list_decks():
        return True
    try:
        payload={"action":"createDeck","version":6,"params":{"deck":deck_name}}
        req=urllib.request.Request("http://127.0.0.1:8765", data=json.dumps(payload).encode("utf-8"))
        with urllib.request.urlopen(req, timeout=5) as r:
            _=json.load(r)
        return True
    except Exception as e:
        log(f"Failed to create deck '{deck_name}': {e}")
        return False

def anki_find(word_en: str, word_pt: str) -> bool:
    try:
        q = f'word_en:"{word_en}"'
        payload={"action":"findNotes","version":6,"params":{"query":q}}
        req=urllib.request.Request("http://127.0.0.1:8765", data=json.dumps(payload).encode("utf-8"))
        with urllib.request.urlopen(req, timeout=5) as r:
            ids = json.load(r).get("result") or []
        return bool(ids)
    except Exception:
        return False

def anki_add(rows, deck_name, model_name):
    payload = {
        "action": "addNotes",
        "version": 6,
        "params": {
            "notes": [{
                "deckName": deck_name,
                "modelName": model_name,
                "fields": {
                    "date_added":  r[0],
                    "word_pt":     r[1],
                    "word_en":     r[2],
                    "sentence_pt": r[3],
                    "sentence_en": r[4],
                },
                "options": {"allowDuplicate": False, "duplicateScope": "collection"},
                "tags": ["from_gpt pt-PT"]
            } for r in rows]
        }
    }
    try:
        req=urllib.request.Request("http://127.0.0.1:8765", data=json.dumps(payload).encode("utf-8"))
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r).get("result")
    except Exception as e:
        log(f"AnkiConnect addNotes failed: {e}")
        return None

def append_master(rows):
    MASTER.parent.mkdir(parents=True, exist_ok=True)
    with open(MASTER, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        for r in rows:
            w.writerow(r)

def main():
    if not OPENAI_API_KEY:
        log("No OPENAI_API_KEY; skipping auto-write.")
        return

    entries = read_jsonl()
    if not entries:
        log("No inbox items.")
        return

    deck_name, model_name = resolve_targets()
    log(f"Targets → deck='{deck_name}', model='{model_name}'")
    if not anki_ensure_deck(deck_name):
        log(f"Deck '{deck_name}' unavailable; aborting add.")
        return

    words = ", ".join([e.get("entries", "").strip() for _, e in entries])
    log(f"Inbox snippets: {len(entries)}")

    try:
        block = gpt_rows(words)
        log("GPT block:\n" + block)
        rows = parse_csv_block(block)
        today = datetime.date.today().isoformat()
        rows = [(today, r[1], r[2], r[3], r[4]) for r in rows]
    except Exception as e:
        log(f"ERROR transforming inbox: {e}")
        return

    master = load_master_pairs()
    new, skip = [], []
    for r in rows:
        pair = (r[1].strip().lower(), r[2].strip().lower())
        if pair in master or anki_find(r[2], r[1]):
            skip.append(r)
        else:
            new.append(r)

    if new:
        append_master(new)
        res = anki_add(new, deck_name, model_name)
        log(f"Added {len(new)} notes via AnkiConnect. Result: {res}")
    else:
        log("All rows were duplicates; nothing added.")

    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    for path, _ in entries:
        try:
            os.rename(path, str(Path(path).with_suffix(f".{ts}.done")))
        except Exception:
            pass

    log(f"SUMMARY new={len(new)} skipped={len(skip)}")

if __name__ == "__main__":
    main()