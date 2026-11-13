"""Queen reads the Mac's screen (13.11.2026).

Marko: "don't ask me if I see something. You have screen-capturing possibilities ... teach the queen to learn to read
screens and ask her if there's a subtitle on the screen. She must tell you. If she lies, then you fix her skill."

    POST /api/screen/look {question, display?: 1|2|"all", region?: [x,y,w,h] points, window?: "<owner app name>", max_edge?}
Silent capture (screencapture -x, nothing comes to the front, no mouse or key), downscaled, then her eyes (/api/vision/ask).
Returns {ok, answer, path, captured_at, target, size, blank}. A blank or black capture is a capture failure: no answer is
asked of her (she would invent one). Display 1 = BenQ (2560x1440 points), display 2 = MacBook.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

from flask import jsonify, request

WORK = Path.home() / ".groq" / "work"

GUARD = (
    "You are looking at a real screenshot of a Mac screen. Answer ONLY from what is visible in this picture. "
    "Quote any text you read exactly, character for character, as it appears. If what is asked about is not visible, "
    "answer exactly 'not visible'. Never guess from context, never invent text, never describe what 'would' be there.\n\n"
)


SUBTITLE_DEF = (
    "DEFINITION: a subtitle (Voice Engine) is ORANGE text, centred, large, drawn over the picture in a band, with the word "
    "being spoken in RED. Text in a window (white, grey or small text in a terminal, chat or app, left-aligned or in a "
    "column) is NOT a subtitle, even if it is readable, and a window's text must never be reported as one. If there is no "
    "orange centred text, answer exactly: no subtitle on screen. QUESTION: ")


LINUX = sys.platform.startswith("linux")   # the VM (13.11.2026, two locations): X11 on display :1, ImageMagick instead of screencapture/sips


def _windows():
    if LINUX:
        out = subprocess.run(["wmctrl", "-lG"], capture_output=True, text=True, timeout=15,
                             env={**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":1")}).stdout
        res = []
        for ln in out.splitlines():
            p = ln.split(None, 8)
            if len(p) >= 9:
                res.append({"id": int(p[0], 16), "owner": p[8], "name": p[8], "layer": 0, "area": int(p[6]) * int(p[7])})
        return res
    code = ("import Quartz,json;print(json.dumps([{'id':w['kCGWindowNumber'],'owner':w.get('kCGWindowOwnerName',''),"
            "'name':w.get('kCGWindowName','') or '','layer':w['kCGWindowLayer'],'area':w['kCGWindowBounds']['Width']*w['kCGWindowBounds']['Height']}"
            "for w in Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly,0)]))")
    import json
    r = subprocess.run(["/usr/bin/python3", "-c", code], capture_output=True, text=True, timeout=15)
    return json.loads(r.stdout or "[]")


def _capture_linux(data, raw):
    env = {**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":1")}
    cmd = ["import", "-silent"]
    target = "display :1"
    if data.get("window"):
        want = str(data["window"]).lower()
        cands = [w for w in _windows() if want in w["owner"].lower() and w["area"] > 10000]
        if not cands:
            raise ValueError(f"no on-screen window matching '{data['window']}'")
        w = max(cands, key=lambda c: c["area"])
        cmd += ["-window", hex(w["id"])]
        target = f"window {w['owner']}"
    else:
        cmd += ["-window", "root"]
        if data.get("region"):
            x, y, w, h = [int(v) for v in data["region"]]
            cmd += ["-crop", f"{w}x{h}+{x}+{y}", "+repage"]
            target = f"region {x},{y},{w},{h}"
    cmd.append(str(raw))
    subprocess.run(cmd, check=True, timeout=30, env=env)
    return raw, target


def capture(data):
    WORK.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    raw = WORK / f"screen_{stamp}_raw.png"
    if LINUX:
        return _capture_linux(data, raw)
    cmd = ["/usr/sbin/screencapture", "-x"]
    target = "display 1"
    if data.get("window"):
        want = str(data["window"]).lower()
        cands = [w for w in _windows() if want in w["owner"].lower() and w["layer"] == 0 and w["area"] > 10000]
        if not cands:
            raise ValueError(f"no on-screen window of app '{data['window']}'")
        w = max(cands, key=lambda c: c["area"])
        cmd += ["-l", str(w["id"])]
        target = f"window {w['owner']} / {w['name']}"
    elif data.get("region"):
        x, y, w, h = [int(v) for v in data["region"]]
        cmd += ["-R", f"{x},{y},{w},{h}"]
        target = f"region {x},{y},{w},{h}"
    else:
        d = data.get("display", 1)
        if d == "all":
            target = "all displays"
        else:
            cmd += ["-D", str(int(d))]
            target = f"display {int(d)}"
    cmd.append(str(raw))
    subprocess.run(cmd, check=True, timeout=20)
    return raw, target


def look(data, pool, record_spend):
    import vision  # noqa: PLC0415
    raw, target = capture(data)
    when = time.strftime("%H:%M:%S")
    out_path = raw.with_name(raw.name.replace("_raw", ""))
    edge = int(data.get("max_edge") or 1800)
    if LINUX:
        subprocess.run(["convert", str(raw), "-resize", f"{edge}x{edge}>", str(out_path)], capture_output=True, timeout=30)
    else:
        subprocess.run(["/usr/bin/sips", "-Z", str(edge), str(raw), "--out", str(out_path)], capture_output=True, timeout=20)
    raw.unlink(missing_ok=True)
    size = out_path.stat().st_size if out_path.exists() else 0
    res = {"path": str(out_path), "captured_at": when, "target": target, "size": size}
    if size < 12000:                         # a black or empty PNG compresses to almost nothing
        return {**res, "ok": False, "blank": True,
                "error": "capture is blank or black: a capture failure (screen locked, display asleep, or no Screen Recording permission), not an answer"}
    q = GUARD + (data.get("question") or "Describe what is on the screen.")
    a = vision.ask({"question": q, "path": str(out_path), "max_tokens": data.get("max_tokens") or 800}, pool, record_spend)
    return {**res, "ok": True, "blank": False, **a}


def register(app, pool, record_spend):
    @app.post("/api/screen/look")
    def screen_look():
        data = request.get_json(silent=True) or {}
        try:
            r = look(data, pool, record_spend)
            return jsonify(r), (200 if r.get("ok") else 422)
        except Exception as exc:
            return jsonify(ok=False, error=f"{type(exc).__name__}: {exc}"), 400
    return app


def chat_screen_command(text, pool, record_spend):
    """Chat: "look at the screen: is there a subtitle?", "is there a subtitle on the screen", "read the screen",
    "what does the Terminal window say" (window <app>), "on the MacBook screen ..." (display 2). Answered locally."""
    import re
    t = (text or "").strip()
    low = t.lower()
    if not re.search(r"\b(screen|subtitle|subtitles|on display|window says?)\b", low) or len(t) > 400:
        return None
    if not re.match(r"^(look|read|check|see|is there|are there|what|does|do you see|can you see|tell me|please)", low):
        return None
    data = {"question": t, "display": 1}
    if re.search(r"macbook|display 2|second (screen|display)", low):
        data["display"] = 2
    elif re.search(r"all (screens|displays)|both (screens|displays)", low):
        data["display"] = "all"
    m = re.search(r"\b(?:window of|in the|in) ([A-Z][\w .+-]{2,30}?) window\b", t)
    if m:
        data["window"] = m.group(1).strip()
    if re.search(r"subtitle", low) and data["display"] == 1 and "window" not in data:
        data["region"] = [0, 700, 2560, 160]
        data["question"] = SUBTITLE_DEF + t
    r = look(data, pool, record_spend)
    if not r.get("ok"):
        return f"I could not look: {r.get('error')} (capture {r.get('path')}, {r.get('captured_at')})"
    return f"{r['answer']}\n\n(seen at {r['captured_at']}, {r['target']}, screenshot {r['path']})"
