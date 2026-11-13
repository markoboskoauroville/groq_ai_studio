When: Marko wants N photographs of a theme collected, checked and stored in Google Drive ("find 222 images of ...", "good resolution", "store in my Drive").
Where it runs: the Mac or the VM chromium-vm; on the VM everything downloads and uploads there (the Mac is on a weak 4G hotspot, nothing comes to it).
Call: `POST /api/skills/image-collect {action:"run", job, target, budget}` (starts tools/image_collect.py in the background; log
~/.groq/work/image_collect/<job>/log.txt), `{action:"status", job}` for the counts, `{action:"publish", job, target, folder}` to upload.
Order of sources (13.11.2026 change by Marko: "copyright is not important ... just for my own research, give me the best images you can find"; private Drive folder, never published, no logins, no paywalls, nothing that bypasses access): 1. Wikimedia Commons (API: full-size file, license, author, categories),
2. Openverse (api.openverse.org, CC), 3. the open web (Bing Images HTML, then Google/Flickr/news/blog pages) for the strongest moments; when a page only shows the picture in the browser, a full-size screen capture on the VM is allowed. The three sources run in turns. Never a file without its source page URL in the sheet.
Every candidate is shown to YOUR EYES (/api/vision/ask, a 1024 px copy, JSON answer). You accept only when ALL hold: real camera photograph (not AI, not an
illustration, painting or render); no watermark or stock preview; not a collage, poster or screenshot; Ganesha (Vinayagar/Pillaiyar) visible; at least one
person visibly worshipping (folded hands, offering, lamp or camphor, puja, circumambulation, carrying or immersing the idol, kolam/offerings at his shrine);
place clearly Tamil Nadu (strong evidence in the picture, or plausible South Indian plus Tamil Nadu in the file's title/description/categories).
Reject: Ganesha alone, idol makers and shop shelves, people just posing, other states (Maharashtra pandals, Nepal, Bali), unknown place.
Traps (your own, 13.11.2026 rule): do not take "Hindu devotees" for Tamil Nadu by default; a decorated pandal in a big crowd with Marathi text is Maharashtra;
a count of people is not worship; say "unknown" instead of guessing the place.
Quality, checked by code on the ORIGINAL file: at least 1600 px on the long side, sharpness (Laplacian variance on a 1600 px grey copy) at least 35, no duplicate
(perceptual dhash distance <= 10), saved as the original file (jpg/png/webp), never re-encoded.
Result: Drive folder with 001_<short-description>.<ext> ... and 000_sheet.csv (number, file, what it shows, place, setting, pixels, source page, file URL, author if known, source).
Cost: about $0.004 to $0.01 per judged candidate; cap with budget; say the spent total. Judgements are cached in cands.json: a re-run costs nothing for old ones.
Self-check before "done" (rule 8): count the Drive folder with `rclone lsf`; open 20 at random with your eyes AND show Claude a contact sheet; replace any misfit; report
accepted, rejected and why, license mix. If you cannot reach 222 honestly, say how many you have and what is missing; never pad with misfits.
Lesson 1 (13.11.2026, measured, Claude looked at the same 8 pictures): you answered "collage / vertical stack of several frames" (collage_or_screenshot true, and
after rewording single_photograph false) for plain single photographs of a beach immersion and a decorated idol, and your "reason" even contradicted it. Your eyes are NOT
reliable for "is this one picture or several". So that test is no longer yours: the script decides collage/screenshot/poster by file title, description, categories and aspect
ratio (> 2.6). You still judge real_photo, watermark, Ganesha visible, worship, place. Never invent structure ("a vertical stack of frames") that you cannot point at;
describe only what you see in `look`.
Lesson 2 (13.11.2026, Claude's contact sheet of the first 20 accepted, 16 good): you let through posed actors in a decorated living room (a TV-news photo), a picture with a news-channel/police logo
burnt in, an empty shrine with a tiny person far off, and costumed children mimicking deities. The judge now also asks `staged_or_ai_look` and `channel_logo_overlay`
(true = reject) and the second look says an empty shrine with a tiny far person is not worship. A candid real moment beats a perfect-looking one: if the light and faces look
too perfect, say staged.
Yield measured (first 1100 judged): about 2.5 accepted per 100 judged from Commons + Openverse + Bing; most rejects are too small (<1600 px), no people, no Ganesha. Plan on ~$4 per 25 accepted.
