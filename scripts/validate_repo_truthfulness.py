# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = [ROOT / "README.md", *(ROOT / "docs").glob("*.md")]
CANONICAL_DOCS = [
    ROOT / "README.md",
    ROOT / "docs/architecture/ARCHITECTURE.md",
    ROOT / "docs/architecture/IMPLEMENTATION_STATUS.md",
    ROOT / "docs/architecture/FEATURE_COVERAGE_MATRIX.md",
    ROOT / "docs/architecture/GAP_AND_TODO_ANALYSIS.md",
    ROOT / "docs/architecture/SECURITY_AND_POLICY.md",
    ROOT / "docs/architecture/SECURITY_ARCHITECTURE.md",
    ROOT / "docs/architecture/MEMORY_GOVERNANCE_RULES.md",
    ROOT / "docs/architecture/RAIKER_TOOL_AND_PLUGIN_CATALOG.md",
    ROOT / "docs/architecture/LOCAL_VALIDATION_GATE.md",
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
    "/trace <session_id> <turn_id>",
    "/launch --provider <provider> --model <model>",
    "/quit",
    "/runtime-mode",
    "/runtime-mode status",
    "/runtime-mode activate <mode_name> [--reason <reason>]",
    "/runtime-mode disable [--reason <reason>]",
    "/capability-gates",
    "/capability-gate <capability>",
    "/capability-gate enable <capability> --state <state> [--reason <reason>]",
    "/capability-gate disable <capability> [--reason <reason>]",
    "/runtime-readiness",
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
    # BUG-06 narrowed this guard rather than removing it. Resolution really does
    # execute an approved *file mutation* now, so a flat ban on "approval
    # resolution executes" would forbid the truth. What must stay forbidden is
    # the **unbounded** claim — that approving runs whatever was approved.
    "approval resolution executes any",
    "approval resolution executes every",
    "approval resolution executes the approved action",
    "approving executes any action",
)

# Wording that correctly states the boundary. A doc discussing approval
# resolution must carry one of these: either the old flat metadata-only claim
# (still true of every capability outside the relayed pair) or a phrasing that
# names what executes *and* that everything else does not.
APPROVAL_BOUNDARY_MARKERS = (
    "approval resolution is metadata-only",
    "does not execute approved action",
    "metadata-only for every other capability",
    "metadata-only for every capability except",
    "for every capability except an approved",
    "metadata-only otherwise",
    "executes exactly one narrow class of action",
    "executes a narrow allowlist",
    "metadata-only: it records the human decision",
    "records the decision and executes nothing",
)


def _catalog_commands() -> set[str]:
    text = (ROOT / "docs/architecture/RAIKER_TOOL_AND_PLUGIN_CATALOG.md").read_text(encoding="utf-8")
    match = re.search(r"## CLI Command Surface.*?```text\n(.*?)\n```", text, re.S)
    if not match:
        return set()
    return {line.strip() for line in match.group(1).splitlines() if line.strip()}


def _literal_command_prefixes() -> set[str]:
    tree = ast.parse((ROOT / "raiker/cli/commands.py").read_text(encoding="utf-8"))
    prefixes: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value.startswith("/")
        ):
            prefixes.add(node.value.split()[0])
    return {prefix for prefix in prefixes if prefix not in {"/exit", "/"}}


def _validate_snippet(name: str, text: str) -> list[str]:
    lowered = text.lower()
    errors: list[str] = []
    if (
        any(
            token in name for token in ("IMPLEMENTATION_STATUS", "SECURITY", "TOOL", "ARCHITECTURE")
        )
        and "metadata-only" not in lowered
        and "metadata only" not in lowered
    ):
        errors.append(f"{name} missing metadata-only wording")
    if ("approval resolution" in lowered or "/approve" in lowered) and not any(
        marker in lowered for marker in APPROVAL_BOUNDARY_MARKERS
    ):
        errors.append(f"{name} missing approval execution-boundary wording")
    if (
        "no-executor" not in lowered
        and "fail closed" not in lowered
        and "fail-closed" not in lowered
        and "disabled/deferred" not in lowered
    ):
        errors.append(f"{name} missing fail-closed/deferred wording")
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

    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in CANONICAL_DOCS if path.exists()
    )
    for status in CANONICAL_STATUSES:
        if status not in combined:
            errors.append(f"missing_canonical_status:{status}")
    for marker in REQUIRED_DISABLED_MARKERS:
        if marker not in combined:
            errors.append(f"missing_disabled_runtime_marker:{marker}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    normalized_readme = " ".join(readme.split())
    for marker in (
        "web dashboard and terminal client are available",
        "hosted multi-user",
        "docs/guide/README.md",
        "docs/architecture/README.md",
    ):
        if marker.lower() not in normalized_readme.lower():
            errors.append(f"README missing truth marker: {marker}")

    architecture = (ROOT / "docs/architecture/ARCHITECTURE.md").read_text(encoding="utf-8")
    for marker in (
        "Current Backend Capability Matrix",
        "checkpoint_created` and `turn_closed` are gateway finalisation events",
        "sessions: deferred; no `/sessions` command is currently implemented",
    ):
        if marker not in architecture:
            errors.append(f"ARCHITECTURE missing marker: {marker}")

    security_arch = (ROOT / "docs/architecture/SECURITY_ARCHITECTURE.md").read_text(encoding="utf-8")
    for marker in (
        "SSH remote execution | unavailable until owner profile selection",
        "Daytona cloud execution | unavailable until owner profile",
        "finance, medical, pregnancy, CCTV, home security, hardware | disabled/fail-closed",
        "Approval resolution executes a narrow allowlist",
        "remains metadata-only: it records the decision and executes nothing",
        "no tamper-proof logging is implemented",
    ):
        if marker.lower() not in security_arch.lower():
            errors.append(f"SECURITY_ARCHITECTURE missing marker: {marker}")

    memory_rules = (ROOT / "docs/architecture/MEMORY_GOVERNANCE_RULES.md").read_text(encoding="utf-8")
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
    catalog = (ROOT / "docs/architecture/RAIKER_TOOL_AND_PLUGIN_CATALOG.md").read_text(encoding="utf-8")
    for marker in (
        "implemented_approval_required",
        "metadata_only",
        "executed once through the governed approval execution relay",
        "metadata-only for every other capability",
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
