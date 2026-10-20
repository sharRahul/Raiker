"""DW-06 — bringing brand material into a design system, on this machine only.

Two readers, neither of which calls a model or a provider:

* :func:`parse_tokens` reads a codebase's design tokens — CSS custom properties
  (``--brand-primary: #1144aa;``) or a JSON tokens file, flat, nested or in the
  W3C design-tokens shape (``{"$value": …, "$type": "color"}``) — into the
  colours, fonts and spacing a system holds. Everything it could not place is
  returned as skipped, with the reason, so nothing is dropped silently;
* :func:`extract_palette` reads the dominant colours of a picture the owner
  already has (a screenshot, a logo) with Pillow's quantizer.

Both only *propose*: what they return fills the New design system form, and a
system exists only when the owner saves it, with a source note naming the file
and its hash.
"""

from __future__ import annotations

import io
import json
import re
from collections.abc import Mapping
from typing import Any

from PIL import Image

from raiker.design.systems import MAX_VARIABLES_PER_GROUP

MAX_TOKEN_FILE_CHARS = 200_000
MAX_SKIPPED = 40
PALETTE_SIZE = 6

_NAME = re.compile(r"^[a-z][a-z0-9_.-]{0,59}$")
_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_FONT = re.compile(r"^[A-Za-z0-9 _-]{1,80}$")
_CSS_VAR = re.compile(r"--([A-Za-z0-9_-]+)\s*:\s*([^;}{]+)")
_LENGTH = re.compile(r"^(-?\d+(?:\.\d+)?)(px)?$")
_REM = re.compile(r"^(-?\d+(?:\.\d+)?)rem$")


def _name(raw: str) -> str | None:
    """A token path as a variable name: lowercase, dashes, at most 60 characters."""
    name = re.sub(r"[^a-z0-9_.-]+", "-", raw.strip().lower()).strip("-.")
    name = re.sub(r"^(?:color|colour|colors|colours|font|fonts|font-family|space|spacing)[-.]", "", name) or name
    return name[:60] if _NAME.match(name[:60]) else None


def _hex(value: str) -> str | None:
    value = value.strip()
    if not _HEX.match(value):
        return None
    digits = value[1:]
    if len(digits) in (3, 4):
        digits = "".join(ch * 2 for ch in digits)
    return f"#{digits.lower()}"


def _font(value: str) -> str | None:
    first = value.split(",")[0].strip().strip("'\"").strip()
    return first if _FONT.match(first) else None


def _spacing(value: str) -> float | None:
    value = value.strip().lower()
    match = _LENGTH.match(value)
    if match:
        number = float(match.group(1))
    else:
        rem = _REM.match(value)
        if not rem:
            return None
        number = float(rem.group(1)) * 16
    return round(number, 2) if 0 <= number <= 2_000 else None


def _classify(path: str, value: Any, declared: str | None) -> tuple[str, Any] | str:
    """``(group, value)`` for a token, or the reason it was skipped."""
    if isinstance(value, bool) or value is None:
        return "not a colour, font or size"
    text = str(value).strip()
    lowered = path.lower()
    kind = (declared or "").lower()
    if kind == "color" or (not kind and _hex(text)):
        found = _hex(text)
        return ("colors", found) if found else "colour is not #rgb, #rrggbb or #rrggbbaa"
    if kind in ("fontfamily", "font-family") or (not kind and "font" in lowered and "size" not in lowered
                                                   and "weight" not in lowered):
        found = _font(text)
        return ("fonts", found) if found else "font family name is not plain text"
    if kind in ("dimension", "spacing") or (not kind and any(word in lowered for word in ("space", "spacing", "gap", "padding", "margin", "size", "radius"))):
        number = _spacing(text) if isinstance(value, str) else (float(value) if isinstance(value, (int, float)) else None)
        return ("spacing", round(number, 2)) if number is not None and 0 <= number <= 2_000 else "size is not px or rem"
    return "not a colour, font or size"


def _walk_json(node: Any, path: list[str], out: list[tuple[str, Any, str | None]]) -> None:
    if isinstance(node, Mapping):
        if "$value" in node or ("value" in node and not isinstance(node.get("value"), Mapping)):
            value = node.get("$value", node.get("value"))
            declared = node.get("$type", node.get("type"))
            out.append(("-".join(path), value, str(declared) if isinstance(declared, str) else None))
            return
        for key, child in node.items():
            if str(key).startswith("$"):
                continue
            _walk_json(child, [*path, str(key)], out)
    elif isinstance(node, (str, int, float)) and path:
        out.append(("-".join(path), node, None))


def parse_tokens(filename: str, text: str) -> dict[str, Any]:
    """Colours, fonts and spacing found in a tokens file, and what was skipped and why."""
    text = text[:MAX_TOKEN_FILE_CHARS]
    entries: list[tuple[str, Any, str | None]] = []
    stripped = text.lstrip()
    if filename.lower().endswith(".json") or stripped.startswith("{"):
        try:
            _walk_json(json.loads(text), [], entries)
        except ValueError:
            return {"format": "json", "variables": {"colors": {}, "fonts": {}, "spacing": {}},
                    "skipped": [{"name": filename, "reason": "not valid JSON"}], "found": 0}
        fmt = "json"
    else:
        for match in _CSS_VAR.finditer(re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)):
            entries.append((match.group(1), match.group(2).strip(), None))
        fmt = "css"
    variables: dict[str, dict[str, Any]] = {"colors": {}, "fonts": {}, "spacing": {}}
    skipped: list[dict[str, str]] = []
    for path, value, declared in entries:
        name = _name(path)
        if name is None:
            skipped.append({"name": path[:80], "reason": "name cannot be a variable name"})
            continue
        if isinstance(value, str) and value.strip().startswith("var("):
            skipped.append({"name": path[:80], "reason": "refers to another variable"})
            continue
        placed = _classify(path, value, declared)
        if isinstance(placed, str):
            skipped.append({"name": path[:80], "reason": placed})
            continue
        group, cleaned = placed
        if len(variables[group]) >= MAX_VARIABLES_PER_GROUP:
            skipped.append({"name": path[:80], "reason": f"more than {MAX_VARIABLES_PER_GROUP} {group}"})
            continue
        variables[group].setdefault(name, cleaned)
    found = sum(len(group) for group in variables.values())
    return {"format": fmt, "variables": variables, "skipped": skipped[:MAX_SKIPPED], "found": found}


def extract_palette(data: bytes, size: int = PALETTE_SIZE) -> list[dict[str, Any]]:
    """The picture's dominant colours, most common first, each with its share of the pixels."""
    with Image.open(io.BytesIO(data)) as opened:
        picture = opened.convert("RGBA")
    picture.thumbnail((200, 200))
    # Fully transparent pixels are not part of a logo's colours.
    raw = picture.tobytes()
    opaque = [(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw), 4) if raw[i + 3] >= 128]
    if not opaque:
        return []
    flat = Image.new("RGB", (len(opaque), 1))
    flat.putdata(opaque)
    quantized = flat.quantize(colors=size, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette() or []
    counts = sorted(quantized.getcolors() or [], reverse=True)
    total = sum(count for count, _index in counts) or 1
    out = []
    for count, index in counts[:size]:
        at = int(index) * 3  # type: ignore[call-overload]
        r, g, b = palette[at : at + 3]
        out.append({"color": f"#{r:02x}{g:02x}{b:02x}", "share": round(count / total, 3)})
    return out


__all__ = ["extract_palette", "parse_tokens"]
