"""Open any System Settings pane and VERIFY it (14.11.2026). Marko: Queen said "Done" for Control Center, but System Settings
showed "Accessibility" and another app was in front.

    GET  /api/system/settings?pane=<name>     (also POST {"pane": "..."})  -> {ok, pane, title, expected, front_app, attempts}
    GET  /api/system/settings/panes           -> the known names

`open x-apple.systempreferences:<id>`, then System Events reads the System Settings window title and the front app. Wrong title or
not in front: activate System Settings and `open` again, once. ok is true ONLY when the title read back equals the expected one.
Chat (local, $0): "open the Control Center settings page", "open Bluetooth settings", "open system settings sound".
"""
import re
import subprocess
import sys
import time

from flask import jsonify, request

# name -> (extension id, expected window title on macOS 15)
PANES = {
    "wi-fi": ("com.apple.wifi-settings-extension", "Wi-Fi"),
    "bluetooth": ("com.apple.BluetoothSettings", "Bluetooth"),
    "network": ("com.apple.Network-Settings.extension", "Network"),
    "notifications": ("com.apple.Notifications-Settings.extension", "Notifications"),
    "sound": ("com.apple.Sound-Settings.extension", "Sound"),
    "focus": ("com.apple.Focus-Settings.extension", "Focus"),
    "screen time": ("com.apple.Screen-Time-Settings.extension", "Screen Time"),
    "general": ("com.apple.systempreferences.GeneralSettings", "General"),
    "appearance": ("com.apple.Appearance-Settings.extension", "Appearance"),
    "accessibility": ("com.apple.Accessibility-Settings.extension", "Accessibility"),
    "control center": ("com.apple.ControlCenter-Settings.extension", "Control Center"),
    "siri": ("com.apple.Siri-Settings.extension", "Siri"),
    "privacy": ("com.apple.settings.PrivacySecurity.extension", "Privacy & Security"),
    "desktop dock": ("com.apple.Desktop-Settings.extension", "Desktop & Dock"),
    "displays": ("com.apple.Displays-Settings.extension", "Displays"),
    "wallpaper": ("com.apple.Wallpaper-Settings.extension", "Wallpaper"),
    "battery": ("com.apple.Battery-Settings.extension", "Battery"),
    "lock screen": ("com.apple.Lock-Screen-Settings.extension", "Lock Screen"),
    "touch id": ("com.apple.Touch-ID-Settings.extension", "Touch ID & Password"),
    "users": ("com.apple.Users-Groups-Settings.extension", "Users & Groups"),
    "passwords": ("com.apple.Passwords-Settings.extension", "Passwords"),
    "keyboard": ("com.apple.Keyboard-Settings.extension", "Keyboard"),
    "trackpad": ("com.apple.Trackpad-Settings.extension", "Trackpad"),
    "mouse": ("com.apple.Mouse-Settings.extension", "Mouse"),
    "printers": ("com.apple.Print-Scan-Settings.extension", "Printers & Scanners"),
    "login items": ("com.apple.LoginItems-Settings.extension", "Login Items & Extensions"),
    "sharing": ("com.apple.Sharing-Settings.extension", "Sharing"),
    "software update": ("com.apple.Software-Update-Settings.extension", "Software Update"),
    "storage": ("com.apple.settings.Storage", "Storage"),
}
ALIASES = {
    "wifi": "wi-fi", "wi fi": "wi-fi", "wireless": "wi-fi", "audio": "sound", "volume": "sound",
    "privacy & security": "privacy", "privacy and security": "privacy", "security": "privacy",
    "desktop & dock": "desktop dock", "dock": "desktop dock", "desktop": "desktop dock",
    "display": "displays", "monitor": "displays", "monitors": "displays", "screen": "displays",
    "controlcenter": "control center", "menu bar": "control center", "menubar": "control center",
    "keyboards": "keyboard", "update": "software update", "updates": "software update",
    "printer": "printers", "scanners": "printers", "password": "passwords", "lock": "lock screen",
    "login": "login items", "startup": "login items", "accounts": "users", "touchid": "touch id",
    "energy": "battery", "notification": "notifications", "dnd": "focus", "do not disturb": "focus",
}


