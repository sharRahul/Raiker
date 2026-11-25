"""RU-08 — `raiker doctor` prints the local checks with their fixes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from raiker.cli import main as cli


def _report(ready: bool) -> dict[str, Any]:
    return {
        "ready": ready,
        "blocking": [] if ready else ["memory"],
        "checks": [
            {"id": "os", "label": "Operating system", "state": "pass", "detail": "Windows 11", "remedy": ""},
            {
                "id": "memory",
                "label": "Memory",
                "state": "pass" if ready else "fail",
                "detail": "3 GB",
                "remedy": "Raiker needs at least 4 GB of memory.",
            },
        ],
    }


@pytest.mark.parametrize("ready", [True, False])
def test_doctor_says_each_check_and_the_fix_for_a_failure(
    ready: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("raiker.app.system_check.system_readiness", lambda _root: _report(ready))
    code = cli.main(["doctor", "--workspace", str(tmp_path)])
    out = capsys.readouterr().out
    assert "[ok  ] Operating system: Windows 11" in out
    if ready:
        assert code == 0
        assert "Ready:" in out
        assert "Fix:" not in out
    else:
        assert code == 1
        assert "[FAIL] Memory: 3 GB" in out
        assert "Fix: Raiker needs at least 4 GB of memory." in out


def test_doctor_json_is_the_wizards_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("raiker.app.system_check.system_readiness", lambda _root: _report(True))
    assert cli.main(["doctor", "--json", "--workspace", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["ready"] is True


def test_doctor_runs_on_this_machine(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = cli.main(["doctor", "--workspace", str(tmp_path)])
    out = capsys.readouterr().out
    assert code in {0, 1}
    assert "Operating system" in out
