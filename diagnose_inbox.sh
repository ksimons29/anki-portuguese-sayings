#!/usr/bin/env bash
# Diagnostic script to troubleshoot quick.jsonl loading issues

set -euo pipefail

echo "=== Portuguese Anki Pipeline Diagnostics ==="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ICLOUD_ROOT="$HOME/Library/Mobile Documents/com~apple~CloudDocs"
ANKI_DATA_DIR="$ICLOUD_ROOT/Portuguese/Anki"
INBOX_DIR="$ANKI_DATA_DIR/inbox"
QUICK="$INBOX_DIR/quick.jsonl"

# 1. Check iCloud Drive path
echo "1. Checking iCloud Drive path..."
if [[ -d "$ICLOUD_ROOT" ]]; then
  echo -e "   ${GREEN}✓${NC} iCloud root exists: $ICLOUD_ROOT"
else
  echo -e "   ${RED}✗${NC} iCloud root NOT found: $ICLOUD_ROOT"
  echo "   Alternative location:"
  ALT="$HOME/Library/CloudStorage/iCloud Drive"
  if [[ -d "$ALT" ]]; then
    echo -e "   ${YELLOW}!${NC} Found at: $ALT"
  fi
fi
echo ""

# 2. Check inbox directory
echo "2. Checking inbox directory..."
if [[ -d "$INBOX_DIR" ]]; then
  echo -e "   ${GREEN}✓${NC} Inbox directory exists: $INBOX_DIR"
  ls -lah "$INBOX_DIR"
else
  echo -e "   ${RED}✗${NC} Inbox directory NOT found: $INBOX_DIR"
fi
echo ""

# 3. Check quick.jsonl file
echo "3. Checking quick.jsonl file..."
if [[ -f "$QUICK" ]]; then
  LINES=$(wc -l < "$QUICK" | tr -d ' ')
  SIZE=$(stat -f %z "$QUICK" 2>/dev/null || stat -c %s "$QUICK" 2>/dev/null || echo "?")
  echo -e "   ${GREEN}✓${NC} File exists: $QUICK"
  echo "   Lines: $LINES"
  echo "   Size: $SIZE bytes"

  if [[ $LINES -eq 0 ]]; then
    echo -e "   ${YELLOW}!${NC} Warning: File is empty"
  else
    echo ""
    echo "   First 10 lines:"
    head -10 "$QUICK" | sed 's/^/   | /'
  fi
else
  echo -e "   ${RED}✗${NC} File NOT found: $QUICK"
fi
echo ""

