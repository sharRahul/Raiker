# SPDX-License-Identifier: Apache-2.0
"""Models: readiness, surface defaults and decisions, operations, the library,
Hugging Face, pricing, capacity, usage and connections."""

from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

from raiker.control.views.models import ProviderCatalogueRefreshView
from raiker.models.huggingface import HfSearchResult, HfVariant
from raiker.models.price_sync import SyncResult as PriceSyncResult
from raiker.models.provider_usage import ProviderWeeklyUsage
from raiker.models.setup import SetupState
from raiker.models.wire import (
    LocalModelView,
    ModelDecisionView,
    ModelOperationView,
    ModelReadinessView,
    PartialFiles,
    SpeechRuntimeView,
)


class ModelReadinessList(TypedDict):
    items: list[ModelReadinessView]


class SurfacePick(TypedDict):
    profile_id: str
    model: str


class SurfaceModels(TypedDict):
    """Where each surface's model picker starts — a preference, never readiness."""

    surfaces: dict[str, SurfacePick]


class SurfaceModelSet(TypedDict):
    ok: bool
    surface: str
    profile_id: str
    model: str


class ModelDecisions(TypedDict):
    surfaces: dict[str, ModelDecisionView]


class LocalRuntime(TypedDict):
    """A local model runtime found (or not) on this machine by a PATH lookup."""

    runtime: str
    present: bool
    executable: str | None
    detected_at: str


class LocalRuntimes(TypedDict):
    runtimes: list[LocalRuntime]


class OperationReview(TypedDict):
    """An operation other than an install, shown for review before it is confirmed."""

    kind: str
    target: str
    action: Literal["review_operation"]
    confirmed: bool


class ModelOperations(TypedDict):
    items: list[ModelOperationView]


class OperationCleared(TypedDict):
    ok: bool


class PartialFilesDeleted(PartialFiles):
    ok: bool


class PartialFilesRefused(PartialFiles):
    ok: bool
    reason_code: Literal["no_partial_files"]


class LibraryRoot(TypedDict):
    path: str


class ModelLibraryView(TypedDict):
    roots: list[LibraryRoot]
    models: list[LocalModelView]


class LibraryRootAdded(TypedDict):
    ok: bool
    path: str


class LibraryRescanned(TypedDict):
    ok: bool
    models: list[LocalModelView]


class HuggingFaceCredentialSaved(TypedDict):
    configured: bool


class HuggingFaceUnreachable(TypedDict):
    reason_code: str
    repository_url: str | None


class HuggingFaceDownloadResult(ModelOperationView):
    """The queued download, and where its snapshot and any conversion will land."""

    snapshot_path: str
    conversion_output_path: str


class HuggingFaceSearch(TypedDict):
    items: list[HfSearchResult]


class HuggingFaceTrending(TypedDict):
    """The most-downloaded repositories; an unreachable Hub is an answer here (BUG-296)."""

    items: list[HfSearchResult]
    unreachable: NotRequired[HuggingFaceUnreachable]


class HuggingFaceVariants(TypedDict):
    items: list[HfVariant]


class CapacityHistoryEntry(TypedDict):
    """One recorded change to a model's context capacity."""

    capacity_id: str
    endpoint_identity: str
    context_window_tokens: int | None
    action: str
    reason: str | None
    recorded_by: str
    recorded_at: str


class CapacityRefreshState(TypedDict):
    """When one local profile's capacity was last read from its runtime."""

    profile_id: str
    last_refresh_at: str | None
    next_refresh_at: str
    status: str
    reason_code: str | None


class ModelCapacityEntry(TypedDict):
    profile_id: str
    provider: str
    model: str
    endpoint_identity: str
    context_window_tokens: int | None
    source: str | None
    history: list[CapacityHistoryEntry]


class ModelCapacities(TypedDict):
    ok: bool
    entries: list[ModelCapacityEntry]
    sync: list[CapacityRefreshState]
    refresh_due: bool
    cadence_hours: int
    can_override: bool


class CapacityRefreshOutcome(TypedDict):
    profile_id: str
    status: str
    reason_code: str | None


class CapacitiesRefreshed(TypedDict):
    ok: bool
    profiles: list[CapacityRefreshOutcome]


class CapacitySet(TypedDict):
    ok: bool
    profile_id: str
    model: str
    tokens: int | None


