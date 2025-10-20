#!/bin/zsh
# Merges all quick.jsonl*.json files into quick.jsonl, removing duplicates

set -euo pipefail
cd ~/Library/CloudStorage/iCloud\ Drive/Portuguese/Anki/inbox

OUT="quick.jsonl"
TMP="merged.tmp"

# Merge and deduplicate
cat quick.jsonl*.json 2>/dev/null | jq -s 'unique' > "$TMP" || exit 0

# If non-empty, save to main quick.jsonl
if [ -s "$TMP" ]; then
  cp "$TMP" "$OUT"
  echo "✅ Merged into $OUT"
else
  echo "⚠️ No files to merge"
fi

# Archive old fragments
TS=$(date +%Y%m%d-%H%M%S)
for f in quick.jsonl*.json; do
  [ -e "$f" ] && mv "$f" "$f.$TS.done"
done

rm -f "$TMP"
