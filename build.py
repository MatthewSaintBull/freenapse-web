"""Build freenapse.app into dist/.

Reads the templates in src/, inlines the stylesheet, fetches the releases of
MatthewSaintBull/freenapse from the GitHub API (falling back to the snapshot in
data/releases.json when the API is unreachable) and writes index.html, the
guides, changelog/index.html, 404.html, feed.xml, sitemap.xml and the static
files. index.html is a full page; every other page is a <main> wrapped in
src/_page.html.
Standard library only, so it runs the same on a laptop and on the runner.
"""

import html
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
DIST = ROOT / "dist"
DATA = ROOT / "data" / "releases.json"
SITE = "https://freenapse.app"
REPO = "MatthewSaintBull/freenapse"
API = f"https://api.github.com/repos/{REPO}/releases?per_page=50"
FALLBACK_DOWNLOAD = f"https://github.com/{REPO}/releases/latest/download/freenapse.exe"
AUTHOR = {"@type": "Person", "name": "Matteo Santoro", "url": "https://github.com/MatthewSaintBull"}
NAV = [("/guides/", "Guides"), ("/changelog/", "Changelog"), (f"https://github.com/{REPO}", "GitHub")]

# The guides: src/guides/<slug>.html holds the <main>; the rest comes from here.
# Bump "modified" when a guide's text changes; it goes to the sitemap and the structured data.
GUIDES = [
    {"slug": "set-dpi-polling-rate-without-synapse",
     "title": "Set the Viper V3 Pro DPI and polling rate without Synapse",
     "description": "Change the Razer Viper V3 Pro’s DPI stages and polling rate on Windows without Razer Synapse, with one command or the settings window. The values are stored in the mouse.",
     "published": "2026-10-29", "modified": "2026-10-29"},
    {"slug": "settings-not-saving-onboard-memory",
     "title": "Viper V3 Pro settings not saving to onboard memory",
     "description": "Why the Razer Viper V3 Pro seems to forget DPI, polling rate or button settings, how to read what the mouse actually holds, and the four reasons a setting does not stick.",
     "published": "2026-10-29", "modified": "2026-10-29"},
    {"slug": "uninstall-razer-synapse-keep-settings",
     "title": "Uninstall Razer Synapse and keep your mouse settings",
     "description": "How to remove Razer Synapse 4 from Windows without losing the DPI, polling rate and button settings of a Viper V3 Pro, and what the uninstaller leaves behind.",
     "published": "2026-10-29", "modified": "2026-10-29"},
    {"slug": "razer-synapse-alternatives",
     "title": "Razer Synapse alternatives",
     "description": "The ways to configure a Razer mouse without running Synapse 4: freenapse on Windows, OpenRazer and Polychromatic on Linux, Synapse Web in a browser, or setting the mouse once and removing everything.",
     "published": "2026-10-29", "modified": "2026-10-29"},
]

TAG = re.compile(r"<[^>]+>")


def nav_links(path):
    items = []
    for href, label in NAV:
        if href == path:
            cur = ' aria-current="page"'
        elif href.startswith("/") and path.startswith(href) and path != href:
            cur = ' aria-current="true"'
        else:
            cur = ""
        items.append(f'<li><a href="{href}"{cur}>{label}</a></li>')
    return "\n        ".join(items)


def faq_jsonld(body):
    """The FAQPage structured data, read from the page's own <dl class="qa"> so the two never drift."""
    m = re.search(r'<dl class="qa">(.*?)</dl>', body, re.S)
    if not m:
        return None
    pairs = re.findall(r"<dt>(.*?)</dt>\s*<dd>(.*?)</dd>", m.group(1), re.S)

    def text(s):
        return " ".join(html.unescape(TAG.sub("", s)).replace(" ", " ").split())

    return {"@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": text(q), "acceptedAnswer": {"@type": "Answer", "text": text(a)}}
        for q, a in pairs]}


def guide_jsonld(g, body):
    url = f"{SITE}/guides/{g['slug']}/"
    graph = [
        {"@type": "TechArticle", "@id": url + "#article", "headline": g["title"], "description": g["description"],
         "url": url, "inLanguage": "en", "datePublished": g["published"], "dateModified": g["modified"],
         "image": f"{SITE}/assets/og.jpg", "author": AUTHOR, "publisher": AUTHOR, "about": {"@id": f"{SITE}/#app"}},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "freenapse", "item": f"{SITE}/"},
            {"@type": "ListItem", "position": 2, "name": "Guides", "item": f"{SITE}/guides/"},
            {"@type": "ListItem", "position": 3, "name": g["title"]}]},
    ]
    faq = faq_jsonld(body)
    if faq:
        graph.append(faq)
    data = json.dumps({"@context": "https://schema.org", "@graph": graph}, indent=1, ensure_ascii=False)
    return f'<script type="application/ld+json">\n{data}\n</script>'


