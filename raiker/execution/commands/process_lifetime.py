"""Make a sandbox runner die when Raiker does.

A governed command must not be able to outlive the runtime that governs it. On
Linux the runner asks the kernel for that directly (`PR_SET_PDEATHSIG`). Windows
has no parent-death signal: a child keeps running when its parent exits, so a
killed Raiker would leave a sandboxed process holding a Job Object and a
workspace grant with nothing left to reclaim them.

The fix is a Job Object the **runtime** owns. Every runner is assigned to it, the
handle is held for the life of the process, and `KILL_ON_JOB_CLOSE` means the
kernel reaps the whole set when that handle closes — including on a hard kill,
where no Python `atexit` or signal handler runs.

Deliberately *not* a parent-pid watcher: a bare pid cannot distinguish "still
running" from "pid reused", so a runner could end up watching a stranger and
never exit.
"""
from __future__ import annotations

import ctypes
import sys
import threading
from typing import Any

# `ctypes.wintypes` does not import off Windows, and this module is imported on
# every platform. `DWORD` is a 32-bit unsigned integer; spelling it that way
# keeps the structures portable enough to define once.
_DWORD = ctypes.c_uint32

_lock = threading.Lock()
_job: Any = None
_unavailable_reason: str | None = None

_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_PROCESS_SET_QUOTA = 0x0100
_PROCESS_TERMINATE = 0x0001


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", _DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", _DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", _DWORD),
        ("SchedulingClass", _DWORD),
    ]


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def _runtime_job() -> Any:
    """One job for the whole runtime, created on first use."""
    global _job, _unavailable_reason
    if _job is not None or _unavailable_reason is not None:
        return _job
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.CreateJobObjectW(None, None)
    if not handle:
        _unavailable_reason = "runtime_job_object_unavailable"
        return None
    limits = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    limits.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel32.SetInformationJobObject(
        handle,
        _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
        ctypes.byref(limits),
        ctypes.sizeof(limits),
    ):
        kernel32.CloseHandle(handle)
        _unavailable_reason = "runtime_job_object_unavailable"
        return None
    _job = handle
    return _job


def bind_to_runtime_lifetime(pid: int | None) -> bool:
    """Bind one process to the runtime's lifetime. Returns whether it worked.

    A false return is not fatal — the runner still enforces its own deadline —
    but it does mean a hard kill of Raiker could leave that command running
    until the deadline expires. Callers that report posture should say so
    rather than assume it.
    """
    if sys.platform != "win32":
        # Linux runners set `PR_SET_PDEATHSIG` themselves; macOS has neither
        # mechanism and says so in its reported posture.
        return True
    if pid is None:
        return False
    with _lock:
        job = _runtime_job()
        if job is None:
            return False
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        process = kernel32.OpenProcess(_PROCESS_SET_QUOTA | _PROCESS_TERMINATE, False, pid)
        if not process:
            return False
        try:
            return bool(kernel32.AssignProcessToJobObject(job, process))
        finally:
            kernel32.CloseHandle(process)
