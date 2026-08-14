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
        "Approval resolution executes approved local file mutations",
        "CLI durable memory mutation is `implemented_approval_required`",
        "container read tools, governed local commands",
        "Sensitive finance/investment/medical/pregnancy/CCTV/",
        "Phase 4 memory MVP is implemented",
    ],
    Path("docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md"): [
        "implemented_approval_required",
        "metadata_only",
        "Each is executed once through its governed execution relay",
    ],
    Path("docs/EVENT_CATALOG.md"): [
        "approval_denied",
        "tool_started",
        "tool_completed",
        "tool_failed",
    ],
    Path("docs/SECURITY_ARCHITECTURE.md"): [
        "Approval resolution executes a narrow allowlist",
        "SSH remote execution | unavailable until owner profile selection; approval-required",
        "Daytona cloud execution | unavailable until owner profile, credential reference, and cost ceiling; approval-required",
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
