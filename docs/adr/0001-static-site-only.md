# ADR 0001 — Static site only

Status: ACCEPTED
Date  : 2026-04-22

## Context

The village needs a public web presence. Options considered:
- Static-site generator (Hugo, Eleventy, Astro)
- Custom static build (Python stdlib)
- Headless CMS + Vercel/Next
- WordPress on shared hosting

## Decision

Custom Python-stdlib static build, deployed as immutable files to
Cloudflare Pages. No runtime backend. No JS framework. Content lives
in TOML files that non-technical operators can edit in any text
editor (or GitHub web UI).

## Consequences

+ Zero runtime dependencies; cannot break from a package upgrade.
+ Determinism is enforceable (audit gate I28 verifies it).
+ Operating cost is zero (CF Pages free tier).
+ Page weight is tiny (~16 KB above the fold).
+ No CVE surface beyond the browser itself.
- Dynamic features (forms, comments, search) are not available.
- Adding a new section requires editing HTML + locales.
- Operators must commit through git or the GitHub web UI; no CMS UI.

## Status

Accepted and load-bearing. Reversing this decision would require
re-evaluating the deployment target, CSP policy, cache contract, and
the entire audit-gate set built around deterministic dist/ output.
