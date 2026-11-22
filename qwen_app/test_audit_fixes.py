"""Tests for the bugs found by the 22.11.2026 audit (AUDIT_2026-11-22.md). Offline: no model, no Chrome, no real state.

Every check prints PASS or FAIL; the file exits 1 when any check failed (so the run before a fix shows every failure).
"""
from __future__ import annotations

import atexit
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

FAILED: list[str] = []


def check(name: str, ok: bool) -> None:
    print(f"{'PASS' if ok else 'FAIL'} {name}")
    if not ok:
        FAILED.append(name)


def section(name, fn):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001  a missing function before the fix is a FAIL, not a crash
        check(f"{name} ({type(exc).__name__}: {str(exc)[:120]})", False)


import queen_backend  # noqa: E402
import capi_chat  # noqa: E402
import claude_link  # noqa: E402

client = queen_backend.app.test_client()
home = Path(tempfile.mkdtemp(prefix="queen-audit-"))
atexit.register(shutil.rmtree, home, ignore_errors=True)
capi_chat.ROOT = home / "capi"
capi_chat.PROVIDER_FILE = home / "capi_provider.json"
FOLDER = ROOT if str(ROOT).startswith(str(Path.home()) + os.sep) else Path.home()


def no_provider(*_a, **_k):
    raise AssertionError("a provider or model was called for a local command")


# ---- 2. /api/claude/* (local Claude Code first) is registered
def t2():
    with patch.object(claude_link, "status", return_value={"reachable": True, "why": "", "auth": "claude.ai plan"}), \
            patch.object(claude_link, "sessions", return_value=[]):
        r = client.get("/api/claude/status")
    check("audit 2: /api/claude/status is registered", r.status_code == 200 and r.get_json().get("reachable") is True)
    with patch.object(claude_link, "ask", return_value={"answer": "PONG", "via": "local Claude Code (plan)"}):
        r = client.post("/api/claude/ask", json={"question": "say PONG"})
    check("audit 2: /api/claude/ask answers through the local Claude Code",
          r.status_code == 200 and r.get_json().get("answer") == "PONG")
    check("audit 2: /api/claude/ask without a question is refused",
          client.post("/api/claude/ask", json={}).status_code == 400)


# ---- 3 / B. ONE local router before any model, on every entry point
def t3():
    with patch.object(capi_chat.Conv, "send", no_provider):
        r = client.post("/api/capi/ask", json={"text": "list skills", "cwd": str(FOLDER)})
        d = r.get_json()
        check("audit 3 /api/capi/ask: 'list skills' runs locally at $0",
              r.status_code == 200 and "Available local Python skills" in d.get("answer", "") and d.get("cost") == 0
              and not d.get("error"))
        room = client.get(f"/api/capi/get?id={d['id']}").get_json()["room"]
        check("audit 3 /api/capi/ask: the local answer is stored in the chat",
              room["messages"][-1].get("label") == "PYTHON · list-skills")
        r = client.post("/api/capi/turn", json={"text": "current folder", "cwd": str(FOLDER)})
        lines = [json.loads(x) for x in r.get_data(as_text=True).splitlines() if x.strip()]
        check("audit 3 /api/capi/turn: 'current folder' runs locally",
              any("working folder" in (x.get("text") or "") for x in lines) and any(x.get("done") for x in lines))
        created = client.post("/api/capi/new", json={"cwd": str(FOLDER)}).get_json()
        sent = client.post("/api/capi/send", json={"id": created["room"]["id"], "text": "ableton help"}).get_json()
        check("audit 3 /api/capi/send (window): 'ableton help' runs locally", sent.get("local_skill") == "ableton-control")
    import queen_brain
    with patch.object(claude_link, "ask", no_provider), patch.object(claude_link, "status", no_provider):
        r = client.post("/api/chat", json={"messages": [{"role": "user", "content": "list skills"}]})
    lines = [json.loads(x) for x in r.get_data(as_text=True).splitlines() if x.strip()]
    check("audit 3 /api/chat (queen CLI): 'list skills' runs locally, no model",
          any("Available local Python skills" in (x.get("t") or "") for x in lines)
          and any((x.get("u") or {}).get("local_skill") == "list-skills" for x in lines))
    with patch.object(claude_link, "ask", no_provider), patch.object(claude_link, "status", no_provider):
        r = client.post("/api/internal/local_command", json={"text": "ABLETON: nonsense words"})
    check("audit 3 /api/internal/local_command: ABLETON: prefix is matched locally",
          r.status_code == 200 and r.get_json().get("skill") == "ableton-control")
    import local_router
    check("audit 3: a QUEEN: OFF chat gets Python skills but not her hands",
          local_router.route("pause status", {}, hands=False) is None)
    del queen_brain


