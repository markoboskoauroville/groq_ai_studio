"""The WhatsApp machine: the VM's Firefox, specialised in WhatsApp only (VM only, 14.11.2026).

Marko, 14.11.2026: "teach the queen to open Firefox, put it in the remote control mode, and open WhatsApp ... from now on
the Firefox itself will be the WhatsApp machine. It is going to be specialized in WhatsApp only, and when it runs, its
homepage needs to come to WhatsApp and my messages. Queen is going to do what I ask her to do with my WhatsApp."

Chat commands, answered locally (no model, no cost), only where QUEEN_LOCATION=vm:
    open whatsapp | open firefox | open the whatsapp machine | start whatsapp | otvori whatsapp
        -> `vm-whatsapp start`: Firefox with remote control (BiDi 127.0.0.1:9223), WhatsApp Web, in front and full;
           the answer says linked (chats there) or QR (Marko scans it with his phone: WhatsApp -> Linked devices)
    log in with my phone number [+385 ...]             -> `vm-whatsapp phone-login`: number + country, Next, the 8-character code
    whatsapp status | is whatsapp linked                -> `vm-whatsapp status`
    whatsapp qr                                          -> a picture of the QR code in ~/Pictures/<date> WhatsApp/
    whatsapp: <anything>  /  whatsapp <anything>         -> the same planner and hands as the Mac's WhatsApp remote
           (whatsapp_remote: rules first, then the local Claude Code; wa_remote.py over BiDi), drafts stay UNSENT
"""
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

VMWA = shutil.which("vm-whatsapp") or "/usr/local/lib/chromium-vm/vm-whatsapp"
OPEN = re.compile(r"^\s*(?:please\s+)?(?:open|start|launch|run|otvori|pokreni)\s+(?:the\s+|my\s+)?(?:firefox|whatsapp|whats app)"
                  r"(?:\s+(?:machine|web|in firefox|browser))?\s*[.!]?\s*$", re.I)
STATUS = re.compile(r"^\s*(?:whatsapp\s+status|is\s+(?:my\s+)?whatsapp\s+(?:linked|connected|on|running)\??)\s*$", re.I)
QR = re.compile(r"^\s*(?:show\s+(?:me\s+)?)?(?:the\s+)?whatsapp\s+qr(?:\s+code)?\s*$", re.I)
PHONE = re.compile(r"^\s*(?:please\s+)?(?:whatsapp\s+)?(?:log\s*in|login|link|sign\s*in)(?:\s+(?:to\s+)?whatsapp)?\s+(?:with|by|using)\s+(?:my\s+)?(?:phone(?:\s+number)?|number)"
                   r"(?:\s+(\+[\d\s]{8,}))?\s*[.!]?\s*$", re.I)
ASK = re.compile(r"^\s*(?:whatsapp|wa)\s*[:,\-]?\s+(.+)$", re.I | re.S)


def _run(*args, timeout=120):
    env = dict(os.environ, DISPLAY=os.environ.get("DISPLAY", ":1"))
    r = subprocess.run([VMWA, *args], capture_output=True, text=True, timeout=timeout, env=env)
    line = next((l for l in reversed(r.stdout.strip().splitlines()) if l.strip()), "")
    if r.returncode:
        raise RuntimeError((r.stderr.strip().splitlines() or [f"vm-whatsapp {args[0]} failed"])[-1][:300])
    return line


def _state_words(s):
    st = s.get("state")
    if st == "linked":
        return "WhatsApp is open in Firefox on the VM and linked: your chats are there. Tell me what to do (\"whatsapp: show my latest messages\")."
    if st == "qr":
        return ("WhatsApp is open in Firefox on the VM and shows the QR code (not linked yet). On your phone: WhatsApp, "
                "Settings, Linked devices, Link a device, and scan the code on the VM screen. Then say \"whatsapp status\".")
    if st == "loading":
        return "Firefox is up with remote control, WhatsApp is still loading. Ask \"whatsapp status\" in a moment."
    return f"The WhatsApp machine is not ready: {json.dumps(s)}"


def _pictures():
    d = Path.home() / "Pictures" / f"{time.strftime('%Y-%m-%d')} WhatsApp"
    d.mkdir(parents=True, exist_ok=True)
    return d


def chat_whatsapp_machine_command(text):
    if os.environ.get("QUEEN_LOCATION") != "vm" or not text:
        return None
    t = text.strip()
    if OPEN.match(t):
        s = json.loads(_run("start"))
        ok = s.get("bidi") and s.get("window")
        return ("Checked: Firefox running, remote control on 9223, window in front. " if ok else "Check FAILED: ") + _state_words(s)
    m = PHONE.match(t)
    if m:   # 14.11.2026 (Marko: "enter my phone number and my country and press Next"): number from the VM file unless given
        if not json.loads(_run("status", timeout=40)).get("bidi"):   # Firefox closed or without remote control: start it first
            _run("start")
        r = json.loads(_run("phone-login", *([m.group(1).strip()] if m.group(1) else []), timeout=90))
        if r.get("code"):
            return (f"Checked: number typed, country {r.get('country')}, Next pressed. WhatsApp's link code is {r['code']}. "
                    "On your phone: WhatsApp, Settings, Linked devices, Link a device, then 'Link with phone number instead', "
                    f"and type {r['code']}. Then say \"whatsapp status\".")
        return f"Next pressed (country {r.get('country')}), but I could not read a link code. The page says: {r.get('page', '')[:300]}"
    if STATUS.match(t):
        return _state_words(json.loads(_run("status", timeout=40)))
    if QR.match(t):
        s = json.loads(_run("status", timeout=40))
        if s.get("state") == "linked":
            return "WhatsApp is already linked, there is no QR code to scan."
        p = _pictures() / f"whatsapp-qr-{time.strftime('%H%M%S')}.png"
        _run("qr", str(p), timeout=40)
        return f"The WhatsApp page with the QR code is saved as {p} ({p.stat().st_size // 1024} KB) and is on the VM screen now."
    m = ASK.match(t)
    if m:
        import whatsapp_remote as wr
        s = json.loads(_run("status", timeout=40))
        if s.get("state") != "linked":
            s = json.loads(_run("start"))
            if s.get("state") != "linked":
                return _state_words(s)
        words = m.group(1).strip()
        plan = wr.plan_by_rules(words) or wr.plan_by_claude(words)
        res = wr.execute(plan)
        out = res.get("say") or ("done" if res.get("ok") else "failed")
        if res.get("choices"):
            out += "\nChoices: " + "; ".join(res["choices"])
        if res.get("draft"):
            out += f"\nDraft typed, NOT sent: {res['draft']}"
        if res.get("image_b64"):
            import base64
            p = _pictures() / f"whatsapp-{time.strftime('%H%M%S')}.jpg"
            p.write_bytes(base64.b64decode(res["image_b64"]))
            out += f"\nScreenshot: {p}"
        return ("" if res.get("ok") else "FAILED: ") + out + f"\n(action: {plan.get('action')})"
    return None
