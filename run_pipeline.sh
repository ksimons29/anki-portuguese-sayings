#!/bin/bash
set -euo pipefail

# --- BASE PATH (Mobile Documents – your preferred folder) ---
export ANKI_BASE="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Portuguese/Anki"

LOG_DIR="$ANKI_BASE/logs"
INBOX="$ANKI_BASE/inbox"
QUICK="$INBOX/quick.jsonl"
PY="$HOME/anki-tools/.venv/bin/python"   # venv python

# If the agent's environment doesn't provide it, uncomment and set your key:
# export OPENAI_API_KEY='sk-...'

mkdir -p "$LOG_DIR" "$INBOX"
LOG="$LOG_DIR/$(date +%F).log"
echo "=== $(date) START ===" | tee -a "$LOG"
echo "[paths] ANKI_BASE=$ANKI_BASE" | tee -a "$LOG"

# ---- prevent overlapping runs ----
LOCKDIR="$INBOX/.pipeline.lock"
if ! mkdir "$LOCKDIR" 2>/dev/null; then
  echo "Another pipeline run is already active; exiting." | tee -a "$LOG"
  exit 0
fi
trap 'rmdir "$LOCKDIR"' EXIT

# --- locale: force UTF-8 so Python prints won't crash on curly quotes ---
export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8
export PYTHONIOENCODING=UTF-8
export PYTHONUTF8=1

# Ensure Anki is open
open -gj -a "Anki" || true
sleep 2

# Merge .json + .jsonl fragments first (and log it)
$PY "$HOME/anki-tools/merge_quick.py" | tee -a "$LOG" || true

# Transform + push to Anki (archive only on success)
if $PY "$HOME/anki-tools/transform_inbox_to_csv.py" | tee -a "$LOG"; then
  if [[ -s "$QUICK" ]]; then
    ts=$(date +%Y%m%d-%H%M%S)
    cp "$QUICK" "$INBOX/quick.$ts.done" || true
    : > "$QUICK" || true
    echo "Archived to: $INBOX/quick.$ts.done" | tee -a "$LOG"
  fi
else
  echo "[ERROR] transform failed; leaving $QUICK untouched for retry" | tee -a "$LOG"
  exit 1
fi

echo "=== $(date) DONE ===" | tee -a "$LOG"