# ---- B. her brain: local Claude Code with her skills; unreachable -> the manifest's sentence, never a paid provider
def tB():
    import queen_brain
    captured = {}

    def fake_ask(q, model="sonnet", system=None, **_k):
        captured.update(q=q, system=system, model=model)
        return {"answer": "Hello Marko", "via": "local Claude Code (plan)"}

    with patch.object(claude_link, "status", return_value={"reachable": True}), patch.object(claude_link, "ask", fake_ask):
        r = client.post("/api/chat", json={"messages": [{"role": "user", "content": "how do I open a settings pane?"}]})
    lines = [json.loads(x) for x in r.get_data(as_text=True).splitlines() if x.strip()]
    check("B: /api/chat answers through the local Claude Code", any(x.get("t") == "Hello Marko" for x in lines))
    sysp = captured.get("system") or ""
    check("B: her skills are the system prompt (catalogue + working rules)",
          "## Her skills" in sysp and "how-queen-works" not in sysp.split("## Her skills")[1][:0] and "open-settings-pane" in sysp)
    check("B: the matching skill's full text is included", "## Skill open-settings-pane" in sysp)
    _, info = queen_brain.system_prompt("how do I open a settings pane?")
    check("B: the skills prompt is much smaller than all skills (catalogue, not every body)",
          info["prompt_chars"] < info["all_skills_chars"] / 2)
    with patch.object(claude_link, "status", return_value={"reachable": False, "why": "test"}), \
            patch.object(claude_link, "ask", no_provider), patch.object(capi_chat.Conv, "send", no_provider):
        r = client.post("/api/chat", json={"messages": [{"role": "user", "content": "write me a poem"}]})
    lines = [json.loads(x) for x in r.get_data(as_text=True).splitlines() if x.strip()]
    check("B: Claude Code unreachable -> 'I cannot reach the local Claude Code. Do you want to use API credits?'",
          any(x.get("t") == claude_link.CONSENT_TEXT for x in lines)
          and any((x.get("u") or {}).get("need_consent") for x in lines))


# ---- A. every route her skills name is registered (the pin: the next rewrite fails the build instead of reaching him)
SKILL_ROUTE_EXEMPT = {
    # negative examples inside the skills ("do not invent ...")
    "/api/system/mv": "move-file.md says there is NO such route",
    "/api/system/set_volume": "system-volume.md says there is NO such route",
    # other apps' doors, not Queen's
    "/api/ndi": "Meditation Room :8965", "/api/preshow": "Meditation Room :8965", "/api/state": "Meditation Room :8965",
    "/api/text": "Meditation Room :8965", "/api/snapshot": "VM pre-show :8996",
    # need a Groq model: off since v31 (Groq-free), decision of 22.11.2026 not to bring Groq back
    "/api/brain/escalate": "Groq-bound (brain.py)", "/api/remote/send": "Groq-bound (legacy chat)",
    "/api/screen/look": "Groq-bound (screen_look)", "/api/selfcheck/image-live": "Groq-bound (live_check)",
    "/api/skills/band-posters": "Groq-bound (poster_skill)", "/api/skills/describe-images": "Groq-bound (describe_skill)",
    "/api/skills/gemini-posters": "Groq-bound (poster_skill)", "/api/skills/live-check": "Groq-bound (live_check)",
    "/api/skills/poster-like": "Groq-bound (poster_skill)", "/api/skills/web-photo": "Groq-bound (web_photo_skill)",
    "/api/triple/get": "Groq-bound (triple_chat)", "/api/triple/list": "Groq-bound (triple_chat)",
    "/api/triple/new": "Groq-bound (triple_chat)", "/api/triple/settings": "Groq-bound (triple_chat)",
    "/api/triple/turn": "Groq-bound (triple_chat)", "/api/vision/ask": "Groq-bound (vision)",
    # inside the retired 3,844-line app, not yet ported (Groq-free but entangled); /api/repo/* reads repos meanwhile
    "/api/github/contents": "retired monolith, not ported", "/api/elevate/whatsapp": "retired monolith, not ported",
}


