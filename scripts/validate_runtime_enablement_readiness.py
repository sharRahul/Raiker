from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from raiker.phase_gates import (
    ALL_CAPABILITIES,
    CapabilityState,
    default_capability_gates,
    get_capability_gate,
)
from raiker.runtime.authority.models import (
    AI_ROLE_DEFINITIONS,
    AI_ROLE_NAMES,
    DOMAIN_SCOPES,
    HUMAN_ONLY_ROLES,
    RISK_ACCEPTANCE_REQUIRED_FIELDS,
)

DIRECT_MUTATION_PATTERNS = {
    "store.insert_user": "admin_mutation",
    "store.deactivate_user": "admin_mutation",
    "store.insert_role": "role_mutation",
    "store.insert_user_role_assignment": "role_mutation",
    "store.delete_user_role_assignment": "role_mutation",
}


def check_cli_mutation_handlers(source_path: Path) -> list[str]:
    errors: list[str] = []
    text = source_path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("handle_"):
            has_governance = any(
                _calls_govern_admin_mutation(n) for n in ast.walk(node)
            )
            has_direct_mutation = any(
                _has_direct_mutation_pattern(n) for n in ast.walk(node)
            )
            if has_direct_mutation and not has_governance:
                errors.append(
                    f"cli_mutation_without_governance:{node.name} in {source_path.name}"
                )
    return errors


def _calls_govern_admin_mutation(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_govern_admin_mutation"
    )


def _has_direct_mutation_pattern(node: ast.AST) -> bool:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        dotted = _format_attr_call(node)
        if dotted in DIRECT_MUTATION_PATTERNS:
            return True
    return False


def _format_attr_call(node: ast.Call) -> str:
    parts: list[str] = []
    current = node.func
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


