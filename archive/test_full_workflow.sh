#!/bin/bash
# Full workflow test: quick.jsonl → Anki → Google Sheets → Dashboard
# This script tests the complete pipeline end-to-end

set -e

echo "=== FULL WORKFLOW TEST ==="
echo ""

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Paths
ANKI_TOOLS_DIR="$HOME/anki-tools"
ANKI_BASE_MOBILE="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Portuguese/Anki"
ANKI_BASE_CLOUD="$HOME/Library/CloudStorage/iCloud Drive/Portuguese/Anki"

# Detect which iCloud path exists
if [ -d "$ANKI_BASE_MOBILE" ]; then
    ANKI_BASE="$ANKI_BASE_MOBILE"
    echo "Using iCloud path: $ANKI_BASE_MOBILE"
elif [ -d "$ANKI_BASE_CLOUD" ]; then
    ANKI_BASE="$ANKI_BASE_CLOUD"
    echo "Using iCloud path: $ANKI_BASE_CLOUD"
else
    echo -e "${RED}ERROR: Cannot find iCloud Drive path${NC}"
    echo "Please create: $ANKI_BASE_MOBILE"
    exit 1
fi

INBOX_DIR="$ANKI_BASE/inbox"
QUICK_JSONL="$INBOX_DIR/quick.jsonl"
SAYINGS_CSV="$ANKI_BASE/sayings.csv"
DASHBOARD_HTML="$ANKI_BASE/Portuguese-Dashboard.html"

# Step 1: Check prerequisites
echo ""
echo "=== [1/6] CHECKING PREREQUISITES ==="
echo ""

# Check Anki
if curl -s http://127.0.0.1:8765 -X POST -d '{"action":"version","version":6}' > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Anki is running"
else
    echo -e "${YELLOW}⚠${NC} Anki is not running"
    echo "  Opening Anki... Please wait for it to start."
    open -a Anki
    echo "  Waiting 5 seconds for Anki to start..."
    sleep 5

    if curl -s http://127.0.0.1:8765 -X POST -d '{"action":"version","version":6}' > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Anki is now running"
    else
        echo -e "${RED}✗${NC} Failed to start Anki. Please start it manually and run this script again."
        exit 1
    fi
fi

# Check Google Sheets credentials
if [ -f "$HOME/.config/anki-tools/credentials.json" ]; then
    echo -e "${GREEN}✓${NC} Google Sheets credentials found"
elif [ -n "$GOOGLE_SHEETS_CREDENTIALS" ] && [ -f "$GOOGLE_SHEETS_CREDENTIALS" ]; then
    echo -e "${GREEN}✓${NC} Google Sheets credentials found at $GOOGLE_SHEETS_CREDENTIALS"
else
    echo -e "${YELLOW}⚠${NC} Google Sheets credentials not found (continuing without Sheets sync)"
fi

# Check Python dependencies
if python3 -c "import gspread; from google.oauth2.service_account import Credentials" 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Python dependencies installed"
else
    echo -e "${YELLOW}⚠${NC} Installing Python dependencies..."
    pip3 install gspread google-auth
fi

# Step 2: Check current inbox
echo ""
echo "=== [2/6] CHECKING INBOX ==="
echo ""

mkdir -p "$INBOX_DIR"

if [ -f "$QUICK_JSONL" ]; then
    LINE_COUNT=$(wc -l < "$QUICK_JSONL" | tr -d ' ')
    echo "Current inbox: $QUICK_JSONL"
    echo "Entries in inbox: $LINE_COUNT"
    echo ""
    echo "Current entries:"
    cat "$QUICK_JSONL" | head -20
    echo ""
else
    echo "No inbox file exists yet. Creating sample entries..."
    cat > "$QUICK_JSONL" <<'EOF'
{"word":"bíceps"}
{"word":"peito"}
{"word":"guardar"}
{"word":"rodeado"}
{"word":"enrolar"}
EOF
    echo "Created sample inbox with 5 test entries"
    echo ""
    cat "$QUICK_JSONL"
    echo ""
fi

# Count entries before
if [ -f "$SAYINGS_CSV" ]; then
    BEFORE_COUNT=$(wc -l < "$SAYINGS_CSV" | tr -d ' ')
    BEFORE_COUNT=$((BEFORE_COUNT - 1))  # Subtract header
else
    BEFORE_COUNT=0
fi

echo "Cards in sayings.csv before: $BEFORE_COUNT"

# Step 3: Run the pipeline
echo ""
echo "=== [3/6] RUNNING PIPELINE ==="
echo ""

cd "$ANKI_TOOLS_DIR"

if [ ! -f "run_pipeline.sh" ]; then
    echo -e "${RED}ERROR: run_pipeline.sh not found in $ANKI_TOOLS_DIR${NC}"
    exit 1
