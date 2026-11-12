"""Queen's skill: describe every image of a website's repository, into an Excel workbook (12.11.2026).

Marko: "test her skills of describing images by taking all the images from Santoshi's website, describing them, and then in
the same folder, write an Excel sheet with the description of each image." And: "each image needs to have its own sheet,
i.e., tab, inside the sheet. On the tab, there is an image name, and inside is a description."

    POST /api/skills/describe-images {repo:"santoshi_band_site", project:"Santoshi poster", site:"https://..."}
    chat: "describe all images from the Santoshi website"

The workbook: an Index tab first (one row per image), then one tab per image named after the file (Excel allows 31
characters; longer names are shortened and the full name is on the tab). Thumbnails (*_t.*) are small copies of photos
already described and are listed, not described again; SVG cannot be shown to the model and is listed only.
Descriptions are cached (~/.groq/skill_cache/describe_<repo>.json): a second run costs nothing.
"""
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from flask import jsonify, request

CACHE = Path.home() / ".groq" / "skill_cache"
SITES = {"santoshi_band_site": "https://santoshi-band.pages.dev"}
EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif")

# 12.11.2026, first run: instruments named wrong ("dholak, tabla, ukulele" for djembe, mridangam, nylon guitar) and two
# AI-generated pictures called "photo". So the question now names the band's real instruments and the signs of AI pictures.
QUESTION = (
    "The SANTOSHI kirtan band has seven members; their instruments are: electric bass, djembe (hand drum between the "
    "knees), mridangam (long two-headed drum lying sideways), acoustic guitar, nylon-string guitar, tambourine, voices "
    "(and sometimes harmonium). Use these names; do not guess tabla, dholak or ukulele unless you clearly see them. "
    "The site mixes real photos with AI-generated pictures: call it ai-generated when faces are too smooth or generic, "
    "people do not match the band, hands, text or instruments are malformed, or the scene looks staged and perfect. "
    "The seven members look like this: a bald man with a short beard in a brown plaid shirt (bass); a bald man in a white "
    "T-shirt (djembe); a young man with short dark hair in a white T-shirt (mridangam); a man with long dark hair and "
    "glasses in a dark blue top (acoustic guitar, singing); a woman with short dark hair in a blue-grey shirt (voice); an "
    "older bald man with a white beard in a light shirt (nylon guitar); a woman with her hair tied back in a dark brown "
    "top (tambourine). Count how many of THESE seven you clearly recognise (members_recognised). "
    "Describe this image for a catalogue of a band's website (the SANTOSHI kirtan band from Zagreb). In 3 to 5 plain "
    "sentences say what is shown, who and how many people, what they do or play, the setting, the light and colours, and "
    "any text on it. Then classify it. JSON only: {\"description\":\"...\",\"kind\":\"photo|ai-generated|illustration|"
    "logo|icon|poster|graphic|screenshot\",\"people\":int,\"text_on_image\":\"... or empty\",\"members_recognised\":int,\"good_for\":\"short: where on a "
    "site or poster it fits\"}")


def _safe_title(name, used):
    t = re.sub(r"[\[\]\*\?/\\:]", "_", name)[:31] or "image"
    base, i = t, 2
    while t.lower() in used:
        suffix = f"~{i}"
        t = base[:31 - len(suffix)] + suffix
        i += 1
    used.add(t.lower())
    return t


