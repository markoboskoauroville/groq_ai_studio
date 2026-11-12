"""Queen's skill: posters for the band's next concert, from the band's own photos, in Affinity (12.11.2026).

Marko: "Ask her to get some images from Santoshi Band, any band picture ... understand where we are all in the image:
everybody from the band. For all those images, make an affinity poster for the coming-up concert. In the background, there
is an image. In front there is a text, basic text, to explain to people who, what, and where. Don't save posters. Keep them
in the multiple tabs inside Affinity." And: "Anything we are doing now is becoming a skill for Queen."

The steps, all Queen's own tools (no Claude Code):
  1. the next event       repo_reader: santoshi_band_site/events.json, the first event that starts after now
  2. the photos           every picture in the profile's photo_dirs (thumbnails, logos, posters skipped)
  3. her eyes, per photo  /api/vision with a per-member checklist written from a verified photo: real photograph?
                          which of the 7 are there? where are the faces (top/bottom) and where is room for text?
                          Answers are cached by file and size, so a second run costs nothing.
  4. the choice           all 7 present + a real photograph; best first; at most `max` posters
  5. Affinity             the photo is copied to ~/Desktop/Queen poster photos (Affinity reads the Desktop only);
                          one new document per photo, the size of the photo (nobody cropped), the photo as background,
                          a see-through dark band where there are no faces, the text centred in it, scaled to fit.
                          Each poster stays open as its own tab. Nothing is saved or exported.
  6. the check            every poster rendered back and looked at by her eyes: is the text readable, are faces covered?

Why the checklist (12.11.2026): asked "is the whole band here?", the model said yes to an AI illustration with other
people in it, and compared side by side with a reference it miscounted. One photo + seven described people worked on all
four test photos (7, 7, 6 and the illustration: 0).

    POST /api/skills/band-posters {profile?: "santoshi_band", max?: 4, dry_run?: false}
    chat: "make posters for the next Santoshi concert"
"""
import json
import re
import shutil
import time
from datetime import datetime
from pathlib import Path

from flask import jsonify, request

SKILLS_DIR = Path(__file__).resolve().parent.parent / "queen_skills"
CACHE = Path.home() / ".groq" / "skill_cache"
DESKTOP_PHOTOS = Path.home() / "Desktop" / "Queen poster photos"     # old (12.11.2026 morning); not used any more
PROJECT = "Santoshi poster"

# Marko, 12.11.2026: "All the photos are saved locally in the Pictures folder, by today's date and project name, and then
# they are used in the poster building." And: "in the same folder, save all the poster versions as PNGs, and the format
# which I can edit ... but I need layers." Affinity's scripts may read and write the Desktop ONLY (PERMISSION_DENIED for
# ~/Pictures, even through a symlink: tested), so Affinity works on a staging copy on the Desktop and every file ends in
# the Pictures folder: the photos, the Gemini pictures, and each poster as .af (layered, editable) + .png.


def project_dirs(name=PROJECT):
    from datetime import date  # noqa: PLC0415
    tag = f"{date.today().isoformat()} {name}"
    pics = Path.home() / "Pictures" / tag
    stage = Path.home() / "Desktop" / "Queen Affinity work" / tag
    pics.mkdir(parents=True, exist_ok=True)
    stage.mkdir(parents=True, exist_ok=True)
    return pics, stage


def stage_file(src, pics, stage, name=None):
    """Keep the file in Pictures, hand Affinity the Desktop copy."""
    name = name or Path(src).name
    keep = pics / name
    if Path(src).resolve() != keep.resolve():
        shutil.copy2(src, keep)
    work = stage / name
    shutil.copy2(keep, work)
    return work


SAVE_JS = r"""
const {Document, FileExportOptions} = require('/document.js');
let d = null; for (const x of Document.all) if (x.sessionUuid === __UUID__) d = x;
if (!d) throw new Error('poster not open');
d.saveAs(__AF__);
d.export(__PNG__, FileExportOptions.createWithPresetName('PNG'));
console.log('saved');
"""


def next_free(pics, stage, name):
    """A name that is free in both folders: the name itself, then ' v2', ' v3' ... (whole-number versions, MANTRA_MANIFEST
    versioning.md). Saving over a poster that is open in another tab fails silently in Affinity (12.11.2026)."""
    cand, v = name, 1
    while (pics / f"{cand}.af").exists() or (stage / f"{cand}.af").exists():
        v += 1
        cand = f"{name} v{v}"
    return cand


def save_poster(aff, out, pics, stage, name):
    """Save the open poster as layered .af and as .png (on the Desktop for Affinity), then copy both into Pictures."""
    m = re.search(r"uuid=(\S+)", out or "")
    if not m:
        return {"uuid": None, "error": (out or "").strip()[-200:]}
    uuid = m.group(1)
    name = next_free(pics, stage, name)
    af, png = stage / f"{name}.af", stage / f"{name}.png"
    js = SAVE_JS.replace("__UUID__", json.dumps(uuid)).replace("__AF__", json.dumps(str(af))).replace("__PNG__", json.dumps(str(png)))
    res = aff.Affinity().execute(js)
    saved = {}
    for p in (af, png):
        for _ in range(20):
            if p.exists() and p.stat().st_size > 0:
                break
            time.sleep(0.5)
        if p.exists():
            shutil.copy2(p, pics / p.name)
            saved[p.suffix[1:]] = str(pics / p.name)
    return {"uuid": uuid, "saved": saved, "affinity": (res or "").strip()[-120:]}
POSTER_WIDTH = 1800

