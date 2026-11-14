# whatsapp-machine (VM only)

Marko, 14.11.2026: "the Firefox itself will be the WhatsApp machine. It is going to be specialized in WhatsApp only ... its
homepage needs to come to WhatsApp and my messages. Queen is going to do what I ask her to do with my WhatsApp."

Use when, on the VM, Marko says: "open Firefox", "open WhatsApp", "start the WhatsApp machine", "is WhatsApp linked",
"show me the QR code", or asks for anything in his WhatsApp ("show my latest messages", "open the chat with Petra",
"write to Igor that ...").

The machine: Firefox on the VM screen (own profile ~/.config/vm-firefox, the dock's "Firefox" tile), remote control on
127.0.0.1:9223 (WebDriver BiDi), home page https://web.whatsapp.com. Nothing else is done in this Firefox.

Chat commands (answered by your code, no model, free):
1. `open whatsapp` (also: open firefox, start the whatsapp machine, otvori whatsapp) -> runs `vm-whatsapp start`. It starts
   Firefox with remote control (closing and restarting a Firefox that runs without it), opens WhatsApp, puts it in front and
   full, and tells you the state.
2. `whatsapp status` -> linked | qr | loading.
3. `whatsapp qr` -> a picture of the QR code page in ~/Pictures/<date> WhatsApp/. It is on the VM screen too.
4. `whatsapp: <his words>` -> the same planner and hands as the Mac's WhatsApp remote (skill whatsapp-remote): shot, open a chat,
   scroll, draft, chats. The hands are ~/Developer/claude-code/tools/wa_remote.py with FIREFOXCTL_PORT=9223.

Linking by PHONE NUMBER (Marko, 14.11.2026: "I cannot log in with QR code through this interface ... enter my phone number and
my country and press Next"): chat command `log in with my phone number` (optionally followed by +<country code> <number>) runs
`vm-whatsapp phone-login`: opens "Log in with phone number" if the QR page is shown, types the number with its + country code
(WhatsApp then picks the country itself; the page defaulted to Germany), reads the box back, presses Next with a real click, and
reads the 8-character link code. Tell Marko the code and the path on his phone: WhatsApp > Settings > Linked devices > Link a device
> "Link with phone number instead" > type the code. His number lives only on the VM (~/.config/chromium-vm/whatsapp-phone), never
in a repo or a chat. The code expires after a few minutes: if he is late, run the command again.

Linking by QR (only Marko can do it, with his phone): state "qr" -> tell him: on the phone, WhatsApp > Settings > Linked devices >
Link a device, scan the code on the VM screen. Then check with `whatsapp status`; say "linked" only when the status says so.

Rules:
1. NEVER send a message. Drafts are typed unsent and read back; Marko presses Send (same as whatsapp-remote, rule 1).
2. Several chats match a name: give the list, never guess.
3. His words verbatim, in his language.
4. Check before "done": the status (linked), the chat header after opening, the draft read back from the box.
5. Firefox allows one remote-control session at a time: if a call fails with "session already started", wait and try once more;
   never kill Firefox while a draft is in the box.
