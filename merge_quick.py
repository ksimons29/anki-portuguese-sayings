from pathlib import Path
import datetime as dt

INBOX = Path.home() / "Library/CloudStorage/iCloud Drive/Portuguese/Anki/inbox"
TARGET = INBOX / "quick.jsonl"
INBOX.mkdir(parents=True, exist_ok=True)

# collect fragments (covers quick.jsonl-6.json, quick.jsonl.json, quick-foo.jsonl, etc.)
frags = list(INBOX.glob("quick*.json")) + list(INBOX.glob("quick*.jsonl"))
frags = [f for f in frags if f.is_file() and f.name != "quick.jsonl" and not f.name.endswith(".done") and f != TARGET]
if not frags:
    print("[merge] nothing to merge"); raise SystemExit(0)

# de-dup by filename
seen = set(); unique = []
for f in sorted(frags, key=lambda p: p.name):
    if f.name in seen: continue
    seen.add(f.name); unique.append(f)

# read existing
lines, seen_lines = [], set()
if TARGET.exists():
    for line in TARGET.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and s not in seen_lines:
            seen_lines.add(s); lines.append(s)

# append from frags
for frag in unique:
    for line in frag.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and s not in seen_lines:
            seen_lines.add(s); lines.append(s)

# write back
TARGET.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

# archive the fragments
ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
for frag in unique:
    frag.rename(frag.with_name(frag.name + f".{ts}.done"))

print(f"[merge] merged {len(unique)} fragment(s) into quick.jsonl, size={TARGET.stat().st_size} bytes")
