# Groq AI Studio: lessons

11.11.2026
- The app was written by an agent in nine installer versions in four hours; four of those installers re-embedded the whole app in
  a heredoc (900 to 3000 lines). Source of truth is now this repo, not an installer. Never regenerate it from an installer.
- Keys must never be copied into code, an installer or this repo. The first installer read groq-api.txt and wrote keys.txt;
  from 09 on install loads nothing and keys come in through the Key Manager.
- A hard-coded personal path (`/Users/<name>/Downloads/API/groq-api.txt`) was in `app.py`; replaced by `Path.home()`.
- `groq_pool.py` and `DynamicKeyPool` duplicate the failover logic; a fix in one is missed in the other.
- `which qwen` found nothing in a Claude Code shell: the tool shell does not read ~/.zshrc. The command lives in ~/.groq, added to
  the PATH by .zshrc. Look in ~/.zshrc and ~/.groq before saying a command does not exist.
- Proving "no secret in the public repo": compare the real keys on disk against every file by exact match (without printing them),
  not only a `gsk_` pattern search; the prefix alone appears in the docs and the key parser.
- Backdoor chat test (11.11.2026, three turns, qwen/qwen3.8-27b, about 0.5 s each): each turn showed about 2,600 tokens and $0.0022
  even for a one-line greeting. Likely the hidden reasoning is counted as output; not verified. The ledger cannot be trusted
  until the token counts are checked against Groq's own usage.
- The model ignored the casual persona's spirit and said "I'm stuck as an AI" twice: a system prompt for a character needs a
  stronger line (stay in character, never mention being an AI) if street-talk tests matter.
- Public and unpromoted repository: no README, no description; the description lives in TAKEOVER.md (repo-privacy.md).
- Groq streaming usage lives on `chunk.x_groq.usage` (with `completion_tokens_details.reasoning_tokens`), not always top-level `chunk.usage`. Reading `x_groq.usage` fixed the inflated ~2,600-token estimate down to exact Groq invoice counts (e.g. 729 in / 71 out).
- `sys.path.insert(0, str(Path.home() / ".groq"))` before repo root caused `qwen_app/app.py` to import the stale installed `~/.groq/groq_pool.py` during pre-deploy CI checks; inserting repo root after `~/.groq` at index `0` ensures source-first resolution.
- `btnSend.disabled = true` during streaming prevented clicking the Stop (`AbortController`) button in `index.html`; keeping `btnSend.disabled = false` while `isBusy` is true restores one-click stream cancellation.
- In Python f-strings, backslash escapes inside `{...}` expressions (e.g. `f"...{\"key\": ...}"`) raise `SyntaxError` on older/strict AST parsers or when quotes collide; construct JSON test fixtures via `json.dumps({...})` instead.
- Full-file LLM code rewrites waste ~40k output tokens (~$0.60+) and risk truncation; pre-indexing file landmarks + keyword windows and streaming surgical `SEARCH -> REPLACE` blocks inside `<queen_update>` cuts auto-update cost to fractions of a cent while still running full `ci_run_all` AST + HTML validation on the resulting file in memory.
- Using a fixed `.tmp` suffix (`path.with_suffix(".tmp")`) in multi-threaded Waitress routes (`save_chat`, `save_auto_update_store`) causes `FileNotFoundError` when two concurrent saves rename the same `.tmp` file simultaneously; always include a random hex token or `pid + timestamp` in temporary atomic write filenames.
- macOS `/usr/bin/python3` is Python 3.9, which rejects escaped quotes inside f-string `{...}` expressions (`SyntaxError: f-string expression part cannot include a backslash`); bind dictionary lookups to local variables before formatting in shell-embedded Python snippets.
- Google Gemini / Cloud API keys in `~/Downloads/API/` come in two shapes: `AIza[0-9A-Za-z_-]{20,}` AND `AQ\.[A-Za-z0-9_.-]{20,}` (from `KEY_RING_TESTER`); matching only `AIza` misses `AQ.` keys.
- Multi-file surgical updates (`app.py` + `index.html`) need `max_tokens >= 16000` (not `4096`) and must include `#sidebar` + `app.py` imports/globals in `build_surgical_context` so the external model never truncates JSON or guesses helper names.
- Never include "orphan" landmarks in `build_surgical_context` whose line numbers are not inside the provided verbatim code slices: if a model sees `L946: @app.post("/api/keys/clear")` in a landmark header without lines 946-951 in the excerpt, it will guess the function body and fail strict `search` matching. Filter landmarks strictly to excerpted windows and include a unique decorator-block fallback + 1-round self-heal loop.
- When an LLM updates an existing function surgically, it may emit two overlapping `replace` edits on the same function (`L957` and `L961`), causing Edit #2's `search` anchor to fail or corrupt indentation after Edit #1 mutates the lines. Enforce `ONE edit per function` in the system prompt, add whitespace-normalized multi-line matching in `_find_normalized_span`, and inject exact line-numbered context into the self-heal prompt.
- Google's `models/gemini-2.5-flash` returns HTTP `404` (`no longer available to new users; use models/gemini-3.8-flash`) on newer Google API keys even when `GET /models` lists it; always try `models/gemini-flash-lite-latest` / `models/gemini-3.8-flash` and follow `use (models/...)` hints on 404 in Key Tester.
- **12.11.2026, `install.sh` copies files by name.** `qwen_app/brain.py` was written, `app.py` imported it, and the
  routes 404ed because install.sh never copied it to `~/.groq`. Any new file in `qwen_app/` must be added to the `cp`
  line in install.sh in the same commit.
