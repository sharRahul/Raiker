# mypy: disable-error-code="misc"
"""Execution environments, remote execution profiles, budgets and cloud cost
(GCR-11).

One part of :class:`raiker.storage.sqlite.SQLiteStore`, which inherits it. Every method
is typed against the whole store (``self: SQLiteStore``), so a call into another
part is checked exactly as it was when every method lived in one class. mypy
reports that self-type as ``misc`` on a mixin, which is the one code this file
turns off.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import BudgetRecord, ExecutionBudget, RemoteExecutionProfile

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore


class ExecutionStore:

    def insert_budget_record(self: SQLiteStore, budget: BudgetRecord) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO budget_records
            (budget_id, name, max_cost, current_cost, currency, scope, enabled, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                budget.budget_id,
                budget.name,
                budget.max_cost,
                budget.current_cost,
                budget.currency,
                budget.scope,
                int(budget.enabled),
                budget.created_by,
                budget.created_at,
                budget.updated_at,
            ),
        )

    def list_budget_records(self: SQLiteStore, enabled_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM budget_records"
        params: list[Any] = []
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY created_at DESC"
        rows = self._rows(query, params)
        return [dict(row) for row in rows]

    def load_budget_record(self: SQLiteStore, budget_id: str) -> dict[str, Any] | None:
        row = self._row("SELECT * FROM budget_records WHERE budget_id = ?", (budget_id,))
        return dict(row) if row else None

    def update_budget_cost(self: SQLiteStore, budget_id: str, additional_cost: float) -> bool:
        changed = self._execute(
            "UPDATE budget_records SET current_cost = current_cost + ?, updated_at = ? WHERE budget_id = ?",
            (additional_cost, utc_now(), budget_id),
        )
        return changed > 0


    def insert_remote_execution_profile(self: SQLiteStore, profile: RemoteExecutionProfile) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO remote_execution_profiles
            (profile_id, profile_type, name, config_json, enabled, created_by, created_at, updated_at, owner_principal_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile.profile_id,
                profile.profile_type,
                profile.name,
                profile.config_json,
                int(profile.enabled),
                profile.created_by,
                profile.created_at,
                profile.updated_at,
                profile.created_by,
            ),
        )

    def list_remote_execution_profiles(
        self: SQLiteStore, enabled_only: bool = False, *, owner_principal_id: str | None = None
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM remote_execution_profiles"
        params: list[Any] = []
        conditions: list[str] = []
        if enabled_only:
            conditions.append("enabled = 1")
        if owner_principal_id is not None:
            conditions.append("owner_principal_id = ?")
            params.append(owner_principal_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC"
        rows = self._rows(query, params)
        return [dict(row) for row in rows]

    def load_remote_execution_profile(
        self: SQLiteStore, profile_id: str, *, owner_principal_id: str
    ) -> dict[str, Any] | None:
        row = self._row(
            "SELECT * FROM remote_execution_profiles WHERE profile_id = ? AND owner_principal_id = ?",
            (profile_id, owner_principal_id),
        )
        return dict(row) if row else None

    def select_execution_environment(self: SQLiteStore, owner_principal_id: str, profile_id: str) -> None:
        self._execute(
            """INSERT INTO execution_environment_selection VALUES (?, ?, ?)
            ON CONFLICT(owner_principal_id) DO UPDATE SET profile_id = excluded.profile_id,
            selected_at = excluded.selected_at""",
            (owner_principal_id, profile_id, utc_now()),
        )

    def selected_execution_environment(self: SQLiteStore, owner_principal_id: str) -> str:
        row = self._row(
            "SELECT profile_id FROM execution_environment_selection WHERE owner_principal_id = ?",
            (owner_principal_id,),
        )
        return str(row["profile_id"]) if row else "local_native"

    def execution_environment_was_chosen(self: SQLiteStore, owner_principal_id: str) -> bool:
        """Whether the owner picked an environment, rather than getting the default.

        BUG-308 — the two read the same on :meth:`selected_execution_environment`,
        and they mean different things to a command that runs code: an owner who
        chose the host has chosen its network, and one who never chose anything
        gets the network-isolated sandbox wherever this machine has one.
        """
        row = self._row(
            "SELECT 1 FROM execution_environment_selection WHERE owner_principal_id = ?",
            (owner_principal_id,),
        )
        return row is not None

    @staticmethod
    def _cloud_cost_totals(
        rows: list[Any],
    ) -> tuple[Decimal, Decimal, Decimal, list[dict[str, Any]]]:
        actions: dict[str, dict[str, Any]] = {}
        provider_snapshots: list[Decimal] = []
        history: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                amount = Decimal(str(item["amount"]))
            except (InvalidOperation, ValueError):
                amount = Decimal("0")
            event_type = str(item["event_type"])
            if event_type == "provider_snapshot":
                provider_snapshots.append(amount)
                action = None
            else:
                action = actions.setdefault(
                    str(item["action_id"]),
                    {
                        "estimated": Decimal("0"),
                        "actual": None,
                        "released": False,
                        "status": "pending",
                    },
                )
            if event_type == "reserved":
                assert action is not None
                action.update(estimated=amount, status="reserved")
            elif event_type == "reconciled":
                assert action is not None
                action.update(actual=amount, status="reconciled")
            elif event_type == "released":
                assert action is not None
                action.update(released=True, status="released")
            elif (
                event_type == "provider_unavailable"
                and action is not None
                and action["status"] == "reserved"
            ):
                action["status"] = "provider_unavailable"
            history.append(
                {
                    "event_id": str(item["event_id"]),
                    "action_id": str(item["action_id"]),
                    "event_type": event_type,
                    "amount": float(amount),
                    "provider_reference": item.get("provider_reference"),
                    "reason": item.get("reason"),
                    "recorded_at": str(item["recorded_at"]),
                }
            )
        actual = sum(
            (entry["actual"] for entry in actions.values() if entry["actual"] is not None),
            Decimal("0"),
        )
        reserved = sum(
            (
                entry["estimated"]
                for entry in actions.values()
                if entry["actual"] is None and not entry["released"]
            ),
            Decimal("0"),
        )
        provider_spend = (
            max(provider_snapshots[-1] - provider_snapshots[0], Decimal("0"))
            if len(provider_snapshots) >= 2
            else Decimal("0")
        )
        return actual, reserved, provider_spend, history

    def reserve_cloud_execution_cost(
        self: SQLiteStore,
        *,
        owner_principal_id: str,
        profile_id: str,
        action_id: str,
        estimated_cost: float,
        max_cost: float,
    ) -> bool:
        """Atomically reserve cumulative budget before Daytona execution."""
        estimate = Decimal(str(max(estimated_cost, 0)))
        limit = Decimal(str(max(max_cost, 0)))
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """SELECT * FROM cloud_execution_cost_ledger
                WHERE owner_principal_id = ? AND profile_id = ?
                ORDER BY rowid""",
                (owner_principal_id, profile_id),
            ).fetchall()
            if any(
                str(row["action_id"]) == action_id and row["event_type"] == "reserved"
                for row in rows
            ):
                return False
            actual, reserved, provider_spend, _history = self._cloud_cost_totals(list(rows))
            if limit <= 0 or max(actual, provider_spend) + reserved + estimate > limit:
                return False
            connection.execute(
                """INSERT INTO cloud_execution_cost_ledger
                (event_id, owner_principal_id, profile_id, action_id, event_type, amount,
                 provider_reference, reason, recorded_at)
                VALUES (?, ?, ?, ?, 'reserved', ?, NULL, NULL, ?)""",
                (
                    new_id("cost_"),
                    owner_principal_id,
                    profile_id,
                    action_id,
                    str(estimate),
                    utc_now(),
                ),
            )
        return True

    def record_cloud_execution_cost(
        self: SQLiteStore,
        *,
        owner_principal_id: str,
        profile_id: str,
        action_id: str,
        event_type: str,
        amount: float,
        provider_reference: str | None = None,
        reason: str | None = None,
    ) -> None:
        if event_type not in {
            "reconciled",
            "released",
            "provider_snapshot",
            "provider_unavailable",
        }:
            raise ValueError("invalid_cloud_cost_event")
        self._execute(
            """INSERT INTO cloud_execution_cost_ledger
            (event_id, owner_principal_id, profile_id, action_id, event_type, amount,
             provider_reference, reason, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                new_id("cost_"),
                owner_principal_id,
                profile_id,
                action_id,
                event_type,
                str(Decimal(str(max(amount, 0)))),
                provider_reference,
                reason,
                utc_now(),
            ),
        )

    def cloud_execution_cost_summary(
        self: SQLiteStore, owner_principal_id: str, profile_id: str, *, max_cost: float | None = None
    ) -> dict[str, Any]:
        rows = self._rows(
            """SELECT * FROM cloud_execution_cost_ledger
            WHERE owner_principal_id = ? AND profile_id = ?
            ORDER BY rowid""",
            (owner_principal_id, profile_id),
        )
        actual, reserved, provider_spend, history = self._cloud_cost_totals(list(rows))
        limit = Decimal(str(max_cost)) if max_cost is not None else None
        committed = max(actual, provider_spend) + reserved
        return {
            "actual_cost": float(actual),
            "provider_cost": float(provider_spend),
            "reserved_cost": float(reserved),
            "committed_cost": float(committed),
            "remaining_cost": float(max(limit - committed, Decimal("0")))
            if limit is not None
            else None,
            "reconciliation_status": (
                "provider_unavailable"
                if any(item["event_type"] == "provider_unavailable" for item in history)
                and reserved > 0
                else "reconciled"
                if history and reserved == 0
                else "reserved"
                if reserved > 0
                else "not_started"
            ),
            "history": history,
        }

    def insert_execution_budget(self: SQLiteStore, budget: ExecutionBudget) -> None:
        self._execute(
            """
            INSERT OR REPLACE INTO execution_budgets
            (budget_id, name, max_cost, current_cost, currency, profile_id, enabled, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                budget.budget_id,
                budget.name,
                budget.max_cost,
                budget.current_cost,
                budget.currency,
                budget.profile_id,
                int(budget.enabled),
                budget.created_by,
                budget.created_at,
                budget.updated_at,
            ),
        )

    def list_execution_budgets(self: SQLiteStore, enabled_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM execution_budgets"
        params: list[Any] = []
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY created_at DESC"
        rows = self._rows(query, params)
        return [dict(row) for row in rows]
