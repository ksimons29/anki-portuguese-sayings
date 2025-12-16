#!/usr/bin/env python3
"""
Find and fix the "stairs" row to correct column order.
"""
import sys
sys.path.insert(0, '.')

try:
    import google_sheets
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError as e:
    print(f"ERROR: {e}")
    sys.exit(1)

print("=== FIXING 'STAIRS' ROW ===\n")

# Connect
print("[1/3] Connecting to Google Sheets...")
creds_path = google_sheets._get_credentials_path()
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_file(str(creds_path), scopes=scopes)
client = gspread.authorize(credentials)
worksheet = client.open_by_key(google_sheets.SPREADSHEET_ID).sheet1
print("      ✓ Connected\n")

# Find the stairs row
print("[2/3] Finding 'stairs' row...")
all_values = worksheet.get_all_values()

stairs_row_index = None
for i, row in enumerate(all_values):
    if any('stairs' in str(cell).lower() or 'escadas' in str(cell).lower() for cell in row):
        # Check if it's in wrong order (starts with "stairs" not date)
        if row and row[0].lower() == 'stairs':
            stairs_row_index = i
            print(f"      Found at row {i + 1} (sheet row {i + 1})")
            print(f"\n      Current order:")
            print(f"        [0]: {row[0]}")
            print(f"        [1]: {row[1]}")
            print(f"        [2]: {row[2][:50]}...")
            print(f"        [3]: {row[3][:50]}...")
            print(f"        [4]: {row[4]}")
            print(f"        [5]: {row[5] if len(row) > 5 else 'NO CATEGORY'}")
            break

if stairs_row_index is None:
    print("      ✗ 'stairs' row not found or already in correct order")
    sys.exit(0)

# Extract data (currently in wrong order)
row = all_values[stairs_row_index]
# Current: word_en, word_pt, sentence_pt, sentence_en, date_added, category
word_en = row[0].strip()        # stairs
word_pt = row[1].strip()        # escadas
sentence_pt = row[2].strip()    # As escadas...
sentence_en = row[3].strip()    # The stairs...
date_added = row[4].strip()     # 2025-12-16
category = row[5].strip() if len(row) > 5 else "🏡 Daily Life"

# Correct order: date_added, word_pt, word_en, sentence_pt, sentence_en, category
corrected_row = [date_added, word_pt, word_en, sentence_pt, sentence_en, category]

print(f"\n[3/3] Fixing to correct order...")
print(f"      Corrected order:")
print(f"        date_added:  {date_added}")
print(f"        word_pt:     {word_pt}")
print(f"        word_en:     {word_en}")
print(f"        sentence_pt: {sentence_pt[:50]}...")
print(f"        sentence_en: {sentence_en[:50]}...")
print(f"        category:    {category}")

# Update the row (gspread uses 1-based indexing)
sheet_row_num = stairs_row_index + 1
range_name = f"A{sheet_row_num}:F{sheet_row_num}"
worksheet.update(range_name, [corrected_row], value_input_option="RAW")

print(f"\n      ✓ Updated row {sheet_row_num}")

# Verify
all_values = worksheet.get_all_values()
verified_row = all_values[stairs_row_index]
print(f"\n=== VERIFICATION ===")
print(f"Row {sheet_row_num} now: {verified_row[0]} | {verified_row[1]} | {verified_row[2]} | {verified_row[5]}")
print("\n✓ DONE! Check your Google Sheet.")
