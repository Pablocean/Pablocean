#!/usr/bin/env python3
"""
cards.py - render self-hosted highlight + language-bar cards as SVGs. Stdlib only.

Like the reference's cards.py, these replace github-readme-stats / trophy
services that go down; but the data is deliberately hand-authored and honest
(Pablo's real work is in private repos, so live public stats would undersell
or misrepresent him). Files are self-hosted in this repo.

    python scripts/cards.py \
        --highlights assets/highlights.json --langbars assets/langbars.json \
        --out assets

Writes assets/card-highlights-{dark,light}.svg and assets/card-langs-{dark,light}.svg
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

THEMES = {
    "dark": {
        "bg": "#16100B", "border": "#3A2A16", "title": "#FF9A3C",
        "text": "#FDF6EC", "muted": "#BFA98E", "value": "#FDF6EC",
        "bar": "#FF6B00", "track": "#2A1E0F",
    },
    "light": {
        "bg": "#FFF8EF", "border": "#E6D8C2", "title": "#D2730F",
        "text": "#17100B", "muted": "#8A775F", "value": "#17100B",
        "bar": "#E04E1A", "track": "#F0E2CC",
    },
}

FONT = "ui-sans-serif,-apple-system,Segoe UI,Helvetica,Arial,sans-serif"


def esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def text_width(s, size):
    return len(s) * size * 0.53


def frame(w, h, c, body, label):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="{w}" height="{h}" role="img" aria-label="{esc(label)}" '
        f'font-family="{FONT}">'
        f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="10" '
        f'fill="{c["bg"]}" stroke="{c["border"]}"/>'
        f"{body}</svg>"
    )


def render_highlights(user, subtitle, tiles, theme):
    c = THEMES[theme]
    pad, cols = 22, 2
    rows = (len(tiles) + cols - 1) // cols
    rh, W = 64, 480
    H = pad + 52 + (rows - 1) * rh + 40 + pad
    tw = (W - 2 * pad) / cols

    out = [
        f'<text x="{pad}" y="{pad + 14}" font-size="15" font-weight="700" '
        f'fill="{c["title"]}">{esc(user)}</text>',
        f'<text x="{W - pad}" y="{pad + 14}" font-size="11" text-anchor="end" '
        f'fill="{c["muted"]}">{esc(subtitle)}</text>',
        f'<line x1="{pad}" y1="{pad + 26}" x2="{W - pad}" y2="{pad + 26}" '
        f'stroke="{c["border"]}"/>',
    ]
    top = pad + 52
    for i, tile in enumerate(tiles):
        cx = pad + (i % cols) * tw
        cy = top + (i // cols) * rh
        out.append(
            f'<text x="{cx:.0f}" y="{cy:.0f}" font-size="23" font-weight="700" '
            f'fill="{c["value"]}">{esc(tile["value"])}</text>'
        )
        out.append(
            f'<text x="{cx:.0f}" y="{cy + 17:.0f}" font-size="10.5" '
            f'fill="{c["muted"]}" textLength="{text_width(tile["label"], 10.5) + 2:.0f}" '
            f'lengthAdjust="spacingAndGlyphs">{esc(tile["label"])}</text>'
        )
    return frame(W, H, c, "".join(out), f"{user} highlights")


def render_langbars(title, subtitle, bars, theme):
    c = THEMES[theme]
    W, H = 480, 24 * len(bars) + 72
    pad = 22
    bar_x, bar_w = pad + 120, W - (pad + 120) - 58

    out = [
        f'<text x="{pad}" y="{pad + 14}" font-size="15" font-weight="700" '
        f'fill="{c["title"]}">{esc(title)}</text>',
        f'<text x="{W - pad}" y="{pad + 14}" font-size="11" text-anchor="end" '
        f'fill="{c["muted"]}">{esc(subtitle)}</text>',
        f'<line x1="{pad}" y1="{pad + 26}" x2="{W - pad}" y2="{pad + 26}" '
        f'stroke="{c["border"]}"/>',
    ]
    top = pad + 48
    for i, b in enumerate(bars):
        cy = top + i * 24
        val = max(0, min(100, float(b["value"])))
        bw = bar_w * val / 100
        color = b.get("color", c["bar"])
        out.append(
            f'<text x="{pad}" y="{cy + 8:.0f}" font-size="11" fill="{c["muted"]}">'
            f'{esc(b["label"])}</text>'
        )
        out.append(
            f'<rect x="{bar_x:.0f}" y="{cy:.0f}" width="{bar_w:.0f}" height="11" rx="5.5" '
            f'fill="{c["track"]}"/>'
        )
        out.append(
            f'<rect x="{bar_x:.0f}" y="{cy:.0f}" width="{bw:.0f}" height="11" rx="5.5" '
            f'fill="{color}"/>'
        )
        out.append(
            f'<text x="{bar_x + bar_w + 12:.0f}" y="{cy + 8:.0f}" font-size="10.5" '
            f'fill="{c["value"]}" text-anchor="end">{val:g}</text>'
        )
    return frame(W, H, c, "".join(out), title)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--highlights", type=Path, default=Path("assets/highlights.json"))
    p.add_argument("--langbars", type=Path, default=Path("assets/langbars.json"))
    p.add_argument("--out", type=Path, default=Path("assets"))
    args = p.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    if args.highlights.exists():
        h = json.loads(args.highlights.read_text(encoding="utf-8"))
        for theme in ("dark", "light"):
            dest = args.out / f"card-highlights-{theme}.svg"
            dest.write_text(
                render_highlights(h.get("title", "at a glance"),
                                  h.get("subtitle", "at a glance"),
                                  h.get("tiles", []), theme),
                encoding="utf-8")
            print(f"wrote {dest}  ({len(h.get('tiles', []))} tiles)")

    if args.langbars.exists():
        lb = json.loads(args.langbars.read_text(encoding="utf-8"))
        for theme in ("dark", "light"):
            dest = args.out / f"card-langs-{theme}.svg"
            dest.write_text(
                render_langbars(lb.get("title", "Languages"),
                                lb.get("subtitle", ""),
                                lb.get("bars", []), theme),
                encoding="utf-8")
            print(f"wrote {dest}  ({len(lb.get('bars', []))} bars)")


if __name__ == "__main__":
    main()