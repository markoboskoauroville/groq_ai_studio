# gmail-reply-firefox (Mac only): find an email and type a reply in Gmail, UNSENT

Marko, 14.11.2026 (first used for Svemir's Wyoga test email). Use when he says "reply to <person> in Gmail", "write back to the
email from <person>", "draft the answer", "add the screenshots to the reply". Claude writes, Marko sends: NEVER press Send.

Space: Marko's own Firefox, controlled by `firefoxctl` over WebDriver BiDi. The port is 9223 for Firefox (9222 is often Chrome's
debug port and answers "403 Connection rejected"): always `export FIREFOXCTL_PORT=9223`; `firefoxctl status` must say listening.
Hands: BiDi `input.performActions` (real pointer + keys, inside Firefox only, never moves his real mouse). `firefoxctl click` is el.click()
(JavaScript): fine to read, not to rely on. Ask the macro recorder first (`macroskill has "gmail reply"`); none stored yet.

Account: marko.bosko@gmail.com = https://mail.google.com/mail/u/0/ (check the tab title ends "marko.bosko@gmail.com - Gmail", or the
avatar label). auroville.community is another account: only when he says so. Never sign in, never type a password: a sign-in page = stop and tell him.

Steps:
1. Open in a NEW tab (other tabs stay untouched): `firefoxctl open "https://mail.google.com/mail/u/0/#search/<words or from:name>" --new`, wait ~6 s.
   Read the list with `firefoxctl text -t mail.google`; pick the right sender/subject.
2. Real-click the first row `tr.zA` (rect via script.evaluate, then pointerMove/Down/Up). Read the mail: `firefoxctl text -t mail.google`.
3. Real-click the bottom Reply (a `[role=link]` or `[aria-label=Reply]` whose text is "Reply"; take the last one). The compose box is
   `div[aria-label="Message Body"]`.
4. Real-click the body, then type key by key: one keyDown/keyUp per character (Unicode is fine: š đ č ć ž), newline = Enter
   (``; in Gmail plain Enter is a new line, only Ctrl/Cmd+Enter sends, which you never press). Write in his style
   (MANTRA_MANIFEST modules/writing-styles.md 1a, no emoji; Croatian for Croatian friends/Santoshi, English with Claude).
5. Attachments (no macOS file dialog): inject a hook `HTMLInputElement.prototype.click = function(){ if(this.type==='file'){window.__fi=this;return} ...orig }`,
   real-click the paperclip (`[command=Files]`, "Attach files"), then build the files IN THE PAGE: base64 -> `new File([bytes], name, {type})`
   -> `DataTransfer` -> `window.__fi.files = dt.files` -> dispatch `change`. `input.setFiles` FAILS on Gmail (InvalidStateError), like on WhatsApp.
   Copy files to short clear names first (wyoga-pixel7.png). Check the chips: `.aZo` shows "name (size)" for each.
6. Read back: `document.querySelector('div[aria-label="Message Body"]').innerText` must equal the text (blank lines may double: fine).
7. Screenshot only the Firefox window: find its window id (Quartz CGWindowListCopyWindowInfo, owner Firefox, the one titled with the mail),
   `screencap -x -l <id> out.png`, look at it: text, chips, Send NOT pressed. Leave the reply open and tell Marko where.

Traps met: Firefox BiDi on 9223 not 9222; `input.setFiles` unusable; the compose body is at the bottom of the thread (scroll into view);
innerText doubles blank lines; Gmail search shows the newest first: confirm the sender. Never draft a second reply to a thread that already has one open.
Ending report: which thread, account, typed and unsent, readback ok, chips seen, screenshot path.
