"""Queen writes and illustrates books (13.11.2026).

Marko: "make another repository. Make a book. AI for beginners ... make drawings, sketches on cream paper with a pencil and
let queen do all the work ... in my style of design ... Cloudflare page ... called like the name of the book .pages.dev ...
illustrated by three Gemini accounts ... We generate the whole book for free ... Let's share the knowledge."

The plan (outline, facts, sources, the sketch style, the scene of every plate) is Claude Code's: books/<REPO>/ in this repo.
Queen's hands, chat commands answered locally:
    book new <REPO>                 a public repository ~/Developer/<REPO> from book_template + the plan (approval: outward)
    book write <REPO> chapter <n|all>   she writes each chapter with her own model from the plan and the sources; every
                                    chapter waits for the supervisor; a rejection's note goes into her next draft
    book draw <REPO> <n|all|cover>  a pencil sketch on cream paper per plate, Gemini in Marko's Chrome, free; the plates
                                    are spread over THREE accounts in turn (each one's next profile takes over if it is spent)
    book build <REPO>               build.py: the one-page book, BOOK.md, sitemap; reports what is still missing
Then `ship <REPO> "<message>"` and `deploy <REPO>` (Cloudflare Pages, the name in book.json).
"""
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

APP_REPO = Path.home() / "Developer" / "groq_ai_studio"
TEMPLATE = APP_REPO / "book_template"
PLANS = APP_REPO / "books"
DEV = Path.home() / "Developer"
MODEL = "qwen/qwen3.6-27b"
ACCOUNTS_FILE = Path.home() / ".groq" / "book_accounts.json"   # the three Gemini accounts: local only, never in a public repo
_CTX = {"pool": None, "spend": None}

WRITER = """You are Queen, writing one chapter of a free book for beginners.
THE READER: a curious sixteen-year-old who has just arrived from another planet and has never heard of computers that talk.
HOW TO WRITE:
- Plain, warm, exact English. Short sentences. Explain every technical word the first time, with an everyday comparison.
- Use the examples and the true story in the SOURCES. Every number, name, date and event must come from the FACTS or SOURCES;
  never invent one. If a fact is not there, write without it.
- Speak like a good teacher, not like an advertisement: no hype words (revolutionary, magic, game-changing), no emojis.
- 600 to 900 words. Markdown only: paragraphs, at most two ### subheadings, at most one short list. No title line.
- End with one line in bold that the reader should remember.
- Do not repeat what the earlier chapters already explained (their titles are given); refer back in one phrase if needed."""


def setup(pool, record_spend):
    _CTX["pool"], _CTX["spend"] = pool, record_spend


def _run(cmd, cwd=None, timeout=900):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout + p.stderr


def _plan(repo):
    p = PLANS / repo
    if not (p / "book.json").exists():
        raise RuntimeError(f"no plan for {repo}: Claude Code writes books/{repo}/book.json first")
    return p, json.loads((p / "book.json").read_text())


def _book_dir(repo):
    d = DEV / repo
    if not (d / "book.json").exists():
        raise RuntimeError(f"{d} is not a book yet: book new {repo}")
    return d, json.loads((d / "book.json").read_text())


