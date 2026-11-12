"""Queen's skill: put a photo on one of Marko's websites, small enough for the web, every change approved first.

Marko, 12.11.2026: "Please make this photo small size, good for web, and add it to the photo gallery inside my website
Kukljica Eco Oasis." Then: "please teach Queen how to do this. Now you need to supervise her before each move. She's going to
ask approval from you, so she doesn't mess up my website." And: "Open the new chat with the title of the task."

    POST /api/skills/web-photo {source, repo:"KUKLJICA_ECOOASIS", title?}
    chat: "add <path> to the gallery of Kukljica"   (a path to an image + the word gallery)

The steps (the ones marked SUPERVISED wait for `queen approve <id>` from a Claude Code session; a reject stops the task):
  1. look      the source size; a web copy in ~/.groq/work (2400 px wide JPEG, quality lowered until <= 450 KB);
               her eyes write the caption in English and Croatian and the alt text
  2. PLAN      SUPERVISED: the file name, size, where on the page (an existing gallery section, or a new one before
               "join"), the captions
  3. CHANGE    SUPERVISED: the exact diff of index.html and the new image file, prepared in a copy first
  4. check     build.sh must pass; sections still balanced
  5. DEPLOY    SUPERVISED: commit message and files; then commit and push (GitHub Actions publishes the site)
  6. verify    the live page answers and carries the image; the link goes into the task chat
"""
import difflib
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from flask import jsonify, request

WORK = Path.home() / ".groq" / "work"
SITES = {"KUKLJICA_ECOOASIS": {"dir": Path.home() / "Developer" / "KUKLJICA_ECOOASIS",
                               "live": "https://markoboskoauroville.github.io/KUKLJICA_ECOOASIS/",
                               "name": "Kukljica EcoOasis"}}
MAX_KB = 450
WIDTH = 2400

SECTION_HTML = """<section id="gallery"><div class="wrap"><div class="slab"></div>
  <div class="kicker" data-i18n="gal.kicker"></div>
  <h2 data-i18n="gal.h"></h2>
{figure}
  <!-- gallery:end -->
</div></section>

"""
FIGURE_HTML = ('  <figure class="pano"><img src="img/{file}" alt="{alt}" loading="lazy" width="{w}" height="{h}">'
               '<figcaption data-i18n="{key}"></figcaption></figure>\n')
CSS = ".pano{margin:34px 0}.pano img{width:100%;height:auto;display:block}\n"


class WebPhotoError(Exception):
    pass


def _run(cmd, cwd=None, timeout=300):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _size(path):
    _, out = _run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)])
    w = re.search(r"pixelWidth:\s*(\d+)", out)
    h = re.search(r"pixelHeight:\s*(\d+)", out)
    return (int(w.group(1)), int(h.group(1))) if w and h else (0, 0)


def web_copy(src, name):
    """JPEG, WIDTH px wide (never upscaled), quality lowered step by step until it is <= MAX_KB."""
    WORK.mkdir(parents=True, exist_ok=True)
    out = WORK / name
    w, _h = _size(src)
    width = min(WIDTH, w or WIDTH)
    for q in (82, 76, 70, 64, 58):
        _run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", str(q), "-Z", str(width), str(src), "--out", str(out)])
        if out.exists() and out.stat().st_size <= MAX_KB * 1024:
            break
    if not out.exists():
        raise WebPhotoError("sips could not make the web copy")
    return out, q


def _slug(src):
    m = re.search(r"(20\d{2})(\d{2})(\d{2})", Path(src).name)
    kind = "panorama" if "pano" in Path(src).name.lower() else "photo"
    return f"{kind}-{m.group(1)}-{m.group(2)}-{m.group(3)}.jpg" if m else re.sub(r"[^a-z0-9]+", "-", Path(src).stem.lower())[:40] + ".jpg"


def _taken(src):
    """When the photo was taken, from the file (12.11.2026: her eyes guessed 'dawn' for a 12:45 photo)."""
    _, out = _run(["sips", "-g", "creation", str(src)])
    m = re.search(r"creation:\s*(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2})", out)
    if not m:
        return ""
    y, mo, d, hh, mm = m.groups()
    return f"{int(d)}.{int(mo)}.{y} at {hh}:{mm}"


def _captions(path, pool, record_spend, taken=""):
    import vision  # noqa: PLC0415
    q = ("This photo goes into the photo gallery of 'Kukljica EcoOasis', an ecosystem restoration site on the island of Ugljan, "
         "Croatia. " + (f"It was taken on {taken} (use this for the time of day and season; do not guess). " if taken else "") +
         "Write a short caption (one sentence, plain, no hype) in English and in correct Croatian, and a short alt text in "
         "English. Describe only what is seen; do NOT name a ridge, bay or place you cannot verify from the picture. "
         'JSON only: {"caption_en":"...","caption_hr":"...","alt":"..."}')
    r = vision.ask({"path": str(path), "question": q, "json": True, "max_tokens": 2000}, pool, record_spend)
    j = r.get("json") or {}
    if not j.get("caption_en"):
        raise WebPhotoError("her eyes gave no caption")
    return j


