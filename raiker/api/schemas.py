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
class AuthSessionRequest:
    # Optional explicit principal; defaults to the resolved local owner. Local-only, human-only.
    as_principal: str | None = None


@dataclass
class PromptRequest:
    text: str
    session_id: str | None = None
    planning_mode: str | None = None
    approval_mode: str | None = None
    model_profile: str | None = None
    max_tool_calls: int | None = None
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


def serialize_dto(dto: Any) -> Any:
    if hasattr(dto, "to_dict"):
        return dto.to_dict()
    if isinstance(dto, (list, tuple)):
        return [serialize_dto(item) for item in dto]
    return dict(dto)
