"""Render the Sunk Cost "meter" Reel: public/video/studio-sunkcost-meter.mp4.

A 12 second, 1080x1920 animation of a meeting's cost climbing in time-lapse to
the figures in the app's own store screenshots: nine people, $10.58 a minute,
47 minutes 17 seconds, $500.25. Two of the quips are the app's own lines. Needs Pillow
and ffmpeg (libx264); run it from the repo root on a laptop, not in CI:

  python tools/make_meter_reel.py

The output is committed, so the workflow never has to render video.
"""
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import brand as B  # noqa: E402

W, H, FPS, SECS = 1080, 1920, 30, 12
OUT = ROOT / "public" / "video" / "studio-sunkcost-meter.mp4"
ICON = ROOT / "assets" / "apps" / "sunkcost.png"

GREEN_TOP, GREEN_BOT = (9, 62, 36), (4, 30, 18)
PANEL, PANEL_EDGE = (6, 24, 14), (150, 122, 40)
GOLD, CREAM, MUTE = (247, 201, 62), (240, 236, 222), (150, 176, 158)

RATE = 10.58                       # dollars a minute, from the app's screenshot
END_SECONDS = 47 * 60 + 17         # 00:47:17 -> $500.25
T_RUN0, T_RUN1 = 1.3, 8.2          # the meter runs between these (video seconds)
T_END = 10.2                       # end card from here
DY = 210                           # push the block down to the middle of the frame

ITALIC = str(ROOT / "assets" / "fonts" / "EBGaramond-Italic.ttf")


def italic(size):
    from PIL import ImageFont
    return ImageFont.truetype(ITALIC, size)


def ground():
    img = Image.new("RGB", (W, H), GREEN_TOP)
    d = ImageDraw.Draw(img)
    for y in range(H):
        k = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * k) for a, b in zip(GREEN_TOP, GREEN_BOT)))
    return img


BG = ground()


def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def fade(t, start, dur=0.35):
    return max(0.0, min(1.0, (t - start) / dur))


def blend(col, a, under=GREEN_BOT):
    return tuple(int(u + (c - u) * a) for c, u in zip(col, under))


