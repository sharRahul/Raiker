"""DW-01 to DW-03 — the structured design document and the typed operations on it.

A design document is data, not a picture: pages (*frames*), each holding an
ordered, nested layer tree whose nodes are text, shapes, images, groups and
stack containers. Every node has a stable id, geometry, style, visibility,
locking state and the actor that created it. The canvas draws this; export
renders it; nothing ever stores a flattened screenshot in its place.

Every change — the owner's own drag, an undo, an accepted agent proposal — is a
list of **typed operations** applied here, so there is one place that decides
what a change may do:

* ids are stable and unique across the whole document, so a later operation
  can always say which node it means;
* a locked node can be shown, hidden, renamed or unlocked, and nothing else;
* sizes, counts and depths are bounded, so no request can grow a document
  without limit;
* after every change the layout is re-derived (a group's box is the union of
  its children, a stack places its children), so a stored document is always
  the one that is drawn.

``touched`` — the ids an operation list read or changed — is what a version
records as its scope. Two changes conflict when their scopes meet, which is how
a stale agent proposal is refused instead of overwriting later owner work
(DW-08).
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

SCHEMA_VERSION = 1

MAX_FRAMES = 40
MAX_NODES = 2_000
MAX_DEPTH = 8
MAX_OPERATIONS = 200
MAX_TEXT = 5_000
MAX_COORD = 100_000.0
MAX_SIZE = 20_000.0
MAX_FRAME_SIZE = 8_000
MAX_COMPONENTS = 50
MAX_NOTES = 200
MAX_NOTE_TEXT = 1_000

NODE_TYPES = ("text", "rect", "ellipse", "image", "group", "stack")
CONTAINER_TYPES = ("group", "stack")

#: DW-03 — the target contexts a new frame can start from. Sizes are the
#: platforms' own published canvases, in CSS pixels (A4 at 96 dpi).
FRAME_PRESETS: dict[str, dict[str, Any]] = {
    "social_square": {"label": "Social post (square)", "width": 1080, "height": 1080},
    "social_story": {"label": "Social story", "width": 1080, "height": 1920},
    "document_a4": {"label": "Document page (A4)", "width": 794, "height": 1123},
    "presentation": {"label": "Presentation (16:9)", "width": 1920, "height": 1080},
    "mobile": {"label": "Mobile screen", "width": 390, "height": 844},
    "desktop": {"label": "Desktop screen", "width": 1440, "height": 900},
    "custom": {"label": "Custom", "width": 800, "height": 600},
}

_ID = re.compile(r"^[a-z][a-z0-9_-]{0,47}$")
_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_TOKEN = re.compile(r"^[a-z][a-z0-9_.-]{0,59}$")
_FONT = re.compile(r"^[A-Za-z0-9 _-]{1,80}$")
_ASSET = re.compile(r"^img_[A-Za-z0-9]{1,64}$")

_COMMON = ("name", "x", "y", "w", "h", "rotation", "visible", "locked", "opacity")
_SHAPE = ("fill", "fill_var", "stroke", "stroke_width")
_FIELDS: dict[str, tuple[str, ...]] = {
    "text": _COMMON + ("text", "color", "color_var", "font_family", "font_var",
                       "font_size", "font_weight", "align", "line_height"),
    "rect": _COMMON + _SHAPE + ("radius",),
    "ellipse": _COMMON + _SHAPE,
    "image": _COMMON + ("asset_id", "alt", "fit", "crop", "radius"),
    "group": _COMMON + ("component_id",),
    "stack": _COMMON + _SHAPE + ("radius", "direction", "gap", "padding", "align"),
}
#: What may still change on a locked node.
_LOCKED_EDITABLE = frozenset({"locked", "visible", "name"})
_FRAME_FIELDS = ("name", "width", "height", "background", "background_var", "grid", "preset")


class DesignError(ValueError):
    """A refused document change. ``reason`` is the stable code; ``detail`` names what."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}:{detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


# ── Reading the tree ──────────────────────────────────────────────────────


def iter_nodes(nodes: Sequence[dict[str, Any]], depth: int = 0) -> Iterator[tuple[dict[str, Any], int]]:
    """Every node under *nodes*, depth first, back to front, with its depth."""
    for node in nodes:
        yield node, depth
        if node.get("type") in CONTAINER_TYPES:
            yield from iter_nodes(node.get("children") or [], depth + 1)


def all_nodes(document: Mapping[str, Any]) -> Iterator[tuple[dict[str, Any], dict[str, Any]]]:
    """``(frame, node)`` for every node in the document."""
    for frame in document.get("frames") or []:
        for node, _depth in iter_nodes(frame.get("nodes") or []):
            yield frame, node


def find_frame(document: Mapping[str, Any], frame_id: str) -> dict[str, Any]:
    for frame in document.get("frames") or []:
        if frame.get("id") == frame_id:
            return frame  # type: ignore[no-any-return]
    raise DesignError("unknown_frame", frame_id)