class PricingRefreshed(TypedDict):
    ok: bool
    providers: list[PriceSyncResult]
    changes_written: int


class PriceSet(TypedDict):
    """An owner price recorded, or cleared (``cleared``) back to the published one."""

    ok: bool
    model: str
    cleared: NotRequired[bool]
    input_per_mtok: NotRequired[str]
    output_per_mtok: NotRequired[str]
    cache_write_per_mtok: NotRequired[str | None]
    cache_read_per_mtok: NotRequired[str | None]
    currency: NotRequired[str]


class ModelSelectionSet(TypedDict):
    ok: bool
    profile_id: str
    model: str


class AdvisorSet(TypedDict):
    ok: bool
    advisor_profile_id: str | None


class FallbackSet(TypedDict):
    ok: bool
    fallback_sequence: list[str]


class AvailableModelsSet(TypedDict):
    ok: bool
    profile_id: str
    models: list[str]


class WeeklyUsage(TypedDict):
    window: Literal["rolling_7_days"]
    providers: list[ProviderWeeklyUsage]


class WeeklyBudgetSet(TypedDict):
    ok: bool
    profile_id: str


class CodexStatus(TypedDict):
    """Whether the ChatGPT subscription is connected, offered, signed out or not installed."""

    connection_status: Literal["connected", "available", "signed_out", "codex_missing"]
    plan_type: str | None


class CodexConnected(TypedDict):
    ok: bool
    connection_status: Literal["connected"]
    plan_type: str | None
    connection_configured: bool


class CodexLoginStarted(TypedDict):
    ok: bool
    connection_status: Literal["login_pending"]


class ConnectionSet(TypedDict):
    ok: bool
    connection_configured: bool


class CatalogueRefreshed(TypedDict):
    """One explicit refresh of the connected providers' model lists, provider by provider."""

    providers: list[ProviderCatalogueRefreshView]


class SetupBackupCreated(TypedDict):
    ok: bool
    path: str
    setup: SetupState


class SpeechRuntime(TypedDict):
    runtime: SpeechRuntimeView
    max_audio_bytes: int


class SpeechProbe(TypedDict):
    ok: bool
    reason_code: str | None
    endpoint: str


class Transcript(TypedDict):
    text: str


class ImageReference(TypedDict):
    """A research passage sent with a prompt, with the pages it came from."""

    name: str
    text: str
    sources: list[str]


class ImageGeneration(TypedDict):
    """One generation as the page sees it — metadata only, never the bytes."""

    generation_id: str
    profile_id: str
    provider: str
    model: str
    prompt: str
    size: str
    status: str
    reason_code: str | None
    has_image: bool
    media_type: str | None
    byte_size: int | None
    created_at: str
    source_generation_id: str | None
    kind: Literal["create", "edit", "variation"]
    project_id: str | None
    #: UX-DESIGN-01 — when this was put in Recently deleted; ``None`` in the
    #: gallery.
    deleted_at: str | None
    #: UX-DESIGN-03 — the research this was sent with, as the provider got it.
    references: list[ImageReference]


class ImageGallery(TypedDict):
    sizes: list[str]
    sized_providers: list[str]
    generations: list[ImageGeneration]
    #: UX-DESIGN-01 — Recently deleted, newest deletion first. Never mixed into
    #: ``generations``, so nothing put away is drawn as a version or sibling.
    deleted: list[ImageGeneration]


class ImageLifecycleChanged(TypedDict):
    """A picture put away, brought back, or removed for good."""

    ok: bool
    generation_id: str
    state: Literal["deleted", "restored", "removed"]


class ImagesGenerated(TypedDict):
    """One governed generation request; ``generation_ids`` holds every variation made."""

    ok: bool
    generation_id: str
    generation_ids: list[str]
    provider: str
    model: str
    size: str
    kind: Literal["create", "edit", "variation"]
    source_generation_id: str | None
    byte_size: int


class LanguageMatch(TypedDict):
    offset: int
    length: int
    message: str
    replacements: list[str]
    rule_id: str
    category: str


class LanguageCheck(TypedDict):
    """A grammar check, or the reason no checker could answer."""

    status: Literal["available", "unavailable"]
    reason_code: NotRequired[str]
    matches: list[LanguageMatch]
