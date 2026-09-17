#!/usr/bin/env python3
"""
radar.py - render a spider / radar chart as a standalone SVG. Stdlib only.

    python scripts/radar.py --data assets/skills.json -o assets/radar-skills
    python scripts/radar.py --data assets/langs.json  -o assets/radar-langs --values

Writes <out>-dark.svg and <out>-light.svg so the README can swap them with
<picture> + prefers-color-scheme.

Data shape (see assets/*.json):
    { "title": "Skill Radar",
      "axes": [ {"label": "...", "value": 88}, ... ] }   // value 0-100
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

THEMES = {
    "dark": {
        "grid": "#3A2A16",
        "spoke": "#241610",
        "label": "#FDF6EC",
        "value": "#BFA98E",
        "title": "#FF9A3C",
        "fill": "#FF6B00",
        "stroke": "#FF9A3C",
        "vertex": "#FFB36B",
        "bg": "none",
    },
    "light": {
        "grid": "#E6D8C2",
        "spoke": "#F0E5D2",
        "label": "#17100B",
        "value": "#8A775F",
        "title": "#D2730F",
        "fill": "#E04E1A",
        "stroke": "#D2730F",
        "vertex": "#8A3B12",
        "bg": "none",
    },
}

FONT = "ui-sans-serif,-apple-system,Segoe UI,Helvetica,Arial,sans-serif"
LBL, VAL, TTL = 13, 11, 15


def from_json(path: Path):
    d = json.loads(path.read_text(encoding="utf-8"))
    axes = [(a["label"], float(a["value"])) for a in d["axes"]]
    return d.get("title", "Radar"), axes


def ring(radius, n, start=-math.pi / 2):
    return [
        (radius * math.cos(start + i * 2 * math.pi / n),
         radius * math.sin(start + i * 2 * math.pi / n))
        for i in range(n)
    ]


def text_width(s, font_size):
    return len(s) * font_size * 0.62


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(title, axes, theme: str, size: int, rings: int, show_values=True,
           animate=True) -> str:
    c = THEMES[theme]
    n = len(axes)
    r = size / 2 - 8
    gap = 20
    vals = [max(0.0, min(100.0, v)) for _, v in axes]
    outer = ring(r, n)

    labels = []
    for i, (label, _) in enumerate(axes):
        ang = -math.pi / 2 + i * 2 * math.pi / n
        cosv, sinv = math.cos(ang), math.sin(ang)
        lx, ly = (r + gap) * cosv, (r + gap) * sinv
        anchor = "middle" if abs(cosv) < 0.25 else ("start" if cosv > 0 else "end")
        dy = 4 if abs(sinv) < 0.25 else (14 if sinv > 0 else -5)
        labels.append((lx, ly + dy, anchor, label, vals[i]))

    minx, maxx, miny, maxy = -r, r, -r, r
    for lx, ly, anchor, label, v in labels:
        w = max(text_width(label, LBL), text_width(f"{v:g}", VAL))
        x0, x1 = (lx, lx + w) if anchor == "start" else (
            (lx - w, lx) if anchor == "end" else (lx - w / 2, lx + w / 2))
        y0, y1 = ly - LBL, ly + 4 + VAL + 4
        minx, maxx, miny, maxy = min(minx, x0), max(maxx, x1), min(miny, y0), max(maxy, y1)

    pad = 10
    title_h = TTL + 14 if title else 0
    W = round((maxx - minx) + 2 * pad)
    H = round((maxy - miny) + 2 * pad + title_h)
    ox, oy = -minx + pad, -miny + pad + title_h
    if title:
        need = round(text_width(title, TTL) + 2 * pad)
        if need > W:
            ox += (need - W) / 2
            W = need

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" role="img" '
        f'aria-label="{esc(title) or "radar chart"}" font-family="{FONT}">'
    ]
    if c["bg"] != "none":
        parts.append(f'<rect width="100%" height="100%" fill="{c["bg"]}"/>')
    if title:
        parts.append(
            f'<text x="{W / 2:.1f}" y="{pad + TTL:.0f}" text-anchor="middle" '
            f'font-size="{TTL}" font-weight="700" fill="{c["title"]}">'
            f'{esc(title)}</text>'
        )
    parts.append(f'<g transform="translate({ox:.1f},{oy:.1f})">')

    for k in range(rings, 0, -1):
        d = " ".join(f"{x:.1f},{y:.1f}" for x, y in ring(r * k / rings, n))
        parts.append(
            f'<polygon points="{d}" fill="none" stroke="{c["grid"]}" '
            f'stroke-width="1" opacity="{0.35 + 0.5 * k / rings:.2f}"/>'
        )
    for x, y in outer:
        parts.append(
            f'<line x1="0" y1="0" x2="{x:.1f}" y2="{y:.1f}" '
            f'stroke="{c["spoke"]}" stroke-width="1"/>'
        )

    shape = [(px * v / 100, py * v / 100) for (px, py), v in zip(outer, vals)]
    d = " ".join(f"{x:.1f},{y:.1f}" for x, y in shape)
    parts.append("<g>")
    if animate:
        parts.append(
            '<animateTransform attributeName="transform" type="scale" '
            'values="0.04;1" dur="1.1s" calcMode="spline" keyTimes="0;1" '
            'keySplines="0.22 1 0.36 1" fill="freeze"/>'
        )
    parts.append(
        f'<polygon points="{d}" fill="{c["fill"]}" fill-opacity="0.22" '
        f'stroke="{c["stroke"]}" stroke-width="2.5" stroke-linejoin="round"/>'
    )
    for x, y in shape:
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.6" fill="{c["vertex"]}" '
            f'stroke="{c["stroke"]}" stroke-width="1.2"/>'
        )
    parts.append("</g>")

    for lx, ly, anchor, label, v in labels:
        parts.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" '
            f'font-size="{LBL}" font-weight="600" fill="{c["label"]}">'
            f'{esc(label)}</text>'
        )
        if show_values:
            parts.append(
                f'<text x="{lx:.1f}" y="{ly + VAL + 4:.1f}" text-anchor="{anchor}" '
                f'font-size="{VAL}" fill="{c["value"]}">{v:g}</text>'
            )
    parts.append("</g></svg>")
    return "".join(parts)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("-o", "--out", type=Path, required=True,
                   help="output path WITHOUT extension")
    p.add_argument("--title", help="override the chart title ('' for none)")
    p.add_argument("--size", type=int, default=440)
    p.add_argument("--rings", type=int, default=4)
    p.add_argument("--values", dest="values", action="store_true", default=True,
                   help="print the number per axis")
    p.add_argument("--no-animate", dest="animate", action="store_false", default=True)
    args = p.parse_args(argv)

    if not args.data.exists():
        sys.exit(f"no data file: {args.data}")
    title, axes = from_json(args.data)
    if args.title is not None:
        title = args.title
    if len(axes) < 3:
        sys.exit("a radar chart needs at least 3 axes")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    for theme in ("dark", "light"):
        svg = render(title, axes, theme, args.size, args.rings,
                     args.values, args.animate)
        dest = args.out.with_name(f"{args.out.name}-{theme}.svg")
        dest.write_text(svg, encoding="utf-8")
        print(f"wrote {dest}  ({len(axes)} axes)")


if __name__ == "__main__":
    main()