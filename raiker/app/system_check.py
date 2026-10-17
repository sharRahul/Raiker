"""What this machine can do, and whether this installation works (DIST-05, DIST-06).

Two answers for the first-run wizard, both computed locally and both honest
about what they did not measure:

* :func:`system_readiness` — operating system, architecture, memory, processor,
  graphics acceleration, free storage, network route, the encrypted store, the
  credential store, local model runtimes already installed, and where Raiker
  keeps its data. It recommends a local model size from the memory it found and
  never makes a dedicated GPU a requirement.
* :func:`installation_checks` — the mandatory components behind a working
  Raiker (the host, the database and its migrations, memory storage, the
  permission registry, the runtime's execution switch, the web app) and the
  optional ones (the sandbox runner for governed commands, a chosen model).

**Nothing here contacts the network.** The network check asks the operating
system whether a route exists by *connecting* a UDP socket to a documentation
address (RFC 5737), which sends no packet; a model request is a separate act the
owner starts from the wizard. Local runtimes are found by a ``PATH`` lookup, as
:mod:`raiker.models.local_presence` already does, never by starting them.

Each check has a ``state``: ``pass``, ``warn`` (works, with a limit worth
knowing), ``fail`` (a mandatory requirement is not met), or ``info``.
"""

from __future__ import annotations

import contextlib
import ctypes
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

CheckState = Literal["pass", "warn", "fail", "info"]

GIB = 1024**3
#: The floor below which the installer refuses, and the size the wizard calls
#: comfortable for Raiker itself with a hosted provider.
MIN_MEMORY_BYTES = 4 * GIB
RECOMMENDED_MEMORY_BYTES = 8 * GIB
MIN_FREE_BYTES = 2 * GIB
RECOMMENDED_FREE_BYTES = 20 * GIB
SUPPORTED_ARCHITECTURES = {"x86_64": "x86-64", "amd64": "x86-64", "arm64": "ARM64", "aarch64": "ARM64"}


@dataclass(frozen=True)
class Check:
    id: str
    label: str
    state: CheckState
    detail: str
    #: What to do about a ``warn`` or ``fail``, in the owner's words.
    remedy: str = ""
    #: Whether a ``fail`` here stops Raiker from working at all.
    mandatory: bool = False
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "state": self.state,
            "detail": self.detail,
            "remedy": self.remedy,
            "mandatory": self.mandatory,
            "data": dict(self.data),
        }


# ── measurements ───────────────────────────────────────────────────────


