"""DW-10 — what can be checked about a design before it is exported, and what cannot.

Each check reports one of four states and never more than it knows:

* ``pass`` — checked, nothing wrong;
* ``fail`` — checked, and each finding names its frame and layer;
* ``unsupported`` — the export cannot honour it (a font the raster renderer
  does not have), said before export rather than discovered after;
* ``unknown`` — it cannot be decided from the document (text over a photo has
  no single background colour to measure contrast against).

The outcome is ``passed`` only when every check passed. A model's opinion of
the design is not a check here, and nothing in this module calls one: visual
quality and accessibility compliance are not inferred from prose.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from raiker.design.document import CONTAINER_TYPES, content_hash, iter_nodes
from raiker.design.render import GENERIC_FONTS, missing_glyphs, raster_font_name, text_height
from raiker.design.systems import VARIABLE_FIELDS

VALIDATOR_VERSION = "design-validate/1"

#: ``asset_id -> "ok" | "deleted" | "missing"`` for this owner.
AssetState = Callable[[str], str]

CHECKS = (
    ("assets", "Placed images resolve to an asset you have"),
    ("alt_text", "Every visible image has alternative text"),
    ("text_overflow", "Text fits its box as the export draws it"),
    ("contrast", "Text meets WCAG AA contrast against what is behind it"),
    ("fonts", "Fonts are ones the export can draw"),
    ("frame_bounds", "Visible layers sit at least partly inside their frame"),
    ("variables", "Variables resolve in the selected design system"),
    ("required_variables", "The design system's required variables are used"),
    ("brand_colors", "Colours come from the selected design system"),
)


def _luminance(color: str) -> float:
    value = color.lstrip("#")
    channels = []
    for index in (0, 2, 4):
        c = int(value[index : index + 2], 16) / 255
        channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(foreground: str, background: str) -> float:
    lighter, darker = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return round((lighter + 0.05) / (darker + 0.05), 2)


def _opaque(color: str | None) -> bool:
    return bool(color) and (len(str(color)) == 7 or str(color).lower().endswith("ff"))


def _behind(painted: list[dict[str, Any]], node: Mapping[str, Any], frame: Mapping[str, Any]) -> str | None:
    """The single colour behind *node*'s centre, or ``None`` when it is not one colour."""
    cx = float(node["x"]) + float(node["w"]) / 2
    cy = float(node["y"]) + float(node["h"]) / 2
    for below in reversed(painted):
        inside = float(below["x"]) <= cx <= float(below["x"]) + float(below["w"]) and float(
            below["y"]
        ) <= cy <= float(below["y"]) + float(below["h"])
        if not inside:
            continue
        if below["type"] == "image" or float(below.get("opacity", 1)) < 1 or below.get("rotation"):
            return None
        if below["type"] in ("rect", "ellipse", "stack"):
            if _opaque(below.get("fill")):
                return str(below["fill"])[:7]
            if below.get("fill"):
                return None
    background = frame.get("background")
    return str(background)[:7] if _opaque(background) else None


