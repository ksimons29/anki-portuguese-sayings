#!/bin/bash
set -euo pipefail

BASE="/Users/koossimons"
TOOLS="$BASE/anki-tools"
DATA="$TOOLS/data"
DECKS="$TOOLS/decks"
PY312="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"

mkdir -p "$DECKS"
DATA="/Users/koossimons/Library/Mobile Documents/com~apple~CloudDocs/Portuguese/Anki"
"$PY312" "$TOOLS/anki_from_csv_dual_audio.py" \
  --csv "$DATA/sayings.csv" \
  --out "$DECKS/Portuguese_ptPT.apkg" \
  --deck-name "Portuguese (pt-PT)" \
  --model-name "Portuguese (pt-PT) 5-Field" \
  --tts-lang pt_PT \
  --tts-voice Joana