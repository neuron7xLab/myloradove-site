# Onboarding — five minutes from clone to live preview

You inherited this site. Here is the shortest honest path from a clean
machine to a working local preview.

## 1. Clone

```bash
git clone <repo-url>
cd <repo>/site
```

## 2. Build

```bash
python3 build.py        # needs Python 3.10+, stdlib only
```

That produces `dist/` — the artefact Cloudflare Pages would serve. Open
it directly:

```bash
python3 -m http.server 8787 --directory dist
# http://127.0.0.1:8787/
```

You have a working local preview. Stop here if all you want to do is
read the site.

## 3. Verify

```bash
python3 audit.py        # 58 fail-closed engineering gates
```

This is the safety net every PR must clear. It must print
`58/58 gates PASS · 0 FAIL`.

If it doesn't, do not push.

## 4. Full pipeline (optional, ~10 min the first time)

```bash
npm install
npx playwright install chromium webkit
npm run ci              # build → audit → vnu → playwright → lhci
```

## 5. Edit

99 % of changes are in two files:

- `data/events.toml`   — what the village is doing
- `data/contacts.toml` — who to write to

The rest:

- `data/locale.uk.toml` / `data/locale.en.toml` — copy text
- `index.html`                                  — structure
- `styles.css`                                  — visuals
- `script.js`                                   — interactions

Anything else (`build.py`, `audit.py`, CI workflows, ADRs) is
infrastructure. Read `MAINTENANCE.md` and the relevant ADR before
changing it.

## 6. Ship

Push your branch. Cloudflare Pages builds a preview within a minute
and posts the URL on the PR. CI runs the full pipeline in parallel.
Both must be green before merging. Merge to `main` → production
deploys automatically.

## What to do if something is wrong

| Symptom | First check |
|---|---|
| `audit.py` shows N FAIL | The output names every gate; the gate's name in `audit.py` carries its docstring |
| Playwright fails | Open `playwright-report/index.html` — frame-by-frame trace |
| Lighthouse fails | `.lighthouseci/lhr-*.json` — full report per run |
| Build is non-deterministic (I28 fails) | You introduced a wall-clock dependency. Find it; derive from content lastmod instead |
| Locale parity fails (I29a) | You added a key in one language; add it in the other |

## When to ask a human

- You don't understand why an audit gate exists. Read the ADR. If
  still unclear, ask.
- You think an audit gate is wrong. Open an issue with a concrete
  failure case, not just a complaint.
- The Cloudflare deploy fails. Check the operator runbook in
  `MAINTENANCE.md` first; if still stuck, ping the maintainer.

## Where the documents live

```
MAINTENANCE.md                  operator runbook (deploy / incidents)
docs/CONTRIBUTING.md            who edits what
docs/ONBOARDING.md              this file
docs/RESPONSIVE_AUDIT.md        WSE §22, §26 compliance
docs/ACCESSIBILITY_AUDIT.md     WCAG 2.1 AA + Reflow
docs/PERFORMANCE_AUDIT.md       Core Web Vitals
docs/COMPONENT_CONTRACTS.md     every component → its enforcing test
docs/adr/0001…                  architecture decision records
```
