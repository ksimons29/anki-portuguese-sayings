#!/bin/zsh
set -euo pipefail

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