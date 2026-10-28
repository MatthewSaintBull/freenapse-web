# Design: freenapse.app

The locked system. Every Hallmark run reads this first and pages share it. It is the desktop app's design system (`DESIGN.md` v1.1 in the freenapse repository) carried to the web: the site must look like a page of the settings window, not like a product site that happens to be green. Change it on purpose; the file is the rule.

## System
- Genre: modern-minimal
- Shape of the first page: Workbench (the app's own captures with factual captions; job: try, the download under the head)
- Theme: custom, derived from the app (vibe: "calm, dark, flat, Windows 11 settings")
- Axes: dark 7/grotesk-sans Segoe UI Variable/chromatic-green 145 · posture: restrained (the accent is a signal: one filled button, the wordmark, on-states)

## Tokens
`src/style.css` is the source of truth; the values are the app's, in hex because the app is in hex. The roles:
```css
:root {
  --color-paper: #111112;    --color-paper-2: #1c1c1e;   --color-paper-3: #262628;
  --color-ink: #f3f3f3;      --color-ink-2: #a9aaad;     --color-muted: #7c7d81;
  --color-rule: #2a2a2c;     --color-rule-strong: #3c3c3f;
  --color-accent: #1db954;   --color-accent-hover: #25cf61;  --color-accent-pressed: #189b47;
  --color-accent-ink: #06200f;  --color-focus: #f3f3f3;
  --font-display: "Segoe UI Variable Display", "Segoe UI", system-ui, sans-serif;
  --font-body: "Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif;
  --font-outlier: "Cascadia Mono", Consolas, ui-monospace, monospace;   /* code and the probe output only */
  --radius-card: 4px;  --radius-window: 8px;  --rule-hair: 1px;  --shadow-card: none;
}
```
Dark only: the app has no light theme, so the site has none. No web font is downloaded; Segoe UI Variable is the app's face and `system-ui` stands in elsewhere.

## Rules carried from the app
- Sentence case everywhere, including every heading. Semibold (600) is the strongest weight; no bold, no italics, no tracked capitals.
- Text on the accent is always `--color-accent-ink`. Never white on green.
- Surfaces are flat: a 1 px `--color-rule` outline, a 1 px highlight inside the top edge at white 4 %, no shadows at rest. Lighter surface means more elevated.
- Radius 4 px on cards, buttons, chips and code blocks; 8 px on the app captures, which are windows.
- Spacing on the 4 px scale; the settings row (title left, description right, hairline between rows) is the site's building block for lists of facts.
- Captures are shown as they are, in a figure, never inside a drawn window or device.

## Controls
- Primary: `--color-accent` fill, `--color-accent-ink` text · 4 px · 48 px (44 px on the changelog page's links)
- Secondary: `--color-paper-3` fill with a 1 px `--color-rule-strong` outline, `--color-ink` text · same radius and height
- Focus: a 2 px `--color-focus` outline, 2 px off the control, instant

## Motion
- Character: still, like the app (GDI, no compositor animations). Colour changes on hover and press only; no reveals; under reduced motion nothing is left to switch off.

## Exports
`src/style.css` in this project. Tailwind, DTCG or shadcn blocks are added here on request.