def _dict_insert(html, lang, pairs):
    """Add "key":"value" pairs right after `en:{` / `hr:{` (the site's dictionaries, one per language)."""
    marker = f"\n{lang}:{{\n"
    i = html.find(marker)
    if i < 0:
        raise WebPhotoError(f"no {lang}:{{ dictionary in index.html")
    line = ",".join(f"{json.dumps(k)}:{json.dumps(v, ensure_ascii=False)}" for k, v in pairs) + ",\n"
    j = i + len(marker)
    return html[:j] + line + html[j:]


def plan_edit(html, file, alt, w, h, cap_en, cap_hr):
    """The new index.html: into the existing gallery, or a new gallery section before 'join'."""
    n = len(re.findall(r'data-i18n="gal\.c\d+"', html)) + 1
    key = f"gal.c{n}"
    fig = FIGURE_HTML.format(file=file, alt=alt.replace('"', "'"), w=w, h=h, key=key)
    if "<!-- gallery:end -->" in html:
        new = html.replace("  <!-- gallery:end -->", fig + "  <!-- gallery:end -->", 1)
        where = "into the existing Photo gallery section"
        pairs_en, pairs_hr = [(key, cap_en)], [(key, cap_hr)]
    else:
        anchor = '<section id="join">'
        if anchor not in html:
            raise WebPhotoError("no section 'join' to put the new gallery before")
        new = html.replace(anchor, SECTION_HTML.format(figure=fig.rstrip("\n")) + anchor, 1)
        if ".pano{" not in new:
            new = new.replace("/* gallery */\n", "/* gallery */\n" + CSS, 1)
        where = "a NEW section 'Photo gallery / Fotogalerija' just before 'join' (the site had no general gallery)"
        pairs_en = [("gal.kicker", "Photo gallery"), ("gal.h", "Views of the land"), (key, cap_en)]
        pairs_hr = [("gal.kicker", "Fotogalerija"), ("gal.h", "Pogledi na posjed"), (key, cap_hr)]
    new = _dict_insert(new, "en", pairs_en)
    new = _dict_insert(new, "hr", pairs_hr)
    return new, where, key


