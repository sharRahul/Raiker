from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


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


@dataclass
class SetCapabilityDecisionModeRequest:
    reason: str = ""
    as_principal: str | None = None


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


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str
    password: str


class SessionCommandGrantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    commands: list[list[str]]
    timeout_seconds: int = 120
    ttl_minutes: int = 120


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str
    password: str
    device_label: str | None = None


class MfaVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket: str
    code: str


class MfaCodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str


class ElevateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str | None = None
    mfa_code: str | None = None


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    old_password: str
    new_password: str


class PasswordRecoveryBeginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str


class PasswordRecoveryCompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket: str
    code: str
    new_password: str


class VaultKeyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    mfa_code: str | None = None


class SettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    settings: dict[str, Any]


class ComposerApprovalModeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approval_mode: str


class TaskCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())
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
    attachments: list[dict[str, Any]] | None = None


class SetModelSelectionRequest(BaseModel):
    # Persist the operator's model selection: a profile id plus, for providers
    # that serve several models (or ship a placeholder), the concrete model.
    # extra="forbid" rejects unknown fields.
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    profile_id: str
    model: str | None = None


class ModelReadinessCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    profile_id: str
    model: str


class SurfaceModelDefaultRequest(BaseModel):
    """Where one work surface's model picker should start.

    An empty ``profile_id`` clears the surface, returning it to the global model.
    """

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    surface: str
    profile_id: str = ""
    model: str = ""


class ModelSetupUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    status: Literal["required", "in_progress", "skipped", "complete"]
    step: Literal["choose_path", "provider", "model", "review", "ready"]
    path: Literal["provider", "ollama", "lm_studio", "local_gguf", "hugging_face"] | None = None
    selected_profile_id: str | None = None
    selected_model: str | None = None


class SetupUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    status: Literal["required", "in_progress", "skipped", "complete"]
    stage: Literal["account", "model", "privacy", "backup", "finish"]
    selected_profile_id: str | None = None
    selected_model: str | None = None
    model_deferred: bool = False
    privacy_mode: Literal["local_first", "balanced"] | None = None
    backup_mode: Literal["later", "local"] = "later"
    backup_target: str | None = None
    background_service_enabled: bool = False


class SetupBackupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str


class ModelOperationRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    kind: Literal["install", "download", "convert", "deploy", "pull"]
    target: str
    confirmed: bool = False
    source_url: str | None = None
    destination: str | None = None


class ModelLibraryRootRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str


class HuggingFaceCredentialRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str


class HuggingFaceSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repo_id: str
    revision: str
    files: list[str]
    destination: str | None = None
    confirmed: bool = False


class ModelConversionRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    output: str
    revision: str
    quantization: Literal["Q4_K_M", "Q5_K_M", "Q6_K", "Q8_0"]
    confirmed: bool = False


class OllamaPullRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str
    confirmed: bool = False


class ExportSessionRequest(BaseModel):
    """Which rendering of a conversation transcript to produce (BUG-22).

    The format is the whole request: scope comes from the authenticated session
    and the session id in the path, never from the body, so an export cannot be
    widened by what a caller asks for.
    """

    model_config = ConfigDict(extra="forbid")

    format: str = "html"


class ConversationBranchRequest(BaseModel):
    """A title for the branch, and nothing else (GAP-CHAT C14).

    The checkpoint is in the path and the owner comes from the authenticated
    session, so the only thing a caller may supply is what to call the new
    conversation. An empty title lets the service derive one from the
    checkpoint's own summary rather than accepting a caller-chosen default.
    """

    model_config = ConfigDict(extra="forbid")

    title: str = ""


class ModelPriceRequest(BaseModel):
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

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model: str
    input_per_mtok: str | None = None
    output_per_mtok: str | None = None
    cache_write_per_mtok: str | None = None
    cache_read_per_mtok: str | None = None
    currency: str | None = None
    effective_from: str | None = None
    reason: str | None = None


class ModelConnectionRequest(BaseModel):
    """Encrypted per-user endpoint/key data for one model profile."""

    model_config = ConfigDict(extra="forbid")

    endpoint: str | None = None
    api_key: str | None = None
    # OpenAI and Anthropic expose organization usage only to separate admin
    # credentials. It is optional, encrypted with the connection, and never
    # substituted for the inference key.
    admin_api_key: str | None = None


