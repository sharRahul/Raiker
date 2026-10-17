"""Prove a built or installed desktop host works on the machine it is on.

DIST-07. A package that builds is not a package that runs. This drives the
frozen host exactly as the desktop window does — ``--no-browser --ready-file``
— against a fresh, empty profile, and checks what an owner's first minutes
depend on:

1. the host starts and reports ready within the window's own timeout;
2. ``/api/health`` answers with the encrypted store open and FTS5 search;
3. the built web app is served, so the window has something to show;
4. the provenance record beside the host is readable and states whether the
   build was signed;
5. the first-run path works: the owner account is created, setup state is read
   and saved, the system check answers, and the installation check reports no
   failed mandatory component;
6. the host quits on request, and a second start over the same profile opens the
   same data (restart, and the account survives it).

It uses only the standard library, and needs no credential and no network: a
model provider is not part of what an installation must prove, and the check
says so rather than pretending to test one.

    python -m raiker.app.desktop_smoke --host desktop-dist/Raiker/Raiker
"""

from __future__ import annotations

import argparse
import json
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

READY_TIMEOUT_SECONDS = 180.0
EXIT_TIMEOUT_SECONDS = 60.0


class SmokeFailure(AssertionError):
    """One check failed; the message says which and why."""


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _request(
    url: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    token: str | None = None,
    timeout: float = 30.0,
) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, method=method)  # noqa: S310 - loopback URL
    if data is not None:
        request.add_header("Content-Type", "application/json")
    if token is not None:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            raw = response.read()
            status = response.status
    except urllib.error.HTTPError as error:
        raw = error.read()
        status = error.code
    try:
        return status, json.loads(raw) if raw else None
    except ValueError:
        return status, raw.decode("utf-8", "replace")


def _wait_ready(ready_file: Path, process: subprocess.Popen[bytes], log: Path) -> str:
    deadline = time.monotonic() + READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if ready_file.is_file():
            try:
                record = json.loads(ready_file.read_text(encoding="utf-8"))
                return str(record["url"])
            except (ValueError, KeyError):
                pass
        if process.poll() is not None:
            raise SmokeFailure(
                f"host exited with {process.returncode} before it was ready:\n{_tail(log)}"
            )
        time.sleep(0.25)
    raise SmokeFailure(f"host was not ready within {READY_TIMEOUT_SECONDS:.0f}s:\n{_tail(log)}")


def _tail(log: Path, lines: int = 40) -> str:
    try:
        return "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
    except OSError:
        return "(no log)"


def _start(host: Path, workspace: Path, port: int, log: Path) -> tuple[subprocess.Popen[bytes], str]:
    ready_file = workspace.parent / f"ready-{port}.json"
    ready_file.unlink(missing_ok=True)
    handle = log.open("ab")
    process = subprocess.Popen(  # noqa: S603 - the host under test, fixed argv
        [str(host), "--workspace", str(workspace), "--port", str(port),
         "--no-browser", "--ready-file", str(ready_file)],
        stdin=subprocess.DEVNULL,
        stdout=handle,
        stderr=subprocess.STDOUT,
    )
    return process, _wait_ready(ready_file, process, log)