POSTER_JS = r"""
const {Document, NewDocumentOptions} = require('/document.js');
const {UnitType} = require('/units.js');
const {ImageNodeDefinition, ShapeNodeDefinition, FrameTextNodeDefinition} = require('/nodes.js');
const {Bitmap, RasterFormat} = require('/rasterobject.js');
const {TransformBuilder, Rectangle} = require('/geometry.js');
const {ShapeRectangle} = require('/shapes.js');
const {Colour} = require('/colours.js');
const {FillDescriptor} = require('/fills.js');
const {StoryBuilder} = require('/storybuilder.js');
const {StoryDelta, ParagraphAlignXType} = require('/storydelta.js');
const {GlyphAttDoubleType} = require('/glyphatts.js');
const {BlendMode} = require('/blendmodeinterface.js');
const P = __PARAMS__;
const bmp = Bitmap.loadFromFile(P.photo, RasterFormat.RGBA8);
const W = P.width, H = Math.round(P.width * bmp.height / bmp.width);
const o = NewDocumentOptions.createDefault(); o.units = UnitType.Pixel; o.width = W; o.height = H; o.dpi = 72;
const doc = Document.create(o);
const lastNode = () => { let l = null; for (const n of doc.currentSpread.children.all) l = n; return l; };
const img = ImageNodeDefinition.create(RasterFormat.RGBA8); img.bitmap = bmp;
const tb = new TransformBuilder(); tb.scaleXY(W / bmp.width, W / bmp.width); img.transform = tb.transform;
doc.addNode(img);
const bandH = Math.round(H * P.band), bandY = P.text_at === 'top' ? 0 : H - bandH;
const r = ShapeNodeDefinition.createDefault(); r.shape = ShapeRectangle.create();
r.setBoundingRectangle(new Rectangle(0, bandY, W, bandH)); doc.addNode(r);
lastNode().brushFillInterface.currentDescriptor = Colour.createRGBA8({r: 10, g: 6, b: 18, a: 255});
doc.setOpacity(P.band_opacity, lastNode());
const white = FillDescriptor.createSolid(Colour.createRGBA8({r: 255, g: 255, b: 255, a: 255}), BlendMode.Normal);
const gold = FillDescriptor.createSolid(Colour.createRGBA8({r: 245, g: 190, b: 90, a: 255}), BlendMode.Normal);
let y = bandY + Math.round(bandH * P.pad);
for (const L of P.lines) {
  const px = Math.round(L.px);
  const sb = StoryBuilder.create();
  sb.setToFrameTextDefaultStyle(doc.dpi, doc.rasterFormat);
  sb.applyGlyphDelta(StoryDelta.createGlyphDouble(GlyphAttDoubleType.Height, px));
  sb.applyGlyphDelta(StoryDelta.createBrushFill(L.gold ? gold : white));
  sb.applyParagraphDelta(StoryDelta.createAlignX(ParagraphAlignXType.Centre));   // paragraph, not glyph: a glyph delta is ignored
  sb.addText(L.text);
  const h = Math.round(px * 1.45);
  doc.addNode(FrameTextNodeDefinition.createFromStoryBuilder(new Rectangle(Math.round(W * 0.05), y, Math.round(W * 0.90), h), sb));
  y += h + Math.round(px * L.gap);
}
console.log('uuid=' + doc.sessionUuid + ' size=' + W + 'x' + H + ' band=' + bandY + '..' + (bandY + bandH) + ' text_end=' + y);
"""


class SkillError(Exception):
    pass


def _profile(name):
    p = SKILLS_DIR / f"{name}.json"
    if not p.exists():
        raise SkillError(f"no profile {p.name} in queen_skills")
    return json.loads(p.read_text())


def next_event(prof):
    import repo_reader  # noqa: PLC0415
    r = repo_reader.read(prof["repo"], prof["events_file"])
    events = json.loads(r["content"]).get("events", [])
    now = datetime.now()
    upcoming = []
    for e in events:
        try:
            start = datetime.fromisoformat(e.get("start", ""))
        except Exception:
            continue
        if start > now:
            upcoming.append((start, e))
    if not upcoming:
        raise SkillError("no upcoming event in " + prof["events_file"])
    return sorted(upcoming, key=lambda x: x[0])[0][1]


def poster_lines(prof, e):
    """Who, what, when, where, entry: Croatian first, English after (the site's own two languages)."""
    t, d = e.get("title", {}), e.get("date", {})
    about = json.dumps(e, ensure_ascii=False).lower()
    lines = [{"text": prof["band"], "size": 0.060, "gold": True, "gap": 0.30}]
    if t:
        lines.append({"text": " · ".join(x for x in (t.get("hr"), t.get("en")) if x), "size": 0.030})
    if d:
        lines.append({"text": d.get("hr") or d.get("en"), "size": 0.030})
    if e.get("place"):
        lines.append({"text": e["place"], "size": 0.024})
    if "free" in about or "slobodan" in about or "besplat" in about:
        lines.append({"text": "Ulaz slobodan, donacije dobrodošle · Free entry, donations welcome", "size": 0.022, "gold": True})
    return lines


def fit_lines(lines, W, H, band, pad=0.08):
    """Sizes in px so every line fits the frame width on one line and the block fits the band."""
    out = []
    for L in lines:
        px = L["size"] * W
        est = len(L["text"]) * 0.52 * px            # average glyph width of a sans face
        if est > 0.88 * W:
            px *= 0.88 * W / est
        out.append({**L, "px": px, "gap": L.get("gap", 0.18)})
    total = sum(x["px"] * 1.45 + x["px"] * x["gap"] for x in out)
    room = H * band * (1 - 2 * pad)
    if total > room:
        k = room / total
        for x in out:
            x["px"] *= k
    return out


def candidates(prof):
    import repo_reader  # noqa: PLC0415
    files = []
    for d in prof["photo_dirs"]:
        for f in repo_reader.tree(prof["repo"], d)["files"]:
            p = f["path"].lower()
            if p.endswith((".jpg", ".jpeg", ".png")) and not any(s in p for s in prof["skip_name_parts"]):
                files.append(f)
    return files


