#!/usr/bin/env python3
"""
Quick environment test - run this to see what's failing
"""
import sys
from pathlib import Path

print("=== Environment Check ===\n")

# 1. Python version
print(f"1. Python: {sys.version}")
print()

# 2. Check imports
print("2. Checking required packages:")
packages = {
    'openai': 'OpenAI API client',
    'requests': 'HTTP library',
    'gspread': 'Google Sheets (optional)',
    'google.oauth2': 'Google Auth (optional)',
}

missing = []
for pkg, desc in packages.items():
    try:
        __import__(pkg)
        print(f"   ✓ {pkg} - {desc}")
    except ImportError:
        print(f"   ✗ {pkg} - {desc} - MISSING")
        missing.append(pkg)
print()

# 3. Check paths
print("3. Checking paths:")
home = Path.home()
icloud = home / "Library/Mobile Documents/com~apple~CloudDocs/Portuguese/Anki"
alt_icloud = home / "Library/CloudStorage/iCloud Drive/Portuguese/Anki"

if icloud.exists():
    print(f"   ✓ iCloud path: {icloud}")
    inbox = icloud / "inbox/quick.jsonl"
    if inbox.exists():
        lines = len(inbox.read_text().strip().split('\n')) if inbox.stat().st_size > 0 else 0
        print(f"   ✓ quick.jsonl exists: {lines} lines")
    else:
        print(f"   ✗ quick.jsonl not found: {inbox}")
elif alt_icloud.exists():
    print(f"   ✓ iCloud path (alt): {alt_icloud}")
else:
    print(f"   ✗ iCloud path not found")
    print(f"      Checked: {icloud}")
    print(f"      Checked: {alt_icloud}")
print()

# 4. Check API key
print("4. Checking OpenAI API key:")
import subprocess
try:
    result = subprocess.run(
        ['security', 'find-generic-password', '-a', Path.home().name, '-s', 'anki-tools-openai', '-w'],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        key = result.stdout.strip()
        print(f"   ✓ Found in Keychain: {key[:8]}...")
    else:
        print(f"   ✗ Not found in Keychain")
except Exception as e:
    print(f"   ✗ Error checking Keychain: {e}")
print()

# 5. Test transform_inbox_to_csv import
print("5. Testing main script import:")
try:
    sys.path.insert(0, str(Path(__file__).parent))
    import transform_inbox_to_csv
    print(f"   ✓ transform_inbox_to_csv imported successfully")

    # Test the fixed function
    from transform_inbox_to_csv import read_quick_entries, _detect_csv_format
    print(f"   ✓ Key functions available")
except Exception as e:
    print(f"   ✗ Import failed: {e}")
    import traceback
    traceback.print_exc()
print()

# 6. Summary
print("=== Summary ===")
if missing:
    print(f"⚠ Missing packages: {', '.join(missing)}")
    print("\nTo install missing packages:")
    if 'gspread' in missing or 'google.oauth2' in missing:
        print("  cd ~/anki-tools")
        print("  source .venv/bin/activate  # or: python3 -m venv .venv && source .venv/bin/activate")
        print("  pip install -r requirements.txt")
    else:
        print(f"  pip install {' '.join(missing)}")
else:
    print("✓ All required packages installed")
print()
