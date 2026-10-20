"""The goal coordinator (PA-D01, PA-D02).

It is deliberately small and model-independent. It decides which step is due,
reserves budget, files that step as an ordinary governed task, reads the task's
status back, and assesses the outcome from recorded evidence. Every tool call
the step's turn makes still goes through the policy engine, the broker and the
runtime authority exactly as any task's does: the coordinator adds no tool, no
grant and no executor, and a step never has more authority than a task the
owner filed by hand.

Rules it keeps:

* **Nothing runs without the owner's Start.** Accepting a plan pins the
  execution profile; Start is the intent to run. A model cannot create, accept
  or start a goal — there is no tool for it.
* **The profile is a ceiling, checked on every dispatch and again just before
  the scheduler runs a step.** Every model the turn could fall back to must be
  allowed, so a local-only goal is never carried to a hosted model by the
  owner's fallback sequence. A refusal is a named blocker with a route to
  Settings, never a silent switch.
* **A changed profile pauses work at a safe boundary.** Resume revalidates
  owner, profile, model chain and budget before anything further is filed.
* **Completion is evidence, not prose.** A criterion is met by the steps linked
  to it finishing (named as that) or by the owner confirming it. No model
  statement completes a goal.
* **Stop reaches every step.** Linked tasks and what they delegated are
  stopped through the same interrupt path as a task's Stop; nothing new is
  claimed afterwards.
"""

from __future__ import annotations

import logging
from contextlib import suppress
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from raiker.contracts.ids import new_id, utc_now
from raiker.goals import profiles as profile_store
from raiker.goals import store as goal_store
from raiker.goals.lifecycle import (
    ACTIVE_STATES,
    REASONS,
    SETTLED_STATES,
    STEP_SETTLED,
    allowed_actions,
    step_from_task,
)
from raiker.goals.profiles import ExecutionProfile
from raiker.goals.store import GoalError

_LOG = logging.getLogger(__name__)

#: Linked task statuses Stop and Pause reach.
_ACTIVE_TASK = frozenset(
    {"queued", "running", "continuing", "waiting_for_approval", "waiting_for_user_answer",
     "waiting_for_children", "paused"}
)


@dataclass(frozen=True)
class Spend:
    total_usd: Decimal
    unpriced: list[str]
    providers: list[str]


