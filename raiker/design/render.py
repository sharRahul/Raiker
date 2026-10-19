"""DW-11 — drawing a design document: SVG, a raster page, and the text layout both share.

Two renderers read the same stored document and never write it:

* **SVG** keeps the structure — text stays ``<text>``, shapes stay shapes, and
  placed images are embedded with their crop and fit — so it remains editable
  in a vector tool. Fonts are named, not embedded: a viewer without the
  family substitutes its own.
* **Raster** (PNG, and a PDF page made from it) is drawn with Pillow in one
  sans font: the first broad one this host has (DejaVu Sans, Arial, Liberation
  Sans, Helvetica), else the small font bundled with Pillow. Which one drew an
  export is recorded with it. A family other than that sans is drawn in it, and
  a character the font has no glyph for is named by validation before export
  rather than discovered as a box in the file.

Text wrapping is :func:`wrap_text`, used by the raster renderer and by the
overflow check alike, so "this text overflows" is a statement about the export
that is about to be written rather than an estimate.
"""

from __future__ import annotations

import base64
import io
import math
from collections.abc import Callable, Mapping
from functools import lru_cache
from typing import Any
from xml.sax.saxutils import escape, quoteattr

from PIL import Image, ImageDraw, ImageFont

from raiker.design.document import CONTAINER_TYPES, find_frame

#: ``asset_id -> (media_type, bytes)`` for an owner-scoped image, or ``None``.
AssetLoader = Callable[[str], tuple[str, bytes] | None]

GENERIC_FONTS = frozenset({"sans-serif", "serif", "monospace"})
MAX_RASTER_PIXELS = 40_000_000


#: Broad sans fonts, by the file names Pillow can find in each platform's font folders.
_FONT_CANDIDATES = (
    "DejaVuSans.ttf", "arial.ttf", "Arial.ttf", "LiberationSans-Regular.ttf", "Helvetica.ttc",
)


@lru_cache(maxsize=1)
def raster_font_name() -> str:
    """The font raster exports are drawn in on this host: a file name, or ``bundled-sans``."""
    for name in _FONT_CANDIDATES:
        try:
            ImageFont.truetype(name, 12)
        except OSError:
            continue
        return name
    return "bundled-sans"


def _font(size: float) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    name = raster_font_name()
    if name != "bundled-sans":
        return ImageFont.truetype(name, max(1, round(float(size))))
    return ImageFont.load_default(size=max(1.0, float(size)))


@lru_cache(maxsize=4096)
def _has_glyph(character: str) -> bool:
    font = _font(32)
    # A character with no glyph is drawn as the font's "missing" box, which is
    # exactly what a code point no font defines draws as.
    missing = font.getmask("\U0010FFFD")
    drawn = font.getmask(character)
    return drawn.size != missing.size or bytes(drawn) != bytes(missing)


def missing_glyphs(text: str) -> list[str]:
    """Characters in *text* the raster font has no glyph for, in order, once each."""
    return list(dict.fromkeys(ch for ch in text if not ch.isspace() and not _has_glyph(ch)))


def wrap_text(text: str, font_size: float, width: float) -> list[str]:
    """Lines *text* breaks into at *width*, measured with the raster font."""
    font = _font(font_size)
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split(" ")
        line = ""
        for word in words:
            candidate = word if not line else f"{line} {word}"
            if line and font.getlength(candidate) > width:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
    return lines


def text_height(node: Mapping[str, Any]) -> float:
    """How tall a text node's wrapped text is when drawn."""
    lines = wrap_text(str(node.get("text") or ""), float(node["font_size"]), float(node["w"]))
    return len(lines) * float(node["font_size"]) * float(node["line_height"])


def _rgba(color: str | None, opacity: float = 1.0) -> tuple[int, int, int, int] | None:
    if not color:
        return None
    value = color.lstrip("#")
    alpha = int(value[6:8], 16) if len(value) == 8 else 255
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16), round(alpha * opacity))


