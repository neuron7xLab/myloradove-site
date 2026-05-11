# ADR 0003 — Bawah-DNA visual adaptation, Milorado-signature meander

Status: ACCEPTED
Date  : 2026-05-10

## Context

The civic site needed a visual register that reads as "considered" — not
cottage-industry, not municipal-generic, not Bootstrap-default. A
luxury-hospitality reference (bawahreserve.com) was studied for
typography, palette, pacing, and rhythm: uppercase nav, generous
spacing, fine 1 px gold hairlines, editorial drop caps, slow scroll-
driven reveals, photo-as-page.

## Decision

Adopt the Bawah/Aman editorial pattern at the level of tokens and
rhythm (gold #d4af37 accent canon, Playfair italic display, Inter
humanist body, uppercase nav at 0.10 em tracking, 80–128 px chapter
padding-block). Do NOT clone individual ornaments.

Invent ONE Milorado-specific signature element: the Kovzhyzha-meander
divider. A three-half-cycle sinusoid in inline SVG, 96 × 14 px,
1 px gold-deep stroke + a 1.6 px gold disc on the central wave-node.
Used as the inter-chapter rule between every adjacent chapter. The
shape evokes the bend of the river the village sits on — not a stock
geometric line.

## Consequences

+ The site reads in the same visual family as the high-end editorial
  reference, so it inherits "considered" without copying.
+ The meander divider is a thumbprint — anyone scrolling past sees a
  Kovzhyzha bend three times before they reach the footer.
+ Implementation cost is zero: one inline data-URI SVG, no extra HTTP.
- The Bawah/Aman colour canon is widely used in luxury hospitality;
  Milorado-uniqueness rests on (a) the meander signature and (b) the
  content itself, not on novel CSS tokens.
- If the meander wears thin over time, replace the SVG path; the
  rule selector `.chapter + .chapter::before` is the single point of
  contact.
