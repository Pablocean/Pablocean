#!/usr/bin/env python3
"""Generate the animated Spring-Boot-style profile banner for the Pablocean repo.

Writes assets/banner-{dark,light}.svg. Stdlib + Pillow only.

The composition mirrors the reference terminal "live profile" UI (macOS window
chrome, a dithered 1-bit portrait in a left VISUAL frame, a SYSTEM.INFO panel
with dotted-leader rows, a pulsing LIVE badge and a status footer) but the
flavour is Pablo's own world: Spring Boot boot-log lines reveal inside the
SYSTEM panel.

Run from the repository root:
    python scripts/banner.py
"""

from __future__ import annotations

import html
import io
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/source/profile.png"
ASSETS = ROOT / "assets"

W, H = 1180, 610
PORT_W, PORT_H = 300, 340
PTS_CAP = 18000
SEED = 130620

# Portrait crop, in source-pixel space: (left, top, right, bottom).
# Source is 1024x1536 (portrait). Kept generous to capture head + shoulders.
CROP = (224, 84, 800, 1476)

THEMES = {
    "dark": {
        "bg": "#140E07",
        "panel": "#1B1209",
        "panel2": "#21160B",
        "line": "#3A2A16",
        "muted": "#BFA98E",
        "text": "#FDF6EC",
        "portrait": "#FF6B00",
        "chrome": "#FF9A3C",
        "accent": "#FF7A1A",
        "ok": "#7DB36E",
        "shadow": "#050301",
    },
    "light": {
        "bg": "#FDF6EC",
        "panel": "#FFFFFF",
        "panel2": "#FFF4E5",
        "line": "#E6D8C2",
        "muted": "#8A775F",
        "text": "#17100B",
        "portrait": "#E04E1A",
        "chrome": "#D2730F",
        "accent": "#E04E1A",
        "ok": "#2E7D32",
        "shadow": "#C9B89E",
    },
}

ROWS = [
    ("Subject", "Pablo"),
    ("Role", "Backend Engineer · Full Stack"),
    ("Origin", "Havana, Cuba"),
    ("Education", "B.Sc. CS @ UCI"),
    ("Status", "Building · Learning · Shipping"),
    ("ToolChain", "IntelliJ · VS Code · Git"),
    ("Core.Lang", "Java · TypeScript · Python"),
    ("Core.Backend", "Spring Boot · WebFlux · Node.js"),
    ("Core.Frontend", "React · React Native · Tailwind"),
    ("Core.Data", "MongoDB · Postgres · MySQL"),
    ("Core.Infra", "Docker · Git · GitHub Actions"),
    ("Grid.GitHub", "Pablocean"),
    ("Grid.LinkedIn", "/in/pablo-perera-marcoleta"),
]

BOOT_LINES = [
    ("INFO", "Starting PabloceanApplication v2.0 using Java 21"),
    ("INFO", "No active profile set, falling back to 1 default profile"),
    ("INFO", "Tomcat initialized on port 8080 (http)"),
    ("OK", "Started PabloceanApplication in 4.213s"),
]


def dither_points(theme: str) -> list[tuple[int, int]]:
    """Return lit-pixel coordinates from a 1-bit Floyd-Steinberg portrait."""
    source = Image.open(SOURCE).convert("RGBA")
    crop = source.crop(CROP).resize((PORT_W, PORT_H), Image.Resampling.LANCZOS)
    rgb = crop.convert("RGB")
    alpha = crop.getchannel("A")
    amask = alpha.point(lambda p: 255 if p > 20 else 0)

    if theme == "dark":
        lum = ImageOps.grayscale(rgb)
        lum = ImageChops.multiply(lum, alpha)  # fold alpha in
        lum = ImageOps.equalize(lum, mask=amask).convert("L")
        select_lit = True
    else:
        white = Image.new("RGBA", crop.size, "white")
        white.alpha_composite(crop)
        lum = ImageOps.grayscale(white.convert("RGB"))
        lum = ImageOps.autocontrast(lum, cutoff=1)
        select_lit = False

    lum = ImageEnhance.Contrast(lum).enhance(1.35)
    lum = lum.filter(ImageFilter.UnsharpMask(radius=2, percent=175, threshold=1))
    bits = lum.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
    px = bits.load()

    pts: list[tuple[int, int]] = []
    for y in range(PORT_H):
        for x in range(PORT_W):
            lit = px[x, y] == 255  # mode "1": 0 = black, 255 = white
            active = lit if select_lit else (not lit)
            if not active:
                continue
            if theme == "dark" and amask.getpixel((x, y)) == 0:
                continue
            pts.append((74 + x, 154 + y))
    if len(pts) > PTS_CAP:
        pts = random.Random(SEED).sample(pts, PTS_CAP)
    return pts


