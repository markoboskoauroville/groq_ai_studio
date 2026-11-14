"""WhatsApp, supervised: Queen plans, Claude assesses, then the hands act (14.11.2026).

Marko, 14.11.2026: "I need to have a chat interface to chat with Queen about what to do with WhatsApp ... Queen is in this
WhatsApp mode, specialized to remotely control my Firefox browser and do whatever I say ... supervise everything with Claude
in the virtual machine. Claude is watching what Queen is doing and then correcting. Before she does anything, Claude is
assessing: 'Is this the correct action?' and then corrects it. It's teaching the skill of dealing with WhatsApp to Queen."

    POST /api/whatsapp/supervised {text, conv}   (also {pick: "<chat>"} for a chat chosen from the last choices)
    -> {ok, reply, plan, assessment: {verdict: ok|corrected, why, lesson}, action, chat, draft, choices[], shot: true,
        queen_plan, understood}

1. Queen plans ONE action: her rules (whatsapp_remote.plan_by_rules, plus `read` here), else her own Groq model with the
   WhatsApp skills (never Claude: Claude is the assessor, not the planner).
2. The local Claude Code (claude_link, the plan, no API credits) gets the words, the skills and her plan and answers
   {verdict, plan, why, lesson}. Not reachable -> nothing runs, the reply says so.
3. The final plan runs through whatsapp_remote.execute (wa_remote over BiDi). Drafts stay UNSENT; only /api/whatsapp/send
   sends (the app's SEND button, the exact text).
4. corrected -> the lesson (dated, one bullet) is appended to queen_skills/whatsapp-lessons.md in the installed skills
   AND in the repo clone, committed and pushed (only that file; a failed push stays committed locally and is logged).
The phone reaches this through the WhatsApp door on the VM (WHATSAPP_REMOTE_VIEWER/vm/wa_door.py, 100.102.86.30:8879).
"""
import datetime
import json
import re
import subprocess
import threading
import time
from pathlib import Path

from flask import jsonify, request

import whatsapp_remote as WR

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent / "queen_skills"                       # ~/.groq/queen_skills when installed
REPO = Path.home() / "Developer" / "groq_ai_studio"         # the clone the lesson is committed in
LESSONS = "whatsapp-lessons.md"
SKILL_FILES = ("whatsapp-supervised.md", "whatsapp-remote.md", LESSONS)
MODEL = "qwen/qwen3.6-27b"
CLAUDE_MODEL = "sonnet"
CLAUDE_TIMEOUT = 90
ACTIONS = ("shot", "open", "scroll", "draft", "photo_draft", "chats", "read")
LOG = Path.home() / ".groq" / "whatsapp_supervised.log"
_CTX = {"pool": None, "spend": None}
CONVS = {}                                                   # conv -> {"turns": [...], "chat": str, "choices": [...]}
LOCK = threading.Lock()
GIT_LOCK = threading.Lock()

READ = re.compile(r"\b(read|reads|pročitaj|procitaj)\b(?:\s+me)?(?:\s+the)?(?:\s+(?:last|latest|newest|zadnj\w*))?\s*(\d+)?\s*(?:new\s+)?(?:messages?|poruk\w*)?"
                  r"(?:\s+(?:from|in|of|with|od|u|sa|s)\s+(.+?))?\s*$", re.I)
LAST_N = re.compile(r"\b(?:last|latest|zadnj\w*)\s+(\d+)\s+(?:messages?|poruk\w*)\b", re.I)


def _log(**kw):
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a") as f:
            f.write(json.dumps(dict(at=time.strftime("%Y-%m-%d %H:%M:%S"), **kw), ensure_ascii=False) + "\n")
    except Exception:
        pass


def _skills():
    out = []
    for n in SKILL_FILES:
        p = SKILLS / n
        if p.exists():
            out.append(f"## {n}\n" + p.read_text(encoding="utf-8")[:6000])
    return "\n\n".join(out)


# ------------------------------------------------------------------ 1. Queen plans
LESSON_LINE = re.compile(r'\(Marko: "(.*?)"; Queen .*? -> Claude (\{.*\})\)\s*$')


def _norm(t):
    return re.sub(r"\s+", " ", t.strip().lower().strip(".!?"))


def plan_by_lessons(text):
    """What Claude taught her: the same words are planned the way Claude corrected them (newest lesson wins)."""
    p = SKILLS / LESSONS
    if not p.exists():
        return None
    found = None
    for line in p.read_text(encoding="utf-8").splitlines():
        m = LESSON_LINE.search(line)
        if m and _norm(m.group(1)) == _norm(text[:120]):
            try:
                found = json.loads(m.group(2))
            except Exception:
                pass
    return found if found and found.get("action") in ACTIONS and found.get("action") not in ("draft", "photo_draft") else None


