"""Rows for durable goals (PA-D01).

Every read and write names the owner; another owner's goal id reads exactly as
one that was never issued. Every owner change names the revision it was made
against and is compared-and-set, so a second tab acting on an older copy gets a
conflict instead of overwriting a newer decision.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from raiker.contracts.ids import new_id, utc_now
from raiker.goals.lifecycle import VALIDATORS

MAX_CRITERIA = 12
MAX_STEPS = 12
STEP_SURFACES = ("chat", "build")


class GoalError(ValueError):
    """A goal change refused, with the reason code the route answers with."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}:{detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def _text(value: Any, *, field: str, limit: int, required: bool = True) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise GoalError("goal_field_required", field)
    if len(text) > limit:
        raise GoalError("goal_field_too_long", field)
    return text


def clean_plan(
    *, title: Any, objective: Any, criteria: Sequence[Mapping[str, Any]], steps: Sequence[Mapping[str, Any]],
    has_project: bool, model_profile: Any = None, model: Any = None,
) -> dict[str, Any]:
    """Validate an intake or edited plan. Indices, not ids, link steps and criteria.

    A step may depend only on steps *before* it, so a plan can never contain a
    cycle and the coordinator never needs to detect one.
    """
    if len(criteria) > MAX_CRITERIA:
        raise GoalError("goal_too_many_criteria")
    if len(steps) > MAX_STEPS:
        raise GoalError("goal_too_many_steps")
    clean_criteria: list[dict[str, Any]] = []
    for index, entry in enumerate(criteria):
        validator = str(entry.get("validator") or "owner_confirms")
        if validator not in VALIDATORS:
            raise GoalError("goal_validator_unknown", validator)
        clean_criteria.append(
            {
                "criterion_id": f"c{index + 1}",
                "text": _text(entry.get("text"), field=f"criteria[{index}].text", limit=300),
                "mandatory": bool(entry.get("mandatory", True)),
                "validator": validator,
            }
        )
    clean_steps: list[dict[str, Any]] = []
    for index, entry in enumerate(steps):
        surface = str(entry.get("surface") or "chat")
        if surface not in STEP_SURFACES:
            raise GoalError("goal_step_surface_unknown", surface)
        if surface == "build" and not has_project:
            # Build's method is a repository it can read; a Build task needs a
            # project, so the goal must be filed in one (backlog #23).
            raise GoalError("goal_build_step_requires_project", f"steps[{index}]")
        depends: list[str] = []
        for dep in entry.get("depends_on") or []:
            if not isinstance(dep, int) or isinstance(dep, bool) or not 0 <= dep < index:
                raise GoalError("goal_step_dependency_invalid", f"steps[{index}]")
            depends.append(f"s{dep + 1}")
        linked: list[str] = []
        for crit in entry.get("criteria") or []:
            if not isinstance(crit, int) or isinstance(crit, bool) or not 0 <= crit < len(clean_criteria):
                raise GoalError("goal_step_criterion_invalid", f"steps[{index}]")
            linked.append(f"c{crit + 1}")
        clean_steps.append(
            {
                "step_id": f"s{index + 1}",
                "title": _text(entry.get("title"), field=f"steps[{index}].title", limit=120),
                "instruction": _text(entry.get("instruction"), field=f"steps[{index}].instruction", limit=4000),
                "surface": surface,
                "depends_on": sorted(set(depends)),
                "criterion_ids": sorted(set(linked)),
            }
        )
    chosen_profile = str(model_profile or "").strip() or None
    chosen_model = str(model or "").strip() or None
    if bool(chosen_profile) != bool(chosen_model):
        raise GoalError("goal_model_pair_required")
    return {
        "model_profile": chosen_profile,
        "model": chosen_model,
        "title": _text(title, field="title", limit=120),
        "objective": _text(objective, field="objective", limit=4000, required=False),
        "criteria": clean_criteria,
        "steps": clean_steps,
    }


