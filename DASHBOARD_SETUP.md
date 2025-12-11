# 🎙️ Audio Capture & Dashboard Add-On Setup

This add-on provides **two optional features** to complement your existing Anki workflow:

1. **Audio Recording & Transcription** — Capture longer Portuguese conversations with context
2. **Anki Overview Dashboard** — See your learning progress in Apple Notes

**Important**: Your existing "Save to AnkiInbox" Shortcut workflow remains your **primary** method for adding words. This is just an add-on!

---

## ✅ What Stays the Same

Your core workflow is **unchanged**:
- ✅ "Save to AnkiInbox" Shortcut (Voice/Type) → `quick.jsonl`
- ✅ Pipeline runs 4x daily (09:00, 13:00, 17:00, 21:00)
- ✅ GPT enrichment → Anki cards
- ✅ All existing Python scripts

---

## 🆕 What's New

### 1. Audio Recording (Optional)
Use when you want to capture **longer conversations** with full context:
- Record in Voice Memos
- iOS/macOS auto-transcribes
- Store in Apple Notes
- Extract words later → Use your **existing Shortcut**

### 2. Dashboard (Automatic)
- Runs once daily at **21:00**
- Reads your `sayings.csv`
- Generates overview in Apple Notes
- Shows categories, counts, all cards

---

## 📱 Part 1: Voice Memos Setup (5 min)

### iPhone & iPad

1. **Enable Transcription**:
   - Open **Settings** → **Voice Memos**
   - Toggle **Transcription** → **ON**

2. **Create Folder**:
   - Open **Voice Memos** app
   - Tap **Browse** (bottom right)
   - Tap **Edit** → **New Folder**
   - Name it: `Portuguese`

3. **Test It**:
   - Tap **Record** button
   - Say a Portuguese sentence: "Bom dia, como estás?"
   - Stop recording
   - Tap the recording → You should see transcription text appear

### Mac

1. **Create Folder**:
   - Open **Voice Memos** app
   - Click **New Folder** in sidebar
   - Name it: `Portuguese`

2. **Test It**:
   - Click **Record** button
   - Say a Portuguese sentence
   - Stop recording
   - Transcription will appear (requires macOS Sonoma 14+)

---

## 📝 Part 2: Apple Notes Setup (5 min)

### Create Note Structure

Open **Notes** app and create these notes:

```
📁 Portuguese Learning/
├── 📄 Gym Conversations
├── 📄 Dating Conversations
├── 📄 Work Conversations
├── 📄 Admin Conversations
└── 📄 Daily Life Conversations
```

**Or keep it simpler**: Just create one note called **"Portuguese Transcripts"** and append everything there with dates.

### Example Note Format

```markdown
---
📅 2025-12-11 — Gym
---
Bom dia! Queria aumentar a carga hoje.
Quanto é que devo adicionar à barra?
Acho que consigo fazer mais três repetições.

Words to add:
- aumentar a carga
- barra
- repetições

---
📅 2025-12-11 — Grocery Store
---
Bom dia, onde estão os tomates?
Quanto custa um quilo de bananas?

Words to add:
- quilo
- bananas
```

---

## 🔄 Part 3: Daily Workflow Examples

### Scenario A: Quick Word (Your Main Method — Unchanged)

1. Hear a new word: "ginásio"
2. Open **"Save to AnkiInbox"** Shortcut
3. Choose **Voice** → Speak word
4. Done! ✅

### Scenario B: Longer Conversation (New Optional Method)

1. **At gym**: Open Voice Memos → Hit record
2. **While talking**: Keep recording the conversation
3. **After workout**:
   - Stop recording
   - iOS shows transcription text
   - Tap transcription → **Copy**
4. **Open Apple Notes** → Open "Gym Conversations"
5. **Paste** transcript
6. Add date header: `📅 2025-12-11`
7. **Review transcript** → Identify interesting words:
   - "aumentar a carga"
   - "fazer agachamentos"
8. **For each word**:
   - Copy word
   - Open **"Save to AnkiInbox"** Shortcut
   - Choose **Type**
   - Paste word
   - Submit