def plan_by_queen_rules(text):
    t = text.strip()
    m = READ.match(t) if re.match(r"^(?:please\s+)?(read|pročitaj|procitaj)\b", t, re.I) else None
    if m:
        p = {"action": "read", "n": int(m.group(2) or 10)}
        if m.group(3) and not re.fullmatch(r"(this|the|that)?\s*(chat|conversation|razgovor)", m.group(3).strip(), re.I):
            p["chat"] = m.group(3).strip().strip('"“”')
        return p
    m = LAST_N.search(t)
    if m and re.search(r"\b(show|read|what|pokaži|pročitaj)\b", t, re.I) and re.search(r"\b(this|the|open|current)\s+chat\b|\bhere\b", t, re.I) is not None:
        return {"action": "read", "n": int(m.group(1))}
    return WR.plan_by_rules(t)


def plan_by_queen_model(text, conv):
    """Her own Groq model with the WhatsApp skills: one json plan. Returns (plan or None, why)."""
    pool = _CTX["pool"]
    if pool is None:
        return None, "her model is not wired in (no key pool)"
    from groq import Groq  # noqa: PLC0415
    import cost_gate  # noqa: PLC0415
    try:
        cost_gate.require("queen-whatsapp", "plan one WhatsApp action", cost_gate.CHAT_CALL_USD)
    except Exception as exc:
        return None, f"the Cost Agent did not allow her model: {exc}"
    system = ("You are Queen in WhatsApp mode: you control WhatsApp Web in Marko's Firefox on the VM through one action.\n"
              + _skills() + "\n\nAnswer with ONE json object and nothing else: {\"action\": one of " + "|".join(ACTIONS)
              + ", \"chat\": \"...\", \"text\": \"...\", \"dir\": \"up|down\", \"n\": 10}. Keep his words verbatim in text. "
              "Never plan a send.")
    user = (f"Open chat now: {conv.get('chat') or 'none'}\nRecent turns: {json.dumps(conv.get('turns', [])[-4:], ensure_ascii=False)}\n"
            f"Marko says: {json.dumps(text, ensure_ascii=False)}")
    last = None
    for key in pool.candidates(MODEL) or []:
        try:
            r = Groq(api_key=key, max_retries=0).chat.completions.create(
                model=MODEL, temperature=0, max_tokens=400, reasoning_effort="none",
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
            pool.good(key, MODEL)
            try:
                u = r.usage
                _CTX["spend"](MODEL, u.prompt_tokens, u.completion_tokens, f"wa_sup_{int(time.time() * 1000)}")
            except Exception:
                pass
            a = re.sub(r"<think>.*?</think>", "", r.choices[0].message.content or "", flags=re.S)
            m = re.search(r"\{.*\}", a, re.S)
            p = json.loads(m.group(0)) if m else {}
            if p.get("action") not in ACTIONS:
                return None, "her model gave no valid action: " + a[:120]
            return p, ""
        except Exception as exc:
            last = exc
            pool.cool(key, MODEL, exc)
    return None, f"no Groq key answered: {last}"


# ------------------------------------------------------------------ 2. Claude assesses
def assess(text, queen_plan, conv):
    import claude_link  # noqa: PLC0415
    prompt = (
        "You SUPERVISE Queen, who controls WhatsApp Web in Marko's Firefox (VM) by ONE action per request. You are the teacher: "
        "check her plan BEFORE it runs. Her skills:\n\n" + _skills() +
        "\n\n---\nActions: shot (picture of the screen, chat list), open {chat}, scroll {dir up|down}, draft {chat, text} "
        "(typed UNSENT into the box), photo_draft {chat, text}, chats (list the chat titles), read {chat?, n} (last n messages "
        "of the open chat, or of chat). There is NO send action: sending is never planned. A draft's text is Marko's words "
        "verbatim (his language), without the instruction words around them. chat is the name as he said it; the hands "
        "search it and offer choices when several match.\n"
        f"Chat open now: {conv.get('chat') or 'unknown'}\n"
        f"Earlier turns: {json.dumps(conv.get('turns', [])[-4:], ensure_ascii=False)}\n"
        f"Marko said: {json.dumps(text, ensure_ascii=False)}\n"
        f"Queen's plan: {json.dumps(queen_plan, ensure_ascii=False) if queen_plan else 'NONE (she could not plan it)'}\n\n"
        "Answer with ONE json object and nothing else: {\"verdict\": \"ok\" or \"corrected\", \"plan\": {the plan to run, "
        "the same as hers when ok}, \"why\": \"one sentence\", \"lesson\": \"when corrected: one rule Queen should learn, "
        "general, one sentence; else empty\"}. Correct only real mistakes (wrong action, wrong chat, text not verbatim, "
        "a missing plan); never add a send.")
    a = claude_link.ask(prompt, model=CLAUDE_MODEL, timeout=CLAUDE_TIMEOUT)["answer"]
    m = re.search(r"\{.*\}", a, re.S)
    d = json.loads(m.group(0)) if m else {}
    if d.get("verdict") not in ("ok", "corrected") or not isinstance(d.get("plan"), dict):
        raise ValueError("Claude's assessment was not the json asked for: " + a[:160])
    if d["verdict"] == "ok" and queen_plan:
        d["plan"] = queen_plan
    if d["plan"].get("action") not in ACTIONS:
        raise ValueError("Claude's plan has no valid action: " + json.dumps(d["plan"])[:160])
    return d


# ------------------------------------------------------------------ 4. the lesson
def add_lesson(lesson, text, queen_plan, final_plan):
    day = datetime.date.today()
    line = (f"- {day.day}.{day.month}.{day.year}: {lesson.strip()} (Marko: \"{text.strip()[:120]}\"; Queen "
            f"{json.dumps(queen_plan, ensure_ascii=False) if queen_plan else 'had no plan'} -> Claude "
            f"{json.dumps(final_plan, ensure_ascii=False)})\n")
    head = ("# whatsapp-lessons\n\nWhat Claude corrected in Queen's WhatsApp plans (POST /api/whatsapp/supervised). Read "
            "before planning: the same request is planned the corrected way.\n\n")
    targets = [SKILLS / LESSONS]
    if (REPO / ".git").exists() and (REPO / "queen_skills").resolve() != SKILLS.resolve():
        targets.append(REPO / "queen_skills" / LESSONS)
    key = (_norm(text[:120]), json.dumps(final_plan, sort_keys=True))
    for l in (SKILLS / LESSONS).read_text(encoding="utf-8").splitlines() if (SKILLS / LESSONS).exists() else []:
        m = LESSON_LINE.search(l)
        try:
            if m and (_norm(m.group(1)), json.dumps(json.loads(m.group(2)), sort_keys=True)) == key:
                return None                        # already learned (two phones asked the same at once)
        except Exception:
            pass
    for p in targets:
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.write_text(head, encoding="utf-8")
        with p.open("a", encoding="utf-8") as f:
            f.write(line)
    threading.Thread(target=_push_lesson, args=(lesson,), daemon=True).start()
    return line


def _git(*a, timeout=60):
    return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True, timeout=timeout)


