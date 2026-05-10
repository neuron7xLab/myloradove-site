#!/usr/bin/env python3
"""
build.py · Милорадове / Myloradove

Deterministic bilingual static-site build. Python 3.11+ stdlib only.

Locale strategy
  uk (default) → dist/index.html, dist/events.ics
  en           → dist/en/index.html, dist/en/events.ics
  alternates linked via <link rel="alternate" hreflang="..."> in <head>
  Cloudflare Pages _headers emits per-path CSP hash and Early Hints.

Source of truth per language
  index.html             — single template with {{t.KEY}} markers
  data/locale.uk.toml    — Ukrainian strings (authoritative)
  data/locale.en.toml    — English strings (fallback to uk if missing)
  data/events.toml       — events; optional `_en` fields
  data/contacts.toml     — emails; optional `_en` fields
  site.config.json       — origin, geo, address

Usage:
  python3 build.py             production, absolute URLs, hashed assets
  python3 build.py --preview   local preview, relative URLs, no hash
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import html
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import textwrap
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent
DIST = ROOT / "dist"
DATA = ROOT / "data"

LOCALES = ("uk", "en")
DEFAULT_LOCALE = "uk"


# ─── Config & data ─────────────────────────────────────────────────
def load_config() -> dict:
    with open(ROOT / "site.config.json", encoding="utf-8") as f:
        return json.load(f)


def load_locale(code: str) -> dict:
    """Load locale.{code}.toml as a nested dict. Unknown keys are harmless."""
    p = DATA / f"locale.{code}.toml"
    with open(p, "rb") as f:
        return tomllib.load(f)


def load_events() -> list[dict]:
    p = DATA / "events.toml"
    return tomllib.load(p.open("rb")).get("event", []) if p.exists() else []


def load_contacts() -> list[dict]:
    p = DATA / "contacts.toml"
    return tomllib.load(p.open("rb")).get("contact", []) if p.exists() else []


# ─── Hashing ───────────────────────────────────────────────────────
def content_hash(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


def sha256_b64(text: str) -> str:
    return base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode("ascii")


# ─── Template: nested {{t.a.b}} dotted-key expansion ───────────────
def _get(d: dict, dotted_key: str, fallback: dict | None = None):
    for seg in dotted_key.split("."):
        if isinstance(d, dict) and seg in d:
            d = d[seg]
        else:
            if fallback is not None:
                return _get(fallback, dotted_key, None)
            return None
    return d


def render_template(template: str, locale: dict, fallback: dict) -> str:
    """Replace every `{{t.a.b.c}}` with the resolved value. Missing keys fall
    back to the default-locale value; if still missing we leave the marker
    untouched so it's visible in audit.py and immediately fixable."""
    def sub(m: re.Match) -> str:
        key = m.group(1)
        val = _get(locale, key, fallback)
        if val is None:
            return m.group(0)
        return str(val)

    return re.sub(r"\{\{\s*t\.([\w.]+)\s*\}\}", sub, template)


# ─── Events split + render ─────────────────────────────────────────
def _event_field(e: dict, base: str, locale: str) -> str:
    """`title_en` takes precedence when locale==en, else `title`."""
    if locale != DEFAULT_LOCALE:
        suffix = f"_{locale}"
        if e.get(base + suffix):
            return str(e[base + suffix])
    return str(e.get(base, ""))


def split_events(events: list[dict], today: dt.date) -> tuple[list[dict], list[dict]]:
    upcoming, past = [], []
    for e in events:
        d = dt.date.fromisoformat(str(e["date"]))
        (upcoming if d >= today else past).append(e)
    upcoming.sort(key=lambda e: (str(e["date"]), e.get("time", "")))
    past.sort(key=lambda e: str(e["date"]), reverse=True)
    return upcoming, past


UA_MONTHS = {
    1: "січня", 2: "лютого", 3: "березня", 4: "квітня",
    5: "травня", 6: "червня", 7: "липня", 8: "серпня",
    9: "вересня", 10: "жовтня", 11: "листопада", 12: "грудня",
}
UA_MON_SHORT = {k: v[:3] for k, v in UA_MONTHS.items()}
EN_MONTHS = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}
EN_MON_SHORT = {k: v[:3].upper() for k, v in EN_MONTHS.items()}


