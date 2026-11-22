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
# Round 2 (22.11.2026): her window's place before the quit (read only), to check it after the restart.
PY="$HOME/.queen/venv/bin/python"; WS="$(cd "$(dirname "$0")" && pwd)/tools/window_state.py"
BEFORE='{"found": false}'; WAS_RUNNING=0
if pgrep -f "/Applications/$NAME.app/Contents/MacOS/$NAME" >/dev/null 2>&1; then
    WAS_RUNNING=1
    [ -x "$PY" ] && BEFORE="$("$PY" "$WS" "$NAME" 2>/dev/null || echo '{"found": false}')"
fi
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
# Back where she was: started in the background (never activated); the frame comes back by her frame autosave
# ("QueenMain"). macOS has no public way to choose a window's Space, so if her window was on the visible Space before
# and is not now, say so: Marko finds it once (Mission Control), and it stays there.
if [ "$WAS_RUNNING" = 1 ]; then
    open -g "/Applications/$NAME.app"
    AFTER='{"found": false}'
    for _ in $(seq 1 20); do
        sleep 1
        [ -x "$PY" ] && AFTER="$("$PY" "$WS" "$NAME" 2>/dev/null || echo '{"found": false}')"
        echo "$AFTER" | grep -q '"found": true' && break
    done
    "$PY" - "$BEFORE" "$AFTER" <<'PYEOF' || true
import json, sys
b, a = json.loads(sys.argv[1]), json.loads(sys.argv[2])
if not b.get("found"):
    print("window: no window before the quit, nothing to compare")
elif not a.get("found"):
    print("window: NOT found after the restart (she may still be starting)")
else:
    same = all(b.get(k) == a.get(k) for k in ("x", "y", "w", "h"))
    print(f"window frame before {b['x']},{b['y']} {b['w']}x{b['h']}, after {a['x']},{a['y']} {a['w']}x{a['h']}: "
          + ("same" if same else "DIFFERENT"))
    if b.get("onscreen") and not a.get("onscreen"):
        print("window: it was on the visible Space before and is on another Space now; macOS gives no public way to put "
              "it back: find it once in Mission Control")
    else:
        print("window: Space as before (" + ("visible" if a.get("onscreen") else "not on the visible Space, as before") + ")")
PYEOF
fi
