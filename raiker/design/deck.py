"""DW-11 — a Design document as a presentation: one slide per frame.

BUG-348 named presentation formats as the last missing export. A deck is the
form a design is most often shown in, so every frame of the document becomes a
slide, in document order, drawn by the same raster renderer PNG and PDF use (so
the slide shows exactly what Check measured) and placed full-bleed on a slide
sized to the first frame's aspect.

The file is plain Office Open XML written here, with no new dependency: a
presentation part, one slide master and layout, a theme, and per slide one
picture. Every frame's text is also kept as the slide's alternative text, so a
screen reader and a search over the deck still find the words. Pictures are not
editable shapes; the stored document stays the editable source, as with PNG.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Callable, Mapping, Sequence
from typing import Any
from xml.sax.saxutils import escape

#: English Metric Units per CSS pixel (914400 per inch at 96 px per inch).
EMU_PER_PX = 9525
#: PowerPoint's limits on a slide's sides, in EMU (1 inch to 56 inches).
_MIN_SIDE = 914400
_MAX_SIDE = 51206400
#: A deck of a large document stays bounded.
MAX_SLIDES = 60

_NS_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
_NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"


def _slide_size(width: float, height: float) -> tuple[int, int]:
    """The slide's size in EMU, the first frame's aspect, within PowerPoint's limits."""
    w = max(1.0, float(width)) * EMU_PER_PX
    h = max(1.0, float(height)) * EMU_PER_PX
    scale = 1.0
    if max(w, h) > _MAX_SIDE:
        scale = _MAX_SIDE / max(w, h)
    if min(w, h) * scale < _MIN_SIDE:
        scale = _MIN_SIDE / min(w, h)
    return int(min(_MAX_SIDE, w * scale)), int(min(_MAX_SIDE, h * scale))


def frame_text(frame: Mapping[str, Any]) -> str:
    """Every text layer's words in the frame, in layer order, for alternative text."""
    words: list[str] = []

    def walk(nodes: Sequence[Mapping[str, Any]]) -> None:
        for node in nodes:
            if node.get("hidden"):
                continue
            if node.get("type") == "text" and str(node.get("text") or "").strip():
                words.append(" ".join(str(node["text"]).split()))
            children = node.get("children")
            if isinstance(children, list):
                walk(children)

    nodes = frame.get("nodes")
    walk(nodes if isinstance(nodes, list) else [])
    return " · ".join(words)[:2000]


def _fit(image_w: int, image_h: int, slide_w: int, slide_h: int) -> tuple[int, int, int, int]:
    """The picture's offset and size: the whole frame visible, centred, aspect kept."""
    scale = min(slide_w / max(1, image_w), slide_h / max(1, image_h))
    w, h = int(image_w * scale), int(image_h * scale)
    return (slide_w - w) // 2, (slide_h - h) // 2, w, h


def _slide_xml(index: int, name: str, alt: str, box: tuple[int, int, int, int]) -> str:
    x, y, w, h = box
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<p:sld xmlns:a="{_NS_A}" xmlns:r="{_NS_R}" xmlns:p="{_NS_P}">'
        "<p:cSld><p:spTree>"
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
        '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        "<p:pic><p:nvPicPr>"
        f'<p:cNvPr id="2" name="{escape(name, {chr(34): "&quot;"})}" descr="{escape(alt, {chr(34): "&quot;"})}"/>'
        '<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
        f'<p:blipFill><a:blip r:embed="rId2"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
        f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{w}" cy="{h}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>'
        "</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>"
    )


def _slide_rels(index: int) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{_PKG_REL}">'
        f'<Relationship Id="rId1" Type="{_REL}/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
        f'<Relationship Id="rId2" Type="{_REL}/image" Target="../media/frame{index}.png"/>'
        "</Relationships>"
    )


_THEME = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<a:theme xmlns:a="{_NS_A}" name="Raiker">'
    "<a:themeElements>"
    '<a:clrScheme name="Raiker">'
    '<a:dk1><a:srgbClr val="1A1A1A"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>'
    '<a:dk2><a:srgbClr val="333333"/></a:dk2><a:lt2><a:srgbClr val="F2F2F2"/></a:lt2>'
    '<a:accent1><a:srgbClr val="3B5BDB"/></a:accent1><a:accent2><a:srgbClr val="2B8A3E"/></a:accent2>'
    '<a:accent3><a:srgbClr val="E67700"/></a:accent3><a:accent4><a:srgbClr val="C92A2A"/></a:accent4>'
    '<a:accent5><a:srgbClr val="5F3DC4"/></a:accent5><a:accent6><a:srgbClr val="0B7285"/></a:accent6>'
    '<a:hlink><a:srgbClr val="3B5BDB"/></a:hlink><a:folHlink><a:srgbClr val="5F3DC4"/></a:folHlink>'
    "</a:clrScheme>"
    '<a:fontScheme name="Raiker"><a:majorFont><a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>'
    '<a:minorFont><a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont></a:fontScheme>'
    '<a:fmtScheme name="Raiker"><a:fillStyleLst>'
    '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
    '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>'
    '<a:lnStyleLst><a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>'
    '<a:ln w="12700"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>'
    '<a:ln w="19050"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst>'
    "<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle>"
    "<a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>"
    '<a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
    '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
    "</a:bgFillStyleLst></a:fmtScheme></a:themeElements></a:theme>"
)

