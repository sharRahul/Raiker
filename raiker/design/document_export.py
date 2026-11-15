"""DW-11 — a Design document as a Word document: one section per frame.

BUG-348 left document formats as the remaining DW-11 gap after the slide deck
(FIXED-1486). A document is the form a design is handed over in when someone
will edit the words around it, so each frame becomes a heading (its name), the
frame drawn by the same raster renderer PNG, PDF and the deck use (so the
picture shows exactly what Check measured), and then every visible text layer
as an ordinary paragraph, in layer order. Those paragraphs are real, editable
text — the part of a design people most often need to change — while the
picture stays the faithful record of the layout.

Plain Office Open XML written here, with no new dependency: a document part,
its relationships, one style part (Title, Heading 1, Normal and Caption) and the
core properties. The picture's description carries the frame's words for a
screen reader. The stored document stays the editable design source.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Callable, Mapping, Sequence
from typing import Any
from xml.sax.saxutils import escape

#: A document of a large design stays bounded, like the deck.
MAX_FRAMES = 60
#: English Metric Units per CSS pixel (914400 per inch at 96 px per inch).
EMU_PER_PX = 9525
#: Letter page, one-inch margins: the picture fits 6.5 by 8 inches.
_MAX_W = 6 * 914400 + 457200
_MAX_H = 8 * 914400

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"

#: Characters XML 1.0 cannot carry at all; a layer's text never breaks the file.
_FORBIDDEN = {code for code in range(0x20) if code not in (0x09, 0x0A, 0x0D)}


def _clean(text: str) -> str:
    return escape("".join(ch for ch in text if ord(ch) not in _FORBIDDEN))


def frame_paragraphs(frame: Mapping[str, Any]) -> list[str]:
    """Every visible text layer's words, one entry per layer, in layer order."""
    found: list[str] = []

    def walk(nodes: Sequence[Mapping[str, Any]]) -> None:
        for node in nodes:
            if node.get("hidden"):
                continue
            if node.get("type") == "text":
                words = " ".join(str(node.get("text") or "").split())
                if words:
                    found.append(words[:4000])
            children = node.get("children")
            if isinstance(children, list):
                walk(children)

    nodes = frame.get("nodes")
    walk(nodes if isinstance(nodes, list) else [])
    return found


def _fit(width: int, height: int) -> tuple[int, int]:
    """The picture's size on the page in EMU: the whole frame, aspect kept."""
    w = max(1, width) * EMU_PER_PX
    h = max(1, height) * EMU_PER_PX
    scale = min(1.0, _MAX_W / w, _MAX_H / h)
    return int(w * scale), int(h * scale)


def _paragraph(text: str, style: str | None = None) -> str:
    props = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f'<w:p>{props}<w:r><w:t xml:space="preserve">{_clean(text)}</w:t></w:r></w:p>'


def _picture(index: int, name: str, alt: str, size: tuple[int, int]) -> str:
    cx, cy = size
    return (
        "<w:p><w:pPr><w:jc w:val=\"center\"/></w:pPr><w:r><w:drawing>"
        f'<wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
        f'<wp:docPr id="{index}" name="{_clean(name)}" descr="{_clean(alt)}"/>'
        f'<a:graphic xmlns:a="{_A}"><a:graphicData uri="{_PIC}">'
        f'<pic:pic xmlns:pic="{_PIC}"><pic:nvPicPr><pic:cNvPr id="{index}" name="{_clean(name)}" descr="{_clean(alt)}"/>'
        "<pic:cNvPicPr/></pic:nvPicPr>"
        f'<pic:blipFill><a:blip r:embed="rIdImg{index}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
        "</a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>"
    )


_STYLES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<w:styles xmlns:w="{_W}">'
    '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Inter" w:hAnsi="Inter" w:cs="Inter"/>'
    '<w:sz w:val="22"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="120"/></w:pPr>'
    "</w:pPrDefault></w:docDefaults>"
    '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
    '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/>'
    '<w:pPr><w:spacing w:after="240"/></w:pPr><w:rPr><w:b/><w:sz w:val="44"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/>'
    '<w:next w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr>'
    '<w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="caption"/><w:basedOn w:val="Normal"/>'
    '<w:rPr><w:i/><w:color w:val="686761"/><w:sz w:val="18"/></w:rPr></w:style>'
    "</w:styles>"
)


def build_docx(
    frames: Sequence[Mapping[str, Any]],
    render_png: Callable[[str], tuple[bytes, int, int]],
    *,
    title: str = "Raiker design",
) -> bytes:
    """One section per frame. ``render_png(frame_id)`` returns ``(png, width, height)``."""
    chosen = [frame for frame in frames if frame.get("id")][:MAX_FRAMES]
    if not chosen:
        raise ValueError("design_document_has_no_frames")
    rendered = [(frame, *render_png(str(frame["id"]))) for frame in chosen]

    body: list[str] = [_paragraph(title[:200] or "Raiker design", "Title")]
    rels = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        f'<Relationships xmlns="{_PKG_REL}">',
        f'<Relationship Id="rIdStyles" Type="{_REL}/styles" Target="styles.xml"/>',
    ]
    for index, (frame, _png, width, height) in enumerate(rendered, start=1):
        name = str(frame.get("name") or f"Frame {index}")[:120]
        words = frame_paragraphs(frame)
        if index > 1:
            body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
        body.append(_paragraph(name, "Heading1"))
        body.append(_picture(index, name, " · ".join(words)[:2000] or name, _fit(width, height)))
        body.append(_paragraph(f"{name} · {width} × {height} px", "Caption"))
        body.extend(_paragraph(text) for text in words)
        rels.append(f'<Relationship Id="rIdImg{index}" Type="{_REL}/image" Target="media/frame{index}.png"/>')
    rels.append("</Relationships>")
    body.append(
        '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/>'
        "</w:sectPr>"
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{_W}" xmlns:r="{_R}" xmlns:wp="{_WP}" xmlns:a="{_A}" xmlns:pic="{_PIC}">'
        f"<w:body>{''.join(body)}</w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="png" ContentType="image/png"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        '<Override PartName="/docProps/core.xml" '
        'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        "</Types>"
    )
    core = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f"<dc:title>{_clean(title[:200])}</dc:title><dc:creator>Raiker</dc:creator>"
        "</cp:coreProperties>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml", content_types)
        package.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="{_PKG_REL}">'
            f'<Relationship Id="rId1" Type="{_REL}/officeDocument" Target="word/document.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/'
            'metadata/core-properties" Target="docProps/core.xml"/>'
            "</Relationships>",
        )
        package.writestr("docProps/core.xml", core)
        package.writestr("word/document.xml", document)
        package.writestr("word/styles.xml", _STYLES)
        package.writestr("word/_rels/document.xml.rels", "".join(rels))
        for index, (_frame, png, _width, _height) in enumerate(rendered, start=1):
            package.writestr(f"word/media/frame{index}.png", png)
    return buffer.getvalue()
