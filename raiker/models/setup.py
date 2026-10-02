from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from raiker.contracts.views import View

SetupStatus = Literal["required", "in_progress", "skipped", "complete"]
ModelSetupStep = Literal["choose_path", "provider", "model", "review", "ready"]
ModelSetupPath = Literal["provider", "ollama", "lm_studio", "local_gguf", "hugging_face"]
SetupStage = Literal["welcome", "account", "model", "privacy", "backup", "finish"]
PrivacyMode = Literal["local_first", "balanced"]
BackupMode = Literal["later", "local"]


@dataclass(frozen=True)
class ModelSetupState(View):
    owner_principal_id: str
    status: SetupStatus = "required"
    step: ModelSetupStep = "choose_path"
    path: ModelSetupPath | None = None
    selected_profile_id: str | None = None
    selected_model: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True)
class SetupState(View):
    owner_principal_id: str
    status: SetupStatus = "required"
    #: First launch opens on what the product is, not on a provider matrix
    #: (FIRST-03). `account` and `backup` remain readable stored values.
    stage: SetupStage = "welcome"
    selected_profile_id: str | None = None
    selected_model: str | None = None
    model_deferred: bool = False
    privacy_mode: PrivacyMode | None = None
    privacy_acknowledged_at: str | None = None
    backup_mode: BackupMode = "later"
    backup_target: str | None = None
    backup_verified_at: str | None = None
    background_service_enabled: bool = False
    created_at: str | None = None
    updated_at: str | None = None