def fetch_releases():
    req = urllib.request.Request(API, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "freenapse-web build",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.load(r)
        if isinstance(data, list) and data:
            DATA.parent.mkdir(exist_ok=True)
            DATA.write_text(json.dumps(data, indent=1), encoding="utf-8", newline="\n")
            print(f"releases: {len(data)} from the GitHub API")
            return data
        print("releases: the API answered without a list, using the snapshot", file=sys.stderr)
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        print(f"releases: API unreachable ({e}), using the snapshot", file=sys.stderr)
    data = json.loads(DATA.read_text(encoding="utf-8"))
    print(f"releases: {len(data)} from data/releases.json")
    return data


INLINE = [
    (re.compile(r"`([^`]+)`"), lambda m: f"<code>{m.group(1)}</code>"),
    (re.compile(r"\*\*([^*]+)\*\*"), lambda m: f"<strong>{m.group(1)}</strong>"),
    (re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)"), lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>'),
    (re.compile(r"(?<![\"'>])(https?://[^\s<)]+)"), lambda m: f'<a href="{m.group(1)}">{m.group(1)}</a>'),
]


def inline_md(text):
    out = html.escape(text, quote=False)
    for pattern, repl in INLINE:
        out = pattern.sub(repl, out)
    return out


def md_to_html(body):
    """A small Markdown subset: headings, paragraphs, bullet lists, bold, code, links."""
    lines = body.replace("\r\n", "\n").split("\n")
    blocks, para, items = [], [], []

    def flush():
        nonlocal para, items
        if items:
            blocks.append("<ul>" + "".join(f"<li>{inline_md(i)}</li>" for i in items) + "</ul>")
            items = []
        if para:
            text = " ".join(para).strip()
            m = re.fullmatch(r"\*\*(.+)\*\*", text)
            if m:
                blocks.append(f"<h3>{inline_md(m.group(1))}</h3>")
            else:
                blocks.append(f"<p>{inline_md(text)}</p>")
            para = []

    for line in lines:
        s = line.strip()
        if not s:
            flush()
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            flush()
            blocks.append(f"<h3>{inline_md(m.group(2))}</h3>")
            continue
        m = re.match(r"^[-*]\s+(.*)$", s)
        if m:
            if para:
                flush()
            items.append(m.group(1))
            continue
        if items and line.startswith("  "):
            items[-1] += " " + s
            continue
        if items:
            flush()
        para.append(s)
    flush()
    return "\n".join(blocks)


def date_text(iso):
    d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return f"{d.day} {d.strftime('%B %Y')}"


def render_release(r):
    tag = r["tag_name"]
    version = tag.lstrip("v")
    exe = next((a for a in r.get("assets", []) if a["name"] == "freenapse.exe"), None)
    date = r.get("published_at") or r.get("created_at")
    meta = [f'<h2 id="{html.escape(tag)}">{html.escape(version)}</h2>',
            f'<time datetime="{date[:10]}">{date_text(date)}</time>']
    if exe:
        meta.append(f'<a href="{exe["browser_download_url"]}">freenapse.exe, {exe["size"] / 1048576:.1f}&nbsp;MB</a>')
    meta.append(f'<a href="{r["html_url"]}">Release on GitHub</a>')
    body = md_to_html(r.get("body") or "")
    return (f'<article class="release">\n<div class="release__meta">{"".join(meta)}</div>\n'
            f'<div class="release__body">{body}</div>\n</article>')


def render_feed(releases, now):
    entries = []
    for r in releases:
        date = r.get("published_at") or r.get("created_at")
        entries.append(
            f'<entry><title>freenapse {html.escape(r["tag_name"].lstrip("v"))}</title>'
            f'<link href="{SITE}/changelog/#{html.escape(r["tag_name"])}"/>'
            f'<id>{html.escape(r["html_url"])}</id><updated>{date}</updated>'
            f'<content type="html">{html.escape(md_to_html(r.get("body") or ""))}</content></entry>')
    return ('<?xml version="1.0" encoding="utf-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom">'
            f'<title>freenapse releases</title><link href="{SITE}/changelog/"/>'
            f'<link rel="self" href="{SITE}/feed.xml"/><id>{SITE}/feed.xml</id>'
            f'<updated>{now}</updated><author><name>Matteo Santoro</name></author>'
            + "".join(entries) + "</feed>\n")


def main():
    releases = [r for r in fetch_releases() if not r.get("draft")]
    stable = [r for r in releases if not r.get("prerelease")] or releases
    if not stable:
        sys.exit("no releases to build from")
    latest = stable[0]
    exe = next((a for a in latest.get("assets", []) if a["name"] == "freenapse.exe"), None)
    sha = next((a for a in latest.get("assets", []) if a["name"].endswith(".sha256")), None)
    date = (latest.get("published_at") or latest.get("created_at"))[:10]
    now = datetime.now(timezone.utc)
    css = (SRC / "style.css").read_text(encoding="utf-8")
    values = {
        "css": css,
        "version": latest["tag_name"].lstrip("v"),
        "release_date": date,
        "release_date_text": date_text(date),
        "download_url": exe["browser_download_url"] if exe else FALLBACK_DOWNLOAD,
        "exe_size_mb": f"{exe['size'] / 1048576:.1f}" if exe else "1",
        "exe_size_kb": str(round(exe["size"] / 1024)) if exe else "1024",
        "sha_url": sha["browser_download_url"] if sha else f"https://github.com/{REPO}/releases/latest",
        "build_date": now.strftime("%Y-%m-%d"),
        "build_date_text": date_text(now.strftime("%Y-%m-%d")),
        "releases": "\n".join(render_release(r) for r in releases),
    }

    def fill(text, extra=None, name="template"):
        vals = {**values, **(extra or {})}
        missing = set(re.findall(r"{{(\w+)}}", text)) - vals.keys()
        if missing:
            sys.exit(f"{name}: no value for {', '.join(sorted(missing))}")
        return re.sub(r"{{(\w+)}}", lambda m: vals[m.group(1)], text)

    def src(name):
        return (SRC / name).read_text(encoding="utf-8")

    layout = src("_page.html")

    def page(body, path, title, description, jsonld="", robots="", og_type="website"):
        """Wrap a rendered <main> in the shared chrome of src/_page.html."""
        return fill(layout, {
            "page_body": body, "page_path": path, "page_title": title, "page_description": description,
            "page_jsonld": jsonld, "page_robots": robots, "page_og_type": og_type, "nav_links": nav_links(path),
        }, name=f"_page.html for {path}")

    def write(rel, text):
        out = DIST / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8", newline="\n")

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    index = src("index.html")
    index_faq = faq_jsonld(index)
    if not index_faq:
        sys.exit("index.html: no <dl class=\"qa\"> to build the FAQ structured data from")
    write("index.html", fill(index, {"nav_links": nav_links("/"),
                                     "index_faq": json.dumps(index_faq, indent=4, ensure_ascii=False)}, name="index.html"))
    write("changelog/index.html", page(
        fill(src("changelog.html"), name="changelog.html"), "/changelog/", "freenapse changelog",
        "Every freenapse release and what changed in it, newest first, taken from the GitHub releases of the Razer Viper V3 Pro configurator."))
    write("404.html", page(
        fill(src("404.html"), name="404.html"), "/404.html", "Page not found, freenapse",
        "There is nothing at this address.", robots='<meta name="robots" content="noindex">\n'))
    write("guides/index.html", page(
        fill(src("guides.html"), name="guides.html"), "/guides/", "freenapse guides: the Viper V3 Pro without Synapse",
        "Short guides for the Razer Viper V3 Pro on Windows: set the DPI and polling rate without Synapse, fix settings that do not save, uninstall Synapse, and the alternatives."))
    urls = [(f"{SITE}/", values["build_date"], "weekly", "1.0"),
            (f"{SITE}/guides/", max(g["modified"] for g in GUIDES), "monthly", "0.8"),
            (f"{SITE}/changelog/", date, "weekly", "0.6")]
    for g in GUIDES:
        path = f"/guides/{g['slug']}/"
        body = fill(src(f"guides/{g['slug']}.html"), name=f"guides/{g['slug']}.html")
        write(f"guides/{g['slug']}/index.html", page(
            body, path, f"{g['title']} | freenapse", g["description"], jsonld=guide_jsonld(g, body), og_type="article"))
        urls.append((SITE + path, g["modified"], "monthly", "0.8"))
    write("feed.xml", render_feed(releases, now.strftime("%Y-%m-%dT%H:%M:%SZ")))
    write("sitemap.xml",
          '<?xml version="1.0" encoding="utf-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join(f'<url><loc>{loc}</loc><lastmod>{mod}</lastmod><changefreq>{freq}</changefreq><priority>{pri}</priority></url>\n'
                    for loc, mod, freq, pri in urls)
          + '</urlset>\n')
    for name in ("robots.txt", "CNAME"):
        shutil.copy(SRC / name, DIST / name)
    shutil.copytree(SRC / "assets", DIST / "assets")
    shutil.copy(SRC / "assets" / "favicon.ico", DIST / "favicon.ico")
    (DIST / ".nojekyll").write_text("", encoding="utf-8")
    total = sum(p.stat().st_size for p in DIST.rglob("*") if p.is_file())
    print(f"built dist/: {len(list(DIST.rglob('*')))} entries, {total / 1024:.0f} KB, latest {values['version']}")


if __name__ == "__main__":
    main()