def format_date(iso: str, locale: str) -> str:
    d = dt.date.fromisoformat(iso)
    if locale == "en":
        return f"{EN_MONTHS[d.month]} {d.day}, {d.year}"
    return f"{d.day} {UA_MONTHS[d.month]} {d.year}"


def month_short(d: dt.date, locale: str) -> str:
    return EN_MON_SHORT[d.month] if locale == "en" else UA_MON_SHORT[d.month]


def render_event_card(e: dict, locale: str) -> str:
    date_iso = str(e["date"])
    time = e.get("time", "")
    datetime_attr = f"{date_iso}T{time}" if time else date_iso
    d = dt.date.fromisoformat(date_iso)

    title = _event_field(e, "title", locale)
    place = _event_field(e, "place", locale)
    desc = _event_field(e, "description", locale)
    cta_label = _event_field(e, "cta_label", locale)
    cta_url = e.get("cta_url", "")

    cta = (
        f'<a class="event__cta" href="{html.escape(cta_url)}" rel="noopener" target="_blank">'
        f'{html.escape(cta_label)} →</a>'
        if cta_url and cta_label else ""
    )
    place_html = f'<span class="event__place">{html.escape(place)}</span>' if place else ""
    time_html = f' · <time>{html.escape(time)}</time>' if time else ""

    return (
        '<article class="event">'
        '<div class="event__date" aria-hidden="true">'
        f'<span class="event__day">{d.day}</span>'
        f'<span class="event__mon">{month_short(d, locale)}</span>'
        '</div>'
        '<div class="event__body">'
        f'<h3 class="event__title">{html.escape(title)}</h3>'
        f'<p class="event__meta"><time datetime="{datetime_attr}">{format_date(date_iso, locale)}</time>'
        f'{time_html}{(" · " + place_html) if place_html else ""}</p>'
        f'<p class="event__desc">{html.escape(desc)}</p>'
        f'{cta}'
        '</div>'
        '</article>'
    )


def render_events_section(
    upcoming: list[dict], past: list[dict], t: dict, locale: str
) -> str:
    if not upcoming and not past:
        return f'<p class="events__empty">{t["events"]["empty"]}</p>'
    parts = []
    if upcoming:
        parts.append(
            '<div class="events__list">'
            + "".join(render_event_card(e, locale) for e in upcoming)
            + "</div>"
        )
    else:
        parts.append(f'<p class="events__empty">{t["events"]["empty_soon"]}</p>')
    if past:
        parts.append(
            '<details class="events__archive">'
            f'<summary>{html.escape(t["events"]["archive"])}</summary>'
            '<div class="events__list events__list--past">'
            + "".join(render_event_card(e, locale) for e in past)
            + "</div>"
            "</details>"
        )
    return "".join(parts)


# ─── JSON-LD ───────────────────────────────────────────────────────
def render_jsonld(
    cfg: dict, contacts: list[dict], events_upcoming: list[dict],
    locale: str, t: dict, *, absolute: bool,
) -> str:
    origin = cfg["origin"].rstrip("/") if absolute else ""
    path = "/" if locale == DEFAULT_LOCALE else f"/{locale}/"
    email_domain = cfg["email_domain"]

    place = {
        "@context": "https://schema.org",
        "@type": "Place",
        "@id": f"{origin}{path}#place" if absolute else f"{path}#place",
        "name": t["hero"]["title"],
        "alternateName": cfg.get("alternateNames", []),
        "description": t["meta"]["description"],
        "inLanguage": locale,
        "url": f"{origin}{path}" if absolute else path,
        "geo": {
            "@type": "GeoCoordinates",
            "latitude": cfg["geo"]["lat"],
            "longitude": cfg["geo"]["lon"],
            "elevation": cfg["geo"]["elevation"],
        },
        "address": {
            "@type": "PostalAddress",
            "addressCountry": cfg["address"]["country"],
            "addressRegion": cfg["address"]["region"],
            "addressLocality": cfg["address"]["locality"],
            "postalCode": cfg["address"]["postalCode"],
            "streetAddress": cfg["address"]["street"],
        },
        "containedInPlace": {
            "@type": "AdministrativeArea",
            "name": cfg["containedIn"],
        },
        "image": f"{origin}/images/milorado_fields-1184.webp" if absolute else "images/milorado_fields-1184.webp",
    }
    if contacts:
        place["contactPoint"] = [
            {
                "@type": "ContactPoint",
                "contactType": (c.get(f"role_{locale}") if locale != DEFAULT_LOCALE else c.get("role")) or c["role"],
                "email": f"{c['handle']}@{email_domain}",
                "areaServed": "UA",
                "availableLanguage": ["uk", "en"],
            }
            for c in contacts
        ]

    graph = [place]
    for e in events_upcoming:
        date_iso = str(e["date"])
        tm = e.get("time", "")
        start = f"{date_iso}T{tm}:00+03:00" if tm else date_iso
        graph.append({
            "@type": "Event",
            "name": _event_field(e, "title", locale),
            "startDate": start,
            "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
            "eventStatus": "https://schema.org/EventScheduled",
            "location": {
                "@type": "Place",
                "name": _event_field(e, "place", locale) or t["hero"]["title"],
                "address": place["address"],
            },
            "description": _event_field(e, "description", locale),
            "inLanguage": locale,
            "organizer": {"@type": "Place", "@id": place["@id"]},
        })

    doc = {"@context": "https://schema.org", "@graph": graph} if len(graph) > 1 else place
    return json.dumps(doc, ensure_ascii=False, indent=2)


