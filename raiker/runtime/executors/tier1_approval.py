from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from raiker.contracts.ids import new_id, utc_now
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority.models import Principal
from raiker.runtime.authority.posture import capture_posture, posture_degraded_reason
from raiker.runtime.executors.base import ExecutionResult
from raiker.storage.sqlite import SQLiteStore

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction, RuntimeAuthority


class ApprovalExecutionRelay:
    """Execute a previously human-approved action under fresh, full governance.

    The relay is a governed executor itself (``approval_execution_relay``). Given
    an ``approval_id`` it does *not* trust anything captured at approval time
    except the immutable intent snapshot (A1):

    * TTL — a past-``expires_at`` approval resolves ``expired`` and never runs;
    * arguments hash — a payload that drifted since approval is refused (TOCTOU);
    * posture (A4) — a revoked approving session denies with ``posture_degraded``.

    It then dispatches the approved action's ``action_type`` to its *own*
    capability's executor by **re-routing through ``RuntimeAuthority``** (A2/A3):
    the target runs under its capability gate state, decision mode, and
    PolicyEngine review *at execution time*, not as trusted from approval time.
    Single-execution is enforced by an atomic ``pending → executing → executed``
    transition in SQLite.
    """

    capability = "approval_execution_relay"

    def __init__(
        self,
        workspace_root: str | Path,
        store: SQLiteStore,
        *,
        authority_factory: Callable[[], RuntimeAuthority] | None = None,
    ) -> None:
        self._workspace_root = Path(workspace_root).resolve()
        self._store = store
        self._authority_factory = authority_factory
        self._authority: RuntimeAuthority | None = None
        self._writer: EventLogWriter | None = None

    # ── wiring ────────────────────────────────────────────────────────────────

    def _get_authority(self) -> RuntimeAuthority:
        """Lazily build the authority used to re-govern the target action.

        Lazy + local imports break the construction cycle (the default executor
        registry contains *this* relay). The built registry also holds a relay
        instance, but the target is never ``approval_execution_relay`` (guarded
        below), so it is never invoked and cannot recurse.
        """
        if self._authority is None:
            if self._authority_factory is not None:
                self._authority = self._authority_factory()
            else:
                from raiker.runtime.authority.router import RuntimeAuthority
                from raiker.runtime.executors import build_default_executor_registry

                registry = build_default_executor_registry(self._workspace_root, self._store)
                self._authority = RuntimeAuthority(
                    self._store, self._events(), executor_registry=registry
                )
        return self._authority

    def _events(self) -> EventLogWriter:
        if self._writer is None:
            self._writer = EventLogWriter(self._store)
        return self._writer

    def _emit(
        self, action: GovernedAction, event_type: str, payload: dict[str, object]
    ) -> None:
        self._events().append(
            make_event(
                session_id=action.session_id or "approval_relay",
                turn_id=action.turn_id,
                event_type=event_type,
                actor="approval_execution_relay",
                payload=payload,
            )
        )

    # ── execution ─────────────────────────────────────────────────────────────

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        approval_id = str(action.arguments.get("approval_id", ""))
        if not approval_id:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="missing_argument:approval_id",
                summary="Approval relay denied: no approval_id provided.",
            )

        approval = self._store.load_approval(approval_id)
        if approval is None:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="approval_not_found",
                summary=f"Approval {approval_id} not found.",
            )
        if approval.get("status") != "pending":
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="approval_already_resolved",
                summary=f"Approval {approval_id} already resolved.",
            )

        # F7 — a critical approval executes only through the critical lifecycle
        # (`RuntimeAuthority.resolve_critical_approval`), which drives this relay
        # with a one-shot `CriticalConfirmation`. Without that confirmation the
        # relay refuses to touch it, so an AI (or a stray direct relay call) can
        # neither claim nor re-park a critical approval.
        if approval.get("critical") and action.critical_confirmation is None:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="critical_approval_requires_lifecycle",
                summary=f"Approval {approval_id} is critical; resolve it via the critical lifecycle.",
            )

        # A1 — TTL check first: an expired approval resolves to `expired` and
        # never executes. `expires_at` is stored in the same canonical UTC
        # ISO-8601 format as `utc_now()`, so a lexicographic compare is
        # chronological.
        now = utc_now()
        expires_at = approval.get("expires_at")
        if expires_at is not None and str(expires_at) and now > str(expires_at):
            self._store.expire_approval(approval_id)
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="approval_expired",
                summary=f"Approval {approval_id} expired at {expires_at}; not executed.",
            )

        # A1 — TOCTOU defense: the immutable intent hash was captured at approval
        # creation. Recompute it from the tool action as it stands now; if the
        # arguments (or tool/risk) drifted since approval, refuse — the human
        # approved a different action than the one about to run.
        stored_hash = approval.get("action_payload_sha256")
        if stored_hash is not None:
            current_hash = self._store.tool_action_payload_sha256(
                str(approval.get("tool_name", "")),
                str(approval.get("arguments_json", "{}")),
                str(approval.get("risk_level", "")),
            )
            if str(stored_hash) != current_hash:
                return ExecutionResult(
                    ok=False, capability=self.capability, action_id=action.action_id,
                    reason_code="approval_payload_tampered",
                    summary=(
                        f"Approval {approval_id} arguments changed since approval; refused."
                    ),
                )

        arguments_json = str(approval.get("arguments_json", "{}"))
        try:
            tool_args: dict[str, Any] = json.loads(arguments_json)
        except json.JSONDecodeError:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="invalid_arguments_json",
                summary="Approval relay denied: invalid arguments JSON.",
            )

        # A4 — posture snapshot + revoked-session denial. Captured before any
        # state change so a degraded posture never claims or runs the action.
        posture = capture_posture(self._store, principal, action.session_id)
        degraded = posture_degraded_reason(posture)
        if degraded is not None:
            self._emit(action, "approval_execution_denied", {
                "approval_id": approval_id, "reason_code": degraded, "posture": posture,
            })
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code=degraded,
                summary=f"Approval {approval_id} denied: {degraded}.",
                artifacts={"approval_id": approval_id, "posture": posture},
            )

        # A2 — resolve the approved action's target capability. A relay may never
        # execute another relay (no recursion, no relay-approves-relay).
        from raiker.runtime.authority.router import CAPABILITY_GATE_MAP, NON_ALLOW_DECISIONS

        tool_name = str(approval.get("tool_name", ""))
        risk_level = str(approval.get("risk_level", "low"))
        target_cap = CAPABILITY_GATE_MAP.get(tool_name, tool_name)
        if tool_name == self.capability or target_cap == self.capability:
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="relay_target_not_permitted",
                summary="Approval relay cannot execute another approval relay.",
            )

        # A2 — single-execution: atomically claim pending → executing. The loser
        # of a race (or a re-entrant call) sees a non-pending row and stops.
        if not self._store.claim_approval_for_execution(approval_id):
            return ExecutionResult(
                ok=False, capability=self.capability, action_id=action.action_id,
                reason_code="approval_already_resolved",
                summary=f"Approval {approval_id} already claimed for execution.",
            )

        # A2/A3 — dispatch by re-routing the target through full governance. The
        # executing human is the approver; the target runs under its own gate,
        # decision mode, and policy review at execution time.
        from raiker.runtime.authority.router import GovernedAction as _GovernedAction

        target_action = _GovernedAction(
            action_id=new_id("act_"),
            principal_id=principal.principal_id,
            action_type=tool_name,
            tool_or_service_name=tool_name,
            arguments=tool_args,
            risk_level=risk_level,
            requires_approval=False,
            session_id=action.session_id,
            turn_id=action.turn_id,
            # BUG-62 — the conversation that proposed the action, carried across
            # from the approval row. The executing session is the inbox's, so a
            # capability whose subject is the proposing chat has to be told which
            # one it was; it is read from the approval rather than from the model.
            origin_session_id=str(approval.get("session_id") or ""),
            # F7 — carry a live human's critical confirmation (issued only by
            # `resolve_critical_approval`) onto the re-governed target, so a
            # human-approved critical action clears the deny floor while still
            # running under its own gate, policy review, and posture check.
            critical_confirmation=action.critical_confirmation,
        )
        result = self._get_authority().route_action(target_action, principal)
        executed = result.decision == "allow" and result.error is None

        if executed:
            self._store.finalize_approval_execution(
                approval_id, status="executed", resolved_by=principal.principal_id
            )
            self._emit(action, "approval_executed", {
                "approval_id": approval_id,
                "target_action_id": target_action.action_id,
                "capability": target_cap,
                "tool_name": tool_name,
                "decision": result.decision,
                "principal_id": principal.principal_id,
                "result": result.artifacts,
                "posture": posture,
            })
            return ExecutionResult(
                ok=True, capability=self.capability, action_id=action.action_id,
                summary=f"Approval executed: {tool_name} via {target_cap}.",
                artifacts={
                    "approval_id": approval_id,
                    "target_action_id": target_action.action_id,
                    "capability": target_cap,
                    "decision": result.decision,
                    "result": result.artifacts,
                },
            )

        # Not executed. If governance blocked the action *before* any executor
        # ran (gate disabled, policy deny, no registered executor), nothing was
        # committed, so release the claim back to pending — a retry after the
        # owner fixes the gate is safe. If the executor ran and failed, keep the
        # approval terminal (execution_failed) so it can never be double-run.
        nothing_ran = (
            result.decision in NON_ALLOW_DECISIONS
            or result.error == "execution_unavailable:no_executor"
        )
        if nothing_ran:
            self._store.release_approval_claim(approval_id)
        else:
            self._store.finalize_approval_execution(
                approval_id, status="execution_failed", resolved_by=principal.principal_id
            )
        reason = result.error or result.message or result.decision
        self._emit(action, "approval_execution_denied", {
            "approval_id": approval_id,
            "target_action_id": target_action.action_id,
            "capability": target_cap,
            "decision": result.decision,
            "reason_code": reason,
            "released_to_pending": nothing_ran,
            "posture": posture,
        })
        return ExecutionResult(
            ok=False, capability=self.capability, action_id=action.action_id,
            reason_code=f"target_not_executed:{reason}",
            summary=f"Approval {approval_id} not executed: {result.decision} ({reason}).",
            artifacts={
                "approval_id": approval_id,
                "target_decision": result.decision,
                "capability": target_cap,
                "released_to_pending": nothing_ran,
                "result": result.artifacts,
            },
        )
