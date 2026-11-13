#!/usr/bin/env python3
"""image_collect: find, judge, download, deduplicate and upload a themed set of photographs (13.11.2026).

Written by Claude Code for Queen (skill queen_skills/image-collect.md), first job: 222 photos of people worshipping
Ganesha in Tamil Nadu, into Google Drive from the VM chromium-vm. Runs wherever Queen runs; needs Pillow + numpy
(venv ~/.venvs/imgcollect or system), rclone with a `gdrive:` remote, and Queen on 127.0.0.1:8765 (her eyes).

    image_collect.py run   --job ganesha-tn [--target 222] [--budget 1500] [--folder "<Drive folder>"]
    image_collect.py status --job ganesha-tn
    image_collect.py publish --job ganesha-tn            (rename 001_.., upload, CSV)

State: ~/.groq/work/image_collect/<job>/  cands.json (every candidate and its verdict: re-runs cost nothing),
originals/ (accepted files only), judge/ (small JPEG for her eyes), log.txt.
Sources, in order: Wikimedia Commons (license + author via the API), Openverse (CC). Nothing is taken without its
source URL, author and license in the sheet.
"""
import argparse, csv, hashlib, io, json, os, re, subprocess, sys, time, urllib.parse, urllib.request
from pathlib import Path

UA = "QueenImageCollect/1.0 (https://github.com/markoboskoauroville/groq_ai_studio; private photo research) python-urllib"
ROOT = Path.home() / ".groq" / "work" / "image_collect"
QUEEN = "http://127.0.0.1:8765"
MIN_LONG = 1600
MIN_SHARP = 35.0          # Laplacian variance on a 1600 px grey copy; blurry photos fall below
TN_WORDS = re.compile(r"tamil|chennai|madras|madurai|coimbatore|trichy|tiruchirappalli|tiruchi|thanjavur|tanjore|rameswaram|"
                      r"kanyakumari|kanniyakumari|salem|tirunelveli|vellore|erode|tiruppur|tirupur|thoothukudi|tuticorin|"
                      r"kanchipuram|kancheepuram|mylapore|kapaleeshwarar|pillayar|pillaiyar|vinayagar|vinayaka? chaturthi|"
                      r"rockfort|uchi|mahabalipuram|mamallapuram|chidambaram|kumbakonam|nagercoil|hosur|dindigul|karur|"
                      r"tiruvannamalai|thiruvannamalai|cuddalore|nagapattinam|pudukkottai|sivaganga|karaikudi|ooty|nilgiri|"
                      r"theni|thiruvallur|tambaram|marina|besant|pillayarpatti|manakula|srirangam|palani|tenkasi|virudhunagar|"
                      r"ramanathapuram|namakkal|krishnagiri|dharmapuri|ariyalur|perambalur|ranipet|tirupathur", re.I)

