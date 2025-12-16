#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Update Google Sheets to match README specifications:
1. Reorder columns: date_added, word_pt, word_en, sentence_pt, sentence_en, category
2. Remove second row (redundant headers)
3. Add category column based on dashboard keyword matching
4. Ensure all Anki cards are present in the sheet
"""
import json
import urllib.request
from urllib.error import URLError
from datetime import datetime
from typing import Dict, List, Set, Tuple
import sys

# Import Google Sheets integration
try:
    import google_sheets
except ImportError:
    print("ERROR: google_sheets module not found")
    sys.exit(1)

# ===== CONFIGURATION =====

SPREADSHEET_ID = "1q20cEuHXoaLNWJ06i1Nv9Eo2JkJ00LMmPboTYSGz1xg"
SHEET_NAME = "Sheet1"
ANKI_DECK = "Portuguese Mastery (pt-PT)"
ANKI_URL = "http://127.0.0.1:8765"

# Category keywords (from generate_dashboard_html.py)
TOPIC_KEYWORDS = {
    "💪 Gym": [
        "gym", "workout", "exercise", "weight", "muscle", "squat", "bench",
        "cardio", "trainer", "fitness", "lift", "rep", "set", "barbell",
        "dumbbell", "stretch", "warm", "cool down", "protein", "athletic",
        "treino", "músculo", "peso", "academia", "exercício", "ginásio",
        "agachamento", "alongar", "repetições", "barra", "carga",
    ],
    "❤️ Dating": [
        "date", "dinner", "romantic", "relationship", "girlfriend", "boyfriend",
        "kiss", "love", "restaurant", "café", "bar", "movie", "flowers",
        "valentine", "anniversary", "couple",
        "encontro", "jantar", "romântico", "namorad", "amor", "beijo",
        "restaurante", "café", "namoro", "casal", "paixão",
    ],
    "💼 Work": [
        "work", "office", "meeting", "email", "deadline", "colleague", "boss",
        "project", "presentation", "report", "task", "client", "business",
        "salary", "contract", "team",
        "trabalho", "escritório", "reunião", "colega", "prazo", "projeto",
        "equipa", "chefe", "salário", "contrato", "tarefa", "negócio",
    ],
    "📋 Admin": [
        "form", "document", "bureaucracy", "payment", "bill", "passport",
        "visa", "license", "certificate", "registration", "permit", "tax",
        "insurance", "bank", "account",
        "formulário", "documento", "pagamento", "conta", "passaporte",
        "renovar", "visto", "certidão", "registo", "imposto", "seguro",
        "banco", "licença",
    ],
    "🏡 Daily Life": [
        "home", "shopping", "cooking", "cleaning", "house", "kitchen", "food",
        "grocery", "laundry", "dishes", "breakfast", "lunch", "dinner",
        "sleep", "wake", "shower", "clothes", "market",
        "compras", "casa", "cozinha", "comida", "limpar", "lavar",
        "pequeno-almoço", "almoço", "jantar", "dormir", "acordar",
        "roupa", "mercado", "cozinhar", "loiça",
    ],
}

# New header structure as per README
NEW_HEADERS = ["date_added", "word_pt", "word_en", "sentence_pt", "sentence_en", "category"]


# ===== ANKI INTEGRATION =====

def anki_invoke(payload: dict) -> dict:
    """Call AnkiConnect API."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        ANKI_URL, data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except URLError as e:
        raise RuntimeError(f"Could not connect to Anki. Is Anki running? Error: {e}")


def load_cards_from_anki(deck_name: str = ANKI_DECK) -> List[Dict[str, str]]:
    """Load all cards directly from Anki using AnkiConnect."""
    print(f"[anki] Connecting to Anki deck: {deck_name}")

    # Find all note IDs in the deck
    search_result = anki_invoke({
        "action": "findNotes",
        "version": 6,
        "params": {"query": f'deck:"{deck_name}"'}
    })

    if search_result.get("error"):
        raise RuntimeError(f"AnkiConnect error: {search_result['error']}")

    note_ids = search_result.get("result", [])
    print(f"[anki] Found {len(note_ids)} notes in deck")

    if not note_ids:
        return []

    # Get full note info
    notes_info = anki_invoke({
        "action": "notesInfo",
        "version": 6,
        "params": {"notes": note_ids}
    })

    if notes_info.get("error"):
        raise RuntimeError(f"AnkiConnect error: {notes_info['error']}")

    # Convert to our format
    cards = []
    for note in notes_info.get("result", []):
        fields = note.get("fields", {})
        note_id = note.get("noteId", "")

        # Extract date from noteId (Anki IDs are timestamps in milliseconds)
        try:
            timestamp = int(note_id) / 1000
            date_added = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
        except:
            date_added = datetime.now().strftime("%Y-%m-%d")

        word_en = fields.get("word_en", {}).get("value", "").strip()
        word_pt = fields.get("word_pt", {}).get("value", "").strip()
        sentence_pt = fields.get("sentence_pt", {}).get("value", "").strip()
        sentence_en = fields.get("sentence_en", {}).get("value", "").strip()

        if word_en and word_pt:
            cards.append({
                "date_added": date_added,
                "word_en": word_en,
                "word_pt": word_pt,
                "sentence_pt": sentence_pt,
                "sentence_en": sentence_en,
            })

    print(f"[anki] Loaded {len(cards)} valid cards")
    return cards


