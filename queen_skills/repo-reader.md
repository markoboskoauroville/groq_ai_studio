When: "find in the repo", "what does repository X say about Y", "read file F", "search for", any question whose answer is in
Marko's GitHub repositories. READ ONLY: never write to GitHub.
Steps:
1. Which repo: `GET /api/repo/list` (name, description, privacy, size). Pick by name/description; several are fine.
2. `GET /api/repo/sync?repo=<name>` mirrors it (first time a few seconds; repos over 400 MB need big=1: ask Marko first,
   his SIM data is precious; for one file of a big repo use `GET /api/github/contents?repo=owner/name&path=F` instead).
3. Search: `GET /api/repo/search?repo=<name>&q=<text>` (regex=1, context=2, path=dir, repo=all for every mirrored repo).
   Search several words and spellings (Croatian too: koncert, studeni...).
4. Read: `GET /api/repo/tree?repo=<name>&q=<words>` then `GET /api/repo/read?repo=<name>&path=<file>&start=&end=`.
5. Answer with the facts AND the file each came from; say how old the file is if it matters ("last read 25.10.2026").
Chat shortcuts Marko can type: `tree R`, `read R:path lines A-B`, `search R for text`, `sync R`.
Secret files (.env, keys, tokens) are never shown.