def describe_all(repo="santoshi_band_site", project="Santoshi poster", site=None, pool=None, record_spend=None, workers=4,
                 force=False):
    import repo_reader  # noqa: PLC0415
    import vision  # noqa: PLC0415
    from poster_skill import project_dirs, _image_size  # noqa: PLC0415
    t0 = time.time()
    full, repo_dir = repo_reader._ready(repo)
    files = [f for f in repo_reader.tree(repo)["files"] if f["path"].lower().endswith(EXTS + (".svg",))]
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE / f"describe_{repo}.json"
    cache = {} if force else (json.loads(cache_file.read_text()) if cache_file.exists() else {})
    todo = [f for f in files if not f["path"].lower().endswith(".svg") and "_t." not in f["path"]
            and f"{f['path']}:{f['size']}" not in cache]

    def one(f):
        try:
            r = vision.ask({"repo": repo, "file": f["path"], "question": QUESTION, "json": True, "max_tokens": 2500},
                           pool, record_spend)
            v = {**(r.get("json") or {"description": r.get("answer", "")}), "cost": r.get("cost", 0)}
            # 12.11.2026: the model calls AI pictures "photo". A picture of a kirtan crowd/stage in which NONE of the seven
            # members is recognised is not the band: flag it (concerts/img/10.jpg and 4.jpg are AI images of strangers).
            try:
                if v.get("kind") == "photo" and int(v.get("people") or 0) >= 3 and int(v.get("members_recognised") or 0) == 0:
                    v["kind"] = "ai-generated? (no band member recognised)"
            except Exception:
                pass
            return f, v
        except Exception as exc:
            return f, {"description": f"(not described: {exc})", "kind": "?", "cost": 0}

    with ThreadPoolExecutor(workers) as ex:
        for f, v in ex.map(one, todo):
            cache[f"{f['path']}:{f['size']}"] = v
            cache_file.write_text(json.dumps(cache, indent=1, ensure_ascii=False))

    from openpyxl import Workbook  # noqa: PLC0415
    from openpyxl.styles import Alignment, Font  # noqa: PLC0415
    wb = Workbook()
    idx = wb.active
    idx.title = "Index"
    idx.append(["Image", "Tab", "Kind", "People", "Pixels", "KB", "Description (short)", "Link"])
    for c in idx[1]:
        c.font = Font(bold=True)
    base = site or SITES.get(repo, "")
    used = {"index"}
    spent = 0.0
    for f in sorted(files, key=lambda x: x["path"]):
        p = f["path"]
        name = Path(p).name
        v = cache.get(f"{p}:{f['size']}")
        if p.lower().endswith(".svg"):
            v = {"description": "(SVG vector file: listed, not described: the model sees raster images only)", "kind": "graphic"}
        elif "_t." in p:
            v = {"description": f"(thumbnail of {name.replace('_t.', '.')}: described there)", "kind": "thumbnail"}
        v = v or {"description": "(not described)", "kind": "?"}
        spent += v.get("cost", 0) or 0
        try:
            w, h = _image_size(repo_dir / p) if not p.lower().endswith(".svg") else ("", "")
        except Exception:
            w, h = "", ""
        title = _safe_title(name, used)
        link = f"{base}/{p}" if base else ""
        idx.append([p, title, v.get("kind", ""), v.get("people", ""), f"{w}x{h}" if w else "", round(f["size"] / 1024),
                    (v.get("description") or "")[:160], link])
        ws = wb.create_sheet(title)
        rows = [("Image", name), ("Path in the repository", p), ("Link on the site", link), ("Kind", v.get("kind", "")),
                ("People", v.get("people", "")), ("Size", f"{w} x {h} px" if w else ""), ("File size", f"{round(f['size'] / 1024)} KB"),
                ("Text on the image", v.get("text_on_image", "")), ("Good for", v.get("good_for", "")),
                ("Description", v.get("description", ""))]
        for k, val in rows:
            ws.append([k, val])
        ws.column_dimensions["A"].width = 24
        ws.column_dimensions["B"].width = 100
        for r in ws.iter_rows():
            r[0].font = Font(bold=True)
            r[1].alignment = Alignment(wrap_text=True, vertical="top")
            r[0].alignment = Alignment(vertical="top")
    for col, wdt in zip("ABCDEFGH", (40, 24, 14, 8, 12, 8, 90, 60)):
        idx.column_dimensions[col].width = wdt
    pics, _stage = project_dirs(project)
    out = pics / f"{project.split()[0]} website images ({repo}).xlsx"
    wb.save(out)
    return {"workbook": str(out), "images": len(files), "described_now": len(todo),
            "tabs": len(wb.sheetnames), "vision_usd": round(spent, 4), "seconds": round(time.time() - t0, 1)}


def register(app, pool, record_spend):
    @app.post("/api/skills/describe-images")
    def describe_images():
        d = request.get_json(silent=True) or {}
        try:
            return jsonify(ok=True, **describe_all(d.get("repo") or "santoshi_band_site", d.get("project") or "Santoshi poster",
                                                   d.get("site"), pool, record_spend, force=bool(d.get("force"))))
        except Exception as exc:
            return jsonify(ok=False, error=f"{type(exc).__name__}: {exc}"), 500
    return app


_CHAT = re.compile(r"\bdescribe\b.*\b(all\s+)?(the\s+)?images?\b.*\b(santoshi|website|site)\b", re.I)


def chat_describe_command(text, pool, record_spend):
    if not _CHAT.search((text or "").strip()):
        return None
    r = describe_all("santoshi_band_site", "Santoshi poster", None, pool, record_spend)
    return (f"Described {r['described_now']} new images ({r['images']} files on the site), one tab each plus an Index: "
            f"{r['workbook']} (vision ${r['vision_usd']}, {r['seconds']} s).")
