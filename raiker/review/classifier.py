from __future__ import annotations

import re

from raiker.review.diff_parser import classify_file
from raiker.review.models import ReviewFinding, ReviewInput

# Disabled runtime capability flags that must stay false. An added line that enables any of
# them is a Phase 3/4 scope-expansion signal during Phase 2.5.
_DISABLED_FLAGS = (
    "plugin_execution",
    "graph_indexing",
    "semantic_memory_writes",
    "vector_writes",
    "embedding_creation",
    "approval_execution",
    "approval_relay_runtime",
    "cleanup_execution",
    "rollback_execution",
    "external_channels",
    "notifications",
    "remote_execution",
    "container_execution",
    "cloud_execution",
    "process_execution",
    "shell_execution",
    "network_execution",
    "runtime_execution",
)
_FLAG_ENABLE_RE = re.compile(
    r"\b(" + "|".join(_DISABLED_FLAGS) + r")_enabled\b\s*[:=]\s*(?:true|1|yes|on)\b",
    re.IGNORECASE,
)
# Documentation/runtime activation overclaims for deferred surfaces.
_RUNTIME_CLAIM_RES = (
    re.compile(
        r"\b(?:desktop|web|dashboard|mobile|ide)\s*(?:ui|app|extension)\b.{0,40}"
        r"\b(?:implemented|complete|completed|shipped|live|enabled)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\brest\s*api\b.{0,40}\b(?:implemented|complete|completed|server|live)\b",
        re.IGNORECASE,
    ),
)
# Risky runtime activation introduced by added code. Labels are reported, never raw lines.
_RUNTIME_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(?:import\s+subprocess|from\s+subprocess\b)"), "subprocess_import"),
    (
        re.compile(r"\bsubprocess\.(?:run|Popen|call|check_output|check_call)\b"),
        "subprocess_call",
    ),
    (re.compile(r"\basyncio\.create_subprocess_(?:exec|shell)\b"), "subprocess_call"),
    (re.compile(r"\bos\.(?:system|popen)\s*\("), "os_system"),
    (re.compile(r"\bpty\.spawn\s*\("), "shell_spawn"),
    (re.compile(r"\b(?:import\s+socket\b|socket\.socket\s*\()"), "socket_use"),
    (
        re.compile(
            r"\b(?:import\s+requests\b|requests\.(?:get|post|put|delete|patch|request)\s*\()"
        ),
        "network_client",
    ),
    (
        re.compile(r"\bhttpx\.(?:get|post|put|delete|patch|Client|AsyncClient)\b"),
        "network_client",
    ),
    (re.compile(r"\burllib\.request\b"), "network_client"),
    (
        re.compile(
            r"\b(?:threading\.Thread\s*\(|multiprocessing\.Process\s*\(|"
            r"watchdog\.observers|FileSystemEventHandler|start_background_worker)"
        ),
        "background_worker",
    ),
)


def _added_text(input_bundle: ReviewInput) -> str:
    from raiker.review.diff_parser import parse_unified_diff

    parsed = parse_unified_diff(input_bundle.diff_text)
    return "\n".join(parsed.added_lines)


def _detect_scope(added_text: str) -> list[str]:
    labels: set[str] = set()
    for match in _FLAG_ENABLE_RE.finditer(added_text):
        labels.add(f"{match.group(1).lower()}_enabled")
    for pattern in _RUNTIME_CLAIM_RES:
        if pattern.search(added_text):
            labels.add("runtime_activation_claim")
    return sorted(labels)


def _detect_runtime(added_text: str) -> list[str]:
    labels: set[str] = set()
    for pattern, label in _RUNTIME_PATTERNS:
        if pattern.search(added_text):
            labels.add(label)
    return sorted(labels)


