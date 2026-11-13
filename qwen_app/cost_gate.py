"""Queen's client of the Cost Agent (13.11.2026). Every paid call of hers asks first.

Marko, 13.11.2026: "We almost spent all my savings on Groq recognizing images in virtual machine. That should not be
happening anymore. ... anything which costs money, it needs to ask me and give me how much money it costs."

    cost_gate.require(who, what, estimate_usd, items=None, job=None, provider="groq")   raises CostDenied on NO
    cost_gate.report(usd, ref, what)                                                    after the call, tells the ledger

The gate is on the Mac (127.0.0.1, port from ~/.config/mantra-ports.json "costagent", fallback 9047). On the VM the
file ~/.config/cost-agent/url holds the Mac's Tailscale address and ~/.config/cost-agent/token the token, so the VM
asks the Mac's box. If the gate cannot be reached the answer is NO (nothing is spent without a YES); on the Mac the
gate is started on demand. Rule: MANTRA_MANIFEST modules/cost-agent.md.
"""
import json
import os
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

HOME = Path.home()
GATE_SCRIPT = HOME / "Developer" / "COST_AGENT" / "gate" / "costagent.py"
_ctx = threading.local()
VISION_IMAGE_USD = 0.009       # measured from Queen's ledger on 13.11.2026 (Qwen 3.6 27B, one picture and its answer)
CHAT_CALL_USD = 0.002


class CostDenied(Exception):
    pass


def _remote():
    f = HOME / ".config" / "cost-agent"
    try:
        return (f / "url").read_text().strip(), (f / "token").read_text().strip()
    except Exception:
        return None, None


def _base():
    url, tok = _remote()
    if url:
        return url, {"X-Cost-Token": tok}
    port = 9047
    try:
        port = int(json.load(open(HOME / ".config" / "mantra-ports.json")).get("costagent", {}).get("port", 9047))
    except Exception:
        pass
    return f"http://127.0.0.1:{port}", {}


def _post(path, data, timeout):
    base, hdr = _base()
    req = urllib.request.Request(base + path, data=json.dumps(data).encode(),
                                 headers={"Content-Type": "application/json", **hdr})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def _start_local():
    if _remote()[0] or not GATE_SCRIPT.exists():
        return
    subprocess.Popen(["python3", str(GATE_SCRIPT), "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    time.sleep(1.5)


def require(who, what, estimate_usd, items=None, job=None, provider="groq", unit=None, timeout=130):
    d = {"who": who, "what": what, "provider": provider, "estimate_usd": estimate_usd, "items": items, "job": job,
         "unit": unit, "timeout": 120}
    try:
        try:
            r = _post("/ask", d, timeout)
        except (ConnectionError, OSError):
            _start_local()
            r = _post("/ask", d, timeout)
    except Exception as exc:
        raise CostDenied(f"Cost Agent not reachable ({type(exc).__name__}): nothing is spent without a YES") from exc
    if r.get("answer") != "yes":
        raise CostDenied(f"Cost Agent: NO ({r.get('reason')})")
    _ctx.job = job or f"{who}|{provider}"
    _ctx.who = who
    return r


def report(usd, ref=None, what="", provider="groq"):
    """Tell the ledger what a call really cost (never blocks, never raises)."""
    d = {"who": getattr(_ctx, "who", "queen"), "provider": provider, "usd": usd, "ref": ref, "what": what,
         "job": getattr(_ctx, "job", None), "where": "vm" if _remote()[0] else "mac"}
    threading.Thread(target=lambda: _try(d), daemon=True).start()


def _try(d):
    try:
        _post("/spent", d, 5)
    except Exception:
        pass
