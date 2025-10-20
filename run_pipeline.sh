#!/bin/bash
set -euo pipefail

LOG_DIR="$HOME/Library/CloudStorage/iCloud Drive/Portuguese/Anki/logs"
INBOX="$HOME/Library/CloudStorage/iCloud Drive/Portuguese/Anki/inbox"
QUICK="$INBOX/quick.jsonl"
mkdir -p "$LOG_DIR" "$INBOX"

LOG="$LOG_DIR/$(date +%F).log"
echo "=== $(date) START ===" | tee -a "$LOG"

# ---- prevent overlapping runs ----
LOCKDIR="$INBOX/.pipeline.lock"
if ! mkdir "$LOCKDIR" 2>/dev/null; then
  echo "Another pipeline run is already active; exiting." | tee -a "$LOG"
  exit 0
fi
trap 'rmdir "$LOCKDIR"' EXIT
# ----------------------------------

# Ensure Anki is open
open -gj -a "Anki" || true
sleep 2

# Always merge .json + .jsonl fragments first (replaces old merge_inbox.sh)
"$HOME/anki-tools/.venv/bin/python" "$HOME/anki-tools/merge_quick.py" || true

# Transform + push to Anki
"$HOME/anki-tools/.venv/bin/python" "$HOME/anki-tools/transform_inbox_to_csv.py" | tee -a "$LOG" || true

# Optionally snapshot current quick.jsonl (if it exists & non-empty)
if [[ -s "$QUICK" ]]; then
  ts=$(date +%Y%m%d-%H%M%S)
  cp "$QUICK" "$INBOX/quick.$ts.done" || true
  : > "$QUICK" || true
  echo "Archived to: $INBOX/quick.$ts.done" | tee -a "$LOG"
fi

echo "=== $(date) DONE ===" | tee -a "$LOG"
