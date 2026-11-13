"""Supervised steps: Queen proposes, Claude Code approves, then she acts (12.11.2026).

Marko: "please teach Queen how to do this. Now you need to supervise her before each move. She's going to ask approval from
you, so she doesn't mess up my website."

Every step that changes something outside Queen (a file in a repository, a page, a commit, a push = a deploy) is first a
PROPOSAL: what, why, and the exact change (a diff, a file and its size, a commit). It waits in ~/.groq/approvals/ until a
supervisor decides. Nothing is done on a reject; the note says why, and Queen stops (or proposes again, changed).

    POST /api/supervisor/propose {task, step, summary, detail}   -> {id}       (Queen's own skills call propose_and_wait)
    GET  /api/supervisor/pending                                  -> proposals waiting
    GET  /api/supervisor/get?id=                                  -> one proposal, its decision
    POST /api/supervisor/decide {id, decision: approve|reject, note, by}

The supervisor is a Claude Code session: `queen pending`, `queen show <id>`, `queen approve <id> ["note"]`,
`queen reject <id> "why"` (hub tools/queen). A proposal nobody answers in time is a reject ("no supervisor answered"):
silence never means yes.
"""
import json
import time
import uuid
from pathlib import Path

from flask import jsonify, request

DIR = Path.home() / ".groq" / "approvals"


def _path(pid):
    if not pid or "/" in pid or ".." in pid:
        raise ValueError("bad id")
    return DIR / f"{pid}.json"


def propose(task, step, summary, detail):
    DIR.mkdir(parents=True, exist_ok=True)
    pid = time.strftime("%H%M%S-") + uuid.uuid4().hex[:6]
    rec = {"id": pid, "task": task, "step": step, "summary": summary, "detail": detail,
           "status": "pending", "asked": time.strftime("%Y-%m-%d %H:%M:%S")}
    try:   # the chat turn whose command made this proposal (training data, 13.11.2026)
        import training_log
        rec["turn"] = getattr(training_log.TURN, "id", None)
    except Exception:
        pass
    _path(pid).write_text(json.dumps(rec, indent=1, ensure_ascii=False))
    print(f"[supervisor] waiting for approval {pid}: {task} / {step}: {summary}", flush=True)
    return pid


def get(pid):
    return json.loads(_path(pid).read_text())


def decide(pid, decision, note="", by="Claude Code"):
    rec = get(pid)
    if rec["status"] != "pending":
        raise ValueError(f"{pid} is already {rec['status']}")
    if decision not in ("approve", "reject"):
        raise ValueError("decision is approve or reject")
    rec.update(status="approved" if decision == "approve" else "rejected", note=note, by=by,
               decided=time.strftime("%Y-%m-%d %H:%M:%S"))
    _path(pid).write_text(json.dumps(rec, indent=1, ensure_ascii=False))
    try:   # every decision and its note is a training event (the correction in words)
        import training_log
        training_log.log_verdict(rec)
    except Exception:
        pass
    return rec


def pending():
    DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for p in sorted(DIR.glob("*.json")):
        try:
            r = json.loads(p.read_text())
        except Exception:
            continue
        if r.get("status") == "pending":
            out.append(r)
    return out


class Rejected(Exception):
    pass


def propose_and_wait(task, step, summary, detail, timeout=1800):
    """Ask, then wait for the supervisor. Returns the note on approve; raises Rejected otherwise."""
    pid = propose(task, step, summary, detail)
    end = time.time() + timeout
    while time.time() < end:
        rec = get(pid)
        if rec["status"] == "approved":
            return rec.get("note", "")
        if rec["status"] == "rejected":
            raise Rejected(f"{step}: rejected by {rec.get('by')}: {rec.get('note')}")
        time.sleep(2)
    rec = get(pid)
    rec.update(status="rejected", note="no supervisor answered in time", decided=time.strftime("%Y-%m-%d %H:%M:%S"))
    _path(pid).write_text(json.dumps(rec, indent=1, ensure_ascii=False))
    raise Rejected(f"{step}: no supervisor answered in {timeout // 60} min")


def register(app):
    @app.post("/api/supervisor/propose")
    def sup_propose():
        d = request.get_json(silent=True) or {}
        return jsonify(ok=True, id=propose(d.get("task", ""), d.get("step", ""), d.get("summary", ""), d.get("detail", "")))

    @app.get("/api/supervisor/pending")
    def sup_pending():
        return jsonify(ok=True, pending=pending())

    @app.get("/api/supervisor/get")
    def sup_get():
        try:
            return jsonify(ok=True, **get(request.args.get("id", "")))
        except Exception as exc:
            return jsonify(ok=False, error=str(exc)), 404

    @app.get("/api/supervisor/recent")
    def sup_recent():
        """The last proposals of every status, newest first: the Tasks tab shows what was asked and decided."""
        DIR.mkdir(parents=True, exist_ok=True)
        out = []
        for p in sorted(DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:int(request.args.get("n", 40))]:
            try:
                out.append(json.loads(p.read_text()))
            except Exception:
                pass
        return jsonify(ok=True, recent=out)

    @app.get("/api/skills/list")
    def skills_list():
        """Queen's skills (queen_skills/*.md), for the Skills tab."""
        d = Path(__file__).resolve().parent.parent / "queen_skills"
        out = [{"name": f.stem, "text": f.read_text(encoding="utf-8")} for f in sorted(d.glob("*.md"))]
        return jsonify(ok=True, skills=out)

    @app.post("/api/supervisor/decide")
    def sup_decide():
        d = request.get_json(silent=True) or {}
        try:
            return jsonify(ok=True, **decide(d.get("id", ""), d.get("decision", ""), d.get("note", ""), d.get("by") or "Claude Code"))
        except Exception as exc:
            return jsonify(ok=False, error=str(exc)), 400
    return app
