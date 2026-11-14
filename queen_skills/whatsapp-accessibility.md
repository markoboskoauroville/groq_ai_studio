# whatsapp-accessibility (Mac only): read WhatsApp through Accessibility, who wrote, what is not answered

Marko, 14.11.2026: "ask her to check my last 5 WhatsApp messages, and it needs to understand who sent them and what was not responded
to. Without taking screenshots, it needs to use accessibility to get the text" ... "WhatsApp, as always, we are using the Firefox
browser with something we call remote control".

Use when Marko asks: "check my last 5 WhatsApp messages", "who wrote to me on WhatsApp", "what did I not answer on WhatsApp",
"which WhatsApp messages are waiting for me", "provjeri zadnjih 5 poruka na whatsappu". The number he says is N (default 5).

Do: answer with the chat command itself (it runs locally, $0): the line goes to `whatsapp_ax` and returns the list. Route:
`POST /api/whatsapp/ax/latest {n}` -> {ok, chats: [{name, time, sender, from_me, text, unread, group, community, kind, answered}],
not_answered, skipped_events, via, say}. `say` is the finished answer: give it as it is.

What the answer must say, for each of the N newest chats (sorted by time, pinned chats do not jump the line):
1. the chat (and "(group)", and its community), the time,
2. WHO sent the last message: "you" when it is Marko's, otherwise the person (in a group the name before ":"; in a one-to-one chat the
   chat's name),
3. the text, the unread count,
4. NOT answered when the last message is the other person's; answered when it is Marko's (a reaction of his counts as an answer);
   someone else's reaction is "only a reaction". Group events ("X joined", "X added Y") are not messages: left out and counted.
Then one line "Not answered: ...".

How it reads (so you can explain it): the macOS Accessibility tree of Firefox (axread), the web area "WhatsApp", its table "Chat list".
WhatsApp hides the tick icon from Accessibility, so "is it Marko's" is read from where the text starts (~20 px right = an icon = his tick),
from "You reacted ...", and from the "~Name:" prefix in groups.

Rules:
1. NEVER a screenshot, never vision, for this. Never press Send, never type into a chat, never open a chat to read (that needs clicks).
2. Firefox under remote control (BiDi 127.0.0.1:9223) is the WhatsApp machine on the Mac. If its WhatsApp tab is not readable the skill
   opens or selects it over remote control and gives Marko his front app back at once; it does nothing else in Firefox.
3. Errors are said as they are: "no Firefox window shows WhatsApp Web (another Space?)", "chat list not there (QR / loading)",
   "Accessibility not allowed". Never fill the list from memory.
4. Writing a reply is another skill (whatsapp-remote.md: drafts, never sent).
