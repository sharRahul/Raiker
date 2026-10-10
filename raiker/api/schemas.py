from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from raiker.contracts.views import json_ready


class StrictRequest(BaseModel):
    """Every JSON request body the API validates with Pydantic.

    An unknown field is refused rather than ignored, so a client that misspells
    a field — or sends one this route never reads — is told instead of believing
    it was honoured. Inherited, not repeated: a new request model gets this
    posture by naming its base (OPT-03), and ``test_api_request_models`` fails a
    ``BaseModel`` request under ``raiker/api`` that does not.

    The ``@dataclass`` bodies below (prompts, interrupts, runtime modes and
    capability controls) keep FastAPI's ignore-unknown behaviour on purpose:
    they are the documented REST contract for external single-user clients, and
    a client written against an older revision must not start failing because
    it sends a field this one dropped.
    """

    model_config = ConfigDict(extra="forbid")


class StrictModelRequest(StrictRequest):
    """A strict request with ``model_*`` fields, which Pydantic reserves by default."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())


class LocalModelDeployRequest(StrictRequest):
    profile_id: str | None = None


@dataclass
class ActivateRuntimeModeRequest:
    mode_name: str
    reason: str = ""
    as_principal: str | None = None


@dataclass
class DisableRuntimeModeRequest:
    reason: str = ""
    as_principal: str | None = None


@dataclass
class SetCapabilityStateRequest:
    target_state: str
    reason: str = ""
    as_principal: str | None = None
    # Tier-2 step-up: forwarded to the existing activation check; no new authority is granted.
    confirmation_token: str | None = None
    # §13.2 item 6 — the state the page showed. A save from a page that is out
    # of date is refused 409 `capability_conflict` instead of overwriting.
    expected_state: str | None = None


@dataclass
class RecordThreatModelAckRequest:
    # Human acknowledgement that the capability's threat model was reviewed. The
    # reason is stored as the acknowledgement's doc reference. Owner/gate-manager
    # only; only accepted for capabilities that actually require an ack.
    reason: str = ""
    as_principal: str | None = None


@dataclass
class DisableCapabilityRequest:
    reason: str = ""
    as_principal: str | None = None
    expected_state: str | None = None


@dataclass
class SetCapabilityDecisionModeRequest:
    reason: str = ""
    as_principal: str | None = None
    # §13.2 item 6 — the mode the page showed. If another tab or device changed
    # it since, the change is refused 409 `capability_conflict`: a stale page
    # must not silently loosen (or undo a tightening of) a permission.
    expected_mode: str | None = None


@dataclass
class CreateTelemetryDestinationRequest:
    # Backlog #18 — where governed events may be exported to. `header_ref` names
    # the environment variable an `Authorization` value lives in; the value
    # itself is never accepted here, so a credential cannot be typed into a form
    # and stored. `include_content` is the owner's explicit opt-in to the
    # redacted payload; without it a record carries identifiers and a type.
    name: str
    endpoint_url: str
    header_ref: str = ""
    include_content: bool = False


@dataclass
class ImageReferenceRequest:
    """One research passage the owner consented to send with an image prompt."""

    name: str
    text: str
    sources: list[str] = field(default_factory=list)


@dataclass
class GenerateImageRequest:
    # What an owner chooses. Everything else — the endpoint, the credential —
    # comes from the profile they already configured, because a request is a
    # thing a model can propose and neither of those may be proposed.
    #
    # `model` is a choice rather than a proposal: the executor accepts it only
    # if the profile declares it for images, and falls back to the profile's
    # default when it is empty. Without that check this field would be a
    # free-text string forwarded to a provider unread.
    #
    # BUG-277 — `source_generation_id` is what makes "edit this" possible, and
    # it is the one field here that names something the owner already has. It is
    # resolved owner-scoped in the executor rather than trusted: a generation id
    # is short and guessable in shape, and an id belonging to another owner
    # answers exactly as one that was never issued.
    profile_id: str
    prompt: str
    size: str = "1024x1024"
    model: str = ""
    source_generation_id: str = ""
    variations: int = 1
    project_id: str = ""
    # UX-DESIGN-03 — research the owner chose to send with the prompt, each a
    # named passage with the pages it came from. Validated and bounded again in
    # the executor: this is an action argument, so it is checked where it is
    # used rather than trusted because the page built it.
    references: list[ImageReferenceRequest] = field(default_factory=list)


class RevertImageRequest(StrictRequest):
    # DEC-07 step 4 — the earlier version, in the head's own history, whose
    # picture comes back as a new version.
    to: str


@dataclass
class TelemetryCadenceRequest:
    # BUG-276 — how often this destination is delivered to. `off` is the shipped
    # default and means what the card said before this field existed: on demand
    # only. Every other value is a cadence the task scheduler already honours.
    cadence: str


@dataclass
class CreateStandingGrantRequest:
    # Scoped standing approval grant (F3). Creation is a critical, human-decided
    # action; the authority enforces the human-only + sub-critical ceiling.
    action_type: str
    risk_ceiling: str
    tool_name: str = ""
    scope_pattern: str = "*"
    reason: str = ""
    ttl_days: float | None = None
    as_principal: str | None = None


@dataclass
class AuthSessionRequest:
    # Optional explicit principal; defaults to the resolved local owner. Local-only, human-only.
    as_principal: str | None = None


class RegisterRequest(StrictRequest):
    username: str
    password: str


class SessionCommandGrantRequest(StrictRequest):
    commands: list[list[str]]
    timeout_seconds: int = 120
    ttl_minutes: int = 120


class AnswerOwnerQuestionRequest(StrictRequest):
    """The owner's answer to a mid-turn question (ADD-22).

    `answers` is keyed by the exact question text and each value is the chosen
    option label, or a list of them for a multi-select. `response` is the owner
    replying in their own words instead of picking; when it is set the answers
    map is ignored, because they said something the options did not offer.
    """

    answers: dict[str, Any] = {}
    response: str | None = None


class CompactConversationRequest(StrictRequest):
    through_turn_id: str


class LoginRequest(StrictRequest):
    username: str
    password: str
    device_label: str | None = None


class MfaVerifyRequest(StrictRequest):
    ticket: str
    code: str


class MfaCodeRequest(StrictRequest):
    code: str


class ElevateRequest(StrictRequest):
    password: str | None = None
    mfa_code: str | None = None


class ChangePasswordRequest(StrictRequest):
    old_password: str
    new_password: str


class PasswordRecoveryBeginRequest(StrictRequest):
    username: str


class PasswordRecoveryCompleteRequest(StrictRequest):
    ticket: str
    code: str
    new_password: str


class VaultKeyRequest(StrictRequest):
    key: str
    mfa_code: str | None = None


class SettingsRequest(StrictRequest):
    settings: dict[str, Any]
    # 13.2 #6 — the revision the page read, and what each key it changed held
    # then. Omitted by an older client, which keeps the whole-document write.
    expected_revision: str | None = None
    base: dict[str, Any] | None = None


class ComposerApprovalModeRequest(StrictRequest):
    approval_mode: str


class SpeechRuntimeRequest(StrictModelRequest):
    """The local transcription runtime dictation should use, if any (BUG-256).

    Both fields are optional so a caller can set the address without restating
    the model, which is the common case: most transcription servers serve one.
    """

    endpoint: str | None = None
    model: str | None = None


class TaskCreateRequest(StrictModelRequest):
    title: str
    description: str = ""
    priority: str | None = None
    scheduled_at: str | None = None
    recurrence: str | None = None
    reminder_at: str | None = None
    parent_task_id: str | None = None
    # Project-scoped schedules: create this task under a specific project. When
    # omitted the active project is used, so a schedule created inside a project
    # stays scoped to it.
    project_id: str | None = None
    model_profile: str | None = None
    model: str | None = None
    # Backlog #23 — the working method this task's cycles run under. A `build`
    # task needs a project, and is refused with `build_task_requires_project`
    # rather than accepted and quietly run as Chat.
    surface: Literal["chat", "build", "design"] = "chat"
    attachments: list[dict[str, Any]] | None = None
    # UX-TASK-02 — a repeating schedule's terms: the IANA zone it was composed
    # in, the last instant it may run, and what a missed slot does. Refused on a
    # task that does not repeat, rather than stored and never read.
    timezone: str | None = None
    run_until: str | None = None
    missed_runs: Literal["run_once", "skip"] | None = None
    # DEC-12 step 6 — the longest one run may take, in minutes. Omitted is the
    # default limit, never "no limit".
    max_run_minutes: int | None = Field(default=None, ge=1, le=720)


class TaskRunLimitRequest(StrictModelRequest):
    # DEC-12 step 6 — null restores the default limit.
    max_run_minutes: int | None = Field(default=None, ge=1, le=720)
    # The most tool calls one run may make; null removes the routine's own
    # limit. Left out, the stored limit is unchanged.
    max_tool_calls: int | None = Field(default=None, ge=1, le=1000)
    # The most one run may cost, in US dollars; null removes it, left out
    # leaves it unchanged.
    max_run_cost_usd: float | None = Field(default=None, ge=0.01, le=1000)


class SetModelSelectionRequest(StrictModelRequest):
    # Persist the operator's model selection: a profile id plus, for providers
    # that serve several models (or ship a placeholder), the concrete model.
    # The strict base rejects unknown fields.

    profile_id: str
    model: str | None = None


class ModelReadinessCheckRequest(StrictModelRequest):
    profile_id: str
    model: str


class SurfaceModelDefaultRequest(StrictModelRequest):
    """Where one work surface's model picker should start.

    An empty ``profile_id`` clears the surface, returning it to the global model.
    """

    surface: str
    profile_id: str = ""
    model: str = ""


class ModelSetupUpdateRequest(StrictModelRequest):
    status: Literal["required", "in_progress", "skipped", "complete"]
    step: Literal["choose_path", "provider", "model", "review", "ready"]
    path: Literal["provider", "ollama", "lm_studio", "local_gguf", "hugging_face"] | None = None
    selected_profile_id: str | None = None
    selected_model: str | None = None


class SetupUpdateRequest(StrictModelRequest):
    status: Literal["required", "in_progress", "skipped", "complete"]
    # `welcome` is where first launch now starts; `account` and `backup` stay
    # accepted because an instance part-way through the previous wizard has one
    # of them stored, and a stored row must still round-trip.
    stage: Literal["welcome", "account", "model", "privacy", "backup", "finish"]
    selected_profile_id: str | None = None
    selected_model: str | None = None
    model_deferred: bool = False
    privacy_mode: Literal["local_first", "balanced"] | None = None
    backup_mode: Literal["later", "local"] = "later"
    backup_target: str | None = None
    background_service_enabled: bool = False


class SetupBackupRequest(StrictRequest):
    target: str


class ModelOperationRequestBody(StrictModelRequest):
    kind: Literal["install", "download", "convert", "deploy", "pull"]
    target: str
    confirmed: bool = False
    source_url: str | None = None
    destination: str | None = None


class ModelLibraryRootRequest(StrictRequest):
    path: str


class HuggingFaceCredentialRequest(StrictRequest):
    token: str


class HuggingFaceSelectionRequest(StrictRequest):
    repo_id: str
    revision: str
    files: list[str]
    destination: str | None = None
    confirmed: bool = False


class ModelConversionRequestBody(StrictRequest):
    source: str
    output: str
    revision: str
    quantization: Literal["Q4_K_M", "Q5_K_M", "Q6_K", "Q8_0"]
    confirmed: bool = False


class OllamaPullRequestBody(StrictRequest):
    model: str
    confirmed: bool = False


class ExportSessionRequest(StrictRequest):
    """Which rendering of a conversation transcript to produce (BUG-22).

    The format is the whole request: scope comes from the authenticated session
    and the session id in the path, never from the body, so an export cannot be
    widened by what a caller asks for.
    """

    format: str = "html"


class ConversationBranchRequest(StrictRequest):
    """A title for the branch, and nothing else (GAP-CHAT C14).

    The checkpoint is in the path and the owner comes from the authenticated
    session, so the only thing a caller may supply is what to call the new
    conversation. An empty title lets the service derive one from the
    checkpoint's own summary rather than accepting a caller-chosen default.
    """

    title: str = ""


class ModelPriceRequest(StrictModelRequest):
    """An administrator's price override for one model, per million tokens.

    Both input and output null clears the override and returns the model to the
    provider-published or documented list price. Rates are strings so a decimal
    price survives the round trip without binary float drift.

    Cache-write and cache-read are separate optional components (BUG-21): a
    provider bills them independently of input, and an omitted one stays unset
    rather than being inferred. ``effective_from`` dates the row so a correction
    can be recorded as of when it actually applied, and ``reason`` is kept with
    the row so an override is never anonymous.
    """

    model: str
    input_per_mtok: str | None = None
    output_per_mtok: str | None = None
    cache_write_per_mtok: str | None = None
    cache_read_per_mtok: str | None = None
    currency: str | None = None
    effective_from: str | None = None
    reason: str | None = None


class ModelConnectionRequest(StrictRequest):
    """Encrypted per-user endpoint/key data for one model profile."""

    endpoint: str | None = None
    api_key: str | None = None
    # OpenAI and Anthropic expose organization usage only to separate admin
    # credentials. It is optional, encrypted with the connection, and never
    # substituted for the inference key.
    admin_api_key: str | None = None
    # BUG-274 — an identity-linked key acts inside one workspace and the
    # provider will not accept it without the id. Not a credential: it names
    # where the key acts, and it is stored beside the key so the pair travels
    # together.
    workspace_id: str | None = None


class ModelCatalogueRefreshRequest(StrictRequest):
    """An owner-requested refresh of known, connected provider catalogues."""

    profile_ids: list[str] | None = None


class AvailableModelsRequest(StrictRequest):
    """Which of one provider's models stay offered in every model picker."""

    models: list[str]