def look(prof, f, pool, record_spend, cache):
    import vision  # noqa: PLC0415
    key = f"{prof['repo']}:{f['path']}:{f['size']}"
    if key in cache:
        return cache[key]
    M = prof["members_by_look"]
    q = ("Look carefully at this picture. First: is it a REAL camera photograph, or AI-generated / an illustration / a "
         f"painting? Then check each of these {len(M)} people one by one; for each say present true only if you clearly "
         "see THAT person:\n" + "\n".join(f"{i+1}. {m}" for i, m in enumerate(M)) +
         f'\nAnswer JSON only: {{"real_photo":bool,"present":[{len(M)} booleans in order],"people_total":int,'
         '"people_top":0-1 (fraction of the height of the highest head),"people_bottom":0-1 (lowest body part of the band),'
         '"free_area":"top|bottom" (the larger area with no faces, for text),"sharp":1-5}')
    try:
        r = vision.ask({"repo": prof["repo"], "file": f["path"], "question": q, "json": True, "max_tokens": 4000},
                       pool, record_spend)
        j = r.get("json") or {}
        v = {"ok": bool(j), "real": bool(j.get("real_photo")), "present": j.get("present") or [],
             "top": j.get("people_top"), "bottom": j.get("people_bottom"), "free": j.get("free_area"),
             "sharp": j.get("sharp"), "cost": r.get("cost", 0)}
    except Exception as exc:
        v = {"ok": False, "error": str(exc)[:200], "cost": 0}
    v["members"] = sum(1 for x in v.get("present", []) if x is True)
    cache[key] = v
    return v


def _image_size(path):
    """Width and height by macOS sips (no Python imaging library needed)."""
    import subprocess  # noqa: PLC0415
    r = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)], capture_output=True, text=True)
    w = re.search(r"pixelWidth:\s*(\d+)", r.stdout)
    h = re.search(r"pixelHeight:\s*(\d+)", r.stdout)
    return (int(w.group(1)), int(h.group(1))) if w and h else (1800, 1200)


def second_look(prof, f, pool, record_spend, cache):
    """An independent count before a photo is accepted (12.11.2026: the checklist once passed a 6-person frame)."""
    import vision  # noqa: PLC0415
    key = f"2nd:{prof['repo']}:{f['path']}:{f['size']}"
    if key not in cache:
        q = ("List every MUSICIAN of the band you can see in this photo, one entry each, left to right, with the instrument "
             "they play or 'voice' if they only sing. People in the audience do not count; count each person once. "
             'JSON {"musicians":[{"position":"left|centre|right","instrument":".."}]}')
        try:
            r = vision.ask({"repo": prof["repo"], "file": f["path"], "question": q, "json": True, "max_tokens": 3000},
                           pool, record_spend)
            ms = (r.get("json") or {}).get("musicians") or []
            cache[key] = {"count": len(ms), "musicians": ms, "cost": r.get("cost", 0)}
        except Exception as exc:
            cache[key] = {"count": 0, "error": str(exc)[:200]}
    return cache[key]


def layout(v):
    """Text where there are no faces: top band when the band sits low, else bottom."""
    top, bottom = v.get("top"), v.get("bottom")
    try:
        top, bottom = float(top), float(bottom)
    except Exception:
        return ("top" if v.get("free") == "top" else "bottom"), 0.36
    if v.get("free") == "top" and top >= 0.2:
        return "top", max(0.24, min(0.40, top - 0.02))
    return "bottom", max(0.26, min(0.40, 1 - bottom - 0.02)) if bottom < 0.74 else 0.34


def run(profile="santoshi_band", max_posters=4, dry_run=False, pool=None, record_spend=None):
    prof = _profile(profile)
    t0 = time.time()
    event = next_event(prof)
    lines = poster_lines(prof, event)
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE / f"photos_{profile}.json"
    cache = json.loads(cache_file.read_text()) if cache_file.exists() else {}
    looked, spent = [], 0.0
    for f in candidates(prof):
        v = look(prof, f, pool, record_spend, cache)
        spent += v.get("cost", 0) or 0
        looked.append((f, v))
    cache_file.write_text(json.dumps(cache, indent=1))
    need = len(prof["members_by_look"])
    first = [(f, v) for f, v in looked if v.get("ok") and v.get("real") and v.get("members") == need]
    chosen = []
    for f, v in first:                                   # both looks must agree on the whole band
        s2 = second_look(prof, f, pool, record_spend, cache)
        spent += s2.get("cost", 0) or 0
        v["second_count"] = s2.get("count")
        if s2.get("count") == need:
            chosen.append((f, v))
    cache_file.write_text(json.dumps(cache, indent=1))
    chosen.sort(key=lambda fv: -(fv[1].get("sharp") or 0))
    chosen = chosen[:max_posters]
    report = {"event": {"title": event.get("title"), "date": event.get("date"), "place": event.get("place")},
              "looked_at": len(looked), "whole_band": [f["path"] for f, _ in chosen], "vision_usd": round(spent, 4),
              "posters": []}
    if dry_run or not chosen:
        report["note"] = "dry run" if dry_run else "no photo shows the whole band"
        return report

    import affinity_bridge  # noqa: PLC0415
    aff = affinity_bridge._client()
    aff.open_app()
    import repo_reader  # noqa: PLC0415
    _full, repo_dir = repo_reader._ready(prof["repo"])
    pics, stage = project_dirs()
    for f, v in chosen:
        src = repo_dir / f["path"]
        dst = stage_file(src, pics, stage)
        text_at, band = layout(v)
        w, h = _image_size(src)
        H = round(POSTER_WIDTH * h / w)
        params = {"photo": str(dst), "width": POSTER_WIDTH, "text_at": text_at, "band": band, "band_opacity": 0.55,
                  "pad": 0.08, "lines": fit_lines(lines, POSTER_WIDTH, H, band)}
        out = aff.Affinity().execute(POSTER_JS.replace("__PARAMS__", json.dumps(params, ensure_ascii=False)))
        sv = save_poster(aff, out, pics, stage, f"{prof['band']} {event.get('start', '')[:10]} band {Path(f['path']).stem}")
        report["posters"].append({"photo": f["path"], "text_at": text_at, "band": round(band, 2), **sv})
    report["seconds"] = round(time.time() - t0, 1)
    report["folder"] = str(pics)
    return report


def register(app, pool, record_spend):
    @app.post("/api/skills/band-posters")
    def band_posters():
        d = request.get_json(silent=True) or {}
        try:
            return jsonify(ok=True, **run(d.get("profile") or "santoshi_band", int(d.get("max") or 4),
                                          bool(d.get("dry_run")), pool, record_spend))
        except SkillError as exc:
            return jsonify(ok=False, error=str(exc)), 400
        except Exception as exc:
            return jsonify(ok=False, error=f"{type(exc).__name__}: {exc}"), 500
    return app


