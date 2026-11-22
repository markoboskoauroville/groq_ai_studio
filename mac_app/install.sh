#!/bin/sh
# install.sh: the Latest release from GitHub into /Applications, signed "Mantra Apps" (no compile on the Mac).
# Usage: ./install.sh [vN]
set -e
REPO=markoboskoauroville/groq_ai_studio
NAME="Queen"
D="${TMPDIR:-/tmp}/groq-ai-studio-mac"
rm -rf "$D"; mkdir -p "$D"
gh release download $1 --repo "$REPO" --pattern app.zip -D "$D" --clobber
# v28+: every quit asks "Are you sure you want to quit?". Ask her to quit, then WAIT until she has really gone; never
# delete a running app (audit 22.11.2026: the old 1-second sleep removed /Applications/Queen.app under a running Queen).
if pgrep -f "/Applications/$NAME.app/Contents/MacOS/" >/dev/null 2>&1; then
    osascript -e "tell application \"$NAME\" to quit" 2>/dev/null || true
    for _ in $(seq 1 60); do
        pgrep -f "/Applications/$NAME.app/Contents/MacOS/" >/dev/null 2>&1 || break
        sleep 1
    done
    if pgrep -f "/Applications/$NAME.app/Contents/MacOS/" >/dev/null 2>&1; then
        echo "$NAME is still running (press Quit in her 'Are you sure you want to quit?' dialog), nothing was replaced." >&2
        exit 1
    fi
fi
rm -rf "/Applications/$NAME.app" "/Applications/Groq AI Studio (Mantra).app" "/Applications/Groq Queen AI Studio (Mantra).app"
ditto -x -k "$D/app.zip" /Applications
xattr -dr com.apple.quarantine "/Applications/$NAME.app" 2>/dev/null || true
codesign --force -s "Mantra Apps" "/Applications/$NAME.app/Contents/MacOS/axread"
codesign --force -s "Mantra Apps" "/Applications/$NAME.app"
mkdir -p "$HOME/.local/bin" && ln -sf "/Applications/$NAME.app/Contents/MacOS/axread" "$HOME/.local/bin/axread"
codesign -dv "/Applications/$NAME.app" 2>&1 | grep -E "Authority|Identifier" || true
echo "installed /Applications/$NAME.app"
