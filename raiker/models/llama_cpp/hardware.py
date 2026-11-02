"""What this machine offers a llama.cpp server, and which backend should use it.

:func:`raiker.app.system_check.detect_acceleration` answers "is there a GPU
driver" for the first-run wizard from files alone. Choosing a llama.cpp build
and sizing its GPU offload needs more: *how much* GPU memory there is, which
CUDA version the driver supports, and whether a Vulkan loader exists for the
GPUs CUDA cannot drive.

* **NVIDIA** — ``nvidia-smi`` is the one interface every NVIDIA driver ships on
  Windows and Linux that reports memory and the supported CUDA version, so it is
  run here: a fixed argv, no shell, a five-second timeout, and its absence or
  failure is an ordinary "unknown", never an error.
* **AMD / Intel** — Linux publishes vendor and VRAM in ``/sys/class/drm``;
  Windows publishes adapter memory in the display class's registry key. These
  GPUs are driven through **Vulkan**, so the Vulkan loader must be present.
* **Apple silicon** — the GPU shares system memory and runs **Metal**; macOS
  lets it wire roughly two thirds to three quarters of RAM.

Everything is gathered through a :class:`Probe`, so tests can describe a
Windows CUDA laptop, a Linux AMD desktop or an M-series Mac on any host.
"""

from __future__ import annotations

import contextlib
import ctypes
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from raiker.contracts.views import View

Backend = Literal["cuda", "vulkan", "metal", "cpu"]
BACKENDS: tuple[Backend, ...] = ("cuda", "vulkan", "metal", "cpu")
OsName = Literal["windows", "macos", "linux"]
Arch = Literal["x64", "arm64"]

GIB = 1024**3
MIB = 1024**2

_NVIDIA, _AMD, _INTEL, _APPLE = "nvidia", "amd", "intel", "apple"
_PCI_VENDORS = {"0x10de": _NVIDIA, "0x1002": _AMD, "0x1022": _AMD, "0x8086": _INTEL}


@dataclass(frozen=True)
class GpuDevice(View):
    vendor: str
    name: str
    #: ``None`` when the platform does not say. A GPU of unknown size is still
    #: offered as a backend, but the planner will not offload onto it blind.
    memory_total_bytes: int | None
    memory_free_bytes: int | None
    #: Integrated GPUs share system memory; offload rarely helps them enough to
    #: be chosen automatically, so they are never the *recommended* device.
    discrete: bool
    #: The newest CUDA runtime the NVIDIA driver supports, e.g. ``"12.8"``.
    cuda_version: str | None = None
    #: Apple silicon: GPU and CPU share one pool, so offload costs no copy.
    unified_memory: bool = False


@dataclass(frozen=True)
class HardwareProfile(View):
    os: str
    arch: str
    cpu_cores: int
    total_memory_bytes: int | None
    available_memory_bytes: int | None
    gpus: tuple[GpuDevice, ...]
    vulkan_available: bool
    metal_available: bool
    #: Every backend this machine can run, best first; ``cpu`` is always last.
    backends: tuple[str, ...]
    recommended_backend: str
    #: One sentence for the owner on why that backend was chosen.
    reason: str
    detected_at: float = field(default=0.0)

    def gpu_for(self, backend: str) -> GpuDevice | None:
        """The device ``backend`` would offload onto, or ``None`` for CPU."""
        if backend == "cpu":
            return None
        if backend == "metal":
            return next((gpu for gpu in self.gpus if gpu.vendor == _APPLE), None)
        if backend == "cuda":
            candidates = [gpu for gpu in self.gpus if gpu.vendor == _NVIDIA]
        else:
            candidates = [gpu for gpu in self.gpus if gpu.vendor != _APPLE]
        candidates.sort(
            key=lambda gpu: (gpu.discrete, gpu.memory_free_bytes or gpu.memory_total_bytes or 0),
            reverse=True,
        )
        return candidates[0] if candidates else None


# ── probing ────────────────────────────────────────────────────────────


@dataclass
class Probe:
    """The host's answers, each replaceable in a test."""

    os: OsName
    arch: Arch
    run: Callable[[Sequence[str]], str | None]
    read: Callable[[Path], str | None]
    exists: Callable[[Path], bool]
    glob: Callable[[str, str], list[Path]]
    which: Callable[[str], str | None]
    environ: dict[str, str]

    @staticmethod
    def host() -> Probe:
        return Probe(
            os=host_os(),
            arch=host_arch(),
            run=_run,
            read=_read,
            exists=lambda path: path.exists(),
            glob=lambda root, pattern: sorted(Path(root).glob(pattern)) if Path(root).is_dir() else [],
            which=shutil.which,
            environ=dict(os.environ),
        )


