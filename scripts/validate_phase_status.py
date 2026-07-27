# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path

REQUIRED_DOCS = [
    Path("README.md"),
    Path("docs/IMPLEMENTATION_STATUS.md"),
    Path("docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md"),
    Path("docs/EVENT_CATALOG.md"),
    Path("docs/SECURITY_ARCHITECTURE.md"),
]
REQUIRED_MARKERS = {
    Path("docs/IMPLEMENTATION_STATUS.md"): [
        "Canonical Backend Capability Statuses",
        "Approval resolution is `metadata_only` for every capability except",
        "CLI durable memory mutation is `implemented_approval_required`",
        "Integrated real executors (including graph indexing, semantic/vector runtimes, plugin execution slices, channel runtime, container, scheduled routines, model-provider runtime, and local email/calendar/reminder stores) are `implemented_policy_gated`/governed per action; remote/cloud command execution and sensitive finance/investment/medical/pregnancy/CCTV/home-security/hardware domains remain `disabled_deferred` and fail closed.",
        "Phase 4 memory MVP is implemented",
    ],
    Path("docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md"): [
        "implemented_approval_required",
        "metadata_only",
        # BUG-06: resolution executes a file mutation through the relay and
        # nothing else. The catalogue must keep saying which half is which.
        "executed once through the governed approval execution relay",
    ],
    Path("docs/EVENT_CATALOG.md"): [
        "approval_denied",
        "tool_started",
        "tool_completed",
        "tool_failed",
    ],
    Path("docs/SECURITY_ARCHITECTURE.md"): [
        "Approval resolution executes exactly one narrow class of action",
        "remote execution | disabled/fail-closed",
        "cloud execution | disabled/fail-closed",
    ],
}


def main() -> int:
    missing: list[str] = []
    for doc in REQUIRED_DOCS:
        if not doc.exists():
            missing.append(f"missing_doc:{doc}")
    for doc, markers in REQUIRED_MARKERS.items():
        if not doc.exists():
            continue
        text = doc.read_text(encoding="utf-8")
        for marker in markers:
            if marker.lower() not in text.lower():
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