def tA():
    adapter = queen_backend.app.url_map.bind("localhost")
    rules = [r.rule for r in queen_backend.app.url_map.iter_rules()]
    named: dict[str, set] = {}
    for f in glob.glob(str(ROOT / "queen_skills" / "*")):
        for m in re.finditer(r"(/api/[A-Za-z0-9_/\-<>{}.]+)", Path(f).read_text(errors="ignore")):
            named.setdefault(m.group(1).rstrip(".").split("?")[0], set()).add(Path(f).name)
    missing = {}
    for route, files in named.items():
        if route in SKILL_ROUTE_EXEMPT:
            continue
        if route.endswith("/"):
            if not any(r.startswith(route) for r in rules):
                missing[route] = files
            continue
        probe = re.sub(r"<[^>]+>|\{[^}]+\}", "x", route)
        found = False
        for method in ("GET", "POST"):
            try:
                adapter.match(probe, method=method)
                found = True
                break
            except Exception as exc:  # noqa: BLE001
                if type(exc).__name__ == "MethodNotAllowed":
                    found = True
                    break
        if not found:
            missing[route] = files
    check(f"A: every route named in queen_skills/ is registered ({len(named)} named, missing: "
          f"{ {k: sorted(v) for k, v in missing.items()} })", not missing)
    import restored_routes
    check(f"A: every Groq-free module loaded (failed: {restored_routes.FAILED})", not restored_routes.FAILED)
    d = client.get("/api/queen/modules").get_json()
    check("A: /api/queen/modules lists loaded, failed and Groq-bound-off modules",
          "loaded" in d and "failed" in d and d.get("groq_bound_off"))
    check("A: pause routes are back", client.get("/api/pause/status").status_code == 200)
    check("A: supervisor pending route is back", client.get("/api/supervisor/pending").status_code in (200, 500))


# ---- 7. self-update gate
def t7():
    ok, errs = queen_backend._ci("x = 1\n", "capi_chat.py", old_code="x = 1\n" * 200, run_tests=False)
    check("audit 7: CI refuses a file shrunk below 30 % of the old one", not ok and any("30" in e for e in errs))
    ok, _ = queen_backend._ci("x = 2\n" * 150, "capi_chat.py", old_code="x = 1\n" * 200, run_tests=False)
    check("audit 7: CI passes a normal edit (no tests)", ok)
    ok, _ = queen_backend._ci("def f(:\n", "capi_chat.py", old_code="", run_tests=False)
    check("audit 7: CI still refuses broken Python", not ok)
    if not os.environ.get("QUEEN_GATE"):        # inside the gate's own test run, do not recurse
        broken = (HERE / "queen_python_skills" / "__init__.py").read_text().replace('"list skills",', '"list skillz",')
        ok, errs = queen_backend._ci(broken, "queen_python_skills/__init__.py")
        check("audit 7: CI runs the tests on a copy and refuses an edit that breaks them", not ok)
    repo = home / "repo"
    (repo / "mac_app" / "app").mkdir(parents=True)
    (repo / "version.json").write_text(json.dumps({"version": 31, "log": []}))
    (repo / "mac_app" / "app" / "App.swift").write_text("import SwiftUI\nlet VERSION = 31\nlet X = 1\n")
    with patch.object(queen_backend, "VERSION_FILE", repo / "version.json"), patch.object(queen_backend, "REPO_ROOT", repo):
        v = queen_backend._bump_version(["capi_chat.py"], "test")
        check("audit 7: a self-update bumps version.json and App.swift together",
              v == 32 and json.loads((repo / "version.json").read_text())["version"] == 32
              and "let VERSION = 32\n" in (repo / "mac_app" / "app" / "App.swift").read_text())
        (repo / "mac_app" / "app" / "App.swift").unlink()
        try:
            queen_backend._bump_version(["capi_chat.py"], "test")
            refused = False
        except RuntimeError:
            refused = True
        check("audit 7: no version bump without App.swift", refused
              and json.loads((repo / "version.json").read_text())["version"] == 32)
        check("audit 7: the preflight refuses before any file is written", bool(queen_backend._version_preflight()))
    msg = queen_backend._commit_message("v32: change", provider="anthropic", model="claude-sonnet-5-5")
    check("audit 7: the commit names the model that wrote it, not Copilot",
          "Copilot" not in msg and "claude-sonnet-5-5" in msg)
    src = (HERE / "queen_backend.py").read_text()
    check("audit 7: no hard-coded Copilot trailer left", "223556219+Copilot" not in src)


# ---- 11. Gemini hands: no shell, allowlist; the obvious bypasses are refused
def t11():
    import gemini_hands as H
    root = home / "hands"
    (root / "a").mkdir(parents=True)
    (root / "a" / "hello.py").write_text("print(2+2)\n")
    root = os.path.realpath(root)
    bypasses = ["cd $HOME && ls", "ls $(echo /)", "ls `pwd`/..", "cat ~/.ssh/id_rsa", "ls /etc", "echo hi; rm -rf a",
                "ls | sh", "python3 -c 'import os'", "curl https://example.com", "find . -exec rm {} +",
                "git push origin main", "bash -c ls", "zsh -lc ls", "ls > /tmp/x", "cat ../../.zshrc",
                "env", "awk 'BEGIN{system(\"ls\")}'", "/bin/sh -c ls", "osascript -e 1", "sudo ls"]
    leaked = [c for c in bypasses if "error" not in H.tool(root, "run_shell", {"command": c})[0]]
    check(f"11: every bypass is refused (allowed by mistake: {leaked})", not leaked)
    res, _ = H.tool(root, "run_shell", {"command": "python3 a/hello.py"})
    check("11: a script in the folder still runs", res.get("exit_code") == 0 and "4" in res.get("output", ""))
    res, _ = H.tool(root, "run_shell", {"command": "ls a"})
    check("11: ls inside the folder runs", res.get("exit_code") == 0 and "hello.py" in res.get("output", ""))
    check("11: the tool declaration no longer offers a zsh shell", "zsh" not in json.dumps(H.DECLS))