def _push_lesson(lesson):
    if not (REPO / ".git").exists():
        return
    with GIT_LOCK:
        try:
            f = f"queen_skills/{LESSONS}"
            _git("add", f)
            r = _git("commit", "-m", f"Queen WhatsApp lesson (Claude corrected her plan): {lesson[:60]}", "--", f)
            if r.returncode:
                _log(event="lesson-commit-failed", out=(r.stdout + r.stderr)[-300:])
                return
            r = _git("pull", "--rebase", "--autostash", timeout=120)
            if r.returncode:
                _git("rebase", "--abort")
                _log(event="lesson-pull-failed", out=(r.stdout + r.stderr)[-300:])
                return
            r = _git("push", "origin", "HEAD:main", timeout=120)
            _log(event="lesson-pushed" if not r.returncode else "lesson-push-failed", out=(r.stdout + r.stderr)[-300:])
        except Exception as exc:
            _log(event="lesson-git-error", error=str(exc))


# ------------------------------------------------------------------ 3. doing it
def run_plan(plan):
    a = plan["action"]
    if a == "read":
        args = ["read"] + ([plan["chat"]] if plan.get("chat") else []) + [str(int(plan.get("n") or 10))]
        r = WR._wa(*args)
        return {"ok": bool(r.get("ok")), "say": r.get("text") or r.get("error") or "", "chat": r.get("chat", ""),
                "messages": r.get("messages", []), "action": a, "choices": []}
    res = WR.execute(dict(plan))
    res.pop("image_b64", None)
    return res


def _reply(verdict, why, res, how):
    who = ("Claude approved Queen's plan." if verdict == "ok" else f"Claude corrected Queen: {why}")
    return f"{res.get('say') or ('Done.' if res.get('ok') else 'It did not work.')}\n({who} Planned by {how}.)"