COMMONS_QUERIES = [
    'Ganesh Chaturthi Tamil Nadu', 'Vinayagar Chaturthi', 'Vinayagar Chathurthi Chennai', 'Pillaiyar worship',
    'Ganesha procession Chennai', 'Ganesha immersion Chennai', 'Ganesha immersion Marina', 'Ganesh Chaturthi Coimbatore',
    'Ganesh Chaturthi Madurai', 'Ganesha idols Tamil Nadu festival', 'Vinayagar temple devotees', 'Pillayarpatti devotees',
    'Uchi Pillayar temple Rockfort', 'Manakula Vinayagar temple', 'Karpaga Vinayagar', 'Vinayagar roadside shrine',
    'Ganesha shrine Tamil Nadu devotees', 'Ganesh Chaturthi Tiruchirappalli', 'Ganesh Chaturthi Salem', 'Ganesh Chaturthi Thanjavur',
    'Vinayaka Chaturthi Kanyakumari', 'Ganesh Chaturthi kolam', 'Vinayagar Chaturthi pooja', 'Ganapati puja Tamil Nadu',
    'Ganesha Vinayagar temple Tamil Nadu', 'Ganesh idol immersion Tamil Nadu', 'Vinayagar idols Chennai street',
    'Ganesha Chaturthi Tirunelveli', 'Ganesha Chaturthi Vellore', 'Ganesha Chaturthi Erode', 'Ganesh Chaturthi Tiruppur',
    'Ganesh Chaturthi Pondicherry', 'Pillaiyar kovil', 'Vinayagar kovil', 'Ganesha temple Chennai devotees',
    'Ganesh Visarjan Chennai', 'Vinayagar Chaturthi procession', 'Ganesha festival Tamil Nadu village',
    'Ganesha puja Tamil home', 'Vinayagar puja', 'Ganesha offerings kolukattai', 'Ganesha Chaturthi Mylapore',
    'Ganesha Chaturthi Madurai Meenakshi', 'Ganesha Chaturthi Rameswaram', 'Ganesha Chaturthi Tamil Nadu 2019',
    'Ganesha Chaturthi Tamil Nadu 2023', 'Ganesha Chaturthi Tamil Nadu 2024', 'Ganesha Chaturthi Tamil Nadu 2022',
]
COMMONS_CATS = [
    'Ganesh Chaturthi in Tamil Nadu', 'Ganesh Chaturthi in Chennai', 'Vinayaka Chaturthi', 'Ganesh Chaturthi',
    'Ganesha temples in Tamil Nadu', 'Pillayarpatti', 'Ucchi Pillayar Temple', 'Vinayagar temples in Tamil Nadu',
    'Ganesh Chaturthi in Coimbatore', 'Ganesh Chaturthi in Madurai', 'Ganesh Visarjan', 'Ganesha festivals',
    'Ganesha shrines', 'Ganesha in Tamil Nadu', 'Vinayagar', 'Pillaiyar', 'Hindu festivals in Tamil Nadu',
]
OPENVERSE_QUERIES = [
    'Ganesh Chaturthi Tamil Nadu', 'Vinayagar Chaturthi', 'Pillaiyar temple devotees', 'Ganesha immersion Chennai',
    'Ganesha festival Chennai', 'Vinayagar temple', 'Ganesha procession Tamil Nadu', 'Ganesh Chaturthi Coimbatore',
    'Ganesha puja Tamil', 'Pillayarpatti', 'Ganesh Chaturthi Madurai', 'Vinayagar idol', 'Ganesha shrine Tamil Nadu',
]


def log(job_dir, msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    with open(job_dir / "log.txt", "a") as f:
        f.write(line + "\n")


import threading
_WM = threading.Semaphore(2)          # Wikimedia answers 429 to more than a couple of parallel downloads


def http(url, data=None, headers=None, timeout=40, tries=4):
    if "wikimedia.org" in url:
        for i in range(3):                     # never sleep inside the semaphore
            with _WM:
                time.sleep(0.5)
                try:
                    return _http(url, data, headers, timeout, 1)
                except RuntimeError as e:
                    if "429" not in str(e):
                        raise
            time.sleep(20 * (i + 1))
        raise RuntimeError(url[:100] + ": HTTP 429 (Wikimedia throttle)")
    return _http(url, data, headers, timeout, tries)


def _http(url, data=None, headers=None, timeout=40, tries=4):
    h = {"User-Agent": UA}
    h.update(headers or {})
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 503):
                time.sleep(10 * (i + 1))
            elif e.code in (400, 403, 404):
                break
            else:
                time.sleep(3)
        except Exception as e:
            last = e
            time.sleep(3)
    raise RuntimeError(f"{url[:100]}: {last}")


def jget(url, **kw):
    return json.loads(http(url, **kw))