- **12.11.2026, the pricing table was two generations behind.** It knew `claude-sonnet-4-5` (deprecated, retires
  30.11.2026) but none of the current models, so every auto-update cost was priced at the default. Extended with
  Fable 5.2, Opus 5.5, Sonnet 5.5, Haiku 5.5 and the rest, and the active model moved to `claude-sonnet-5-5`.
- **12.11.2026, Queen passes the gate now.** `verify ~/Developer/groq_ai_studio/qwen_app` is CLEAR. It was not: the
  first run reported 18 errors, all of them false - unused imports counted as defects, and macOS tidy from 2006
  calling `<main>` and `<svg>` errors. The checker was wrong, not the code.
- **12.11.2026, install.sh named its files one by one, and that bit twice.** `brain.py` and then `model_router.py`
  were written, imported by `app.py`, and silently absent from `~/.groq`, so their routes 404ed. Now it copies
  `qwen_app/*.py`. A list of filenames in an install script is a trap that springs on the next new file.
- **12.11.2026, naming the exact mistake cures it.** Queen failed the same three Chrome manifest checks three times
  out of three. Writing those three mistakes into her system prompt, by name, took the ladder to 7/7. The cost of
  the longer prompt is real: the same run went from $0.013 to $0.101 on qwen3.8-27b, which is why the model router
  now sends that work to gpt-oss-20b at $0.0108.
- **12.11.2026, `bool({})` is False.** My own grader marked `"action": {}` - which is correct and complete - as a
  missing key, and blamed Queen for it. Test for the KEY, not its truthiness.
- **12.11.2026, the server that looked alive.** `create_server()` binds the socket before `run()`, and `run()` was
  wrapped in `except Exception: pass`. Queen printed "LIVE", held port 8765, and answered nothing. The real cause was
  thread starvation: `threads=8` with one long-lived `/api/events` stream per open page, and a NEW browser tab opened
  on every restart. Never swallow a server exception; never let unbounded long-lived streams share a small pool.
- **12.11.2026, the benchmark that measured itself.** `/api/remote/send` appended every turn to `active_messages`, so
  each task carried all the earlier ones: costs grew down the list and a model benchmarked later paid for the one
  before it. Worse, a model could read its own earlier correct answers as worked examples - which is why the
  "cure" first looked like 7/7 and was 3/7 on clean turns. Independent work needs `fresh: true`.
- **12.11.2026, no token cap.** With none sent, Groq's default cut the hardest answer off mid-thinking: 8 KB of
  reasoning, no closing tag, no code. `MAX_OUTPUT_TOKENS` now gives room to think AND answer.
- **12.11.2026, do not read the model's thinking as its output.** qwen emits `<think>...</think>` and quotes the
  requested output format inside it. The harness saved that prose as `content.js` and reported a broken file when the
  model had correctly reasoned "only manifest.json is needed". Strip the thinking first; when a filename repeats,
  keep the last block.
- **12.11.2026, rules are weaker than an example.** Naming the three Chrome mistakes in the system prompt fixed them
  only while the channel was feeding the model its own earlier answers. A short worked example of a complete correct
  extension did the real work.

12.11.2026, the rule that outranks the rest: teach Queen
- Marko: "Every time I ask you to do something through Queen, you need to teach her, you need to write a skill so next time
  if I ask directly, she's able to do it without you." Claude Code finding the way once is fine; leaving the way only in a
  Claude transcript is not. Every task ends with `queen_skills/<name>.md` + its route/chat command + a test through her chat.
- Her model only writes text. A skill that needs action needs a route (her hands), not just a paragraph in her prompt.
- Her eyes lie in a specific way: asked "is the whole band here?", Qwen 3.6 said yes to concerts/img/10.jpg, an AI
  illustration with other people in it. A count is not an identity: compare against a verified reference photo.
- Groq lists no Llama-4/vision model on this account, but Qwen 3.6/3.8 take image_url and see well (counts, instruments,
  left-to-right). Nothing had to be enabled: /api/vision/ask.
- 12.11.2026, the hub's SessionEnd hook `exit_all.sh` killed Queen: it ends the shell above `claude` when a session closes, and
  for a headless `claude -p` started by Queen that "shell" was Queen herself (SIGTERM, then SIGKILL a second later: no log line).
  Fixed in the hook: never for a -p/--print run, and only a real shell (zsh, bash, login...). Same cause as a nested
  `claude -p` in a Claude Code Bash tool dying with exit 144.
- A headless Claude still reads Marko's CLAUDE.md and tries to speak every answer (langsay). --append-system-prompt alone
  did not stop it; removing Bash (--disallowedTools Bash) for plain questions did.
- `--bare` would skip the hooks, but it accepts only ANTHROPIC_API_KEY (never the claude.ai login): that is API credits. Not used.
- One headless question costs about 70k context tokens of the plan (hooks + CLAUDE.md) and 3-10 s; no API money.