def resolve(name):
    k = re.sub(r"\s+", " ", (name or "").lower().replace("_", " ").replace("-", " ")).strip()
    k = re.sub(r"\b(settings?|pane|page|preferences)\b", "", k).strip()
    k = re.sub(r"\s+", " ", k)
    for cand in (k, k.replace(" ", "-")):
        if cand in PANES:
            return cand
    if k in ALIASES:
        return ALIASES[k]
    for key in PANES:
        if key.replace("-", " ") == k:
            return key
    hits = [key for key in PANES if k and (k in key or key in k)]
    return hits[0] if len(hits) == 1 else None


def _norm(t):
    """The title follows the system language (British "Control Centre"): compare without case and with centre = center."""
    return (t or "").lower().replace("centre", "center").replace(" and ", " & ").strip()


def _osa(script, timeout=10):
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "osascript failed")
    return r.stdout.strip()


def _state():
    """(window title of System Settings, front app) read through System Events."""
    title = ""
    try:
        title = _osa('tell application "System Events" to tell process "System Settings" to '
                     'if (count of windows) > 0 then get name of window 1')
    except Exception as e:
        title = f"(unreadable: {e})"
    try:
        front = _osa('tell application "System Events" to get name of first application process whose frontmost is true')
    except Exception:
        front = "?"
    return title, front


def open_pane(name):
    key = resolve(name)
    if not key:
        return {"ok": False, "error": f"unknown pane '{name}'", "known": sorted(PANES)}
    ident, expected = PANES[key]
    attempts, title, front = 0, "", ""
    for attempt in range(2):
        attempts += 1
        if attempt:
            try:
                _osa('tell application "System Settings" to activate')
            except Exception:
                pass
        subprocess.run(["open", f"x-apple.systempreferences:{ident}"], capture_output=True, timeout=10)
        try:
            _osa('tell application "System Settings" to activate')
        except Exception:
            pass
        for _ in range(10):          # up to ~3 s for the window to settle on the right title
            time.sleep(0.3)
            title, front = _state()
            if _norm(title) == _norm(expected) and front == "System Settings":
                break
        if _norm(title) == _norm(expected) and front == "System Settings":
            break
    ok = _norm(title) == _norm(expected) and front == "System Settings"
    out = {"ok": ok, "pane": key, "id": ident, "expected": expected, "title": title, "front_app": front, "attempts": attempts}
    if not ok:
        out["error"] = f"System Settings shows '{title}' with '{front}' in front, not '{expected}'"
    return out


def register(app):
    @app.route("/api/system/settings", methods=["GET", "POST"])
    def system_settings():
        d = request.get_json(silent=True) or {}
        pane = request.args.get("pane") or d.get("pane") or ""
        if not pane:
            return jsonify(ok=False, error="pane is required", known=sorted(PANES)), 400
        r = open_pane(pane)
        return jsonify(r), (200 if r["ok"] else (400 if "known" in r else 502))

    @app.get("/api/system/settings/panes")
    def system_settings_panes():
        return jsonify(ok=True, panes={k: v[1] for k, v in PANES.items()}, aliases=ALIASES)


def chat_settings_command(text):
    """Local chat command; None when the sentence is not about opening a Settings pane."""
    if sys.platform != "darwin":
        return None
    t = (text or "").strip()
    low = t.lower()
    if len(t) > 160 or not re.search(r"\b(open|show|go to|take me to|otvori|pokazi)\b", low):
        return None
    if not re.search(r"\b(settings?|preferences|postavke)\b", low):
        return None
    m = re.search(r"(?:system\s+)?(?:settings?|preferences)\s+(?:for\s+|to\s+)?(.+)$", low)
    cand = None
    if m:
        cand = m.group(1)
    if not (cand and resolve(cand)):
        m = re.search(r"\b(?:open|show|go to|take me to|otvori|pokazi)\s+(?:the\s+|my\s+)?(.+?)\s+(?:system\s+)?(?:settings?|preferences)\b", low)
        cand = m.group(1) if m else None
    if not cand or not resolve(cand):
        return None
    r = open_pane(cand)
    if r["ok"]:
        return f"Opened: System Settings is in front, window title \"{r['title']}\"."
    return f"I could not open it: {r.get('error')}."
