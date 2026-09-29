"""CR-01 — a real executor runs only when the runtime authority dispatches it.

The security review's P0: nothing made it *impossible* to fetch a side-effecting
executor and call it without the reference monitor. The registry now hands out
each executor behind the dispatch token ``RuntimeAuthority.route_action`` issues
for one capability and one action (CR-03), and the one other way to reach an
executor — constructing its class — is held to a short, reasoned list here.

The review's acceptance test is the first one below: a synthetic direct
invocation without runtime-issued authority fails before any side effect.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from raiker.runtime.authority.models import Principal, RiskLevelValue
from raiker.runtime.authority.routed import routed_dispatch
from raiker.runtime.authority.router import GovernedAction
from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES, build_default_executor_registry
from raiker.runtime.executors.base import ExecutionResult
from raiker.runtime.executors.registry import ExecutorRegistry, RoutedExecutor
from raiker.storage.sqlite import SQLiteStore
from tests.factories import governed_action, human

ROOT = Path(__file__).resolve().parents[1]


class _Spy:
    capability = "file_write_execution"

    def __init__(self) -> None:
        self.calls = 0

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        self.calls += 1
        return ExecutionResult(ok=True, capability=self.capability, action_id=action.action_id)


def _action(capability: str = "file_write_execution", **arguments: Any) -> GovernedAction:
    return governed_action(
        capability,
        principal_id="principal_owner",
        arguments=arguments,
        risk_level=RiskLevelValue.HIGH,
    )


def _principal() -> Principal:
    return human("principal_owner", role_ids=())


class TestTheRegistryHandsOutOnlyRoutedExecutors:
    def test_a_direct_call_is_refused_before_the_executor_runs(self) -> None:
        spy = _Spy()
        registry = ExecutorRegistry()
        registry.register("file_write_execution", spy)
        executor = registry.get("file_write_execution")
        assert executor is not None

        result = executor.execute(_action(), _principal())

        assert result.ok is False
        assert result.reason_code == "executor_not_routed"
        assert spy.calls == 0

    def test_the_live_dispatch_of_this_action_runs_it(self) -> None:
        spy = _Spy()
        registry = ExecutorRegistry()
        registry.register("file_write_execution", spy)
        executor = registry.get("file_write_execution")
        assert executor is not None
        action = _action()

        with routed_dispatch("file_write_execution", action.action_id):
            result = executor.execute(action, _principal())

        assert result.ok is True
        assert spy.calls == 1

    def test_a_dispatch_of_another_action_does_not_lend_its_authority(self) -> None:
        spy = _Spy()
        registry = ExecutorRegistry()
        registry.register("file_write_execution", spy)
        executor = registry.get("file_write_execution")
        assert executor is not None

        with routed_dispatch("file_write_execution", "act_some_other_action"):
            result = executor.execute(_action(), _principal())

        assert result.reason_code == "executor_not_routed"
        assert spy.calls == 0

    def test_a_dispatch_of_another_capability_does_not_lend_its_authority(self) -> None:
        spy = _Spy()
        registry = ExecutorRegistry()
        registry.register("file_write_execution", spy)
        executor = registry.get("file_write_execution")
        assert executor is not None
        action = _action()

        with routed_dispatch("web_fetch", action.action_id):
            result = executor.execute(action, _principal())

        assert result.reason_code == "executor_not_routed"
        assert spy.calls == 0

    def test_a_token_does_not_outlive_its_dispatch(self) -> None:
        spy = _Spy()
        registry = ExecutorRegistry()
        registry.register("file_write_execution", spy)
        executor = registry.get("file_write_execution")
        assert executor is not None
        action = _action()
        with routed_dispatch("file_write_execution", action.action_id):
            pass

        assert executor.execute(action, _principal()).reason_code == "executor_not_routed"


class TestTheRealRegistry:
    def test_every_real_executor_is_guarded(self, tmp_path: Path) -> None:
        registry = build_default_executor_registry(tmp_path, SQLiteStore(tmp_path))
        for capability in registry.capabilities():
            executor = registry.get(capability)
            assert isinstance(executor, RoutedExecutor), capability
            assert executor.capability == capability
        assert registry.capabilities() <= REAL_EXECUTOR_CAPABILITIES

    def test_the_acceptance_test_a_direct_write_changes_nothing(self, tmp_path: Path) -> None:
        registry = build_default_executor_registry(tmp_path, SQLiteStore(tmp_path))
        executor = registry.get("file_write_execution")
        assert executor is not None
        target = tmp_path / "direct.md"

        result = executor.execute(
            _action(path=str(target), content="written without authority"), _principal()
        )

        assert result.reason_code == "executor_not_routed"
        assert not target.exists()


# ── The other way in: constructing an executor class ──────────────────────────

#: Every place outside the registry builder that constructs an executor class,
#: and why that is not a way around the authority. A new one fails this file
#: until it is either routed or listed here with its reason.
_DIRECT_CONSTRUCTIONS: dict[tuple[str, str], str] = {
    ("raiker/runtime/authority/router.py", "ApprovalExecutionRelay"): (
        "The authority itself, relaying a critical approval the owner just "
        "confirmed with step-up; the relay re-governs its target through "
        "RuntimeAuthority, so the target is routed."
    ),
    ("raiker/runtime/executors/scheduled.py", "SubagentExecutor"): (
        "A scheduled routine's bounded read-only steps, run inside the routed "
        "dispatch of `scheduled_routines`, whose own gate and mode admitted it."
    ),
    ("raiker/runtime/executors/tier2_shell.py", "ShellExecutor"): (
        "Held by `HostNetworkCodeExecutor`, which the registry guards under "
        "`host_network_code_execution`; it runs only inside that dispatch (BUG-308)."
    ),
    ("raiker/runtime/executors/tier2_shell.py", "ProcessExecutor"): (
        "Held by `HostNetworkCodeExecutor` for the `process` half of the same "
        "capability, inside the same guarded dispatch (BUG-308)."
    ),
    ("raiker/runtime/executors/tier4_plugins.py", "PluginSandboxedRuntimeExecutor"): (
        "The bare plugin runtime hands a run to the no-network container when "
        "this machine has one, inside the routed dispatch of `plugin_runtime_cap` "
        "(BUG-308): only ever a stricter boundary than the one routed."
    ),
    ("raiker/tools/mcp_tools.py", "McpConnectorExecutor"): (
        "The chat MCP tool applies `mcp_connector_runtime`'s own gate and "
        "decision mode before it constructs the connector, the governed-service "
        "pattern CR-03 describes."
    ),
}


def _executor_classes() -> set[str]:
    names: set[str] = set()
    for path in (ROOT / "raiker" / "runtime" / "executors").rglob("*.py"):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if not isinstance(node, ast.ClassDef):
                continue
            methods = {item.name for item in node.body if isinstance(item, ast.FunctionDef)}
            declares_capability = any(
                isinstance(item, (ast.Assign, ast.AnnAssign))
                and "capability" in ast.unparse(item).split("=")[0]
                for item in node.body
            )
            if "execute" in methods and declares_capability:
                names.add(node.name)
    return names


def test_no_executor_is_constructed_outside_the_builder_without_a_reason() -> None:
    classes = _executor_classes()
    assert len(classes) > 30, "the executor scan found almost nothing; it has gone stale"
    found: set[tuple[str, str]] = set()
    for path in (ROOT / "raiker").rglob("*.py"):
        relative = path.relative_to(ROOT).as_posix()
        if relative == "raiker/runtime/executors/__init__.py":
            continue  # the registry builder: everything it builds is guarded
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = (
                func.id
                if isinstance(func, ast.Name)
                else func.attr
                if isinstance(func, ast.Attribute)
                else None
            )
            if name in classes:
                found.add((relative, name))
    unlisted = sorted(found - set(_DIRECT_CONSTRUCTIONS))
    assert unlisted == [], f"an executor is constructed outside the registry: {unlisted}"
    stale = sorted(set(_DIRECT_CONSTRUCTIONS) - found)
    assert stale == [], f"listed constructions that no longer exist: {stale}"


@pytest.mark.parametrize("reason", list(_DIRECT_CONSTRUCTIONS.values()))
def test_every_listed_construction_says_why(reason: str) -> None:
    assert len(reason) > 40
