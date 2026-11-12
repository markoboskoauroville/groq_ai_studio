# Queen's profile: what Groq AI Studio is good at, and where it must be watched

Marko, 12.11.2026: "His best advantage is that he is fast as a thunderstruck. We need to use this in our everyday work,
but we need to understand his strong sides and his weak sides. Go and test him and build his profile."

Measured on 12.11.2026 by `MANTRA_CHROME_EXTENSIONS/tools/queen_bench.py`: seven Chrome extensions, trivial to complex,
each graded mechanically (manifest parses, required MV3 fields, every declared file written, every file reachable,
every `chrome.*` API declared, every `.js` parses under `node --check`). Model `qwen/qwen3.8-27b`.

## The ladder

| # | What it was asked to build | Verdict | Time | Cost |
|---|---|---|---|---|
| 1 | A valid MV3 manifest, nothing else | clean | 0.4 s | $0.0011 |
| 2 | Content script that rewrites `document.title` | clean | 0.5 s | $0.0015 |
| 3 | Popup that reads the page with `scripting.executeScript` | clean | 0.9 s | $0.0025 |
| 4 | Content script -> service worker -> `storage.local` -> badge | **broken** | 0.8 s | $0.0027 |
| 5 | Finds a dollar amount on a page and stores it | **broken** | 1.0 s | $0.0033 |
| 6 | Service worker polling a local server, forwarding DOM commands | clean | 2.6 s | $0.0067 |
| 7 | Human-like typing and clicking, retries, `runtime.reload()` | **broken** | 2.1 s | $0.0065 |

Seven working-or-nearly-working extensions in **8.3 seconds for 1.4 cents**. That is the advantage, and it is real.

## The one weakness, and it is always the same one

Every single failure was the same defect: **the manifest and the files disagree.** Never a logic error. The JavaScript
always parsed, and always did the thing that was asked.

| # | What it got wrong | What Chrome does about it |
|---|---|---|
| 4 | Calls `chrome.action.setBadgeText` but never puts `"action"` in the manifest | throws at runtime, badge never appears |
| 5 | Manifest names `popup.html`; the file was never written | the extension refuses to load at all |
| 7 | Writes `content.js`, then declares no `content_scripts` and never injects it | dead code, the feature silently does nothing |

Levels 4 and 5 were re-run twice more: **3 failures out of 3 each time.** This is systematic, not bad luck. And note
that the two hardest levels passed while two middle ones failed — so this is not a complexity ceiling. It is a blind spot.

## So where is the line for leaving him alone?

**The honest answer is that the line is not a difficulty level — it is whether a machine checks his work.**

Every defect above is caught in under a second by `tools/extcheck.py`, which also prints the exact fix
("add `"action": {}` to the manifest"). With that linter in the loop, Queen can be left unsupervised at **every level
tested**, including the hardest. Without it, he cannot be trusted past level 3, because the failures are invisible:
nothing crashes, the extension just quietly does not work.

| Leave him alone | Watch him |
|---|---|
| Writing any extension, at any level, **when `extcheck` runs and passes before the result is used** | Deciding **what** should be built, and which permissions are reasonable |
| Anything whose output a program can check: code that must parse, JSON that must validate, files that must exist | Anything that spends money, touches Marko's accounts, or cannot be undone |
| Fast first drafts to be checked — his real job | Anything where being wrong is silent and expensive to discover later |
| Repeated, shaped work: the same kind of extension again with different details | Security and privacy judgements, and anything a checker cannot express |

## What this means for how he works

1. **Never accept his output unchecked.** `extcheck <dir>` before anything is loaded. It is 10,000x faster than he is.
2. **Two strikes, then escalate.** If he fails the same check twice, he has hit his limit. He then calls Claude through
   the Anthropic API for the fix, and the lesson is written into a skill so neither of them repeats it.
3. **Use him for the first draft, always.** At under half a cent and a second or two, a draft from Queen that a linter
   then corrects is far cheaper than anything else on this Mac.
4. **He does not know he is wrong.** None of the three broken extensions came with a warning or a hedge. His confidence
   is identical whether he is right or wrong, so the check is not optional.

## Where everything lives

| Repository | What |
|---|---|
| `markoboskoauroville/groq_ai_studio` | Queen herself: the Flask server, the page, the key pool, the auto-update engine, her skills in `skills/`, and this profile |
| `markoboskoauroville/groq-auto-update` | the public mirror her CI-validated self-updates are pushed to |
| `markoboskoauroville/MACRO_SKILLS` (private) | the hands: the action catalogue, the blocks, the macro router, `chrometabs` |
| `markoboskoauroville/MANTRA_CHROME_EXTENSIONS` | the extensions she builds, `extcheck.py`, and `queen_bench.py` which produced this table |

Re-run the measurement at any time: `python3 tools/queen_bench.py` (about 1.4 cents, under a minute).
