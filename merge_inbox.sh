#!/bin/zsh
# Merges all quick.jsonl*.json files into quick.jsonl, removing duplicates

set -euo pipefail
cd ~/Library/CloudStorage/iCloud\ Drive/Portuguese/Anki/inbox

<<<<<<< HEAD
# === CONFIG ===
INBOX="$HOME/Library/CloudStorage/iCloud Drive/Portuguese/Anki/inbox"
TARGET="$INBOX/quick.jsonl"
TEMP="$INBOX/.merged.tmp"

# Ensure target exists
touch "$TARGET"
> "$TEMP"

echo "🧩 Starting merge in: $INBOX"

# === STEP 1: Merge all quick.jsonl*.json files into quick.jsonl ===
for file in "$INBOX"/quick.jsonl*.json(.N); do
  [[ "$file" == "$TARGET" ]] && continue
  echo "📥 Merging: $file"
  cat "$file" >> "$TARGET"
  rm -f "$file"
done

# === STEP 2: Remove duplicate entries ===
# Deduplicate based on the "entries" field in JSON lines.
awk '
  BEGIN { FS="\""; }
  /"entries"/ {
    if (!seen[$4]++) print $0;
  }
' "$TARGET" > "$TEMP"

mv "$TEMP" "$TARGET"
echo "✅ Merged & deduplicated successfully → $TARGET"
=======
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
>>>>>>> f97f5f70ec95b6cfe32be61cf538e6ba4cf7821a
