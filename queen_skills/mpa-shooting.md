Skill: MPA shooting assistant (13.11.2026, taught by Claude Code; app MPA Lessons Analyzer (Mantra), API 127.0.0.1:8965)
When: the MPA Lessons Analyzer sends you Marko's spoken words during SHOOT mode, with the shot list as JSON; or Marko asks
you to "shoot lesson 2", "next shot", "play clip 5"; or the app hands you the FINISH PROMPT.
Marko is the teacher Mantreshwar (never "Marko" on the website); the student is Natasha. The recording of the class is the
only source of truth for what goes into the lesson.

1. During SHOOT: answer with ONE JSON line and nothing else: a JSON ARRAY of actions in the order he said them:
   [{"action":"watch|record|again|skip|next|note|edit_shot|add_say","shot":<n>,"text":"<note, new say text, or words to add>"}]
   He often says two things at once ("good, keep it, and on the next one say ..."): give BOTH actions, never drop one.
   edit_shot replaces the say text; add_say appends his words to it (use add_say when he says "also").
   - "yes", "ready", "go", "let's do it" = record. "show me", "what did I do", "play it" = watch.
   - "again", "one more", "that was bad" = again. "skip", "later", "not now" = skip. "good", "keep it", "next" = next.
   - A correction of the plan ("say also the elbow", "drop the foot from this one") = edit_shot with the new say text.
   - Anything else he wants remembered = note. When unsure, choose watch (it changes nothing) and put your doubt in text.
2. By text, from any distance (MANTRA_MANIFEST text-before-files.md): GET /shots, POST /watch {"n"}, POST /play {"n"},
   POST /shoot/start, POST /shoot/action {"action"}, GET /takes, GET /finish. Webcam Recorder has its own API (see
   APPS AND SERVERS.md): POST /record/start {"name"}, POST /record/stop. Never cut or send video files to show a part:
   play start to end of the original.
3. FINISH PROMPT: turn it into tasks, one per kept take, in this order: Resolve (his film-look grade, trim the silence at
   start and end, export H.265 vertical 1080x1920 to the export folder), then the upload, then the website lesson
   (video + text + the Lab sequencer by its code, e.g. TR01; a missing exercise = a new Lab item, never edit his items).
   Every step waits for the supervisor's approval (queen pending). Never publish, never upload before approval.
4. After the task, write in the chat what was done, the file paths, and the self-check (the export exists, its duration
   is the take minus the trims, it plays).

Round 1 (13.11.2026): "good, keep it, and on the next one say also that the left hand is only a touch" was answered with only
edit_shot: the "keep it" (= next) was lost, and "also" means add_say, not replace. Right answer:
[{"action":"next","shot":1},{"action":"add_say","shot":2,"text":"The left hand is only a touch."}]
