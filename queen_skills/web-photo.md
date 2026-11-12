When: "put this photo on my website", "add <path> to the gallery of Kukljica EcoOasis", any picture onto one of Marko's sites.
Call: `POST /api/skills/web-photo {source, repo}` (chat: the image path + "gallery" + the site's name).
SUPERVISED (Marko, 12.11.2026: "supervise her before each move ... so she doesn't mess up my website"): every step that
changes the site waits for a Claude Code session to approve it (`/api/supervisor/*`; the session runs `queen pending`,
`queen show <id>`, `queen approve|reject <id>`). A reject or 30 minutes of silence stops the task; nothing more changes.
Steps: look (web copy 2400 px JPEG <= 450 KB, captions EN/HR by your eyes) -> PLAN (approve) -> CHANGE with the exact diff
(approve) -> build.sh check (undone automatically if it fails) -> DEPLOY commit + push (approve) -> verify the live page.
Each task opens its own chat in your window, titled with the task, and writes every step there (task_chat.py).
Never: work on top of uncommitted changes in the site repo; crop a panorama into a 4:3 tile; push without the DEPLOY approval.
Sites known: KUKLJICA_ECOOASIS (single index.html, dictionaries en:{ / hr:{, live on GitHub Pages).
