#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Sheets integration for Portuguese vocabulary storage.

This module provides read/write access to Google Sheets as a replacement
for the local sayings.csv file.

Setup instructions:
1. Install required packages: pip install gspread google-auth
2. Create a Google Cloud project and enable Sheets API
3. Create a service account and download the JSON key file
4. Share your spreadsheet with the service account email
5. Set GOOGLE_SHEETS_CREDENTIALS env var to the path of the JSON key file
   OR place credentials.json in ~/.config/anki-tools/

Spreadsheet format (columns A-E):
  A: word_en
  B: word_pt
  C: sentence_pt
  D: sentence_en
  E: date_added
"""
from __future__ import annotations

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime

# Google Sheets constants
SPREADSHEET_ID = "1q20cEuHXoaLNWJ06i1Nv9Eo2JkJ00LMmPboTYSGz1xg"
SHEET_NAME = "Sheet1"  # Default sheet name, can be overridden

# Column mapping (0-indexed for internal use)
COLUMNS = {
    "word_en": 0,
    "word_pt": 1,
    "sentence_pt": 2,
    "sentence_en": 3,
    "date_added": 4,
}

# Expected headers
HEADERS = ["word_en", "word_pt", "sentence_pt", "sentence_en", "date_added"]


def _get_credentials_path() -> Optional[Path]:
    """Find Google Sheets credentials file."""
    # Check environment variable first
    env_path = os.environ.get("GOOGLE_SHEETS_CREDENTIALS")
    if env_path:
        p = Path(env_path).expanduser()
        if p.exists():
            return p

    # Check common locations
    locations = [
        Path.home() / ".config" / "anki-tools" / "credentials.json",
        Path.home() / ".config" / "gspread" / "service_account.json",
        Path(__file__).parent / "credentials.json",
        Path.home() / "credentials.json",
    ]

    for loc in locations:
        if loc.exists():
            return loc

    return None


def _get_gspread_client():
    """Get authenticated gspread client."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        raise ImportError(
            "Google Sheets integration requires gspread and google-auth packages.\n"
            "Install with: pip install gspread google-auth"
        )

    creds_path = _get_credentials_path()
    if not creds_path:
        raise RuntimeError(
            "Google Sheets credentials not found.\n"
            "Set GOOGLE_SHEETS_CREDENTIALS env var or place credentials.json in ~/.config/anki-tools/"
        )

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    credentials = Credentials.from_service_account_file(str(creds_path), scopes=scopes)
    return gspread.authorize(credentials)


def _get_worksheet(spreadsheet_id: str = SPREADSHEET_ID, sheet_name: str = SHEET_NAME):
    """Get the worksheet object."""
    print(f"[DEBUG] Opening spreadsheet: {spreadsheet_id}")
    print(f"[DEBUG] Spreadsheet ID length: {len(spreadsheet_id)}")
    print(f"[DEBUG] Spreadsheet ID repr: {repr(spreadsheet_id)}")
    client = _get_gspread_client()
    spreadsheet = client.open_by_key(spreadsheet_id)

    try:
        worksheet = spreadsheet.worksheet(sheet_name)
    except Exception:
        # If sheet doesn't exist, use the first sheet
        worksheet = spreadsheet.sheet1

    return worksheet


def _ensure_headers(worksheet) -> bool:
    """Ensure the worksheet has proper headers. Returns True if headers were added."""
    try:
        first_row = worksheet.row_values(1)
    except Exception:
        first_row = []

    if not first_row or first_row != HEADERS:
        # Check if sheet is empty
        if not first_row:
            worksheet.append_row(HEADERS, value_input_option="RAW")
            return True
        # If first row doesn't match headers, check if it looks like data
        # (i.e., no header row exists)
        if first_row[0].lower() not in ["word_en", "word"]:
            # Insert header row at top
            worksheet.insert_row(HEADERS, 1, value_input_option="RAW")
            return True
    return False


def _normalize_sentence_for_key(value: str) -> str:
    """Normalize sentence text for duplicate comparison."""
    import html as html_module

    if not isinstance(value, str):
        return ""
    text = html_module.unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return " ".join(text.split()).strip()


def _sentence_duplicate_key(word_en: str, sentence_pt: str, sentence_en: str) -> Tuple[str, str, str]:
    """Create a normalized key for sentence-level deduplication."""
    return (
        (word_en or "").strip().lower(),
        _normalize_sentence_for_key(sentence_pt),
        _normalize_sentence_for_key(sentence_en),
    )


