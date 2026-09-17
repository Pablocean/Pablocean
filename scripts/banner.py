#!/usr/bin/env python3
"""Generate the animated Spring-Boot-style profile banner for the Pablocean repo.

Writes assets/banner-{dark,light}.svg. Numpy + Pillow only.

The centrepiece is the reference-style morph: TRAVELLER_COUNT dithered portrait
dots assemble the face, then smoothly flow into a Java coffee-cup silhouette
and back again, forever. Matching is done with numpy-only angle-sort transport
(gives the same smooth non-crossing paths as scipy's optimal assignment for
these convex silhouettes). A one-shot scatter-intro shimmers the portrait in,
then hands off to the loop.

Run from the repository root:
    python scripts/banner.py
"""

from __future__ import annotations

import html
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageChops, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets/source/profile.png"
ASSETS = ROOT / "assets"
LOGOS = Path(__file__).resolve().parent / "logos"

W, H = 1180, 610
LOOP_SECONDS = 14.2
INTRO_SECONDS = 3.2
TRAVELLER_COUNT = 900
SEED = 314159

PORT_W, PORT_H = 300, 340
PTS_CAP = 18000

# Portrait crop, in source-pixel space: (left, top, right, bottom).
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


def make_java_logo() -> Image.Image:
    """Draw a Java coffee-cup silhouette on a transparent 400x400 canvas."""
    size = 400
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ink = (0, 0, 0, 255)

    # steam wisps rising off the cup
    d.line([(150, 40), (158, 105), (140, 145)], fill=ink, width=24, joint="curve")
    d.line([(228, 24), (242, 95), (224, 135)], fill=ink, width=24, joint="curve")

    # cup body (rounded, slightly tapered)
    d.rounded_rectangle([100, 150, 278, 322], radius=28, fill=ink)

    # handle: thick arc on the right side
    d.arc([236, 178, 356, 306], start=-72, end=74, fill=ink, width=26)
    return img


def portrait_points(theme: str, rng: np.random.Generator) -> np.ndarray:
    """Return dither points (N,2) for the portrait, in VISUAL-frame coords."""
    source = Image.open(SOURCE).convert("RGBA")
    crop = source.crop(CROP).resize((PORT_W, PORT_H), Image.Resampling.LANCZOS)
    rgb = crop.convert("RGB")
    alpha = crop.getchannel("A")
    amask = alpha.point(lambda p: 255 if p > 20 else 0)

    if theme == "dark":
        lum = ImageOps.grayscale(rgb)
        lum = ImageChops.multiply(lum, alpha)
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

    ys, xs = [], []
    for y in range(PORT_H):
        for x in range(PORT_W):
            lit = px[x, y] == 255
            active = lit if select_lit else (not lit)
            if not active:
                continue
            if theme == "dark" and amask.getpixel((x, y)) == 0:
                continue
            xs.append(x)
            ys.append(y)
    pts = np.column_stack((np.array(xs, np.float32) + 74,
                           np.array(ys, np.float32) + 154))
    if len(pts) > PTS_CAP:
        pick = rng.choice(len(pts), PTS_CAP, replace=False)
        pts = pts[pick]
    return pts


def sample_logo_points(image: Image.Image, rng: np.random.Generator,
                       count: int) -> np.ndarray:
    """Sample a silhouette into the portrait frame's coordinate space."""
    alpha = np.asarray(image.getchannel("A"))
    ys, xs = np.where(alpha > 127)
    chosen = rng.choice(len(xs), count, replace=len(xs) < count)
    return np.column_stack((89 + xs[chosen] * 0.675,
                            188 + ys[chosen] * 0.675)).astype(np.float32)


