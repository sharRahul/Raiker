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
    Path("docs/PHASE_3_BUILD_PLAN.md"),
    Path("docs/PHASE_4_BUILD_PLAN.md"),
]


def main() -> int:
    status = Path("docs/IMPLEMENTATION_STATUS.md").read_text(encoding="utf-8")
    missing: list[str] = []
    for row in REQUIRED_PHASE_2_ROWS:
        marker = f"| {row} | `phase_2_required` | `implemented_verified`"
        if marker not in status:
            missing.append(row)
    for doc in REQUIRED_DOCS:
        if not doc.exists():
            missing.append(str(doc))
    if missing:
        print("Phase/status validation failed:")
        for item in missing:
            print(f"- {item}")
        return 1
    print("Phase/status validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
