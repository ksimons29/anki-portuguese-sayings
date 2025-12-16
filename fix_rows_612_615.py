#!/usr/bin/env python3
"""
Fix specific rows 611-615 in Google Sheets to correct column order.
Target order: date_added, word_pt, word_en, sentence_pt, sentence_en, category
"""
import sys
sys.path.insert(0, '.')

try:
    import google_sheets
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError as e:
    print(f"ERROR: Missing module: {e}")
    sys.exit(1)

# Category classification
TOPIC_KEYWORDS = {
    "💪 Gym": ["gym", "workout", "exercise", "weight", "muscle", "treino", "músculo", "peso", "biceps", "triceps", "peito", "chest", "bíceps"],
    "❤️ Dating": ["date", "dinner", "romantic", "relationship", "love", "encontro", "jantar", "romântico", "amor"],
    "💼 Work": ["work", "office", "meeting", "email", "deadline", "trabalho", "escritório", "reunião"],
    "📋 Admin": ["form", "document", "bureaucracy", "payment", "formulário", "documento", "pagamento"],
    "🏡 Daily Life": ["home", "shopping", "cooking", "house", "kitchen", "food", "stairs", "lobby", "sunset", "statue", "soaking", "wet", "calm",
                      "compras", "casa", "cozinha", "comida", "escadas", "calmo"],
}

def classify_card(word_en: str, word_pt: str, sentence_en: str, sentence_pt: str) -> str:
    text = f"{word_en} {word_pt} {sentence_en} {sentence_pt}".lower()
    scores = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword.lower() in text)
        if score > 0:
            scores[topic] = score
    return max(scores.items(), key=lambda x: x[1])[0] if scores else "🔍 Other"

print("=== FIXING ROWS 611-615 IN GOOGLE SHEETS ===\n")

# Connect
print("[1/4] Connecting to Google Sheets...")
creds_path = google_sheets._get_credentials_path()
if not creds_path:
    print("ERROR: Credentials not found")
    sys.exit(1)

scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_file(str(creds_path), scopes=scopes)
client = gspread.authorize(credentials)
spreadsheet = client.open_by_key(google_sheets.SPREADSHEET_ID)
worksheet = spreadsheet.sheet1
print("      ✓ Connected\n")

# Read all data
print("[2/4] Reading all data...")
all_values = worksheet.get_all_values()
header = all_values[0]
print(f"      Header: {header}")
print(f"      Total rows: {len(all_values)}\n")

# Check rows 611-615 (row numbers are 1-indexed in sheets, 0-indexed in Python)
# Row 611 in sheet = index 611 in array (including header at index 0)
print("[3/4] Checking rows 611-615...")

target_rows = [611, 612, 613, 614, 615]  # Sheet row numbers
fixed_count = 0

for row_num in target_rows:
    if row_num >= len(all_values):
        print(f"      ⚠ Row {row_num} doesn't exist (only {len(all_values)} rows)")
        continue

    row = all_values[row_num]

    if not row or len(row) < 5:
        print(f"      ⚠ Row {row_num} is empty or too short")
        continue

    print(f"\n   Row {row_num} BEFORE:")
    print(f"      [0]: {row[0][:50] if row[0] else ''}...")
    print(f"      [1]: {row[1][:50] if len(row) > 1 else ''}...")
    print(f"      [2]: {row[2][:50] if len(row) > 2 else ''}...")

    # Detect if this row is in wrong order
    # Wrong order starts with word_en (English word like "sunset", "stairs", etc.)
    # Correct order starts with date (YYYY-MM-DD)

    if row[0].startswith('20'):  # Already starts with date
        print(f"      ✓ Row {row_num} already in correct order")
        continue

    # Wrong order detected: word_en, word_pt, sentence_pt, sentence_en, date_added
    print(f"      ⚠ Wrong order detected - fixing...")

    word_en = row[0].strip()
    word_pt = row[1].strip() if len(row) > 1 else ""
    sentence_pt = row[2].strip() if len(row) > 2 else ""
    sentence_en = row[3].strip() if len(row) > 3 else ""
    date_added = row[4].strip() if len(row) > 4 else ""

    # Classify
    category = classify_card(word_en, word_pt, sentence_en, sentence_pt)

    # Create correct order: date_added, word_pt, word_en, sentence_pt, sentence_en, category
    corrected_row = [date_added, word_pt, word_en, sentence_pt, sentence_en, category]

    print(f"   Row {row_num} AFTER:")
    print(f"      date_added: {date_added}")
    print(f"      word_pt:    {word_pt}")
    print(f"      word_en:    {word_en}")
    print(f"      category:   {category}")

    # Update this specific row in the sheet (row_num + 1 because gspread is 1-indexed)
    range_name = f"A{row_num + 1}:F{row_num + 1}"
    worksheet.update(range_name, [corrected_row], value_input_option="RAW")
    print(f"      ✓ Updated row {row_num}")
    fixed_count += 1

print(f"\n[4/4] Complete!")
print(f"      Fixed {fixed_count} rows\n")

print("=== VERIFICATION ===")
print("Re-reading rows 611-615 to verify...\n")

# Re-read to verify
all_values = worksheet.get_all_values()
for row_num in target_rows:
    if row_num < len(all_values):
        row = all_values[row_num]
        print(f"Row {row_num}: {row[0][:10]} | {row[1][:15]} | {row[2][:15]} | {row[5] if len(row) > 5 else 'NO CAT'}")

print("\n✓ DONE! Check your Google Sheet now.")
