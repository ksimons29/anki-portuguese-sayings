#!/bin/bash
set -euo pipefail
# -e  : exit immediately if a command exits with a non-zero status
# -u  : treat unset variables as an error and exit
# -o pipefail : ensures the whole pipeline fails if any command fails

# ---- Basic diagnostic output (helps debugging LaunchAgent runs) ----
echo "START $(date)"         # exact start time
echo "whoami=$(whoami)"      # user running the script
echo "pwd=$(pwd)"            # working directory

/usr/bin/caffeinate -i -w $$ &
# Use -di instead of -i if you want the screen to stay on during the run.

# ---- Log everything to iCloud logs (one file per day) ----
LOGDIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Portuguese/Anki/logs"
mkdir -p "$LOGDIR"
exec >>"$LOGDIR/pipeline.$(date +%F).log" 2>>"$LOGDIR/pipeline.$(date +%F).err"

echo "START $(date)"
echo "whoami=$(whoami)"
echo "pwd=$(pwd)"

# ---- Ensure PATH is sane under launchd (optional but recommended) ----
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export PYTHONIOENCODING=UTF-8

# ---- Network gate with short backoff (skip run if offline) ----
require_network() {
  local tries=6
  while ! /sbin/ping -q -c1 -t1 1.1.1.1 >/dev/null 2>&1 ; do
    tries=$((tries-1))
    [ $tries -le 0 ] && { echo "[net] offline; skipping this run"; return 1; }
    echo "[net] no connectivity; retrying..."
    sleep 10
  done
  return 0
}

# ---- Atomic iCloud-safe overwrite (handles transient file locks) ----
# usage: some_content | atomic_overwrite "/path/to/file"
atomic_overwrite() {
  local target="$1"
  local tmp="${target}.tmp.$$"
  cat > "$tmp" || return 1

  local i=0
  local max=30  # up to 30 retries (≈30 seconds total)
  while ! mv -f "$tmp" "$target" 2>/dev/null; do
    i=$((i+1))
    if [ $i -ge $max ]; then
      echo "[atomic] failed after $max retries: $target"
      rm -f "$tmp"
      return 1
    fi
    echo "[atomic] target locked (retry $i/$max)"
    sleep 1
  done
  return 0
}

# ---- Detect if this run likely happened right after wake from sleep ----
if pmset -g log | tail -n 80 | grep -q "Wake from Sleep"; then
  echo "[info] Detected recent system wake; this run may be a catch-up after sleep."
fi

# ---- Paths for the inbox + daily rotation marker ----
ANKI_BASE="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Portuguese/Anki"
INBOX="$ANKI_BASE/inbox"
QUICK="$INBOX/quick.jsonl"
TODAY="$(date +%F)"
ROTATE_STAMP="$INBOX/.rotated-$TODAY"
mkdir -p "$INBOX"

# remove old stamps (keep only today's)
for f in "$INBOX"/.rotated-*; do
  [ -e "$f" ] || continue
  [ "$(basename "$f")" = ".rotated-$TODAY" ] && continue
  rm -f "$f"
done

# ---- Retrieve OpenAI API key (prefer env, else Keychain) ----
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  if KEY_FROM_KC="$(security find-generic-password -a "$USER" -s "anki-tools-openai" -w 2>/dev/null)"; then
    export OPENAI_API_KEY="$KEY_FROM_KC"
  else
    echo "[err] OPENAI_API_KEY not set and Keychain item 'anki-tools-openai' not found."
    echo "      Add it with: security add-generic-password -a \"$USER\" -s \"anki-tools-openai\" -w 'sk-...'"
    exit 1
  fi
fi

# Optional: only if you’ve stored a separate project id (not needed for sk-proj- keys)
if [[ -z "${OPENAI_PROJECT:-}" ]]; then
  OPENAI_PROJECT="$(security find-generic-password -a "$USER" -s "anki-tools-openai-project" -w 2>/dev/null || true)"
  [[ -n "$OPENAI_PROJECT" ]] && export OPENAI_PROJECT
fi

# Avoid legacy var conflicts
unset OPENAI_BASE_URL OPENAI_API_BASE OPENAI_ORG_ID
# Minimal diagnostics (safe prefix only)
echo "key_prefix=${OPENAI_API_KEY:0:6} project=${OPENAI_PROJECT:-<none>}"

# ---- Ensure Anki is open (quietly launches the app if not running) ----
open -gj -a "Anki" || true
sleep 3   # give Anki + AnkiConnect time to start

# ---- Network + AnkiConnect guards (prevents noisy failures) ----
require_network || exit 0
if ! curl -sS --max-time 2 localhost:8765 >/dev/null ; then
  echo "[anki] AnkiConnect not reachable; skipping this run"
  exit 0
fi

# ---- Run the main transformer (capture exit code, don't 'exec') ----
set +e
"$HOME/anki-tools/.venv/bin/python" -u "$HOME/anki-tools/transform_inbox_to_csv.py" \
  --deck "Portuguese Mastery (pt-PT)" --model "GPT Vocabulary Automater"
STATUS=$?
set -e

# ---- Daily clear on first successful run (atomic, iCloud-safe) ----
if [[ $STATUS -eq 0 && ! -f "$ROTATE_STAMP" ]]; then
  echo "[rotate] status=$STATUS stamp=$ROTATE_STAMP quick=$QUICK"
  mv -f "$QUICK" "$QUICK.$(date +%H%M%S).bak" 2>/dev/null || true
  : > "$QUICK"
  touch "$ROTATE_STAMP"
  echo "[rotate] quick.jsonl cleared for $TODAY"
fi