_CHAT = re.compile(r"^\W*(please\W+)?(make|create|build|design)\s+(the\s+|some\s+)?posters?\b.*\b(santoshi|concert|band)\b", re.I)


def chat_poster_command(text, pool, record_spend):
    if not _CHAT.match((text or "").strip()):
        return None
    r = run("santoshi_band", 4, False, pool, record_spend)
    if not r["posters"]:
        return f"I looked at {r['looked_at']} photos; none shows the whole band, so I made no poster."
    e = r["event"]
    lines = [f"{len(r['posters'])} poster(s) open in Affinity, one tab each, saved as .af (layers) + .png in {r.get('folder')}, for "
             f"{(e.get('title') or {}).get('en', '')}, {(e.get('date') or {}).get('en', '')}, {e.get('place', '')}.",
             f"I looked at {r['looked_at']} photos (vision ${r['vision_usd']}); the whole band is in:"]
    lines += [f"- {p['photo']} (text {p['text_at']})" for p in r["posters"]]
    return "\n".join(lines)


# ============================================================================ poster like a reference poster (A4)
# Marko, 12.11.2026: "find an image when the band is from behind, and we see the audience, and use this picture as a
# background picture. Make the poster A4 aspect ratio, portrait. There is already a poster made by AI on the site. Look
# at this poster and copy its layout, but using the real picture."
# A wide stage photo in an A4 portrait page would lose most of the band if cropped, so: the same photo enlarged and
# darkened fills the page (the hall, the mood), the whole photo sits uncropped in the middle (everyone in it), and the
# reference poster's lines go on top and bottom over dark gradients, in its order, sizes, capitals and weights.

A4_W, A4_H = 1240, 1754          # A4 portrait at 150 dpi (1 : 1.4142)

A4_JS = r"""
const {Document, NewDocumentOptions} = require('/document.js');
const {UnitType} = require('/units.js');
const {ImageNodeDefinition, ShapeNodeDefinition, FrameTextNodeDefinition} = require('/nodes.js');
const {Bitmap, RasterFormat} = require('/rasterobject.js');
const {TransformBuilder, Rectangle} = require('/geometry.js');
const {ShapeRectangle} = require('/shapes.js');
const {Colour} = require('/colours.js');
const {FillDescriptor} = require('/fills.js');
const {StoryBuilder} = require('/storybuilder.js');
const {StoryDelta, ParagraphAlignXType} = require('/storydelta.js');
const {GlyphAttDoubleType} = require('/glyphatts.js');
const {BlendMode} = require('/blendmodeinterface.js');
const P = __PARAMS__;
const W = P.W, H = P.H;
const o = NewDocumentOptions.createDefault(); o.units = UnitType.Pixel; o.width = W; o.height = H; o.dpi = 150;
const doc = Document.create(o);
const lastNode = () => { let l = null; for (const n of doc.currentSpread.children.all) l = n; return l; };
const place = (sc, tx, ty) => {
  const d = ImageNodeDefinition.create(RasterFormat.RGBA8); d.bitmap = Bitmap.loadFromFile(P.photo, RasterFormat.RGBA8);
  const tb = new TransformBuilder(); tb.scaleXY(sc, sc); tb.translateXY(tx, ty); d.transform = tb.transform; doc.addNode(d);
};
const rect = (x, y, w, h, op) => {
  const r = ShapeNodeDefinition.createDefault(); r.shape = ShapeRectangle.create();
  r.setBoundingRectangle(new Rectangle(x, y, w, h)); doc.addNode(r);
  lastNode().brushFillInterface.currentDescriptor = Colour.createRGBA8({r: 8, g: 4, b: 16, a: 255});
  doc.setOpacity(op, lastNode());
};
// 1. background: the photo enlarged to cover the page, blurred and darkened (mood, not a second copy of the scene)
const {GaussianBlurLayerEffect} = require('/layereffects.js');
const cover = Math.max(W / P.pw, H / P.ph);
place(cover, (W - P.pw * cover) / 2, (H - P.ph * cover) / 2);
const fx = GaussianBlurLayerEffect.create(); fx.radius = P.blur; doc.setGaussianBlurLayerEffect(lastNode(), fx);
rect(0, 0, W, H, P.bg_dark);
// 2. the whole photo, uncropped, in the middle
const fit = W / P.pw, fh = P.ph * fit;
place(fit, 0, P.photo_y);
// 3. soft seams: the photo's top and bottom edges fade into the dark background; then the text gradients.
//    Strips have exact, non-overlapping edges (overlaps drew faint lines, 12.11.2026).
const strips = (y0, y1, a0, a1, n) => {
  for (let i = 0; i < n; i++) {
    const ya = Math.round(y0 + (y1 - y0) * i / n), yb = Math.round(y0 + (y1 - y0) * (i + 1) / n);
    if (yb > ya) rect(0, ya, W, yb - ya, a0 + (a1 - a0) * (i + 0.5) / n);
  }
};
const fe = Math.round(fh * P.edge);
strips(P.photo_y, P.photo_y + fe, P.edge_dark, 0, 10);
strips(P.photo_y + fh - fe, P.photo_y + fh, 0, P.edge_dark, 10);
strips(0, P.top_grad * H, P.grad_max, 0, 16);
strips(H - P.bot_grad * H, H, 0, P.grad_max, 16);
// 4. the lines, as on the reference poster
const white = FillDescriptor.createSolid(Colour.createRGBA8({r: 255, g: 255, b: 255, a: 255}), BlendMode.Normal);
for (const L of P.lines) {
  const sb = StoryBuilder.create();
  sb.setToFrameTextDefaultStyle(doc.dpi, doc.rasterFormat);
  sb.applyGlyphDelta(StoryDelta.createGlyphDouble(GlyphAttDoubleType.Height, L.em));
  sb.applyGlyphDelta(StoryDelta.createBrushFill(white));
  sb.applyGlyphDelta(StoryDelta.createPostscriptName(L.font));
  sb.applyParagraphDelta(StoryDelta.createAlignX(ParagraphAlignXType.Centre));   // paragraph, not glyph: a glyph delta is ignored
  sb.addText(L.text);
  const h = Math.round(L.em * 1.5);
  doc.addNode(FrameTextNodeDefinition.createFromStoryBuilder(new Rectangle(Math.round(W * 0.04), Math.round(L.y - h / 2), Math.round(W * 0.92), h), sb));
}
console.log('uuid=' + doc.sessionUuid + ' size=' + W + 'x' + H + ' photo_y=' + P.photo_y + '..' + Math.round(P.photo_y + fh));
"""


