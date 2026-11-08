# SPDX-License-Identifier: Apache-2.0
"""AG-4 / BUG-355 — kill a live ``raiker-web`` in the middle of a goal's step, restart, and read the goal.

The same harness as ``build_restart_fault.py`` (a real host, real routes,
coordinator, scheduler, leases and store, with only the model scripted), with
one difference: the step's model call is scripted to take a minute, so the
host can be killed while the step is genuinely in flight.

1. A fresh workspace, an owner, a balanced execution profile, and a goal with
   one step, accepted and started.
2. The step's task is claimed and its model call begins (the script's position
   file proves the call started).
3. The host is killed with ``SIGKILL`` (``TerminateProcess`` on Windows).
4. A new host is started on the same workspace, and the goal is read until the
   step settles.

The scenario passes when, after the restart:

* the step does not read ``running`` for ever and never reads finished: a step
  whose turn the host never saw complete is not evidence of anything;
* the goal says so in its own state rather than ``completed``;
* nothing was done twice: the goal still has exactly one task, and the model
  was not called again behind the owner's back.

    python scripts/goal_restart_fault.py --report goal-restart-fault.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_restart_fault import Host, _free_port, serve  # noqa: E402

#: The step's turn: a model call that takes a minute, then an answer.
SCRIPT = [
    {"text": "Working on the first step.", "sleep_seconds": 60},
    {"text": "First step done."},
]
SETTLED = {"done", "failed", "waiting", "blocked", "stopped", "cancelled", "paused"}


def _model_calls(workspace: Path) -> int:
    counter = workspace / "fault-script.position"
    return int(counter.read_text(encoding="utf-8")) if counter.exists() else 0


def _goal(host: Host, goal_id: str) -> dict[str, Any]:
    return dict(host.call("GET", f"/api/goals/{goal_id}"))


def _tasks_for(host: Host, goal: dict[str, Any]) -> list[str]:
    return [str(step["task_id"]) for step in goal.get("steps", []) if step.get("task_id")]


def run_scenario(workspace: Path, report: dict[str, Any]) -> bool:
    (workspace / "fault-script.json").write_text(json.dumps(SCRIPT), encoding="utf-8")
    host = Host(workspace, _free_port(), workspace / "host.log")
    try:
        host.start()
        host.sign_in(register=True)
        host.call("POST", "/api/execution-profiles", {"template": "balanced"})
        # The model is scripted, so the connection is never used; it only makes
        # the goal's model a configured one, as an owner's saved key would.
        host.call("PUT", "/api/models/anthropic-hosted/connection", {"api_key": "sk-ant-api03-" + "x" * 40})
        host.call("PUT", "/api/model-selection", {"profile_id": "anthropic-hosted", "model": "claude-haiku-4-5-20251001"})
        goal = host.call("POST", "/api/goals", {
            "title": "Restart fault",
            "model_profile": "anthropic-hosted",
            "model": "claude-haiku-4-5-20251001",
            "objective": "Prove a goal survives its host dying honestly.",
            "criteria": [{"text": "The step finishes", "mandatory": True, "validator": "steps_finish"}],
            "steps": [{"title": "Only step", "instruction": "Say hello.", "criteria": [0]}],
        })
        goal_id = str(goal["goal_id"])
        goal = host.call("POST", f"/api/goals/{goal_id}/accept", {"base_revision": goal["revision"]})
        goal = host.call("POST", f"/api/goals/{goal_id}/start", {"base_revision": goal["revision"]})
        report["started"] = {"status": goal.get("status"), "steps": [s.get("state") for s in goal.get("steps", [])]}

        # Wait for the step's model call to begin: then the host dies mid-step.
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline and _model_calls(workspace) == 0:
            time.sleep(1)
        report["model_calls_before_kill"] = _model_calls(workspace)
        if report["model_calls_before_kill"] == 0:
            report["error"] = "the step's model call never started"
            return False
        before = _goal(host, goal_id)
        report["before_kill"] = {"status": before.get("status"), "steps": [s.get("state") for s in before.get("steps", [])]}
        tasks_before = _tasks_for(host, before)

        host.kill()
        report["killed"] = True
        host.start()
        host.sign_in(register=False)

        # The step's lease lapses (two minutes) and the new host settles it.
        deadline = time.monotonic() + 240
        after = _goal(host, goal_id)
        while time.monotonic() < deadline:
            after = _goal(host, goal_id)
            states = [str(s.get("state")) for s in after.get("steps", [])]
            if states and all(state in SETTLED for state in states):
                break
            time.sleep(5)
        steps = after.get("steps", [])
        report["after_restart"] = {
            "status": after.get("status"),
            "steps": [{"state": s.get("state"), "reason": s.get("reason") or s.get("state_reason")} for s in steps],
        }
        report["model_calls_after_restart"] = _model_calls(workspace)
        tasks_after = _tasks_for(host, after)
        report["tasks"] = {"before": tasks_before, "after": tasks_after}

        states = [str(s.get("state")) for s in steps]
        settled = bool(states) and all(state in SETTLED for state in states)
        never_done = "done" not in states and after.get("status") != "completed"
        reasons = [str(s.get("reason") or "") for s in steps]
        said_why = all(reason in {"interrupted_by_restart", "run_lease_lapsed"} for reason in reasons)
        once = tasks_after == tasks_before and report["model_calls_after_restart"] == report["model_calls_before_kill"]
        if not settled:
            report["error"] = "the step still read as running after its lease lapsed"
        elif not never_done:
            report["error"] = "a step the dead host never finished read as done"
        elif not once:
            report["error"] = "the step was filed or run again after the restart"
        elif not said_why:
            report["error"] = "the step failed without saying the host stopped it"
        return settled and never_done and once and said_why
    finally:
        host.stop()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--serve", nargs=2, metavar=("WORKSPACE", "PORT"), help=argparse.SUPPRESS)
    parser.add_argument("--report", type=Path, help="Write what was observed to this JSON file.")
    parser.add_argument("--keep", action="store_true", help="Keep the workspace for inspection.")
    args = parser.parse_args(argv)
    if args.serve:
        return serve(Path(args.serve[0]), int(args.serve[1]))
    workspace = Path(tempfile.mkdtemp(prefix="raiker-goal-restart-fault-"))
    report: dict[str, Any] = {"scenario": "AG-4 host killed mid-goal-step", "workspace": str(workspace)}
    try:
        ok = run_scenario(workspace, report)
    except SystemExit as exc:
        ok = False
        report["error"] = str(exc)
    finally:
        log = workspace / "host.log"
        report["host_log_tail"] = log.read_text(encoding="utf-8", errors="replace")[-2000:] if log.exists() else ""
        if not args.keep:
            shutil.rmtree(workspace, ignore_errors=True)
    report["result"] = "pass" if ok else "fail"
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.report:
        args.report.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
