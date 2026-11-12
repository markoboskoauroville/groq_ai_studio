"""The model router: pick the Groq model that does the job for the least money.

Marko, 12.11.2026: "Please also build in the Queen model router to leverage the best of all the models Groq is using
for different tasks here, and to switch models as needed." And: "Before giving the role to any of Groq models, please
test them truly and see their bugs."

So no model has a role here that it did not earn on the bench. Everything below was measured on 12.11.2026 with
MANTRA_CHROME_EXTENSIONS/tools/queen_stress.py (10 tasks: Python, shell, HTML, JavaScript, JSON, Swift, a multi-file
package, three files that reference each other, a config read back, and an honesty test) and queen_bench.py
(7 Chrome extensions, trivial to complex), every answer graded by real tools through `verify`.

    MEASURED, 12.11.2026
    model                 10-task stress     7 extensions      verdict
    openai/gpt-oss-20b    10/10  $0.0060     7/7  $0.0108      best value by far; the default for code
    openai/gpt-oss-120b   10/10  $0.0076     6/7  $0.0211      one JavaScript syntax slip; no measured edge
    qwen/qwen3.8-27b      10/10  $0.0182     7/7  $0.1012      correct, but 9x the price of gpt-oss-20b
    qwen/qwen3.6-27b       9/10  $0.0667     not run           slowest and dearest; superseded
    allam-2-7b            Arabic-first, not benchmarked for code
    canopylabs/orpheus-*  speech only (6 fixed voices, no cloning)

The surprise worth keeping: the CHEAPEST model was the most reliable. That is why roles are measured, not assumed.
"""
from __future__ import annotations

# what each job needs, and the cheapest model measured to do it
ROUTES: dict[str, dict] = {
    "code": {
        "model": "openai/gpt-oss-20b",
        "why": "10/10 on the stress battery and 7/7 on the extension ladder, at $0.0108 a run - "
               "a ninth of qwen3.8-27b for the same score",
        "fallback": ["qwen/qwen3.8-27b", "openai/gpt-oss-120b"],
    },
    "extension": {
        "model": "openai/gpt-oss-20b",
        "why": "7/7 on the extension ladder; gpt-oss-120b failed one on a JavaScript syntax error",
        "fallback": ["qwen/qwen3.8-27b"],
    },
    "plan": {
        "model": "openai/gpt-oss-20b",
        "why": "planned the same chains as qwen3.8-27b and refused the impossible goal just as firmly",
        "fallback": ["qwen/qwen3.8-27b"],
    },
    "chat": {
        "model": "openai/gpt-oss-20b",
        "why": "fast and cheap; nothing measured favours a dearer model for conversation",
        "fallback": ["qwen/qwen3.8-27b"],
    },
    "long": {
        "model": "qwen/qwen3.8-27b",
        "why": "kept as the choice for long or unusual work until something harder is benchmarked - "
               "NOT a measured advantage, an unmeasured caution",
        "fallback": ["openai/gpt-oss-120b"],
    },
    "speech_out": {
        "model": "canopylabs/orpheus-v1-english",
        "why": "about 5x faster than real time; six fixed voices (autumn diana hannah austin daniel troy) "
               "and NO voice cloning - the API rejects every reference-audio field",
        "fallback": [],
    },
    "speech_in": {
        "model": "whisper-large-v3",
        "why": "13x faster than real time at 95.8% on a round trip through the speakers",
        "fallback": ["whisper-large-v3-turbo"],
    },
}

DEFAULT = "openai/gpt-oss-20b"

# words in the prompt that say what kind of job it is
HINTS: list[tuple[str, tuple[str, ...]]] = [
    ("extension", ("chrome extension", "manifest.json", "manifest v3", "content script", "service worker")),
    ("code", ("write a script", "write a function", "in the code box", "code only", "just the code",
              "python", "javascript", "swift", "shell script", "html", "refactor", "unit test")),
    ("plan", ("plan", "which steps", "in what order", "sequence of", "chain of")),
    ("speech_out", ("read this aloud", "say this", "text to speech")),
    ("speech_in", ("transcribe", "speech to text", "what does this recording say")),
]


def kind_of(prompt: str) -> str:
    low = (prompt or "").lower()
    for kind, words in HINTS:
        if any(w in low for w in words):
            return kind
    if len(low) > 4000:
        return "long"
    return "chat"


def pick(prompt: str = "", kind: str | None = None, available: list[str] | None = None) -> dict:
    """Return {model, kind, why, fallback} - the cheapest model measured to do this job."""
    k = kind or kind_of(prompt)
    route = ROUTES.get(k) or ROUTES["chat"]
    model = route["model"]
    chain = [model] + list(route.get("fallback", []))
    if available:
        chain = [m for m in chain if m in available] or [DEFAULT]
        model = chain[0]
    return {"kind": k, "model": model, "why": route["why"], "chain": chain}


def table() -> list[dict]:
    return [{"kind": k, **v} for k, v in ROUTES.items()]


# ---------------------------------------------------------------- HTTP
try:
    from flask import Blueprint, jsonify, request

    router_bp = Blueprint("model_router", __name__)

    @router_bp.route("/api/router/table", methods=["GET"])
    def router_table():
        """Every role, the model that earned it, and why - the measurement, not an opinion."""
        return jsonify(ok=True, default=DEFAULT, routes=table())

    @router_bp.route("/api/router/pick", methods=["POST"])
    def router_pick():
        body = request.get_json(silent=True) or {}
        return jsonify(ok=True, **pick(body.get("prompt", ""), body.get("kind"), body.get("available")))
except Exception:                                   # importable without Flask, for the tests
    router_bp = None
