"""BR-D06 — injected faults never turn into a verified Build outcome.

Coding autonomy that is honest only on the happy path is not safe to leave
running. Each case below injects one fault a real turn meets — a write that
failed, a check lost to a restart, a check cancelled or timed out, a run that
never reported an exit code, a provider that died before the check, a check in
the wrong folder, a destination removed after the write, the target moving
under the turn, a check still waiting for approval — on top of a turn that is
otherwise verified, and asserts the claim drops to the truthful alternative.

The happy path is asserted first, so a fixture that broke the baseline cannot
pass by accident.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest

from raiker.control.build_outcome import classify_build_turn

WRITE_AT = "2026-10-19T11:00:00Z"
CHECKS = ["pytest -q", "ruff check ."]


def _turn() -> dict[str, Any]:
    return {
        "tool_actions": [
            {
                "tool_name": "write_file",
                "status": "success",
                "completed_at": WRITE_AT,
                "arguments_json": json.dumps({"path": "repo/a.py", "text": "x = 1\n"}),
            }
        ],
        "command_runs": [
            {
                "run_id": f"cmd_{index}",
                "safe_display": check,
                "started_at": f"2026-10-19T11:00:1{index}Z",
                "state": "succeeded",
                "exit_code": 0,
                "cwd": "repo",
            }
            for index, check in enumerate(CHECKS)
        ],
        "checks": list(CHECKS),
        "expected_cwd": "repo",
        "readback": [{"path": "repo/a.py", "state": "matches"}],
        "target_drift": [],
    }


def _write_failed(turn: dict[str, Any]) -> None:
    turn["tool_actions"][0]["status"] = "failed"


def _second_write_after_checks(turn: dict[str, Any]) -> None:
    turn["tool_actions"].append({**turn["tool_actions"][0], "completed_at": "2026-10-19T11:05:00Z"})


def _lost_on_restart(turn: dict[str, Any]) -> None:
    turn["command_runs"][0].update(state="lost", exit_code=None)


def _cancelled(turn: dict[str, Any]) -> None:
    turn["command_runs"][1].update(state="cancelled", exit_code=None)


def _timed_out(turn: dict[str, Any]) -> None:
    turn["command_runs"][0].update(state="timed_out", exit_code=None)


def _still_running(turn: dict[str, Any]) -> None:
    turn["command_runs"][1].update(state="running", exit_code=None)


def _provider_died_before_checks(turn: dict[str, Any]) -> None:
    turn["command_runs"] = []


def _hidden_failure(turn: dict[str, Any]) -> None:
    turn["command_runs"][0].update(state="failed", exit_code=2)


def _wrong_folder(turn: dict[str, Any]) -> None:
    turn["command_runs"][0]["cwd"] = "."


def _destination_removed(turn: dict[str, Any]) -> None:
    turn["readback"] = [{"path": "repo/a.py", "state": "missing"}]


def _branch_switched(turn: dict[str, Any]) -> None:
    turn["target_drift"] = ["branch"]


def _folder_vanished(turn: dict[str, Any]) -> None:
    turn["target_drift"] = ["folder_exists"]


def _waiting_for_approval(turn: dict[str, Any]) -> None:
    turn["command_runs"] = turn["command_runs"][:1]
    turn["tool_actions"].append(
        {"tool_name": "shell", "status": "approval_required", "arguments_json": json.dumps({"command": CHECKS[1]})}
    )


FAULTS: dict[str, tuple[Callable[[dict[str, Any]], None], str]] = {
    "write failed": (_write_failed, "no_change"),
    "changed again after the checks": (_second_write_after_checks, "completed_unverified"),
    "check lost on restart": (_lost_on_restart, "outcome_unknown"),
    "check cancelled": (_cancelled, "outcome_unknown"),
    "check timed out": (_timed_out, "outcome_unknown"),
    "check still running": (_still_running, "outcome_unknown"),
    "provider died before the checks": (_provider_died_before_checks, "completed_unverified"),
    "hidden failing test": (_hidden_failure, "failed"),
    "check in the wrong folder": (_wrong_folder, "completed_unverified"),
    "destination removed": (_destination_removed, "completed_unverified"),
    "branch switched under the turn": (_branch_switched, "completed_unverified"),
    "folder vanished under the turn": (_folder_vanished, "completed_unverified"),
    "check waiting for approval": (_waiting_for_approval, "blocked"),
}


def test_the_baseline_is_verified() -> None:
    assert classify_build_turn(**_turn())["outcome"] == "completed_verified"


@pytest.mark.parametrize("name", sorted(FAULTS))
def test_an_injected_fault_is_never_verified(name: str) -> None:
    inject, expected = FAULTS[name]
    turn = _turn()
    inject(turn)
    outcome = classify_build_turn(**turn)
    assert outcome["outcome"] == expected, (name, outcome)
    assert outcome["outcome"] != "completed_verified"
    assert outcome["reason"]
