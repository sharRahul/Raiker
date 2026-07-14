from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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
class DisableCapabilityRequest:
    reason: str = ""
    as_principal: str | None = None


@dataclass
class SetCapabilityDecisionModeRequest:
    reason: str = ""
    as_principal: str | None = None


@dataclass
class AuthSessionRequest:
    # Optional explicit principal; defaults to the resolved local owner. Local-only, human-only.
    as_principal: str | None = None


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str
    password: str


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


class VaultKeyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    mfa_code: str | None = None


class SettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    settings: dict[str, Any]


class TaskCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    description: str = ""
    priority: str | None = None
    scheduled_at: str | None = None
    recurrence: str | None = None
    reminder_at: str | None = None


class SetModelSelectionRequest(BaseModel):
    # Persist the operator's model selection: a profile id plus, for providers
    # that serve several models (or ship a placeholder), the concrete model.
    # extra="forbid" rejects unknown fields.
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    profile_id: str
    model: str | None = None


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


class CreateProjectRequest(BaseModel):
    # Create a named project (web-app task 5). The root subpath is derived
    # server-side from the name and contained inside the workspace — the client
    # never supplies a path. extra="forbid" rejects unknown fields.
    model_config = ConfigDict(extra="forbid")

    name: str


class SelectProjectRequest(BaseModel):
    # Set (or clear, with null/empty) the active project. Selecting a project
    # grants nothing — it is an organizing scope only.
    model_config = ConfigDict(extra="forbid")

    project_id: str | None = None


class SaveProjectContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instructions: str = ""
    attachment_ids: list[str] = []
    memory_enabled: bool = False


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
    max_tool_calls: int | None = None
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