# ─── iCal ──────────────────────────────────────────────────────────
def render_ics(events: list[dict], cfg: dict, locale: str) -> str:
    origin = cfg["origin"].rstrip("/")
    # Deterministic DTSTAMP: derived from content lastmod, not wall clock.
    # Wall-clock now() would silently break audit gate I28 (build determinism)
    # and pollute Cache-Control: immutable on /events.ics.
    stamp_date = _content_lastmod().replace("-", "")
    stamp = f"{stamp_date}T000000Z"
    anchor = "#events"
    path = "/" if locale == DEFAULT_LOCALE else f"/{locale}/"
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Myloradove//Civic Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Events — Myloradove" if locale == "en" else "X-WR-CALNAME:Події села Милорадове",
        "X-WR-TIMEZONE:Europe/Kyiv",
    ]
    for e in events:
        uid = f'{e["id"]}@{cfg["email_domain"]}'
        dc = str(e["date"]).replace("-", "")
        tm = e.get("time", "")
        if tm:
            tcs = tm.replace(":", "") + "00"
            dtstart = f"DTSTART;TZID=Europe/Kyiv:{dc}T{tcs}"
        else:
            dtstart = f"DTSTART;VALUE=DATE:{dc}"
        title = _event_field(e, "title", locale)
        desc = _event_field(e, "description", locale)
        place = _event_field(e, "place", locale) or "Myloradove"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{stamp}",
            dtstart,
            f"SUMMARY:{_ics_escape(title)}",
            f"DESCRIPTION:{_ics_escape(desc)}",
            f"LOCATION:{_ics_escape(place)}",
            f"URL:{origin}{path}{anchor}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def _ics_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", r"\;").replace(",", r"\,").replace("\n", r"\n")


# ─── Contacts ──────────────────────────────────────────────────────
def render_contacts_block(contacts: list[dict], cfg: dict, t: dict, locale: str) -> str:
    if not contacts:
        return ""
    dom = cfg["email_domain"]
    items = []
    copy_label = t["contact"]["copy_label"]
    copy_aria = t["contact"]["copy_aria"]
    for c in contacts:
        email = f'{c["handle"]}@{dom}'
        role = (c.get(f"role_{locale}") if locale != DEFAULT_LOCALE else None) or c["role"]
        desc = (c.get(f"description_{locale}") if locale != DEFAULT_LOCALE else None) or c["description"]
        items.append(
            '<li class="email-card">'
            f'<p class="email-card__role">{html.escape(role)}</p>'
            f'<p class="email-card__desc">{html.escape(desc)}</p>'
            '<div class="email-card__row">'
            f'<a class="email-card__addr" href="mailto:{html.escape(email)}">{html.escape(email)}</a>'
            f'<button class="email-card__copy" type="button" data-copy="{html.escape(email)}" '
            f'aria-label="{html.escape(copy_aria)} {html.escape(email)}">'
            '<svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
            '<rect x="9" y="9" width="13" height="13" rx="2"/>'
            '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>'
            "</svg>"
            f'<span class="email-card__copy-label">{html.escape(copy_label)}</span>'
            "</button>"
            "</div>"
            "</li>"
        )
    return (
        '<ul class="emails" role="list">' + "".join(items) + "</ul>"
        '<p class="emails__hint" role="status" aria-live="polite" data-copy-status '
        f'data-copy-ok="{html.escape(t["contact"]["copy_status_ok"])}" '
        f'data-copy-err="{html.escape(t["contact"]["copy_status_err"])}"></p>'
    )


