Skill: open, rename and install apps; rename repositories (13.11.2026, taught by Claude Code)
Marko, 13.11.2026: "rename this repository and application to Mantra Remote Viewing ... she needs to understand."
Since that day YOU do these things; Claude Code only teaches and reviews (MANTRA_MANIFEST modules/claude-teaches-only.md).

When Marko says "open X", "rename the app X to Y", "rename the repo", "install the new version", answer with these chat
commands. Each one is answered locally (no tokens). Write the command line exactly, on its own line:
  open app <name>                                   a star app (Star API :8863); quit app <name> closes it
  rename app "<old visible name>" to "<new name>" in <REPO>
  rename repo <OLD_REPO> to <NEW_REPO>
  install latest <REPO> replacing "<old app name>"  (Mac .zip -> /Applications, or Android .apk -> every adb device)

What to understand before you rename (the traps):
1. The OLD name is the name the app really carries in its code, not the name Marko says. Marko said "Mantra Remote";
   the Android label was "Mantra Remote VNC". Look it up first (search <REPO> for the name) and use the exact string.
2. The app name and the repository name are two different things. An app can live in a repository with other things
   (the Mac viewer lives in vm-chromium together with the VM's agent): rename the APP there, never that whole repository.
3. Never change the bundle id or the Android package: macOS permissions (Accessibility) and phone updates hang on them.
4. A rename is a new version (whole numbers: v28 -> v29). The skill bumps `let VERSION` / `appVersion` itself.
5. Apps are compiled only by GitHub Actions (push to main). The skill watches the run and reports its colour and link.
   A red run is reported red, never "done".
6. Docs keep their history: only README/TAKEOVER titles change, TAKEOVER gets one dated "Renamed" line.
7. A GitHub repository rename is outward: it waits for an approval whose note says Marko asked. The local folder keeps
   its name; only its origin URL changes.
8. After installing: check the new app runs, the version is the new one, the old-named copy is gone, and the star row
   carries the new name. On Android: "Success" from adb for every device. Write what you checked.
Order for a full rename: rename app -> (build green) -> install latest -> rename repo (when asked) -> open app.

Corrections from Claude Code, round 1 (13.11.2026). You wrote `open app <exact name>` and `rename app "<old exact name>"`: those
ran as written and failed. Your commands RUN the moment you write them, one per line, in the order you write them; you get
no second turn to "wait for results". So:
- NEVER write a placeholder (<...>). Write the name as Marko said it: `open app VM viewer`,
  `rename app "Mac VM viewer" to "Mantra Remote Viewing" in vm-chromium`. The skill finds the exact name in the code itself
  and tells you which one it used.
- Do not search first and promise to continue later; there is no later. Write the final commands straight away.
- Write each command once. Do not repeat it in a summary at the end (it would run twice).

Names are hints (Marko, 13.11.2026: "The name can be an approximation ... even an abbreviation ... It needs to offer me the top
5 matches ... what she thinks makes the most sense needs to be at the top."). Pass Marko's words as they are ("remote", "vmrv",
"VM viewer"). The skill ranks every name by probability (words, prefixes, abbreviations, spelling): one clear winner is used
and named; several close ones come back as a numbered list, most probable first, up to 5. Show that list to Marko and wait
for his number; never pick from a close list yourself.
Round 3 (13.11.2026): the Android rename also rewrote a code comment quoting Marko ("update the Android application Mantra
Remote VNC ..."). Rejected: his quoted words are history and stay as he said them. The skill now skips lines that quote him.

Make a code repository public (13.11.2026; MANTRA_MANIFEST building-repos-public.md). Marko: "We have private repositories for
data only, and the pure code of the application is always public." When a build says "recent account payments have failed or
your spending limit", the repository is PRIVATE: never send Marko to billing. Write `make repo public <REPO>`. The skill runs the
three secret checks (patterns, exact key values against files and history, what gets published). A key: it stops. Personal
addresses only: it proposes a history rewrite (no-reply author, addresses masked), then the flip to public, then builds again.
Your data (chats, handover, skills, ledgers) lives in the PRIVATE repo groq_ai_studio_data, mirrored every minute.
Round 4 (13.11.2026): you wrote rename app, install latest and rename repo for one repository and all three ran AT ONCE (the
install would have put the old v42). Now tasks on the same repository QUEUE: they run in the order you write them, each only
after the one before finished well (a red build or a reject stops the rest). So write the whole chain in order, once.
Round 6-7 (13.11.2026): the in-app title "MANTRA REMOTE VNC" (capitals) survived the rename, then a fix would have made it
mixed case. Now the rename finds every spelling of the name in any letter case, and each place keeps its own case
(capitals stay capitals). After an install, LOOK at the app (screenshot) before you say done: the version number alone did not
show the old title. A renamed Mac app that keeps a password in the keychain makes macOS ask Marko once ("wants to access
key"): say so in the plan, and never answer that dialog yourself.
