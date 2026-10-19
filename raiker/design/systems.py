"""DW-06 — owner-selected design systems, versioned, applied only by choice.

A design system is the owner's brand as data: named colours, font families
and spacing values, usage rules, the variables a finished design must use, and a
note on where it came from. It is versioned like a document — editing it
writes a new version and never changes what an earlier version said — so a
design that chose ``Acme v2`` keeps reading ``Acme v2`` until its owner moves
it.

A node refers to the system through a variable (``fill_var``, ``color_var``,
``font_var``, a frame's ``background_var``) and also keeps the literal
value it is drawn with. Choosing or upgrading a system for a document is
therefore two steps, both explicit:

1. :func:`plan_system_change` lists every node whose drawn value would change,
   from what to what, and every variable the new system does not define; nothing
   is written;
2. applying that plan is an ordinary document version, on that one document.

No document is ever rewritten because a system it does not use changed.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from raiker.design.document import DesignError, iter_nodes

_NAME = re.compile(r"^[a-z][a-z0-9_.-]{0,59}$")
_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_FONT = re.compile(r"^[A-Za-z0-9 _-]{1,80}$")

MAX_VARIABLES_PER_GROUP = 64
MAX_RULES = 20

#: Which node field each variable field drives, and which variable group it reads.
VARIABLE_FIELDS: dict[str, tuple[str, str]] = {
    "fill_var": ("fill", "colors"),
    "color_var": ("color", "colors"),
    "font_var": ("font_family", "fonts"),
}


def clean_variables(raw: Any) -> dict[str, Any]:
    """A system's variables as stored, or :class:`DesignError`."""
    if not isinstance(raw, Mapping):
        raise DesignError("invalid_variables")
    out: dict[str, Any] = {"colors": {}, "fonts": {}, "spacing": {}, "rules": [], "required": []}
    for group, pattern in (("colors", _COLOR), ("fonts", _FONT)):
        values = raw.get(group) or {}
        if not isinstance(values, Mapping) or len(values) > MAX_VARIABLES_PER_GROUP:
            raise DesignError("invalid_variables", group)
        for name, value in values.items():
            if not isinstance(name, str) or not _NAME.match(name):
                raise DesignError("invalid_variable", f"{group}.{str(name)[:40]}")
            if not isinstance(value, str) or not pattern.match(value):
                raise DesignError("invalid_variable_value", f"{group}.{name}")
            out[group][name] = value.lower() if group == "colors" else value.strip()
    spacing = raw.get("spacing") or {}
    if not isinstance(spacing, Mapping) or len(spacing) > MAX_VARIABLES_PER_GROUP:
        raise DesignError("invalid_variables", "spacing")
    for name, value in spacing.items():
        if not isinstance(name, str) or not _NAME.match(name):
            raise DesignError("invalid_variable", f"spacing.{str(name)[:40]}")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 2_000:
            raise DesignError("invalid_variable_value", f"spacing.{name}")
        out["spacing"][name] = round(float(value), 2)
    rules = raw.get("rules") or []
    if not isinstance(rules, list) or len(rules) > MAX_RULES:
        raise DesignError("invalid_variables", "rules")
    out["rules"] = [" ".join(str(rule).split())[:200] for rule in rules if str(rule).strip()]
    required = raw.get("required") or []
    if not isinstance(required, list) or len(required) > MAX_VARIABLES_PER_GROUP:
        raise DesignError("invalid_variables", "required")
    for name in required:
        if name not in out["colors"] and name not in out["fonts"]:
            raise DesignError("unknown_required_variable", str(name)[:60])
    out["required"] = sorted({str(name) for name in required})
    return out


def _resolve(variables: Mapping[str, Any], group: str, name: str | None) -> str | None:
    if not name:
        return None
    value = (variables.get(group) or {}).get(name)
    return str(value) if value is not None else None


def plan_system_change(document: Mapping[str, Any], variables: Mapping[str, Any]) -> dict[str, Any]:
    """What moving *document* onto *variables* would change, without changing it.

    ``operations`` is the exact operation list that applying the plan sends, so
    what the owner previews is what is written.
    """
    changes: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    operations: list[dict[str, Any]] = []
    for frame in document.get("frames") or []:
        background = _resolve(variables, "colors", frame.get("background_var"))
        if frame.get("background_var"):
            if background is None:
                missing.append({"frame_id": frame["id"], "node_id": None, "variable": frame["background_var"]})
            elif background != frame.get("background"):
                changes.append({"frame_id": frame["id"], "node_id": None, "name": frame["name"],
                                "field": "background", "before": frame.get("background"), "after": background})
                operations.append({"op": "update_frame", "frame_id": frame["id"], "set": {"background": background}})
        for node, _depth in iter_nodes(frame.get("nodes") or []):
            updates: dict[str, Any] = {}
            for variable_field, (field, group) in VARIABLE_FIELDS.items():
                name = node.get(variable_field)
                if not name:
                    continue
                value = _resolve(variables, group, name)
                if value is None:
                    missing.append({"frame_id": frame["id"], "node_id": node["id"], "variable": name})
                elif value != node.get(field):
                    changes.append({"frame_id": frame["id"], "node_id": node["id"], "name": node["name"],
                                    "field": field, "before": node.get(field), "after": value})
                    updates[field] = value
            if updates:
                if node.get("locked"):
                    # A locked layer is the owner saying "not this one": reported, not changed.
                    missing.append({"frame_id": frame["id"], "node_id": node["id"], "variable": "(locked)"})
                    changes = [c for c in changes if c["node_id"] != node["id"]]
                    continue
                operations.append({"op": "update_node", "node_id": node["id"], "set": updates})
    return {"changes": changes, "missing": missing, "operations": operations}


__all__ = ["VARIABLE_FIELDS", "clean_variables", "plan_system_change"]
