# SPDX-License-Identifier: Apache-2.0
"""BD-5 (beta plan) — a real model in Build fixes a failing test within three attempts.

Drives a running ``raiker-web`` over loopback, as its owner, with whatever model
the host serves for Build (the beta round serves a 7B GGUF on the owner's GPU):

1. a disposable repository with one bug and the test that catches it;
2. a project that declares ``python -m unittest discover -q`` as its check, the repository
   selected, and a session command grant for exactly that check;
3. one Build turn asking for the fix. Every write and command the agent
   proposes is approved by the owner here, and every attempt is recorded;
4. the turn's own outcome (``completed_verified`` only when the declared check
   ran after the last change and passed) and each command run's exit.

Passes when the outcome is ``completed_verified`` within three runs of the
check. The report lists every attempt.

    python scripts/live_build_fix_loop.py --base http://127.0.0.1:8765 --workspace <ws> \\
        --user Rahul --password-env RAIKER_LIVE_PASSWORD --report bd5.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# The standard library's runner: the command sandbox reaches only a system
# Python, and pytest is often installed for the owner's account alone.
CHECK = "python -m unittest discover -q"
BUGGY = "def average(values):\n    return sum(values) / (len(values) + 1)\n"
TEST = (
    "import unittest\n\nfrom stats import average\n\n\n"
    "class AverageTest(unittest.TestCase):\n"
    "    def test_average_of_three(self):\n        self.assertEqual(average([2, 4, 6]), 4)\n\n"
    "    def test_average_of_one(self):\n        self.assertEqual(average([5]), 5)\n"
)


class Host:
    def __init__(self, base: str) -> None:
        self.base = base
        self.token = ""
        self.csrf = ""

    def call(self, method: str, path: str, body: Any = None, *, timeout: float = 600) -> Any:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(f"{self.base}{path}", data=data, method=method)  # noqa: S310 — loopback
        request.add_header("Content-Type", "application/json")
        if self.token:
            request.add_header("Authorization", f"Bearer {self.token}")
        if self.csrf:
            request.add_header("X-CSRF-Token", self.csrf)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 — loopback
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise SystemExit(f"{method} {path} answered {exc.code}: {exc.read()[:400]!r}") from None
        return json.loads(raw) if raw else None


def _git(root: Path, *args: str) -> None:
    subprocess.run(  # noqa: S603 - fixed argv
        ["git", "-C", str(root), "-c", "user.name=BD5", "-c", "user.email=bd5@example.invalid", *args],
        check=True, capture_output=True,
    )


def _seed(workspace: Path) -> Path:
    # A fresh folder each run: Git's object files are read-only on Windows.
    repo = workspace / f"bd5-stats-{int(time.time())}"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    (repo / "stats.py").write_text(BUGGY, encoding="utf-8")
    (repo / "test_stats.py").write_text(TEST, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "a bug and the test that catches it")
    return repo


def _turn_on(host: Host, capability: str, *, acknowledge: bool = False) -> None:
    if acknowledge:
        host.call("POST", f"/api/capability-gates/{capability}/threat-ack", {"reason": "BD-5 live fix loop"})
    body: dict[str, Any] = {"target_state": "enabled_runtime", "reason": "BD-5 live fix loop"}
    if acknowledge:
        body["confirmation_token"] = CONFIRMATION_WORD
    host.call("POST", f"/api/capability-gates/{capability}/set", body)


#: The word the gate's confirmation step asks the owner to type; not a secret.
CONFIRMATION_WORD = "confirm"


def run(args: argparse.Namespace) -> dict[str, Any]:
    workspace = Path(args.workspace)
    repo = _seed(workspace)
    host = Host(args.base)
    login = host.call("POST", "/api/auth/login", {"username": args.user, "password": os.environ[args.password_env]})
    host.token, host.csrf = str(login["token"]), str(login.get("csrf_token") or "")
    for capability in ("file_write_execution", "patch_apply_execution", "approval_execution_relay"):
        _turn_on(host, capability)
    _turn_on(host, "host_network_code_execution", acknowledge=True)
    project = host.call("POST", "/api/projects", {"name": f"BD-5 fix loop {int(time.time())}"})["project_id"]
    host.call("PUT", f"/api/projects/{project}/context", {"instructions": "", "attachment_ids": [], "checks": [CHECK]})
    repo_id = host.call("POST", "/api/code/repos", {"kind": "local", "path": repo.name})["repo_id"]
    host.call("PUT", "/api/code/repos/selection", {"repo_id": repo_id})
    first = host.call("POST", "/api/prompts", {
        "text": "Look at the repository.", "surface": "build", "project_id": project, "capability_modes": {},
        "model_profile": args.profile, "model": args.model,
    })
    session = str(first["session_id"])
    host.call("PUT", f"/api/sessions/{session}/command-grant", {
        "commands": [CHECK.split()], "timeout_seconds": 180, "ttl_minutes": 60,
    })
    attempts: list[dict[str, Any]] = []
    answer = host.call("POST", "/api/prompts", {
        "text": (
            f"test_stats.py fails. Fix the bug in stats.py so that `{CHECK}` passes. "
            f"Edit the file with the write tool, then run `{CHECK}` with the command tool "
            "and read its output. If it still fails, fix it again. Make at most three attempts, "
            "and report each attempt."
        ),
        "surface": "build", "project_id": project, "session_id": session, "capability_modes": {},
        "model_profile": args.profile, "model": args.model,
    })
    turn = str(answer["turn_id"])
    for _ in range(12):
        if answer.get("status") != "needs_approval":
            break
        approval = answer["approval"]
        attempts.append({"approved": approval.get("tool_name"), "summary": approval.get("summary", "")[:160]})
        approval_id = str(approval["approval_id"])
        host.call("POST", f"/api/approvals/{approval_id}/resolve", {"approve": True, "reason": "owner approves"})
        answer = host.call("POST", f"/api/approvals/{approval_id}/resume")
    runs = host.call("GET", f"/api/command-runs?session_id={session}")
    rows = runs if isinstance(runs, list) else runs.get("runs", [])
    checks = [
        {"command": row.get("safe_display"), "state": row.get("state"), "exit": row.get("exit_code")}
        for row in rows
    ]
    outcome = host.call("GET", f"/api/sessions/{session}/turns/{turn}/outcome")
    return {
        "scenario": "BD-5 fix a failing test within three attempts",
        "session_id": session,
        "turn_id": turn,
        "final_status": answer.get("status"),
        "final_message": str(answer.get("message", ""))[-1200:],
        "approvals": attempts,
        "check_runs": checks,
        "outcome": outcome.get("outcome"),
        "outcome_reason": outcome.get("reason"),
        "result": "pass" if outcome.get("outcome") == "completed_verified" and 0 < len(checks) <= 3 else "fail",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--base", default="http://127.0.0.1:8765")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--user", default="Rahul")
    parser.add_argument("--password-env", default="RAIKER_LIVE_PASSWORD")
    parser.add_argument("--profile", default="raiker-local-llama-cpp")
    parser.add_argument("--model", default="local-gguf")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    report = run(args)
    text = json.dumps(report, indent=2)
    if args.report:
        args.report.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["result"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
