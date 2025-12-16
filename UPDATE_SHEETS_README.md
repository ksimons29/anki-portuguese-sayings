# Google Sheets Structure Update Guide

This guide explains how to update your Portuguese Learning Word Tracker Google Sheet to match the structure specified in the README.

## What Will Change

The script will update your Google Sheets to have the following structure:

### Current Structure (Old)
- Column A: `word_en` (English word)
- Column B: `word_pt` (Portuguese word)
- Column C: `sentence_pt` (Portuguese example)
- Column D: `sentence_en` (English example)
- Column E: `date_added` (Date)
- Row 2: Redundant headers (Date, Portuguese, English, Example_PT, Example_EN)

### New Structure (Updated)
- Column A: `date_added` (YYYY-MM-DD)
- Column B: `word_pt` (Portuguese word)
- Column C: `word_en` (English word)
- Column D: `sentence_pt` (Portuguese example sentence)
- Column E: `sentence_en` (English example sentence)
- Column F: `category` (💪 Gym, ❤️ Dating, 💼 Work, 📋 Admin, 🏡 Daily Life, 🔍 Other)
- Row 2: Removed

## Categories

Cards are automatically classified into these categories based on keyword matching:

- **💪 Gym**: Fitness, workout, exercise-related words
- **❤️ Dating**: Romance, relationships, social interactions
- **💼 Work**: Office, business, professional context
- **📋 Admin**: Bureaucracy, documents, official processes
- **🏡 Daily Life**: Home, shopping, cooking, everyday activities
- **🔍 Other**: Everything else (fallback category)

## Prerequisites

Before running the update script, ensure you have:

1. **Google Sheets credentials** set up (see `GOOGLE_SHEETS_SETUP.md`)
2. **Anki running** with AnkiConnect enabled (optional but recommended)
3. **Python dependencies** installed:
   ```bash
   pip install gspread google-auth
   ```

## Running the Update Script

### Step 1: Verify Prerequisites

Check if credentials are available:
```bash
ls ~/.config/anki-tools/credentials.json
```

Check if Anki is running:
```bash
curl http://127.0.0.1:8765 -X POST -d '{"action":"version","version":6}'
```

### Step 2: Run the Update Script

```bash
cd ~/anki-portuguese-sayings
python3 update_sheets_structure.py
```

### Step 3: Verify Results

The script will:
1. Connect to your Google Sheet
2. Read all current data
3. Load cards from Anki (if running)
4. Reorder columns to the new structure
5. Remove the redundant second row
6. Classify all cards into categories
7. Add any missing Anki cards to the sheet
8. Write everything back with the new structure

You should see output like:
```
=== UPDATING GOOGLE SHEETS STRUCTURE ===

[1/6] Connecting to Google Sheets...
      ✓ Connected

[2/6] Reading current data from Google Sheets...
      ✓ Found 150 rows
      ✓ Detected redundant second row, will remove it
      ✓ Parsed 148 valid data rows

[3/6] Loading cards from Anki deck...
[anki] Connecting to Anki deck: Portuguese Mastery (pt-PT)
[anki] Found 150 notes in deck
[anki] Loaded 150 valid cards
      ✓ Loaded 150 cards from Anki

[4/6] Merging data and adding missing Anki cards...
      ✓ Added 2 missing cards from Anki
      ✓ Total cards: 150

[5/6] Classifying cards and adding categories...
      ✓ Categories assigned

[6/6] Writing updated data to Google Sheets...
      ✓ Cleared existing data
      ✓ Written 150 rows with new structure

=== UPDATE COMPLETE ===

Summary:
  • Total rows: 150
  • New cards from Anki: 2
  • Column order: date_added, word_pt, word_en, sentence_pt, sentence_en, category

Category breakdown:
  • 💪 Gym: 45
  • 💼 Work: 32
  • 🏡 Daily Life: 28
  • 📋 Admin: 22
  • ❤️ Dating: 15
  • 🔍 Other: 8
```

## Troubleshooting

### Error: "Google Sheets credentials not found"

**Solution:** Set up credentials following `GOOGLE_SHEETS_SETUP.md`

```bash
mkdir -p ~/.config/anki-tools
# Move your downloaded credentials file
mv ~/Downloads/your-project-xxxxx.json ~/.config/anki-tools/credentials.json
```

### Error: "Could not connect to Anki"

**Solution:** Make sure Anki is running. If Anki is not available, the script will continue but won't add missing cards from Anki.

```bash
# Open Anki first
open -a Anki
# Wait a few seconds, then run the script
python3 update_sheets_structure.py
```

### Error: "Spreadsheet not found"

**Solution:** Verify the spreadsheet ID in `google_sheets.py` matches your sheet:
```python
SPREADSHEET_ID = "1q20cEuHXoaLNWJ06i1Nv9Eo2JkJ00LMmPboTYSGz1xg"
```

Also ensure you've shared the spreadsheet with your service account email.

### Warning: Some categories seem wrong

**Solution:** The categories are assigned based on keyword matching. You can:
1. Manually adjust categories in the Google Sheet after the update
2. Or modify the keyword lists in `update_sheets_structure.py` and re-run

## Manual Alternative

If you prefer to update the sheet manually:

1. **Insert a new column F** for categories
2. **Cut and paste** to reorder columns: A→E, B→A, C→B, old A→C, old E→D
3. **Delete row 2** (the redundant header row)
4. **Update the header row** to: `date_added`, `word_pt`, `word_en`, `sentence_pt`, `sentence_en`, `category`
5. **Manually assign categories** or leave them blank

## Next Steps

After updating the sheet:

1. **Verify the data** looks correct in Google Sheets
2. **Update any scripts** that reference the old column order
3. **Run the dashboard** to see your categorized vocabulary:
   ```bash
   cd ~/anki-tools
   python3 generate_dashboard_html.py
   ```

## Support

For issues or questions:
- Check `GOOGLE_SHEETS_SETUP.md` for Google Sheets setup
- Check `README.md` for overall project documentation
- Report issues at: https://github.com/ksimons29/anki-portuguese-sayings/issues
