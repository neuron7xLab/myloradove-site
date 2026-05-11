# Milorado — civic site

[![CI](https://github.com/neuron7xLab/myloradove-site/actions/workflows/ci.yml/badge.svg)](https://github.com/neuron7xLab/myloradove-site/actions/workflows/ci.yml)

The public web presence of Milorado village (Poltava district, Poltava
oblast, Ukraine). Static, deterministic, zero JS framework, 58
fail-closed engineering invariants, Cloudflare Pages deploy target.

> Production URL (when live): https://myloradove.com.ua

## What this is

- **One semantic HTML page** in two locales (`uk` at `/`, `en` at `/en/`).
- **One CSS sheet**, 7-layer `@layer` cascade, ~76 KB.
- **One JS module**, ~19 KB, no library dependency.
- **One Python `build.py`**, standard-library only, deterministic.
- **One audit script** (`audit.py`), 58 fail-closed gates.
- **Tests**: Playwright (desktop + mobile webkit + viewport sweep) + axe + Lighthouse CI + Nu HTML Checker.

## Five minutes from clone to preview

```bash
git clone https://github.com/neuron7xLab/myloradove-site.git
cd myloradove-site
python3 build.py                                       # produces dist/
python3 audit.py                                       # 58/58 PASS
python3 -m http.server 8787 --directory dist           # http://127.0.0.1:8787/
```

Heavier toolchain (Playwright + Lighthouse) optional and CI-only.

## The 58 invariants

`audit.py` enforces, in seven families:

1. Artefact integrity (I01–I05): files exist, refs resolve.
2. Metadata canonicity (I06, I09, I10, I27): absolute URLs, single host.
3. CSP hash sync (I08) between `_headers` and `.htaccess`.
4. Asset budgets (I11–I13, I31, I32) — including a 600 KB LCP cap.
5. Accessibility basics (I15, I16, I23).
6. Locale parity (I29a — UK and EN keys byte-identical; I29b — no orphan keys).
7. Build invariants (I28 determinism; I30 srcset-width-vs-file truthfulness).

Each gate is fail-closed: exit code = number of failures. CI blocks the merge.

## Documents

- [`MAINTENANCE.md`](MAINTENANCE.md) — operator runbook (deploy, incidents, reject list)
- [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md) — three editor profiles
- [`docs/ONBOARDING.md`](docs/ONBOARDING.md) — 5-minute path
- [`docs/RESPONSIVE_AUDIT.md`](docs/RESPONSIVE_AUDIT.md) — WSE §22 viewport sweep
- [`docs/ACCESSIBILITY_AUDIT.md`](docs/ACCESSIBILITY_AUDIT.md) — WCAG 2.1 AA + axe
- [`docs/PERFORMANCE_AUDIT.md`](docs/PERFORMANCE_AUDIT.md) — Core Web Vitals + budgets
- [`docs/COMPONENT_CONTRACTS.md`](docs/COMPONENT_CONTRACTS.md) — every component → its enforcing test
- [`docs/adr/`](docs/adr/) — architecture decision records

## Editing content

99 % of edits land in two files:

- [`data/events.toml`](data/events.toml) — what the village is doing
- [`data/contacts.toml`](data/contacts.toml) — four role-based emails

UK/EN copy in [`data/locale.uk.toml`](data/locale.uk.toml) /
[`data/locale.en.toml`](data/locale.en.toml). Audit gate **I29a**
blocks the merge if either is missing a key the other has.

## Deployment

See [`MAINTENANCE.md` §3](MAINTENANCE.md) for the full Cloudflare Pages
walkthrough. Summary: connect this repo to CF Pages with
`python3 build.py` as the build command and `dist` as the output dir.

## License

[MIT](LICENSE). Photographs are © original photographers, used under
a village-content release.

## Sources for the history page

The "From khutir to hromada" timeline is grounded in primary sources
(Ukrainian Wikipedia, KATOTTH register, Cabinet of Ministers
resolution № 721-р of 12 June 2020, Schubert military-topographic
maps 1826—1840). Full source list rendered on the page itself.