def locate(document: Mapping[str, Any], node_id: str) -> tuple[dict[str, Any], list[dict[str, Any]], int, dict[str, Any] | None]:
    """``(frame, sibling list, index, parent)`` for *node_id*; the parent is ``None`` at frame root."""

    def search(
        siblings: list[dict[str, Any]], parent: dict[str, Any] | None
    ) -> tuple[list[dict[str, Any]], int, dict[str, Any] | None] | None:
        for index, node in enumerate(siblings):
            if node.get("id") == node_id:
                return siblings, index, parent
            if node.get("type") in CONTAINER_TYPES:
                found = search(node.setdefault("children", []), node)
                if found is not None:
                    return found
        return None

    for frame in document.get("frames") or []:
        hit = search(frame.setdefault("nodes", []), None)
        if hit is not None:
            return frame, hit[0], hit[1], hit[2]
    raise DesignError("unknown_node", node_id)


def subtree_ids(node: Mapping[str, Any]) -> list[str]:
    """*node*'s id and every descendant's."""
    return [str(item["id"]) for item, _ in iter_nodes([dict(node)])]


def content_hash(document: Mapping[str, Any]) -> str:
    """SHA-256 of the document's canonical JSON: what a version and an export are pinned to."""
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ── Building ──────────────────────────────────────────────────────────────


def new_frame(frame_id: str, name: str, preset: str = "custom", *, width: int | None = None,
              height: int | None = None) -> dict[str, Any]:
    if preset not in FRAME_PRESETS:
        raise DesignError("unknown_frame_preset", preset)
    spec = FRAME_PRESETS[preset]
    frame = {
        "id": frame_id,
        "name": name,
        "preset": preset,
        "width": int(width or spec["width"]),
        "height": int(height or spec["height"]),
        "background": "#ffffff",
        "background_var": None,
        "grid": {"size": 8, "visible": False},
        "variant_of": None,
        "nodes": [],
    }
    return _clean_frame(frame)


def blank_document(preset: str = "social_square") -> dict[str, Any]:
    """A document with one empty frame, which is what *New design* opens on."""
    return {"schema": SCHEMA_VERSION, "frames": [new_frame("frame-1", "Frame 1", preset)]}


# ── Field validation ─────────────────────────────────────────────────────


