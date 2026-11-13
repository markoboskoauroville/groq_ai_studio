#!/usr/bin/env bash
# two_locations_sync.sh: the pull-only sync between the two locations (Mac and the VM chromium-vm), every 5 minutes
# (Marko, 13.11.2026: "any lessons or skills are written in the same repository ... all this knowledge is coming to the common database").
# For groq_ai_studio, MANTRA_MACRO, MACRO_SKILLS, MANTRA_MANIFEST in ~/Developer: `git pull --ff-only`, nothing else.
# Never pushes, never stashes, never resets, never forces. A pull that cannot fast-forward (local commits or a dirty file in
# the way) is a CONFLICT: written to ~/.cache/two-locations/conflicts.log and left for a session to merge by hand.
# What a new pull changes locally:
#   groq_ai_studio queen_skills/*.md|json  -> copied newer-only to ~/.groq/queen_skills (Queen reads them every turn, no restart)
#   groq_ai_studio qwen_app/ (code)        -> VM: ./install.sh and `systemctl --user restart queen`; Mac: only reported
#                                             (the running Mac Queen is never restarted from here)
#   MANTRA_MACRO linux/                    -> VM: a newer linux-vN release is installed (sh linux/install.sh)
set -u
cd "$HOME" || exit 0
D="$HOME/Developer"; LOG="$HOME/.cache/two-locations"; mkdir -p "$LOG"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH" GIT_TERMINAL_PROMPT=0
OS="$(uname -s)"; NOW="$(date '+%d.%m.%Y %H:%M:%S')"
say() { printf '%s %s\n' "$NOW" "$*" >> "$LOG/sync.log"; }
for r in groq_ai_studio MANTRA_MACRO MACRO_SKILLS MANTRA_MANIFEST; do
  [ -d "$D/$r/.git" ] || continue
  before="$(git -C "$D/$r" rev-parse HEAD 2>/dev/null)"
  if ! out="$(git -C "$D/$r" pull --ff-only -q 2>&1)"; then
    printf '%s CONFLICT %s: %s\n' "$NOW" "$r" "$(printf '%s' "$out" | tr '\n' ' ' | cut -c1-300)" >> "$LOG/conflicts.log"
    say "$r: could not fast-forward (see conflicts.log)"; continue
  fi
  after="$(git -C "$D/$r" rev-parse HEAD)"
  [ "$before" = "$after" ] && continue
  say "$r: $(git -C "$D/$r" rev-list --count "$before..$after") new commit(s)"
  changed="$(git -C "$D/$r" diff --name-only "$before" "$after")"
  case "$r" in
    groq_ai_studio)
      if printf '%s\n' "$changed" | grep -q '^queen_skills/'; then
        mkdir -p "$HOME/.groq/queen_skills"
        for f in "$D"/groq_ai_studio/queen_skills/*.md "$D"/groq_ai_studio/queen_skills/*.json; do
          [ -f "$f" ] && { [ ! -e "$HOME/.groq/queen_skills/$(basename "$f")" ] || [ "$f" -nt "$HOME/.groq/queen_skills/$(basename "$f")" ]; } && cp -p "$f" "$HOME/.groq/queen_skills/"
        done; say "queen_skills copied (newer only) to ~/.groq/queen_skills"
      fi
      if printf '%s\n' "$changed" | grep -qE '^(qwen_app/|groq_pool.py|requirements.txt)'; then
        if [ "$OS" = Linux ]; then
          if (cd "$D/groq_ai_studio" && ./install.sh >> "$LOG/install.log" 2>&1) && systemctl --user restart queen.service; then say "Queen code reinstalled, queen restarted"
          else say "Queen reinstall FAILED (see install.log); the old copy keeps running"; fi
        else say "Queen code changed in the repo; the running Mac Queen was NOT touched: ./install.sh and a restart are Marko's or a session's call"; fi
      fi ;;
    MANTRA_MACRO)
      if [ "$OS" = Linux ] && printf '%s\n' "$changed" | grep -q '^linux/'; then
        new="$(gh release list -R markoboskoauroville/MANTRA_MACRO --limit 50 --json tagName --jq '[.[].tagName|select(startswith("linux-v"))]|map(ltrimstr("linux-v")|tonumber)|max' 2>/dev/null)"
        have="$(macro version 2>/dev/null | sed -n 's/.*v\([0-9][0-9]*\)$/\1/p')"
        if [ -n "$new" ] && [ "$new" != "${have:-0}" ]; then (cd "$D/MANTRA_MACRO" && sh linux/install.sh >> "$LOG/install.log" 2>&1) && say "Macro Recorder Linux v$new installed"; fi
      fi ;;
  esac
done
