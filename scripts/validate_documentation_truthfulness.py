# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import sys
from pathlib import Path

REQUIRED_CONTENT: dict[str, list[str]] = {
    "README.md": [
        "local-first AI assistant and coding agent",
        "docs/guide/README.md",
        "docs/architecture/README.md",
        "raiker-app",
    ],
    "docs/architecture/ARCHITECTURE.md": [
        "owner bootstrap",
        "production_ready_local_single_user_runtime",
    ],
    "docs/architecture/IMPLEMENTATION_STATUS.md": [
        "owner bootstrap",
        "acting-principal",
        "runtime_gate_manager",
        "production_ready_local_single_user_runtime",
    ],
    "docs/architecture/SECURITY_ARCHITECTURE.md": [
        "owner bootstrap",
        "owner principal",
        "runtime_gate_manager",
        "acting principal",
        "AI principal",
        "RuntimeAuthority",
        "capability_gate_state",
        "runtime_mode_state",
        "recovery",
        "approval execution relay",
    ],
    "docs/architecture/SECURITY_AND_POLICY.md": [
        "owner bootstrap",
        "ready",
    ],
    "docs/architecture/API_AND_CONTRACT_SCHEMAS.md": [
        "runtime_mode_state",
        "capability_gate_state",
        "persisted principal",
        "runtime-readiness",
    ],
    "docs/architecture/CONTRACTS.md": [
        "Runtime mode activation contract",
        "Capability gate transition contract",
        "Principal resolution contract",
    ],
    "docs/architecture/GAP_AND_TODO_ANALYSIS.md": [
        "Completed items",
        "no longer active gaps",
    ],
}

STALE_PHRASES = [
    "production_ready_local_single_user_runtime_candidate",
    "runtime_enablement_candidate_with_limitations",
]


def check_required_content(root: Path) -> list[str]:
    errors: list[str] = []
    for rel_path, required_terms in REQUIRED_CONTENT.items():
        full_path = root / rel_path
        if not full_path.exists():
            errors.append(f"missing_doc:{rel_path}")
            continue
        text = full_path.read_text(encoding="utf-8")
        text_lower = text.lower()
        for term in required_terms:
            if term.lower() not in text_lower:
                errors.append(f"missing_content:{term} in {rel_path}")
    return errors


def check_no_stale_phrases(root: Path) -> list[str]:
    errors: list[str] = []
    for rel_path in list(REQUIRED_CONTENT.keys()):
        full_path = root / rel_path
        if not full_path.exists():
            continue
        text = full_path.read_text(encoding="utf-8")
        for phrase in STALE_PHRASES:
            if phrase in text:
                lines = text.splitlines()
                for i, line in enumerate(lines, 1):
                    if phrase in line and "previous state" not in line and "changelog" not in line:
                        errors.append(
                            f"stale_phrase:{phrase} in {rel_path}:{i} (mark as historical context)"
                        )
    return errors


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    errors: list[str] = []

    errors.extend(check_required_content(root))
    errors.extend(check_no_stale_phrases(root))

    if errors:
        print("validate_documentation_truthfulness: FAILED")
        for err in errors:
            print(f"  FAIL: {err}")
        return 1

    print("validate_documentation_truthfulness: PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
