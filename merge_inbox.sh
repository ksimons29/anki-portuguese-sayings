#!/bin/zsh
set -euo pipefail

# Resolve iCloud inbox (new path → legacy path → local ./inbox)
INBOX="$HOME/Library/CloudStorage/iCloud Drive/Portuguese/Anki/inbox"
if [ ! -d "$INBOX" ]; then
  INBOX="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Portuguese/Anki/inbox"
fi
if [ ! -d "$INBOX" ]; then
  INBOX="$(pwd)/inbox"
  mkdir -p "$INBOX"
fi

OUT="$INBOX/quick.jsonl"
TMP="$(mktemp)"

# Merge all .jsonl and .json (except quick.jsonl) into TMP
# Use -print0 to handle spaces safely
find "$INBOX" -maxdepth 1 -type f \( -iname '*.jsonl' -o -iname '*.json' \) ! -name 'quick.jsonl' -print0 |
while IFS= read -r -d '' f; do
  case "$f" in
    *.jsonl|*.JSONL)
      awk 'NF' "$f" >> "$TMP"
      ;;
    *.json|*.JSON)
      /usr/bin/python3 - "$f" >> "$TMP" <<'PY'
import json, sys
p = sys.argv[1]
with open(p,'r',encoding='utf-8') as fh:
    data = json.load(fh)
def emit(obj):
    print(json.dumps(obj, ensure_ascii=False))
if isinstance(data, list):
    for item in data: emit(item)
else:
    emit(data)
PY
      ;;
  esac
done

# If nothing was added, stop quietly
if [ ! -s "$TMP" ]; then
  echo "merge_inbox: nothing to merge in $INBOX"
  rm -f "$TMP"
  exit 0
fi

# De-dup and replace quick.jsonl (keep a backup)
sort -u "$TMP" > "$TMP.sorted"
if [ -s "$OUT" ]; then cp -f "$OUT" "$OUT.bak.$(date +%Y%m%d-%H%M%S)"; fi
mv -f "$TMP.sorted" "$OUT"
rm -f "$TMP"

echo "merge_inbox: wrote $(wc -l < "$OUT") lines to $OUT"
