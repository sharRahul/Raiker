# SPDX-License-Identifier: Apache-2.0
"""Draw the desktop installers' artwork into ``desktop/build-resources/``.

The installers show the same brand as the app's Setup window
(``desktop/static/shell.css``): the open-ring mark, Inter, and the Quiet UI
palette (QUI-V01), on flat grounds. The images are committed; run this only to change
them::

    pip install pillow fonttools brotli
    python scripts/render_brand_icons.py   # the mark it places
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
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "desktop" / "build-resources"
ICON = ROOT / "raiker" / "assets" / "raiker-icon.png"
INTER = ROOT / "desktop" / "static" / "fonts" / "inter-latin.woff2"

INK = (28, 28, 26)
INK_2 = (27, 27, 27)
PAPER = (247, 246, 242)
GOLD = (184, 135, 27)
STEEL = (47, 111, 143)
TEXT_LIGHT = (244, 241, 234)
TEXT_MUTED = (183, 180, 172)
TEXT_DARK = (28, 28, 26)
TEXT_DARK_MUTED = (104, 103, 97)


def inter(size: int, weight: int) -> ImageFont.FreeTypeFont:
    font = TTFont(str(INTER))
    font.flavor = None
    data = io.BytesIO()
    font.save(data)
    data.seek(0)
    face = ImageFont.truetype(data, size)
    face.set_variation_by_axes([weight])
    return face


def mark(size: int) -> Image.Image:
    return Image.open(ICON).convert("RGBA").resize((size, size), Image.LANCZOS)


def sidebar() -> Image.Image:
    scale = 3  # drawn large, reduced once, so edges and text stay crisp
    w, h = 164 * scale, 314 * scale
    image = Image.new("RGB", (w, h), INK)
    draw = ImageDraw.Draw(image)
    icon = mark(72 * scale)
    image.paste(icon, ((w - icon.width) // 2, 64 * scale), icon)
    title = inter(24 * scale, 650)
    draw.text((w // 2, 160 * scale), "raiker", font=title, fill=TEXT_LIGHT, anchor="mm")
    sub = inter(9 * scale, 600)
    for index, line in enumerate(("Your private AI assistant", "and governed agent")):
        draw.text((w // 2, (186 + index * 13) * scale), line, font=sub, fill=TEXT_MUTED, anchor="mm")
    return image.resize((164, 314), Image.LANCZOS)


def header() -> Image.Image:
    scale = 3
    w, h = 150 * scale, 57 * scale
    image = Image.new("RGB", (w, h), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    icon = mark(34 * scale)
    image.paste(icon, (w - icon.width - 10 * scale, (h - icon.height) // 2), icon)
    draw.text((w - icon.width - 18 * scale, h // 2), "raiker", font=inter(15 * scale, 650), fill=TEXT_DARK, anchor="rm")
    return image.resize((150, 57), Image.LANCZOS)


def dmg_background(scale: int) -> Image.Image:
    w, h = 540 * scale, 380 * scale
    image = Image.new("RGB", (w, h), PAPER)
    draw = ImageDraw.Draw(image)
    draw.text((w // 2, 56 * scale), "Install Raiker", font=inter(22 * scale, 800), fill=TEXT_DARK, anchor="mm")
    draw.text(
        (w // 2, 84 * scale), "Drag Raiker onto Applications. It finishes setting up when you open it.",
        font=inter(11 * scale, 500), fill=TEXT_DARK_MUTED, anchor="mm",
    )
    # The arrow between the two icons electron-builder places at y=200.
    y = 200 * scale
    draw.line((222 * scale, y, 312 * scale, y), fill=STEEL, width=3 * scale)
    draw.polygon(
        [(318 * scale, y), (306 * scale, y - 8 * scale), (306 * scale, y + 8 * scale)], fill=STEEL,
    )
    draw.text(
        (w // 2, 338 * scale), "Raiker keeps your data on this Mac. Nothing is sent anywhere during setup.",
        font=inter(10 * scale, 500), fill=TEXT_DARK_MUTED, anchor="mm",
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
