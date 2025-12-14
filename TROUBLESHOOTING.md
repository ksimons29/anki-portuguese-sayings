# Troubleshooting: Words Not Appearing

Your quick.jsonl entries aren't being processed. Follow these steps to diagnose the issue:

## Step 1: Pull Latest Changes

First, make sure you have the latest fixes:

```bash
cd ~/anki-tools
git fetch origin
git checkout claude/fix-words-not-showing-gkxvQ
git pull origin claude/fix-words-not-showing-gkxvQ
```

## Step 2: Run Environment Test

This will check your Python environment, packages, and paths:

```bash
cd ~/anki-tools
python3 test_environment.py
```

**What to look for:**
- ❌ Missing packages? → Follow the install instructions it shows
- ❌ iCloud path not found? → Note the actual path and we'll fix it
- ❌ OpenAI key not found? → Need to set it up
- ❌ Import errors? → Copy the full error message

## Step 3: Check Your Inbox File

Verify your quick.jsonl file has the entries:

```bash
cat ~/Library/Mobile\ Documents/com~apple~CloudDocs/Portuguese/Anki/inbox/quick.jsonl
```

**Expected output:**
```
{"ts":"2025-12-12 13:19:51","src":"quick","entries":"apontado"}
{"ts":"2025-12-13 16:23:10","src":"quick","entries":"chewing gum"}
{"ts":"2025-12-14 22:48:45","src":"quick","entries":"Dry run"}
{"ts":"2025-12-14 22:49:00","src":"quick","entries":"Sunset"}
```

If the file doesn't exist or has a different path, note the actual location.

## Step 4: Run Comprehensive Diagnostics

```bash
cd ~/anki-tools
./diagnose_inbox.sh
```

This checks:
- iCloud paths
- quick.jsonl location and contents
- Python packages
- OpenAI API key
- Recent logs and errors

**Copy the entire output** - it will show exactly what's wrong.

## Step 5: Test in Dry-Run Mode

Try running the pipeline in dry-run mode to see what errors occur:

```bash
cd ~/anki-tools
bash run_pipeline.sh --dry-run 2>&1 | tee /tmp/pipeline-test.log
```

This will:
- ✓ NOT modify any files
- ✓ Show all processing steps
- ✓ Reveal any errors
- ✓ Save output to /tmp/pipeline-test.log

**Look for:**
- `[ERROR]` messages
- `ModuleNotFoundError`
- `FileNotFoundError`
- `[INFO] Will process X item(s)` ← Should show 4 items

## Step 6: Check Recent Logs

If you've run the pipeline before, check the logs:

```bash
# Today's log
cat ~/Library/Mobile\ Documents/com~apple~CloudDocs/Portuguese/Anki/logs/pipeline.$(date +%Y-%m-%d).log

# Today's errors
cat ~/Library/Mobile\ Documents/com~apple~CloudDocs/Portuguese/Anki/logs/pipeline.$(date +%Y-%m-%d).err
```

## Common Issues & Fixes

### Issue 1: Virtual Environment Not Set Up

**Symptom:** `ModuleNotFoundError: No module named 'openai'`

**Fix:**
```bash
cd ~/anki-tools
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Issue 2: Google Sheets Credentials Missing

**Symptom:** `[WARN] Google Sheets unavailable` or similar

**Fix:** Either:
- Set up Google Sheets credentials (see GOOGLE_SHEETS_SETUP.md), OR
- Force CSV mode: Add `--use-csv` flag to run_pipeline.sh

**To force CSV mode:**
Edit `~/anki-tools/run_pipeline.sh` and change line ~237 to:
```bash
declare -a PY_ARGS=(
  --deck "$DECK"
  --model "$MODEL"
  --inbox-file "$SCRATCH"
  --limit "$LIMIT"
  --log-level "$LOG_LEVEL"
  --use-csv           # ← ADD THIS LINE
)
```

### Issue 3: OpenAI API Key Not Set

**Symptom:** `[ERROR] OPENAI_API_KEY not set and not found in Keychain`

**Fix:**
```bash
# Replace sk-YOUR_KEY_HERE with your actual OpenAI API key
security add-generic-password -a "$USER" -s "anki-tools-openai" -w 'sk-YOUR_KEY_HERE' -U

# If you have a project key, also set:
security add-generic-password -a "$USER" -s "anki-tools-openai-project" -w 'proj-YOUR_PROJECT_ID' -U
```

### Issue 4: Anki Not Running

**Symptom:** `[anki] AnkiConnect not ready after 30s`

**Fix:**
- Make sure Anki desktop app is running
- Ensure AnkiConnect add-on is installed
- Try: `curl http://127.0.0.1:8765 -X POST -d '{"action":"version","version":6}'`
  - Should return: `{"result":5,"error":null}`

### Issue 5: iCloud Path Different

**Symptom:** `[err] iCloud root not found`

**Fix:** Check your actual iCloud path:
```bash
ls -la ~/Library/Mobile\ Documents/
ls -la ~/Library/CloudStorage/
```

If your path is different, set the `ANKI_BASE` environment variable:
```bash
export ANKI_BASE="/path/to/your/Portuguese/Anki"
bash run_pipeline.sh --dry-run
```

## After Fixing Issues

Once you've fixed any issues found above:

1. **Test again in dry-run:**
   ```bash
   cd ~/anki-tools
   bash run_pipeline.sh --dry-run
   ```

   Should see:
   ```
   [inbox] Processing 4 JSON entries from inbox
   [norm] 'apontado' -> 'apontado' (rule: short-phrase)
   [norm] 'chewing gum' -> 'chewing gum' (rule: short-phrase)
   [norm] 'Dry run' -> 'Dry run' (rule: short-phrase)
   [norm] 'Sunset' -> 'Sunset' (rule: short-phrase)
   [INFO] Will process 4 item(s).
   ```

2. **Run for real:**
   ```bash
   cd ~/anki-tools
   bash run_pipeline.sh
   ```

   Should see:
   ```
   [OK] 1/4  apontado -> [Portuguese word]
   [OK] 2/4  chewing gum -> [Portuguese translation]
   ...
   [inbox] ✓ Archived 4 lines to quick.2025-12-14_HHMMSS.jsonl
   [inbox] ✓ Cleared quick.jsonl (now empty)
   ```

## Send Me the Output

If you're still stuck, run these commands and send me the output:

```bash
cd ~/anki-tools

# 1. Environment test
echo "=== ENVIRONMENT TEST ===" > /tmp/debug.txt
python3 test_environment.py >> /tmp/debug.txt 2>&1

# 2. Diagnostics
echo -e "\n\n=== DIAGNOSTICS ===" >> /tmp/debug.txt
./diagnose_inbox.sh >> /tmp/debug.txt 2>&1

# 3. Dry run test
echo -e "\n\n=== DRY RUN TEST ===" >> /tmp/debug.txt
bash run_pipeline.sh --dry-run >> /tmp/debug.txt 2>&1

# Show the file
cat /tmp/debug.txt
```

Copy the entire output and share it with me.
