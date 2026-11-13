"""Queen's hand: make a code repository public, the three secret checks first (13.11.2026).

Marko, 13.11.2026: "Make the repository public, and then build and keep it public. We have private repositories for data
only, and the pure code of the application is always public." Rule: MANTRA_MANIFEST modules/building-repos-public.md.

Chat:  make repo public <REPO>
  1. check 1, patterns: key formats, password/token assignments, key-like file names, emails, phone numbers
  2. check 2, exact values: every secret-looking value in his key stores against the tracked files AND the whole history
     (git log -p --all), by value, printed masked
  3. check 3, what goes out: commit author/committer addresses, workflow secrets by name only
  A key found anywhere: STOP, nothing goes public. Only personal addresses found: a proposal to rewrite the history
  (author and committer -> the GitHub no-reply address, the addresses masked in every file of every commit, one
  force-push to main), then the proposal to flip it public (the note must say Marko asked), then the last failed build is
  run again and watched to its colour.
"""
import glob
import json
import os
import re
import shlex
import subprocess
import time
from pathlib import Path

NOREPLY = "213746898+markoboskoauroville@users.noreply.github.com"
KEY_STORES = ["~/Downloads/API", "~/.config/mantra", "~/.config/chromium-vm", "~/.config/mantra-door.token"]
PAT_KEYS = (r"gsk_[A-Za-z0-9]{20}|sk-ant-|sk-[A-Za-z0-9]{30}|ghp_[A-Za-z0-9]{20}|github_pat_|AKIA[0-9A-Z]{16}|"
            r"AIza[0-9A-Za-z_-]{30}|xox[abp]-|PRIVATE KEY-----|SM[0-9a-f]{32}|AC[0-9a-f]{32}")
PAT_ASSIGN = r"(password|passwd|secret|api_key|apikey|token)\s*[:=]\s*['\"][^'\"$ ]{8,}['\"]"
PAT_EMAIL = r"[A-Za-z0-9._%+-]+@(?:gmail|auroville|yahoo|hotmail|icloud|outlook)(?:\.[a-z]+)+"
PAT_PHONE = r"\+385 ?9[1-9] ?\d{3} ?\d{3,4}|\b09[1-9] ?\d{3} ?\d{3,4}\b"   # any Croatian mobile, no real number here


def _run(cmd, cwd=None, timeout=900, env=None):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
    return p.returncode, p.stdout + p.stderr


def _mask(v):
    return v[:4] + "…" + v[-2:] if len(v) > 8 else "…"