def host_os() -> OsName:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def host_arch() -> Arch:
    """The *native* architecture, which an emulated Raiker must not mistake.

    Raiker's Windows build is x86-64 and runs under emulation on Windows on Arm,
    where ``platform.machine()`` answers ``AMD64``. A native arm64 llama.cpp is
    several times faster than an emulated x64 one, so the kernel is asked.
    """
    if sys.platform == "win32":
        native = _windows_native_machine()
        if native is not None:
            return native
    machine = platform.machine().lower()
    if sys.platform == "darwin" and machine == "x86_64":
        # Rosetta reports x86_64; `sysctl.proc_translated` says whether it is.
        translated = _run(["/usr/sbin/sysctl", "-n", "sysctl.proc_translated"])
        if translated is not None and translated.strip() == "1":
            return "arm64"
    return "arm64" if machine in {"arm64", "aarch64"} else "x64"


def _windows_native_machine() -> Arch | None:
    with contextlib.suppress(Exception):
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        process_machine = ctypes.c_ushort()
        native_machine = ctypes.c_ushort()
        if kernel32.IsWow64Process2(
            kernel32.GetCurrentProcess(), ctypes.byref(process_machine), ctypes.byref(native_machine)
        ):
            return "arm64" if native_machine.value == 0xAA64 else "x64"
    return None


def _run(argv: Sequence[str]) -> str | None:
    """A fixed system tool's stdout, or ``None`` on any failure."""
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
            list(argv), capture_output=True, text=True, timeout=5, check=False,
            stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return completed.stdout if completed.returncode == 0 else None


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


# ── memory ─────────────────────────────────────────────────────────────


def available_memory_bytes(probe: Probe | None = None) -> int | None:
    """Memory a new process could use without pushing the system into swap."""
    probe = probe or Probe.host()
    if probe.os == "linux":
        text = probe.read(Path("/proc/meminfo")) or ""
        match = re.search(r"^MemAvailable:\s+(\d+)\s+kB", text, re.MULTILINE)
        return int(match.group(1)) * 1024 if match else None
    if probe.os == "macos":
        text = probe.run(["/usr/bin/vm_stat"]) or ""
        page = re.search(r"page size of (\d+) bytes", text)
        if not page:
            return None
        pages = 0
        for label in ("Pages free", "Pages inactive", "Pages speculative", "Pages purgeable"):
            found = re.search(rf"^{label}:\s+(\d+)", text, re.MULTILINE)
            pages += int(found.group(1)) if found else 0
        return pages * int(page.group(1))
    return _windows_available_memory()


def _windows_available_memory() -> int | None:
    with contextlib.suppress(Exception):

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
            return int(status.ullAvailPhys)
    return None


def total_memory_bytes(probe: Probe | None = None) -> int | None:
    probe = probe or Probe.host()
    if probe.os == "linux":
        text = probe.read(Path("/proc/meminfo")) or ""
        match = re.search(r"^MemTotal:\s+(\d+)\s+kB", text, re.MULTILINE)
        return int(match.group(1)) * 1024 if match else None
    if probe.os == "macos":
        text = (probe.run(["/usr/sbin/sysctl", "-n", "hw.memsize"]) or "").strip()
        return int(text) if text.isdigit() else None
    from raiker.app.system_check import total_memory_bytes as windows_total

    return windows_total()


# ── GPUs ───────────────────────────────────────────────────────────────


def _nvidia_smi(probe: Probe) -> str | None:
    found = probe.which("nvidia-smi")
    if found:
        return found
    if probe.os == "windows":
        root = Path(probe.environ.get("SYSTEMROOT", r"C:\Windows"))
        for candidate in (
            root / "System32" / "nvidia-smi.exe",
            Path(probe.environ.get("PROGRAMFILES", r"C:\Program Files"))
            / "NVIDIA Corporation" / "NVSMI" / "nvidia-smi.exe",
        ):
            if probe.exists(candidate):
                return str(candidate)
    elif probe.exists(Path("/usr/bin/nvidia-smi")):
        return "/usr/bin/nvidia-smi"
    return None


