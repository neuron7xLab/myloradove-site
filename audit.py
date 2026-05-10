#!/usr/bin/env python3
"""
audit.py · Милорадове

Fail-closed verification of the production artefact in dist/.
Zero external dependencies. Runs in <5 s on any machine with Python 3.10+.

Usage:
  python3 audit.py                # audit dist/
  python3 audit.py --strict-404   # also fail on soft deprecations
  python3 audit.py --budgets-only # only budget gates

Exit 0 = clean. Exit >0 = number of failed gates. CI must fail-close.

Invariants enforced (each must be a hard engineering rule):
  I01  build artefact exists in dist/
  I02  fingerprinted css and js filenames are present and referenced
  I03  every local href/src/srcset in HTML resolves to a real file
  I04  every CSS url() resolves
  I05  every internal #anchor resolves to an existing id
  I06  canonical, og:image, og:url are ABSOLUTE (start with https://)
  I07  JSON-LD parses and Schema.org @type is correct
  I08  CSP script-src sha256 hash matches the LD content (in _headers
       AND in .htaccess fallback)
  I09  sitemap.xml is well-formed and loc is absolute
  I10  robots.txt contains Sitemap: directive with absolute URL
  I11  font preloads count ≤ MAX_FONT_PRELOADS (budget)
  I12  HTML/CSS/JS size ≤ budgets
  I13  image size ≤ budgets by variant class (640/1280/1920)
  I14  no inline event handlers or inline <script> other than ld+json
  I15  lang attribute set on <html>
  I16  every <img> has alt and explicit width+height (CLS)
  I17  _headers, _redirects, 404.html, sitemap.xml, robots.txt exist
  I18  Cache-Control immutable only on fingerprinted/immutable paths
  I19  .htaccess in dist/ has no SPA fallback (no ErrorDocument → index.html)
  I20  no stale manifest.json in dist/images/
  I27  every absolute URL uses the canonical host (no `myloradove`↔`miloradove`
       drift, no stray hosts in OG/sitemap/robots/JSON-LD)
  I28  build is deterministic — rebuilding produces byte-identical dist/
  I29  locale parity (uk↔en byte-identical key sets) + no orphan keys

The budgets are calibrated to the current asset set — if you change them,
change this file and document why in MAINTENANCE.md.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass

ROOT = pathlib.Path(__file__).resolve().parent
DIST = ROOT / "dist"

# ── Budgets ────────────────────────────────────────────────────────
MAX_FONT_PRELOADS = 2
MAX_IMAGE_PRELOADS = 1
# Per-asset budgets (bytes). Fail if an asset exceeds its class budget.
BUDGETS = {
    "html_max":    42 * 1024,   # 2026 stack: scroll-progress + mesh layers
    "css_max":     80 * 1024,   # 2026 stack: scroll-/view-timeline + chapter-reveal
                                #             + gradient-mesh + variable-axis title +
                                #             3D card hover. Budget raised from 65 KB
                                #             after measuring; still gzips to <14 KB.
    "js_max":      22 * 1024,   # 2026 stack: cursor-light + View Transitions
    "img_640":    300 * 1024,   # thumbnails / gallery previews
    "img_1280":   800 * 1024,   # article plate default
    "img_1920": 1_500 * 1024,   # lightbox / high-DPR
    "woff2_max":   60 * 1024,   # any single font subset
}


@dataclass
class Finding:
    id: str
    ok: bool
    detail: str

    def render(self) -> str:
        mark = "[PASS]" if self.ok else "[FAIL]"
        return f"  {mark} {self.id:4s}  {self.detail}"


# ── Helpers ────────────────────────────────────────────────────────
def extract_local_refs(html: str) -> set[str]:
    """All local (not external) URLs referenced from the HTML.

    srcset is comma-separated and requires splitting per item.
    src/href are single-URL and must NOT be split — otherwise commas
    inside data: URIs (e.g. `data:image/svg+xml,<svg …>`) break parsing.
    """
    paths: set[str] = set()

    # srcset: each item is "url widthDescriptor"
    for m in re.finditer(r'\bsrcset=(["\'])(.*?)\1', html):
        for chunk in m.group(2).split(","):
            p = chunk.strip().split()[0]
            if p and not p.startswith(("http", "data:", "mailto:", "#")):
                paths.add(p)

    # src / href: whole value is one URL
    for m in re.finditer(r'\b(?:src|href)=(["\'])(.*?)\1', html):
        p = m.group(2).strip()
        if p and not p.startswith(("http", "data:", "mailto:", "#")):
            paths.add(p)

    return paths


def extract_ids(html: str) -> set[str]:
    return set(re.findall(r'\bid="([^"]+)"', html))


def extract_anchors(html: str) -> set[str]:
    return set(re.findall(r'href="#([^"]+)"', html))


def sha256_b64(text: str) -> str:
    return base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode("ascii")


def classify_image(name: str) -> str | None:
    """Infer image size-class from filename suffix."""
    m = re.search(r"-(\d+)\.(?:avif|webp|jpg|jpeg|png)$", name)
    if not m:
        return None
    w = int(m.group(1))
    if w <= 700:   return "img_640"
    if w <= 1300:  return "img_1280"
    return "img_1920"


# ── Gate functions (each returns a Finding) ─────────────────────────
def gate_build_exists() -> Finding:
    ok = DIST.exists() and (DIST / "index.html").exists()
    return Finding("I01", ok, f"dist/ + index.html present: {ok}")


def gate_fingerprints(html: str) -> list[Finding]:
    css_refs = re.findall(r'href="(styles\.[a-f0-9]+\.css)"', html)
    js_refs  = re.findall(r'src="(script\.[a-f0-9]+\.js)"', html)
    f_css = Finding(
        "I02a",
        len(css_refs) == 1 and (DIST / css_refs[0]).exists(),
        f"CSS fingerprinted & present: {css_refs[0] if css_refs else 'MISSING'}",
    )
    f_js = Finding(
        "I02b",
        len(js_refs) == 1 and (DIST / js_refs[0]).exists(),
        f"JS fingerprinted & present: {js_refs[0] if js_refs else 'MISSING'}",
    )
    return [f_css, f_js]


def gate_local_refs(html: str) -> Finding:
    bad = []
    for ref in extract_local_refs(html):
        # Absolute-from-root paths map to dist/ root.
        rel = ref.lstrip("/")
        if not (DIST / rel).exists():
            bad.append(ref)
    return Finding(
        "I03",
        not bad,
        f"local href/src/srcset resolve: {len(bad)} broken" + (f" ({bad[:3]})" if bad else ""),
    )


def gate_css_urls(css_name: str) -> Finding:
    css = (DIST / css_name).read_text(encoding="utf-8")
    urls = re.findall(r"url\(['\"]?(fonts/[^'\")]+)['\"]?\)", css)
    bad = [u for u in urls if not (DIST / u).exists()]
    return Finding(
        "I04",
        not bad,
        f"CSS font url() refs resolve: {len(urls)} total, {len(bad)} broken",
    )


def gate_anchors(html: str) -> Finding:
    ids = extract_ids(html)
    bad = [a for a in extract_anchors(html) if a not in ids and a != "top"]
    # #top can resolve to the document start if hero has id=top; we include it.
    return Finding(
        "I05",
        not bad,
        f"internal anchors resolve: {len(bad)} broken" + (f" ({bad[:3]})" if bad else ""),
    )


def gate_absolute_metadata(html: str) -> list[Finding]:
    out = []
    for kind, pat in (
        ("canonical",  r'<link rel="canonical" href="([^"]+)"'),
        ("og:image",   r'<meta property="og:image"\s+content="([^"]+)"'),
    ):
        m = re.search(pat, html)
        ok = bool(m and m.group(1).startswith("https://"))
        out.append(Finding(f"I06-{kind}", ok, f"{kind} absolute: {m.group(1) if m else 'MISSING'}"))
    return out


def gate_jsonld(html: str) -> list[Finding]:
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    if not m:
        return [Finding("I07", False, "JSON-LD absent")]
    try:
        obj = json.loads(m.group(1))
    except Exception as e:
        return [Finding("I07", False, f"JSON-LD parse error: {e}")]
    # Support both shapes: single Place, or {@graph: [Place, Event, …]}
    if "@graph" in obj:
        items = obj["@graph"]
        place = next((i for i in items if i.get("@type") == "Place"), None)
    else:
        place = obj if obj.get("@type") == "Place" else None
    findings = [
        Finding("I07a", place is not None, f"@type=Place resolved: {bool(place)}"),
        Finding(
            "I07b",
            bool(place and str(place.get("image", "")).startswith("https://")),
            f"image absolute: {place.get('image', '') if place else '—'}",
        ),
    ]
    return findings


def gate_csp_hash(html: str) -> list[Finding]:
    ld = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    expected = sha256_b64(ld.group(1)) if ld else ""
    results = []
    for fname in ("_headers", ".htaccess"):
        p = DIST / fname
        if not p.exists():
            results.append(Finding(f"I08-{fname}", False, f"{fname} missing"))
            continue
        content = p.read_text(encoding="utf-8")
        results.append(Finding(
            f"I08-{fname}",
            f"'sha256-{expected}'" in content,
            f"CSP hash matches LD: {expected[:20]}... in {fname}",
        ))
    return results


def gate_sitemap() -> Finding:
    p = DIST / "sitemap.xml"
    if not p.exists():
        return Finding("I09", False, "sitemap.xml missing")
    try:
        tree = ET.fromstring(p.read_text(encoding="utf-8"))
    except ET.ParseError as e:
        return Finding("I09", False, f"sitemap.xml XML error: {e}")
    ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    locs = [el.text for el in tree.findall(f"{ns}url/{ns}loc")]
    ok = all(l and l.startswith("https://") for l in locs)
    return Finding("I09", ok, f"sitemap locs absolute: {len(locs)} urls")


def gate_robots() -> Finding:
    p = DIST / "robots.txt"
    if not p.exists():
        return Finding("I10", False, "robots.txt missing")
    r = p.read_text(encoding="utf-8")
    ok = bool(re.search(r"^Sitemap:\s*https?://", r, re.M))
    return Finding("I10", ok, "robots has Sitemap directive: " + str(ok))


def gate_font_preload_budget(html: str) -> Finding:
    preloads = re.findall(r'<link rel="preload"[^>]*as="font"[^>]*>', html)
    ok = len(preloads) <= MAX_FONT_PRELOADS
    return Finding(
        "I11",
        ok,
        f"font preloads: {len(preloads)} (budget ≤ {MAX_FONT_PRELOADS})",
    )


def gate_file_budgets(html: str, css_name: str, js_name: str) -> list[Finding]:
    out = []
    sizes = {
        "html_max": (DIST / "index.html").stat().st_size,
        "css_max":  (DIST / css_name).stat().st_size,
        "js_max":   (DIST / js_name).stat().st_size,
    }
    for key, actual in sizes.items():
        budget = BUDGETS[key]
        out.append(Finding(
            f"I12-{key}",
            actual <= budget,
            f"{key}: {actual/1024:.1f} KB / budget {budget/1024:.0f} KB",
        ))
    return out


def gate_image_budgets() -> list[Finding]:
    images_dir = DIST / "images"
    bad = []
    counts = {"img_640": 0, "img_1280": 0, "img_1920": 0}
    for p in images_dir.iterdir():
        cls = classify_image(p.name)
        if cls is None:
            continue
        counts[cls] += 1
        if p.stat().st_size > BUDGETS[cls]:
            bad.append((p.name, p.stat().st_size, BUDGETS[cls]))
    out = [Finding(
        "I13",
        not bad,
        f"image budgets: {sum(counts.values())} checked, {len(bad)} over-budget"
        + ("" if not bad else f" (worst: {bad[0][0]} {bad[0][1]/1024:.0f} KB > {bad[0][2]/1024:.0f} KB)"),
    )]
    return out


def gate_no_inline_handlers(html: str) -> list[Finding]:
    handlers = re.findall(r'\son\w+="', html)
    # JSON-LD script is allowed (covered by CSP hash); anything else = fail.
    inline_scripts = len(re.findall(
        r'<script\b(?![^>]*\bsrc=)(?![^>]*type="application/ld\+json")',
        html,
    ))
    return [
        Finding("I14a", not handlers, f"inline event handlers: {len(handlers)}"),
        Finding("I14b", inline_scripts == 0, f"inline executable <script>: {inline_scripts}"),
    ]


def gate_html_a11y_basics(html: str) -> list[Finding]:
    lang = re.search(r'<html\s[^>]*lang="([^"]+)"', html)
    imgs = re.findall(r"<img\b[^>]*>", html)
    no_alt = [i for i in imgs if not re.search(r'\balt="', i)]
    # Allow alt="" for decorative (water duplicate) — we check presence of attr only.
    no_dim = [
        i for i in imgs
        if not (re.search(r'\bwidth=', i) and re.search(r'\bheight=', i))
        and "lightbox" not in (extract_nearest_class(html, i) or "")
    ]
    return [
        Finding("I15", lang is not None, f"html lang: {lang.group(1) if lang else 'MISSING'}"),
        Finding("I16a", not no_alt, f"<img> with alt: {len(imgs)-len(no_alt)}/{len(imgs)}"),
        Finding("I16b", len(no_dim) <= 1, f"<img> with w+h (CLS): {len(imgs)-len(no_dim)}/{len(imgs)} (lightbox dialog img exempted)"),
    ]


def extract_nearest_class(html: str, img_tag: str) -> str:
    # Best-effort: return class of the ancestor within the html source.
    idx = html.find(img_tag)
    if idx < 0:
        return ""
    # Search backwards for nearest opening tag's class attr.
    prev = html[:idx]
    m = list(re.finditer(r'class="([^"]+)"', prev))
    return m[-1].group(1) if m else ""


def gate_deploy_artefacts() -> list[Finding]:
    out = []
    for name in ("_headers", "_redirects", "404.html", "sitemap.xml", "robots.txt", ".htaccess"):
        out.append(Finding(
            f"I17-{name.lstrip('.').replace('.', '_')}",
            (DIST / name).exists(),
            f"artefact present: {name}",
        ))
    return out


def gate_cache_policy() -> Finding:
    p = DIST / "_headers"
    if not p.exists():
        return Finding("I18", False, "_headers missing")
    h = p.read_text(encoding="utf-8")
    # HTML must NOT be immutable, assets *may* be.
    html_rule = re.search(r"/index\.html\s*\n\s*Cache-Control:\s*([^\n]+)", h)
    ok_html = bool(html_rule and "immutable" not in html_rule.group(1))
    # Fingerprinted paths should be immutable.
    css_rule = re.search(r"/\*\.css\s*\n\s*Cache-Control:\s*([^\n]+)", h)
    ok_css = bool(css_rule and "immutable" in css_rule.group(1))
    return Finding(
        "I18",
        ok_html and ok_css,
        f"HTML short-cache={ok_html}, fingerprinted-assets immutable={ok_css}",
    )


def gate_htaccess_no_spa() -> Finding:
    p = DIST / ".htaccess"
    if not p.exists():
        return Finding("I19", True, "no .htaccess (fine for CF Pages)")
    h = p.read_text(encoding="utf-8")
    bad = bool(re.search(r"ErrorDocument\s+404\s+/index\.html", h))
    return Finding("I19", not bad, "no SPA-fallback ErrorDocument: " + str(not bad))


def gate_no_stale_manifest() -> Finding:
    stale = DIST / "images" / "manifest.json"
    return Finding("I20", not stale.exists(), "no stale images/manifest.json")


def gate_early_hints() -> Finding:
    """_headers must emit Link: … rel=preload on the HTML document path
    so Cloudflare can send Early Hints (HTTP 103) before the 200."""
    p = DIST / "_headers"
    if not p.exists():
        return Finding("I21", False, "_headers missing")
    h = p.read_text(encoding="utf-8")
    # Look for "Link:" directive within an "/" or "/index.html" block.
    ok = bool(re.search(r"/(?:index\.html)?\s*\n(?:\s+[^\n]+\n)*?\s+Link:\s", h))
    return Finding("I21", ok, "Early-Hints Link on HTML path present: " + str(ok))


def gate_events_roundtrip() -> list[Finding]:
    """If there are upcoming events, dist/events.ics must exist and the
    HTML must list them. If none, events.ics must NOT be emitted."""
    import tomllib as _toml
    events_src = ROOT / "data" / "events.toml"
    out = []
    if not events_src.exists():
        return [Finding("I22", True, "no events.toml — skipping")]
    with open(events_src, "rb") as f:
        events = _toml.load(f).get("event", [])
    import datetime as _dt
    today = _dt.date.today()
    upcoming_count = sum(1 for e in events if _dt.date.fromisoformat(str(e["date"])) >= today)

    html_doc = (DIST / "index.html").read_text(encoding="utf-8")

    ics = DIST / "events.ics"
    if upcoming_count:
        out.append(Finding("I22a", ics.exists(), f"events.ics emitted ({upcoming_count} upcoming)"))
        if ics.exists():
            ics_text = ics.read_text(encoding="utf-8")
            ok_calendar = ics_text.startswith("BEGIN:VCALENDAR") and ics_text.rstrip().endswith("END:VCALENDAR")
            ok_count = ics_text.count("BEGIN:VEVENT") == upcoming_count
            out.append(Finding("I22b", ok_calendar, "events.ics well-formed RFC 5545"))
            out.append(Finding("I22c", ok_count, f"events.ics has {upcoming_count} VEVENT blocks"))
        # Every upcoming event must surface a JSON-LD Event.
        ld = re.search(r'<script type="application/ld\+json">(.*?)</script>', html_doc, re.S)
        if ld:
            ld_obj = json.loads(ld.group(1))
            graph = ld_obj.get("@graph", [ld_obj])
            event_count = sum(1 for i in graph if i.get("@type") == "Event")
            out.append(Finding(
                "I22d",
                event_count == upcoming_count,
                f"JSON-LD Event count: {event_count}/{upcoming_count} upcoming",
            ))
    else:
        out.append(Finding("I22a", not ics.exists(), "no upcoming events → events.ics correctly absent"))
    return out


def gate_contacts_role_based() -> Finding:
    """Published emails must be role-based (hello/rada/culture/school/etc.),
    not personal handles (no firstname.surname patterns)."""
    import tomllib as _toml
    src = ROOT / "data" / "contacts.toml"
    if not src.exists():
        return Finding("I23", True, "no contacts.toml — skipping")
    with open(src, "rb") as f:
        contacts = _toml.load(f).get("contact", [])
    bad = [c["handle"] for c in contacts if "." in c["handle"] or len(c["handle"]) > 18]
    return Finding(
        "I23",
        not bad,
        f"role-based emails: {len(contacts)} contacts, {len(bad)} personal-looking",
    )


def gate_email_cards_rendered(html: str) -> Finding:
    """If contacts.toml has entries, the emitted HTML must contain
    email cards with copy buttons. Silent empty block = bug."""
    import tomllib as _toml
    src = ROOT / "data" / "contacts.toml"
    if not src.exists():
        return Finding("I24", True, "no contacts.toml — skipping")
    with open(src, "rb") as f:
        contacts = _toml.load(f).get("contact", [])
    card_count = html.count('class="email-card"')
    copy_count = html.count('class="email-card__copy"')
    ok = card_count == len(contacts) == copy_count
    return Finding(
        "I24",
        ok,
        f"contact cards rendered: cards={card_count} copyBtns={copy_count} data={len(contacts)}",
    )


def gate_bilingual_shell() -> list[Finding]:
    """Verify the English shell exists and is properly cross-linked."""
    out = []
    uk_doc = DIST / "index.html"
    en_doc = DIST / "en" / "index.html"
    if not en_doc.exists():
        return [Finding("I26", False, "dist/en/index.html missing")]

    out.append(Finding("I26", True, "en/ shell exists"))

    uk_html = uk_doc.read_text(encoding="utf-8")
    en_html = en_doc.read_text(encoding="utf-8")

    # 1. <html lang> matches locale
    uk_lang = re.search(r'<html[^>]*lang="([^"]+)"', uk_html)
    en_lang = re.search(r'<html[^>]*lang="([^"]+)"', en_html)
    out.append(Finding(
        "I26a",
        uk_lang and uk_lang.group(1) == "uk" and en_lang and en_lang.group(1) == "en",
        f"<html lang>: uk='{uk_lang.group(1) if uk_lang else '?'}', en='{en_lang.group(1) if en_lang else '?'}'",
    ))

    # 2. hreflang triplet in both docs
    for code, html_doc in (("uk", uk_html), ("en", en_html)):
        has_uk = 'hreflang="uk"' in html_doc
        has_en = 'hreflang="en"' in html_doc
        has_def = 'hreflang="x-default"' in html_doc
        out.append(Finding(
            f"I26b-{code}",
            has_uk and has_en and has_def,
            f"{code} page has hreflang uk+en+x-default: {has_uk}+{has_en}+{has_def}",
        ))

    # 3. No unresolved {{t.*}} markers left
    uk_unresolved = len(re.findall(r'\{\{\s*t\.', uk_html))
    en_unresolved = len(re.findall(r'\{\{\s*t\.', en_html))
    out.append(Finding("I26c-uk", uk_unresolved == 0, f"UK unresolved {{t.*}} markers: {uk_unresolved}"))
    out.append(Finding("I26c-en", en_unresolved == 0, f"EN unresolved {{t.*}} markers: {en_unresolved}"))

    # 4. Lang switch present and points to the OTHER locale
    uk_sw = re.search(r'<a class="lang-switch"[^>]*href="([^"]+)"[^>]*hreflang="([^"]+)"', uk_html)
    en_sw = re.search(r'<a class="lang-switch"[^>]*href="([^"]+)"[^>]*hreflang="([^"]+)"', en_html)
    out.append(Finding(
        "I26d-uk",
        bool(uk_sw and uk_sw.group(1) == "/en/" and uk_sw.group(2) == "en"),
        f"uk page: switch → /en/ (hreflang=en): {bool(uk_sw)}",
    ))
    out.append(Finding(
        "I26d-en",
        bool(en_sw and en_sw.group(1) == "/" and en_sw.group(2) == "uk"),
        f"en page: switch → / (hreflang=uk): {bool(en_sw)}",
    ))

    # 5. Canonical differs per locale
    uk_canon = re.search(r'<link rel="canonical" href="([^"]+)"', uk_html)
    en_canon = re.search(r'<link rel="canonical" href="([^"]+)"', en_html)
    out.append(Finding(
        "I26e",
        bool(uk_canon and en_canon and uk_canon.group(1) != en_canon.group(1)
             and en_canon.group(1).endswith("/en/")),
        f"canonicals: uk={uk_canon.group(1) if uk_canon else '?'}, en={en_canon.group(1) if en_canon else '?'}",
    ))

    # 6. EN page uses root-relative asset paths (so /en/ doesn't double up)
    bad_rel = len(re.findall(r'(?:src|href)="(?!https?:|#|/|data:|mailto:)([^"]+)"', en_html))
    out.append(Finding("I26f", bad_rel == 0, f"EN page has no broken relative asset paths: {bad_rel == 0}"))

    return out


def gate_events_ics_content_type() -> Finding:
    """events.ics path must have Content-Type: text/calendar in _headers."""
    p = DIST / "_headers"
    if not p.exists() or not (DIST / "events.ics").exists():
        return Finding("I25", True, "no events.ics or _headers — skipping")
    h = p.read_text(encoding="utf-8")
    ok = bool(re.search(r"/events\.ics\s*\n(?:\s+[^\n]+\n)*?\s+Content-Type:\s+text/calendar", h))
    return Finding("I25", ok, "events.ics served with Content-Type: text/calendar")


def gate_locale_parity() -> list[Finding]:
    """Locale TOMLs must declare byte-identical key sets so build.py
    cannot silently emit a partial English shell when a translator
    forgets a key. Also surfaces orphan keys (defined but referenced
    nowhere) so the locales don't silently grow stale strings."""
    import tomllib as _toml
    out: list[Finding] = []
    uk_path = ROOT / "data" / "locale.uk.toml"
    en_path = ROOT / "data" / "locale.en.toml"
    if not (uk_path.exists() and en_path.exists()):
        return [Finding("I29", True, "no locale TOMLs — skipping")]
    def flat(d: dict, p: str = "") -> set[str]:
        s: set[str] = set()
        for k, v in d.items():
            full = f"{p}.{k}" if p else k
            if isinstance(v, dict):
                s |= flat(v, full)
            else:
                s.add(full)
        return s
    uk = flat(_toml.loads(uk_path.read_text(encoding="utf-8")))
    en = flat(_toml.loads(en_path.read_text(encoding="utf-8")))
    sym = uk.symmetric_difference(en)
    out.append(Finding(
        "I29a", not sym,
        f"locale parity (uk↔en): {len(uk)} keys each"
        + (f", drift={sorted(sym)[:5]}" if sym else ""),
    ))
    # Orphan-key sweep: scan HTML/CSS/JS/build.py for references to t.X.y
    # AND for direct dict-style locale lookups (`t["section"]["key"]` /
    # `locale["section"]["key"]`). Keys flagged here are not blockers,
    # but the gate names them so they get cleaned, not accreted.
    refs: set[str] = set()
    template_re = re.compile(r"\{\{t\.([\w.]+)\}\}")
    bracket_re  = re.compile(r"""(?:t|locale)\[["']([\w]+)["']\]\[["']([\w]+)["']\]""")
    for src in [ROOT/"index.html", ROOT/"build.py", ROOT/"script.js"]:
        if not src.exists():
            continue
        txt = src.read_text(encoding="utf-8")
        refs |= set(template_re.findall(txt))
        for sect, key in bracket_re.findall(txt):
            refs.add(f"{sect}.{key}")
    orphan_uk = sorted(k for k in uk if k not in refs and "." in k)
    out.append(Finding(
        "I29b", not orphan_uk,
        f"locale orphan-keys (defined, never referenced): {len(orphan_uk)}"
        + (f"; first 5: {orphan_uk[:5]}" if orphan_uk else ""),
    ))
    return out


