# check-your-shape (taught 22.11.2026 by Claude Code, after the audit of v31)

When: Marko or a session says "check your shape", "check yourself", "self check", "health check", or asks whether
Queen is all right after an update or after another AI changed her.

Do: answer with the self-check, never from memory. It is local and costs $0:
- chat: `check your shape` (the Python skill self-check answers before any model)
- route: `GET /api/queen/selfcheck` -> `{ok, problems, lines, missing_routes, text}`
- CLI for sessions: `queen "check your shape"`, and `queen status` (brain + modules)

It checks five things and says OK or PROBLEM for each:
1. versions: the running app (8765), her backend, version.json, the repo. They must be one number.
2. modules: every Groq-free module loaded (`GET /api/queen/modules`: loaded, failed, Groq-bound off).
3. routes: every /api/... route named in her skills is registered (other apps' doors and the Groq-bound ones are
   listed apart, they are off on purpose).
4. brain: the local Claude Code reachable on the plan. Not reachable: say "I cannot reach the local Claude Code. Do you
   want to use API credits?" and wait.
5. skills: every skill file readable, none empty, none identical to another.

Traps:
- Do not "fix" a PROBLEM yourself: report it with the line as it is. Fixes are Claude Code's, through GitHub (her
  workflows python-tests and mac-app), a whole-number version and her own update.
- Do not restart yourself to make a check pass; do not call a model or a paid provider for this skill.
- A version mismatch right after a release is normal until the app updates itself at its next start: say so.
