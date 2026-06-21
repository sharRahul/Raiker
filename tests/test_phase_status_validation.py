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
    assert "python -m mypy" in ci
    assert "python scripts/validate_phase_status.py" in phase


def test_phase_docs_align_on_current_backend_foundation() -> None:
    status = Path("docs/IMPLEMENTATION_STATUS.md").read_text(encoding="utf-8")
    catalog = Path("docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md").read_text(encoding="utf-8")
    security = Path("docs/SECURITY_ARCHITECTURE.md").read_text(encoding="utf-8")
    assert "Canonical Backend Capability Statuses" in status
    assert "Approval resolution is `metadata_only`" in status
    assert "implemented_approval_required" in catalog
    assert "approval resolution is metadata-only" in security.lower()