# 4. Test parsing with Python
echo "4. Testing Python parser..."
if [[ -f "$QUICK" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  cd "$SCRIPT_DIR"

  PARSED=$(python3 -c "
import sys
sys.path.insert(0, '.')
from pathlib import Path
from transform_inbox_to_csv import read_quick_entries

entries = read_quick_entries(Path('$QUICK'))
print(f'{len(entries)}')
for e in entries:
    print(e)
" 2>&1)

  if [[ $? -eq 0 ]]; then
    COUNT=$(echo "$PARSED" | head -1)
    echo -e "   ${GREEN}✓${NC} Successfully parsed $COUNT entries:"
    echo "$PARSED" | tail -n +2 | sed 's/^/   - /'
  else
    echo -e "   ${RED}✗${NC} Parser failed:"
    echo "$PARSED" | sed 's/^/   | /'
  fi
else
  echo -e "   ${YELLOW}!${NC} Skipping - no quick.jsonl file to parse"
fi
echo ""

# 5. Check Python environment
echo "5. Checking Python environment..."
if [[ -d "$HOME/anki-tools/.venv" ]]; then
  echo -e "   ${GREEN}✓${NC} Virtual environment exists"
  PY="$HOME/anki-tools/.venv/bin/python"
else
  echo -e "   ${YELLOW}!${NC} No virtual environment, using system python"
  PY="$(command -v python3)"
fi
echo "   Python: $PY"
echo "   Version: $($PY --version)"
echo ""

# 6. Check required packages
echo "6. Checking required packages..."
MISSING=""
for PKG in openai requests; do
  if $PY -c "import $PKG" 2>/dev/null; then
    echo -e "   ${GREEN}✓${NC} $PKG installed"
  else
    echo -e "   ${RED}✗${NC} $PKG NOT installed"
    MISSING="$MISSING $PKG"
  fi
done

if [[ -n "$MISSING" ]]; then
  echo ""
  echo -e "   ${YELLOW}Fix:${NC} Install missing packages:"
  echo "   cd ~/anki-tools && source .venv/bin/activate && pip install$MISSING"
fi
echo ""

# 7. Check OpenAI API key
echo "7. Checking OpenAI API key..."
KEY_FOUND=""
for SVC in "anki-tools-openai" "OPENAI_API_KEY"; do
  if KEY=$(/usr/bin/security find-generic-password -a "$USER" -s "$SVC" -w 2>/dev/null); then
    PREFIX="${KEY:0:6}"
    echo -e "   ${GREEN}✓${NC} Found in Keychain ($SVC): ${PREFIX}..."
    KEY_FOUND="yes"
    break
  fi
done

if [[ -z "$KEY_FOUND" ]]; then
  if [[ -n "${OPENAI_API_KEY:-}" ]]; then
    echo -e "   ${GREEN}✓${NC} Found in environment variable"
  else
    echo -e "   ${RED}✗${NC} No API key found"
    echo "   Set with: security add-generic-password -a \"$USER\" -s \"anki-tools-openai\" -w 'sk-...' -U"
  fi
fi
echo ""

# 8. Check CSV storage
echo "8. Checking CSV storage..."
CSV="$ANKI_DATA_DIR/sayings.csv"
if [[ -f "$CSV" ]]; then
  LINES=$(wc -l < "$CSV" | tr -d ' ')
  echo -e "   ${GREEN}✓${NC} CSV exists: $CSV"
  echo "   Total lines: $LINES"
else
  echo -e "   ${YELLOW}!${NC} CSV not found (will be created): $CSV"
fi
echo ""

# 9. Check logs
echo "9. Checking recent logs..."
LOG_DIR="$ANKI_DATA_DIR/logs"
if [[ -d "$LOG_DIR" ]]; then
  TODAY=$(date +%Y-%m-%d)
  LOG_FILE="$LOG_DIR/pipeline.$TODAY.log"
  ERR_FILE="$LOG_DIR/pipeline.$TODAY.err"

  if [[ -f "$LOG_FILE" ]]; then
    LINES=$(wc -l < "$LOG_FILE" | tr -d ' ')
    echo -e "   ${GREEN}✓${NC} Today's log exists ($LINES lines)"
    echo "   Last 5 lines:"
    tail -5 "$LOG_FILE" | sed 's/^/   | /'
  else
    echo -e "   ${YELLOW}!${NC} No log for today: $LOG_FILE"
  fi

  echo ""
  if [[ -f "$ERR_FILE" ]] && [[ -s "$ERR_FILE" ]]; then
    echo -e "   ${RED}!${NC} Errors found in $ERR_FILE:"
    tail -10 "$ERR_FILE" | sed 's/^/   | /'
  fi
else
  echo -e "   ${YELLOW}!${NC} Log directory not found: $LOG_DIR"
fi
echo ""

# 10. Summary
echo "=== Summary ==="
if [[ -f "$QUICK" ]] && [[ $(wc -l < "$QUICK" | tr -d ' ') -gt 0 ]]; then
  echo -e "${GREEN}Ready to process!${NC}"
  echo ""
  echo "Run the pipeline with:"
  echo "  cd ~/anki-tools && bash run_pipeline.sh"
  echo ""
  echo "Or test in dry-run mode first:"
  echo "  cd ~/anki-tools && bash run_pipeline.sh --dry-run"
else
  echo -e "${YELLOW}No entries in quick.jsonl${NC}"
  echo "Add entries using your iPhone/iPad Shortcut or manually"
fi
echo ""
