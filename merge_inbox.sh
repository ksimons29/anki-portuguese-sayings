cat > ~/anki-tools/merge_inbox.sh <<'EOF'
#!/bin/bash
set -euo pipefail

INBOX="$HOME/Library/CloudStorage/iCloud Drive/Portuguese/Anki/inbox"
TARGET="$INBOX/quick.jsonl"
TMP="$INBOX/.quick.merge.tmp"

mkdir -p "$INBOX"
cd "$INBOX"

echo "🔎 merge_inbox: INBOX=$INBOX"
touch "$TARGET"

# be permissive: accept both *.json and *.jsonl variants commonly produced by Shortcuts
shopt -s nullglob
frags=( quick.jsonl.* quick.jsonl*.json quick.*.jsonl *.quick.jsonl *.jsonl.quick )

# filter out the main target and any archive files
filtered=()
for f in "${frags[@]}"; do
  [[ "$f" == "$(basename "$TARGET")" ]] && continue
  [[ "$f" == *.done ]] && continue
  [[ -f "$f" ]] && filtered+=( "$f" )
done

echo "🧾 merge_inbox: found ${#filtered[@]} fragment(s): ${filtered[*]:-"<none>"}"

if (( ${#filtered[@]} == 0 )); then
  echo "⚠️  merge_inbox: nothing to merge in $INBOX"
  exit 0
fi

# Merge + dedupe preserving first occurrence
cat "$TARGET" "${filtered[@]}" | awk 'NF{ if (!seen[$0]++) print $0 }' > "$TMP"
mv "$TMP" "$TARGET"
echo "✅ merge_inbox: merged ${#filtered[@]} fragment(s) into $(basename "$TARGET")"

# Archive fragments
ts=$(date +%Y%m%d-%H%M%S)
for f in "${filtered[@]}"; do
  mv "$f" "$f.$ts.done"
done
echo "🗂️  merge_inbox: archived fragments with .$ts.done suffix"
EOF

chmod +x ~/anki-tools/merge_inbox.sh