#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate Portuguese Learning Dashboard from sayings.csv and write to Apple Notes.

Reads sayings.csv, classifies cards by topic using keyword matching,
and creates a detailed overview note in Apple Notes.
"""
import csv
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

# ===== CONFIGURATION =====

# Keyword lists for topic detection (case-insensitive matching)
TOPIC_KEYWORDS = {
    "💪 Gym": [
        # English
        "gym", "workout", "exercise", "weight", "muscle", "squat", "bench",
        "cardio", "trainer", "fitness", "lift", "rep", "set", "barbell",
        "dumbbell", "stretch", "warm", "cool down", "protein", "athletic",
        # Portuguese
        "treino", "músculo", "peso", "academia", "exercício", "ginásio",
        "agachamento", "alongar", "repetições", "barra", "carga",
    ],
    "❤️ Dating": [
        # English
        "date", "dinner", "romantic", "relationship", "girlfriend", "boyfriend",
        "kiss", "love", "restaurant", "café", "bar", "movie", "flowers",
        "valentine", "anniversary", "couple",
        # Portuguese
        "encontro", "jantar", "romântico", "namorad", "amor", "beijo",
        "restaurante", "café", "namoro", "casal", "paixão",
    ],
    "💼 Work": [
        # English
        "work", "office", "meeting", "email", "deadline", "colleague", "boss",
        "project", "presentation", "report", "task", "client", "business",
        "salary", "contract", "team",
        # Portuguese
        "trabalho", "escritório", "reunião", "colega", "prazo", "projeto",
        "equipa", "chefe", "salário", "contrato", "tarefa", "negócio",
    ],
    "📋 Admin": [
        # English
        "form", "document", "bureaucracy", "payment", "bill", "passport",
        "visa", "license", "certificate", "registration", "permit", "tax",
        "insurance", "bank", "account",
        # Portuguese
        "formulário", "documento", "pagamento", "conta", "passaporte",
        "renovar", "visto", "certidão", "registo", "imposto", "seguro",
        "banco", "licença",
    ],
    "🏡 Daily Life": [
        # English
        "home", "shopping", "cooking", "cleaning", "house", "kitchen", "food",
        "grocery", "laundry", "dishes", "breakfast", "lunch", "dinner",
        "sleep", "wake", "shower", "clothes", "market",
        # Portuguese
        "compras", "casa", "cozinha", "comida", "limpar", "lavar",
        "pequeno-almoço", "almoço", "jantar", "dormir", "acordar",
        "roupa", "mercado", "cozinhar", "loiça",
    ],
}


# ===== PATHS =====

def get_anki_base() -> Path:
    """Get Anki base directory from iCloud."""
    # Check CloudStorage first (macOS Sonoma+)
    cloud = (
        Path.home()
        / "Library"
        / "CloudStorage"
        / "iCloud Drive"
        / "Portuguese"
        / "Anki"
    )
    if cloud.exists():
        return cloud

    # Fallback to Mobile Documents (older macOS)
    mobile = (
        Path.home()
        / "Library"
        / "Mobile Documents"
        / "com~apple~CloudDocs"
        / "Portuguese"
        / "Anki"
    )
    return mobile


BASE = get_anki_base()
MASTER_CSV = BASE / "sayings.csv"


# ===== CLASSIFICATION =====

def classify_card(word_en: str, word_pt: str, sentence_en: str, sentence_pt: str) -> str:
    """
    Classify a card into a topic based on keyword matching.
    Returns the topic name or "🔍 Other" if no match.
    """
    # Combine all text for matching
    text = f"{word_en} {word_pt} {sentence_en} {sentence_pt}".lower()

    # Count matches per topic
    scores = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword.lower() in text)
        if score > 0:
            scores[topic] = score

    # Return topic with highest score
    if scores:
        return max(scores.items(), key=lambda x: x[1])[0]
    return "🔍 Other"


# ===== CSV READING =====

def load_cards() -> List[Dict[str, str]]:
    """Load all cards from sayings.csv."""
    if not MASTER_CSV.exists() or MASTER_CSV.stat().st_size == 0:
        print(f"[DEBUG] File doesn't exist or is empty: {MASTER_CSV}")
        return []

    cards = []
    total_rows = 0
    skipped_rows = 0

    with MASTER_CSV.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        print(f"[DEBUG] CSV headers: {reader.fieldnames}")

        for i, row in enumerate(reader):
            total_rows += 1
            if row.get("word_en"):  # Skip empty rows
                cards.append(row)
            else:
                skipped_rows += 1
                if i < 3:  # Show first few skipped rows
                    print(f"[DEBUG] Skipped row {i}: {row}")

    print(f"[DEBUG] Total rows read: {total_rows}")
    print(f"[DEBUG] Rows with word_en: {len(cards)}")
    print(f"[DEBUG] Skipped rows: {skipped_rows}")

    return cards


# ===== DASHBOARD GENERATION =====

def generate_dashboard(cards: List[Dict[str, str]]) -> str:
    """Generate detailed dashboard markdown with clean table layout."""
    if not cards:
        return "# 🇵🇹 Portuguese Learning Overview\n\nNo cards found yet. Start capturing words!\n"

    # Classify cards by topic
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

    # Sort topics by size (descending)
    sorted_topics = sorted(
        by_topic.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )

    # Find most active topic
    most_active = sorted_topics[0][0] if sorted_topics else "None"
    most_active_count = len(sorted_topics[0][1]) if sorted_topics else 0

    # Generate markdown with clean layout
    lines = [
        "═" * 60,
        "🇵🇹  PORTUGUESE LEARNING OVERVIEW",
        "═" * 60,
        "",
        f"📅  Last updated: {datetime.now().strftime('%A, %B %d, %Y at %H:%M')}",
        f"📊  Total vocabulary: {total} cards",
        "",
        "─" * 60,
        "",
        "📈  RECENT ACTIVITY",
        "",
        f"  This week:     {this_week} new cards",
        f"  This month:    {this_month} new cards",
        f"  Top category:  {most_active} ({most_active_count} cards)",
        "",
        "═" * 60,
        "",
    ]

    # Add each topic section with clean table
    for topic, topic_cards in sorted_topics:
        count = len(topic_cards)
        percentage = (count / total * 100) if total > 0 else 0

        lines.extend([
            f"{topic}  •  {count} cards  •  {percentage:.1f}%",
            "─" * 60,
            "",
        ])

        # Sort cards by date (most recent first)
        sorted_cards = sorted(
            topic_cards,
            key=lambda x: x.get("date_added", ""),
            reverse=True
        )

        # Create clean table with all cards
        lines.append("Word (Portuguese)        Translation (English)          Added")
        lines.append("─" * 60)

        for card in sorted_cards:
            word_pt = card.get("word_pt", "").strip()
            word_en = card.get("word_en", "").strip()
            date = card.get("date_added", "")

            if word_pt and word_en:
                # Truncate if too long for clean display
                pt_display = (word_pt[:22] + "...") if len(word_pt) > 25 else word_pt
                en_display = (word_en[:28] + "...") if len(word_en) > 31 else word_en

                # Format with padding
                lines.append(f"{pt_display:<25}{en_display:<31}{date}")

        lines.extend([
            "",
            "═" * 60,
            "",
        ])

    # Add insights section
    lines.extend([
        "🎯  INSIGHTS & RECOMMENDATIONS",
        "─" * 60,
        "",
    ])

    if sorted_topics:
        strongest = sorted_topics[0]
        lines.append(f"✓ Strongest area: {strongest[0]} with {len(strongest[1])} cards")

        if len(sorted_topics) > 1:
            weakest = sorted_topics[-1]
            if weakest[0] != "🔍 Other":
                lines.append(f"! Opportunity: {weakest[0]} has only {len(weakest[1])} cards")

        if this_week > 0:
            lines.append(f"🔥 Great momentum: {this_week} new cards this week!")
        elif this_month > 0:
            lines.append(f"📚 Steady progress: {this_month} cards this month")

    lines.extend([
        "",
        "═" * 60,
        f"Auto-generated from sayings.csv  •  {total} total cards",
        "═" * 60,
    ])

    return "\n".join(lines)


# ===== APPLE NOTES INTEGRATION =====

def write_to_apple_notes(markdown: str) -> bool:
    """Write dashboard to Apple Notes via AppleScript."""
    # Escape quotes for AppleScript
    escaped = markdown.replace("\\", "\\\\").replace('"', '\\"')

    applescript = f'''
tell application "Notes"
    set noteFound to false
    set noteName to "🇵🇹 Portuguese Learning Overview"

    -- Try to find existing note in any folder
    repeat with theFolder in folders
        try
            set theNote to note noteName of theFolder
            set body of theNote to "{escaped}"
            set noteFound to true
            exit repeat
        end try
    end repeat

    -- If not found, create new note in default account
    if not noteFound then
        set defaultAccount to default account
        tell defaultAccount
            make new note with properties {{name:noteName, body:"{escaped}"}}
        end tell
    end if
end tell
'''

    try:
        subprocess.run(
            ["osascript", "-e", applescript],
            check=True,
            capture_output=True,
            text=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to write to Apple Notes: {e.stderr}", file=sys.stderr)
        return False
    except FileNotFoundError:
        print("[ERROR] osascript not found (not on macOS?)", file=sys.stderr)
        return False


# ===== MAIN =====

def main() -> int:
    """Main entry point."""
    print(f"[dashboard] Looking for sayings.csv at: {MASTER_CSV}")
    print("[dashboard] Loading cards from sayings.csv...")
    cards = load_cards()

    if not cards:
        print("[dashboard] No cards found in sayings.csv")
        print(f"[dashboard] File exists: {MASTER_CSV.exists()}")
        if MASTER_CSV.exists():
            print(f"[dashboard] File size: {MASTER_CSV.stat().st_size} bytes")
        return 0

    print(f"[dashboard] Loaded {len(cards)} cards from sayings.csv")
    print("[dashboard] Generating dashboard markdown...")

    markdown = generate_dashboard(cards)

    # Option to print to stdout for testing
    if os.getenv("DASHBOARD_STDOUT") == "1":
        print("\n" + "="*60)
        print(markdown)
        print("="*60 + "\n")
        return 0

    print("[dashboard] Writing to Apple Notes...")
    success = write_to_apple_notes(markdown)

    if success:
        print("[dashboard] ✓ Dashboard updated successfully in Apple Notes")
        print("[dashboard] Open Notes app and look for '🇵🇹 Portuguese Learning Overview'")
        return 0
    else:
        print("[dashboard] ✗ Failed to update Apple Notes", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
