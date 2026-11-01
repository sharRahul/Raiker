"""One interpreter on one workspace script, inside the native boundary.

Local stdio MCP servers and installed plugins are both an owner-chosen program
that Raiker starts and talks to over its pipes. Neither may run on the host, so
both come here: the folder holding the script is copied into a throwaway
folder under the copy base, and the program runs there through
`raiker-command-runner` with no network. It sees itself and what it was sent,
never the rest of the project or Raiker's own state.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from raiker.execution.commands.backends.base import CommandBackendError

_PIPE_CHUNK = 65_536


class ProgramRefused(Exception):
    """The sandbox cannot hold this program's folder or one of its arguments."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass
class BoundedRun:
    """What a bounded run read back, and why it stopped if it did."""

    stdout: bytes = b""
    stderr_tail: bytes = b""
    stderr_bytes: int = 0
    overflowed: bool = False
    timed_out: bool = False
    returncode: int | None = None


#: What one program folder may bring into the sandbox. It is copied in for
#: every run, so a folder this large is refused rather than copied.
PROGRAM_FOLDER_MAX_FILES = 20_000
PROGRAM_FOLDER_MAX_BYTES = 256 * 1024 * 1024
_FOLDER_SKIP = frozenset({".git", ".raiker"})


def stage_program_folder(workspace: Path, args: list[str], target: Path) -> tuple[Path, list[str]]:
    """Copy the program's folder into *target* and re-express *args* against it.

    The program's folder is the one holding the first argument that names a
    file in the workspace: the script. Arguments naming a path are rewritten
    relative to it, and one naming a path outside it is refused, because the
    sandbox holds only that folder. Other arguments pass unchanged.
    """
    from raiker.execution.task_tree import _copy_files
    from raiker.execution.workspaces import _copy_file

    named = [(workspace / arg).resolve() for arg in args]
    script = next((path for path in named if path.is_file()), None)
    target.mkdir()
    if script is None:
        return target, list(args)
    source = script.parent
    if source != workspace and workspace not in source.parents:
        raise ProgramRefused("sandbox_argument_not_workspace_relative")
    files = [
        path
        for path in _copy_files(source)
        if not _FOLDER_SKIP.intersection(path.relative_to(source).parts[:-1])
    ]
    if len(files) > PROGRAM_FOLDER_MAX_FILES or (
        sum(path.stat().st_size for path in files) > PROGRAM_FOLDER_MAX_BYTES
    ):
        raise ProgramRefused("sandbox_program_folder_too_large")
    for path in files:
        destination = target / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        _copy_file(path, destination)
    rewritten: list[str] = []
    for arg, path in zip(args, named, strict=True):
        if not path.exists():
            rewritten.append(arg)
        elif path == source or source in path.parents:
            rewritten.append(path.relative_to(source).as_posix() or ".")
        else:
            raise ProgramRefused("sandbox_argument_outside_program_folder")
    return target, rewritten


def sandbox_interpreter(name: str, search_path: str, workspace: Path) -> Path:
    """The first *name* on *search_path* that the sandbox can run.

    An interpreter in the owner's home (a user install, a virtualenv) or in the
    project is out of the sandbox's reach on every platform, and so is any
    drive but the system drive on Windows, so those are passed over for a
    system install rather than tried and refused.
    """
    unreachable = [workspace, Path.home().resolve()]
    system_drive = os.environ.get("SYSTEMDRIVE", "C:").upper()
    directories = search_path.split(os.pathsep)
    if Path(name).is_absolute():
        # An absolute interpreter is tried first, then its name on the path.
        directories.insert(0, str(Path(name).parent))
        name = Path(name).name
    for directory in directories:
        found = shutil.which(name, path=directory) if directory else None
        if found is None:
            continue
        candidate = Path(found).resolve()
        if sys.platform == "win32" and candidate.drive.upper() != system_drive:
            continue
        found_path = Path(found).absolute()
        # Both the name as found and what it links to must be in reach: a
        # virtualenv in the owner's home links to a system interpreter, but
        # its own folder is still out of the sandbox.
        if not any(
            place == root or root in place.parents
            for place in (candidate, found_path)
            for root in unreachable
        ):
            # As found, not resolved: a virtualenv finds itself from the name it
            # was started under, and the boundary mounts both prefixes.
            return found_path
    raise FileNotFoundError(name)


def _terminate_tree(proc: subprocess.Popen[bytes]) -> None:
    """Stop the runner; its boundary stops the server and anything it started."""
    if os.name == "posix":
        with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
            os.killpg(proc.pid, 9)  # type: ignore[attr-defined]  # POSIX-only branch
    with contextlib.suppress(OSError):
        proc.kill()


