# Google Sheets Setup Guide

This guide walks you through setting up Google Sheets as the storage backend for Portuguese vocabulary.

## Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Create Project" or select an existing project
3. Name it something like "Anki Portuguese Tools"

## Step 2: Enable Google Sheets API

1. In the Cloud Console, go to "APIs & Services" > "Enable APIs and Services"
2. Search for "Google Sheets API"
3. Click "Enable"

## Step 3: Create a Service Account

1. Go to "APIs & Services" > "Credentials"
2. Click "Create Credentials" > "Service Account"
3. Name it (e.g., "anki-sheets-access")
4. Click "Create and Continue"
5. Skip the optional steps and click "Done"

## Step 4: Generate and Download Key

1. Click on the service account you just created
2. Go to the "Keys" tab
3. Click "Add Key" > "Create new key"
4. Choose "JSON" format
5. Click "Create" - this downloads your credentials file

## Step 5: Save Credentials

Save the downloaded JSON file to one of these locations:
- `~/.config/anki-tools/credentials.json` (recommended)
- Set `GOOGLE_SHEETS_CREDENTIALS` environment variable to the file path

```bash
# Create config directory
mkdir -p ~/.config/anki-tools

# Move the downloaded file
mv ~/Downloads/your-project-xxxxx.json ~/.config/anki-tools/credentials.json
```

## Step 6: Share Your Spreadsheet

1. Open your Google Spreadsheet: https://docs.google.com/spreadsheets/d/1q20cEuHXoaLNWJ06i1Nv9Eo2JkJ00LMmPboTYSGz1xg/edit
2. Click "Share" button
3. Add the service account email (found in the JSON file as `client_email`, looks like: `service-account-name@project-id.iam.gserviceaccount.com`)
4. Give it "Editor" access
5. Click "Share"

## Step 7: Test the Connection

```bash
python3 google_sheets.py
```

You should see:
```
Testing Google Sheets connection...
Successfully connected! Found X rows.
```

## Spreadsheet Format

The spreadsheet should have these columns (in order):
- A: word_en (English word)
- B: word_pt (Portuguese word)
- C: sentence_pt (Portuguese example sentence)
- D: sentence_en (English translation)
- E: date_added (YYYY-MM-DD)

The first row should contain headers.

## Environment Variables

You can also configure the integration using environment variables:

```bash
# Path to credentials file
export GOOGLE_SHEETS_CREDENTIALS=/path/to/credentials.json

# Force use of CSV instead of Google Sheets
export USE_CSV=1
```

## Troubleshooting

### "Could not find credentials"
- Ensure the credentials file exists at `~/.config/anki-tools/credentials.json`
- Or set `GOOGLE_SHEETS_CREDENTIALS` environment variable

### "Permission denied"
- Make sure you shared the spreadsheet with the service account email
- The service account needs "Editor" access

### "Spreadsheet not found"
- Verify the spreadsheet ID is correct in `google_sheets.py`
- Current ID: `1q20cEuHXoaLNWJ06i1Nv9Eo2JkJ00LMmPboTYSGz1xg`
