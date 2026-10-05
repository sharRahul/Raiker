"""Will this routine be able to run? (DEC-12 step 8)

A routine fails at 03:00 for reasons that were already true at 17:00 — the host
was paused, nothing had chosen a model, the schedule had ended, the clock it
was written in was not the one it read. Each of those was only discovered by
the run that failed. The doctor asks the same questions before the run, from
records only: it reads the scheduler's own pass record, the stored model check,
the schedule's terms and the owner's delivery policy. It sends nothing to a
provider and starts nothing — a doctor that probed would be a second way to
run the routine.

Every check answers one of ``ok``, ``warn``, ``blocked`` or ``unknown``; an
answer that could not be read is ``unknown``, never ``ok``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from typing_extensions import TypedDict

from raiker.contracts.models import TaskRecord
from raiker.notify.delivery_policy import QuietHours
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.cost_limit import cost_limit
from raiker.tasks.run_limit import effective_minutes, tool_call_budget
from raiker.tasks.schedule import is_repeating, parse_instant, valid_zone

CheckState = Literal["ok", "warn", "blocked", "unknown"]


class DoctorCheck(TypedDict):
    key: str
    label: str
    state: CheckState
    detail: str
    #: Where the owner fixes it, when somewhere in Raiker does.
    href: str | None


class RoutineDoctor(TypedDict):
    task_id: str
    #: The worst state among the checks: one ``blocked`` makes the routine blocked.
    state: CheckState
    checked_at: str
    checks: list[DoctorCheck]


_RANK: dict[str, int] = {"blocked": 0, "unknown": 1, "warn": 2, "ok": 3}

#: The scheduler's own pass name (`raiker.api.instance_runtime`).
SCHEDULER_PASS = "scheduled_tasks"


def _check(key: str, label: str, state: CheckState, detail: str, href: str | None = None) -> DoctorCheck:
    return {"key": key, "label": label, "state": state, "detail": detail, "href": href}


def _scheduler(store: SQLiteStore, workspace_root: Path) -> DoctorCheck:
    from raiker.app.host import HostControl

    label = "The scheduler"
    try:
        if HostControl(workspace_root).is_paused():
            return _check(
                "scheduler", label, "blocked",
                "Raiker is paused, so no background work starts until you resume it.",
                "#/home",
            )
        rows = {row["pass_name"]: row for row in store.list_background_worker_health()}
    except Exception:  # noqa: BLE001 - unreadable is unknown, not fine
        return _check("scheduler", label, "unknown", "The scheduler's record could not be read.")
    row = rows.get(SCHEDULER_PASS)
    if row is None:
        return _check(
            "scheduler", label, "unknown",
            "The scheduler has not recorded a pass since this workspace started. It runs while Raiker is open.",
            "#/observe?tab=overview",
        )
    if row["state"] == "failing":
        return _check(
            "scheduler", label, "blocked",
            f"The scheduler's last {row['consecutive_failures']} passes failed ({row['last_error_class']}).",
            "#/observe?tab=overview",
        )
    if row["state"] == "stale":
        return _check(
            "scheduler", label, "warn",
            "The scheduler has not recorded a pass for over five minutes. It runs while Raiker is open.",
            "#/observe?tab=overview",
        )
    return _check("scheduler", label, "ok", "Running: it checks for due work every fifteen seconds.")


def _schedule(task: TaskRecord, zone: str, now: datetime) -> DoctorCheck:
    label = "Its schedule"
    if task.status == "cancelled":
        return _check("schedule", label, "blocked", "This routine was stopped, so it will not run again.")
    if task.status == "paused":
        return _check(
            "schedule", label, "blocked",
            "This routine is paused. Continue it in Tasks to run it again.",
            f"#/tasks?task={task.task_id}",
        )
    if task.schedule_timezone and not valid_zone(task.schedule_timezone):
        return _check(
            "schedule", label, "blocked",
            f"It was written for the time zone {task.schedule_timezone}, which this machine does not know.",
        )
    if task.schedule_until:
        try:
            if parse_instant(task.schedule_until) < now:
                return _check("schedule", label, "blocked", "Its schedule has ended; it will not run again.")
        except ValueError:
            return _check("schedule", label, "unknown", "Its end date could not be read.")
    if not task.scheduled_at:
        return _check(
            "schedule", label, "warn",
            "It has no next run. It runs when you start it.",
        )
    try:
        due = parse_instant(task.scheduled_at)
    except ValueError:
        return _check("schedule", label, "unknown", "Its next run time could not be read.")
    reading_zone = task.schedule_timezone or zone
    repeats = " and then repeats" if is_repeating(task.recurrence) else ""
    when = due.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
    if due < now and task.status == "queued":
        return _check(
            "schedule", label, "warn",
            f"It was due at {when} and has not started yet — it starts on the scheduler's next pass.",
        )
    return _check(
        "schedule", label, "ok",
        f"Next run {when}{repeats}, read on the {reading_zone} clock.",
    )


def _model(store: SQLiteStore, task: TaskRecord, owner: str) -> DoctorCheck:
    from raiker.models.readiness import ModelReadinessService, ProviderCatalogueProbe

    label = "Its model"
    try:
        service = ModelReadinessService(store, probe=ProviderCatalogueProbe(store))
        profile_id, model = service.resolve_request_target(owner, task.model_profile, task.model)
        readiness = service.current_selected(owner, profile_id, model)
    except Exception:  # noqa: BLE001 - unreadable is unknown, not fine
        return _check(
            "model", label, "blocked",
            "No model is chosen that this routine can run on.",
            "#/models",
        )
    if not model or model.startswith("<"):
        # The registry's placeholder: nothing — the routine nor the account —
        # names a model, so the run would start and stop at its readiness check.
        return _check(
            "model", label, "blocked",
            "No model is chosen, for this routine or as your default. Choose one in Models.",
            "#/models",
        )
    name = model
    if readiness.ready:
        return _check("model", label, "ok", f"{name} passed its last check.")
    if readiness.reason_code == "readiness_expired":
        return _check(
            "model", label, "ok",
            f"{name} passed a check that has since expired; it is checked again when the run starts.",
        )
    if readiness.reason_code == "model_not_checked":
        return _check(
            "model", label, "warn",
            f"{name} has not been checked yet. It is checked when the run starts, and the run waits if it fails.",
            "#/models",
        )
    return _check("model", label, "blocked", f"{readiness.summary} {readiness.remediation}".strip(), "#/models")


def _delivery(store: SQLiteStore, task: TaskRecord, owner: str) -> DoctorCheck:
    label = "Telling you"
    try:
        settings, zone = store.notification_settings(owner)
    except Exception:  # noqa: BLE001
        return _check("delivery", label, "unknown", "Your notification settings could not be read.")
    quiet = QuietHours.from_settings(settings, zone)
    detail = "When it ends, a notice is recorded in Raiker and counted by the bell."
    if task.scheduled_at and quiet.enabled:
        try:
            due = parse_instant(task.scheduled_at)
        except ValueError:
            due = None
        if due is not None and quiet.active(due):
            return _check(
                "delivery", label, "ok",
                detail + f" Its next run falls in your quiet hours ({quiet.start:%H:%M}–{quiet.end:%H:%M}),"
                " so the notice will wait for the summary when they end.",
                "#/settings?tab=notification",
            )
    if task.delivery_state == "failed":
        return _check(
            "delivery", label, "warn",
            f"The last notice failed: {task.delivery_detail or 'no reason was recorded'}.",
        )
    return _check("delivery", label, "ok", detail)


def _clock(store: SQLiteStore, owner: str) -> tuple[DoctorCheck, str]:
    from raiker.runtime.environment import resolve_timezone

    label = "The clock it reads"
    zone, source = resolve_timezone(store, owner)
    if source == "fallback":
        return (
            _check(
                "clock", label, "warn",
                "No time zone is set, so times are read in UTC. Set yours in General.",
                "#/settings?tab=general",
            ),
            zone,
        )
    return _check("clock", label, "ok", f"{zone}."), zone


def _cost_price_known(store: SQLiteStore, task: TaskRecord, owner: str) -> bool | None:
    """Whether the routine's model has a price a cost limit can be measured in.

    ``None`` when the model cannot be resolved at all — the model check says why.
    """
    from raiker.models.readiness import ModelReadinessService, ProviderCatalogueProbe
    from raiker.tasks.cost_limit import resolve_price

    try:
        service = ModelReadinessService(store, probe=ProviderCatalogueProbe(store))
        profile_id, model = service.resolve_request_target(owner, task.model_profile, task.model)
        if not model or model.startswith("<"):
            return None
        from raiker.models.registry import ModelProfileRegistry

        profile = ModelProfileRegistry.load().resolve_profile_id(profile_id)
        provider = str(getattr(profile, "provider", "") or profile_id)
        raw = (getattr(profile, "raw", {}) or {}).get("pricing")
        return resolve_price(store, owner, provider, model, raw) is not None
    except Exception:  # noqa: BLE001 - unreadable is unknown, not fine
        return None


def _limits(task: TaskRecord, store: SQLiteStore | None = None, owner: str = "") -> DoctorCheck:
    minutes = effective_minutes(task.max_run_minutes)
    failed = task.failed_cycles
    calls = tool_call_budget(task.max_tool_calls)
    usd = cost_limit(task.max_run_cost_usd)
    bounds = [f"{minutes} minutes"]
    if calls is not None:
        bounds.append(f"{calls} tool calls")
    if usd is not None:
        bounds.append(f"${usd:.2f}")
    detail = "Each run is stopped after " + (
        bounds[0] if len(bounds) == 1 else ", ".join(bounds[:-1]) + " or " + bounds[-1]
    ) + "."
    # DEC-12 step 6 — a dollar limit on a model with no known price measures
    # nothing. Said, so the owner does not believe it is protecting them.
    if usd is not None and store is not None and _cost_price_known(store, task, owner) is False:
        return _check(
            "limits", "Its limits", "warn",
            detail + " Its model has no known price, so the cost limit cannot be measured. Set one in Models → Pricing.",
            "#/models?tab=pricing",
        )
    if failed:
        return _check(
            "limits", "Its limits", "warn",
            detail + f" The last {failed} run{'s' if failed != 1 else ''} did not complete; at 3 in a row it is paused.",
            f"#/tasks?task={task.task_id}",
        )
    return _check("limits", "Its limits", "ok", detail + " Three failed runs in a row pause it.")


def routine_doctor(
    store: SQLiteStore,
    task: TaskRecord,
    *,
    owner_principal_id: str,
    workspace_root: Path,
    now: datetime | None = None,
) -> RoutineDoctor:
    moment = now or datetime.now(UTC)
    clock, zone = _clock(store, owner_principal_id)
    checks = [
        _scheduler(store, workspace_root),
        _schedule(task, zone, moment),
        clock,
        _model(store, task, owner_principal_id),
        _delivery(store, task, owner_principal_id),
        _limits(task, store, owner_principal_id),
    ]
    worst = min(checks, key=lambda check: _RANK[check["state"]])["state"]
    return {
        "task_id": task.task_id,
        "state": worst,
        "checked_at": moment.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "checks": checks,
    }
