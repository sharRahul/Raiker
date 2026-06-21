from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = [ROOT / "README.md", *(ROOT / "docs").glob("*.md")]
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
    "/graph-approval-preview",
    "/memory-approval-preview [--summary]",
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
    "/approval-previews [--json] [--status <status>] [--limit <n>]",
    "/approval-preview <preview_id> [--json]",
    "/doctor",
    "/channels",
    "/launch --provider mock --model mock-deterministic",
    "/quit",
}

# Phase 2.5 review must stay documented as local CLI-only and never claim deferred surfaces.
REVIEW_LOCAL_CLI_MARKERS = ("local CLI code review",)
REVIEW_FORBIDDEN_OVERCLAIMS = (
    "review dashboard",
    "review web ui",
    "review desktop ui",
    "ide review ui",
    "github pr review automation is complete",
    "semantic review intelligence is complete",
)

# Phase 3 Slice A proposal lifecycle must stay metadata-only/proposal-only and must never
# claim execution/apply/approval/PR/UI/runtime capabilities.
PROPOSAL_LIFECYCLE_FORBIDDEN_OVERCLAIMS = (
    "proposal execution is complete",
    "proposal execution is implemented",
    "auto-fix is complete",
    "auto-fix is implemented",
    "patch application is complete",
    "patch application is implemented",
    "approval execution is complete",
    "github pr automation is complete",
    "proposal apply is implemented",
    "apply-fixes is implemented",
)


def _slash_prefix(command: str) -> str:
    token = command.split()[0]
    if token in {"/model", "/reasoning"}:
        return token
    return token


def _catalog_commands() -> set[str]:
    # The canonical CLI command surface lives in the tool/plugin catalog (the README is a
    # conventional overview and no longer carries the full ledger).
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
    return {p for p in prefixes if p not in {"/exit", "/"}}


def _ci_has_active_triggers() -> bool:
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    return "pull_request:" in ci and "push:" in ci


def _has_test_only_launch_wording(text: str) -> bool:
    lowered = text.lower()
    return "/launch --provider mock --model mock-deterministic" in text and "test-only" in lowered and "deterministic_test_provider_requires_test_mode" in text


