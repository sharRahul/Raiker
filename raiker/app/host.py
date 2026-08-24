"""Is the host running, is it paused, and what would quitting interrupt?

BUG-40. ``docs/architecture/DESKTOP_DISTRIBUTION_DESIGN.md`` requires a control that reports
``running``, ``paused``, ``needs attention`` or ``stopped`` and offers Open,
Pause, Restart and Quit — and requires that quitting *reports any waiting work*
before it stops. That last clause is the whole point: a governed agent host is
not a text editor, and a quit that silently abandons a run the owner approved a
minute ago is a data-loss bug wearing a menu item's clothes.

Everything here is file-backed under ``.raiker/host/`` rather than held in a
process, for one reason: the two things that need to agree about the host — the
running host itself, and a ``raiker-app`` invocation in a terminal that wants to
pause or stop it — are different processes. A flag in memory can only ever
answer for one of them.

**What Pause actually does.** It stops *new* background work: the scheduler's
due-work pass returns without claiming anything, and the model-capacity refresh
is skipped. It deliberately does **not** stop an approved continuation. A run
that parked on an approval the owner has just granted is not new work — it is
work already under way, and stranding it would turn Pause into a way to lose a
decision. This is stated in the UI rather than left to be discovered.

**What "needs attention" means.** The host is up and healthy, but something is
waiting on the owner: a pending approval, or a task that stopped in a failed
state. It is a distinct state from ``running`` because a tray icon that reads
"running" while three approvals block every scheduled routine is telling the
truth about the process and lying about the product.
"""

from __future__ import annotations

import json
import os
import signal
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from raiker.contracts.ids import utc_now
from raiker.storage.internal_paths import internal_io_path

# Task states that mean real work would be interrupted by a quit. Sourced here
# rather than imported from the web UI's copy so the CLI and the API agree
# without either depending on the other.
IN_FLIGHT_TASK_STATES = frozenset({"queued", "running", "continuing", "paused"})
BLOCKED_TASK_STATES = frozenset({"waiting_for_approval"})
_IS_WINDOWS = os.name == "nt"


@dataclass(frozen=True)
class PauseState:
    """Whether new background work is being started, and since when."""

    paused: bool
    since: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class WaitingWork:
    """One thing a quit would interrupt or leave undone, in the owner's terms."""

    kind: str
    label: str
    detail: str


@dataclass(frozen=True)
class HostStatus:
    """Everything the tray/menu-bar control has to be able to say."""

    state: str
    detail: str
    pid: int | None
    port: int | None
    started_at: str | None
    pause: PauseState
    waiting: list[WaitingWork] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "detail": self.detail,
            "pid": self.pid,
            "port": self.port,
            "started_at": self.started_at,
            "paused": self.pause.paused,
            "paused_since": self.pause.since,
            "paused_reason": self.pause.reason,
            "waiting": [asdict(item) for item in self.waiting],
        }


