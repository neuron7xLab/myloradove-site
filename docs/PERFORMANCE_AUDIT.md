# Performance Audit — Milorado civic site

Reference: WSE-TOP3-V-2026 §12, §13, §22, §26.
Audited: 2026-05-10.

## Core Web Vitals targets

Lighthouse CI assertions (`lighthouserc.json` desktop, `lighthouserc.mobile.json` mobile):

| Metric | Target          | Status |
| ------ | ---------------:| ------ |
| LCP    | ≤ 2 500 ms      | PASS   |
| FCP    | ≤ 1 500 ms      | PASS   |
| CLS    | ≤ 0.05          | PASS   |
| TBT    | ≤ 200 ms        | PASS   |
| Performance score    | ≥ 0.95 desktop / ≥ 0.90 mobile | PASS |
| Accessibility score  | ≥ 0.95 both                    | PASS |
| Best-practices score | ≥ 0.95 both                    | PASS |
| SEO score (canonical pages) | ≥ 0.95                  | PASS |

(404 page is `noindex`, so SEO category excluded by `assertMatrix`.)

## LCP protocol

- [x] LCP element identified: `.hero__slide--lcp <img>` (img_4886-1920.webp, 1920 × 2560).
- [x] Format: AVIF + WebP via `<source>` chain.
- [x] Dimensions explicit: `width="1920" height="2560"` → CLS ≤ 0.05.
- [x] `fetchpriority="high"` on the LCP `<img>`.
- [x] Preload header: `<link rel="preload" as="image" type="image/avif" href="…img_4886-1920.avif" imagesrcset="…" imagesizes="100vw" fetchpriority="high">`.
- [x] Not lazy-loaded.
- [x] Not injected via JS.

## CLS protocol

- [x] Every `<img>` has `width` + `height` attributes (`audit.py I16b` enforces 14/14).
- [x] No ad slots, no late-injected banners, no third-party iframes.
- [x] Two font preloads only (`audit.py I11` budget 2/2): `inter-cyrillic.woff2`, `playfair-italic-cyr.woff2`. `font-display: swap` allows fallback paint without layout jump.
- [x] No layout-shifting animations: hero carousel uses opacity-only crossfade, parallax uses transform-only via `translateZ(0)`.

## TBT / INP protocol

- [x] JS budget 22 KB; current 19.1 KB. Single bundle, no eval, no third-party scripts.
- [x] All event handlers `passive: true` where they touch scroll axis (`pointermove` on hero cursor halo).
- [x] `requestAnimationFrame` throttle on cursor-light handler — at most one update per frame.
- [x] IntersectionObserver for chapter-indicator and scroll reveals; no per-scroll JS.

## Asset budgets (audit.py I12, I13)

| Asset     | Limit     | Current   |
| --------- | ---------:| ---------:|
| HTML      | 42 KB     | 38.5 KB   |
| CSS       | 80 KB     | 72.0 KB   |
| JS        | 22 KB     | 19.1 KB   |
| 640 w img | 300 KB    | max 19 KB |
| 1184/1280 w img | 800 KB | max 130 KB |
| 1920 w img | 1500 KB  | max 1304 KB |
| Font woff2 (each) | 60 KB | max ~54 KB |

## Caching contract

| Path                     | Cache-Control                         |
| ------------------------ | ------------------------------------- |
| `/`, `/index.html`, `/en/` | `public, max-age=0, must-revalidate` |
| `/styles.<sha>.css`      | `public, max-age=31536000, immutable` |
| `/script.<sha>.js`       | `public, max-age=31536000, immutable` |
| `/fonts/*.woff2`         | `public, max-age=31536000, immutable` |
| `/images/*`              | `public, max-age=31536000, immutable` |
| `/events.ics`            | `public, max-age=3600`                |

CSP `script-src` SHA-256 hash recomputed per build and synced to both `_headers` and `.htaccess` (`audit.py I08`).

## Determinism (I28)

Build is byte-deterministic — `audit.py` snapshots dist/, runs `build.py` again, diffs SHA-256 hashes. Zero drift across 84 files. This pins:
- `Cache-Control: immutable` semantically — same content always hashes to the same name.
- CSP hash stays stable until JSON-LD content actually changes.
- ICS DTSTAMP derived from content `lastmod`, never wall-clock now().

## Final verdict

**PASS** — all WSE §12 gates met, all custom budgets honoured, Lighthouse CI gates green on desktop + mobile.
