# Contributing to the Milorado site

This is a civic project for the village of Milorado in Poltava district.
The bar for changes is: it must help the people of the village or the
people who visit the site, and it must not regress any of the 58 audit
gates.

## Three editor profiles

### A. Content editor (non-technical)

You add an event, fix a typo, change an email address.

1. Open the GitHub web UI.
2. Navigate to one of:
   - `site/data/events.toml`     — adding / updating events
   - `site/data/contacts.toml`   — changing the four role-based emails
   - `site/data/locale.uk.toml`  — updating Ukrainian text
   - `site/data/locale.en.toml`  — updating English text
3. Edit. Commit through the GitHub web UI ("Edit this file" → save).
4. Cloudflare Pages builds a preview within a minute. The preview URL
   is posted on the PR. Open it. If it looks right, merge.

**Important:** Every key you change in `locale.uk.toml` must also be
changed in `locale.en.toml` (the same key, translated). Audit gate
I29a blocks the merge otherwise.

### B. Designer / structural editor

You move a block, add a section, change typography.

1. Clone locally.
2. `cd site && python3 build.py && python3 audit.py`. Must be 58/58 PASS.
3. Edit HTML / CSS / locale TOML. Each section's geometry contract is
   documented in `docs/COMPONENT_CONTRACTS.md`.
4. Re-run `python3 audit.py`. Must stay 58/58 PASS.
5. Open a PR. CI will run the full pipeline (audit + html-validation +
   playwright + lighthouse).

### C. Engineer

You change the build, add a gate, change CI.

1. Read `MAINTENANCE.md` end-to-end before touching anything.
2. Read the relevant ADR in `docs/adr/` before reversing an
   architectural decision. If an ADR is wrong, write a new ADR that
   supersedes it. Don't quietly undo it.
3. Tests: any new behaviour gets a Playwright spec; any new invariant
   gets an audit gate.
4. Determinism is load-bearing. If you add a wall-clock dependency,
   I28 will fail.

## What is not negotiable

- The site stays static and JS-light. No frameworks. No CMS. No
  Workers. No analytics SDK. See ADR 0001 and `MAINTENANCE.md §10`.
- Every locale key must exist in both languages.
- Every absolute URL must use the canonical host.
- Every build must be byte-identical to the previous build given the
  same source.
- No PII or personal addresses in `contacts.toml`. Role-based handles
  only. Audit I23 enforces this.

## How to test locally without a heavy toolchain

```bash
cd site
python3 build.py
python3 audit.py            # 58 fail-closed gates
python3 -m http.server 8787 --directory dist
# open http://127.0.0.1:8787/
```

That's enough to ship most content changes safely. The heavier suite
(`npm test`, `npm run lhci`, `npm run vnu`) runs in CI on every PR.

## When stuck

- `MAINTENANCE.md`        — operator runbook, deploy, incident steps
- `docs/RESPONSIVE_AUDIT.md`
- `docs/ACCESSIBILITY_AUDIT.md`
- `docs/PERFORMANCE_AUDIT.md`
- `docs/COMPONENT_CONTRACTS.md`
- `docs/adr/`             — architecture decision records