9. Done! ✅

**Key Point**: The audio transcription is just for **context preservation**. You still add words through your **existing Shortcut**.

---

## 📊 Part 4: Dashboard Overview

### What It Shows

The dashboard is an **auto-generated Apple Note** that shows:

1. **Summary Stats**:
   - Total cards
   - Cards added this week/month
   - Most active category

2. **Categories with ALL Cards**:
   - 💪 Gym
   - ❤️ Dating
   - 💼 Work
   - 📋 Admin
   - 🏡 Daily Life
   - 🔍 Other

3. **Insights**:
   - Strongest areas
   - Underrepresented topics
   - Recent momentum

### Example Dashboard Output

```markdown
# 🇵🇹 Portuguese Learning Overview
Last updated: 2025-12-11 21:00

## 📊 Summary
- **Total cards**: 487
- **Added this week**: 23
- **Added this month**: 89
- **Most active area**: 🏡 Daily Life (203 cards)

---

## 📂 By Category

### 🏡 Daily Life — 203 cards (41.7%)

• **limpar a casa** → clean the house `2025-12-10`
• **fazer compras** → do shopping `2025-12-09`
• **cozinhar o jantar** → cook dinner `2025-12-08`
• **lavar a loiça** → wash the dishes `2025-12-08`
• **dormir cedo** → sleep early `2025-12-07`
... [all 203 cards listed]

---

### 💪 Gym — 89 cards (18.3%)

• **aumentar a carga** → increase the weight `2025-12-11`
• **fazer agachamentos** → do squats `2025-12-11`
• **alongar os músculos** → stretch the muscles `2025-12-10`
• **treino de peito** → chest workout `2025-12-09`
... [all 89 cards listed]

---

### 💼 Work — 67 cards (13.8%)

• **reunião de equipa** → team meeting `2025-12-10`
• **prazo de entrega** → deadline `2025-12-09`
• **enviar um e-mail** → send an email `2025-12-08`
... [all 67 cards listed]

---

### ❤️ Dating — 54 cards (11.1%)

• **marcar um encontro** → set up a date `2025-12-11`
• **jantar romântico** → romantic dinner `2025-12-10`
... [all 54 cards listed]

---

### 📋 Admin — 34 cards (7.0%)

• **preencher um formulário** → fill out a form `2025-12-09`
• **pagar uma conta** → pay a bill `2025-12-08`
... [all 34 cards listed]

---

### 🔍 Other — 40 cards (8.2%)

• **qualquer coisa** → anything `2025-12-05`
... [all 40 cards listed]

---

## 🎯 Insights

• Your strongest area is **🏡 Daily Life** with 203 cards
• **📋 Admin** has only 34 cards — consider capturing more!
• Great momentum: 23 new cards this week!

---

*Auto-generated from sayings.csv (487 cards)*
```

### When Dashboard Updates

- **Automatically** at **21:00** (after final pipeline run)
- Dashboard note appears in Apple Notes with title: **"🇵🇹 Portuguese Learning Overview"**

---

## 🧪 Part 5: Testing the Dashboard

### Test Dashboard Generation

```bash
# Navigate to anki-tools directory
cd ~/anki-tools

# Activate Python environment
source .venv/bin/activate

# Test dashboard generation (prints to stdout, doesn't write to Notes)
DASHBOARD_STDOUT=1 python generate_dashboard.py

# If that looks good, test writing to Apple Notes
python generate_dashboard.py

# Check Apple Notes - should see "🇵🇹 Portuguese Learning Overview"
```

### Verify Dashboard in Apple Notes

1. Open **Notes** app
2. Search for: `🇵🇹 Portuguese Learning Overview`
3. You should see the dashboard with all your cards categorized

### Manual Dashboard Update

If you want to update the dashboard manually (outside of 21:00):

```bash
cd ~/anki-tools
source .venv/bin/activate
python generate_dashboard.py
```

---

## 🎯 How Topic Classification Works

