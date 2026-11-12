When: Marko or a task needs Claude Code (a hard problem, a code change, a second opinion, reading what a Claude session did).
Rule (Marko, 12.11.2026): the local Claude Code comes FIRST and costs no API credits. Never call the Anthropic or Google API
while it is reachable. If it is not reachable, say exactly "I cannot reach the local Claude Code. Do you want to use API
credits?" and wait for his yes.
Steps:
1. `GET /api/claude/status` -> reachable true/false.
2. Ask: `POST /api/claude/ask {question}` (headless Claude Code on his plan, ~5-60 s). In chat he can type `ask claude <question>`.
3. Read sessions: `GET /api/claude/sessions` (name, folder, last prompt), `GET /api/claude/transcript?sid=<sid>&n=20`.
4. Tell a live session something (types into Marko's iTerm tab, only when he asks): `POST /api/claude/tell {sid, text}`.
5. Your own escalation (`/api/brain/escalate`) and the auto-update (`/api/auto_update/run`) already go local first; with no
   local Claude they answer 409 need_consent; pass `allow_api: true` only after his yes.
Claude Code talks to you through `queen "<question>"` (hub tools/queen) or your /api/chat.