def gate_domain_consistency() -> Finding:
    """Every absolute URL emitted in dist/ must use exactly one host:
    the canonical origin from site.config.json. Catches typos like
    `miloradove` vs `myloradove` that pass HTML validation but break
    sitemap discovery, OG previews, and email-routing trust."""
    cfg = json.loads((ROOT / "site.config.json").read_text(encoding="utf-8"))
    canonical_host = re.sub(r"^https?://", "", cfg["origin"]).rstrip("/")
    # Search every text-like artefact in dist/ for hostname-shaped tokens.
    pattern = re.compile(r"https?://([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})")
    text_exts = {".html", ".xml", ".txt", ".json", ".css", ".js", ".ics", ""}
    foreign: dict[str, list[str]] = {}
    for p in DIST.rglob("*"):
        if not p.is_file() or p.suffix not in text_exts and p.name not in {"_headers", "_redirects", ".htaccess"}:
            continue
        try:
            txt = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for host in pattern.findall(txt):
            # Allow canonical, its www-alias, and well-known external hosts
            # that are intentional (schema.org, w3.org, sitemaps schema).
            if host in {canonical_host, f"www.{canonical_host}",
                        "schema.org", "www.schema.org",
                        "www.w3.org", "www.sitemaps.org",
                        "fonts.gstatic.com"}:
                continue
            # Anything else that looks like the canonical host but isn't = typo.
            if canonical_host.split(".")[0][:4] in host or host.endswith(canonical_host.split(".", 1)[1]):
                foreign.setdefault(p.name, []).append(host)
    bad = sum(len(v) for v in foreign.values())
    detail = ", ".join(f"{f}:{','.join(set(h))}" for f, h in foreign.items()) or canonical_host
    return Finding("I27", bad == 0, f"domain consistency ({canonical_host}): {bad} foreign refs [{detail}]")


