#!/bin/bash
set -euo pipefail

echo "START $(date)"
echo "whoami=$(whoami)"
echo "pwd=$(pwd)"
/usr/bin/caffeinate -i -w $$ &

# ---- Logging ----
LOGDIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Portuguese/Anki/logs"
mkdir -p "$LOGDIR"
exec >>"$LOGDIR/pipeline.$(date +%F).log" 2>>"$LOGDIR/pipeline.$(date +%F).err"
echo "START $(date)"
echo "whoami=$(whoami)"
echo "pwd=$(pwd)"

# ---- Env ----
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export PYTHONIOENCODING=UTF-8

# ---- Network gate ----
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

# ---- Paths ----
ANKI_BASE="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Portuguese/Anki"
INBOX="$ANKI_BASE/inbox"
QUICK="$INBOX/quick.jsonl"
TODAY="$(date +%F)"
ROTATE_STAMP="$INBOX/.rotated-$TODAY"
mkdir -p "$INBOX"

# Single-run lock (avoid overlap)
LOCK="$INBOX/.pipeline.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "[lock] another run is active; exiting."
  exit 0
fi
trap 'rmdir "$LOCK"' EXIT

# cleanup old rotation stamps
for f in "$INBOX"/.rotated-*; do
  [ -e "$f" ] || continue
  [ "$(basename "$f")" = ".rotated-$TODAY" ] && continue
  rm -f "$f"
done

# ---- OpenAI key from Keychain + sanitize ----
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  if KEY_FROM_KC="$(security find-generic-password -a "$USER" -s "anki-tools-openai" -w 2>/dev/null)"; then
    OPENAI_API_KEY="$KEY_FROM_KC"
  else
    echo "[err] OPENAI_API_KEY not set and Keychain item 'anki-tools-openai' not found." >&2
    exit 1
  fi
fi
OPENAI_API_KEY="$(printf %s "$OPENAI_API_KEY" | LC_ALL=C tr -d '\r\n' | tr -d '“”‘’')"
export OPENAI_API_KEY
unset OPENAI_BASE_URL OPENAI_API_BASE OPENAI_ORG_ID
echo "key_prefix=${OPENAI_API_KEY:0:6}"

# ---- Bring up AnkiConnect ----
open -gj -a "Anki" || true
require_network || exit 0
for i in {1..20}; do
  if curl -sS --max-time 1 localhost:8765 >/dev/null ; then
    echo "[anki] AnkiConnect reachable."
    break
  fi
  sleep 1
done
if ! curl -sS --max-time 1 localhost:8765 >/dev/null ; then
  echo "[anki] AnkiConnect not reachable; skipping this run"
  exit 0
fi

# ---- Run the main transformer (capture exit code, don't 'exec') ----
# Copy iCloud inbox to a local scratch (avoid iCloud locks/TCC)
SCRATCH="$(mktemp -t quick_copy.XXXXXX.jsonl)"
/bin/cp -f "$QUICK" "$SCRATCH" || echo "[warn] Could not copy $QUICK (maybe empty)."

set +e
"$HOME/anki-tools/.venv/bin/python" -u "$HOME/anki-tools/transform_inbox_to_csv.py" \
  --deck "Portuguese Mastery (pt-PT)" --model "GPT Vocabulary Automater" \
  --inbox-file "$SCRATCH"
STATUS=$?
set -e

# ---- Optional: rotate iCloud inbox (default OFF; needs Full Disk Access) ----
if [[ "${ROTATE_INBOX:-0}" == "1" && $STATUS -eq 0 && ! -f "$ROTATE_STAMP" ]]; then
  echo "[rotate] status=$STATUS stamp=$ROTATE_STAMP quick=$QUICK"
  mv -f "$QUICK" "$QUICK.$(date +%H%M%S).bak" 2>/dev/null || true
  : > "$QUICK"
  touch "$ROTATE_STAMP"
  echo "[rotate] quick.jsonl cleared for $TODAY"
fi

exit "$STATUS"