def _write_plan(connection: Any, goal_id: str, plan: Mapping[str, Any]) -> None:
    now = utc_now()
    connection.execute("DELETE FROM goal_criteria WHERE goal_id = ?", (goal_id,))
    connection.execute("DELETE FROM goal_steps WHERE goal_id = ?", (goal_id,))
    for position, c in enumerate(plan["criteria"]):
        connection.execute(
            "INSERT INTO goal_criteria (goal_id, criterion_id, position, text, mandatory, validator) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (goal_id, c["criterion_id"], position, c["text"], int(c["mandatory"]), c["validator"]),
        )
    for position, s in enumerate(plan["steps"]):
        connection.execute(
            "INSERT INTO goal_steps (goal_id, step_id, position, title, instruction, surface, depends_on_json, "
            "criterion_ids_json, state, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
            (goal_id, s["step_id"], position, s["title"], s["instruction"], s["surface"],
             json.dumps(s["depends_on"]), json.dumps(s["criterion_ids"]), now),
        )


def record_event(connection: Any, goal_id: str, owner: str, kind: str, detail: Mapping[str, Any] | None = None) -> None:
    connection.execute(
        "INSERT INTO goal_events (event_id, goal_id, owner_principal_id, kind, detail_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (new_id("gevt_"), goal_id, owner, kind, json.dumps(dict(detail or {}), sort_keys=True), utc_now()),
    )


def create_goal(store: Any, *, owner: str, project_id: str | None, plan: Mapping[str, Any]) -> str:
    goal_id = new_id("goal_")
    now = utc_now()
    with store.connect() as connection:
        connection.execute(
            "INSERT INTO goals (goal_id, owner_principal_id, title, objective, project_id, model_profile, model, "
            "status, revision, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', 1, ?, ?)",
            (goal_id, owner, plan["title"], plan["objective"], project_id, plan.get("model_profile"),
             plan.get("model"), now, now),
        )
        _write_plan(connection, goal_id, plan)
        record_event(connection, goal_id, owner, "goal_created",
                     {"criteria": len(plan["criteria"]), "steps": len(plan["steps"])})
    return goal_id


def replace_plan(store: Any, *, owner: str, goal_id: str, base_revision: int, plan: Mapping[str, Any]) -> None:
    """Rewrite a draft's plan, only over the revision the owner was looking at."""
    with store.connect() as connection:
        changed = connection.execute(
            "UPDATE goals SET title = ?, objective = ?, model_profile = ?, model = ?, revision = revision + 1, "
            "updated_at = ? WHERE goal_id = ? AND owner_principal_id = ? AND revision = ? AND status = 'draft'",
            (plan["title"], plan["objective"], plan.get("model_profile"), plan.get("model"), utc_now(), goal_id,
             owner, base_revision),
        ).rowcount
        if not changed:
            raise GoalError("goal_revision_stale")
        _write_plan(connection, goal_id, plan)
        record_event(connection, goal_id, owner, "goal_plan_edited",
                     {"criteria": len(plan["criteria"]), "steps": len(plan["steps"])})


def transition(
    connection: Any, *, owner: str, goal_id: str, base_revision: int | None, from_states: Sequence[str],
    to_state: str, reason: str = "", reason_detail: str = "", **fields: Any,
) -> bool:
    """Move a goal between states with compare-and-set; ``False`` when it moved first.

    ``base_revision`` ``None`` is the coordinator's own pass, which checks the
    state it expects but not an owner's view of the plan.
    """
    sets = ["status = ?", "reason = ?", "reason_detail = ?", "revision = revision + 1", "updated_at = ?"]
    values: list[Any] = [to_state, reason, reason_detail, utc_now()]
    for key, value in fields.items():
        sets.append(f"{key} = ?")
        values.append(value)
    where = f"goal_id = ? AND owner_principal_id = ? AND status IN ({','.join('?' * len(from_states))})"
    values.extend([goal_id, owner, *from_states])
    if base_revision is not None:
        where += " AND revision = ?"
        values.append(base_revision)
    return bool(connection.execute(f"UPDATE goals SET {', '.join(sets)} WHERE {where}", values).rowcount)  # noqa: S608 - column names are this module's own