def generate_findings(input_bundle: ReviewInput) -> list[ReviewFinding]:
    """Produce deterministic rule-based findings for a review input.

    Detection runs against the already-redacted, bounded diff. No raw secret, file content,
    or diff text is ever placed into a finding; only safe labels/counts are reported.
    """

    findings: list[ReviewFinding] = []
    files = list(input_bundle.files)
    classes = [classify_file(path) for path in files]
    code_files = [path for path, kind in zip(files, classes, strict=True) if kind == "code"]
    test_files = [path for path, kind in zip(files, classes, strict=True) if kind == "test"]
    has_changes = bool(files)
    only_docs = has_changes and all(kind == "doc" for kind in classes)
    only_tests = has_changes and all(kind == "test" for kind in classes)
    added_text = _added_text(input_bundle)

    if code_files and not test_files:
        findings.append(
            ReviewFinding(
                finding_id="missing-tests",
                severity="medium",
                category="tests",
                title="Source changed without matching test changes",
                description=(
                    "Source files changed but no test files changed in the same review scope."
                ),
                evidence="Source files changed but no test files changed.",
                recommendation="Add or update focused tests for the changed behavior.",
                confidence="medium",
            )
        )

    if only_docs:
        findings.append(
            ReviewFinding(
                finding_id="docs-only",
                severity="info",
                category="docs",
                title="Documentation-only change",
                description="Only documentation files changed in this review scope.",
                evidence="All changed files are documentation files.",
                recommendation="No code review action required for documentation-only edits.",
                confidence="high",
            )
        )

    if only_tests:
        findings.append(
            ReviewFinding(
                finding_id="test-only",
                severity="info",
                category="tests",
                title="Test-only change",
                description="Only test files changed in this review scope.",
                evidence="All changed files are test files.",
                recommendation="Confirm the tests cover the intended behavior.",
                confidence="high",
            )
        )

    if input_bundle.redaction_applied:
        findings.append(
            ReviewFinding(
                finding_id="secret-introduced",
                severity="high",
                category="security",
                title="Possible secret introduced",
                description=(
                    "The diff contains content matching secret/token/credential patterns. "
                    "The matched value is redacted and never surfaced."
                ),
                evidence="Secret-like content detected and redacted; raw value withheld.",
                recommendation=(
                    "Remove the secret from the change and rotate it; use a secrets manager."
                ),
                confidence="medium",
            )
        )

    scope_labels = _detect_scope(added_text)
    if scope_labels:
        findings.append(
            ReviewFinding(
                finding_id="scope-expansion",
                severity="high",
                category="scope",
                title="Possible Phase 3/4 scope expansion",
                description=(
                    "The diff appears to enable disabled runtime capability or claim activation "
                    "of a deferred surface during Phase 2.5."
                ),
                evidence="Detected scope signals: " + ", ".join(scope_labels) + ".",
                recommendation=(
                    "Keep disabled runtime flags false and avoid Phase 3/4 activation in this scope."
                ),
                confidence="medium",
            )
        )

    runtime_labels = _detect_runtime(added_text)
    if runtime_labels:
        findings.append(
            ReviewFinding(
                finding_id="unsafe-runtime",
                severity="high",
                category="security",
                title="Potential unsafe runtime activation",
                description=(
                    "Added code appears to introduce shell/process/network or background "
                    "worker/watcher activation."
                ),
                evidence="Detected runtime signals: " + ", ".join(runtime_labels) + ".",
                recommendation=(
                    "Route any such capability through brokered, policy-gated, read-only wrappers."
                ),
                confidence="medium",
            )
        )

    if input_bundle.truncated:
        findings.append(
            ReviewFinding(
                finding_id="review-truncated",
                severity="info",
                category="maintainability",
                title="Review was truncated",
                description="The diff or file set exceeded review bounds and was truncated.",
                evidence="Review context exceeded max_files or max_diff_chars and was bounded.",
                recommendation="Narrow the scope (use --path) or raise review bounds to review fully.",
                confidence="high",
            )
        )

    return sort_findings(findings)


def sort_findings(findings: list[ReviewFinding]) -> list[ReviewFinding]:
    from raiker.review.models import SEVERITY_RANK

    return sorted(
        findings,
        key=lambda finding: (
            -SEVERITY_RANK[finding.severity],
            finding.category,
            finding.finding_id,
        ),
    )
