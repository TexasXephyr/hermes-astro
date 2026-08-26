#!/usr/bin/env python3
"""Generate 5 astro-gui icon options, 256x256, matching the app's dark+gold theme.

Run: /usr/bin/python3 scripts/make_icons.py   (any python with Pillow works)
Output: ~/astro/assets/icons/astro-gui-<n>-<name>.png
"""
import math
import os
import random
from PIL import Image, ImageDraw, ImageFilter

S = 1024          # supersample canvas (downscaled to 256 at the end)
FINAL = 256
OUT = os.path.expanduser("~/astro/assets/icons")
os.makedirs(OUT, exist_ok=True)

GOLD = (212, 167, 44)
GOLD_DIM = (138, 109, 31)
CREAM = (238, 238, 238)
BG = (30, 30, 30)
BG_TOP = (35, 35, 35)
BG_BOT = (26, 26, 26)

CX, CY = S // 2, S // 2


def save(img, name):
    img = img.resize((FINAL, FINAL), Image.LANCZOS)
    path = os.path.join(OUT, name)
    img.save(path)
    print("wrote", path)


def make_bg(radius=0.22):
    """Dark rounded-square background: subtle vertical gradient + gold rim."""
    rad = int(S * radius)
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for y in range(S):  # gradient
        t = y / S
        col = tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * t) for i in range(3))
        d.line([(0, y), (S, y)], fill=col + (255,))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=rad, fill=255)
    img.putalpha(mask)
    rim = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(rim).rounded_rectangle([6, 6, S - 7, S - 7], radius=rad - 6,
                                          outline=GOLD_DIM + (130,), width=6)
    return Image.alpha_composite(img, rim)


def glow(fn, radius=40, color=GOLD):
    """Soft glow layer: draw opaque shapes on a layer, blur, tint."""
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    fn(ImageDraw.Draw(layer))
    blur = layer.filter(ImageFilter.GaussianBlur(radius))
    r, g, b = color
    px = blur.load()
    for y in range(S):
        for x in range(S):
            a = px[x, y][3]
            if a:
                px[x, y] = (r, g, b, a // 3)
    return blur


def ring_ellipse_layer(rx, ry, width, tilt, color=GOLD, alpha=255,
                       start=0, end=360, outline=True):
    """A (possibly partial) tilted ellipse ring on its own layer."""
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    bbox = [CX - rx, CY - ry, CX + rx, CY + ry]
    d = ImageDraw.Draw(layer)
    if outline:
        d.ellipse(bbox, outline=color + (alpha,), width=width)
    else:
        d.arc(bbox, start, end, fill=color + (alpha,), width=width)
    return layer.rotate(tilt, center=(CX, CY), resample=Image.BICUBIC)


# ----------------------------------------------------------------------------
# 1. ZODIAC WHEEL
# ----------------------------------------------------------------------------
def icon_wheel():
    img = make_bg()
    base = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)

    outer_r, inner_r = 400, 270
    d.ellipse([CX - outer_r, CY - outer_r, CX + outer_r, CY + outer_r],
              outline=GOLD + (255,), width=16)
    d.ellipse([CX - inner_r, CY - inner_r, CX + inner_r, CY + inner_r],
              outline=GOLD_DIM + (255,), width=6)

    for i in range(12):  # sign ticks + diamonds on the inner ring
        a = math.radians(i * 30 - 90)
        ca, sa = math.cos(a), math.sin(a)
        d.line([CX + (inner_r + 8) * ca, CY + (inner_r + 8) * sa,
                CX + (outer_r - 8) * ca, CY + (outer_r - 8) * sa],
               fill=GOLD + (255,), width=12)
        rd = 24
        mx, my = CX + inner_r * ca, CY + inner_r * sa
        d.polygon([(mx, my - rd), (mx + rd, my), (mx, my + rd), (mx - rd, my)],
                  fill=CREAM + (255,))

    # planets: dots INSIDE the wheel so the ring/ticks stay clean
    planets = [(30, 200, GOLD, 44), (115, 160, CREAM, 24), (190, 200, CREAM, 18),
               (255, 160, CREAM, 22), (315, 200, GOLD_DIM, 28)]
    for deg, r, col, size in planets:
        a = math.radians(deg - 90)
        x, y = CX + r * math.cos(a), CY + r * math.sin(a)
        d.ellipse([x - size, y - size, x + size, y + size], fill=col + (255,))

    d.ellipse([CX - 26, CY - 26, CX + 26, CY + 26], fill=GOLD + (255,))
    d.ellipse([CX - 12, CY - 12, CX + 12, CY + 12], fill=BG + (255,))

    g = glow(lambda dd: dd.ellipse([CX - outer_r, CY - outer_r, CX + outer_r, CY + outer_r],
                                   outline=GOLD + (255,), width=16), radius=30)
    save(Image.alpha_composite(Image.alpha_composite(img, g), base), "astro-gui-1-zodiac-wheel.png")


