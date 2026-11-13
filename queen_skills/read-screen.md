When: Marko or Claude asks what is ON THE SCREEN right now: "is there a subtitle", "what does the window say", "is the app open", "what is the error". Never ask Marko "do you see it?": you look yourself.
Call: `POST /api/screen/look {question, display?: 1|2|"all", region?: [x,y,w,h] in points, window?: "<owner app name>"}`.
Display 1 = the BenQ (2560x1440 points, menu bar), display 2 = the MacBook. It captures silently (nothing comes to the front, no mouse, no key), shrinks the picture and shows it to your eyes. Answer = your reading + screenshot path (~/.groq/work/screen_*.png) + time of capture. Say the time and path with your answer.
Rules (13.11.2026, Marko: "She must tell you. If she lies, then you fix her skill"):
- Answer ONLY what is visible in that capture. Quote the exact text you read, character for character.
- If what was asked about is not visible, the answer is "not visible" / "no subtitle on screen". Never guess from context, never say what "would" be there.
- A blank or black capture (ok:false, blank:true) is a capture failure, not an answer: report the failure, do not describe anything.
- A question is about THIS capture only. For something that changes (a subtitle), capture again; do not reuse an old screenshot.
- Subtitles of the Voice Engine: a band across display 1 at about y=728..838 points, orange text, the word being spoken in red. To read one, ask with region [0,700,2560,160] on display 1 (or the whole display).
- Truth check for subtitles: GET http://127.0.0.1:8837/speaking says "phase":"playing" and gives "sentence" while one is drawn. Any other phase = no subtitle.
Chat command (answered locally, no hand-written route needed): start the message with look / read / check / is there / what / does ... and mention "screen" or "subtitle", e.g. "is there a subtitle on the screen?", "look at the MacBook screen: what is open?". Subtitle questions crop to the subtitle band automatically.
Trap (13.11.2026, her first lie): with no reading playing, the capture showed a terminal's white text in the band and she called it "subtitle text" and quoted it. A subtitle is ORANGE, CENTRED, large text over the picture, the spoken word RED. White/grey/small text in a window, a column or a terminal is window text, never a subtitle. No orange centred text = "no subtitle on screen". Say what colour the text you quote is.
