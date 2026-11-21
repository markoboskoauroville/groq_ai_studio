"""Free Gemini pictures in Marko's Chrome, as a local Queen skill (21.11.2026).

Command:  GEMINI IMAGE: <job.json>
The job file: {"prompt": "...", "images": ["ref1.png", "ref2.png"], "out": "frame.png", "aspect": "9:16",
               "account": "marko.bosko@gmail.com", "max_accounts": 8, "skip": ["father.aya@gmail.com"]}
It runs gemini_skill.make_image: references attached through Gemini's own '+' -> 'Upload files' (the file input
caught and filled over DevTools), '+' -> 'Create image', Aspect ratio chip, Send, the picture copied from Chrome's
memory; an account that refuses, times out or waits for Marko (a consent box, a sign-in) hands over to the next
Chrome profile. Structured callers use POST /api/gemini/image with the same fields ("image" = one path or a list).
"""
from __future__ import annotations

import json
from pathlib import Path

HELP = (
    "Gemini image (free, Marko's Chrome profiles over DevTools). Write a job file and send\n"
    "  GEMINI IMAGE: /path/job.json\n"
    'job.json: {"prompt": "...", "images": ["ref1.png", "ref2.png"], "out": "/path/out.png", "aspect": "9:16",\n'
    '           "account": "<first account>", "max_accounts": 8, "skip": ["<account waiting for Marko>"]}\n'
    "Name the references in the prompt (Image 1 is ..., Image 2 is ...). One image at a time. Boxes that need "
    "Marko (Gemini consent 'Agree', 'Use Gemini', sign-in) are never pressed: that account is skipped and named."
)


def help_text() -> str:
    return HELP


def run_job(path: str) -> str:
    job_file = Path(path.strip().strip('"').strip("'")).expanduser()
    if not job_file.is_file():
        return f"No job file {job_file}.\n\n{HELP}"
    try:
        job = json.loads(job_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return f"The job file is not valid JSON: {exc}"
    if not job.get("prompt") or not job.get("out"):
        return "The job needs at least \"prompt\" and \"out\"."
    try:
        import gemini_skill  # noqa: PLC0415  (installed beside queen_backend.py)
    except ImportError:
        from qwen_app import gemini_skill  # noqa: PLC0415
    try:
        r = gemini_skill.make_image(
            job["prompt"], job.get("images") or job.get("image") or None, job["out"],
            account=job.get("account") or gemini_skill.ACCOUNT, wait=int(job.get("wait") or 180),
            max_accounts=int(job.get("max_accounts") or 4), aspect=job.get("aspect"),
            tool=job.get("tool", True), skip=set(job.get("skip") or ()))
    except gemini_skill.GeminiError as exc:
        return f"Gemini image FAILED: {exc}"
    return (f"Gemini image made: {r['out']} ({r['width']}x{r['height']}) by {r['account']} ({r.get('profile')}); "
            f"tool {r.get('setup')}; tried {r.get('tried')}")