def _cache(name):
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / name
    return p, (json.loads(p.read_text()) if p.exists() else {})


def find_photo(prof, description, pool, record_spend, members_needed=6):
    """Every candidate photo scored by her eyes against a description; best real one with the band in it."""
    import vision  # noqa: PLC0415
    import hashlib  # noqa: PLC0415
    tag = hashlib.sha1(description.encode()).hexdigest()[:10]
    path, cache = _cache(f"find_{tag}.json")
    q = (f"Does this picture match this description: \"{description}\"? Also: is it a REAL camera photograph (not AI-generated, "
         "not an illustration)? How many musicians of the band are visible? "
         'Answer JSON only: {"matches":bool,"score":1-5 (how well it matches),"real_photo":bool,"musicians_visible":int,"why":"short"}')
    scored, spent = [], 0.0
    for f in candidates(prof):
        key = f"{prof['repo']}:{f['path']}:{f['size']}"
        if key not in cache:
            try:
                r = vision.ask({"repo": prof["repo"], "file": f["path"], "question": q, "json": True, "max_tokens": 3000},
                               pool, record_spend)
                cache[key] = {**(r.get("json") or {}), "cost": r.get("cost", 0)}
                spent += r.get("cost", 0) or 0
            except Exception as exc:
                cache[key] = {"error": str(exc)[:200]}
        v = cache[key]
        if v.get("matches") and v.get("real_photo") and (v.get("musicians_visible") or 0) >= members_needed:
            scored.append((v.get("score") or 0, f, v))
    path.write_text(json.dumps(cache, indent=1))
    scored.sort(key=lambda x: (-x[0], -(x[2].get("musicians_visible") or 0)))
    return scored, spent


def read_layout(prof, poster_file, pool, record_spend):
    import vision  # noqa: PLC0415
    path, cache = _cache("layouts.json")
    key = f"{prof['repo']}:{poster_file}"
    if key not in cache:
        q = ("This is a concert poster. Copy its LAYOUT exactly: list every line of text from top to bottom. For each: the exact "
             "text, zone (top or bottom), y position as a fraction of the height (0 top, 1 bottom) of the line centre, height of "
             "the capital letters as a fraction of the poster WIDTH, bold true/false, all caps true/false. "
             'JSON {"lines":[{"text":..,"zone":..,"y":..,"size":..,"bold":..,"caps":..}]}')
        r = vision.ask({"repo": prof["repo"], "file": poster_file, "question": q, "json": True, "max_tokens": 4000},
                       pool, record_spend)
        cache[key] = r.get("json") or {}
        path.write_text(json.dumps(cache, indent=1, ensure_ascii=False))
    return cache[key]


def a4_lines(layout, W, H):
    out = []
    for L in layout.get("lines", []):
        cap = float(L.get("size") or 0.04) * W            # cap height in px
        em = cap / 0.72                                     # Oswald: caps are ~72% of the em
        est = len(L["text"]) * (0.50 if L.get("caps") else 0.44) * em
        if est > 0.92 * W:
            em *= 0.92 * W / est
        out.append({"text": L["text"], "em": round(em, 1), "y": round(float(L.get("y") or 0.5) * H),
                    "font": "Oswald-SemiBold" if L.get("bold") else "Oswald-Regular"})
    return out


def run_like(profile="santoshi_band", reference="img/coming/2026-11-21.jpg",
             description="the band seen from behind, the audience in front of them in the hall",
             pool=None, record_spend=None, dry_run=False):
    prof = _profile(profile)
    t0 = time.time()
    event = next_event(prof)
    layout = read_layout(prof, reference, pool, record_spend)
    if not layout.get("lines"):
        raise SkillError(f"could not read the layout of {reference}")
    day = (event.get("start") or "")[:10]                       # 2026-11-21
    dmy = f"{day[8:10]}.{day[5:7]}.{day[0:4]}" if len(day) == 10 else ""
    text = " ".join(L["text"] for L in layout["lines"])
    if dmy and dmy not in text and str(int(day[8:10])) not in text:
        raise SkillError(f"the reference poster does not show the next event's date ({dmy}): pick the right poster")
    # Marko, 12.11.2026: "She does not understand what behind means ... you choose for her: the same photo looking like
    # the one made with the poster, but it's not AI; I use AI to enhance the photo." A reference poster made from a real
    # photo names that photo in the profile (poster_sources) and it is used as is; the eye search is only the fallback.
    src = (prof.get("poster_sources") or {}).get(reference, {}).get("photo")
    if src:
        import repo_reader  # noqa: PLC0415
        hit = [f for f in repo_reader.tree(prof["repo"], str(Path(src).parent))["files"] if f["path"] == src]
        scored, spent = ([(5, hit[0], {"source": "profile poster_sources"})] if hit else []), 0.0
    else:
        scored, spent = find_photo(prof, description, pool, record_spend)
    report = {"event": {"title": event.get("title"), "date": event.get("date"), "place": event.get("place")},
              "reference": reference, "layout_lines": [L["text"] for L in layout["lines"]],
              "photos_matching": [(s, f["path"]) for s, f, _ in scored[:5]], "vision_usd": round(spent, 4)}
    if dry_run or not scored:
        report["note"] = "dry run" if dry_run else "no real photo matches the description"
        return report
    best = scored[0][1]
    import affinity_bridge  # noqa: PLC0415
    import repo_reader  # noqa: PLC0415
    aff = affinity_bridge._client()
    aff.open_app()
    _full, repo_dir = repo_reader._ready(prof["repo"])
    pics, stage = project_dirs()
    dst = stage_file(repo_dir / best["path"], pics, stage)
    pw, ph = _image_size(dst)
    W, H = A4_W, A4_H
    fh = ph * W / pw
    tops = [L for L in layout["lines"] if (L.get("zone") == "top" or float(L.get("y") or 0) < 0.5)]
    bots = [L for L in layout["lines"] if L not in tops]
    top_end = (max(float(L["y"]) for L in tops) + 0.05) * H if tops else 0.1 * H
    bot_start = (min(float(L["y"]) for L in bots) - 0.05) * H if bots else 0.9 * H
    photo_y = round(top_end + max(0, (bot_start - top_end - fh) / 2))
    params = {"photo": str(dst), "pw": pw, "ph": ph, "W": W, "H": H, "photo_y": photo_y, "bg_dark": 0.55, "blur": 40, "edge": 0.10, "edge_dark": 0.85,
              "top_grad": min(0.32, (top_end / H) + 0.08), "bot_grad": min(0.32, 1 - bot_start / H + 0.08), "grad_max": 0.75,
              "lines": a4_lines(layout, W, H)}
    out = aff.Affinity().execute(A4_JS.replace("__PARAMS__", json.dumps(params, ensure_ascii=False)))
    sv = save_poster(aff, out, pics, stage, f"SANTOSHI {event.get('start', '')[:10]} A4 photo in the middle")
    report.update(photo=best["path"], seconds=round(time.time() - t0, 1), folder=str(pics), **sv)
    return report


