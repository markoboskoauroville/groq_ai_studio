"""Repo reader for Queen: go to a GitHub repository, read every file, search it. READ ONLY.

Marko, 12.11.2026: "teach Queen how to go to the repository and read all the files from there, not writing,
only reading and searching for information."

How it works. A repository is mirrored once into a private cache, a shallow clone of its default branch
(`gh repo clone --depth 1`, so private repositories work with Marko's own gh login), and refreshed with a
fast-forward-only pull. Everything after that is local and instant: the file tree, a file (whole, or a line
range), and `git grep` search. Nothing is ever written to GitHub: there is no commit, push, issue or API
call other than the clone / pull / repo-size lookup, and no route here accepts a body.

    GET /api/repo/list                          the repositories on the account (name, privacy, size)
    GET /api/repo/sync?repo=R                   clone or refresh the cache of R  (R = name or owner/name)
    GET /api/repo/tree?repo=R&path=P&q=Q        every file of R under P, filtered by name; size in bytes
    GET /api/repo/read?repo=R&path=F&start=&end=  a file, or a line range of it
    GET /api/repo/search?repo=R&q=Q&regex=1&path=P&case=1&context=N&limit=N
                                                text search inside R; repo=all searches every cached repo
    GET /api/repo/status                        what is cached, how big, how old

Files that hold secrets (.env, keys, certificates, *.pem, id_rsa) are never read out or searched: the
house rule is that a key is never shown (CLAUDE.md, "never a key in the open").
Chat: chat_repo_command() answers "tree R", "read R:path", "search R for text", "sync R" locally, no model.
"""
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from flask import jsonify, request

OWNER = "markoboskoauroville"
CACHE = Path.home() / ".groq" / "repo_cache"
MAX_REPO_MB = 400            # refuse to mirror anything larger unless ?big=1
MAX_READ_BYTES = 200_000     # one read call returns at most this much text
MAX_HITS = 200
STALE_SECONDS = 600          # a cache younger than this is not refreshed again

_REPO = re.compile(r"^[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)?$")
_SECRET_NAME = re.compile(
    r"(^|/)(\.env(\..*)?|.*\.(pem|key|p12|pfx|jks|keystore|cer|crt)|id_(rsa|dsa|ecdsa|ed25519)(\.pub)?|"
    r".*(secret|credential|password|token|apikey|api_key)s?(\.(txt|json|ya?ml|ini|cfg|conf|env|plist))?|"
    r"twilio\.txt|.*-API\.txt)$", re.I)


class ReadError(Exception):
    pass


def _full(repo):
    repo = (repo or "").strip().strip("/")
    if not repo or not _REPO.match(repo):
        raise ReadError("pass repo=<name> or repo=<owner>/<name>")
    return repo if "/" in repo else f"{OWNER}/{repo}"


def _dir(full):
    owner, name = full.split("/")
    return CACHE / owner / name


def _run(cmd, cwd=None, timeout=60):
    env = dict(os.environ, GH_PROMPT_DISABLED="1", GIT_TERMINAL_PROMPT="0")
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
    return r.returncode, r.stdout, r.stderr


def _git(d, *args, timeout=60):
    return _run(["git", "-C", str(d), *args], timeout=timeout)


def _safe(d, rel):
    """A path inside the cached repo, or ReadError. No '..', no absolute paths, no .git."""
    rel = (rel or "").strip().lstrip("/")
    p = (d / rel).resolve()
    root = d.resolve()
    if p != root and root not in p.parents:
        raise ReadError("path is outside the repository")
    if ".git" in p.relative_to(root).parts:
        raise ReadError("the .git folder is not readable here")
    return p


def _is_secret(rel):
    return bool(_SECRET_NAME.search(rel))


# ------------------------------------------------------------------------------ sync

def repo_size_mb(full):
    code, out, err = _run(["gh", "api", f"repos/{full}", "--jq", ".size"], timeout=20)
    if code != 0:
        raise ReadError(f"GitHub does not show {full}: {(err or out).strip()[:200]}")
    return int(out.strip() or 0) / 1024


