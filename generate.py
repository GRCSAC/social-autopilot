"""Render a 1080x1080 branded social card from a spec dict.

Two card types:
  quote   -> eyebrow + centered pull-quote + attribution, inside a brass frame
  feature -> book cover on the right, hook line + labels on the left

Usage (CLI, for local testing):
  python generate.py quote  "Compassion is not the opposite of strength." \
                     --eyebrow "COMPASSION UNLEASHED" --attrib "PAUL ZAROU" -o out.jpg
"""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw
import brand as B

ROOT = Path(__file__).resolve().parent
COVERS = ROOT / "assets" / "covers"
S = 1080


def _bg(size=S):
    img = Image.new("RGB", (size, size), B.INK)
    # subtle diagonal ink gradient for depth
    top = Image.new("RGB", (size, size), B.INK_2)
    mask = Image.new("L", (size, size))
    md = ImageDraw.Draw(mask)
    for y in range(size):
        md.line([(0, y), (size, y)], fill=int(70 * (1 - y / size)))
    img = Image.composite(top, img, mask)
    return img


def render_quote(spec, out_path):
    img = _bg()
    d = ImageDraw.Draw(img)
    d.rectangle([44, 44, S - 44, S - 44], outline=B.BRASS, width=2)
    cx = S // 2

    eyebrow = spec.get("eyebrow", "").upper()
    ef = B.label(26)
    ew = B.text_w(d, eyebrow, ef)
    d.text((cx - ew / 2, 150), eyebrow, font=ef, fill=B.BRASS_SOFT)
    d.rectangle([cx - 45, 210, cx + 45, 213], fill=B.BRASS)

    quote = '“' + spec["quote"].strip('"“”') + '”'
    qf, lines, lh = B.fit_wrapped(d, quote, B.serif, max_w=S - 240,
                                  max_h=520, hi=90, lo=44)
    block_h = len(lines) * lh
    top = 300 + (520 - block_h) // 2
    B.draw_center_block(d, lines, qf, lh, cx, top, B.ON_INK)

    d.rectangle([cx - 45, 872, cx + 45, 875], fill=B.BRASS)
    attrib = spec.get("attribution", "PAUL ZAROU").upper()
    af = B.label(26)
    aw = B.text_w(d, attrib, af)
    d.text((cx - aw / 2, 900), attrib, font=af, fill=B.MUTE)

    img.save(out_path, "JPEG", quality=90)
    return out_path


def render_feature(spec, out_path):
    img = _bg()
    d = ImageDraw.Draw(img)

    cover = Image.open(COVERS / spec["cover"]).convert("RGB")
    ch = 560
    cw = int(ch * cover.width / cover.height)
    cover = cover.resize((cw, ch), Image.LANCZOS)
    cx = S - cw - 70
    cy = (S - ch) // 2
    shadow = Image.new("RGB", (cw, ch), B.SHADOW)
    img.paste(shadow, (cx + 12, cy + 16))
    img.paste(cover, (cx, cy))
    d.rectangle([cx, cy, cx + cw, cy + ch], outline=B.BRASS, width=2)

    lx, lw = 80, cx - 80 - 40
    ef = B.label(24)
    d.text((lx, 150), spec.get("eyebrow", "").upper(), font=ef, fill=B.BRASS_SOFT)
    d.rectangle([lx, 196, lx + 72, 199], fill=B.BRASS)

    hf, lines, lh = B.fit_wrapped(d, spec["hook"], B.serif, max_w=lw,
                                  max_h=520, hi=66, lo=38)
    B.draw_left_block(d, lines, hf, lh, lx, 250, B.ON_INK)

    d.rectangle([lx, 880, lx + 72, 883], fill=B.BRASS)
    ff = B.label(24)
    d.text((lx, 904), spec.get("footer", "").upper(), font=ff, fill=B.MUTE)

    img.save(out_path, "JPEG", quality=90)
    return out_path


def render(spec, out_path):
    kind = spec.get("type", "quote")
    if kind == "feature":
        return render_feature(spec, out_path)
    return render_quote(spec, out_path)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("type", choices=["quote", "feature"])
    p.add_argument("text", help="quote text, or hook for feature")
    p.add_argument("--eyebrow", default="")
    p.add_argument("--attrib", default="PAUL ZAROU")
    p.add_argument("--cover", default="create-promote-allow.jpg")
    p.add_argument("--footer", default="")
    p.add_argument("-o", "--out", default="preview.jpg")
    a = p.parse_args()
    spec = {"type": a.type, "eyebrow": a.eyebrow, "attribution": a.attrib,
            "cover": a.cover, "footer": a.footer,
            "quote": a.text, "hook": a.text}
    render(spec, a.out)
    print("wrote", a.out)
