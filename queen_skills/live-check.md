When: after ANYTHING you publish (a photo on a site, a page change, a poster uploaded): prove it is live before saying done.
Call: `POST /api/selfcheck/image-live {url, image: "<part of the img src>", local: "<the file you published>"}`.
It opens the live page in a background Chrome tab (cache-busted), finds the <img>, checks the browser really loaded it,
scrolls it into view, SCREENSHOTS it (~/.groq/work/live_*.png) and shows you both pictures: same photo or not.
ok = found + loaded + same photo. Write all three and the screenshot path into the task chat.
Traps (12.11.2026): the live address comes from the deploy workflow (the README said GitHub Pages, which was 404; the site is on
Cloudflare Pages); a blank screenshot is a capture failure, not "a different picture" (you once invented "different framing" for
a black image); the screenshot clip is in page coordinates. The web-photo skill runs this check itself at the end.
