# 🚀 Deployment Guide

## ⚠️ CRITICAL: Source of Truth

**ALL code changes MUST be made in this git repository:**
```
~/anki-portuguese-sayings/
```

**NEVER edit files directly in:**
```
~/anki-tools/
```

The files in `~/anki-tools/` are **symlinks** that point to this repo. Editing them directly will work, but changes won't be version-controlled and can be lost.

---

## 📂 Architecture

```
~/anki-portuguese-sayings/          ← GIT REPO (SOURCE OF TRUTH)
├── generate_dashboard_html.py      ← Edit this file
├── unified_transcribe.py
├── deploy.sh                        ← Deployment script
└── ...

~/anki-tools/                        ← RUNTIME LOCATION
├── generate_dashboard_html.py →    ← SYMLINK to repo version
├── google_sheets.py                 ← Other scripts (not in repo)
└── ...
```

---

## 🔄 Workflow

### Making Changes

1. **Edit in the repo:**
   ```bash
   cd ~/anki-portuguese-sayings
   # Edit generate_dashboard_html.py or other scripts
   ```

2. **Test your changes:**
   ```bash
   cd ~/anki-tools
   source .venv/bin/activate
   python generate_dashboard_html.py
   ```

3. **Commit and push:**
   ```bash
   cd ~/anki-portuguese-sayings
   git add .
   git commit -m "Your change description"
   git push
   ```

### After Git Pull

If you pull changes from another machine:

```bash
cd ~/anki-portuguese-sayings
git pull
./deploy.sh    # Ensures symlinks are correct
```

### If You Suspect Sync Issues

Run the deployment script to fix everything:

```bash
~/anki-portuguese-sayings/deploy.sh
```

This will:
- ✅ Remove any stale copies in `~/anki-tools/`
- ✅ Create fresh symlinks to the repo versions
- ✅ Back up any existing files to `*.backup`

---

## 🛡️ Prevention Measures

**Why This System?**

Previously, we had duplicate copies:
- Repository: `~/anki-portuguese-sayings/generate_dashboard_html.py` (60KB, latest)
- Runtime: `~/anki-tools/generate_dashboard_html.py` (52KB, outdated)

This caused bugs to "come back" because the old version was being run.

**Current Solution:**

1. **Symlinks**: Only ONE actual file exists (in the git repo)
2. **deploy.sh**: Automates the linking process
3. **Documentation**: Clear instructions on where to edit

**The Rule:**
```
┌─────────────────────────────────────┐
│  EDIT IN REPO                       │
│  RUN FROM ~/anki-tools              │
│  COMMIT AND PUSH FROM REPO          │
└─────────────────────────────────────┘
```

---

## 🔧 Troubleshooting

### "My changes disappeared!"

You probably edited the file in `~/anki-tools/` before the symlink was created, or the symlink got broken.

**Fix:**
```bash
~/anki-portuguese-sayings/deploy.sh
```

Then re-apply your changes in `~/anki-portuguese-sayings/`.

### "Script not found" or "Permission denied"

Make sure the deploy script is executable:
```bash
chmod +x ~/anki-portuguese-sayings/deploy.sh
```

### "How do I know which version is running?"

Check if it's a symlink:
```bash
ls -lh ~/anki-tools/generate_dashboard_html.py
```

Should show:
```
lrwxr-xr-x ... generate_dashboard_html.py -> /Users/koossimons/anki-portuguese-sayings/generate_dashboard_html.py
```

If it shows a regular file (`-rw-r--r--`), run `deploy.sh`.

---

## 📊 Quick Reference

| Action | Command |
|--------|---------|
| Deploy symlinks | `~/anki-portuguese-sayings/deploy.sh` |
| Edit code | `cd ~/anki-portuguese-sayings && vim generate_dashboard_html.py` |
| Test changes | `cd ~/anki-tools && source .venv/bin/activate && python generate_dashboard_html.py` |
| Commit changes | `cd ~/anki-portuguese-sayings && git add . && git commit -m "..."` |
| Push to production | `cd ~/anki-portuguese-sayings && git push` |
| Sync after pull | `cd ~/anki-portuguese-sayings && git pull && ./deploy.sh` |

---

## 🎯 Summary

✅ **Source of truth**: `~/anki-portuguese-sayings/` (git repo)
✅ **Runtime location**: `~/anki-tools/` (symlinks)
✅ **Deployment**: `deploy.sh` (automatic linking)
✅ **Workflow**: Edit → Test → Commit → Push

**Remember**: If you edit in the repo, you NEVER have to worry about sync issues! 🎉
