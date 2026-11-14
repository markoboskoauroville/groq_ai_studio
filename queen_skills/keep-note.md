When: Marko asks to put a note, a link, a reminder or a text into his Google Keep ("write this to my Keep", "save the link to Keep").
Rule: Keep has no API for personal accounts; the only hand is his Pixel 7 over adb. Never click Keep yourself, never use the emulator.
Steps:
1. Run `keepnote "<title>" "<text or link>"` (title short, text the link or the words, exactly as given). It locks the phone with a
   countdown, opens Keep's share dialog, presses Save, unlocks and brings his Claude app back. Exit 0 and "saved" = done.
2. Test first with `keepnote "<title>" "<text>" --dry-run` when unsure: it opens the dialog and discards.
3. Do NOT run it twice for one note (it creates a copy each time). If it says the lock was overridden, stop: he took the phone; wait.
4. The note lands in marko.bosko@gmail.com Keep (his notes); tell him that. Proof: the screenshot path it prints.
5. If the phone is not reachable it prints so: tell Marko, never fall back to guessing.
Catalogue: macroskill has "google keep note" (action keep-note, repo MACRO_SKILLS).
