"""One chat per task in Queen's window (12.11.2026).

Marko: "in queue with new task. Open the new chat with the title of the task, please."
A task (a skill run) opens a new chat titled with the task; every step, proposal to the supervisor, decision and result is
written into it, saved like any chat (~/.groq/chats) and pushed live to the open page (event "task_chat").
"""
import json
import secrets
import time

_BROADCAST = {"fn": None}
_CHATS = {"dir": None}


def setup(broadcast_fn, chats_dir):
    _BROADCAST["fn"], _CHATS["dir"] = broadcast_fn, chats_dir


class TaskChat:
    def __init__(self, title):
        self.id = "task_" + time.strftime("%Y%m%d_%H%M%S_") + secrets.token_hex(2)
        self.title = title
        self.messages = []
        self.say(f"Task started: {title}")

    def say(self, text, role="assistant"):
        self.messages.append({"role": role, "content": text})
        self._save()

    def _save(self):
        d = _CHATS["dir"]
        if d:
            d.mkdir(parents=True, exist_ok=True)
            now = time.strftime("%Y-%m-%dT%H:%M:%S%z")
            data = {"id": self.id, "title": self.title, "messages": self.messages, "message_count": len(self.messages),
                    "created_at": now, "updated_at": now}
            (d / f"{self.id}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        if _BROADCAST["fn"]:
            try:
                _BROADCAST["fn"]({"type": "task_chat", "chat": {"id": self.id, "title": self.title, "messages": self.messages}})
            except Exception:
                pass