def nvidia_gpus(probe: Probe) -> list[GpuDevice]:
    """NVIDIA GPUs with their memory and the CUDA version the driver supports."""
    tool = _nvidia_smi(probe)
    if tool is None:
        return []
    listing = probe.run(
        [tool, "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"]
    )
    if not listing:
        return []
    header = probe.run([tool]) or ""
    cuda = re.search(r"CUDA Version:\s*([0-9]+\.[0-9]+)", header)
    devices: list[GpuDevice] = []
    for line in listing.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 3 or not parts[0]:
            continue
        devices.append(
            GpuDevice(
                vendor=_NVIDIA,
                name=parts[0],
                memory_total_bytes=_mib(parts[1]),
                memory_free_bytes=_mib(parts[2]),
                discrete=True,
                cuda_version=cuda.group(1) if cuda else None,
            )
        )
    return devices


def _mib(text: str) -> int | None:
    return int(float(text)) * MIB if re.fullmatch(r"\d+(\.\d+)?", text) else None


def _linux_drm_gpus(probe: Probe, skip_vendors: set[str]) -> list[GpuDevice]:
    """Non-NVIDIA GPUs from sysfs: vendor, and VRAM where the driver reports it."""
    devices: list[GpuDevice] = []
    seen: set[str] = set()
    for card in probe.glob("/sys/class/drm", "card[0-9]*"):
        if "-" in card.name:
            continue  # a connector (card0-HDMI-A-1), not a device
        device = card / "device"
        vendor = _PCI_VENDORS.get((probe.read(device / "vendor") or "").strip().lower())
        if vendor is None or vendor in skip_vendors:
            continue
        key = str(device)
        if key in seen:
            continue
        seen.add(key)
        total = _int(probe.read(device / "mem_info_vram_total"))
        used = _int(probe.read(device / "mem_info_vram_used"))
        # An APU reports a small carve-out as "VRAM"; under 1 GiB is integrated.
        discrete = vendor == _AMD and total is not None and total >= GIB
        if vendor == _INTEL and probe.exists(device / "lmem_total_bytes"):
            total = _int(probe.read(device / "lmem_total_bytes"))
            discrete = total is not None and total >= GIB
        devices.append(
            GpuDevice(
                vendor=vendor,
                name=f"{vendor.upper()} GPU ({card.name})",
                memory_total_bytes=total,
                memory_free_bytes=(total - used) if total is not None and used is not None else None,
                discrete=discrete,
            )
        )
    return devices


def _int(text: str | None) -> int | None:
    value = (text or "").strip()
    return int(value) if value.isdigit() else None


def _windows_registry_gpus(skip_vendors: set[str]) -> list[GpuDevice]:
    """Display adapters from the registry, with dedicated memory where recorded."""
    devices: list[GpuDevice] = []
    with contextlib.suppress(Exception):
        import winreg  # type: ignore[import-not-found,unused-ignore]

        path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as root:  # type: ignore[attr-defined,unused-ignore]
            index = 0
            while True:
                try:
                    sub = winreg.EnumKey(root, index)  # type: ignore[attr-defined,unused-ignore]
                except OSError:
                    break
                index += 1
                if not sub.isdigit():
                    continue
                with contextlib.suppress(OSError), winreg.OpenKey(root, sub) as key:  # type: ignore[attr-defined,unused-ignore]
                    name = str(winreg.QueryValueEx(key, "DriverDesc")[0])  # type: ignore[attr-defined,unused-ignore]
                    lowered = name.lower()
                    vendor = (
                        _NVIDIA if "nvidia" in lowered
                        else _AMD if ("amd" in lowered or "radeon" in lowered)
                        else _INTEL if "intel" in lowered
                        else None
                    )
                    if vendor is None or vendor in skip_vendors:
                        continue
                    memory: int | None = None
                    with contextlib.suppress(OSError):
                        raw = winreg.QueryValueEx(key, "HardwareInformation.qwMemorySize")[0]  # type: ignore[attr-defined,unused-ignore]
                        memory = int.from_bytes(raw, "little") if isinstance(raw, bytes) else int(raw)
                    # "Intel UHD Graphics", "AMD Radeon(TM) Graphics": integrated parts.
                    discrete = memory is not None and memory >= 2 * GIB and not lowered.endswith("graphics")
                    devices.append(GpuDevice(vendor, name, memory, None, discrete))
    return devices


