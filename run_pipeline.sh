#!/bin/bash
set -euo pipefail
# -e  : exit immediately if a command exits with a non-zero status
# -u  : treat unset variables as an error and exit
# -o pipefail : ensures the whole pipeline fails if any command fails

# ---- Basic diagnostic output (helps debugging LaunchAgent runs) ----
echo "START $(date)"         # Logs the exact start time of the run
echo "whoami=$(whoami)"      # Shows which user account is running the script (should be your macOS user)
echo "pwd=$(pwd)"            # Prints the current working directory from which the script is executed

# ---- Detect if this run likely happened right after wake from sleep ----
# Uses the macOS power log (pmset) to check if the system recently woke up.
# If a "Wake from Sleep" event appears in the last ~80 lines, it logs a note.
# This helps you see in your log when a run was triggered right after opening your MacBook.
if pmset -g log | tail -n 80 | grep -q "Wake from Sleep"; then
  echo "[info] Detected recent system wake; this run may be a catch-up after sleep."
fi

# ---- Retrieve and load the OpenAI API key securely from the macOS Keychain ----
# The key was previously stored under the service name "anki-tools-openai".
export OPENAI_API_KEY="$(security find-generic-password -a "$USER" -s "anki-tools-openai" -w)"
echo "key_prefix=${OPENAI_API_KEY:0:6}"   # Log only the first 6 characters for quick sanity check
unset OPENAI_BASE_URL OPENAI_API_BASE OPENAI_ORG_ID OPENAI_PROJECT  # Clear possible env leftovers

# ---- Ensure Anki is open (quietly launches the app if not already running) ----
# The "-gj" flags open the app in the background without switching focus.
open -gj -a "Anki" || true
sleep 3   # Wait a few seconds to ensure Anki and AnkiConnect are ready

# ---- Run the main Python transformer that handles the Anki Automator ----
# This script processes your iCloud inbox, generates C1 Portuguese sentences, 
# and pushes them automatically into your Anki deck via AnkiConnect.
exec "$HOME/anki-tools/.venv/bin/python" -u "$HOME/anki-tools/transform_inbox_to_csv.py" \
  --deck "Portuguese (pt-PT)" --model "GPT Vocabulary Automater"