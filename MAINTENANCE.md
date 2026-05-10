# MAINTENANCE · Милорадове

One-page operator runbook. Read once. Come back before you break something.

---

## 1. Architecture

```
source-of-truth files                 build                dist/
─────────────────────                 ─────                ─────
index.html           ─┐                                    index.html
styles.css           ─┤                                    styles.<sha>.css
script.js            ─┤                                    script.<sha>.js
fonts/               ─┤                                    events.ics
images/              ─┼─▶  build.py  ─▶   deterministic    sitemap.xml, robots.txt
site.config.json     ─┤     (stdlib)      static artefact  _headers, _redirects
data/events.toml     ─┤                                    404.html
data/contacts.toml   ─┘                                    .htaccess
                                                           fonts/, images/
                                                                 │
                                                                 ▼
                                                         Cloudflare Pages
```

No JS framework, no server, no CMS, no Workers, no Functions. If you are
about to add any of those, pause and re-read the reject list in § 10.

---

## 2. Build

```bash
python3 build.py              # production (absolute URLs + fingerprint)
python3 build.py --preview    # local preview (relative URLs, no hash)
python3 audit.py              # 41-gate fail-closed verification
python3 -m http.server 8787 --directory dist    # local smoke server
```

The CI toolchain (Playwright, axe, Lighthouse CI, vnu HTML validator) is
**CI-only**. You can run it locally if you want; you don't need to.

```bash
npm ci && npx playwright install --with-deps chromium
npm test            # Playwright smoke + axe (~30 s)
npm run lhci        # full Lighthouse run (~60 s)
npm run vnu         # HTML validation
```

---

## 3. Deploy (Cloudflare Pages)

### First-time setup

1. Push this repo to GitHub.
2. CF Dashboard → **Pages** → Create project → **Connect to Git**.
3. Build settings:
   - Framework preset: **None**
   - Build command: `python3 build.py`
   - Build output directory: `dist`
   - Environment variable: `PYTHON_VERSION=3.12`
4. Deploy → wait for first green build.
5. **Custom domains** → add `myloradove.com.ua`, confirm DNS in CF, wait
   5-15 min for SSL provisioning.
6. Add `www.myloradove.com.ua` as secondary domain —
   the apex-redirect is already wired in `dist/_redirects`.

### Preview deploys

Every `git push` to a non-`main` branch or a **pull request** produces a
unique preview URL from Cloudflare Pages
(`<branch-hash>.<project>.pages.dev`). Review the preview URL before
merging. Never merge a PR with a red CI badge.

### Promotion

Merge to `main` → CF Pages auto-deploys production.
Rollback: CF Dashboard → Deployments → Promote an earlier build.

---

## 4. Edit workflow for non-technical operators

**99 % of changes happen in two files.**

### Adding an event

Edit `data/events.toml`, copy an existing block, fill in:

```toml
[[event]]
id          = "unique-slug-2026"     # lowercase, hyphens, unique
title       = "Назва події"
date        = "2026-08-24"            # YYYY-MM-DD
time        = "14:00"                 # optional
place       = "Будинок культури"
description = "Один-два речення для сайту."
# Optional:
cta_url     = "https://forms.gle/..."
cta_label   = "Зареєструватися"
```

Commit → push. Preview URL appears within a minute. Merge to `main` → live.

Past events slide into the **«Минулі події»** collapsed archive
automatically (`build.py` compares event date against today).

### Updating a contact email

Edit `data/contacts.toml`. The `handle` field is the local part
(e.g. `rada` becomes `rada@myloradove.com.ua`). Order in the file =
order on the site. Don't put personal addresses here.

### Updating copy text / adding a photo

See `index.html` + `MAINTENANCE.md § 7`.

---

## 5. Email Routing (Cloudflare, 15-min setup, free)

The four role-based addresses (`hello@`, `rada@`, `culture@`, `school@`)
are **not** a mail server. CF Email Routing forwards them to real
mailboxes that the village already uses.

1. CF Dashboard → your zone → **Email** → Email Routing → **Enable**.
2. CF adds MX records and a TXT SPF record automatically — confirm.
3. Under **Routing Rules**, map each public address to its real mailbox:
   ```
   hello@myloradove.com.ua   →  village.manager@gmail.com
   rada@myloradove.com.ua    →  starosta.personal@ukr.net
   culture@myloradove.com.ua →  budynok.kultury@gmail.com
   school@myloradove.com.ua  →  director.school@ukr.net
   ```
4. Add a **catch-all rule** (optional) to capture typos.
5. Validate by sending a test message to each public address.

No code changes. The sender never sees the forwarding target.

---

## 6. Cloudflare Web Analytics (0-JS privacy-respecting analytics)

CF Web Analytics is free, cookieless, adds no third-party script for
domains served from Cloudflare.

1. CF Dashboard → **Analytics & Logs** → **Web Analytics** → Add site.
2. Choose **Automatic setup** and select the CF Pages project.
3. Done. No code edits needed.

