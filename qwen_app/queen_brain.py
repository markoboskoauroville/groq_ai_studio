"""Queen's brain since v32 (audit 22.11.2026, decision of the Fable master session): the LOCAL Claude Code on the plan.

`queen "<q>"` and POST /api/chat come here. Order, every turn:
  1. local_router.route(...) with hands: pause, Python skills, the Groq-free chat commands. $0, no model.
  2. the local Claude Code (`claude -p`, claude.ai plan, $0) with her skills as system prompt.
  3. Claude Code not reachable: the manifest's sentence, and she waits. Never a paid provider from here
     (MANTRA_MANIFEST modules/queen-local-claude-first.md).

The skills prompt: queen_skills/ is about 140 KB (66 files), too big for every turn. Each turn gets her working rules
(how-queen-works.md), a one-line catalogue of every skill, and the full text of at most MAX_BODIES skills whose name
matches the question. Marko can change the brain (Groq, a CAPI provider) by deciding so; this module is the one place.
"""
from __future__ import annotations

import re
from pathlib import Path

import claude_link
import local_router

REPO_SKILLS = Path(__file__).resolve().parent.parent / "queen_skills"
INSTALLED_SKILLS = Path.home() / ".queen" / "queen_skills"
MAX_BODIES = 3
MAX_BODY_CHARS = 8000
MODEL = "sonnet"
HISTORY = 12
BRAIN = "local Claude Code (claude.ai plan)"


def skills_dir() -> Path:
    if (REPO_SKILLS / "how-queen-works.md").is_file() and (Path(__file__).resolve().parent.parent / ".git").exists():
        return REPO_SKILLS
    return INSTALLED_SKILLS if INSTALLED_SKILLS.is_dir() else REPO_SKILLS


def _first_line(text: str) -> str:
    for line in text.splitlines():
        s = line.strip().lstrip("#").strip()
        if s:
            return s[:160]
    return ""


def skills() -> dict[str, str]:
    d = skills_dir()
    return {f.stem: f.read_text(encoding="utf-8", errors="replace") for f in sorted(d.glob("*.md"))}


def catalogue(all_skills: dict[str, str] | None = None) -> str:
    all_skills = skills() if all_skills is None else all_skills
    return "\n".join(f"- {name}: {_first_line(body)}" for name, body in all_skills.items())


def matching(question: str, all_skills: dict[str, str]) -> list[str]:
    """Skills whose every name word (3+ letters) is in the question, best (most words) first."""
    q = (question or "").lower()
    words_q = set(re.findall(r"[a-z0-9]+", q))
    scored = []
    for name in all_skills:
        if name == "how-queen-works":
            continue
        words = [w for w in name.split("-") if len(w) >= 3]
        if words and all(w in words_q or w in q for w in words):
            scored.append((len(words), name))
    return [n for _, n in sorted(scored, reverse=True)[:MAX_BODIES]]


def system_prompt(question: str) -> tuple[str, dict]:
    all_skills = skills()
    picked = matching(question, all_skills)
    parts = [
        "You are QUEEN, Marko's local assistant on his Mac. You answer through the local Claude Code on his plan. "
        "Her chat commands that match locally were already tried before you were asked; you get what they did not answer. "
        "Answer short and plainly. Never claim an action happened unless you did it and read it back.",
        "## Her working rules (how-queen-works.md)\n" + all_skills.get("how-queen-works", ""),
        "## Her skills (one line each; the full text of the matching ones follows)\n" + catalogue(all_skills),
    ]
    for name in picked:
        parts.append(f"## Skill {name}\n" + all_skills[name][:MAX_BODY_CHARS])
    text = "\n\n".join(parts)
    return text, {"skills_total": len(all_skills), "skills_full": picked, "prompt_chars": len(text),
                  "all_skills_chars": sum(len(b) for b in all_skills.values())}


def _transcript(messages: list[dict]) -> tuple[str, str]:
    msgs = [m for m in messages if isinstance(m, dict) and str(m.get("content") or "").strip()]
    if not msgs:
        return "", ""
    last = str(msgs[-1].get("content"))
    earlier = msgs[:-1][-HISTORY:]
    if not earlier:
        return last, last
    lines = [f"{'Marko' if m.get('role') == 'user' else 'Queen'}: {m.get('content')}" for m in earlier]
    return last, "Earlier in this chat:\n" + "\n".join(lines) + f"\n\nNow Marko says:\n{last}"


def answer(messages: list[dict], context: dict | None = None) -> dict:
    """-> {text, via, model, cost, local_skill?, need_consent?, prompt?}. Never raises for an ordinary failure."""
    last, prompt = _transcript(messages)
    if not last:
        return {"text": "", "error": "empty message", "via": "none", "model": "", "cost": 0.0}
    local = local_router.route(last, context or {}, hands=True)
    if local:
        return {"text": local.answer, "via": "local skill", "local_skill": local.skill_id, "model": "python", "cost": 0.0}
    if not claude_link.status()["reachable"]:
        return {"text": claude_link.CONSENT_TEXT, "need_consent": True, "via": "none", "model": "", "cost": 0.0}
    system, info = system_prompt(last)
    try:
        r = claude_link.ask(prompt, model=MODEL, system=system)
    except claude_link.NeedConsent:
        return {"text": claude_link.CONSENT_TEXT, "need_consent": True, "via": "none", "model": "", "cost": 0.0}
    except Exception as exc:  # noqa: BLE001
        return {"text": "", "error": f"The local Claude Code did not answer: {exc}", "via": BRAIN, "model": MODEL,
                "cost": 0.0, "prompt": info}
    return {"text": r.get("answer", ""), "via": BRAIN, "model": f"claude-code {MODEL}", "cost": 0.0, "prompt": info}
