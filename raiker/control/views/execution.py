"""Execution environments: where a command runs, and what that boundary was measured to do."""

from __future__ import annotations

from typing import Any, Literal, NotRequired

from typing_extensions import TypedDict

ProbeVerdict = Literal["enforced", "unenforced", "indeterminate"]


class CostEvent(TypedDict):
    event_id: str
    action_id: str
    event_type: Literal["reserved", "reconciled", "released", "provider_snapshot", "provider_unavailable"]
    amount: float
    provider_reference: str | None
    reason: str | None
    recorded_at: str


class CloudCost(TypedDict):
    actual_cost: float
    provider_cost: float
    reserved_cost: float
    committed_cost: float
    remaining_cost: float | None
    reconciliation_status: Literal["not_started", "reserved", "reconciled", "provider_unavailable"]
    history: list[CostEvent]


class ExecutionEnvironmentView(TypedDict):
    """One boundary a command could run in, as measured on this host.

    The container keys are present for a container profile; ``boundary`` and
    ``probe_observations`` for the boundaries a probe measures; ``config`` for
    an owner-configured profile, never with its secrets.
    """

    profile_id: str
    kind: Literal["local", "native", "container", "ssh", "daytona"]
    name: str
    enabled: bool
    configured: bool
    available: bool
    status: str
    selected: bool
    credential_configured: bool
    budget: float | None
    cost: CloudCost | None
    selected_for_commands: bool
    assigned_tools: list[str]
    #: What this boundary was measured or built to do (BUG-194), as a flat map.
    features: dict[str, bool]
    probe_checked_at: str
    availability_reason: str | None
    boundary: NotRequired[str]
    #: ``indeterminate`` proves nothing and must never be rendered as enforcement.
    probe_observations: NotRequired[dict[str, ProbeVerdict]]
    #: Publisher trust for the exact runner; null when the backend does not expose it.
    runner_trust: NotRequired[
        Literal["publisher_verified", "package_relative_integrity", "development_unverified"] | None
    ]
    runtime: NotRequired[Literal["docker", "podman"] | None]
    image: NotRequired[str | None]
    repository_access: NotRequired[Literal["none", "read_only"]]
    writable_output: NotRequired[bool]
    assigned_tool_count: NotRequired[int]
    config: NotRequired[dict[str, Any]]


class ContainerOptions(TypedDict):
    runtimes: list[Literal["docker", "podman"]]
    images: list[str]
    supported_tools: list[str]


class ExecutionEnvironmentsView(TypedDict):
    selected_profile_id: str
    environments: list[ExecutionEnvironmentView]
    container_options: ContainerOptions
