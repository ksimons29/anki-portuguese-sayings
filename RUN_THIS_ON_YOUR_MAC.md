# 🔧 Run This On Your Mac

Since the changes are in the repository but not working when you run the pipeline on your Mac, follow these steps **on your actual Mac** (not in this coding environment):

## Quick Start (Copy & Paste These Commands)

Open Terminal on your Mac and run:

```bash
# 1. Go to your anki-tools directory
cd ~/anki-tools

# 2. Pull the latest fixes
git fetch origin
git checkout claude/fix-words-not-showing-gkxvQ
git pull origin claude/fix-words-not-showing-gkxvQ

# 3. Run the environment test
python3 test_environment.py
```

## What You'll See

The environment test will show you exactly what's wrong. Here are the possible issues:

### ✅ Everything OK
```
=== Environment Check ===
1. Python: 3.x.x
2. Checking required packages:
   ✓ openai - OpenAI API client
   ✓ requests - HTTP library
   ...
```
→ **Skip to "Test the Pipeline" below**

### ❌ Missing Packages
```
2. Checking required packages:
   ✗ openai - OpenAI API client - MISSING
   ...
```
→ **Fix:** Run these commands:
```bash
cd ~/anki-tools
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### ❌ Wrong iCloud Path
```
3. Checking paths:
   ✗ iCloud path not found
```
→ **Fix:** Find your actual path:
```bash
ls ~/Library/Mobile\ Documents/ | grep -i icloud
ls ~/Library/CloudStorage/ | grep -i icloud
```
Then tell me what you see.

### ❌ No API Key
```
4. Checking OpenAI API key:
   ✗ Not found in Keychain
```
→ **Fix:** Set your OpenAI API key:
```bash
security add-generic-password -a "$USER" -s "anki-tools-openai" -w 'sk-YOUR_ACTUAL_KEY' -U
```

## Test the Pipeline

After fixing any issues, test in dry-run mode:

```bash
cd ~/anki-tools
bash run_pipeline.sh --dry-run 2>&1 | tee ~/Desktop/pipeline-test.log
```

This will:
- ✅ NOT modify any files
- ✅ Show you exactly what would happen
- ✅ Save output to your Desktop for review

**Look for these lines:**
```
[inbox] Processing 4 JSON entries from inbox
[norm] 'apontado' -> 'apontado' (rule: short-phrase)
[norm] 'chewing gum' -> 'chewing gum' (rule: short-phrase)
[norm] 'Dry run' -> 'Dry run' (rule: short-phrase)
[norm] 'Sunset' -> 'Sunset' (rule: short-phrase)
[INFO] Will process 4 item(s).
```

## If It Works in Dry-Run

Run it for real:

```bash
cd ~/anki-tools
bash run_pipeline.sh
```

You should see:
- Processing messages for each word
- `[OK] 1/4 apontado -> [Portuguese word]`
- `[inbox] ✓ Archived 4 lines to quick.TIMESTAMP.jsonl`
- `[inbox] ✓ Cleared quick.jsonl (now empty)`

Then check:
- **Anki:** Should have 4 new cards in "Portuguese Mastery (pt-PT)" deck
- **Google Sheets** (if configured): 4 new rows
- **CSV:** `~/Library/Mobile Documents/com~apple~CloudDocs/Portuguese/Anki/sayings.csv` updated

## Still Not Working?

Run the full diagnostics and send me the output:

```bash
cd ~/anki-tools

# Create debug file
echo "=== ENVIRONMENT TEST ===" > ~/Desktop/anki-debug.txt
python3 test_environment.py >> ~/Desktop/anki-debug.txt 2>&1

echo -e "\n\n=== DIAGNOSTICS ===" >> ~/Desktop/anki-debug.txt
./diagnose_inbox.sh >> ~/Desktop/anki-debug.txt 2>&1

echo -e "\n\n=== DRY RUN TEST ===" >> ~/Desktop/anki-debug.txt
bash run_pipeline.sh --dry-run >> ~/Desktop/anki-debug.txt 2>&1

echo -e "\n\nDebug file created on Desktop"
open ~/Desktop/anki-debug.txt
```

Then:
1. Open `~/Desktop/anki-debug.txt` that just opened
2. Copy the entire contents
3. Send it to me

I'll tell you exactly what's wrong and how to fix it.

## Quick Reference

| Command | What It Does |
|---------|--------------|
| `python3 test_environment.py` | Quick check of Python, packages, paths |
| `./diagnose_inbox.sh` | Comprehensive diagnostics |
| `bash run_pipeline.sh --dry-run` | Test without modifying files |
| `bash run_pipeline.sh` | Run for real |
| `cat ~/Library/Mobile\ Documents/com~apple~CloudDocs/Portuguese/Anki/inbox/quick.jsonl` | See your inbox entries |

---

**Remember:** You need to run these commands **on your Mac**, not in the development environment where I created the fixes.
