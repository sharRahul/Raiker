from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PluginPlanRegistry:
    _plans: list[dict[str, Any]] = field(default_factory=list)

    def add_plan(self, plan: dict[str, Any]) -> None:
        self._plans.append(dict(plan))

    def list_plans(self) -> list[dict[str, Any]]:
        return [dict(plan) for plan in self._plans]
