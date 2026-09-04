"""The scheduler: it starts due work, and it finishes work you approved.

Both halves matter, and only the first one used to exist. A scheduled run that
reached an approval boundary parked correctly — the turn suspended, the approval
appeared in the inbox, the task card said *waiting for approval* — and then, when
the owner granted it, nothing continued it. Chat can resume a parked turn because
a Chat tab is watching; a scheduler-launched turn has no client at all, so its
continuation had no owner and the task sat in ``waiting_for_approval`` forever
(BUG-25). ``resume_approved`` is that owner.

It is deliberately the same machinery a Chat tab uses rather than a second one:
``list_resumable_suspended_turns`` names what is resolved-but-unclaimed, and
``AgentGateway.aresume_after_approval`` claims it through the atomic
``suspended → resuming`` transition. Exactly-once is that claim, so a scheduler
tick and a browser tab racing on the same approval cannot both replay the turn —
one wins and the other is told it was already continued, which is the truth.

Every continuation re-checks the world before it runs: the task still exists, has
not been cancelled or stopped at a safe boundary, and still belongs to a real
owner. Nothing is resumed on the strength of what was true when it parked.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

from raiker.app.host import HostControl
from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import (
    ClientMetadata,
    PromptEnvelope,
    PromptOptions,
    PromptPayload,
    TaskRecord,
    UserMetadata,
)
from raiker.events.writer import EventLogWriter
from raiker.gateway.agent_gateway import AgentGateway
from raiker.notify.approval_notifier import (
    dispatch_notification_hook,
    fire_os_notification,
)
from raiker.runtime.turn_suspension import TurnSuspensionError
from raiker.storage.sqlite import SQLiteStore
from raiker.tasks.manager import TaskManager

# A task in one of these states must never be continued: the owner has stopped
# it, or it has already reached a terminal state through some other path.
NON_RESUMABLE_TASK_STATES = frozenset({"cancelled", "cancelling", "completed", "failed"})

#: BUG-276 — a scheduled telemetry delivery changed its mind about working. Its
#: own kind so the notification centre can group it and an owner can tell it from
#: a task that finished or an approval that needs a decision.
TELEMETRY_DELIVERY_KIND = "telemetry_delivery"


class TaskScheduler:
    """Runs due dashboard tasks inside the same always-on Raiker host."""

    def __init__(self, workspace_root: str | Path) -> None:
        self.workspace_root = Path(workspace_root)
        self.store = SQLiteStore(self.workspace_root)

    async def refresh_model_capacities(self) -> int:
        """Refresh due local-model facts on the resident host's 24-hour cadence."""
        # Paused means no background work of any kind starts, and a capacity
        # probe is background work that talks to a local runtime (BUG-40).
        if HostControl(self.workspace_root).is_paused():
            return 0
        owner = self.store.original_account_principal_id()
        if owner is None:
            return 0
        # Local import avoids a module cycle: DashboardService also uses this
        # scheduler for task controls.
        from raiker.control.dashboard import DashboardService

        result = await DashboardService(self.workspace_root).refresh_local_model_capacities(owner)
        if not result.ok or not isinstance(result.data, dict):
            return 0
        profiles = result.data.get("profiles", [])
        return len(profiles) if isinstance(profiles, list) else 0

    # ── delivering the record on a cadence (BUG-276) ─────────────────────

    async def deliver_due_telemetry(self) -> int:
        """Deliver to every telemetry destination whose next run has come.

        BUG-276. The wire backlog #18 built delivered only when the owner
        pressed **Deliver now**, and a collector that receives while its
        operator is watching is not something a dashboard can be built on.

        **This is not a second scheduler, and it is deliberately not a routine
        that prompts a model.** The entry proposed an owner-created task on the
        Tasks board, and half of that was right: the cadence, the pause switch
        and the audit trail should be the ones that already exist, which is why
        this pass runs on the host tick beside :meth:`run_due` and answers to
        the same ``is_paused``. The other half was not. A task cycle is a
        governed *turn* — a model reads a prompt and decides what to call — and
        putting a model in the path of "did the record leave the machine" makes
        delivery a judgement where it is currently an arithmetic fact about a
        cursor. Every other authority path in this product keeps the model out;
        the observability wire is the last place to make an exception.

        What the owner gets instead is the same thing by the same means: a
        cadence chosen from the scheduler's own interval table, a claim the host
        advances exactly once, delivery through ``route_action`` so the export
        is an event in the log it exported, and a card that states the cadence
        and the next run rather than implying a feed.

        Returns how many deliveries this pass ran.
        """
        # Pause means "start no new background work", and a delivery reaches the
        # network. A paused host leaves the claim where it is; the destination
        # becomes due again the moment the owner resumes.
        if HostControl(self.workspace_root).is_paused():
            return 0
        claimed = self.store.claim_due_telemetry_destinations(utc_now(), _next_delivery)
        if not claimed:
            return 0
        # Local import: the control service builds an executor registry, and
        # importing it at module scope would make every scheduler import pay for
        # one. It is the same facade the Deliver-now route uses, so a scheduled
        # delivery cannot take a shorter path through governance than a pressed
        # one — the gate, the policy review, the approval and the audit event
        # are all the same code.
        from raiker.control.service import RuntimeControlService

        service = RuntimeControlService(self.workspace_root)
        delivered = 0
        for destination in claimed:
            destination_id = str(destination.get("destination_id", ""))
            owner = str(destination.get("principal_id", ""))
            previous = str(destination.get("last_status") or "")
            try:
                result = service.run_telemetry_export(owner, destination_id)
            except Exception as error:  # noqa: BLE001 — one collector must not stop the rest
                self._report_delivery(
                    destination, previous, f"telemetry_delivery_failed:{type(error).__name__}"
                )
                continue
            if result.ok:
                delivered += 1
            self._report_delivery(
                destination, previous, "ok" if result.ok else (result.reason_code or "failed")
            )
        return delivered

    def _report_delivery(
        self, destination: Mapping[str, object], previous: str, status: str
    ) -> None:
        """Tell the owner when a scheduled wire starts failing, and when it recovers.

        Only on the *transition*. A collector that has been unreachable for a
        day should not produce seventy-two identical notices, and one that has
        been fine for a week should not produce any: what an owner needs to know
        is that the answer changed. The card carries the standing state either
        way, so nothing is only in a notice.
        """
        if status == previous or (status != "ok" and previous not in ("", "ok")):
            return
        name = str(destination.get("name", "")) or "a collector"
        owner = str(destination.get("principal_id", ""))
        subject = str(destination.get("destination_id", ""))
        if not owner:
            return
        recovered = status == "ok"
        title = (
            "Telemetry delivery recovered" if recovered else "Telemetry delivery is failing"
        )
        body = (
            f"“{name}” delivered again."
            if recovered
            # The reason code, never the collector's answer body: a rejection
            # from an outside service is text this product did not write.
            else f"“{name}” could not be delivered to ({status}). Events are still queued."
        )
        try:
            notification_id = self.store.insert_notification(
                principal_id=owner,
                kind=TELEMETRY_DELIVERY_KIND,
                title=title,
                body=body,
                subject_id=subject or None,
            )
        except Exception:  # noqa: BLE001 — a notice must not fail the delivery pass
            return
        fire_os_notification(title, body)
        dispatch_notification_hook(
            self.store,
            owner_principal_id=owner,
            kind=TELEMETRY_DELIVERY_KIND,
            notification_id=notification_id,
            subject_id=subject,
        )

    # ── continuing approved work (BUG-25) ────────────────────────────────

    async def resume_approved(self) -> int:
        """Continue every parked scheduled run whose approval has been decided.

        Returns how many continuations this pass actually ran. A task whose
        approval is still pending is not touched; a task that cannot be
        continued keeps its ``waiting_for_approval`` card and is told why, so
        the owner sees a stated reason and a retry rather than silence.
        """
        resumed = 0
        for task in self.store.list_tasks(status="waiting_for_approval"):
            resumed += await self._resume_task(task)
        return resumed

    async def resume_task(self, task_id: str, owner_principal_id: str) -> dict[str, object]:
        """Continue one parked task on the owner's explicit request (the retry).

        Automatic continuation is best-effort by nature: a browser tab may have
        won the claim, the parked state may be unreadable, the host may have
        been down when the decision landed. The owner needs a way to say "try
        that again" that is not "re-prompt and pay for the whole context", and
        this is it. It is the same code path as the scheduler pass, so it can
        never continue something the automatic pass would have refused.
        """
        task = self.store.load_task(task_id)
        if task is None:
            return {"ok": False, "reason_code": "task_not_found"}
        if task.session_id.removeprefix("sess_inbox_") != owner_principal_id:
            # Not this owner's task. Same answer as a missing one: a 404 that
            # confirms the id exists is still a disclosure.
            return {"ok": False, "reason_code": "task_not_found"}
        if task.status not in ("waiting_for_approval", "paused"):
            return {"ok": False, "reason_code": f"task_not_resumable:{task.status}"}
        ran = await self._resume_task(task)
        current = self.store.load_task(task_id)
        return {
            "ok": ran > 0,
            "reason_code": None if ran > 0 else "no_resolved_approval",
            "task_status": current.status if current is not None else "",
            "summary": (current.summary if current is not None else "") or "",
        }

    async def _resume_task(self, task: TaskRecord) -> int:
        """Continue every resolved-but-unclaimed turn parked under one task.

        C11 — the owner principal comes from the task's ``session_id`` (the
        Inbox, which is where it has always been carried) and the parked turn is
        looked for in ``run_session_id`` (the task's own thread, when it has
        one). Reading the two from separate fields is what lets a routine own a
        conversation without the resume path losing track of whose it is.
        """
        task_id = task.task_id
        session_id = task.session_id
        principal_id = session_id.removeprefix("sess_inbox_")
        manager = TaskManager(self.store, EventLogWriter(self.store))
        if principal_id == session_id or self.store.get_principal(principal_id) is None:
            manager.report_resume_blocked(
                task_id, "This scheduled run has no valid owner, so it cannot continue."
            )
            return 0
        turns = self.store.list_resumable_suspended_turns(
            principal_id, session_id=task.run_session_id
        )
        if not turns:
            # Still waiting on the decision. Not an error, and not a state
            # change: the card already says exactly this.
            return 0
        resumed = 0
        for turn in turns:
            # Re-read immediately before each continuation. A decision made
            # minutes ago says nothing about whether the owner has since
            # stopped this task.
            current = self.store.load_task(task_id)
            if current is None or current.status in NON_RESUMABLE_TASK_STATES:
                break
            approval_id = str(turn["approval_id"])
            manager.mark_task_continuing(task_id, str(turn.get("tool_name") or ""))
            try:
                response = await AgentGateway(
                    self.workspace_root, principal_id=principal_id
                ).aresume_after_approval(approval_id)
            except TurnSuspensionError as error:
                # `suspended_turn_already_resumed` means a browser tab won the
                # race — the turn continued, just not here, so the task goes
                # back to waiting for whatever comes next rather than being
                # failed for someone else's success.
                manager.report_resume_blocked(task_id, _resume_block_reason(str(error)))
                continue
            except Exception as error:  # noqa: BLE001
                # A continuation that throws must not take the scheduler loop
                # down with it, and must not silently drop the task.
                manager.report_resume_blocked(
                    task_id,
                    f"Continuing this run failed: {type(error).__name__}. You can run it again.",
                )
                continue
            resumed += 1
            self._land_outcome(manager, task_id, response.status, response.message)
        return resumed

    def _land_outcome(
        self, manager: TaskManager, task_id: str, status: str, message: str
    ) -> None:
        """Record one governed turn's result on the task it belongs to."""
        task = self.store.load_task(task_id)
        if task is None or task.status == "cancelled":
            return
        outcome, summary = run_outcome(status, message)
        interval = RECURRING_INTERVALS.get(task.recurrence or "")
        if interval is not None and task.scheduled_at:
            manager.store.reschedule_task(
                task_id,
                next_run_after(task.scheduled_at, interval),
                summary if outcome == "completed" else f"Last run did not complete: {summary}",
            )
        elif outcome == "completed":
            manager.complete_task(task_id, summary)
        elif outcome == "waiting_for_approval":
            manager.block_task_on_approval(task_id, summary)
        else:
            manager.fail_task(task_id, summary)

    async def run_due(self) -> int:
        # BUG-40 — Pause means "start no new background work". A due task is new
        # work, so a paused host leaves it in the queue rather than claiming it;
        # it becomes due the moment the owner resumes. Continuing a run the owner
        # already approved is deliberately *not* gated here: that work is already
        # under way, and abandoning it would make Pause a way to lose a decision.
        if HostControl(self.workspace_root).is_paused():
            return 0
        tasks = self.store.claim_due_tasks(utc_now())
        for task in tasks:
            principal_id = task.session_id.removeprefix("sess_inbox_")
            if principal_id == task.session_id or self.store.get_principal(principal_id) is None:
                TaskManager(self.store, EventLogWriter(self.store)).fail_task(task.task_id, "Scheduled task has no valid owner.")
                continue
            prompt = task.objective or task.title
            turn_id = new_id("turn_")
            # C11 — the cycle runs in the task's own conversation, so the
            # routine accumulates a readable thread and anything the owner
            # replied there is already in the context this cycle reads.
            run_session_id = task.run_session_id
            for attachment in task.attachments:
                attachment_id = str(attachment.get("attachment_id", ""))
                if attachment_id and self.store.load_attachment_metadata(
                    attachment_id, owner_principal_id=principal_id
                ) is not None:
                    self.store.save_session_attachment_ref(
                        session_id=run_session_id,
                        attachment_id=attachment_id,
                        owner_principal_id=principal_id,
                        turn_id=turn_id,
                    )
            response = await AgentGateway(self.workspace_root, principal_id=principal_id).submit_prompt_async(
                PromptEnvelope(
                    request_id=new_id("req_"), session_id=run_session_id, turn_id=turn_id,
                    client=ClientMetadata(type="dashboard", name="raiker-scheduler", version="1"),
                    user=UserMetadata(id=principal_id),
                    prompt=PromptPayload(
                        text=prompt,
                        attachments=task.attachments,
                        # Backlog #23 — the working method this task was created
                        # for. Every cycle ran as Chat before this, so a task
                        # whose job is "read the repository, make the change, run
                        # the tests" was given the assistant's method for it.
                        metadata={"surface": task.surface},
                    ),
                    options=PromptOptions(
                        model_profile=task.model_profile or "",
                        model=task.model or "",
                    ),
                )
            )
            manager = TaskManager(self.store, EventLogWriter(self.store))
            # A user may have stopped the task while its governed turn was
            # reaching a safe boundary; `_land_outcome` re-reads the task and
            # never overwrites that cancellation. A recurring task keeps its
            # slot whatever one cycle did, so the summary says which it was —
            # otherwise a cycle that never ran reads exactly like one that
            # succeeded.
            self._land_outcome(manager, task.task_id, response.status, response.message)
        return len(tasks)


