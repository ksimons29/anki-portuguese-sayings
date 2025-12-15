#!/usr/bin/env python3
"""
Test Google Sheets connection with detailed error reporting
"""
import sys
from pathlib import Path

print("=== Google Sheets Connection Test ===\n")

# 1. Check credentials file
creds_path = Path.home() / ".config/anki-tools/credentials.json"
print(f"1. Checking credentials file: {creds_path}")
if creds_path.exists():
    print(f"   ✓ File exists ({creds_path.stat().st_size} bytes)")

    import json
    with open(creds_path) as f:
        creds_data = json.load(f)

    client_email = creds_data.get('client_email', 'NOT FOUND')
    project_id = creds_data.get('project_id', 'NOT FOUND')
    print(f"   ✓ Service account: {client_email}")
    print(f"   ✓ Project ID: {project_id}")
else:
    print(f"   ✗ File not found!")
    sys.exit(1)

print()

# 2. Check packages
print("2. Checking required packages:")
try:
    import gspread
    print(f"   ✓ gspread version {gspread.__version__}")
except ImportError as e:
    print(f"   ✗ gspread not installed: {e}")
    sys.exit(1)

try:
    from google.oauth2.service_account import Credentials
    print(f"   ✓ google-auth installed")
except ImportError as e:
    print(f"   ✗ google-auth not installed: {e}")
    sys.exit(1)

print()

# 3. Try to authenticate
print("3. Authenticating with Google Sheets API:")
try:
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    credentials = Credentials.from_service_account_file(str(creds_path), scopes=scopes)
    print(f"   ✓ Credentials loaded")

    client = gspread.authorize(credentials)
    print(f"   ✓ Client authorized")
except Exception as e:
    print(f"   ✗ Authentication failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# 4. Try to open the spreadsheet
SPREADSHEET_ID = "1q20cEuHXoaLNWJ06i1Nv9Eo2JkJ00LMmPboTYSGz1xg"
print(f"4. Opening spreadsheet: {SPREADSHEET_ID}")
try:
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    print(f"   ✓ Spreadsheet opened: {spreadsheet.title}")
    print(f"   ✓ URL: {spreadsheet.url}")

    # Get worksheets
    worksheets = spreadsheet.worksheets()
    print(f"   ✓ Found {len(worksheets)} worksheets:")
    for ws in worksheets:
        print(f"      - {ws.title} ({ws.row_count} rows x {ws.col_count} cols)")

except gspread.exceptions.SpreadsheetNotFound:
    print(f"   ✗ Spreadsheet not found (404)")
    print(f"   This means:")
    print(f"      1. The spreadsheet ID is wrong, OR")
    print(f"      2. The spreadsheet wasn't shared with: {client_email}")
    print(f"   ")
    print(f"   Please verify:")
    print(f"      - Open: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit")
    print(f"      - Click 'Share'")
    print(f"      - Verify this email has Editor access: {client_email}")
    sys.exit(1)
except Exception as e:
    print(f"   ✗ Error opening spreadsheet: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("=== SUCCESS ===")
print("Google Sheets connection is working correctly!")
