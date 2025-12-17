#!/usr/bin/env python3
"""
Fix row 611 specifically - force fix regardless of detection
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

print("=== EXAMINING AND FIXING ROW 611 ===\n")

# Connect
print("[1/3] Connecting...")
creds_path = google_sheets._get_credentials_path()
scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_file(str(creds_path), scopes=scopes)
client = gspread.authorize(credentials)
worksheet = client.open_by_key(google_sheets.SPREADSHEET_ID).sheet1
print("      ✓ Connected\n")

# Read row 611
print("[2/3] Reading row 611...")
all_values = worksheet.get_all_values()
row_611 = all_values[611] if len(all_values) > 611 else []

if not row_611:
    print("ERROR: Row 611 doesn't exist")
    sys.exit(1)

print(f"\nCurrent row 611 data:")
print(f"  Column A (index 0): '{row_611[0][:50] if row_611[0] else 'EMPTY'}'")
print(f"  Column B (index 1): '{row_611[1][:50] if len(row_611) > 1 else 'EMPTY'}'")
print(f"  Column C (index 2): '{row_611[2][:50] if len(row_611) > 2 else 'EMPTY'}'")
print(f"  Column D (index 3): '{row_611[3][:50] if len(row_611) > 3 else 'EMPTY'}'")
print(f"  Column E (index 4): '{row_611[4][:50] if len(row_611) > 4 else 'EMPTY'}'")
print(f"  Column F (index 5): '{row_611[5][:50] if len(row_611) > 5 else 'EMPTY'}'")

# Determine if it needs fixing
# Correct format: date_added, word_pt, word_en, sentence_pt, sentence_en, category
# Wrong format: word_en, word_pt, sentence_pt, sentence_en, date_added

# Check if column A is a date (starts with 20) or a word
is_date_first = row_611[0].startswith('20') if row_611[0] else False

print(f"\nDetected format:")
if is_date_first:
    print("  ✓ Appears to be correct (starts with date)")
    print("  However, let's verify columns B and C...")
    print(f"  Column B should be word_pt (Portuguese): '{row_611[1][:30]}'")
    print(f"  Column C should be word_en (English): '{row_611[2][:30]}'")

    # Double check - if column B looks like English and C looks like Portuguese, it's wrong
    # Simple heuristic: check for common Portuguese letters in expected position
    response = input("\nDoes this look WRONG (column B is English when it should be Portuguese)? (y/n): ")
    if response.lower() != 'y':
        print("Skipping row 611 - appears correct")
        sys.exit(0)
    needs_fix = True
else:
    print("  ✗ WRONG format (starts with word_en)")
    needs_fix = True

if not needs_fix:
    print("Row 611 is already correct!")
    sys.exit(0)

# Fix it
print("\n[3/3] Fixing row 611...")

# Extract fields based on current format
if is_date_first:
    # Current: date_added, word_pt, word_en, sentence_pt, sentence_en, category
    # But they're in wrong positions, so extract as:
    date_added = row_611[0].strip()
    # Columns are mixed up - B and C are swapped
    word_en = row_611[1].strip()  # Actually in column B
    word_pt = row_611[2].strip()  # Actually in column C
    sentence_pt = row_611[3].strip() if len(row_611) > 3 else ""
    sentence_en = row_611[4].strip() if len(row_611) > 4 else ""
else:
    # Current: word_en, word_pt, sentence_pt, sentence_en, date_added
    word_en = row_611[0].strip()
    word_pt = row_611[1].strip()
    sentence_pt = row_611[2].strip() if len(row_611) > 2 else ""
    sentence_en = row_611[3].strip() if len(row_611) > 3 else ""
    date_added = row_611[4].strip() if len(row_611) > 4 else ""

category = classify_card(word_en, word_pt, sentence_en, sentence_pt)

# Correct format: date_added, word_pt, word_en, sentence_pt, sentence_en, category
corrected_row = [date_added, word_pt, word_en, sentence_pt, sentence_en, category]

print(f"\nCorrected row 611:")
print(f"  date_added:  {date_added}")
print(f"  word_pt:     {word_pt}")
print(f"  word_en:     {word_en}")
print(f"  sentence_pt: {sentence_pt[:50]}...")
print(f"  sentence_en: {sentence_en[:50]}...")
print(f"  category:    {category}")

# Update
worksheet.update("A612:F612", [corrected_row], value_input_option="RAW")
print("\n✓ Row 611 fixed!")

# Verify
all_values = worksheet.get_all_values()
row_611_new = all_values[611]
print(f"\nVerification - Row 611 now:")
print(f"  {row_611_new[0][:10]} | {row_611_new[1][:15]} | {row_611_new[2][:15]} | {row_611_new[5] if len(row_611_new) > 5 else 'NO CAT'}")
