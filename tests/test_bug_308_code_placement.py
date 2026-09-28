"""BUG-308 — code that runs with this machine's network says so, and asks.

CR-05 and CR-09 of the security review: ``python``, ``node``, ``npm`` and
``npx`` passed every argv check and then ran with the host's network, and so
did an allowlisted plugin's entrypoint. The owner's decision (2026-09-28): where
this machine has a sandbox, that code runs inside it; where it has none, the
code still runs, but under its own capability — ``host_network_code_execution``,
its own switch, its decision mode starting at *Ask me* — and Permissions and
the plugin card say which of the two this machine is.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from raiker.contracts.ids import new_id, utc_now
from raiker.events.writer import EventLogWriter
from raiker.execution import code_placement
from raiker.execution.code_placement import (
    HOST_NETWORK_CODE_CAPABILITY,
    argv_of,
    code_runner,
    place_code,
)
from raiker.execution.commands.service import CommandService, CommandServiceError
from raiker.runtime.authority.models import Principal, PrincipalType, RiskLevelValue
from raiker.runtime.authority.router import GovernedAction, RuntimeAuthority
from raiker.runtime.executors import build_default_executor_registry
from raiker.storage.sqlite import SQLiteStore

OWNER = "principal_owner"


@pytest.fixture
def no_sandbox() -> Iterator[None]:
    code_placement.set_sandbox_prober(lambda _root: False)
    yield
    code_placement.set_sandbox_prober(None)


@pytest.fixture
def with_sandbox() -> Iterator[None]:
    code_placement.set_sandbox_prober(lambda _root: True)
    yield
    code_placement.set_sandbox_prober(None)


def _human() -> Principal:
    return Principal(
        principal_id=OWNER,
        principal_type=PrincipalType.HUMAN,
        display_name="Owner",
        role_ids=(),
        is_active=True,
    )


def _shell(command: str) -> GovernedAction:
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id=OWNER,
        action_type="shell",
        tool_or_service_name="shell",
        arguments={"command": command},
        risk_level=RiskLevelValue.MEDIUM,
    )


def _set_gate(store: SQLiteStore, capability: str, state: str) -> None:
    now = utc_now()
    store.upsert_capability_gate_state(
        {
            "capability": capability,
            "state": state,
            "runtime_mode": "",
            "requested_by": OWNER,
            "requested_at": now,
            "reason": "test",
            "created_at": now,
            "updated_at": now,
        }
    )


def _set_mode(store: SQLiteStore, capability: str, mode: str) -> None:
    now = utc_now()
    store.upsert_capability_decision_mode(
        {
            "capability": capability,
            "decision_mode": mode,
            "set_by": OWNER,
            "set_at": now,
            "reason": "test",
            "event_id": None,
            "created_at": now,
            "updated_at": now,
        }
    )


class TestWhatCountsAsCode:
    @pytest.mark.parametrize(
        "argv",
        [["python3", "x.py"], ["node", "a.js"], ["npm", "test"], ["npx", "tsc"], ["pip", "install", "."],
         ["/usr/bin/python3", "x.py"], ["python.exe", "x.py"]],
    )
    def test_a_code_runner_is_recognised_however_it_is_named(self, argv: list[str]) -> None:
        assert code_runner(argv) is not None

    @pytest.mark.parametrize("argv", [["ls"], ["git", "status"], ["grep", "x", "y"], []])
    def test_everything_else_is_not_code(self, argv: list[str]) -> None:
        assert code_runner(argv) is None

    def test_the_argv_of_a_shell_and_a_process_action(self) -> None:
        assert argv_of("shell_execution", {"command": "python3 run.py --fast"}) == [
            "python3", "run.py", "--fast",
        ]
        assert argv_of("process_execution", {"executable": "node", "args": ["a.js"]}) == [
            "node", "a.js",
        ]


class TestWhereItRuns:
    def test_with_a_sandbox_and_no_choice_code_goes_into_it(
        self, tmp_path: Path, with_sandbox: None
    ) -> None:
        placement = place_code(SQLiteStore(tmp_path), OWNER, ["python3", "x.py"], tmp_path)
        assert placement.kind == "sandbox"

    def test_with_no_sandbox_code_runs_with_the_host_network_and_says_so(
        self, tmp_path: Path, no_sandbox: None
    ) -> None:
        placement = place_code(SQLiteStore(tmp_path), OWNER, ["node", "a.js"], tmp_path)
        assert placement.kind == "host_network"
        assert placement.reason == "no_sandbox_on_this_host"

    def test_an_owner_who_chose_the_host_chose_its_network(
        self, tmp_path: Path, with_sandbox: None
    ) -> None:
        store = SQLiteStore(tmp_path)
        store.select_execution_environment(OWNER, "local_native")
        assert place_code(store, OWNER, ["npm", "test"], tmp_path).reason == "owner_chose_host"

    def test_an_owner_who_chose_another_environment_keeps_it(
        self, tmp_path: Path, no_sandbox: None
    ) -> None:
        store = SQLiteStore(tmp_path)
        store.select_execution_environment(OWNER, "container_default")
        assert place_code(store, OWNER, ["python3", "x.py"], tmp_path).kind == "owner_environment"

    def test_a_run_the_sandbox_cannot_host_goes_to_the_host_under_the_named_capability(
        self, tmp_path: Path, with_sandbox: None
    ) -> None:
        placement = place_code(
            SQLiteStore(tmp_path), OWNER, ["npm", "run", "dev"], tmp_path, background=True
        )
        assert placement.kind == "host_network"

    def test_a_command_that_runs_no_code_is_untouched(
        self, tmp_path: Path, no_sandbox: None
    ) -> None:
        assert place_code(SQLiteStore(tmp_path), OWNER, ["ls"], tmp_path).kind == "not_code"


class TestTheCommandServiceNeverRunsHostCodeUnasked:
    def test_host_placed_code_without_the_capability_is_refused(
        self, tmp_path: Path, no_sandbox: None
    ) -> None:
        (tmp_path / "hello.py").write_text("print('hi')\n", encoding="utf-8")
        service = CommandService(tmp_path)
        with pytest.raises(CommandServiceError) as refused:
            service.run_foreground(
                owner_principal_id=OWNER,
                acting_principal_id=OWNER,
                session_id="sess_1",
                turn_id="turn_1",
                action_id=new_id("act_"),
                authority_kind="approval",
                authority_id="apr_1",
                command="python3 hello.py",
                argv=["python3", "hello.py"],
            )
        assert refused.value.reason_code == "host_network_code_not_authorized"

    def test_with_the_capability_it_runs(self, tmp_path: Path, no_sandbox: None) -> None:
        (tmp_path / "hello.py").write_text("print('hi')\n", encoding="utf-8")
        service = CommandService(tmp_path)
        # `python`, as the governed shell allowlist spells it.
        result = service.run_foreground(
            owner_principal_id=OWNER,
            acting_principal_id=OWNER,
            session_id="sess_1",
            turn_id="turn_1",
            action_id=new_id("act_"),
            authority_kind="approval",
            authority_id="apr_1",
            command="python hello.py",
            argv=["python", "hello.py"],
            host_network_code=True,
        )
        assert result["returncode"] == 0
        assert "hi" in result["stdout"]

    def test_an_ordinary_command_needs_nothing_new(self, tmp_path: Path, no_sandbox: None) -> None:
        service = CommandService(tmp_path)
        result = service.run_foreground(
            owner_principal_id=OWNER,
            acting_principal_id=OWNER,
            session_id="sess_1",
            turn_id="turn_1",
            action_id=new_id("act_"),
            authority_kind="approval",
            authority_id="apr_1",
            command="pwd",
            argv=["pwd"],
        )
        assert result["returncode"] == 0


def _authority(tmp_path: Path) -> tuple[SQLiteStore, RuntimeAuthority]:
    store = SQLiteStore(tmp_path)
    authority = RuntimeAuthority(
        store,
        EventLogWriter(store),
        executor_registry=build_default_executor_registry(tmp_path, store),
    )
    return store, authority


def _events(store: SQLiteStore, event_type: str) -> list[dict[str, Any]]:
    return [
        row for row in store.list_event_index(limit=500) if row.get("event_type") == event_type
    ]


class TestTheRouterNamesTheCapability:
    def test_code_with_the_host_network_answers_to_its_own_switch(
        self, tmp_path: Path, no_sandbox: None
    ) -> None:
        store, authority = _authority(tmp_path)
        _set_gate(store, HOST_NETWORK_CODE_CAPABILITY, "disabled")

        result = authority.route_action(_shell("python3 build.py"), _human())

        assert result.decision == "disabled_by_capability_gate"

    def test_turning_shell_off_is_not_walked_around_by_running_python(
        self, tmp_path: Path, no_sandbox: None
    ) -> None:
        store, authority = _authority(tmp_path)
        _set_gate(store, "shell_execution", "disabled")

        result = authority.route_action(_shell("python3 build.py"), _human())

        assert result.decision == "disabled_by_capability_gate"

    def test_never_on_shell_is_never_for_python_too(
        self, tmp_path: Path, no_sandbox: None
    ) -> None:
        store, authority = _authority(tmp_path)
        _set_mode(store, "shell_execution", "deny")

        result = authority.route_action(_shell("node script.js"), _human())

        assert result.decision == "deny"

    def test_never_on_host_network_code_refuses_the_script_and_not_the_listing(
        self, tmp_path: Path, no_sandbox: None
    ) -> None:
        store, authority = _authority(tmp_path)
        _set_mode(store, HOST_NETWORK_CODE_CAPABILITY, "deny")

        assert authority.route_action(_shell("python3 build.py"), _human()).decision == "deny"
        assert authority.route_action(_shell("ls"), _human()).decision != "deny"

    def test_the_reclassification_is_recorded(self, tmp_path: Path, no_sandbox: None) -> None:
        store, authority = _authority(tmp_path)
        _set_mode(store, HOST_NETWORK_CODE_CAPABILITY, "deny")

        authority.route_action(_shell("npm test"), _human())

        classified = _events(store, "code_placement_classified")
        assert classified, "no code_placement_classified event"

    def test_with_a_sandbox_the_command_stays_a_shell_command(
        self, tmp_path: Path, with_sandbox: None
    ) -> None:
        store, authority = _authority(tmp_path)
        _set_gate(store, HOST_NETWORK_CODE_CAPABILITY, "disabled")

        result = authority.route_action(_shell("python3 build.py"), _human())

        # The host-network switch is not asked: the code is headed for the
        # sandbox, and only shell's own gate and mode decide it.
        assert result.decision != "disabled_by_capability_gate"
        assert not _events(store, "code_placement_classified")


class TestPermissionsSaysWhichMachineThisIs:
    def test_a_code_capability_names_the_boundary_and_others_do_not(
        self, tmp_path: Path, no_sandbox: None
    ) -> None:
        from raiker.control.service import RuntimeControlService

        control = RuntimeControlService(tmp_path)
        assert "no native sandbox" in control._network_boundary("shell_execution")
        assert "no native sandbox" in control._network_boundary(HOST_NETWORK_CODE_CAPABILITY)
        assert control._network_boundary("web_fetch") == ""

    def test_with_a_sandbox_it_says_the_code_has_no_network(
        self, tmp_path: Path, with_sandbox: None
    ) -> None:
        from raiker.control.service import RuntimeControlService

        text = RuntimeControlService(tmp_path)._network_boundary("shell_execution")
        assert "with no network" in text


class TestThePluginCardSaysWhereItsCodeRuns:
    def test_a_plugin_not_on_the_allowlist_runs_no_code(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from raiker.runtime.executors.tier4_plugins import plugin_code_runtime

        monkeypatch.delenv("RAIKER_PLUGIN_RUNTIME_ALLOWLIST", raising=False)
        assert plugin_code_runtime("demo")["where"] == "not_enabled"

    def test_with_no_container_it_says_host_network(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from raiker.runtime.executors.tier4_plugins import plugin_code_runtime

        monkeypatch.setenv("RAIKER_PLUGIN_RUNTIME_ALLOWLIST", "demo")
        monkeypatch.delenv("RAIKER_PLUGIN_RUNTIME_IMAGE", raising=False)
        answer = plugin_code_runtime("demo")
        assert answer["where"] == "host_network"
        assert "network" in answer["summary"]

    def test_with_a_container_ready_it_runs_there_instead(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from raiker.runtime.executors import tier4_plugins

        monkeypatch.setenv("RAIKER_PLUGIN_RUNTIME_ALLOWLIST", "demo")
        monkeypatch.setenv("RAIKER_PLUGIN_RUNTIME_IMAGE", "python:3.11-slim")
        monkeypatch.setenv("RAIKER_CONTAINER_IMAGE_ALLOWLIST", "python:3.11-slim")
        monkeypatch.setattr(tier4_plugins.shutil, "which", lambda name: f"/usr/bin/{name}")
        assert tier4_plugins.plugin_code_runtime("demo")["where"] == "isolated"

        seen: list[str] = []

        class _Sandboxed:
            def __init__(self, *_args: Any, **_kwargs: Any) -> None:
                pass

            def execute(self, action: GovernedAction, principal: Principal) -> Any:
                seen.append(action.action_id)
                return "ran-in-container"

        monkeypatch.setattr(tier4_plugins, "PluginSandboxedRuntimeExecutor", _Sandboxed)
        action = GovernedAction(
            action_id=new_id("act_"),
            principal_id=OWNER,
            action_type="plugin_runtime_cap",
            tool_or_service_name="plugin_runtime_cap",
            arguments={"plugin_id": "demo", "entrypoint": "main.py"},
        )
        outcome = tier4_plugins.PluginRuntimeExecutor(tmp_path, SQLiteStore(tmp_path)).execute(
            action, _human()
        )
        assert outcome == "ran-in-container"
        assert seen == [action.action_id]
