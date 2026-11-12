When: "describe all images from the Santoshi website" (or any repository of a site): a catalogue of the pictures.
Call: `POST /api/skills/describe-images {repo:"santoshi_band_site", project:"Santoshi poster"}`.
It mirrors the repo, shows every raster image to your eyes (4 at a time), and writes an Excel workbook into
~/Pictures/<date> <project>/: an Index tab (one row per image, with kind, people, size, short description, link on the
site) and ONE TAB PER IMAGE named after the file (31 characters at most), with the description inside (Marko's format).
Thumbnails (*_t.*) are listed and point to their original; SVG is listed only. Descriptions are cached: re-runs are free.
Say how many were described, the cost and where the workbook is.
Quality (12.11.2026): the question names the band's real instruments (no tabla/ukulele guesses) and the members by look;
a crowd/stage picture with 0 members recognised is marked 'ai-generated? (no band member recognised)'.
Re-describe everything with {force:true} after the question improves.
