"""The web client's generated read-model types are current (OPT-01).

``web/src/lib/generated/apiViews.ts`` is written by
``scripts/generate_web_api_types.py`` from the backend views. A view changed
without regenerating it would leave the browser compiled against a shape the
server no longer sends — the drift a hand-written mirror allowed — so a stale
file fails here, in the Python job that runs for every backend change.
"""

from __future__ import annotations

import dataclasses

from raiker.contracts.views import View
from scripts.generate_web_api_types import OUTPUT, _wire_is_fields, generated_views, render


def test_the_generated_types_match_the_backend_views() -> None:
    assert OUTPUT.read_text(encoding="utf-8") == render(), (
        "web/src/lib/generated/apiViews.ts is stale; run "
        "`python -m scripts.generate_web_api_types`"
    )


def test_only_views_whose_json_is_their_fields_are_generated() -> None:
    """A view with its own `to_dict` projects differently; deriving it would lie."""
    for name, view in generated_views().items():
        assert issubclass(view, View), name
        assert view.to_dict is View.to_dict, name


@dataclasses.dataclass(frozen=True)
class _Renamed(View):
    value: str

    def to_dict(self) -> dict[str, str]:
        return {"renamed": self.value}


@dataclasses.dataclass(frozen=True)
class _Parent(View):
    child: _Renamed


def test_a_view_nesting_a_custom_projection_is_not_generated() -> None:
    assert not _wire_is_fields(_Renamed)
    assert not _wire_is_fields(_Parent)


def test_a_defaulted_field_is_required_because_it_is_always_sent() -> None:
    text = OUTPUT.read_text(encoding="utf-8")
    assert "?:" not in text