class GoalCoordinator:
    def __init__(self, workspace_root: str | Path) -> None:
        from raiker.storage.sqlite import SQLiteStore

        self.workspace_root = Path(workspace_root)
        self.store = SQLiteStore(self.workspace_root)

    # ── reading ──────────────────────────────────────────────────────────

    def _goal(self, owner: str, goal_id: str) -> dict[str, Any]:
        goal = goal_store.get_goal(self.store, owner=owner, goal_id=goal_id)
        if goal is None:
            raise GoalError("goal_not_found")
        return goal

    def _event(self, owner: str, goal_id: str, kind: str, detail: dict[str, Any] | None = None) -> None:
        with self.store.connect() as connection:
            goal_store.record_event(connection, goal_id, owner, kind, detail)
        self._audit(owner, kind, {"goal_id": goal_id, **(detail or {})})

    def _audit(self, owner: str, event_type: str, payload: dict[str, Any]) -> None:
        """Ids, states and counts only — never a criterion's or step's text."""
        from raiker.events.types import make_event
        from raiker.events.writer import EventLogWriter

        session_id = f"sess_inbox_{owner}"
        with suppress(Exception):
            self.store.create_session(session_id, str(self.workspace_root), title="Inbox")
            EventLogWriter(self.store).append(
                make_event(session_id=session_id, turn_id=None, event_type=event_type, actor="goal_coordinator",
                           payload={"principal_id": owner, **payload})
            )

    def spend(self, owner: str, goal: dict[str, Any]) -> Spend:
        """What the goal's step runs have cost, reconciled from the usage ledger.

        The ledger records the provider that actually answered each call, so
        this is also the after-the-fact receipt of where the goal's work went.
        """
        from raiker.tasks.cost_limit import resolve_price

        sessions: list[str] = []
        for step in goal["steps"]:
            if step.get("task_id"):
                task = self.store.load_task(str(step["task_id"]))
                if task is not None:
                    sessions.append(task.run_session_id)
        if not sessions:
            return Spend(Decimal(0), [], [])
        marks = ",".join("?" * len(sessions))
        with self.store.connect() as connection:
            rows = connection.execute(
                f"SELECT provider, model, SUM(input_tokens) AS i, SUM(output_tokens) AS o, "  # noqa: S608 - placeholders only
                f"SUM(cache_read_tokens) AS cr, SUM(cache_write_tokens) AS cw FROM model_usage_ledger "
                f"WHERE owner_principal_id = ? AND session_id IN ({marks}) GROUP BY provider, model",
                (owner, *sessions),
            ).fetchall()
        total = Decimal(0)
        unpriced: list[str] = []
        providers: list[str] = []
        for row in rows:
            provider, model = str(row["provider"]), str(row["model"])
            if provider not in providers:
                providers.append(provider)
            try:
                price = resolve_price(self.store, owner, provider, model, _configured_pricing(provider, model))
            except Exception:  # noqa: BLE001 - an unreadable price is an unpriced model
                price = None
            if price is None:
                if (int(row["i"] or 0) + int(row["o"] or 0)) > 0 and model not in unpriced:
                    unpriced.append(model)
                continue
            total += price.cost(
                input_tokens=int(row["i"] or 0), output_tokens=int(row["o"] or 0),
                cache_write_tokens=int(row["cw"] or 0), cache_read_tokens=int(row["cr"] or 0),
            )
        return Spend(total, unpriced, providers)

    def view(self, owner: str, goal_id: str) -> dict[str, Any]:
        """The goal as surfaces show it, with the actions its state permits."""
        goal = self._goal(owner, goal_id)
        pinned = None
        if goal.get("profile_id"):
            pinned = profile_store.get_profile(
                self.store, owner=owner, profile_id=str(goal["profile_id"]), version=goal.get("profile_version")
            )
        current, source = profile_store.resolve_for(self.store, owner=owner, project_id=goal.get("project_id"))
        spend = self.spend(owner, goal)
        steps = []
        for step in goal["steps"]:
            task = self.store.load_task(str(step["task_id"])) if step.get("task_id") else None
            steps.append({
                "step_id": step["step_id"], "title": step["title"], "instruction": step["instruction"],
                "surface": step["surface"], "depends_on": step["depends_on"], "criterion_ids": step["criterion_ids"],
                "state": step["state"], "reason": step["reason"], "task_id": step.get("task_id"),
                "task_status": task.status if task is not None else None,
                "task_summary": (task.summary or task.current_step) if task is not None else None,
            })
        criteria = [
            {
                "criterion_id": c["criterion_id"], "text": c["text"], "mandatory": c["mandatory"],
                "validator": c["validator"], "evidence_kind": c.get("evidence_kind"),
                "evidence_ref": c.get("evidence_ref"), "evidence_note": c.get("evidence_note"),
                "verified_at": c.get("verified_at"),
            }
            for c in goal["criteria"]
        ]
        outside = [p for p in spend.providers if pinned is not None and not _provider_in(pinned, p)]
        status = str(goal["status"])
        return {
            "goal_id": goal["goal_id"], "title": goal["title"], "objective": goal["objective"],
            "project_id": goal.get("project_id"), "model_profile": goal.get("model_profile"),
            "model": goal.get("model"), "status": status, "reason": goal["reason"],
            "reason_text": REASONS.get(str(goal["reason"]), ""), "reason_detail": goal["reason_detail"],
            "revision": int(goal["revision"]), "allowed_actions": allowed_actions(status),
            "created_at": goal["created_at"], "updated_at": goal["updated_at"],
            "accepted_at": goal.get("accepted_at"), "settled_at": goal.get("settled_at"),
            "criteria": criteria, "steps": steps,
            "profile": pinned.view() if pinned is not None else None,
            "profile_current": (
                current is not None and pinned is not None
                and (current.profile_id, current.version) == (pinned.profile_id, pinned.version)
            ),
            "profile_source": source,
            "budget": {
                "max_step_runs": goal.get("max_step_runs"), "step_runs": int(goal.get("step_runs") or 0),
                "max_cost_usd": goal.get("max_cost_usd"), "spent_usd": float(round(spend.total_usd, 4)),
                "unpriced_models": spend.unpriced,
            },
            "providers_used": spend.providers,
            "providers_outside_profile": outside,
            "events": goal["events"],
        }

    def list_views(self, owner: str, *, archived: bool = False) -> list[dict[str, Any]]:
        views = []
        for goal_id in goal_store.list_goal_ids(self.store, owner=owner, archived=archived):
            with suppress(GoalError):
                views.append(self.view(owner, goal_id))
        return views

    # ── owner actions ────────────────────────────────────────────────────

    def _require_action(self, goal: dict[str, Any], action: str) -> None:
        if action not in allowed_actions(str(goal["status"])):
            raise GoalError("goal_action_not_allowed", f"{action}:{goal['status']}")

    def accept(self, owner: str, goal_id: str, base_revision: int) -> None:
        """Draft → ready under the profile Settings binds for this goal (PA-D02)."""
        goal = self._goal(owner, goal_id)
        self._require_action(goal, "accept")
        if not any(c["mandatory"] for c in goal["criteria"]):
            raise GoalError("goal_needs_mandatory_criterion")
        if not goal["steps"]:
            raise GoalError("goal_needs_step")
        if not goal.get("model_profile") or not goal.get("model"):
            # A step with no model runs on whatever an empty selection resolves
            # to, which is neither what the owner chose nor what the profile was
            # asked about (FIXED-1054).
            raise GoalError("goal_needs_model")
        if not self.store.is_configured_model(owner, str(goal["model_profile"]), str(goal["model"])):
            raise GoalError("goal_model_not_configured")
        linked = {cid for step in goal["steps"] for cid in step["criterion_ids"]}
        for criterion in goal["criteria"]:
            if criterion["validator"] == "steps_finish" and criterion["criterion_id"] not in linked:
                # It could never be met: no step would ever count as its evidence.
                raise GoalError("goal_criterion_has_no_step", criterion["criterion_id"])
        profile, _source = profile_store.resolve_for(self.store, owner=owner, project_id=goal.get("project_id"))
        if profile is None:
            raise GoalError("no_execution_profile")
        with self.store.connect() as connection:
            if not goal_store.transition(
                connection, owner=owner, goal_id=goal_id, base_revision=base_revision, from_states=("draft",),
                to_state="ready", profile_id=profile.profile_id, profile_version=profile.version,
                max_step_runs=profile.max_step_runs, max_cost_usd=profile.max_cost_usd, accepted_at=utc_now(),
            ):
                raise GoalError("goal_revision_stale")
        self._event(owner, goal_id, "goal_accepted",
                    {"profile_id": profile.profile_id, "profile_version": profile.version})

    def start(self, owner: str, goal_id: str, base_revision: int) -> None:
        goal = self._goal(owner, goal_id)
        self._require_action(goal, "start")
        blocker = self._revalidate(owner, goal, repin=True)
        if blocker is not None:
            raise GoalError(*blocker)
        # A repin writes the goal, so the owner's revision is read back: Start
        # is still refused if anything else moved the goal since they saw it.
        base_revision += int(self._goal(owner, goal_id)["revision"]) - int(goal["revision"])
        with self.store.connect() as connection:
            if not goal_store.transition(
                connection, owner=owner, goal_id=goal_id, base_revision=base_revision,
                from_states=("ready",), to_state="running",
            ):
                raise GoalError("goal_revision_stale")
        self._event(owner, goal_id, "goal_started")
        self.advance(owner, goal_id)

    def pause(self, owner: str, goal_id: str, base_revision: int | None, *, reason: str = "owner_paused") -> None:
        goal = self._goal(owner, goal_id)
        if base_revision is not None:
            self._require_action(goal, "pause")
        with self.store.connect() as connection:
            if not goal_store.transition(
                connection, owner=owner, goal_id=goal_id, base_revision=base_revision,
                from_states=("running", "waiting"), to_state="paused", reason=reason,
            ):
                raise GoalError("goal_revision_stale")
        reached = self._interrupt(owner, goal, "pause", REASONS.get(reason, reason))
        self._event(owner, goal_id, "goal_paused", {"reason": reason, "steps_paused": reached})

    def resume(self, owner: str, goal_id: str, base_revision: int) -> None:
        """Paused → running, only after owner, profile, model chain and budget recheck."""
        goal = self._goal(owner, goal_id)
        self._require_action(goal, "resume")
        blocker = self._revalidate(owner, goal, repin=True)
        if blocker is not None:
            raise GoalError(*blocker)
        with self.store.connect() as connection:
            if not goal_store.transition(
                connection, owner=owner, goal_id=goal_id, base_revision=base_revision,
                from_states=("paused",), to_state="running",
            ):
                raise GoalError("goal_revision_stale")
        reached = self._interrupt(owner, self._goal(owner, goal_id), "resume", "Goal resumed")
        self._event(owner, goal_id, "goal_resumed", {"steps_resumed": reached})
        self.advance(owner, goal_id)

    def stop(self, owner: str, goal_id: str, base_revision: int) -> dict[str, int]:
        """Stop every linked task and everything it delegated; keep what finished."""
        goal = self._goal(owner, goal_id)
        self._require_action(goal, "stop")
        with self.store.connect() as connection:
            if not goal_store.transition(
                connection, owner=owner, goal_id=goal_id, base_revision=base_revision,
                from_states=("ready", "running", "waiting", "paused"), to_state="stopped",
                settled_at=utc_now(),
            ):
                raise GoalError("goal_revision_stale")
            connection.execute(
                "UPDATE goal_steps SET state = 'stopped', reason = 'goal_stopped', updated_at = ? "
                "WHERE goal_id = ? AND state NOT IN ('done', 'failed', 'stopped', 'blocked')",
                (utc_now(), goal_id),
            )
        reached = self._interrupt(owner, goal, "cancel", "The owner stopped the goal")
        done = sum(1 for s in goal["steps"] if s["state"] == "done")
        report = {"steps_done": done, "steps_stopped": len(goal["steps"]) - done, "tasks_stopped": reached}
        self._event(owner, goal_id, "goal_stopped", report)
        return report

    def archive(self, owner: str, goal_id: str, base_revision: int) -> None:
        goal = self._goal(owner, goal_id)
        self._require_action(goal, "archive")
        with self.store.connect() as connection:
            if not goal_store.transition(
                connection, owner=owner, goal_id=goal_id, base_revision=base_revision,
                from_states=("draft", *sorted(SETTLED_STATES)), to_state="archived",
                reason=str(goal["status"]), archived_at=utc_now(),
            ):
                raise GoalError("goal_revision_stale")
        self._event(owner, goal_id, "goal_archived", {"from": goal["status"]})

    def confirm(self, owner: str, goal_id: str, criterion_id: str, base_revision: int, note: str) -> None:
        """The owner's own check of one criterion — recorded as theirs, never as a model's."""
        goal = self._goal(owner, goal_id)
        self._require_action(goal, "confirm")
        if int(goal["revision"]) != base_revision:
            raise GoalError("goal_revision_stale")
        if criterion_id not in {c["criterion_id"] for c in goal["criteria"]}:
            raise GoalError("goal_criterion_unknown")
        with self.store.connect() as connection:
            connection.execute(
                "UPDATE goal_criteria SET evidence_kind = 'owner_confirmed', evidence_ref = NULL, "
                "evidence_note = ?, verified_at = ? WHERE goal_id = ? AND criterion_id = ?",
                (note.strip()[:300] or None, utc_now(), goal_id, criterion_id),
            )
            connection.execute(
                "UPDATE goals SET revision = revision + 1, updated_at = ? WHERE goal_id = ?", (utc_now(), goal_id)
            )
        self._event(owner, goal_id, "goal_criterion_confirmed", {"criterion_id": criterion_id})
        if goal["status"] == "partial":
            self._assess(owner, self._goal(owner, goal_id), from_states=("partial",))
        elif goal["status"] in ACTIVE_STATES:
            self.advance(owner, goal_id)

    # ── safety checks ────────────────────────────────────────────────────

    def _pinned(self, owner: str, goal: dict[str, Any]) -> ExecutionProfile | None:
        if not goal.get("profile_id"):
            return None
        return profile_store.get_profile(
            self.store, owner=owner, profile_id=str(goal["profile_id"]), version=goal.get("profile_version")
        )

    def _revalidate(self, owner: str, goal: dict[str, Any], *, repin: bool) -> tuple[str, str] | None:
        """``None`` when the goal may run now; otherwise ``(reason, detail)``.

        ``repin`` is Start and Resume — the owner's explicit intent to run: a
        profile that changed since acceptance is adopted only after the new one
        admits the model chain and budget, and the adoption is recorded. The
        coordinator's own pass never repins; it pauses instead.
        """
        principal = self.store.get_principal(owner)
        if principal is None:
            return ("goal_owner_unknown", "")
        current, _source = profile_store.resolve_for(self.store, owner=owner, project_id=goal.get("project_id"))
        if current is None:
            return ("no_execution_profile", "")
        pinned = self._pinned(owner, goal)
        if pinned is None or (pinned.profile_id, pinned.version) != (current.profile_id, current.version):
            if not repin:
                return ("profile_changed", "")
            pinned = current
        refused = profile_store.chain_refusal(profile_store.model_chain(self.store, owner, pinned, goal.get("model_profile"), goal.get("model")))
        if refused:
            return ("profile_blocks_model", refused)
        if repin and (goal.get("profile_id"), goal.get("profile_version")) != (pinned.profile_id, pinned.version):
            with self.store.connect() as connection:
                connection.execute(
                    "UPDATE goals SET profile_id = ?, profile_version = ?, max_step_runs = ?, max_cost_usd = ?, "
                    "updated_at = ? WHERE goal_id = ?",
                    (pinned.profile_id, pinned.version, pinned.max_step_runs, pinned.max_cost_usd, utc_now(),
                     goal["goal_id"]),
                )
            self._event(owner, str(goal["goal_id"]), "goal_profile_repinned",
                        {"profile_id": pinned.profile_id, "profile_version": pinned.version})
            goal = self._goal(owner, str(goal["goal_id"]))
        exhausted = self._budget_exhausted(owner, goal)
        if exhausted:
            return ("budget_exhausted", exhausted)
        return None

    def _budget_exhausted(self, owner: str, goal: dict[str, Any]) -> str:
        runs, limit = int(goal.get("step_runs") or 0), goal.get("max_step_runs")
        pending = any(s["state"] == "pending" for s in goal["steps"])
        if limit is not None and runs >= int(limit) and pending:
            return f"{runs} of {limit} step runs used"
        cap = goal.get("max_cost_usd")
        if cap is not None and self.spend(owner, goal).total_usd >= Decimal(str(cap)):
            return f"spent at least ${cap}"
        return ""

    def guard_task(self, task: Any) -> tuple[str, str] | None:
        """Called by the scheduler just before it runs a claimed task.

        ``None`` for a task that is not a goal step, or a step whose goal may
        still run it. Otherwise ``(reason, detail)``: the goal is no longer
        running (Stop or Pause reached it first) or the model chain is now
        outside its profile — the owner changed their default model or
        fallbacks after the step was filed.
        """
        found = goal_store.goal_for_task(self.store, task.task_id)
        if found is None:
            return None
        owner, goal_id, _step_id = found
        goal = goal_store.get_goal(self.store, owner=owner, goal_id=goal_id)
        if goal is None or goal["status"] not in ACTIVE_STATES:
            return ("goal_not_running", str(goal["status"]) if goal else "")
        pinned = self._pinned(owner, goal)
        if pinned is None:
            return ("no_execution_profile", "")
        refused = profile_store.chain_refusal(profile_store.model_chain(self.store, owner, pinned, goal.get("model_profile"), goal.get("model")))
        if refused:
            # The step goes back to pending and its run is refunded: nothing ran,
            # and the goal waits on the named blocker. The next pass files it
            # again once Settings or the owner's models admit the chain.
            with self.store.connect() as connection:
                connection.execute(
                    "UPDATE goal_steps SET state = 'pending', reason = '', task_id = NULL, updated_at = ? "
                    "WHERE goal_id = ? AND step_id = ? AND task_id = ?",
                    (utc_now(), goal_id, _step_id, task.task_id),
                )
                connection.execute(
                    "UPDATE goals SET step_runs = MAX(step_runs - 1, 0) WHERE goal_id = ?", (goal_id,)
                )
            self._wait(owner, goal, "profile_blocks_model", refused)
            return ("profile_blocks_model", refused)
        return None

    def _interrupt(self, owner: str, goal: dict[str, Any], action_type: str, reason: str) -> int:
        """Carry Pause, Resume or Stop to the goal's linked tasks.

        * **Stop** goes through the task's own interrupt path, with its cascade,
          so a step's delegated work stops too and nothing is claimed after.
        * **Pause** parks step tasks that are filed but not yet claimed. A run
          already in flight finishes its current turn — pausing a goal starts
          nothing new, it does not abandon a turn half way (Stop does that).
        * **Resume** makes those parked tasks due again, atomically on their
          status, so two presses run each once.
        """
        from raiker.contracts.models import InterruptAction
        from raiker.events.writer import EventLogWriter
        from raiker.runtime.interrupts import InterruptController

        reached = 0
        for step in goal["steps"]:
            task = self.store.load_task(str(step["task_id"])) if step.get("task_id") else None
            if task is None:
                continue
            if action_type == "cancel" and task.status in _ACTIVE_TASK:
                InterruptController(self.store, EventLogWriter(self.store)).apply_at_safe_boundary(
                    InterruptAction(
                        action_id=new_id("act_"), task_id=task.task_id, session_id=task.session_id,
                        action_type="cancel", reason=reason, steer_text=None,
                    )
                )
                reached += 1
            elif action_type == "pause" and task.status == "queued":
                with self.store.connect() as connection:
                    reached += connection.execute(
                        "UPDATE tasks SET status = 'paused', current_step = ?, updated_at = ? "
                        "WHERE task_id = ? AND status = 'queued'",
                        ("Paused with its goal", utc_now(), task.task_id),
                    ).rowcount
            elif action_type == "resume" and task.status == "paused":
                reached += int(self.store.resume_paused_routine(task.task_id))
        return reached

    # ── the pass ─────────────────────────────────────────────────────────

    def _wait(self, owner: str, goal: dict[str, Any], reason: str, detail: str = "") -> None:
        if goal["status"] == "waiting" and goal["reason"] == reason and goal["reason_detail"] == detail:
            return
        with self.store.connect() as connection:
            goal_store.transition(
                connection, owner=owner, goal_id=goal["goal_id"], base_revision=None,
                from_states=("running", "waiting"), to_state="waiting", reason=reason, reason_detail=detail,
            )
        self._event(owner, goal["goal_id"], "goal_waiting", {"reason": reason})

    def _run(self, owner: str, goal: dict[str, Any]) -> None:
        if goal["status"] == "running" and not goal["reason"]:
            return
        with self.store.connect() as connection:
            goal_store.transition(
                connection, owner=owner, goal_id=goal["goal_id"], base_revision=None,
                from_states=("running", "waiting"), to_state="running",
            )

    def _refresh_steps(self, goal: dict[str, Any]) -> None:
        now = utc_now()
        with self.store.connect() as connection:
            for step in goal["steps"]:
                if step["state"] in STEP_SETTLED:
                    continue
                if not step.get("task_id"):
                    if step["state"] == "running" and _older_than(str(step["updated_at"]), seconds=120):
                        # Claimed for dispatch and never given a task: the host
                        # stopped between the two writes. The run counter kept
                        # its reservation, so the step fails rather than re-files.
                        connection.execute(
                            "UPDATE goal_steps SET state = 'failed', reason = 'dispatch_interrupted', "
                            "updated_at = ? WHERE goal_id = ? AND step_id = ? AND task_id IS NULL",
                            (now, goal["goal_id"], step["step_id"]),
                        )
                        step["state"], step["reason"] = "failed", "dispatch_interrupted"
                    continue
                task = self.store.load_task(str(step["task_id"]))
                state, reason = step_from_task(task.status if task is not None else None)
                if (state, reason) != (step["state"], step["reason"]):
                    connection.execute(
                        "UPDATE goal_steps SET state = ?, reason = ?, updated_at = ? WHERE goal_id = ? AND step_id = ?",
                        (state, reason, now, goal["goal_id"], step["step_id"]),
                    )
                    step["state"], step["reason"] = state, reason

    def advance(self, owner: str, goal_id: str) -> None:
        """One coordinator pass over a running or waiting goal."""
        goal = self._goal(owner, goal_id)
        if goal["status"] not in ACTIVE_STATES:
            return
        current, _source = profile_store.resolve_for(self.store, owner=owner, project_id=goal.get("project_id"))
        pinned = self._pinned(owner, goal)
        if current is None or pinned is None or (current.profile_id, current.version) != (
            pinned.profile_id, pinned.version
        ):
            # PROF-03 — the boundary this work was accepted under is not the
            # one Settings states now. Pause at this safe boundary; Resume
            # revalidates against the new one.
            self.pause(owner, goal_id, None, reason="profile_changed")
            return
        self._refresh_steps(goal)
        states = {s["step_id"]: s["state"] for s in goal["steps"]}
        due: list[dict[str, Any]] = []
        with self.store.connect() as connection:
            for step in goal["steps"]:
                if step["state"] != "pending":
                    continue
                deps = [states.get(d, "failed") for d in step["depends_on"]]
                if any(d in {"failed", "stopped", "blocked"} for d in deps):
                    connection.execute(
                        "UPDATE goal_steps SET state = 'blocked', reason = 'dependency_not_finished', updated_at = ? "
                        "WHERE goal_id = ? AND step_id = ? AND state = 'pending'",
                        (utc_now(), goal_id, step["step_id"]),
                    )
                    step["state"] = states[step["step_id"]] = "blocked"
                elif all(d == "done" for d in deps):
                    due.append(step)
        if due:
            chain = profile_store.model_chain(self.store, owner, pinned, goal.get("model_profile"), goal.get("model"))
            refused = profile_store.chain_refusal(chain)
            if refused:
                self._wait(owner, goal, "profile_blocks_model", refused)
                return
            exhausted = self._budget_exhausted(owner, goal)
            if exhausted:
                self.pause(owner, goal_id, None, reason="budget_exhausted")
                return
            hosted = any(not entry.local for entry in chain)
            for step in due:
                if not self._dispatch(owner, goal, step, pinned, withhold_memory=hosted and not pinned.memory_to_hosted):
                    break
            goal = self._goal(owner, goal_id)
            self._refresh_steps(goal)
        self._settle_or_report(owner, goal)

    def _dispatch(
        self, owner: str, goal: dict[str, Any], step: dict[str, Any], profile: ExecutionProfile, *,
        withhold_memory: bool,
    ) -> bool:
        """Reserve one step run, then file the step as an ordinary task. ``False`` stops the batch."""
        from raiker.control.dashboard import DashboardService

        goal_id = str(goal["goal_id"])
        with self.store.connect() as connection:
            # Reserve before dispatch: the run counter and the step claim move
            # together, compared-and-set, so two passes cannot both file it.
            reserved = connection.execute(
                "UPDATE goals SET step_runs = step_runs + 1, updated_at = ? WHERE goal_id = ? "
                "AND status IN ('running', 'waiting') AND (max_step_runs IS NULL OR step_runs < max_step_runs)",
                (utc_now(), goal_id),
            ).rowcount
            if not reserved:
                return False
            claimed = connection.execute(
                "UPDATE goal_steps SET state = 'running', reason = 'dispatching', updated_at = ? "
                "WHERE goal_id = ? AND step_id = ? AND state = 'pending' AND task_id IS NULL",
                (utc_now(), goal_id, step["step_id"]),
            ).rowcount
            if not claimed:
                connection.execute("UPDATE goals SET step_runs = step_runs - 1 WHERE goal_id = ?", (goal_id,))
                return True
        principal = self.store.get_principal(owner)
        user_id = getattr(principal, "delegated_by_user_id", None) if principal is not None else None
        try:
            view = DashboardService(self.workspace_root).create_task(
                title=f"{goal['title']} — {step['title']}"[:160],
                objective=step["instruction"],
                user_id=user_id,
                principal_id=owner,
                project_id=goal.get("project_id"),
                surface=str(step["surface"]),
                model_profile=goal.get("model_profile"),
                model=goal.get("model"),
            )
        except Exception as exc:  # noqa: BLE001 - the refusal is the step's outcome
            reason = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
            with self.store.connect() as connection:
                connection.execute(
                    "UPDATE goal_steps SET state = 'failed', reason = ?, updated_at = ? WHERE goal_id = ? AND step_id = ?",
                    (reason[:120], utc_now(), goal_id, step["step_id"]),
                )
            self._event(owner, goal_id, "goal_step_refused", {"step_id": step["step_id"], "reason": reason[:120]})
            return True
        task_id = str(view.task_id)
        task = self.store.load_task(task_id)
        if profile.max_cost_usd is not None and task is not None:
            # The run itself stops at its next safe boundary once the goal's
            # remaining budget is spent, rather than only the next dispatch.
            remaining = Decimal(str(profile.max_cost_usd)) - self.spend(owner, goal).total_usd
            self.store.set_task_cost_limit(task_id, max(0.01, float(round(remaining, 2))))
        if withhold_memory and task is not None:
            goal_store.withhold_session_memory(
                self.store, session_id=task.run_session_id, owner=owner, reason="execution_profile"
            )
        with self.store.connect() as connection:
            connection.execute(
                "UPDATE goal_steps SET task_id = ?, reason = '', updated_at = ? WHERE goal_id = ? AND step_id = ?",
                (task_id, utc_now(), goal_id, step["step_id"]),
            )
        self._event(owner, goal_id, "goal_step_started",
                    {"step_id": step["step_id"], "task_id": task_id, "memory_withheld": withhold_memory})
        return True

    def _auto_evidence(self, goal: dict[str, Any]) -> None:
        """``steps_finish`` criteria whose every linked step is done get that evidence."""
        with self.store.connect() as connection:
            for criterion in goal["criteria"]:
                if criterion["validator"] != "steps_finish" or criterion.get("evidence_kind"):
                    continue
                linked = [s for s in goal["steps"] if criterion["criterion_id"] in s["criterion_ids"]]
                if linked and all(s["state"] == "done" for s in linked):
                    ref = ",".join(str(s.get("task_id")) for s in linked)
                    connection.execute(
                        "UPDATE goal_criteria SET evidence_kind = 'steps_finished', evidence_ref = ?, verified_at = ? "
                        "WHERE goal_id = ? AND criterion_id = ?",
                        (ref, utc_now(), goal["goal_id"], criterion["criterion_id"]),
                    )
                    criterion["evidence_kind"] = "steps_finished"

    def _settle_or_report(self, owner: str, goal: dict[str, Any]) -> None:
        self._auto_evidence(goal)
        steps = goal["steps"]
        running = [s for s in steps if s["state"] == "running"]
        waiting = [s for s in steps if s["state"] == "waiting"]
        if running:
            self._run(owner, goal)
            return
        if waiting:
            self._wait(owner, goal, str(waiting[0]["reason"] or "step_paused"))
            return
        if all(s["state"] in STEP_SETTLED for s in steps):
            self._assess(owner, goal, from_states=("running", "waiting"))
            return
        # Pending steps with nothing running: their dependencies are settled
        # but the batch stopped (budget reserve lost a race). Next pass files them.

    def _assess(self, owner: str, goal: dict[str, Any], *, from_states: tuple[str, ...]) -> None:
        """Completed only when every mandatory criterion has evidence (PA-D01)."""
        goal = self._goal(owner, str(goal["goal_id"]))
        self._auto_evidence(goal)
        mandatory = [c for c in goal["criteria"] if c["mandatory"]]
        met = [c for c in goal["criteria"] if c.get("evidence_kind")]
        if mandatory and all(c.get("evidence_kind") for c in mandatory):
            outcome = "completed"
        elif met:
            outcome = "partial"
        else:
            outcome = "failed"
        unmet = [c["criterion_id"] for c in mandatory if not c.get("evidence_kind")]
        with self.store.connect() as connection:
            moved = goal_store.transition(
                connection, owner=owner, goal_id=goal["goal_id"], base_revision=None, from_states=from_states,
                to_state=outcome, reason="", reason_detail=",".join(unmet), settled_at=utc_now(),
            )
        if moved:
            self._event(owner, goal["goal_id"], f"goal_{outcome}",
                        {"criteria_met": len(met), "criteria_unmet": len(unmet)})

    def reconcile_all(self) -> int:
        """Advance every running or waiting goal; one goal's failure is its own."""
        advanced = 0
        for owner, goal_id in goal_store.active_goals(self.store):
            try:
                self.advance(owner, goal_id)
                advanced += 1
            except Exception as exc:  # noqa: BLE001 - contained per goal
                _LOG.warning("goal %s could not advance: %s", goal_id, type(exc).__name__)
        return advanced

    def profile_changed(self, owner: str) -> int:
        """PROF-03 — pause each of the owner's active goals the change moved."""
        paused = 0
        for active_owner, goal_id in goal_store.active_goals(self.store):
            if active_owner != owner:
                continue
            goal = self._goal(owner, goal_id)
            current, _ = profile_store.resolve_for(self.store, owner=owner, project_id=goal.get("project_id"))
            pinned = self._pinned(owner, goal)
            if current is None or pinned is None or (current.profile_id, current.version) != (
                pinned.profile_id, pinned.version
            ):
                with suppress(GoalError):
                    self.pause(owner, goal_id, None, reason="profile_changed")
                    paused += 1
        return paused


