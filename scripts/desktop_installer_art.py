"""Draw the desktop installers' artwork into ``desktop/build-resources/``.

The installers show the same brand as the app's Setup window
(``desktop/static/shell.css``): the Raiker mark, Manrope, the deep ink
background with a gold glow. The images are committed; run this only to change
them::

    pip install pillow fonttools brotli
    python scripts/desktop_installer_art.py

* ``installerSidebar.bmp`` / ``uninstallerSidebar.bmp`` — 164x314, the Windows
  installer's Welcome and Finish pages.
* ``installerHeader.bmp`` — 150x57, the top-right of every other installer page.
* ``dmg-background.png`` — 540x380 (and ``@2x``), the macOS disk image window:
  drag the app onto Applications.
"""

from __future__ import annotations

import io
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "desktop" / "build-resources"
ICON = ROOT / "raiker" / "assets" / "raiker-icon.png"
MANROPE = ROOT / "desktop" / "static" / "fonts" / "manrope-latin.woff2"

INK = (11, 13, 16)
INK_2 = (18, 22, 31)
PAPER = (248, 250, 252)
GOLD = (236, 208, 111)
STEEL = (54, 95, 125)
TEXT_LIGHT = (226, 232, 240)
TEXT_MUTED = (148, 163, 184)
TEXT_DARK = (15, 23, 42)
TEXT_DARK_MUTED = (71, 85, 105)


def manrope(size: int, weight: int) -> ImageFont.FreeTypeFont:
    font = TTFont(str(MANROPE))
    font.flavor = None
    data = io.BytesIO()
    font.save(data)
    data.seek(0)
    face = ImageFont.truetype(data, size)
    face.set_variation_by_axes([weight])
    return face


def glow(size: tuple[int, int], base: tuple[int, int, int], spots: list[tuple[float, float, float, tuple[int, int, int, int]]]) -> Image.Image:
    image = Image.new("RGB", size, base)
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for cx, cy, radius, colour in spots:
        x, y, r = cx * size[0], cy * size[1], radius * max(size)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=colour)
    layer = layer.filter(ImageFilter.GaussianBlur(max(size) * 0.18))
    image.paste(layer, (0, 0), layer)
    return image


def mark(size: int) -> Image.Image:
    return Image.open(ICON).convert("RGBA").resize((size, size), Image.LANCZOS)


def sidebar() -> Image.Image:
    scale = 3  # drawn large, reduced once, so edges and text stay crisp
    w, h = 164 * scale, 314 * scale
    image = glow((w, h), INK, [(1.0, 0.0, 0.55, (*GOLD, 70)), (0.0, 1.0, 0.6, (*STEEL, 90))])
    draw = ImageDraw.Draw(image)
    icon = mark(72 * scale)
    image.paste(icon, ((w - icon.width) // 2, 64 * scale), icon)
    title = manrope(24 * scale, 800)
    draw.text((w // 2, 160 * scale), "Raiker", font=title, fill=TEXT_LIGHT, anchor="mm")
    sub = manrope(9 * scale, 600)
    for index, line in enumerate(("Your private AI assistant", "and governed agent")):
        draw.text((w // 2, (186 + index * 13) * scale), line, font=sub, fill=TEXT_MUTED, anchor="mm")
    draw.line(((w // 2 - 14 * scale), 222 * scale, (w // 2 + 14 * scale), 222 * scale), fill=GOLD, width=2 * scale)
    return image.resize((164, 314), Image.LANCZOS)


def header() -> Image.Image:
    scale = 3
    w, h = 150 * scale, 57 * scale
    image = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    icon = mark(34 * scale)
    image.paste(icon, (w - icon.width - 10 * scale, (h - icon.height) // 2), icon)
    draw.text((w - icon.width - 18 * scale, h // 2), "Raiker", font=manrope(15 * scale, 800), fill=TEXT_DARK, anchor="rm")
    return image.resize((150, 57), Image.LANCZOS)


def dmg_background(scale: int) -> Image.Image:
    w, h = 540 * scale, 380 * scale
    image = glow((w, h), PAPER, [(1.0, 0.0, 0.5, (*GOLD, 90)), (0.0, 1.0, 0.55, (*STEEL, 40))])
    draw = ImageDraw.Draw(image)
    draw.text((w // 2, 56 * scale), "Install Raiker", font=manrope(22 * scale, 800), fill=TEXT_DARK, anchor="mm")
    draw.text(
        (w // 2, 84 * scale), "Drag Raiker onto Applications. It finishes setting up when you open it.",
        font=manrope(11 * scale, 500), fill=TEXT_DARK_MUTED, anchor="mm",
    )
    # The arrow between the two icons electron-builder places at y=200.
    y = 200 * scale
    draw.line((222 * scale, y, 312 * scale, y), fill=STEEL, width=3 * scale)
    draw.polygon(
        [(318 * scale, y), (306 * scale, y - 8 * scale), (306 * scale, y + 8 * scale)], fill=STEEL,
    )
    draw.text(
        (w // 2, 338 * scale), "Raiker keeps your data on this Mac. Nothing is sent anywhere during setup.",
        font=manrope(10 * scale, 500), fill=TEXT_DARK_MUTED, anchor="mm",
    )
    return image


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    side = sidebar()
    side.save(OUT / "installerSidebar.bmp")
    side.save(OUT / "uninstallerSidebar.bmp")
    header().save(OUT / "installerHeader.bmp")
    dmg_background(1).save(OUT / "dmg-background.png", optimize=True)
    dmg_background(2).save(OUT / "dmg-background@2x.png", optimize=True)
    for name in ("installerSidebar.bmp", "installerHeader.bmp", "dmg-background.png", "dmg-background@2x.png"):
        print(OUT / name)


if __name__ == "__main__":
    main()
