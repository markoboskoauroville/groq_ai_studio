"""Queen's skill: collect a themed set of photographs into Google Drive (13.11.2026, first job: Ganesha worship in Tamil Nadu).

    POST /api/skills/image-collect {action:"run"|"publish"|"status", job, target?, budget?, folder?}
    GET  /api/skills/image-collect/status?job=

`run` and `publish` start tools/image_collect.py in the background (detached; its log is ~/.groq/work/image_collect/<job>/log.txt),
`status` answers the counts. The script judges every candidate with her eyes (/api/vision/ask), downloads only accepted originals,
checks size, sharpness and duplicates, and `publish` uploads 001_.. files and a CSV sheet with rclone (gdrive:).
"""
import json
import subprocess
import sys
from pathlib import Path

from flask import jsonify, request

HERE = Path(__file__).resolve().parent
CANDIDATES = [HERE.parent / "tools" / "image_collect.py", Path.home() / "Developer" / "groq_ai_studio" / "tools" / "image_collect.py"]


def _script():
    for c in CANDIDATES:
        if c.is_file():
            return c
    return None


def _python():
    venv = Path.home() / ".venvs" / "imgcollect" / "bin" / "python3"
    return str(venv) if venv.exists() else sys.executable


def register(app):
    @app.post("/api/skills/image-collect")
    def image_collect():
        d = request.get_json(silent=True) or {}
        action = d.get("action", "status")
        job = d.get("job", "ganesha-tn")
        script = _script()
        if not script:
            return jsonify(ok=False, error="tools/image_collect.py not found"), 500
        if action not in ("run", "publish", "status"):
            return jsonify(ok=False, error="action is run, publish or status"), 400
        cmd = [_python(), str(script), action, "--job", job]
        for k in ("target", "budget", "spare", "folder"):
            if d.get(k) is not None:
                cmd += [f"--{k}", str(d[k])]
        if action == "status":
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            try:
                return jsonify(ok=True, **json.loads(r.stdout))
            except Exception:
                return jsonify(ok=False, error=(r.stdout + r.stderr)[-400:]), 500
        out = Path.home() / ".groq" / "work" / "image_collect" / job
        out.mkdir(parents=True, exist_ok=True)
        with open(out / f"{action}.out", "a") as fh:
            p = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, start_new_session=True)
        return jsonify(ok=True, started=action, pid=p.pid, log=str(out / "log.txt"))

    @app.get("/api/skills/image-collect/status")
    def image_collect_status():
        job = request.args.get("job", "ganesha-tn")
        r = subprocess.run([_python(), str(_script()), "status", "--job", job], capture_output=True, text=True, timeout=60)
        try:
            return jsonify(ok=True, **json.loads(r.stdout))
        except Exception:
            return jsonify(ok=False, error=(r.stdout + r.stderr)[-400:]), 500
    return app
