# whatsapp-supervised (VM, the WhatsApp door)

When: Marko writes in the chat of the phone app "WhatsApp Remote Viewer (Mantra)" (or anywhere) what to do in WhatsApp on the
VM: "show my latest messages", "open the chat with X", "read the last 5 messages", "write to X: ...", "scroll up".
Marko, 14.11.2026: "Before she does anything, Claude is assessing: 'Is this the correct action?' and then corrects it. It's
teaching the skill of dealing with WhatsApp to Queen."
Call: `POST /api/whatsapp/supervised {text, conv}` (a chat picked from choices: `{pick}` or the exact title as text). The phone
reaches it through the door `100.102.86.30:8879 POST /chat` (WHATSAPP_REMOTE_VIEWER/vm/wa_door.py, X-Token).
Answer: {ok, reply, plan, assessment {verdict ok|corrected, why, lesson}, action, chat, draft, choices[], shot: true, messages[]}.
Steps:
1. You plan ONE action: shot | open {chat} | scroll {dir} | draft {chat, text} | photo_draft {chat, text} | chats | read {chat?, n}.
   Rules first (whatsapp_remote.plan_by_rules + `read`), else your own model with these skills.
2. The local Claude Code checks it (claude -p, the plan, sonnet, 90 s). corrected = Claude's plan runs and the lesson goes into
   whatsapp-lessons.md (read it: plan it right the next time). Claude not reachable = NOTHING runs; say so.
3. The hands: ~/Developer/claude-code/tools/wa_remote.py --json (real BiDi input, lock /tmp/wa-bidi.lock).
How to open messages: `open {chat}` (search box, real click on the title). How to read them: `read {n}` gives the last n
bubbles as text (who, time, text; photos and voice messages named). How to write: `draft {chat, text}` types his words
verbatim, UNSENT, read back.
Never send: no plan ever sends. Only the app's SEND button sends, through `/send` -> `POST /api/whatsapp/send {chat, text}`
with the exact text the app shows, in the chat shown (wa_remote refuses anything else). Enter is never pressed in a box.
Several chats match: return the choices, never guess.
Calls ("call Svemir", "answer", "hang up"): NOT possible yet (tested 14.11.2026). WhatsApp Web turns calling on per account
(server flag enable_web_calling, off for Marko); no browser setting changes it. Say so plainly, plan nothing, and offer to
open the chat instead. The microphone path is ready on the VM (null sink wamic) for the day the flag is on.