def register_like(app, pool, record_spend):
    @app.post("/api/skills/poster-like")
    def poster_like():
        d = request.get_json(silent=True) or {}
        try:
            kw = {k: d[k] for k in ("reference", "description") if d.get(k)}
            return jsonify(ok=True, **run_like(d.get("profile") or "santoshi_band", pool=pool, record_spend=record_spend,
                                               dry_run=bool(d.get("dry_run")), **kw))
        except SkillError as exc:
            return jsonify(ok=False, error=str(exc)), 400
        except Exception as exc:
            return jsonify(ok=False, error=f"{type(exc).__name__}: {exc}"), 500
    return app


_LIKE = re.compile(r"\b(poster)\b.*\b(behind|layout|like the (ai )?poster|copy)\b|\b(behind|layout)\b.*\bposter\b", re.I)


def chat_like_command(text, pool, record_spend):
    t = (text or "").strip()
    if not _LIKE.search(t):
        return None
    r = run_like("santoshi_band", pool=pool, record_spend=record_spend)
    if not r.get("uuid"):
        return f"No poster: {r.get('note', 'no matching photo')}."
    return (f"A4 poster open in Affinity, saved as .af (layers) + .png in {r.get('folder')}: the real photo {r['photo']} (band from behind, audience in front), "
            f"layout copied from {r['reference']}: " + " / ".join(r["layout_lines"]))


# ============================================================================ Gemini versions: full-bleed and three stripes
# Marko, 12.11.2026: the wide photo in a portrait poster loses parts -> Gemini (free, his Chrome, auroville.community)
# extends it to A4; then "English and Croatian posters, two versions"; then "another version with three horizontal
# stripes: the upper part pink lights regenerated in Gemini, ... the down part a stripe with pictures of band members".

EXTEND_PROMPT = ("Extend this photo to a vertical portrait picture with the proportions of an A4 page (portrait, about 3:4). "
                 "Keep the original photo exactly as it is: the same seven musicians seen from behind, their faces, hair, "
                 "clothes, instruments, chairs, cables, fairy lights, and the audience in the purple-lit hall. Do not change, "
                 "move, add or remove any person. Only paint what is missing: above, more of the hall ceiling, walls and purple "
                 "stage lights; below, more of the wooden stage floor with cables and fairy lights. Photorealistic, the same "
                 "lighting, colours and depth; sharp and high quality.")
LIGHTS_PROMPT = ("Using this concert hall photo as the reference for colour and mood, create a new wide photorealistic image "
                 "(landscape, about 2:1) of only the hall's pink and purple stage lights glowing in the dark: the lit ceiling, "
                 "the walls washed in magenta, soft beams and bokeh, string lights. No people, no text. Sharp, high quality.")