class SpendLimitRequest(StrictRequest):
    """DEC-24 step 2 — the owner's 24-hour spending limit in US dollars; null clears it."""

    limit_usd: float | None = None


class ModelWeeklyBudgetRequest(StrictRequest):
    """Owner-defined advisory budget; null clears it."""

    token_budget: int | None = None


class SetModelAdvisorRequest(StrictRequest):
    # Persist (or clear, with null/empty) the user-owned advisor model profile.
    # The strict base rejects unknown fields.

    profile_id: str | None = None


class UploadAttachmentRequest(StrictRequest):
    # One base64-encoded image upload for the governed attachment store.
    # Validation is fail-closed server-side (media-type allowlist, size cap,
    # magic-byte sniff); the strict base rejects unknown fields.

    filename: str
    media_type: str
    data_base64: str


class UploadSkillRequest(StrictRequest):
    """One base64-encoded ``SKILL.md`` or ``*.skill`` upload.

    Validation is fail-closed server-side (extension allowlist, size caps,
    frontmatter contract, archive-member safety); the strict base rejects
    unknown fields.
    """

    filename: str
    data_base64: str


class SkillUrlRequest(StrictRequest):
    """A published skill's URL, to verify or to import."""

    url: str


class BuildSkillRequest(StrictRequest):
    """A skill Raiker authored: the name, the trigger description, the body."""

    name: str
    description: str
    body: str
    command_trigger: str | None = None