# ---- E. the header shows Google's last real answer, not an estimate presented as money left
def tE():
    import gcloud_chat
    with patch.object(gcloud_chat, "STATUS_FILE", home / "provider_status.json"):
        gcloud_chat.record_answer(402, "Your prepayment credits are depleted. Please go to AI Studio")
        line = gcloud_chat.status_line()
        check("E: a 402 shows as 'Gemini: 402, credits depleted (date)'", line.startswith("Gemini: 402, credits depleted ("))
        with patch.object(capi_chat, "get_provider", return_value="gcloud"):
            d = capi_chat._credit_info()
        check("E: /api/capi/credit carries the status line and explains the old estimate",
              d["status_line"] == line and "estimate" in d["note"] and "not a balance" in d["note"])
        check("E: the window intro says what answers and what it costs", "Gemini on Google Cloud answers here" in d["intro"])
    swift = (ROOT / "mac_app" / "app" / "Capi.swift").read_text()
    check("E: the window shows status_line when the backend gives one", "statusLine" in swift and "status_line" in swift)
    poll = swift[swift.index("private func startPolling()"):][:1200]
    check("v33: the CAPI tab asks the credit again until the backend has answered once (launch race)",
          "if !self.creditLoaded { await self.loadCredit() }" in poll and "creditLoaded = true" in swift)
    check("D: the old wording 'Claude Code on your API credit. Ask for anything' is gone",
          "Claude Code on your API credit. Ask for anything" not in swift)


# ---- D. no ON/OFF button (rule no-on-off-button.md, 16.11.2026); the window's own X quits the app
def tD():
    app = (ROOT / "mac_app" / "app" / "App.swift").read_text()
    top = app[app.index("struct TopRow"):app.index("static func float")]
    check("D: the top row has no ON and no OFF", 'Text("ON")' not in top and 'text: "OFF"' not in top)
    check("D: the app's own X quits Queen (through the quit guard)", 'axButton("Quit Queen"' in top and ".onTapGesture { DispatchQueue.main.async { NSApp.terminate(nil) } }" in top)


# ---- C. she listens only on loopback; there is no Tailscale listener to guard
def tC():
    calls = {}
    with patch.object(queen_backend, "serve", lambda app, **k: calls.update(k)), \
            patch.object(queen_backend, "migrate_legacy_state", lambda: None), \
            patch.object(queen_backend, "HOME", home), \
            patch("restored_routes.register_runtime", lambda app: None), patch("pause_state.install", lambda: None):
        queen_backend.main()
    check("C: the Python backend binds 127.0.0.1 only", calls.get("host") == "127.0.0.1")
    net = (ROOT / "mac_app" / "app" / "core" / "Net.swift").read_text()
    start = net[net.index("func start(port: UInt16)"):][:900]
    check("C: the Swift server binds the loopback address only",
          "Sock.loopback(port)" in start and 'inet_addr("127.0.0.1")' in net and "INADDR_ANY" not in net)
    r = client.get("/api/version", environ_base={"REMOTE_ADDR": "100.102.86.30"})
    check("C: a request from a Tailscale address is refused by the backend", r.status_code == 403)


# ---- 12 / 8. launchers
def t12():
    qwen = (ROOT / "qwen").read_text()
    check("audit 12: qwen looks for /Applications/Queen.app/Contents/MacOS/Queen",
          'MacOS/Queen"' in qwen and "GroqAIStudio" not in qwen)
    inst = (ROOT / "mac_app" / "install.sh").read_text()
    check("audit 8: install.sh waits until Queen has really quit before replacing her",
          "pgrep" in inst and "still running" in inst)
    r = subprocess.run(["sh", "-n", str(ROOT / "mac_app" / "install.sh")], capture_output=True)
    check("audit 8: install.sh is valid sh", r.returncode == 0)


for name, fn in (("2", t2), ("3", t3), ("B", tB), ("A", tA), ("7", t7), ("11", t11), ("E", tE), ("D", tD), ("C", tC),
                 ("12/8", t12)):
    section(f"section {name}", fn)

if FAILED:
    print(f"{len(FAILED)} FAILED")
    sys.exit(1)
print("ALL PASS")
