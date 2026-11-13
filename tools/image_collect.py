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

UA = "QueenImageCollect/1.0 (research collection; contact via repository)"
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


def http(url, data=None, headers=None, timeout=40, tries=4):
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
                time.sleep(8 * (i + 1))
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
Answer ONE JSON object with these keys:
real_photo (true only for a real camera photograph; false for AI-generated, illustration, painting, 3D render, drawing),
watermark_or_stock_preview (visible watermark / stock agency overlay), collage_or_screenshot (several pictures joined, a screenshot, a poster, a phone UI),
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


def decide(j, c):
    if not isinstance(j, dict):
        return False, "no judgement"
    if not j.get("real_photo"):
        return False, "not a real photo (AI/illustration)"
    if j.get("watermark_or_stock_preview"):
        return False, "watermark / stock preview"
    if j.get("collage_or_screenshot"):
        return False, "collage / screenshot"
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
    job_dir = ROOT / a.job
    for sub in ("originals", "judge"):
        (job_dir / sub).mkdir(parents=True, exist_ok=True)
    cf = job_dir / "cands.json"
    cands = json.loads(cf.read_text()) if cf.exists() else {}
    Image = load_pil()
    Image.MAX_IMAGE_PIXELS = 400_000_000
    spent = sum(v.get("cost", 0) for v in cands.values())
    judged = sum(1 for v in cands.values() if "verdict" in v)
    hashes = {k: v["hash"] for k, v in cands.items() if v.get("accepted") and v.get("hash")}
    log(job_dir, f"start: {sum(1 for v in cands.values() if v.get('accepted'))} accepted, {judged} judged, ${spent:.2f} spent")

    def save():
        cf.write_text(json.dumps(cands, indent=1))

    def accepted():
        return sum(1 for v in cands.values() if v.get("accepted"))

    def gens():
        yield from gen_commons(job_dir)
        yield from gen_openverse(job_dir)

    for c in gens():
        if accepted() >= a.target + a.spare:
            break
        if judged >= a.budget:
            log(job_dir, "budget reached")
            break
        if c["id"] in cands:
            continue
        rec = dict(c)
        cands[c["id"]] = rec
        try:
            jp = job_dir / "judge" / (hashlib.md5(c["id"].encode()).hexdigest() + ".jpg")
            raw = http(c["thumb"], timeout=60)
            im = Image.open(io.BytesIO(raw))
            im.load()
            rgb = im.convert("RGB")
            h = dhash(rgb)
            if any(hamming(h, o) <= 10 for o in hashes.values()):
                rec["verdict"] = "reject"; rec["reason"] = "duplicate (perceptual hash)"
                continue
            rgb.thumbnail((1024, 1024))
            rgb.save(jp, quality=85)
            q = JUDGE_Q.format(title=c["title"][:150], desc=c["desc"][:300], cats="; ".join(c["cats"])[:300])
            d = ask_queen(jp, q)
            judged += 1
            rec["cost"] = d.get("cost", 0)
            spent += rec["cost"]
            ok, why = decide(d.get("json"), c)
            rec["judge"] = d.get("json")
            rec["reason"] = why
            rec["verdict"] = "accept?" if ok else "reject"
            if ok:
                # download the ORIGINAL and check it properly
                ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get(
                    "image/jpeg" if c["orig"].lower().endswith((".jpg", ".jpeg")) else
                    "image/png" if c["orig"].lower().endswith(".png") else "image/webp", ".jpg")
                of = job_dir / "originals" / (hashlib.md5(c["id"].encode()).hexdigest() + ext)
                body = http(c["orig"], timeout=180)
                of.write_bytes(body)
                full = Image.open(of); full.load()
                if max(full.size) < MIN_LONG:
                    rec["verdict"] = "reject"; rec["reason"] = f"original only {full.size}"; of.unlink(); continue
                sh = sharpness(full)
                rec["sharp"] = round(sh, 1)
                if sh < MIN_SHARP:
                    rec["verdict"] = "reject"; rec["reason"] = f"blurry (sharpness {sh:.0f})"; of.unlink(); continue
                fh = dhash(full.convert("RGB"))
                if any(hamming(fh, o) <= 10 for o in hashes.values()):
                    rec["verdict"] = "reject"; rec["reason"] = "duplicate (perceptual hash)"; of.unlink(); continue
                rec["accepted"] = True; rec["verdict"] = "accept"; rec["hash"] = fh; rec["file"] = of.name
                rec["size"] = list(full.size); rec["sha"] = hashlib.sha256(body).hexdigest()
                hashes[c["id"]] = fh
            log(job_dir, f"{c['id']} {rec['verdict']} ({rec['reason']}) accepted={accepted()} judged={judged} ${spent:.2f}")
        except Exception as e:
            rec["verdict"] = "error"; rec["reason"] = str(e)[:150]
            log(job_dir, f"{c['id']} error {rec['reason']}")
        if len(cands) % 5 == 0:
            save()
    save()
    log(job_dir, f"run finished: accepted={accepted()} judged={judged} spent=${spent:.2f}")


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
                     f"{v['size'][0]}x{v['size'][1]}", v["page"], v["orig"], v["author"], v["license"], v["license_url"], v["src"]])
    with open(pdir / "000_sheet.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["number", "file name", "what it shows", "place if known", "setting", "pixels", "source page", "file URL", "author", "license", "license URL", "source"])
        w.writerows(rows)
    subprocess.run(["rclone", "mkdir", f"gdrive:{a.folder}"], check=True)
    subprocess.run(["rclone", "copy", str(pdir), f"gdrive:{a.folder}", "--transfers", "4", "-v", "--stats-one-line"], check=True)
    out = subprocess.run(["rclone", "lsf", f"gdrive:{a.folder}"], capture_output=True, text=True).stdout.split()
    print(f"uploaded; Drive folder holds {len(out)} files (incl. sheet)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "status", "publish"])
    ap.add_argument("--job", default="ganesha-tn")
    ap.add_argument("--target", type=int, default=222)
    ap.add_argument("--spare", type=int, default=30, help="extra accepted photos kept as replacements")
    ap.add_argument("--budget", type=int, default=2000, help="max Queen vision judgements")
    ap.add_argument("--per-author", type=int, default=8)
    ap.add_argument("--folder", default="Ganesha worship Tamil Nadu (222) 13.11.2026")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    {"run": run, "status": status, "publish": publish}[a.cmd](a)
