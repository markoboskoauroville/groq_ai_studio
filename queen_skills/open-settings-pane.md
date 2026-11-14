# Skill: open-settings-pane (Mac only)

Marko, 14.11.2026: asked Queen to open System Settings -> Control Center. She answered "Done" with a bare `open x-apple.systempreferences:...`,
but the window said "Accessibility" and another app was in front. She had not looked.

**When:** he asks to open any Settings / System Settings page or pane ("open the Control Center settings page", "open Bluetooth settings",
"open the keyboard settings", "otvori postavke zvuka").
**How:** the chat sentence is answered locally, $0. Route: `GET /api/system/settings?pane=<name>` (names: `GET /api/system/settings/panes`;
control center, keyboard, displays, sound, accessibility, privacy, bluetooth, wi-fi, general, battery, network, notifications, ...).
It runs `open x-apple.systempreferences:<id>`, brings System Settings to the front, reads the real window title and the front app through
System Events, retries once, and returns `{ok, expected, title, front_app}`.
**Check:** say "opened" ONLY when `ok` is true, i.e. `title` equals `expected` and `front_app` is System Settings. Otherwise report the
returned `error` honestly with the title you got; never claim success from the `open` command alone.
**Traps:** do not write your own `open "x-apple.systempreferences:..."` command; do not invent other routes. Leave the pane open: it is for Marko.
Quitting System Settings is not part of this skill. Needs Accessibility permission for the Queen process to read the title.
