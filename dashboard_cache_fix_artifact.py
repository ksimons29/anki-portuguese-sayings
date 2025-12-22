#!/usr/bin/env python3
"""
Dashboard Browser Cache Fix - Artifact
=======================================

Problem: The dashboard HTML file was being cached by browsers (Chrome, Safari)
         when opened via file:// protocol. Meta http-equiv cache headers do NOT
         work for local files - they are only effective over HTTP.

Solution: Generate dashboard files with unique timestamps in the filename.
          A new filename = a new browser cache entry = guaranteed fresh content.

This artifact contains the complete fix applied to generate_dashboard_html.py
"""

import glob
import os
from datetime import datetime
from pathlib import Path


# ============================================================================
# CLEANUP FUNCTION (added before main())
# ============================================================================

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


# ============================================================================
# FILENAME GENERATION (modified in main())
# ============================================================================

def generate_dashboard_filename() -> str:
    """Generate a unique dashboard filename with timestamp.

    Returns:
        Filename like 'Portuguese-Dashboard-20251222_150000.html'
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"Portuguese-Dashboard-{timestamp}.html"


# ============================================================================
# EXAMPLE USAGE (how it's used in main())
# ============================================================================

def example_main():
    """Example showing how the fix is applied in the main() function."""

    # Simulated paths (actual paths from generate_dashboard_html.py)
    BASE = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/Portuguese/Anki"

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

    print(f"[dashboard] Would save to: {output_path}")
    print(f"[dashboard] Would copy to: {desktop_path}")

    return filename


# ============================================================================
# WHAT WAS REMOVED (ineffective for file:// protocol)
# ============================================================================

REMOVED_META_TAGS = """
These meta tags were removed from the HTML template because they do NOT work
for local files opened via file:// protocol:

    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">

Why they don't work:
- http-equiv tags are designed to simulate HTTP headers
- When opening file:///path/to/file.html, there is no HTTP transaction
- The browser's file system handler ignores these completely
- Only works when served via HTTP/HTTPS from a web server
"""


# ============================================================================
# SUMMARY OF CHANGES
# ============================================================================

CHANGES_SUMMARY = """
Files Modified:
- generate_dashboard_html.py

Changes Made:
1. Added 'import glob' (line 22)
2. Added cleanup_old_dashboards() function (before main())
3. Modified main() to generate timestamped filenames
4. Removed ineffective meta http-equiv cache tags from HTML template

Expected Behavior:
- Each dashboard run creates: Portuguese-Dashboard-YYYYMMDD_HHMMSS.html
- Old files are automatically cleaned up (keeps last 3)
- Browser treats each new file as fresh (no cache conflicts)
- Works on macOS Chrome, iOS Safari/Files app, and all other browsers
"""


if __name__ == "__main__":
    print("Dashboard Cache Fix - Artifact")
    print("=" * 50)
    print()
    print("Testing filename generation:")
    filename = example_main()
    print()
    print(f"Generated filename: {filename}")
    print()
    print(CHANGES_SUMMARY)
