#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Merge inbox fragments (json/jsonl) -> quick.jsonl, then transform to CSV and push to Anki.
"""
from __future__ import annotations
import argparse, csv, datetime as dt, json, os, re, sys, urllib.request, urllib.error
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---- OpenAI compat (new SDK preferred, legacy fallback) ----
try:
    from openai import OpenAI  # new SDK
    def _compat_chat(model, messages, temperature=0.2, top_p=0.95, max_tokens=300):
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        r = client.chat.completions.create(
            model=model, messages=messages,
            temperature=temperature, top_p=top_p, max_tokens=max_tokens,
        )
        return {"choices":[{"message":{"content": r.choices[0].message.content}}]}
except ImportError:
    import openai  # legacy
    def _compat_chat(model, messages, temperature=0.2, top_p=0.95, max_tokens=300):
        if os.getenv("OPENAI_API_KEY"): openai.api_key = os.getenv("OPENAI_API_KEY")
        r = openai.ChatCompletion.create(
            model=model, messages=messages,
            temperature=temperature, top_p=top_p, max_tokens=max_tokens,
        )
        return {"choices":[{"message":{"content": r["choices"][0]["message"]["content"]}}]}

# ===== PATHS / DEFAULTS =====
BASE       = Path("/Users/koossimons/Library/CloudStorage/iCloud Drive/Portuguese/Anki")
INBOX_DIR  = BASE / "inbox"
INBOX_FILE = INBOX_DIR / "quick.jsonl"
MASTER_CSV  = BASE / "sayings.csv"
LAST_IMPORT = BASE / "last_import.csv"
DEFAULT_DECK  = "Portuguese (pt-PT)"
DEFAULT_MODEL = "GPT Vocabulary Automater"

# ===== OPENAI =====
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
if os.environ.get("OPENAI_API_KEY","").startswith("sk-"):
    pass  # good; env already set

FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$")
def _extract_json(raw: str) -> Dict[str,str]:
    s = FENCE_RE.sub("", raw.strip())
    try: return json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s, flags=re.S)
        if m: return json.loads(m.group(0))
        raise
def _clean_spaces(s: str) -> str:
    return re.sub(r"\s+"," ", s).strip()

# ===== MERGE (.json + .jsonl -> quick.jsonl) =====
def merge_inbox_fragments(inbox: Path, target: Path) -> int:
    """
    Merge any 'quick*.json' or 'quick*.jsonl' into target JSONL.
    Handles quick.jsonl-6.json, quick.jsonl.json, quick-foo.jsonl, etc.
    Dedupes lines; archives fragments with .YYYYMMDD-HHMMSS.done.
    Returns number of merged fragments.
    """
    inbox.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)

    pats = ["quick*.json", "quick*.jsonl"]
    frags: List[Path] = []
    for pat in pats: frags.extend(inbox.glob(pat))
    frags = [f for f in frags if f.is_file() and f.name != "quick.jsonl" and not f.name.endswith(".done") and f != target]
    if not frags: return 0

    # de-dupe by filename
    seen, uniq = set(), []
    for f in sorted(frags, key=lambda p: p.name):
        if f.name in seen: continue
        seen.add(f.name); uniq.append(f)

    # read existing lines
    lines, seen_lines = [], set()
    if target.exists():
        with target.open("r", encoding="utf-8") as tf:
            for line in tf:
                line=line.strip()
                if line and line not in seen_lines:
                    seen_lines.add(line); lines.append(line)

    # append from frags
    for frag in uniq:
        with frag.open("r", encoding="utf-8") as ff:
            for line in ff:
                line=line.strip()
                if line and line not in seen_lines:
                    seen_lines.add(line); lines.append(line)

    # write back
    with target.open("w", encoding="utf-8") as tf:
        for l in lines: tf.write(l+"\n")

    # archive
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    for frag in uniq:
        frag.rename(frag.with_name(frag.name+f".{ts}.done"))

    print(f"[merge] merged {len(uniq)} fragment(s) into {target.name}")
    return len(uniq)

# ===== READ JSONL =====
def read_quick_entries(path: Path) -> List[str]:
    if not path.exists() or path.stat().st_size == 0: return []
    out: List[str] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line: continue
            try: obj=json.loads(line)
            except json.JSONDecodeError: continue
            if "entries" in obj:
                e=obj["entries"]
                if isinstance(e,str):
                    out.extend([p.strip() for p in re.split(r"[,\n;]+", e) if p.strip()])
                elif isinstance(e,list):
                    for item in e:
                        if isinstance(item,str):
                            out.extend([p.strip() for p in re.split(r"[,\n;]+", item) if p.strip()])
            elif isinstance(obj.get("word"),str):
                out.append(obj["word"])
    return [w for w in (s.strip() for s in out) if w]

# ===== CSV =====
def ensure_header(csv_path: Path) -> None:
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow(["word_en","word_pt","sentence_pt","sentence_en","date_added"])

def load_existing_wordens(csv_path: Path) -> set:
    seen=set()
    if csv_path.exists() and csv_path.stat().st_size>0:
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            r=csv.reader(f); header=True
            for row in r:
                if not row: continue
                if header and row[:1]==["word_en"]: header=False; continue
                seen.add(row[0].strip().lower())
    return seen

def append_rows(csv_path: Path, rows: List[List[str]]) -> None:
    ensure_header(csv_path)
    with csv_path.open("a", encoding="utf-8", newline="") as f:
        w=csv.writer(f)
        for row in rows: w.writerow(row)

# ===== OPENAI =====
def ask_llm(word_en: str) -> Dict[str, str]:
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("Missing OPENAI_API_KEY")
    system=("You are a meticulous European Portuguese (pt-PT) language expert. "
            "For each English lemma, produce (JSON only): word_en, word_pt, sentence_pt, sentence_en. "
            "Sentence_pt must be idiomatic pt-PT, 12–22 words, C1 level. "
            "Sentence_en is a natural English gloss.")
    user=f"Return ONLY valid JSON, no code fences. Keys: word_en, word_pt, sentence_pt, sentence_en.\nTarget word: {word_en.strip()}"
    r=_compat_chat(model=LLM_MODEL, messages=[{"role":"system","content":system},{"role":"user","content":user}],
                   temperature=0.2, top_p=0.95, max_tokens=300)
    text=r["choices"][0]["message"]["content"].strip()
    data=_extract_json(text)
    for k in ("word_en","word_pt","sentence_pt","sentence_en"):
        if not str(data.get(k,"")).strip(): raise ValueError(f"Missing '{k}': {text}")
    return {"word_en":data["word_en"].strip(),"word_pt":data["word_pt"].strip(),
            "sentence_pt":_clean_spaces(data["sentence_pt"]),
            "sentence_en":_clean_spaces(data["sentence_en"])}

# ===== ANKICONNECT =====
ANKI_URL=os.environ.get("ANKI_URL","http://127.0.0.1:8765")
def anki_invoke(payload: dict) -> dict:
    data=json.dumps(payload).encode("utf-8")
    req=urllib.request.Request(ANKI_URL, data, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def add_notes_to_anki(deck: str, model: str, rows: List[List[str]]) -> Tuple[int, List[Optional[int]]]:
    """Skip duplicates gracefully using canAddNotes."""
    if not rows: return 0,[]
    tag=dt.datetime.now().strftime("auto_ptPT_%Y%m%d")
    notes=[{"deckName":deck,"modelName":model,
            "fields":{"word_en":r[0],"word_pt":r[1],"sentence_pt":r[2],"sentence_en":r[3],"date_added":r[4]},
            "tags":["auto","pt-PT",tag],
            "options":{"allowDuplicate":False,"duplicateScope":"deck"}} for r in rows]
    can=anki_invoke({"action":"canAddNotes","version":6,"params":{"notes":notes}})
    if can.get("error"): raise RuntimeError(f"AnkiConnect canAddNotes error: {can['error']}")
    flags=can.get("result",[])
    addable=[n for n,ok in zip(notes,flags) if ok]
    if not addable:
        print("[INFO] All candidate notes already exist in Anki (nothing to add)."); return 0,[]
    res=anki_invoke({"action":"addNotes","version":6,"params":{"notes":addable}})
    if res.get("error"):
        err=res["error"]
        if isinstance(err,str) and "duplicate" in err.lower():
            print("[INFO] Some notes were duplicates and were skipped by Anki.")
        else:
            raise RuntimeError(f"AnkiConnect error: {err}")
    gids=res.get("result",[])
    added=sum(1 for nid in gids if isinstance(nid,int))
    return added,gids

# ===== MAIN =====
def main(argv: Optional[List[str]] = None) -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--deck", default=DEFAULT_DECK)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--limit", type=int, default=0)
    args=ap.parse_args(argv)

    BASE.mkdir(parents=True, exist_ok=True)
    INBOX_DIR.mkdir(parents=True, exist_ok=True)

    # Always merge first
    try:
        merged=merge_inbox_fragments(INBOX_DIR, INBOX_FILE)
        if merged: print(f"[merge] archived fragments and updated {INBOX_FILE.name}")
    except Exception as e:
        print(f"[merge] WARNING: merge failed: {e} (continuing)")

    words=read_quick_entries(INBOX_FILE)
    if not words:
        print(f"[INFO] No entries to process in {INBOX_FILE}")
        return 0

    existing=load_existing_wordens(MASTER_CSV)
    seen,todo=set(),[]
    for w in words:
        k=w.strip().lower()
        if not k or k in seen or k in existing: continue
        seen.add(k); todo.append(w)
    if args.limit>0: todo=todo[:args.limit]
    if not todo:
        print("[INFO] Nothing new after duplicate filtering."); return 0

    print(f"[INFO] Will process {len(todo)} item(s).")
    today=dt.datetime.now().strftime("%Y-%m-%d")
    new_rows=[]
    for i,w in enumerate(todo,1):
        try:
            pack=ask_llm(w)
            row=[pack["word_en"],pack["word_pt"],pack["sentence_pt"],pack["sentence_en"],today]
            new_rows.append(row)
            print(f"[OK] {i}/{len(todo)}  {row[0]} -> {row[1]}")
        except Exception as e:
            print(f"ERROR: LLM failed on '{w}': {e}", file=sys.stderr); return 1

    try:
        append_rows(MASTER_CSV,new_rows)
        with LAST_IMPORT.open("w",encoding="utf-8",newline="") as f:
            w=csv.writer(f); w.writerow(["word_en","word_pt","sentence_pt","sentence_en","date_added"]); w.writerows(new_rows)
        print(f"[INFO] Appended {len(new_rows)} row(s) to {MASTER_CSV}")
        print(f"[INFO] Snapshot written to {LAST_IMPORT}")
    except Exception as e:
        print(f"ERROR: Writing CSV failed: {e}", file=sys.stderr); return 1

    try:
        added,_=add_notes_to_anki(args.deck,args.model,new_rows)
        print(f"[INFO] Anki addNotes added {added}/{len(new_rows)}")
    except Exception as e:
        print(f"ERROR: Anki addNotes failed: {e}", file=sys.stderr); return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