def strip_html(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


# ---------------------------------------------------------------- sources
def commons_pages(params):
    base = "https://commons.wikimedia.org/w/api.php"
    q = {"action": "query", "format": "json", "prop": "imageinfo|categories", "cllimit": "20", "iilimit": "1",
         "iiprop": "url|size|mime|extmetadata", "iiurlwidth": "1280", "formatversion": "2"}
    q.update(params)
    cont = {}
    for _ in range(40):
        d = jget(base + "?" + urllib.parse.urlencode({**q, **cont}))
        for p in d.get("query", {}).get("pages", []):
            yield p
        if "continue" not in d:
            return
        cont = d["continue"]
        time.sleep(0.5)


def commons_cand(p):
    ii = (p.get("imageinfo") or [{}])[0]
    if not ii or ii.get("mime") not in ("image/jpeg", "image/png", "image/webp"):
        return None
    w, h = ii.get("width", 0), ii.get("height", 0)
    if max(w, h) < MIN_LONG:
        return None
    em = ii.get("extmetadata", {})
    g = lambda k: strip_html((em.get(k) or {}).get("value", ""))
    cats = [c["title"].replace("Category:", "") for c in p.get("categories", [])]
    return {"id": "c:" + str(p["pageid"]), "src": "Wikimedia Commons", "title": p["title"], "w": w, "h": h,
            "orig": ii["url"], "thumb": ii.get("thumburl") or ii["url"], "page": ii.get("descriptionurl", ""),
            "author": g("Artist") or "unknown", "license": g("LicenseShortName") or "unknown",
            "license_url": g("LicenseUrl"), "desc": g("ImageDescription")[:400], "cats": cats[:12],
            "meta_tn": bool(TN_WORDS.search(" ".join([p["title"], g("ImageDescription"), " ".join(cats),
                                                       g("GPSLatitude")])))}


def gen_commons(job_dir):
    seen = set()
    for q in COMMONS_QUERIES:
        for p in commons_pages({"generator": "search", "gsrsearch": q + " filetype:bitmap", "gsrnamespace": "6", "gsrlimit": "50"}):
            if p["pageid"] not in seen:
                seen.add(p["pageid"])
                c = commons_cand(p)
                if c:
                    yield c
        log(job_dir, f"commons search done: {q}")
    # categories, two levels
    todo = [(c, 0) for c in COMMONS_CATS]
    done = set()
    while todo:
        cat, depth = todo.pop(0)
        if cat in done:
            continue
        done.add(cat)
        for p in commons_pages({"generator": "categorymembers", "gcmtitle": "Category:" + cat, "gcmtype": "file", "gcmlimit": "50"}):
            if p["pageid"] not in seen:
                seen.add(p["pageid"])
                c = commons_cand(p)
                if c:
                    yield c
        if depth < 2:
            try:
                d = jget("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(
                    {"action": "query", "format": "json", "list": "categorymembers", "cmtitle": "Category:" + cat,
                     "cmtype": "subcat", "cmlimit": "100"}))
                for m in d["query"]["categorymembers"]:
                    t = m["title"].replace("Category:", "")
                    if re.search(r"ganesh|vinayag|pillaiy|pillay|ganapati|chaturthi|tamil|chennai|madurai|coimbatore|visarjan", t, re.I):
                        todo.append((t, depth + 1))
            except Exception:
                pass
        log(job_dir, f"commons category done: {cat}")


def gen_openverse(job_dir):
    seen = set()
    for q in OPENVERSE_QUERIES:
        for page in range(1, 6):
            try:
                d = jget("https://api.openverse.org/v1/images/?" + urllib.parse.urlencode(
                    {"q": q, "page_size": 20, "page": page, "extension": "jpg,jpeg,png,webp"}))
            except Exception as e:
                log(job_dir, f"openverse stop {q} p{page}: {str(e)[:80]}")
                break
            for r in d.get("results", []):
                if r["id"] in seen:
                    continue
                seen.add(r["id"])
                w, h = r.get("width") or 0, r.get("height") or 0
                if max(w, h) < MIN_LONG:
                    continue
                txt = " ".join([r.get("title") or "", " ".join(t["name"] for t in r.get("tags", []) if t.get("name"))])
                yield {"id": "o:" + r["id"], "src": "Openverse/" + (r.get("source") or r.get("provider") or ""),
                       "title": r.get("title") or "", "w": w, "h": h, "orig": r["url"], "thumb": r["url"],
                       "page": r.get("foreign_landing_url") or "", "author": r.get("creator") or "unknown",
                       "license": ("CC " + (r.get("license") or "").upper() + " " + (r.get("license_version") or "")).strip(),
                       "license_url": r.get("license_url") or "", "desc": txt[:400], "cats": [],
                       "meta_tn": bool(TN_WORDS.search(txt))}
            if not d.get("results"):
                break
            time.sleep(1)
        log(job_dir, f"openverse done: {q}")


