When: "when is the next Santoshi concert", "what is coming up", date/time/place of a band event.
Steps: 1. `GET /api/repo/read?repo=santoshi_band_site&path=events.json` (the published list: date en/hr, place, start, end).
2. The first event whose `start` is after today is the next one; say weekday, date, time, place, entry.
3. Cross-check `santoshi_band/band/COMING_UP.md` with `GET /api/github/contents?repo=markoboskoauroville/santoshi_band&path=band/COMING_UP.md`
   (the band repo is 440 MB: read the single file, do not mirror it). Say its "Read <date>" and that Instagram is the live source.
Found 12.11.2026: Saturday 21.11.2026, 19:00-21:00, Velika dvorana, Češki narodni dom, Pavla Šubića 20, Zagreb; free, donations welcome.
