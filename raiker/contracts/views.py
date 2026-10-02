"""One way a read model becomes the JSON an API answers with.

OPT-05. A hundred and thirty-four frozen dataclasses each carried a ``to_dict``
that was either ``asdict(self)`` or the same thing typed out field by field —
``list(self.tags)``, ``[row.to_dict() for row in self.rows]``. They inherit
:class:`View` now, and a projection that genuinely differs from its fields (one
that omits an owner id, derives a notice, renames a key) keeps its own
``to_dict``, which is then the only kind of ``to_dict`` left to read.

Only declared dataclass fields are serialised, and only for classes that opt in
by inheriting :class:`View`: a view is a dedicated projection, never a storage
or domain object, so nothing private can reach a response by accident.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from typing import Any

__all__ = ["View", "json_ready", "view_to_dict"]


def _value(value: Any) -> Any:
    # A nested object with its own projection is asked for it, so a parent never
    # widens what a child chose to expose.
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict) and not isinstance(value, type):
        return to_dict()
    if is_dataclass(value) and not isinstance(value, type):
        return view_to_dict(value)
    if isinstance(value, Mapping):
        return {key: _value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_value(item) for item in value]
    return value


def json_ready(value: Any) -> Any:
    """``value`` with every nested view projected, as a view's own fields are."""
    return _value(value)


def view_to_dict(view: Any) -> dict[str, Any]:
    """A dataclass's declared fields as JSON-ready values, in declaration order."""
    return {field.name: _value(getattr(view, field.name)) for field in fields(view)}


class View:
    """Mixin for a frozen dataclass whose JSON is exactly its fields."""

    __slots__ = ()

    def to_dict(self) -> dict[str, Any]:
        return view_to_dict(self)