def sync(repo, big=False, force=False):
    """Clone (shallow) or fast-forward the cache of one repository. Read only."""
    full = _full(repo)
    d = _dir(full)
    if (d / ".git").exists():
        age = time.time() - (d / ".git").stat().st_mtime
        if not force and age < STALE_SECONDS:
            return {"repo": full, "state": "fresh", "age_seconds": int(age)}
        code, out, err = _git(d, "pull", "--ff-only", "--depth", "1", timeout=180)
        if code != 0:
            # a shallow history that cannot fast-forward: fetch and hard-align the CACHE (never the remote)
            code, out, err = _git(d, "fetch", "--depth", "1", "origin", timeout=180)
            if code != 0:
                raise ReadError(f"refresh failed: {(err or out).strip()[:300]}")
            _git(d, "reset", "--hard", "FETCH_HEAD")
        os.utime(d / ".git")
        return {"repo": full, "state": "refreshed"}
    mb = repo_size_mb(full)
    if mb > MAX_REPO_MB and not big:
        raise ReadError(f"{full} is {mb:.0f} MB, over the {MAX_REPO_MB} MB limit; add big=1 to mirror it anyway")
    d.parent.mkdir(parents=True, exist_ok=True)
    code, out, err = _run(["gh", "repo", "clone", full, str(d), "--", "--depth", "1", "--quiet"], timeout=600)
    if code != 0:
        shutil.rmtree(d, ignore_errors=True)
        raise ReadError(f"clone failed: {(err or out).strip()[:300]}")
    return {"repo": full, "state": "cloned", "size_mb": round(mb, 1)}


def _ready(repo, refresh=True):
    full = _full(repo)
    sync(full)            # fresh within STALE_SECONDS, else a quick fast-forward
    return full, _dir(full)


# ------------------------------------------------------------------------------ reading

def tree(repo, path="", q=""):
    full, d = _ready(repo)
    base = _safe(d, path)
    code, out, err = _git(d, "ls-files", "-z", "--", str(base.relative_to(d.resolve())) if path else ".")
    if code != 0:
        raise ReadError(err.strip()[:200])
    words = [w for w in (q or "").lower().split() if w]
    files = []
    for rel in out.split("\0"):
        if not rel or _is_secret(rel):
            continue
        if words and not all(w in rel.lower() for w in words):
            continue
        try:
            size = (d / rel).stat().st_size
        except OSError:
            size = 0
        files.append({"path": rel, "size": size})
    return {"repo": full, "path": path, "count": len(files), "files": files[:5000],
            "truncated": len(files) > 5000}


def read(repo, path, start=None, end=None):
    full, d = _ready(repo)
    p = _safe(d, path)
    rel = str(p.relative_to(d.resolve()))
    if _is_secret(rel):
        raise ReadError(f"{rel} holds secrets; it is not read out")
    if not p.is_file():
        raise ReadError(f"{rel} is not a file in {full} (use tree)")
    raw = p.read_bytes()
    if b"\0" in raw[:8192]:
        return {"repo": full, "path": rel, "binary": True, "size": len(raw),
                "content": "(binary file: not shown)"}
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    total = len(lines)
    s = max(1, int(start)) if start else 1
    e = min(total, int(end)) if end else total
    chunk = "\n".join(lines[s - 1:e])
    cut = False
    if len(chunk.encode("utf-8")) > MAX_READ_BYTES:
        chunk = chunk.encode("utf-8")[:MAX_READ_BYTES].decode("utf-8", errors="ignore")
        e = s + chunk.count("\n")
        cut = True
    return {"repo": full, "path": rel, "size": len(raw), "lines_total": total, "start": s, "end": e,
            "truncated": cut, "content": chunk,
            "next": f"read again with start={e + 1}" if (cut or e < total) else ""}


