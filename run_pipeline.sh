#!/bin/bash
set -euo pipefail
echo "START $(date)"
echo "whoami=$(whoami)"
echo "pwd=$(pwd)"
export OPENAI_API_KEY="$(security find-generic-password -a "$USER" -s "anki-tools-openai" -w)"
echo "key_prefix=${OPENAI_API_KEY:0:6}"
unset OPENAI_BASE_URL OPENAI_API_BASE OPENAI_ORG_ID OPENAI_PROJECT
open -gj -a "Anki" || true
sleep 3
exec "$HOME/anki-tools/.venv/bin/python" -u "$HOME/anki-tools/transform_inbox_to_csv.py" \
  --deck "Portuguese (pt-PT)" --model "GPT Vocabulary Automater"
