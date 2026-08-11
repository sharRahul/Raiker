from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ModelSetupState:
    owner_principal_id: str
    status: str = "required"
    step: str = "choose_path"
    path: str | None = None
    selected_profile_id: str | None = None
    selected_model: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SetupState:
    owner_principal_id: str
    status: str = "required"
    stage: str = "model"
    selected_profile_id: str | None = None
    selected_model: str | None = None
    model_deferred: bool = False
    privacy_mode: str | None = None
    privacy_acknowledged_at: str | None = None
    backup_mode: str = "later"
    backup_target: str | None = None
    backup_verified_at: str | None = None
    background_service_enabled: bool = False
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
