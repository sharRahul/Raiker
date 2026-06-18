from __future__ import annotations

from pathlib import Path

REQUIRED_PHASE_2_ROWS = [
    "Side-question child-turn contract",
    "Read-only side-question runtime",
    "Interrupt/steer action contracts",
    "Safe-boundary interrupt handling",
    "Approval inbox service",
    "Approval terminal commands",
    "Checkpoint restore/fork planning",
    "stat_path and diff_files tools",
    "write_file/edit_file/apply_patch",
    "git status/diff/log wrappers",
    "Local provider health-check",
    "Memory candidate listing",
]

REQUIRED_DOCS = [
    Path("README.md"),
    Path("docs/PHASE_3_BUILD_PLAN.md"),
    Path("docs/PHASE_3_COMPLETION_AUDIT.md"),
    Path("docs/PHASE_4_BUILD_PLAN.md"),
    Path("docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md"),
    Path("docs/EVENT_CATALOG.md"),
    Path("EVENT_CATALOG.md"),
]

REQUIRED_IMPLEMENTATION_STATUS_MARKERS = [
    "Phase 3 rollout slice A status",
    "RAIKER-3501 read-only rich workspace view/API foundation | `implemented_verified`",
    "`/workspace-view` safe terminal snapshot command | `implemented_verified`",
    "All Phase 3 slices A through P are implemented, tested, and documented.",
    "Phase 3 is now marked `implemented_verified` per the completion audit",
    "All runtime execution remains disabled. Phase 4 remains blocked.",
]

REQUIRED_STATUS_FILES = {
    Path("README.md"): [
        "All Phase 3 slices A through P are implemented, tested, and documented.",
        "Runtime execution remains disabled.",
        "Phase 4 is not complete",
    ],
    Path("docs/PHASE_3_COMPLETION_AUDIT.md"): [
        "**Phase 3 can be marked complete.**",
        "Runtime execution remains disabled.",
        "Phase 4 remains blocked.",
    ],
    Path("docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md"): [
        "Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`.",
        "Phase 4 remains blocked.",
    ],
    Path("docs/EVENT_CATALOG.md"): [
        "Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`.",
        "Phase 4 remains blocked.",
    ],
    Path("EVENT_CATALOG.md"): [
        "Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`.",
        "Phase 4 remains blocked.",
    ],
}

REQUIRED_DISABLED_GATES_MARKER = (
    "Preserved disabled gates: plugin execution, graph/codemap runtime indexing, semantic/vector memory writes, external channels, subagents, multi-agent teams, remote execution, and container execution"
)


def main() -> int:
    status = Path("docs/IMPLEMENTATION_STATUS.md").read_text(encoding="utf-8")
    missing: list[str] = []
    for row in REQUIRED_PHASE_2_ROWS:
        marker = f"| {row} | `phase_2_required` | `implemented_verified`"
        if marker not in status:
            missing.append(row)
    for marker in REQUIRED_IMPLEMENTATION_STATUS_MARKERS:
        if marker not in status:
            missing.append(marker)
    if REQUIRED_DISABLED_GATES_MARKER not in status:
        missing.append(REQUIRED_DISABLED_GATES_MARKER)
    for doc in REQUIRED_DOCS:
        if not doc.exists():
            missing.append(str(doc))
    for doc, markers in REQUIRED_STATUS_FILES.items():
        if not doc.exists():
            continue
        text = doc.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                missing.append(f"{doc}:{marker}")
    if missing:
        print("Phase/status validation failed:")
        for item in missing:
            print(f"- {item}")
        return 1
    print("Phase/status validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
