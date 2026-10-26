# SPDX-License-Identifier: Apache-2.0
"""BR-D06 — kill a live ``raiker-web`` mid-check, start it again, and read the outcome.

The fault fixtures in ``tests/test_build_fault_boundaries.py`` inject faults
into the classifier and the stores. This one injects the fault a person meets:
the host process dies while a Build turn's declared check is still running in
the background, and is started again on the same workspace.

It runs a real ``raiker-web`` process — real routes, gateway, broker, command
service, leases and store — with only the model scripted, so it needs no
provider credential and runs the same on a laptop and in CI:

1. a fresh workspace, an owner registered over loopback, a project whose
   declared check is ``python check.py`` and a git repository whose check
   sleeps long enough to still be running when the host dies;
2. a Build turn writes a file (accepted by the owner through the approval
   routes) and starts the check in the background under a session command grant;
3. the host is killed with ``SIGKILL`` (``TerminateProcess`` on Windows) while
   the check is running — no handler of Raiker's runs;
4. a new host is started on the same workspace, and the turn's outcome is read.

The scenario passes only when the outcome is **not** ``completed_verified`` and
names the check as not passed: a check the host never saw finish is never
evidence that a change works. Exit status 0 is a pass; the report says what was
observed either way.

    python scripts/build_restart_fault.py --report build-restart-fault.json
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
#: The throwaway owner this scenario registers on its own fresh workspace,
#: made per run so nothing here is a stored credential.
OWNER_PASSPHRASE = secrets.token_urlsafe(24)
#: What the owner types to confirm a Tier-2 capability on the Permissions page.
HUMAN_CONFIRMATION = "confirm"
#: The project's declared check: a script that passes, slowly — still running
#: when the host is killed, and certain to pass had it been left to finish.
SLOW_CHECK = "import time\n\ntime.sleep(90)\nprint('checks passed')\n"
CHECK = "python check.py"


# ── The host, with only the model scripted ─────────────────────────────────


def _scripted_responses(workspace: Path) -> list[dict[str, Any]]:
    return json.loads((workspace / "fault-script.json").read_text(encoding="utf-8"))


def _next_response(workspace: Path) -> dict[str, Any]:
    """The next scripted answer. The position survives a restart: it is on disk."""
    counter = workspace / "fault-script.position"
    position = int(counter.read_text(encoding="utf-8")) if counter.exists() else 0
    script = _scripted_responses(workspace)
    counter.write_text(str(position + 1), encoding="utf-8")
    return script[min(position, len(script) - 1)]


def serve(workspace: Path, port: int) -> int:
    """Run ``raiker-web`` on *workspace* with a scripted provider and model readiness held ready."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from collections.abc import AsyncIterator
    from datetime import UTC, datetime, timedelta

    from raiker.api import serve as serve_module
    from raiker.models.contracts import ModelResponse, ModelStreamEvent, ToolCallProposal
    from raiker.models.readiness import ModelReadiness, ModelReadinessService, ModelReadinessState
    from raiker.models.router import ModelRouter

    def respond() -> ModelResponse:
        item = _next_response(workspace)
        calls = [
            ToolCallProposal(call_id=call["call_id"], tool_name=call["tool_name"], arguments=call["arguments"])
            for call in item.get("tool_calls", [])
        ]
        return ModelResponse(text=str(item.get("text", "")), tool_calls=calls)

    async def achat(self: Any, *args: Any, **kwargs: Any) -> ModelResponse:
        return respond()

    async def astream(self: Any, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        response = respond()
        if response.text:
            yield ModelStreamEvent(event_type="text_delta", text_delta=response.text)
        for call in response.tool_calls:
            yield ModelStreamEvent(
                event_type="tool_call_delta",
                tool_call_delta={"call_id": call.call_id, "tool_name": call.tool_name, "arguments": call.arguments},
            )
        yield ModelStreamEvent(event_type="finish", finish_reason=response.finish_reason)

    def ready(service: Any, owner: str, profile: str | None, model: str | None) -> Any:
        resolved_profile, resolved_model = service.resolve_request_target(owner, profile, model)
        now = datetime.now(UTC)
        readiness = ModelReadiness(
            key=service._selected_key(owner, resolved_profile, resolved_model),  # noqa: SLF001
            state=ModelReadinessState.READY,
            checked_at=now.isoformat(),
            expires_at=(now + timedelta(minutes=30)).isoformat(),
            summary="Scripted model for the restart fault.",
            reason_code="model_ready",
            remediation="",
            evidence={"source": "build_restart_fault"},
        )
        service.store.save_model_readiness(readiness)
        return readiness

    async def ready_async(service: Any, owner: str, profile: str | None, model: str | None) -> Any:
        return ready(service, owner, profile, model)

    ModelRouter.achat = achat  # type: ignore[method-assign]
    ModelRouter.astream = astream  # type: ignore[method-assign]
    ModelReadinessService.require_ready = ready  # type: ignore[method-assign]
    ModelReadinessService.require_ready_async = ready_async  # type: ignore[method-assign]
    return int(
        serve_module.main(["--workspace", str(workspace), "--port", str(port), "--no-browser"]) or 0
    )


# ── Driving it over HTTP ───────────────────────────────────────────────────


class Host:
    def __init__(self, workspace: Path, port: int, log: Path) -> None:
        self.workspace = workspace
        self.port = port
        self.log = log
        self.process: subprocess.Popen[bytes] | None = None
        self.token = ""
        self.csrf = ""

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        env = dict(os.environ)
        handle = self.log.open("ab")
        self.process = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--serve", str(self.workspace), str(self.port)],
            stdout=handle, stderr=subprocess.STDOUT, env=env, cwd=str(ROOT),
        )
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise SystemExit(f"the host exited during start-up; see {self.log}")
            with (
                contextlib.suppress(OSError, urllib.error.URLError),
                urllib.request.urlopen(f"{self.base}/api/health", timeout=2) as response,  # noqa: S310 — loopback
            ):
                if response.status == 200:
                    return
            time.sleep(0.5)
        raise SystemExit("the host did not answer /api/health within two minutes")

    def kill(self) -> None:
        """The fault: no shutdown handler of Raiker's runs."""
        assert self.process is not None
        if sys.platform == "win32":
            self.process.kill()
        else:
            os.kill(self.process.pid, signal.SIGKILL)
        self.process.wait(timeout=30)

    def stop(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            with contextlib.suppress(subprocess.TimeoutExpired):
                self.process.wait(timeout=20)
            if self.process.poll() is None:
                self.process.kill()

    def call(self, method: str, path: str, body: Any = None, *, timeout: float = 120) -> Any:
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

    def sign_in(self, *, register: bool) -> None:
        route = "/api/auth/register" if register else "/api/auth/login"
        body = self.call("POST", route, {"username": "owner", "password": OWNER_PASSPHRASE})
        self.token = str(body["token"])
        self.csrf = str(body.get("csrf_token") or "")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=Fault", "-c", "user.email=fault@example.invalid", *args],
        check=True, capture_output=True,
    )


