#!/bin/bash
set -euo pipefail

LOG_DIR="$HOME/Library/CloudStorage/iCloud Drive/Portuguese/Anki/logs"
INBOX="$HOME/Library/CloudStorage/iCloud Drive/Portuguese/Anki/inbox"
QUICK="$INBOX/quick.jsonl"
PY="$HOME/anki-tools/.venv/bin/python"   # <-- venv python

# If needed:
# export OPENAI_API_KEY='sk-...'
# export LLM_MODEL='gpt-4o-mini'

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

# --- locale: force UTF-8 so Python prints won't crash on curly quotes ---
export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8
export PYTHONIOENCODING=UTF-8
export PYTHONUTF8=1
# ------------------------------------------------------------------------

# Ensure Anki is open
open -gj -a "Anki" || true
sleep 2

# Merge .json + .jsonl fragments first (log stdout+stderr)
"$PY" "$HOME/anki-tools/merge_quick.py" 2>&1 | tee -a "$LOG" || true

# Transform + push to Anki (archive only on success) + log stdout+stderr
if "$PY" "$HOME/anki-tools/transform_inbox_to_csv.py" 2>&1 | tee -a "$LOG"; then
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