class RenameSkillRequest(StrictRequest):
    name: str


class SetSkillActiveRequest(StrictRequest):
    active: bool


class SetSkillCommandRequest(StrictRequest):
    command_trigger: str | None = None


class BrainSourceRequest(StrictRequest):
    """One location inside the Knowledge Map's boundary.

    Either a scoped source path (``<root_id>/<relative>``) for the source
    endpoints, or an absolute folder path for the grant endpoint.
    """

    path: str


class BrainSourceUploadRequest(StrictRequest):
    """A file the owner chose from their computer, to be *copied* into Raiker.

    ``store_copy`` is the permission, and it has no default: an upload duplicates
    the file into the workspace, which is exactly the thing that must not happen
    because a file picker was opened. A request without an explicit true is
    refused rather than treated as consent.
    """

    filename: str
    content_base64: str
    store_copy: bool


class ConnectCodeRepoRequest(StrictRequest):
    """Reference a repository from the Build workspace.

    ``kind="local"`` needs ``path`` — a folder already inside this Raiker
    workspace; anything resolving outside it is refused server-side.
    ``kind="github"`` needs ``owner`` and ``repo`` and performs no network call:
    it records the coordinate, and reads still run through the brokered
    ``github_read`` tool under the ``connector_github_runtime`` gate.
    """

    kind: Literal["local", "github"]
    path: str | None = None
    owner: str | None = None
    repo: str | None = None
    branch: str | None = None


