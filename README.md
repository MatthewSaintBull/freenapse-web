# freenapse.app

The website of [freenapse](https://github.com/MatthewSaintBull/freenapse), the
Razer Viper V3 Pro configurator for Windows that replaces Razer Synapse. Two
static pages, hosted on GitHub Pages at https://freenapse.app.

* `src/index.html`: the home page, a full template. `{{version}}`,
  `{{download_url}}` and the other fields are filled at build time from the
  GitHub releases of the app, so the download button always points at the
  latest release. Its FAQ structured data is generated from the page's own
  questions.
* `src/_page.html`: the shared chrome (head, nav, footer) of every other page.
  `src/changelog.html`, `src/guides.html`, `src/404.html` and
  `src/guides/<slug>.html` are the `<main>` of each; the guides' titles,
  descriptions and dates live in the `GUIDES` list of `build.py`, which also
  emits their TechArticle, BreadcrumbList and FAQPage structured data.
* `src/style.css`: one stylesheet, inlined into each page. Its tokens are the
  desktop app's design system (`design.md` here, `DESIGN.md` in the app).
* `src/assets/`: the app's own captures in AVIF, WebP and PNG, the logo, the
  icons and the Open Graph image.
* `build.py`: standard-library Python. Fetches the releases (or uses the
  snapshot in `data/releases.json`), renders the pages, writes `feed.xml`,
  `sitemap.xml`, `robots.txt` and `CNAME` into `dist/`.
* `.github/workflows/deploy.yml`: builds and deploys to Pages on every push to
  `main`, once a day, by hand, and when the app's release workflow sends a
  `repository_dispatch` event of type `release`.

## Build locally

```
python build.py
python -m http.server --directory dist 8000
```

## Design

`design.md` is the locked system: the pages reuse the app's colours, type
ramp, spacing, flat surfaces and settings rows, so the site looks like a page
of the settings window. It was built with the
[Hallmark](https://www.usehallmark.com) design skill; the stamp at the top of
`src/style.css` records the decisions.

## License

MIT, the same as the app. The screenshots show freenapse itself. Razer, Razer
Synapse, Viper, HyperSpeed and HyperPolling are trademarks of Razer Inc.;
freenapse is not affiliated with, endorsed by or supported by Razer Inc.