BING_QUERIES = [
    'Ganesh Chaturthi Tamil Nadu devotees praying', 'Vinayagar Chaturthi celebration Tamil Nadu', 'Vinayagar Chaturthi Chennai idol procession',
    'Vinayagar idol immersion Chennai Marina beach', 'Pillaiyar temple Tamil Nadu devotees worship', 'Ganesha roadside shrine Tamil Nadu villagers pooja',
    'Vinayagar Chaturthi pooja at home Tamil family', 'Vinayagar Chaturthi kolam house front Tamil Nadu', 'Pillayarpatti Karpaga Vinayagar devotees',
    'Uchi Pillayar temple Trichy devotees', 'Ganesh Chaturthi Madurai celebration', 'Ganesh Chaturthi Coimbatore celebration procession',
    'Vinayagar Chaturthi village Tamil Nadu', 'Ganesha visarjan Tamil Nadu', 'Vinayagar temple abhishekam devotees Tamil Nadu',
    'Ganesh Chaturthi Tamil Nadu photo', 'Vinayagar Chaturthi street pandal Tamil Nadu', 'Tamil women pray Ganesha idol', 'Tamil Nadu village Vinayagar festival',
    'Vinayagar Chaturthi Tirunelveli', 'Vinayagar Chaturthi Salem', 'Vinayagar Chaturthi Tiruppur', 'Vinayagar Chaturthi Thanjavur', 'Vinayagar Chaturthi Vellore',
    'Ganesh Chaturthi Kanyakumari', 'Ganesha puja Tamil Nadu home altar', 'Vinayagar Chaturthi kozhukattai offering pooja', 'Ganesh Chaturthi Mylapore Chennai',
    'Ganesh Chaturthi Pondicherry Manakula Vinayagar devotees', 'Vinayagar Chaturthi Erode', 'Ganesha festival Tamil Nadu news photo',
    'Vinayagar procession Tamil Nadu police bandobast', 'Tamil Nadu Ganesha idols immersion sea devotees',
]


TN_PLACES = ["Chennai", "Madurai", "Coimbatore", "Tiruchirappalli Trichy", "Salem", "Tirunelveli", "Thanjavur", "Vellore", "Erode", "Tiruppur",
             "Kanyakumari", "Rameswaram", "Kumbakonam", "Dindigul", "Karur", "Nagercoil", "Thoothukudi", "Kanchipuram", "Cuddalore", "Pudukkottai",
             "Sivaganga Karaikudi", "Namakkal", "Hosur", "Tiruvannamalai", "Ooty Nilgiris", "Mylapore", "Pillayarpatti", "Pondicherry", "Theni", "Virudhunagar Sivakasi",
             "Tamil Nadu village", "Tamil Nadu temple", "Tamil Nadu street", "Tamil Nadu home"]
TN_PHRASES = ["Vinayagar Chaturthi celebration", "Ganesh Chaturthi devotees pray", "Vinayagar idol procession", "Vinayagar idol immersion", "Pillaiyar temple worship", "Vinayagar pooja"]
BING_QUERIES += [f"{ph} {pl}" for pl in TN_PLACES for ph in TN_PHRASES]
GANESH_TITLE = re.compile(r"ganesh|ganesa|ganapati|ganpati|vinayag|vinayak|pillai?yar|pillayar|chaturthi|chathurthi|vinayaka", re.I)


def gen_bing(job_dir):
    """Bing Images HTML (no login): each tile carries a JSON with murl (full-size file), purl (page), t (title)."""
    import html as _html
    seen = set()
    for q, q_size in [(q, sz) for sz in ("+filterui:imagesize-custom_1600_1000", "+filterui:imagesize-custom_2400_1500") for q in BING_QUERIES]:
        for first in range(0, 35 * 8, 35):
            try:
                body = http("https://www.bing.com/images/async?" + urllib.parse.urlencode(
                    {"q": q, "first": first, "count": 35, "qft": q_size, "adlt": "off"}),
                    headers={"Accept-Language": "en"}, timeout=30, tries=2).decode("utf8", "ignore")
            except Exception as e:
                log(job_dir, f"bing stop {q} first={first}: {str(e)[:80]}")
                break
            tiles = re.findall(r' m="(\{.*?\})"', body)
            if not tiles:
                break
            for t in tiles:
                try:
                    m = json.loads(_html.unescape(t))
                except Exception:
                    continue
                u = m.get("murl")
                if not u or u in seen or not re.search(r"\.(jpe?g|png|webp)(\?|$)", u, re.I):
                    continue
                seen.add(u)
                if not GANESH_TITLE.search((m.get("t") or "") + " " + (m.get("purl") or "") + " " + u):
                    continue               # title says nothing about Ganesha: skip without downloading
                txt = " ".join([m.get("t") or "", m.get("purl") or "", q])
                yield {"id": "b:" + hashlib.md5(u.encode()).hexdigest()[:16], "src": "Web/Bing: " + urllib.parse.urlparse(m.get("purl") or u).netloc,
                       "title": _html.unescape(m.get("t") or "")[:150], "w": 0, "h": 0, "orig": u, "thumb": None,
                       "page": m.get("purl") or "", "author": "", "license": "", "license_url": "", "desc": "", "cats": [],
                       "meta_tn": bool(TN_WORDS.search(_html.unescape(m.get("t") or "") + " " + (m.get("purl") or "")))}
            time.sleep(1.2)
        log(job_dir, f"bing done: {q}")