def num(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


def point_path(points: list[tuple[int, int]]) -> str:
    """Aggregate adjacent horizontal one-pixel dots into compact path runs."""
    if not points:
        return ""
    unique = sorted(set(points), key=lambda p: (p[1], p[0]))
    chunks: list[str] = []
    i = 0
    while i < len(unique):
        x0, y = unique[i]
        x1 = x0
        i += 1
        while i < len(unique) and unique[i][1] == y and unique[i][0] <= x1 + 1:
            x1 = unique[i][0]
            i += 1
        chunks.append(f"M{x0} {y}h{x1 - x0 + 1}")
    return "".join(chunks)


def dotted_leader(x1: float, x2: float, y: float) -> str:
    if x2 <= x1:
        return ""
    return "".join(f"M{x} {num(y)}h1" for x in range(int(x1), int(x2), 5))


def text_width(s: str, font_size: float) -> float:
    return len(s) * font_size * 0.605


def render_svg(theme: str, pts: list[tuple[int, int]], rng: random.Random) -> str:
    t = THEMES[theme]
    rand = rng.random

    # --- split portrait into 48 interleaved opacity bands for the intro -----
    band_count = 48
    band_of = [rng.randrange(band_count) for _ in pts]
    starts = sorted(rng.random() * 0.9 + 0.0 for _ in range(band_count))

    parts: list[str] = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
        'aria-labelledby="title desc">',
        "<title id=\"title\">Pablo's live system profile</title>",
        '<desc id="desc">Spring Boot terminal profile with a dithered portrait '
        "and a boot-log reveal.</desc>",
        "<defs>",
        '<filter id="shadow" x="-20%" y="-20%" width="140%" height="150%">'
        f'<feDropShadow dx="0" dy="12" stdDeviation="16" flood-color="{t["shadow"]}" '
        'flood-opacity=".30"/></filter>',
        '<filter id="glow" x="-100%" y="-100%" width="300%" height="300%">'
        f'<feGaussianBlur stdDeviation="2.5" result="b"/><feFlood flood-color="{t["chrome"]}" '
        'flood-opacity=".30"/><feComposite in2="b" operator="in"/>'
        '<feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge></filter>',
        '<clipPath id="visualClip"><rect x="49" y="124" width="390" height="414" rx="3"/></clipPath>',
        "</defs>",
        f'<rect width="{W}" height="{H}" rx="18" fill="{t["bg"]}"/>',
        f'<rect x="13" y="13" width="1154" height="584" rx="13" fill="{t["panel"]}" '
        f'stroke="{t["line"]}" filter="url(#shadow)"/>',
        f'<path d="M13 62H1167" stroke="{t["line"]}"/>',
        '<circle cx="38" cy="38" r="6" fill="#FF5F57"/>'
        '<circle cx="59" cy="38" r="6" fill="#FEBC2E"/>'
        '<circle cx="80" cy="38" r="6" fill="#28C840"/>',
        f'<text x="590" y="43" text-anchor="middle" fill="{t["muted"]}" '
        'font-family="ui-monospace,SFMono-Regular,Consolas,monospace" font-size="13" '
        'letter-spacing=".4">pablocean.sh --live</text>',
        # Left visual frame.
        f'<rect x="35" y="88" width="418" height="472" rx="6" fill="{t["panel2"]}" '
        f'stroke="{t["line"]}"/>',
        f'<path d="M35 124H453" stroke="{t["line"]}"/>',
        f'<text x="49" y="111" fill="{t["chrome"]}" '
        'font-family="ui-monospace,SFMono-Regular,Consolas,monospace" font-size="13" '
        'font-weight="700" letter-spacing="1.2">PROFILE.MAP</text>',
        f'<text x="438" y="111" text-anchor="end" fill="{t["muted"]}" '
        'font-family="ui-monospace,SFMono-Regular,Consolas,monospace" font-size="11">'
        f'{PORT_W}×{PORT_H} / 1-BIT</text>',
        f'<path d="M49 141h12M49 141v12M439 141h-12M439 141v12M49 539h12M49 539v-12'
        f'M439 539h-12M439 539v-12" fill="none" stroke="{t["chrome"]}" opacity=".55"/>',
        '<g clip-path="url(#visualClip)" shape-rendering="crispEdges">',
        '<g opacity="1">',
    ]

    # Portrait dots, revealed in staggered bands then held.
    for b in range(band_count):
        band = [p for p, bj in zip(pts, band_of) if bj == b]
        if not band:
            continue
        d = point_path(band)
        parts.append(
            f'<path d="{d}" fill="none" stroke="{t["portrait"]}" stroke-width="1" '
            f'opacity="0"><animate attributeName="opacity" begin="{num(starts[b])}s" '
            'dur=".55s" values="0;1" fill="freeze"/></path>'
        )
    parts.extend(
        [
            "</g>",
            "</g>",
            f'<text x="58" y="551" fill="{t["muted"]}" '
            'font-family="ui-monospace,SFMono-Regular,Consolas,monospace" font-size="10">'
            f'PTS {len(pts):05d} · FS/SERPENTINE</text>',
            # Right information panel.
            f'<rect x="474" y="88" width="672" height="472" rx="6" fill="{t["panel2"]}" '
            f'stroke="{t["line"]}"/>',
            f'<path d="M474 124H1146" stroke="{t["line"]}"/>',
            f'<text x="490" y="111" fill="{t["chrome"]}" '
            'font-family="ui-monospace,SFMono-Regular,Consolas,monospace" font-size="13" '
            'font-weight="700" letter-spacing="1.2">SYSTEM.INFO</text>',
            '<g filter="url(#glow)"><circle cx="915" cy="106" r="4" fill="#FF4D5A">'
            '<animate attributeName="opacity" values="1;.3;1" dur="1.6s" repeatCount="indefinite"/>'
            '</circle></g>',
            '<text x="927" y="111" fill="#FF4D5A" '
            'font-family="ui-monospace,SFMono-Regular,Consolas,monospace" font-size="12" '
            'font-weight="700">LIVE</text>',
            f'<rect x="982" y="94" width="146" height="24" rx="12" fill="{t["chrome"]}" opacity=".16" '
            f'stroke="{t["chrome"]}"/>',
            f'<text x="1055" y="111" text-anchor="middle" fill="{t["chrome"]}" '
            'font-family="ui-monospace,SFMono-Regular,Consolas,monospace" font-size="14" '
            'font-weight="700">@Pablocean</text>',
        ]
    )

    # ---- Spring Boot art + boot-log reveal ---------------------------------
    sb = (
        '\u0020 .   ____          _            __ _ _\n'
        ' /\\\\ / ___\'_ __ _ _(_)_ __  __ _ \\ \\ \\ \\\n'
        "( ( )\\___ | '_ | '_| | '_ \\/ _` | \\ \\ \\ \\\n"
        ' \\\\/  ___)| |_)| | | | | || (_| |  ) ) ) )\n'
        "  '  |____| .__|_| |_|_| |_\\__, | / / / /\n"
        ' =========|_|==============|___/=/_/_/_/'
    )
    art_lines = sb.splitlines()
    art_y = 138.0
    for i, line in enumerate(art_lines):
        parts.append(
            f'<text x="491" y="{num(art_y)}" fill="{t["chrome"]}" opacity=".75" '
            'font-family="ui-monospace,SFMono-Regular,Consolas,monospace" '
            f'font-size="9" letter-spacing=".6">{html.escape(line)}</text>'
        )
        art_y += 10.5
    parts.append(
        f'<text x="491" y="{num(art_y + 3)}" fill="{t["chrome"]}" '
        'font-family="ui-monospace,SFMono-Regular,Consolas,monospace" font-size="10" '
        'font-weight="700">:: Spring Boot :: (v3.4.1)</text>'
    )
    boot_top = art_y + 13
    for i, (sev, msg) in enumerate(BOOT_LINES):
        color = t["ok"] if sev == "OK" else t["text"]
        begin = "" if i == 0 else f' begin="{num(.6 + .55 * i)}s" fill="freeze"'
        anim = ""
        if i > 0:
            anim = (
                '<animate attributeName="opacity" '
                f'from="0" to="1" begin="{num(.6 + .55 * i)}s" dur=".35s" fill="freeze"/>'
            )
        parts.append(
            f'<text x="491" y="{num(boot_top + i * 14)}" fill="{color}" opacity="1" '
            'font-family="ui-monospace,SFMono-Regular,Consolas,monospace" font-size="10.5">'
            f'<tspan fill="{t["muted"]}">[{"INFO" if sev == "OK" else sev}]</tspan> '
            f'{html.escape(msg)}{anim}</text>'
        )
    # blinking cursor after the boot block
    cur_y = boot_top + (len(BOOT_LINES) - 1) * 14
    parts.append(
        f'<text x="491" y="{num(cur_y + 2)}" fill="{t["chrome"]}" '
        'font-family="ui-monospace,SFMono-Regular,Consolas,monospace" font-size="10.5">'
        '<animate id="cursorBlink" attributeName="opacity" values="1;0;1" '
        'dur="1.1s" repeatCount="indefinite"/>_</text>'
    )

    # ---- info rows ----------------------------------------------------------
    value_right = 1127.0
    row_y = 300.0
    for label, value in ROWS:
        value_len = text_width(value, 13)
        label_len = text_width(label, 13)
        leader_start = 491 + label_len + 12
        leader_end = value_right - value_len - 12
        parts.extend(
            [
                f'<text x="491" y="{num(row_y)}" fill="{t["muted"]}" '
                'font-family="ui-monospace,SFMono-Regular,Consolas,monospace" font-size="13">'
                f"{html.escape(label)}</text>",
                f'<path d="{dotted_leader(leader_start, leader_end, row_y - 4)}" '
                f'fill="none" stroke="{t["line"]}" stroke-width="1" shape-rendering="crispEdges"/>',
                f'<text x="{num(value_right)}" y="{num(row_y)}" text-anchor="end" '
                f'fill="{t["text"]}" font-family="ui-monospace,SFMono-Regular,Consolas,monospace" '
                f'font-size="13" textLength="{num(value_len)}" lengthAdjust="spacingAndGlyphs">'
                f"{html.escape(value)}</text>",
            ]
        )
        row_y += 15

    parts.extend(
        [
            f'<path d="M490 526H1130" stroke="{t["line"]}"/>',
            f'<text x="491" y="545" fill="{t["accent"]}" '
            'font-family="ui-monospace,SFMono-Regular,Consolas,monospace" font-size="11">'
            "● ALL SYSTEMS NOMINAL</text>",
            f'<text x="1128" y="545" text-anchor="end" fill="{t["muted"]}" '
            'font-family="ui-monospace,SFMono-Regular,Consolas,monospace" font-size="11">'
            "HEX-TZ · HAVANA CST</text>",
            "</svg>",
        ]
    )
    return "".join(parts)


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Missing source portrait: {SOURCE}")
    ASSETS.mkdir(parents=True, exist_ok=True)
    for theme in ("dark", "light"):
        pts = dither_points(theme)
        svg = render_svg(theme, pts, random.Random(SEED))
        dest = ASSETS / f"banner-{theme}.svg"
        dest.write_text(svg, encoding="utf-8")
        kb = dest.stat().st_size / 1024
        print(f"{dest.name}: {kb:.1f} KiB, {len(pts):,} portrait dots")


if __name__ == "__main__":
    main()