# ─── Language switcher ─────────────────────────────────────────────
UK_FLAG_SVG = (
    '<svg class="lang-switch__flag" viewBox="0 0 60 40" aria-hidden="true">'
    '<rect width="60" height="20" fill="#005BBB"/>'
    '<rect y="20" width="60" height="20" fill="#FFD500"/>'
    "</svg>"
)

GB_FLAG_SVG = (
    # Union Jack, simplified but geometrically correct.
    '<svg class="lang-switch__flag" viewBox="0 0 60 40" aria-hidden="true">'
    '<clipPath id="gb-clip"><rect width="60" height="40"/></clipPath>'
    '<g clip-path="url(#gb-clip)">'
    '<rect width="60" height="40" fill="#012169"/>'
    '<path d="M0,0 60,40 M60,0 0,40" stroke="#fff" stroke-width="8"/>'
    '<path d="M0,0 60,40" stroke="#C8102E" stroke-width="4" '
    'clip-path="polygon(0 0, 50% 50%, 100% 0%)"/>'
    '<path d="M60,0 0,40" stroke="#C8102E" stroke-width="4" '
    'clip-path="polygon(50% 50%, 100% 100%, 0% 100%)"/>'
    '<path d="M30,0 V40 M0,20 H60" stroke="#fff" stroke-width="10"/>'
    '<path d="M30,0 V40 M0,20 H60" stroke="#C8102E" stroke-width="6"/>'
    "</g></svg>"
)


def render_lang_switch(current: str, t: dict) -> str:
    """Badge in top-right. Shows the OTHER language's flag + 2-letter code;
    clicking switches to that language's page. Inline SVG = no extra fetch."""
    href = "/en/" if current == DEFAULT_LOCALE else "/"
    other_hreflang = "en" if current == DEFAULT_LOCALE else "uk"
    other_flag = GB_FLAG_SVG if current == DEFAULT_LOCALE else UK_FLAG_SVG
    code = t["lang_switch"]["other_code"]
    label = t["lang_switch"]["to_other_label"]
    return (
        '<a class="lang-switch" '
        f'href="{href}" hreflang="{other_hreflang}" '
        f'aria-label="{html.escape(label)}">'
        f"{other_flag}"
        f'<span class="lang-switch__code">{html.escape(code)}</span>'
        "</a>"
    )


# ─── Deploy artefacts ──────────────────────────────────────────────
def render_robots(cfg: dict, *, absolute: bool) -> str:
    if absolute:
        origin = cfg["origin"].rstrip("/")
        return (
            "User-agent: *\n"
            "Allow: /\n\n"
            f"Sitemap: {origin}/sitemap.xml\n"
        )
    return "User-agent: *\nAllow: /\n"


def _content_lastmod() -> str:
    """ISO date of the newest content-source file. Drives sitemap <lastmod>.
    Prefers `git log` for CI/PR determinism (commit time stable across
    checkouts); falls back to filesystem mtime for unversioned trees."""
    sources = [
        ROOT / "index.html",
        ROOT / "data" / "locale.uk.toml",
        ROOT / "data" / "locale.en.toml",
        ROOT / "data" / "events.toml",
        ROOT / "data" / "contacts.toml",
    ]
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--"] + [str(p) for p in sources],
            cwd=ROOT, capture_output=True, text=True, timeout=5, check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    import datetime as _dt
    newest = max((p.stat().st_mtime for p in sources if p.exists()), default=0)
    return _dt.datetime.fromtimestamp(newest, tz=_dt.timezone.utc).date().isoformat()


