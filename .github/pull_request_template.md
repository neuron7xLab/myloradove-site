## Summary

One-paragraph "what + why". Link the issue if one exists.

## Touched areas

- [ ] Content (`data/*.toml`)
- [ ] Structure (`index.html` / chapter geometry)
- [ ] Styles (`styles.css`)
- [ ] Build / audit (`build.py` / `audit.py`)
- [ ] Tests (`tests/*.spec.ts`)
- [ ] CI (`.github/workflows/`)
- [ ] Docs (`docs/`, `MAINTENANCE.md`, ADR)

## Locale parity

If any locale string was touched:

- [ ] Updated in `data/locale.uk.toml`
- [ ] Updated in `data/locale.en.toml`
- [ ] `python3 audit.py` shows I29a + I29b green

## Verification done locally

- [ ] `python3 build.py` — clean
- [ ] `python3 audit.py` — N/N PASS (paste line)
- [ ] `npx playwright test --project=desktop` — passes
- [ ] If visual: screenshot snapshots updated and reviewed
- [ ] If LCP / hero image touched: I32 still PASS (cap 600 KB)

## Preview

Cloudflare Pages will post a preview URL on this PR. Confirm by opening
it on mobile + desktop before merging.