def check(d, refs="--all"):
    """The three checks. Returns {keys: [...], personal: [...], authors: [...], secrets_named: [...]}."""
    out = {"keys": [], "personal": [], "authors": [], "secrets_named": [], "values_checked": 0}
    _, hits = _run(["git", "grep", "-n", "-I", "-E", PAT_KEYS], cwd=d)
    out["keys"] += [f"pattern {l.split(':')[0]}:{l.split(':')[1]}" for l in hits.splitlines() if l.count(":") >= 2]
    _, hits = _run(["git", "grep", "-n", "-I", "-i", "-E", PAT_ASSIGN], cwd=d)
    out["keys"] += [f"assignment {l.split(':')[0]}:{l.split(':')[1]}" for l in hits.splitlines() if l.count(":") >= 2]
    _, names = _run(["git", "log", "--all", "--name-only", "--format="], cwd=d)
    bad = {n for n in names.split() if re.search(r"(^|/)\.env$|\.pem$|\.p12$|\.keystore$|\.jks$|id_rsa|credentials", n)}
    out["keys"] += [f"file name {n}" for n in sorted(bad)]
    # 2. exact values from the key stores, against files and history
    vals = set()
    for root in (os.path.expanduser(p) for p in KEY_STORES):
        files = [root] if os.path.isfile(root) else glob.glob(root + "/**/*", recursive=True)
        for f in files:
            if not os.path.isfile(f) or os.path.getsize(f) > 2_000_000 or f.endswith((".md", ".sh", ".py")):
                continue                        # scripts in the key folder carry code words, not keys
            try:
                t = open(f, errors="ignore").read()
            except OSError:
                continue
            for v in re.findall(r"[A-Za-z0-9_\-+/=.]{16,}", t):
                if re.search(r"\d", v) and re.search(r"[A-Za-z]", v) and not v.startswith(("http", "/Users")):
                    vals.add(v)
    out["values_checked"] = len(vals)
    _, tracked = _run(["git", "grep", "-I", "-h", "-o", "-E", r"[A-Za-z0-9_+/=.-]{16,}"], cwd=d)
    _, hist = _run(["git", "log", "-p", refs], cwd=d)
    for v in vals:
        if v in tracked or v in hist:
            out["keys"].append(f"exact value {_mask(v)} ({'tracked' if v in tracked else 'history'})")
    # personal details (not keys): emails, phone, in files and history
    for pat in (PAT_EMAIL, PAT_PHONE):
        _, files_now = _run(["git", "grep", "-h", "-o", "-I", "-E", pat], cwd=d)
        out["personal"] += [m.group(0) for m in re.finditer(pat, hist + "\n" + files_now)]
    out["personal"] = sorted(set(out["personal"]))
    _, authors = _run(["git", "log", refs, "--format=%ae%n%ce"], cwd=d)
    out["authors"] = sorted({a for a in authors.split() if a and a != NOREPLY and "noreply" not in a})
    for wf in (Path(d) / ".github" / "workflows").glob("*.y*ml"):
        out["secrets_named"] += re.findall(r"secrets\.([A-Z0-9_]+)", wf.read_text())
    return out


def rewrite(d, personal, authors):
    """Author/committer -> no-reply; every personal address masked in every file of every commit; force-push main."""
    env_filter = (f'for v in GIT_AUTHOR_EMAIL GIT_COMMITTER_EMAIL; do eval e=\\${{$v}}; case "$e" in *noreply*) ;; '
                  f'*) export $v="{NOREPLY}";; esac; done')
    # shlex.quote, never repr: repr doubled every backslash and nothing was masked (13.11.2026, caught on a scratch copy)
    tree = ("git ls-files -z | xargs -0 grep -I -l -E " + shlex.quote("|".join(re.escape(p) for p in personal)) +
            " 2>/dev/null | while read f; do perl -pi -e " + shlex.quote(_perl(personal)) + ' "$f"; done; true')
    env = dict(os.environ, FILTER_BRANCH_SQUELCH_WARNING="1")
    _run(["git", "config", "user.email", NOREPLY], cwd=d)
    code, out = _run(["git", "filter-branch", "-f", "--env-filter", env_filter, "--tree-filter", tree,
                      "--msg-filter", "perl -pe " + shlex.quote(_perl(personal)), "--", "--all"], cwd=d, timeout=3600, env=env)
    if code:
        raise RuntimeError(f"filter-branch failed: {out[-400:]}")
    _run(["rm", "-rf", ".git/refs/original"], cwd=d)
    _run(["git", "reflog", "expire", "--expire=now", "--all"], cwd=d)
    _run(["git", "gc", "-q", "--prune=now"], cwd=d)
    left = check(d, "--branches")      # the remote-tracking refs still show the old history until the push
    if left["personal"] or left["authors"]:
        raise RuntimeError(f"after the rewrite still found: {left['personal'][:5]} {left['authors'][:3]}")
    code, out = _run(["git", "push", "--force", "origin", "main"], cwd=d)
    if code:
        raise RuntimeError(f"force-push failed: {out[-300:]}")
    _, tags = _run(["git", "tag"], cwd=d)
    if tags.strip():
        _run(["git", "push", "--force", "--tags", "origin"], cwd=d)
    return True