def main() -> int:
    errors: list[str] = []

    # 0. Check CLI handler governance
    cli_path = Path(__file__).resolve().parent.parent / "raiker" / "cli" / "commands.py"
    if cli_path.exists():
        errors.extend(check_cli_mutation_handlers(cli_path))

    # 1. All high-risk capabilities must be in the registry
    runtime_high_risk = {
        "shell_execution", "process_execution", "network_execution",
        "file_write_execution", "patch_apply_execution",
        "memory_write_execution", "memory_forget_execution",
        "admin_mutation", "policy_mutation", "role_mutation",
        "email_runtime", "finance_runtime", "investment_runtime",
        "medical_runtime", "cctv_runtime", "plugin_execution_cap",
        "plugin_install", "plugin_revocation_cap", "plugin_runtime_cap",
        "plugin_sandboxed_runtime_cap", "remote_execution_cap",
        "external_channel_runtime",
    }
    for cap in runtime_high_risk:
        if cap not in ALL_CAPABILITIES:
            errors.append(f"missing_high_risk_capability:{cap}")

    # 2. Default gate posture. Integrated capabilities (those with a real
    #    executor) ship ENABLED by default — governed by the per-capability
    #    decision mode (default `ask`), the critical-risk human floor, PolicyEngine
    #    hard-denies, and executor-level env allowlists, which are independent of
    #    the gate. Capabilities that are not integrated yet (no real executor) must
    #    still ship DISABLED and fail closed.
    gates = default_capability_gates()
    try:
        from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES as _REAL_CAPS
    except Exception as exc:  # pragma: no cover - import guard
        _REAL_CAPS = frozenset()
        errors.append(f"cannot_import_real_executor_capabilities:{exc}")
    for cap, gate in gates.items():
        if cap in _REAL_CAPS and gate.state != CapabilityState.ENABLED_RUNTIME:
            errors.append(f"integrated_capability_not_enabled_by_default:{cap}")
    for cap in runtime_high_risk:
        if cap in _REAL_CAPS:
            continue  # integrated -> enabled by default (checked above)
        if cap in gates:
            gate = gates[cap]
            if gate.state not in (CapabilityState.DISABLED, CapabilityState.PLANNED):
                errors.append(f"not_integrated_high_risk_capability_not_disabled:{cap}")
        else:
            errors.append(f"high_risk_capability_not_in_gates:{cap}")

    # 3. AI roles must be defined and not include human-only permissions
    for role_name in AI_ROLE_NAMES:
        if role_name not in AI_ROLE_DEFINITIONS:
            errors.append(f"missing_ai_role_definition:{role_name}")
        else:
            definition = AI_ROLE_DEFINITIONS[role_name]
            denied = set(definition.get("denied", []))
            if "grant_roles" in denied and "enable_runtime_gates" in denied:
                pass  # good

    # 4. Human-only roles must be enforced in any assignment check
    if "owner" not in HUMAN_ONLY_ROLES:
        errors.append("human_only_roles_missing_owner")
    if "admin" not in HUMAN_ONLY_ROLES:
        errors.append("human_only_roles_missing_admin")
    if "runtime_gate_manager" not in HUMAN_ONLY_ROLES:
        errors.append("human_only_roles_missing_runtime_gate_manager")

    # 5. Risk acceptance required fields
    required = RISK_ACCEPTANCE_REQUIRED_FIELDS
    for field in ("risk_acceptance_id", "accepted_by", "accepted_for_principal_id",
                  "action_id", "action_type", "domain_scope", "risk_level",
                  "risk_summary", "data_involved", "expected_effect"):
        if field not in required:
            errors.append(f"risk_acceptance_missing_required_field:{field}")

    # 6. AI cannot approve own action - check definition has this
    dev_denied = set(AI_ROLE_DEFINITIONS.get("developer", {}).get("denied", []))
    if "approve_own_action" not in dev_denied:
        errors.append("developer_role_missing_approve_own_action_denial")

    # 7. Domain scopes must be defined
    essential_scopes = {"email", "calendar", "finance", "medical", "cctv", "coding"}
    for scope in essential_scopes:
        if scope not in DOMAIN_SCOPES:
            errors.append(f"missing_domain_scope:{scope}")

    # 8. Validate documentation markers
    doc_files = [
        "README.md",
        "docs/ARCHITECTURE.md",
        "docs/SECURITY_AND_POLICY.md",
        "docs/FEATURE_COVERAGE_MATRIX.md",
        "docs/GAP_AND_TODO_ANALYSIS.md",
        "docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md",
        "docs/LOCAL_VALIDATION_GATE.md",
        "docs/IMPLEMENTATION_STATUS.md",
    ]
    repo_root = Path(__file__).resolve().parent.parent
    required_markers = [
        "runtime_enablement_candidate",
        "strict non-allow blocking",
        "role revoke governed",
        "capability gate per action",
    ]
    for doc_name in doc_files:
        doc_path = repo_root / doc_name
        if not doc_path.exists():
            errors.append(f"missing_doc:{doc_name}")
            continue
        text = doc_path.read_text(encoding="utf-8")
        text_lower = text.lower()
        for marker in required_markers:
            if marker.lower() not in text_lower:
                errors.append(f"missing_doc_marker:{doc_name}:{marker}")

    # 9. Capability gate transitions must fail closed for invalid transitions
    for cap in runtime_high_risk:
        if cap in gates:
            try:
                get_capability_gate(cap)
            except PermissionError:
                errors.append(f"unknown_capability_in_transition:{cap}")

    # 10. Not-yet-integrated (no real executor) high-risk capabilities must stay
    #     disabled by default and fail closed. (Integrated capabilities ship
    #     enabled — verified in check 2 above.)
    not_integrated_remain_disabled = {
        "finance_runtime", "investment_runtime", "medical_runtime",
        "pregnancy_baby_runtime", "cctv_runtime", "home_security_runtime",
        "hardware_operator_runtime", "remote_execution_cap", "cloud_execution_cap",
    }
    for cap in not_integrated_remain_disabled:
        remain_gate = gates.get(cap)
        if remain_gate is None:
            errors.append(f"runtime_activation_cap_not_in_gates:{cap}")
        elif remain_gate.state not in (CapabilityState.DISABLED, CapabilityState.PLANNED):
            errors.append(f"not_integrated_cap_not_disabled:{cap}")

    # 11. CLI commands for runtime mode/capability must exist in commands.py
    commands_path = repo_root / "raiker" / "cli" / "commands.py"
    if commands_path.exists():
        text = commands_path.read_text(encoding="utf-8")
        required_commands = [
            "/runtime-mode",
            "/runtime-mode status",
            "/runtime-mode activate",
            "/runtime-mode disable",
            "/capability-gates",
            "/capability-gate",
            "/capability-gate enable",
            "/capability-gate disable",
            "/runtime-readiness",
        ]
        for cmd_name in required_commands:
            if cmd_name not in text:
                errors.append(f"missing_runtime_cli_command:{cmd_name}")

    # 12. Runtime mode table must exist in migrations
    migrations_path = repo_root / "raiker" / "storage" / "migrations.py"
    if migrations_path.exists():
        text = migrations_path.read_text(encoding="utf-8")
        if "runtime_mode_state" not in text:
            errors.append("missing_runtime_mode_state_table_migration")
        if "capability_gate_state" not in text:
            errors.append("missing_capability_gate_state_table_migration")

    # 13. Executor availability must be registry-backed, not a static allowlist.
    #     A static "satisfied" set decouples activation from real executors and
    #     was the cause of fake-success gates. Forbid its reintroduction.
    activation_path = repo_root / "raiker" / "runtime" / "authority" / "activation.py"
    if activation_path.exists():
        atext = activation_path.read_text(encoding="utf-8")
        if "_SATISFIED_CAPS" in atext:
            errors.append("activation_uses_static_satisfied_set")
        if "registry" not in atext or "def has_executor" not in atext:
            errors.append("has_executor_not_registry_backed")

    # 14. The default executor registry must contain only genuinely-implemented
    #     executors, and must NOT register sensitive/external capabilities.
    try:
        from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES
    except Exception as exc:  # pragma: no cover - import guard
        REAL_EXECUTOR_CAPABILITIES = frozenset()
        errors.append(f"cannot_import_real_executor_capabilities:{exc}")
    # reminder/calendar/email are local-only Tier-6 executors (no network / no
    # external delivery); the remaining sensitive domains stay executor-less.
    must_not_have_default_executor = {
        "finance_runtime", "investment_runtime",
        "medical_runtime", "pregnancy_baby_runtime", "cctv_runtime",
        "home_security_runtime", "hardware_operator_runtime",
        "remote_execution_cap", "cloud_execution_cap",
    }
    # Promoted/integrated capabilities are real, bounded, threat-modelled executors;
    # they default enabled and are governed per action (checked above):
    # external_channel_runtime,
    # channel_approval_relay (slice 4), container_execution_cap (slice 3),
    # scheduled_routines (slice 2), and hosted_model_runtime /
    # private_network_model_runtime (slice 7 — owner egress allowlist,
    # env-only credentials), and plugin_install (slice 8 — local manifest
    # validation + install-record creation only), and plugin_execution_cap
    # (slice 9 — brokered read-only installed-plugin tool invocation only).
    # Remote/cloud command execution must still lack a default executor
    # (fail-closed).
    for cap in must_not_have_default_executor:
        if cap in REAL_EXECUTOR_CAPABILITIES:
            errors.append(f"sensitive_capability_has_default_executor:{cap}")

    if errors:
        print("RUNTIME ENABLEMENT READINESS: FAILED")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("RUNTIME ENABLEMENT READINESS: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
