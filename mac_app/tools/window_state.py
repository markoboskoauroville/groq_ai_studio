#!/usr/bin/env python3
"""window_state.py: Queen's main window as the window server sees it: {"found", "onscreen", "x", "y", "w", "h"}.

Used by mac_app/install.sh (audit round 2, 22.11.2026) before the quit and after the restart, so the installer can say
whether her window came back where it was. Read only (Quartz CGWindowList), never moves anything.
Usage: window_state.py [owner]     (default owner "Queen"); needs pyobjc Quartz (~/.queen/venv has it).
"""
import json
import sys

try:
    import Quartz
except ImportError:
    print(json.dumps({"found": False, "error": "no Quartz module"}))
    sys.exit(0)

owner = sys.argv[1] if len(sys.argv) > 1 else "Queen"
wins = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionAll, Quartz.kCGNullWindowID) or []
best = None
for w in wins:
    if w.get("kCGWindowOwnerName") != owner or w.get("kCGWindowLayer", 0) != 0:
        continue
    b = w.get("kCGWindowBounds") or {}
    if b.get("Width", 0) < 300 or b.get("X", 0) < -20000:      # skip tiny helper windows and off-screen renders
        continue
    if best is None or b.get("Width", 0) * b.get("Height", 0) > best[1]:
        best = (w, b.get("Width", 0) * b.get("Height", 0))
if not best:
    print(json.dumps({"found": False}))
else:
    w, _ = best
    b = w["kCGWindowBounds"]
    print(json.dumps({"found": True, "onscreen": bool(w.get("kCGWindowIsOnscreen")), "x": int(b["X"]), "y": int(b["Y"]),
                      "w": int(b["Width"]), "h": int(b["Height"])}))
