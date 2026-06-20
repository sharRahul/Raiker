from __future__ import annotations

import subprocess
from pathlib import Path


def test_phase_status_validation_script_passes() -> None:
    result = subprocess.run(
        ["python", "scripts/validate_phase_status.py"], check=False, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "passed" in result.stdout


def test_required_github_workflows_exist() -> None:
    ci = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    phase = Path(".github/workflows/phase-status.yml").read_text(encoding="utf-8")
    assert "python -m pytest" in ci
    assert "python -m ruff check ." in ci
    assert "python -m mypy raiker apps tests" in ci
    assert "python scripts/validate_phase_status.py" in phase


def test_active_phase_3_status_docs_align_on_completion_and_blocked_phase_4() -> None:
    docs = [
        Path("README.md"),
        Path("docs/PHASE_3_COMPLETION_AUDIT.md"),
        Path("docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md"),
        Path("docs/EVENT_CATALOG.md"),
    ]
    for path in docs:
        text = path.read_text(encoding="utf-8")
        assert "Phase 4 remains blocked" in text or "Phase 4 is not complete" in text
    assert "All Phase 3 slices A through P are implemented, tested, and documented." in Path(
        "README.md"
    ).read_text(encoding="utf-8")
    assert "**Phase 3 can be marked complete.**" in Path(
        "docs/PHASE_3_COMPLETION_AUDIT.md"
    ).read_text(encoding="utf-8")
