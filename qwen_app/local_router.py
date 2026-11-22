"""The ONE local router (audit 22.11.2026): every entry point asks it before any model is called.

Entry points: the CAPI window (/api/capi/send), /api/capi/ask, /api/capi/turn, /api/chat (the `queen "<q>"` CLI) and
/api/internal/local_command. Order:
  1. pause / resume / pause status (Queen's own chats, $0)
  2. the deterministic Python skills (queen_python_skills.dispatch: list skills, current folder, ABLETON:, GEMINI IMAGE:,
     webcam recorder, lan scan)
  3. only when `hands` is true (Queen is on for that chat): the Groq-free chat commands of the old server (v3-v30
     `_local_command_answer` without the commands that needed a Groq model: web photo, screen look, describe, posters).
A command that fails says it failed, with the reason; the model is never asked to cover for it (lesson of 12.11.2026).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

try:
    from queen_python_skills import dispatch as _skills_dispatch
except ImportError:  # imported as a package (tests)
    from qwen_app.queen_python_skills import dispatch as _skills_dispatch


@dataclass(frozen=True)
class Local:
    skill_id: str
    answer: str


# (module, function, mac_only): the order of the old server, Groq-bound ones left out
HANDS = (
    ("pair_chat", "chat_pair_command", False),
    ("system_volume", "chat_volume_command", True),
    ("system_files", "chat_move_command", True),
    ("gphotos_album", "chat_gphotos_command", True),
    ("ops_hands", "chat_ops_command", False),
    ("router_mode", "chat_router_command", False),
    ("ndi_monitor", "chat_ndi_command", True),
    ("second_take", "chat_second_take_command", True),
    ("sony_camera", "chat_sony_command", True),
    ("phone_say", "chat_phone_say_command", True),
    ("system_settings", "chat_settings_command", True),
    ("whatsapp_desktop", "chat_whatsapp_desktop_command", True),
    ("whatsapp_draft", "chat_whatsapp_draft_command", True),
    ("whatsapp_ax", "chat_whatsapp_ax_command", True),
    ("whatsapp_machine", "chat_whatsapp_machine_command", False),
    ("ax_read", "chat_ax_command", True),
    ("affinity_bridge", "chat_app_command", False),
    ("rename_skill", "chat_rename_command", False),
    ("repo_reader", "chat_repo_command", False),
    ("claude_link", "chat_claude_command", False),
)
# Chat commands of the old server that needed a Groq model; off since v31 (Groq-free), listed, not loaded.
GROQ_BOUND_HANDS = ("web_photo_skill.chat_web_photo_command", "screen_look.chat_screen_command",
                    "describe_skill.chat_describe_command", "poster_skill.chat_gemini_command",
                    "poster_skill.chat_like_command", "poster_skill.chat_poster_command")


FAILED_HANDS: dict[str, str] = {}


def _pause_answer(text: str):
    try:
        import pause_state
    except ImportError:
        return None, False
    return pause_state.chat_command(text), pause_state.is_paused()


def route(text: str, context: dict | None = None, hands: bool = False) -> Local | None:
    """-> Local(skill_id, answer) when a local command answers, else None (the caller may then ask a model)."""
    text = (text or "").strip()
    if not text:
        return None
    if hands:                              # Queen's own chats: PAUSE stops every hand (a QUEEN: OFF chat is not hers)
        pause_answer, paused = _pause_answer(text)
        if pause_answer:
            return Local("pause", pause_answer)
        if paused:
            return Local("pause", "Queen is paused: no hand starts until you say resume.")
    try:
        result = _skills_dispatch(text, context or {})
    except Exception as exc:  # noqa: BLE001
        return Local("python-skill", f"The skill failed, nothing was done: {type(exc).__name__}: {exc}")
    if result is not None:
        return Local(result.skill_id, result.answer)
    if not hands:
        return None
    for module, func, mac_only in HANDS:
        if mac_only and sys.platform != "darwin":
            continue
        try:
            fn = getattr(__import__(module), func)
        except Exception as exc:  # noqa: BLE001  a broken module is skipped, logged and shown in `queen status`
            if module not in FAILED_HANDS:
                FAILED_HANDS[module] = f"{type(exc).__name__}: {exc}"
                print(f"[local_router] {module}.{func} not loaded: {FAILED_HANDS[module]}", flush=True)
            continue
        try:
            answer = fn(text)
        except Exception as exc:  # noqa: BLE001
            return Local(module, f"The skill failed, nothing was done: {type(exc).__name__}: {exc}")
        if answer:
            return Local(module, str(answer))
    return None
