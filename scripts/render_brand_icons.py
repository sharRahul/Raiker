# SPDX-License-Identifier: Apache-2.0
"""Draw Raiker's icons from the open-ring mark (QUI-V04).

The mark is a rounded ring with one gap at about half past one. The browser
draws it inline from ``web/src/lib/components/Logo.svelte``; the files written
here are the places that need a picture: favicons, the web manifest's icons,
the desktop app's icon and its Setup window. The images are committed; run this
only to change them::

    pip install pillow
    python scripts/render_brand_icons.py

Drawn at 8x and reduced, so the 16 px favicon keeps a clean stroke.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "web" / "public"

ACCENT_LIGHT = (47, 111, 143)  # QUI-V01 primary action, light
ACCENT_DARK = (120, 183, 213)  # QUI-V01 primary action, dark
PAPER = (247, 246, 242)  # QUI-V01 background, light
SCALE = 8

# Geometry in the 32-unit box Logo.svelte uses: radius 11, stroke 5, round caps,
# the arc running clockwise from -13 degrees to -77 degrees (the gap between).
RADIUS, STROKE, START, END = 11.0, 5.0, -13.0, -77.0 + 360.0


def ring(size: int, colour: tuple[int, int, int], inset: float = 0.0) -> Image.Image:
    """The ring alone on a transparent ground, ``inset`` units in from each edge."""
    big = size * SCALE
    unit = big / (32 + 2 * inset)
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    centre = big / 2
    r, half = RADIUS * unit, STROKE * unit / 2
    steps = 720
    for index in range(steps + 1):
        angle = math.radians(START + (END - START) * index / steps)
        x, y = centre + r * math.cos(angle), centre + r * math.sin(angle)
        draw.ellipse((x - half, y - half, x + half, y + half), fill=colour + (255,))
    return image.resize((size, size), Image.Resampling.LANCZOS)


def tile(size: int, ground: tuple[int, int, int], colour: tuple[int, int, int]) -> Image.Image:
    """The ring on a rounded square: app icons, where a bare ring floats."""
    big = size * SCALE
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(image).rounded_rectangle((0, 0, big - 1, big - 1), radius=big * 0.225, fill=ground + (255,))
    image = image.resize((size, size), Image.Resampling.LANCZOS)
    image.alpha_composite(ring(size, colour, inset=9.0))
    return image


def main() -> None:
    for size in (16, 32):
        ring(size, ACCENT_LIGHT, inset=0.5).save(PUBLIC / f"favicon-{size}x{size}.png")
        ring(size, ACCENT_DARK, inset=0.5).save(PUBLIC / f"favicon-dark-{size}x{size}.png")
    ring(256, ACCENT_LIGHT).save(PUBLIC / "raiker-mark.png")
    ring(256, ACCENT_DARK).save(PUBLIC / "raiker-mark-dark.png")
    ring(48, ACCENT_LIGHT, inset=0.5).save(PUBLIC / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    tile(180, ACCENT_LIGHT, PAPER).save(PUBLIC / "apple-touch-icon.png")
    tile(192, ACCENT_LIGHT, PAPER).save(PUBLIC / "icon-192.png")
    tile(512, ACCENT_LIGHT, PAPER).save(PUBLIC / "icon-512.png")
    tile(512, ACCENT_LIGHT, PAPER).save(ROOT / "raiker" / "assets" / "raiker-icon.png")
    ring(192, ACCENT_LIGHT).save(ROOT / "desktop" / "static" / "raiker-mark.png")


if __name__ == "__main__":
    main()
