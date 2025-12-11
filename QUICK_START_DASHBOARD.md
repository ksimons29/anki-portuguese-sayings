# 🚀 Quick Start — Dashboard Add-On

## What This Does

Adds **2 optional features** to your existing Anki workflow:

1. **Voice Memos transcription** (for longer Portuguese conversations)
2. **Auto-generated dashboard** in Apple Notes (shows your learning progress)

**Your existing "Save to AnkiInbox" Shortcut stays your primary capture method!**

---

## 5-Minute Setup

### 1. Enable Voice Transcription (iPhone/iPad)
```
Settings → Voice Memos → Transcription → ON
Voice Memos app → Create folder "Portuguese"
```

### 2. Test Dashboard
```bash
cd ~/anki-tools
source .venv/bin/activate
python generate_dashboard.py
```

Check Apple Notes for: **"🇵🇹 Portuguese Learning Overview"**

### 3. Done!
- Dashboard auto-updates **daily at 21:00**
- Voice Memos now transcribe Portuguese automatically

---

## Daily Usage

### Quick Word Capture (Primary — Unchanged)
1. Open "Save to AnkiInbox" Shortcut
2. Voice or Type → Submit
3. Pipeline handles the rest ✅

### Long Conversation (New Optional)
1. Record in Voice Memos
2. Copy transcription
3. Paste in Apple Notes (organize by topic)
4. Extract interesting words
5. Use "Save to AnkiInbox" Shortcut to add them ✅

### View Progress (New)
1. Open Apple Notes
2. Search: "🇵🇹 Portuguese Learning Overview"
3. See all your cards organized by category ✅

---

## What the Dashboard Shows

- Total cards count
- Cards added this week/month
- All cards organized by:
  - 💪 Gym
  - ❤️ Dating
  - 💼 Work
  - 📋 Admin
  - 🏡 Daily Life
  - 🔍 Other
- Insights about strong/weak areas

---

## Manual Dashboard Update

If you want to update dashboard outside of 21:00:

```bash
cd ~/anki-tools
source .venv/bin/activate
python generate_dashboard.py
```

---

## Full Documentation

See **DASHBOARD_SETUP.md** for:
- Detailed setup instructions
- Troubleshooting
- Customizing keywords
- Example outputs

---

That's it! Your existing workflow is unchanged, these are just optional add-ons. 🎉
