# 📊 How to Open Your Dashboard

## Quick Access (No Terminal Needed!)

### On Mac:
1. Open **Notes** app (⌘ + Space, type "Notes")
2. In the search bar, type: `Portuguese Learning Overview`
3. Click the note that appears

**Or:**
1. Open **Notes** app
2. Look for the note with 🇵🇹 emoji: **"🇵🇹 Portuguese Learning Overview"**

### On iPhone/iPad:
1. Open **Notes** app
2. Tap the search icon (magnifying glass)
3. Type: `Portuguese Learning Overview`
4. Tap the note

---

## First Time Setup

Run this **once** to create the dashboard:

```bash
cd ~/anki-tools
git pull origin claude/apple-anki-portuguese-workflow-015jhBxxAsn9atLhGspFuobz
source .venv/bin/activate
python generate_dashboard.py
```

You should see:
```
[dashboard] Looking for sayings.csv at: ...
[dashboard] Loaded 627 cards from sayings.csv
[dashboard] ✓ Dashboard updated successfully in Apple Notes
```

---

## Automatic Updates

After the first run, the dashboard automatically updates **every day at 21:00** when your pipeline runs.

No action needed! Just open Notes to see your latest progress.

---

## Manual Refresh (Optional)

If you want to refresh the dashboard outside of 21:00:

```bash
cd ~/anki-tools
source .venv/bin/activate
python generate_dashboard.py
```

---

## Troubleshooting

### "No cards found"

Check if the file exists:
```bash
ls -lh "$HOME/Library/CloudStorage/iCloud Drive/Portuguese/Anki/sayings.csv"
```

Should show ~127 KB (627 cards)

### Dashboard shows fewer than 627 cards

Run with debug output:
```bash
cd ~/anki-tools
source .venv/bin/activate
python generate_dashboard.py
```

Look for the line: `[dashboard] Loaded XXX cards`

If it says 627 but the Note doesn't show all of them, the cards are grouped by category. Scroll down to see all sections!

---

## What You'll See

```
════════════════════════════════════════════════════════════
🇵🇹  PORTUGUESE LEARNING OVERVIEW
════════════════════════════════════════════════════════════

📅  Last updated: Wednesday, December 11, 2025 at 16:40
📊  Total vocabulary: 627 cards

────────────────────────────────────────────────────────────

📈  RECENT ACTIVITY
  This week:     23 new cards
  This month:    89 new cards
  ...

════════════════════════════════════════════════════════════

💪 Gym  •  89 cards  •  14.2%
────────────────────────────────────────────────────────────

Word (Portuguese)        Translation (English)          Added
────────────────────────────────────────────────────────────
aumentar a carga         increase the weight            2025-12-11
fazer agachamentos       do squats                      2025-12-10
...

[All 627 cards organized by category]
```

---

That's it! The dashboard is just a regular Apple Note that syncs across all your devices. 🎉