def _number(value: Any, field: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise DesignError("invalid_field", field)
    if value < low or value > high:
        raise DesignError("field_out_of_range", field)
    return round(float(value), 2)


def _color(value: Any, field: str) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not _COLOR.match(value):
        raise DesignError("invalid_color", field)
    return value.lower()


def _variable(value: Any, field: str) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not _TOKEN.match(value):
        raise DesignError("invalid_variable", field)
    return value


def _text(value: Any, field: str, limit: int) -> str:
    if not isinstance(value, str):
        raise DesignError("invalid_field", field)
    if len(value) > limit:
        raise DesignError("field_too_long", field)
    return value


def _choice(value: Any, field: str, options: tuple[str, ...]) -> str:
    if value not in options:
        raise DesignError("invalid_field", field)
    return str(value)


def _clean_field(kind: str, field: str, value: Any) -> Any:
    if field in ("x", "y"):
        return _number(value, field, -MAX_COORD, MAX_COORD)
    if field in ("w", "h"):
        return _number(value, field, 0, MAX_SIZE)
    if field == "rotation":
        return _number(value, field, -360, 360)
    if field == "opacity":
        return _number(value, field, 0, 1)
    if field in ("visible", "locked"):
        if not isinstance(value, bool):
            raise DesignError("invalid_field", field)
        return value
    if field == "name":
        return _text(value, field, 120).strip() or kind
    if field in ("fill", "stroke", "color"):
        return _color(value, field)
    if field in ("fill_var", "color_var", "font_var"):
        return _variable(value, field)
    if field == "stroke_width":
        return _number(value, field, 0, 200)
    if field == "radius":
        return _number(value, field, 0, 10_000)
    if field == "text":
        return _text(value, field, MAX_TEXT)
    if field == "font_family":
        if not isinstance(value, str) or not _FONT.match(value):
            raise DesignError("invalid_field", field)
        return value.strip()
    if field == "font_size":
        return _number(value, field, 1, 1_000)
    if field == "font_weight":
        weight = int(_number(value, field, 100, 900))
        return weight - weight % 100
    if field == "line_height":
        return _number(value, field, 0.5, 4)
    if field == "align":
        options = ("left", "center", "right") if kind == "text" else ("start", "center", "end")
        return _choice(value, field, options)
    if field == "asset_id":
        if value is None or value == "":
            return None
        if not isinstance(value, str) or not _ASSET.match(value):
            raise DesignError("invalid_asset", field)
        return value
    if field == "alt":
        return _text(value, field, 500)
    if field == "fit":
        return _choice(value, field, ("cover", "contain", "fill"))
    if field == "crop":
        return _crop(value)
    if field == "direction":
        return _choice(value, field, ("row", "column"))
    if field in ("gap", "padding"):
        return _number(value, field, 0, 2_000)
    if field == "component_id":
        if value is None or value == "":
            return None
        if not isinstance(value, str) or not _ID.match(value):
            raise DesignError("invalid_field", field)
        return value
    raise DesignError("unknown_field", field)


def _crop(value: Any) -> dict[str, float] | None:
    """DW-03 — a non-destructive crop: the visible part of the asset, as fractions."""
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise DesignError("invalid_field", "crop")
    box = {key: _number(value.get(key), "crop", 0, 1) for key in ("x", "y", "w", "h")}
    if box["w"] <= 0 or box["h"] <= 0 or box["x"] + box["w"] > 1.0001 or box["y"] + box["h"] > 1.0001:
        raise DesignError("invalid_field", "crop")
    return box


_DEFAULTS: dict[str, dict[str, Any]] = {
    "text": {"text": "Text", "color": "#111111", "color_var": None, "font_family": "sans-serif",
             "font_var": None, "font_size": 32, "font_weight": 400, "align": "left", "line_height": 1.2},
    "rect": {"fill": "#d9d9d9", "fill_var": None, "stroke": None, "stroke_width": 0, "radius": 0},
    "ellipse": {"fill": "#d9d9d9", "fill_var": None, "stroke": None, "stroke_width": 0},
    "image": {"asset_id": None, "alt": "", "fit": "cover", "crop": None, "radius": 0},
    "group": {"component_id": None},
    "stack": {"fill": None, "fill_var": None, "stroke": None, "stroke_width": 0, "radius": 0,
              "direction": "column", "gap": 16, "padding": 16, "align": "start"},
}


def clean_node(raw: Any, *, created_by: str, depth: int = 0) -> dict[str, Any]:
    """A node as stored: known fields only, each checked, defaults filled in."""
    if not isinstance(raw, Mapping):
        raise DesignError("invalid_node")
    kind = raw.get("type")
    if kind not in NODE_TYPES:
        raise DesignError("unknown_node_type", str(kind)[:40])
    node_id = raw.get("id")
    if not isinstance(node_id, str) or not _ID.match(node_id):
        raise DesignError("invalid_node_id", str(node_id)[:48])
    if depth > MAX_DEPTH:
        raise DesignError("too_deep", node_id)
    node: dict[str, Any] = {
        "id": node_id, "type": kind, "name": kind, "x": 0.0, "y": 0.0, "w": 100.0, "h": 100.0,
        "rotation": 0.0, "visible": True, "locked": False, "opacity": 1.0,
        "created_by": created_by if created_by in ("owner", "agent") else "owner",
    }
    node.update(copy.deepcopy(_DEFAULTS[str(kind)]))
    for field in _FIELDS[str(kind)]:
        if field in raw:
            node[field] = _clean_field(str(kind), field, raw[field])
    if raw.get("created_by") in ("owner", "agent"):
        node["created_by"] = raw["created_by"]
    if kind in CONTAINER_TYPES:
        children = raw.get("children") or []
        if not isinstance(children, list):
            raise DesignError("invalid_field", "children")
        node["children"] = [clean_node(child, created_by=created_by, depth=depth + 1) for child in children]
    return node


def _clean_frame(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise DesignError("invalid_frame")
    frame_id = raw.get("id")
    if not isinstance(frame_id, str) or not _ID.match(frame_id):
        raise DesignError("invalid_frame_id", str(frame_id)[:48])
    preset = raw.get("preset") or "custom"
    if preset not in FRAME_PRESETS:
        raise DesignError("unknown_frame_preset", str(preset)[:40])
    grid = raw.get("grid") or {}
    if not isinstance(grid, Mapping):
        raise DesignError("invalid_field", "grid")
    variant_of = raw.get("variant_of")
    if variant_of is not None and (not isinstance(variant_of, str) or not _ID.match(variant_of)):
        raise DesignError("invalid_field", "variant_of")
    return {
        "id": frame_id,
        "name": _text(raw.get("name") or frame_id, "name", 120).strip() or frame_id,
        "preset": preset,
        "width": int(_number(raw.get("width", 800), "width", 1, MAX_FRAME_SIZE)),
        "height": int(_number(raw.get("height", 600), "height", 1, MAX_FRAME_SIZE)),
        "background": _color(raw.get("background", "#ffffff"), "background"),
        "background_var": _variable(raw.get("background_var"), "background_var"),
        "grid": {
            "size": int(_number(grid.get("size", 8), "grid", 0, 400)),
            "visible": bool(grid.get("visible", False)),
        },
        "variant_of": variant_of,
        "nodes": list(raw.get("nodes") or []),
    }


def validate_document(raw: Any, *, created_by: str = "owner") -> dict[str, Any]:
    """The document as stored, or :class:`DesignError`. Ids are unique across frames and nodes."""
    if not isinstance(raw, Mapping):
        raise DesignError("invalid_document")
    frames_raw = raw.get("frames")
    if not isinstance(frames_raw, list) or not frames_raw:
        raise DesignError("document_needs_a_frame")
    if len(frames_raw) > MAX_FRAMES:
        raise DesignError("too_many_frames")
    frames = []
    for item in frames_raw:
        frame = _clean_frame(item)
        frame["nodes"] = [clean_node(node, created_by=created_by) for node in frame["nodes"]]
        frames.append(frame)
    document: dict[str, Any] = {"schema": SCHEMA_VERSION, "frames": frames}
    system = raw.get("system")
    if isinstance(system, Mapping) and isinstance(system.get("id"), str) and isinstance(system.get("version"), int):
        document["system"] = {"id": system["id"][:80], "version": int(system["version"])}
    components = _clean_components(raw.get("components"), created_by)
    if components:
        document["components"] = components
    notes = _clean_notes(raw.get("notes"))
    if notes:
        document["notes"] = notes
    _check_ids(document)
    return normalize(document)


def _clean_component(raw: Any, created_by: str) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise DesignError("invalid_component")
    nodes = raw.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise DesignError("invalid_component")
    return {
        "name": _text(raw.get("name") or "Component", "name", 120).strip() or "Component",
        "nodes": [clean_node(node, created_by=created_by) for node in nodes],
    }


def _clean_components(raw: Any, created_by: str) -> dict[str, Any]:
    """DW-06 — reusable components: a name and a layer tree drawn from (0, 0)."""
    if raw is None:
        return {}
    if not isinstance(raw, Mapping) or len(raw) > MAX_COMPONENTS:
        raise DesignError("invalid_field", "components")
    out: dict[str, Any] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not _ID.match(key):
            raise DesignError("invalid_component_id", str(key)[:48])
        out[key] = _clean_component(value, created_by)
    return out


def _clean_note(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise DesignError("invalid_note")
    note_id, target = raw.get("id"), raw.get("target")
    if not isinstance(note_id, str) or not _ID.match(note_id):
        raise DesignError("invalid_note_id", str(note_id)[:48])
    if not isinstance(target, str) or not _ID.match(target):
        raise DesignError("invalid_field", "target")
    text = _text(raw.get("text"), "text", MAX_NOTE_TEXT).strip()
    if not text:
        raise DesignError("empty_note", note_id)
    return {
        "id": note_id,
        "target": target,
        "text": text,
        "author": raw.get("author") if raw.get("author") in ("owner", "agent") else "owner",
        "resolved": bool(raw.get("resolved", False)),
    }


def _clean_notes(raw: Any) -> list[dict[str, Any]]:
    """DW-08 — notes on a layer or a frame. Not drawn and not exported as pixels."""
    if raw is None:
        return []
    if not isinstance(raw, list) or len(raw) > MAX_NOTES:
        raise DesignError("invalid_field", "notes")
    return [_clean_note(item) for item in raw]


def _check_ids(document: Mapping[str, Any]) -> None:
    seen: set[str] = set()
    count = 0
    frame_ids = {str(frame["id"]) for frame in document["frames"]}
    for frame in document["frames"]:
        if frame["id"] in seen:
            raise DesignError("duplicate_id", str(frame["id"]))
        seen.add(str(frame["id"]))
        if frame.get("variant_of") is not None and frame["variant_of"] not in frame_ids:
            frame["variant_of"] = None
    for _frame, node in all_nodes(document):
        count += 1
        if node["id"] in seen:
            raise DesignError("duplicate_id", str(node["id"]))
        seen.add(str(node["id"]))
    if count > MAX_NODES:
        raise DesignError("too_many_nodes")
    note_ids: set[str] = set()
    for note in document.get("notes") or []:
        if note["id"] in note_ids:
            raise DesignError("duplicate_id", str(note["id"]))
        note_ids.add(str(note["id"]))


# ── Layout ────────────────────────────────────────────────────────────────


def _translate(node: dict[str, Any], dx: float, dy: float) -> None:
    for item, _ in iter_nodes([node]):
        item["x"] = round(float(item["x"]) + dx, 2)
        item["y"] = round(float(item["y"]) + dy, 2)


def _fit_groups(nodes: list[dict[str, Any]]) -> None:
    """Bottom up: a group's box is the union of its children's."""
    for node in nodes:
        if node["type"] in CONTAINER_TYPES:
            _fit_groups(node["children"])
        if node["type"] == "group" and node["children"]:
            left = min(float(child["x"]) for child in node["children"])
            top = min(float(child["y"]) for child in node["children"])
            right = max(float(child["x"]) + float(child["w"]) for child in node["children"])
            bottom = max(float(child["y"]) + float(child["h"]) for child in node["children"])
            node.update(x=round(left, 2), y=round(top, 2), w=round(right - left, 2), h=round(bottom - top, 2))


def _place_stacks(nodes: list[dict[str, Any]]) -> None:
    """Top down: a stack places its visible children along its direction."""
    for node in nodes:
        if node["type"] == "stack":
            pad = float(node["padding"])
            cursor = pad
            column = node["direction"] == "column"
            for child in node["children"]:
                if not child.get("visible", True):
                    continue
                span_main = float(child["h"] if column else child["w"])
                span_cross = float(child["w"] if column else child["h"])
                room = float(node["w"] if column else node["h"])
                cross = {"start": pad, "center": (room - span_cross) / 2, "end": room - pad - span_cross}[
                    node["align"]
                ]
                target_x = float(node["x"]) + (cross if column else cursor)
                target_y = float(node["y"]) + (cursor if column else cross)
                _translate(child, target_x - float(child["x"]), target_y - float(child["y"]))
                cursor += span_main + float(node["gap"])
        if node["type"] in CONTAINER_TYPES:
            _place_stacks(node["children"])


def normalize(document: dict[str, Any]) -> dict[str, Any]:
    for frame in document["frames"]:
        _fit_groups(frame["nodes"])
        _place_stacks(frame["nodes"])
        _fit_groups(frame["nodes"])
    return document


# ── Operations ────────────────────────────────────────────────────────────

OPERATION_KINDS = (
    "add_node", "update_node", "remove_node", "move_node", "group_nodes", "ungroup",
    "add_frame", "update_frame", "remove_frame", "duplicate_frame",
    "define_component", "place_component", "update_instance", "remove_component",
    "add_note", "update_note", "remove_note",
)


def _fresh_id(base: str, taken: set[str]) -> str:
    candidate = base[:44]
    counter = 2
    while candidate in taken or not _ID.match(candidate):
        candidate = f"{base[:40]}-{counter}"
        counter += 1
    taken.add(candidate)
    return candidate


def _ids(document: Mapping[str, Any]) -> set[str]:
    taken = {str(frame["id"]) for frame in document["frames"]}
    taken.update(str(node["id"]) for _frame, node in all_nodes(document))
    return taken


def _apply_one(document: dict[str, Any], op: Mapping[str, Any], actor: str, touched: set[str]) -> str:
    kind = op.get("op")
    if kind == "add_node":
        frame = find_frame(document, str(op.get("frame_id") or ""))
        node = clean_node(op.get("node"), created_by=actor)
        parent_id = op.get("parent_id")
        siblings = frame["nodes"]
        if parent_id:
            _f, holder, index, _p = locate(document, str(parent_id))
            host = holder[index]
            if host["type"] not in CONTAINER_TYPES or _f is not frame:
                raise DesignError("invalid_parent", str(parent_id))
            siblings = host["children"]
            touched.add(str(parent_id))
        at = op.get("index")
        siblings.insert(len(siblings) if not isinstance(at, int) else max(0, min(at, len(siblings))), node)
        touched.update(subtree_ids(node))
        return f"added {node['type']} {node['name']}"
    if kind == "update_node":
        node_id = str(op.get("node_id") or "")
        _frame, holder, index, _parent = locate(document, node_id)
        node = holder[index]
        changes = op.get("set")
        if not isinstance(changes, Mapping) or not changes:
            raise DesignError("empty_update", node_id)
        if node.get("locked") and not set(changes) <= _LOCKED_EDITABLE:
            raise DesignError("node_locked", node_id)
        allowed = _FIELDS[node["type"]]
        before = (float(node["x"]), float(node["y"]))
        for field, value in changes.items():
            if field not in allowed:
                raise DesignError("unknown_field", str(field)[:40])
            node[field] = _clean_field(node["type"], field, value)
        if node["type"] in CONTAINER_TYPES and ("x" in changes or "y" in changes):
            # Moving a container moves what it holds: its own x/y were already set.
            dx, dy = float(node["x"]) - before[0], float(node["y"]) - before[1]
            for child in node["children"]:
                _translate(child, dx, dy)
        touched.add(node_id)
        return f"changed {node['name']}"
    if kind == "remove_node":
        node_id = str(op.get("node_id") or "")
        _frame, holder, index, parent = locate(document, node_id)
        node = holder[index]
        if node.get("locked"):
            raise DesignError("node_locked", node_id)
        touched.update(subtree_ids(node))
        if parent is not None:
            touched.add(str(parent["id"]))
        del holder[index]
        return f"removed {node['name']}"
    if kind == "move_node":
        node_id = str(op.get("node_id") or "")
        frame, holder, index, parent = locate(document, node_id)
        node = holder[index]
        if node.get("locked"):
            raise DesignError("node_locked", node_id)
        target_id = op.get("parent_id")
        target = frame["nodes"]
        if target_id:
            if str(target_id) in subtree_ids(node):
                raise DesignError("invalid_parent", str(target_id))
            tframe, tholder, tindex, _tp = locate(document, str(target_id))
            container = tholder[tindex]
            if container["type"] not in CONTAINER_TYPES or tframe is not frame:
                raise DesignError("invalid_parent", str(target_id))
            target = container["children"]
            touched.add(str(target_id))
        if parent is not None:
            touched.add(str(parent["id"]))
        del holder[index]
        at = op.get("index")
        target.insert(len(target) if not isinstance(at, int) else max(0, min(at, len(target))), node)
        touched.add(node_id)
        return f"moved {node['name']}"
    if kind == "group_nodes":
        ids = op.get("node_ids")
        if not isinstance(ids, list) or len(ids) < 1:
            raise DesignError("invalid_field", "node_ids")
        located = [locate(document, str(item)) for item in ids]
        holder = located[0][1]
        if any(entry[1] is not holder for entry in located):
            raise DesignError("group_needs_siblings")
        indexes = sorted(entry[2] for entry in located)
        members = [holder[i] for i in indexes]
        if any(member.get("locked") for member in members):
            raise DesignError("node_locked", str(next(m["id"] for m in members if m.get("locked"))))
        group = clean_node(
            {"id": op.get("group_id"), "type": "group", "name": op.get("name") or "Group"}, created_by=actor
        )
        if group["id"] in _ids(document):
            raise DesignError("duplicate_id", group["id"])
        for i in reversed(indexes):
            del holder[i]
        group["children"] = members
        holder.insert(indexes[0], group)
        touched.update(str(item) for item in ids)
        touched.add(group["id"])
        if located[0][3] is not None:
            touched.add(str(located[0][3]["id"]))
        return f"grouped {len(members)} layers"
    if kind == "ungroup":
        node_id = str(op.get("node_id") or "")
        _frame, holder, index, _parent = locate(document, node_id)
        group = holder[index]
        if group["type"] != "group":
            raise DesignError("not_a_group", node_id)
        if group.get("locked"):
            raise DesignError("node_locked", node_id)
        holder[index : index + 1] = group["children"]
        touched.add(node_id)
        touched.update(str(child["id"]) for child in group["children"])
        return f"ungrouped {group['name']}"
    if kind == "add_frame":
        raw = op.get("frame")
        if not isinstance(raw, Mapping):
            raise DesignError("invalid_frame")
        preset = raw.get("preset") or "custom"
        if preset not in FRAME_PRESETS:
            raise DesignError("unknown_frame_preset", str(preset)[:40])
        spec = FRAME_PRESETS[str(preset)]
        frame = _clean_frame(
            {"width": spec["width"], "height": spec["height"], "background": "#ffffff",
             **{key: value for key, value in raw.items() if key not in ("nodes", "variant_of")}}
        )
        frame["nodes"] = [clean_node(node, created_by=actor) for node in raw.get("nodes") or []]
        if frame["id"] in _ids(document):
            raise DesignError("duplicate_id", frame["id"])
        if len(document["frames"]) >= MAX_FRAMES:
            raise DesignError("too_many_frames")
        document["frames"].append(frame)
        touched.add(frame["id"])
        return f"added frame {frame['name']}"
    if kind == "update_frame":
        frame = find_frame(document, str(op.get("frame_id") or ""))
        changes = op.get("set")
        if not isinstance(changes, Mapping) or not changes:
            raise DesignError("empty_update", frame["id"])
        merged = {**frame, **{k: v for k, v in changes.items() if k in _FRAME_FIELDS}}
        unknown = set(changes) - set(_FRAME_FIELDS)
        if unknown:
            raise DesignError("unknown_field", sorted(unknown)[0][:40])
        cleaned = _clean_frame(merged)
        cleaned["nodes"] = frame["nodes"]
        frame.clear()
        frame.update(cleaned)
        touched.add(frame["id"])
        return f"changed frame {frame['name']}"
    if kind == "remove_frame":
        frame = find_frame(document, str(op.get("frame_id") or ""))
        if len(document["frames"]) == 1:
            raise DesignError("document_needs_a_frame")
        if any(node.get("locked") for node, _ in iter_nodes(frame["nodes"])):
            raise DesignError("node_locked", frame["id"])
        document["frames"].remove(frame)
        touched.add(frame["id"])
        touched.update(str(node["id"]) for node, _ in iter_nodes(frame["nodes"]))
        for other in document["frames"]:
            if other.get("variant_of") == frame["id"]:
                other["variant_of"] = None
        return f"removed frame {frame['name']}"
    if kind == "duplicate_frame":
        return _duplicate_frame(document, op, actor, touched)
    if kind in ("define_component", "place_component", "update_instance", "remove_component"):
        return _component_op(document, op, actor, touched)
    if kind in ("add_note", "update_note", "remove_note"):
        return _note_op(document, op, actor, touched)
    raise DesignError("unknown_operation", str(kind)[:40])


# ── Components (DW-06) ────────────────────────────────────────────────────


def _component_copy(document: dict[str, Any], component_id: str, instance_id: str, x: float, y: float,
                    actor: str) -> list[dict[str, Any]]:
    """The component's layers with fresh ids under *instance_id*, placed at (*x*, *y*)."""
    component = (document.get("components") or {}).get(component_id)
    if component is None:
        raise DesignError("unknown_component", component_id)
    taken = _ids(document)
    copies = copy.deepcopy(component["nodes"])
    for node, _ in iter_nodes(copies):
        node["id"] = _fresh_id(f"{instance_id}-{node['id']}"[:40], taken)
        node["created_by"] = actor
    for node in copies:
        _translate(node, x, y)
    return copies


def _component_op(document: dict[str, Any], op: Mapping[str, Any], actor: str, touched: set[str]) -> str:
    """A component is a named layer tree kept in the document; an instance is a group linked to it.

    Placing copies the tree with fresh ids, so an instance is ordinary layers the
    owner can still edit. *Update from component* replaces an instance's layers
    with the component's again — an explicit act, never automatic.
    """
    kind = op.get("op")
    components = document.setdefault("components", {})
    if kind == "define_component":
        component_id = str(op.get("component_id") or "")
        if not _ID.match(component_id) or component_id in components:
            raise DesignError("invalid_component_id", component_id[:48])
        if len(components) >= MAX_COMPONENTS:
            raise DesignError("too_many_components")
        node_id = str(op.get("node_id") or "")
        _frame, holder, index, _parent = locate(document, node_id)
        source = copy.deepcopy(holder[index])
        if source["type"] == "group" and source.get("component_id"):
            # Made from an instance: the component is what the instance holds.
            nodes = source["children"]
        else:
            nodes = [source]
        left = min(float(node["x"]) for node in nodes)
        top = min(float(node["y"]) for node in nodes)
        for node in nodes:
            _translate(node, -left, -top)
        components[component_id] = _clean_component(
            {"name": op.get("name") or source["name"], "nodes": nodes}, actor
        )
        touched.add(component_id)
        return f"made component {components[component_id]['name']}"
    if kind == "place_component":
        component_id = str(op.get("component_id") or "")
        if component_id not in components:
            raise DesignError("unknown_component", component_id)
        frame = find_frame(document, str(op.get("frame_id") or ""))
        instance_id = str(op.get("node_id") or "")
        if not _ID.match(instance_id) or instance_id in _ids(document):
            raise DesignError("invalid_node_id", instance_id[:48])
        x = _number(op.get("x", 0), "x", -MAX_COORD, MAX_COORD)
        y = _number(op.get("y", 0), "y", -MAX_COORD, MAX_COORD)
        group = clean_node({"id": instance_id, "type": "group", "name": components[component_id]["name"],
                            "component_id": component_id}, created_by=actor)
        group["children"] = _component_copy(document, component_id, instance_id, x, y, actor)
        frame["nodes"].append(group)
        touched.update(subtree_ids(group))
        touched.add(component_id)
        return f"placed {group['name']}"
    if kind == "update_instance":
        node_id = str(op.get("node_id") or "")
        _frame, holder, index, _parent = locate(document, node_id)
        instance = holder[index]
        component_id = str(instance.get("component_id") or "") if instance["type"] == "group" else ""
        if not component_id:
            raise DesignError("not_an_instance", node_id)
        if instance.get("locked") or any(child.get("locked") for child, _ in iter_nodes(instance["children"])):
            raise DesignError("node_locked", node_id)
        touched.update(subtree_ids(instance))
        x, y = float(instance["x"]), float(instance["y"])
        instance["children"] = []
        instance["children"] = _component_copy(document, str(component_id), node_id, x, y, actor)
        touched.update(subtree_ids(instance))
        return f"updated {instance['name']} from its component"
    if kind == "remove_component":
        component_id = str(op.get("component_id") or "")
        if component_id not in components:
            raise DesignError("unknown_component", component_id)
        # Instances keep their layers; their link reads as broken until they are
        # detached or the component comes back, and Check says so.
        name = components.pop(component_id)["name"]
        touched.add(component_id)
        return f"removed component {name}"
    raise DesignError("unknown_operation", str(kind)[:40])


# ── Notes (DW-08) ─────────────────────────────────────────────────────────


def _note_op(document: dict[str, Any], op: Mapping[str, Any], actor: str, touched: set[str]) -> str:
    """Notes are versioned like any change, so a note's history is the document's."""
    kind = op.get("op")
    notes = document.setdefault("notes", [])
    if kind == "add_note":
        raw = op.get("note")
        if not isinstance(raw, Mapping):
            raise DesignError("invalid_note")
        note = _clean_note({**raw, "author": actor, "resolved": False})
        if note["target"] not in _ids(document):
            raise DesignError("unknown_note_target", note["target"])
        if any(item["id"] == note["id"] for item in notes):
            raise DesignError("duplicate_id", note["id"])
        if len(notes) >= MAX_NOTES:
            raise DesignError("too_many_notes")
        notes.append(note)
        touched.add(note["id"])
        return f"added a note on {note['target']}"
    note_id = str(op.get("note_id") or "")
    found = next((item for item in notes if item["id"] == note_id), None)
    if found is None:
        raise DesignError("unknown_note", note_id)
    touched.add(note_id)
    if kind == "update_note":
        changes = op.get("set")
        if not isinstance(changes, Mapping) or not changes or set(changes) - {"text", "resolved"}:
            raise DesignError("invalid_field", "set")
        updated = _clean_note({**found, **changes})
        found.update(text=updated["text"], resolved=updated["resolved"])
        return "resolved a note" if changes.get("resolved") else "changed a note"
    notes.remove(found)
    return "removed a note"


def _duplicate_frame(document: dict[str, Any], op: Mapping[str, Any], actor: str, touched: set[str]) -> str:
    """DW-03 — a copy, or a responsive *variant* linked to its source frame.

    A variant at another size is scaled from its source once, here; it records
    ``variant_of`` so the link is visible, and never follows the source again
    on its own — the spec's "linked without implying it stays identical".
    """
    source = find_frame(document, str(op.get("frame_id") or ""))
    if len(document["frames"]) >= MAX_FRAMES:
        raise DesignError("too_many_frames")
    taken = _ids(document)
    new_id = str(op.get("new_frame_id") or "")
    if not _ID.match(new_id) or new_id in taken:
        raise DesignError("invalid_frame_id", new_id[:48])
    taken.add(new_id)
    width = int(_number(op.get("width", source["width"]), "width", 1, MAX_FRAME_SIZE))
    height = int(_number(op.get("height", source["height"]), "height", 1, MAX_FRAME_SIZE))
    sx, sy = width / source["width"], height / source["height"]
    copy_frame = copy.deepcopy(source)
    copy_frame.update(
        id=new_id,
        name=_text(op.get("name") or f"{source['name']} copy", "name", 120),
        width=width,
        height=height,
        preset=str(op.get("preset") or source["preset"]) if (op.get("preset") or source["preset"]) in FRAME_PRESETS else "custom",
        variant_of=source["id"] if op.get("variant") else None,
    )
    for node, _ in iter_nodes(copy_frame["nodes"]):
        node["id"] = _fresh_id(f"{node['id']}-{new_id}"[:44], taken)
        node["x"], node["w"] = round(float(node["x"]) * sx, 2), round(float(node["w"]) * sx, 2)
        node["y"], node["h"] = round(float(node["y"]) * sy, 2), round(float(node["h"]) * sy, 2)
        node["created_by"] = actor
        touched.add(node["id"])
    document["frames"].append(copy_frame)
    touched.update({new_id, source["id"]})
    return f"{'made a variant of' if op.get('variant') else 'duplicated'} {source['name']}"


def apply_operations(
    document: Mapping[str, Any], operations: Sequence[Mapping[str, Any]], *, actor: str
) -> tuple[dict[str, Any], set[str], list[str]]:
    """Apply *operations* in order to a copy of *document*: all of them or none.

    Returns the new document, the ids the change touched, and one line per
    operation saying what it did.
    """
    if not isinstance(operations, Sequence) or isinstance(operations, (str, bytes)):
        raise DesignError("invalid_operations")
    if not operations:
        raise DesignError("no_operations")
    if len(operations) > MAX_OPERATIONS:
        raise DesignError("too_many_operations")
    working = copy.deepcopy(dict(document))
    touched: set[str] = set()
    summary: list[str] = []
    for position, op in enumerate(operations):
        if not isinstance(op, Mapping):
            raise DesignError("invalid_operation", str(position))
        try:
            summary.append(_apply_one(working, op, actor, touched))
        except DesignError as exc:
            raise DesignError(exc.reason, f"{exc.detail}@{position}" if exc.detail else str(position)) from None
    _check_ids(working)
    if not working.get("components"):
        working.pop("components", None)
    if not working.get("notes"):
        working.pop("notes", None)
    return normalize(working), touched, summary


__all__ = [
    "FRAME_PRESETS",
    "MAX_OPERATIONS",
    "OPERATION_KINDS",
    "DesignError",
    "all_nodes",
    "apply_operations",
    "blank_document",
    "clean_node",
    "content_hash",
    "find_frame",
    "iter_nodes",
    "locate",
    "new_frame",
    "normalize",
    "subtree_ids",
    "validate_document",
]
