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

Three further facts can only lower a claim, never raise one:

* **Where a check ran.** A declared check counts only in the selected
  repository's folder. The same command run anywhere else reads
  ``wrong_directory``, because ``pytest`` at the workspace root checks a
  different tree.
* **Destination read-back.** Each file the turn wrote is read back from disk.
  A file that is no longer there means nothing on disk is what was checked, so
  the turn cannot be ``completed_verified``.
* **Target drift.** When the folder, repository, branch or command environment
  the turn started on has changed since, the checks ran against a target that
  is not the one now in front of the owner, so the turn is not verified either.

The commands are the owner's and the results are the runtime's; the model can
neither declare a check nor fake its exit code. Run order is compared at the
one-second resolution both records use, so a check started in the same second
as the last write counts as after it.
"""

from __future__ import annotations

import json
import shlex
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from raiker.models.tool_registry import FAMILY_FILE_WRITE, TOOL_DEFINITIONS

BuildOutcome = Literal[
    "no_change", "completed_verified", "completed_unverified", "failed", "blocked", "outcome_unknown"
]
CheckResult = Literal[
    "passed", "failed", "not_run", "ran_before_change", "waiting", "unknown", "wrong_directory"
]
ReadBack = Literal["matches", "present", "changed_since", "missing", "unreadable"]

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
    "readback_missing": "Every check passed, but a file this turn wrote is no longer on disk.",
    "target_changed": "Every check passed, but the folder, repository, branch or environment this turn started on has changed since.",
    "review_high": "Every check passed, but the review of the current patch has a high-severity finding.",
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


def _arguments(row: Mapping[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(str(row.get("arguments_json") or "{}"))
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _patch_paths(patch: str) -> list[tuple[str, bool]]:
    """Each file a unified diff touches, and whether it should still exist."""
    paths: list[tuple[str, bool]] = []
    previous = ""
    for line in patch.splitlines():
        if line.startswith("--- "):
            previous = line[4:].split("\t")[0].strip()
        elif line.startswith("+++ "):
            target = line[4:].split("\t")[0].strip()
            if target == "/dev/null":
                name, keep = previous, False
            else:
                name, keep = target, True
            name = name[2:] if name[:2] in {"a/", "b/"} else name
            if name and name != "/dev/null":
                paths.append((name, keep))
    return paths


def read_back_writes(
    tool_actions: Iterable[Mapping[str, Any]], workspace_root: str | Path
) -> list[dict[str, Any]]:
    """BR-D01 — read each file the turn wrote back from disk, once per path.

    ``matches``: a whole-file write is on disk exactly as written, or an edit's
    new text is still there. ``present``: a patched or generated file exists
    (its exact bytes are not known from the call). ``changed_since``: the file is
    there but no longer holds what this turn wrote — a later change, which does
    not undo this turn's verification. ``missing``: it is gone. Paths resolve
    through the read authority, so this can never read outside the workspace.
    """
    from raiker.tools.filesystem import resolve_workspace_path

    root = Path(workspace_root).resolve()
    expected: dict[str, tuple[str, str | None, bool]] = {}
    for row in tool_actions:
        name = str(row.get("tool_name") or "")
        if name not in WRITE_TOOLS or row.get("status") != "success":
            continue
        args = _arguments(row)
        if name == "apply_patch":
            for path, keep in _patch_paths(str(args.get("patch") or "")):
                expected[path] = ("present" if keep else "absent", None, keep)
            continue
        path = str(args.get("path") or "").strip()
        if not path:
            continue
        if name == "write_file":
            expected[path] = ("exact", str(args.get("text") or ""), True)
        elif name == "edit_file":
            expected[path] = ("contains", str(args.get("new_text") or ""), True)
        else:
            expected[path] = ("present", None, True)
    rows: list[dict[str, Any]] = []
    for path, (mode, text, keep) in expected.items():
        state: ReadBack
        try:
            target = resolve_workspace_path(root, path)
        except Exception:  # noqa: BLE001 — an unreadable destination is stated
            rows.append({"path": path, "state": "unreadable"})
            continue
        if not keep:
            state = "matches" if not target.exists() else "changed_since"
        elif not target.is_file():
            state = "missing"
        elif mode == "present":
            state = "present"
        else:
            try:
                content = target.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                rows.append({"path": path, "state": "unreadable"})
                continue
            same = content == text if mode == "exact" else bool(text) and (text or "") in content
            state = "matches" if same else "changed_since"
        rows.append({"path": path, "state": state})
    return rows


def classify_build_turn(
    *,
    tool_actions: Iterable[Mapping[str, Any]],
    command_runs: Iterable[Mapping[str, Any]],
    checks: Sequence[str],
    expected_cwd: str | None = None,
    readback: Sequence[Mapping[str, Any]] = (),
    target_drift: Sequence[str] = (),
    review: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """The outcome a Build turn's own records support, with one row per declared check.

    ``expected_cwd`` is the workspace-relative folder a check must run in (the
    selected repository's); ``None`` accepts any folder. ``readback`` is
    :func:`read_back_writes`; ``target_drift`` is the list of target fields that
    moved since the turn began. ``review`` is the stored review of the patch
    in the working tree now (BR-D04), when one was taken; a high-severity
    finding on it keeps the turn short of verified.
    """
    actions = list(tool_actions)
    writes = [
        row for row in actions
        if str(row.get("tool_name") or "") in WRITE_TOOLS and row.get("status") == "success"
    ]
    last_write = max((str(row.get("completed_at") or row.get("proposed_at") or "") for row in writes), default="")
    if not writes:
        return {
            "outcome": "no_change",
            "writes": 0,
            "checks": [],
            "reason": _REASONS["no_change"],
            "readback": [],
            "target_drift": [],
            "review": None,
        }

    runs = sorted(command_runs, key=lambda row: str(row.get("started_at") or row.get("created_at") or ""))
    waiting = [
        _tokens(_command_of(row)) for row in actions
        if str(row.get("tool_name") or "") in COMMAND_TOOLS and row.get("status") == "approval_required"
    ]
    rows: list[dict[str, Any]] = []
    for check in checks:
        wanted = _tokens(check)
        same_command = [run for run in runs if _tokens(str(run.get("safe_display") or "")) == wanted]
        matching = [
            run for run in same_command
            if expected_cwd is None or _folder(run.get("cwd")) == _folder(expected_cwd)
        ]
        after = [run for run in matching if str(run.get("started_at") or run.get("created_at") or "") >= last_write]
        elsewhere = [
            run for run in same_command
            if run not in matching
            and str(run.get("started_at") or run.get("created_at") or "") >= last_write
        ]
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
        elif elsewhere:
            result = "wrong_directory"
            run_id = str(elsewhere[-1].get("run_id") or "") or None
        elif matching:
            result = "ran_before_change"
        else:
            result = "not_run"
        ran_in: str | None
        if result == "wrong_directory":
            ran_in = _folder(elsewhere[-1].get("cwd"))
        else:
            ran_in = _folder(after[-1].get("cwd")) if after else None
        rows.append(
            {
                "command": check,
                "result": result,
                "exit_code": exit_code,
                "run_id": run_id,
                "cwd": ran_in,
            }
        )

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
    if outcome == "completed_verified":
        if any(item.get("state") == "missing" for item in readback):
            outcome, reason = "completed_unverified", _REASONS["readback_missing"]
        elif target_drift:
            outcome, reason = "completed_unverified", _REASONS["target_changed"]
        elif review is not None and int((review.get("counts") or {}).get("high") or 0) > 0:
            outcome, reason = "completed_unverified", _REASONS["review_high"]
    return {
        "outcome": outcome,
        "writes": len(writes),
        "checks": rows,
        "reason": reason,
        "readback": [dict(item) for item in readback],
        "target_drift": list(target_drift),
        "review": _review_summary(review),
    }


def _review_summary(review: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if review is None:
        return None
    counts = review.get("counts") or {}
    return {
        "fingerprint": str(review.get("fingerprint") or ""),
        "high": int(counts.get("high") or 0),
        "findings": len(review.get("findings") or []),
    }


def _folder(value: Any) -> str:
    text = str(value or ".").replace("\\", "/").strip().strip("/")
    while text.startswith("./"):
        text = text[2:]
    return text or "."
