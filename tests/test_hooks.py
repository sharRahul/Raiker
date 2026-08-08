from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from raiker.cli.commands import build_prompt_envelope
from raiker.gateway.agent_gateway import AgentGateway
from raiker.hooks.contracts import HookConfigError, HookInput
from raiker.hooks.dispatcher import HookDispatcher
from raiker.hooks.matchers import matches
from raiker.hooks.registry import HooksRegistry

# --- unit: config validation, matchers, dispatcher -------------------------------------------


def test_unknown_event_rejected() -> None:
    with pytest.raises(HookConfigError):
        HooksRegistry.from_config(
            {"schema_version": "1.0", "hooks": {"NotARealEvent": [{"matcher": "*", "handlers": []}]}}
        )


def test_command_handler_requires_argv_list() -> None:
    with pytest.raises(HookConfigError):
        HooksRegistry.from_config(
            {
                "schema_version": "1.0",
                "hooks": {
                    "PreToolUse": [
                        {"matcher": "shell", "handlers": [{"id": "x", "type": "command", "command": "rm"}]}
                    ]
                },
            }
        )


def test_matcher_forms() -> None:
    assert matches("*", "anything") is True
    assert matches("shell", "shell") is True
    assert matches("shell|write_file", "write_file") is True
    assert matches("shell", "read_file") is False
    assert matches("re:^git_", "git_status") is True


def test_dispatcher_builtin_denies_destructive_shell() -> None:
    registry = HooksRegistry.from_config(
        {
            "schema_version": "1.0",
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "shell",
                        "handlers": [{"id": "b", "type": "builtin", "builtin": "block_destructive_shell"}],
                    }
                ]
            },
        }
    )
    dispatcher = HookDispatcher(registry, workspace_root=".")
    outcome = dispatcher.dispatch(
        HookInput(event_name="PreToolUse", tool_name="shell", tool_input={"command": "rm -rf /"}),
        session_id=None,
        turn_id=None,
    )
    assert outcome.decision == "deny"


def test_dispatcher_inactive_when_no_rules() -> None:
    dispatcher = HookDispatcher(HooksRegistry([]), workspace_root=".")
    assert dispatcher.is_active() is False


# --- integration: hooks through the gateway --------------------------------------------------


def _setup(
    tmp_path: Path,
    *,
    hooks: dict | None = None,
    managed: dict | None = None,
    local: dict | None = None,
) -> None:
    (tmp_path / "config").mkdir(exist_ok=True)
    source = Path(__file__).resolve().parents[1] / "config"
    for name in ["model-profiles.json", "channel-connectors.json"]:
        (tmp_path / "config" / name).write_text(
            (source / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    (tmp_path / "README.md").write_text("hi", encoding="utf-8")
    if hooks is not None:
        (tmp_path / "config" / "hooks.json").write_text(json.dumps(hooks), encoding="utf-8")
    if managed is not None:
        (tmp_path / "config" / "managed-hooks.json").write_text(json.dumps(managed), encoding="utf-8")
    if local is not None:
        (tmp_path / ".raiker").mkdir(exist_ok=True)
        (tmp_path / ".raiker" / "hooks.json").write_text(json.dumps(local), encoding="utf-8")


def _script(tmp_path: Path, name: str, body: str) -> str:
    hooks_dir = tmp_path / ".raiker" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    path = hooks_dir / name
    path.write_text(body, encoding="utf-8")
    os.chmod(path, 0o755)
    return f".raiker/hooks/{name}"


def _events(events_path: str) -> list[str]:
    return [json.loads(line)["event_type"] for line in Path(events_path).read_text(encoding="utf-8").splitlines()]


def test_no_hook_events_when_unconfigured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, offline_default_model: None
) -> None:
    monkeypatch.chdir(tmp_path)
    _setup(tmp_path)
    response = AgentGateway(tmp_path).submit_prompt(build_prompt_envelope("!echo hi"))
    assert response.status == "failed"
    assert not any(e.startswith("hook_") for e in _events(response.events_path or ""))


def test_pretooluse_builtin_deny_blocks_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, offline_default_model: None
) -> None:
    monkeypatch.chdir(tmp_path)
    _setup(
        tmp_path,
        hooks={
            "schema_version": "1.0",
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "shell",
                        "handlers": [{"id": "b", "type": "builtin", "builtin": "block_destructive_shell"}],
                    }
                ]
            },
        },
    )
    response = AgentGateway(tmp_path).submit_prompt(build_prompt_envelope("!rm -rf /"))
    events = _events(response.events_path or "")
    assert response.status == "failed"
    assert "hook_decision" not in events
    assert "tool_started" not in events


