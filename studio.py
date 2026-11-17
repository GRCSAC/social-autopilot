"""Studio cards: one Instagram portrait card (1080x1350) per app post.

Used by the `studio_instagram` stream (the GRCSAC Studio Instagram account).
Distinct from generate.py's book cards on purpose: a dark product ground, the
app's own icon and accent colour, a Barlow headline, a Garamond sub-line, and
the app's site as the footer. Everything renders from bundled fonts so a
GitHub Actions runner produces the same image as a laptop.

Three layouts, picked by what the item carries:
  headline + sub            the typographic card (optionally "icons": [app, ...]
                            for a row of app icons under the text)
  + "shot": "file.jpg"      a real screenshot from assets/shots/ in a phone frame
  "slides": [...]           a carousel; each slide is one of the two above and
                            inherits the item's app, name and footer

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
SHOTS = ROOT / "assets" / "shots"

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


def slides_of(item):
    """The specs to render for an item: one for a card, several for a carousel."""
    if item.get("slides"):
        base = {k: v for k, v in item.items() if k not in ("slides", "caption", "headline", "sub", "shot", "icons")}
        return [{**base, **sl} for sl in item["slides"]]
    return [item]


def _phone(shot, width):
    """A screenshot with rounded corners inside a thin dark bezel."""
    im = Image.open(SHOTS / shot).convert("RGB")
    h = int(im.height * width / im.width)
    im = im.resize((width, h), Image.LANCZOS)
    bez = 14
    r = int(width * 0.085)
    body = Image.new("RGB", (width + 2 * bez, h + 2 * bez), (8, 10, 16))
    bmask = Image.new("L", body.size, 0)
    ImageDraw.Draw(bmask).rounded_rectangle([0, 0, body.width - 1, body.height - 1], radius=r + bez, fill=255)
    smask = Image.new("L", (width, h), 0)
    ImageDraw.Draw(smask).rounded_rectangle([0, 0, width - 1, h - 1], radius=r, fill=255)
    body.paste(im, (bez, bez), smask)
    edge = ImageDraw.Draw(body)
    edge.rounded_rectangle([1, 1, body.width - 2, body.height - 2], radius=r + bez, outline=(70, 78, 96), width=2)
    return body, bmask


def render_shot(spec, out_path):
    """Headline on top, the app's own screen underneath, running off the card."""
    app = spec["app"]
    accent = tuple(spec.get("accent", ACCENT.get(app, ACCENT["grcsac"])))
    img = _ground(accent)
    d = ImageDraw.Draw(img)
    M = 80

    # compact header: icon, name, platform, site
    isz = 92
    icon, mask = _icon(app, isz)
    img.paste(icon, (M, 70), mask)
    d.text((M + isz + 26, 70), spec["name"], font=B.label(40), fill=ON)
    line = "  ·  ".join(x for x in (spec.get("platform", ""), spec.get("status", "")) if x).upper()
    d.text((M + isz + 26, 122), line, font=B.label(22), fill=accent)
    site = spec.get("footer", "").upper()
    sf = B.label(22)
    d.text((W - M - B.text_w(d, site, sf), 82), site, font=sf, fill=MUTE)

    # headline, then an optional sub
    hf, lines, lh = B.fit_wrapped(d, spec["headline"], B.label, max_w=W - 2 * M,
                                  max_h=250, hi=84, lo=50, line_ratio=1.06)
    y = 212
    for ln in lines:
        d.text((M, y), ln, font=hf, fill=ON)
        y += lh
    sub = spec.get("sub", "")
    if sub:
        uf, ulines, ulh = B.fit_wrapped(d, sub, _serif_reg, max_w=W - 2 * M,
                                        max_h=110, hi=40, lo=30, line_ratio=1.28)
        y += 14
        for ln in ulines:
            d.text((M, y), ln, font=uf, fill=MUTE)
            y += ulh

    # the phone, centred, as large as the space allows, bleeding off the bottom
    top = y + 52
    pw = 600
    phone, pmask = _phone(spec["shot"], pw)
    px = (W - phone.width) // 2
    sm = pmask.filter(ImageFilter.GaussianBlur(26))
    glow = Image.new("L", (W, H), 0)
    glow.paste(sm, (px + 6, top + 26))
    img.paste(Image.new("RGB", (W, H), (0, 0, 0)), (0, 0), glow.point(lambda v: int(v * 0.55)))
    img.paste(phone, (px, top), pmask)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "JPEG", quality=90)
    return out_path


def render(spec, out_path):
    if spec.get("shot"):
        return render_shot(spec, out_path)
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
        # Directly under the headline, but never into the footer (or the icons).
        floor = 930 if spec.get("icons") else 1170
        sy = min(y + 56, floor - len(slines) * slh)
        for ln in slines:
            d.text((M, sy), ln, font=sf, fill=MUTE)
            sy += slh

    # --- optional row of app icons
    names = spec.get("icons") or []
    if names:
        isz2, gap = 150, 54
        x = M
        for a in names:
            ic, mk = _icon(a, isz2)
            img.paste(Image.new("RGB", (isz2, isz2), (0, 0, 0)), (x + 8, 978 + 10), mk)
            img.paste(ic, (x, 978), mk)
            x += isz2 + gap

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
            if it.get("video"):
                continue                  # posted as a Reel, no card to render
            specs = slides_of(it)
            for i, sp in enumerate(specs, 1):
                tail = f"-{i}" if len(specs) > 1 else ""
                print(render(sp, Path(a.out) / f"{it['id']}{tail}.jpg"))
    else:
        it = next(x for x in items if x["id"] == a.item)
        specs = slides_of(it)
        for i, sp in enumerate(specs, 1):
            out = Path(a.out)
            if len(specs) > 1:
                out = out.with_name(f"{out.stem}-{i}{out.suffix}")
            print(render(sp, out))
