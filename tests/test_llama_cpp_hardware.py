"""Hardware detection and backend choice, described for each platform on any host."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from raiker.models.llama_cpp import hardware
from raiker.models.llama_cpp.hardware import GpuDevice, Probe, rank_backends

GIB = 1024**3
NVIDIA_HEADER = """
+-----------------------------------------------------------------------------+
| NVIDIA-SMI 550.54       Driver Version: 550.54       CUDA Version: 12.4     |
"""
MEMINFO = "MemTotal:       32000000 kB\nMemFree:  1000 kB\nMemAvailable:   20000000 kB\n"


def _probe(
    os_name: str = "linux",
    arch: str = "x64",
    *,
    commands: dict[str, str] | None = None,
    files: dict[str, str] | None = None,
    which: dict[str, str] | None = None,
) -> Probe:
    commands = commands or {}
    files = files or {}
    which = which or {}

    def run(argv: Sequence[str]) -> str | None:
        # Real Windows renders paths with backslashes; the table uses "/".
        key = " ".join(argv).replace("\\", "/")
        for prefix, output in commands.items():
            if key.startswith(prefix):
                return output
        return None

    def glob(root: str, pattern: str) -> list[Path]:
        prefix = root.rstrip("/") + "/"
        cards = {
            path[len(prefix):].split("/")[0]
            for path in files
            if path.startswith(prefix)
        }
        return sorted(Path(prefix + card) for card in cards if card.startswith("card"))

    return Probe(
        os=os_name,  # type: ignore[arg-type]
        arch=arch,  # type: ignore[arg-type]
        run=run,
        read=lambda path: files.get(path.as_posix()),
        exists=lambda path: path.as_posix() in files or any(
            key.startswith(path.as_posix() + "/") for key in files
        ),
        glob=glob,
        which=lambda name: which.get(name),
        environ={"SYSTEMROOT": "C:/Windows"},
    )


def test_linux_nvidia_reports_vram_and_cuda_and_recommends_cuda() -> None:
    probe = _probe(
        commands={
            "/usr/bin/nvidia-smi --query-gpu": "NVIDIA GeForce RTX 4070, 12282, 11000\n",
            "/usr/bin/nvidia-smi": NVIDIA_HEADER,
        },
        files={"/proc/meminfo": MEMINFO, "/usr/lib/x86_64-linux-gnu/libvulkan.so.1": ""},
        which={"nvidia-smi": "/usr/bin/nvidia-smi"},
    )
    profile = hardware.detect(probe)
    assert profile.recommended_backend == "cuda"
    assert profile.backends == ("cuda", "vulkan", "cpu")
    gpu = profile.gpu_for("cuda")
    assert gpu is not None and gpu.cuda_version == "12.4"
    assert gpu.memory_total_bytes == 12282 * 1024**2
    assert gpu.memory_free_bytes == 11000 * 1024**2
    assert profile.available_memory_bytes == 20000000 * 1024
    assert profile.total_memory_bytes == 32000000 * 1024


def test_linux_amd_discrete_gpu_uses_vulkan_with_sysfs_vram() -> None:
    probe = _probe(
        files={
            "/proc/meminfo": MEMINFO,
            "/usr/lib64/libvulkan.so.1": "",
            "/sys/class/drm/card1/device/vendor": "0x1002\n",
            "/sys/class/drm/card1/device/mem_info_vram_total": str(16 * GIB),
            "/sys/class/drm/card1/device/mem_info_vram_used": str(1 * GIB),
            "/sys/class/drm/card1-DP-1/status": "connected",
        },
    )
    profile = hardware.detect(probe)
    assert profile.recommended_backend == "vulkan"
    assert profile.backends == ("vulkan", "cpu")
    gpu = profile.gpu_for("vulkan")
    assert gpu is not None and gpu.discrete and gpu.memory_free_bytes == 15 * GIB


def test_integrated_gpu_is_offered_but_not_recommended() -> None:
    probe = _probe(
        files={
            "/proc/meminfo": MEMINFO,
            "/usr/lib/libvulkan.so.1": "",
            "/sys/class/drm/card0/device/vendor": "0x8086",
        },
    )
    profile = hardware.detect(probe)
    assert profile.backends == ("vulkan", "cpu")
    assert profile.recommended_backend == "cpu"
    assert "integrated" in profile.reason.lower()


def test_gpu_without_vulkan_loader_falls_back_to_cpu() -> None:
    probe = _probe(
        files={
            "/proc/meminfo": MEMINFO,
            "/sys/class/drm/card0/device/vendor": "0x1002",
            "/sys/class/drm/card0/device/mem_info_vram_total": str(8 * GIB),
        },
    )
    assert hardware.detect(probe).backends == ("cpu",)


def test_apple_silicon_uses_metal_with_a_unified_memory_budget() -> None:
    probe = _probe(
        "macos",
        "arm64",
        commands={
            "/usr/sbin/sysctl -n hw.memsize": str(16 * GIB),
            "/usr/sbin/sysctl -n machdep.cpu.brand_string": "Apple M2",
            "/usr/bin/vm_stat": "Mach Virtual Memory Statistics: (page size of 16384 bytes)\n"
            "Pages free:   100000.\nPages inactive:  50000.\n",
        },
    )
    profile = hardware.detect(probe)
    assert profile.recommended_backend == "metal"
    assert profile.metal_available
    gpu = profile.gpu_for("metal")
    assert gpu is not None and gpu.unified_memory
    assert gpu.memory_total_bytes == int(16 * GIB * 0.67)
    assert profile.available_memory_bytes == 150000 * 16384


def test_large_mac_gets_three_quarters_for_the_gpu() -> None:
    probe = _probe("macos", "arm64", commands={"/usr/sbin/sysctl -n hw.memsize": str(64 * GIB)})
    gpu = hardware.detect(probe).gpu_for("metal")
    assert gpu is not None and gpu.memory_total_bytes == int(64 * GIB * 0.75)


def test_intel_mac_runs_on_cpu() -> None:
    probe = _probe("macos", "x64", commands={"/usr/sbin/sysctl -n hw.memsize": str(8 * GIB)})
    profile = hardware.detect(probe)
    assert profile.backends == ("cpu",) and profile.recommended_backend == "cpu"


def test_windows_nvidia_found_in_system32_without_path() -> None:
    probe = _probe(
        "windows",
        commands={
            "C:/Windows/System32/nvidia-smi.exe --query-gpu": "NVIDIA RTX A2000, 6144, 5000\n",
            "C:/Windows/System32/nvidia-smi.exe": NVIDIA_HEADER.replace("12.4", "13.0"),
        },
        files={"C:/Windows/System32/nvidia-smi.exe": "", "C:/Windows/System32/vulkan-1.dll": ""},
    )
    profile = hardware.detect(probe)
    assert profile.recommended_backend == "cuda"
    assert profile.gpus[0].cuda_version == "13.0"
    assert "vulkan" in profile.backends


def test_nvidia_driver_without_cuda_version_is_explained() -> None:
    gpus = [GpuDevice("nvidia", "Old GPU", GIB, GIB, True, cuda_version=None)]
    backends, recommended, reason = rank_backends("linux", "x64", gpus, vulkan=False)
    assert backends == ("cpu",) and recommended == "cpu"
    assert "driver" in reason


def test_failing_nvidia_smi_is_unknown_not_an_error() -> None:
    probe = _probe(files={"/proc/meminfo": MEMINFO}, which={"nvidia-smi": "/usr/bin/nvidia-smi"})
    profile = hardware.detect(probe)
    assert profile.gpus == () and profile.recommended_backend == "cpu"


def test_real_host_detection_runs_and_is_cached() -> None:
    hardware.forget()
    first = hardware.detect()
    assert first.backends[-1] == "cpu"
    assert first.recommended_backend in first.backends
    assert hardware.detect() is first
    assert hardware.detect(force=True) is not first
