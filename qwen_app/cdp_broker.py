"""One permanent DevTools connection to Marko's Chrome, shared by Queen's hands (13.11.2026).

Marko: "Everything must run the whole operation in the background while I'm using computer ... using debugging mode in Chrome
browser to do the work, so interaction with mouse is not necessary. I can have mouse and keyboard and speakers to do my work."

Chrome asks "Allow remote debugging?" for EVERY new DevTools connection, and an unanswered or denied question makes it refuse
the next ones (403). So the connection is opened ONCE, by this broker, and kept; every picture goes through it. Chrome asks
once per Chrome session, not once per picture.

The one question: if Marko has not touched mouse or keyboard for 60 s, Macro Recorder presses Allow (his rule of 12.11.2026);
if he is working, the broker does NOT move his pointer: it asks him once, by voice (:8837/say), and waits up to 10 minutes.

    python3 cdp_broker.py              runs on 127.0.0.1:9333 (it stays up until Chrome closes the connection)
    GET  /health                       {"ok", "connected", "since"}
    POST /send {method, params, sessionId?, timeout?}   -> {"result"} or {"error"}
    GET  /events?after=N               Chrome's notices after number N (the newest 3000 are kept)
"""
import itertools
import json
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = 9333
PORT_FILE = Path.home() / "Library" / "Application Support" / "Google" / "Chrome" / "DevToolsActivePort"
ALLOW_TOOL = Path.home() / "Developer" / "MACRO_SKILLS" / "tools" / "chrome_allow_debugging.py"
STATE = {"ws": None, "since": None, "lock": threading.Lock(), "waiting": {}, "events": [], "seq": itertools.count(1),
         "ids": itertools.count(1)}


def idle_seconds():
    out = subprocess.run(["ioreg", "-c", "IOHIDSystem"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if "HIDIdleTime" in line:
            return int(line.split("=")[-1].strip()) / 1e9
    return 0


def say(text):
    try:
        req = urllib.request.Request("http://127.0.0.1:8837/say", data=json.dumps({"text": text}).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10).read()
    except Exception:
        pass


def answer_allow(stop):
    """Press Allow only while Marko is idle; otherwise ask him once by voice."""
    sys.path.insert(0, str(ALLOW_TOOL.parent))
    import chrome_allow_debugging as allow  # noqa: PLC0415
    asked = False
    end = time.time() + 600
    while time.time() < end and not stop.is_set():
        b = allow.dialog()
        if b:
            if idle_seconds() >= 60:
                time.sleep(1.2)
                allow.press(allow.dialog() or b)
                time.sleep(1)
            elif not asked:
                say("Marko, Chrome asks once to allow remote debugging for Queen. Please press Allow when you have a moment.")
                asked = True
        time.sleep(0.5)


def connect():
    import websocket  # noqa: PLC0415
    port, path = PORT_FILE.read_text().split()[:2]
    stop = threading.Event()
    t = threading.Thread(target=answer_allow, args=(stop,), daemon=True)
    t.start()
    try:
        ws = websocket.create_connection(f"ws://127.0.0.1:{port}{path}", timeout=620, suppress_origin=True)
    finally:
        stop.set()
    ws.settimeout(None)
    STATE["ws"], STATE["since"] = ws, time.strftime("%H:%M:%S")
    threading.Thread(target=reader, daemon=True).start()
    print(f"[broker] connected to Chrome at {STATE['since']}", flush=True)


def reader():
    ws = STATE["ws"]
    while True:
        try:
            m = json.loads(ws.recv())
        except Exception as exc:
            print(f"[broker] Chrome closed the connection: {exc}", flush=True)
            STATE["ws"] = None
            for w in list(STATE["waiting"].values()):
                w["reply"] = {"error": {"message": "Chrome closed the connection"}}
                w["done"].set()
            return
        if "id" in m and m["id"] in STATE["waiting"]:
            w = STATE["waiting"].pop(m["id"])
            w["reply"] = m
            w["done"].set()
        else:
            STATE["events"].append({"n": next(STATE["seq"]), **m})
            del STATE["events"][:-3000]


def send(method, params=None, session=None, timeout=60):
    if not STATE["ws"]:
        raise RuntimeError("not connected to Chrome")
    mid = next(STATE["ids"])
    w = {"done": threading.Event(), "reply": None}
    STATE["waiting"][mid] = w
    msg = {"id": mid, "method": method, "params": params or {}}
    if session:
        msg["sessionId"] = session
    with STATE["lock"]:
        STATE["ws"].send(json.dumps(msg))
    if not w["done"].wait(timeout):
        STATE["waiting"].pop(mid, None)
        return {"error": {"message": f"no answer in {timeout}s"}}
    return w["reply"]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/health"):
            return self._json(200, {"ok": True, "connected": bool(STATE["ws"]), "since": STATE["since"]})
        if self.path.startswith("/events"):
            after = int(self.path.split("after=")[-1]) if "after=" in self.path else 0
            return self._json(200, {"events": [e for e in STATE["events"] if e["n"] > after]})
        self._json(404, {"error": "no such path"})

    def do_POST(self):
        if not self.path.startswith("/send"):
            return self._json(404, {"error": "no such path"})
        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        try:
            r = send(d["method"], d.get("params"), d.get("sessionId"), float(d.get("timeout", 60)))
        except Exception as exc:
            r = {"error": {"message": str(exc)}}
        self._json(200, r)


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    connect()
    while STATE["ws"]:
        time.sleep(1)
    srv.shutdown()          # Chrome went away: the next hand that needs it starts a new broker


if __name__ == "__main__":
    main()