STRIPES_JS = r"""
const {Document, NewDocumentOptions} = require('/document.js');
const {UnitType} = require('/units.js');
const {ImageNodeDefinition, ShapeNodeDefinition, FrameTextNodeDefinition} = require('/nodes.js');
const {Bitmap, RasterFormat} = require('/rasterobject.js');
const {TransformBuilder, Rectangle} = require('/geometry.js');
const {ShapeRectangle} = require('/shapes.js');
const {Colour} = require('/colours.js');
const {FillDescriptor} = require('/fills.js');
const {StoryBuilder} = require('/storybuilder.js');
const {StoryDelta, ParagraphAlignXType} = require('/storydelta.js');
const {GlyphAttDoubleType} = require('/glyphatts.js');
const {BlendMode} = require('/blendmodeinterface.js');
const P = __PARAMS__;
const W = P.W, H = P.H;
const o = NewDocumentOptions.createDefault(); o.units = UnitType.Pixel; o.width = W; o.height = H; o.dpi = 150;
const doc = Document.create(o);
const lastNode = () => { let l = null; for (const n of doc.currentSpread.children.all) l = n; return l; };
const rect = (x, y, w, h, c, op) => {
  const r = ShapeNodeDefinition.createDefault(); r.shape = ShapeRectangle.create();
  r.setBoundingRectangle(new Rectangle(x, y, w, h)); doc.addNode(r);
  lastNode().brushFillInterface.currentDescriptor = Colour.createRGBA8({r: c[0], g: c[1], b: c[2], a: 255});
  if (op < 1) doc.setOpacity(op, lastNode());
};
// an image covering the box x,y,w,h (centred crop); boxes are drawn top to bottom, so the next stripe hides any overflow
const cover = (path, iw, ih, x, y, w, h) => {
  const d = ImageNodeDefinition.create(RasterFormat.RGBA8); d.bitmap = Bitmap.loadFromFile(path, RasterFormat.RGBA8);
  const s = Math.max(w / iw, h / ih); const tb = new TransformBuilder(); tb.scaleXY(s, s);
  tb.translateXY(x + (w - iw * s) / 2, y + (h - ih * s) / 2); d.transform = tb.transform; doc.addNode(d);
};
const text = (t, em, y, font, col, frameW) => {
  const sb = StoryBuilder.create(); sb.setToFrameTextDefaultStyle(doc.dpi, doc.rasterFormat);
  sb.applyGlyphDelta(StoryDelta.createGlyphDouble(GlyphAttDoubleType.Height, em));
  sb.applyGlyphDelta(StoryDelta.createBrushFill(FillDescriptor.createSolid(Colour.createRGBA8({r: col[0], g: col[1], b: col[2], a: 255}), BlendMode.Normal)));
  sb.applyGlyphDelta(StoryDelta.createPostscriptName(font));
  sb.applyParagraphDelta(StoryDelta.createAlignX(ParagraphAlignXType.Centre));
  sb.addText(t); const h = Math.round(em * 1.5), fw = frameW || W * 0.92, fx = (frameW ? P._x : (W - fw) / 2);
  doc.addNode(FrameTextNodeDefinition.createFromStoryBuilder(new Rectangle(Math.round(fx), Math.round(y - h / 2), Math.round(fw), h), sb));
};
rect(0, 0, W, H, [10, 6, 18], 1);                                       // the page: night colour
// 1. top stripe: the pink lights (Gemini), darkened a little at the bottom for the title
cover(P.lights, P.lw, P.lh, 0, 0, W, P.top);
for (let i = 0; i < 12; i++) rect(0, Math.round(P.top * (0.35 + 0.65 * i / 12)), W, Math.ceil(P.top * 0.65 / 12), [10, 6, 18], 0.05 + 0.5 * i / 12);
// 2. middle stripe: the band photo, whole width, uncropped
cover(P.photo, P.pw, P.ph, 0, P.top, W, P.mid);
// 3. bottom stripe: the members, in a row, names under them
const n = P.members.length, gap = 10, cw = Math.floor((W - gap * (n + 1)) / n), ch = Math.round(cw * 4 / 3);
const by = P.top + P.mid + P.pad;
P.members.forEach((m, i) => {
  const x = gap + i * (cw + gap);
  cover(m.path, m.w, m.h, x, by, cw, ch);
  P._x = x - 6; text(m.name, P.name_em, by + ch + P.name_em * 0.95, 'Oswald-Regular', [235, 225, 245], cw + 12);
});
// gold hairlines between the stripes
rect(0, P.top - 2, W, 4, [245, 190, 90], 1); rect(0, P.top + P.mid - 2, W, 4, [245, 190, 90], 1);
// the words
for (const L of P.lines) text(L.text, L.em, L.y, L.font, L.gold ? [245, 190, 90] : [255, 255, 255]);
console.log('uuid=' + doc.sessionUuid + ' size=' + W + 'x' + H + ' stripes=' + P.top + '/' + P.mid + '/' + (H - P.top - P.mid));
"""


def bilingual_lines(event, layout):
    """The reference poster's English lines, and the same five roles in Croatian from events.json."""
    en = [L["text"] for L in layout.get("lines", [])]
    t, d = event.get("title", {}), event.get("date", {})
    start, end = event.get("start", ""), event.get("end", "")
    days_hr = ["PONEDJELJAK", "UTORAK", "SRIJEDA", "ČETVRTAK", "PETAK", "SUBOTA", "NEDJELJA"]
    try:
        s = datetime.fromisoformat(start)
        e_ = datetime.fromisoformat(end) if end else None
        when = f"{s:%d.%m.%Y}" + (f" · {s:%H:%M}–{e_:%H:%M}" if e_ else f" · {s:%H:%M}")
        hr_date = f"{days_hr[s.weekday()]} {s:%d.%m.%Y}." + when[10:]
        en_date = f"{s:%A}".upper() + " " + when
    except Exception:
        hr_date, en_date = d.get("hr", ""), d.get("en", "")
    place = event.get("place", "").replace(", Zagreb", " · Zagreb")
    hr = ["SANTOSHI KIRTAN BAND", t.get("hr", ""), hr_date, place.upper(), "Ulaz slobodan · donacije dobrodošle"]
    if len(en) != 5:
        en = ["SANTOSHI KIRTAN BAND", t.get("en", ""), en_date, place.upper(), "Free entry · donations welcome"]
    return {"en": en, "hr": hr}


def _gemini_once(prompt, src, out):
    """One Gemini image, made once: the file on the Desktop is reused on the next run (no second generation)."""
    out = Path(out)
    if out.exists() and out.stat().st_size > 50_000:
        return str(out), False
    import gemini_skill  # noqa: PLC0415
    r = gemini_skill.make_image(prompt, src, out)
    return r["out"], True


