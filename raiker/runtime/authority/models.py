from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class PrincipalType(StrEnum):
    HUMAN = "human"
    AI_AGENT = "ai_agent"
    AUTOMATION = "automation"
    SYSTEM = "system"


class RiskLevelValue(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RuntimeMode(StrEnum):
    DEVELOPMENT_PREVIEW = "development_preview"
    LOCAL_SINGLE_USER_SAFE = "local_single_user_safe"
    LOCAL_SINGLE_USER_RUNTIME = "local_single_user_runtime"
    MULTI_USER_LOCAL_RUNTIME = "multi_user_local_runtime"
    HOSTED_OR_NETWORKED_RUNTIME = "hosted_or_networked_runtime"


class DomainScope(StrEnum):
    EMAIL = "email"
    CALENDAR = "calendar"
    REMINDERS = "reminders"
    DOCUMENTS = "documents"
    FINANCE = "finance"
    INVESTMENTS = "investments"
    MEDICAL = "medical"
    PREGNANCY_BABY = "pregnancy_baby"
    HOME_SECURITY = "home_security"
    CCTV = "cctv"
    HARDWARE = "hardware"
    SYSTEMS = "systems"
    PROJECTS = "projects"
    CODING = "coding"
    SHOPPING = "shopping"
    TRAVEL = "travel"


@dataclass(frozen=True)
class Principal:
    principal_id: str
    principal_type: PrincipalType
    display_name: str
    delegated_by_user_id: str | None = None
    model_profile_id: str | None = None
    session_id: str | None = None
    role_ids: tuple[str, ...] = ()
    domain_scopes: tuple[str, ...] = ()
    max_runtime_mode: str = RuntimeMode.DEVELOPMENT_PREVIEW
    created_at: str = ""
    expires_at: str | None = None
    is_active: bool = True

    def is_expired(self, now: str) -> bool:
        if self.expires_at is None:
            return False
        return now > self.expires_at


@dataclass(frozen=True)
class RiskLevel:
    level: RiskLevelValue
    label: str
    description: str
    auto_allowed: bool = False
    requires_approval: bool = False
    requires_risk_acceptance: bool = False
    requires_human_confirmation: bool = False


@dataclass(frozen=True)
class RiskAcceptance:
    risk_acceptance_id: str
    accepted_by: str
    accepted_for_principal_id: str
    action_id: str
    action_type: str
    domain_scope: str
    risk_level: str
    risk_summary: str
    data_involved: str
    expected_effect: str
    one_time_or_reusable: str
    expires_at: str | None
    created_at: str
    policy_decision_id: str | None = None
    approval_id: str | None = None


AI_ROLE_NAMES = frozenset({"assistant", "automation", "operator", "developer"})

HUMAN_ONLY_ROLES = frozenset({
    "owner",
    "admin",
    "approver",
    "security_admin",
    "finance_approver",
    "medical_decision_maker",
    "runtime_gate_manager",
})

DOMAIN_SCOPES = frozenset(scope.value for scope in DomainScope)

RISK_LEVELS = frozenset(level.value for level in RiskLevelValue)

RISK_ACCEPTANCE_REQUIRED_FIELDS = frozenset({
    "risk_acceptance_id",
    "accepted_by",
    "accepted_for_principal_id",
    "action_id",
    "action_type",
    "domain_scope",
    "risk_level",
    "risk_summary",
    "data_involved",
    "expected_effect",
    "one_time_or_reusable",
    "created_at",
})

RUNTIME_MODES = frozenset(mode.value for mode in RuntimeMode)

PRINCIPAL_TYPES = frozenset(pt.value for pt in PrincipalType)

AI_ROLE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "assistant": {
        "description": "Default AI role for general assistance",
        "auto_allowed": [
            "read", "search", "summarise", "classify", "monitor",
            "draft", "plan", "recommend", "prepare_actions", "create_reports",
            "create_reminders", "prepare_email_changes", "explain_information",
        ],
        "requires_approval_or_risk_acceptance": [
            "send_email", "delete_email", "move_money", "buy_stock",
            "sell_stock", "share_records", "make_medical_decisions",
            "book_appointment", "cancel_appointment", "delete_cctv_footage",
            "change_security_settings", "grant_permissions", "enable_runtime_gates",
        ],
    },
    "automation": {
        "description": "For repeated/background tasks with fixed scope",
        "must_be_scoped": True,
        "auto_allowed": [
            "scheduled_summaries", "recurring_reports", "stock_movement_alerts",
            "calendar_reminders", "checklist_reminders", "hardware_monitoring",
            "cctv_summaries", "progress_reports", "validation_reports",
        ],
        "denied": [
            "buy_stock", "sell_stock", "move_money", "change_portfolio_settings",
            "self_expand_scope",
        ],
    },
    "operator": {
        "description": "For systems, hardware, CCTV, backups, infrastructure",
        "auto_allowed": [
            "check_runtime_status", "check_queues", "check_backups",
            "check_disk_health", "check_cctv_events", "check_server_status",
            "check_network_status", "generate_diagnostics",
            "recommend_maintenance", "recommend_hardware_upgrade",
        ],
        "requires_approval_or_risk_acceptance": [
            "delete_backups", "change_cctv_settings", "disable_monitoring",
            "change_retention", "change_storage_cleanup", "restart_service",
            "export_sensitive_diagnostics",
        ],
        "denied_unless_explicitly_enabled": [
            "remote_execution", "container_execution", "cloud_execution",
            "delete_cctv_footage", "disable_audit_logs", "change_security_policy",
            "enable_runtime_gates",
        ],
    },
    "developer": {
        "description": "For code, repositories, projects, PR work",
        "auto_allowed": [
            "read_workspace", "inspect_git_diff", "run_safe_static_analysis",
            "create_patch_proposals", "create_review_findings",
            "create_implementation_plans", "save_proposals", "request_approval",
        ],
        "requires_approval": [
            "write_file", "edit_file", "apply_patch", "run_tests",
            "run_shell_commands", "memory_write", "memory_forget",
        ],
        "denied": [
            "approve_own_action", "merge_pr", "change_policy", "grant_roles",
            "enable_runtime_gates", "install_plugins", "execute_plugins",
            "remote_execution", "container_execution", "cloud_execution",
            "network_fetch",
        ],
    },
}
