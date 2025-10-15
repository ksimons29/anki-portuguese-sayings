cd ~/anki-tools
cat > README.md <<'EOF'
# 🇵🇹 Anki Portuguese Sayings Generator (pt-PT)

Generate two-way Anki decks from CSV with built-in TTS (no mp3).  
Schema (fixed order): `date_added,word_pt,word_en,sentence_pt,sentence_en`.

## Usage
./import_all.sh

The script builds `decks/Portuguese_ptPT.apkg`.  
Templates include: `{{tts pt_PT voices=Joana:sentence_pt}}`.

## Layout
anki-tools/
├─ anki_from_csv_dual_audio.py
├─ import_all.sh
├─ data/ (CSV)
└─ decks/ (.apkg output)
EOF