def search(repo, q, regex=False, path="", case=False, context=0, limit=MAX_HITS):
    q = q or ""
    if not q.strip():
        raise ReadError("pass q=<text to find>")
    limit = max(1, min(int(limit or MAX_HITS), MAX_HITS))
    context = max(0, min(int(context or 0), 5))
    if (repo or "").strip().lower() == "all":
        repos = sorted(f"{o.name}/{r.name}" for o in CACHE.glob("*") if o.is_dir()
                       for r in o.glob("*") if (r / ".git").exists())
        if not repos:
            raise ReadError("no repository is cached yet; sync one first")
    else:
        repos = [_full(repo)]
    hits, per_repo = [], {}
    try:
        pat = re.compile(q if regex else re.escape(q), 0 if case else re.I)
    except re.error as exc:
        raise ReadError(f"bad regular expression: {exc}")
    for full in repos:
        if len(repos) == 1:
            sync(full)
        d = _dir(full)
        if not (d / ".git").exists():
            continue
        cmd = ["grep", "-n", "-I", "--null", "--no-color", "-e", q]
        cmd[1:1] = ["-E"] if regex else ["-F"]
        if not case:
            cmd.insert(1, "-i")
        if context:
            cmd[1:1] = [f"-C{context}"]
        cmd += ["--", path or "."]
        code, out, err = _git(d, *cmd, timeout=60)
        if code not in (0, 1):
            raise ReadError(f"search failed: {(err or out).strip()[:200]}")
        for line in out.splitlines():
            if line == "--":
                continue
            # git grep --null: "path\0line\0text"; context lines come back as "path\0line\0text" too,
            # so a context line is told from a match by re-checking the pattern below.
            m = re.match(r"^([^\0]+)\0(\d+)\0(.*)$", line)
            if not m or _is_secret(m.group(1)):
                continue
            rel, no, txt = m.groups()
            hits.append({"repo": full, "path": rel, "line": int(no), "match": (not context) or bool(pat.search(txt)),
                         "text": txt[:300]})
            per_repo[full] = per_repo.get(full, 0) + 1
            if len(hits) >= limit * (1 + 2 * context):
                break
        if len(hits) >= limit * (1 + 2 * context):
            break
    return {"query": q, "regex": regex, "repos_searched": len(repos), "count": len(hits),
            "limit": limit, "truncated": len(hits) >= limit * (1 + 2 * context), "per_repo": per_repo,
            "hits": hits}


def status():
    out = []
    for o in sorted(CACHE.glob("*")):
        for r in sorted(o.glob("*")):
            if (r / ".git").exists():
                size = sum(f.stat().st_size for f in r.rglob("*") if f.is_file() and ".git" not in f.parts)
                out.append({"repo": f"{o.name}/{r.name}", "size_mb": round(size / 1e6, 1),
                            "age_seconds": int(time.time() - (r / ".git").stat().st_mtime)})
    return {"cache": str(CACHE), "repos": out}


def list_repos(limit=200):
    code, out, err = _run(["gh", "repo", "list", OWNER, "--limit", str(limit), "--json",
                           "name,nameWithOwner,description,isPrivate,diskUsage,updatedAt"], timeout=30)
    if code != 0:
        raise ReadError(f"GitHub read failed: {(err or out).strip()[:200]}")
    return {"repos": json.loads(out)}


# ------------------------------------------------------------------------------ routes

def _flag(name):
    return (request.args.get(name) or "").lower() in ("1", "true", "yes")


