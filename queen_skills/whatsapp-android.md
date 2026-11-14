# whatsapp-android (VM: WhatsApp Business on Pixel 2 is THE WhatsApp machine)

Marko, 14.11.2026: "it's better to open the WhatsApp Business inside the Android emulator, then inside the Firefox browser ...
If we can teach [Queen] to work with the emulator, even better ... I can click elements directly on the screen."
Machine: WhatsApp Business (com.whatsapp.w4b), linked as a companion device on Pixel 2 (redroid container pixel7b,
adb 127.0.0.1:5556, dark mode). Firefox WhatsApp Web is only the fallback when Pixel 2 is down or not linked.
Hands: ~/Developer/claude-code/tools/wa_android.py --json  (status | chats | unread | open "<chat>" | read ["<chat>"] [N] |
draft "<chat>" "<text>" | clear | shot). Supervised route: POST /api/whatsapp/supervised picks Android by default
(`machine: "android"` in the answer).
How it works: uiautomator dumps and resource-ids (search_bar_inner_layout, search_input, conversations_row_contact_name,
conversation_contact_name, message_text, date, status, entry); taps by adb. Unicode (č ć š đ ž, emoji) goes through the
clipboard helper watext.dex + paste. Nothing is matched by colour.
Rules:
1. NEVER send. A draft is typed into the box and read back; WhatsApp's send button is never tapped by code and Enter is never
   pressed. Marko sends with his own tap on the live screen in the app (or the app's SEND).
2. Type only into a box you have just verified: the search field after the search opened, the entry after the header shows the
   right chat. Otherwise stop (14.11.2026: a missed tap typed a name into Snoopy Badjan's box).
3. A test always ends with `clear` and a look at the chat list: no "Draft:" rows may be left.
4. Several chats match a name: return the choices, never guess.
5. Calls: plan call {chat} / answer / hangup; they run on the door (POST /call /answer /hangup), audio through /audio.