class HostControl:
    """Read and change the lifecycle state of one workspace's Raiker host."""

    def __init__(self, workspace_root: str | Path) -> None:
        self.workspace_root = Path(workspace_root).resolve()

    # ── where the state lives ────────────────────────────────────────────

    @property
    def state_dir(self) -> Path:
        return internal_io_path(self.workspace_root / ".raiker" / "host")

    @property
    def record_path(self) -> Path:
        return self.state_dir / "host.json"

    @property
    def pause_path(self) -> Path:
        return self.state_dir / "paused.json"

    def _write(self, path: Path, payload: dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        # Written whole then moved into place: a control that half-writes its own
        # state file during a crash is a control that lies after the restart.
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(path)

    def _read(self, path: Path) -> dict[str, Any]:
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    # ── the running host ─────────────────────────────────────────────────

    def record_start(self, *, pid: int, port: int) -> None:
        """Claim this workspace for this process."""
        self._write(
            self.record_path, {"pid": pid, "port": port, "started_at": utc_now()}
        )

    def clear(self) -> None:
        """Forget the running host. Safe to call when there was never one."""
        self.record_path.unlink(missing_ok=True)

    def record(self) -> dict[str, Any]:
        """The recorded host, or ``{}``. A stale record is cleaned up, not returned.

        "Stale" means the recorded process is gone — the host crashed, or the
        machine was reset without a clean shutdown. Reporting that as *running*
        would send the owner to a URL nothing is listening on.
        """
        saved = self._read(self.record_path)
        pid = saved.get("pid")
        if not isinstance(pid, int) or not process_is_alive(pid):
            return {}
        return saved

    # ── pause / resume ───────────────────────────────────────────────────

    def pause(self, reason: str | None = None) -> PauseState:
        state = PauseState(paused=True, since=utc_now(), reason=(reason or None))
        self._write(
            self.pause_path,
            {"paused": True, "since": state.since, "reason": state.reason},
        )
        return state

    def resume(self) -> PauseState:
        self.pause_path.unlink(missing_ok=True)
        return PauseState(paused=False)

    def pause_state(self) -> PauseState:
        saved = self._read(self.pause_path)
        if not saved.get("paused"):
            return PauseState(paused=False)
        since = saved.get("since")
        reason = saved.get("reason")
        return PauseState(
            paused=True,
            since=since if isinstance(since, str) else None,
            reason=reason if isinstance(reason, str) else None,
        )

    def is_paused(self) -> bool:
        return self.pause_state().paused

    # ── what a quit would interrupt ──────────────────────────────────────

    def waiting_work(self) -> list[WaitingWork]:
        """Background work in flight or blocked, newest concern first.

        Read straight from the store rather than from a cached counter: the
        report exists to be trusted at the moment Quit is pressed, and a stale
        count is worse than no count at all. A workspace with no database yet
        simply has nothing waiting, which is the truth.
        """
        if not internal_io_path(
            self.workspace_root / ".raiker" / "raiker.db"
        ).is_file():
            return []
        from raiker.storage.sqlite import SQLiteStore

        try:
            store = SQLiteStore(self.workspace_root)
            tasks = list(store.list_tasks())
        except Exception:  # noqa: BLE001  # A control that cannot read must not crash the host.
            return []

        waiting: list[WaitingWork] = []
        running = [task for task in tasks if task.status in IN_FLIGHT_TASK_STATES]
        blocked = [task for task in tasks if task.status in BLOCKED_TASK_STATES]
        if running:
            waiting.append(
                WaitingWork(
                    kind="running_task",
                    label=f"{len(running)} background {_plural(len(running), 'run')} in flight",
                    detail=(
                        "Quitting stops these at their next safe boundary; each one "
                        "resumes as a fresh run when Raiker starts again."
                    ),
                )
            )
        if blocked:
            waiting.append(
                WaitingWork(
                    kind="blocked_task",
                    label=f"{len(blocked)} run {_plural(len(blocked), 'is', 'are')} waiting for your approval",
                    detail=(
                        "These are already parked and are not lost by quitting, but "
                        "nothing continues them until Raiker is running again."
                    ),
                )
            )
        return waiting

    # ── the reported state ───────────────────────────────────────────────

    def status(self, *, running: bool | None = None) -> HostStatus:
        """The reported state.

        ``running`` overrides the record for the one caller that knows better
        than any file can: the host itself, answering a request. A workspace
        first opened before background registration existed has no record yet,
        and telling a browser loaded *from that very process* that Raiker is
        stopped would be the single state that is provably wrong.
        """
        record = self.record()
        pause = self.pause_state()
        waiting = self.waiting_work()
        if not record and not running:
            return HostStatus(
                state="stopped",
                detail="No Raiker host is running for this workspace.",
                pid=None,
                port=None,
                started_at=None,
                pause=pause,
                waiting=waiting,
            )
        pid = record.get("pid")
        port = record.get("port")
        started_at = record.get("started_at")
        blocked = [item for item in waiting if item.kind == "blocked_task"]
        if pause.paused:
            state, detail = "paused", "New background work is not being started."
        elif blocked:
            state, detail = "needs attention", blocked[0].label.capitalize() + "."
        else:
            state, detail = "running", "Raiker is running and starting work on schedule."
        return HostStatus(
            state=state,
            detail=detail,
            pid=pid if isinstance(pid, int) else None,
            port=port if isinstance(port, int) else None,
            started_at=started_at if isinstance(started_at, str) else None,
            pause=pause,
            waiting=waiting,
        )

    # ── quitting ─────────────────────────────────────────────────────────

    def request_quit(self) -> bool:
        """Ask the recorded host to stop the way the platform stops a process.

        ``SIGTERM`` rather than a kill: uvicorn turns it into its own graceful
        shutdown, which runs the lifespan teardown, which is what lets in-flight
        governed work reach a safe boundary. False means there was nothing
        running to stop — which is not a failure, it is the desired end state
        already being true.
        """
        record = self.record()
        pid = record.get("pid")
        if not isinstance(pid, int):
            return False
        try:
            os.kill(pid, getattr(signal, "SIGTERM", signal.SIGINT))
        except (OSError, ValueError):
            return False
        return True


def process_is_alive(pid: int) -> bool:
    """Is this pid a live process? False for anything we cannot confirm.

    POSIX uses ``os.kill(pid, 0)``. Windows must not: CPython maps ``os.kill`` to
    a process signal/termination API there, so even signal zero is not a safe
    read. Windows opens a query-only process handle instead. ``PermissionError``
    (or Windows access denied) still proves that the process exists. Corrupted
    or hand-edited identifiers answer "not running" rather than taking status
    reads down with them.
    """
    if pid <= 0:
        return False
    if _IS_WINDOWS:
        return _windows_process_is_alive(pid)
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except (OSError, ValueError, OverflowError):
        return False
    return True


def _windows_process_is_alive(pid: int) -> bool:
    """Read process state through a query handle; never signal the target."""
    try:
        import ctypes
        from ctypes import wintypes

        win_dll = getattr(ctypes, "WinDLL", None)
        get_last_error = getattr(ctypes, "get_last_error", None)
        if win_dll is None or get_last_error is None:
            return False
        kernel32 = win_dll("kernel32", use_last_error=True)
        open_process = kernel32.OpenProcess
        open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        open_process.restype = wintypes.HANDLE
        get_exit_code = kernel32.GetExitCodeProcess
        get_exit_code.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        get_exit_code.restype = wintypes.BOOL
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL

        handle = open_process(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return get_last_error() == 5  # access denied still proves existence
        try:
            exit_code = wintypes.DWORD()
            return bool(get_exit_code(handle, ctypes.byref(exit_code))) and exit_code.value == 259
        finally:
            close_handle(handle)
    except (AttributeError, OSError, OverflowError, ValueError):
        return False


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return singular if count == 1 else (plural or f"{singular}s")