def _quit(host: Path, workspace: Path, port: int, process: subprocess.Popen[bytes]) -> None:
    subprocess.run(  # noqa: S603 - the host under test, fixed argv
        [str(host), "quit", "--workspace", str(workspace), "--port", str(port), "--force"],
        check=False,
        timeout=EXIT_TIMEOUT_SECONDS,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        process.wait(timeout=EXIT_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        raise SmokeFailure("host did not stop when asked to quit") from None


def check(condition: bool, message: str, results: list[str]) -> None:
    if not condition:
        raise SmokeFailure(message)
    results.append(f"PASS {message}")


def _provenance(host: Path, results: list[str], *, expect_signed: bool | None) -> None:
    record_path = host.parent / "installation.json"
    if not record_path.is_file():
        results.append("SKIP provenance record (not a release build)")
        return
    record = json.loads(record_path.read_text(encoding="utf-8"))
    check(record.get("distribution") == "desktop", "provenance names the desktop distribution", results)
    signed = bool(record.get("signing", {}).get("applied"))
    if expect_signed is not None:
        check(signed == expect_signed, f"provenance says signed={expect_signed}", results)
    results.append(f"INFO version {record.get('version')} target {record.get('target')} signed={signed}")


def run(host: Path, *, expect_signed: bool | None = None, keep: bool = False) -> list[str]:
    """Run every check; return the evidence lines, or raise :class:`SmokeFailure`."""
    results: list[str] = []
    if not host.is_file():
        raise SmokeFailure(f"no host executable at {host}")
    _provenance(host, results, expect_signed=expect_signed)
    scratch = Path(tempfile.mkdtemp(prefix="raiker-smoke-"))
    workspace = scratch / "profile"
    log = scratch / "host.log"
    port = _free_port()
    process, url = _start(host, workspace, port, log)
    results.append(f"PASS host ready at {url}")
    try:
        status, health = _request(f"{url}api/health")
        check(status == 200 and isinstance(health, dict) and health.get("status") == "ok",
              "health answers ok", results)
        assert isinstance(health, dict)
        check(health.get("store") == "ok", "encrypted store opens", results)
        check(health.get("text_search_engine") == "fts5", "full-text search is FTS5", results)
        status, page = _request(url)
        check(status == 200 and isinstance(page, str) and "<html" in page.lower(),
              "web app is served", results)

        status, boot = _request(f"{url}api/auth/bootstrap-status")
        check(status == 200 and isinstance(boot, dict) and boot.get("can_register") is True,
              "fresh profile offers owner registration", results)
        password = secrets.token_urlsafe(18) + "Aa1!"
        status, login = _request(f"{url}api/auth/register", method="POST",
                                 body={"username": "smoke-owner", "password": password})
        check(status == 200 and isinstance(login, dict) and bool(login.get("token")),
              "owner account is created", results)
        assert isinstance(login, dict)
        token = str(login["token"])
        status, setup = _request(f"{url}api/setup", token=token)
        check(status == 200 and isinstance(setup, dict) and setup.get("status") == "required",
              "first-run setup is required on a fresh profile", results)
        status, system = _request(f"{url}api/setup/system", token=token)
        check(status == 200 and isinstance(system, dict) and bool(system.get("checks")),
              "system check answers", results)
        assert isinstance(system, dict)
        blocking = [c["id"] for c in system["checks"] if c.get("state") == "fail"]
        check(not blocking, f"system check has no blocking failure {blocking}", results)
        status, verify = _request(f"{url}api/setup/verify", method="POST", token=token, body={})
        check(status == 200 and isinstance(verify, dict), "installation check answers", results)
        assert isinstance(verify, dict)
        failed = [c["id"] for c in verify.get("checks", []) if c.get("state") == "fail"]
        check(not failed, f"installation check has no failed mandatory component {failed}", results)
        status, saved = _request(f"{url}api/setup", method="PUT", token=token,
                                 body={"status": "in_progress", "stage": "model"})
        check(status == 200 and isinstance(saved, dict) and saved.get("stage") == "model",
              "setup progress is saved", results)
    finally:
        _quit(host, workspace, port, process)
    results.append("PASS host quits on request")

    process, url = _start(host, workspace, port, log)
    try:
        status, boot = _request(f"{url}api/auth/bootstrap-status")
        check(status == 200 and isinstance(boot, dict) and boot.get("can_register") is False,
              "restart opens the same profile (owner account survives)", results)
        status, login = _request(f"{url}api/auth/login", method="POST",
                                 body={"username": "smoke-owner", "password": password})
        check(status == 200 and isinstance(login, dict) and bool(login.get("token")),
              "owner signs in after restart", results)
        assert isinstance(login, dict)
        status, setup = _request(f"{url}api/setup", token=str(login["token"]))
        check(status == 200 and isinstance(setup, dict) and setup.get("stage") == "model",
              "setup progress survives restart", results)
    finally:
        _quit(host, workspace, port, process)
    if not keep:
        import shutil

        shutil.rmtree(scratch, ignore_errors=True)
    else:
        results.append(f"INFO kept {scratch}")
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--host", required=True, help="The frozen or installed host executable.")
    signed = parser.add_mutually_exclusive_group()
    signed.add_argument("--expect-signed", dest="expect_signed", action="store_const", const=True)
    signed.add_argument("--expect-unsigned", dest="expect_signed", action="store_const", const=False)
    parser.add_argument("--keep", action="store_true", help="Keep the scratch profile and log.")
    parser.add_argument("--report", default=None, help="Also write the evidence lines here.")
    args = parser.parse_args(argv)
    try:
        lines = run(Path(args.host), expect_signed=args.expect_signed, keep=args.keep)
        code = 0
    except SmokeFailure as failure:
        lines = [f"FAIL {failure}"]
        code = 1
    for line in lines:
        print(line, flush=True)
    if args.report:
        Path(args.report).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return code


if __name__ == "__main__":
    sys.exit(main())