def roundrobin(*gens):
    gens = list(gens)
    while gens:
        for g in list(gens):
            try:
                yield next(g)
            except StopIteration:
                gens.remove(g)


# ---------------------------------------------------------------- image checks
def load_pil():
    from PIL import Image
    return Image


def dhash(img, size=16):
    import numpy as np
    g = img.convert("L").resize((size + 1, size))
    a = np.asarray(g, dtype=np.int16)
    return "".join("1" if x else "0" for x in (a[:, 1:] > a[:, :-1]).flatten())


def hamming(a, b):
    return sum(x != y for x, y in zip(a, b))


def sharpness(img):
    import numpy as np
    im = img.convert("L")
    s = 1600 / max(im.size)
    if s < 1:
        im = im.resize((int(im.width * s), int(im.height * s)))
    a = np.asarray(im, dtype=np.float32)
    lap = a[1:-1, 1:-1] * -4 + a[:-2, 1:-1] + a[2:, 1:-1] + a[1:-1, :-2] + a[1:-1, 2:]
    return float(lap.var())


def ask_queen(path, question):
    body = json.dumps({"path": str(path), "question": question, "json": True, "max_tokens": 1200}).encode()
    d = json.loads(http(QUEEN + "/api/vision/ask", data=body, headers={"Content-Type": "application/json"}, timeout=120, tries=3))
    return d


JUDGE_Q = """You judge photographs for a documentary collection: "How people in Tamil Nadu (villages and cities) worship Ganesha
(Vinayagar / Pillaiyar): temples, roadside shrines, home altars, house fronts, Vinayaka Chaturthi processions, idol immersion,
kolam and offerings". Metadata of the file (may help with the place, but your eyes decide what is visible):
TITLE: {title}
DESCRIPTION: {desc}
CATEGORIES: {cats}
Answer ONE JSON object with these keys, in this order:
look (two plain sentences: what exactly is in the picture and what the people are doing),
real_photo (true for an ordinary real camera photograph; false only for AI-generated pictures, illustrations, paintings, 3D renders),
single_photograph (true when it is ONE ordinary photograph, one frame; false ONLY if it is clearly several pictures joined side by side or in a grid,
a screenshot with phone/browser interface, or a poster with large text boards. A normal wide or tall photo of a crowd is single_photograph = true),
staged_or_ai_look (true when it looks like posed actors, an advertisement/studio shot, a stock-style staged family, or an AI-rendered scene with too-perfect skin and light; false for a candid real moment),
channel_logo_overlay (true when a TV/news channel logo, corporate or police emblem, text banner or caption bar is burnt into the picture),
clean_of_watermark (true when there is no large watermark, stock-agency overlay or logo across the picture; false only if there is one),
ganesha_visible (a Ganesha image/idol/shrine is clearly in the picture),
people_count (number of people clearly visible, integer),
people_worshipping (true ONLY if at least one visible person is clearly engaged in worship or festival devotion towards Ganesha: praying with folded hands,
offering, lighting a lamp or camphor, circumambulating, performing puja, carrying or immersing the idol in a procession, making kolam or offerings at his shrine;
false for people just standing, tourists posing, workers making idols, or a shop selling idols),
tamil_nadu: "strong" (clearly Tamil Nadu: Tamil script, South Indian Dravidian gopuram, typical TN dress such as veshti/saree, kolam, TN place), "plausible" (South Indian setting, could be TN), "other_state" (clearly elsewhere, e.g. Maharashtra pandal, Nepal, Bali), "unknown",
setting (one of: temple, roadside_shrine, home_altar, house_front, procession, immersion, kolam_offering, other),
place_guess (short, or ""),
description (at most 12 words, plain English, what is shown),
reason (one short sentence).
"""