def run_gemini_versions(profile="santoshi_band", reference="img/coming/2026-11-21.jpg", pool=None, record_spend=None,
                        versions=("full", "stripes"), langs=("en", "hr"), force=False):
    prof = _profile(profile)
    t0 = time.time()
    event = next_event(prof)
    layout = read_layout(prof, reference, pool, record_spend)
    texts = bilingual_lines(event, layout)
    src_rel = (prof.get("poster_sources") or {}).get(reference, {}).get("photo")
    if not src_rel:
        raise SkillError(f"no real source photo named for {reference} in the profile (poster_sources)")
    import affinity_bridge  # noqa: PLC0415
    import repo_reader  # noqa: PLC0415
    _full, repo_dir = repo_reader._ready(prof["repo"])
    pics, stage = project_dirs()
    photo = stage_file(repo_dir / src_rel, pics, stage)
    stem = Path(src_rel).stem
    report = {"event": event.get("start"), "posters": [], "gemini": []}
    aff = affinity_bridge._client()
    aff.open_app()
    W, H = A4_W, A4_H
    if "full" in versions:
        ext, made = _gemini_once(EXTEND_PROMPT, pics / Path(src_rel).name, pics / f"{stem} A4 (nano banana).png")
        ext = str(stage_file(ext, pics, stage))
        report["gemini"].append({"image": ext, "new": made})
        ew, eh = _image_size(ext)
        for lang in langs:
            if not force and (pics / f"SANTOSHI {event.get('start', '')[:10]} A4 full-bleed {lang.upper()}.af").exists():
                report["posters"].append({"version": "full-bleed", "lang": lang, "skipped": "already in the folder"})
                continue
            lines = [dict(L, text=txt) for L, txt in zip(layout["lines"], texts[lang])]
            params = {"photo": ext, "pw": ew, "ph": eh, "W": W, "H": H, "photo_y": 0, "bg_dark": 0.0, "blur": 0,
                      "edge": 0.0, "edge_dark": 0.0, "top_grad": 0.26, "bot_grad": 0.26, "grad_max": 0.75,
                      "full": True, "lines": a4_lines({"lines": lines}, W, H)}
            js = A4_JS.replace("__PARAMS__", json.dumps(params, ensure_ascii=False))
            js = js.replace("place(fit, 0, P.photo_y);", "if (!P.full) place(fit, 0, P.photo_y);")
            js = js.replace("const fx = GaussianBlurLayerEffect.create(); fx.radius = P.blur; doc.setGaussianBlurLayerEffect(lastNode(), fx);",
                            "if (P.blur > 0) { const fx = GaussianBlurLayerEffect.create(); fx.radius = P.blur; doc.setGaussianBlurLayerEffect(lastNode(), fx); }")
            js = js.replace("strips(P.photo_y, P.photo_y + fe, P.edge_dark, 0, 10);\nstrips(P.photo_y + fh - fe, P.photo_y + fh, 0, P.edge_dark, 10);",
                            "if (!P.full) { strips(P.photo_y, P.photo_y + fe, P.edge_dark, 0, 10); strips(P.photo_y + fh - fe, P.photo_y + fh, 0, P.edge_dark, 10); }")
            out = aff.Affinity().execute(js)
            sv = save_poster(aff, out, pics, stage, f"SANTOSHI {event.get('start', '')[:10]} A4 full-bleed {lang.upper()}")
            report["posters"].append({"version": "full-bleed", "lang": lang, **sv})
    if "stripes" in versions:
        lights, made = _gemini_once(LIGHTS_PROMPT, pics / Path(src_rel).name, pics / f"{stem} pink lights (nano banana).png")
        lights = str(stage_file(lights, pics, stage))
        report["gemini"].append({"image": lights, "new": made})
        lw, lh = _image_size(lights)
        pw, ph = _image_size(photo)
        band = json.loads(repo_reader.read(prof["repo"], "band.json")["content"]).get("players", [])
        members = []
        for p in band:
            rel = f"img/band/{p['img']}"
            dst = stage_file(repo_dir / rel, pics, stage)
            mw, mh = _image_size(dst)
            members.append({"path": str(dst), "w": mw, "h": mh, "name": p["name"].split()[0]})
        mid = round(W * ph / pw)                            # the band photo at full width, uncropped
        n = len(members) or 7
        cw = (W - 10 * (n + 1)) // n
        name_em, pad = 26, 16
        bottom_need = pad + round(cw * 4 / 3) + round(name_em * 2.2) + 250
        top = H - mid - bottom_need
        for lang in langs:
            if not force and (pics / f"SANTOSHI {event.get('start', '')[:10]} A4 three stripes {lang.upper()}.af").exists():
                report["posters"].append({"version": "three stripes", "lang": lang, "skipped": "already in the folder"})
                continue
            t = texts[lang]
            base = top + mid + pad + round(cw * 4 / 3) + round(name_em * 2.2)
            lines = [{"text": t[0], "em": 92, "y": round(top * 0.40), "font": "Oswald-SemiBold"},
                     {"text": t[1], "em": 54, "y": round(top * 0.40) + 100, "font": "Oswald-SemiBold"},
                     {"text": t[2], "em": 58, "y": base + 60, "font": "Oswald-SemiBold", "gold": True},
                     {"text": t[3], "em": 32, "y": base + 130, "font": "Oswald-SemiBold"},
                     {"text": t[4], "em": 30, "y": base + 185, "font": "Oswald-Regular"}]
            for L in lines:                                  # one line each, inside the width
                est = len(L["text"]) * 0.50 * L["em"]
                if est > 0.92 * W:
                    L["em"] = round(L["em"] * 0.92 * W / est, 1)
            params = {"W": W, "H": H, "top": top, "mid": mid, "pad": pad, "lights": lights, "lw": lw, "lh": lh,
                      "photo": str(photo), "pw": pw, "ph": ph, "members": members, "name_em": name_em, "lines": lines}
            out = aff.Affinity().execute(STRIPES_JS.replace("__PARAMS__", json.dumps(params, ensure_ascii=False)))
            sv = save_poster(aff, out, pics, stage, f"SANTOSHI {event.get('start', '')[:10]} A4 three stripes {lang.upper()}")
            report["posters"].append({"version": "three stripes", "lang": lang, **sv})
    report["seconds"] = round(time.time() - t0, 1)
    report["folder"] = str(pics)
    return report


def register_gemini_versions(app, pool, record_spend):
    @app.post("/api/skills/gemini-posters")
    def gemini_posters():
        d = request.get_json(silent=True) or {}
        try:
            return jsonify(ok=True, **run_gemini_versions(
                d.get("profile") or "santoshi_band", pool=pool, record_spend=record_spend,
                versions=tuple(d.get("versions") or ("full", "stripes")), langs=tuple(d.get("langs") or ("en", "hr"))))
        except SkillError as exc:
            return jsonify(ok=False, error=str(exc)), 400
        except Exception as exc:
            return jsonify(ok=False, error=f"{type(exc).__name__}: {exc}"), 500
    return app


_GEM = re.compile(r"\bgemini\b.*\bposters?\b|\bposters?\b.*\b(gemini|stripes?|english and croatian|croatian and english)\b", re.I)


def chat_gemini_command(text, pool, record_spend):
    if not _GEM.search((text or "").strip()):
        return None
    r = run_gemini_versions("santoshi_band", pool=pool, record_spend=record_spend)
    lines = [f"{len(r['posters'])} posters open in Affinity, each saved as .af (layers) + .png in {r.get('folder')}, {r['seconds']} s:"]
    lines += [f"- {p['version']}, {p['lang'].upper()}" + (f" ({p['skipped']})" if p.get("skipped") else "") for p in r["posters"]]
    lines += [f"Gemini: {Path(g['image']).name} ({'new' if g['new'] else 'reused'})" for g in r["gemini"]]
    return "\n".join(lines)
