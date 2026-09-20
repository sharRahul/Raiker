# SPDX-License-Identifier: Apache-2.0
"""Compare the TypeScript API mirror against the backend DTOs it mirrors.

GCR-42. ``web/src/lib/apiTypes.ts`` says of itself that it mirrors the backend
DTOs and that the backend remains the source of truth. That was true and
unenforced: the file is a hand-maintained copy of a contract defined elsewhere,
and the guard standing behind it — ``tests/test_api_contract_schemas.py`` —
was a *second* hand-maintained copy, a set of field names transcribed out of
the TypeScript into Python. Three hands had to agree, and only two of them ever
failed a build.

This derives the comparison instead of transcribing it. Every backend
``@dataclass`` whose name is ``<Name>View`` is paired with the interface called
``<Name>`` in the TypeScript file, and every field that interface declares as
required must exist on the dataclass. The direction is deliberate and matches
the older guard's: the backend may carry fields the UI ignores, but it may
never drop one the UI reads.

What it deliberately does not do is compare *types*. The mirror uses the type
vocabulary of a different language — string unions where Python has `str`,
`Record<string, …>` where Python has `dict[str, Any]` — and asserting a
correspondence between those would be asserting a translation table nobody
maintains. Field presence is what silently breaks a page; a widened union is
not.

Run it directly (`python -m scripts.check_api_contract`) or through
``tests/test_api_contract_generated.py``, which is how CI reaches it.
"""

from __future__ import annotations

import ast
import dataclasses
import importlib
import inspect
import re
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
API_TYPES = REPO_ROOT / "web" / "src" / "lib" / "apiTypes.ts"

#: Where the backend's read DTOs live. A module added here is covered from the
#: moment its first ``…View`` dataclass gets a TypeScript mirror.
DTO_MODULES = (
    "raiker.control.dtos",
    "raiker.control.dashboard",
    "raiker.control.service",
    "raiker.control.web_read_models",
)

#: Interfaces in the mirror that are not a ``…View`` at all: request bodies,
#: hand-shaped client helpers, and unions assembled in the browser. They have no
#: backend dataclass to be compared with, so pairing them by name would compare
#: them with nothing and report a false pass.
_UNPAIRED_SUFFIXES = ("Request", "Body", "Payload", "Params", "Options", "Props")

#: Interfaces whose name collides with a backend DTO they are not a mirror of.
#: Each entry names why, because an exclusion with no reason is how a real drift
#: gets silenced.
_NOT_MIRRORS = {
    # The TypeScript shape is the *envelope* the route returns — `{providers:
    # [...]}` — and `ProviderCatalogueRefreshView` is one element of that list.
    # Pairing them by name compares a wrapper with its contents.
    "ProviderCatalogueRefresh",
}

_INTERFACE = re.compile(r"^export interface (\w+)\s*(?:extends\s+[\w\s,]+)?\{\s*$")
_FIELD = re.compile(r"^\s{2}(\w+)(\?)?\s*:")
_CLOSE = re.compile(r"^\}\s*$")


@dataclass(frozen=True)
class Drift:
    """One field the browser reads and the backend does not send."""

    interface: str
    dataclass_name: str
    field_name: str

    def __str__(self) -> str:
        return (
            f"{self.interface}.{self.field_name} is required in apiTypes.ts but "
            f"{self.dataclass_name} has no such field"
        )


def parse_interfaces(source: str) -> dict[str, dict[str, bool]]:
    """``{interface: {field: optional}}`` for each top-level interface.

    A deliberately shallow parse: only two-space-indented members are read, so a
    nested object literal's own keys are not mistaken for the interface's.
    """
    interfaces: dict[str, dict[str, bool]] = {}
    current: str | None = None
    for line in source.splitlines():
        if current is None:
            match = _INTERFACE.match(line)
            if match:
                current = match.group(1)
                interfaces[current] = {}
            continue
        if _CLOSE.match(line):
            current = None
            continue
        field_match = _FIELD.match(line)
        if field_match:
            interfaces[current][field_match.group(1)] = bool(field_match.group(2))
    return interfaces


def serialised_keys(dto: type) -> set[str]:
    """What one DTO actually puts on the wire.

    Its dataclass fields, plus any literal key its own ``to_dict`` adds. A view
    that computes a key rather than storing it — a constant notice, a derived
    count — is sending that key just as surely as a stored one, and comparing
    only against ``dataclasses.fields`` would report the browser reading a field
    the backend does send.
    """
    keys = {item.name for item in dataclasses.fields(dto)}
    to_dict = getattr(dto, "to_dict", None)
    if to_dict is None:
        return keys
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(to_dict)))
    except (OSError, TypeError, SyntaxError):
        return keys
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys.update(
            key.value
            for key in node.keys
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        )
    return keys


def backend_dataclasses() -> dict[str, type]:
    """Every ``@dataclass`` the read modules define, by class name."""
    found: dict[str, type] = {}
    for module_name in DTO_MODULES:
        module = importlib.import_module(module_name)
        for name in dir(module):
            value = getattr(module, name)
            if isinstance(value, type) and dataclasses.is_dataclass(value):
                found.setdefault(name, value)
    return found


def pairs(
    interfaces: dict[str, dict[str, bool]], dtos: dict[str, type]
) -> dict[str, str]:
    """``{interface: dataclass}`` for every mirror that has a backend original."""
    matched: dict[str, str] = {}
    for interface in interfaces:
        if interface.endswith(_UNPAIRED_SUFFIXES) or interface in _NOT_MIRRORS:
            continue
        for candidate in (f"{interface}View", interface):
            if candidate in dtos:
                matched[interface] = candidate
                break
    return matched


def drifts() -> list[Drift]:
    """Every required mirror field with no backend field behind it."""
    interfaces = parse_interfaces(API_TYPES.read_text(encoding="utf-8"))
    dtos = backend_dataclasses()
    found: list[Drift] = []
    for interface, dataclass_name in sorted(pairs(interfaces, dtos).items()):
        backend_fields = serialised_keys(dtos[dataclass_name])
        for name, optional in interfaces[interface].items():
            if not optional and name not in backend_fields:
                found.append(Drift(interface, dataclass_name, name))
    return found


def main() -> int:
    found = drifts()
    interfaces = parse_interfaces(API_TYPES.read_text(encoding="utf-8"))
    checked = pairs(interfaces, backend_dataclasses())
    print(f"paired {len(checked)} of {len(interfaces)} interfaces in {API_TYPES.name}")
    for drift in found:
        print(f"refused: {drift}", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