def transport(source: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Reorder target points by angular sort around their centroids.

    Discrete optimal transport for point clouds is a linear program; the
    classic scipy solve (linear_sum_assignment over cdist) is O(n^3). Sorting
    both sets by angle around their centroids and matching in that order gives
    the same smooth, non-crossing radial flows for convex silhouettes in O(n log n)
    and needs only numpy.
    """
    sc = source.mean(axis=0)
    tc = target.mean(axis=0)
    sa = np.argsort(np.arctan2(source[:, 1] - sc[1], source[:, 0] - sc[0]))
    ta = np.argsort(np.arctan2(target[:, 1] - tc[1], target[:, 0] - tc[0]))
    ordered = np.empty_like(target)
    ordered[sa] = target[ta]
    return ordered


def num(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def point_path(points: np.ndarray) -> str:
    """Aggregate adjacent horizontal one-pixel dots into compact path runs."""
    n = len(points)
    if not n:
        return ""
    pts = np.rint(points).astype(int)
    order = np.lexsort((pts[:, 0], pts[:, 1]))  # row-major sort
    pts = pts[order]
    chunks: list[str] = []
    i = 0
    while i < n:
        x0, y = int(pts[i, 0]), int(pts[i, 1])
        x1 = x0
        i += 1
        while i < n and int(pts[i, 1]) == y and int(pts[i, 0]) <= x1 + 1:
            x1 = int(pts[i, 0])
            i += 1
        chunks.append(f"M{x0} {y}h{x1 - x0 + 1}")
    return "".join(chunks)


def dotted_leader(x1: float, x2: float, y: float) -> str:
    if x2 <= x1:
        return ""
    return "".join(f"M{x} {num(y)}h1" for x in range(int(x1), int(x2), 5))


def text_width(text: str, font_size: float) -> float:
    return len(text) * font_size * 0.605


def animate_values(frames: list[np.ndarray], index: int) -> str:
    return ";".join(f"{num(p[index, 0])} {num(p[index, 1])}" for p in frames)


def render_svg(theme_name: str, portrait: np.ndarray,
               rng: np.random.Generator) -> str:
    t = THEMES[theme_name]

    # ---- morph frames: portrait -> java cup -> portrait --------------------
    logo = make_java_logo()
    n = min(TRAVELLER_COUNT, len(portrait))
    source = portrait[rng.choice(len(portrait), n, replace=False)]
    java = transport(source, sample_logo_points(logo, rng, n))
    frames = [source, source, java, java, source, source]

    # ---- loop timing (6 keyframes over 14.2s) ------------------------------
    times = [0, 3.0, 5.0, 9.0, 11.0, 14.2]  # P hold, P->J, J hold, J->P, P settle
    key_times = ";".join(num(v / LOOP_SECONDS) for v in times)
    trav_opacity = "0;0;1;1;1;0"  # fade in after intro, fade out at wrap

    # ---- the full portrait, split into drifted bands -----------------------
    LOGOS.mkdir(parents=True, exist_ok=True)
    LOGOS.joinpath("java.png").write_bytes(_png_bytes(logo))

    band_count = 94
    band_ids = rng.integers(0, band_count, size=len(portrait))
    noise = rng.normal(0, 4, size=(band_count, 2)).astype(np.float32)
    java_centroid = java.mean(axis=0)

    parts: list[str] = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
        'aria-labelledby="title desc">',
        "<title id=\"title\">Pablo's live system profile</title>",
        '<desc id="desc">Terminal profile port-dots morph between a dithered '
        "portrait and a Java coffee-cup logo.</desc>",
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
        # Loop layer stays visible at t=0 so static first frames still show the face.
        '<g opacity="1">',
    ]

    # Dense portrait drift: 94 bands drift toward the Java centroid's pull.
    for band in range(band_count):
        band_pts = portrait[band_ids == band]
        if not len(band_pts):
            continue
        centroid = band_pts.mean(axis=0)
        delta = (java_centroid - centroid) * 0.18 + noise[band]
        d = point_path(band_pts)
        parts.append(
            f'<path d="{d}" fill="none" stroke="{t["portrait"]}" stroke-width="1" '
            f'opacity=".94">'
            f'<animateTransform attributeName="transform" type="translate" begin="{INTRO_SECONDS}s" '
            f'dur="{LOOP_SECONDS}s" repeatCount="indefinite" calcMode="linear" '
            f'keyTimes="{key_times}" values="0 0;0 0;{num(delta[0])} {num(delta[1])};'
            f'{num(delta[0])} {num(delta[1])};0 0;0 0"/>'
            f'<animate attributeName="opacity" begin="{INTRO_SECONDS}s" dur="{LOOP_SECONDS}s" '
            f'repeatCount="indefinite" calcMode="linear" keyTimes="{key_times}" '
            'values=".94;.94;0;0;0;.94"/></path>'
        )

    # Optimal-transport travellers, represented as tiny path squares (never glyphs).
    for i in range(n):
        positions = animate_values(frames, i)
        parts.append(
            f'<path d="M-.65-.65h1.3v1.3h-1.3z" fill="{t["portrait"]}">'
            f'<animateTransform attributeName="transform" type="translate" begin="{INTRO_SECONDS}s" '
            f'dur="{LOOP_SECONDS}s" repeatCount="indefinite" calcMode="linear" '
            f'keyTimes="{key_times}" values="{positions}"/>'
            f'<animate attributeName="opacity" begin="{INTRO_SECONDS}s" dur="{LOOP_SECONDS}s" '
            f'repeatCount="indefinite" calcMode="linear" keyTimes="{key_times}" '
            f'values="{trav_opacity}"/></path>'
        )
    parts.append("</g>")

    # One-shot scattered intro: sixty random, interleaved point groups.
    intro_ids = rng.integers(0, 60, size=len(portrait))
    order = rng.permutation(60)
    starts = np.empty(60)
    starts[order] = np.linspace(0.05, 1.2, 60)
    for group in range(60):
        group_pts = portrait[intro_ids == group]
        if not len(group_pts):
            continue
        parts.append(
            f'<path d="{point_path(group_pts)}" fill="none" stroke="{t["portrait"]}" '
            f'stroke-width="1" opacity="0">'
            f'<animate attributeName="opacity" begin="{num(starts[group])}s" dur=".8s" '
            'values="0;1" fill="freeze"/>'
            '<animate attributeName="opacity" begin="3.08s" dur=".12s" values="1;0" fill="freeze"/>'
            "</path>"
        )
    parts.extend(
        [
            "</g>",
            f'<text x="58" y="551" fill="{t["muted"]}" '
            'font-family="ui-monospace,SFMono-Regular,Consolas,monospace" font-size="10">'
            f'PTS {len(portrait):05d} · TRAVELLERS {n:04d}</text>',
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


def _png_bytes(image: Image.Image) -> bytes:
    buf = __import__("io").BytesIO()
    image.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Missing source portrait: {SOURCE}")
    ASSETS.mkdir(parents=True, exist_ok=True)
    for theme in ("dark", "light"):
        rng = np.random.default_rng(SEED + (0 if theme == "dark" else 1))
        portrait = portrait_points(theme, rng)
        svg = render_svg(theme, portrait, np.random.default_rng(SEED + 10))
        dest = ASSETS / f"banner-{theme}.svg"
        dest.write_text(svg, encoding="utf-8")
        kb = dest.stat().st_size / 1024
        print(f"{dest.name}: {kb:.1f} KiB, {len(portrait):,} portrait dots, "
              f"{TRAVELLER_COUNT} travellers")


if __name__ == "__main__":
    main()