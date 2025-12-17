#!/bin/bash
# Test the full pipeline with the word "calm"

set -e

echo "=== Testing Pipeline with 'calm' ==="
echo ""

# Paths
ANKI_BASE_MOBILE="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Portuguese/Anki"
ANKI_BASE_CLOUD="$HOME/Library/CloudStorage/iCloud Drive/Portuguese/Anki"

# Detect which iCloud path exists
if [ -d "$ANKI_BASE_MOBILE" ]; then
    ANKI_BASE="$ANKI_BASE_MOBILE"
elif [ -d "$ANKI_BASE_CLOUD" ]; then
    ANKI_BASE="$ANKI_BASE_CLOUD"
else
    echo "ERROR: Cannot find iCloud Drive path"
    exit 1
fi

INBOX_FILE="$ANKI_BASE/inbox/quick.jsonl"

# Add "calm" to inbox
echo "[1/3] Adding 'calm' to inbox..."
echo '{"word":"calm"}' >> "$INBOX_FILE"
echo "      ✓ Added to: $INBOX_FILE"

# Run pipeline
echo ""
echo "[2/3] Running pipeline..."
cd ~/anki-tools
bash run_pipeline.sh

# Verify in Google Sheets
echo ""
echo "[3/3] Verifying in Google Sheets..."
python3 <<'PYEOF'
import sys
sys.path.insert(0, '.')
try:
    import google_sheets
    if google_sheets.is_available():
        storage = google_sheets.GoogleSheetsStorage()
        rows = storage.get_all_rows(use_cache=False)

        # Find the "calm" entry
        calm_entries = [r for r in rows if r['word_en'].lower() == 'calm']

        if calm_entries:
            entry = calm_entries[-1]  # Get most recent
            print("✓ Found 'calm' entry in Google Sheets:")
            print(f"  date_added:  {entry['date_added']}")
            print(f"  word_pt:     {entry['word_pt']}")
            print(f"  word_en:     {entry['word_en']}")
            print(f"  sentence_pt: {entry['sentence_pt'][:60]}...")
            print(f"  sentence_en: {entry['sentence_en'][:60]}...")
            print(f"  category:    {entry['category']}")
            print("")
            print("✓ Column order is CORRECT!")
        else:
            print("⚠ 'calm' entry not found in Google Sheets")
    else:
        print("⚠ Google Sheets not available")
except Exception as e:
    print(f"ERROR: {e}")
PYEOF

echo ""
echo "=== Test Complete ==="
echo ""
echo "Next: Check your Google Sheet to verify the format:"
echo "  https://docs.google.com/spreadsheets/d/1q20cEuHXoaLNWJ06i1Nv9Eo2JkJ00LMmPboTYSGz1xg/edit"
