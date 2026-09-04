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

#: Where an installed plugin's contributed hook rules are written (BUG-221).
#:
#: A plugin contributes through a surface that is already governed rather than
#: through a new one. Hooks were the first candidate for exactly that reason: a
#: hook already has an execution model (argv resolved inside the workspace, under
#: a bounded timeout), an audit trail, and a scope — and ``plugin`` sits below
#: ``managed``, ``user``, ``project`` and ``local`` in :data:`HOOK_SCOPES`, so a
#: plugin rule can never override a deny the owner or their organisation set.
#:
#: The contribution is a *file*, deliberately. It is the owner's to read, the
#: owner's to delete, and revoking the plugin removes it — so "what does this
#: plugin do" has an answer that does not require trusting the manifest.
PLUGIN_HOOKS_DIR = ".raiker/plugins"
PLUGIN_HOOKS_FILE = "hooks.json"


def _parse_handler(data: dict[str, Any]) -> HookHandler:
    handler_type = str(data.get("type", ""))
    return HookHandler(
        id=str(data.get("id", "")),
        type=handler_type,
        command=list(data["command"]) if isinstance(data.get("command"), list) else None,
        builtin=str(data["builtin"]) if data.get("builtin") is not None else None,
        prompt=str(data["prompt"]) if data.get("prompt") is not None else None,
        model=str(data["model"]) if data.get("model") is not None else None,
        url=str(data["url"]) if data.get("url") is not None else None,
        args=[str(a) for a in data.get("args", [])],
        timeout_ms=int(data.get("timeout_ms", 5000)),
        max_tokens=int(data.get("max_tokens", 256)),
        # A model's output is evidence, never authority. Even a project file that
        # asks for it cannot turn an advisory prompt into a policy decision.
        decision_authority=(
            bool(data.get("decision_authority", False)) if handler_type != "prompt" else False
        ),
    )


def _parse_config(data: dict[str, Any], scope: str, source: str | None = None) -> list[HookRule]:
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
                    source=source,
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


def _plugin_sources(root: Path) -> list[tuple[str, str]]:
    """Every installed plugin's contributed hooks file, in a stable order.

    Sorted by plugin id so two plugins contributing rules for the same event
    always load in the same order — the aggregate decision does not depend on
    it (a deny from either wins), but the audit trail and the Hooks page do, and
    a list that reshuffles between reads is a list nobody trusts.

    Missing directory, unreadable directory: no plugin rules. A contribution that
    cannot be read is not guessed at.
    """
    plugins_dir = root / PLUGIN_HOOKS_DIR
    try:
        entries = sorted(entry.name for entry in plugins_dir.iterdir() if entry.is_dir())
    except OSError:
        return []
    return [
        (f"{PLUGIN_HOOKS_DIR}/{name}/{PLUGIN_HOOKS_FILE}", "plugin")
        for name in entries
        if (plugins_dir / name / PLUGIN_HOOKS_FILE).is_file()
    ]


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
        for relative, scope in (*_SOURCES, *_plugin_sources(root)):
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
                parsed = _parse_config(data, scope, relative)
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
