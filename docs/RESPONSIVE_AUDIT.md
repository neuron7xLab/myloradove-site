# Responsive Audit — Milorado civic site

Reference: WSE-TOP3-V-2026 §22, §26.
Audited: 2026-05-10.

## Viewport contract

- [x] `<meta name="viewport" content="width=device-width, initial-scale=1.0">` present on all three rendered shells (`/`, `/en/`, `/404.html`)
- [x] No forced desktop viewport
- [x] Playwright `tests/viewport.spec.ts` runs the WSE §22.1 sweep at 320 / 360 / 390 / 430 / 768 / 1024 / 1280 / 1440 / 1920 px and asserts `document.documentElement.scrollWidth ≤ clientWidth + 1`. Hero section additionally asserted on 320×568.

**Verdict: PASS.**

## Layout strategy

- [x] Mobile-first cascade: base styles target the smallest viewport; `@media (min-width: …)` enhances upward. No `max-width: …` patches as architecture.
- [x] Cascade layers: `@layer reset, tokens, base, layout, components, atmospherics, utilities;` — deterministic specificity.
- [x] Grid where 2-D (chapter shells, gallery, vitals ribbon, contacts grid).
- [x] Flexbox where 1-D (nav menu, brand cluster, scroll-cue glyph, copy-row).
- [x] Container queries: `.email-card { container-type: inline-size; container-name: email-card; }` with `@container email-card (min-inline-size: 28rem)` → component adapts to its slot, not the viewport.
- [x] Device-named breakpoints absent (`iPhone breakpoint` etc.). All breakpoints content-derived (`(min-width: 64rem)` for sidebar, `(width <= 640px)` for narrower phones, `(width <= 720px)` for sticky chapter pill).

**Verdict: PASS.**

## Content integrity

- [x] No content hidden by viewport. Hero photo carousel rotates the same three slides on phone and desktop; only chapter-pill indicator hides under 720 px (decorative, not informational).
- [x] Navigation preserved — `.nav__menu` links collapse into a drawer ≤640 px; all anchors remain reachable via keyboard.
- [x] Forms — site has no forms (civic email-only contract); contact emails render as plain `mailto` cards with copy-to-clipboard fallback.
- [x] Pricing, claims, evidence, legal, privacy paths preserved (none drop on small viewports).
- [x] Vitals ribbon (founded · residents · elevation · hromada · coords) — single-line desktop, wraps on narrow; never hidden.

**Verdict: PASS.**

## Sweep summary

| Width | Body overflow | Hero overflow | Result |
| -----:| -------------:| -------------:| ------ |
| 320   | 0 px          | 0 px          | PASS   |
| 360   | 0             | 0             | PASS   |
| 390   | 0             | 0             | PASS   |
| 430   | 0             | 0             | PASS   |
| 768   | 0             | 0             | PASS   |
| 1024  | 0             | 0             | PASS   |
| 1280  | 0             | 0             | PASS   |
| 1440  | 0             | 0             | PASS   |
| 1920  | 0             | 0             | PASS   |

(`+1 px` tolerance for sub-pixel rounding accepted by the assertion.)

## Final verdict

**PASS** — full WSE §22 / §26 compliance, regression-guarded by Playwright viewport sweep.
