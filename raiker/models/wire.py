# SPDX-License-Identifier: Apache-2.0
"""What the model read models put on the wire (OPT-01 Stage B).

Several model classes keep their own ``to_dict`` because the wire differs from
their fields — a key renamed, a choice nested, a payload withheld. Each of those
methods is declared to return one of these, so the projection is the contract:
``mypy`` checks the dict where it is built, and ``scripts/api_contract.py``
describes the route from it. Nothing here imports a class that imports it.
"""

from __future__ import annotations

from typing import Any, Literal

from typing_extensions import TypedDict

ReadinessState = Literal[
    "not_configured",
    "checking",
    "ready",
    "runtime_missing",
    "runtime_stopped",
    "model_missing",
    "policy_blocked",
    "authentication_failed",
    "quota_exhausted",
    "unreachable",
    "unsupported",
    "stale",
    "configuration_unreadable",
]


class ModelReadinessView(TypedDict):
    """Whether one exact profile and model can answer now, and what it would take."""

    owner_principal_id: str
    profile_id: str
    model: str
    endpoint_fingerprint: str
    state: ReadinessState
    checked_at: str | None
    expires_at: str | None
    summary: str
    reason_code: str
    remediation: str
    evidence: dict[str, Any]
    ready: bool


class DecisionScope(TypedDict):
    surface: str
    project_id: str | None


class SelectedChoice(TypedDict):
    """The owner's choice, and where it came from — most specific first."""

    profile_id: str
    model: str
    source: Literal["surface_default", "global_default", "native_default"]


class EffectiveChoice(TypedDict):
    """The pair that will run, and why it is that one rather than the selection."""

    profile_id: str
    model: str
    reason: Literal["selected", "fallback", "no_ready_candidate"]


class DecisionProblem(TypedDict):
    reason_code: str
    summary: str
    remediation: str


class ModelDecisionView(TypedDict):
    """Which model is selected for a surface, and which one will actually run."""

    scope: DecisionScope
    selected: SelectedChoice
    effective: EffectiveChoice
    ready: bool
    running: bool | None
    problem: DecisionProblem | None
    revision: str


OperationKind = Literal["install", "download", "convert", "deploy", "pull"]
OperationState = Literal["queued", "running", "cancel_requested", "cancelled", "failed", "complete"]


class ModelOperationView(TypedDict):
    """One install, download, conversion, deployment or pull — redacted, with what it allows."""

    operation_id: str
    owner_principal_id: str
    kind: OperationKind
    target: str
    state: OperationState
    phase: str
    progress_bytes: int
    total_bytes: int | None
    progress_percent: int | None
    source_url: str | None
    destination: str | None
    error_code: str | None
    error_detail: str | None
    created_at: str
    updated_at: str
    retryable: bool
    partial_files_present: bool


class PartialFiles(TypedDict):
    """What a confirmed cleanup would delete: the exact paths, and their bytes."""

    path: str | None
    paths: list[str]
    exists: bool
    bytes: int
    file_count: int


class LocalModelView(TypedDict):
    """One model file set found under an approved library root."""

    owner_principal_id: str
    root_path: str
    model_id: str
    name: str
    architecture: str
    quantization: str | None
    primary_path: str
    shard_count: int
    expected_shards: int
    complete: bool
    size_bytes: int
    indexed_at: str
    format: Literal["gguf", "mlx"]


class SpeechRuntimeView(TypedDict):
    """The speech runtime the owner set up, and which one the microphone will use."""

    endpoint: str
    model: str
    configured: bool
    effective: Literal["local", "browser"]