# How a governed turn's terminal status lands on the task the scheduler ran, and
# what the owner is told when the turn leaves no message of its own (BUG-09).
# Treating every non-`completed` status as a failure was wrong twice over: a run
# parked on an approval had not failed at all, and a blank message produced a
# `Task failed` card and audit line that said nothing about why.
SUMMARY_MAX_CHARS = 500
RUN_OUTCOMES: dict[str, tuple[str, str]] = {
    "completed": ("completed", "The run finished without a summary."),
    "needs_approval": (
        "waiting_for_approval",
        "Waiting for your approval before this run can continue.",
    ),
    "denied": ("failed", "Policy denied an action this run needed."),
    "failed": ("failed", "The run failed without a stated reason."),
}


def run_outcome(status: str, message: str) -> tuple[str, str]:
    """Map one governed turn's result onto ``(task status, stated summary)``.

    An unrecognised status fails closed *and* says so, rather than recording a
    terminal state the owner cannot account for.
    """
    task_status, fallback = RUN_OUTCOMES.get(
        status,
        ("failed", f"The run ended with an unrecognised status: {status or 'unknown'}."),
    )
    return task_status, ((message or "").strip()[:SUMMARY_MAX_CHARS] or fallback)


def _resume_block_reason(error: str) -> str:
    """Why an automatic continuation could not proceed, in the owner's terms."""
    if error == "suspended_turn_already_resumed":
        return "This run was already continued somewhere else, so it was not continued twice."
    if error == "suspended_turn_too_large":
        return "This run's parked state is too large to replay, so it must be started again."
    if error in ("suspended_turn_unreadable", "suspended_turn_not_found"):
        return "This run's parked state could not be read, so it must be started again."
    return f"This run could not be continued automatically ({error}). You can run it again."


