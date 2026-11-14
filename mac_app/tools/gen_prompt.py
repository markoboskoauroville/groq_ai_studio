#!/usr/bin/env python3
"""gen_prompt.py: Queen's system prompt, taken out of qwen_app/app.py with ast (no Flask, no groq, stdlib only).

Phase A (14.11.2026): the Swift app builds the system prompt exactly like build_queen_system_prompt(). It does not copy the
text by hand: it runs this helper on the installed ~/.groq/qwen_app/app.py (again whenever that file changes) and gets
the template with three markers, then puts in the version, where she runs, and every queen_skills/*.md (every turn).
A copy made at build time sits in the app bundle as the fallback.

    gen_prompt.py APP_PY                       -> JSON {template, where_mac, where_other}
    gen_prompt.py APP_PY --full VERSION LOCATION SKILLS_DIR [PERSONA]
                                               -> the whole prompt as Python builds it (the CI test compares Swift's to it)
"""
import ast
import json
import os
import sys
from pathlib import Path

V, W, S = "VERSION", "WHERE", "SKILLS"
FUNCS = ("build_queen_system_prompt", "_where_i_run", "_queen_skills_block")


def load(app_py):
    tree = ast.parse(Path(app_py).read_text(encoding="utf-8"))
    keep = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in FUNCS:
            keep.append(node)
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            keep.append(node)      # plain constants (AUTO_UPDATE_REPO, DEFAULT_MODEL, ...)
    ns = {"os": os, "Path": Path, "__name__": "queen_prompt"}
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(app_py), "exec"), ns)
    missing = [f for f in FUNCS if f not in ns]
    if missing:
        raise SystemExit(f"gen_prompt: {missing} not found in {app_py}")
    return ns


def where(ns, location):
    old = os.environ.get("QUEEN_LOCATION")
    os.environ["QUEEN_LOCATION"] = location
    try:
        return ns["_where_i_run"]()
    finally:
        if old is None:
            os.environ.pop("QUEEN_LOCATION", None)
        else:
            os.environ["QUEEN_LOCATION"] = old


def template(app_py):
    ns = load(app_py)
    real_where = ns["_where_i_run"]
    wm, wo = where(ns, "mac"), where(ns, "vm")
    ns["VERSION"] = V
    ns["_where_i_run"] = lambda: W
    ns["_queen_skills_block"] = lambda: S
    t = ns["build_queen_system_prompt"]("")
    ns["_where_i_run"] = real_where
    for mark in (V, W, S):
        if mark not in t:
            raise SystemExit(f"gen_prompt: marker {mark!r} missing in the template")
    return {"template": t, "where_mac": wm, "where_other": wo}


def full(app_py, version, location, skills, persona=""):
    ns = load(app_py)
    ns["VERSION"] = version
    ns["QUEEN_SKILLS_DIR"] = Path(skills)
    os.environ["QUEEN_LOCATION"] = location
    return ns["build_queen_system_prompt"](persona)


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) >= 5 and a[1] == "--full":
        sys.stdout.buffer.write(full(a[0], a[2], a[3], a[4], a[5] if len(a) > 5 else "").encode("utf-8"))
    elif len(a) == 1:
        sys.stdout.write(json.dumps(template(a[0]), ensure_ascii=False))
    else:
        raise SystemExit(__doc__)
