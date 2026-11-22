"""Queen checks her own shape (teach step of the 22.11.2026 audit): chat "check your shape", GET /api/queen/selfcheck.

Read-only and $0: no model call, no provider call, nothing restarted. Checks:
  1. versions: the running app (/health on 8765), her backend, version.json in ~/.queen, the repo if it is there
  2. modules: every Groq-free module loaded (restored_routes.FAILED, local_router.FAILED_HANDS empty)
  3. routes: every /api/... route named in her skills is registered, except the listed exemptions
  4. her brain: the local Claude Code reachable on the plan (claude auth status, no question asked)
  5. her skills: every queen_skills/*.md readable, not empty, no two identical
Each line says OK or the problem; the answer ends with the count of problems.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from pathlib import Path

# routes her skills name that are not hers or are off on purpose (same list as the pin test in test_audit_fixes.py)
EXEMPT_PREFIXES = ("/api/system/mv", "/api/system/set_volume", "/api/ndi", "/api/preshow", "/api/state", "/api/text",
                   "/api/snapshot")
GROQ_OR_UNPORTED = ("/api/brain/escalate", "/api/remote/send", "/api/screen/look", "/api/selfcheck/image-live",
                    "/api/skills/band-posters", "/api/skills/describe-images", "/api/skills/gemini-posters",
                    "/api/skills/live-check", "/api/skills/poster-like", "/api/skills/web-photo", "/api/triple/",
                    "/api/vision/ask")


def _skill_routes(skills_dir: Path) -> dict[str, set]:
    named: dict[str, set] = {}
    for f in sorted(skills_dir.glob("*")):
        try:
            text = f.read_text(errors="ignore")
        except OSError:
            continue
        for m in re.finditer(r"(/api/[A-Za-z0-9_/\-<>{}.]+)", text):
            named.setdefault(m.group(1).rstrip(".").split("?")[0], set()).add(f.name)
    return named


def _registered(app, route: str) -> bool:
    rules = [r.rule for r in app.url_map.iter_rules()]
    if route.endswith("/"):
        return any(r.startswith(route) for r in rules)
    probe = re.sub(r"<[^>]+>|\{[^}]+\}", "x", route)
    adapter = app.url_map.bind("localhost")
    for method in ("GET", "POST"):
        try:
            adapter.match(probe, method=method)
            return True
        except Exception as exc:  # noqa: BLE001
            if type(exc).__name__ == "MethodNotAllowed":
                return True
    return False


def report(app=None) -> dict:
    if app is None:
        from flask import current_app
        app = current_app._get_current_object()
    import queen_brain
    import restored_routes
    import local_router
    import claude_link
    lines, problems = [], 0

    def line(ok, text):
        nonlocal problems
        problems += 0 if ok else 1
        lines.append(("OK   " if ok else "PROBLEM ") + text)

    # 1. versions
    here = Path(__file__).resolve().parent
    vfile = here.parent / "version.json"
    try:
        backend_v = json.loads(vfile.read_text()).get("version")
    except (OSError, ValueError):
        backend_v = None
    try:
        with urllib.request.urlopen("http://127.0.0.1:8765/health", timeout=3) as r:
            app_v = str(json.load(r).get("version", "")).lstrip("v")
    except Exception as exc:  # noqa: BLE001
        app_v = f"not answering ({type(exc).__name__})"
    repo_v = None
    repo = Path.home() / "Developer" / "groq_ai_studio" / "version.json"
    if repo.is_file():
        try:
            repo_v = json.loads(repo.read_text()).get("version")
        except ValueError:
            pass
    same = str(backend_v) == str(app_v) and (repo_v is None or str(repo_v) == str(backend_v))
    line(same, f"versions: app v{app_v}, backend v{backend_v}" + (f", repo v{repo_v}" if repo_v is not None else ""))
    # 2. modules
    failed = {**restored_routes.FAILED, **local_router.FAILED_HANDS}
    line(not failed, f"modules: {len(restored_routes.LOADED)} loaded" + (f", failed {failed}" if failed else ""))
    # 3. routes her skills name
    sdir = queen_brain.skills_dir()
    named = _skill_routes(sdir)
    missing = sorted(r for r in named if not r.startswith(EXEMPT_PREFIXES + GROQ_OR_UNPORTED) and not _registered(app, r))
    off = sorted(r for r in named if r.startswith(GROQ_OR_UNPORTED))
    line(not missing, f"routes in her skills: {len(named)} named, {len(missing)} missing"
         + (f": {', '.join(missing)}" if missing else "")
         + (f"; off on purpose (need Groq): {', '.join(off)}" if off else ""))
    # 6. chat files that could not be read: kept aside, never deleted (round 2, 22.11.2026)
    try:
        import capi_chat
        bad = capi_chat.corrupt_chats()
    except Exception as exc:  # noqa: BLE001
        bad = [{"file": "?", "reason": f"could not list: {exc}"}]
    line(not bad, "chat files: all readable" if not bad else
         "chat files NOT readable (kept aside): " + "; ".join(f"{b['file']} ({b['reason']})" for b in bad))
    # 7. the Google Cloud ledger behind the credit
    try:
        import gcloud_chat
        _, ledger_err = gcloud_chat.spent_checked()
    except Exception as exc:  # noqa: BLE001
        ledger_err = f"could not check: {exc}"
    line(not ledger_err, "Google Cloud ledger: readable" if not ledger_err else f"Google Cloud ledger unreadable: {ledger_err}")
    # 4. brain
    st = claude_link.status()
    line(st.get("reachable", False), "brain: local Claude Code " + ("reachable on the plan" if st.get("reachable")
                                                                    else f"NOT reachable ({st.get('why')})"))
    # 5. skills files
    files = sorted(sdir.glob("*.md"))
    empty = [f.name for f in files if len(f.read_text(errors="ignore").strip()) < 80]
    digests: dict[str, list] = {}
    for f in files:
        digests.setdefault(hashlib.md5(f.read_bytes()).hexdigest(), []).append(f.name)
    dups = [v for v in digests.values() if len(v) > 1]
    line(not empty and not dups, f"skills: {len(files)} files in {sdir}" + (f", empty {empty}" if empty else "")
         + (f", identical {dups}" if dups else ""))
    text = "My shape:\n" + "\n".join(lines) + f"\n{problems} problem(s)."
    return {"ok": problems == 0, "problems": problems, "lines": lines, "text": text, "missing_routes": missing}
