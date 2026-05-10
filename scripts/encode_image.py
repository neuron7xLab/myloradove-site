#!/usr/bin/env python3
"""
encode_image.py · Милорадове

Codifies MAINTENANCE.md §7. Takes one source photo (HEIC/JPG/PNG) and
emits the canonical 6-variant set into site/images/:

    {slug}-640.{avif,webp}
    {slug}-1280.{avif,webp}
    {slug}-1920.{avif,webp}

Quality ladder is calibrated to the audit.py image budgets:
    640w  ≤ 300 KB
    1280w ≤ 800 KB
    1920w ≤ 1500 KB

Idempotent: running twice produces byte-identical output (PIL is
deterministic for our settings, AVIF/WebP encoders are stable).

Usage:
    python3 scripts/encode_image.py ../_sources/photos/IMG_4886.HEIC img_4886
    python3 scripts/encode_image.py ../_sources/photos/IMG_4886.HEIC \
            --slug img_4886 --check-budgets

Dependencies (install once):
    pip install pillow pillow-avif-plugin pillow-heif
"""

from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
IMAGES = ROOT / "images"

VARIANTS = [
    # (width, avif_quality, webp_quality)
    (640, 60, 82),
    (1280, 60, 82),
    (1920, 50, 75),  # tighter for the lightbox tier; matches audit budget
]

BUDGETS_KB = {640: 300, 1280: 800, 1920: 1500}


def encode(source: pathlib.Path, slug: str, *, check_budgets: bool) -> int:
    try:
        from PIL import Image, ImageOps
        import pillow_avif  # noqa: F401  (registers AVIF encoder)
    except ImportError:
        print("[FAIL] missing deps. Run: pip install pillow pillow-avif-plugin pillow-heif")
        return 2

    if source.suffix.lower() in {".heic", ".heif"}:
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            print("[FAIL] HEIC source needs: pip install pillow-heif")
            return 2

    if not source.exists():
        print(f"[FAIL] source not found: {source}")
        return 2

    IMAGES.mkdir(exist_ok=True)
    img = ImageOps.exif_transpose(Image.open(source))
    if img.mode != "RGB":
        img = img.convert("RGB")
    src_w, src_h = img.size

    overruns = []
    for width, q_avif, q_webp in VARIANTS:
        if width > src_w:
            print(f"  [skip] {width}w  (source is only {src_w}w)")
            continue
        h = round(src_h * width / src_w)
        resized = img.resize((width, h), Image.LANCZOS)
        avif_path = IMAGES / f"{slug}-{width}.avif"
        webp_path = IMAGES / f"{slug}-{width}.webp"
        resized.save(avif_path, "AVIF", quality=q_avif, speed=4)
        resized.save(webp_path, "WEBP", quality=q_webp, method=6)
        a_kb, w_kb = avif_path.stat().st_size / 1024, webp_path.stat().st_size / 1024
        budget = BUDGETS_KB[width]
        flag = "  " if max(a_kb, w_kb) <= budget else "!!"
        print(f"{flag} {width:>4}w  avif={a_kb:6.0f}KB  webp={w_kb:6.0f}KB  budget={budget}KB")
        if max(a_kb, w_kb) > budget:
            overruns.append((width, max(a_kb, w_kb)))

    if check_budgets and overruns:
        print(f"\n[FAIL] {len(overruns)} variant(s) exceed budget. Lower quality or pick a softer source.")
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", type=pathlib.Path, help="path to HEIC/JPG/PNG source")
    ap.add_argument("slug", nargs="?", help="output stem; defaults to source filename lowered, no ext")
    ap.add_argument("--check-budgets", action="store_true",
                    help="exit non-zero if any variant exceeds the audit.py image budgets")
    args = ap.parse_args()

    slug = args.slug or args.source.stem.lower().replace(" ", "_")
    return encode(args.source, slug, check_budgets=args.check_budgets)


if __name__ == "__main__":
    sys.exit(main())