def _complete(system, user):
    from groq import Groq  # noqa: PLC0415
    pool, last = _CTX["pool"], None
    for key in pool.candidates(MODEL):
        try:
            # the reasoning stays hidden (13.11.2026: an unclosed <think> leaked 2,900 words of thinking into chapter 1)
            r = Groq(api_key=key, max_retries=0).chat.completions.create(
                model=MODEL, temperature=0.4, max_tokens=4000, reasoning_effort="none",
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
            pool.good(key, MODEL)
            u = r.usage
            try:
                _CTX["spend"](MODEL, u.prompt_tokens, u.completion_tokens, f"book_{int(time.time() * 1000)}")
            except Exception:
                pass
            text = r.choices[0].message.content or ""
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
            if "<think>" in text:                      # unclosed: nothing before the end of the thinking is the answer
                text = text.split("</think>")[-1] if "</think>" in text else ""
            return text.strip()
        except Exception as exc:
            last = exc
            pool.cool(key, MODEL, exc)
    raise RuntimeError(f"no key could answer: {last}")


# ---------- book new ----------

def book_new(repo, chat):
    import supervisor  # noqa: PLC0415
    plan, b = _plan(repo)
    d = DEV / repo
    if d.exists():
        raise RuntimeError(f"{d} already exists")
    msg = (f"create the PUBLIC repository markoboskoauroville/{repo} (Marko: share the knowledge) for the book "
           f"'{b['title']}', live at https://{b['pages']}.pages.dev")
    chat.say("Plan: " + msg)
    supervisor.propose_and_wait(chat.title, "new repository", msg, msg)
    shutil.copytree(TEMPLATE, d)
    for item in plan.iterdir():
        if item.is_dir():
            shutil.copytree(item, d / item.name)
        else:
            shutil.copy2(item, d / item.name)
    (d / "chapters").mkdir(exist_ok=True)
    (d / "img").mkdir(exist_ok=True)
    (d / ".gitignore").write_text("dist/\n.DS_Store\n__pycache__/\n")
    _run(["git", "init", "-q", "-b", "main"], cwd=d)
    _run(["git", "config", "user.email", "213746898+markoboskoauroville@users.noreply.github.com"], cwd=d)
    _run(["git", "add", "-A"], cwd=d)
    _run(["git", "commit", "-q", "-m", f"{b['title']}: the plan, the template (Queen, 13.11.2026)"], cwd=d)
    code, out = _run(["gh", "repo", "create", f"markoboskoauroville/{repo}", "--public", "--source", str(d), "--push",
                      "--description", b["subtitle"], "--homepage", f"https://{b['pages']}.pages.dev"])
    if code:
        raise RuntimeError(f"gh repo create failed: {out[-300:]}")
    chat.say(f"Created and pushed: https://github.com/markoboskoauroville/{repo}\nTask finished.")
    return {"repo": repo, "dir": str(d)}


# ---------- book write ----------

def write_chapter(repo, n, chat):
    import supervisor  # noqa: PLC0415
    d, b = _book_dir(repo)
    ch = next(c for c in b["chapters"] if c["n"] == n)
    sources = "\n\n".join(f"### {p.name}\n{p.read_text(encoding='utf-8')}" for p in sorted((d / "sources").glob("*.md")))
    before = [c["title"] for c in b["chapters"] if c["n"] < n]
    notes_f = d / "notes" / f"{n:02d}.txt"
    notes = notes_f.read_text() if notes_f.exists() else ""
    user = (f"BOOK: {b['title']}: {b['subtitle']}\nCHAPTER {n}: {ch['title']}\nWHAT THIS CHAPTER MUST DO:\n{ch['brief']}\n"
            f"EARLIER CHAPTERS: {', '.join(before) or 'none, this is the first'}\n"
            + (f"\nCORRECTIONS FROM YOUR TEACHER ON YOUR LAST DRAFT (follow every one):\n{notes}\n" if notes else "")
            + f"\nSOURCES AND FACTS:\n{sources}")
    for _ in range(3):   # a draft that is empty, still thinking, or far too long is redone before the teacher sees it
        text = _complete(WRITER, user)
        words = len(text.split())
        if text and "<think>" not in text and 400 <= words <= 1100:
            break
        chat.say(f"Draft refused by her own check ({words} words): writing it again.")
    else:
        raise RuntimeError(f"chapter {n}: three drafts failed her own check (empty, thinking left in, or not 400-1100 words)")
    chat.say(f"Chapter {n} drafted ({words} words). Waiting for the teacher's review.\n\n{text[:5000]}")
    try:
        supervisor.propose_and_wait(chat.title, f"chapter {n}", f"{ch['title']} ({words} words)", text, timeout=3600)
    except supervisor.Rejected as exc:
        notes_f.parent.mkdir(exist_ok=True)
        notes_f.write_text((notes + "\n" if notes else "") + str(exc).split(": rejected by", 1)[-1])
        raise
    (d / "chapters" / f"{n:02d}.md").write_text(text + "\n", encoding="utf-8")
    chat.say(f"Chapter {n} approved and saved: chapters/{n:02d}.md")
    return {"chapter": n, "words": words}


# ---------- book draw ----------

def draw(repo, which, chat):
    from gemini_skill import make_image  # noqa: PLC0415
    d, b = _book_dir(repo)
    accounts = json.loads(ACCOUNTS_FILE.read_text())[:3]
    items = [("cover", b["cover_scene"])] if which in ("cover", "all") else []
    items += [(f"{c['n']:02d}", c["scene"]) for c in b["chapters"] if which == "all" or str(c["n"]) == str(which)]
    done = []
    for i, (name, scene) in enumerate(items):
        out = d / "img" / f"{name}.jpg"
        if out.exists() and which == "all":
            continue                                        # never generate the same picture twice
        prompt = f"{b['sketch_style']}\n\nThe scene: {scene}"
        acct = accounts[i % len(accounts)]                   # three accounts in turn
        t0 = time.time()
        r = make_image(prompt, None, str(out.with_suffix(".png")), account=acct, wait=240, max_accounts=3)
        png = Path(r["out"])
        _run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "82", "-Z", "1600", str(png), "--out", str(out)])
        png.unlink(missing_ok=True)
        kb = round(out.stat().st_size / 1024)
        chat.say(f"Plate {name}: {r['width']}x{r['height']} by {r['account']} in {round(time.time() - t0)} s, {kb} KB "
                 f"(tried: {', '.join(r.get('tried', []))})")
        done.append({"plate": name, "account": r["account"], "kb": kb})
    chat.say(f"{len(done)} plates drawn.\nTask finished.")
    return {"drawn": done}


