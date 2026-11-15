"""DW-11 — a vector PDF page: shapes stay paths, text stays selectable text.

The raster PDF (:func:`raiker.design.render.encode_raster`) is a picture of the
frame. This one is drawn with PDF's own operators, so it stays sharp at any
zoom and its text can be selected and searched:

* rectangles (with their corner radius) and ellipses are filled and stroked
  paths; opacity is a graphics state, rotation a transform about the centre;
* text is real text in the same font the raster export uses — the TrueType
  file is embedded, so the page looks the same on a machine without it — and
  wrapped by :func:`~raiker.design.render.wrap_text`, so a line breaks where
  the PNG breaks it and where Check measured it. Bold is drawn the way the PNG
  draws it (a thin outline), not by substituting another file;
* a placed picture is embedded at twice its box's size after its crop and fit,
  the one part of the page that is pixels because the asset itself is.

Since 2026-11-19 (BUG-348 DW-11) text is written in any script the embedded
font covers: the TrueType file is a composite (``Type0``, ``Identity-H``) font,
each character is its glyph id read from the file's own ``cmap`` table, and a
``ToUnicode`` map keeps the words selectable and searchable. A character the
font has no glyph for is counted, so the export can say so. Only a host with no
TrueType file falls back to Helvetica and Windows-1252, writing ``?`` for the rest.
"""

from __future__ import annotations

import io
import math
import struct
import zlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from PIL import Image, ImageFont

from raiker.design.document import CONTAINER_TYPES, find_frame
from raiker.design.render import AssetLoader, _fit_image, _font, raster_font_name, wrap_text

#: CSS pixels to PDF points: a 794-pixel A4 frame is a 595-point A4 page.
PT = 0.75
_KAPPA = 0.5522847498
_FIRST, _LAST = 32, 255


