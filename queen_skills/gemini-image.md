When: a picture must be made or changed for free: extend a photo to another shape, regenerate a background, enhance,
storyboard frames from character/product references (Elevate Media UGC, 21.11.2026).
Call: `POST /api/gemini/image {prompt, image, out, aspect?}`: Gemini in Marko's Chrome over its DevTools (broker
127.0.0.1:9333, remote debugging on). `image` is one path OR a list of paths: several references are attached at once
(say in the prompt "Image 1 is ..., Image 2 is ..., Image 3 is ..."). `aspect` "9:16" / "3:4" / "1:1" / "4:3" / "16:9"
sets the Aspect ratio chip of Gemini's Create image tool. Python: `gemini_skill.make_image(prompt, [paths], out,
account=..., aspect="9:16", max_accounts=8, skip={...})`. Never Firefox, never the download button.

THE METHOD (fixed 21.11.2026, proven on marko.bosko@gmail.com and cafeteriavc.media@auroville.org.in):
1. open gemini.google.com/app in the profile's window (focus emulated, background tab, Marko's screen untouched);
2. patch HTMLInputElement.prototype.click so the file input Gemini clicks is CAUGHT (marked data-q-cap) instead of
   opening the macOS chooser;
3. '+' ("Upload & tools", found by aria-label, visible copy only) -> "Upload files" ([role=menuitem]); press '+' only
   when its menu is not already open (a second press closes it);
4. DOM.setFileInputFiles on the caught input's node with all the files; wait until the thumbnails are there and the
   upload spinner is gone (fallback: Page.fileChooserOpened -> backendNodeId);
5. '+' -> "Create image" ([role=menuitemcheckbox]) -> chip "Aspect ratio" -> [role=menuitemradio] "9:16";
6. type the prompt (Input.insertText), press Send, wait for the picture, copy its bytes from Chrome's memory
   (Page.getResourceContent). Gemini serves WebP: the file is converted to the format its name says (sips).
Why it failed before (21.11.2026 06:30): Chrome's file-chooser event did not come back through the broker, the '+' was
pressed twice (menu closed), the preview test counted hidden copies.

WAITS FOR MARKO (never pressed by Queen; the account is skipped and the next one used; screenshots in ~/.groq/gemini_fail):
- "Creating content from images and files ... Agree" on an account's first upload (av.live.vmix@gmail.com, 21.11.2026);
- Gemini's landing page / "Use Gemini" first-use consent (father.aya@gmail.com, 21.11.2026);
- a sign-in. Tell Marko which account and bring that window to the front of the MacBook screen for him.

WINDOWS (Marko, 21.11.2026: "Anything you generate with Gemini automatically, put the windows on the Mac screen."): every
profile window opened for a picture goes to the MacBook's built-in display at once (`macro win-snap "Google Chrome – <profile
name>" maximize 2`, checked in `macro win-list` = "Built-in Retina Display"), never the BenQ; done by `_to_mac_screen`.

ROTATION: when an account refuses ("I can't create images" / limit), times out (3 min) or waits for Marko, the next
Chrome profile signed in to Google takes over (window opened by Chrome's launcher; tabs it opened are closed after).
marko.bosko@auroville.community first, santoshi.bend and mantreshvar.margii last. Start the next picture with the account
that made the last one (`r["account"]`). One image at a time. In-tab account switching: skill gemini-switch-account.
Save every result in the project's folder and reuse it (no second generation for the same picture). Log the account used.
Prompts that work: say what must stay EXACTLY (people, faces, clothes, product label) and what only may change; ask for
photorealistic, same light and colours, "no captions or text".