CONFIRM_Q = """Second look, strict. Point at ONE person in this picture who is clearly doing an act of worship or festival devotion towards a Ganesha image:
folded hands in prayer, placing an offering (flowers, coconut, fruit, sweets), lighting a lamp or camphor, performing puja/aarti, circumambulating, touching the idol in reverence,
carrying the idol in a devotional procession or immersing it, or drawing kolam for the festival. An empty shrine with a tiny person far away does not count. Standing next to the idol, looking at it, posing for the camera,
walking on a beach, or making/selling idols is NOT worship.
Answer ONE JSON object: {"person_visible": true/false, "who": "short description of that person", "act": "one of folded_hands, offering, lamp, puja, circumambulation, touching_idol, procession, immersion, kolam, none"}"""


def decide(j, c):
    if not isinstance(j, dict):
        return False, "no judgement"
    if not j.get("real_photo"):
        return False, "not a real photo (AI/illustration)"
    if j.get("staged_or_ai_look") is True:
        return False, "staged / AI-looking"
    if j.get("channel_logo_overlay") is True:
        return False, "logo / banner burnt in"
    if j.get("clean_of_watermark") is False:
        return False, "watermark / stock preview"
    # Queen's single_photograph answer is NOT used: she called plain single photos "vertical stacks of frames" (lesson 1).
    if re.search(r"collage|montage|screenshot|poster|banner|wallpaper|infographic|logo", " ".join([c["title"], c["desc"], " ".join(c["cats"])]), re.I):
        return False, "collage / screenshot (by file metadata)"
    if max(c["w"], c["h"]) / max(1, min(c["w"], c["h"])) > 2.6:
        return False, "collage / banner (extreme aspect ratio)"
    if not j.get("ganesha_visible"):
        return False, "no Ganesha visible"
    if int(j.get("people_count") or 0) < 1:
        return False, "no people"
    if not j.get("people_worshipping"):
        return False, "people not worshipping"
    tn = j.get("tamil_nadu")
    if tn == "other_state":
        return False, "other state"
    if tn == "strong" or (c.get("meta_tn") and tn in ("plausible", "strong")):
        return True, "ok"
    return False, "Tamil Nadu not established"


