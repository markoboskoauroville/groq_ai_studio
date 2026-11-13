"""The news line at the top of Queen's window (13.11.2026).

Marko: "She needs to always summarize where we are ... next to the model name, like a current situation news channel ...
max 4 sentences." and "she needs to say what she's up to, what she's planning to do, and what we did so far."

Marko, 13.11.2026: "after every step, she needs to write a handover, so basically this line is a summary of handovers."
Every step (a task step, a chat answer, a command she ran) is one dated line in ~/.groq/HANDOVER.md (handover()).

POST /api/news {messages}  ->  {text}   at most 4 sentences: now / next / done so far, from the handover.
GET  /api/handover?n=40     ->  {lines} the newest handover lines
The facts come from the chat plus the task chats and the proposals waiting for the supervisor, so the line is true even
while a task runs in the background. One small call to the cheapest model, recorded in the ledger like every call.
"""
import json
import re
import time
from pathlib import Path

from flask import jsonify, request

MODEL = "openai/gpt-oss-20b"
G = Path.home() / ".groq"
SYSTEM = ("You write the news line at the top of Queen's window for Marko. At most 4 short sentences, plain English, no lists, "
          "no markdown, no emojis. Say, in this order: what Queen is doing now, what she will do next, what was done so far. "
          "Use only the facts given; a task waiting for approval is waiting, a failed step is failed. A task whose newest line says "
          "Stopped, rejected, Not started or FAILED has ENDED without doing its work: never call it next or in progress; say it "
          "was stopped and why in a few words. Never invent progress.")


HANDOVER = G / "HANDOVER.md"


def handover(text):
    """One step, one line: what was done, by whom, its outcome. Never raises."""
    try:
        t = time.localtime()
        line = re.sub(r"\s+", " ", str(text)).strip()[:400]
        if not HANDOVER.exists():
            HANDOVER.write_text("# Queen's handover: every step, newest last\n\n", encoding="utf-8")
        with HANDOVER.open("a", encoding="utf-8") as f:
            f.write(f"- {t.tm_mday}.{t.tm_mon}.{t.tm_year} {time.strftime('%H:%M')} · {line}\n")
        from data_sync import mark_dirty   # every step reaches the private data repo within a minute
        mark_dirty()
    except Exception:
        pass


def recent(n=25):
    try:
        return [l[2:] for l in HANDOVER.read_text(encoding="utf-8").splitlines() if l.startswith("- ")][-n:]
    except OSError:
        return []


def _facts():
    lines = []
    try:
        import supervisor  # noqa: PLC0415
        for p in supervisor.pending():
            lines.append(f"WAITING FOR APPROVAL: {p['task']} / {p['step']}: {p['summary']}")
    except Exception:
        pass
    chats = sorted((G / "chats").glob("task_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:4]
    for c in chats:
        if time.time() - c.stat().st_mtime > 6 * 3600:
            continue
        try:
            d = json.loads(c.read_text())
            last = d["messages"][-1]["content"].replace("\n", " ")[:300]
            lines.append(f"TASK {d['title']}: last step: {last}")
        except Exception:
            pass
    return lines


def summarize(messages, pool, record_spend):
    from groq import Groq  # noqa: PLC0415
    talk = []
    for m in messages[-4:]:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            talk.append(f"{'MARKO' if m['role'] == 'user' else 'QUEEN'}: {str(m['content'])[:700]}")
    facts = _facts()
    steps = recent()
    if not talk and not facts and not steps:
        return "Nothing is running. Queen is waiting for Marko's first task."
    prompt = ("HANDOVER (every step, newest last):\n" + ("\n".join(steps) or "none") + "\n\nWAITING NOW:\n"
              + ("\n".join(facts) or "none") + "\n\nLAST CHAT LINES:\n" + "\n".join(talk))
    last = None
    import cost_gate  # noqa: PLC0415
    try:
        cost_gate.require("queen-news", "the Queen news line", cost_gate.CHAT_CALL_USD)
    except cost_gate.CostDenied as exc:
        return f"(the Cost Agent has not allowed the news line: {exc})"
    for key in pool.candidates(MODEL):
        try:
            r = Groq(api_key=key, max_retries=0).chat.completions.create(
                model=MODEL, temperature=0, max_tokens=900, reasoning_effort="low",
                messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}])
            pool.good(key, MODEL)
            u = r.usage
            try:
                record_spend(MODEL, u.prompt_tokens, u.completion_tokens, f"news_{int(time.time() * 1000)}")
            except Exception:
                pass
            text = re.sub(r"\s+", " ", (r.choices[0].message.content or "").replace("*", "")).strip()
            sentences = re.split(r"(?<=[.!?])\s+", text)
            return " ".join(sentences[:4])
        except Exception as exc:
            last = exc
            pool.cool(key, MODEL, exc)
    return f"The news line could not be written: {last}"


def register(app, pool, record_spend):
    @app.post("/api/news")
    def news():
        d = request.get_json(silent=True) or {}
        return jsonify(ok=True, text=summarize(d.get("messages") or [], pool, record_spend))

    @app.get("/api/handover")
    def handover_lines():
        return jsonify(ok=True, lines=recent(int(request.args.get("n", 40))))
    return app
