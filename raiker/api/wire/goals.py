"""PA-D01 / PA-D02 — what the goal and execution-profile routes answer with."""

from __future__ import annotations

from typing import Any

from typing_extensions import TypedDict


class ExecutionProfileView(TypedDict):
    profile_id: str
    version: int
    name: str
    template: str
    allow_local: bool
    allow_hosted: bool
    allowed_providers: list[str]
    memory_to_hosted: bool
    max_step_runs: int
    max_cost_usd: float | None
    created_at: str


class ExecutionProfileTemplate(TypedDict):
    template: str
    name: str
    summary: str
    allow_local: bool
    allow_hosted: bool
    memory_to_hosted: bool


class ExecutionProfileBinding(TypedDict):
    project_id: str
    profile_id: str


class ExecutionProfileList(TypedDict):
    """Every profile at its latest version, the templates, and what is bound where.

    ``active_profile_id`` is what new goals outside a project-bound project
    inherit; ``None`` means Settings has not chosen one, and a goal cannot be
    accepted until it does.
    """

    profiles: list[ExecutionProfileView]
    templates: list[ExecutionProfileTemplate]
    active_profile_id: str | None
    project_bindings: list[ExecutionProfileBinding]


class ExecutionProfileChanged(TypedDict):
    """A Settings change, and how many running goals it paused at a safe boundary."""

    ok: bool
    profile: ExecutionProfileView | None
    goals_paused: int


class GoalCriterionView(TypedDict):
    criterion_id: str
    text: str
    mandatory: bool
    validator: str
    #: ``steps_finished`` (every linked step finished) or ``owner_confirmed``.
    evidence_kind: str | None
    evidence_ref: str | None
    evidence_note: str | None
    verified_at: str | None


class GoalStepView(TypedDict):
    step_id: str
    title: str
    instruction: str
    surface: str
    depends_on: list[str]
    criterion_ids: list[str]
    state: str
    reason: str
    task_id: str | None
    task_status: str | None
    task_summary: str | None


class GoalBudget(TypedDict):
    max_step_runs: int | None
    step_runs: int
    max_cost_usd: float | None
    #: Reconciled from the usage ledger for the goal's own step conversations.
    spent_usd: float
    unpriced_models: list[str]


class GoalEvent(TypedDict):
    kind: str
    detail: dict[str, Any]
    created_at: str


class GoalView(TypedDict):
    """One goal: its plan, evidence, budget, profile and the actions its state allows."""

    goal_id: str
    title: str
    objective: str
    project_id: str | None
    #: The model every step's task runs on; judged, with the owner's fallbacks, by the profile.
    model_profile: str | None
    model: str | None
    status: str
    reason: str
    reason_text: str
    reason_detail: str
    revision: int
    allowed_actions: list[str]
    created_at: str
    updated_at: str
    accepted_at: str | None
    settled_at: str | None
    criteria: list[GoalCriterionView]
    steps: list[GoalStepView]
    profile: ExecutionProfileView | None
    profile_current: bool
    profile_source: str
    budget: GoalBudget
    providers_used: list[str]
    providers_outside_profile: list[str]
    events: list[GoalEvent]


class GoalList(TypedDict):
    goals: list[GoalView]
    archived: list[GoalView]
    #: The profile a new goal outside a bound project would be accepted under.
    active_profile: ExecutionProfileView | None


class GoalStopped(TypedDict):
    ok: bool
    steps_done: int
    steps_stopped: int
    tasks_stopped: int
    goal: GoalView