def register(app):
    def wrap(fn):
        try:
            return jsonify(ok=True, **fn())
        except ReadError as exc:
            return jsonify(ok=False, error=str(exc)), 400
        except subprocess.TimeoutExpired:
            return jsonify(ok=False, error="timed out"), 504
        except Exception as exc:
            return jsonify(ok=False, error=f"{type(exc).__name__}: {exc}"), 500

    @app.get("/api/repo/list")
    def repo_list():
        return wrap(lambda: list_repos())

    @app.get("/api/repo/status")
    def repo_status():
        return wrap(status)

    @app.get("/api/repo/sync")
    def repo_sync():
        return wrap(lambda: sync(request.args.get("repo"), big=_flag("big"), force=_flag("force")))

    @app.get("/api/repo/tree")
    def repo_tree():
        return wrap(lambda: tree(request.args.get("repo"), request.args.get("path", ""),
                                 request.args.get("q", "")))

    @app.get("/api/repo/read")
    def repo_read():
        return wrap(lambda: read(request.args.get("repo"), request.args.get("path", ""),
                                 request.args.get("start"), request.args.get("end")))

    @app.get("/api/repo/search")
    def repo_search():
        return wrap(lambda: search(request.args.get("repo"), request.args.get("q", ""),
                                   regex=_flag("regex"), path=request.args.get("path", ""),
                                   case=_flag("case"), context=request.args.get("context", 0),
                                   limit=request.args.get("limit", MAX_HITS)))

    return app


# ------------------------------------------------------------------------------ chat

_SEARCH = re.compile(r"^\W*(please\W+)?(search|grep|find)\s+(in\s+)?(?P<repo>[\w./-]+)\s+for\s+(?P<q>.+?)\W*$", re.I)
_READ = re.compile(r"^\W*(please\W+)?(read|show|cat)\s+(?P<repo>[\w.-]+(/[\w.-]+)?)[:\s]\s*(?P<path>[\w./@+-]+)"
                   r"(\s+lines?\s+(?P<s>\d+)\s*(-|to)\s*(?P<e>\d+))?\W*$", re.I)
_TREE = re.compile(r"^\W*(please\W+)?(tree|list files( of| in)?|files of)\s+(?P<repo>[\w.-]+(/[\w.-]+)?)"
                   r"(\s+(under|in|path)\s+(?P<path>[\w./-]+))?\W*$", re.I)
_SYNC = re.compile(r"^\W*(please\W+)?(sync|refresh|mirror|clone)\s+(?P<repo>[\w.-]+(/[\w.-]+)?)\W*$", re.I)


def chat_repo_command(text):
    """A chat line asking to tree / read / search / sync a repository -> the answer, else None. No model."""
    t = (text or "").strip()
    try:
        m = _SYNC.match(t)
        if m:
            r = sync(m["repo"], force=True)
            return f"{r['repo']}: {r['state']}."
        m = _SEARCH.match(t)
        if m:
            r = search(m["repo"], m["q"].strip("\"' "))
            if not r["count"]:
                return f"No match for “{m['q']}” in {m['repo']}."
            lines = [f"{r['count']} match(es){' (cut)' if r['truncated'] else ''} for “{m['q']}”:"]
            lines += [f"{h['repo']}/{h['path']}:{h['line']}: {h['text'].strip()}" for h in r["hits"][:40]]
            if r["count"] > 40:
                lines.append(f"... and {r['count'] - 40} more (GET /api/repo/search for all)")
            return "\n".join(lines)
        m = _READ.match(t)
        if m:
            r = read(m["repo"], m["path"], m["s"], m["e"])
            head = f"{r['repo']}/{r['path']} ({r.get('lines_total', '?')} lines)"
            return head + "\n```\n" + r["content"] + "\n```" + (f"\n{r['next']}" if r.get("next") else "")
        m = _TREE.match(t)
        if m:
            r = tree(m["repo"], m["path"] or "")
            lines = [f"{r['repo']}: {r['count']} file(s)"]
            lines += [f"{f['path']}  ({f['size']} B)" for f in r["files"][:150]]
            if r["count"] > 150:
                lines.append(f"... and {r['count'] - 150} more (GET /api/repo/tree?q=... to filter)")
            return "\n".join(lines)
    except ReadError as exc:
        return f"Repository reader: {exc}"
    except Exception as exc:
        return f"Repository reader failed: {type(exc).__name__}: {exc}"
    return None
