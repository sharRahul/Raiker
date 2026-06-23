from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from raiker.agents.orchestration import SubagentSpecError, parse_subagent_spec
from raiker.contracts.ids import new_id, utc_now
from raiker.runtime.executors.base import ExecutionResult
from raiker.runtime.executors.orchestration import SubagentExecutor
from raiker.storage.sqlite import SQLiteStore

if TYPE_CHECKING:
    from raiker.runtime.authority.models import Principal
    from raiker.runtime.authority.router import GovernedAction

# Local scheduled routines (Phase 4 slice 2), on-demand: a routine bundles a
# bounded read-only subagent spec with an interval. There is NO background
# daemon/thread/watcher — the owner (or an external trigger) calls `run_due`,
# which runs the routines whose next_run has passed. This keeps the runtime
# free of long-lived background execution while still being genuinely useful.

MAX_ROUTINES_PER_TICK = 50
MIN_INTERVAL_SECONDS = 60


def _plus_seconds(iso: str, seconds: int) -> str:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (dt + timedelta(seconds=seconds)).astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ScheduledRoutinesExecutor:
    """Real executor for ``scheduled_routines`` — local, on-demand routine runner."""

    capability = "scheduled_routines"

    def __init__(self, workspace_root: str | Path, store: SQLiteStore) -> None:
        self._ws = Path(workspace_root).resolve()
        self._store = store
        self._subagent = SubagentExecutor(self._ws, store)

    def execute(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        operation = str(action.arguments.get("operation", "run_due")).strip()
        if operation == "define":
            return self._define(action, principal)
        if operation == "run_due":
            return self._run_due(action, principal)
        if operation == "run":
            return self._run_one(action, principal)
        return ExecutionResult(
            ok=False, capability=self.capability, action_id=action.action_id,
            reason_code=f"unknown_operation:{operation}",
            summary="Scheduled-routine operation must be define|run_due|run.",
        )

    # ── define ──
    def _define(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        name = str(action.arguments.get("name", "routine")).strip() or "routine"
        try:
            interval = int(action.arguments.get("interval_seconds", 0))
        except (TypeError, ValueError):
            return self._fail(action, "invalid:interval_seconds")
        if interval < MIN_INTERVAL_SECONDS:
            return self._fail(action, f"interval_too_small:min_{MIN_INTERVAL_SECONDS}s")
        payload = action.arguments.get("payload")
        if not isinstance(payload, dict):
            return self._fail(action, "missing_argument:payload")
        routine_id = new_id("rtn_")
        # Validate the payload is a bounded read-only subagent spec (fail closed otherwise).
        try:
            parse_subagent_spec({"parent_task_id": routine_id, **payload})
        except SubagentSpecError as exc:
            return self._fail(action, f"invalid_payload:{exc}")
        now = utc_now()
        self._store.insert_scheduled_routine({
            "routine_id": routine_id,
            "name": name,
            "interval_seconds": interval,
            "payload_json": json.dumps(payload),
            "enabled": 1 if bool(action.arguments.get("enabled", False)) else 0,
            "next_run": now,
            "last_run": None,
            "created_by": principal.principal_id,
            "created_at": now,
            "status": "scheduled",
        })
        return ExecutionResult(
            ok=True, capability=self.capability, action_id=action.action_id,
            summary=f"Defined routine '{name}' (interval {interval}s).",
            artifacts={"routine_id": routine_id, "name": name, "interval_seconds": interval},
        )

    # ── run_due ──
    def _run_due(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        now = utc_now()
        due = self._store.list_scheduled_routines(enabled_only=True, due_before=now)[:MAX_ROUTINES_PER_TICK]
        results: list[dict[str, Any]] = []
        ok_all = True
        first_failure: str | None = None
        for routine in due:
            outcome = self._run_routine(routine, principal, action)
            results.append({"routine_id": routine["routine_id"], "ok": outcome[0], "reason_code": outcome[1]})
            if not outcome[0]:
                ok_all = False
                first_failure = first_failure or outcome[1]
        return ExecutionResult(
            ok=ok_all,
            capability=self.capability,
            action_id=action.action_id,
            reason_code=None if ok_all else (first_failure or "routine_run_failed"),
            summary=f"Ran {len(results)} due routine(s); all_ok={ok_all}.",
            artifacts={"ran": len(results), "results": results},
        )

    # ── run one ──
    def _run_one(self, action: GovernedAction, principal: Principal) -> ExecutionResult:
        routine_id = str(action.arguments.get("routine_id", "")).strip()
        if not routine_id:
            return self._fail(action, "missing_argument:routine_id")
        routine = self._store.get_scheduled_routine(routine_id)
        if routine is None:
            return self._fail(action, "unknown_routine")
        ok, reason = self._run_routine(routine, principal, action)
        return ExecutionResult(
            ok=ok, capability=self.capability, action_id=action.action_id,
            reason_code=reason,
            summary=f"Ran routine '{routine['name']}'.",
            artifacts={"routine_id": routine_id, "ok": ok},
        )

    def _run_routine(
        self, routine: dict[str, Any], principal: Principal, action: GovernedAction
    ) -> tuple[bool, str | None]:
        try:
            payload = json.loads(routine["payload_json"])
        except (json.JSONDecodeError, TypeError):
            return False, "invalid_payload_json"
        from dataclasses import replace
        # Reuse the governed subagent executor for the bounded read-only steps.
        sub_action = replace(
            action,
            arguments={"parent_task_id": routine["routine_id"], **payload},
        )
        result = self._subagent.execute(sub_action, principal)
        now = utc_now()
        self._store.update_scheduled_routine_run(
            routine["routine_id"],
            last_run=now,
            next_run=_plus_seconds(now, int(routine["interval_seconds"])),
        )
        return result.ok, result.reason_code

    def _fail(self, action: GovernedAction, reason: str) -> ExecutionResult:
        return ExecutionResult(
            ok=False, capability=self.capability, action_id=action.action_id,
            reason_code=reason, summary="Scheduled-routine request failed closed.",
        )
