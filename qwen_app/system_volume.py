"""Mac output volume (14.11.2026). Marko: "please reduce the output volume on my computer to 10%".

    GET  /api/system/volume                       -> {ok, volume, muted, device}
    POST /api/system/volume {percent?, change?, mute?}   percent 0-100, change +-N, mute true/false
Set with osascript, then read back; the answer is the read-back, not what was asked. The output DEVICE is never changed
(the ADAM D3V stays default); the device name is only reported (SwitchAudioSource -c, else system_profiler).
Chat (answered locally, no model): "set/reduce/raise/lower the volume to 10%", "volume 30", "turn it up by 10", "mute", "unmute",
"how loud is it", Croatian "stisaj / glasnoca na 20%".
"""
import re
import subprocess
import sys

from flask import jsonify, request


def _osa(script):
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "osascript failed")
    return r.stdout.strip()


def device_name():
    try:
        r = subprocess.run(["SwitchAudioSource", "-c", "-t", "output"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    try:
        out = subprocess.run(["system_profiler", "SPAudioDataType"], capture_output=True, text=True, timeout=10).stdout
        name = None
        for line in out.splitlines():
            if line.startswith("        ") and not line.startswith("         ") and line.rstrip().endswith(":"):
                name = line.strip().rstrip(":")
            if "Default Output Device: Yes" in line:
                return name
    except Exception:
        pass
    return None


def read():
    vol = int(_osa("output volume of (get volume settings)"))
    muted = _osa("output muted of (get volume settings)") == "true"
    return {"volume": vol, "muted": muted, "device": device_name()}


def apply(percent=None, change=None, mute=None):
    if percent is None and change is None and mute is None:
        return read()
    if percent is not None or change is not None:
        cur = int(_osa("output volume of (get volume settings)"))
        target = int(percent) if percent is not None else cur + int(change)
        target = max(0, min(100, target))
        _osa(f"set volume output volume {target}")
    if mute is not None:
        _osa(f"set volume output muted {'true' if mute else 'false'}")
    return read()


def register(app):
    @app.get("/api/system/volume")
    def system_volume_get():
        try:
            return jsonify(ok=True, **read())
        except Exception as e:
            return jsonify(ok=False, error=str(e)), 500

    @app.post("/api/system/volume")
    def system_volume_set():
        d = request.get_json(silent=True) or {}
        try:
            for k in ("percent", "change"):
                if d.get(k) is not None:
                    d[k] = int(d[k])
            if "mute" in d and d["mute"] is not None and not isinstance(d["mute"], bool):
                return jsonify(ok=False, error="mute must be true or false"), 400
            return jsonify(ok=True, **apply(d.get("percent"), d.get("change"), d.get("mute")))
        except (ValueError, TypeError):
            return jsonify(ok=False, error="percent and change must be whole numbers"), 400
        except Exception as e:
            return jsonify(ok=False, error=str(e)), 500


def _say(r):
    s = f"The Mac output volume is {r['volume']}%" + (", muted" if r["muted"] else "")
    if r.get("device"):
        s += f" (output: {r['device']})"
    return s + "."


def chat_volume_command(text):
    """Local chat command; returns None when the sentence is not about the volume."""
    if sys.platform != "darwin":
        return None
    t = (text or "").strip()
    low = t.lower().replace("š", "s").replace("č", "c").replace("ć", "c").replace("đ", "d").replace("ž", "z")
    if len(t) > 160 or not re.search(r"\b(volume|loud|glasnoca|stisaj|pojacaj|mute|unmute|utisaj)\b", low):
        return None
    num = re.search(r"(\d{1,3})\s*(%|percent|posto|posto)?", low)
    n = int(num.group(1)) if num else None
    try:
        if re.search(r"\bunmute\b|\bukljuci zvuk\b", low):
            return _say(apply(mute=False))
        if re.search(r"\bmute\b|\bisklju?ci zvuk\b", low):
            return _say(apply(mute=True))
        if re.search(r"how loud|what.*volume|current volume|volume (level|now)\??$|koliko je glasno|koja je glasnoca", low) and n is None:
            return _say(read())
        down = re.search(r"reduce|lower|decrease|turn (it )?down|quieter|softer|stisaj|smanji|utisaj", low)
        up = re.search(r"raise|increase|turn (it )?up|louder|pojacaj|povecaj", low)
        by = re.search(r"\bby\b|\bza\b", low)
        if n is not None and (down or up) and by:
            return _say(apply(change=-n if down else n))
        if n is not None:
            return _say(apply(percent=min(n, 100)))
        if down or up:
            return _say(apply(change=-10 if down else 10))
        if re.search(r"\bvolume\b|glasnoca", low):
            return _say(read())
    except Exception as e:
        return f"I could not set the volume: {e}"
    return None