class SelectCodeRepoRequest(StrictRequest):
    """Point the Build workspace at one repository, or at none with ``null``."""

    repo_id: str | None = None


class InstanceCreateRequest(StrictRequest):
    """Name and optional first account for a locally isolated Raiker instance."""

    name: str
    username: str | None = None
    password: str | None = None


class CreateProjectRequest(StrictRequest):
    # Create a named project (web-app task 5). The root subpath is derived
    # server-side from the name and contained inside the workspace — the client
    # never supplies a path. The strict base rejects unknown fields.
    # parent_id (optional) creates a nested project under the given parent.
    # attach_path is the one path a client may send, and only because the owner
    # is naming a folder they already have: the server validates it, records it
    # as a grant, and refuses one already inside the workspace.

    name: str
    parent_id: str | None = None
    attach_path: str | None = None
    attach_writable: bool = True


class SelectProjectRequest(StrictRequest):
    # Set (or clear, with null/empty) the active project. Selecting a project
    # grants nothing — it is an organizing scope only.

    project_id: str | None = None


class SaveProjectContextRequest(StrictRequest):
    instructions: str = ""
    attachment_ids: list[str] = []
    # ``memory_enabled`` remains accepted for older clients. New clients send
    # a tri-state override so child folders can inherit their nearest ancestor.
    memory_enabled: bool | None = None
    memory_mode: Literal["inherit", "enabled", "disabled"] | None = None
    # §13.2 item 6 — the context revision the editor read; 409 `project_conflict`
    # when it was saved elsewhere since. Omitted by older clients.
    expected_revision: str | None = None


