#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate interactive HTML dashboard for Portuguese learning.

Creates a beautiful, clickable dashboard showing:
- Overview stats
- Categories with top words (collapsible to show all)
- Recent activity
- Search functionality

Data sources (in priority order):
1. Anki (live via AnkiConnect)
2. Google Sheets
3. CSV file (fallback)
"""
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple
import csv
import glob
import os
import subprocess
import sys

# Google Sheets integration (optional)
_google_sheets_available = False
try:
    import google_sheets
    _google_sheets_available = google_sheets.is_available()
except ImportError:
    pass

# ===== CONFIGURATION =====

# Keyword lists for topic detection (same as before)
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


# ===== PATHS =====

def get_anki_base() -> Path:
    """Get Anki base directory from iCloud - pick the path with the larger sayings.csv."""
    mobile = (
        Path.home()
        / "Library"
        / "Mobile Documents"
        / "com~apple~CloudDocs"
        / "Portuguese"
        / "Anki"
    )
    cloud = (
        Path.home()
        / "Library"
        / "CloudStorage"
        / "iCloud Drive"
        / "Portuguese"
        / "Anki"
    )

    mobile_csv = mobile / "sayings.csv"
    cloud_csv = cloud / "sayings.csv"

    mobile_size = mobile_csv.stat().st_size if mobile_csv.exists() else 0
    cloud_size = cloud_csv.stat().st_size if cloud_csv.exists() else 0

    if mobile_size > cloud_size:
        return mobile
    elif cloud_size > 0:
        return cloud
    else:
        return mobile


BASE = get_anki_base()
MASTER_CSV = BASE / "sayings.csv"


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


# ===== ANKI INTEGRATION =====

import json
import urllib.request
from urllib.error import URLError

ANKI_URL = "http://127.0.0.1:8765"

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


def get_learning_stats(deck_name: str = "Portuguese Mastery (pt-PT)") -> Dict[str, any]:
    """
    Get learning statistics from Anki.

    Returns dict with:
    - learning_count: Cards currently in learning phase
    - learning_cards: List of cards currently being learned
    - struggling_cards: List of cards with high lapse count (failing often)
    - due_today: Cards due for review today
    - new_cards: List of cards not yet studied (queue 0)
    """
    stats = {
        "learning_count": 0,
        "due_today": 0,
        "learning_cards": [],
        "struggling_cards": [],
        "new_cards": [],
    }

    try:
        # Find all cards in the deck
        cards_result = anki_invoke({
            "action": "findCards",
            "version": 6,
            "params": {"query": f'deck:"{deck_name}"'}
        })

        if cards_result.get("error"):
            print(f"[anki-stats] Error finding cards: {cards_result['error']}")
            return stats

        card_ids = cards_result.get("result", [])
        if not card_ids:
            return stats

        # Also find cards due today specifically using Anki's is:due query
        due_today_result = anki_invoke({
            "action": "findCards",
            "version": 6,
            "params": {"query": f'deck:"{deck_name}" is:due'}
        })

        due_today_ids = set(due_today_result.get("result", []))
        stats["due_today"] = len(due_today_ids)

        # Get detailed card info
        cards_info = anki_invoke({
            "action": "cardsInfo",
            "version": 6,
            "params": {"cards": card_ids}
        })

        if cards_info.get("error"):
            print(f"[anki-stats] Error getting card info: {cards_info['error']}")
            return stats

        # Also get notes info for word data
        note_ids = list(set(c.get("note") for c in cards_info.get("result", []) if c.get("note")))
        notes_map = {}
        if note_ids:
            notes_info = anki_invoke({
                "action": "notesInfo",
                "version": 6,
                "params": {"notes": note_ids}
            })
            if not notes_info.get("error"):
                for note in notes_info.get("result", []):
                    notes_map[note.get("noteId")] = note

        for card in cards_info.get("result", []):
            queue = card.get("queue", 0)
            lapses = card.get("lapses", 0)
            due = card.get("due", 0)
            note_id = card.get("note")

            # Queue types:
            # -1 = suspended, 0 = new, 1 = learning, 2 = review, 3 = day-learn, 4 = preview

            # New cards (not yet studied)
            if queue == 0:
                note = notes_map.get(note_id, {})
                fields = note.get("fields", {})
                word_pt = fields.get("word_pt", {}).get("value", "").strip()
                word_en = fields.get("word_en", {}).get("value", "").strip()
                sentence_pt = fields.get("sentence_pt", {}).get("value", "").strip()
                sentence_en = fields.get("sentence_en", {}).get("value", "").strip()
                if word_pt and word_en:
                    stats["new_cards"].append({
                        "word_pt": word_pt,
                        "word_en": word_en,
                        "sentence_pt": sentence_pt,
                        "sentence_en": sentence_en,
                        "note_id": note_id,
                    })

            # Learning or day-learn cards
            if queue in (1, 3):
                stats["learning_count"] += 1
                # Also capture the card data for display
                note = notes_map.get(note_id, {})
                fields = note.get("fields", {})
                word_pt = fields.get("word_pt", {}).get("value", "").strip()
                word_en = fields.get("word_en", {}).get("value", "").strip()
                sentence_pt = fields.get("sentence_pt", {}).get("value", "").strip()
                sentence_en = fields.get("sentence_en", {}).get("value", "").strip()
                if word_pt and word_en:
                    stats["learning_cards"].append({
                        "word_pt": word_pt,
                        "word_en": word_en,
                        "sentence_pt": sentence_pt,
                        "sentence_en": sentence_en,
                        "queue": queue,
                    })

            # Struggling: ANY lapses (1+)
            # A lapse occurs when you press "Again" on a review card
            # If you failed it even once, it's worth reviewing
            if lapses >= 1:
                note = notes_map.get(note_id, {})
                fields = note.get("fields", {})
                word_pt = fields.get("word_pt", {}).get("value", "").strip()
                word_en = fields.get("word_en", {}).get("value", "").strip()
                sentence_pt = fields.get("sentence_pt", {}).get("value", "").strip()
                sentence_en = fields.get("sentence_en", {}).get("value", "").strip()
                if word_pt and word_en:
                    stats["struggling_cards"].append({
                        "word_pt": word_pt,
                        "word_en": word_en,
                        "sentence_pt": sentence_pt,
                        "sentence_en": sentence_en,
                        "lapses": lapses,
                    })

        # Sort struggling cards by lapses (most failed first) and limit to top 10
        stats["struggling_cards"].sort(key=lambda x: x["lapses"], reverse=True)
        stats["struggling_cards"] = stats["struggling_cards"][:10]

        # Sort new cards by note_id (timestamp) descending to show newest first
        stats["new_cards"].sort(key=lambda x: x.get("note_id", 0), reverse=True)

        print(f"[anki-stats] Learning: {stats['learning_count']}, Due: {stats['due_today']}, Struggling: {len(stats['struggling_cards'])}, New: {len(stats['new_cards'])}")

    except Exception as e:
        print(f"[anki-stats] Error fetching stats: {e}")

    return stats


def load_cards_from_anki(deck_name: str = "Portuguese Mastery (pt-PT)") -> List[Dict[str, str]]:
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
        tags = note.get("tags", [])
        note_id = note.get("noteId", "")

        # Extract date from noteId (Anki IDs are timestamps in milliseconds)
        try:
            timestamp = int(note_id) / 1000
            date_added = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
        except:
            date_added = "Unknown"

        word_en = fields.get("word_en", {}).get("value", "").strip()
        word_pt = fields.get("word_pt", {}).get("value", "").strip()
        sentence_pt = fields.get("sentence_pt", {}).get("value", "").strip()
        sentence_en = fields.get("sentence_en", {}).get("value", "").strip()

        if word_en and word_pt:
            cards.append({
                "word_en": word_en,
                "word_pt": word_pt,
                "sentence_pt": sentence_pt,
                "sentence_en": sentence_en,
                "date_added": date_added,
                "tags": tags,
                "note_id": note_id,
            })

    print(f"[anki] Loaded {len(cards)} cards with complete data")
    return cards


def load_cards_from_google_sheets() -> List[Dict[str, str]]:
    """Load all cards from Google Sheets."""
    if not _google_sheets_available:
        raise RuntimeError("Google Sheets not available")

    print("[gsheets] Connecting to Google Sheets...")
    storage = google_sheets.GoogleSheetsStorage()
    cards = storage.get_all_rows(use_cache=False)
    print(f"[gsheets] Loaded {len(cards)} cards from Google Sheets")
    return cards


def load_cards() -> Tuple[List[Dict[str, str]], str]:
    """
    Load cards from best available source.

    Priority:
    1. Anki (live data)
    2. Google Sheets
    3. CSV file (fallback)

    Returns: (cards, data_source_name)
    """
    # Try Anki first
    try:
        cards = load_cards_from_anki()
        print(f"[anki] ✓ Successfully loaded {len(cards)} cards from Anki database")
        return cards, "Anki Database (Live)"
    except Exception as e:
        print(f"[anki] ✗ Could not connect to Anki: {e}")

    # Try Google Sheets second
    if _google_sheets_available:
        try:
            cards = load_cards_from_google_sheets()
            print(f"[gsheets] ✓ Successfully loaded {len(cards)} cards from Google Sheets")
            return cards, "Google Sheets"
        except Exception as e:
            print(f"[gsheets] ✗ Could not connect to Google Sheets: {e}")

    # Fallback to CSV
    print("[csv] Falling back to CSV file...")
    cards = load_cards_from_csv()
    print(f"[csv] Loaded {len(cards)} cards from CSV")
    return cards, "CSV File (May be outdated)"


def load_cards_from_csv() -> List[Dict[str, str]]:
    """Load all cards from sayings.csv (fallback)."""
    if not MASTER_CSV.exists() or MASTER_CSV.stat().st_size == 0:
        return []

    cards = []
    with MASTER_CSV.open("r", encoding="utf-8", newline="") as f:
        first_line = f.readline().strip()
        f.seek(0)

        has_headers = "word_en" in first_line or "word_pt" in first_line

        if has_headers:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("word_en"):
                    cards.append(row)
        else:
            # No headers - positional columns
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 5 and row[2].strip():
                    cards.append({
                        "date_added": row[0].strip(),
                        "word_pt": row[1].strip(),
                        "word_en": row[2].strip(),
                        "sentence_pt": row[3].strip(),
                        "sentence_en": row[4].strip() if len(row) > 4 else "",
                    })

    return cards


# ===== HTML GENERATION =====

def generate_html_dashboard(cards: List[Dict[str, str]], data_source: str = "Anki", learning_stats: Dict = None) -> str:
    """Generate interactive HTML dashboard."""
    if not cards:
        return "<html><body><h1>No cards found</h1></body></html>"

    if learning_stats is None:
        learning_stats = {"learning_count": 0, "due_today": 0, "learning_cards": [], "struggling_cards": [], "new_cards": []}

    # Classify cards
    by_topic = defaultdict(list)
    for card in cards:
        topic = classify_card(
            card.get("word_en", ""),
            card.get("word_pt", ""),
            card.get("sentence_en", ""),
            card.get("sentence_pt", ""),
        )
        by_topic[topic].append(card)

    # Calculate stats
    total = len(cards)
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    this_week = sum(
        1 for c in cards
        if c.get("date_added") and c["date_added"] >= week_ago.isoformat()
    )
    this_month = sum(
        1 for c in cards
        if c.get("date_added") and c["date_added"] >= month_ago.isoformat()
    )

    # Filter cards from the last 2 weeks for the recent words section
    two_weeks_ago = today - timedelta(days=14)
    recent_cards = [
        c for c in cards
        if c.get("date_added") and c["date_added"] >= two_weeks_ago.isoformat()
    ]
    # Sort by date descending
    recent_cards.sort(key=lambda x: x.get("date_added", ""), reverse=True)

    # Group recent cards by date
    recent_by_date = defaultdict(list)
    for card in recent_cards:
        date = card.get("date_added", "Unknown")
        recent_by_date[date].append(card)

    # Sort topics
    sorted_topics = sorted(by_topic.items(), key=lambda x: len(x[1]), reverse=True)

    # Build HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🇵🇹 Portuguese Learning Dashboard</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        .header {{
            background: white;
            border-radius: 20px;
            padding: 30px 40px;
            margin-bottom: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}

        .header h1 {{
            font-size: 2.5em;
            color: #2d3748;
            margin-bottom: 10px;
        }}

        .header .subtitle {{
            color: #718096;
            font-size: 1.1em;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}

        .stat-card {{
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            text-align: center;
        }}

        .stat-number {{
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }}

        .stat-label {{
            color: #718096;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}

        .search-box {{
            background: white;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 30px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }}

        .search-box input {{
            width: 100%;
            padding: 15px 20px;
            border: 2px solid #e2e8f0;
            border-radius: 10px;
            font-size: 1.1em;
            transition: all 0.3s;
        }}

        .search-box input:focus {{
            outline: none;
            border-color: #667eea;
        }}

        .category {{
            background: white;
            border-radius: 15px;
            margin-bottom: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            overflow: hidden;
        }}

        .category-header {{
            padding: 25px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: background 0.3s;
        }}

        .category-header:hover {{
            background: #f7fafc;
        }}

        .category-title {{
            font-size: 1.5em;
            font-weight: 600;
            color: #2d3748;
        }}

        .category-count {{
            background: #667eea;
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 600;
        }}

        .top-words {{
            padding: 0 25px 15px 25px;
            color: #718096;
            font-size: 0.95em;
        }}

        .category-content {{
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease-out;
        }}

        .category-content.expanded {{
            max-height: 5000px;
            transition: max-height 0.5s ease-in;
        }}

        .words-table {{
            width: 100%;
            border-collapse: collapse;
        }}

        .words-table th {{
            background: #f7fafc;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            color: #4a5568;
            border-bottom: 2px solid #e2e8f0;
            font-size: 0.9em;
        }}

        .words-table td {{
            padding: 12px;
            border-bottom: 1px solid #e2e8f0;
            vertical-align: top;
            word-wrap: break-word;
            max-width: 400px;
        }}

        .words-table tr:hover {{
            background: #f7fafc;
        }}

        .word-pt {{
            font-weight: 600;
            color: #2d3748;
            font-size: 1.1em;
        }}

        .word-en {{
            color: #718096;
            font-size: 1.05em;
        }}

        .sentence-pt {{
            color: #4a5568;
            font-style: italic;
            margin-top: 5px;
            font-size: 0.95em;
            line-height: 1.4;
        }}

        .sentence-en {{
            color: #718096;
            font-style: italic;
            margin-top: 5px;
            font-size: 0.9em;
            line-height: 1.4;
        }}

        .date {{
            color: #a0aec0;
            font-size: 0.9em;
            white-space: nowrap;
        }}

        .expand-icon {{
            transition: transform 0.3s;
        }}

        .expand-icon.rotated {{
            transform: rotate(180deg);
        }}

        /* Recent Words Section */
        .recent-words-section {{
            background: white;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 30px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }}

        .recent-words-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #e2e8f0;
        }}

        .recent-words-title {{
            font-size: 1.5em;
            font-weight: 600;
            color: #2d3748;
        }}

        .recent-words-badge {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.9em;
        }}

        .date-group {{
            margin-bottom: 20px;
        }}

        .date-group:last-child {{
            margin-bottom: 0;
        }}

        .date-label {{
            font-size: 0.85em;
            color: #718096;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
            padding-left: 5px;
        }}

        .words-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 12px;
        }}

        .word-card {{
            background: #f7fafc;
            border-radius: 10px;
            padding: 12px 15px;
            border-left: 4px solid #667eea;
            transition: all 0.2s;
            cursor: pointer;
        }}

        .word-card:hover {{
            background: #edf2f7;
            transform: translateX(3px);
        }}

        .word-card.expanded {{
            background: #edf2f7;
        }}

        .word-card .word-pair {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 10px;
        }}

        .word-card .pt {{
            font-weight: 600;
            color: #2d3748;
            font-size: 1.05em;
        }}

        .word-card .arrow {{
            color: #a0aec0;
            flex-shrink: 0;
        }}

        .word-card .en {{
            color: #667eea;
            font-size: 0.95em;
            text-align: right;
        }}

        .word-card .sentences {{
            display: none;
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid #e2e8f0;
        }}

        .word-card.expanded .sentences {{
            display: block;
        }}

        .word-card .sentence-pt {{
            color: #4a5568;
            font-style: italic;
            font-size: 0.9em;
            line-height: 1.4;
            margin-bottom: 5px;
        }}

        .word-card .sentence-en {{
            color: #718096;
            font-size: 0.85em;
            line-height: 1.4;
        }}

        .no-recent-words {{
            text-align: center;
            padding: 30px;
            color: #718096;
        }}

        /* Difficult Words Section */
        .difficult-words-section {{
            background: white;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            border-left: 5px solid #e53e3e;
        }}

        .top-panels-wrapper .difficult-words-section {{
            margin-bottom: 0;
        }}

        .difficult-words-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #fed7d7;
        }}

        .difficult-words-title {{
            font-size: 1.5em;
            font-weight: 600;
            color: #c53030;
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .difficult-words-badge {{
            background: linear-gradient(135deg, #e53e3e 0%, #c53030 100%);
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.9em;
        }}

        .difficult-words-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 15px;
        }}

        .difficult-word-card {{
            background: #fff5f5;
            border-radius: 12px;
            padding: 15px;
            border: 1px solid #fed7d7;
            transition: all 0.2s;
            cursor: pointer;
        }}

        .difficult-word-card:hover {{
            background: #fee2e2;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(229, 62, 62, 0.15);
        }}

        .difficult-word-card.expanded {{
            background: #fee2e2;
        }}

        .difficult-word-main {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 15px;
        }}

        .difficult-word-text {{
            flex: 1;
        }}

        .difficult-word-pt {{
            font-weight: 700;
            color: #c53030;
            font-size: 1.15em;
            margin-bottom: 3px;
        }}

        .difficult-word-en {{
            color: #718096;
            font-size: 0.95em;
        }}

        .difficult-word-stats {{
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 4px;
        }}

        .fail-count {{
            background: #e53e3e;
            color: white;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 600;
        }}

        .fail-label {{
            font-size: 0.75em;
            color: #a0aec0;
            text-transform: uppercase;
        }}

        .difficult-word-sentences {{
            display: none;
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid #fed7d7;
        }}

        .difficult-word-card.expanded .difficult-word-sentences {{
            display: block;
        }}

        .difficult-sentence-pt {{
            color: #4a5568;
            font-style: italic;
            font-size: 0.9em;
            line-height: 1.5;
            margin-bottom: 6px;
        }}

        .difficult-sentence-en {{
            color: #718096;
            font-size: 0.85em;
            line-height: 1.4;
        }}

        .no-difficult-words {{
            text-align: center;
            padding: 40px 20px;
            color: #48bb78;
        }}

        .no-difficult-words .icon {{
            font-size: 3em;
            margin-bottom: 15px;
        }}

        .no-difficult-words .message {{
            font-size: 1.1em;
            font-weight: 500;
        }}

        .no-difficult-words .submessage {{
            font-size: 0.9em;
            color: #718096;
            margin-top: 5px;
        }}

        /* Subsection headers in difficult words */
        .subsection-header {{
            font-size: 1.1em;
            font-weight: 600;
            margin: 15px 0 10px 0;
            padding-bottom: 8px;
            border-bottom: 1px solid #e2e8f0;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .subsection-header:first-of-type {{
            margin-top: 0;
        }}

        .subsection-header.new {{
            color: #38a169;
        }}

        .subsection-header.learning {{
            color: #5a67d8;
        }}

        .subsection-header.struggling {{
            color: #c53030;
        }}

        .subsection-count {{
            background: #e2e8f0;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 0.85em;
            color: #4a5568;
        }}

        /* Learning cards (blue theme) */
        .learning-word-card {{
            background: #ebf4ff;
            border-radius: 12px;
            padding: 15px;
            border: 1px solid #c3dafe;
            transition: all 0.2s;
            cursor: pointer;
        }}

        .learning-word-card:hover {{
            background: #dbeafe;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(90, 103, 216, 0.15);
        }}

        .learning-word-card.expanded {{
            background: #dbeafe;
        }}

        .learning-word-pt {{
            font-weight: 700;
            color: #5a67d8;
            font-size: 1.15em;
            margin-bottom: 3px;
        }}

        .learning-word-en {{
            color: #718096;
            font-size: 0.95em;
        }}

        .learning-badge {{
            background: #5a67d8;
            color: white;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 600;
        }}

        .learning-word-sentences {{
            display: none;
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid #c3dafe;
        }}

        .learning-word-card.expanded .learning-word-sentences {{
            display: block;
        }}

        .learning-sentence-pt {{
            color: #4a5568;
            font-style: italic;
            font-size: 0.9em;
            line-height: 1.5;
            margin-bottom: 6px;
        }}

        .learning-sentence-en {{
            color: #718096;
            font-size: 0.85em;
            line-height: 1.4;
        }}

        /* New cards (green theme) */
        .new-word-card {{
            background: #f0fff4;
            border-radius: 12px;
            padding: 15px;
            border: 1px solid #9ae6b4;
            transition: all 0.2s;
            cursor: pointer;
        }}

        .new-word-card:hover {{
            background: #c6f6d5;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(56, 161, 105, 0.15);
        }}

        .new-word-card.expanded {{
            background: #c6f6d5;
        }}

        .new-word-pt {{
            font-weight: 700;
            color: #38a169;
            font-size: 1.15em;
            margin-bottom: 3px;
        }}

        .new-word-en {{
            color: #718096;
            font-size: 0.95em;
        }}

        .new-badge {{
            background: #38a169;
            color: white;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 600;
        }}

        .new-word-sentences {{
            display: none;
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid #9ae6b4;
        }}

        .new-word-card.expanded .new-word-sentences {{
            display: block;
        }}

        .new-sentence-pt {{
            color: #4a5568;
            font-style: italic;
            font-size: 0.9em;
            line-height: 1.5;
            margin-bottom: 6px;
        }}

        .new-sentence-en {{
            color: #718096;
            font-size: 0.85em;
            line-height: 1.4;
        }}

        /* Learning Stats Panel & Words Overview - side by side */
        .top-panels-wrapper {{
            display: grid;
            grid-template-columns: 1fr 2fr;
            gap: 20px;
            margin-bottom: 20px;
        }}

        .learning-stats-panel {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 15px;
            padding: 20px;
            color: white;
        }}

        .learning-stats-panel h3 {{
            font-size: 1.1em;
            margin-bottom: 15px;
            opacity: 0.95;
        }}

        .learning-stats-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }}

        .learning-stat-column {{
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}

        .learning-stat-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px;
            background: rgba(255,255,255,0.1);
            border-radius: 8px;
            cursor: help;
            position: relative;
        }}

        .learning-stat-row:hover {{
            background: rgba(255,255,255,0.15);
        }}

        .difficult-words-badge {{
            cursor: help;
            position: relative;
        }}

        .difficult-words-badge:hover::after {{
            content: attr(data-tooltip);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            background: #2d3748;
            color: white;
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 0.85em;
            white-space: pre-line;
            width: 320px;
            margin-bottom: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            z-index: 1000;
            line-height: 1.5;
        }}

        .difficult-words-badge:hover::before {{
            content: '';
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            border: 6px solid transparent;
            border-top-color: #2d3748;
            margin-bottom: 2px;
        }}

        .learning-stat-row:hover::after {{
            content: attr(data-tooltip);
            position: absolute;
            top: 100%;
            right: 0;
            background: rgba(45, 55, 72, 0.95);
            color: white;
            padding: 10px 14px;
            border-radius: 8px;
            font-size: 0.8em;
            white-space: nowrap;
            margin-top: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            z-index: 1000;
        }}

        .learning-stat-label {{
            font-size: 0.9em;
            opacity: 0.9;
        }}

        .learning-stat-value {{
            font-weight: bold;
            font-size: 1.2em;
        }}

        .learning-stat-value.warning {{
            color: #fbd38d;
        }}

        .struggling-section {{
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid rgba(255,255,255,0.3);
        }}

        .struggling-title {{
            font-size: 0.85em;
            opacity: 0.9;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 5px;
        }}

        .struggling-word {{
            background: rgba(255,255,255,0.15);
            border-radius: 8px;
            padding: 8px 12px;
            margin-bottom: 6px;
            font-size: 0.9em;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .struggling-word:last-child {{
            margin-bottom: 0;
        }}

        .struggling-word .word {{
            font-weight: 500;
        }}

        .struggling-word .lapses {{
            background: rgba(251, 211, 141, 0.3);
            color: #fbd38d;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.8em;
            font-weight: 600;
        }}

        @media (max-width: 1000px) {{
            .top-panels-wrapper {{
                grid-template-columns: 1fr;
            }}
            .learning-stats-grid {{
                grid-template-columns: 1fr 1fr;
            }}
        }}

        @media (max-width: 768px) {{
            .header h1 {{
                font-size: 1.8em;
            }}
            .learning-stats-grid {{
                grid-template-columns: 1fr;
            }}
            .stats-grid {{
                grid-template-columns: 1fr;
            }}
            .words-grid {{
                grid-template-columns: 1fr;
            }}
            .word-card .word-pair {{
                flex-direction: column;
                align-items: flex-start;
                gap: 5px;
            }}
            .word-card .arrow {{
                display: none;
            }}
            .word-card .en {{
                text-align: left;
            }}
            .recent-words-header {{
                flex-direction: column;
                align-items: flex-start;
                gap: 10px;
            }}
            .difficult-words-grid {{
                grid-template-columns: 1fr;
            }}
            .difficult-words-header {{
                flex-direction: column;
                align-items: flex-start;
                gap: 10px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🇵🇹 Portuguese Learning Dashboard</h1>
            <p class="subtitle">Last updated: {datetime.now().strftime('%A, %B %d, %Y at %H:%M')}</p>
            <p class="subtitle" style="margin-top: 5px; font-size: 0.9em;">📊 Data source: <strong>{data_source}</strong></p>
        </div>

        <div class="top-panels-wrapper">
            <div class="learning-stats-panel">
                <h3>📚 Learning Progress</h3>
                <div class="learning-stats-grid">
                    <div class="learning-stat-column">
                        <div class="learning-stat-row" data-tooltip="Cards in active learning (queue 1 or 3)">
                            <span class="learning-stat-label">Currently Learning</span>
                            <span class="learning-stat-value">{learning_stats['learning_count']}</span>
                        </div>
                        <div class="learning-stat-row" data-tooltip="Cards due for review today (is:due query)">
                            <span class="learning-stat-label">Due for Review</span>
                            <span class="learning-stat-value">{learning_stats['due_today']}</span>
                        </div>
                    </div>
                    <div class="learning-stat-column">
                        <div class="learning-stat-row" data-tooltip="Cards with failures (pressed 'Again' during reviews)">
                            <span class="learning-stat-label">Need Practice</span>
                            <span class="learning-stat-value{' warning' if len(learning_stats['struggling_cards']) > 0 else ''}">{len(learning_stats['struggling_cards'])}</span>
                        </div>
                    </div>
                </div>
"""

    # Add struggling words if any
    if learning_stats['struggling_cards']:
        html += """
                    <div class="struggling-section">
                        <div class="struggling-title">⚠️ Words to Review (3+ fails)</div>
"""
        for word in learning_stats['struggling_cards'][:5]:  # Show top 5
            word_pt_safe = word['word_pt'].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            html += f"""
                        <div class="struggling-word">
                            <span class="word">{word_pt_safe}</span>
                            <span class="lapses">{word['lapses']}x</span>
                        </div>
"""
        html += """
                    </div>
"""

    html += f"""
            </div>

            <div class="difficult-words-section">
            <div class="difficult-words-header">
                <div class="difficult-words-title">📖 Words Overview</div>
                <div class="difficult-words-badge" data-tooltip="Includes cards that need attention:
• New Cards (queue 0) - Not yet studied
• Learning (queue 1/3) - Being learned
• Need Practice (1+ lapses) - Failed at least once

Excludes: Review cards with no failures">{len(learning_stats['new_cards']) + len(learning_stats['learning_cards']) + len(learning_stats['struggling_cards'])} words to focus on</div>
            </div>
"""

    # Calculate totals
    has_new = len(learning_stats['new_cards']) > 0
    has_learning = len(learning_stats['learning_cards']) > 0
    has_struggling = len(learning_stats['struggling_cards']) > 0

    # Show new cards first (not yet studied) - limit to 20 most recent
    if has_new:
        display_new_cards = learning_stats['new_cards'][:20]
        html += f"""
            <div class="subsection-header new">
                ✨ New Cards (Not Yet Studied)
                <span class="subsection-count">{len(learning_stats['new_cards'])} total ({len(display_new_cards)} shown)</span>
            </div>
            <div class="difficult-words-grid">
"""
        for word in display_new_cards:
            word_pt = word.get("word_pt", "").strip()
            word_en = word.get("word_en", "").strip()
            sentence_pt = word.get("sentence_pt", "").strip()
            sentence_en = word.get("sentence_en", "").strip()

            # Escape HTML entities
            word_pt_safe = word_pt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            word_en_safe = word_en.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            sentence_pt_safe = sentence_pt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            sentence_en_safe = sentence_en.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

            html += f"""
                <div class="new-word-card" onclick="this.classList.toggle('expanded')">
                    <div class="difficult-word-main">
                        <div class="difficult-word-text">
                            <div class="new-word-pt">{word_pt_safe}</div>
                            <div class="new-word-en">{word_en_safe}</div>
                        </div>
                        <div class="difficult-word-stats">
                            <span class="new-badge">New</span>
                        </div>
                    </div>
                    <div class="new-word-sentences">
                        <div class="new-sentence-pt">{sentence_pt_safe}</div>
                        <div class="new-sentence-en">{sentence_en_safe}</div>
                    </div>
                </div>
"""
        html += """
            </div>
"""

    # Show learning cards (currently being studied)
    if has_learning:
        html += f"""
            <div class="subsection-header learning">
                📚 Currently Learning
                <span class="subsection-count">{len(learning_stats['learning_cards'])} words</span>
            </div>
            <div class="difficult-words-grid">
"""
        for word in learning_stats['learning_cards']:
            word_pt = word.get("word_pt", "").strip()
            word_en = word.get("word_en", "").strip()
            sentence_pt = word.get("sentence_pt", "").strip()
            sentence_en = word.get("sentence_en", "").strip()

            # Escape HTML entities
            word_pt_safe = word_pt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            word_en_safe = word_en.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            sentence_pt_safe = sentence_pt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            sentence_en_safe = sentence_en.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

            html += f"""
                <div class="learning-word-card" onclick="this.classList.toggle('expanded')">
                    <div class="difficult-word-main">
                        <div class="difficult-word-text">
                            <div class="learning-word-pt">{word_pt_safe}</div>
                            <div class="learning-word-en">{word_en_safe}</div>
                        </div>
                        <div class="difficult-word-stats">
                            <span class="learning-badge">Learning</span>
                        </div>
                    </div>
                    <div class="learning-word-sentences">
                        <div class="learning-sentence-pt">{sentence_pt_safe}</div>
                        <div class="learning-sentence-en">{sentence_en_safe}</div>
                    </div>
                </div>
"""
        html += """
            </div>
"""

    # Show struggling cards (failed 1+ times - pressed "Again" at least once)
    if has_struggling:
        html += f"""
            <div class="subsection-header struggling">
                ⚠️ Need More Practice
                <span class="subsection-count">{len(learning_stats['struggling_cards'])} words</span>
            </div>
            <div class="difficult-words-grid">
"""
        for word in learning_stats['struggling_cards']:
            word_pt = word.get("word_pt", "").strip()
            word_en = word.get("word_en", "").strip()
            sentence_pt = word.get("sentence_pt", "").strip()
            sentence_en = word.get("sentence_en", "").strip()
            lapses = word.get("lapses", 0)

            # Escape HTML entities
            word_pt_safe = word_pt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            word_en_safe = word_en.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            sentence_pt_safe = sentence_pt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            sentence_en_safe = sentence_en.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

            html += f"""
                <div class="difficult-word-card" onclick="this.classList.toggle('expanded')">
                    <div class="difficult-word-main">
                        <div class="difficult-word-text">
                            <div class="difficult-word-pt">{word_pt_safe}</div>
                            <div class="difficult-word-en">{word_en_safe}</div>
                        </div>
                        <div class="difficult-word-stats">
                            <span class="fail-count">{lapses}x failed</span>
                        </div>
                    </div>
                    <div class="difficult-word-sentences">
                        <div class="difficult-sentence-pt">{sentence_pt_safe}</div>
                        <div class="difficult-sentence-en">{sentence_en_safe}</div>
                    </div>
                </div>
"""
        html += """
            </div>
"""

    # Show message if nothing to show
    if not has_new and not has_learning and not has_struggling:
        html += """
            <div class="no-difficult-words">
                <div class="icon">🎉</div>
                <div class="message">All caught up!</div>
                <div class="submessage">No new cards, no words currently in learning phase, and no struggling words</div>
            </div>
"""

    html += f"""
            </div>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">{total}</div>
                <div class="stat-label">Total Cards</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{this_week}</div>
                <div class="stat-label">This Week</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{this_month}</div>
                <div class="stat-label">This Month</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{len(sorted_topics)}</div>
                <div class="stat-label">Categories</div>
            </div>
        </div>

        <div class="recent-words-section">
            <div class="recent-words-header">
                <div class="recent-words-title">📅 Recent Words (Last 2 Weeks)</div>
                <div class="recent-words-badge">{len(recent_cards)} words</div>
            </div>
"""

    # Generate recent words grouped by date
    if recent_cards:
        sorted_dates = sorted(recent_by_date.keys(), reverse=True)
        for date in sorted_dates:
            date_cards = recent_by_date[date]
            # Format the date nicely
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                if date == today.isoformat():
                    formatted_date = "Today"
                elif date == (today - timedelta(days=1)).isoformat():
                    formatted_date = "Yesterday"
                else:
                    formatted_date = date_obj.strftime("%A, %B %d")
            except:
                formatted_date = date

            html += f"""
            <div class="date-group">
                <div class="date-label">{formatted_date} ({len(date_cards)} words)</div>
                <div class="words-grid">
"""
            for card in date_cards:
                word_pt = card.get("word_pt", "").strip()
                word_en = card.get("word_en", "").strip()
                sentence_pt = card.get("sentence_pt", "").strip()
                sentence_en = card.get("sentence_en", "").strip()

                # Escape HTML entities
                word_pt_safe = word_pt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                word_en_safe = word_en.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                sentence_pt_safe = sentence_pt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                sentence_en_safe = sentence_en.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

                html += f"""
                    <div class="word-card" onclick="this.classList.toggle('expanded')">
                        <div class="word-pair">
                            <span class="pt">{word_pt_safe}</span>
                            <span class="arrow">→</span>
                            <span class="en">{word_en_safe}</span>
                        </div>
                        <div class="sentences">
                            <div class="sentence-pt">{sentence_pt_safe}</div>
                            <div class="sentence-en">{sentence_en_safe}</div>
                        </div>
                    </div>
"""
            html += """
                </div>
            </div>
"""
    else:
        html += """
            <div class="no-recent-words">
                No words added in the last 2 weeks. Keep learning! 📚
            </div>
"""

    html += """
        </div>

        <div class="search-box">
            <input type="text" id="searchInput" placeholder="🔍 Search words in Portuguese or English...">
        </div>

        <div id="categories">
"""

    # Add each category
    for topic, topic_cards in sorted_topics:
        count = len(topic_cards)
        percentage = (count / total * 100) if total > 0 else 0

        # Sort by date
        sorted_cards = sorted(
            topic_cards,
            key=lambda x: x.get("date_added", ""),
            reverse=True
        )

        # Top 5 words for preview
        top_5 = sorted_cards[:5]
        top_words_preview = ", ".join([f"{c.get('word_pt', '')}" for c in top_5])

        # Sanitize for HTML
        category_id = topic.replace(" ", "_").replace("🔍", "other").replace("💪", "gym").replace("❤️", "dating").replace("💼", "work").replace("📋", "admin").replace("🏡", "daily")

        html += f"""
        <div class="category" data-category="{topic}">
            <div class="category-header" onclick="toggleCategory('{category_id}')">
                <div>
                    <div class="category-title">{topic}</div>
                    <div class="top-words">Top words: {top_words_preview}</div>
                </div>
                <div>
                    <span class="category-count">{count} cards ({percentage:.1f}%)</span>
                    <span class="expand-icon" id="icon-{category_id}">▼</span>
                </div>
            </div>
            <div class="category-content" id="content-{category_id}">
                <table class="words-table">
                    <thead>
                        <tr>
                            <th style="width: 40%;">Portuguese Word & Sentence</th>
                            <th style="width: 45%;">English Translation & Sentence</th>
                            <th style="width: 15%;">Date Added</th>
                        </tr>
                    </thead>
                    <tbody>
"""

        for card in sorted_cards:
            word_pt = card.get("word_pt", "").strip()
            word_en = card.get("word_en", "").strip()
            sentence_pt = card.get("sentence_pt", "").strip()
            sentence_en = card.get("sentence_en", "").strip()
            date = card.get("date_added", "")

            # Escape HTML entities
            word_pt_safe = word_pt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            word_en_safe = word_en.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            sentence_pt_safe = sentence_pt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            sentence_en_safe = sentence_en.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

            # Prepare search data (escape for HTML attribute - & MUST be first!)
            search_text = f"{word_pt} {word_en} {sentence_pt} {sentence_en}".lower()
            search_text_safe = (search_text
                .replace("&", "&amp;")  # MUST be first!
                .replace('"', "&quot;")
                .replace("'", "&#39;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )

            html += f"""
                        <tr class="word-row" data-search="{search_text_safe}">
                            <td>
                                <div class="word-pt">{word_pt_safe}</div>
                                <div class="sentence-pt">{sentence_pt_safe}</div>
                            </td>
                            <td>
                                <div class="word-en">{word_en_safe}</div>
                                <div class="sentence-en">{sentence_en_safe}</div>
                            </td>
                            <td class="date">{date}</td>
                        </tr>
"""

        html += """
                    </tbody>
                </table>
            </div>
        </div>
"""

    # Add JavaScript
    html += """
    </div>
    </div>

    <script>
        function toggleCategory(categoryId) {
            const content = document.getElementById('content-' + categoryId);
            const icon = document.getElementById('icon-' + categoryId);

            content.classList.toggle('expanded');
            icon.classList.toggle('rotated');
        }

        // Search functionality
        const searchInput = document.getElementById('searchInput');
        searchInput.addEventListener('input', function(e) {
            const searchTerm = e.target.value.toLowerCase();
            const rows = document.querySelectorAll('.word-row');

            rows.forEach(row => {
                const searchText = row.getAttribute('data-search');

                if (searchText.includes(searchTerm)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            });

            // If searching, expand all categories
            if (searchTerm) {
                document.querySelectorAll('.category-content').forEach(content => {
                    content.classList.add('expanded');
                });
                document.querySelectorAll('.expand-icon').forEach(icon => {
                    icon.classList.add('rotated');
                });
            }
        });
    </script>
</body>
</html>
"""

    return html


# ===== CLEANUP =====

def cleanup_old_dashboards(directory: Path, pattern: str, keep: int = 3) -> None:
    """Remove old dashboard files, keeping the most recent ones.

    Args:
        directory: Directory containing the dashboard files
        pattern: Glob pattern to match dashboard files (e.g., "Portuguese-Dashboard-*.html")
        keep: Number of most recent files to keep (default: 3)
    """
    old_files = sorted(glob.glob(str(directory / pattern)))
    files_to_remove = old_files[:-keep] if len(old_files) > keep else []
    for old_file in files_to_remove:
        try:
            os.remove(old_file)
            print(f"[dashboard] Cleaned up old file: {Path(old_file).name}")
        except OSError as e:
            print(f"[dashboard] Could not remove {old_file}: {e}")


# ===== MAIN =====

def main() -> int:
    """Main entry point."""
    print("[dashboard] Loading vocabulary data...")

    # Use the unified load_cards function
    cards, data_source = load_cards()

    if not cards:
        print("[dashboard] No cards found")
        return 0

    # Get learning statistics from Anki
    learning_stats = {"learning_count": 0, "due_today": 0, "learning_cards": [], "struggling_cards": [], "new_cards": []}
    if "Anki" in data_source:
        print("[dashboard] Fetching learning statistics from Anki...")
        learning_stats = get_learning_stats()

    print("[dashboard] Generating HTML dashboard...")

    html = generate_html_dashboard(cards, data_source, learning_stats)

    # Generate unique filename with timestamp to bust browser cache
    # Each new file = new cache entry = guaranteed fresh content
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"Portuguese-Dashboard-{timestamp}.html"

    # Clean up old dashboard files before creating new ones (keep last 3)
    cleanup_old_dashboards(BASE, "Portuguese-Dashboard-*.html", keep=3)
    cleanup_old_dashboards(Path.home() / "Desktop", "Portuguese-Dashboard-*.html", keep=3)

    # Save to iCloud Drive (syncs to iPhone/iPad)
    output_path = BASE / filename

    # Also create a Desktop copy for easy Mac access
    desktop_path = Path.home() / "Desktop" / filename

    with output_path.open("w", encoding="utf-8") as f:
        f.write(html)

    print(f"[dashboard] ✓ Dashboard saved to: {output_path}")

    # Copy to Desktop for convenient Mac access
    try:
        import shutil
        shutil.copy2(output_path, desktop_path)
        print(f"[dashboard] ✓ Copy saved to Desktop: {desktop_path}")
    except Exception as e:
        print(f"[dashboard] Note: Could not copy to Desktop: {e}")

    # Auto-open in browser (Mac)
    try:
        subprocess.run(["open", str(output_path)], check=True)
        print("[dashboard] ✓ Dashboard opened in browser")
    except Exception as e:
        print(f"[dashboard] Could not auto-open: {e}")
        print(f"[dashboard] Manually open: {output_path}")

    print(f"\n[dashboard] 📱 Access on iPhone/iPad:")
    print(f"[dashboard]    Files app → iCloud Drive → Portuguese → Anki → {filename}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