def render_sitemap(cfg: dict, *, absolute: bool) -> str:
    origin = cfg["origin"].rstrip("/") if absolute else ""
    uk = f"{origin}/" if absolute else "/"
    en = f"{origin}/en/" if absolute else "/en/"
    lastmod = _content_lastmod()
    return textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
                xmlns:xhtml="http://www.w3.org/1999/xhtml">
          <url>
            <loc>{uk}</loc>
            <lastmod>{lastmod}</lastmod>
            <xhtml:link rel="alternate" hreflang="uk" href="{uk}"/>
            <xhtml:link rel="alternate" hreflang="en" href="{en}"/>
            <xhtml:link rel="alternate" hreflang="x-default" href="{uk}"/>
            <changefreq>weekly</changefreq>
            <priority>1.0</priority>
          </url>
          <url>
            <loc>{en}</loc>
            <lastmod>{lastmod}</lastmod>
            <xhtml:link rel="alternate" hreflang="uk" href="{uk}"/>
            <xhtml:link rel="alternate" hreflang="en" href="{en}"/>
            <xhtml:link rel="alternate" hreflang="x-default" href="{uk}"/>
            <changefreq>weekly</changefreq>
            <priority>0.9</priority>
          </url>
        </urlset>
        """)


def render_cf_headers(css_name: str, ld_hashes: dict, preloaded_fonts: list[str]) -> str:
    """Per-path CSP (different JSON-LD hash per locale) + Early Hints."""
    link_entries = [f'</{css_name}>; rel=preload; as=style']
    for f in preloaded_fonts:
        link_entries.append(f'</{f}>; rel=preload; as=font; type="font/woff2"; crossorigin')
    link_header = ", ".join(link_entries)

    uk_hash = ld_hashes.get("uk", "")
    en_hash = ld_hashes.get("en", "")

    # Common CSP body (hashes vary per path). frame-ancestors 'none' is
    # consistent with X-Frame-Options: DENY — civic site is never legitimately
    # embedded. upgrade-insecure-requests catches stale http:// references.
    def csp(hsh: str) -> str:
        return (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; "
            f"script-src 'self' 'sha256-{hsh}'; font-src 'self'; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; "
            "form-action 'self'; object-src 'none'; upgrade-insecure-requests"
        )

    # Permissions-Policy: deny everything not actively used. Each entry is
    # disabled by default in modern browsers; explicit denial removes
    # ambiguity for security scanners and silences FLoC opt-in attempts.
    perms_policy = ", ".join([
        "interest-cohort=()", "geolocation=()", "camera=()", "microphone=()",
        "accelerometer=()", "gyroscope=()", "magnetometer=()",
        "payment=()", "usb=()", "midi=()", "fullscreen=(self)",
        "autoplay=()", "browsing-topics=()", "screen-wake-lock=()",
    ])

    return textwrap.dedent(f"""\
        # Cloudflare Pages headers — generated by build.py
        # Per-path CSP hashes track per-locale JSON-LD content.
        # Early-Hints Link directives emit on the HTML path before the 200.

        /*
          X-Content-Type-Options: nosniff
          X-Frame-Options: DENY
          Referrer-Policy: strict-origin-when-cross-origin
          Permissions-Policy: {perms_policy}
          Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
          Cross-Origin-Opener-Policy: same-origin
          Cross-Origin-Resource-Policy: same-origin

        /
          Cache-Control: public, max-age=0, must-revalidate
          Content-Security-Policy: {csp(uk_hash)}
          Link: {link_header}

        /index.html
          Cache-Control: public, max-age=0, must-revalidate
          Content-Security-Policy: {csp(uk_hash)}
          Link: {link_header}

        /en/
          Cache-Control: public, max-age=0, must-revalidate
          Content-Security-Policy: {csp(en_hash)}
          Link: {link_header}

        /en/index.html
          Cache-Control: public, max-age=0, must-revalidate
          Content-Security-Policy: {csp(en_hash)}
          Link: {link_header}

        /*.css
          Cache-Control: public, max-age=31536000, immutable

        /*.js
          Cache-Control: public, max-age=31536000, immutable

        /fonts/*
          Cache-Control: public, max-age=31536000, immutable
          Access-Control-Allow-Origin: *

        /images/*
          Cache-Control: public, max-age=31536000, immutable

        /events.ics
          Content-Type: text/calendar; charset=utf-8
          Cache-Control: public, max-age=3600

        /en/events.ics
          Content-Type: text/calendar; charset=utf-8
          Cache-Control: public, max-age=3600
        """)


def render_cf_redirects(origin: str) -> str:
    host = origin.split("://", 1)[1]
    return textwrap.dedent(f"""\
        # Cloudflare Pages redirects — generated by build.py
        # Force apex (no www) to match canonical.
        https://www.{host}/*   https://{host}/:splat   301!
        """)


def render_404(cfg: dict, css_link: str) -> str:
    return textwrap.dedent(f"""\
        <!doctype html>
        <html lang="uk">
        <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>404 · {html.escape(cfg['title'])}</title>
        <meta name="robots" content="noindex, follow">
        <link rel="stylesheet" href="{css_link}">
        </head>
        <body class="is-404">
        <main class="e404">
          <div>
            <h1 class="e404__title"><span class="e404__num">404</span><em>Сторінки немає.</em></h1>
            <p class="e404__text">Такої адреси в Милорадовому не існує. <br>This page doesn't exist. Повертаймося на головну.</p>
            <a class="e404__link" href="/">На головну →</a>
          </div>
        </main>
        </body>
        </html>
        """)


# ─── Hreflang alternates ───────────────────────────────────────────
def render_hreflang(origin: str, current: str, *, absolute: bool) -> str:
    if not absolute:
        return ""
    origin = origin.rstrip("/")
    uk_url = f"{origin}/"
    en_url = f"{origin}/en/"
    return (
        f'<link rel="alternate" hreflang="uk" href="{uk_url}">\n'
        f'<link rel="alternate" hreflang="en" href="{en_url}">\n'
        f'<link rel="alternate" hreflang="x-default" href="{uk_url}">'
    )


# ─── Main build ────────────────────────────────────────────────────
def build(preview: bool = False) -> None:
    cfg = load_config()
    contacts = load_contacts()
    events = load_events()
    today = dt.date.today()
    upcoming, past = split_events(events, today)
    absolute = not preview

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()

    # Static assets — shared across locales.
    for sub in ("images", "fonts"):
        src_sub = ROOT / sub
        if src_sub.exists():
            shutil.copytree(src_sub, DIST / sub)
    stale = DIST / "images" / "manifest.json"
    if stale.exists():
        stale.unlink()

    # Fingerprint CSS + JS (once, shared).
    css_src = ROOT / "styles.css"
    js_src = ROOT / "script.js"
    if absolute:
        css_name = f"styles.{content_hash(css_src)}.css"
        js_name = f"script.{content_hash(js_src)}.js"
    else:
        css_name, js_name = "styles.css", "script.js"
    shutil.copy2(css_src, DIST / css_name)
    shutil.copy2(js_src, DIST / js_name)

    # Read template once.
    template = (ROOT / "index.html").read_text(encoding="utf-8")

    # Load default-locale fallback.
    uk_locale = load_locale("uk")

    ld_hashes: dict[str, str] = {}

    for loc in LOCALES:
        locale = load_locale(loc)

        # 1. JSON-LD
        ld_json = render_jsonld(cfg, contacts, upcoming, loc, locale, absolute=absolute)

        # 2. Dynamic blocks
        events_html = render_events_section(upcoming, past, locale, loc)
        contacts_html = render_contacts_block(contacts, cfg, locale, loc)
        ics_link = (
            f'<a href="events.ics" class="ics-link">{html.escape(locale["events"]["ics"])}</a>'
            if upcoming else ""
        )
        lang_switch_html = render_lang_switch(loc, locale)
        hreflang_html = render_hreflang(cfg["origin"], loc, absolute=absolute)

        # 3. Template pass: dotted {{t.*}} first, then structural placeholders.
        page = render_template(template, locale, uk_locale)
        page = page.replace("{{HREFLANG}}", hreflang_html)
        page = page.replace("{{JSONLD}}", ld_json)
        page = page.replace("{{LANG_SWITCH}}", lang_switch_html)
        page = page.replace("{{EVENTS}}", events_html)
        page = page.replace("{{CONTACTS}}", contacts_html)
        page = page.replace("{{ICS_LINK}}", ics_link)
        page = page.replace('href="styles.css"', f'href="{css_name}"')
        page = page.replace('src="script.js"', f'src="{js_name}"')

        # For locales served from a sub-path (e.g. /en/) we rewrite every
        # relative asset reference to root-relative. Anchor links (#foo)
        # and external URLs are left alone — intra-page navigation stays
        # inside /en/.
        if loc != DEFAULT_LOCALE:
            def rootify(m: re.Match) -> str:
                attr = m.group(1)      # src | href | srcset
                quote = m.group(2)
                value = m.group(3)
                # srcset is comma-separated "url Xw, url Xw"
                if attr == "srcset":
                    parts = []
                    for chunk in value.split(","):
                        chunk = chunk.strip()
                        if not chunk:
                            continue
                        toks = chunk.split(None, 1)
                        url = toks[0]
                        rest = f" {toks[1]}" if len(toks) > 1 else ""
                        if not url.startswith(("http", "data:", "#", "/", "mailto:")):
                            url = "/" + url
                        parts.append(url + rest)
                    new_val = ", ".join(parts)
                else:
                    if value.startswith(("http", "data:", "#", "/", "mailto:")):
                        return m.group(0)
                    new_val = "/" + value
                return f'{attr}={quote}{new_val}{quote}'
            page = re.sub(
                r'\b(src|href|srcset)=(["\'])([^"\']+)\2',
                rootify,
                page,
            )

        if absolute:
            origin = cfg["origin"].rstrip("/")
            path = "/" if loc == DEFAULT_LOCALE else f"/{loc}/"
            page = re.sub(
                r'<link rel="canonical" href="[^"]*">',
                f'<link rel="canonical" href="{origin}{path}">',
                page,
            )
            page = re.sub(
                r'(<meta property="og:image"\s+content=")([^"]+)(")',
                lambda m: f'{m.group(1)}{origin}/{m.group(2)}{m.group(3)}'
                if not m.group(2).startswith("http") else m.group(0),
                page,
            )
            if 'property="og:url"' not in page:
                page = page.replace(
                    '<meta property="og:type"',
                    f'<meta property="og:url" content="{origin}{path}">\n'
                    '<meta property="og:type"',
                )

        # Compute CSP hash from the JSON-LD that actually lives in the emitted HTML.
        ld_match = re.search(r'<script type="application/ld\+json">(.*?)</script>', page, re.S)
        if ld_match:
            ld_hashes[loc] = sha256_b64(ld_match.group(1))

        # Write page
        if loc == DEFAULT_LOCALE:
            (DIST / "index.html").write_text(page, encoding="utf-8")
            if upcoming:
                (DIST / "events.ics").write_text(render_ics(upcoming, cfg, loc), encoding="utf-8")
        else:
            loc_dir = DIST / loc
            loc_dir.mkdir()
            (loc_dir / "index.html").write_text(page, encoding="utf-8")
            if upcoming:
                (loc_dir / "events.ics").write_text(render_ics(upcoming, cfg, loc), encoding="utf-8")

    # Shared artefacts
    (DIST / "robots.txt").write_text(render_robots(cfg, absolute=absolute), encoding="utf-8")
    (DIST / "sitemap.xml").write_text(render_sitemap(cfg, absolute=absolute), encoding="utf-8")
    (DIST / "404.html").write_text(render_404(cfg, f"/{css_name}"), encoding="utf-8")

    # Preloaded fonts from the authored template (constant across locales).
    preloaded_fonts = re.findall(
        r'<link rel="preload"[^>]*as="font"[^>]*href="([^"]+)"',
        template,
    )

    (DIST / "_headers").write_text(
        render_cf_headers(css_name, ld_hashes, preloaded_fonts), encoding="utf-8"
    )
    (DIST / "_redirects").write_text(render_cf_redirects(cfg["origin"]), encoding="utf-8")

    # .htaccess fallback — sync primary-locale hash.
    ht_src = ROOT / ".htaccess"
    if ht_src.exists():
        ht = ht_src.read_text(encoding="utf-8")
        ht = re.sub(r"'sha256-[^']+'", f"'sha256-{ld_hashes.get('uk', '')}'", ht)
        (DIST / ".htaccess").write_text(ht, encoding="utf-8")

    print("── build summary ────────────────────────────────")
    print(f"  mode:              {'preview' if preview else 'production'}")
    print(f"  origin:            {cfg['origin']}")
    print(f"  locales:           {', '.join(LOCALES)}")
    print(f"  css:               {css_name}")
    print(f"  js:                {js_name}")
    print(f"  events upcoming:   {len(upcoming)}")
    print(f"  events past:       {len(past)}")
    print(f"  contacts:          {len(contacts)}")
    for loc, h in ld_hashes.items():
        print(f"  LD sha-256 [{loc}]:  {h[:24]}…")
    total = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file())
    count = sum(1 for _ in DIST.rglob("*") if _.is_file())
    print(f"  files:             {count}")
    print(f"  total size:        {total/1024/1024:.2f} MB")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    args = ap.parse_args()
    build(preview=args.preview)
    return 0


if __name__ == "__main__":
    sys.exit(main())