def supervised(text, conv_id, pick=""):
    conv = CONVS.setdefault(conv_id or "default", {"turns": [], "chat": "", "choices": []})
    if not pick and text and any(text.strip().lower() == c.lower() for c in conv.get("choices") or []):
        pick = text.strip()
    if pick:
        plan = WR.PENDING.get("plan")
        if plan and time.time() - WR.PENDING["at"] < 600:
            plan = dict(plan, chat=pick)
            WR.PENDING.update(plan=None)
            res = run_plan(plan)
            conv.update(choices=res.get("choices") or [], chat=res.get("chat") or conv["chat"])
            return {"ok": bool(res.get("ok")), "reply": res.get("say", ""), "plan": plan,
                    "assessment": {"verdict": "ok", "why": "Marko picked the chat himself.", "lesson": ""},
                    "action": plan["action"], "chat": res.get("chat", ""), "draft": res.get("draft"),
                    "choices": res.get("choices") or [], "shot": True, "queen_plan": plan, "understood": "his pick"}
    queen_plan, how = plan_by_lessons(text), "her lessons"
    if not queen_plan:
        queen_plan, how = plan_by_queen_rules(text), "her rules"
    if not queen_plan:
        queen_plan, why_none = plan_by_queen_model(text, conv)
        how = "her model" if queen_plan else f"nobody ({why_none})"
    try:
        a = assess(text, queen_plan, conv)
    except Exception as exc:
        msg = str(exc)
        if type(exc).__name__ == "NeedConsent":
            msg = "I cannot reach the local Claude Code to check my plan, so I did nothing. Do you want to use API credits?"
        elif isinstance(exc, subprocess.TimeoutExpired):
            msg = f"Claude did not answer within {CLAUDE_TIMEOUT} s, so I did nothing (my plan was not checked)."
        else:
            msg = "Claude could not check my plan, so I did nothing: " + msg[:200]
        _log(event="no-assessment", text=text, queen_plan=queen_plan, error=msg)
        return {"ok": False, "reply": msg, "plan": queen_plan,
                "assessment": {"verdict": "unchecked", "why": msg, "lesson": ""}, "action": (queen_plan or {}).get("action", ""),
                "chat": conv.get("chat", ""), "draft": None, "choices": [], "shot": False, "queen_plan": queen_plan, "understood": how}
    plan = a["plan"]
    if a["verdict"] == "corrected" and (a.get("lesson") or "").strip():
        try:
            add_lesson(a["lesson"], text, queen_plan, plan)
        except Exception as exc:
            _log(event="lesson-write-failed", error=str(exc))
    res = run_plan(plan)
    if res.get("chat"):
        conv["chat"] = res["chat"]
    conv["choices"] = res.get("choices") or []
    conv["turns"] = (conv["turns"] + [{"marko": text, "plan": plan, "result": (res.get("say") or "")[:200]}])[-8:]
    _log(event="supervised", text=text, queen_plan=queen_plan, verdict=a["verdict"], plan=plan, why=a.get("why"),
         lesson=a.get("lesson"), ok=res.get("ok"))
    out = {"ok": bool(res.get("ok")), "reply": _reply(a["verdict"], a.get("why", ""), res, how), "plan": plan,
           "assessment": {"verdict": a["verdict"], "why": a.get("why", ""), "lesson": a.get("lesson", "") if a["verdict"] == "corrected" else ""},
           "action": plan["action"], "chat": res.get("chat") or conv.get("chat", ""), "draft": res.get("draft"),
           "choices": res.get("choices") or [], "shot": True, "queen_plan": queen_plan, "understood": how}
    if res.get("messages"):
        out["messages"] = res["messages"]
    return out


def register(app, pool=None, record_spend=None):
    _CTX["pool"], _CTX["spend"] = pool, record_spend

    @app.route("/api/whatsapp/supervised", methods=["POST"])
    def whatsapp_supervised():
        d = request.get_json(force=True, silent=True) or {}
        text, pick = (d.get("text") or "").strip(), (d.get("pick") or "").strip()
        if not text and not pick:
            return jsonify({"ok": False, "reply": "Say what to do in WhatsApp.", "shot": False}), 400
        with LOCK, WR.LOCK:
            try:
                return jsonify(supervised(text, str(d.get("conv") or "default"), pick))
            except Exception as exc:
                _log(event="error", text=text, error=f"{type(exc).__name__}: {exc}")
                return jsonify({"ok": False, "reply": f"{type(exc).__name__}: {str(exc)[:300]}", "plan": None,
                                "assessment": {"verdict": "unchecked", "why": "", "lesson": ""}, "action": "",
                                "chat": "", "draft": None, "choices": [], "shot": False})
