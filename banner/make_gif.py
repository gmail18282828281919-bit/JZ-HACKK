#!/usr/bin/env python3
"""Fabrique une banniere animee (GIF en boucle) a partir d'une image fixe.

    python3 banner/make_gif.py source.png -o banner/banner.gif --preset discord

Les petales, le zoom et le reflet bouclent exactement : la derniere image
enchaine sur la premiere sans saut.
"""
import argparse
import math
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter

PRESETS = {
    "discord": (680, 240),    # banniere de profil Discord
    "server": (960, 540),     # banniere de serveur Discord
    "wide": (960, 384),       # 2.5:1, le format de l'image d'origine
}


def petal_stamp(size=96):
    """Un petale blanc-bleute, en RGBA, oriente vers le haut."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((size * 0.22, size * 0.05, size * 0.78, size * 0.95),
              fill=(255, 255, 255, 255))
    d.ellipse((size * 0.30, size * 0.45, size * 0.70, size * 1.02),
              fill=(178, 212, 255, 255))
    img = img.filter(ImageFilter.GaussianBlur(size * 0.02))
    return img


def vignette(w, h, strength=0.55):
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse((-w * 0.22, -h * 0.34, w * 1.22, h * 1.34), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(min(w, h) * 0.16))
    dark = Image.new("RGB", (w, h), (4, 14, 38))
    alpha = mask.point(lambda v: int((255 - v) * strength))
    dark.putalpha(alpha)
    return dark


def sweep_band(w, h):
    """Bande lumineuse diagonale, pre-rendue une fois."""
    bw = int(w * 0.34)
    band = Image.new("L", (bw, h * 2), 0)
    d = ImageDraw.Draw(band)
    for x in range(bw):
        t = x / max(bw - 1, 1)
        v = math.sin(math.pi * t) ** 2
        d.line((x, 0, x, h * 2), fill=int(190 * v))
    band = band.rotate(-14, expand=True, resample=Image.BICUBIC)
    light = Image.new("RGB", band.size, (214, 236, 255))
    light.putalpha(band.filter(ImageFilter.GaussianBlur(6)))
    return light


def build(src, out, size, frames, fps, count, seed):
    random.seed(seed)
    w, h = size
    base = Image.open(src).convert("RGB")

    # recadrage centre au bon ratio
    target = w / h
    bw, bh = base.size
    if bw / bh > target:
        nw = int(bh * target)
        base = base.crop(((bw - nw) // 2, 0, (bw + nw) // 2, bh))
    else:
        nh = int(bw / target)
        top = int((bh - nh) * 0.42)   # garde le haut, ou vivent les fleurs
        base = base.crop((0, top, bw, top + nh))

    zoom_max = 1.06
    big = base.resize((int(w * zoom_max), int(h * zoom_max)), Image.LANCZOS)
    stamp = petal_stamp()
    vig = vignette(w, h)
    band = sweep_band(w, h)
    travel = w + band.width

    petals = []
    for _ in range(count):
        depth = random.random()
        petals.append({
            "x": random.uniform(-0.05, 1.05),
            "y": random.random(),
            "size": random.uniform(0.020, 0.055) * (0.6 + depth) * h,
            "phase": random.uniform(0, math.tau),
            "sway": random.uniform(0.012, 0.030),
            "spin": random.choice((-1, 1)) * random.randint(1, 2),
            "rot": random.uniform(0, 360),
            "alpha": int(random.uniform(90, 235) * (0.45 + depth * 0.7)),
        })

    out_frames = []
    for i in range(frames):
        t = i / frames                      # 0 -> 1 sur la boucle

        # zoom sinusoidal : identique au debut et a la fin
        z = 1.0 + (zoom_max - 1.0) * (0.5 - 0.5 * math.cos(math.tau * t))
        cw, ch = int(w * z), int(h * z)
        frame = big.resize((cw, ch), Image.LANCZOS)
        frame = frame.crop(((cw - w) // 2, (ch - h) // 2,
                            (cw - w) // 2 + w, (ch - h) // 2 + h))

        # reflet lumineux : entre et sort du cadre sur une boucle
        pos = int(-band.width + travel * t)
        glow = Image.new("RGB", (w, h), (0, 0, 0))
        glow.paste(band.convert("RGB"), (pos, -h // 4), band.split()[3])
        frame = Image.blend(frame, _screen(frame, glow), 0.55)

        # petales
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        for p in petals:
            y = ((p["y"] + t) % 1.18) * h - h * 0.09
            x = (p["x"] + math.sin(math.tau * t + p["phase"]) * p["sway"]) * w
            s = max(int(p["size"]), 3)
            sp = stamp.resize((s, s), Image.LANCZOS)
            sp = sp.rotate(p["rot"] + p["spin"] * 360 * t, expand=True,
                           resample=Image.BICUBIC)
            sp.putalpha(sp.split()[3].point(lambda v: v * p["alpha"] // 255))
            layer.alpha_composite(sp, (int(x - sp.width / 2), int(y - sp.height / 2)))
        frame = Image.alpha_composite(frame.convert("RGBA"), layer)

        frame = Image.alpha_composite(frame, vig.convert("RGBA")).convert("RGB")
        out_frames.append(frame.quantize(colors=200, method=Image.MEDIANCUT))

    out_frames[0].save(out, save_all=True, append_images=out_frames[1:],
                       duration=int(1000 / fps), loop=0, optimize=True,
                       disposal=2)
    return out


def _screen(a, b):
    """Fusion 'ecran' : eclaircit sans cramer."""
    return Image.merge("RGB", [_screen_channel(ca, cb)
                               for ca, cb in zip(a.split(), b.split())])


def _screen_channel(a, b):
    inv_a = a.point(lambda v: 255 - v)
    inv_b = b.point(lambda v: 255 - v)
    return ImageChops.multiply(inv_a, inv_b).point(lambda v: 255 - v)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="image de depart (png/jpg)")
    ap.add_argument("-o", "--out", default="banner.gif")
    ap.add_argument("--preset", choices=sorted(PRESETS), default="discord")
    ap.add_argument("--frames", type=int, default=40)
    ap.add_argument("--fps", type=int, default=16)
    ap.add_argument("--petals", type=int, default=48, help="nombre de petales")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()

    path = build(a.source, a.out, PRESETS[a.preset], a.frames, a.fps,
                 a.petals, a.seed)
    import os
    print("%s  %s  %.1f Mo  %d images" % (
        path, "x".join(map(str, PRESETS[a.preset])),
        os.path.getsize(path) / 1e6, a.frames))


if __name__ == "__main__":
    main()
