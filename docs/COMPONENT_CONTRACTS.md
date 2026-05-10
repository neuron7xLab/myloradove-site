# Component Contracts — Milorado civic site

Reference: WSE-TOP3-V-2026 §15, §22, §23.
Audited: 2026-05-10.

## Component: `.hero` (full-bleed photo carousel)

Required:
- Renders a single visible slide at any moment. CSS-only crossfade, 18 s loop.
- LCP slide opaque from frame zero, `fetchpriority="high"`, `<link rel="preload">`.
- Decorative slides `aria-hidden="true"`, `alt=""`, `loading="lazy"`.
- `prefers-reduced-motion: reduce` → static LCP slide, no rotation.
- Scroll-driven parallax via `animation-timeline: scroll(root block)`; falls back to a slow ambient drift when unsupported.
- Hero centre is visually empty by design; `<h1>` lives in `.sr-only` for SEO/a11y outline.

Forbidden:
- Per-slide layout (only opacity changes; transform on parent only).
- JS-controlled rotation (would need re-implementation under reduced motion).

## Component: `.email-card` (contact email tile, container-aware)

Required:
- `container-type: inline-size; container-name: email-card;`
- Adapts via `@container email-card (min-inline-size: 28rem)` → wider card slot expands address row + lifts copy-button typography.
- Email address rendered as `mailto:` anchor + copy-to-clipboard button with `aria-label` and announcement region.
- Visible focus ring on all interactive children.
- 3D hover tilt scoped to `@media (hover: hover) and (prefers-reduced-motion: no-preference)`; touch devices get a static card.

Forbidden:
- Form intermediaries, third-party widgets, tracker scripts.
- `placeholder` substituting `aria-label` (no inputs anyway).

## Component: `.tile` (gallery thumb)

Required:
- Single 640w AVIF + WebP responsive `<picture>`; full-resolution lightbox open via dialog.
- Keyboard activation: `<a>`, opens `<dialog class="lightbox">` programmatically.
- ESC closes; close button restores focus to the originating tile (Playwright-verified).
- Hover tilt scoped to pointer hover.

Forbidden:
- Layout-shifting hover effect (only `transform` + `box-shadow`).

## Component: `.vitals` (fine-print ribbon)

Required:
- One semantic `<aside>` block above footer.
- `<dl>`/`<dt>`/`<dd>` semantics — assistive tech pairs label and value.
- Single line on desktop, wraps on phones (`flex-wrap: wrap`).
- Coordinates render last; share the same typographic scale as the rest.
- Border-top hairline tint reads as structure, not decoration.

## Component: `.chapter-indicator` (sticky chapter pill)

Required:
- `position: fixed`, `backdrop-filter: blur(12px) saturate(140%)`.
- Updated by IntersectionObserver — appears only after the hero leaves the viewport, hides again on scroll-back.
- Hidden under 720 px viewport (purely informational, redundant with chapter heads).
- `pointer-events: none` so it never blocks clicks.

Forbidden:
- Hard scroll listeners.
- Modifying URL fragment as side effect.

## Component: `.scroll-progress` (top progress bar)

Required:
- 2 px gradient hairline at top of viewport, fixed.
- `animation-timeline: scroll(root)` — `transform: scaleX(0)` → `scaleX(1)`.
- Pure compositor; no layout, no paint per scroll tick.

Forbidden:
- JS-driven scroll math (would defeat the cost model).

## Component: `.flag` (Ukrainian flag mark, 32×22 px)

Required:
- 6 strips in a clipped fabric group.
- Per-strip phase-shifted wave (lagrangian clamp at the pole), peak skew ≤ 0.6° at the trailing edge.
- Whole-fabric ride (rotate ±0.5° around the pole) layered above the strip wave for cloth-weight feel.
- `prefers-reduced-motion` halts both layers; static flag still readable.

Forbidden:
- Skew > 1.8° (cardboard fold).
- Strips escaping their column (Δy > 1 px).

## Component: `.lightbox` (image modal)

Required:
- `<dialog class="lightbox">` with native `showModal()` semantics.
- ESC closes; close button restores focus to trigger element.
- `<img alt="" src="data:image/gif…">` placeholder for valid HTML5; populated on open.
- ScrollLock acquires/releases via `safely('lightbox')` module — no body-class race.

## Verification

| Component       | Test                          |
| --------------- | ----------------------------- |
| hero parallax   | tests/visual.spec.ts (hero fold snapshot) |
| hero a11y       | tests/a11y.spec.ts (axe)      |
| nav menu        | tests/smoke.spec.ts (mobile drawer) |
| gallery lightbox| tests/smoke.spec.ts (open/close/focus) |
| email cards     | tests/smoke.spec.ts (copy button rendered) |
| viewport sweep  | tests/viewport.spec.ts (320 → 1920 px) |
| 404 page        | tests/smoke.spec.ts + tests/a11y.spec.ts |

Every component contract is enforced by either a Playwright assertion or an `audit.py` invariant. None are aspirational.