def centered(d, text, font, y, fill):
    d.text(((W - B.text_w(d, text, font)) // 2, y), text, font=font, fill=fill)


def fixed_digits(d, text, font, cy, fill, cell):
    """Draw text with every digit in an equal cell so the number does not jitter."""
    widths = [cell if ch.isdigit() else B.text_w(d, ch, font) for ch in text]
    x = (W - sum(widths)) // 2
    for ch, w in zip(text, widths):
        cw = B.text_w(d, ch, font)
        d.text((x + (w - cw) // 2, cy), ch, font=font, fill=fill)
        x += w


def wrap_center(d, text, font, y, fill, max_w=860, lh=74):
    for ln in B.wrap(d, text, font, max_w):
        centered(d, ln, font, y, fill)
        y += lh
    return y


def frame(i):
    t = i / FPS
    img = BG.copy()
    d = ImageDraw.Draw(img)

    if t < T_END:
        # --- set-up line
        a = fade(t, 0.15)
        centered(d, "NINE PEOPLE WALK INTO A MEETING", B.label(40), 330 + DY, blend(MUTE, a, GREEN_TOP))

        # --- the meter panel
        a = fade(t, 0.7)
        if a > 0:
            box = [90, 470 + DY, W - 90, 1010 + DY]
            d.rounded_rectangle(box, radius=56, fill=blend(PANEL, a, GREEN_TOP), outline=blend(PANEL_EDGE, a, GREEN_TOP), width=4)
            run = ease((t - T_RUN0) / (T_RUN1 - T_RUN0))
            secs = int(END_SECONDS * run)
            dollars = secs / 60 * RATE if run < 1 else 500.25
            running = T_RUN0 <= t < T_RUN1
            dot = (230, 70, 60) if running and int(t * 2) % 2 == 0 else blend(MUTE, 0.5, PANEL)
            lab = "METER RUNNING" if t < T_RUN1 else "TOTAL DAMAGE"
            lf = B.label(34)
            lw = B.text_w(d, lab, lf)
            d.ellipse([(W - lw) // 2 - 40, 534 + DY, (W - lw) // 2 - 18, 556 + DY], fill=blend(dot, a, PANEL))
            centered(d, lab, lf, 524 + DY, blend(MUTE, a, PANEL))
            big = B.label(190)
            if t >= T_RUN1:                     # a soft glow once it lands
                gl = Image.new("RGB", (W, H), (0, 0, 0))
                gd = ImageDraw.Draw(gl)
                fixed_digits(gd, f"${dollars:,.2f}", big, 600 + DY, GOLD, 104)
                gl = gl.filter(ImageFilter.GaussianBlur(22))
                img = Image.composite(Image.new("RGB", (W, H), GOLD), img, gl.convert("L").point(lambda v: int(v * 0.45)))
                d = ImageDraw.Draw(img)
            fixed_digits(d, f"${dollars:,.2f}", big, 600 + DY, blend(GOLD, a, PANEL), 104)
            clock = f"{secs // 3600:02d}:{secs % 3600 // 60:02d}:{secs % 60:02d}"
            fixed_digits(d, clock, B.label(84), 846 + DY, blend(CREAM, a, PANEL), 48)

        # --- quips, timed to the meeting clock
        minutes = END_SECONDS * ease((t - T_RUN0) / (T_RUN1 - T_RUN0)) / 60
        qf = italic(60)
        qy = 1130 + DY
        if t >= T_RUN1 + 0.25:
            a = fade(t, T_RUN1 + 0.25)
            wrap_center(d, "This meeting could have been an email.", qf, qy, blend(CREAM, a))
        elif minutes >= 44:
            wrap_center(d, "\"Let's take this offline\" has been said twice.", qf, qy, CREAM)
        elif minutes >= 31:
            wrap_center(d, "A latecomer. We start over.", qf, qy, CREAM)
        elif minutes >= 17:
            wrap_center(d, "Still no agenda.", qf, qy, CREAM)
        elif minutes >= 4:
            wrap_center(d, "Someone is sharing the wrong screen.", qf, qy, CREAM)
        if t >= 0.7:
            centered(d, "9 IN THE ROOM   .   $635 AN HOUR   .   $10.58 A MINUTE".replace(" . ", " · "),
                     B.label(30), 1040 + DY, blend(MUTE, fade(t, 0.9)))
    else:
        # --- end card
        a = fade(t, T_END, 0.4)
        isz = 300
        ic = Image.open(ICON).convert("RGB").resize((isz, isz), Image.LANCZOS)
        mk = Image.new("L", (isz, isz), 0)
        ImageDraw.Draw(mk).rounded_rectangle([0, 0, isz - 1, isz - 1], radius=int(isz * 0.22), fill=int(255 * a))
        img.paste(ic, ((W - isz) // 2, 560), mk)
        centered(d, "Sunk Cost", B.label(110), 920, blend(CREAM, a, GREEN_TOP))
        centered(d, "What is this meeting costing?", italic(58), 1060, blend(GOLD, a))
        centered(d, "GOOGLE PLAY  ·  APP STORE", B.label(40), 1200, blend(MUTE, a))
        centered(d, "SUNKCOST.GRCSAC.COM", B.label(34), 1270, blend(MUTE, a))
    return img


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-v", "error", "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
           "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "96k", "-shortest", "-movflags", "+faststart", str(OUT)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(FPS * SECS):
        p.stdin.write(frame(i).tobytes())
    p.stdin.close()
    p.wait()
    print(OUT, OUT.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    if len(sys.argv) > 1:              # python tools/make_meter_reel.py 4.0 out.jpg  -> one frame
        frame(int(float(sys.argv[1]) * FPS)).save(sys.argv[2], quality=85)
    else:
        main()