def run_bounded(
    command: list[str],
    payload: bytes,
    *,
    workspace: str | Path,
    env: Mapping[str, str],
    timeout: float,
    max_stdout: int,
    stderr_tail: int,
    label: str,
) -> BoundedRun:
    """Run an interpreter on a workspace script in the native boundary.

    *command* is an interpreter and its arguments; the folder holding the
    script is copied into a throwaway folder and the program runs there with no
    network, so it sees itself and *payload*, never the rest of the project or
    Raiker's state. *env* is the program's own grant, overlaid on the sandbox's
    constructed environment except for the folders the sandbox sets.

    Both pipes are drained concurrently in bounded chunks (DEC-25): stdout
    stops being kept, and the run is stopped, the moment it passes
    *max_stdout*; stderr is drained to the end and only its last *stderr_tail*
    bytes are kept, so a program that fills one pipe while Raiker waits on the
    other cannot deadlock.

    Raises :class:`CommandBackendError` when the host's boundary is not
    enforced or the runner refused to build it (nothing runs on the host),
    :class:`ProgramRefused` for a folder or argument the sandbox cannot hold,
    ``FileNotFoundError`` when no reachable interpreter is found, and
    ``OSError`` from spawning.
    """
    from raiker.execution.commands.backends.native import scratch_run

    root = Path(workspace).resolve()
    interpreter = sandbox_interpreter(command[0], env.get("PATH", ""), root)
    with scratch_run(root, label, timeout_seconds=timeout) as run:
        folder, args = stage_program_folder(root, command[1:], run.folder / "program")
        argv = run.command([str(interpreter), *args], cwd=folder)
        return _drain_bounded(
            argv,
            payload,
            env=run.environment(_owner_variables(env)),
            timeout=timeout,
            max_stdout=max_stdout,
            stderr_tail=stderr_tail,
        )


#: Set by the sandbox itself; a program's own grant never replaces these.
_SANDBOX_OWNED = frozenset(
    {"HOME", "PWD", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR"}
)


def _owner_variables(env: Mapping[str, str]) -> dict[str, str]:
    return {name: value for name, value in env.items() if name.upper() not in _SANDBOX_OWNED}


def _drain_bounded(
    argv: list[str],
    payload: bytes,
    *,
    env: dict[str, str],
    timeout: float,
    max_stdout: int,
    stderr_tail: int,
) -> BoundedRun:
    proc = subprocess.Popen(  # noqa: S603 - the runner's own argv, no shell
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        # Unbuffered: a read returns what the pipe holds now, up to one chunk,
        # rather than waiting to fill a buffer the bound is meant to cap.
        bufsize=0,
        start_new_session=os.name == "posix",
    )
    result = BoundedRun()
    stdout_parts: list[bytes] = []
    stdout_size = 0
    stderr_buffer = bytearray()
    stderr_size = 0
    lock = threading.Lock()

    def feed() -> None:
        assert proc.stdin is not None
        with contextlib.suppress(OSError, ValueError):
            proc.stdin.write(payload)
        with contextlib.suppress(OSError, ValueError):
            proc.stdin.close()

    def read_stdout() -> None:
        nonlocal stdout_size
        assert proc.stdout is not None
        while True:
            try:
                chunk = proc.stdout.read(_PIPE_CHUNK)
            except (OSError, ValueError):
                return
            if not chunk:
                return
            with lock:
                if stdout_size + len(chunk) > max_stdout:
                    result.overflowed = True
                    _terminate_tree(proc)
                    return
                stdout_parts.append(chunk)
                stdout_size += len(chunk)

    def read_stderr() -> None:
        assert proc.stderr is not None
        while True:
            try:
                chunk = proc.stderr.read(_PIPE_CHUNK)
            except (OSError, ValueError):
                return
            if not chunk:
                return
            nonlocal stderr_size
            stderr_size += len(chunk)
            stderr_buffer.extend(chunk)
            if len(stderr_buffer) > stderr_tail:
                del stderr_buffer[: len(stderr_buffer) - stderr_tail]

    workers = [
        threading.Thread(target=feed, daemon=True),
        threading.Thread(target=read_stdout, daemon=True),
        threading.Thread(target=read_stderr, daemon=True),
    ]
    for worker in workers:
        worker.start()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        result.timed_out = True
        _terminate_tree(proc)
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=5)
    for worker in workers:
        # The readers end when the pipes close, which the exit (or the kill)
        # guarantees; the bound only matters for a grandchild still holding a
        # pipe open, and then the session is reported on what was read.
        worker.join(timeout=5)
    if result.overflowed:
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=5)
    for pipe in (proc.stdout, proc.stderr):
        with contextlib.suppress(OSError, ValueError):
            if pipe is not None:
                pipe.close()
    with lock:
        result.stdout = b"".join(stdout_parts)
    result.stderr_tail = bytes(stderr_buffer)
    result.stderr_bytes = stderr_size
    result.returncode = proc.returncode
    if proc.returncode == 91 and b"raiker_runner_error" in result.stderr_tail and not result.stdout:
        # The runner refused to build the boundary; the program never started.
        raise CommandBackendError("native_sandbox_launch_refused")
    return result
