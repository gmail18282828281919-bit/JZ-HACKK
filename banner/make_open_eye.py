#!/usr/bin/env python3
"""Fabrique la version « les deux yeux ouverts » de l'illustration.

Le personnage fait un clin d'oeil : un oeil est ferme. Pour pouvoir l'ouvrir
en cours d'animation, il faut une deuxieme image ou il est ouvert. On la
fabrique en recopiant l'oeil valide, en le retournant, puis en le posant a
l'emplacement de l'oeil ferme avec un masque a bords doux.

    python3 banner/make_open_eye.py banner/source.png -o banner/source-open.png
"""
import argparse

from PIL import Image, ImageDraw, ImageFilter

# Reperes mesures sur l'illustration d'origine (1983 x 793).
EYE_BOX = (495, 335, 650, 485)     # boite de l'oeil ouvert
TARGET = (786, 405)                # centre vise pour l'oeil recree
SCALE = 0.84                       # il est vu de plus loin, donc plus petit
ROT = -8.0                         # inclinaison du visage


def build(src, out, box=EYE_BOX, target=TARGET, scale=SCALE, rot=ROT):
    im = Image.open(src).convert("RGB")
    k = im.width / 1983.0           # les reperes sont donnes en 1983 px de large
    box = tuple(v * k for v in box)
    target = (target[0] * k, target[1] * k)

    patch = im.crop(tuple(int(v) for v in box)).transpose(Image.FLIP_LEFT_RIGHT)
    w, h = patch.size

    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).ellipse((w * 0.06, h * 0.10, w * 0.94, h * 0.92), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(w * 0.07))

    size = (max(int(w * scale), 1), max(int(h * scale), 1))
    patch = patch.resize(size, Image.LANCZOS)
    mask = mask.resize(size, Image.LANCZOS)
    patch = patch.rotate(rot, expand=True, resample=Image.BICUBIC)
    mask = mask.rotate(rot, expand=True, resample=Image.BICUBIC)

    im.paste(patch, (int(target[0] - patch.width / 2),
                     int(target[1] - patch.height / 2)), mask)
    im.save(out)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source")
    ap.add_argument("-o", "--out", default="source-open.png")
    ap.add_argument("--scale", type=float, default=SCALE)
    ap.add_argument("--rot", type=float, default=ROT)
    ap.add_argument("--x", type=float, default=TARGET[0])
    ap.add_argument("--y", type=float, default=TARGET[1])
    a = ap.parse_args()
    print(build(a.source, a.out, EYE_BOX, (a.x, a.y), a.scale, a.rot))


if __name__ == "__main__":
    main()
