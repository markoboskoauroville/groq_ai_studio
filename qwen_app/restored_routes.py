"""Routes lost in the v31 rewrite, restored in v32 (audit 22.11.2026, decision (A) of the Fable master session).

v31 ("Groq-free runtime", 19.11.2026) registered only CAPI, Gemini image, Ableton, the skill catalogue and Auto Update; the
routes of every other module stayed in the repo but answered 404, so 32 of her 66 skills named dead routes and the
`queen` CLI was dead. Every Groq-free module is registered again here, each in its own guard: a module that fails to
load is logged and listed by GET /api/queen/modules (and `queen status`), never silent, and never takes the server down.
Modules that need a Groq model stay off and are listed as such (GROQ_BOUND). Groq is not brought back.
"""
from __future__ import annotations

import json
import time

from flask import Response, jsonify, request

# Groq-free modules with register(app); data_sync is started only by the running server (it pushes a data repo).
MODULES = (
    "claude_link", "supervisor", "repo_reader", "ax_read", "whatsapp_ax", "whatsapp_desktop", "whatsapp_remote",
    "whatsapp_supervised", "system_volume", "system_settings", "system_files", "gphotos_album", "ndi_monitor",
    "affinity_bridge", "speak", "training_log", "image_collect_skill", "vm_gemini_skill",
)
RUNTIME_ONLY = ("data_sync",)
# Modules of the old server that need a Groq model (pool / record_spend / the Groq chat). Off since v31.
GROQ_BOUND = {
    "legacy chat + keys + billing + chats + self_update + github reader + remote/send + test/live": "legacy_groq_app.py",
    "vision": "vision.py", "posters": "poster_skill.py", "describe": "describe_skill.py", "web photo": "web_photo_skill.py",
    "live check": "live_check.py", "screen look": "screen_look.py", "news": "news.py", "triple chat": "triple_chat.py",
    "brain escalate / model router": "brain.py, model_router.py",
}

LOADED: list[str] = []
FAILED: dict[str, str] = {}


def _register_one(app, name: str) -> None:
    try:
        module = __import__(name)
        module.register(app)
        LOADED.append(name)
    except Exception as exc:  # noqa: BLE001  one broken module must not stop the others
        FAILED[name] = f"{type(exc).__name__}: {exc}"
        print(f"[restored_routes] {name} NOT loaded: {FAILED[name]}", flush=True)


def register(app) -> None:
    for name in MODULES:
        _register_one(app, name)

    import pause_state

    @app.post("/api/pause")
    def api_pause():
        return jsonify(ok=True, **pause_state.set_paused(True))

    @app.post("/api/resume")
    def api_resume():
        return jsonify(ok=True, **pause_state.set_paused(False))

    @app.get("/api/pause/status")
    def api_pause_status():
        return jsonify(ok=True, **pause_state.status())

    @app.errorhandler(pause_state.PausedError)
    def _paused_error(_e):
        return jsonify(ok=False, paused=True, error="Queen is paused"), 409

    @app.post("/api/internal/local_command")
    def internal_local_command():
        import local_router
        d = request.get_json(silent=True) or {}
        hit = local_router.route(d.get("text") or "", {"cwd": d.get("cwd") or ""}, hands=True)
        return jsonify(ok=True, answer=hit.answer if hit else None, skill=hit.skill_id if hit else None)

    @app.get("/api/queen/modules")
    def queen_modules():
        import local_router
        return jsonify(ok=not FAILED and not local_router.FAILED_HANDS, loaded=LOADED, failed=FAILED,
                       failed_hands=local_router.FAILED_HANDS, groq_bound_off=GROQ_BOUND,
                       groq_bound_hands_off=list(local_router.GROQ_BOUND_HANDS))

    @app.post("/api/chat")
    def queen_chat():
        """`queen "<q>"`: NDJSON lines {"t": text} ... {"u": {...}} (the old wire format, so the CLI works unchanged)."""
        import queen_brain
        d = request.get_json(silent=True) or {}
        messages = d.get("messages") if isinstance(d.get("messages"), list) else []
        if not messages and d.get("prompt"):
            messages = [{"role": "user", "content": str(d["prompt"])}]
        t0 = time.time()
        r = queen_brain.answer(messages, {"cwd": d.get("cwd") or ""})

        def lines():
            if r.get("text"):
                yield json.dumps({"t": r["text"]}, ensure_ascii=False) + "\n"
            if r.get("error"):
                yield json.dumps({"error": r["error"]}, ensure_ascii=False) + "\n"
            u = {"model": r.get("model", ""), "cost": r.get("cost", 0.0), "via": r.get("via", ""),
                 "secs": round(time.time() - t0, 1)}
            for k in ("local_skill", "need_consent", "prompt"):
                if k in r:
                    u[k] = r[k]
            yield json.dumps({"u": u}, ensure_ascii=False) + "\n"
        return Response(lines(), mimetype="application/x-ndjson")


def register_runtime(app) -> None:
    """Only from the running server's main(): modules with background threads (never in tests)."""
    for name in RUNTIME_ONLY:
        _register_one(app, name)
