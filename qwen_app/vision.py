"""Queen's eyes: ask a question about a picture (12.11.2026).

Marko: "If she cannot see images, you need to enable that model on the Groq to understand where we are all in the
image." Groq lists no Llama-4/vision model on this account (12.11.2026), but Qwen 3.6 / 3.8 read images natively
(tested: a band photo, people and instruments counted right). So nothing had to be enabled: Queen sends the picture
as an image_url data URL to her own Qwen model, through her key pool, and the cost goes into her ledger.

    POST /api/vision/ask  {question, path | repo+file | url, model?, json?}
        path       a local image file
        repo+file  an image inside a mirrored repository (see repo_reader.py), e.g. santoshi_band_site + img/x.jpg
        url        an http(s) image (fetched here, never forwarded)
        json=true  asks for a JSON answer and parses it
"""
import base64
import json
import mimetypes
import re
import time
import urllib.request
from pathlib import Path

from flask import jsonify, request

VISION_MODEL = "qwen/qwen3.6-27b"
MAX_BYTES = 4_000_000          # Groq's base64 image limit is about 4 MB


class VisionError(Exception):
    pass


def _image_bytes(data):
    if data.get("path"):
        p = Path(data["path"]).expanduser()
        if not p.is_file():
            raise VisionError(f"no file {p}")
        return p.read_bytes(), mimetypes.guess_type(p.name)[0] or "image/jpeg"
    if data.get("repo") and data.get("file"):
        import repo_reader  # noqa: PLC0415
        full, d = repo_reader._ready(data["repo"])
        p = repo_reader._safe(d, data["file"])
        if not p.is_file():
            raise VisionError(f"{data['file']} is not a file in {full}")
        return p.read_bytes(), mimetypes.guess_type(p.name)[0] or "image/jpeg"
    if data.get("url"):
        url = data["url"]
        if not re.match(r"^https?://", url):
            raise VisionError("url must be http(s)")
        req = urllib.request.Request(url, headers={"User-Agent": "Queen/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read(MAX_BYTES + 1), r.headers.get_content_type() or "image/jpeg"
    raise VisionError("pass path, or repo + file, or url")


def ask(data, pool, record_spend):
    from groq import Groq  # noqa: PLC0415
    question = (data.get("question") or "").strip() or "Describe this picture."
    raw, mime = _image_bytes(data)
    if len(raw) > MAX_BYTES:
        raise VisionError(f"image is {len(raw)//1000} KB; the limit is {MAX_BYTES//1000} KB")
    url = f"data:{mime};base64," + base64.b64encode(raw).decode()
    extra = []                                   # more pictures in the same question (e.g. "is this the same photo?")
    for p in data.get("also") or []:
        pb = Path(p).expanduser().read_bytes()
        extra.append({"type": "image_url", "image_url": {"url": f"data:{mimetypes.guess_type(str(p))[0] or 'image/jpeg'};base64,"
                                                          + base64.b64encode(pb).decode()}})
    model = data.get("model") or VISION_MODEL
    want_json = bool(data.get("json"))
    if want_json:
        question += "\nAnswer with ONE JSON object only, no prose, no code fence."
    last = None
    for key in pool.candidates(model) or []:
        try:
            t0 = time.time()
            r = Groq(api_key=key, max_retries=0).chat.completions.create(
                model=model, max_tokens=int(data.get("max_tokens") or 1500),
                messages=[{"role": "user", "content": [{"type": "text", "text": question},
                                                       {"type": "image_url", "image_url": {"url": url}}] + extra}])
            pool.good(key, model)
            text = (r.choices[0].message.content or "").split("</think>")[-1].strip()
            u = r.usage
            cost, _ledger = record_spend(model, u.prompt_tokens or 0, u.completion_tokens or 0,
                                         getattr(r, "id", ""))
            out = {"answer": text, "model": model, "elapsed": round(time.time() - t0, 2),
                   "cost": cost["total_cost"], "tokens": (u.prompt_tokens or 0) + (u.completion_tokens or 0)}
            if want_json:
                m = re.search(r"\{.*\}", text, re.S)
                try:
                    out["json"] = json.loads(m.group(0)) if m else None
                except Exception:
                    out["json"] = None
            return out
        except Exception as exc:
            pool.cool(key, model, exc)
            last = exc
    raise VisionError(f"no key could answer: {last}")


def register(app, pool, record_spend):
    @app.post("/api/vision/ask")
    def vision_ask():
        data = request.get_json(silent=True) or {}
        try:
            return jsonify(ok=True, **ask(data, pool, record_spend))
        except VisionError as exc:
            return jsonify(ok=False, error=str(exc)), 400
        except Exception as exc:
            return jsonify(ok=False, error=f"{type(exc).__name__}: {exc}"), 500
    return app