fi

echo "Running: bash run_pipeline.sh"
echo "----------------------------------------"
bash run_pipeline.sh
echo "----------------------------------------"

# Count entries after
if [ -f "$SAYINGS_CSV" ]; then
    AFTER_COUNT=$(wc -l < "$SAYINGS_CSV" | tr -d ' ')
    AFTER_COUNT=$((AFTER_COUNT - 1))  # Subtract header
else
    AFTER_COUNT=0
fi

NEW_ENTRIES=$((AFTER_COUNT - BEFORE_COUNT))

echo ""
echo -e "${GREEN}✓${NC} Pipeline completed"
echo "Cards in sayings.csv after: $AFTER_COUNT"
echo "New cards added: $NEW_ENTRIES"

# Step 4: Verify in Anki
echo ""
echo "=== [4/6] VERIFYING IN ANKI ==="
echo ""

# Get count from Anki
ANKI_COUNT=$(curl -s http://127.0.0.1:8765 -X POST -d '{
    "action": "findNotes",
    "version": 6,
    "params": {"query": "deck:\"Portuguese Mastery (pt-PT)\""}
}' | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('result', [])))")

echo "Total cards in Anki deck: $ANKI_COUNT"

# Get the most recent cards
echo ""
echo "Most recent cards in Anki:"
curl -s http://127.0.0.1:8765 -X POST -d '{
    "action": "findNotes",
    "version": 6,
    "params": {"query": "deck:\"Portuguese Mastery (pt-PT)\" added:1"}
}' | python3 -c "
import sys, json
data = json.load(sys.stdin)
note_ids = data.get('result', [])[-5:]  # Last 5
print(f'Found {len(note_ids)} cards added today')
"

echo -e "${GREEN}✓${NC} Anki verification complete"

# Step 5: Verify in Google Sheets
echo ""
echo "=== [5/6] VERIFYING IN GOOGLE SHEETS ==="
echo ""

if python3 -c "import google_sheets" 2>/dev/null; then
    cd "$ANKI_TOOLS_DIR"

    python3 <<'PYEOF'
import sys
sys.path.insert(0, '.')
try:
    import google_sheets
    if google_sheets.is_available():
        storage = google_sheets.GoogleSheetsStorage()
        rows = storage.get_all_rows(use_cache=False)
        print(f"Total rows in Google Sheets: {len(rows)}")

        # Show last 5 entries
        print("\nMost recent entries:")
        for row in rows[-5:]:
            print(f"  • {row['word_pt']:15} ({row['word_en']:15}) - {row['category']}")

        # Show category breakdown
        from collections import Counter
        categories = Counter(row['category'] for row in rows)
        print("\nCategory breakdown:")
        for cat, count in sorted(categories.items()):
            print(f"  {cat}: {count}")

        print("\n✓ Google Sheets verification complete")
    else:
        print("⚠ Google Sheets not available (credentials not configured)")
except Exception as e:
    print(f"⚠ Could not verify Google Sheets: {e}")
PYEOF
else
    echo -e "${YELLOW}⚠${NC} google_sheets module not available"
fi

# Step 6: Generate and check dashboard
echo ""
echo "=== [6/6] GENERATING DASHBOARD ==="
echo ""

cd "$ANKI_TOOLS_DIR"

if [ -f "generate_dashboard_html.py" ]; then
    echo "Running dashboard generator..."
    python3 generate_dashboard_html.py

    if [ -f "$DASHBOARD_HTML" ]; then
        echo -e "${GREEN}✓${NC} Dashboard generated: $DASHBOARD_HTML"

        # Count categories in dashboard
        echo ""
        echo "Dashboard statistics:"
        grep -o 'class="category-header">[^<]*' "$DASHBOARD_HTML" | head -10 || true

        # Open dashboard
        echo ""
        echo "Opening dashboard in browser..."
        open "$DASHBOARD_HTML"
    else
        echo -e "${YELLOW}⚠${NC} Dashboard file not found"
    fi
else
    echo -e "${YELLOW}⚠${NC} generate_dashboard_html.py not found"
fi

# Summary
echo ""
echo "=== TEST COMPLETE ==="
echo ""
echo "Summary:"
echo "  • CSV entries: $BEFORE_COUNT → $AFTER_COUNT (added $NEW_ENTRIES)"
echo "  • Anki cards: $ANKI_COUNT"
echo "  • Google Sheets: Check browser"
echo "  • Dashboard: Check browser"
echo ""
echo "Verification steps:"
echo "  1. Check Anki app - search for your new words"
echo "  2. Check Google Sheets - verify columns: date_added, word_pt, word_en, sentence_pt, sentence_en, category"
echo "  3. Check Dashboard - verify categories and search functionality"
echo ""
echo -e "${GREEN}✓ All systems tested!${NC}"
