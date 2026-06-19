from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = [ROOT / "README.md", *(ROOT / "docs").glob("*.md"), ROOT / "EVENT_CATALOG.md"]
RUNTIME_DISABLED_MARKERS = [
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
]
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
    "/approval-previews",
    "/graph-approval-preview",
    "/memory-approval-preview [--summary]",
    "/approval-preview <preview_id>",
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
    "/doctor",
    "/channels",
    "/launch --provider mock --model mock-deterministic",
    "/quit",
}


def _slash_prefix(command: str) -> str:
    token = command.split()[0]
    if token in {"/model", "/reasoning"}:
        return token
    return token


def _readme_commands() -> set[str]:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
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
    return {p for p in prefixes if p not in {"/exit"}}


def main() -> int:
    errors: list[str] = []
    readme_commands = _readme_commands()
    missing = REQUIRED_COMMANDS - readme_commands
    if missing:
        errors.append("README CLI Command Surface missing: " + ", ".join(sorted(missing)))
    code_prefixes = _literal_command_prefixes()
    readme_prefixes = {_slash_prefix(c) for c in readme_commands}
    missing_prefixes = code_prefixes - readme_prefixes
    if missing_prefixes:
        errors.append("README command list omits implemented command prefixes: " + ", ".join(sorted(missing_prefixes)))

    catalog = (ROOT / "docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md").read_text(encoding="utf-8")
    for command in REQUIRED_COMMANDS:
        if f"`{command}`" not in catalog:
            errors.append(f"Tool/plugin catalog missing implemented command row: {command}")
    stale = []
    for path in DOCS:
        text = path.read_text(encoding="utf-8")
        if "No — Phase 3 planned" in text:
            stale.append(str(path.relative_to(ROOT)))
        if "full Desktop" in text and "specified/deferred" not in text and "not implemented" not in text:
            errors.append(f"{path.relative_to(ROOT)} may imply full Desktop implementation without qualification")
    if stale:
        errors.append("Unreconciled 'No — Phase 3 planned' rows: " + ", ".join(stale))

    required_truth = [
        "current launchable UI is a simple terminal/CLI shell",
        "Desktop/Web/Dashboard/Mobile apps",
        "specified/deferred, not implemented",
        "safe foundation/readiness slices A-P",
        "Phase 4 remains blocked",
        "runtime execution remains disabled",
    ]
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    for marker in required_truth:
        if marker.lower() not in readme_text.lower():
            errors.append(f"README missing truthfulness marker: {marker}")

    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    phase = (ROOT / ".github/workflows/phase-status.yml").read_text(encoding="utf-8")
    if "pull_request:" not in ci or "push:" not in ci or "branches:" not in ci or "- main" not in ci:
        errors.append("README/workflow mismatch: ci.yml is expected to run on pull_request and push to main")
    if "workflow_dispatch:" not in phase:
        errors.append("README/workflow mismatch: phase-status.yml is expected to remain workflow_dispatch")
    if "Workflows are currently `workflow_dispatch` only" in readme_text:
        errors.append("README incorrectly says all workflows are workflow_dispatch-only")

    status_text = (ROOT / "docs/IMPLEMENTATION_STATUS.md").read_text(encoding="utf-8")
    for marker in RUNTIME_DISABLED_MARKERS:
        if marker not in readme_text + status_text + catalog:
            errors.append(f"Missing runtime-disabled marker: {marker}")
    if errors:
        print("Repository truthfulness validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Repository truthfulness validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
