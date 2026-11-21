#!/usr/bin/env python3
"""VELMORA — a travel poster for a place that isn't there.

Writes a single 1024x1024 travel poster to /output/entry.png.

The poster is drawn entirely procedurally with the Python standard library
only: no network, no external assets, no fonts from disk. The place name is
rendered from an embedded block-letter font, so the program runs identically
in any sandbox.

The place: VELMORA, a floating island above a sea of clouds at sunset, with
a white lighthouse tower, waterfalls pouring off its edges, and smaller
islets drifting nearby.
"""

import math
import os
import struct
import zlib

W = 1024
H = 1024
OUT = "/output/entry.png"

# ---------------------------------------------------------------- canvas
# img is a list of rows; each row is a bytearray of W*3 RGB bytes.
img = [bytearray(W * 3) for _ in range(H)]


def clamp(v, lo=0, hi=255):
    return lo if v < lo else hi if v > hi else v


def blend_px(x, y, r, g, b, a):
    """Blend colour (r,g,b) over pixel (x,y) with opacity a in [0,1]."""
    if a <= 0.0 or x < 0 or x >= W or y < 0 or y >= H:
        return
    row = img[y]
    i = x * 3
    if a >= 1.0:
        row[i] = r
        row[i + 1] = g
        row[i + 2] = b
    else:
        ia = 1.0 - a
        row[i] = clamp(int(row[i] * ia + r * a))
        row[i + 1] = clamp(int(row[i + 1] * ia + g * a))
        row[i + 2] = clamp(int(row[i + 2] * ia + b * a))


def fill_rect(x0, y0, x1, y1, color, alpha=1.0):
    r, g, b = color
    for y in range(max(0, y0), min(H, y1)):
        for x in range(max(0, x0), min(W, x1)):
            blend_px(x, y, r, g, b, alpha)


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(c1, c2, t):
    return (int(lerp(c1[0], c2[0], t)),
            int(lerp(c1[1], c2[1], t)),
            int(lerp(c1[2], c2[2], t)))


def vgrad(y0, y1, stops):
    """Vertical gradient between y0..y1; stops = [(pos0..1, (r,g,b)), ...]."""
    for y in range(max(0, y0), min(H, y1)):
        t = (y - y0) / max(1, (y1 - y0))
        for i in range(len(stops) - 1):
            p0, c0 = stops[i]
            p1, c1 = stops[i + 1]
            if p0 <= t <= p1:
                tt = 0.0 if p1 == p0 else (t - p0) / (p1 - p0)
                c = lerp_color(c0, c1, tt)
                break
        else:
            c = stops[-1][1]
        row = img[y]
        for x in range(W):
            i = x * 3
            row[i] = c[0]
            row[i + 1] = c[1]
            row[i + 2] = c[2]


def disc(cx, cy, rad, color, alpha=1.0):
    r, g, b = color
    x0, x1 = int(cx - rad), int(cx + rad) + 1
    y0, y1 = int(cy - rad), int(cy + rad) + 1
    for y in range(max(0, y0), min(H, y1)):
        dy = (y - cy) / rad
        for x in range(max(0, x0), min(W, x1)):
            dx = (x - cx) / rad
            if dx * dx + dy * dy <= 1.0:
                blend_px(x, y, r, g, b, alpha)


def radial_glow(cx, cy, rad, color, peak=0.55):
    """Soft radial glow fading to transparent at rad."""
    r, g, b = color
    x0, x1 = int(cx - rad), int(cx + rad) + 1
    y0, y1 = int(cy - rad), int(cy + rad) + 1
    for y in range(max(0, y0), min(H, y1)):
        dy = (y - cy) / rad
        for x in range(max(0, x0), min(W, x1)):
            dx = (x - cx) / rad
            d = math.sqrt(dx * dx + dy * dy)
            if d < 1.0:
                a = peak * (1.0 - d) * (1.0 - d)
                blend_px(x, y, r, g, b, a)


