#!/usr/bin/env python3
"""Generate the full-i3 GRUB artwork and small boot-font subsets."""
from math import exp
from pathlib import Path
import subprocess

from PIL import Image, ImageChops, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "packages/ooonana/usr/share/ooonana/grub-ui"
FONTS = Path("/usr/share/fonts/truetype/dejavu")
REGULAR = FONTS / "DejaVuSansCondensed.ttf"
BOLD = FONTS / "DejaVuSansCondensed-Bold.ttf"


def background():
    image = Image.new("RGB", (400, 250))
    pixels = image.load()
    for y in range(image.height):
        v = y / (image.height - 1)
        for x in range(image.width):
            u = x / (image.width - 1)
            warm = .96 * exp(-(((u - .22) / .35) ** 2 + ((v - .35) / .48) ** 2))
            cool = .70 * exp(-(((u - .81) / .46) ** 2 + ((v - .80) / .72) ** 2))
            edge = 4.4 * ((u - .5) ** 2 + (v - .5) ** 2)
            pixels[x, y] = (round(12 + 31 * warm + 2 * cool - edge),
                            round(14 + 19 * warm + 9 * cool - edge),
                            round(18 + 5 * warm + 17 * cool - edge))
    image.save(OUTPUT / "backdrop.png", optimize=True)


