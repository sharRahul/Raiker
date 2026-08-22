from __future__ import annotations

import json
from dataclasses import dataclass
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


@dataclass(frozen=True)
class HookSourceStatus:
    """What one configuration file contributed, and why it contributed nothing.

    A hooks file is owner-authored text on disk. A typo in it used to raise out of
    ``HooksRegistry.load``, which runs inside the ``AgentGateway`` constructor —
    so one misplaced brace made **every prompt in the product fail**, with a raw
    ``JSONDecodeError`` and nothing anywhere that said which file was wrong.

    Failing closed is right for the *hook*: a file Raiker cannot read must not be
    guessed at, and none of its rules load. Failing closed for the whole runtime
    is not, and neither is failing silently. So a bad source becomes a recorded
    status the owner can be shown, and the rest of the runtime is untouched.
    """

    path: str
    scope: str
    exists: bool
    loaded: bool
    rule_count: int
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "scope": self.scope,
            "exists": self.exists,
            "loaded": self.loaded,
            "rule_count": self.rule_count,
            "error": self.error,
        }


class HooksRegistry:
    def __init__(
        self, rules: list[HookRule], sources: list[HookSourceStatus] | None = None
    ) -> None:
        self.rules = rules
        self.sources = sources or []

    @classmethod
    def load(cls, workspace_root: str | Path) -> HooksRegistry:
        """Read every configured source, keeping a broken one from taking the rest.

        This never raises. A source that cannot be parsed contributes no rules and
        is reported through :attr:`sources`; see :class:`HookSourceStatus` for why
        that is the fail-closed behaviour rather than the lenient one.
        """
        root = Path(workspace_root)
        rules: list[HookRule] = []
        sources: list[HookSourceStatus] = []
        for relative, scope in _SOURCES:
            path = root / relative
            if not path.exists():
                sources.append(
                    HookSourceStatus(
                        path=relative, scope=scope, exists=False, loaded=False, rule_count=0
                    )
                )
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                parsed = _parse_config(data, scope)
            except json.JSONDecodeError as exc:
                sources.append(
                    HookSourceStatus(
                        path=relative,
                        scope=scope,
                        exists=True,
                        loaded=False,
                        rule_count=0,
                        error=f"invalid_json:{exc.lineno}:{exc.colno}",
                    )
                )
                continue
            except (HookConfigError, OSError, TypeError, ValueError) as exc:
                sources.append(
                    HookSourceStatus(
                        path=relative,
                        scope=scope,
                        exists=True,
                        loaded=False,
                        rule_count=0,
                        error=str(exc),
                    )
                )
                continue
            rules.extend(parsed)
            sources.append(
                HookSourceStatus(
                    path=relative,
                    scope=scope,
                    exists=True,
                    loaded=True,
                    rule_count=len(parsed),
                )
            )
        return cls(rules, sources)

    @classmethod
    def from_config(cls, data: dict[str, Any], *, scope: str = "project") -> HooksRegistry:
        """Parse one in-memory config, raising on anything invalid.

        Unlike :meth:`load` this is the explicit-parse path: a caller handing over
        a config wants to be told it is wrong, not handed an empty registry.
        """
        return cls(_parse_config(data, scope))

    def is_empty(self) -> bool:
        return not self.rules

    def for_event(self, event: str) -> list[HookRule]:
        return [rule for rule in self.rules if rule.event == event]

    def failed_sources(self) -> list[HookSourceStatus]:
        """Configured files that exist but could not be read."""
        return [source for source in self.sources if source.exists and not source.loaded]
