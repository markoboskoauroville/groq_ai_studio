"""Elevate Media routes (/api/elevate/*), ported 22.11.2026 from the retired legacy_groq_app.py (audit round 2),
unchanged except that they register on the v32+ backend."""
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

ELEVATE_REPO_DIR = Path.home() / "ElevateMedia"
ELEVATE_MONITOR_DIR = Path.home() / "Developer" / "ELEVATE_MEDIA_MONITOR"
ELEVATE_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "ElevateMediaMonitor"
ELEVATE_MOVIES_DIR = Path.home() / "Movies" / "ElevateMedia"


def _read_json_safe(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


ELEVATE_ALLOWED_RESOLVE_TOOLS = {
    "layout_check.py",
    "resolve_checklist.py",
    "resolve_fades.py",
    "caption_check.py",
    "centre_verify.py",
    "centre_blocks.py",
    "overlap_check.py",
    "clip_audio_check.py",
    "delivery_check.py",
    "resolve_to_4x5.py",
}


def _safe_project_code(raw: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "", (raw or "").strip())




def register(app):
    @app.get("/api/elevate/board")
    def elevate_board():
        """Return Project Watcher board (watcher.json: HIR_xx projects, stages, next steps)."""
        watcher_path = ELEVATE_SUPPORT_DIR / "watcher.json"
        data = _read_json_safe(watcher_path, {"projects": []})
        return jsonify(
            ok=True,
            exists=watcher_path.exists(),
            path=str(watcher_path),
            projects=data.get("projects", []) if isinstance(data, dict) else [],
            board=data,
        )


    @app.get("/api/elevate/whatsapp")
    def elevate_whatsapp():
        """Return latest messages from WhatsApp group 'AI Videos' (messages.jsonl)."""
        try:
            count = max(1, min(200, int(request.args.get("count", "30"))))
        except ValueError:
            count = 30
        chat_filter = (request.args.get("chat") or "AI Videos").strip()

        jsonl_path = ELEVATE_SUPPORT_DIR / "messages.jsonl"
        fallback_jsonl = ELEVATE_REPO_DIR / "production" / "damjan" / "chat" / "ai_videos.jsonl"
        src = jsonl_path if jsonl_path.exists() else fallback_jsonl

        messages = []
        if src.exists():
            try:
                lines = src.read_text(encoding="utf-8", errors="replace").splitlines()
                for ln in lines:
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        item = json.loads(ln)
                        if not chat_filter or item.get("chat") == chat_filter:
                            messages.append(item)
                    except Exception:
                        continue
            except Exception as exc:
                return jsonify(ok=False, error=str(exc)), 500

        recent = messages[-count:]
        return jsonify(
            ok=True,
            source=str(src),
            chat=chat_filter,
            count=len(recent),
            total_available=len(messages),
            messages=recent,
        )


    @app.post("/api/elevate/whatsapp/draft")
    def elevate_whatsapp_draft():
        """
        Type an UNSENT draft reply into WhatsApp Web via whatsapp_draft.py.
        HUMAN GATE: Never presses Send — Marko reviews and sends himself.
        """
        data = request.get_json(silent=True) or {}
        chat_name = (data.get("chat") or "AI Videos").strip()
        text = (data.get("text") or "").strip()
        if not text:
            return jsonify(ok=False, error="Missing 'text' for WhatsApp draft"), 400

        script = ELEVATE_REPO_DIR / "tools" / "whatsapp_draft.py"
        if not script.exists():
            return jsonify(ok=False, error=f"Script not found: {script}"), 404

        with tempfile.NamedTemporaryFile("w", suffix=".txt", encoding="utf-8", delete=False) as tf:
            tf.write(text)
            tmp_path = tf.name

        try:
            res = subprocess.run(
                ["python3", str(script), chat_name, tmp_path],
                capture_output=True,
                text=True,
                timeout=25,
            )
            ok = res.returncode == 0
            return jsonify(
                ok=ok,
                unsent_human_gated=True,
                chat=chat_name,
                stdout=res.stdout.strip(),
                stderr=res.stderr.strip(),
                error=None if ok else (res.stderr.strip() or res.stdout.strip() or "whatsapp_draft.py failed"),
            ), (200 if ok else 409)
        except Exception as exc:
            return jsonify(ok=False, error=str(exc)), 500
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


    @app.get("/api/elevate/drive-comments")
    def elevate_drive_comments():
        """Read timestamped video revision comments on Google Drive (LongevityStore) via drive_comments.py."""
        project = _safe_project_code(request.args.get("project", ""))
        include_all = request.args.get("all", "0") in ("1", "true", "yes")
        if not project:
            return jsonify(ok=False, error="Query param 'project' (e.g. HIR_98) is required"), 400

        gdrive_py = Path.home() / "Applications" / "GDriveDownloader" / ".venv" / "bin" / "python"
        py_bin = str(gdrive_py) if gdrive_py.exists() else "python3"
        script = ELEVATE_MONITOR_DIR / "tools" / "drive_comments.py"
        if not script.exists():
            return jsonify(ok=False, error=f"Script not found: {script}"), 404

        cmd = [py_bin, "-I", str(script), project] if gdrive_py.exists() else [py_bin, str(script), project]
        if include_all:
            cmd.append("--all")

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
            if res.returncode != 0:
                return jsonify(ok=False, project=project, error=(res.stderr or res.stdout).strip()), 502
            parsed = json.loads(res.stdout) if res.stdout.strip() else {}
            return jsonify(ok=True, **parsed)
        except Exception as exc:
            return jsonify(ok=False, project=project, error=str(exc)), 500


    @app.post("/api/elevate/fetch-image")
    def elevate_fetch_image():
        """
        Download a high-resolution product photo into ~/Movies/ElevateMedia/<project>/refs/web/,
        verify image MIME type, and inspect pixel dimensions via macOS `sips`.
        """
        data = request.get_json(silent=True) or {}
        url = (data.get("url") or "").strip()
        project = _safe_project_code(data.get("project", ""))
        name = re.sub(r"[^A-Za-z0-9_.-]", "_", (data.get("name") or "product_ref").strip())

        if not url or not url.startswith(("http://", "https://")):
            return jsonify(ok=False, error="Valid http(s) 'url' is required"), 400
        if not project:
            return jsonify(ok=False, error="'project' (e.g. HIR_98) is required"), 400

        # Resolve matching project folder under ~/Movies/ElevateMedia if one starts with HIR_xx
        target_project_dir = ELEVATE_MOVIES_DIR / project
        if ELEVATE_MOVIES_DIR.is_dir() and not target_project_dir.exists():
            matches = sorted(ELEVATE_MOVIES_DIR.glob(f"{project}*"))
            if matches:
                target_project_dir = matches[0]

        refs_dir = target_project_dir / "refs" / "web"
        refs_dir.mkdir(parents=True, exist_ok=True)

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; GroqAIStudio)"})
            with urllib.request.urlopen(req, timeout=25) as resp:
                ctype = (resp.headers.get("Content-Type") or "").lower()
                if not ctype.startswith("image/"):
                    return jsonify(ok=False, error=f"URL did not return an image (Content-Type: {ctype})"), 415
                img_bytes = resp.read()
        except Exception as exc:
            return jsonify(ok=False, error=f"Download failed: {exc}"), 502

        ext_map = {"image/png": ".png", "image/webp": ".webp", "image/jpeg": ".jpg", "image/jpg": ".jpg"}
        ext = ext_map.get(ctype.split(";")[0].strip(), ".png")
        if not os.path.splitext(name)[1]:
            name = f"{name}{ext}"

        out_path = refs_dir / name
        out_path.write_bytes(img_bytes)

        width, height = 0, 0
        try:
            sips = subprocess.run(
                ["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(out_path)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            m_w = re.search(r"pixelWidth:\s*(\d+)", sips.stdout)
            m_h = re.search(r"pixelHeight:\s*(\d+)", sips.stdout)
            if m_w:
                width = int(m_w.group(1))
            if m_h:
                height = int(m_h.group(1))
        except Exception:
            pass

        return jsonify(
            ok=True,
            project=project,
            path=str(out_path),
            content_type=ctype,
            bytes=len(img_bytes),
            width=width,
            height=height,
            high_res=(max(width, height) >= 1000),
        )


    @app.post("/api/elevate/gemini-chrome")
    def elevate_gemini_chrome():
        """
        Free image generation workflow via Gemini in Chrome:
        - mode='chrome': copies prompt to clipboard and opens https://gemini.google.com/app in Google Chrome
        - mode='vm': stages batch.json + optional refs to gdrive:Chromium Downloads/Gemini/_batch/batch.json via rclone
        """
        data = request.get_json(silent=True) or {}
        prompt = (data.get("prompt") or "").strip()
        project = _safe_project_code(data.get("project") or "HIR_GEN")
        shot_name = re.sub(r"[^A-Za-z0-9_.-]", "_", (data.get("name") or "shot_01").strip())
        mode = (data.get("mode") or "chrome").strip().lower()
        refs = data.get("refs") if isinstance(data.get("refs"), list) else []

        if not prompt:
            return jsonify(ok=False, error="Missing 'prompt'"), 400
        if mode not in ("chrome", "vm"):
            return jsonify(ok=False, error="Invalid 'mode': must be 'chrome' or 'vm'"), 400

        if mode == "chrome":
            try:
                subprocess.run(["pbcopy"], input=prompt, text=True, timeout=5)
                subprocess.run(["open", "-a", "Google Chrome", "https://gemini.google.com/app"], timeout=8)
                return jsonify(
                    ok=True,
                    mode="chrome",
                    project=project,
                    name=shot_name,
                    clipboard_copied=True,
                    opened_url="https://gemini.google.com/app",
                    message="Prompt copied to clipboard and Google Chrome opened to Gemini.",
                )
            except Exception as exc:
                return jsonify(ok=False, error=str(exc)), 500

        # mode == "vm" -> upload batch.json via rclone
        rclone_bin = shutil.which("rclone") or "/opt/homebrew/bin/rclone"
        if not Path(rclone_bin).exists():
            return jsonify(ok=False, error="rclone binary not found"), 500

        uploaded_refs = []
        remote_base = f"gdrive:Chromium Downloads/Gemini/em-{project}"
        for r_path in refs:
            p = Path(os.path.expanduser(str(r_path)))
            if p.exists():
                res_ref = subprocess.run(
                    [rclone_bin, "copy", str(p), f"{remote_base}/refs/"],
                    capture_output=True,
                    text=True,
                    timeout=45,
                )
                if res_ref.returncode == 0:
                    uploaded_refs.append(p.name)

        batch_payload = {
            "project": f"em-{project}",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "output_dir": f"{remote_base}/",
            "items": [
                {
                    "name": shot_name,
                    "prompt": prompt,
                    "refs": uploaded_refs,
                }
            ],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as tf:
            json.dump(batch_payload, tf, indent=2)
            tmp_batch = tf.name

        try:
            res = subprocess.run(
                [rclone_bin, "copyto", tmp_batch, "gdrive:Chromium Downloads/Gemini/_batch/batch.json"],
                capture_output=True,
                text=True,
                timeout=45,
            )
            ok = res.returncode == 0
            return jsonify(
                ok=ok,
                mode="vm",
                project=project,
                name=shot_name,
                uploaded_refs=uploaded_refs,
                remote_output=remote_base,
                error=None if ok else (res.stderr or res.stdout).strip(),
            ), (200 if ok else 502)
        finally:
            try:
                os.unlink(tmp_batch)
            except OSError:
                pass


    @app.get("/api/elevate/gemini-status")
    def elevate_gemini_status():
        """Check completed Gemini VM images in gdrive:Chromium Downloads/Gemini/em-<project>/."""
        project = _safe_project_code(request.args.get("project", ""))
        if not project:
            return jsonify(ok=False, error="Query param 'project' is required"), 400

        rclone_bin = shutil.which("rclone") or "/opt/homebrew/bin/rclone"
        if not Path(rclone_bin).exists():
            return jsonify(ok=False, error="rclone binary not found"), 500

        remote_dir = f"gdrive:Chromium Downloads/Gemini/em-{project}"
        try:
            res = subprocess.run(
                [rclone_bin, "lsjson", remote_dir],
                capture_output=True,
                text=True,
                timeout=25,
            )
            if res.returncode != 0:
                return jsonify(ok=True, project=project, remote=remote_dir, files=[], note="Folder not created yet or empty")
            files = json.loads(res.stdout) if res.stdout.strip() else []
            return jsonify(ok=True, project=project, remote=remote_dir, count=len(files), files=files)
        except Exception as exc:
            return jsonify(ok=False, project=project, error=str(exc)), 500


    @app.post("/api/elevate/resolve")
    def elevate_resolve_tool():
        """
        Run an allowlisted Elevate Media DaVinci Resolve verification/layout tool.
        JSON Body: { "tool": "layout_check.py", "args": [], "use_resolve_run": false }
        """
        data = request.get_json(silent=True) or {}
        tool_name = (data.get("tool") or "").strip()
        extra_args = [str(a) for a in (data.get("args") or []) if isinstance(a, (str, int, float))]

        if tool_name not in ELEVATE_ALLOWED_RESOLVE_TOOLS:
            return jsonify(
                ok=False,
                error=f"Tool '{tool_name}' is not in the safe Elevate Resolve allowlist: {sorted(ELEVATE_ALLOWED_RESOLVE_TOOLS)}",
            ), 403

        tool_path = ELEVATE_REPO_DIR / "tools" / tool_name
        if not tool_path.exists():
            return jsonify(ok=False, error=f"Tool script not found on disk: {tool_path}"), 404

        resolve_run_bin = Path.home() / ".local" / "bin" / "resolve-run"
        needs_router = bool(data.get("use_resolve_run")) or tool_name.startswith("resolve_")
        if needs_router and resolve_run_bin.exists():
            cmd = [str(resolve_run_bin), "--who", "elevate", str(tool_path)] + extra_args
        else:
            cmd = ["python3", str(tool_path)] + extra_args

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            return jsonify(
                ok=(res.returncode == 0),
                tool=tool_name,
                command=cmd,
                returncode=res.returncode,
                stdout=res.stdout[-4000:],
                stderr=res.stderr[-4000:],
            ), (200 if res.returncode == 0 else 422)
        except Exception as exc:
            return jsonify(ok=False, tool=tool_name, error=str(exc)), 500


    return app