def soft_ellipse(cx, cy, rx, ry, color, alpha=1.0, feather=0.22):
    """Filled ellipse with a feathered edge."""
    r, g, b = color
    x0, x1 = int(cx - rx), int(cx + rx) + 1
    y0, y1 = int(cy - ry), int(cy + ry) + 1
    for y in range(max(0, y0), min(H, y1)):
        dy = (y - cy) / ry
        for x in range(max(0, x0), min(W, x1)):
            dx = (x - cx) / rx
            d = dx * dx + dy * dy
            if d < 1.0:
                edge = (1.0 - d) / feather
                a = alpha * (1.0 if edge > 1.0 else edge)
                blend_px(x, y, r, g, b, a)


def polygon(points, color, alpha=1.0):
    """Scanline-filled polygon."""
    r, g, b = color
    ys = [p[1] for p in points]
    y0, y1 = max(0, int(min(ys))), min(H, int(max(ys)) + 1)
    n = len(points)
    for y in range(y0, y1):
        xs = []
        for i in range(n):
            x1, y1p = points[i]
            x2, y2p = points[(i + 1) % n]
            if (y1p <= y < y2p) or (y2p <= y < y1p):
                t = (y - y1p) / (y2p - y1p)
                xs.append(x1 + t * (x2 - x1))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            for x in range(max(0, int(xs[i])), min(W, int(xs[i + 1]) + 1)):
                blend_px(x, y, r, g, b, alpha)


def thick_line(x0, y0, x1, y1, width, color, alpha=1.0):
    """A thick straight line drawn as a chain of discs."""
    length = max(1, int(math.hypot(x1 - x0, y1 - y0)))
    for i in range(length + 1):
        t = i / length
        disc(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, width / 2.0, color, alpha)


# ------------------------------------------------------------------ font
# Embedded 5x7 block capitals (only the letters VELMORA is built from).
GLYPHS = {
    "V": ("#...#",
          "#...#",
          "#...#",
          "#...#",
          ".#.#.",
          ".#.#.",
          "..#.."),
    "E": ("#####",
          "#....",
          "#....",
          "####.",
          "#....",
          "#....",
          "#####"),
    "L": ("#....",
          "#....",
          "#....",
          "#....",
          "#....",
          "#....",
          "#####"),
    "M": ("#...#",
          "##.##",
          "#.#.#",
          "#.#.#",
          "#...#",
          "#...#",
          "#...#"),
    "O": (".###.",
          "#...#",
          "#...#",
          "#...#",
          "#...#",
          "#...#",
          ".###."),
    "R": ("####.",
          "#...#",
          "#...#",
          "####.",
          "#.#..",
          "#..#.",
          "#...#"),
    "A": ("..#..",
          ".#.#.",
          "#...#",
          "#...#",
          "#####",
          "#...#",
          "#...#"),
}


def draw_text(text, cx, y, scale, color, shadow=None):
    """Draw centred block text; scale = pixels per glyph cell."""
    gw, gh = 5 * scale, 7 * scale
    gap = int(scale * 1.25)
    total = len(text) * gw + (len(text) - 1) * gap
    x = cx - total // 2
    for ch in text:
        glyph = GLYPHS[ch]
        for gy, row in enumerate(glyph):
            for gx, cell in enumerate(row):
                if cell == "#":
                    px, py = x + gx * scale, y + gy * scale
                    if shadow is not None:
                        fill_rect(px + 5, py + 6, px + scale + 5, py + scale + 6,
                                  shadow, 0.45)
                    fill_rect(px, py, px + scale, py + scale, color)
        x += gw + gap


def diamond(cx, cy, s, color, alpha=1.0):
    polygon([(cx, cy - s), (cx + s, cy), (cx, cy + s), (cx - s, cy)],
            color, alpha)


