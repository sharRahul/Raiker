from __future__ import annotations

import subprocess
from pathlib import Path


def test_phase_status_validation_script_passes() -> None:
    result = subprocess.run(["python", "scripts/validate_phase_status.py"], check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "passed" in result.stdout


def test_required_github_workflows_exist() -> None:
    ci = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    phase = Path(".github/workflows/phase-status.yml").read_text(encoding="utf-8")
    assert "python -m pytest" in ci
    assert "python -m ruff check ." in ci
    assert "python -m mypy raiker apps tests" in ci
    assert "python scripts/validate_phase_status.py" in phase
