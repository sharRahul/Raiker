"""BR-D01 — what a Build turn may truthfully claim about the change it made.

A plausible patch, or the model saying it ran the tests, is not a verified
outcome. This reads two records the runtime wrote itself — the turn's tool
actions and its command runs — against the checks the *owner* declared for the
project, and names the strongest claim those records support:

* ``no_change`` — the turn wrote nothing, so there is nothing to verify.
* ``completed_verified`` — every declared check ran, exactly as written, after
  the turn's last file change, and exited 0.
* ``completed_unverified`` — files changed, and no checks are declared, or one
  never ran after the last change.
* ``failed`` — a declared check ran after the last change and exited non-zero.
* ``blocked`` — a declared check is waiting for the owner's approval.
* ``outcome_unknown`` — a check timed out, was cancelled or lost, or is still
  running, so its result is not known.

The commands are the owner's and the results are the runtime's; the model can
neither declare a check nor fake its exit code. Run order is compared at the
one-second resolution both records use, so a check started in the same second
as the last write counts as after it.
"""

from __future__ import annotations

import json
import shlex
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Literal

from raiker.models.tool_registry import FAMILY_FILE_WRITE, TOOL_DEFINITIONS

BuildOutcome = Literal[
    "no_change", "completed_verified", "completed_unverified", "failed", "blocked", "outcome_unknown"
]
CheckResult = Literal["passed", "failed", "not_run", "ran_before_change", "waiting", "unknown"]

#: Tools whose success changes a file the owner has.
WRITE_TOOLS: frozenset[str] = frozenset(
    item.name for item in TOOL_DEFINITIONS if item.family == FAMILY_FILE_WRITE
)
COMMAND_TOOLS: frozenset[str] = frozenset({"run_command", "shell"})
_UNKNOWN_STATES = frozenset({"timed_out", "cancelled", "contained", "lost", "queued", "starting", "running", "finalizing"})

_REASONS: dict[str, str] = {
    "no_change": "This turn changed no files.",
    "completed_verified": "Every check you declared ran after the last change and passed.",
    "completed_unverified": "Files changed, and not every check you declared ran after the last change.",
    "no_checks": "Files changed. No checks are declared for this project, so nothing verified the change.",
    "failed": "A check you declared ran after the last change and failed.",
    "blocked": "A check you declared is waiting for your approval.",
    "outcome_unknown": "A check you declared did not finish, so its result is not known.",
}


def _tokens(command: str) -> tuple[str, ...]:
    try:
        return tuple(shlex.split(command))
    except ValueError:
        return tuple(command.split())


def _command_of(row: Mapping[str, Any]) -> str:
    try:
        arguments = json.loads(str(row.get("arguments_json") or "{}"))
    except (TypeError, ValueError):
        return ""
    if not isinstance(arguments, dict):
        return ""
    value = arguments.get("command") or arguments.get("cmd") or ""
    if isinstance(value, list):
        return shlex.join(str(part) for part in value)
    return str(value)


def classify_build_turn(
    *,
    tool_actions: Iterable[Mapping[str, Any]],
    command_runs: Iterable[Mapping[str, Any]],
    checks: Sequence[str],
) -> dict[str, Any]:
    """The outcome a Build turn's own records support, with one row per declared check."""
    actions = list(tool_actions)
    writes = [
        row for row in actions
        if str(row.get("tool_name") or "") in WRITE_TOOLS and row.get("status") == "success"
    ]
    last_write = max((str(row.get("completed_at") or row.get("proposed_at") or "") for row in writes), default="")
    if not writes:
        return {"outcome": "no_change", "writes": 0, "checks": [], "reason": _REASONS["no_change"]}

    runs = sorted(command_runs, key=lambda row: str(row.get("started_at") or row.get("created_at") or ""))
    waiting = [
        _tokens(_command_of(row)) for row in actions
        if str(row.get("tool_name") or "") in COMMAND_TOOLS and row.get("status") == "approval_required"
    ]
    rows: list[dict[str, Any]] = []
    for check in checks:
        wanted = _tokens(check)
        matching = [run for run in runs if _tokens(str(run.get("safe_display") or "")) == wanted]
        after = [run for run in matching if str(run.get("started_at") or run.get("created_at") or "") >= last_write]
        result: CheckResult
        exit_code: int | None = None
        run_id: str | None = None
        if after:
            latest = after[-1]
            run_id = str(latest.get("run_id") or "") or None
            state = str(latest.get("state") or "")
            raw_exit = latest.get("exit_code")
            exit_code = int(raw_exit) if isinstance(raw_exit, int) else None
            if state in _UNKNOWN_STATES or exit_code is None:
                result = "unknown"
            else:
                result = "passed" if exit_code == 0 else "failed"
        elif wanted in waiting:
            result = "waiting"
        elif matching:
            result = "ran_before_change"
        else:
            result = "not_run"
        rows.append({"command": check, "result": result, "exit_code": exit_code, "run_id": run_id})

    results = {row["result"] for row in rows}
    outcome: BuildOutcome
    if not checks:
        outcome, reason = "completed_unverified", _REASONS["no_checks"]
    elif "failed" in results:
        outcome, reason = "failed", _REASONS["failed"]
    elif "unknown" in results:
        outcome, reason = "outcome_unknown", _REASONS["outcome_unknown"]
    elif "waiting" in results:
        outcome, reason = "blocked", _REASONS["blocked"]
    elif results == {"passed"}:
        outcome, reason = "completed_verified", _REASONS["completed_verified"]
    else:
        outcome, reason = "completed_unverified", _REASONS["completed_unverified"]
    return {"outcome": outcome, "writes": len(writes), "checks": rows, "reason": reason}