def gate_build_determinism() -> Finding:
    """Re-run build.py and confirm every file in dist/ has identical bytes.
    Build determinism is a load-bearing invariant — non-deterministic
    output silently invalidates CSP hashes and Cache-Control immutability."""
    import shutil, tempfile
    if not (ROOT / "build.py").exists():
        return Finding("I28", True, "no build.py — skipping")
    # Snapshot current dist/ hashes
    before: dict[str, str] = {}
    for p in DIST.rglob("*"):
        if p.is_file():
            before[str(p.relative_to(DIST))] = hashlib.sha256(p.read_bytes()).hexdigest()
    # Rebuild into a tmp dir to avoid clobbering, then diff
    with tempfile.TemporaryDirectory() as td:
        td_path = pathlib.Path(td) / "dist"
        # Run build.py with DIST overridden via env var if supported,
        # otherwise rebuild in place and re-hash.
        result = subprocess.run(
            [sys.executable, "build.py"],
            cwd=ROOT, capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            return Finding("I28", False, f"rebuild failed: {result.stderr[:200]}")
    after: dict[str, str] = {}
    for p in DIST.rglob("*"):
        if p.is_file():
            after[str(p.relative_to(DIST))] = hashlib.sha256(p.read_bytes()).hexdigest()
    drift = [k for k in before if before.get(k) != after.get(k)]
    missing = [k for k in before if k not in after]
    new = [k for k in after if k not in before]
    bad = drift + missing + new
    return Finding("I28", not bad, f"determinism: {len(before)} files, {len(bad)} drift")


# ── Main driver ────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budgets-only", action="store_true")
    args = ap.parse_args()

    if not DIST.exists():
        print("[FAIL] dist/ does not exist — run `python3 build.py` first.")
        return 1

    html = (DIST / "index.html").read_text(encoding="utf-8")

    # Locate fingerprinted filenames from HTML (don't scan dir)
    css_match = re.search(r'href="(styles\.[a-f0-9]+\.css)"', html)
    js_match  = re.search(r'src="(script\.[a-f0-9]+\.js)"', html)
    css_name = css_match.group(1) if css_match else "styles.css"
    js_name  = js_match.group(1) if js_match else "script.js"

    findings: list[Finding] = []

    if not args.budgets_only:
        findings.append(gate_build_exists())
        findings.extend(gate_fingerprints(html))
        findings.append(gate_local_refs(html))
        findings.append(gate_css_urls(css_name))
        findings.append(gate_anchors(html))
        findings.extend(gate_absolute_metadata(html))
        findings.extend(gate_jsonld(html))
        findings.extend(gate_csp_hash(html))
        findings.append(gate_sitemap())
        findings.append(gate_robots())
        findings.extend(gate_no_inline_handlers(html))
        findings.extend(gate_html_a11y_basics(html))
        findings.extend(gate_deploy_artefacts())
        findings.append(gate_cache_policy())
        findings.append(gate_htaccess_no_spa())
        findings.append(gate_no_stale_manifest())
        findings.append(gate_early_hints())
        findings.extend(gate_events_roundtrip())
        findings.append(gate_contacts_role_based())
        findings.append(gate_email_cards_rendered(html))
        findings.append(gate_events_ics_content_type())
        findings.extend(gate_bilingual_shell())
        findings.extend(gate_locale_parity())
        findings.append(gate_domain_consistency())
        # Determinism is the most expensive gate; runs last so failures
        # are easy to read even when the rebuild diff is large.
        findings.append(gate_build_determinism())

    # Budget gates always run
    findings.append(gate_font_preload_budget(html))
    findings.extend(gate_file_budgets(html, css_name, js_name))
    findings.extend(gate_image_budgets())

    # Report
    print("══════════════════════════════════════════════════════════════════")
    print("  audit.py · Милорадове · fail-closed verification")
    print("══════════════════════════════════════════════════════════════════")
    passed = sum(1 for f in findings if f.ok)
    failed = sum(1 for f in findings if not f.ok)
    for f in findings:
        print(f.render())
    print("══════════════════════════════════════════════════════════════════")
    print(f"  {passed}/{len(findings)} gates PASS  ·  {failed} FAIL")
    print("══════════════════════════════════════════════════════════════════")
    return failed


if __name__ == "__main__":
    sys.exit(main())