# ---------- book build ----------

def build(repo, chat):
    d, _ = _book_dir(repo)
    code, out = _run(["python3", "build.py"], cwd=d)
    chat.say(f"Build {'OK' if code == 0 else 'FAILED'}: {out.strip()[-600:]}\nTask finished.")
    if code:
        raise RuntimeError("build.py failed")
    return json.loads(out.strip().splitlines()[-1])


# ---------- chat ----------

_NEW = re.compile(r"^\s*book\s+new\s+(?P<repo>[\w.-]+)\s*$", re.I)
_WRITE = re.compile(r"^\s*book\s+write\s+(?P<repo>[\w.-]+)\s+chapters?\s+(?P<n>\d+|all)\s*$", re.I)
_DRAW = re.compile(r"^\s*book\s+draw\s+(?P<repo>[\w.-]+)\s+(?P<w>\d+|all|cover)\s*$", re.I)
_BUILD = re.compile(r"^\s*book\s+build\s+(?P<repo>[\w.-]+)\s*$", re.I)


def chat_book_command(text):
    from rename_skill import _task  # noqa: PLC0415
    t = (text or "").strip()
    m = _NEW.match(t)
    if m:
        r = m.group("repo")
        return _task(f"Book: new {r}", lambda c: book_new(r, c), r)
    m = _WRITE.match(t)
    if m:
        r, n = m.group("repo"), m.group("n")

        def go(c):
            _, b = _book_dir(r)
            ns = [ch["n"] for ch in b["chapters"]] if n == "all" else [int(n)]
            import supervisor  # noqa: PLC0415
            res = []
            for k in ns:
                if n == "all" and (DEV / r / "chapters" / f"{k:02d}.md").exists():
                    continue
                # a "no" is not the end: she rewrites with the teacher's notes, up to three drafts (13.11.2026: the first
                # rejection stopped the whole book)
                for attempt in range(1, 4):
                    try:
                        res.append(write_chapter(r, k, c))
                        break
                    except supervisor.Rejected as exc:
                        c.say(f"Chapter {k}, draft {attempt} rejected: {exc}. Rewriting with the notes.")
                else:
                    raise RuntimeError(f"chapter {k}: three drafts rejected; the teacher writes the brief again")
            c.say("Task finished.")
            return {"written": res}
        return _task(f"Book: write {r} chapter {n}", go, r)
    m = _DRAW.match(t)
    if m:
        r, w = m.group("repo"), m.group("w")
        return _task(f"Book: draw {r} {w}", lambda c: draw(r, w, c), r + "-draw")
    m = _BUILD.match(t)
    if m:
        r = m.group("repo")
        return _task(f"Book: build {r}", lambda c: build(r, c), r)
    return None
