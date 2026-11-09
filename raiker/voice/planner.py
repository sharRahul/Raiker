# SPDX-License-Identifier: Apache-2.0
"""Where each voice engine runs: processor or GPU, and how many threads.

Voice spec §7, placement policy:

1. A local thinking model keeps priority on the GPU; voice uses what is left.
2. Whisper goes on the GPU only if, after everything already planned, free
   VRAM covers Whisper plus 512 MB. Otherwise the processor, with threads at
   half the physical cores, at most 8.
3. Kokoro runs on the processor unless the profile is High quality and the GPU
   has room.
4. Voice activity detection runs in the client.

A profile that does not fit in system memory next to what is already held is
refused with the next smaller profile named, never started anyway.
"""

from __future__ import annotations

from dataclasses import dataclass

from raiker.models.engines.resources import ResourceLedger
from raiker.models.llama_cpp.hardware import MIB, HardwareProfile
from raiker.voice.profiles import PROFILE_ORDER, ResolvedProfile

WHISPER_GPU_HEADROOM = 512 * MIB
#: Kept free for the operating system and everything else on the computer.
SYSTEM_RESERVE = 2 * 1024 * MIB


@dataclass(frozen=True)
class Placement:
    engine: str
    device: str  # "cpu" or a backend name ("cuda", "metal", "vulkan")
    gpu_name: str | None
    threads: int
    ram_bytes: int
    vram_bytes: int
    reason: str


@dataclass(frozen=True)
class VoicePlan:
    fits: bool
    placements: tuple[Placement, ...]
    #: One sentence for the owner (spec §6.2, Resources).
    sentence: str
    #: When it does not fit: the next smaller profile to offer.
    smaller_profile: str | None = None
    reason_code: str | None = None


def cpu_threads(hardware: HardwareProfile) -> int:
    physical = max(1, hardware.cpu_cores // 2)
    return max(1, min(8, physical))


def plan(
    profile: ResolvedProfile,
    hardware: HardwareProfile,
    ledger: ResourceLedger,
    *,
    run_on: str = "auto",
) -> VoicePlan:
    """Place ``profile``'s engines next to what ``ledger`` already holds."""
    held_ram, held_vram = ledger.committed()
    placements: list[Placement] = []
    threads = cpu_threads(hardware)
    gpu_backend = next((b for b in hardware.backends if b in {"cuda", "metal", "vulkan"}), None)
    gpu = hardware.gpu_for(gpu_backend) if gpu_backend else None
    gpu_key = gpu.name if gpu is not None else None
    gpu_free = 0
    if gpu is not None:
        total = gpu.memory_free_bytes or gpu.memory_total_bytes or 0
        gpu_free = max(0, total - held_vram.get(gpu_key or "", 0))
        if gpu.unified_memory:
            gpu_free = 0  # shared with system memory; counted there instead

    whisper = profile.part("whisper_model")
    if whisper is not None:
        need_gpu = (whisper.memory_bytes_gpu or 0) + WHISPER_GPU_HEADROOM
        on_gpu = (
            run_on != "cpu"
            and gpu is not None
            and gpu_backend is not None
            and (gpu.unified_memory or gpu_free >= need_gpu)
            and gpu_backend in {"cuda", "metal", "vulkan"}
        )
        if run_on == "gpu" and not on_gpu:
            reason = "There is not enough graphics memory free, so speech recognition runs on the processor."
        elif on_gpu:
            reason = f"Speech recognition runs on your {gpu.name if gpu else 'GPU'}."
        elif gpu is not None and run_on != "cpu":
            reason = "Speech recognition runs on the processor because the GPU is busy with the model you chose."
        else:
            reason = f"Speech recognition runs on the processor with {threads} threads."
        vram = (whisper.memory_bytes_gpu or 0) if on_gpu and not (gpu and gpu.unified_memory) else 0
        if on_gpu and gpu is not None and not gpu.unified_memory:
            gpu_free -= vram
        placements.append(Placement(
            engine="whisper",
            device=gpu_backend if on_gpu and gpu_backend else "cpu",
            gpu_name=gpu.name if on_gpu and gpu is not None else None,
            threads=threads,
            ram_bytes=(whisper.memory_bytes_cpu or 0) if not on_gpu or (gpu and gpu.unified_memory) else 200 * MIB,
            vram_bytes=vram,
            reason=reason,
        ))

    if profile.speaking == "kokoro":
        model = profile.part("kokoro_model")
        need = (model.memory_bytes_cpu or 0) if model else 0
        placements.append(Placement(
            engine="kokoro", device="cpu", gpu_name=None, threads=min(4, threads),
            ram_bytes=need, vram_bytes=0,
            reason="Speech runs on the processor.",
        ))

    needed = sum(item.ram_bytes for item in placements)
    available = hardware.available_memory_bytes
    if available is None and hardware.total_memory_bytes is not None:
        available = hardware.total_memory_bytes - held_ram
    if available is not None and needed + SYSTEM_RESERVE > max(0, available):
        index = PROFILE_ORDER.index(profile.profile_id) if profile.profile_id in PROFILE_ORDER else 0
        smaller = PROFILE_ORDER[index - 1] if index > 0 else None
        return VoicePlan(
            fits=False,
            placements=tuple(placements),
            sentence=(
                f"{profile.name} does not fit next to what is already running."
                + (f" Try {smaller.capitalize()}." if smaller else "")
            ),
            smaller_profile=smaller,
            reason_code="voice_profile_does_not_fit",
        )
    sentence = placements[0].reason if placements else "Nothing to run."
    return VoicePlan(fits=True, placements=tuple(placements), sentence=sentence)
