# Security policy

## Supported versions

`main` is the only supported branch. The site is static, deterministically
built, and ships from `dist/`. There are no past versions to patch — every
deploy supersedes the previous one.

## Reporting a vulnerability

If you find a security issue:

- For routine issues (CSP-violation patterns, missing security header on
  a path, broken `Reporting-Endpoints` config, etc.) — open a regular
  issue on this repo with a clear reproduction.
- For anything that could materially harm site visitors (data leak via
  some path, redirect open, malicious-content injection vector through
  a TOML edit, etc.) — **do not open a public issue**. Email
  `hello@myloradove.com.ua` with the subject `SECURITY` and a brief
  reproduction. Expect a first response within 72 hours.

## What's in scope

- Anything served from `myloradove.com.ua` or `www.myloradove.com.ua`.
- The build script (`build.py`) — bugs that could let a malicious TOML
  edit smuggle bytes into the rendered HTML.
- The audit script (`audit.py`) — false negatives on safety-critical
  gates (CSP hash sync, domain consistency, locale parity).
- The Cloudflare Pages deploy pipeline.

## What's not in scope

- Third-party browser bugs.
- Hypothetical attacks that require the attacker to already control
  the user's machine (clipboard read on click, etc.).
- Performance regressions (open a regular issue).

## Hardening already in place

- Strict CSP with SHA-256 hash for the inline JSON-LD; hash recomputed
  per build and synced to both `_headers` and `.htaccess`
  (audit gate I08).
- HSTS preload-eligible: `max-age=31536000; includeSubDomains; preload`.
- `X-Frame-Options: DENY` + CSP `frame-ancestors 'none'` — site is never
  legitimately embedded.
- `Cross-Origin-Opener-Policy: same-origin` + `Cross-Origin-Resource-Policy: same-origin`.
- `Permissions-Policy` denies 14 capabilities the site doesn't use.
- `Reporting-Endpoints` + `NEL` + `Report-To` send CSP / network-error
  reports first-party.
- Domain-consistency audit gate (I27) blocks any drift in absolute URLs.
- Build determinism (I28) makes `Cache-Control: immutable` honest.
- No third-party JS, no analytics SDK, no CDN runtime, no service worker.
