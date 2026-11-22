# Skill: tell-marko-on-screen (a short notice on his screen; local, no model, $0)

Marko, 22.11.2026: "the text blob which needs to pop up and if something needs to be said to me while I'm working on computer and
you are working in the background ... You can use the computer now."
**When:** "tell Marko on screen that ...", "tell Marko: ...", "blob: ...", "put a blob on screen saying ...", or any time you work
in the background and have ONE short thing to tell him that needs no answer (a test is done, you are about to take the keyboard).
**What:** Macro Recorder (Mantra) v32+ shows a dark rounded panel at the top centre of the screen where he is working. It never
takes focus, shows over full-screen apps, makes no sound, at most three at once. It also shows "You can use the computer now" by
itself when the input lock is released: do not send that yourself.
**Command:** `macro blob "<text>" [--kind info|done|ask] [--seconds N] [--sticky] [--id ID]`, `macro blob --clear <id|all>`.
Chat: `tell Marko on screen that the test is done` (the local skill runs it, no model). From a session: `queen "tell Marko on screen that the test is done"`.
**Kinds:** info = grey, neutral; done = green, finished or "you can work" (chosen when the text says done, finished, ready, complete);
ask = amber, "I need you" (chosen when the text says I need you or waiting for you).
**Write it:** English, one or two short sentences, plain text (no markup), at most about 150 characters; three lines is the limit.
**Never for questions that need an answer:** the question goes in the chat (and by voice when the Voice Engine is on); a blob can
only say "I need you in the chat". Re-use `--id` to update a blob, `--clear` it when it is no longer true.
**Check before "done":** the answer starts `Told Marko on screen`; the log ~/.mantra_macro/blob_log.jsonl has the line with the full text.
**Traps:** Macro Recorder must run and be v32 or newer (`macro blob` says "not running" otherwise). While his input lock is held he
cannot click a blob closed: it leaves by time. Do not flood him: one notice per event.
