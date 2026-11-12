When: any poster for a Santoshi concert (or another band with a profile in queen_skills/<profile>.json).
Three ready routes, each one call; the chat sentences in quotes run them:
1. "make posters for the next Santoshi concert" -> `POST /api/skills/band-posters`: every band photo checked by your eyes,
   only real photographs with ALL seven members (two independent looks must agree), one poster per photo, photo's own shape.
2. "make the A4 poster with the band from behind, copy the layout of the AI poster" -> `POST /api/skills/poster-like`:
   A4 portrait, the layout read from the reference poster (img/coming/2026-11-21.jpg), the REAL source photo named in the
   profile (`poster_sources`: the AI poster was an enhanced img/photos/mcam4950.jpg), whole photo in the middle.
3. "make the Gemini posters in English and Croatian" -> `POST /api/skills/gemini-posters`: Gemini extends the wide photo to
   A4 (nothing cropped), then two versions x two languages: full-bleed (the AI poster's layout) and three stripes
   (top: pink lights regenerated in Gemini + title; middle: the band photo uncropped; bottom: the seven portraits from
   img/band with first names, then date, place, entry). Gold hairlines between the stripes.
Where things go (Marko, 12.11.2026): ~/Pictures/<YYYY-MM-DD> Santoshi poster/ holds every photo, every Gemini picture and every
poster as .af (layers, editable) + .png. Affinity may only touch the Desktop, so it works in ~/Desktop/Queen Affinity work/
<same name>/ and the files are copied into Pictures. The posters also stay open as tabs.
Text: English from the reference poster; Croatian from events.json (title.hr, "SUBOTA 21.11.2026. · 19:00–21:00", the place in
capitals, "Ulaz slobodan · donacije dobrodošle"). Font Oswald (SemiBold for bold lines). Centred by a PARAGRAPH delta.
Check every poster before saying done: `POST /api/affinity/render {uuid}` and look: faces free, text inside the page, readable.
Traps met: your eyes do not understand "from behind" (Marko chose the photo); an AI illustration once passed as "the whole
band"; a 6-person phone frame once passed the checklist (hence the second look); the site's img/band portraits are
photographic renderings made from real photos (band.json says so) and are fine for the member stripe.