class MoveProjectRequest(StrictRequest):
    parent_id: str | None = None
    # §13.2 item 6 — the project's placement revision as the tree showed it.
    expected_revision: str | None = None


class SetSessionPinnedRequest(StrictRequest):
    # Pin (or unpin) a session. Pinning is an organizing label only — it grants
    # nothing. The strict base rejects unknown fields.

    pinned: bool


class AttachProjectFolderRequest(StrictRequest):
    """A folder of the owner's to put behind a project, and whether Raiker may write to it."""

    path: str
    writable: bool = True


class BulkDeleteSessionsRequest(StrictRequest):
    session_ids: list[str]


class SetSessionProjectRequest(StrictRequest):
    # Move a chat into a project, or out of every project with a null
    # project_id. A project is an organizing scope — the move grants nothing
    # and only changes the bounded context the chat receives.
    # The strict base rejects unknown fields.

    project_id: str | None = None


class RenameSessionRequest(StrictRequest):
    # Rename one session. The title is an organizing label only — it grants
    # nothing. The server normalizes (trim, collapse whitespace, length cap) and
    # rejects invalid input. The strict base rejects unknown fields.

    title: str


class CreateMcpServerRequest(StrictRequest):
    # Build a local stdio MCP server from a reviewed template (Control Deck
    # task 4b). Both fields are validated/normalized server-side; the actual
    # write runs through the governed mcp_builder_runtime capability.

    name: str
    template: str


class RenameMcpServerRequest(StrictRequest):
    # Rename one owner-scoped MCP server profile. The server normalizes the name
    # and rejects a clash with the caller's other servers.

    name: str
    # §13.2 item 6 — the name the page showed. Renamed elsewhere since, the
    # answer is 409 `mcp_server_conflict` and nothing changes.
    expected_name: str | None = None


class CreateRemoteMcpServerRequest(StrictRequest):
    # Add a remote (HTTP) MCP connection (monitored MCP connections, Phase A).
    # `endpoint_url` is the owner-added server URL; `auth_ref` optionally names
    # the env var holding the owner token (never the token itself).

    name: str
    endpoint_url: str
    auth_ref: str | None = None


class ContainMcpServerRequest(StrictRequest):
    # Optional redacted reason for a pause/kill of a monitored MCP connection
    # (Phase C). The reason is human-readable copy shown back to the owner — it
    # must never carry a payload or token. The strict base rejects unknown fields.

    reason: str | None = None


class ApproveMcpToolsRequest(StrictRequest):
    # DEC-15 step 10 — the held tools the owner accepts, by name. Only names
    # the server offers and holds are accepted; anything else is ignored.
    tools: list[str]
    # §13.2 item 6 — the fingerprint of each declaration the page showed. When
    # a named tool's declaration has changed since, nothing is accepted and the
    # answer is 409 `mcp_tool_changed`. Older clients that send none accept the
    # tools as declared now, as before.
    fingerprints: dict[str, str] | None = None