def _configured_pricing(provider: str, model: str) -> Any:
    """The shipped profile's ``pricing`` block, priced the way the spend limit prices it.

    Without it a model whose rate ships with Raiker (rather than one the owner
    entered) reads as unpriced.
    """
    from raiker.models.registry import ModelProfileRegistry

    try:
        profile = ModelProfileRegistry.load().resolve(provider, model)
    except Exception:  # noqa: BLE001 - no registry entry is no configured price
        return None
    return (getattr(profile, "raw", {}) or {}).get("pricing")


def _older_than(stamp: str, *, seconds: int) -> bool:
    from datetime import UTC, datetime

    try:
        then = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return True
    if then.tzinfo is None:
        then = then.replace(tzinfo=UTC)
    return (datetime.now(UTC) - then).total_seconds() > seconds


def _provider_in(profile: ExecutionProfile, provider: str) -> bool:
    """Whether a provider the usage ledger recorded is one the profile admits.

    The ledger names a provider, not a placement, so a provider that ships only
    local profiles reads as local and every other one as hosted — the same
    conservative reading the dispatch check uses.
    """
    from raiker.models.registry import ModelProfileRegistry

    placements = {p.local_only for p in ModelProfileRegistry.load().profiles if p.provider == provider}
    local = placements == {True}
    return profile.allows(provider=provider, local=local)
