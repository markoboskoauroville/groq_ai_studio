"""build.py: book.json + chapters/NN.md + img/NN.jpg -> index.html (the whole book on one page), BOOK.md, sitemap, robots.

    python3 build.py            (no packages needed; run from the book's folder)

The illustrated-book rule (MANTRA_MANIFEST modules/illustrated-book.md): one page, the shared night stylesheet, a plate at
every chapter, a contents list with anchors, a colophon. Chapters are Markdown written by Queen: paragraphs, ### headings,
**bold**, *italic*, `code`, lists, > quotes and ``` blocks. A chapter or a plate that does not exist yet is left out of the
page and named in the build's report, so a half-made book still builds.
"""
import html
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
SPEECHIFY = '<script src="https://speechifykeys.pages.dev/speechify-keys.js" defer></script>'
TABS = ["#C9A46B", "#D8B270", "#DFAB57", "#D68A55", "#CE7A4C", "#C46B41", "#B85F3C", "#AC5636", "#A14E31", "#9A4A2A",
        "#8F4427", "#843E24"]


def inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?!\w)", r"<em>\1</em>", t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', t)
    return t


def md(text):
    out, para, lst, code = [], [], None, None

    def flush():
        nonlocal para, lst
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para = []
        if lst:
            tag = lst[0]
            out.append(f"<{tag}>" + "".join(f"<li>{inline(i)}</li>" for i in lst[1:]) + f"</{tag}>")
            lst = None

    for line in text.splitlines():
        if code is not None:
            if line.strip().startswith("```"):
                out.append("<pre><code>" + html.escape("\n".join(code)) + "</code></pre>")
                code = None
            else:
                code.append(line)
            continue
        s = line.strip()
        if s.startswith("```"):
            flush(); code = []
        elif not s:
            flush()
        elif s.startswith("#"):
            flush()
            level = min(4, max(3, len(s) - len(s.lstrip("#"))))
            out.append(f"<h{level}>{inline(s.lstrip('#').strip())}</h{level}>")
        elif s.startswith(">"):
            flush(); out.append(f"<blockquote><p>{inline(s.lstrip('>').strip())}</p></blockquote>")
        elif re.match(r"^([-*]|\d+[.)])\s+", s):
            para and flush()
            tag = "ol" if s[0].isdigit() else "ul"
            if not lst or lst[0] != tag:
                flush(); lst = [tag]
            lst.append(re.sub(r"^([-*]|\d+[.)])\s+", "", s))
        else:
            if lst:
                flush()
            para.append(s)
    flush()
    return "\n".join(out)


def main():
    b = json.loads((HERE / "book.json").read_text())
    url = f"https://{b['pages']}.pages.dev/"
    missing, toc, body, plain = [], [], [], [f"# {b['title']}\n\n*{b['subtitle']}*\n\n{b['byline']}\n"]
    for i, c in enumerate(b["chapters"]):
        f = HERE / "chapters" / f"{c['n']:02d}.md"
        img = HERE / "img" / f"{c['n']:02d}.jpg"
        if not f.exists():
            missing.append(f"chapter {c['n']}")
            continue
        text = f.read_text(encoding="utf-8").strip()
        text = re.sub(r"^#\s+.*\n+", "", text)                       # the title comes from book.json
        toc.append(f'<a class="toc-row" href="#{c["slug"]}" style="--bg:{TABS[i % len(TABS)]}"><span class="n">{c["n"]}</span>'
                   f'<span class="t">{html.escape(c["title"])}</span><span class="d">{html.escape(c["dek"])}</span></a>')
        plate = ""
        if img.exists():
            plate = (f'<figure class="plate sketch"><img src="img/{img.name}" alt="{html.escape(c["alt"])}" loading="lazy">'
                     f'<figcaption>{html.escape(c["caption"])}</figcaption></figure>')
        else:
            missing.append(f"plate {c['n']}")
        body.append(f'<section class="chapter" id="{c["slug"]}">\n<header class="ch-head"><p class="ch-kicker">'
                    f'{html.escape(c["kicker"])}</p><h2>{html.escape(c["title"])}</h2><p class="dek">{html.escape(c["dek"])}</p>'
                    f'</header>\n{plate}\n{md(text)}\n</section>\n<p class="rule" aria-hidden="true">&#10022;</p>')
        plain.append(f"\n## {c['n']}. {c['title']}\n\n*{c['dek']}*\n\n{text}\n")
    cover = HERE / "img" / "cover.jpg"
    hero = (f'<div class="hero-lamp"><img src="img/cover.jpg" alt="{html.escape(b["cover_alt"])}" loading="eager"></div>'
            if cover.exists() else "")
    if not cover.exists():
        missing.append("cover")
    css = (HERE / "style.css").read_text()
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<meta name="theme-color" content="#16110D">
<title>{html.escape(b['title'])} &mdash; {html.escape(b['subtitle'])}</title>
<meta name="description" content="{html.escape(b['description'])}">
<meta name="author" content="{html.escape(b['author'])}">
<link rel="canonical" href="{url}">
<meta property="og:site_name" content="{html.escape(b['title'])}">
<meta property="og:title" content="{html.escape(b['title'])}">
<meta property="og:description" content="{html.escape(b['description'])}">
<meta property="og:type" content="book">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{url}img/cover.jpg">
<meta name="twitter:card" content="summary_large_image">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..900;1,9..144,300..700&family=Newsreader:ital,opsz,wght@0,6..72,300..700;1,6..72,300..600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><path d='M8 27 22 5l3 2-14 22z' fill='%23E8A64B'/><path d='M8 27l-1 3 3-1z' fill='%23E2D0B5'/></svg>">
<script type="application/ld+json">{json.dumps({"@context": "https://schema.org", "@type": "Book", "name": b["title"], "alternativeHeadline": b["subtitle"], "author": {"@type": "Person", "name": b["author"]}, "inLanguage": "en", "isAccessibleForFree": True, "url": url, "datePublished": b["date"]})}</script>
<style>{css}</style>
</head>
<body>
<div class="wrap">
<header class="masthead">
{hero}
<p class="eyebrow">{html.escape(b['eyebrow'])}</p>
<h1>{html.escape(b['title'])}</h1>
<p class="sub">{html.escape(b['subtitle'])}</p>
<p class="byline">{b['byline_html']}</p>
</header>
<nav class="toc" id="contents" aria-label="Contents"><h2>Contents</h2>
{chr(10).join(toc)}
</nav>
{chr(10).join(body)}
<footer class="colophon"><p class="flame">&#10022;</p>{b['colophon_html']}</footer>
</div>
{SPEECHIFY}
</body>
</html>
"""
    (HERE / "index.html").write_text(page, encoding="utf-8")
    plain.append("\n---\n\n" + re.sub(r"<[^>]+>", "", b["colophon_html"]) + "\n")
    (HERE / "BOOK.md").write_text("".join(plain), encoding="utf-8")
    (HERE / "sitemap.txt").write_text(url + "\n")
    (HERE / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {url}sitemap.txt\n")
    print(json.dumps({"built": "index.html", "chapters": len(body), "missing": missing}))


if __name__ == "__main__":
    main()