def _num(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def _rgb(color: str) -> tuple[float, float, float, float]:
    value = color.lstrip("#")
    alpha = int(value[6:8], 16) / 255 if len(value) == 8 else 1.0
    return int(value[0:2], 16) / 255, int(value[2:4], 16) / 255, int(value[4:6], 16) / 255, alpha


def _encode(text: str) -> tuple[bytes, int]:
    """*text* as Windows-1252 PDF string bytes, and how many characters became ``?``."""
    out = bytearray()
    lost = 0
    for ch in text:
        try:
            byte = ch.encode("cp1252")
        except UnicodeEncodeError:
            byte, lost = b"?", lost + 1
        if byte in (b"(", b")", b"\\"):
            out += b"\\" + byte
        elif byte[0] < 32:
            out += b" "
        else:
            out += byte
    return bytes(out), lost


class _Page:
    def __init__(self, height: float) -> None:
        self.height = height
        self.ops: list[str] = []
        self.states: dict[float, str] = {}
        self.images: list[tuple[str, Image.Image]] = []
        self.lost = 0
        #: Code point → glyph id of the embedded font; empty writes Windows-1252.
        self.cmap: dict[int, int] = {}
        #: Glyph id → the character it was written for (for ToUnicode and widths).
        self.used: dict[int, str] = {}

    def glyphs(self, text: str) -> str:
        """*text* as a hex string of two-byte glyph ids, counting characters with no glyph."""
        out: list[str] = []
        for ch in text:
            gid = self.cmap.get(ord(ch), 0)
            if gid == 0:
                self.lost += 1
            else:
                self.used.setdefault(gid, ch)
            out.append(f"{gid:04X}")
        return "".join(out)

    def y(self, value: float) -> float:
        return (self.height - value) * PT

    def state(self, alpha: float) -> str | None:
        alpha = round(max(0.0, min(1.0, alpha)), 3)
        if alpha >= 1:
            return None
        return self.states.setdefault(alpha, f"GS{len(self.states) + 1}")

    def paint(self, fill: str | None, stroke: str | None, stroke_width: float, opacity: float) -> str | None:
        """Set colours and the alpha state; the path operator that paints, or ``None`` for nothing."""
        fill_alpha = stroke_alpha = 0.0
        if fill:
            r, g, b, fill_alpha = _rgb(fill)
            self.ops.append(f"{_num(r)} {_num(g)} {_num(b)} rg")
        if stroke and stroke_width > 0:
            r, g, b, stroke_alpha = _rgb(stroke)
            self.ops.append(f"{_num(r)} {_num(g)} {_num(b)} RG {_num(stroke_width * PT)} w")
        alpha = max(fill_alpha, stroke_alpha) * opacity
        name = self.state(alpha)
        if name:
            self.ops.append(f"/{name} gs")
        if fill and stroke and stroke_width > 0:
            return "B"
        if fill:
            return "f"
        if stroke and stroke_width > 0:
            return "S"
        return None


def _box_path(kind: str, x: float, y: float, w: float, h: float, radius: float, page: _Page) -> str:
    left, right = x * PT, (x + w) * PT
    top, bottom = page.y(y), page.y(y + h)
    if kind == "ellipse":
        cx, cy, rx, ry = (left + right) / 2, (top + bottom) / 2, (right - left) / 2, (top - bottom) / 2
        kx, ky = rx * _KAPPA, ry * _KAPPA
        return (
            f"{_num(cx + rx)} {_num(cy)} m "
            f"{_num(cx + rx)} {_num(cy + ky)} {_num(cx + kx)} {_num(cy + ry)} {_num(cx)} {_num(cy + ry)} c "
            f"{_num(cx - kx)} {_num(cy + ry)} {_num(cx - rx)} {_num(cy + ky)} {_num(cx - rx)} {_num(cy)} c "
            f"{_num(cx - rx)} {_num(cy - ky)} {_num(cx - kx)} {_num(cy - ry)} {_num(cx)} {_num(cy - ry)} c "
            f"{_num(cx + kx)} {_num(cy - ry)} {_num(cx + rx)} {_num(cy - ky)} {_num(cx + rx)} {_num(cy)} c h"
        )
    r = min(radius * PT, (right - left) / 2, (top - bottom) / 2)
    if r <= 0:
        return f"{_num(left)} {_num(bottom)} {_num(right - left)} {_num(top - bottom)} re"
    k = r * _KAPPA
    return (
        f"{_num(left + r)} {_num(top)} m {_num(right - r)} {_num(top)} l "
        f"{_num(right - r + k)} {_num(top)} {_num(right)} {_num(top - r + k)} {_num(right)} {_num(top - r)} c "
        f"{_num(right)} {_num(bottom + r)} l "
        f"{_num(right)} {_num(bottom + r - k)} {_num(right - r + k)} {_num(bottom)} {_num(right - r)} {_num(bottom)} c "
        f"{_num(left + r)} {_num(bottom)} l "
        f"{_num(left + r - k)} {_num(bottom)} {_num(left)} {_num(bottom + r - k)} {_num(left)} {_num(bottom + r)} c "
        f"{_num(left)} {_num(top - r)} l "
        f"{_num(left)} {_num(top - r + k)} {_num(left + r - k)} {_num(top)} {_num(left + r)} {_num(top)} c h"
    )


def _draw(page: _Page, node: Mapping[str, Any], load: AssetLoader) -> None:
    if not node.get("visible", True):
        return
    x, y, w, h = (float(node[k]) for k in ("x", "y", "w", "h"))
    kind = node["type"]
    page.ops.append("q")
    if node.get("rotation"):
        # PDF's y axis points up, so a clockwise canvas rotation is negative here.
        angle = math.radians(-float(node["rotation"]))
        cx, cy = (x + w / 2) * PT, page.y(y + h / 2)
        cos, sin = math.cos(angle), math.sin(angle)
        page.ops.append(
            f"{_num(cos)} {_num(sin)} {_num(-sin)} {_num(cos)} "
            f"{_num(cx - cos * cx + sin * cy)} {_num(cy - sin * cx - cos * cy)} cm"
        )
    opacity = float(node.get("opacity", 1))
    if kind in CONTAINER_TYPES:
        if kind == "stack" and (node.get("fill") or node.get("stroke")):
            paint = page.paint(node.get("fill"), node.get("stroke"), float(node.get("stroke_width") or 0), opacity)
            if paint:
                page.ops.append(f"{_box_path('rect', x, y, w, h, float(node.get('radius') or 0), page)} {paint}")
        for child in node.get("children") or []:
            _draw(page, child, load)
    elif kind in ("rect", "ellipse"):
        paint = page.paint(node.get("fill"), node.get("stroke"), float(node.get("stroke_width") or 0), opacity)
        if paint:
            page.ops.append(f"{_box_path(kind, x, y, w, h, float(node.get('radius') or 0), page)} {paint}")
    elif kind == "text":
        _text(page, node, x, y, w, opacity)
    elif kind == "image":
        asset = load(str(node["asset_id"])) if node.get("asset_id") else None
        if asset is None:
            page.paint("#eeeeee", "#999999", 1, 1)
            page.ops.append(f"{_box_path('rect', x, y, w, h, 0, page)} B")
        else:
            with Image.open(io.BytesIO(asset[1])) as opened:
                picture = _fit_image(opened.convert("RGBA"), node, (max(1, round(w * 2)), max(1, round(h * 2))))
            name = f"Im{len(page.images) + 1}"
            page.images.append((name, picture))
            state = page.state(opacity)
            if state:
                page.ops.append(f"/{state} gs")
            page.ops.append(f"{_num(w * PT)} 0 0 {_num(h * PT)} {_num(x * PT)} {_num(page.y(y + h))} cm /{name} Do")
    page.ops.append("Q")


def _text(page: _Page, node: Mapping[str, Any], x: float, y: float, w: float, opacity: float) -> None:
    size = float(node["font_size"])
    font = _font(size)
    r, g, b, alpha = _rgb(str(node.get("color") or "#000000"))
    page.ops.append(f"{_num(r)} {_num(g)} {_num(b)} rg {_num(r)} {_num(g)} {_num(b)} RG")
    state = page.state(alpha * opacity)
    if state:
        page.ops.append(f"/{state} gs")
    bold = int(node.get("font_weight") or 400) >= 600
    page.ops.append(f"BT /F1 {_num(size * PT)} Tf " + (f"2 Tr {_num(size * PT * 0.03)} w" if bold else "0 Tr"))
    for index, line in enumerate(wrap_text(str(node.get("text") or ""), size, w)):
        length = font.getlength(line)
        left = {"left": x, "center": x + (w - length) / 2, "right": x + w - length}[node["align"]]
        # The raster export draws from the line's top; its baseline sits at the
        # font's ascent below that, which this matches.
        baseline = y + index * size * float(node["line_height"]) + _ascent(size)
        position = f"1 0 0 1 {_num(left * PT)} {_num(page.y(baseline))} Tm "
        if page.cmap:
            page.ops.append(position + "<" + page.glyphs(line) + "> Tj")
            continue
        encoded, lost = _encode(line)
        page.lost += lost
        page.ops.append(position + "(" + encoded.decode("latin-1") + ") Tj")
    page.ops.append("ET")


def _ascent(size: float) -> float:
    font = _font(size)
    metrics = getattr(font, "getmetrics", None)
    return float(metrics()[0]) if metrics else size * 0.8


def read_cmap(font: bytes) -> dict[int, int]:
    """Code point → glyph id from a TrueType file's ``cmap`` (formats 12 and 4).

    Read here rather than through a font library: these two formats are what
    every Unicode TrueType font carries, and anything unexpected reads as an
    empty map, which only means the page falls back to Windows-1252.
    """
    try:
        count = struct.unpack_from(">H", font, 4)[0]
        tables = {}
        for index in range(count):
            tag, _check, offset, _length = struct.unpack_from(">4sIII", font, 12 + index * 16)
            tables[tag] = offset
        base = tables[b"cmap"]
        subtables = struct.unpack_from(">H", font, base + 2)[0]
        found: dict[tuple[int, int], int] = {}
        for index in range(subtables):
            platform, encoding, offset = struct.unpack_from(">HHI", font, base + 4 + index * 8)
            found[(platform, encoding)] = base + offset
        mapping: dict[int, int] = {}
        for key in ((3, 10), (0, 4), (0, 6)):
            if key in found and struct.unpack_from(">H", font, found[key])[0] == 12:
                start = found[key]
                groups = struct.unpack_from(">I", font, start + 12)[0]
                for group in range(groups):
                    first, last, gid = struct.unpack_from(">III", font, start + 16 + group * 12)
                    for offset_code in range(min(last - first + 1, 0x110000)):
                        mapping[first + offset_code] = gid + offset_code
                return mapping
        for key in ((3, 1), (0, 3), (0, 1), (0, 0)):
            if key not in found or struct.unpack_from(">H", font, found[key])[0] != 4:
                continue
            start = found[key]
            segments = struct.unpack_from(">H", font, start + 6)[0] // 2
            ends = struct.unpack_from(f">{segments}H", font, start + 14)
            starts = struct.unpack_from(f">{segments}H", font, start + 16 + segments * 2)
            deltas = struct.unpack_from(f">{segments}h", font, start + 16 + segments * 4)
            range_base = start + 16 + segments * 6
            offsets = struct.unpack_from(f">{segments}H", font, range_base)
            for segment in range(segments):
                for code in range(starts[segment], ends[segment] + 1):
                    if code == 0xFFFF:
                        continue
                    if offsets[segment] == 0:
                        gid = (code + deltas[segment]) & 0xFFFF
                    else:
                        at = range_base + segment * 2 + offsets[segment] + (code - starts[segment]) * 2
                        gid = struct.unpack_from(">H", font, at)[0]
                        gid = (gid + deltas[segment]) & 0xFFFF if gid else 0
                    if gid:
                        mapping[code] = gid
            return mapping
    except (KeyError, struct.error, IndexError):
        return {}
    return {}


def _to_unicode(used: Mapping[int, str]) -> bytes:
    """The CMap that maps each written glyph id back to its character."""
    lines = [
        "/CIDInit /ProcSet findresource begin 12 dict begin begincmap",
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
        "/CMapName /Adobe-Identity-UCS def /CMapType 2 def",
        "1 begincodespacerange <0000> <FFFF> endcodespacerange",
    ]
    items = sorted(used.items())
    for chunk in range(0, len(items), 100):
        block = items[chunk:chunk + 100]
        lines.append(f"{len(block)} beginbfchar")
        for gid, ch in block:
            utf16 = ch.encode("utf-16-be").hex().upper()
            lines.append(f"<{gid:04X}> <{utf16}>")
        lines.append("endbfchar")
    lines += ["endcmap CMapName currentdict /CMap defineresource pop end end"]
    return "\n".join(lines).encode("ascii")


def _host_font_file() -> bytes | None:
    name = raster_font_name()
    if name == "bundled-sans":
        return None
    candidate = getattr(ImageFont.truetype(name, 12), "path", None)
    path = str(candidate) if candidate and Path(str(candidate)).is_file() else None
    return Path(path).read_bytes() if path else None


def _font_objects() -> tuple[dict[str, bytes], bytes | None]:
    """The font dictionary entries and, when the host has a TrueType file, its bytes."""
    name = raster_font_name()
    widths: list[str] = []
    measure = _font(1000)
    for code in range(_FIRST, _LAST + 1):
        try:
            ch = bytes([code]).decode("cp1252")
        except UnicodeDecodeError:
            ch = "?"
        widths.append(str(round(measure.getlength(ch))))
    path: str | None = None
    if name != "bundled-sans":
        candidate = getattr(ImageFont.truetype(name, 12), "path", None)
        path = str(candidate) if candidate and Path(str(candidate)).is_file() else None
    base = "RaikerSans" if path else "Helvetica"
    font = {
        "Type": b"/Font", "Subtype": b"/TrueType" if path else b"/Type1", "BaseFont": f"/{base}".encode(),
        "FirstChar": str(_FIRST).encode(), "LastChar": str(_LAST).encode(),
        "Widths": ("[" + " ".join(widths) + "]").encode(), "Encoding": b"/WinAnsiEncoding",
    }
    return font, Path(path).read_bytes() if path else None


def _simple_font(add: Any, stream: Any) -> tuple[int, bytes | None]:
    """The Windows-1252 font: the host's TrueType file when it has one, else Helvetica."""
    font, font_file = _font_objects()
    font_ref = ""
    if font_file is not None:
        file_ref = stream(f"/Length1 {len(font_file)}", font_file)
        descriptor = add(
            f"<< /Type /FontDescriptor /FontName /RaikerSans /Flags 32 /FontBBox [-1021 -463 1793 1232] "
            f"/ItalicAngle 0 /Ascent 928 /Descent -236 /CapHeight 729 /StemV 80 /FontFile2 {file_ref} 0 R >>".encode()
        )
        font_ref = f" /FontDescriptor {descriptor} 0 R"
    return add(("<< " + " ".join(f"/{k} {v.decode()}" for k, v in font.items()) + font_ref + " >>").encode()), font_file


def render_pdf(document: Mapping[str, Any], frame_id: str, load: AssetLoader) -> tuple[bytes, dict[str, Any]]:
    """One frame as a one-page vector PDF, and what the export should record about it."""
    frame = find_frame(document, frame_id)
    page = _Page(float(frame["height"]))
    host_font = _host_font_file()
    page.cmap = read_cmap(host_font) if host_font is not None else {}
    width_pt, height_pt = frame["width"] * PT, frame["height"] * PT
    page.ops.append("q")
    page.paint(frame.get("background") or "#ffffff", None, 0, 1)
    page.ops.append(f"0 0 {_num(width_pt)} {_num(height_pt)} re f Q")
    for node in frame["nodes"]:
        _draw(page, node, load)

    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    def stream(dictionary: str, data: bytes) -> int:
        packed = zlib.compress(data)
        return add(f"<< {dictionary} /Filter /FlateDecode /Length {len(packed)} >>\nstream\n".encode()
                   + packed + b"\nendstream")

    font_file: bytes | None
    if page.cmap and host_font is not None:
        font_file = host_font
        file_ref = stream(f"/Length1 {len(font_file)}", font_file)
        descriptor = add(
            f"<< /Type /FontDescriptor /FontName /RaikerSans /Flags 32 /FontBBox [-1021 -463 1793 1232] "
            f"/ItalicAngle 0 /Ascent 928 /Descent -236 /CapHeight 729 /StemV 80 /FontFile2 {file_ref} 0 R >>".encode()
        )
        measure = _font(1000)
        widths = " ".join(f"{gid} [{round(measure.getlength(ch))}]" for gid, ch in sorted(page.used.items()))
        cid_font = add(
            f"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /RaikerSans "
            f"/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> "
            f"/FontDescriptor {descriptor} 0 R /DW 500 /W [{widths}] /CIDToGIDMap /Identity >>".encode()
        )
        to_unicode = stream("", _to_unicode(page.used))
        font_id = add(
            f"<< /Type /Font /Subtype /Type0 /BaseFont /RaikerSans /Encoding /Identity-H "
            f"/DescendantFonts [{cid_font} 0 R] /ToUnicode {to_unicode} 0 R >>".encode()
        )
    else:
        font_id, font_file = _simple_font(add, stream)

    xobjects = []
    for name, picture in page.images:
        rgb = picture.convert("RGB")
        jpeg = io.BytesIO()
        rgb.save(jpeg, format="JPEG", quality=90)
        mask = ""
        alpha = picture.getchannel("A")
        if alpha.getextrema() != (255, 255):
            mask_id = stream(f"/Type /XObject /Subtype /Image /Width {picture.width} /Height {picture.height} "
                             "/ColorSpace /DeviceGray /BitsPerComponent 8", alpha.tobytes())
            mask = f" /SMask {mask_id} 0 R"
        data = jpeg.getvalue()
        image_id = add(
            f"<< /Type /XObject /Subtype /Image /Width {picture.width} /Height {picture.height} "
            f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode{mask} /Length {len(data)} >>\nstream\n".encode()
            + data + b"\nendstream"
        )
        xobjects.append(f"/{name} {image_id} 0 R")

    states = " ".join(f"/{name} << /Type /ExtGState /ca {_num(alpha)} /CA {_num(alpha)} >>"
                      for alpha, name in page.states.items())
    resources = f"<< /Font << /F1 {font_id} 0 R >>"
    if xobjects:
        resources += " /XObject << " + " ".join(xobjects) + " >>"
    if states:
        resources += f" /ExtGState << {states} >>"
    resources += " >>"
    content_id = stream("", "\n".join(page.ops).encode("latin-1"))
    pages_id = len(objects) + 2
    page_id = add(f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {_num(width_pt)} {_num(height_pt)}] "
                  f"/Resources {resources} /Contents {content_id} 0 R >>".encode())
    add(f"<< /Type /Pages /Kids [{page_id} 0 R] /Count 1 >>".encode())
    title, _lost = _encode(str(frame["name"]))
    info_id = add(b"<< /Producer (Raiker Design) /Title (" + title + b") >>")
    catalog_id = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode())

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R /Info {info_id} 0 R >>\n"
              f"startxref\n{xref}\n%%EOF\n".encode())
    settings = {
        "font": raster_font_name() if font_file is not None else "Helvetica (not embedded)",
        "text_encoding": "unicode" if page.cmap and font_file is not None else "windows-1252",
        "characters_replaced": page.lost,
    }
    return out.getvalue(), settings


__all__ = ["render_pdf"]
