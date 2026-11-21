"""Webcam Recorder (Mantra) through its own local API on 127.0.0.1:8867 (21.11.2026): local skill, $0, no model (queen_python_skills, dispatched by queen_python_skills.dispatch).
Skill: queen_skills/webcam-recorder.md. The app must be running (the star starts it); nothing here starts it.
Phrases: "webcam recorder status", "webcam recorder sony status", "connect the sony in the webcam recorder",
"disconnect the sony in the webcam recorder", "start webcam recording", "stop webcam recording"."""
import json, re, sys, urllib.request

API = "http://127.0.0.1:8867"


def _call(method, path, body=None, timeout=40):
    data = json.dumps(body or {}).encode() if method == "POST" else None
    req = urllib.request.Request(API + path, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read() or b"{}")
        except Exception:
            return {"error": f"HTTP {e.code}"}


def _sony_text(s):
    if s.get("connected"):
        bits = [f"Sony {s.get('model') or ''} connected over {s.get('transport')}", f"camera {s.get('rec')}"]
        for k, n in (("battery", "battery"), ("iso", "ISO"), ("shutter", "shutter"), ("fnumber", "aperture"), ("pictureProfile", "picture profile")):
            if s.get(k):
                bits.append(f"{n} {s[k]}")
        return ", ".join(bits) + "."
    d = s.get("diagnosis") or {}
    lines = [s.get("message") or "The Sony is not connected."]
    lines += d.get("stages") or []
    return "\n".join(lines)


def chat_webcam_command(text):
    """None when the sentence is not about the Webcam Recorder."""
    if sys.platform != "darwin":
        return None
    t = (text or "").strip()
    low = t.lower()
    if len(t) > 160 or not re.search(r"\bweb ?cam(era)?( recorder)?\b|\bwebcam\b", low):
        return None
    try:
        sony = re.search(r"\b(sony|camera control|alpha|a7)\b", low)
        if sony and re.search(r"\b(disconnect|release)\b", low):
            return _sony_text(_call("POST", "/sony/disconnect"))
        if sony and re.search(r"\b(connect|pair|control)\b", low):
            s = _call("POST", "/sony/connect", {"wait": 25})
            return _sony_text(s)
        if sony and re.search(r"\b(status|state|check|why|connected)\b", low):
            return _sony_text(_call("GET", "/sony/status?check=1"))
        if re.search(r"\b(start|begin)\b.*\b(record|recording)\b|\brecord\b", low) and not re.search(r"\bstop\b", low) and not sony:
            s = _call("GET", "/status")
            if s.get("recording"):
                return f"The webcam recorder is already recording: {s.get('currentTake')}."
            r = _call("POST", "/record/start", {})
            if r.get("error"):
                return f"The webcam recorder could not start: {r['error']}."
            return f"Recording started: {r.get('path')}. Sound input: {r.get('sound') or 'none'}."
        if re.search(r"\b(stop|end|finish)\b.*\b(record|recording)\b", low) and not sony:
            r = _call("POST", "/record/stop", {})
            if r.get("error"):
                return f"The webcam recorder could not stop: {r['error']}."
            return f"Recording stopped and saved: {r.get('path')} ({round(float(r.get('duration') or 0))} s)."
        if re.search(r"\b(status|state|recording\?|is it recording)\b", low):
            s = _call("GET", "/status")
            if s.get("error"):
                return f"The webcam recorder answered: {s['error']}."
            rec = f"recording {round(s.get('elapsed') or 0)} s" if s.get("recording") else "not recording"
            warn = f" WARNING: {s['soundWarning']}." if s.get("soundWarning") else ""
            return (f"Webcam Recorder: {rec}, camera {s.get('camera')} {s.get('size')} at {s.get('fps')} FPS, "
                    f"quality {s.get('quality')}, sound {s.get('sound') or 'none'}.{warn} " + _sony_text(s.get("sony") or {}))
    except OSError:
        return "I cannot reach the Webcam Recorder (Mantra) on port 8867: it is not running. The star's tick starts it."
    except Exception as e:
        return f"The webcam recorder hand failed: {e}"
    return None
