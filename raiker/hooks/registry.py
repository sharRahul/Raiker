from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from raiker.hooks.contracts import HookConfigError, HookHandler, HookRule

# (relative path under the workspace, scope). Managed config has the highest authority.
_SOURCES: tuple[tuple[str, str], ...] = (
    ("config/managed-hooks.json", "managed"),
    ("config/hooks.json", "project"),
    (".raiker/hooks.json", "local"),
)


def _parse_handler(data: dict[str, Any]) -> HookHandler:
    return HookHandler(
        id=str(data.get("id", "")),
        type=str(data.get("type", "")),
        command=list(data["command"]) if isinstance(data.get("command"), list) else None,
        builtin=str(data["builtin"]) if data.get("builtin") is not None else None,
        args=[str(a) for a in data.get("args", [])],
        timeout_ms=int(data.get("timeout_ms", 5000)),
        decision_authority=bool(data.get("decision_authority", False)),
    )


def _parse_config(data: dict[str, Any], scope: str) -> list[HookRule]:
    if data.get("schema_version") != "1.0" or not isinstance(data.get("hooks"), dict):
        raise HookConfigError("invalid_hooks_config")
    rules: list[HookRule] = []
    for event, entries in data["hooks"].items():
        if not isinstance(entries, list):
            raise HookConfigError(f"hook_event_entries_must_be_list:{event}")
        for entry in entries:
            handlers = [_parse_handler(h) for h in entry.get("handlers", [])]
            rules.append(
                HookRule(
                    event=str(event),
                    matcher=str(entry.get("matcher", "*")),
                    handlers=handlers,
                    scope=scope,
                    if_guard=str(entry["if"]) if entry.get("if") is not None else None,
                )
            )
    return rules


class HooksRegistry:
    def __init__(self, rules: list[HookRule]) -> None:
        self.rules = rules

    @classmethod
    def load(cls, workspace_root: str | Path) -> HooksRegistry:
        root = Path(workspace_root)
        rules: list[HookRule] = []
        for relative, scope in _SOURCES:
            path = root / relative
            if not path.exists():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            rules.extend(_parse_config(data, scope))
        return cls(rules)

    @classmethod
    def from_config(cls, data: dict[str, Any], *, scope: str = "project") -> HooksRegistry:
        return cls(_parse_config(data, scope))

    def is_empty(self) -> bool:
        return not self.rules

    def for_event(self, event: str) -> list[HookRule]:
        return [rule for rule in self.rules if rule.event == event]
