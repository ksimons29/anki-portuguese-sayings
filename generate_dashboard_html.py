#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate interactive HTML dashboard for Portuguese learning.

Creates a beautiful, clickable dashboard showing:
- Overview stats
- Categories with top words (collapsible to show all)
- Recent activity
- Search functionality
"""
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List
import csv
import os
import subprocess
import sys

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


def load_cards() -> List[Dict[str, str]]:
    """Load cards from Anki first, fallback to CSV if Anki unavailable."""
    try:
        return load_cards_from_anki()
    except Exception as e:
        print(f"[anki] Could not load from Anki: {e}")
        print("[anki] Falling back to CSV file...")
        return load_cards_from_csv()


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

def generate_html_dashboard(cards: List[Dict[str, str]]) -> str:
    """Generate interactive HTML dashboard."""
    if not cards:
        return "<html><body><h1>No cards found</h1></body></html>"

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
            padding: 40px;
            margin-bottom: 30px;
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
            padding: 15px;
            text-align: left;
            font-weight: 600;
            color: #4a5568;
            border-bottom: 2px solid #e2e8f0;
        }}

        .words-table td {{
            padding: 15px;
            border-bottom: 1px solid #e2e8f0;
        }}

        .words-table tr:hover {{
            background: #f7fafc;
        }}

        .word-pt {{
            font-weight: 600;
            color: #2d3748;
        }}

        .word-en {{
            color: #718096;
        }}

        .date {{
            color: #a0aec0;
            font-size: 0.9em;
        }}

        .expand-icon {{
            transition: transform 0.3s;
        }}

        .expand-icon.rotated {{
            transform: rotate(180deg);
        }}

        @media (max-width: 768px) {{
            .header h1 {{
                font-size: 1.8em;
            }}
            .stats-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🇵🇹 Portuguese Learning Dashboard</h1>
            <p class="subtitle">Last updated: {datetime.now().strftime('%A, %B %d, %Y at %H:%M')}</p>
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
                            <th>Portuguese</th>
                            <th>English</th>
                            <th>Date Added</th>
                        </tr>
                    </thead>
                    <tbody>
"""

        for card in sorted_cards:
            word_pt = card.get("word_pt", "").strip()
            word_en = card.get("word_en", "").strip()
            date = card.get("date_added", "")

            html += f"""
                        <tr class="word-row" data-pt="{word_pt.lower()}" data-en="{word_en.lower()}">
                            <td class="word-pt">{word_pt}</td>
                            <td class="word-en">{word_en}</td>
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
                const pt = row.getAttribute('data-pt');
                const en = row.getAttribute('data-en');

                if (pt.includes(searchTerm) || en.includes(searchTerm)) {
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


# ===== MAIN =====

def main() -> int:
    """Main entry point."""
    print("[dashboard] Loading cards from sayings.csv...")
    cards = load_cards()

    if not cards:
        print("[dashboard] No cards found in sayings.csv")
        return 0

    print(f"[dashboard] Loaded {len(cards)} cards")
    print("[dashboard] Generating HTML dashboard...")

    html = generate_html_dashboard(cards)

    # Save to Desktop or iCloud
    output_path = Path.home() / "Desktop" / "Portuguese-Dashboard.html"

    with output_path.open("w", encoding="utf-8") as f:
        f.write(html)

    print(f"[dashboard] ✓ Dashboard saved to: {output_path}")

    # Auto-open in browser
    try:
        subprocess.run(["open", str(output_path)], check=True)
        print("[dashboard] ✓ Dashboard opened in browser")
    except Exception as e:
        print(f"[dashboard] Could not auto-open: {e}")
        print(f"[dashboard] Manually open: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