def _visible(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [node for node in nodes if node.get("visible", True)]


# ── SVG ──────────────────────────────────────────────────────────────────


def _asset_size(data: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(data)) as image:
        return image.size


def _svg_node(node: Mapping[str, Any], load: AssetLoader, out: list[str]) -> None:
    x, y, w, h = (float(node[k]) for k in ("x", "y", "w", "h"))
    attrs = f' data-layer={quoteattr(str(node["id"]))} opacity="{node.get("opacity", 1)}"'
    if node.get("rotation"):
        attrs += f' transform="rotate({node["rotation"]} {x + w / 2:.2f} {y + h / 2:.2f})"'
    kind = node["type"]
    if kind in CONTAINER_TYPES:
        out.append(f"<g{attrs}><title>{escape(str(node['name']))}</title>")
        if kind == "stack" and (node.get("fill") or node.get("stroke")):
            out.append(_svg_box("rect", node, x, y, w, h, ""))
        for child in _visible(node.get("children") or []):
            _svg_node(child, load, out)
        out.append("</g>")
    elif kind in ("rect", "ellipse"):
        out.append(_svg_box(kind, node, x, y, w, h, attrs))
    elif kind == "text":
        size = float(node["font_size"])
        anchor = {"left": ("start", x), "center": ("middle", x + w / 2), "right": ("end", x + w)}[node["align"]]
        lines = wrap_text(str(node.get("text") or ""), size, w)
        out.append(
            f'<text{attrs} font-family={quoteattr(str(node["font_family"]))} font-size="{size}" '
            f'font-weight="{node["font_weight"]}" fill="{node.get("color") or "#000000"}" '
            f'text-anchor="{anchor[0]}">'
        )
        for index, line in enumerate(lines):
            baseline = y + size * 0.85 + index * size * float(node["line_height"])
            out.append(f'<tspan x="{anchor[1]:.2f}" y="{baseline:.2f}">{escape(line)}</tspan>')
        out.append("</text>")
    elif kind == "image":
        asset = load(str(node["asset_id"])) if node.get("asset_id") else None
        if asset is None:
            out.append(
                f'<rect{attrs} x="{x}" y="{y}" width="{w}" height="{h}" fill="#eeeeee" stroke="#999999"/>'
            )
            return
        media_type, data = asset
        natural_w, natural_h = _asset_size(data)
        crop = node.get("crop") or {"x": 0, "y": 0, "w": 1, "h": 1}
        view = (crop["x"] * natural_w, crop["y"] * natural_h, crop["w"] * natural_w, crop["h"] * natural_h)
        ratio = {"cover": "xMidYMid slice", "contain": "xMidYMid meet", "fill": "none"}[node["fit"]]
        href = f"data:{media_type};base64,{base64.b64encode(data).decode('ascii')}"
        out.append(
            f'<svg{attrs} x="{x}" y="{y}" width="{w}" height="{h}" '
            f'viewBox="{view[0]:.2f} {view[1]:.2f} {view[2]:.2f} {view[3]:.2f}" preserveAspectRatio="{ratio}">'
            f'<title>{escape(str(node.get("alt") or node["name"]))}</title>'
            f'<image width="{natural_w}" height="{natural_h}" href="{href}"/></svg>'
        )


def _svg_box(kind: str, node: Mapping[str, Any], x: float, y: float, w: float, h: float, attrs: str) -> str:
    paint = f'fill="{node.get("fill") or "none"}"'
    if node.get("stroke") and float(node.get("stroke_width") or 0) > 0:
        paint += f' stroke="{node["stroke"]}" stroke-width="{node["stroke_width"]}"'
    if kind == "ellipse":
        return f'<ellipse{attrs} cx="{x + w / 2:.2f}" cy="{y + h / 2:.2f}" rx="{w / 2:.2f}" ry="{h / 2:.2f}" {paint}/>'
    radius = float(node.get("radius") or 0)
    return f'<rect{attrs} x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" {paint}/>'


def render_svg(document: Mapping[str, Any], frame_id: str, load: AssetLoader) -> str:
    frame = find_frame(document, frame_id)
    width, height = frame["width"], frame["height"]
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        f"<title>{escape(str(frame['name']))}</title>",
        f'<rect width="{width}" height="{height}" fill="{frame.get("background") or "#ffffff"}"/>',
    ]
    for node in _visible(frame["nodes"]):
        _svg_node(node, load, out)
    out.append("</svg>")
    return "".join(out)


# ── Raster ───────────────────────────────────────────────────────────────


