#!/bin/zsh
set -euo pipefail
set -o pipefail

cd "$HOME/anki-tools"

LOG_DIR="$HOME/Library/CloudStorage/iCloud Drive/Portuguese/Anki/logs"
INBOX="$HOME/Library/CloudStorage/iCloud Drive/Portuguese/Anki/inbox"
QUICK="$INBOX/quick.jsonl"
PY="${PY:-$PWD/.venv/bin/python}"

mkdir -p "$LOG_DIR" "$INBOX"
TRANS_LOG="$LOG_DIR/transform.$(date +%Y%m%d-%H%M%S).log"

echo "=== $(date) START ===" | tee -a "$LOG_DIR/autorun.out.log"

# Ensure Anki (AnkiConnect) is up
open -gj -a "Anki" || true
sleep 2

# Merge fragments
"$HOME/anki-tools/merge_inbox.sh" | tee -a "$LOG_DIR/autorun.out.log" || true

# Nothing to do?
if [[ ! -s "$QUICK" ]]; then
  echo "No $QUICK to process" | tee -a "$LOG_DIR/autorun.out.log"
  echo "=== $(date) DONE (nothing) ===" | tee -a "$LOG_DIR/autorun.out.log"
  exit 0
fi

# Normalize Unicode (… — – etc.)
export PYTHONIOENCODING=UTF-8
export LANG=en_US.UTF-8
"$PY" ./sanitize_quick_jsonl.py "$QUICK" | tee -a "$LOG_DIR/autorun.out.log" || true

# Transform + add to Anki
if [[ -x "$PY" ]]; then
  "$PY" ./transform_inbox_to_csv.py --deck "Portuguese (pt-PT)" --model "GPT Vocabulary Automater" \
    2>&1 | tee "$TRANS_LOG"
  STATUS=${pipestatus[1]}
else
  /usr/bin/python3 ./transform_inbox_to_csv.py --deck "Portuguese (pt-PT)" --model "GPT Vocabulary Automater" \
    2>&1 | tee "$TRANS_LOG"
  STATUS=${pipestatus[1]}
fi

# If transformer failed, keep QUICK for retry
if grep -q "ERROR" "$TRANS_LOG" || [[ $STATUS -ne 0 ]]; then
  echo "Transformer failed; leaving $QUICK in place for retry" | tee -a "$LOG_DIR/autorun.out.log"
  echo "=== $(date) DONE (error) ===" | tee -a "$LOG_DIR/autorun.out.log"
  exit 1
fi

# Success → archive copy and truncate input
TS=$(date +%Y%m%d-%H%M%S)
cp "$QUICK" "$INBOX/quick.$TS.done" || true
: > "$QUICK"

echo "Archived to: $INBOX/quick.$TS.done" | tee -a "$LOG_DIR/autorun.out.log"
echo "=== $(date) DONE ===" | tee -a "$LOG_DIR/autorun.out.log"