# ===== CLASSIFICATION =====

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


# ===== GOOGLE SHEETS UPDATE =====

def get_worksheet():
    """Get the worksheet using gspread directly."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        print("ERROR: gspread not installed. Run: pip install gspread google-auth")
        sys.exit(1)

    # Get credentials
    creds_path = google_sheets._get_credentials_path()
    if not creds_path:
        print("ERROR: Google Sheets credentials not found")
        sys.exit(1)

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    credentials = Credentials.from_service_account_file(str(creds_path), scopes=scopes)
    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    try:
        worksheet = spreadsheet.worksheet(SHEET_NAME)
    except Exception:
        worksheet = spreadsheet.sheet1

    return worksheet


def update_sheets_structure():
    """Main function to update the Google Sheets structure."""
    print("\n=== UPDATING GOOGLE SHEETS STRUCTURE ===\n")

    # Step 1: Get worksheet
    print("[1/6] Connecting to Google Sheets...")
    worksheet = get_worksheet()
    print("      ✓ Connected")

    # Step 2: Read current data
    print("\n[2/6] Reading current data from Google Sheets...")
    all_values = worksheet.get_all_values()
    print(f"      ✓ Found {len(all_values)} rows")

    # Identify and parse current data (skip first 2 rows if row 2 is redundant)
    current_data = []
    start_row = 1  # Default: skip only header

    if len(all_values) > 1:
        # Check if row 2 looks like redundant headers
        row2 = all_values[1]
        if any(h.lower() in ["date", "portuguese", "english", "example_pt", "example_en"]
               for h in row2):
            print("      ✓ Detected redundant second row, will remove it")
            start_row = 2

    # Parse current data
    for i in range(start_row, len(all_values)):
        row = all_values[i]
        if len(row) >= 5 and row[0].strip():  # Has data
            # Current structure: A=word_en, B=word_pt, C=sentence_pt, D=sentence_en, E=date_added
            current_data.append({
                "date_added": row[4].strip() if len(row) > 4 else "",
                "word_pt": row[1].strip() if len(row) > 1 else "",
                "word_en": row[0].strip(),
                "sentence_pt": row[2].strip() if len(row) > 2 else "",
                "sentence_en": row[3].strip() if len(row) > 3 else "",
            })

    print(f"      ✓ Parsed {len(current_data)} valid data rows")

    # Step 3: Load Anki cards
    print("\n[3/6] Loading cards from Anki deck...")
    try:
        anki_cards = load_cards_from_anki()
        print(f"      ✓ Loaded {len(anki_cards)} cards from Anki")
    except Exception as e:
        print(f"      ⚠ Warning: Could not load Anki cards: {e}")
        print("      Continuing with Google Sheets data only...")
        anki_cards = []

    # Step 4: Merge data - add missing Anki cards
    print("\n[4/6] Merging data and adding missing Anki cards...")
    existing_keys = {(row["word_en"].lower(), row["word_pt"].lower())
                     for row in current_data}

    added_count = 0
    for card in anki_cards:
        key = (card["word_en"].lower(), card["word_pt"].lower())
        if key not in existing_keys:
            current_data.append(card)
            added_count += 1
            existing_keys.add(key)

    print(f"      ✓ Added {added_count} missing cards from Anki")
    print(f"      ✓ Total cards: {len(current_data)}")

    # Step 5: Add categories to all rows
    print("\n[5/6] Classifying cards and adding categories...")
    categorized_data = []
    for row in current_data:
        category = classify_card(
            row["word_en"],
            row["word_pt"],
            row["sentence_en"],
            row["sentence_pt"]
        )
        categorized_data.append({
            "date_added": row["date_added"],
            "word_pt": row["word_pt"],
            "word_en": row["word_en"],
            "sentence_pt": row["sentence_pt"],
            "sentence_en": row["sentence_en"],
            "category": category,
        })

    print("      ✓ Categories assigned")

    # Step 6: Write back to Google Sheets with new structure
    print("\n[6/6] Writing updated data to Google Sheets...")

    # Clear the sheet
    worksheet.clear()
    print("      ✓ Cleared existing data")

    # Prepare new data with headers
    new_data = [NEW_HEADERS]
    for row in categorized_data:
        new_data.append([
            row["date_added"],
            row["word_pt"],
            row["word_en"],
            row["sentence_pt"],
            row["sentence_en"],
            row["category"],
        ])

    # Write all data at once
    worksheet.update(new_data, value_input_option="RAW")
    print(f"      ✓ Written {len(categorized_data)} rows with new structure")

    print("\n=== UPDATE COMPLETE ===")
    print(f"\nSummary:")
    print(f"  • Total rows: {len(categorized_data)}")
    print(f"  • New cards from Anki: {added_count}")
    print(f"  • Column order: {', '.join(NEW_HEADERS)}")
    print(f"\nCategory breakdown:")
    category_counts = {}
    for row in categorized_data:
        cat = row["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    for cat in sorted(category_counts.keys()):
        print(f"  • {cat}: {category_counts[cat]}")


if __name__ == "__main__":
    try:
        update_sheets_structure()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
