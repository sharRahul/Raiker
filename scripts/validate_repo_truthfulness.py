from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = [ROOT / "README.md", *(ROOT / "docs").glob("*.md")]
CANONICAL_DOCS = [
    ROOT / "README.md",
    ROOT / "docs/ARCHITECTURE.md",
    ROOT / "docs/IMPLEMENTATION_STATUS.md",
    ROOT / "docs/FEATURE_COVERAGE_MATRIX.md",
    ROOT / "docs/GAP_AND_TODO_ANALYSIS.md",
    ROOT / "docs/SECURITY_AND_POLICY.md",
    ROOT / "docs/SECURITY_ARCHITECTURE.md",
    ROOT / "docs/MEMORY_GOVERNANCE_RULES.md",
    ROOT / "docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md",
    ROOT / "docs/LOCAL_VALIDATION_GATE.md",
]
CANONICAL_STATUSES = {
    "implemented_read_only",
    "implemented_policy_gated",
    "implemented_approval_required",
    "metadata_only",
    "readiness_only",
    "dry_run_only",
    "contract_only",
    "disabled_deferred",
    "test_only",
}
REQUIRED_COMMANDS = {
    "/help",
    "/providers",
    "/models",
    "/model current",
    "/model use <profile_id>",
    "/model use --provider <provider> --model <model>",
    "/model health",
    "/model capabilities",
    "/reasoning",
    "/reasoning status",
    "/reasoning set <mode-or-effort>",
    "/reasoning off",
    "/status",
    "/tasks",
    "/events",
    "/checkpoints",
    "/approvals",
    "/approve <id>",
    "/deny <id>",
    "/memory",
    "/memory-store <text>",
    "/memory-search <query>",
    "/memory-forget <memory_id>",
    "/memory-list",
    "/semantic-memory",
    "/capabilities",
    "/execution-profiles",
    "/workspace",
    "/workspace-view",
    "/clients",
    "/plugins",
    "/plugin-plan <manifest_path>",
    "/graph-status",
    "/graph-plan",
    "/graph-readiness [--summary|--json]",
    "/memory-readiness [--summary|--json]",
    "/approval-readiness [--summary|--json]",
    "/cleanup-readiness [--summary|--json]",
    "/remote-readiness [--summary|--json]",
    "/plugin-readiness [--summary|--json]",
    "/channel-readiness [--summary|--json]",
    "/memory-review [--summary]",
    "/approval-previews [--json] [--status <status>] [--limit <n>]",
    "/graph-approval-preview",
    "/memory-approval-preview [--summary]",
    "/approval-preview <preview_id> [--json]",
    "/approval-audit [--summary]",
    "/rollback-plan",
    "/graph-rollback-plan",
    "/memory-rollback-plan",
    "/storage-lifecycle [--summary|--graph|--memory]",
    "/storage-lifecycle-retention [--summary]",
    "/storage-lifecycle-cleanup-preview [--summary]",
    "/storage-lifecycle-handoff [--summary]",
    "/storage-lifecycle-evidence [--summary] [--json] [--status <status>] [--target <graph|memory|rollback|storage|plugin|channel|remote>] [--limit <number>]",
    "/storage-lifecycle-policy-simulation [--summary] [--json] [--status <status>] [--target <graph|memory|rollback|storage|plugin|channel|remote>] [--limit <number>]",
    "/review [--summary] [--staged] [--path <path>] [--json] [--limit <number>] [--severity <info|low|medium|high>] [--propose-fixes] [--proposals-only] [--save-proposals]",
    "/proposals [--json] [--status <proposed|acknowledged|deferred|rejected|superseded>] [--limit <number>]",
    "/proposal <proposal_id> [--json] [--mark <proposed|acknowledged|deferred|rejected|superseded>] [--approval-preview]",
    "/doctor",
    "/channels",
    "/launch --provider mock --model mock-deterministic",
    "/quit",
}
REQUIRED_DISABLED_MARKERS = {
    "plugin_execution_enabled",
    "graph_indexing_enabled",
    "semantic_memory_writes_enabled",
    "vector_writes_enabled",
    "embedding_creation_enabled",
    "approval_execution_enabled",
    "approval_relay_runtime_enabled",
    "cleanup_execution_enabled",
    "rollback_execution_enabled",
    "external_channels_enabled",
    "notifications_enabled",
    "remote_execution_enabled",
    "container_execution_enabled",
    "cloud_execution_enabled",
    "process_execution_enabled",
    "shell_execution_enabled",
    "network_execution_enabled",
    "runtime_execution_enabled",
}
FORBIDDEN_GLOBAL = (
    "memory_reviewing",
    "approval executes pending action",
    "approval resolution executes",
)


