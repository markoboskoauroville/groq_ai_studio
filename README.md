# Queen

This repository contains Queen's macOS app and local Python runtime. The app owns
`127.0.0.1:8765`; it starts the Python API/skills backend on `127.0.0.1:8766` and
proxies CAPI and Auto Update routes to it.

## Runtime model

- Recognized commands run as deterministic Python skills in
  `qwen_app/queen_python_skills/`, without a model call. The provider-independent
  Ableton skill controls Live through guarded AbletonOSC actions.
- Unmatched CAPI prompts use the selected external provider. The runtime has no
  internal Groq chat or key manager.
- Since v32 (audit 22.11.2026) `queen "<q>"` and `/api/chat` are answered by the
  local Claude Code on the plan with her skills (queen_skills/) as system prompt;
  one local router (`qwen_app/local_router.py`) answers known commands first on
  every entry point. The Groq-free routes of the old server are registered again
  (`qwen_app/restored_routes.py`, `GET /api/queen/modules`); the Groq-bound ones stay off.
- Self-check: chat `check your shape`, `GET /api/queen/selfcheck`.
- State is stored under `~/.queen`. On first runtime start, selected CAPI and
  Google/Anthropic updater state is copied from `~/.groq`; legacy model keys and
  the old directory are not copied or deleted.

The current Python skill catalog contains `list-skills`, `current-folder`,
`ableton-control`, `webcam-recorder`, `gemini-image`, `self-check` (and lan-scan by phrase). Ableton actions are available through `GET /api/ableton/capabilities`,
`POST /api/ableton/action`, or explicit `ABLETON:`
commands in CAPI. Android-emulator actions, including timestamp-named audio
recording, have not yet been converted into Python skills.

## Build and validate

The macOS app is built and packaged by GitHub Actions (mac-app.yml); the Python tests run there too
(python-tests.yml). Never compile on the Mac. Local offline checks (Python only):

```sh
python3 qwen_app/test_queen_backend.py
python3 qwen_app/test_capi_features.py
python3 qwen_app/test_pair_chat.py
python3 qwen_app/test_audit_fixes.py    # includes the pin: every route named in queen_skills/ is registered
```

Install the Python runtime with `./install.sh`. The app release installer is
`mac_app/install.sh vN`.

See [TAKEOVER.md](./TAKEOVER.md) for runtime details and outstanding work,
[LESSONS.md](./LESSONS.md) for operational lessons, and
[CAPI_PYTHON_API.md](./CAPI_PYTHON_API.md) for the CAPI interface.
