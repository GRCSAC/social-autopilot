"""Brand system for GRCSAC social cards — palette, fonts, and text helpers.

Warm ink ground, brass accents, a book serif (EB Garamond) for the words and a
clean grotesque (Barlow) for labels. Everything renders with bundled fonts so a
GitHub Actions Linux runner produces the exact same image as a laptop.
"""
from pathlib import Path
from PIL import ImageFont

ROOT = Path(__file__).resolve().parent
FONT_DIR = ROOT / "assets" / "fonts"

# --- palette (RGB) ---
INK        = (23, 20, 15)
INK_2      = (35, 30, 22)
ON_INK     = (242, 239, 232)
MUTE       = (165, 157, 144)
BRASS      = (173, 137, 66)
BRASS_SOFT = (205, 175, 115)
SHADOW     = (0, 0, 0)

_SERIF_VAR = str(FONT_DIR / "EBGaramond.ttf")          # variable weight axis
_LABEL     = str(FONT_DIR / "Barlow-Bold.ttf")         # static


def serif(size, weight=700):
    """EB Garamond at a given pixel size and weight (400-800)."""
    f = ImageFont.truetype(_SERIF_VAR, size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def label(size):
    return ImageFont.truetype(_LABEL, size)


def text_w(draw, s, fnt):
    return draw.textbbox((0, 0), s, font=fnt)[2]


def wrap(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if text_w(draw, trial, fnt) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit_wrapped(draw, text, make_font, max_w, max_h, hi, lo=30, line_ratio=1.16):
    """Largest size in [lo, hi] whose wrapped block fits max_w x max_h.

    make_font(size) -> ImageFont. Returns (font, lines, line_height).
    """
    size = hi
    while size >= lo:
        fnt = make_font(size)
        lines = wrap(draw, text, fnt, max_w)
        line_h = int(size * line_ratio)
        if len(lines) * line_h <= max_h:
            return fnt, lines, line_h
        size -= 2
    fnt = make_font(lo)
    return fnt, wrap(draw, text, fnt, max_w), int(lo * line_ratio)


def draw_center_block(draw, lines, fnt, line_h, cx, top, fill):
    y = top
    for ln in lines:
        w = text_w(draw, ln, fnt)
        draw.text((cx - w / 2, y), ln, font=fnt, fill=fill)
        y += line_h


def draw_left_block(draw, lines, fnt, line_h, x, top, fill):
    y = top
    for ln in lines:
        draw.text((x, y), ln, font=fnt, fill=fill)
        y += line_h