def _perl(personal):
    # "@" and "$" must be escaped for perl, or "@gmail" is read as an array and nothing is masked
    return "; ".join("s/" + re.escape(p).replace("@", "\\@").replace("$", "\\$").replace("/", "\\/") + "/[address removed]/g"
                     for p in personal)


def make_public(repo, chat):
    import supervisor  # noqa: PLC0415
    from rename_skill import _slug, repo_dir, watch_run  # noqa: PLC0415
    d = repo_dir(repo)
    slug = _slug(d)
    _, vis = _run(["gh", "repo", "view", slug, "--json", "visibility", "-q", ".visibility"])
    _, st = _run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=d)
    if st.strip():
        chat.say(f"Stopped: {d.name} has uncommitted changes:\n{st[:400]}")
        raise RuntimeError("uncommitted changes")
    _run(["git", "pull", "-q", "--ff-only", "origin", "main"], cwd=d)
    r = check(d)
    chat.say(f"Three checks on {slug} ({vis.strip()}):\n1. patterns and file names: {len([k for k in r['keys'] if not k.startswith('exact')])} hits\n"
             f"2. exact values: {r['values_checked']} values from the key stores, {len([k for k in r['keys'] if k.startswith('exact')])} found\n"
             f"3. published: authors {r['authors'] or 'no-reply only'}; personal addresses {len(r['personal'])}; "
             f"workflow secrets by name {sorted(set(r['secrets_named'])) or 'none'}\n" + "\n".join(r["keys"][:20]))
    if r["keys"]:
        chat.say("STOP: something key-shaped is in the repository. Nothing goes public. Claude Code and Marko look at it.")
        raise RuntimeError("key-shaped finding")
    if r["personal"] or r["authors"]:
        plan = (f"Rewrite the whole history of {slug}: author and committer -> {NOREPLY}; "
                f"{len(r['personal'])} addresses masked as [address removed] in every file and message; one force-push to main.")
        supervisor.propose_and_wait(chat.title, "rewrite history", plan, plan + "\n(masked list kept local)")
        rewrite(d, r["personal"], r["authors"])
        chat.say("History rewritten and force-pushed; checked again: no personal address, no author address left.")
    if vis.strip() != "PUBLIC":
        note = supervisor.propose_and_wait(chat.title, "make public", f"{slug} -> PUBLIC",
                                           "OUTWARD: the code becomes public. Approve only with a note saying Marko asked.")
        if "marko" not in (note or "").lower():
            raise RuntimeError("the approval note does not say Marko asked")
        code, out = _run(["gh", "repo", "edit", slug, "--visibility", "public", "--accept-visibility-change-consequences"])
        if code:
            raise RuntimeError(f"visibility change failed: {out[-300:]}")
        _run(["gh", "repo", "edit", slug, "--description", ""])
    _, vis = _run(["gh", "repo", "view", slug, "--json", "visibility", "-q", ".visibility"])
    chat.say(f"Visibility now: {vis.strip()}.")
    # the build again
    _, wfs = _run(["gh", "workflow", "list", "-R", slug, "--json", "name,id", "-q", ".[].id"])
    for wid in wfs.split():
        _run(["gh", "workflow", "run", wid, "-R", slug, "--ref", "main"])
    time.sleep(8)
    _, sha = _run(["git", "rev-parse", "HEAD"], cwd=d)
    colour, url = watch_run(slug, sha.strip(), chat)
    chat.say(f"Build: {colour.upper()} {url}\nTask finished.")
    return {"repo": slug, "visibility": vis.strip(), "build": colour, "run": url}


_CHAT = re.compile(r"^\s*make\s+repo\s+public\s+(?P<repo>[\w./-]+)\s*$", re.I)


def chat_publish_command(text):
    m = _CHAT.match((text or "").strip())
    if not m:
        return None
    from rename_skill import _task  # noqa: PLC0415
    repo = m.group("repo")
    return _task(f"Make {repo.split('/')[-1]} public (three checks first)", lambda c: make_public(repo, c), repo)