def _loads(raw: Any) -> list[str]:
    try:
        value = json.loads(raw or "[]")
    except ValueError:
        return []
    return [str(v) for v in value] if isinstance(value, list) else []


def get_goal(store: Any, *, owner: str, goal_id: str) -> dict[str, Any] | None:
    with store.connect() as connection:
        row = connection.execute(
            "SELECT * FROM goals WHERE goal_id = ? AND owner_principal_id = ?", (goal_id, owner)
        ).fetchone()
        if row is None:
            return None
        criteria = connection.execute(
            "SELECT * FROM goal_criteria WHERE goal_id = ? ORDER BY position", (goal_id,)
        ).fetchall()
        steps = connection.execute(
            "SELECT * FROM goal_steps WHERE goal_id = ? ORDER BY position", (goal_id,)
        ).fetchall()
        events = connection.execute(
            "SELECT kind, detail_json, created_at FROM goal_events WHERE goal_id = ? AND owner_principal_id = ? "
            "ORDER BY created_at DESC, event_id DESC LIMIT 30",
            (goal_id, owner),
        ).fetchall()
    goal = dict(row)
    goal["criteria"] = [
        {**dict(c), "mandatory": bool(c["mandatory"])} for c in criteria
    ]
    goal["steps"] = [
        {
            **{k: v for k, v in dict(s).items() if k not in {"depends_on_json", "criterion_ids_json"}},
            "depends_on": _loads(s["depends_on_json"]),
            "criterion_ids": _loads(s["criterion_ids_json"]),
        }
        for s in steps
    ]
    goal["events"] = [
        {"kind": str(e["kind"]), "detail": json.loads(e["detail_json"] or "{}"), "created_at": str(e["created_at"])}
        for e in events
    ]
    return goal


def list_goal_ids(store: Any, *, owner: str, archived: bool = False) -> list[str]:
    with store.connect() as connection:
        rows = connection.execute(
            "SELECT goal_id FROM goals WHERE owner_principal_id = ? AND (status = 'archived') = ? "
            "ORDER BY updated_at DESC LIMIT 200",
            (owner, 1 if archived else 0),
        ).fetchall()
    return [str(r["goal_id"]) for r in rows]


def active_goals(store: Any) -> list[tuple[str, str]]:
    """``(owner, goal_id)`` of every goal the coordinator should advance."""
    with store.connect() as connection:
        rows = connection.execute(
            "SELECT owner_principal_id, goal_id FROM goals WHERE status IN ('running', 'waiting')"
        ).fetchall()
    return [(str(r["owner_principal_id"]), str(r["goal_id"])) for r in rows]


def goal_for_task(store: Any, task_id: str) -> tuple[str, str, str] | None:
    """``(owner, goal_id, step_id)`` of the goal step whose task this is."""
    with store.connect() as connection:
        row = connection.execute(
            "SELECT g.owner_principal_id, s.goal_id, s.step_id FROM goal_steps s "
            "JOIN goals g ON g.goal_id = s.goal_id WHERE s.task_id = ?",
            (task_id,),
        ).fetchone()
    return (str(row[0]), str(row[1]), str(row[2])) if row is not None else None


def withhold_session_memory(store: Any, *, session_id: str, owner: str, reason: str) -> None:
    with store.connect() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO session_memory_withholds (session_id, owner_principal_id, reason, created_at) "
            "VALUES (?, ?, ?, ?)",
            (session_id, owner, reason, utc_now()),
        )


def session_memory_withheld(store: Any, session_id: str | None) -> str:
    """Why this conversation's turns recall no personal memory; "" when nothing withholds it."""
    if not session_id:
        return ""
    try:
        with store.connect() as connection:
            row = connection.execute(
                "SELECT reason FROM session_memory_withholds WHERE session_id = ?", (session_id,)
            ).fetchone()
    except Exception:  # noqa: BLE001 - an unreadable marker withholds, it never releases
        return "unreadable"
    return str(row[0]) if row is not None else ""