# ------------------------------------------------------------------ scene
def draw():
    # --- sky: indigo dusk down to a golden horizon
    vgrad(0, 660, [
        (0.00, (24, 30, 74)),
        (0.30, (62, 52, 110)),
        (0.55, (146, 74, 128)),
        (0.78, (214, 105, 104)),
        (1.00, (247, 171, 92)),
    ])

    # --- stars, faint, high in the dusk
    stars = [(90, 60), (170, 120), (260, 55), (700, 70), (790, 130),
             (880, 60), (940, 170), (40, 200), (350, 90), (620, 150)]
    for sx, sy in stars:
        disc(sx, sy, 2, (255, 240, 210), 0.7)
        disc(sx, sy, 1, (255, 255, 255), 0.9)

    # --- low sun and its glow, just above the cloud sea, clear of the island
    radial_glow(848, 545, 330, (255, 190, 110), 0.55)
    radial_glow(848, 545, 190, (255, 220, 150), 0.6)
    disc(848, 545, 84, (255, 222, 150), 1.0)
    disc(848, 545, 68, (255, 236, 180), 1.0)

    # --- distant islets, small and hazy, left and right
    for (ix, iy, s, tone) in [(150, 600, 0.45, (122, 84, 120)),
                              (880, 615, 0.38, (122, 84, 120)),
                              (300, 630, 0.30, (140, 96, 128))]:
        w = 190 * s
        polygon([(ix - w, iy), (ix - w * 0.7, iy - 26 * s),
                 (ix - w * 0.2, iy - 34 * s), (ix + w * 0.3, iy - 30 * s),
                 (ix + w * 0.8, iy - 18 * s), (ix + w, iy),
                 (ix + w * 0.45, iy + 52 * s), (ix, iy + 74 * s),
                 (ix - w * 0.45, iy + 52 * s)], tone, 0.9)
        # a tiny tower on the distant islet
        tx = ix - w * 0.15
        fill_rect(int(tx - 5 * s), int(iy - 58 * s), int(tx + 5 * s),
                  int(iy - 34 * s), (245, 234, 214), 0.95)
        polygon([(tx - 7 * s, iy - 58 * s), (tx + 7 * s, iy - 58 * s),
                 (tx, iy - 68 * s)], (198, 92, 74), 0.95)

    # --- cloud sea: base wash, then billows
    vgrad(620, H, [(0.0, (250, 226, 196)),
                   (0.5, (232, 196, 196)),
                   (1.0, (176, 138, 168))])
    clouds = [
        (120, 700, 190, 42, (255, 244, 224), 0.95),
        (300, 730, 230, 50, (248, 228, 210), 0.95),
        (520, 690, 210, 46, (255, 240, 220), 0.95),
        (740, 730, 240, 52, (244, 222, 208), 0.95),
        (920, 700, 180, 44, (255, 242, 224), 0.95),
        (60, 830, 220, 55, (238, 208, 200), 0.95),
        (280, 870, 260, 60, (226, 190, 196), 0.9),
        (560, 850, 250, 58, (240, 210, 200), 0.95),
        (830, 880, 260, 62, (222, 184, 196), 0.9),
        (960, 950, 200, 55, (210, 172, 190), 0.9),
        (180, 960, 240, 55, (214, 176, 192), 0.9),
        (500, 970, 260, 55, (206, 166, 188), 0.9),
        (700, 985, 200, 45, (200, 160, 184), 0.9),
        (420, 790, 150, 34, (252, 236, 218), 0.9),
        (660, 800, 150, 34, (252, 236, 218), 0.9),
        (150, 990, 220, 50, (226, 196, 200), 0.9),
        (860, 995, 230, 52, (228, 196, 200), 0.9),
        (430, 1010, 210, 45, (214, 178, 194), 0.9),
        (848, 700, 190, 42, (255, 214, 160), 0.45),
    ]
    for cx, cy, rx, ry, col, a in clouds:
        soft_ellipse(cx, cy, rx, ry, col, a, feather=0.30)

    # --- the floating island of Velmora
    # rock body: wide plateau tapering to a point below
    polygon([(252, 540), (296, 480), (380, 462), (512, 454),
             (644, 462), (728, 480), (772, 540), (716, 632),
             (620, 724), (512, 786), (404, 724), (308, 632)],
            (96, 58, 74), 1.0)
    # sunlit upper rock
    polygon([(252, 540), (296, 480), (380, 462), (512, 454),
             (644, 462), (728, 480), (772, 540), (700, 580),
             (512, 596), (324, 580)], (150, 92, 96), 1.0)
    # shadowed underside
    polygon([(340, 600), (512, 596), (684, 600), (620, 724),
             (512, 786), (404, 724)], (66, 38, 54), 0.85)
    # grassy plateau top
    polygon([(288, 484), (380, 462), (512, 454), (644, 462),
             (736, 484), (700, 500), (512, 508), (324, 500)],
            (196, 158, 74), 1.0)
    polygon([(340, 478), (512, 468), (684, 478), (660, 490),
             (512, 496), (364, 490)], (122, 138, 62), 1.0)

    # --- lighthouse tower on the plateau
    fill_rect(484, 336, 540, 470, (246, 236, 214))
    fill_rect(484, 336, 498, 470, (214, 196, 178), 0.7)   # shaded side
    fill_rect(484, 396, 540, 404, (198, 92, 74))           # terracotta band
    fill_rect(484, 436, 540, 444, (198, 92, 74))
    polygon([(478, 336), (546, 336), (528, 306), (496, 306)],
            (198, 92, 74), 1.0)                            # roof
    fill_rect(500, 288, 524, 308, (255, 226, 150))         # lamp room
    radial_glow(512, 298, 60, (255, 220, 140), 0.5)
    disc(512, 298, 9, (255, 238, 170), 1.0)
    # lamp beams
    polygon([(512, 298), (760, 250), (760, 268), (512, 306)],
            (255, 228, 150), 0.22)
    polygon([(512, 298), (264, 252), (264, 270), (512, 306)],
            (255, 228, 150), 0.18)
    # warm windows
    for wy in (352, 416):
        fill_rect(506, wy, 518, wy + 16, (255, 214, 130))

    # --- cypress trees flanking the tower
    for tx in (392, 636):
        fill_rect(tx + 5, 398, tx + 9, 428, (58, 70, 44))
        polygon([(tx, 402), (tx + 14, 402), (tx + 7, 332)],
                (46, 78, 48), 1.0)
    # small houses at the plateau edges
    for hx in (330, 668):
        fill_rect(hx - 18, 448, hx + 18, 478, (240, 224, 196))
        polygon([(hx - 22, 448), (hx + 22, 448), (hx, 428)],
                (188, 88, 70), 1.0)

    # --- waterfalls pouring off the island into the clouds
    for fx, fw in [(300, 16), (330, 9), (700, 14), (726, 8)]:
        fill_rect(fx, 505, fx + fw, 780, (214, 232, 240), 0.75)
        fill_rect(fx + 2, 505, fx + 5, 780, (240, 248, 252), 0.8)
    for mx, my, mr in [(308, 800, 46), (718, 800, 42), (330, 815, 30)]:
        soft_ellipse(mx, my, mr, mr // 2, (240, 244, 248), 0.55, 0.35)

    # --- foreground clouds lapping the island's point
    soft_ellipse(430, 830, 200, 48, (250, 234, 214), 0.95, 0.30)
    soft_ellipse(620, 845, 210, 50, (246, 228, 212), 0.95, 0.30)
    soft_ellipse(512, 880, 260, 55, (238, 216, 206), 0.9, 0.30)

    # --- birds
    for bx, by, s in [(330, 250, 14), (372, 228, 10), (700, 290, 12),
                      (742, 262, 9), (250, 330, 9)]:
        thick_line(bx - s, by, bx, by - s // 2, 3, (40, 32, 56), 0.9)
        thick_line(bx, by - s // 2, bx + s, by, 3, (40, 32, 56), 0.9)

    # --- title: VELMORA, set large into the dusk sky
    fill_rect(150, 46, 874, 49, (248, 236, 212), 0.85)
    draw_text("VELMORA", 512, 66, 18, (248, 236, 212),
              shadow=(30, 22, 54))
    fill_rect(150, 212, 874, 215, (248, 236, 212), 0.85)
    diamond(512, 236, 9, (248, 236, 212), 0.9)
    diamond(150, 47, 6, (248, 236, 212), 0.9)
    diamond(874, 47, 6, (248, 236, 212), 0.9)


# -------------------------------------------------------------------- png
def write_png(path):
    raw = bytearray()
    for y in range(H):
        raw.append(0)  # filter: none
        raw += img[y]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(ctype, data):
        c = struct.pack(">I", len(data)) + ctype + data
        c += struct.pack(">I", zlib.crc32(ctype + data) & 0xFFFFFFFF)
        return c

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n"
    data += chunk(b"IHDR", ihdr)
    data += chunk(b"IDAT", comp)
    data += chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return len(data)


def main():
    draw()
    size = write_png(OUT)
    print(f"wrote {OUT}: {W}x{H}, {size} bytes")


if __name__ == "__main__":
    main()