class AcknowledgeHeldNotificationsRequest(StrictRequest):
    # DEC-21a — the held notices the end-of-interval summary listed. Only the
    # owner's own rows that quiet hours actually held are changed.
    notification_ids: list[str]


class BreachCheckRequest(StrictRequest):
    password: str
    enabled: bool = False


class SetSessionTagsRequest(StrictRequest):
    # Replace the tag set for one session. Tags are organizing labels only —
    # they grant nothing. The server normalizes (trim, lowercase, dedupe,
    # length/count caps) and rejects invalid input. The strict base rejects
    # unknown fields.

    tags: list[str]


class SetModelFallbackRequest(StrictRequest):
    # Ordered list of model profile ids to try (in order) when the selected
    # provider is unavailable. The strict base rejects unknown fields.

    profile_ids: list[str]


@dataclass
class PromptRequest:
    text: str
    # Client-reported input provenance only. The server can constrain this
    # label but cannot prove how a REST or web client produced the text.
    input_mode: Literal["typed", "dictated", "mixed"] = "typed"
    # Which composer sent this prompt. It selects the operating protocol the
    # turn runs under — Build gets the engineering protocol, Design the research
    # one, Chat neither — and grants nothing: capabilities, gates and approvals
    # are identical whichever it is. It must name every surface in
    # `PROMPT_SURFACES`; a stale list here refused every Design research turn.
    # Defaults to "chat" so an external REST client that has never heard of the
    # field gets the conservative surface rather than the coding one.
    surface: Literal["chat", "build", "design"] = "chat"
    # The project this turn may retrieve inside. Required by "build" and
    # rejected for "chat", because the two surfaces have genuinely different
    # boundaries and a request that leaves it to the server to guess is a
    # request whose boundary nobody stated. It is sent explicitly on every turn
    # rather than read from the account's active-project preference, so what the
    # owner selected in Build is what the backend enforces.
    project_id: str | None = None
    session_id: str | None = None
    planning_mode: str | None = None
    approval_mode: str | None = None
    model_profile: str | None = None
    # Optional concrete model for the chosen profile (per-turn only; provider
    # policy is still enforced downstream).
    model: str | None = None
    # Per-turn only; the runtime validates it against the selected model's
    # declared capabilities and does not persist it as a global selection.
    reasoning_effort: str | None = None
    max_tool_calls: int | None = None
    # BUG-70 — a turn-scoped capability posture (Build's Plan / Edit chips).
    # Only `ask` and `deny` are accepted, so the turn can tighten itself and can
    # never grant itself authority; the owner's standing decision modes are not
    # touched. Validated in PromptOptions, which is where an invalid value fails.
    capability_modes: dict[str, str] | None = None
    # Optional attachments for this prompt:
    #   {"type": "path", "path": "<workspace-relative path>"} — resolved through
    #     the workspace-scoped filesystem layer (outside the workspace fails
    #     closed), included as bounded, untrusted-labelled context items;
    #   {"type": "image", "attachment_id": "att_…"} — an image previously
    #     uploaded via POST /api/attachments, delivered as an image block only
    #     when the turn's model profile supports vision (withheld otherwise);
    #   {"type": "document", "attachment_id": "att_…"} — a text document
    #     previously uploaded via POST /api/attachments; its extracted text is
    #     folded into context as a bounded, untrusted-labelled item.
    # Unknown shapes are rejected before a turn starts.
    attachments: list[dict[str, Any]] | None = None
    # Origin of the prompt: the bundled SPA sends "web_ui"; external single-user
    # REST clients (other machines/UIs) send "rest". Both land in the same
    # session when they share session_id (Phase 8 same-session gate).
    client_type: str | None = None


class PairChannelRequest(StrictRequest):
    """Pair one connector profile. Paired is not enabled and not trusted."""

    connector_id: str
    display_name: str | None = None
    #: Sender identifiers the inbound receiver will accept. Required by profiles
    #: that declare `requires_sender_allowlist`, which is what turns that
    #: declaration into enforcement rather than documentation.
    senders: list[str] | None = None


