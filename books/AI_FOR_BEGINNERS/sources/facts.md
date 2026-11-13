# FACTS (true, from Marko's house, 12-13 November 2026). Use only these numbers.

## The people and the machines
- Marko Bosko: a musician and maker in Auroville (India) and Croatia. He builds his own apps with AI and talks to it by voice.
- Queen: Marko's name for his AI helper. Her model is Qwen (qwen3.6-27b, about 27 billion numbers), run by the company Groq.
  She lives in a program on his Mac called Groq AI Studio.
- Claude (Opus): the teacher. On 13 November 2026 Marko made the rule: "You stop doing anything physically in this computer
  ... Mantra, Macro, and Queen are doing everything. You are just giving the tasks. You are writing the skills, and you are
  assessing and reviewing ... You are the master teacher ... corrections until they come to the level of your Opus model."
- Macro Recorder: Marko's program that moves the mouse and presses keys; one of Queen's "hands".

## Queen's first big job (13 November 2026)
- Rename two apps to "Mantra Remote Viewing": a Mac app that shows a computer in the cloud, and an Android phone app.
- She did it in about two hours, with 11 rounds of corrections. Every step waited for the teacher's yes or no.
- Mistakes, each turned into a written rule (a "skill") she reads before every answer:
  1. She wrote placeholders like <exact name> instead of real names; they ran as written.
  2. She fired three steps at once (rename, install, rename the repository); the install would have put the OLD version.
  3. She used a short name; the real app name was longer.
  4. The title in CAPITALS stayed unchanged; then a fix would have made it mixed case. Rule: each place keeps its own letter case.
  5. A name change would have broken a web link into a repository that does not exist.
  6. She wrote "RDP" in a note for a program that speaks "VNC". Rule: use only words you are sure of.
  7. Once she invented fake tool calls instead of her real commands.
- The teacher made mistakes too, and they are part of the story:
  - Claude deleted, by accident, the line of code that applied the rename; a test now checks every lesson before Queen is installed.
  - Claude's first "bandwidth saver" for a video class would have frozen the picture of a calmly talking face (it averaged the
    whole picture). Caught in review, before anyone used it.
- Result: Mac app version 29 then 30, Android app version 44 to 46, the repository renamed, everything checked by the teacher.
- A bandwidth saver: when the remote picture stands still, nothing is sent. Measured: 0 bytes in 15 seconds while frozen,
  173 bytes while live.

## The training record (built 13 November 2026)
- Every Queen answer is saved with a turn number; every yes/no of the teacher with its reason; every better answer the teacher writes.
- It goes into a private GitHub repository. Dataset version 1 was made the same day: 39 lessons, 1 corrected answer.
- A new dataset version builds itself after every 25 new examples. Training needs about 100 good examples to start.
- One example in ten is locked away for the exam and never used for practice.
- The exam rule: keep the new version only if it wins at least 60 out of 100 against the old one, judged blind.

## The money (13 November 2026)
- Queen on Groq: 67 calls in about 15 hours cost 0.30 US dollars (219,268 tokens read, 57,643 tokens written).
  Price: 0.80 dollars per million tokens read, 4 dollars per million written. About 15 dollars a month for Marko.
- Renting your own graphics card on RunPod all month: about 245 dollars (cheapest RTX 4090), more on bigger cards.
  Paying per second only while it works: about 40 to 60 dollars a month for Marko's use.
- Your own server pays off only at about 17 times Marko's use.
- Training a small Qwen (4 billion numbers) fits on a free graphics card with 16 GB (Google Colab). A Mac cannot do the
  4-bit training; it needs an NVIDIA graphics card.
