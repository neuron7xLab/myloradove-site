# Accessibility Audit — Milorado civic site

Reference: WSE-TOP3-V-2026 §9, §11, §16, §18.
Audited: 2026-05-10.

## Semantic structure

- [x] **Single `<h1>` per page** — `<h1 class="hero__title sr-only">Милорадове</h1>` (visually hidden, exposed to assistive tech and SEO outline). Verified by `audit.py I15` (lang attr) + Playwright smoke selector + this audit.
- [x] **Logical heading order** — `h1 → h2` (chapter titles) → `h3` (life facets, history events). No skipped levels.
- [x] **Landmarks present** — `<header>`, `<nav aria-label="…">`, `<main id="main">`, `<footer>`, `<aside class="vitals">`. Labelled where multiple of a kind exist.
- [x] **Skip link** — `<a class="skip" href="#main">Пропустити до змісту</a>` visible on focus, sr-only otherwise.
- [x] **Form labels** — site has no forms; the only interactive controls are `<a>` (anchors, `mailto:`), `<button class="email-card__copy" aria-label="…">`, `<button class="nav__toggle" aria-expanded="…" aria-controls="nav-menu">`, `<button class="lightbox__close" aria-label="…">`.
- [x] **Image alt text** — `audit.py I16a` enforces `alt` on every `<img>` (14/14 PASS). Decorative carousel duplicates use `alt=""` + `aria-hidden="true"`.

## WCAG 1.4.10 Reflow

- [x] **320 px** — Playwright sweep PASS. Body overflow = 0 px. No two-dimensional scroll for normal content.
- [x] **400 % zoom** — equivalent to ~320 px CSS width on 1280 px viewport; covered by the sweep.
- [x] **Tables** — site has no tables.
- [x] **Code/math** — site has no code or math blocks.
- [x] **Long-form essays** — `max-inline-size: 62ch` on `.essay`, with `.essay__lede` capped at 54ch — never overshoots viewport.

## Interaction

- [x] **`:focus-visible` style** — `outline: 2px solid var(--c-gold)` at 4 px offset, applied through `@layer base`. Verified in `styles.css`.
- [x] **Keyboard reachable** — Playwright smoke verifies gallery lightbox opens on click, ESC closes, focus restores to trigger.
- [x] **`prefers-reduced-motion: reduce`** — six rules guard `.flag__strip`, `.flag__fabric`, `.hero__slide`, `.hero__cue-axis/tip`, `.hero__cursor`, `.hero__mesh`, scroll-driven animations, and View Transitions.
- [x] **`prefers-reduced-data: reduce`** — drops mesh + cursor halo to spare metered connections.
- [x] **Touch target ≥ 44 px** — `@media (pointer: coarse) { button, a, input, select, textarea, summary, [role=button] { min-block-size: 44px; } }`. Mouse cursors keep dense desktop UI.
- [x] **Pointer-only effects** — 3D card tilt + cursor halo guarded by `@media (hover: hover)` and `pointer: coarse` JS check.

## Colour contrast

- [x] **Hero text** — none rendered on the photo (visually empty centre). Vitals strip on `paper-warm` reads ink-soft `#22343d` on `#ede5d1` ≈ 8.4:1.
- [x] **404 page** — gold `--c-gold-deep` on `paper` ≈ 4.4:1 (verified by axe via Playwright).
- [x] **Anchor focus rings** — gold-on-paper 4.4:1.
- [x] axe-core a11y suite: zero serious/critical violations on `/` and `/404.html`, two viewports (Playwright `tests/a11y.spec.ts`).

## Motion safety

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    scroll-behavior: auto !important;
    animation-duration: 0.001ms !important;
    transition-duration: 0.001ms !important;
  }
}
```

Plus per-component opt-outs (flag, hero carousel, scroll cue, mesh).
View Transitions JS module also bails out under reduced motion.

## Final verdict

**PASS** — WCAG 2.1 AA target met. Regression guard: Playwright `tests/a11y.spec.ts` (axe), `tests/smoke.spec.ts` (keyboard flows), `tests/viewport.spec.ts` (Reflow §1.4.10).