def _fit_image(source: Image.Image, node: Mapping[str, Any], size: tuple[int, int]) -> Image.Image:
    crop = node.get("crop")
    if crop:
        sw, sh = source.size
        source = source.crop((round(crop["x"] * sw), round(crop["y"] * sh),
                              round((crop["x"] + crop["w"]) * sw), round((crop["y"] + crop["h"]) * sh)))
    target_w, target_h = max(1, size[0]), max(1, size[1])
    if node.get("fit") == "fill":
        return source.resize((target_w, target_h))
    scale = (max if node.get("fit") == "cover" else min)(target_w / source.width, target_h / source.height)
    resized = source.resize((max(1, round(source.width * scale)), max(1, round(source.height * scale))))
    canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    canvas.paste(resized, ((target_w - resized.width) // 2, (target_h - resized.height) // 2))
    return canvas


def _draw_node(base: Image.Image, node: Mapping[str, Any], load: AssetLoader, scale: float) -> None:
    kind = node["type"]
    if kind in CONTAINER_TYPES:
        if kind == "stack" and (node.get("fill") or node.get("stroke")):
            _draw_node(base, {**node, "type": "rect"}, load, scale)
        for child in _visible(node.get("children") or []):
            _draw_node(base, child, load, scale)
        return
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    x, y, w, h = (float(node[k]) * scale for k in ("x", "y", "w", "h"))
    box = (x, y, x + max(w, 1), y + max(h, 1))
    opacity = float(node.get("opacity", 1))
    if kind in ("rect", "ellipse"):
        fill = _rgba(node.get("fill"), opacity)
        outline = _rgba(node.get("stroke"), opacity) if float(node.get("stroke_width") or 0) > 0 else None
        stroke = round(float(node.get("stroke_width") or 0) * scale)
        if kind == "ellipse":
            draw.ellipse(box, fill=fill, outline=outline, width=stroke)
        else:
            draw.rounded_rectangle(box, radius=float(node.get("radius") or 0) * scale, fill=fill,
                                   outline=outline, width=stroke)
    elif kind == "text":
        size = float(node["font_size"]) * scale
        font = _font(size)
        color = _rgba(node.get("color") or "#000000", opacity)
        bold = 1 if int(node.get("font_weight") or 400) >= 600 else 0
        for index, line in enumerate(wrap_text(str(node.get("text") or ""), float(node["font_size"]), float(node["w"]))):
            length = font.getlength(line)
            left = {"left": x, "center": x + (w - length) / 2, "right": x + w - length}[node["align"]]
            top = y + index * size * float(node["line_height"])
            draw.text((left, top), line, font=font, fill=color, stroke_width=bold, stroke_fill=color)
    elif kind == "image":
        asset = load(str(node["asset_id"])) if node.get("asset_id") else None
        if asset is None:
            draw.rectangle(box, fill=(238, 238, 238, 255), outline=(153, 153, 153, 255))
        else:
            with Image.open(io.BytesIO(asset[1])) as opened:
                picture = _fit_image(opened.convert("RGBA"), node, (round(w), round(h)))
            if opacity < 1:
                alpha = picture.getchannel("A").point(lambda value: round(value * opacity))
                picture.putalpha(alpha)
            layer.alpha_composite(picture, (round(x), round(y)))
    if node.get("rotation"):
        layer = layer.rotate(-float(node["rotation"]), center=(x + w / 2, y + h / 2), resample=Image.Resampling.BICUBIC)
    base.alpha_composite(layer)


def render_raster(document: Mapping[str, Any], frame_id: str, load: AssetLoader, *, scale: float = 1.0) -> Image.Image:
    frame = find_frame(document, frame_id)
    width, height = math.ceil(frame["width"] * scale), math.ceil(frame["height"] * scale)
    if width * height > MAX_RASTER_PIXELS:
        raise ValueError("export_too_large")
    base = Image.new("RGBA", (width, height), _rgba(frame.get("background") or "#ffffff") or (255, 255, 255, 255))
    for node in _visible(frame["nodes"]):
        _draw_node(base, node, load, scale)
    return base


def encode_raster(image: Image.Image, fmt: str) -> bytes:
    buffer = io.BytesIO()
    if fmt == "png":
        image.save(buffer, format="PNG", optimize=True)
    else:
        image.convert("RGB").save(buffer, format="PDF", resolution=96.0)
    return buffer.getvalue()


__all__ = [
    "GENERIC_FONTS", "encode_raster", "missing_glyphs", "raster_font_name", "render_raster", "render_svg",
    "text_height", "wrap_text",
]
