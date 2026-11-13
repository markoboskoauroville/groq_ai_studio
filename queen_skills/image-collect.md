When: Marko wants N photographs of a theme collected, checked and stored in Google Drive ("find 222 images of ...", "good resolution", "store in my Drive").
Where it runs: the Mac or the VM chromium-vm; on the VM everything downloads and uploads there (the Mac is on a weak 4G hotspot, nothing comes to it).
Call: `POST /api/skills/image-collect {action:"run", job, target, budget}` (starts tools/image_collect.py in the background; log
~/.groq/work/image_collect/<job>/log.txt), `{action:"status", job}` for the counts, `{action:"publish", job, target, folder}` to upload.
Order of sources (reuse allowed, license and author on record): 1. Wikimedia Commons (API: full-size file, license, author, categories),
2. Openverse (api.openverse.org, CC), 3. Google Images or other sites only if the first two cannot reach the number, and then with the source page
written down. Never a file without source URL, author and license in the sheet.
Every candidate is shown to YOUR EYES (/api/vision/ask, a 1024 px copy, JSON answer). You accept only when ALL hold: real camera photograph (not AI, not an
illustration, painting or render); no watermark or stock preview; not a collage, poster or screenshot; Ganesha (Vinayagar/Pillaiyar) visible; at least one
person visibly worshipping (folded hands, offering, lamp or camphor, puja, circumambulation, carrying or immersing the idol, kolam/offerings at his shrine);
place clearly Tamil Nadu (strong evidence in the picture, or plausible South Indian plus Tamil Nadu in the file's title/description/categories).
Reject: Ganesha alone, idol makers and shop shelves, people just posing, other states (Maharashtra pandals, Nepal, Bali), unknown place.
Traps (your own, 13.11.2026 rule): do not take "Hindu devotees" for Tamil Nadu by default; a decorated pandal in a big crowd with Marathi text is Maharashtra;
a count of people is not worship; say "unknown" instead of guessing the place.
Quality, checked by code on the ORIGINAL file: at least 1600 px on the long side, sharpness (Laplacian variance on a 1600 px grey copy) at least 35, no duplicate
(perceptual dhash distance <= 10), saved as the original file (jpg/png/webp), never re-encoded.
Result: Drive folder with 001_<short-description>.<ext> ... and 000_sheet.csv (number, file, what it shows, place, setting, pixels, source page, file URL, author, license).
Cost: about $0.004 to $0.01 per judged candidate; cap with budget; say the spent total. Judgements are cached in cands.json: a re-run costs nothing for old ones.
Self-check before "done" (rule 8): count the Drive folder with `rclone lsf`; open 20 at random with your eyes AND show Claude a contact sheet; replace any misfit; report
accepted, rejected and why, license mix. If you cannot reach 222 honestly, say how many you have and what is missing; never pad with misfits.
Lesson 1 (13.11.2026, measured, Claude looked at the same 8 pictures): you answered "collage / vertical stack of several frames" (collage_or_screenshot true, and
after rewording single_photograph false) for plain single photographs of a beach immersion and a decorated idol, and your "reason" even contradicted it. Your eyes are NOT
reliable for "is this one picture or several". So that test is no longer yours: the script decides collage/screenshot/poster by file title, description, categories and aspect
ratio (> 2.6). You still judge real_photo, watermark, Ganesha visible, worship, place. Never invent structure ("a vertical stack of frames") that you cannot point at;
describe only what you see in `look`.