# ----------------------------------------------------------------------------
# 2. SATURN
# ----------------------------------------------------------------------------
def icon_saturn():
    img = make_bg()
    base = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)

    random.seed(7)
    for _ in range(70):  # starfield
        x, y = random.randint(20, S - 20), random.randint(20, S - 20)
        r = random.choice([3, 4, 5, 7])
        col = random.choice([CREAM, GOLD_DIM, (255, 255, 255)])
        d.ellipse([x - r, y - r, x + r, y + r], fill=col + (180,))

    pr = 200
    back_ring = ring_ellipse_layer(rx=400, ry=170, width=30, tilt=-22)

    planet = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    pd = ImageDraw.Draw(planet)
    pd.ellipse([CX - pr, CY - pr, CX + pr, CY + pr], fill=GOLD + (255,))
    # subtle banding
    for i, w in enumerate([24, 16, 24]):
        yy = CY - 36 + i * 40
        pd.ellipse([CX - pr, yy - w, CX + pr, yy + w], outline=(0, 0, 0, 60), width=12)

    # front half of the ring: drawn as an arc in the same coordinate space as
    # the back ring, then rotated identically so both halves align perfectly.
    front_ring = ring_ellipse_layer(rx=400, ry=170, width=30, tilt=-22,
                                    start=0, end=180, outline=False)

    g = glow(lambda dd: dd.ellipse([CX - pr - 30, CY - pr - 30, CX + pr + 30, CY + pr + 30],
                                   outline=GOLD + (255,), width=24), radius=45)
    img = Image.alpha_composite(Image.alpha_composite(img, g), base)
    img = Image.alpha_composite(img, back_ring)
    img = Image.alpha_composite(img, planet)
    img = Image.alpha_composite(img, front_ring)
    save(img, "astro-gui-2-saturn.png")


# ----------------------------------------------------------------------------
# 3. CRESCENT + STAR
# ----------------------------------------------------------------------------
def icon_crescent():
    img = make_bg()
    base = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)

    bbox = [CX - 300, CY - 300, CX + 300, CY + 300]
    d.arc(bbox, 35, 325, fill=GOLD + (255,), width=120)
    d.arc([CX - 175, CY - 175, CX + 175, CY + 175], 55, 305, fill=BG + (255,), width=70)

    sx, sy = CX + 240, CY - 250
    d.polygon([(sx, sy - 90), (sx + 26, sy - 26), (sx + 90, sy), (sx + 26, sy + 26),
               (sx, sy + 90), (sx - 26, sy + 26), (sx - 90, sy), (sx - 26, sy - 26)],
              fill=CREAM + (255,))

    g = glow(lambda dd: dd.arc(bbox, 35, 325, fill=GOLD + (255,), width=120), radius=40)
    save(Image.alpha_composite(Image.alpha_composite(img, g), base), "astro-gui-3-crescent.png")


# ----------------------------------------------------------------------------
# 4. SUN GLYPH
# ----------------------------------------------------------------------------
def icon_sun():
    img = make_bg()
    base = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)

    r = 185
    d.ellipse([CX - r, CY - r, CX + r, CY + r], outline=GOLD + (255,), width=26)
    for i in range(8):
        a = math.radians(i * 45 - 90)
        ca, sa = math.cos(a), math.sin(a)
        d.line([CX + (r + 55) * ca, CY + (r + 55) * sa,
                CX + (r + 150) * ca, CY + (r + 150) * sa],
               fill=GOLD + (255,), width=30)

    g = glow(lambda dd: [dd.ellipse([CX - r, CY - r, CX + r, CY + r],
                                    outline=GOLD + (255,), width=26),
                         dd.arc([CX - 90, CY - 90, CX + 90, CY + 90], 0, 360,
                                fill=GOLD + (255,), width=20)], radius=50)
    save(Image.alpha_composite(Image.alpha_composite(img, g), base), "astro-gui-4-sun-glyph.png")


# ----------------------------------------------------------------------------
# 5. CONSTELLATION
# ----------------------------------------------------------------------------
def icon_constellation():
    img = make_bg()
    base = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)

    # one faint zodiac band — nothing that can alias into a double trace
    d.ellipse([CX - 380, CY - 380, CX + 380, CY + 380], outline=GOLD_DIM + (110,), width=8)

    stars = [(340, 300, 22), (430, 420, 14), (560, 350, 18), (640, 470, 12),
             (700, 280, 26), (560, 620, 16), (420, 640, 12), (300, 540, 14),
             (660, 660, 10), (520, 200, 12), (350, 210, 10), (700, 560, 12)]
    links = [(0, 1), (1, 2), (2, 3), (3, 4), (2, 5), (5, 6), (6, 7), (7, 0),
             (5, 8), (0, 9), (9, 10), (4, 11)]
    for i, j in links:
        x1, y1, _ = stars[i]
        x2, y2, _ = stars[j]
        d.line([x1, y1, x2, y2], fill=GOLD + (110,), width=8)

    fx, fy = 700, 280
    d.line([fx - 70, fy, fx + 70, fy], fill=CREAM + (255,), width=10)
    d.line([fx, fy - 70, fx, fy + 70], fill=CREAM + (255,), width=10)
    for x, y, r in stars:
        d.ellipse([x - r, y - r, x + r, y + r], fill=GOLD if r >= 18 else CREAM + (230,))

    g = glow(lambda dd: dd.ellipse([fx - 40, fy - 40, fx + 40, fy + 40], fill=CREAM + (255,)),
             radius=60, color=CREAM)
    save(Image.alpha_composite(Image.alpha_composite(img, g), base), "astro-gui-5-constellation.png")


if __name__ == "__main__":
    icon_wheel()
    icon_saturn()
    icon_crescent()
    icon_sun()
    icon_constellation()
    print("done ->", OUT)
