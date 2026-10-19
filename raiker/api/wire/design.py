"""DW-01 to DW-11 — what Raiker Design's structured-document routes answer with."""

from __future__ import annotations

from typing import Any, Literal

from typing_extensions import TypedDict


class DesignFramePreset(TypedDict):
    preset: str
    label: str
    width: int
    height: int


class DesignDocumentSummary(TypedDict):
    """One document in a list: what it is and where, never its layers."""

    document_id: str
    title: str
    project_id: str | None
    system_id: str | None
    system_version: int | None
    current_version: int
    content_hash: str
    frame_count: int
    created_at: str
    updated_at: str
    deleted_at: str | None


class DesignDocumentList(TypedDict):
    documents: list[DesignDocumentSummary]
    deleted: list[DesignDocumentSummary]
    presets: list[DesignFramePreset]


class DesignDocumentView(DesignDocumentSummary):
    """One document with its frames and layer tree, at ``current_version``."""

    document: dict[str, Any]
    can_undo: bool
    can_redo: bool


class DesignChangeView(TypedDict):
    """DW-08 — a change written as a new version.

    ``rebased`` is true when the change was made against an older version and
    touched nothing changed since, so it was applied on top rather than refused.
    """

    ok: bool
    version: int
    rebased: bool
    summary: list[str]
    document: DesignDocumentView


class DesignVersionSummary(TypedDict):
    version: int
    actor: str
    kind: str
    summary: str
    scope: list[str]
    operation_count: int
    content_hash: str
    undo_parent: int | None
    redo_target: int | None
    proposal_id: str | None
    created_at: str


class DesignVersionList(TypedDict):
    current_version: int
    versions: list[DesignVersionSummary]


class DesignVersionView(DesignVersionSummary):
    document: dict[str, Any]


class DesignSystemView(TypedDict):
    """DW-06 — one version of a design system."""

    system_id: str
    version: int
    name: str
    source_note: str
    variables: dict[str, Any]
    created_at: str


class DesignSystemList(TypedDict):
    systems: list[DesignSystemView]


class DesignSystemChange(TypedDict):
    frame_id: str
    node_id: str | None
    name: str
    field: str
    before: str | None
    after: str


class DesignSystemMissing(TypedDict):
    frame_id: str
    node_id: str | None
    variable: str


class DesignSystemPreview(TypedDict):
    """DW-06 — what choosing a system would change in this document, before anything is written."""

    system: DesignSystemView | None
    changes: list[DesignSystemChange]
    missing: list[DesignSystemMissing]
    operation_count: int


class DesignValidationFinding(TypedDict):
    frame_id: str | None
    node_id: str | None
    layer: str
    message: str


class DesignValidationCheck(TypedDict):
    check: str
    label: str
    status: Literal["pass", "fail", "unsupported", "unknown"]
    findings: list[DesignValidationFinding]


class DesignValidationView(TypedDict):
    """DW-10 — each check's honest state, at one document version."""

    outcome: Literal["passed", "failed", "partly_checked"]
    validator_version: str
    document_hash: str
    version: int
    checks: list[DesignValidationCheck]


class DesignExportView(TypedDict):
    """DW-11 — one export, pinned to the version and validation it came from."""

    export_id: str
    document_id: str
    version: int
    frame_id: str
    format: str
    settings: dict[str, Any]
    validation_outcome: str
    media_type: str
    sha256: str
    byte_size: int
    created_at: str


class DesignExportList(TypedDict):
    exports: list[DesignExportView]


class DesignProposalOperation(TypedDict):
    index: int
    operation: dict[str, Any]
    status: Literal["valid", "refused"]
    reason_code: str | None
    summary: str
    touched: list[str]


class DesignProposalView(TypedDict):
    """DW-07 — an agent's plan and typed operations, waiting on the owner."""

    proposal_id: str
    document_id: str
    base_version: int
    frame_id: str
    brief: str
    provider: str
    model: str
    plan: dict[str, Any]
    operations: list[DesignProposalOperation]
    status: str
    result: dict[str, Any] | None
    created_at: str
    decided_at: str | None


class DesignProposalList(TypedDict):
    proposals: list[DesignProposalView]


class DesignProposalConflict(TypedDict):
    index: int
    node_ids: list[str]
    changed_in_version: int


class DesignProposalDecision(TypedDict):
    """DW-08 — what accepting or rejecting a proposal did, and what it refused to overwrite."""

    ok: bool
    proposal: DesignProposalView
    applied: list[int]
    conflicts: list[DesignProposalConflict]
    version: int | None


class DesignHandoffRecord(TypedDict):
    """DW-11 — what Build was given: a bounded context document, never authority."""

    handoff_id: str
    document_id: str
    version: int
    frame_ids: list[str]
    target: str
    attachment_id: str
    sha256: str
    created_at: str


class DesignHandoffView(DesignHandoffRecord):
    """A handoff just made, with the attachment Build's composer carries."""

    filename: str
    media_type: str
    byte_size: int


class DesignHandoffList(TypedDict):
    handoffs: list[DesignHandoffRecord]


class DesignAssetUse(TypedDict):
    document_id: str
    title: str
    layers: int


class DesignAssetUsage(TypedDict):
    """DW-05 — which live documents place an image, so removing it is never silent."""

    asset_id: str
    documents: list[DesignAssetUse]