Cards are automatically classified by **keyword matching** in both English and Portuguese text.

### Keywords by Category

**💪 Gym**: gym, workout, exercise, weight, muscle, squat, bench, cardio, trainer, fitness, treino, músculo, peso, academia, exercício, barra, carga, alongar, repetições

**❤️ Dating**: date, dinner, romantic, relationship, girlfriend, boyfriend, kiss, love, restaurant, encontro, jantar, romântico, namorad, amor, beijo, casal

**💼 Work**: work, office, meeting, email, deadline, colleague, boss, project, trabalho, escritório, reunião, colega, prazo, projeto, equipa

**📋 Admin**: form, document, bureaucracy, payment, bill, passport, formulário, documento, pagamento, conta, passaporte, renovar, visto, imposto

**🏡 Daily Life**: home, shopping, cooking, cleaning, house, kitchen, food, compras, casa, cozinha, comida, limpar, lavar, dormir, acordar

**🔍 Other**: Anything that doesn't match above keywords

### Customizing Keywords

To add/remove keywords, edit `~/anki-tools/generate_dashboard.py`:

```python
TOPIC_KEYWORDS = {
    "💪 Gym": [
        # Add your custom keywords here
        "musculação", "personal trainer", "proteína",
        # ...
    ],
    # ...
}
```

After editing, test with:
```bash
cd ~/anki-tools
source .venv/bin/activate
DASHBOARD_STDOUT=1 python generate_dashboard.py
```

---

## 🔧 Troubleshooting

### Dashboard not updating?

**Check 1**: Verify the script is installed
```bash
ls -la ~/anki-tools/generate_dashboard.py
```

**Check 2**: Check the 21:00 log
```bash
tail -100 ~/Library/Mobile\ Documents/com~apple~CloudDocs/Portuguese/Anki/logs/pipeline.$(date +%F).log | grep dashboard
```

**Check 3**: Run manually to see errors
```bash
cd ~/anki-tools
source .venv/bin/activate
python generate_dashboard.py
```

### Voice Memos not transcribing?

- **iOS/iPadOS**: Requires iOS 17+ with on-device intelligence
- **macOS**: Requires macOS Sonoma 14+
- **Language**: Make sure Portuguese keyboard is installed
- **First time**: Transcription may take 30-60 seconds to appear

### Transcription in wrong language?

- Voice Memos auto-detects language after first few words
- Speak clearly in Portuguese for first 5-10 seconds
- If it defaults to English, wait for it to correct itself
- Or manually set language: Settings → Voice Memos → Language → Portuguese

---

## 📚 Summary

### What You Now Have

1. ✅ **Your existing Shortcut workflow** (unchanged, still primary)
2. ✅ **Voice Memos transcription** (optional, for longer context)
3. ✅ **Apple Notes organization** (optional, for storing transcripts)
4. ✅ **Auto-generated dashboard** (runs daily at 21:00)

### Daily Flow

**Morning**: Record gym conversation → Transcribe → Store in Notes
**Midday**: Review notes → Extract interesting words → **Use existing Shortcut**
**Evening (21:00)**: Pipeline runs → Dashboard auto-updates
**Night**: Check dashboard in Notes → See your progress

### Key Principle

**Voice Memos + Apple Notes** = Context preservation
**Your Existing Shortcut** = Primary word capture
**Dashboard** = Progress overview

Everything feeds into your existing `quick.jsonl` → `sayings.csv` → Anki pipeline!

---

## 🎓 Next Steps

1. ✅ Set up Voice Memos transcription (iPhone/iPad/Mac)
2. ✅ Create Apple Notes structure
3. ✅ Test dashboard generation: `python ~/anki-tools/generate_dashboard.py`
4. ✅ Record a test Voice Memo in Portuguese
5. ✅ Transcribe it and paste into Notes
6. ✅ Extract a word using your **existing "Save to AnkiInbox" Shortcut**
7. ✅ Wait for 21:00 or run pipeline manually
8. ✅ Check Apple Notes for dashboard

Happy learning! 🇵🇹
