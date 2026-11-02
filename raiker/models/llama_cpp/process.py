"""Starting ``llama-server`` so it never outlives Raiker by accident.

A model server holds gigabytes of memory and a loopback port. If Raiker exits
without stopping it — a crash, a killed process, a power-button shutdown of
the desktop app — the next start finds the port taken and the memory gone.

* **Windows** — every server is assigned to one Job object created with
  ``JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE``. The job's handle lives as long as
  Raiker's process, so the kernel ends the servers when Raiker ends, however
  it ends.
* **macOS and Linux** — each server runs in its own session (so a terminal's
  Ctrl+C reaches Raiker, which then stops it cleanly, rather than both at once)
  and a pid file records it. On the next start :func:`reap_orphans` stops any
  recorded process that is still running *and* is still a ``llama-server``
  from Raiker's own runtime directory or the command line Raiker gave it — a pid
  reused by some unrelated program is left alone.

Output goes to a per-slot log file, so a server that fails to start can be
explained (out of memory, unsupported model, missing library) instead of
reported as merely "not ready".
"""

from __future__ import annotations

import contextlib
import ctypes
import json
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from raiker.models.llama_cpp.installer import runtime_environment

_job_lock = threading.Lock()
_job_handle: Any = None

LOG_TAIL_BYTES = 32 * 1024


def log_dir(workspace_root: Path) -> Path:
    path = Path(workspace_root) / "logs" / "llama-server"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _windows_job() -> Any:
    """The process-wide kill-on-close job, created on first use."""
    global _job_handle
    with _job_lock:
        if _job_handle is not None:
            return _job_handle
        with contextlib.suppress(Exception):
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]

            class IoCounters(ctypes.Structure):
                _fields_ = [(name, ctypes.c_ulonglong) for name in (
                    "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                    "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

            class BasicLimits(ctypes.Structure):
                _fields_ = [
                    ("PerProcessUserTimeLimit", ctypes.c_longlong),
                    ("PerJobUserTimeLimit", ctypes.c_longlong),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD),
                ]

            class ExtendedLimits(ctypes.Structure):
                _fields_ = [
                    ("BasicLimitInformation", BasicLimits),
                    ("IoInfo", IoCounters),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t),
                ]

            kernel32.CreateJobObjectW.restype = wintypes.HANDLE
            job = kernel32.CreateJobObjectW(None, None)
            if not job:
                return None
            info = ExtendedLimits()
            info.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
            extended_limit_information = 9
            if not kernel32.SetInformationJobObject(
                job, extended_limit_information, ctypes.byref(info), ctypes.sizeof(info)
            ):
                kernel32.CloseHandle(job)
                return None
            _job_handle = job
        return _job_handle


def _assign_to_job(process: subprocess.Popen[bytes]) -> None:
    job = _windows_job()
    if job is None:
        return
    with contextlib.suppress(Exception):
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
        handle = int(process._handle)  # type: ignore[attr-defined]
        kernel32.AssignProcessToJobObject(job, handle)


def spawn(argv: list[str], *, log_path: Path, pid_path: Path) -> subprocess.Popen[bytes]:
    """Start ``argv`` with its output in ``log_path`` and its pid recorded."""
    executable = Path(argv[0])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("wb") as log:
        kwargs: dict[str, Any] = {
            "stdin": subprocess.DEVNULL,
            "stdout": log,
            "stderr": subprocess.STDOUT,
            "shell": False,
            "env": runtime_environment(executable),
            "cwd": str(executable.parent) if executable.parent.is_dir() else None,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
                subprocess, "CREATE_NEW_PROCESS_GROUP", 0
            )
        else:
            kwargs["start_new_session"] = True
        process = subprocess.Popen(argv, **kwargs)  # noqa: S603 - fixed argv, no shell
    if sys.platform == "win32":
        _assign_to_job(process)
    with contextlib.suppress(OSError):
        pid_path.write_text(json.dumps({"pid": process.pid, "argv": argv}), encoding="utf-8")
    return process


def read_log_tail(log_path: Path, limit: int = LOG_TAIL_BYTES) -> str:
    try:
        with log_path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - limit))
            return handle.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


#: What a failed start's log says, most specific first, as a bounded reason.
_FAILURE_SIGNATURES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("local_runtime_out_of_memory", (
        "out of memory", "cudamalloc failed", "erroroutofdevicememory", "failed to allocate",
        "unable to allocate", "insufficient memory", "outofmemory", "cannot allocate memory",
        "ggml_backend_cuda_buffer_type_alloc_buffer", "vk::device::allocatememory",
    )),
    ("llama_cpp_model_unsupported", (
        "unknown model architecture", "unknown architecture", "unsupported model",
        "invalid magic", "wrong number of tensors",
    )),
    ("local_runtime_port_in_use", ("address already in use", "couldn't bind", "failed to bind", "only one usage of each socket")),
    ("llama_cpp_libraries_missing", (
        "error while loading shared libraries", "was not found", "library not loaded",
        "cannot open shared object", "dll load failed",
    )),
    ("local_model_unreadable", ("failed to open", "no such file", "failed to load model")),
)


def classify_failure(log_text: str) -> str:
    lowered = log_text.lower()
    for code, needles in _FAILURE_SIGNATURES:
        if any(needle in lowered for needle in needles):
            return code
    return "local_runtime_exited"


def _process_command(pid: int) -> str | None:
    if sys.platform.startswith("linux"):
        with contextlib.suppress(OSError):
            return Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(
                "utf-8", errors="replace"
            )
        return None
    if sys.platform == "darwin":
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            completed = subprocess.run(  # noqa: S603 - fixed system tool
                ["/bin/ps", "-p", str(pid), "-o", "command="],
                capture_output=True, text=True, timeout=5, check=False,
            )
            return completed.stdout.strip() or None
    return None


def reap_orphans(workspace_root: Path) -> list[int]:
    """Stop ``llama-server`` processes a previous Raiker run left behind.

    Windows needs nothing here: the job object already ended them.
    """
    stopped: list[int] = []
    directory = Path(workspace_root) / "logs" / "llama-server"
    if sys.platform == "win32" or not directory.is_dir():
        return stopped
    for pid_file in directory.glob("*.pid"):
        try:
            record = json.loads(pid_file.read_text(encoding="utf-8"))
            pid = int(record["pid"])
            argv = [str(item) for item in record["argv"]]
        except (OSError, ValueError, KeyError, TypeError):
            pid_file.unlink(missing_ok=True)
            continue
        command = _process_command(pid)
        if command and "llama-server" in command and argv and argv[0] in command:
            with contextlib.suppress(OSError):
                os.kill(pid, signal.SIGTERM)
                stopped.append(pid)
        pid_file.unlink(missing_ok=True)
    return stopped
