#!/usr/bin/env python3
"""Maple Morning -- the best-looking food picture (v3, post-open revision).

A deterministic generative program for the make.fun bounty
"Make the best-looking food picture" (food-picture-01).

What it draws
------------
One original 1024x1024 picture, entirely procedural with the Python
standard library only: a tall stack of five golden pancakes on a white
ceramic plate, maple syrup poured over the top and dripping down the
sides, a pat of melting butter, fresh blueberries, raspberries,
strawberries, banana slices and mint, a dusting of powdered sugar --
on a warm wooden table in soft morning light, with a framed picture
on the wall, a cup of coffee with latte art, a folded napkin and a
fork beside it. Warm colour, glossy syrup, visible texture: the
picture is built to make a viewer hungry at one look, and to still
read as one delicious dish at ~300 pixels across.

Revision notes (v3)
-------------------
- Pancake tops now carry a golden-brown crust ring and a warmer
  highlight, and each pancake in the stack gets its own shade, so
  the layers read separately instead of blending into one block.
- The syrup has extra drips with glossy highlight streaks, a
  shimmering pool on the plate, and a thicker pour over the top.
- The butter pat is bigger, with a wider melt pool and a glossy
  streak, so it reads as melting rather than sitting on top.
- New garnish: raspberries, banana slices on the plate, extra mint
  sprigs, and powdered sugar dusted over the plate rim as well as
  the top pancake.
- The coffee now has latte-art swirls; the wall has a small framed
  picture and a diagonal sunbeam; the table gains wood-grain knots.
- A soft vignette darkens the corners so the eye stays on the stack.

Revision notes (v4)
-------------------
- A glass of fresh orange juice joins the scene at the lower right:
  a clear trapezoid glass, orange juice with pulp, a red-and-white
  striped straw leaning out, a light glint on the glass and a soft
  shadow on the table.
- Pancake crumbs and a dusting of cinnamon now sit on the plate next
  to the stack, so the dish looks freshly served rather than staged.
- The straw leans a little further out and the juice carries extra
  pulp, so the glass reads as freshly squeezed at a glance.

There is no network access, no randomness that is not seeded, and no
external asset: the same run always writes the same bytes, so the two
sandbox runs required by the bounty produce identical files.

Output
------
Writes ``entry.png`` into ``$MAKEFUN_OUTPUT_DIR`` (the sandbox's /output),
or into ``/output`` when the variable is not set. The PNG is encoded by
hand with zlib (colour type 2, 8-bit RGB, per-row filter choice), so the
program needs nothing beyond the standard library.

Run locally:
    mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import hashlib
import math
import os
import random
import struct
import sys
import zlib

# ---------------------------------------------------------------- canvas ---
W = 1024
H = 1024
SEED = 20261113  # fixed seed: every run draws the same picture

canvas = bytearray(W * H * 3)
rng = random.Random(SEED)

# --------------------------------------------------------------- palette ---
BG_TOP = (58, 40, 30)
BG_LOW = (96, 64, 44)
TABLE = (122, 82, 48)
TABLE_DARK = (98, 64, 36)
TABLE_LIGHT = (146, 100, 60)
PLATE = (248, 246, 240)
PLATE_SHADE = (214, 210, 200)
PAN_TOP = (222, 164, 74)
PAN_TOP_LIGHT = (240, 190, 110)
PAN_SIDE = (188, 128, 52)
PAN_SIDE_DARK = (160, 104, 40)
CRUST = (172, 112, 38)          # golden-brown crust ring on pancake tops
SYRUP = (176, 108, 18)
SYRUP_LIGHT = (232, 172, 62)
SYRUP_DARK = (140, 82, 10)
BUTTER = (250, 220, 90)
BUTTER_LIGHT = (255, 238, 160)
BERRY_BLUE = (58, 58, 122)
BERRY_BLUE_LIGHT = (96, 96, 170)
RASP = (196, 38, 78)
RASP_LIGHT = (232, 90, 120)
STRAW = (222, 62, 62)
STRAW_DARK = (180, 40, 40)
BANANA = (246, 226, 160)
BANANA_DARK = (214, 182, 110)
MINT = (52, 140, 74)
NAPKIN = (168, 180, 196)
WHITE = (250, 250, 246)
COFFEE = (62, 36, 20)
JUICE = (240, 140, 30)
JUICE_LIGHT = (255, 182, 84)
JUICE_DARK = (208, 108, 16)
STRAW_RED = (214, 48, 48)


# ------------------------------------------------------------ primitives ---
def hline(x0, x1, y, color):
    """Fill a horizontal span of pixels (clipped)."""
    if y < 0 or y >= H:
        return
    x0 = max(0, int(x0))
    x1 = min(W - 1, int(x1))
    if x1 < x0:
        return
    n = x1 - x0 + 1
    i = (y * W + x0) * 3
    canvas[i:i + n * 3] = bytes(color) * n


def rect(x, y, w, h, color):
    """Fill an axis-aligned rectangle (floats allowed)."""
    y0 = max(0, int(math.floor(y)))
    y1 = min(H - 1, int(math.ceil(y + h)) - 1)
    for yy in range(y0, y1 + 1):
        hline(x, x + w - 1, yy, color)


def blend_px(x, y, color, alpha):
    """Alpha-blend one pixel over the canvas."""
    if 0 <= x < W and 0 <= y < H and alpha > 0:
        i = (y * W + x) * 3
        a = alpha
        canvas[i] = int(color[0] * a + canvas[i] * (1 - a) + 0.5)
        canvas[i + 1] = int(color[1] * a + canvas[i + 1] * (1 - a) + 0.5)
        canvas[i + 2] = int(color[2] * a + canvas[i + 2] * (1 - a) + 0.5)


def fill_poly(pts, color):
    """Scanline-fill a polygon given as [(x, y), ...]."""
    ys = [p[1] for p in pts]
    y0 = max(0, int(math.floor(min(ys))))
    y1 = min(H - 1, int(math.ceil(max(ys))))
    n = len(pts)
    for y in range(y0, y1 + 1):
        yc = y + 0.5
        xs = []
        for i in range(n):
            x0, ya = pts[i]
            x1, yb = pts[(i + 1) % n]
            if ya == yb:
                continue
            lo, hi = (ya, yb) if ya < yb else (yb, ya)
            if lo <= yc < hi:
                t = (yc - ya) / (yb - ya)
                xs.append(x0 + t * (x1 - x0))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            xa = int(math.ceil(xs[k] - 0.5))
            xb = int(math.floor(xs[k + 1] - 0.5))
            hline(xa, xb, y, color)


def fill_circle(cx, cy, r, color):
    """Fill a disc (float centre/radius allowed)."""
    r = float(r)
    y0 = max(0, int(math.floor(cy - r)))
    y1 = min(H - 1, int(math.ceil(cy + r)))
    for y in range(y0, y1 + 1):
        dy = (y + 0.5) - cy
        d2 = r * r - dy * dy
        if d2 < 0:
            continue
        dx = math.sqrt(d2)
        hline(cx - dx, cx + dx, y, color)


def fill_ellipse(cx, cy, rx, ry, color):
    """Fill an axis-aligned ellipse."""
    rx = float(rx)
    ry = float(ry)
    y0 = max(0, int(math.floor(cy - ry)))
    y1 = min(H - 1, int(math.ceil(cy + ry)))
    for y in range(y0, y1 + 1):
        dy = (y + 0.5 - cy) / ry
        d2 = 1.0 - dy * dy
        if d2 < 0:
            continue
        dx = rx * math.sqrt(d2)
        hline(cx - dx, cx + dx, y, color)


def fill_circle_alpha(cx, cy, r, color, alpha):
    """Fill a disc with a constant alpha over the canvas."""
    r = float(r)
    y0 = max(0, int(math.floor(cy - r)))
    y1 = min(H - 1, int(math.ceil(cy + r)))
    for y in range(y0, y1 + 1):
        dy = (y + 0.5) - cy
        d2 = r * r - dy * dy
        if d2 < 0:
            continue
        dx = math.sqrt(d2)
        for x in range(max(0, int(cx - dx)), min(W - 1, int(cx + dx)) + 1):
            blend_px(x, y, color, alpha)


def fill_ellipse_alpha(cx, cy, rx, ry, color, alpha):
    """Fill an axis-aligned ellipse with a constant alpha."""
    rx = float(rx)
    ry = float(ry)
    y0 = max(0, int(math.floor(cy - ry)))
    y1 = min(H - 1, int(math.ceil(cy + ry)))
    for y in range(y0, y1 + 1):
        dy = (y + 0.5 - cy) / ry
        d2 = 1.0 - dy * dy
        if d2 < 0:
            continue
        dx = rx * math.sqrt(d2)
        for x in range(max(0, int(cx - dx)), min(W - 1, int(cx + dx)) + 1):
            blend_px(x, y, color, alpha)


def soft_disc(cx, cy, r, color, strength):
    """Radial glow: colour fading smoothly to nothing at radius r."""
    r = float(r)
    x0 = max(0, int(cx - r))
    x1 = min(W - 1, int(cx + r))
    y0 = max(0, int(cy - r))
    y1 = min(H - 1, int(cy + r))
    for y in range(y0, y1 + 1):
        dy = (y + 0.5 - cy) / r
        for x in range(x0, x1 + 1):
            dx = (x + 0.5 - cx) / r
            d2 = dx * dx + dy * dy
            if d2 < 1.0:
                a = strength * (1.0 - d2) * (1.0 - d2)
                blend_px(x, y, color, a)


def line(x0, y0, x1, y1, w, color, alpha=1.0):
    """Draw a thick line by stamping discs along it."""
    dist = math.hypot(x1 - x0, y1 - y0)
    steps = max(1, int(dist / max(1.0, w * 0.35)))
    for i in range(steps + 1):
        t = i / steps
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        if alpha >= 1.0:
            fill_circle(x, y, w / 2.0, color)
        else:
            fill_circle_alpha(x, y, w / 2.0, color, alpha)


def arc(cx, cy, r, a0, a1, w, color, alpha=1.0):
    """Draw an arc (angles in radians, 0 = east, positive clockwise
    because y grows downwards) by stamping discs along it."""
    steps = max(8, int(abs(a1 - a0) * r / 4))
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / steps
        x = cx + r * math.cos(a)
        y = cy + r * math.sin(a)
        if alpha >= 1.0:
            fill_circle(x, y, w / 2.0, color)
        else:
            fill_circle_alpha(x, y, w / 2.0, color, alpha)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t + 0.5) for i in range(3))


def vgrad(x, y, w, h, top, bottom):
    """Vertical gradient rectangle."""
    for yy in range(int(y), int(y + h)):
        t = (yy - y) / max(1, h - 1)
        rect(x, yy, w, 1, lerp(top, bottom, t))


def vignette(strength=0.16):
    """Darken the corners a little so the eye stays on the stack.

    Cheap version: only the corner bands are visited, row by row,
    with an alpha that grows towards each corner.
    """
    cx, cy = W / 2.0, H / 2.0
    for y in range(H):
        dy = abs(y + 0.5 - cy) / cy
        if dy < 0.62:
            continue
        edge = int((dy - 0.62) / 0.38 * 200)  # band width grows downwards
        a = strength * ((dy - 0.62) / 0.38) ** 2
        for x in range(0, edge):
            blend_px(x, y, (20, 10, 6), a * (1 - x / max(1, edge)))
            blend_px(W - 1 - x, y, (20, 10, 6), a * (1 - x / max(1, edge)))


# ------------------------------------------------------------- the scene ---
def draw_background():
    vgrad(0, 0, W, 620, BG_TOP, BG_LOW)
    soft_disc(300, 170, 430, (255, 220, 170), 0.32)  # morning window light
    # diagonal sunbeam across the wall
    line(120, 0, 620, 560, 130, (255, 214, 150), 0.10)
    line(240, 0, 740, 560, 90, (255, 214, 150), 0.08)
    # small framed picture on the wall, upper left
    rect(96, 96, 150, 118, (52, 34, 22))
    rect(104, 104, 134, 102, (238, 222, 196))
    fill_circle(171, 142, 26, (240, 190, 110))  # sun in the picture
    fill_poly([(110, 200), (150, 150), (190, 200)], (110, 150, 90))
    fill_poly([(150, 200), (200, 138), (232, 200)], (84, 122, 70))
    # wooden table
    vgrad(0, 560, W, H - 560, TABLE, TABLE_DARK)
    for py in (640, 760, 880, 1000):
        hline(0, W - 1, py, TABLE_DARK)
        hline(0, W - 1, py + 2, TABLE_LIGHT)
    for sx in (180, 520, 860):
        line(sx, 560, sx + 24, H, 3, TABLE_DARK, 0.5)
    # wood-grain knots on the table
    for kx, ky, kr in ((700, 900, 26), (150, 960, 20), (900, 700, 18)):
        arc(kx, ky, kr, 0, 2 * math.pi, 3, TABLE_DARK, 0.6)
        arc(kx, ky, kr * 0.55, 0, 2 * math.pi, 2, TABLE_DARK, 0.5)


def draw_coffee():
    """A cup of coffee, upper right, with latte art and steam."""
    fill_ellipse(800, 302, 92, 22, PLATE)
    fill_ellipse(800, 298, 78, 18, PLATE_SHADE)
    fill_poly([(758, 222), (842, 222), (830, 292), (770, 292)], WHITE)
    arc(846, 256, 18, -math.pi * 0.45, math.pi * 0.45, 7, WHITE)
    fill_ellipse(800, 224, 38, 10, COFFEE)
    # latte-art swirl: a pale rosetta on the coffee surface
    arc(800, 224, 22, math.pi * 0.15, math.pi * 0.85, 3, (235, 214, 186))
    arc(800, 224, 13, math.pi * 1.15, math.pi * 1.85, 3, (235, 214, 186))
    fill_circle(800, 224, 3, (235, 214, 186))
    arc(790, 190, 22, math.pi * 1.1, math.pi * 1.9, 5, WHITE, 0.45)
    arc(812, 178, 18, math.pi * 1.1, math.pi * 1.9, 5, WHITE, 0.45)


def draw_napkin():
    """A folded linen napkin, lower left."""
    fill_poly([(96, 700), (300, 686), (316, 900), (112, 912)], NAPKIN)
    fill_poly([(96, 700), (300, 686), (306, 730), (102, 744)], (150, 162, 180))
    line(120, 780, 296, 768, 4, (140, 152, 172), 0.7)
    line(124, 830, 300, 818, 4, (140, 152, 172), 0.7)


def draw_plate():
    """Plate shadow, plate, and a pool of syrup around the stack."""
    fill_ellipse_alpha(512, 814, 415, 64, (0, 0, 0), 0.30)
    fill_ellipse_alpha(512, 810, 385, 54, (0, 0, 0), 0.18)
    fill_ellipse(512, 780, 390, 105, PLATE)
    fill_ellipse(512, 774, 348, 88, (232, 228, 218))
    fill_ellipse(512, 770, 262, 44, SYRUP)  # syrup pool
    fill_ellipse(512, 766, 240, 38, SYRUP_LIGHT)
    # shimmer on the syrup pool
    fill_ellipse(430, 758, 60, 8, (244, 196, 96))
    fill_ellipse(430, 758, 30, 4, (255, 224, 150))
    fill_ellipse(610, 776, 44, 6, (244, 196, 96))


def pancake(cx, top_y, rx, shade=0):
    """One pancake: a cylinder with a golden top, a browned crust ring
    and speckles like the real thing. top_y is the centre of the top
    ellipse; the side is 54 px. ``shade`` shifts the top colour so
    each layer of the stack reads on its own."""
    top = lerp(PAN_TOP, PAN_SIDE_DARK, shade * 0.35)
    top_light = lerp(PAN_TOP_LIGHT, PAN_TOP, shade * 0.3)
    # side
    rect(cx - rx, top_y, rx * 2, 54, PAN_SIDE)
    fill_ellipse(cx, top_y + 54, rx, 30, PAN_SIDE_DARK)
    rect(cx - rx, top_y + 40, rx * 2, 8, PAN_SIDE_DARK)
    # shadow line under this pancake's side: separates the stacked layers
    rect(cx - rx, top_y + 48, rx * 2, 6, (120, 74, 26))
    # top, with a golden-brown crust ring at the rim
    fill_ellipse(cx, top_y, rx, 30, CRUST)
    fill_ellipse(cx, top_y, rx - 9, 26, top)
    fill_ellipse(cx - 8, top_y - 4, rx * 0.78, 20, top_light)
    # browned speckles on the top
    for _ in range(26):
        a = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(0, 0.85)
        sx = cx + rx * rr * math.cos(a)
        sy = top_y + 30 * rr * math.sin(a) * 0.9
        fill_circle(sx, sy, rng.uniform(1.5, 3.5), PAN_SIDE_DARK)


STACK = [(512, 716, 215), (508, 664, 210), (516, 612, 205),
         (510, 560, 198), (512, 508, 185)]


def draw_stack():
    for i, (cx, top_y, rx) in enumerate(STACK):
        pancake(cx, top_y, rx, shade=(i % 3) * 0.12)


def syrup_drip(x, y0, y1, w=16):
    """One glossy drip running down the front of the stack."""
    line(x, y0, x, y1, w, SYRUP)
    line(x - 4, y0, x - 4, y1 - 6, 5, SYRUP_LIGHT)
    fill_circle(x, y1, w / 2 + 1, SYRUP)
    fill_circle(x - 3, y1 - 3, 4, SYRUP_LIGHT)


def draw_syrup():
    """Syrup poured over the top pancake, dripping down the sides."""
    fill_ellipse(512, 506, 152, 27, SYRUP)
    fill_ellipse(500, 502, 122, 19, SYRUP_LIGHT)
    fill_ellipse(512, 506, 98, 17, SYRUP)
    # a thicker pour ridge over the rim, front-left
    fill_ellipse(430, 514, 46, 12, SYRUP)
    fill_ellipse(428, 512, 24, 6, SYRUP_LIGHT)
    # glossy highlight streak on the syrup pool
    fill_ellipse(468, 498, 52, 7, (244, 196, 96))
    fill_ellipse(468, 498, 26, 4, (255, 224, 150))
    syrup_drip(336, 520, 690, 15)
    syrup_drip(688, 520, 648, 15)
    syrup_drip(424, 522, 606, 13)
    syrup_drip(604, 522, 578, 13)
    syrup_drip(512, 524, 742, 12)  # long centre drip to the plate


def draw_butter():
    """A pat of butter, melting on top."""
    fill_poly([(428, 478), (510, 472), (518, 498), (436, 504)], BUTTER)
    fill_poly([(428, 478), (510, 472), (512, 481), (430, 487)], BUTTER_LIGHT)
    # glossy streak across the pat
    line(446, 484, 496, 480, 4, BUTTER_LIGHT)
    # wide melt pool around the pat
    fill_ellipse(474, 502, 42, 8, (250, 226, 110))
    fill_ellipse(474, 500, 26, 5, (255, 240, 170))
    line(470, 500, 464, 518, 6, BUTTER)  # a melt run


def blueberry(cx, cy, r):
    fill_circle(cx, cy, r, BERRY_BLUE)
    fill_circle(cx - r * 0.35, cy - r * 0.4, r * 0.32, BERRY_BLUE_LIGHT)
    fill_circle(cx, cy - r * 0.55, r * 0.18, (30, 30, 60))


def raspberry(cx, cy, r):
    """A raspberry: a bumpy red disc with a pale crown."""
    fill_circle(cx, cy, r, RASP)
    for dx, dy in ((-0.4, -0.3), (0.35, -0.25), (-0.1, 0.35), (0.45, 0.3),
                   (-0.45, 0.25), (0.1, -0.45)):
        fill_circle(cx + dx * r, cy + dy * r, r * 0.34, RASP_LIGHT)
    fill_circle(cx - r * 0.35, cy - r * 0.4, r * 0.28, (244, 140, 160))


def strawberry(cx, cy, s=1.0):
    """A strawberry, point down, with seeds and a green calyx."""
    fill_circle(cx - 8 * s, cy - 4 * s, 11 * s, STRAW)
    fill_circle(cx + 8 * s, cy - 4 * s, 11 * s, STRAW)
    fill_poly([(cx - 17 * s, cy - 2 * s), (cx + 17 * s, cy - 2 * s),
               (cx, cy + 24 * s)], STRAW)
    for dx, dy in ((-8, 2), (6, 4), (-2, 10), (10, -4), (-12, -4), (2, -6)):
        fill_circle(cx + dx * s, cy + dy * s, 1.8 * s, (255, 200, 180))
    fill_poly([(cx - 12 * s, cy - 12 * s), (cx, cy - 4 * s),
               (cx + 12 * s, cy - 12 * s)], MINT)


def banana_slice(cx, cy, r):
    """A banana slice: pale disc, darker rim, tiny centre star."""
    fill_circle(cx, cy, r, BANANA_DARK)
    fill_circle(cx, cy, r * 0.86, BANANA)
    fill_circle(cx, cy, r * 0.22, (226, 196, 128))
    for k in range(3):
        a = k * 2.094
        line(cx, cy, cx + r * 0.2 * math.cos(a), cy + r * 0.2 * math.sin(a),
             2, (200, 168, 100))


def mint_leaf(cx, cy, s=1.0):
    fill_poly([(cx - 16 * s, cy), (cx, cy - 9 * s), (cx + 16 * s, cy),
               (cx, cy + 9 * s)], MINT)
    line(cx - 12 * s, cy, cx + 12 * s, cy, 2, (30, 100, 50))


def draw_toppings():
    draw_butter()
    blueberry(560, 495, 14)
    blueberry(600, 510, 12)
    blueberry(428, 512, 12)
    raspberry(586, 488, 12)
    raspberry(452, 492, 10)
    strawberry(624, 512, 1.0)
    mint_leaf(452, 522, 0.9)
    mint_leaf(486, 528, 0.7)
    mint_leaf(540, 530, 0.8)
    # powdered sugar on the top pancake
    for _ in range(46):
        a = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(0.2, 0.95)
        sx = 512 + 185 * rr * math.cos(a)
        sy = 508 + 30 * rr * math.sin(a) * 0.9
        fill_circle_alpha(sx, sy, rng.uniform(1.5, 3), WHITE, 0.85)


def draw_plate_berries():
    blueberry(300, 806, 13)
    blueberry(330, 822, 11)
    blueberry(724, 812, 12)
    raspberry(706, 786, 11)
    strawberry(742, 786, 0.9)
    banana_slice(352, 792, 15)
    banana_slice(692, 828, 13)
    mint_leaf(318, 786, 0.8)
    mint_leaf(716, 838, 0.7)
    # powdered sugar dusted over the plate rim
    for _ in range(30):
        a = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(0.75, 0.98)
        sx = 512 + 348 * rr * math.cos(a)
        sy = 780 + 88 * rr * math.sin(a) * 0.9
        fill_circle_alpha(sx, sy, rng.uniform(1.5, 2.5), WHITE, 0.6)
    # a thin syrup drizzle across the front of the plate
    for t in range(0, 101, 4):
        x = 300 + t * 4.2
        y = 852 + 10 * math.sin(t / 100 * math.pi * 2.2)
        fill_circle(x, y, 4, SYRUP)
        fill_circle(x - 2, y - 1, 2, SYRUP_LIGHT)
    blueberry(360, 850, 10)
    raspberry(660, 852, 10)


def draw_fork():
    """A fork lying on the table at the right of the plate."""
    line(952, 592, 878, 742, 15, (196, 200, 206))
    fill_poly([(864, 734), (894, 756), (864, 818), (838, 798)], (196, 200, 206))
    for k in range(4):
        t = k / 3.0
        x0 = 864 - 6 + t * 28
        y0 = 812 - t * 6
        line(x0, y0, x0 - 16, y0 + 44, 4, (196, 200, 206))


def draw_orange_juice():
    """A glass of fresh orange juice, lower right, with a striped straw.

    The glass is a trapezoid, wider at the top; the juice sits just
    below the rim, with darker juice at the bottom and pale pulp dots
    floating in it. A red-and-white straw leans out to the upper right.
    """
    # soft shadow on the table under the glass
    fill_ellipse_alpha(930, 1004, 64, 12, (0, 0, 0), 0.25)
    # glass body: a pale, almost-clear trapezoid
    fill_poly([(884, 884), (976, 884), (962, 1002), (898, 1002)],
              (214, 226, 230))
    # juice inside, a little below the rim and inside the walls
    fill_poly([(890, 898), (970, 898), (958, 996), (902, 996)], JUICE)
    fill_poly([(902, 968), (958, 968), (956, 996), (904, 996)], JUICE_DARK)
    # juice surface seen from slightly above
    fill_ellipse(930, 898, 40, 7, JUICE_LIGHT)
    fill_ellipse(930, 898, 26, 4, (255, 205, 130))
    # pulp: pale orange flecks drifting in the juice
    for _ in range(22):
        px = rng.uniform(904, 954)
        py = rng.uniform(908, 988)
        fill_circle(px, py, rng.uniform(1.5, 3), (255, 196, 110))
    # red-and-white striped straw, leaning further out to the upper right
    sx0, sy0 = 952, 902
    sx1, sy1 = 1012, 798
    line(sx0, sy0, sx1, sy1, 10, WHITE)
    steps = 9
    for k in range(steps):
        t0 = k / steps
        t1 = (k + 0.55) / steps
        if k % 2 == 0:
            line(sx0 + (sx1 - sx0) * t0, sy0 + (sy1 - sy0) * t0,
                 sx0 + (sx1 - sx0) * t1, sy0 + (sy1 - sy0) * t1,
                 10, STRAW_RED)
    # glass rim and a glint of light down the left side
    line(884, 884, 976, 884, 4, (238, 244, 246), 0.85)
    line(896, 902, 902, 986, 6, WHITE, 0.5)
    fill_circle(900, 912, 4, WHITE)


def draw_crumbs():
    """Pancake crumbs on the table and cinnamon dust on the plate."""
    # crumbs scattered on the table beside the juice glass
    for _ in range(12):
        a = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(0, 1)
        cx = 828 + 58 * rr * math.cos(a)
        cy = 938 + 18 * rr * math.sin(a)
        fill_circle(cx, cy, rng.uniform(1.5, 3.5), PAN_SIDE_DARK)
    # cinnamon dusted over the plate rim, front right of the stack
    for _ in range(18):
        a = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(0.35, 1)
        cx = 612 + 52 * rr * math.cos(a)
        cy = 822 + 14 * rr * math.sin(a)
        fill_circle_alpha(cx, cy, rng.uniform(1, 2), (150, 92, 40), 0.75)


def draw():
    draw_background()
    draw_coffee()
    draw_napkin()
    draw_plate()
    draw_stack()
    draw_syrup()
    draw_toppings()
    draw_plate_berries()
    draw_crumbs()
    draw_fork()
    draw_orange_juice()
    vignette()


# -------------------------------------------------------------------- png ---
def png_chunk(kind, data):
    chunk = struct.pack(">I", len(data)) + kind + data
    chunk += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return chunk


def encode_png():
    """Encode the RGB canvas as a PNG (colour type 2, 8-bit).

    Each row gets the smallest of filters None/Sub/Up by the usual
    sum-of-absolute-values heuristic, then one zlib stream at level 9.
    Fully deterministic for a fixed canvas.
    """
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    raw = bytearray()
    prev = bytes(W * 3)
    for y in range(H):
        row = bytes(canvas[y * W * 3:(y + 1) * W * 3])
        cands = []
        cands.append((0, row))
        sub = bytearray(row)
        for i in range(3, len(sub)):
            sub[i] = (sub[i] - row[i - 3]) & 0xFF
        cands.append((1, bytes(sub)))
        up = bytearray(row)
        for i in range(len(up)):
            up[i] = (up[i] - prev[i]) & 0xFF
        cands.append((2, bytes(up)))

        def cost(b):
            return sum(v if v < 128 else 256 - v for v in b)

        ftype, fdata = min(cands, key=lambda c: cost(c[1]))
        raw.append(ftype)
        raw.extend(fdata)
        prev = row
    idat = zlib.compress(bytes(raw), 9)
    png = b"\x89PNG\r\n\x1a\n"
    png += png_chunk(b"IHDR", ihdr)
    png += png_chunk(b"IDAT", idat)
    png += png_chunk(b"IEND", b"")
    return png


def main():
    draw()
    png = encode_png()
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(png)
    digest = hashlib.sha256(png).hexdigest()
    print(f"wrote {path} ({len(png)} bytes, {W}x{H}, sha256={digest})")
    if len(png) > 1048576:
        print("WARNING: over the 1 MiB limit", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
