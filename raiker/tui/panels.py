from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Panel:
    panel_id: str
    display_name: str
    can_mutate_state: bool = False


DEFAULT_PANELS = [
    Panel("primary", "Primary / Main Panel"),
    Panel("activity", "Activity Panel"),
    Panel("input", "Input Panel"),
    Panel("status_bar", "Status Bar Panel"),
]
