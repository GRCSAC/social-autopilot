"""Studio cards: one Instagram portrait card (1080x1350) per app post.

Used by the `studio_instagram` stream (the GRCSAC Studio Instagram account).
Distinct from generate.py's book cards on purpose: a dark product ground, the
app's own icon and accent colour, a Barlow headline, a Garamond sub-line, and
the app's site as the footer. Everything renders from bundled fonts so a
GitHub Actions runner produces the same image as a laptop.

Preview one card locally:
  python studio.py content/studio_instagram.json ig-studio-inthezone-1 -o preview.jpg
Render the whole library:
  python studio.py content/studio_instagram.json --all -o preview/
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

import brand as B

ROOT = Path(__file__).resolve().parent
APPS = ROOT / "assets" / "apps"

W, H = 1080, 1350               # Instagram portrait (4:5)
GROUND = (17, 26, 48)           # grcsac.com card ground
GROUND_2 = (10, 15, 30)
ON = (242, 239, 232)
MUTE = (160, 168, 186)

# App accent colours, from the grcsac.com tile palette (light variants).
ACCENT = {
    "inthezone":      (242, 128, 63),
    "pavlove":        (238, 90, 156),
    "fitthis":        (255, 90, 31),
    "findr":          (255, 59, 99),
    "siftlet":        (238, 137, 90),
    "sunkcost":       (63, 185, 80),
    "cysec":          (184, 16, 48),
    "nextfix":        (34, 211, 238),
    "cinedrive":      (107, 123, 255),
    "earnest":        (193, 121, 172),
    "infiniteworlds": (243, 86, 255),
    "zelzi":          (243, 86, 255),
    "grcsac":         (220, 166, 62),
}


def _ground(accent):
    img = Image.new("RGB", (W, H), GROUND)
    # vertical depth
    top = Image.new("RGB", (W, H), GROUND_2)
    mask = Image.new("L", (W, H))
    md = ImageDraw.Draw(mask)
    for y in range(H):
        md.line([(0, y), (W, y)], fill=int(90 * (y / H)))
    img = Image.composite(top, img, mask)
    # soft accent glow, top right
    glow = Image.new("RGB", (W, H), GROUND)
    gd = ImageDraw.Draw(glow)
    gd.ellipse([W - 620, -420, W + 260, 460], fill=accent)
    glow = glow.filter(ImageFilter.GaussianBlur(170))
    gmask = Image.new("L", (W, H), 0)
    gmd = ImageDraw.Draw(gmask)
    gmd.ellipse([W - 620, -420, W + 260, 460], fill=120)
    gmask = gmask.filter(ImageFilter.GaussianBlur(170))
    return Image.composite(glow, img, gmask)


def _icon(app, size):
    im = Image.open(APPS / f"{app}.png").convert("RGB").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.22), fill=255)
    return im, mask


def _serif_reg(size):
    return B.serif(size, 400)


def render(spec, out_path):
    app = spec["app"]
    accent = tuple(spec.get("accent", ACCENT.get(app, ACCENT["grcsac"])))
    img = _ground(accent)
    d = ImageDraw.Draw(img)
    M = 90                                # side margin

    # --- header: icon + app name + platform line
    isz = 200
    icon, mask = _icon(app, isz)
    shadow = Image.new("RGB", (isz, isz), (0, 0, 0))
    img.paste(shadow, (M + 10, 110 + 14), mask)
    img.paste(icon, (M, 110), mask)
    nx = M + isz + 44
    d.text((nx, 128), spec["name"], font=B.label(54), fill=ON)
    d.text((nx, 200), spec.get("platform", "").upper(), font=B.label(26), fill=accent)
    status = spec.get("status", "")
    if status:
        d.text((nx, 244), status.upper(), font=B.label(26), fill=MUTE)

    # --- headline
    d.rectangle([M, 380, M + 96, 385], fill=accent)
    hf, lines, lh = B.fit_wrapped(d, spec["headline"], B.label, max_w=W - 2 * M,
                                  max_h=430, hi=96, lo=56, line_ratio=1.08)
    y = 420
    for ln in lines:
        d.text((M, y), ln, font=hf, fill=ON)
        y += lh

    # --- sub line
    sub = spec.get("sub", "")
    if sub:
        sf, slines, slh = B.fit_wrapped(d, sub, _serif_reg, max_w=W - 2 * M,
                                        max_h=300, hi=46, lo=34, line_ratio=1.3)
        # Directly under the headline, but never into the footer.
        sy = min(y + 56, 1170 - len(slines) * slh)
        for ln in slines:
            d.text((M, sy), ln, font=sf, fill=MUTE)
            sy += slh

    # --- footer
    d.rectangle([M, 1218, W - M, 1219], fill=(45, 56, 84))
    d.text((M, 1246), spec.get("footer", "").upper(), font=B.label(26), fill=accent)
    tag = "GRCSAC STUDIO"
    tf = B.label(26)
    d.text((W - M - B.text_w(d, tag, tf), 1246), tag, font=tf, fill=MUTE)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "JPEG", quality=90)
    return out_path


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("library")
    ap.add_argument("item", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("-o", "--out", default="preview")
    a = ap.parse_args()
    items = json.loads(Path(a.library).read_text(encoding="utf-8"))
    if a.all:
        for it in items:
            print(render(it, Path(a.out) / f"{it['id']}.jpg"))
    else:
        it = next(x for x in items if x["id"] == a.item)
        print(render(it, a.out))