def main() -> int:
    errors: list[str] = []
    catalog_commands = _catalog_commands()
    missing = REQUIRED_COMMANDS - catalog_commands
    if missing:
        errors.append("Catalog CLI Command Surface missing: " + ", ".join(sorted(missing)))
    code_prefixes = _literal_command_prefixes()
    catalog_prefixes = {_slash_prefix(c) for c in catalog_commands}
    missing_prefixes = code_prefixes - catalog_prefixes
    if missing_prefixes:
        errors.append("Catalog command list omits implemented command prefixes: " + ", ".join(sorted(missing_prefixes)))

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
        "current launchable UI is the plain local terminal client only",
        "Rich/native TUI is Phase 8 deferred work",
        "Desktop/Web/Dashboard/Mobile/IDE/Voice/Browser Extension/REST/API clients are Phase 8 deferred",
        "specified but not implemented",
        "safe foundation/readiness slices A-P",
        "Phase 4 memory MVP is implemented",
        "runtime execution remains disabled",
    ]
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    for marker in required_truth:
        if marker.lower() not in readme_text.lower():
            errors.append(f"README missing truthfulness marker: {marker}")
    combined_docs = "\n".join(path.read_text(encoding="utf-8") for path in DOCS)
    forbidden_phase8 = ("there is no Phase 8", "numbering jumps 7→9", "numbering jumps 7->9")
    for phrase in forbidden_phase8:
        if phrase.lower() in combined_docs.lower():
            errors.append(f"Docs contain stale Phase 8 wording: {phrase}")
    forbidden_active_ui = ("native Textual Rich TUI by default", "Textual TUI front-end", "default Rich TUI")
    for phrase in forbidden_active_ui:
        if phrase.lower() in combined_docs.lower():
            errors.append(f"Docs still imply active Rich/Textual runtime: {phrase}")
    if "Phase 8" not in combined_docs or "UI/client" not in combined_docs:
        errors.append("Docs must define Phase 8 as the UI/client phase")

    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    phase = (ROOT / ".github/workflows/phase-status.yml").read_text(encoding="utf-8")
    if "pull_request:" not in ci or "push:" not in ci or "branches:" not in ci or "- main" not in ci:
        errors.append("README/workflow mismatch: ci.yml is expected to run on pull_request and push to main")
    if "workflow_dispatch:" not in phase:
        errors.append("README/workflow mismatch: phase-status.yml is expected to remain workflow_dispatch")
    if "Workflows are currently `workflow_dispatch` only" in readme_text:
        errors.append("README incorrectly says all workflows are workflow_dispatch-only")



    architecture = (ROOT / "docs/ARCHITECTURE.md").read_text(encoding="utf-8")
    phase3_line = next((line for line in architecture.splitlines() if line.startswith("| Phase 3 |")), "")
    if not phase3_line:
        errors.append("ARCHITECTURE missing Phase 3 row")
    elif not all(marker in phase3_line for marker in ["target platform architecture", "safe foundation/readiness", "Phase 8"]):
        errors.append("ARCHITECTURE Phase 3 row must separate target platform architecture, completed A-P readiness scope, and Phase 8 deferred runtime/app work")
    overclaim_terms = ["Desktop UI, Web UI, Dashboard, Apple mobile app, Android mobile app, plugin manager, semantic search, graph/codemap, REST API, worktree isolation."]
    if any(term in phase3_line and "safe foundation/readiness" not in phase3_line for term in overclaim_terms):
        errors.append("ARCHITECTURE Phase 3 row overclaims full app/runtime features")

    matrix = (ROOT / "docs/FEATURE_COVERAGE_MATRIX.md").read_text(encoding="utf-8")
    if "Current implementation status" not in matrix:
        errors.append("FEATURE_COVERAGE_MATRIX must separate specification status from current implementation status")
    deferred_rows = [
        "Desktop UI", "Web UI", "Dashboard", "IDE extension", "Apple mobile app", "Android mobile app",
        "Semantic/vector memory", "Graph memory/code map", "Recursive CTE graph queries",
        "Hosted/cloud inference", "Scheduled automations", "OpenClaw-style gateway and channels",
    ]
    qualifiers = ("contract-only", "readiness-only", "metadata-only", "deferred", "specified only", "policy-gated")
    for row_name in deferred_rows:
        row = next((line for line in matrix.splitlines() if line.startswith(f"| {row_name} |")), "")
        if "phase-3" in row and not any(q in row.lower() for q in qualifiers):
            errors.append(f"FEATURE_COVERAGE_MATRIX row lacks deferred/current implementation qualifier: {row_name}")

    acceptance = (ROOT / "docs/ACCEPTANCE_TESTS_BY_PHASE.md").read_text(encoding="utf-8")
    if "Completed Phase 3 A-P safe foundation/readiness acceptance" not in acceptance or "Deferred platform acceptance after Phase 3 A-P" not in acceptance:
        errors.append("ACCEPTANCE_TESTS_BY_PHASE must split completed Phase 3 A-P acceptance from deferred platform acceptance")
    if "not required" not in acceptance.lower():
        errors.append("ACCEPTANCE_TESTS_BY_PHASE must state deferred platform acceptance is not required for current Phase 3 A-P completion")

    local_gate = (ROOT / "docs/LOCAL_VALIDATION_GATE.md").read_text(encoding="utf-8")
    if _ci_has_active_triggers() and "GitHub Actions are temporarily paused" in local_gate:
        errors.append("LOCAL_VALIDATION_GATE incorrectly claims all Actions/CI are paused while ci.yml has active triggers")
    for marker in ["CI triggers are configured", "hosted CI may stay red or unavailable", "Local validation evidence is required", "phase-status.yml` remains manual"]:
        if marker not in local_gate:
            errors.append(f"LOCAL_VALIDATION_GATE missing CI quota truth marker: {marker}")

    if "/launch --provider mock --model mock-deterministic" in catalog and not _has_test_only_launch_wording(catalog):
        errors.append("Catalog must mark /launch --provider mock --model mock-deterministic as test-only/policy-blocked, not normal production CLI")


    security_arch = ROOT / "docs" / "SECURITY_ARCHITECTURE.md"
    if not security_arch.exists():
        errors.append("Missing docs/SECURITY_ARCHITECTURE.md")
    else:
        security_text = security_arch.read_text(encoding="utf-8")
        security_lower = security_text.lower()
        link_sources = readme_text + "\n" + architecture
        if "docs/security_architecture.md" not in link_sources.lower() and "security_architecture.md" not in link_sources.lower():
            errors.append("README or ARCHITECTURE must link docs/SECURITY_ARCHITECTURE.md")
        required_security_markers = [
            "current launchable interface is the plain local terminal client only",
            "rich/native tui, desktop, web, dashboard, mobile, ide, voice, browser extension, and rest/api clients are phase 8 deferred",
            "runtime execution capabilities remain disabled",
            "deterministic/mock providers are test-only",
            "specified/deferred, not active runtime",
            "shell/process execution | disabled/deferred",
            "plugin execution | disabled/deferred",
            "remote/container/cloud execution | disabled/deferred",
        ]
        for marker in required_security_markers:
            if marker not in security_lower:
                errors.append(f"SECURITY_ARCHITECTURE missing truthfulness marker: {marker}")
        forbidden_security_claims = [
            "plugin execution is implemented",
            "remote execution is implemented",
            "web/api clients are implemented",
            "deterministic/mock providers are production fallback",
        ]
        for phrase in forbidden_security_claims:
            if phrase in security_lower:
                errors.append(f"SECURITY_ARCHITECTURE may overclaim security/runtime status: {phrase}")
        if "tamper-proof logging is implemented" in security_lower or "immutable storage is implemented" in security_lower:
            errors.append("SECURITY_ARCHITECTURE must not claim implemented tamper-proof or immutable logging")

    status_text = (ROOT / "docs/IMPLEMENTATION_STATUS.md").read_text(encoding="utf-8")
    for marker in RUNTIME_DISABLED_MARKERS:
        if marker not in readme_text + status_text + catalog:
            errors.append(f"Missing runtime-disabled marker: {marker}")

    review_docs = readme_text + "\n" + catalog
    for marker in REVIEW_LOCAL_CLI_MARKERS:
        if marker not in review_docs:
            errors.append(f"Review docs missing local-CLI-only marker: {marker}")
    lowered_review_docs = review_docs.lower()
    for overclaim in REVIEW_FORBIDDEN_OVERCLAIMS:
        if overclaim in lowered_review_docs:
            errors.append(f"Review docs overclaim deferred surface: {overclaim}")

    proposal_docs = (
        readme_text
        + "\n"
        + (ROOT / "docs/IMPLEMENTATION_STATUS.md").read_text(encoding="utf-8")
        + "\n"
        + catalog
        + "\n"
        + (ROOT / "docs/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md").read_text(encoding="utf-8")
    )
    lowered_proposal_docs = proposal_docs.lower()
    for overclaim in PROPOSAL_LIFECYCLE_FORBIDDEN_OVERCLAIMS:
        if overclaim in lowered_proposal_docs:
            errors.append(f"Proposal lifecycle docs overclaim deferred capability: {overclaim}")
    if "proposal lifecycle foundation: implemented_verified" not in proposal_docs:
        errors.append("Proposal lifecycle docs missing implemented_verified marker")

    if errors:
        print("Repository truthfulness validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Repository truthfulness validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
