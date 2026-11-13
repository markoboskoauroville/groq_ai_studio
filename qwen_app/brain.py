"""The brain of Macro Recorder, living inside Queen.

Marko, 12.11.2026: "The last step of doing anything on this computer is using Groq AI Studio and Macro Recorder in
tandem. You just prepare plans for them and they execute everything."

Claude writes plans. When no plan exists, this module writes one: a goal plus the catalogue of blocks and actions
goes in, a chain of steps comes out. It never invents a block; it may only say what is missing.

Routes (all under the app's existing local security guard):
    GET  /api/brain/health      is the brain reachable, which model, how many lessons
    POST /api/brain/plan        {goal, catalogue}            -> {goal, steps[], missing, confidence}
    GET  /api/brain/training    the graded examples it learns from
    POST /api/brain/teach       {goal, plan, verdict, note}  keep an example
    POST /api/brain/escalate    {goal, tried, error}         two strikes: ask Claude, and write the skill
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from flask import Blueprint, jsonify, request

brain_bp = Blueprint("brain", __name__)

STATE = Path.home() / ".groq"
TRAINING = STATE / "brain_training.json"
ESCALATIONS = STATE / "brain_escalations.json"
# Marko, 12.11.2026: "qwen3.6-27b is our default model please don't use anything from open AI."
PLAN_MODEL = os.environ.get("BRAIN_MODEL", "qwen/qwen3.6-27b")
MAX_LESSONS = 12

SYSTEM = """You are the brain of Macro Recorder on Marko's Mac. You turn a goal into a PLAN that Macro Recorder runs.

A plan is a chain of steps. Each step is ONE of:
  {"action": "<id from the catalogue>"}                     run a stored macro or built-in command
  {"block": "<id>", "call": "<one line of script>", "say": "<why>"}   use a block's function
  {"script": "<one line of script>", "say": "<why>"}        a plain line of script

HARD RULES
- Use ONLY ids that appear in the catalogue you are given. Never invent a block, an action or a function.
- If the catalogue cannot do the job, return steps you CAN do and name the gap in "missing". Do not guess.
- Put the window in front and check it before sending any key. A real click on a tab raises a Chrome window;
  WinActivate and Command-Tab do not.