# Recurring cadences and the gap between one governed cycle and the next. A
# recurring task is re-armed after every cycle rather than closed, so a standing
# agent — "keep improving the landing page", "watch the build" — keeps working
# until the owner stops it. `continuous` is the shortest cadence offered: it is
# still one discrete governed turn per cycle, never an unbounded loop, so every
# cycle passes through policy, gates, and approvals exactly like a typed prompt.
CONTINUOUS_INTERVAL = timedelta(minutes=20)
RECURRING_INTERVALS: dict[str, timedelta] = {
    "continuous": CONTINUOUS_INTERVAL,
    "hourly": timedelta(hours=1),
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
}


def next_run_after(iso: str, interval: timedelta) -> str:
    """The first `iso + n*interval` that is still in the future.

    Stepping forward from the original slot (rather than from "now") keeps a
    schedule anchored to the time the owner picked, and skipping past every
    elapsed slot means a host that was asleep does not wake up owing a backlog
    of identical runs.
    """
    next_run = datetime.fromisoformat(iso.replace("Z", "+00:00")) + interval
    now = datetime.now(UTC)
    while next_run <= now:
        next_run += interval
    return next_run.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _next_daily(iso: str) -> str:
    return next_run_after(iso, RECURRING_INTERVALS["daily"])


#: BUG-276 — the cadences a telemetry destination may be delivered on, plus the
#: one that means it is not. Drawn from `RECURRING_INTERVALS` rather than
#: redeclared beside it, so the product has one cadence vocabulary: a name the
#: Tasks board offers is a name a collector offers, with the same meaning.
TELEMETRY_CADENCES: tuple[str, ...] = ("off", *RECURRING_INTERVALS)


def _next_delivery(destination: Mapping[str, object]) -> str:
    """When a just-claimed destination becomes due again.

    Anchored to the slot that was claimed rather than to "now", so a delivery
    that took ninety seconds does not drift the schedule by ninety seconds every
    run, and a host that was asleep does not wake up owing a queue of identical
    deliveries. That is `next_run_after`'s contract, and it is why this reads the
    claimed value instead of the clock.

    A row whose cadence is unrecognised — written by a newer version, or edited
    outside the product — falls back to daily rather than to a crash or to a
    tight loop. Slower than asked for is the safe direction for something that
    reaches the network.
    """
    cadence = str(destination.get("delivery_cadence") or "off")
    interval = RECURRING_INTERVALS.get(cadence, RECURRING_INTERVALS["daily"])
    return next_run_after(str(destination.get("next_delivery_at") or utc_now()), interval)
