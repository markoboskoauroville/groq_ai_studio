"""Affinity for Queen: the action database and the hand that fires it.

Marko, 12.11.2026: "Please map all the actions to Macro Recorder and Groq ... They need to have a
database of everything that's possible, and they just fire it in lightning speed."

Affinity 3.3 (the free Canva app) carries its own MCP server on 127.0.0.1 and a complete JavaScript
SDK. This module gives Queen four things, all local, none of them costing a token:

    the action database      every proven action with its arguments (MACRO_SKILLS/affinity/actions.json)
    the API index            492 classes, 5601 members, built from Affinity's own JSLib
    fire                     run one action, or any JavaScript, inside the running app
    look                     render a spread or the selection back as a JPEG

Routes (registered by app.py): /api/affinity/status | /open | /close | /actions | /api/ | /do | /js | /render

/open and /close are also answered straight from Queen's chat ("open Affinity", "close Affinity"),
without the model: chat_app_command() below. Marko, 12.11.2026: "If Affinity is already open, and you
ask Queen to open Affinity, she should respond, 'Affinity is already open.'"
"""
import re
import base64
import json
import subprocess
import sys
from pathlib import Path

from flask import jsonify, request

MACRO_SKILLS = Path.home() / "Developer" / "MACRO_SKILLS"
ACTIONS = MACRO_SKILLS / "affinity" / "actions.json"
API_INDEX = MACRO_SKILLS / "affinity" / "api_index.json"
TOOLS = MACRO_SKILLS / "tools"


_CLIENT = None