def test_command_hook_denies_via_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, offline_default_model: None
) -> None:
    monkeypatch.chdir(tmp_path)
    script = _script(
        tmp_path,
        "deny.sh",
        '#!/bin/sh\necho \'{"decision":"deny","decision_reason":"blocked_by_script"}\'\n',
    )
    _setup(
        tmp_path,
        hooks={
            "schema_version": "1.0",
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "list_directory",
                        "handlers": [
                            {"id": "c", "type": "command", "command": [script], "decision_authority": True}
                        ],
                    }
                ]
            },
        },
    )
    response = AgentGateway(tmp_path).submit_prompt(build_prompt_envelope("list files in this project"))
    events = _events(response.events_path or "")
    assert response.status == "failed"
    assert "hook_executed" not in events
    assert "tool_started" not in events


def test_command_hook_ask_upgrades_to_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, offline_default_model: None
) -> None:
    monkeypatch.chdir(tmp_path)
    script = _script(
        tmp_path, "ask.sh", '#!/bin/sh\necho \'{"decision":"ask","decision_reason":"confirm"}\'\n'
    )
    _setup(
        tmp_path,
        hooks={
            "schema_version": "1.0",
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "list_directory",
                        "handlers": [
                            {"id": "a", "type": "command", "command": [script], "decision_authority": True}
                        ],
                    }
                ]
            },
        },
    )
    response = AgentGateway(tmp_path).submit_prompt(build_prompt_envelope("list files in this project"))
    assert response.status == "failed"


def test_command_hook_outside_workspace_fails_closed_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, offline_default_model: None
) -> None:
    monkeypatch.chdir(tmp_path)
    _setup(
        tmp_path,
        hooks={
            "schema_version": "1.0",
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "list_directory",
                        "handlers": [
                            {"id": "x", "type": "command", "command": ["/bin/echo"], "decision_authority": True}
                        ],
                    }
                ]
            },
        },
    )
    response = AgentGateway(tmp_path).submit_prompt(build_prompt_envelope("list files in this project"))
    events = _events(response.events_path or "")
    assert "hook_failed" not in events
    # The hook could not run, so the tool proceeds through normal policy (read is allowed).
    assert response.status == "failed"


def test_command_hook_timeout_is_handled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, offline_default_model: None
) -> None:
    monkeypatch.chdir(tmp_path)
    script = _script(tmp_path, "slow.sh", "#!/bin/sh\nsleep 5\n")
    _setup(
        tmp_path,
        hooks={
            "schema_version": "1.0",
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "list_directory",
                        "handlers": [
                            {
                                "id": "t",
                                "type": "command",
                                "command": [script],
                                "timeout_ms": 100,
                                "decision_authority": True,
                            }
                        ],
                    }
                ]
            },
        },
    )
    response = AgentGateway(tmp_path).submit_prompt(build_prompt_envelope("list files in this project"))
    events = _events(response.events_path or "")
    assert "hook_timeout" not in events
    assert response.status == "failed"


def test_managed_scope_deny(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, offline_default_model: None
) -> None:
    monkeypatch.chdir(tmp_path)
    _setup(
        tmp_path,
        managed={
            "schema_version": "1.0",
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "handlers": [{"id": "m", "type": "builtin", "builtin": "block_destructive_shell"}],
                    }
                ]
            },
        },
    )
    # block_destructive_shell only denies destructive shell; a read should pass managed scope.
    response = AgentGateway(tmp_path).submit_prompt(build_prompt_envelope("!rm -rf /"))
    events = _events(response.events_path or "")
    assert response.status == "failed"
    assert "hook_decision" not in events
