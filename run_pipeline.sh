#!/bin/zsh
set -euo pipefail
cd ~/anki-tools
LOG_DIR="/Users/koossimons/Library/Mobile Documents/com~apple~CloudDocs/Portuguese/Anki/logs"
mkdir -p "$LOG_DIR"

echo "=== $(date) START ===" >> "$LOG_DIR/pipeline.$(date +%F).log"

/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
  ~/anki-tools/transform_inbox_to_csv.py >> "$LOG_DIR/pipeline.$(date +%F).log" 2>&1 || true

# Fallback build so you still have a deck if Anki wasn't open:
./import_all.sh >> "$LOG_DIR/pipeline.$(date +%F).log" 2>&1 || true

echo "=== $(date) DONE ===" >> "$LOG_DIR/pipeline.$(date +%F).log"
