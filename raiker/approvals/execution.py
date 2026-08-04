"""Wire a human's *Approve* decision to real execution (BUG-06).

Raiker's approval inbox has always been metadata-only: resolving an approval
recorded a decision and nothing else, so a model-proposed ``write_file`` never
wrote a file. That was honest — the README said so — but it meant no surface in
the app could produce a durable artifact, and Build's premise ("every file
write, patch, and command becomes a decision you accept or reject") could not
close its loop.

This module is the bridge, and it is deliberately narrow. It does not implement
execution: it hands the approval to :class:`ApprovalExecutionRelay`, which
already implements the hard parts (TTL, argument-hash TOCTOU check, posture
check, atomic single-execution claim, and re-routing the target through
:class:`RuntimeAuthority` so it re-passes its own capability gate, decision mode
and policy review *at execution time*). The relay is itself entered through
``route_action``, so the "governed entry only" property in
``docs/threat-models/approval-execution-relay.md`` holds unchanged.

What is relayed, and what is not:

* only :data:`EXECUTABLE_ON_APPROVAL` — checkpointed file mutations, the
  owner-configured remote/cloud command capabilities, bounded local ``shell``
  commands, and the two local planning mutations (a task row, a project label).
  ``process``, ``network`` and every other capability keep metadata-only
  resolution.
* **critical** approvals never come here. They keep the human-only, step-up
  gated lifecycle in :meth:`RuntimeAuthority.resolve_critical_approval`.
* if either gate is off — the relay's own ``approval_execution_relay`` or the
  target capability's — resolution falls back to metadata-only. The owner's off
  switch still wins, and the UI is told which of the two it is before the owner
  decides, not after.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from raiker.contracts.ids import new_id
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority.models import Principal, RiskLevelValue
from raiker.runtime.authority.router import (
    CAPABILITY_GATE_MAP,
    GovernedAction,
    RuntimeAuthority,
)
from raiker.storage.sqlite import SQLiteStore

RELAY_CAPABILITY = "approval_execution_relay"

# The only capabilities an ordinary (non-critical) approval resolution executes.
EXECUTABLE_ON_APPROVAL: frozenset[str] = frozenset({
    "file_write_execution",
    "patch_apply_execution",
    "shell_execution",
    "remote_execution_cap",
    "cloud_execution_cap",
    # BUG-62 — a task row and a project label are local, reversible and
    # owner-scoped, which is the same argument that put file mutations here.
    # Leaving them out meant the owner was shown a high-risk decision, told what
    # approving would do, approved it, and got nothing.
    "task_management_runtime",
    "project_assignment_runtime",
})


@dataclass(frozen=True)
class ApprovalExecution:
    """The outcome of relaying one approved action into real execution."""

    ok: bool
    # Terminal approval status as persisted by the relay: `executed`,
    # `execution_failed`, or `pending` when governance blocked before any
    # executor ran and the relay released its claim.
    status: str
    capability: str
    reason_code: str | None = None
    artifacts: dict[str, Any] = field(default_factory=dict)


def executable_capability(tool_name: str) -> str | None:
    """The relayable capability behind *tool_name*, or None if it is not one."""
    capability = CAPABILITY_GATE_MAP.get(tool_name, tool_name)
    return capability if capability in EXECUTABLE_ON_APPROVAL else None


def approval_arguments(approval: dict[str, Any]) -> dict[str, Any]:
    """The approved action's arguments — the immutable intent the relay verified."""
    try:
        parsed = json.loads(str(approval.get("arguments_json", "{}")))
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


class ApprovalExecutionBridge:
    """Answers "will approving this execute?" and, on approval, executes it."""

    def __init__(self, store: SQLiteStore, writer: EventLogWriter | None = None) -> None:
        self._store = store
        self._writer = writer or EventLogWriter(store)
        self._authority: RuntimeAuthority | None = None

    def _authority_for_execution(self) -> RuntimeAuthority:
        """The authority the relay is entered through — with real executors.

        ``RuntimeAuthority``'s default registry is empty, which would fail closed
        with ``execution_unavailable:no_executor``. Building the default registry
        here is what makes the relay reachable at all.
        """
        if self._authority is None:
            from raiker.runtime.executors import build_default_executor_registry

            self._authority = RuntimeAuthority(
                self._store,
                self._writer,
                executor_registry=build_default_executor_registry(
                    self._store.paths.workspace_root, self._store
                ),
            )
        return self._authority

    def _gate_blocked(self, name: str, principal_id: str | None) -> str | None:
        # Same call shape `route_action` uses, so the answer given to the owner
        # before they decide cannot disagree with the answer enforced after.
        return self._authority_for_execution().check_capability_gate(
            name, name, principal_id
        )

    def executes_on_resolution(
        self, tool_name: str, principal_id: str | None, *, critical: bool = False
    ) -> bool:
        """True when approving this action will really perform it.

        Read by the approval detail view and the tool broker so the owner is told
        what Approve does *before* they press it. Both gates are consulted: the
        relay's own, and the target capability the relay will re-route into.
        """
        if critical:
            return False
        if executable_capability(tool_name) is None:
            return False
        if self._gate_blocked(RELAY_CAPABILITY, principal_id) is not None:
            return False
        return self._gate_blocked(tool_name, principal_id) is None

    def execute(
        self,
        approval: dict[str, Any],
        principal: Principal,
        *,
        session_id: str,
        reason: str = "",
    ) -> ApprovalExecution:
        """Relay one approved, non-critical, pending approval into execution.

        *session_id* is the resolving **API session**, matching what the critical
        lifecycle passes, so a revoked approving session is caught by the relay's
        posture check (A4).
        """
        approval_id = str(approval["approval_id"])
        tool_name = str(approval.get("tool_name", ""))
        capability = executable_capability(tool_name) or tool_name
        relay_action = GovernedAction(
            action_id=new_id("act_"),
            principal_id=principal.principal_id,
            action_type=RELAY_CAPABILITY,
            tool_or_service_name=RELAY_CAPABILITY,
            arguments={"approval_id": approval_id},
            risk_level=RiskLevelValue.LOW,
            session_id=session_id,
            turn_id=approval.get("turn_id"),
        )
        result = self._authority_for_execution().route_action(relay_action, principal)
        executed = result.decision == "allow" and result.error is None
        current = self._store.load_approval(approval_id)
        status = str((current or approval).get("status", "pending"))
        if not executed:
            return ApprovalExecution(
                ok=False,
                status=status,
                capability=capability,
                reason_code=result.error or result.message or result.decision,
            )
        # The relay records `approval_executed`; this records the *decision* that
        # authorised it, in the same shape the metadata-only inbox emits, so the
        # audit trail keeps one story for "a human approved this" regardless of
        # which path the resolution took.
        self._writer.append(
            make_event(
                session_id=str(approval.get("session_id") or "approval_inbox"),
                turn_id=approval.get("turn_id"),
                event_type="approval_received",
                actor="approval_inbox",
                payload={
                    "approval_id": approval_id,
                    "action_id": str(approval.get("action_id", "")),
                    "status": "approved",
                    "reason": reason,
                    "executes_action": True,
                    "capability": capability,
                },
            )
        )
        relay_result = result.artifacts.get("result")
        return ApprovalExecution(
            ok=True,
            status=status,
            capability=capability,
            artifacts={
                **(relay_result if isinstance(relay_result, dict) else {}),
                "path": approval_arguments(approval).get("path"),
            },
        )