def _seed(workspace: Path) -> None:
    repo = workspace / "app"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    (repo / "check.py").write_text(SLOW_CHECK, encoding="utf-8")
    (repo / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")
    script = [
        {"text": "Ready to work in app."},
        {"text": "Adding a subtraction helper.", "tool_calls": [{
            "call_id": "call_write", "tool_name": "write_file",
            "arguments": {"path": "app/calc.py", "text": "def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a - b\n"},
        }]},
        {"text": "Running the project's check in the background.", "tool_calls": [{
            "call_id": "call_check", "tool_name": "run_command",
            "arguments": {"command": CHECK, "cwd": "app", "background": True},
        }]},
        {"text": "The check is running in the background."},
    ]
    (workspace / "fault-script.json").write_text(json.dumps(script), encoding="utf-8")


def _turn_on(host: Host, capability: str, *, acknowledge: bool = False) -> None:
    if acknowledge:
        # The owner's threat-model acknowledgement, recorded the way Permissions does.
        host.call(
            "POST", f"/api/capability-gates/{capability}/threat-ack",
            {"reason": "restart fault scenario: the check runs code on this host"},
        )
    body: dict[str, Any] = {"target_state": "enabled_runtime", "reason": "restart fault scenario"}
    if acknowledge:
        # A Tier-2 capability also asks for the owner's typed confirmation.
        body["confirmation_token"] = HUMAN_CONFIRMATION
    host.call("POST", f"/api/capability-gates/{capability}/set", body)


def _kill_processes_in(folder: Path) -> list[int]:
    """Kill every process working in *folder* — the check and its supervisor (Linux)."""
    killed: list[int] = []
    proc = Path("/proc")
    if not proc.is_dir():
        return killed
    target = str(folder.resolve())
    for entry in proc.iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            cwd = os.readlink(entry / "cwd")
        except OSError:
            continue
        if cwd == target or cwd.startswith(target + os.sep):
            with contextlib.suppress(OSError):
                os.kill(int(entry.name), signal.SIGKILL)
                killed.append(int(entry.name))
    return killed


def run_scenario(workspace: Path, report: dict[str, Any], *, variant: str) -> bool:
    """``reattach``: only the host dies. ``lost``: the host and the check both die."""
    _seed(workspace)
    host = Host(workspace, _free_port(), workspace / "host.log")
    try:
        host.start()
        host.sign_in(register=True)
        for capability in ("file_write_execution", "patch_apply_execution", "approval_execution_relay"):
            _turn_on(host, capability)
        _turn_on(host, "host_network_code_execution", acknowledge=True)
        project = host.call("POST", "/api/projects", {"name": "Restart fault"})["project_id"]
        host.call("PUT", f"/api/projects/{project}/context", {"instructions": "", "attachment_ids": [], "checks": [CHECK]})
        repo_id = host.call("POST", "/api/code/repos", {"kind": "local", "path": "app"})["repo_id"]
        host.call("PUT", "/api/code/repos/selection", {"repo_id": repo_id})

        first = host.call("POST", "/api/prompts", {
            "text": "Get ready.", "surface": "build", "project_id": project, "capability_modes": {},
        })
        session_id = str(first["session_id"])
        host.call("PUT", f"/api/sessions/{session_id}/command-grant", {
            "commands": [["python", "check.py"]], "timeout_seconds": 120, "ttl_minutes": 30,
        })
        parked = host.call("POST", "/api/prompts", {
            "text": "Add a sub helper and run the checks.", "surface": "build", "project_id": project,
            "session_id": session_id, "capability_modes": {},
        })
        turn_id = str(parked["turn_id"])
        report["turn_status_before"] = parked.get("status")
        if parked.get("status") == "needs_approval":
            approval_id = str(parked["approval"]["approval_id"])
            host.call("POST", f"/api/approvals/{approval_id}/resolve", {"approve": True, "reason": "accepted"})
            resumed = host.call("POST", f"/api/approvals/{approval_id}/resume")
            report["resumed_status"] = resumed.get("status")

        runs = host.call("GET", f"/api/command-runs?session_id={session_id}")
        rows = runs if isinstance(runs, list) else runs.get("runs", [])
        running = [row for row in rows if str(row.get("state")) in {"running", "starting", "queued"}]
        report["runs_before_kill"] = [{"state": row.get("state"), "command": row.get("safe_display")} for row in rows]
        if not running:
            report["error"] = "the check was not running when the host was to be killed"
            return False

        host.kill()
        report["killed"] = True
        if variant == "lost":
            report["check_processes_killed"] = len(_kill_processes_in(workspace / "app"))
        host.start()
        host.sign_in(register=False)
        time.sleep(2)

        outcome = host.call("GET", f"/api/sessions/{session_id}/turns/{turn_id}/outcome")
        after = host.call("GET", f"/api/command-runs?session_id={session_id}")
        after_rows = after if isinstance(after, list) else after.get("runs", [])
        report["runs_after_restart"] = [{"state": row.get("state"), "command": row.get("safe_display")} for row in after_rows]
        report["outcome"] = outcome.get("outcome")
        report["reason"] = outcome.get("reason")
        report["checks"] = outcome.get("checks")
        passed_checks = [row for row in outcome.get("checks") or [] if row.get("result") == "passed"]

        # The run the dead host was watching must not read "running" for ever:
        # once its lease lapses the new host reclaims it with an honest receipt.
        deadline = time.monotonic() + 150
        final: list[dict[str, Any]] = after_rows
        while time.monotonic() < deadline:
            listed = host.call("GET", f"/api/command-runs?session_id={session_id}")
            final = listed if isinstance(listed, list) else listed.get("runs", [])
            if final and all(str(row.get("state")) not in {"running", "starting", "queued"} for row in final):
                break
            time.sleep(3)
        report["runs_settled"] = [
            {"state": row.get("state"), "command": row.get("safe_display"), "run_id": row.get("run_id")} for row in final
        ]
        receipts = []
        for row in final:
            receipt = host.call("GET", f"/api/command-runs/{row.get('run_id')}/receipt").get("receipt")
            receipts.append({"state": (receipt or {}).get("state"), "termination_reason": (receipt or {}).get("termination_reason")})
        report["receipts"] = receipts
        settled = bool(final) and all(str(row.get("state")) not in {"running", "starting", "queued"} for row in final)
        if not settled:
            report["error"] = "the dead host's check still read as running after its lease lapsed"
        again = host.call("GET", f"/api/sessions/{session_id}/turns/{turn_id}/outcome")
        report["outcome_after_settle"] = again.get("outcome")
        unknown_while_running = outcome.get("outcome") != "completed_verified" and not passed_checks
        if variant == "lost":
            # The check died with the host: nothing may ever read it as passed.
            return unknown_while_running and settled and again.get("outcome") != "completed_verified"
        # The check outlived the host and was taken back over: the turn may read
        # verified only now, on the check's own recorded exit.
        succeeded = all(str(row.get("state")) == "succeeded" for row in final)
        return unknown_while_running and settled and (again.get("outcome") == "completed_verified") == succeeded
    finally:
        host.stop()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--serve", nargs=2, metavar=("WORKSPACE", "PORT"), help=argparse.SUPPRESS)
    parser.add_argument("--report", type=Path, help="Write what was observed to this JSON file.")
    parser.add_argument("--keep", action="store_true", help="Keep the workspaces for inspection.")
    parser.add_argument(
        "--variant", choices=("reattach", "lost", "both"), default="both",
        help="reattach: only the host dies; lost: the host and the check die (Linux).",
    )
    args = parser.parse_args(argv)
    if args.serve:
        return serve(Path(args.serve[0]), int(args.serve[1]))
    variants = ["reattach", "lost"] if args.variant == "both" else [args.variant]
    if "lost" in variants and not Path("/proc").is_dir():
        variants.remove("lost")
    reports: list[dict[str, Any]] = []
    for variant in variants:
        workspace = Path(tempfile.mkdtemp(prefix=f"raiker-restart-fault-{variant}-"))
        report: dict[str, Any] = {"scenario": f"BR-D06 host killed mid-check ({variant})", "workspace": str(workspace)}
        try:
            ok = run_scenario(workspace, report, variant=variant)
        except SystemExit as exc:
            ok = False
            report["error"] = str(exc)
        finally:
            log = workspace / "host.log"
            report["host_log_tail"] = log.read_text(encoding="utf-8", errors="replace")[-2000:] if log.exists() else ""
            if not args.keep:
                shutil.rmtree(workspace, ignore_errors=True)
        report["result"] = "pass" if ok else "fail"
        reports.append(report)
    text = json.dumps({"scenarios": reports}, indent=2, sort_keys=True)
    if args.report:
        args.report.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if all(item["result"] == "pass" for item in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
