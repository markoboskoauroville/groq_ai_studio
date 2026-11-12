"""Queen's self-check on a live page: screenshot what is published and compare it with what she made (12.11.2026).

Marko: "please teach her how to screenshot and confirm that things are live. She can recognize, she can compare the image of
what she did and find it on the page, and confirm the image is there."

    POST /api/selfcheck/image-live {url, image: <file name or src part>, local: <the file she published>}

Three independent proofs, all must hold:
  1. the page   the live page (cache-busted) is opened in a background Chrome tab over DevTools, the <img> whose src
                contains the name is found, and the browser really loaded it (complete, naturalWidth > 0)
  2. the eyes   it is scrolled into view and SCREENSHOTTED (the picture as a visitor sees it, saved in ~/.groq/work)
  3. the match  her eyes get both pictures, what she made and the screenshot, and say whether it is the same photo
The result (and the screenshot path) goes into the task chat. A failed proof is reported as failed, never smoothed over.
"""
import base64
import json
import time
from pathlib import Path

from flask import jsonify, request

WORK = Path.home() / ".groq" / "work"

FIND_JS = """(() => {
  const want = %s;
  const im = [...document.images].find(i => (i.getAttribute('src') || '').includes(want) || (i.currentSrc || '').includes(want));
  if (!im) return null;
  im.scrollIntoView({block: 'center'});
  const r = im.getBoundingClientRect();
  return {loaded: im.complete && im.naturalWidth > 0, nw: im.naturalWidth, nh: im.naturalHeight,
          x: r.x + window.scrollX, y: r.y + window.scrollY, w: r.width, h: r.height, src: im.currentSrc || im.src};
})()"""


def image_live(url, image, local, pool=None, record_spend=None, wait=40):
    import gemini_skill as g  # noqa: PLC0415  (the DevTools client; the Allow watcher comes with it)
    import vision  # noqa: PLC0415
    out = {"url": url, "image": image, "found": False, "loaded": False, "same_photo": None}
    cdp = g.CDP()
    tid = None
    try:
        sep = "&" if "?" in url else "?"
        t = cdp.send("Target.createTarget", {"url": f"{url}{sep}selfcheck={int(time.time())}", "background": True})
        tid = t["targetId"]
        sess = cdp.send("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        for d in ("Page.enable", "Runtime.enable"):
            cdp.send(d, session=sess)
        cdp.send("Emulation.setFocusEmulationEnabled", {"enabled": True}, sess)
        info = None
        end = time.time() + wait
        while time.time() < end:
            time.sleep(1)
            info = cdp.js(sess, FIND_JS % json.dumps(image))
            if info and info.get("loaded"):
                break
        if not info:
            out["why"] = f"no <img> with '{image}' on {url}"
            return out
        out.update(found=True, loaded=bool(info.get("loaded")), natural=[info["nw"], info["nh"]], src=info.get("src"))
        if not out["loaded"]:
            out["why"] = "the <img> is on the page but the picture did not load"
            return out
        time.sleep(1.5)                                       # lazy images settle after the scroll
        info = cdp.js(sess, FIND_JS % json.dumps(image)) or info
        # the clip is in PAGE coordinates (12.11.2026: viewport coordinates after a scroll gave a blank screenshot)
        shot = cdp.send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True, "clip": {
            "x": max(0, info["x"]), "y": max(0, info["y"]), "width": max(1, info["w"]), "height": max(1, info["h"]), "scale": 1}},
            sess, timeout=60)
        WORK.mkdir(parents=True, exist_ok=True)
        snap = WORK / f"live_{Path(image).stem}_{time.strftime('%H%M%S')}.png"
        snap.write_bytes(base64.b64decode(shot["data"]))
        out["screenshot"] = str(snap)
    finally:
        if tid:
            try:
                cdp.send("Target.closeTarget", {"targetId": tid})
            except Exception:
                pass
        cdp.close()
    # a blank screenshot is a CAPTURE failure, not a different picture (12.11.2026: a black capture made her eyes invent
    # "different framing"); a flat PNG of that size is a few KB, a real photo hundreds
    if out.get("screenshot") and Path(out["screenshot"]).stat().st_size < 30_000:
        out.update(ok=False, same_photo=None, why="the screenshot came out blank: a capture problem, not the picture")
        return out
    if local and Path(local).expanduser().exists():
        q = ("Picture 1 is a photo I published. Picture 2 is a screenshot of that spot on the live web page. Is picture 2 the "
             "SAME photo as picture 1 (same scene, same framing; only size or compression may differ)? "
             'JSON only: {"same_photo":bool,"why":"short"}')
        r = vision.ask({"path": str(Path(local).expanduser()), "also": [out["screenshot"]], "question": q, "json": True,
                        "max_tokens": 1500}, pool, record_spend)
        j = r.get("json") or {}
        out["same_photo"], out["why"] = j.get("same_photo"), j.get("why", "")
    out["ok"] = bool(out["found"] and out["loaded"] and out["same_photo"] is not False)
    return out


def register(app, pool, record_spend):
    @app.post("/api/selfcheck/image-live")
    def selfcheck_image_live():
        d = request.get_json(silent=True) or {}
        try:
            return jsonify(**image_live(d.get("url", ""), d.get("image", ""), d.get("local", ""), pool, record_spend))
        except Exception as exc:
            return jsonify(ok=False, error=f"{type(exc).__name__}: {exc}"), 500
    return app
