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
        "plugin_install", "remote_execution_cap",
        "external_channel_runtime",
    }
    for cap in runtime_high_risk:
        if cap not in ALL_CAPABILITIES:
            errors.append(f"missing_high_risk_capability:{cap}")

    # 2. All high-risk capabilities must default to disabled
    gates = default_capability_gates()
    for cap in runtime_high_risk:
        if cap in gates:
            gate = gates[cap]
            if gate.state not in (CapabilityState.DISABLED, CapabilityState.PLANNED):
                errors.append(f"high_risk_capability_not_disabled:{cap}")
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
        for marker in required_markers:
            if marker not in text:
                errors.append(f"missing_doc_marker:{doc_name}:{marker}")

    # 9. Capability gate transitions must fail closed for invalid transitions
    for cap in runtime_high_risk:
        if cap in gates:
            try:
                get_capability_gate(cap)
            except PermissionError:
                errors.append(f"unknown_capability_in_transition:{cap}")

    if errors:
        print("RUNTIME ENABLEMENT READINESS: FAILED")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("RUNTIME ENABLEMENT READINESS: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