# ---------------------------------------------------------------- run
def run(a):
    import threading
    from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
    job_dir = ROOT / a.job
    for sub in ("originals", "judge"):
        (job_dir / sub).mkdir(parents=True, exist_ok=True)
    cf = job_dir / "cands.json"
    cands = json.loads(cf.read_text()) if cf.exists() else {}
    Image = load_pil()
    Image.MAX_IMAGE_PIXELS = 400_000_000
    lock = threading.Lock()
    st = {"spent": sum(v.get("cost", 0) for v in cands.values()),
          "judged": sum(1 for v in cands.values() if "verdict" in v)}
    hashes = {k: v["hash"] for k, v in cands.items() if v.get("accepted") and v.get("hash")}
    log(job_dir, f"start: {sum(1 for v in cands.values() if v.get('accepted'))} accepted, {st['judged']} judged, ${st['spent']:.2f} spent")

    def save():
        with lock:
            cf.write_text(json.dumps(cands, indent=1))

    def accepted():
        return sum(1 for v in cands.values() if v.get("accepted"))

    def dup(h):
        with lock:
            return any(hamming(h, o) <= 10 for o in list(hashes.values()))

    def process(c, rec):
        key = hashlib.md5(c["id"].encode()).hexdigest()
        try:
            jp = job_dir / "judge" / (key + ".jpg")
            full_bytes = None
            raw = http(c["thumb"], timeout=60) if c["thumb"] else None
            if raw is None:                      # web result: the file itself is the only copy we have
                raw = full_bytes = http(c["orig"], timeout=40, tries=1)
                if len(raw) > 60_000_000:
                    raise RuntimeError("file over 60 MB")
            im = Image.open(io.BytesIO(raw))
            im.load()
            if full_bytes is not None:
                c["w"], c["h"] = rec["w"], rec["h"] = im.size
                if max(im.size) < MIN_LONG:
                    rec["verdict"] = "reject"; rec["reason"] = f"too small ({im.size[0]}x{im.size[1]})"
                    return
            rgb = im.convert("RGB")
            h = dhash(rgb)
            if dup(h):
                rec["verdict"] = "reject"; rec["reason"] = "duplicate (perceptual hash)"
                return
            rgb.thumbnail((1024, 1024))
            rgb.save(jp, quality=85)
            q = JUDGE_Q.format(title=c["title"][:150], desc=c["desc"][:300], cats="; ".join(c["cats"])[:300])
            d = ask_queen(jp, q)
            with lock:
                st["judged"] += 1
            rec["cost"] = d.get("cost", 0)
            ok, why = decide(d.get("json"), c)
            rec["judge"] = d.get("json")
            rec["reason"] = why
            rec["verdict"] = "accept?" if ok else "reject"
            if ok:
                d2 = ask_queen(jp, CONFIRM_Q)
                rec["cost"] += d2.get("cost", 0)
                j2 = d2.get("json") or {}
                rec["confirm"] = j2
                if str(j2.get("act", "none")).lower() in ("none", "") or not j2.get("person_visible"):
                    ok = False; rec["reason"] = "second look: no clear act of worship"; rec["verdict"] = "reject"
            if ok:
                u = c["orig"].lower().split("?")[0]
                ext = ".jpg" if u.endswith((".jpg", ".jpeg")) else ".png" if u.endswith(".png") else ".webp" if u.endswith(".webp") else ".jpg"
                of = job_dir / "originals" / (key + ext)
                body = full_bytes if full_bytes is not None else http(c["orig"], timeout=180)
                of.write_bytes(body)
                full = Image.open(of); full.load()
                if max(full.size) < MIN_LONG:
                    rec["verdict"] = "reject"; rec["reason"] = f"original only {full.size}"; of.unlink(); return
                sh = sharpness(full)
                rec["sharp"] = round(sh, 1)
                if sh < MIN_SHARP:
                    rec["verdict"] = "reject"; rec["reason"] = f"blurry (sharpness {sh:.0f})"; of.unlink(); return
                fh = dhash(full.convert("RGB"))
                if dup(fh):
                    rec["verdict"] = "reject"; rec["reason"] = "duplicate (perceptual hash)"; of.unlink(); return
                rec["hash"] = fh; rec["file"] = of.name
                rec["size"] = list(full.size); rec["sha"] = hashlib.sha256(body).hexdigest()
                with lock:
                    hashes[c["id"]] = fh
                    rec["accepted"] = True; rec["verdict"] = "accept"
        except Exception as e:
            rec["verdict"] = "error"; rec["reason"] = str(e)[:150]
        finally:
            with lock:
                st["spent"] += rec.get("cost", 0)
            log(job_dir, f"{c['id']} {rec.get('verdict')} ({rec.get('reason')}) accepted={accepted()} judged={st['judged']} ${st['spent']:.2f}")

    ex = ThreadPoolExecutor(max_workers=a.workers)
    pending = set()
    n = 0
    for c in roundrobin(gen_commons(job_dir), gen_openverse(job_dir), gen_bing(job_dir)):
        if accepted() >= a.target + a.spare or st["judged"] >= a.budget:
            log(job_dir, "stopping: target or budget reached")
            break
        if c["id"] in cands:
            continue
        rec = dict(c)
        cands[c["id"]] = rec
        pending.add(ex.submit(process, c, rec))
        n += 1
        if n % 10 == 0:
            save()
        while len(pending) >= a.workers * 2:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
    wait(pending)
    ex.shutdown()
    save()
    log(job_dir, f"run finished: accepted={accepted()} judged={st['judged']} spent=${st['spent']:.2f}")


def status(a):
    cf = ROOT / a.job / "cands.json"
    cands = json.loads(cf.read_text()) if cf.exists() else {}
    from collections import Counter
    rs = Counter(v.get("reason", "?") for v in cands.values() if v.get("verdict") in ("reject", "error"))
    src = Counter(v["src"].split("/")[0] for v in cands.values() if v.get("accepted"))
    print(json.dumps({"candidates": len(cands), "judged": sum(1 for v in cands.values() if "judge" in v or v.get("reason", "").startswith("dup")),
                      "accepted": sum(1 for v in cands.values() if v.get("accepted")),
                      "spent_usd": round(sum(v.get("cost", 0) for v in cands.values()), 2),
                      "accepted_by_source": src, "rejected_by_reason": rs.most_common(12)}, indent=1))


