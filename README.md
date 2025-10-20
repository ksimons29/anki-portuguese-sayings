# 🇵🇹 Anki Portuguese Automation System
*Updated: 2025-10-20*

End-to-end workflow to capture and automate Portuguese vocabulary from iPhone, iPad, or MacBook into Anki using GPT and AnkiConnect.

---

## 🧠 How It Works

1. You add English or Portuguese words on any Apple device (iPhone, iPad, MacBook).
2. These are saved into:
   ```
   ~/Library/CloudStorage/iCloud Drive/Portuguese/Anki/inbox/quick.jsonl
   ```
3. A macOS LaunchAgent runs a pipeline **automatically at 09:00 Lisbon time** each day.
4. The pipeline does the following:
   - Opens Anki (ensures AnkiConnect is available)
   - Runs `sanitize_quick_jsonl.py` to clean quotes and unicode
   - Calls GPT (OpenAI) using `transform_inbox_to_csv.py`
   - Generates the following:
     - `word_pt`, `word_en`, `sentence_pt`, `sentence_en`, `date_added`
   - Ensures no duplicates (checked against `sayings.csv`)
   - Adds new notes to Anki (deck: `Portuguese (pt‑PT)`, model: `GPT Vocabulary Automater`)
   - Moves processed file to `.done` archive
   - Logs success or failure

---

## 🗂️ Project Structure

```bash
anki-tools/
├── transform_inbox_to_csv.py       # Core logic: GPT + Anki note creation
├── sanitize_quick_jsonl.py         # Cleans jsonl file (unicode, dashes, etc.)
├── check_anki_adds_today.py        # Checks what cards were added today
├── check_openai_key.py             # Verifies your OpenAI API key works
├── run_pipeline.sh                 # End-to-end orchestrator script
├── com.anki.sync.quickjsonl.plist  # macOS LaunchAgent to run pipeline
├── inbox/                          # Holds `quick.jsonl` input file
├── logs/                           # Log files for every automation run
└── sayings.csv                     # Master Anki-import file with all cards
```

---

## 🔄 Automation Details

### LaunchAgent

- File: `~/Library/LaunchAgents/com.anki.sync.quickjsonl.plist`
- Runs: every day at **09:00 Lisbon time**
- Launches: `run_pipeline.sh`
- API key is passed via environment variable

#### Launch Control

```bash
# Reload agent (e.g. after plist edit)
launchctl unload ~/Library/LaunchAgents/com.anki.sync.quickjsonl.plist
launchctl load ~/Library/LaunchAgents/com.anki.sync.quickjsonl.plist

# Check it’s active
launchctl list | grep quickjsonl
```

---

## 🧪 Manual Testing

### 1. Trigger the full pipeline

```bash
cd ~/anki-tools
zsh run_pipeline.sh
```

### 2. Run transformer directly (requires OpenAI key + Anki open)

```bash
/opt/homebrew/bin/python3 transform_inbox_to_csv.py
```

### 3. Verify what was added today

```bash
/opt/homebrew/bin/python3 check_anki_adds_today.py
```

### 4. Check if OpenAI key is working

```bash
/opt/homebrew/bin/python3 check_openai_key.py
```

---

## 🛠️ Logs & Output

### System Logs
```
/tmp/anki_vocab_sync.log
/tmp/anki_vocab_sync.err
```

### Archived Inputs
```
~/Library/CloudStorage/iCloud Drive/Portuguese/Anki/inbox/quick.YYYYMMDD.done
```

### All logs also saved to:
```
~/Library/CloudStorage/iCloud Drive/Portuguese/Anki/logs/
```

---

## ✅ Confirming Automation

- To check if your LaunchAgent worked this morning:
```bash
cat /tmp/anki_vocab_sync.log
```
- Look for:
```
[2025-10-21 09:00:00] No inbox items.
```

---

## 🧩 Tip for Sleep Prevention (Mac)

To ensure your Mac stays awake for automation:
- Use **Amphetamine** or similar app.
- Schedule active time between **08:55 and 09:10**.

---

## 🎯 Summary

| Item | Description |
|------|-------------|
| `transform_inbox_to_csv.py` | Converts `quick.jsonl` into Anki cards |
| `run_pipeline.sh` | Main shell runner that calls Anki + GPT |
| `com.anki.sync.quickjsonl.plist` | Schedules script daily at 09:00 |
| `quick.jsonl` | Your manually added words go here |
| `sayings.csv` | Full Anki-import file, auto-updated |
| `logs/` | All logs from pipeline runs |

---

Created & maintained by **Koos Simons 🇵🇹**