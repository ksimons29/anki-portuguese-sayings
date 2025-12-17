#!/bin/bash
# Quick setup and run script for updating Google Sheets structure

set -e

ANKI_TOOLS_DIR="$HOME/anki-tools"
SCRIPT_NAME="update_sheets_structure.py"
GOOGLE_SHEETS_MODULE="google_sheets.py"
BRANCH="claude/update-sheets-categories-G5NcS"

echo "=== Google Sheets Structure Update Setup ==="
echo ""

# Check if anki-tools directory exists
if [ ! -d "$ANKI_TOOLS_DIR" ]; then
    echo "ERROR: $ANKI_TOOLS_DIR does not exist"
    echo "Please create it first or adjust ANKI_TOOLS_DIR in this script"
    exit 1
fi

cd "$ANKI_TOOLS_DIR"
echo "[1/5] Working directory: $ANKI_TOOLS_DIR"

# Download the update script
echo ""
echo "[2/5] Downloading update script..."
curl -L -o "$SCRIPT_NAME" "https://raw.githubusercontent.com/ksimons29/anki-portuguese-sayings/$BRANCH/$SCRIPT_NAME"
chmod +x "$SCRIPT_NAME"
echo "      ✓ Downloaded $SCRIPT_NAME"

# Download the updated google_sheets.py module
echo ""
echo "[3/5] Downloading updated google_sheets.py module..."
curl -L -o "$GOOGLE_SHEETS_MODULE" "https://raw.githubusercontent.com/ksimons29/anki-portuguese-sayings/$BRANCH/$GOOGLE_SHEETS_MODULE"
echo "      ✓ Downloaded $GOOGLE_SHEETS_MODULE"

# Check prerequisites
echo ""
echo "[4/5] Checking prerequisites..."

# Check credentials
if [ -f "$HOME/.config/anki-tools/credentials.json" ]; then
    echo "      ✓ Google Sheets credentials found"
elif [ -n "$GOOGLE_SHEETS_CREDENTIALS" ] && [ -f "$GOOGLE_SHEETS_CREDENTIALS" ]; then
    echo "      ✓ Google Sheets credentials found at $GOOGLE_SHEETS_CREDENTIALS"
else
    echo "      ⚠ WARNING: Google Sheets credentials not found"
    echo "        Set up credentials following: https://github.com/ksimons29/anki-portuguese-sayings/blob/main/GOOGLE_SHEETS_SETUP.md"
    echo ""
    read -p "Do you want to continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if Anki is running
echo ""
if curl -s http://127.0.0.1:8765 -X POST -d '{"action":"version","version":6}' > /dev/null 2>&1; then
    echo "      ✓ Anki is running (will sync cards from Anki)"
else
    echo "      ⚠ Anki is not running (will only update existing Google Sheets data)"
    echo "        To include Anki cards, open Anki and run this script again"
    echo ""
    read -p "Do you want to continue without Anki? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        echo "Opening Anki... Please wait a few seconds then run this script again."
        open -a Anki
        exit 0
    fi
fi

# Check Python dependencies
echo ""
if python3 -c "import gspread; import google.oauth2.service_account" 2>/dev/null; then
    echo "      ✓ Python dependencies installed"
else
    echo "      ⚠ Installing required Python packages..."
    pip3 install gspread google-auth
fi

# Run the update script
echo ""
echo "[5/5] Running update script..."
echo "======================================"
echo ""

python3 "$SCRIPT_NAME"

echo ""
echo "======================================"
echo ""
echo "✓ Update complete!"
echo ""
echo "Next steps:"
echo "  1. Check your Google Sheet to verify the changes"
echo "  2. Review the category assignments"
echo "  3. View your dashboard: cd ~/anki-tools && python3 generate_dashboard_html.py"
echo ""
