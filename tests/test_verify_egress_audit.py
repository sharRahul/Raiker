import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT = Path(__file__).parents[1] / "scripts" / "verify_egress_audit.py"


def _run(
    tmp_path: Path, records: list[dict[str, Any]], *extra: str
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    capture = tmp_path / "capture.jsonl"
    report = tmp_path / "report.json"
    capture.write_text("\n".join(json.dumps(record) for record in records) + "\n")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--capture", str(capture), "--scope", "local-only", "--output", str(report), *extra],
        check=False,
        capture_output=True,
        text=True,
    )
    return result, json.loads(report.read_text())


def test_egress_audit_approves_a_thirty_minute_local_only_capture(tmp_path: Path) -> None:
    result, report = _run(
        tmp_path,
        [
            {"timestamp": "2026-11-02T10:00:00Z", "host": "127.0.0.1"},
            {"timestamp": "2026-11-02T10:30:00Z", "host": "127.0.0.1"},
        ],
        "--allowed-host", "127.0.0.1",
    )
    assert result.returncode == 0
    assert report["approved"] is True
    assert report["duration_seconds"] == 1800
    assert report["observed_hosts"] == ["127.0.0.1"]
    assert "authorization" not in json.dumps(report).lower()


def test_egress_audit_refuses_unexpected_destination_and_short_capture(tmp_path: Path) -> None:
    result, report = _run(
        tmp_path,
        [
            {"timestamp": "2026-11-02T10:00:00Z", "host": "127.0.0.1"},
            {"timestamp": "2026-11-02T10:01:00Z", "host": "example.invalid"},
        ],
        "--allowed-host", "127.0.0.1",
    )
    assert result.returncode == 2
    assert report["approved"] is False
    assert report["unexpected_hosts"] == ["example.invalid"]
    assert len(report["reasons"]) == 2


def test_release_audit_minimum_cannot_be_shortened(tmp_path: Path) -> None:
    capture = tmp_path / "capture.jsonl"
    capture.write_text('{"timestamp":"2026-11-02T10:00:00Z","host":"127.0.0.1"}\n')
    report = tmp_path / "report.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--capture", str(capture), "--scope", "local-only",
         "--output", str(report), "--minimum-seconds", "1", "--allowed-host", "127.0.0.1"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 2
    assert "at least 1800" in result.stderr
    assert not report.exists()
