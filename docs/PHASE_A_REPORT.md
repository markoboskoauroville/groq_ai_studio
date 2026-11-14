# Phase A report (night of 14.11.2026, cloud)

## Result

- **Version:** Groq Queen AI Studio (Mantra) **v5** (the Mac app). Python's version.json is unchanged (v5).
- **Release:** https://github.com/markoboskoauroville/groq_ai_studio/releases/tag/v5 (marked Latest, `app.zip`).
- **Workflow run:** https://github.com/markoboskoauroville/groq_ai_studio/actions/runs/43643205405 (**green**, first try).
- **Tests:** 79 passed, 0 failed (`mac_app/test.sh`, run by the workflow before the build).
- Nothing was compiled on the Mac or in the cloud sandbox. GitHub compiled it.

## What changed

- The Swift app listens on `127.0.0.1:8765` itself (`mac_app/app/core/`).
- The Python server moved to `127.0.0.1:8766`. It is internal, with no web page. The app starts it as its child.
- Every route Swift does not have yet goes to 8766 unchanged, streaming included.
- On Linux (the VM) nothing changed. `app.py` alone still runs on 8765.
- The Mac worker's plan (`docs/PHASE_A_PLAN.md`) was followed. One change: the prompt is not generated into a Swift file. A
  helper in the app reads the installed app.py at run time, so the prompt never drifts.

## Routes in Swift (native)

| Route | Notes |
|---|---|
| `GET /health`, `/api/version`, `/api/app/status` | status adds `face: "swift"`, `backend`, `app_version` |
| `GET /api/models`, `/api/billing` | live call to Groq with the pool, same fields |
| `POST /api/chat` | NDJSON `{"r"}` `{"t"}` `{"u"}` `{"error"}`; failover before the first token |
| `GET /api/events` | SSE, init + events + ping every 20 s, 12 listeners; the backend's events are relayed in |
| `GET /api/session/messages`, `POST /api/remote/send` | remote/send also takes `test_bad_key: true` |
| `/api/chats`, `/api/chats/<id>`, `save`, `rename`, `delete` | `~/.groq/chats/*.json`, same fields |
| `/api/keys`, `import`, `upload`, `delete`, `clear`, `load-file`, `/api/reset-keys` | Groq key pool, port of groq_pool |
| `/api/claude/ask`, `tell`, `status`, `sessions`, `transcript` | headless `claude -p` on the plan; consent gate (409) kept |
| `/api/supervisor/propose`, `pending`, `get`, `recent`, `decide`, `/api/skills/list` | `~/.groq/approvals/*.json` |
| `/api/training/correct`, `status`, `build` | events jsonl; status/build run build_dataset through a small Python helper |

The security guard (Origin, Referer, Sec-Fetch-Site, X-Queen-Token) runs before every route, native or proxied.

## What /api/chat still asks Python (said plainly)

- **Local chat commands** (volume, settings, WhatsApp, ax, Affinity, rename, repo, "ask claude", photos, screen, describe,
  posters): too big for one night. Swift asks `POST /api/internal/local_command` on the backend first. A hit is answered
  without Groq, in the same NDJSON shape as before.
- **After the answer** (training "output" event, her command lines run, handover line): `POST /api/internal/after_turn`.
- The Groq call, the prompt, the pool, the failover, the ledger and the telemetry line are Swift.
- If the backend is down, Groq still answers; only the local commands and the after-turn work are missing.

## Proxied to 8766 (unchanged)

brain (`/api/brain/*`, used by macro_router), router, vision (`/api/vision/ask`), screen, ax, whatsapp (`send`, `remote`,
`supervised`, `ax/latest`), affinity, gemini, posters and other skills, star, voice, elevate, repo, github, news, handover,
data-sync, self_update, auto_update, key_tester, system, terminal/log, test/live, a multipart key upload.

## Tests (CI, `mac_app/tests/main.swift`)

The server starts on a free port with a temporary `~/.groq`, a fake Groq, a fake Python backend and a fake `claude`.

- Shape of every core route above, and their 400/404/409 answers.
- Failover: key 1 gives 401 (cooled for every model, 30 days), key 2 gives 429 with Retry-After 7 (cooled for that model,
  7 s), key 3 answers. Telemetry says `failovers: 2`. `key_state.json` is checked on disk.