Data lives in CF only — no third-party tracker, no PII, no cookies.
If you ever migrate off CF Pages, analytics will stop without breaking
the site.

---

## 7. Adding / updating images

1. Drop the HEIC/JPG source into `../` (sibling of `site/`).
2. Generate 3 variants (640/1280/1920 w) in both AVIF (q=60, or 50 for
   1920) and WebP (q=82, or 75 for 1920 when >1.5 MB):

   ```python
   from PIL import Image, ImageOps
   import pillow_heif, pillow_avif
   pillow_heif.register_heif_opener()
   img = ImageOps.exif_transpose(Image.open("source.HEIC"))
   w, h = img.size
   for width in (640, 1280, 1920):
       r = img.resize((width, int(h * width/w)), Image.LANCZOS)
       r.save(f"site/images/slug-{width}.avif", "AVIF", quality=60, speed=4)
       r.save(f"site/images/slug-{width}.webp", "WEBP", quality=82, method=6)
   ```

3. Add the `<picture>` in `index.html` using the same srcset pattern
   as existing tiles.
4. `python3 build.py && python3 audit.py` — if image budgets fail,
   re-encode at lower quality.

---

## 8. Budgets (enforced by `audit.py`, fail-closed in CI)

| Asset                     | Budget       | Why                               |
|---------------------------|-------------:|-----------------------------------|
| `index.html`              |      40 KB   | compact document                  |
| `styles.<sha>.css`        |      65 KB   | single-file stylesheet            |
| `script.<sha>.js`         |      20 KB   | zero framework                    |
| `*-640.{avif,webp}`       |     300 KB   | gallery / mobile LCP              |
| `*-1280.{avif,webp}`      |     800 KB   | article plate default             |
| `*-1920.{avif,webp}`      |   1 500 KB   | lightbox / high-DPR only          |
| Font preloads in `<head>` |       2      | only LCP-critical subsets         |
| Lighthouse performance    |      ≥ 0.95  | realistic for static HTML+CSS     |
| Lighthouse accessibility  |      ≥ 0.95  | WCAG 2.1 AA target                |
| CLS                       |      ≤ 0.05  | explicit w/h on every image       |
| LCP                       |    ≤ 2500 ms | static + preloaded critical font  |

Exceeding any budget is a **CI failure**, not a warning.

---

## 9. What NOT to touch casually

- `@property` declarations in `styles.css` — used by animations.
- Any `@supports` block — they're invariant guards.
- The `sha256-…` hash in `_headers` / `.htaccess` (regenerated by
  `build.py` from the live JSON-LD; don't hand-edit).
- `.flag__strip` timings and amplitudes — six strips × phase × amp
  are the Eulerian wave. Change one value and the flag goes from
  fabric to jelly.
- Preloads in `<head>` — currently 2 fonts + 1 LCP image. Adding more
  is almost always wrong; measure first.
- `build.py` core invariants: deterministic output, no timestamp noise,
  CSP hash recomputation.

---

## 10. Reject list (documented refusals)

These were considered and **not** added. Re-opening requires a written
reason and measurement.

| Idea                         | Why rejected                                       |
|------------------------------|----------------------------------------------------|
| React / Next / Astro migration | Zero-JS-framework by design. 100+ KB for nothing. |
| Service worker / offline    | Content volume is one page. No offline use case.    |
| Cloudflare Workers / Pages Functions | No dynamic behaviour needed.               |
| Headless CMS                | Content fits in two TOML files.                    |
| Image CDN (Cloudflare Images)| Already AVIF + WebP × 3 sizes pre-encoded.        |
| Third-party analytics       | CF Web Analytics covers it; no trackers.           |
| Chatbot / AI widget         | Not civic. Privacy risk. Reject.                   |
| Weather widget              | Third-party JS for no civic gain. Reject.          |
| Social-feed embed           | Third-party JS, privacy leak, visual noise.        |
| Newsletter signup           | Requires backend. Mailto works fine.               |
| Contact form                | Same. Use emails from `contacts.toml`.             |
| A/B testing                 | No optimisation hypothesis.                        |
| Animation library (GSAP, Lottie) | Current effects are 40 lines of native CSS/SVG. |
| PWA manifest / install      | Marginal value for one-page info site.             |
| Full embedded map           | Heavy, third-party JS. Current mapto-link is enough.|
| Multiple language versions  | Scope creep; consider only if community asks.      |

---

## 11. Incident response

- **Site down?** Check CF Pages status page + last deployment log.
- **Bad deploy?** CF Dashboard → Deployments → Promote previous build.
- **Content mistake?** Edit `events.toml` / `contacts.toml` → push.
- **CSP blocks something?** `build.py` regenerates the hash on every
  build. If you edited JSON-LD manually *and* didn't rebuild, the hash
  in `_headers` is stale. Fix: run `python3 build.py` and commit.
- **CI red?** Read the failing step; `audit.py` prints a full
  `[PASS]/[FAIL]` table. Never merge with red CI.
