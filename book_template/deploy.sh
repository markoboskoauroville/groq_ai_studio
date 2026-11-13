#!/bin/bash
# deploy.sh: builds the book and puts it on Cloudflare Pages (https://<pages>.pages.dev, the name in book.json).
# The Cloudflare account id and token are read from ~/Downloads/API/Cloudflare.api.txt and never printed.
set -euo pipefail
cd "$(dirname "$0")"
python3 build.py
PAGES=$(python3 -c "import json;print(json.load(open('book.json'))['pages'])")
eval "$(python3 - <<'PY'
import re,os
raw=open(os.path.expanduser('~/Downloads/API/Cloudflare.api.txt')).read()
acc=re.search(r'dash\.cloudflare\.com/([0-9a-f]{32})', raw).group(1)
tok=[l.strip() for l in raw.splitlines() if re.fullmatch(r'[A-Za-z0-9_\-]{30,}', l.strip())][-1]
print(f"export CLOUDFLARE_ACCOUNT_ID={acc}; export CLOUDFLARE_API_TOKEN={tok}")
PY
)"
W="npx --yes wrangler@3"
rm -rf dist && mkdir dist && cp -R index.html BOOK.md sitemap.txt robots.txt dist/ && { [ -d img ] && cp -R img dist/ || true; }
$W pages project create "$PAGES" --production-branch main 2>&1 | grep -v -i "token\|account" | tail -1 || true
$W pages deploy dist --project-name "$PAGES" --branch main --commit-dirty=true 2>&1 | grep -v -i "token\|account" | tail -3
rm -rf dist