class GoogleSheetsStorage:
    """
    Google Sheets storage backend for vocabulary data.

    Provides similar interface to the CSV storage but uses Google Sheets.
    """

    def __init__(
        self,
        spreadsheet_id: str = SPREADSHEET_ID,
        sheet_name: str = SHEET_NAME,
    ):
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name
        self._worksheet = None
        self._data_cache = None
        self._cache_time = None

    def _get_worksheet(self):
        """Get or create worksheet connection."""
        if self._worksheet is None:
            self._worksheet = _get_worksheet(self.spreadsheet_id, self.sheet_name)
            _ensure_headers(self._worksheet)
        return self._worksheet

    def _invalidate_cache(self):
        """Invalidate the data cache."""
        self._data_cache = None
        self._cache_time = None

    def get_all_rows(self, use_cache: bool = True) -> List[Dict[str, str]]:
        """
        Get all rows from the spreadsheet.

        Returns list of dicts with keys: word_en, word_pt, sentence_pt, sentence_en, date_added
        """
        # Use cache if available and requested
        if use_cache and self._data_cache is not None:
            return self._data_cache

        worksheet = self._get_worksheet()
        all_values = worksheet.get_all_values()

        if not all_values:
            return []

        # Skip header row
        data_rows = all_values[1:] if all_values[0] == HEADERS else all_values

        rows = []
        for row in data_rows:
            if len(row) >= 5 and row[0].strip():  # Has word_en
                rows.append({
                    "word_en": row[0].strip(),
                    "word_pt": row[1].strip() if len(row) > 1 else "",
                    "sentence_pt": row[2].strip() if len(row) > 2 else "",
                    "sentence_en": row[3].strip() if len(row) > 3 else "",
                    "date_added": row[4].strip() if len(row) > 4 else "",
                })

        self._data_cache = rows
        self._cache_time = datetime.now()
        return rows

    def load_existing_words(self) -> Set[str]:
        """Load all existing word_en values for deduplication."""
        rows = self.get_all_rows()
        return {row["word_en"].lower() for row in rows if row["word_en"]}

    def load_existing_sentence_pairs(self) -> Set[Tuple[str, str, str]]:
        """Load existing sentence pairs for duplicate detection."""
        rows = self.get_all_rows()
        pairs = set()
        for row in rows:
            if row["word_en"]:
                pairs.add(_sentence_duplicate_key(
                    row["word_en"],
                    row["sentence_pt"],
                    row["sentence_en"]
                ))
        return pairs

    def append_rows(self, rows: List[List[str]]) -> int:
        """
        Append rows to the spreadsheet.

        Args:
            rows: List of [word_en, word_pt, sentence_pt, sentence_en, date_added]

        Returns:
            Number of rows appended
        """
        if not rows:
            return 0

        worksheet = self._get_worksheet()

        # Batch append for efficiency
        worksheet.append_rows(rows, value_input_option="RAW")

        self._invalidate_cache()
        return len(rows)

    def append_row(self, row: List[str]) -> bool:
        """Append a single row."""
        return self.append_rows([row]) == 1

    def get_row_count(self) -> int:
        """Get total number of data rows (excluding header)."""
        return len(self.get_all_rows())

    def search_word(self, word: str) -> List[Dict[str, str]]:
        """Search for a word in the spreadsheet."""
        word_lower = word.lower()
        rows = self.get_all_rows()
        return [
            row for row in rows
            if word_lower in row["word_en"].lower() or word_lower in row["word_pt"].lower()
        ]


# Convenience functions for drop-in replacement of CSV functions

_default_storage: Optional[GoogleSheetsStorage] = None


def get_storage() -> GoogleSheetsStorage:
    """Get the default storage instance."""
    global _default_storage
    if _default_storage is None:
        _default_storage = GoogleSheetsStorage()
    return _default_storage


def load_existing_words() -> Set[str]:
    """Load existing word_en values from Google Sheets."""
    return get_storage().load_existing_words()


def load_existing_sentence_pairs() -> Set[Tuple[str, str, str]]:
    """Load existing sentence pairs from Google Sheets."""
    return get_storage().load_existing_sentence_pairs()


def append_rows(rows: List[List[str]]) -> int:
    """Append rows to Google Sheets."""
    return get_storage().append_rows(rows)


def get_all_cards() -> List[Dict[str, str]]:
    """Get all cards from Google Sheets (for dashboard)."""
    return get_storage().get_all_rows()


def is_available() -> bool:
    """Check if Google Sheets integration is available."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        return _get_credentials_path() is not None
    except ImportError:
        return False


if __name__ == "__main__":
    # Test the connection
    print("Testing Google Sheets connection...")
    print(f"[DEBUG] Using SPREADSHEET_ID: {SPREADSHEET_ID}")
    print(f"[DEBUG] SPREADSHEET_ID length: {len(SPREADSHEET_ID)}")
    print(f"[DEBUG] SPREADSHEET_ID repr: {repr(SPREADSHEET_ID)}")

    if not is_available():
        print("ERROR: Google Sheets integration not available.")
        print("Please install: pip install gspread google-auth")
        print("And set up credentials (see module docstring)")
        exit(1)

    try:
        storage = GoogleSheetsStorage()
        rows = storage.get_all_rows()
        print(f"Successfully connected! Found {len(rows)} rows.")

        words = storage.load_existing_words()
        print(f"Unique words: {len(words)}")

        if rows:
            print(f"\nFirst row: {rows[0]}")
            print(f"Last row: {rows[-1]}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        print("\nFull error details:")
        traceback.print_exc()
        exit(1)
