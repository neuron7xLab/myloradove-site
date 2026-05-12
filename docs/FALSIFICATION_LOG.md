# Falsification Log

## Scope
Structured log of attempts to disprove production-safety claims.

## 2026-05-12

### Attempt F-001: Break deterministic output
- Method: force repeated builds and compare outputs via `audit.py` determinism gate.
- Expected falsifier: non-zero drift in generated artifacts.
- Result: not falsified (I28 PASS).
- Negative learning: current build pipeline is stable under same inputs.

### Attempt F-002: Break locale contract parity
- Method: verify uk/en locale key parity gate.
- Expected falsifier: orphan/missing keys between locale files.
- Result: not falsified (I29a/I29b PASS).
- Negative learning: locale schema discipline currently holds.

### Attempt F-003: Break budget envelope
- Method: run full audit budget checks for HTML/CSS/JS and image caps.
- Expected falsifier: any budget exceedance.
- Result: not falsified (I11-I13, I31-I32 PASS).
- Negative learning: performance guardrails are currently enforced.

## External witness
- Witness: deterministic CI + independent toolchain checks (`audit.py`, Playwright, Lighthouse in CI).
- Status: partial externalization achieved; formal third-party review pending.
