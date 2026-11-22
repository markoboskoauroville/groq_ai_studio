"""GitHub reader (/api/github/repos, /contents, /read-url), ported 22.11.2026 from the retired legacy_groq_app.py
(audit round 2), unchanged except that it registers on the v32+ backend. Reads through `gh` (Marko's login); read only."""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from flask import jsonify, request

def run_gh(args, timeout=15):
    try:
        cmd = ["gh"] + args
        env = os.environ.copy()
        env["GH_PROMPT_DISABLED"] = "1"
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        if res.returncode == 0:
            return True, res.stdout
        return False, res.stderr or res.stdout
    except Exception as exc:
        return False, str(exc)


def register(app):
    @app.get("/api/github/repos")
    def github_repos():
        limit = request.args.get("limit", "100")
        ok, out = run_gh(["repo", "list", "--limit", str(limit),
                          "--json", "name,nameWithOwner,description,isPrivate,updatedAt,stargazerCount,primaryLanguage"])
        if not ok:
            return jsonify(error=f"GitHub read failed: {out}"), 500
        try:
            return jsonify(repos=json.loads(out))
        except Exception as exc:
            return jsonify(error=str(exc)), 500

    @app.get("/api/github/contents")
    def github_contents():
        repo = request.args.get("repo", "").strip()
        path = request.args.get("path", "").strip()
        if not repo:
            return jsonify(error="Repository is required"), 400

        api_path = f"repos/{repo}/contents"
        if path:
            api_path = f"{api_path}/{path.lstrip('/')}"

        ok, out = run_gh(["api", api_path])
        if not ok:
            return jsonify(error=f"Failed to read from GitHub: {out}"), 400

        try:
            data = json.loads(out)
            if isinstance(data, dict) and data.get("type") == "file":
                encoded = data.get("content", "")
                try:
                    decoded = base64.b64decode(encoded).decode("utf-8")
                except UnicodeDecodeError:
                    decoded = "(Binary file content cannot be displayed as UTF-8)"
                return jsonify(
                    type="file",
                    name=data.get("name"),
                    path=data.get("path"),
                    size=data.get("size"),
                    content=decoded,
                    repo=repo
                )
            elif isinstance(data, list):
                items = [{"name": i.get("name"), "path": i.get("path"), "type": i.get("type"), "size": i.get("size", 0)} for i in data]
                return jsonify(type="dir", repo=repo, path=path, items=items)
            return jsonify(data=data)
        except Exception as exc:
            return jsonify(error=str(exc)), 500

    @app.post("/api/github/read-url")
    def github_read_url():
        data = request.get_json(silent=True) or {}
        url = (data.get("url") or "").strip()
        if not url:
            return jsonify(error="URL is required"), 400

        match = re.search(r"github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)", url)
        if match:
            owner, repo, branch, path = match.groups()
            full_repo = f"{owner}/{repo}"
            api_path = f"repos/{full_repo}/contents/{path}?ref={branch}"
            ok, out = run_gh(["api", api_path])
            if ok:
                try:
                    res = json.loads(out)
                    decoded = base64.b64decode(res.get("content", "")).decode("utf-8")
                    return jsonify(
                        name=res.get("name", path.split("/")[-1]),
                        repo=full_repo,
                        path=path,
                        size=res.get("size", len(decoded)),
                        content=decoded
                    )
                except Exception as exc:
                    return jsonify(error=f"Decode error: {exc}"), 500
            return jsonify(error=f"Could not read GitHub URL: {out}"), 400

        raw_url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
        try:
            import urllib.request
            req = urllib.request.Request(raw_url, headers={"User-Agent": "GroqChat/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read().decode("utf-8", errors="replace")
                filename = url.split("/")[-1].split("?")[0] or "github_file.txt"
                return jsonify(name=filename, repo="github", path=url, size=len(content), content=content)
        except Exception as exc:
            return jsonify(error=f"Failed to read URL: {exc}"), 400


    return app
