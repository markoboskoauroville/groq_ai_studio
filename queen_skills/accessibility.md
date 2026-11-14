# accessibility (Mac only)

Marko, 14.11.2026: "upgrade it with new skills for accessibility ... Without taking screenshots, it needs to use accessibility to get the text."

Use when you must know what an app on the Mac shows as TEXT: a window's words, buttons, fields, a list, a web page in Firefox.
This comes BEFORE any screenshot or vision (read-screen.md is for pictures only: a subtitle drawn into a video, a photo).

How (free, no model, nothing clicked or typed):
- Route: `POST /api/ax/read {app, window?, query?, text?, depth?, roles?, max?, timeout?, frames?, focused?}`.
  `query` returns only the lines that contain it (`matches`); `text: true` returns the whole tree as indented lines; nothing else
  returns the JSON tree (`windows`: role, title, value, description, x/y/w/h with `frames`, children).
- Chat lines you answer yourself: `ax read <App>` (the whole text), `ax read <App> for <words>` (only the lines with the words),
  `read the accessibility text of <App>`.
- The reader is the Swift `axread` (~/.local/bin/axread, inside /Applications/Groq AI Studio (Mantra).app); without it the same walk
  runs in Python. `via` says which. `axread --apps` lists the running apps, `axread --trusted` checks the permission.

Rules:
1. Text only. Never take a screenshot to read words that Accessibility gives you.
2. Read, never act: this skill does not click, type or press. Acting is Macro Recorder's (`macro ax-press`) and always supervised.
3. `trusted: false` = the process that started you has no Accessibility permission: say so ("PERMISSIONS in Groq AI Studio (Mantra)
   or System Settings > Privacy & Security > Accessibility"), never guess the text.
4. Only windows on the current Space are visible to Accessibility, and in a browser only the SELECTED tab. Empty `windows` = say that,
   do not invent content.
5. Quote what you read exactly; when the reader truncated (`truncated: true`), say the list may be longer.
6. Web pages: Firefox and Chrome hide the page until an assistive client asks; the reader switches it on (AXManualAccessibility),
   the first read after a fresh start can be empty: read again once.
