#!/usr/bin/env python3
"""
Fix Google Sheets column order for ALL entries.
Converts from: word_en, word_pt, sentence_pt, sentence_en, date_added
To: date_added, word_pt, word_en, sentence_pt, sentence_en, category
"""
import sys
sys.path.insert(0, '.')

try:
    import google_sheets
except ImportError:
    print("ERROR: google_sheets module not found")
    sys.exit(1)

# Category classification
TOPIC_KEYWORDS = {
    "💪 Gym": [
        "gym", "workout", "exercise", "weight", "muscle", "squat", "bench",
        "cardio", "trainer", "fitness", "lift", "rep", "set", "barbell",
        "dumbbell", "stretch", "warm", "cool down", "protein", "athletic",
        "treino", "músculo", "peso", "academia", "exercício", "ginásio",
        "agachamento", "alongar", "repetições", "barra", "carga", "biceps", "triceps",
        "peito", "chest", "bíceps", "tríceps",
    ],
    "❤️ Dating": [
        "date", "dinner", "romantic", "relationship", "girlfriend", "boyfriend",
        "kiss", "love", "restaurant", "café", "bar", "movie", "flowers",
        "encontro", "jantar", "romântico", "namorad", "amor", "beijo",
    ],
    "💼 Work": [
        "work", "office", "meeting", "email", "deadline", "colleague", "boss",
        "project", "presentation", "report", "task", "client", "business",
        "trabalho", "escritório", "reunião", "colega", "prazo", "projeto",
    ],
    "📋 Admin": [
        "form", "document", "bureaucracy", "payment", "bill", "passport",
        "visa", "license", "certificate", "registration", "permit", "tax",
        "formulário", "documento", "pagamento", "conta", "passaporte",
    ],
    "🏡 Daily Life": [
        "home", "shopping", "cooking", "cleaning", "house", "kitchen", "food",
        "grocery", "laundry", "dishes", "breakfast", "lunch", "dinner",
        "sleep", "wake", "shower", "clothes", "market", "stairs", "lobby",
        "sunset", "statue", "soaking", "wet",
        "compras", "casa", "cozinha", "comida", "limpar", "lavar",
        "guardar", "rodeado", "enrolar", "pôr do sol", "estátua", "escadas",
    ],
}

def classify_card(word_en: str, word_pt: str, sentence_en: str, sentence_pt: str) -> str:
    """Classify a card into a topic based on keyword matching."""
    text = f"{word_en} {word_pt} {sentence_en} {sentence_pt}".lower()
    scores = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword.lower() in text)
        if score > 0:
            scores[topic] = score
    if scores:
        return max(scores.items(), key=lambda x: x[1])[0]
    return "🔍 Other"

def fix_google_sheets_order():
    """Fix the column order in Google Sheets."""
    print("=== FIXING GOOGLE SHEETS COLUMN ORDER ===\n")

    # Get worksheet
    print("[1/4] Connecting to Google Sheets...")
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        print("ERROR: gspread not installed")
        sys.exit(1)

    creds_path = google_sheets._get_credentials_path()
    if not creds_path:
        print("ERROR: Credentials not found")
        sys.exit(1)

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = Credentials.from_service_account_file(str(creds_path), scopes=scopes)
    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_key(google_sheets.SPREADSHEET_ID)
    worksheet = spreadsheet.sheet1

    print("      ✓ Connected\n")

    # Read all data
    print("[2/4] Reading current data...")
    all_values = worksheet.get_all_values()

    if not all_values:
        print("ERROR: Sheet is empty")
        sys.exit(1)

    # Check current header
    current_header = all_values[0]
    print(f"      Current header: {current_header}")

    # Detect format
    if current_header[0] in ['word_en', 'Date']:
        print("      ⚠ Detected WRONG order - needs fixing!")
        needs_fix = True
        # Old format: word_en, word_pt, sentence_pt, sentence_en, date_added
        data_rows = all_values[1:]
    elif current_header[0] == 'date_added':
        print("      ✓ Header already correct, checking data rows...")
        needs_fix = False
        data_rows = all_values[1:]
    else:
        print("      ⚠ Unknown format, treating first row as data")
        needs_fix = True
        data_rows = all_values

    # Process all rows
    print(f"      Found {len(data_rows)} data rows\n")

    print("[3/4] Reordering and categorizing rows...")
    fixed_rows = []

    for i, row in enumerate(data_rows):
        if not row or len(row) < 5:
            continue

        # Detect row format and extract fields
        if needs_fix:
            # Old format: word_en, word_pt, sentence_pt, sentence_en, date_added
            word_en = row[0].strip()
            word_pt = row[1].strip() if len(row) > 1 else ""
            sentence_pt = row[2].strip() if len(row) > 2 else ""
            sentence_en = row[3].strip() if len(row) > 3 else ""
            date_added = row[4].strip() if len(row) > 4 else ""
        else:
            # Already in correct format: date_added, word_pt, word_en, sentence_pt, sentence_en, category
            date_added = row[0].strip()
            word_pt = row[1].strip() if len(row) > 1 else ""
            word_en = row[2].strip() if len(row) > 2 else ""
            sentence_pt = row[3].strip() if len(row) > 3 else ""
            sentence_en = row[4].strip() if len(row) > 4 else ""

        if not word_en:
            continue

        # Classify
        category = classify_card(word_en, word_pt, sentence_en, sentence_pt)

        # New format: date_added, word_pt, word_en, sentence_pt, sentence_en, category
        fixed_row = [date_added, word_pt, word_en, sentence_pt, sentence_en, category]
        fixed_rows.append(fixed_row)

    print(f"      ✓ Processed {len(fixed_rows)} rows\n")

    # Write back
    print("[4/4] Writing corrected data to Google Sheets...")
    worksheet.clear()

    new_header = ["date_added", "word_pt", "word_en", "sentence_pt", "sentence_en", "category"]
    all_data = [new_header] + fixed_rows

    worksheet.update(all_data, value_input_option="RAW")
    print(f"      ✓ Written {len(fixed_rows)} rows with correct order\n")

    print("=== FIX COMPLETE ===\n")
    print("Summary:")
    print(f"  • Total rows fixed: {len(fixed_rows)}")
    print(f"  • Column order: {', '.join(new_header)}")

    # Show category breakdown
    from collections import Counter
    categories = Counter(row[5] for row in fixed_rows)
    print("\nCategory breakdown:")
    for cat in sorted(categories.keys()):
        print(f"  {cat}: {categories[cat]}")

    print("\nLast 5 entries:")
    for row in fixed_rows[-5:]:
        print(f"  {row[0]} | {row[1]:15} | {row[2]:15} | {row[5]}")

if __name__ == "__main__":
    try:
        fix_google_sheets_order()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