def panel():
    # Small enough for 640x480; the theme scales this layer independently of text.
    image = Image.new("RGBA", (360, 450))
    pen = ImageDraw.Draw(image)
    for y in range(image.height):
        pen.line((0, y, image.width - 1, y), fill=(216, 222, 237, 26 - 10 * y // image.height))
    bounds = (0, 0, image.width - 1, image.height - 1)
    mask = Image.new("L", image.size)
    ImageDraw.Draw(mask).rounded_rectangle(bounds, radius=13, fill=255)
    image.putalpha(ImageChops.multiply(image.getchannel("A"), mask))
    pen.rounded_rectangle(bounds, radius=13, outline="#494b52")
    image.save(OUTPUT / "panel.png", optimize=True)


def brand():
    with Image.open(ROOT / "branding/boot-mark.png") as source:
        mark = source.convert("RGBA")
    mark = mark.crop(mark.getchannel("A").getbbox())
    mark.thumbnail((114, 74), Image.Resampling.LANCZOS)
    image = Image.new("RGBA", (240, 140))
    image.alpha_composite(mark, ((image.width - mark.width) // 2, 4))
    ImageDraw.Draw(image).text((120, 114), "Ooonana OS", font=ImageFont.truetype(str(REGULAR), 42),
                               fill="#f6f1e9", anchor="mm")
    image.save(OUTPUT / "brand.png", optimize=True)


def labels():
    heading = Image.new("RGBA", (280, 32))
    ImageDraw.Draw(heading).text((0, 15), "Choose how to start", font=ImageFont.truetype(str(BOLD), 25),
                                 fill="#f8f6f2", anchor="lm")
    heading.save(OUTPUT / "heading.png")
    Image.new("RGBA", (1, 1), "#41434b").save(OUTPUT / "divider.png")

    keys = Image.new("RGBA", (406, 58))
    pen = ImageDraw.Draw(keys)
    pen.rounded_rectangle((0, 0, 78, 57), radius=12, fill="#30323a")
    pen.rounded_rectangle((216, 0, 324, 57), radius=12, fill="#30323a")
    for x, tip, tail in ((20, 16, 32), (57, 40, 24)):
        arrow_base = tip + (7 if tip < tail else -7)
        pen.line([(x, tail), (x, tip)], fill="#dadce3", width=3)
        pen.line([(x - 7, arrow_base), (x, tip), (x + 7, arrow_base)], fill="#dadce3", width=3)
    body = ImageFont.truetype(str(REGULAR), 30)
    pen.text((96, 28), "Select", font=body, fill="#bfc2cb", anchor="lm")
    pen.text((270, 28), "Enter", font=ImageFont.truetype(str(BOLD), 28), fill="#e3e3e9", anchor="mm")
    pen.text((343, 28), "Start", font=body, fill="#bfc2cb", anchor="lm")
    keys.resize((203, 29), Image.Resampling.LANCZOS).save(OUTPUT / "controls.png")


def rows():
    selected = Image.new("RGBA", (448, 184))
    pen = ImageDraw.Draw(selected)
    pen.rounded_rectangle((0, 0, 447, 183), radius=36, fill="#403429", outline="#8b6a39", width=4)
    pen.line([(352, 72), (372, 92), (352, 112)], fill="#fbc569", width=6, joint="curve")
    selected = selected.resize((112, 46), Image.Resampling.LANCZOS)
    empty = Image.new("RGBA", selected.size)
    # Same insets in both styles keep icons and text aligned on selection.
    x_edges = (0, 17, 86, 112)
    y_edges = (0, 9, 37, 46)
    for row, names in enumerate((("nw", "n", "ne"), ("w", "c", "e"), ("sw", "s", "se"))):
        for column, name in enumerate(names):
            box = (x_edges[column], y_edges[row], x_edges[column + 1], y_edges[row + 1])
            selected.crop(box).save(OUTPUT / f"selection_{name}.png")
            empty.crop(box).save(OUTPUT / f"item_{name}.png")


def boot_fonts():
    for name, family, source, size in (("menu", "Ooonana Menu", REGULAR, 19),
                                        ("menu-selected", "Ooonana Menu", BOLD, 19),
                                        ("status", "Ooonana Status", REGULAR, 15)):
        subprocess.run(["grub-mkfont", "-n", family, "-s", str(size), "-r", "0x20-0x7e",
                        "-o", str(OUTPUT / f"{name}.pf2"), str(source)], check=True)
    copyright = Path("/usr/share/doc/fonts-dejavu-core/copyright").read_text(encoding="utf-8")
    upstream = copyright.split("\nFiles: debian/*", 1)[0].strip()
    license_text = "\n".join(line.rstrip() for line in upstream.splitlines())
    (OUTPUT / "font-license.txt").write_text(license_text + "\n", encoding="utf-8", newline="\n")


def icon(name, paths):
    image = Image.new("RGBA", (80, 80))
    pen = ImageDraw.Draw(image)
    for path in paths:
        points = [(4 * x, 4 * y) for x, y in path]
        pen.line(points, fill="#eae6e2", width=6, joint="curve")
    image.resize((20, 20), Image.Resampling.LANCZOS).save(OUTPUT / "icons" / f"ooonana-{name}.png")


background()
panel()
brand()
labels()
rows()
boot_fonts()
(OUTPUT / "icons").mkdir(exist_ok=True)
icon("live", (((3, 4), (17, 4), (17, 13), (3, 13), (3, 4)), ((10, 13), (10, 16)), ((6, 16), (14, 16))))
icon("persistent", (((7, 3), (13, 3), (13, 7), (15, 7), (15, 17), (5, 17), (5, 7), (7, 7), (7, 3)),
                    ((5, 7), (15, 7)), ((9, 11), (11, 11))))
icon("install", (((2, 12), (2, 16), (18, 16), (18, 12)), ((10, 3), (10, 12)), ((6, 8), (10, 12), (14, 8))))
icon("safe", (((10, 2), (17, 5), (16, 12), (10, 17), (4, 12), (3, 5), (10, 2)), ((7, 9), (9, 11), (13, 7))))
icon("audio", (((3, 8), (6, 8), (10, 5), (10, 15), (6, 12), (3, 12), (3, 8)),
               ((13, 7), (14, 10), (13, 13)), ((15, 4), (17, 10), (15, 16))))
icon("classic", (((2, 4), (18, 4), (18, 16), (2, 16), (2, 4)), ((5, 7), (8, 10), (5, 13)), ((10, 13), (15, 13))))