- Never click a switch blind: read the state, act, read it back.
- `#` in a Send string is the Command key. A literal hash is {#}. Use SendText for a URL.
- Anything that spends money, sends, submits or deletes goes in "missing" for a human, never in the steps.
- NEVER call anything with an empty or placeholder argument. `ReadBack("")` matches everything and proves nothing;
  if you have nothing specific to check for, do not use that step at all.
- If the goal is to READ or FIND something, use the action that reads (OCR, capture, list) - not a verify block.
  A verify block is only for confirming a specific expected string after you changed something.
- Prefer one action that does the whole job over a chain of blocks that approximates it.

Answer with ONE JSON object and nothing else:
{"goal": "...", "steps": [...], "missing": "", "confidence": 0.0-1.0, "why": "one sentence"}"""


# ---------------------------------------------------------------- store
def _load(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2))
    tmp.replace(path)


def lessons_text():
    """The graded examples, good ones as patterns to copy, bad ones as traps to avoid."""
    ex = _load(TRAINING, [])[-MAX_LESSONS:]
    if not ex:
        return ""
    good = [e for e in ex if e.get("verdict") == "good"]
    bad = [e for e in ex if e.get("verdict") != "good"]
    out = []
    if good:
        out.append("Plans that worked (copy their shape):")
        for e in good:
            out.append(f'  goal: {e.get("goal","")}\n  plan: {json.dumps(e.get("plan",{}).get("steps",[]))[:600]}')
    if bad:
        out.append("Plans that were WRONG (do not repeat):")
        for e in bad:
            out.append(f'  goal: {e.get("goal","")}\n  why wrong: {e.get("note","")}')
    return "\n".join(out)


def extract_json(text):
    """The model may wrap the object in prose or a fence. Take the outermost {...}."""
    t = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", (text or "").strip())
    start = t.find("{")
    if start < 0:
        return None
    depth, in_str, esc = 0, False, False
    for i, ch in enumerate(t[start:], start):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(t[start:i + 1])
                except Exception:
                    return None
    return None


def clean_plan(plan, catalogue):
    """Drop any step naming something the catalogue does not have. Honesty over bravado."""
    ids = {b["id"] for b in catalogue.get("blocks", [])} | {a["id"] for a in catalogue.get("actions", [])}
    kept, dropped, empty = [], [], []
    for s in plan.get("steps", []) or []:
        name = s.get("action") or s.get("block")
        if name and name not in ids:
            dropped.append(name)
            continue
        # a call with an empty or placeholder argument proves nothing: ReadBack("") matches any screen (12.11.2026)
        call = s.get("call") or s.get("script") or ""
        if re.search(r'\(\s*(""|''|"<[^"]*>"|"\.\.\."|"TODO")\s*\)', call):
            empty.append(call.strip()[:60])
            continue
        kept.append(s)
    plan["steps"] = kept
    notes = []
    if dropped:
        notes.append(f'invented and removed: {", ".join(sorted(set(dropped)))}')
    if empty:
        notes.append(f'removed, empty argument proves nothing: {"; ".join(empty)}')
    if notes:
        plan["missing"] = (plan.get("missing") or "") + ("; " if plan.get("missing") else "") + "; ".join(notes)
        plan["confidence"] = min(float(plan.get("confidence") or 0.5), 0.4)
    return plan


# ---------------------------------------------------------------- routes
@brain_bp.route("/api/brain/health", methods=["GET"])
def brain_health():
    ex = _load(TRAINING, [])
    return jsonify(ok=True, model=PLAN_MODEL,
                   lessons=len(ex),
                   good=len([e for e in ex if e.get("verdict") == "good"]),
                   escalations=len(_load(ESCALATIONS, [])))


@brain_bp.route("/api/brain/plan", methods=["POST"])
def brain_plan():
    body = request.get_json(silent=True) or {}
    goal = (body.get("goal") or "").strip()
    catalogue = body.get("catalogue") or {}
    model = (body.get("model") or PLAN_MODEL).strip()        # the router may name a cheaper model
    if not goal:
        return jsonify(error="no goal"), 400
    if not catalogue.get("blocks") and not catalogue.get("actions"):
        return jsonify(error="no catalogue sent: run `macroskill list --json`"), 400

    prompt = (
        f"CATALOGUE\n{json.dumps(catalogue, indent=1)[:12000]}\n\n"
        + (lessons_text() and f"WHAT YOU HAVE LEARNED\n{lessons_text()}\n\n")
        + f"GOAL\n{goal}\n\nAnswer with the JSON object only."
    )
    try:
        from app import pool  # the server's own key pool
        from groq import Groq
    except Exception as exc:                                        # pragma: no cover
        return jsonify(error=f"brain cannot reach the key pool: {exc}"), 503

    try:
        import cost_gate  # noqa: PLC0415
        cost_gate.require("queen-brain", "plan a macro chain with Groq", cost_gate.CHAT_CALL_USD)
    except cost_gate.CostDenied as exc:
        return jsonify(error=str(exc), denied=True), 402
    candidates = pool.candidates(model)
    if not candidates:
        return jsonify(error="every key is cooling down"), 503

    t0, last = time.time(), None
    for key in candidates:
        try:
            r = Groq(api_key=key, max_retries=0).chat.completions.create(
                model=model, temperature=0, max_tokens=2000,
                messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}])
            pool.good(key, model)
            plan = extract_json(r.choices[0].message.content)
            if not plan:
                last = "the model did not answer with JSON"
                continue
            plan = clean_plan(plan, catalogue)
            plan.setdefault("goal", goal)
            plan["model"] = model
            plan["seconds"] = round(time.time() - t0, 2)
            return jsonify(plan)
        except Exception as exc:
            last = str(exc)
            pool.cool(key, model, exc)
    return jsonify(error=f"no key could answer: {last}"), 502


@brain_bp.route("/api/brain/training", methods=["GET"])
def brain_training():
    return jsonify(examples=_load(TRAINING, []))


@brain_bp.route("/api/brain/teach", methods=["POST"])
def brain_teach():
    body = request.get_json(silent=True) or {}
    if not body.get("goal"):
        return jsonify(error="no goal"), 400
    ex = _load(TRAINING, [])
    ex.append({"goal": body.get("goal"), "plan": body.get("plan") or {},
               "verdict": body.get("verdict") or "bad", "note": body.get("note") or "",
               "when": time.strftime("%Y-%m-%d %H:%M")})
    _save(TRAINING, ex)
    return jsonify(ok=True, lessons=len(ex))


@brain_bp.route("/api/brain/escalate", methods=["POST"])
def brain_escalate():
    """Two strikes. Queen admits the limit and asks Claude, then the lesson is written down.

    Marko, 12.11.2026: "He needs to understand correctly that he has his limitations, and when he reaches
    limitations, he is calling with API code to Claude to ask for a solution and to build skills automatically."
    """
    body = request.get_json(silent=True) or {}
    goal = (body.get("goal") or "").strip()
    if not goal:
        return jsonify(error="no goal"), 400
    tried, error = body.get("tried") or "", body.get("error") or ""

    ask = (f"I am Queen, a local assistant on a Mac. I tried this twice and failed, so I am asking you.\n\n"
           f"GOAL\n{goal}\n\nWHAT I TRIED\n{tried}\n\nWHAT WENT WRONG\n{error}\n\n"
           f"Give me: 1) the corrected approach, concretely; 2) the one rule I should remember so I never repeat "
           f"this. Answer as JSON: {{\"solution\": \"...\", \"rule\": \"...\"}}")

    # Marko, 12.11.2026: local Claude Code first; API credits only with his yes (claude_link.py).
    import claude_link
    allow_api = bool(body.get("allow_api"))
    try:
        how = claude_link.route(allow_api)
    except claude_link.NeedConsent as exc:
        return jsonify(ok=False, need_consent=True, message=str(exc)), 409
    usd = None
    if how == "local":
        try:
            got_local = claude_link.ask(ask)
        except Exception as exc:
            return jsonify(error=f"local Claude Code did not answer: {exc}"), 502
        text, model_used, usd = got_local["answer"], "local Claude Code (plan)", 0.0
    else:
        try:
            text, model_used, usd = _anthropic_answer(ask)
        except Exception as exc:
            return jsonify(error=str(exc)), 502
    got = extract_json(text) or {"solution": text, "rule": ""}
    record = {"goal": goal, "tried": tried, "error": error,
              "solution": got.get("solution", ""), "rule": got.get("rule", ""),
              "model": model_used, "via": how, "when": time.strftime("%Y-%m-%d %H:%M"),
              "usd": usd}
    hist = _load(ESCALATIONS, [])
    hist.append(record)
    _save(ESCALATIONS, hist)

    # the rule becomes a lesson the planner reads from now on
    if got.get("rule"):
        ex = _load(TRAINING, [])
        ex.append({"goal": goal, "plan": {}, "verdict": "bad",
                   "note": f'{error} -> {got["rule"]}', "when": time.strftime("%Y-%m-%d %H:%M")})
        _save(TRAINING, ex)
    return jsonify(ok=True, **record)


def _anthropic_answer(prompt):
    """The Anthropic API, only after Marko said yes to API credits. Returns (text, model, usd)."""
    from auto_updater import load_keys                           # the Anthropic key already configured
    keys = (load_keys() or {}).get("anthropic") or []
    if not keys:
        raise RuntimeError("no Anthropic key configured: add one in the Auto-Update panel")
    import anthropic
    msg = anthropic.Anthropic(api_key=keys[0]).messages.create(
        model=os.environ.get("BRAIN_ESCALATION_MODEL", "claude-sonnet-5-5"),
        max_tokens=4000, messages=[{"role": "user", "content": prompt}])
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    try:
        usd = round(msg.usage.input_tokens / 1e6 * 2.0 + msg.usage.output_tokens / 1e6 * 10.0, 6)
    except Exception:
        usd = None
    return text, msg.model, usd


def escalate_text(question):
    """Chat path after Marko's explicit 'with API credits': one answer from the Anthropic API."""
    return _anthropic_answer(question)[0]
