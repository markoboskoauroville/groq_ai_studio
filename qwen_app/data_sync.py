"""Queen's data in a private GitHub repository, mirrored from this Mac (13.11.2026).

Marko: "you need to create a private repository. Grok Studio data in GitHub and all the chat history, all takeovers, all
lessons, all skills need to live there privately. Only API codes are not living there, but all the data from the chats is
there" and "it is synchronized with my local storage, so deleting one chat on my local storage deletes also remotely".

The repository: markoboskoauroville/groq_ai_studio_data (PRIVATE), clone ~/Developer/groq_ai_studio_data.
What goes in (a whitelist, nothing else): ~/.groq/chats, approvals, HANDOVER.md, queen_skills, skill_cache, the ledgers and
the brain's training; from the app repo TAKEOVER, LESSONS, momentaryupdates, PROFILE and skills/.
The local side is the truth: a mirror (rsync --delete), so a chat deleted here is deleted there on the next sync.
Every API key is replaced by [KEY REMOVED] in the copy (one chat had a pasted gsk_ key), and a last scan refuses the push
if anything key-shaped is still there. Keys stay in ~/.groq (keys.txt, .env, api_token, auto_update_keys.json, key_state.json).

    mark_dirty()       called after a chat is saved or deleted and after every task step; a thread syncs within 60 s
    sync_now()         one sync: mirror, redact, scan, commit, push; returns what it did
    GET  /api/data-sync          the last result
    POST /api/data-sync          sync now
"""
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

from flask import jsonify

G = Path.home() / ".groq"
APP_REPO = Path.home() / "Developer" / "groq_ai_studio"
DEST = Path.home() / "Developer" / "groq_ai_studio_data"
SLUG = "markoboskoauroville/groq_ai_studio_data"
DIRS = ["chats", "approvals", "queen_skills", "skill_cache"]
FILES = ["HANDOVER.md", "spend_ledger.json", "auto_update_ledger.json", "brain_training.json", "brain_escalations.json"]
APP_FILES = ["TAKEOVER.md", "LESSONS.md", "momentaryupdates.md", "PROFILE.md"]
KEY = re.compile(r"(gsk_[A-Za-z0-9]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,}|gh[pousr]_[A-Za-z0-9]{30,}|"
                 r"github_pat_[A-Za-z0-9_]{30,}|xox[abp]-[A-Za-z0-9-]{20,}|AC[0-9a-f]{32})")
_STATE = {"dirty": True, "last": None, "lock": threading.Lock(), "thread": None}


def _run(cmd, cwd=None):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=300)
    return p.returncode, p.stdout + p.stderr


def ensure_repo():
    if (DEST / ".git").is_dir():
        return "exists"
    code, _ = _run(["gh", "repo", "view", SLUG, "--json", "visibility", "-q", ".visibility"])
    if code != 0:
        code, out = _run(["gh", "repo", "create", SLUG, "--private", "--disable-wiki", "--disable-issues"])
        if code:
            raise RuntimeError(f"gh repo create failed: {out[-300:]}")
    code, out = _run(["gh", "repo", "clone", SLUG, str(DEST)])
    if code:
        raise RuntimeError(f"clone failed: {out[-300:]}")
    (DEST / "TAKEOVER.md").write_text(
        "# TAKEOVER: groq_ai_studio_data (private)\n\nQueen's data, mirrored from Marko's Mac by "
        "groq_ai_studio/qwen_app/data_sync.py: chats, approvals, handover, skills, ledgers, and copies of the app's "
        "TAKEOVER, LESSONS and requests. The Mac is the truth: a chat deleted there is deleted here on the next sync. "
        "API keys never live here (replaced by [KEY REMOVED]). Do not edit by hand: the next sync overwrites it.\n",
        encoding="utf-8")
    return "created"


def _redact_tree(root):
    n = 0
    for p in root.rglob("*"):
        if p.is_file() and p.suffix in (".json", ".md", ".txt"):
            t = p.read_text(encoding="utf-8", errors="replace")
            t2, k = KEY.subn("[KEY REMOVED]", t)
            if k:
                p.write_text(t2, encoding="utf-8")
                n += k
    return n


def sync_now():
    with _STATE["lock"]:
        _STATE["dirty"] = False
        how = ensure_repo()
        _run(["git", "pull", "-q", "--rebase", "origin", "main"], cwd=DEST)
        data = DEST / "data"
        data.mkdir(exist_ok=True)
        for d in DIRS:
            if (G / d).is_dir():
                _run(["rsync", "-a", "--delete", f"{G / d}/", f"{data / d}/"])
        for f in FILES:
            if (G / f).is_file():
                shutil.copy2(G / f, data / f)
            elif (data / f).exists():
                (data / f).unlink()
        app = DEST / "app"
        app.mkdir(exist_ok=True)
        for f in APP_FILES:
            if (APP_REPO / f).is_file():
                shutil.copy2(APP_REPO / f, app / f)
        if (APP_REPO / "skills").is_dir():
            _run(["rsync", "-a", "--delete", f"{APP_REPO / 'skills'}/", f"{app / 'skills'}/"])
        redacted = _redact_tree(DEST / "data") + _redact_tree(app)
        # last check before the push: 0 = found, 1 = clean, more = the check itself failed (both stop the push)
        code, left = _run(["git", "grep", "--untracked", "-I", "-l", "-E", "-e", KEY.pattern], cwd=DEST)
        if code != 1:
            res = {"ok": False, "why": (f"key-shaped text left in {left.split()[:5]}" if code == 0 else
                                        f"the key check failed: {left[-200:]}") + "; nothing pushed"}
        else:
            _run(["git", "add", "-A"], cwd=DEST)
            _, st = _run(["git", "status", "--porcelain"], cwd=DEST)
            if not st.strip():
                res = {"ok": True, "changed": 0}
            else:
                n = len(st.strip().splitlines())
                _run(["git", "commit", "-q", "-m", f"Queen's data: {n} files ({time.strftime('%d.%m.%Y %H:%M')})"], cwd=DEST)
                code, out = _run(["git", "push", "-q", "origin", "HEAD:main"], cwd=DEST)
                res = {"ok": code == 0, "changed": n, "push": out.strip()[-200:] if code else "pushed"}
        res.update(repo=how, redacted=redacted, at=time.strftime("%H:%M:%S"))
        _STATE["last"] = res
        print(f"[data-sync] {res}", flush=True)
        return res


def mark_dirty():
    _STATE["dirty"] = True


def _loop():
    while True:
        time.sleep(60)
        if _STATE["dirty"]:
            try:
                sync_now()
            except Exception as exc:
                _STATE["last"] = {"ok": False, "why": f"{type(exc).__name__}: {exc}", "at": time.strftime("%H:%M:%S")}


def register(app):
    if not _STATE["thread"]:
        _STATE["thread"] = threading.Thread(target=_loop, daemon=True)
        _STATE["thread"].start()

    @app.get("/api/data-sync")
    def data_sync_state():
        return jsonify(ok=True, last=_STATE["last"], dirty=_STATE["dirty"], repo=SLUG)

    @app.post("/api/data-sync")
    def data_sync_run():
        try:
            return jsonify(**sync_now())
        except Exception as exc:
            return jsonify(ok=False, why=f"{type(exc).__name__}: {exc}"), 500
    return app