class ModelWeeklyBudgetRequest(BaseModel):
    """Owner-defined advisory budget; null clears it."""

    model_config = ConfigDict(extra="forbid")

    token_budget: int | None = None


class SetModelAdvisorRequest(BaseModel):
    # Persist (or clear, with null/empty) the user-owned advisor model profile.
    # extra="forbid" rejects unknown fields.
    model_config = ConfigDict(extra="forbid")

    profile_id: str | None = None


class UploadAttachmentRequest(BaseModel):
    # One base64-encoded image upload for the governed attachment store.
    # Validation is fail-closed server-side (media-type allowlist, size cap,
    # magic-byte sniff); extra="forbid" rejects unknown fields.
    model_config = ConfigDict(extra="forbid")

    filename: str
    media_type: str
    data_base64: str


class UploadSkillRequest(BaseModel):
    """One base64-encoded ``SKILL.md`` or ``*.skill`` upload.

    Validation is fail-closed server-side (extension allowlist, size caps,
    frontmatter contract, archive-member safety); ``extra="forbid"`` rejects
    unknown fields.
    """

    model_config = ConfigDict(extra="forbid")

    filename: str
    data_base64: str


class SkillUrlRequest(BaseModel):
    """A published skill's URL, to verify or to import."""

    model_config = ConfigDict(extra="forbid")

    url: str


class BuildSkillRequest(BaseModel):
    """A skill Raiker authored: the name, the trigger description, the body."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    body: str


class RenameSkillRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str


class SetSkillActiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active: bool


class BrainSourceRequest(BaseModel):
    """One location inside the Knowledge Map's boundary.

    Either a scoped source path (``<root_id>/<relative>``) for the source
    endpoints, or an absolute folder path for the grant endpoint.
    """

    model_config = ConfigDict(extra="forbid")

    path: str


class BrainSourceUploadRequest(BaseModel):
    """A file the owner chose from their computer, to be *copied* into Raiker.

    ``store_copy`` is the permission, and it has no default: an upload duplicates
    the file into the workspace, which is exactly the thing that must not happen
    because a file picker was opened. A request without an explicit true is
    refused rather than treated as consent.
    """

    model_config = ConfigDict(extra="forbid")

    filename: str
    content_base64: str
    store_copy: bool


class ConnectCodeRepoRequest(BaseModel):
    """Reference a repository from the Build workspace.

    ``kind="local"`` needs ``path`` — a folder already inside this Raiker
    workspace; anything resolving outside it is refused server-side.
    ``kind="github"`` needs ``owner`` and ``repo`` and performs no network call:
    it records the coordinate, and reads still run through the brokered
    ``github_read`` tool under the ``connector_github_runtime`` gate.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["local", "github"]
    path: str | None = None
    owner: str | None = None
    repo: str | None = None
    branch: str | None = None


class SelectCodeRepoRequest(BaseModel):
    """Point the Build workspace at one repository, or at none with ``null``."""

    model_config = ConfigDict(extra="forbid")

    repo_id: str | None = None


class InstanceCreateRequest(BaseModel):
    """Name and optional first account for a locally isolated Raiker instance."""

    model_config = ConfigDict(extra="forbid")

    name: str
    username: str | None = None
    password: str | None = None


class CreateProjectRequest(BaseModel):
    # Create a named project (web-app task 5). The root subpath is derived
    # server-side from the name and contained inside the workspace — the client
    # never supplies a path. extra="forbid" rejects unknown fields.
    # parent_id (optional) creates a nested project under the given parent.
    model_config = ConfigDict(extra="forbid")

    name: str
    parent_id: str | None = None


class SelectProjectRequest(BaseModel):
    # Set (or clear, with null/empty) the active project. Selecting a project
    # grants nothing — it is an organizing scope only.
    model_config = ConfigDict(extra="forbid")

    project_id: str | None = None


class SaveProjectContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instructions: str = ""
    attachment_ids: list[str] = []
    # ``memory_enabled`` remains accepted for older clients. New clients send
    # a tri-state override so child folders can inherit their nearest ancestor.
    memory_enabled: bool | None = None
    memory_mode: Literal["inherit", "enabled", "disabled"] | None = None


class MoveProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parent_id: str | None = None


class SetSessionPinnedRequest(BaseModel):
    # Pin (or unpin) a session. Pinning is an organizing label only — it grants
    # nothing. extra="forbid" rejects unknown fields.
    model_config = ConfigDict(extra="forbid")

    pinned: bool


class BulkDeleteSessionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_ids: list[str]


class SetSessionProjectRequest(BaseModel):
    # Move a chat into a project, or out of every project with a null
    # project_id. A project is an organizing scope — the move grants nothing
    # and only changes the bounded context the chat receives.
    # extra="forbid" rejects unknown fields.
    model_config = ConfigDict(extra="forbid")

    project_id: str | None = None


class RenameSessionRequest(BaseModel):
    # Rename one session. The title is an organizing label only — it grants
    # nothing. The server normalizes (trim, collapse whitespace, length cap) and
    # rejects invalid input. extra="forbid" rejects unknown fields.
    model_config = ConfigDict(extra="forbid")

    title: str


class CreateMcpServerRequest(BaseModel):
    # Build a local stdio MCP server from a reviewed template (Control Deck
    # task 4b). Both fields are validated/normalized server-side; the actual
    # write runs through the governed mcp_builder_runtime capability.
    model_config = ConfigDict(extra="forbid")

    name: str
    template: str


class RenameMcpServerRequest(BaseModel):
    # Rename one owner-scoped MCP server profile. The server normalizes the name
    # and rejects a clash with the caller's other servers.
    model_config = ConfigDict(extra="forbid")

    name: str


class CreateRemoteMcpServerRequest(BaseModel):
    # Add a remote (HTTP) MCP connection (monitored MCP connections, Phase A).
    # `endpoint_url` is the owner-added server URL; `auth_ref` optionally names
    # the env var holding the owner token (never the token itself).
    model_config = ConfigDict(extra="forbid")

    name: str
    endpoint_url: str
    auth_ref: str | None = None


class ContainMcpServerRequest(BaseModel):
    # Optional redacted reason for a pause/kill of a monitored MCP connection
    # (Phase C). The reason is human-readable copy shown back to the owner — it
    # must never carry a payload or token. extra="forbid" rejects unknown fields.
    model_config = ConfigDict(extra="forbid")

    reason: str | None = None


class BreachCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str
    enabled: bool = False


class SetSessionTagsRequest(BaseModel):
    # Replace the tag set for one session. Tags are organizing labels only —
    # they grant nothing. The server normalizes (trim, lowercase, dedupe,
    # length/count caps) and rejects invalid input. extra="forbid" rejects
    # unknown fields.
    model_config = ConfigDict(extra="forbid")

    tags: list[str]


class SetModelFallbackRequest(BaseModel):
    # Ordered list of model profile ids to try (in order) when the selected
    # provider is unavailable. extra="forbid" rejects unknown fields.
    model_config = ConfigDict(extra="forbid")

    profile_ids: list[str]


@dataclass
class PromptRequest:
    text: str
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


@dataclass
class InboundChannelMessage:
    # Inbound channel payload. Always treated as untrusted; never executed.
    sender_id: str
    text: str = ""


@dataclass
class InterruptRequest:
    session_id: str
    task_id: str | None = None
    all: bool = False
    action_type: str = "cancel"
    reason: str = "user requested stop"
    steer_text: str | None = None


class ResolveApprovalRequest(BaseModel):
    # extra="forbid" rejects unknown request fields (e.g. an attempt to smuggle an edited payload).
    model_config = ConfigDict(extra="forbid")

    approve: bool
    reason: str


class ApprovalDecisionRequest(BaseModel):
    # Explicit allow/deny endpoints only accept an optional human reason; no payload edits.
    model_config = ConfigDict(extra="forbid")

    reason: str = ""


def serialize_dto(dto: Any) -> Any:
    if hasattr(dto, "to_dict"):
        return dto.to_dict()
    if isinstance(dto, (list, tuple)):
        return [serialize_dto(item) for item in dto]
    return dict(dto)
