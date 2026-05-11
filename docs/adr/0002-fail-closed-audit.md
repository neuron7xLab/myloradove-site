# ADR 0002 — Fail-closed audit before every merge

Status: ACCEPTED
Date  : 2026-04-22

## Context

Static sites tend to rot silently. A broken anchor, a stale CSP hash, a
mismatched locale key, a wall-clock-noise breaking determinism — none of
these throw errors. They simply ship and degrade quietly.

## Decision

Every PR must clear `audit.py`. The script enforces 58 invariants that
the project's quality contract depends on. Failure is not a warning:
exit code = number of failed gates.

The invariants fall into seven families:
1. Artefact integrity (I01–I05): files exist, refs resolve.
2. Metadata canonicity (I06, I09, I10, I27): absolute URLs, single host.
3. CSP hash sync (I08).
4. Asset budgets (I11–I13, I31, I32).
5. Accessibility basics (I15, I16, I23).
6. Locale parity (I29a, I29b).
7. Build invariants (I28 determinism, I30 srcset-width truthfulness).

## Consequences

+ Regressions are caught before merge, not in production.
+ Confidence in any green dist/ is mechanical, not aspirational.
+ New contributors get an instant safety net.
- Adding a new section requires understanding which gates it touches.
- Some gates need updates when budgets legitimately move (documented
  in audit.py BUDGETS comments).
