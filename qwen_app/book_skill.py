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
    import cost_gate  # noqa: PLC0415
    cost_gate.require("queen-book", "book chapter text with Groq", 0.01)
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
        # 13.11.2026: switching accounts opened other profiles' windows, and some profiles fail to open ("Something went
        # wrong when opening your profile", again and again while Marko worked). Only the profile whose window is already
        # open draws now (the first account); no profile window is opened for a picture.
        acct = accounts[0]
        t0 = time.time()
        for attempt in range(1, 4):   # Chrome sometimes does not answer its DevTools door (13.11.2026): wait, try again
            try:
                r = make_image(prompt, None, str(out.with_suffix(".png")), account=acct, wait=240, max_accounts=1)
                break
            except Exception as exc:
                if "cannot reach Chrome" not in str(exc) or attempt == 3:
                    raise
                chat.say(f"Plate {name}: Chrome did not answer (try {attempt}); trying again in 20 s.")
                time.sleep(20)
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
    # the drawing runs in its own queue beside the writing; the book is built only when the drawing is done (13.11.2026)
    from rename_skill import _QUEUES  # noqa: PLC0415
    q = _QUEUES.get(f"{repo}-draw".lower())
    if q and q["n"] > 0:
        chat.say("Waiting for the drawing to finish before building.")
        with q["lock"]:
            pass
    code, out = _run(["python3", "build.py"], cwd=d)
    chat.say(f"Build {'OK' if code == 0 else 'FAILED'}: {out.strip()[-600:]}\nTask finished.")
    if code:
        raise RuntimeError("build.py failed")
    return json.loads(out.strip().splitlines()[-1])


# ---------- add bowl ----------

BOWL_KIT = DEV / "MANTRA_MANIFEST" / "kits" / "donation-bowl"
NO_BOWL = ("markobosko", "djmantra", "djmantraapp")      # Marko: every page "except my own biography and my dj mantra"


def add_bowl(repo, chat):
    """Marko, 13.11.2026: "Donation ball comes to every of my pages ... For the books, donation yes ... attach donation balls
    to all of my books which are on Cloudflare." A book from book_template gets it from its build; any other page gets the
    kit's block before its footer (or before </body>), the bowl and QR pictures beside it."""
    import supervisor  # noqa: PLC0415
    from rename_skill import repo_dir, SkillError  # noqa: PLC0415
    try:
        d = repo_dir(repo)
    except SkillError:
        d = DEV / repo.split("/")[-1]
        code, out = _run(["python3", str(DEV / "DOWNLOAD_MONITOR" / "dlmon.py"), "add", f"clone-{d.name}", "--name",
                          f"git clone {d.name} (Queen)", "--want-mb", "20", "--info", "for the donation bowl"])
        code, out = _run(["gh", "repo", "clone", f"markoboskoauroville/{d.name}", str(d)], timeout=600)
        if code:
            raise RuntimeError(f"clone failed: {out[-300:]}")
        chat.say(f"Cloned {d.name}.")
    if d.name.lower() in NO_BOWL:
        raise RuntimeError(f"{d.name}: no bowl here (Marko's biography and DJ Mantra are the exceptions)")
    if (d / "book.json").exists() and (d / "build.py").exists():
        shutil.copy2(TEMPLATE / "build.py", d / "build.py")              # the template's build carries the bowl
        code, out = _run(["python3", "build.py"], cwd=d)
        ok = code == 0 and "mantra-bowl" in (d / "index.html").read_text(encoding="utf-8")
        chat.say(f"{d.name}: the book's build now carries the bowl ({'checked in index.html' if ok else 'NOT found after build'}).")
        if not ok:
            raise RuntimeError("the bowl is not in the built page")
        return {"repo": d.name, "how": "book build"}
    pages = [p for p in d.rglob("index.html") if ".git" not in p.parts and "node_modules" not in p.parts]
    if not pages:
        raise RuntimeError(f"{d.name}: no index.html")
    page = min(pages, key=lambda p: len(p.parts))                       # the top-most page
    html_text = page.read_text(encoding="utf-8")
    if "mantra-bowl" in html_text:
        chat.say(f"{d.name}: {page.relative_to(d)} already has the bowl.\nTask finished.")
        return {"repo": d.name, "how": "already"}
    block = (BOWL_KIT / "donation-bowl.html").read_text(encoding="utf-8")
    at = html_text.rfind("<footer")
    at = at if at != -1 else html_text.rfind("</body>")
    new = html_text[:at] + block + "\n" + html_text[at:]
    plan = f"{d.name}: the bowl block into {page.relative_to(d)} before its {'footer' if '<footer' in html_text else '</body>'}; tibetan-bowl.jpg and revolut-qr.png into {(page.parent / 'img').relative_to(d)}/"
    chat.say("Plan: " + plan)
    supervisor.propose_and_wait(chat.title, "bowl", plan, plan)
    page.write_text(new, encoding="utf-8")
    (page.parent / "img").mkdir(exist_ok=True)
    for f in ("tibetan-bowl.jpg", "revolut-qr.png"):
        shutil.copy2(BOWL_KIT / f, page.parent / "img" / f)
    chat.say(f"{d.name}: bowl added.\nTask finished.")
    return {"repo": d.name, "how": "inserted", "page": str(page.relative_to(d))}


# ---------- chat ----------

_NEW = re.compile(r"^\s*book\s+new\s+(?P<repo>[\w.-]+)\s*$", re.I)
_WRITE = re.compile(r"^\s*book\s+write\s+(?P<repo>[\w.-]+)\s+chapters?\s+(?P<n>\d+|all)\s*$", re.I)
_DRAW = re.compile(r"^\s*book\s+draw\s+(?P<repo>[\w.-]+)\s+(?P<w>\d+|all|cover)\s*$", re.I)
_BOWL = re.compile(r"^\s*add\s+bowl\s+(?P<repo>[\w./-]+)\s*$", re.I)
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
    m = _BOWL.match(t)
    if m:
        r = m.group("repo")
        return _task(f"Add bowl {r.split('/')[-1]}", lambda c: add_bowl(r, c), r)
    m = _BUILD.match(t)
    if m:
        r = m.group("repo")
        return _task(f"Book: build {r}", lambda c: build(r, c), r)
    return None