def vulkan_loader_present(probe: Probe) -> bool:
    if probe.os == "windows":
        root = Path(probe.environ.get("SYSTEMROOT", r"C:\Windows"))
        return probe.exists(root / "System32" / "vulkan-1.dll")
    if probe.os == "linux":
        for directory in (
            "/usr/lib/x86_64-linux-gnu", "/usr/lib/aarch64-linux-gnu", "/usr/lib64", "/usr/lib",
            "/lib/x86_64-linux-gnu", "/lib/aarch64-linux-gnu", "/lib64",
        ):
            if probe.exists(Path(directory) / "libvulkan.so.1"):
                return True
        return False
    return False


def apple_gpu(probe: Probe, total_memory: int | None) -> GpuDevice | None:
    if probe.os != "macos" or probe.arch != "arm64":
        return None
    # macOS caps what the GPU may wire: about 2/3 of RAM up to 36 GiB, 3/4 above.
    share = 0.75 if (total_memory or 0) > 36 * GIB else 0.67
    budget = int(total_memory * share) if total_memory else None
    chip = (probe.run(["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"]) or "Apple silicon").strip()
    return GpuDevice(_APPLE, f"{chip} GPU", budget, None, True, unified_memory=True)


# ── choosing a backend ────────────────────────────────────────────────


def rank_backends(
    os_name: str, arch: str, gpus: Sequence[GpuDevice], vulkan: bool
) -> tuple[tuple[str, ...], str, str]:
    """Every runnable backend best first, the recommended one, and why."""
    if os_name == "macos":
        if arch == "arm64":
            return ("metal", "cpu"), "metal", "Apple silicon runs local models on its GPU through Metal."
        return ("cpu",), "cpu", "Intel Macs run local models on the processor."
    ranked: list[str] = []
    reason = "No GPU suitable for local models was found, so models run on the processor."
    recommended = "cpu"
    nvidia = [gpu for gpu in gpus if gpu.vendor == _NVIDIA]
    if nvidia and any(gpu.cuda_version for gpu in nvidia):
        ranked.append("cuda")
        recommended = "cuda"
        reason = f"{nvidia[0].name} runs local models fastest through CUDA."
    others = [gpu for gpu in gpus if gpu.vendor != _APPLE]
    if vulkan and others:
        ranked.append("vulkan")
        discrete = [gpu for gpu in others if gpu.discrete]
        if recommended == "cpu" and discrete:
            recommended = "vulkan"
            reason = f"{discrete[0].name} runs local models through Vulkan."
        elif recommended == "cpu":
            reason = (
                "Only an integrated GPU was found; models run on the processor. "
                "Vulkan is available if you want to try the GPU."
            )
    elif nvidia and not any(gpu.cuda_version for gpu in nvidia):
        reason = "An NVIDIA GPU was found but its driver did not report a CUDA version; update the driver to use it."
    ranked.append("cpu")
    return tuple(ranked), recommended, reason


_cache: tuple[float, HardwareProfile] | None = None
_cache_lock = threading.Lock()
#: GPU memory changes as other programs run; a minute is fresh enough to plan.
CACHE_SECONDS = 60.0


def detect(probe: Probe | None = None, *, force: bool = False) -> HardwareProfile:
    """This machine's profile. Cached for :data:`CACHE_SECONDS` on the real host."""
    global _cache
    host = probe is None
    if host and not force:
        with _cache_lock:
            if _cache is not None and time.monotonic() - _cache[0] < CACHE_SECONDS:
                return _cache[1]
    probe = probe or Probe.host()
    total = total_memory_bytes(probe)
    gpus: list[GpuDevice] = []
    if probe.os in {"windows", "linux"}:
        gpus.extend(nvidia_gpus(probe))
        skip = {_NVIDIA} if gpus else set()
        if probe.os == "linux":
            gpus.extend(_linux_drm_gpus(probe, skip))
        elif host:
            gpus.extend(_windows_registry_gpus(skip))
    apple = apple_gpu(probe, total)
    if apple is not None:
        gpus.append(apple)
    vulkan = vulkan_loader_present(probe)
    backends, recommended, reason = rank_backends(probe.os, probe.arch, gpus, vulkan)
    profile = HardwareProfile(
        os=probe.os,
        arch=probe.arch,
        cpu_cores=os.cpu_count() or 1,
        total_memory_bytes=total,
        available_memory_bytes=available_memory_bytes(probe),
        gpus=tuple(gpus),
        vulkan_available=vulkan,
        metal_available=apple is not None,
        backends=backends,
        recommended_backend=recommended,
        reason=reason,
        detected_at=time.time(),
    )
    if host:
        with _cache_lock:
            _cache = (time.monotonic(), profile)
    return profile


def forget() -> None:
    global _cache
    with _cache_lock:
        _cache = None