def _client():
    """The affinityctl MCP client, loaded from MACRO_SKILLS so there is only one copy of it.

    Loaded by path, not by name: this file used to be called affinity.py too, and `import affinity`
    found itself instead of the client (12.11.2026 bug, AttributeError: no attribute affinity_pid).
    """
    global _CLIENT
    if _CLIENT is None:
        import importlib.util  # noqa: PLC0415
        path = TOOLS / "affinity.py"
        if not path.exists():
            raise RuntimeError(f"affinityctl client not found at {path}")
        spec = importlib.util.spec_from_file_location("affinityctl_client", path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["affinityctl_client"] = mod
        spec.loader.exec_module(mod)
        _CLIENT = mod
    return _CLIENT


def _actions():
    try:
        return json.loads(ACTIONS.read_text())
    except Exception:
        return {}


_OPEN = re.compile(r"^\W*(please\W+)?(can you\W+)?(open|start|launch|run)\W+(the\W+)?affinity(\W+app)?\W*(please)?\W*$", re.I)
_CLOSE = re.compile(r"^\W*(please\W+)?(can you\W+)?(close|quit|exit|stop)\W+(the\W+)?affinity(\W+app)?\W*(please)?\W*$", re.I)


def chat_app_command(text):
    """A chat line that only asks to open or close Affinity -> the answer, done locally; else None."""
    t = (text or "").strip()
    if _OPEN.match(t):
        return _client().open_app()["message"]
    if _CLOSE.match(t):
        return _client().close_app()["message"]
    return None


def register(app):
    @app.get("/api/affinity/status")
    def affinity_status():
        aff = _client()
        pid = aff.affinity_pid()
        port = aff.find_port(pid) if pid else None
        acts = _actions()
        idx = {}
        try:
            idx = json.loads(API_INDEX.read_text())
        except Exception:
            pass
        return jsonify(
            ok=bool(pid and port),
            running=bool(pid),
            pid=pid,
            mcp_port=port,
            actions=len(acts),
            tested=sum(1 for a in acts.values() if str(a.get("state", "")).startswith("tested")),
            api_classes=idx.get("class_count", 0),
            api_members=idx.get("member_count", 0),
            note=("" if port else
                  "Affinity's MCP server is off: Settings -> Model Context Protocol -> "
                  "Enable Affinity MCP, then restart Affinity."),
        )

    @app.post("/api/affinity/open")
    def affinity_open():
        """Open Affinity and cancel its start-up pop-ups; says "Affinity is already open." when it is."""
        try:
            return jsonify(_client().open_app())
        except Exception as exc:
            return jsonify(ok=False, message=f"{type(exc).__name__}: {exc}"), 500

    @app.post("/api/affinity/close")
    def affinity_close():
        """Quit Affinity normally; never forced (an unsaved document's question stays for Marko)."""
        try:
            return jsonify(_client().close_app())
        except Exception as exc:
            return jsonify(ok=False, message=f"{type(exc).__name__}: {exc}"), 500

    @app.get("/api/affinity/actions")
    def affinity_actions():
        q = (request.args.get("q") or "").lower().split()
        out = {}
        for aid, a in _actions().items():
            hay = (aid + " " + a.get("title", "") + " " + " ".join(a.get("tags", []))).lower()
            if q and not all(w in hay for w in q):
                continue
            out[aid] = {"title": a.get("title"), "args": a.get("args", []),
                        "tags": a.get("tags", []), "state": a.get("state", "")}
        return jsonify(ok=True, count=len(out), actions=out)

    @app.get("/api/affinity/api")
    def affinity_api():
        """Search the local index of Affinity's SDK: classes, methods, getters, setters."""
        q = [w for w in (request.args.get("q") or "").lower().split() if w]
        if not q:
            return jsonify(ok=False, error="pass ?q=<words>"), 400
        try:
            idx = json.loads(API_INDEX.read_text())
        except Exception as exc:
            return jsonify(ok=False, error=f"no api index: {exc}"), 500
        hits = []
        for mod, classes in idx.get("modules", {}).items():
            for cls, info in classes.items():
                cls_hit = all(w in cls.lower() for w in q)
                members = [m for m in info.get("members", [])
                           if all(w in m["name"].lower() for w in q)]
                if cls_hit or members:
                    hits.append({"module": mod, "class": cls, "extends": info.get("extends"),
                                 "members": (info.get("members") if cls_hit else members)[:40]})
        return jsonify(ok=True, count=len(hits), hits=hits[:40])

    @app.post("/api/affinity/do")
    def affinity_do():
        data = request.get_json(silent=True) or {}
        aid = (data.get("action") or "").strip()
        args = data.get("args") if isinstance(data.get("args"), dict) else {}
        acts = _actions()
        if aid not in acts:
            return jsonify(ok=False, error=f"no action {aid!r}",
                           known=sorted(acts)), 400
        aff = _client()
        try:
            script = aff.fill(acts[aid]["js"], args)
            out = aff.Affinity().execute(script)
        except SystemExit as exc:
            return jsonify(ok=False, error=str(exc)), 400
        except SystemExit as exc:          # the client refuses on purpose (paid Canva, missing args)
            return jsonify(ok=False, error=str(exc)), 400
        except Exception as exc:
            return jsonify(ok=False, error=f"{type(exc).__name__}: {exc}"), 500
        failed = out.strip().startswith(("Error", "TypeError", "ReferenceError", "SyntaxError"))
        return jsonify(ok=not failed, action=aid, output=out)

    @app.post("/api/affinity/js")
    def affinity_js():
        data = request.get_json(silent=True) or {}
        script = data.get("script") or ""
        if not script.strip():
            return jsonify(ok=False, error="pass {'script': '<javascript>'}"), 400
        aff = _client()
        try:
            out = aff.Affinity().execute(script)
        except SystemExit as exc:          # the client refuses on purpose (paid Canva, missing args)
            return jsonify(ok=False, error=str(exc)), 400
        except Exception as exc:
            return jsonify(ok=False, error=f"{type(exc).__name__}: {exc}"), 500
        failed = out.strip().startswith(("Error", "TypeError", "ReferenceError", "SyntaxError"))
        return jsonify(ok=not failed, output=out)

    @app.post("/api/affinity/render")
    def affinity_render():
        """Render a spread (or the selection) and hand it back as base64 JPEG, to look at."""
        data = request.get_json(silent=True) or {}
        aff = _client()
        try:
            a = aff.Affinity()
            uuid = data.get("uuid") or aff._current_uuid(a)
            if data.get("selection"):
                res = a.call("render_selection", {"document_session_uuid": uuid})
            else:
                res = a.call("render_spread", {"document_session_uuid": uuid,
                                               "spread_index": int(data.get("spread", 0))})
        except SystemExit as exc:          # the client refuses on purpose (paid Canva, missing args)
            return jsonify(ok=False, error=str(exc)), 400
        except Exception as exc:
            return jsonify(ok=False, error=f"{type(exc).__name__}: {exc}"), 500
        imgs = aff.Affinity.images(res)
        if not imgs:
            return jsonify(ok=False, error=aff.Affinity.text(res) or "no image"), 500
        out_path = data.get("path")
        if out_path:
            Path(out_path).write_bytes(base64.b64decode(imgs[0]["data"]))
        return jsonify(ok=True, mime=imgs[0].get("mimeType", "image/jpeg"),
                       path=out_path, data=imgs[0]["data"])

    return app