def run(source, repo="KUKLJICA_ECOOASIS", title=None, pool=None, record_spend=None):
    import supervisor  # noqa: PLC0415
    from task_chat import TaskChat  # noqa: PLC0415
    site = SITES.get(repo)
    if not site:
        raise WebPhotoError(f"no site profile for {repo}")
    src = Path(source).expanduser()
    if not src.is_file():
        raise WebPhotoError(f"no file {src}")
    title = title or f"{site['name']}: {src.name} to the photo gallery"
    chat = TaskChat(title)
    d = site["dir"]
    code, out = _run(["git", "status", "--porcelain"], cwd=d)
    if out.strip():
        chat.say(f"Stopped: the repository has uncommitted changes, I do not mix my work into them:\n{out[:500]}")
        raise WebPhotoError("the site repository has uncommitted changes")
    _run(["git", "pull", "--ff-only", "-q"], cwd=d)

    # 1. look
    sw, sh = _size(src)
    name = _slug(src)
    if (d / "img" / name).exists():
        name = name.replace(".jpg", "-2.jpg")
    copy, q = web_copy(src, name)
    w, h = _size(copy)
    kb = round(copy.stat().st_size / 1024)
    taken = _taken(src)
    caps = _captions(copy, pool, record_spend, taken)
    chat.say(f"Source: {src} ({sw} x {sh} px, {round(src.stat().st_size / 1e6)} MB). Web copy: {name}, {w} x {h} px, "
             f"{kb} KB, JPEG quality {q}.\nCaption EN: {caps['caption_en']}\nCaption HR: {caps['caption_hr']}\nAlt: {caps['alt']}")

    html = (d / "index.html").read_text(encoding="utf-8")
    new, where, key = plan_edit(html, name, caps["alt"], w, h, caps["caption_en"], caps["caption_hr"])

    # 2. PLAN
    plan = (f"Site {site['name']} ({repo}). Add img/{name} ({w} x {h} px, {kb} KB) {where}.\n"
            f"Caption EN: {caps['caption_en']}\nCaption HR: {caps['caption_hr']}\nThe panorama keeps its shape (no crop).")
    chat.say("Asking Claude Code to approve the PLAN:\n" + plan)
    note = supervisor.propose_and_wait(title, "plan", f"add img/{name} {where}", plan +
                                       '\n\n(Approve with corrections: a note like {"caption_en":"...","caption_hr":"...","alt":"..."})')
    chat.say("PLAN approved." + (f" Note: {note}" if note else ""))
    fix = re.search(r"\{.*\}", note or "", re.S)
    if fix:                                   # the supervisor's corrections win over her own words
        try:
            caps.update({k: v for k, v in json.loads(fix.group(0)).items() if k in ("caption_en", "caption_hr", "alt") and v})
            new, where, key = plan_edit(html, name, caps["alt"], w, h, caps["caption_en"], caps["caption_hr"])
            chat.say(f"Corrections applied:\nCaption EN: {caps['caption_en']}\nCaption HR: {caps['caption_hr']}\nAlt: {caps['alt']}")
        except Exception as exc:
            chat.say(f"The corrections could not be read ({exc}); I stop.")
            raise WebPhotoError("unreadable corrections in the approval note")

    # 3. CHANGE
    diff = "".join(difflib.unified_diff(html.splitlines(True), new.splitlines(True), "index.html", "index.html", n=1))
    chat.say("Asking Claude Code to approve the CHANGE (diff below):\n" + diff[:6000])
    note = supervisor.propose_and_wait(title, "change", f"index.html (+{diff.count(chr(10) + '+')} lines) and img/{name}",
                                       f"new file img/{name} ({kb} KB)\n\n{diff}")
    shutil.copy2(copy, d / "img" / name)
    (d / "index.html").write_text(new, encoding="utf-8")
    chat.say("CHANGE approved and written." + (f" Note: {note}" if note else ""))

    # 4. check
    code, out = _run(["bash", "build.sh"], cwd=d)
    opened, closed = new.count("<section"), new.count("</section>")
    if code != 0 or opened != closed:
        _run(["git", "checkout", "--", "index.html"], cwd=d)
        (d / "img" / name).unlink(missing_ok=True)
        chat.say(f"Check FAILED, the change is undone. build.sh: {out[-300:]} sections {opened}/{closed}")
        raise WebPhotoError("the build check failed; nothing was kept")
    _run(["rm", "-rf", "dist"], cwd=d)
    chat.say(f"Check passed: {out.strip().splitlines()[-1] if out.strip() else 'build ok'}; sections {opened}/{closed}.")

    # 5. DEPLOY
    msg = f"Gallery: {name} ({caps['caption_en'][:60]})"
    _, st = _run(["git", "status", "--short"], cwd=d)
    chat.say(f"Asking Claude Code to approve the DEPLOY (commit and push to main = the live site):\n{msg}\n{st}")
    supervisor.propose_and_wait(title, "deploy", msg, f"commit: {msg}\nfiles:\n{st}")
    _run(["git", "add", "index.html", f"img/{name}"], cwd=d)
    code, out = _run(["git", "commit", "-q", "-m", msg + "\n\nMade by Queen (Groq AI Studio), each step approved by Claude Code."], cwd=d)
    if code != 0:
        raise WebPhotoError(f"commit failed: {out[-300:]}")
    code, out = _run(["git", "push", "-q", "origin", "main"], cwd=d)
    if code != 0:
        raise WebPhotoError(f"push failed: {out[-300:]}")
    chat.say("Pushed to main; GitHub Actions publishes the site now.")

    # 6. verify
    import urllib.request  # noqa: PLC0415
    live, seen = site["live"], False
    for _ in range(40):
        time.sleep(15)
        try:
            with urllib.request.urlopen(live + f"?v={int(time.time())}", timeout=20) as r:
                if f"img/{name}" in r.read().decode("utf-8", "replace"):
                    seen = True
                    break
        except Exception:
            pass
    chat.say((f"Live: {live}#gallery carries img/{name}." if seen else f"Not yet seen on {live} after 10 min; check the Actions run.")
             + "\nTask finished.")
    return {"chat": chat.id, "title": title, "file": f"img/{name}", "kb": kb, "size": [w, h], "live": live + "#gallery",
            "seen_live": seen, "captions": caps}


def register(app, pool, record_spend):
    @app.post("/api/skills/web-photo")
    def web_photo():
        d = request.get_json(silent=True) or {}
        import supervisor  # noqa: PLC0415
        try:
            return jsonify(ok=True, **run(d.get("source", ""), d.get("repo") or "KUKLJICA_ECOOASIS", d.get("title"), pool, record_spend))
        except supervisor.Rejected as exc:
            return jsonify(ok=False, stopped=str(exc)), 409
        except WebPhotoError as exc:
            return jsonify(ok=False, error=str(exc)), 400
        except Exception as exc:
            return jsonify(ok=False, error=f"{type(exc).__name__}: {exc}"), 500
    return app


_CHAT = re.compile(r"(?P<path>(~|/Users/)[^\n]*?\.(tiff?|jpe?g|png|heic))\b.*\b(gallery|galerij)", re.I | re.S)


def chat_web_photo_command(text, pool, record_spend):
    m = _CHAT.search(text or "")
    if not m or not re.search(r"kuk|eco ?oasis", text or "", re.I):
        return None
    import supervisor  # noqa: PLC0415
    try:
        r = run(m.group("path").strip(), "KUKLJICA_ECOOASIS", None, pool, record_spend)
    except supervisor.Rejected as exc:
        return f"Stopped, nothing more was changed: {exc}"
    return (f"Done, every step approved by Claude Code: {r['file']} ({r['kb']} KB, {r['size'][0]} x {r['size'][1]}) is in the "
            f"photo gallery: {r['live']}" + ("" if r["seen_live"] else " (not yet seen live)"))