def sheet(a):
    """Contact sheet of accepted photos (random sample) for Claude's eyes: sheet --job J --n 20 --out /tmp/sheet.jpg ; prints numbered captions."""
    import random
    from PIL import ImageDraw
    Image = load_pil()
    J = ROOT / a.job
    d = json.loads((J / "cands.json").read_text())
    acc = [v for v in d.values() if v.get("accepted")]
    random.Random(a.seed).shuffle(acc)
    acc = acc[:a.n]
    cols = 5
    rows = (len(acc) + cols - 1) // cols
    sh = Image.new("RGB", (cols * 320, rows * 340), "white")
    for i, v in enumerate(acc):
        im = Image.open(J / "judge" / (hashlib.md5(v["id"].encode()).hexdigest() + ".jpg"))
        im.thumbnail((310, 300))
        sh.paste(im, ((i % cols) * 320, (i // cols) * 340))
        ImageDraw.Draw(sh).text(((i % cols) * 320 + 4, (i // cols) * 340 + 310), f"{i+1} {v['src'][:20]} {v['size'][0]}px", fill="black")
        j = v.get("judge") or {}
        print(i + 1, v["id"], "|", j.get("description"), "|", (v.get("confirm") or {}).get("act"), "|", j.get("place_guess"))
    sh.save(a.out, quality=80)


def slug(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return "-".join(s.split("-")[:7])[:50] or "photo"


def publish(a):
    job_dir = ROOT / a.job
    cands = json.loads((job_dir / "cands.json").read_text())
    acc = [v for v in cands.values() if v.get("accepted")]
    # variety: at most a.per_author photos per author, then best sharpness first
    acc.sort(key=lambda v: -v.get("sharp", 0))
    per, pick = {}, []
    for v in acc:
        k = v["author"]
        if per.get(k, 0) >= a.per_author:
            continue
        per[k] = per.get(k, 0) + 1
        pick.append(v)
    pick = pick[:a.target]
    if len(pick) < a.target:
        print(f"only {len(pick)} usable; need {a.target}"); 
        if not a.force: sys.exit(2)
    pdir = job_dir / "publish"
    if pdir.exists():
        for f in pdir.iterdir(): f.unlink()
    pdir.mkdir(exist_ok=True)
    rows = []
    for i, v in enumerate(pick, 1):
        src = job_dir / "originals" / v["file"]
        name = f"{i:03d}_{slug((v.get('judge') or {}).get('description') or v['title'])}{src.suffix}"
        os.link(src, pdir / name)
        j = v.get("judge") or {}
        rows.append([f"{i:03d}", name, j.get("description", ""), j.get("place_guess", ""), j.get("setting", ""),
                     f"{v['size'][0]}x{v['size'][1]}", v["page"], v["orig"], v["author"], v["src"]])
    with open(pdir / "000_sheet.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["number", "file name", "what it shows", "place if known", "setting", "pixels", "source page", "file URL", "author (if known)", "source"])
        w.writerows(rows)
    subprocess.run(["rclone", "mkdir", f"gdrive:{a.folder}"], check=True)
    subprocess.run(["rclone", "copy", str(pdir), f"gdrive:{a.folder}", "--transfers", "4", "-v", "--stats-one-line"], check=True)
    out = subprocess.run(["rclone", "lsf", f"gdrive:{a.folder}"], capture_output=True, text=True).stdout.split()
    print(f"uploaded; Drive folder holds {len(out)} files (incl. sheet)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "status", "publish", "sheet"])
    ap.add_argument("--job", default="ganesha-tn")
    ap.add_argument("--target", type=int, default=222)
    ap.add_argument("--spare", type=int, default=30, help="extra accepted photos kept as replacements")
    ap.add_argument("--budget", type=int, default=2000, help="max Queen vision judgements")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--per-author", type=int, default=8)
    ap.add_argument("--folder", default="Ganesha worship Tamil Nadu (222) 13.11.2026")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default="/tmp/sheet.jpg")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    {"run": run, "status": status, "publish": publish, "sheet": sheet}[a.cmd](a)