def validate(
    document: Mapping[str, Any],
    *,
    asset_state: AssetState,
    variables: Mapping[str, Any] | None,
) -> dict[str, Any]:
    findings: dict[str, list[dict[str, Any]]] = {key: [] for key, _ in CHECKS}
    states: dict[str, str] = {key: "pass" for key, _ in CHECKS}
    used_variables: set[str] = set()
    palette = {str(value).lower() for value in ((variables or {}).get("colors") or {}).values()}

    def note(check: str, frame: Mapping[str, Any], node: Mapping[str, Any] | None, message: str,
             state: str = "fail") -> None:
        findings[check].append({"frame_id": frame["id"], "node_id": node["id"] if node else None,
                                "layer": node["name"] if node else frame["name"], "message": message})
        # The worst state wins: fail over unknown over unsupported over pass.
        order = {"pass": 0, "unsupported": 1, "unknown": 2, "fail": 3}
        if order[state] > order[states[check]]:
            states[check] = state

    for frame in document.get("frames") or []:
        if frame.get("background_var"):
            used_variables.add(str(frame["background_var"]))
        painted: list[dict[str, Any]] = []
        for node, _depth in iter_nodes(frame.get("nodes") or []):
            for variable_field, (_field, group) in VARIABLE_FIELDS.items():
                name = node.get(variable_field)
                if not name:
                    continue
                used_variables.add(str(name))
                if variables is None:
                    note("variables", frame, node, f"Uses the variable “{name}” but the design has no system selected.")
                elif name not in (variables.get(group) or {}):
                    note("variables", frame, node, f"The selected system does not define “{name}”.")
            if not node.get("visible", True):
                continue
            right, bottom = float(node["x"]) + float(node["w"]), float(node["y"]) + float(node["h"])
            if right < 0 or bottom < 0 or float(node["x"]) > frame["width"] or float(node["y"]) > frame["height"]:
                note("frame_bounds", frame, node, "Lies entirely outside the frame, so no export shows it.")
            if node["type"] == "image":
                state = asset_state(str(node["asset_id"])) if node.get("asset_id") else "missing"
                if state != "ok":
                    message = {
                        "deleted": "Its image is in Recently deleted; restore it or replace this layer.",
                        "missing": "No image is placed here, or the image no longer exists.",
                    }.get(state, "Its image cannot be read.")
                    note("assets", frame, node, message)
                if not str(node.get("alt") or "").strip():
                    note("alt_text", frame, node, "Add alternative text describing this image.")
            if node["type"] == "text":
                needed = text_height(node)
                if needed > float(node["h"]) + 0.5:
                    note("text_overflow", frame, node,
                         f"Needs {needed:.0f}px of height and has {float(node['h']):.0f}px.")
                if node["font_family"] not in GENERIC_FONTS:
                    note("fonts", frame, node,
                         f"“{node['font_family']}” is drawn in {raster_font_name()} in PNG and PDF; SVG names "
                         "it and the viewer substitutes its own if it lacks it.", "unsupported")
                absent = missing_glyphs(str(node.get("text") or ""))
                if absent:
                    note("fonts", frame, node,
                         f"{raster_font_name()} has no glyph for {' '.join(absent[:8])}, so PNG and PDF draw a "
                         "box there; SVG keeps the characters.", "unsupported")
                if float(node.get("opacity", 1)) < 1:
                    note("contrast", frame, node, "Translucent text has no single colour to measure.", "unknown")
                else:
                    behind = _behind(painted, node, frame)
                    if behind is None:
                        note("contrast", frame, node,
                             "What is behind this text is not one solid colour, so contrast is not known.",
                             "unknown")
                    elif _opaque(node.get("color")):
                        ratio = contrast_ratio(str(node["color"])[:7], behind)
                        large = float(node["font_size"]) >= 24 or (
                            float(node["font_size"]) >= 18.66 and int(node["font_weight"]) >= 700
                        )
                        needed_ratio = 3.0 if large else 4.5
                        if ratio < needed_ratio:
                            note("contrast", frame, node,
                                 f"Contrast {ratio}:1 against {behind}; needs {needed_ratio}:1.")
            if variables is not None and palette:
                for field in ("fill", "stroke", "color"):
                    value = node.get(field)
                    if value and str(value).lower()[:7] not in {p[:7] for p in palette}:
                        note("brand_colors", frame, node, f"{field} {value} is not in the system's colours.")
            if node["type"] not in CONTAINER_TYPES or node["type"] == "stack":
                painted.append(node)
    if variables is None:
        states["required_variables"] = "pass"
        states["brand_colors"] = "pass"
    else:
        for name in variables.get("required") or []:
            if name not in used_variables:
                findings["required_variables"].append(
                    {"frame_id": None, "node_id": None, "layer": "Document",
                     "message": f"The system requires “{name}” and no layer uses it."}
                )
                states["required_variables"] = "fail"
    checks = [
        {"check": key, "label": label, "status": states[key], "findings": findings[key][:50]}
        for key, label in CHECKS
    ]
    statuses = {check["status"] for check in checks}
    outcome = "failed" if "fail" in statuses else ("passed" if statuses == {"pass"} else "partly_checked")
    return {
        "outcome": outcome,
        "validator_version": VALIDATOR_VERSION,
        "document_hash": content_hash(document),
        "checks": checks,
    }


__all__ = ["CHECKS", "VALIDATOR_VERSION", "contrast_ratio", "validate"]
