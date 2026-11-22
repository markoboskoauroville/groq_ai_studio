"""tell-marko-on-screen (22.11.2026): Queen's hand for Macro Recorder's text blob: `macro blob "<text>" --kind ...`, local, $0.
Marko, 22.11.2026: "the text blob ... if something needs to be said to me while I'm working on computer and you are working in the
background." Skill file: queen_skills/tell-marko-on-screen.md."""
import os
import re
import subprocess

MACRO = os.path.expanduser("~/.local/bin/macro")
_LEAD = re.compile(
    r"^(?:please\s+)?(?:(?:tell|show|notify|inform)\s+marko(?:\s+(?:on|in)\s+(?:the\s+)?screen)?(?:\s+with\s+a\s+blob)?(?:\s+that)?"
    r"|(?:put|show|pop|send)\s+(?:up\s+)?a\s+blob(?:\s+(?:on|to)\s+(?:the\s+)?(?:screen|marko))?(?:\s+(?:saying|that says|with))?"
    r"|blob)\s*[:,]?\s+(?P<msg>.+)$", re.I | re.S)


def parse(text: str):
    """(message, kind) for a sentence that asks for a blob, else None."""
    t = " ".join((text or "").split())
    if not t or len(t) > 400:
        return None
    m = _LEAD.match(t)
    if not m:
        return None
    msg = m.group("msg").strip().strip('"').strip()
    if not msg:
        return None
    msg = msg[0].upper() + msg[1:]
    if msg[-1] not in ".!?":
        msg += "."
    kind = "ask" if re.search(r"\b(i need you|needs? you|please come|waiting for you)\b", msg, re.I) \
        else "done" if re.search(r"\b(done|finished|ready|complete[d]?|you can use the computer)\b", msg, re.I) else "info"
    return msg, kind


def chat_tell_command(text: str):
    p = parse(text)
    if not p:
        return None
    msg, kind = p
    try:
        r = subprocess.run([MACRO, "blob", msg, "--kind", kind], capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL)
    except Exception as e:
        return f"I could not show the blob ({type(e).__name__}). Is Macro Recorder (Mantra) running?"
    if r.returncode != 0:
        return "The blob was not shown: " + ((r.stdout + r.stderr).strip() or f"macro blob exit {r.returncode}")
    return f'Told Marko on screen ({kind}): "{msg}"'