- NDJSON streaming read by URLSession, the telemetry numbers, the cost, the ledger file.
- The system prompt equals Python's `build_queen_system_prompt()` byte for byte, from the live app.py and from the bundled copy.
- The proxy: body and query unchanged, the first streamed line arrives at once (not at the end), HTTP/1.0 and 1.1, 502 when the
  backend is down.
- SSE: init, a Swift event, a relayed backend event.
- The guard; and no full key appears in any of the 54 answers.

## Open risks

1. **Not run on a real Mac yet.** The tests use fakes. The first real chat is the morning test.
2. **Install order.** Run `./install.sh` (Python) before or right after v5. The v4 app's updater will offer v5 at start; if it
   is taken first, chat works but the local commands and the after-turn work wait for `install.sh` and a START QUEEN.
3. **Permissions.** Python is now a child of the app, so Accessibility and Screen Recording belong to the app, not iTerm2.
   PERMISSIONS (amber) shows when Accessibility is missing; Screen Recording may ask once for screen reading.
4. **Queen lives with the app.** Closing the window keeps her running; OFF or quitting the app stops her and the backend.
5. **A LaunchAgent that starts Python on 8765** (if one exists) would now open the app instead, through the new `qwen`.
6. **Two pools on one file.** Both read key_state.json before every decision; a write race inside the same millisecond is
   still possible and harmless (a cooldown may be lost once).
7. The old web page is not served on the Mac any more (8765 and 8766 both give a plain line). With the app quit,
   `QWEN_STANDALONE=1 qwen` brings back the old Python-only Queen and her page on 8765.

## Phase B plan, by hand group

Each group moves to Swift on its own version, with its own CI tests. Its routes leave the proxy only when that version is green.
Suggested order: small and much used first.

| # | Group | Python today | Routes | In Swift |
|---|---|---|---|---|
| 1 | star | app.py | `/api/star/startup`, `/api/star/action` | a JSON pass-through to :8863 |
| 2 | voice | app.py | `/api/voice/speaking, voices, speak, pause, stop, hear` | a pass-through to :8837 |
| 3 | system | system_volume.py, system_settings.py | `/api/system/volume`, `/api/system/settings[/panes]` | CoreAudio, NSWorkspace, AX window title |
| 4 | news/handover/data-sync | news.py, data_sync.py | `/api/news`, `/api/handover`, `/api/data-sync` | files + git through Process |
| 5 | repo/github | repo_reader.py, app.py | `/api/repo/*`, `/api/github/*` | git/gh through Process, FileManager search |
| 6 | ax/whatsapp | ax_read.py, whatsapp_ax.py, whatsapp_remote.py, whatsapp_supervised.py, whatsapp_machine.py | `/api/ax/read`, `/api/whatsapp/*` | axread is already Swift (AXUIElement); BiDi through URLSessionWebSocketTask |
| 7 | screen/vision | screen_look.py, vision.py, live_check.py, describe_skill.py | `/api/screen/look`, `/api/vision/ask`, `/api/selfcheck/image-live`, `/api/skills/describe-images` | ScreenCaptureKit, the Swift pool with image_url |
| 8 | brain/router | brain.py, model_router.py | `/api/brain/*`, `/api/router/*` | the Swift Groq client (macro_router depends on it: test it first) |
| 9 | affinity | affinity_bridge.py | `/api/affinity/*` | its MCP/JS SDK over its socket |
| 10 | gemini/CDP | gemini_skill.py, cdp_broker.py | `/api/gemini/image` | CDP over URLSessionWebSocketTask |
| 11 | skills posters | poster_skill.py, web_photo_skill.py, image_collect_skill.py, book_skill.py | `/api/skills/*` | after 7, 9 and 10 |
| 12 | elevate | app.py | `/api/elevate/*` | files, WhatsApp drafts, Gemini (after 6 and 10) |
| 13 | self_update | app.py | `/api/self_update/*` | rethink: Queen's code is Swift now, so an update is a commit + CI, not a file swap |
| 14 | auto_update | auto_updater.py (1,773 lines) | `/api/auto_update/*`, `/api/key_tester/*` | the biggest; last |
| 15 | chat commands + after-turn | the chain in app.py, rename_skill.py, training_log.py | `/api/internal/*` | once every hand above is Swift |

Then **Phase C**: delete Flask, the 8766 backend and the proxy. Small Python helper scripts (like gen_prompt.py and the
build_dataset helper) may stay.