_EMPTY_TREE = (
    '<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
    '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
    '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree>'
)

_MASTER = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<p:sldMaster xmlns:a="{_NS_A}" xmlns:r="{_NS_R}" xmlns:p="{_NS_P}">'
    f'<p:cSld><p:bg><p:bgRef idx="1001"><a:schemeClr val="bg1"/></p:bgRef></p:bg>{_EMPTY_TREE}</p:cSld>'
    '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" '
    'accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
    '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>'
    "</p:sldMaster>"
)

_LAYOUT = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<p:sldLayout xmlns:a="{_NS_A}" xmlns:r="{_NS_R}" xmlns:p="{_NS_P}" type="blank" preserve="1">'
    f'<p:cSld name="Blank">{_EMPTY_TREE}</p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>'
)


def build_pptx(
    frames: Sequence[Mapping[str, Any]],
    render_png: Callable[[str], tuple[bytes, int, int]],
    *,
    title: str = "Raiker design",
) -> bytes:
    """One slide per frame. ``render_png(frame_id)`` returns ``(png, width, height)``."""
    chosen = [frame for frame in frames if frame.get("id")][:MAX_SLIDES]
    if not chosen:
        raise ValueError("design_deck_has_no_frames")
    first = chosen[0]
    slide_w, slide_h = _slide_size(float(first.get("width") or 1280), float(first.get("height") or 720))
    rendered = [(frame, *render_png(str(frame["id"]))) for frame in chosen]

    content_types = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
        '<Default Extension="png" ContentType="image/png"/>',
        '<Override PartName="/ppt/presentation.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>',
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>',
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>',
        '<Override PartName="/ppt/theme/theme1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>',
        '<Override PartName="/docProps/core.xml" '
        'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
    ]
    for index in range(1, len(rendered) + 1):
        content_types.append(
            f'<Override PartName="/ppt/slides/slide{index}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        )
    content_types.append("</Types>")

    slide_ids = "".join(
        f'<p:sldId id="{255 + index}" r:id="rId{index + 1}"/>' for index in range(1, len(rendered) + 1)
    )
    presentation = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<p:presentation xmlns:a="{_NS_A}" xmlns:r="{_NS_R}" xmlns:p="{_NS_P}" saveSubsetFonts="1">'
        '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
        f"<p:sldIdLst>{slide_ids}</p:sldIdLst>"
        f'<p:sldSz cx="{slide_w}" cy="{slide_h}"/><p:notesSz cx="6858000" cy="9144000"/>'
        "</p:presentation>"
    )
    presentation_rels = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        f'<Relationships xmlns="{_PKG_REL}">',
        f'<Relationship Id="rId1" Type="{_REL}/slideMaster" Target="slideMasters/slideMaster1.xml"/>',
    ]
    for index in range(1, len(rendered) + 1):
        presentation_rels.append(
            f'<Relationship Id="rId{index + 1}" Type="{_REL}/slide" Target="slides/slide{index}.xml"/>'
        )
    theme_rel = len(rendered) + 2
    presentation_rels.append(f'<Relationship Id="rId{theme_rel}" Type="{_REL}/theme" Target="theme/theme1.xml"/>')
    presentation_rels.append("</Relationships>")

    core = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f"<dc:title>{escape(title[:200])}</dc:title><dc:creator>Raiker</dc:creator>"
        "</cp:coreProperties>"
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml", "".join(content_types))
        package.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="{_PKG_REL}">'
            f'<Relationship Id="rId1" Type="{_REL}/officeDocument" Target="ppt/presentation.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/'
            'metadata/core-properties" Target="docProps/core.xml"/>'
            "</Relationships>",
        )
        package.writestr("docProps/core.xml", core)
        package.writestr("ppt/presentation.xml", presentation)
        package.writestr("ppt/_rels/presentation.xml.rels", "".join(presentation_rels))
        package.writestr("ppt/theme/theme1.xml", _THEME)
        package.writestr("ppt/slideMasters/slideMaster1.xml", _MASTER)
        package.writestr(
            "ppt/slideMasters/_rels/slideMaster1.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="{_PKG_REL}">'
            f'<Relationship Id="rId1" Type="{_REL}/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
            f'<Relationship Id="rId2" Type="{_REL}/theme" Target="../theme/theme1.xml"/>'
            "</Relationships>",
        )
        package.writestr("ppt/slideLayouts/slideLayout1.xml", _LAYOUT)
        package.writestr(
            "ppt/slideLayouts/_rels/slideLayout1.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="{_PKG_REL}">'
            f'<Relationship Id="rId1" Type="{_REL}/slideMaster" Target="../slideMasters/slideMaster1.xml"/>'
            "</Relationships>",
        )
        for index, (frame, png, width, height) in enumerate(rendered, start=1):
            name = str(frame.get("name") or f"Frame {index}")[:120]
            package.writestr(f"ppt/media/frame{index}.png", png)
            package.writestr(
                f"ppt/slides/slide{index}.xml",
                _slide_xml(index, name, frame_text(frame) or name, _fit(width, height, slide_w, slide_h)),
            )
            package.writestr(f"ppt/slides/_rels/slide{index}.xml.rels", _slide_rels(index))
    return buffer.getvalue()