class ChannelEnabledRequest(StrictRequest):
    enabled: bool
    # §13.2 item 6 — the pairing revision the page read; a pairing changed
    # since is refused 409 `channel_conflict`. Omitted by older clients.
    expected_revision: str | None = None


class ChannelPausedRequest(StrictRequest):
    """DEC-14 step 10 — pause or resume one paired channel."""

    paused: bool
    expected_revision: str | None = None


class ChannelSendersRequest(StrictRequest):
    senders: list[str]
    # §13.2 item 6 — the pairing revision the page read; a pairing changed
    # since is refused 409 `channel_conflict`. Omitted by older clients.
    expected_revision: str | None = None


class ChannelRoutingRequest(StrictRequest):
    """Owner-selected route. An inbound payload cannot override these fields."""

    routing_mode: Literal["record_only", "new_turn", "side_question", "interrupt"]
    target_session_id: str | None = None
    owner_sender_id: str | None = None
    approval_relay_enabled: bool = False
    # §13.2 item 6 — the pairing revision the page read; a pairing changed
    # since is refused 409 `channel_conflict`. Omitted by older clients.
    expected_revision: str | None = None


class ChannelTestDeliveryRequest(StrictRequest):
    """One test delivery through the governed outbound path.

    No destination: a test goes where the channel delivers (UX-MSG-04).
    """

    connector_id: str
    text: str = "Raiker test delivery."


class ChannelDestinationRequest(StrictRequest):
    """Bind, or with ``None`` clear, a webhook channel's delivery URL."""

    delivery_url: str | None = None
    # §13.2 item 6 — the pairing revision the page read; a pairing changed
    # since is refused 409 `channel_conflict`. Omitted by older clients.
    expected_revision: str | None = None



class InboundChannelMessage(StrictRequest):
    # Inbound channel payload. Always treated as untrusted; never executed.

    sender_id: str
    text: str = ""


class ChannelApprovalResponse(StrictRequest):
    """One exact, single-use response to a pending relayed approval."""

    sender_id: str
    relay_id: str
    action_id: str
    approve: bool
    reason: str = ""


@dataclass
class InterruptRequest:
    session_id: str
    task_id: str | None = None
    all: bool = False
    action_type: str = "cancel"
    reason: str = "user requested stop"
    steer_text: str | None = None


class ResolveApprovalRequest(StrictRequest):
    # The strict base rejects unknown request fields (e.g. an attempt to smuggle an edited payload).

    approve: bool
    reason: str
    # B14 — the hunks of a proposed change the owner accepted, when they accepted
    # only some. `None` means the whole change set, which is what every approval
    # meant before this existed.
    #
    # These are *positions* in the approved diff ("<file index>:<hunk index>"),
    # never content, so this field cannot carry an edited payload — which is what
    # the strict base refusing unknown fields exists to prevent. The server validates every id
    # against the approval's own patch and refuses the decision if one names no
    # hunk in it.
    accepted_hunks: list[str] | None = None


class ReplaceApprovalRequest(StrictRequest):
    """BUG-271 — the reviewer corrected a line, so this is a *different action*.

    Deliberately not a field on :class:`ResolveApprovalRequest`. That model refuses
    unknown fields precisely so an edited payload cannot arrive on a
    decision, and relaxing it would let the relay execute bytes no human read.
    An edit is submitted as a fresh proposal instead: it gets its own preview,
    its own immutable-intent hash and its own approval, and the approval it
    replaces resolves as denied with the replacement named — so the audit trail
    says what happened rather than showing an amendment.
    """

    #: The reviewer's own unified diff. It replaces the proposed one entirely;
    #: nothing from the original patch is merged into it.
    patch: str
    #: Why the proposed change was not taken as offered. Recorded on the denial.
    reason: str = ""


class ApprovalDecisionRequest(StrictRequest):
    # Explicit allow/deny endpoints only accept an optional human reason; no payload edits.

    reason: str = ""


def serialize_dto(dto: Any) -> Any:
    if hasattr(dto, "to_dict"):
        return dto.to_dict()
    if isinstance(dto, (list, tuple)):
        return [serialize_dto(item) for item in dto]
    # A declared body (a TypedDict) may carry views; each is projected the way a
    # view's own nested fields are, so the wire never depends on who built it.
    return json_ready(dict(dto))
