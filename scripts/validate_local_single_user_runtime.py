from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from raiker.phase_gates import (
    ALL_CAPABILITIES,
    RUNTIME_DOMAIN_CAPABILITIES,
    default_capability_gates,
)
from raiker.runtime.authority.models import AI_ROLE_NAMES, HUMAN_ONLY_ROLES


def _check_file(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        errors.append(f"missing_file:{path}")
    return errors


def check_synthetic_principal_in_commands(source_path: Path) -> list[str]:
    errors: list[str] = []
    text = source_path.read_text(encoding="utf-8")
    tree = ast.parse(text)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("handle_"):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr == "route":
                    for kw in sub.keywords:
                        if kw.arg == "principal" and isinstance(kw.value, ast.Call):
                            call = kw.value
                            if isinstance(call.func, ast.Name) and call.func.id == "Principal":
                                for kw2 in call.keywords:
                                    if kw2.arg == "principal_id" and isinstance(kw2.value, ast.Constant) and kw2.value.value == "cli_local":
                                        errors.append(
                                            f"synthetic_cli_principal:{node.name} in {source_path.name}"
                                        )
    return errors


def check_no_synthetic_rgm_role_auto_creation(source_path: Path) -> list[str]:
    errors: list[str] = []
    text = source_path.read_text(encoding="utf-8")
    if "rl_rgm" in text and "cli_local" in text and "_ensure_runtime_gate_manager_role" not in text:
        pass
    if "def _ensure_runtime_gate_manager_role" in text:
        errors.append("synthetic_rgm_role_creator_still_present:_ensure_runtime_gate_manager_role")
    return errors


def check_dangerous_capabilities_disabled_by_default() -> list[str]:
    errors: list[str] = []
    dangerous = {
        "shell_execution", "process_execution", "network_execution",
        "web_fetch", "email_runtime", "calendar_runtime", "finance_runtime",
        "investment_runtime", "medical_runtime", "pregnancy_baby_runtime",
        "cctv_runtime", "home_security_runtime", "hardware_operator_runtime",
        "plugin_execution_cap", "plugin_install", "external_channel_runtime",
        "channel_approval_relay", "remote_execution_cap", "container_execution_cap",
        "cloud_execution_cap", "approval_execution_relay", "scheduled_routines",
        "graph_indexing_runtime", "semantic_memory_runtime",
        "vector_embedding_runtime", "hosted_model_runtime",
        "private_network_model_runtime",
    }
    for cap in dangerous:
        if cap not in ALL_CAPABILITIES:
            errors.append(f"missing_dangerous_capability:{cap}")
        if cap not in RUNTIME_DOMAIN_CAPABILITIES:
            errors.append(f"dangerous_capability_not_in_runtime_domain:{cap}")

    gates = default_capability_gates()
    for cap in dangerous:
        gate = gates.get(cap)
        if gate is not None:
            from raiker.phase_gates import CapabilityState
            if gate.state not in (CapabilityState.DISABLED, CapabilityState.PLANNED):
                errors.append(f"dangerous_capability_not_disabled_by_default:{cap}={gate.state}")

    return errors


def check_ai_cannot_be_runtime_gate_manager() -> list[str]:
    errors: list[str] = []
    ai_roles = AI_ROLE_NAMES
    human_roles = HUMAN_ONLY_ROLES
    for role in ai_roles:
        if role in human_roles:
            errors.append(f"ai_role_in_human_only_roles:{role}")
    return errors


def check_owner_bootstrap_module_exists() -> list[str]:
    path = Path(__file__).resolve().parent.parent / "raiker" / "cli" / "principal_resolver.py"
    return _check_file(path)


def check_owner_bootstrap_test_file() -> list[str]:
    test_dir = Path(__file__).resolve().parent.parent / "tests"
    if not test_dir.exists():
        return ["missing_tests_directory"]
    test_files = list(test_dir.glob("*owner_bootstrap*")) + list(test_dir.glob("*local_runtime*")) + list(test_dir.glob("*local_single_user_runtime*"))
    if not test_files:
        return ["missing_owner_bootstrap_test_file"]
    return []


def check_docs_markers() -> list[str]:
    errors: list[str] = []
    root = Path(__file__).resolve().parent.parent
    docs_to_check = [
        root / "README.md",
        root / "docs/ARCHITECTURE.md",
        root / "docs/IMPLEMENTATION_STATUS.md",
        root / "docs/SECURITY_ARCHITECTURE.md",
        root / "docs/SECURITY_AND_POLICY.md",
        root / "docs/FEATURE_COVERAGE_MATRIX.md",
        root / "docs/GAP_AND_TODO_ANALYSIS.md",
        root / "docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md",
        root / "docs/LOCAL_VALIDATION_GATE.md",
        root / "docs/API_AND_CONTRACT_SCHEMAS.md",
        root / "docs/CONTRACTS.md",
    ]
    for doc_path in docs_to_check:
        if not doc_path.exists():
            errors.append(f"missing_doc:{doc_path.name}")
            continue
        text = doc_path.read_text(encoding="utf-8")
        if "runtime_enablement_candidate: completed" not in text:
            errors.append(f"missing_runtime_enablement_marker:{doc_path.name}")
        if "production_ready_local_single_user_runtime" in text and "owner_bootstrapped" not in text and "owner bootstrap" not in text.lower():
            errors.append(
                f"overclaim_production_readiness_without_owner_bootstrap:{doc_path.name}"
            )
    return errors


def main() -> int:
    errors: list[str] = []

    cli_path = (
        Path(__file__).resolve().parent.parent / "raiker" / "cli" / "commands.py"
    )

    errors.extend(check_owner_bootstrap_module_exists())
    errors.extend(check_owner_bootstrap_test_file())
    errors.extend(check_synthetic_principal_in_commands(cli_path))
    errors.extend(check_dangerous_capabilities_disabled_by_default())
    errors.extend(check_ai_cannot_be_runtime_gate_manager())
    errors.extend(check_docs_markers())

    if errors:
        print("validate_local_single_user_runtime: FAILED")
        for err in errors:
            print(f"  FAIL: {err}")
        return 1

    print("validate_local_single_user_runtime: PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
