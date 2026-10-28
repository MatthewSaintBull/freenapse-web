"""Build freenapse.app into dist/.

Reads the templates in src/, inlines the stylesheet, fetches the releases of
MatthewSaintBull/freenapse from the GitHub API (falling back to the snapshot in
data/releases.json when the API is unreachable) and writes index.html,
changelog/index.html, 404.html, feed.xml, sitemap.xml and the static files.
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

    def render(name):
        text = (SRC / name).read_text(encoding="utf-8")
        missing = set(re.findall(r"{{(\w+)}}", text)) - values.keys()
        if missing:
            sys.exit(f"{name}: no value for {', '.join(sorted(missing))}")
        return re.sub(r"{{(\w+)}}", lambda m: values[m.group(1)], text)

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    (DIST / "index.html").write_text(render("index.html"), encoding="utf-8", newline="\n")
    (DIST / "changelog").mkdir()
    (DIST / "changelog" / "index.html").write_text(render("changelog.html"), encoding="utf-8", newline="\n")
    (DIST / "404.html").write_text(render("404.html"), encoding="utf-8", newline="\n")
    (DIST / "feed.xml").write_text(render_feed(releases, now.strftime("%Y-%m-%dT%H:%M:%SZ")), encoding="utf-8", newline="\n")
    (DIST / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'<url><loc>{SITE}/</loc><lastmod>{values["build_date"]}</lastmod><changefreq>weekly</changefreq><priority>1.0</priority></url>\n'
        f'<url><loc>{SITE}/changelog/</loc><lastmod>{date}</lastmod><changefreq>weekly</changefreq><priority>0.6</priority></url>\n'
        '</urlset>\n', encoding="utf-8", newline="\n")
    for name in ("robots.txt", "CNAME"):
        shutil.copy(SRC / name, DIST / name)
    shutil.copytree(SRC / "assets", DIST / "assets")
    shutil.copy(SRC / "assets" / "favicon.ico", DIST / "favicon.ico")
    (DIST / ".nojekyll").write_text("", encoding="utf-8")
    total = sum(p.stat().st_size for p in DIST.rglob("*") if p.is_file())
    print(f"built dist/: {len(list(DIST.rglob('*')))} entries, {total / 1024:.0f} KB, latest {values['version']}")


if __name__ == "__main__":
    main()
