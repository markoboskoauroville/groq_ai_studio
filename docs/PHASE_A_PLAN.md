# Phase A plan: the Swift app serves 127.0.0.1:8765 (14.11.2026, handover to cloud)

No Swift code is written yet. This is the design that was worked out from the code.

- **Server:** POSIX socket on 127.0.0.1:8765 in mac_app (Server.swift), one thread per connection, `Connection: close`, streaming by writing then closing. It parses Content-Length and chunked bodies and answers Expect: 100-continue.
- **Proxy:** every route that is not native is forwarded as raw bytes to the Python backend on ~/.groq/backend_port (default 8766). The request is re-sent with `Connection: close` and the response bytes are piped back, so SSE and NDJSON stream unchanged.
- **Native routes:** /health, /api/version, /api/app/status (adds face:"swift"), /api/models, /api/billing, /api/chat, /api/chats*, /api/remote/send (+ `test_bad_key:true` for a failover test), /api/session/messages, /api/claude/*, /api/supervisor/*, /api/skills/list, /api/training/correct. /api/training/status and /api/training/build run build_dataset through the venv python as a helper. GET / gives a plain line saying Queen is the Swift app.
- **Security guard:** the same Origin/Referer/Sec-Fetch-Site/X-Queen-Token guard as local_api_security_guard.
- **Key pool:** port of groq_pool.DynamicKeyPool, on the same files (keys.txt, ~/.groq/.env GROQ_API_KEY, key_state.json, sha256[:12] ids). It reloads the state from disk before every candidates/cool/good. Rules: 401/403 cools scope * for 30 days; anything else cools the model scope for retry-after (min 5 s, default 60 s). Failover only before the first token.
- **Groq call:** URLSession delegate stream to https://api.groq.com/openai/v1/chat/completions, stream:true, max_tokens 16000. It reads delta.content, delta.reasoning, x_groq.usage and x_groq.id.
- **Ledger:** port of record_spend and MODEL_PRICING/get_model_rates onto spend_ledger.json, then POST /spent to the Cost Agent (port from ~/.config/mantra-ports.json "costagent", default 9047).
- **System prompt:** generate Prompt.swift from build_queen_system_prompt with ast. Exec the function with VERSION and WHERE placeholders, json.dumps(ensure_ascii=False), then turn \uXXXX into \u{XXXX}. Every turn it adds ~/.groq/queen_skills/*.md, sorted, as "### skill: <stem>".
- **/api/chat flow:**
  1. The local command goes first through the new Python internal route POST /api/internal/local_command {text} -> {answer|null}. It is the chain refactored out of chat() into _local_command_answer().
  2. Then the Groq stream, written as {"r"} and {"t"} lines.
  3. Then POST /api/internal/after_turn {prompt, content, model, mode} -> {lines}. It does the training log_output, runs her command lines and writes the handover.
  4. Then the spend record and the {"u": telemetry} line, with the same shape as app.py.
- **Data sync:** after chat save/delete and training writes, Swift calls POST /api/internal/mark_dirty so data_sync still pushes.
- **Python changes:**
  - With QWEN_BACKEND=1 the backend writes ~/.groq/backend_port and NOT app_url/active_port.
  - The `qwen` launcher: when the Swift app exists and QWEN_BACKEND is unset, it opens the app with `open -g` if the app is not running; otherwise it runs as the backend on 8766.
- **Backend lifecycle (Backend.swift):** start ~/.groq/qwen with QWEN_BACKEND=1 GROQ_PORT=8766 QWEN_NO_BROWSER=1, no CLAUDE* variables, and a full PATH (~/.pyenv/shims, /opt/homebrew/bin and the rest). A watchdog checks every 5 s and restarts the backend after 3 failed checks if no qwen_app/app.py is running; at most one start per 20 s. OFF stops the backend (pid from its /api/app/status).
- **Migration:** when binding 8765 fails and the holder's /api/app/status has no "face" field, it is the old Python front. SIGTERM its pid, start the backend on 8766, retry the bind. Then Swift writes app_url = http://127.0.0.1:8765.
- **Queen.swift:** base fixed to 8765; START QUEEN = Backend.start; VERSION 5 (next whole number); CI mac-app.yml builds and releases v5 Latest.
- **Order on the Mac (only after CI is green):** run ./install.sh (Python side) and mac_app/install.sh v5 at the same moment. The old v4 app expects Python on 8765.
- **Test:**
  - `queen "hello"`
  - a skill question
  - /api/claude/ask
  - macro_router /api/brain/plan (proxied)
  - remote/send with test_bad_key (failovers=1)
  - the window chat
- **Known risk:** the Python pool keeps its key_state in memory and can overwrite cooldowns that Swift wrote. Note it in LESSONS.