def _catalog_commands() -> set[str]:
    text = (ROOT / "docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md").read_text(encoding="utf-8")
    match = re.search(r"## CLI Command Surface.*?```text\n(.*?)\n```", text, re.S)
    if not match:
        return set()
    return {line.strip() for line in match.group(1).splitlines() if line.strip()}


def _literal_command_prefixes() -> set[str]:
    tree = ast.parse((ROOT / "raiker/cli/commands.py").read_text(encoding="utf-8"))
    prefixes: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith("/"):
            prefixes.add(node.value.split()[0])
    return {prefix for prefix in prefixes if prefix not in {"/exit", "/"}}


def _validate_snippet(name: str, text: str) -> list[str]:
    lowered = text.lower()
    errors: list[str] = []
    if (
        any(token in name for token in ("IMPLEMENTATION_STATUS", "SECURITY", "TOOL", "ARCHITECTURE"))
        and "metadata-only" not in lowered
        and "metadata only" not in lowered
    ):
        errors.append(f"{name} missing metadata-only wording")
    if (
        ("approval resolution" in lowered or "/approve" in lowered)
        and "approval resolution is metadata-only" not in lowered
        and "does not execute approved action" not in lowered
    ):
        errors.append(f"{name} missing approval metadata-only wording")
    if "runtime execution remains disabled" not in lowered and "disabled/deferred" not in lowered:
        errors.append(f"{name} missing runtime-disabled wording")
    for phrase in FORBIDDEN_GLOBAL:
        if phrase in lowered:
            errors.append(f"{name} contains forbidden overclaim: {phrase}")
    return errors


def main() -> int:
    errors: list[str] = []
    for path in CANONICAL_DOCS:
        if not path.exists():
            errors.append(f"missing_doc:{path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        errors.extend(_validate_snippet(str(path.relative_to(ROOT)), text))

    combined = "\n".join(path.read_text(encoding="utf-8") for path in CANONICAL_DOCS if path.exists())
    for status in CANONICAL_STATUSES:
        if status not in combined:
            errors.append(f"missing_canonical_status:{status}")
    for marker in REQUIRED_DISABLED_MARKERS:
        if marker not in combined:
            errors.append(f"missing_disabled_runtime_marker:{marker}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for marker in (
        "current launchable UI is the plain local terminal client only",
        "Phase 8 deferred",
        "approval resolution is metadata-only",
        "durable memory mutation is broker-governed",
    ):
        if marker.lower() not in readme.lower():
            errors.append(f"README missing truth marker: {marker}")

    architecture = (ROOT / "docs/ARCHITECTURE.md").read_text(encoding="utf-8")
    for marker in (
        "Current Backend Capability Matrix",
        "checkpoint_created` and `turn_closed` are gateway finalisation events",
        "sessions: deferred; no `/sessions` command is currently implemented",
    ):
        if marker not in architecture:
            errors.append(f"ARCHITECTURE missing marker: {marker}")

    security_arch = (ROOT / "docs/SECURITY_ARCHITECTURE.md").read_text(encoding="utf-8")
    for marker in (
        "shell/process execution | disabled/deferred",
        "plugin execution | disabled/deferred",
        "remote/container/cloud execution | disabled/deferred",
        "approval resolution is metadata-only",
        "no tamper-proof logging is implemented",
    ):
        if marker.lower() not in security_arch.lower():
            errors.append(f"SECURITY_ARCHITECTURE missing marker: {marker}")

    memory_rules = (ROOT / "docs/MEMORY_GOVERNANCE_RULES.md").read_text(encoding="utf-8")
    for marker in (
        "/memory-store` and `/memory-forget` are brokered approval-required requests",
        "secret/credential-like durable memory content is denied before approval creation",
        "memory_record_created",
        "memory_record_forgotten",
    ):
        if marker.lower() not in memory_rules.lower():
            errors.append(f"MEMORY_GOVERNANCE_RULES missing marker: {marker}")

    catalog_commands = _catalog_commands()
    missing = REQUIRED_COMMANDS - catalog_commands
    if missing:
        errors.append("catalog_missing_commands:" + ",".join(sorted(missing)))
    catalog = (ROOT / "docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md").read_text(encoding="utf-8")
    for marker in (
        "implemented_approval_required",
        "metadata_only",
        "Does not execute approved action.",
    ):
        if marker not in catalog:
            errors.append(f"catalog_missing_marker:{marker}")
    code_prefixes = _literal_command_prefixes()
    catalog_prefixes = {command.split()[0] for command in catalog_commands}
    missing_prefixes = sorted(code_prefixes - catalog_prefixes)
    if missing_prefixes:
        errors.append("catalog_missing_prefixes:" + ",".join(missing_prefixes))

    if errors:
        print("Repository truthfulness validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Repository truthfulness validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