def total_memory_bytes() -> int | None:
    """Physical memory, from the platform's own interface; ``None`` if unknown."""
    try:
        if sys.platform == "win32":

            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatus()
            status.dwLength = ctypes.sizeof(MemoryStatus)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined]
                return int(status.ullTotalPhys)
            return None
        if sys.platform == "darwin":
            output = subprocess.run(  # noqa: S603 - fixed system tool, fixed argv
                ["/usr/sbin/sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True, timeout=5, check=False,
            ).stdout.strip()
            return int(output) if output.isdigit() else None
        pages = os.sysconf("SC_PHYS_PAGES")
        size = os.sysconf("SC_PAGE_SIZE")
        return int(pages) * int(size) if pages > 0 and size > 0 else None
    except (OSError, ValueError, AttributeError, subprocess.SubprocessError):
        return None


def cpu_description() -> tuple[int, str]:
    cores = os.cpu_count() or 0
    name = platform.processor() or platform.machine()
    if sys.platform.startswith("linux"):
        try:
            for line in Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace").splitlines():
                if line.lower().startswith(("model name", "hardware")):
                    name = line.split(":", 1)[1].strip()
                    break
        except OSError:
            pass
    elif sys.platform == "darwin":
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            name = subprocess.run(  # noqa: S603 - fixed system tool, fixed argv
                ["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, timeout=5, check=False,
            ).stdout.strip() or name
    return cores, name


def detect_acceleration(machine: str | None = None) -> tuple[str, str]:
    """``(kind, description)`` for graphics acceleration a local model could use.

    Found from files and executables that exist, never by running a driver
    tool: an NVIDIA driver, AMD ROCm, or Apple silicon's Metal. ``("none", …)``
    is an ordinary answer — Raiker and hosted providers need no GPU, and small
    local models run on the processor.
    """
    machine = (machine or platform.machine()).lower()
    if sys.platform == "darwin" and machine in {"arm64", "aarch64"}:
        return "metal", "Apple silicon GPU (Metal)"
    if sys.platform == "win32":
        system32 = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32"
        if (system32 / "nvcuda.dll").is_file():
            return "cuda", "NVIDIA GPU driver (CUDA)"
        if (system32 / "amdhip64.dll").is_file() or (system32 / "amdhip64_6.dll").is_file():
            return "rocm", "AMD GPU driver (HIP)"
        return "none", "No dedicated GPU driver found"
    if sys.platform.startswith("linux"):
        if Path("/proc/driver/nvidia/version").is_file() or Path("/dev/nvidia0").exists():
            return "cuda", "NVIDIA GPU driver (CUDA)"
        if Path("/dev/kfd").exists():
            return "rocm", "AMD GPU (ROCm)"
    return "none", "No dedicated GPU driver found"


def has_network_route() -> bool:
    """Whether the OS has a route off this machine. Sends nothing."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))
            return not probe.getsockname()[0].startswith("127.")
    except OSError:
        return False


def os_support() -> tuple[CheckState, str, str]:
    """``(state, description, remedy)`` for this operating system release."""
    if sys.platform == "win32":
        version = sys.getwindowsversion()  # type: ignore[attr-defined]
        build = int(version.build)
        name = "Windows 11" if build >= 22000 else f"Windows {version.major}"
        if version.major < 10 or build < 17763:
            return "fail", f"{name} (build {build})", "Raiker needs Windows 10 version 1809 or newer."
        return "pass", f"{name} (build {build})", ""
    if sys.platform == "darwin":
        release = platform.mac_ver()[0] or "unknown"
        major = int(release.split(".")[0]) if release.split(".")[0].isdigit() else 0
        if major and major < 12:
            return "fail", f"macOS {release}", "Raiker needs macOS 12 Monterey or newer."
        return "pass", f"macOS {release}", ""
    if sys.platform.startswith("linux"):
        name = "Linux"
        try:
            fields = dict(
                line.split("=", 1)
                for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines()
                if "=" in line
            )
            name = fields.get("PRETTY_NAME", name).strip('"')
        except OSError:
            pass
        libc, libc_version = platform.libc_ver()
        if libc == "glibc" and libc_version:
            parts = [int(p) for p in re.findall(r"\d+", libc_version)[:2]]
            if len(parts) == 2 and tuple(parts) < (2, 35):
                return (
                    "fail",
                    f"{name} (glibc {libc_version})",
                    "This build needs glibc 2.35 or newer (Ubuntu 22.04, Debian 12, Fedora 36 or later).",
                )
        return "pass", f"{name}" + (f" (glibc {libc_version})" if libc_version else ""), ""
    return "fail", platform.platform(), "This operating system is not supported."


def recommended_local_model(memory: int | None, acceleration: str) -> dict[str, Any]:
    """A local model size this machine can run comfortably, with its footprint.

    Sizes are for 4-bit quantised models, the common local download: roughly
    0.6 GB per billion parameters on disk, and about as much again in memory
    while it answers. These are planning figures, stated as approximate.
    """
    gib = (memory or 0) / GIB
    if gib >= 32 and acceleration != "none":
        tier = ("14B–32B", "about 9–20 GB", "Larger local models can run here.")
    elif gib >= 16:
        tier = ("7B–14B", "about 4–9 GB", "Mid-size local models run comfortably.")
    elif gib >= 8:
        tier = ("3B–8B", "about 2–5 GB", "Small local models run; larger ones will be slow.")
    else:
        tier = (
            "1B–3B",
            "about 1–2 GB",
            "Local models will be limited; a hosted or home-network provider is recommended.",
        )
    return {"parameters": tier[0], "download": tier[1], "note": tier[2]}


def installed_runtimes() -> list[dict[str, Any]]:
    """Local model runtimes already on this machine, by ``PATH`` and install location."""
    from raiker.models.local_presence import RUNTIME_EXECUTABLES, probe

    found: list[dict[str, Any]] = []
    for runtime in RUNTIME_EXECUTABLES:
        present, executable = probe(runtime)
        if not present and runtime == "ollama":
            executable = _ollama_default_location()
            present = executable is not None
        found.append({"runtime": runtime, "present": present, "executable": executable})
    lm_studio = shutil.which("lms")
    found.append({"runtime": "lm-studio", "present": lm_studio is not None, "executable": lm_studio})
    return found


def _ollama_default_location() -> str | None:
    """Where Ollama's official installers put it, when ``PATH`` does not say."""
    candidates: list[Path] = []
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            candidates.append(Path(local) / "Programs" / "Ollama" / "ollama.exe")
    elif sys.platform == "darwin":
        candidates += [Path("/Applications/Ollama.app/Contents/Resources/ollama"),
                       Path("/usr/local/bin/ollama")]
    else:
        candidates += [Path("/usr/local/bin/ollama"), Path("/usr/bin/ollama")]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


# ── the two answers ────────────────────────────────────────────────────


def system_readiness(workspace_root: Path) -> dict[str, Any]:
    from raiker.auth import os_keystore

    checks: list[Check] = []
    state, described, remedy = os_support()
    checks.append(Check("os", "Operating system", state, described, remedy, mandatory=True))

    machine = platform.machine().lower()
    arch = SUPPORTED_ARCHITECTURES.get(machine)
    checks.append(
        Check("arch", "Architecture", "pass" if arch else "fail", arch or machine,
              "" if arch else "Raiker is built for x86-64 and ARM64 only.", mandatory=True)
    )

    memory = total_memory_bytes()
    if memory is None:
        checks.append(Check("memory", "Memory", "info", "Could not be measured"))
    else:
        memory_state: CheckState = (
            "fail" if memory < MIN_MEMORY_BYTES
            else "warn" if memory < RECOMMENDED_MEMORY_BYTES
            else "pass"
        )
        checks.append(Check(
            "memory", "Memory", memory_state, f"{memory / GIB:.1f} GB",
            {"fail": "Raiker needs at least 4 GB of memory.",
             "warn": "Raiker runs; local models need 8 GB or more.", "pass": ""}[memory_state],
            mandatory=True, data={"bytes": memory},
        ))

    cores, cpu_name = cpu_description()
    checks.append(Check(
        "cpu", "Processor", "warn" if cores and cores < 2 else "pass",
        f"{cpu_name} · {cores} logical cores" if cores else cpu_name,
        "A single-core machine will be slow." if cores and cores < 2 else "",
        data={"cores": cores},
    ))

    acceleration, accel_detail = detect_acceleration(machine)
    checks.append(Check(
        "gpu", "Graphics acceleration", "info", accel_detail,
        "" if acceleration != "none" else "Optional. Hosted providers and small local models need no GPU.",
        data={"kind": acceleration},
    ))

    try:
        # Before the first start the data folder may not exist yet (the
        # installer asks); measure the nearest folder that does.
        measured = workspace_root
        while not measured.exists() and measured.parent != measured:
            measured = measured.parent
        free = shutil.disk_usage(measured).free
    except OSError:
        free = None
    if free is None:
        checks.append(Check("storage", "Free storage", "info", "Could not be measured"))
    else:
        storage_state: CheckState = (
            "fail" if free < MIN_FREE_BYTES else "warn" if free < RECOMMENDED_FREE_BYTES else "pass"
        )
        checks.append(Check(
            "storage", "Free storage", storage_state, f"{free / GIB:.1f} GB free where Raiker keeps data",
            {"fail": "Free at least 2 GB for Raiker's data.",
             "warn": "Enough for Raiker; local models need 20 GB or more.", "pass": ""}[storage_state],
            mandatory=True, data={"bytes": free},
        ))

    online = has_network_route()
    checks.append(Check(
        "network", "Network", "pass" if online else "warn",
        "A network route is available" if online else "No network route found",
        "" if online else "Hosted providers need a connection. Local models work offline.",
    ))

    keystore = os_keystore.status()
    checks.append(Check(
        "credentials", "Credential protection",
        "pass" if keystore.backend != "file" else ("warn" if keystore.enabled else "info"),
        keystore.detail,
        "" if keystore.backend != "file" else "Provider keys are still encrypted; their key is kept in a private file.",
        data={"backend": keystore.backend},
    ))

    runtimes = installed_runtimes()
    present = [item["runtime"] for item in runtimes if item["present"]]
    checks.append(Check(
        "local_runtimes", "Local model runtimes", "info",
        ("Found: " + ", ".join(present)) if present else "None installed yet",
        "" if present else "Optional. Ollama can be installed from Models if you want local models.",
        data={"runtimes": runtimes},
    ))

    from raiker.app.installation import detect_installation

    install = detect_installation()
    checks.append(Check(
        "installation", "This installation", "info",
        f"Raiker {install.version}" + (" · signed" if install.signed else " · unsigned" if install.packaged else " · source checkout"),
        data={"packaged": install.packaged, "signed": install.signed, "version": install.version},
    ))

    blocking = [check.id for check in checks if check.state == "fail" and check.mandatory]
    return {
        "checks": [check.to_dict() for check in checks],
        "blocking": blocking,
        "ready": not blocking,
        "recommended_local_model": recommended_local_model(memory, acceleration),
        "locations": {
            "data": str(workspace_root),
            "models": str(workspace_root / ".raiker" / "models"),
            "backups": str(workspace_root / ".raiker" / "backups"),
        },
    }


def installation_checks(
    workspace_root: Path,
    *,
    principal_id: str,
    ui_dir: Path | None,
    executor_registry: Any = None,
) -> dict[str, Any]:
    """Whether each mandatory component is working, from inside the running host."""
    checks: list[Check] = [
        Check("host", "Raiker host", "pass", "Answering on this computer only (loopback)", mandatory=True)
    ]
    checks.append(
        Check("web", "Application window content", "pass" if ui_dir is not None else "fail",
              "Built interface found" if ui_dir is not None else "The interface files are missing",
              "" if ui_dir is not None else "Reinstall Raiker.", mandatory=True)
    )

    from raiker.storage.migrations import SCHEMA_GENERATION
    from raiker.storage.sqlite import SQLiteStore

    store = SQLiteStore(workspace_root)
    try:
        setup = store.load_setup_state(principal_id)
        checks.append(Check("database", "Encrypted database", "pass", "Opened and read", mandatory=True))
    except Exception as exc:  # noqa: BLE001 - reported, never raised to the wizard
        setup = None
        checks.append(Check("database", "Encrypted database", "fail", type(exc).__name__,
                            "Open Diagnostics, or restore a backup.", mandatory=True))

    try:
        from raiker.app.installation import workspace_schema_generation

        generation = workspace_schema_generation(workspace_root)
        if generation is None:
            checks.append(Check("migrations", "Data format", "warn", "Its generation could not be read"))
        else:
            # Older data is migrated when the store opens; a newer generation is
            # data a later Raiker wrote, which this one refuses to open.
            current = generation == SCHEMA_GENERATION
            checks.append(Check(
                "migrations", "Data format", "pass" if current else "fail",
                f"Generation {generation} (this version writes {SCHEMA_GENERATION})",
                "" if current else "This data was written by a different Raiker version.",
                mandatory=True,
            ))
    except Exception as exc:  # noqa: BLE001
        checks.append(Check("migrations", "Data format", "warn", type(exc).__name__))

    memory_dir = workspace_root / ".raiker" / "memory"
    try:
        memory_dir.mkdir(parents=True, exist_ok=True)
        writable = os.access(memory_dir, os.W_OK)
    except OSError:
        writable = False
    checks.append(Check(
        "memory", "Long-term memory storage", "pass" if writable else "fail",
        "Ready" if writable else "Not writable", "" if writable else "Check the data folder's permissions.",
        mandatory=True,
    ))

    try:
        from raiker.control.service import RuntimeControlService

        service = RuntimeControlService(workspace_root, executor_registry=executor_registry)
        gates = service.list_capability_gates(principal_id)
        checks.append(Check(
            "permissions", "Permissions and governance", "pass" if gates else "fail",
            f"{len(gates)} permissions loaded; nothing was granted by setup",
            "" if gates else "The permission registry is empty.", mandatory=True,
            data={"count": len(gates)},
        ))
    except Exception as exc:  # noqa: BLE001
        checks.append(Check("permissions", "Permissions and governance", "fail", type(exc).__name__,
                            "Open Diagnostics.", mandatory=True))

    from raiker.execution.commands.backends.native import NativeSandboxDriver

    runner, reason = NativeSandboxDriver(workspace_root).locate()
    checks.append(Check(
        "sandbox", "Governed command runner", "pass" if runner else "warn",
        "Present and verified" if runner else (reason or "missing"),
        "" if runner else "Commands in Build cannot run until it is restored. Reinstall Raiker.",
    ))

    from raiker.auth import os_keystore
    from raiker.auth.vault_key_file import vault_status

    vault = vault_status(workspace_root)
    keystore = os_keystore.status()
    checks.append(Check(
        "credentials", "Credential vault",
        "fail" if vault == "invalid" else "pass",
        {"configured_valid": f"Ready · {keystore.detail}",
         "missing": "Created when you save your first provider key",
         "invalid": "The vault key cannot be read"}[vault],
        "Unlock your system keyring, or reset the vault in Settings." if vault == "invalid" else "",
    ))

    model = None if setup is None or setup.model_deferred else setup.selected_model
    checks.append(Check(
        "model", "AI model", "pass" if model else "warn",
        f"{model} selected" if model else "No model chosen yet",
        "" if model else "Chat and Build need a model. Choose one in the Model step or in Models.",
    ))

    failed = [check.id for check in checks if check.state == "fail" and check.mandatory]
    return {"checks": [check.to_dict() for check in checks], "failed": failed, "ok": not failed}
