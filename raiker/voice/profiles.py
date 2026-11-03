"""Voice profiles made concrete for this machine, and the one to recommend.

Voice spec §4. A profile chooses the *speech* components only — the model that
thinks is always the owner's own choice and never part of a profile. Here a
profile becomes a concrete component list for this machine (which engine
build, which Whisper file, which speaking model), each marked installable or
not and why, and the hardware probe picks the profile to recommend.
"""

from __future__ import annotations

from dataclasses import dataclass

from raiker.models.llama_cpp.hardware import GIB, HardwareProfile
from raiker.voice.catalogue import Catalogue, CatalogueItem

PROFILE_ORDER = ("lite", "balanced", "high")


@dataclass(frozen=True)
class Component:
    role: str
    item: CatalogueItem

    @property
    def refusal(self) -> str | None:
        return self.item.refusal()


@dataclass(frozen=True)
class ResolvedProfile:
    profile_id: str
    name: str
    audience: str
    speaking: str
    components: tuple[Component, ...]

    @property
    def download_bytes(self) -> int:
        return sum(component.item.display_size or 0 for component in self.components)

    @property
    def memory_bytes(self) -> int:
        return sum(component.item.memory_bytes_cpu or 0 for component in self.components)

    @property
    def missing(self) -> tuple[Component, ...]:
        return tuple(component for component in self.components if component.refusal is not None)

    @property
    def installable(self) -> bool:
        return not self.missing

    def part(self, role: str) -> CatalogueItem | None:
        return next((component.item for component in self.components if component.role == role), None)

    @property
    def listening_installable(self) -> bool:
        parts = [c for c in self.components if c.role in {"whisper_engine", "whisper_model"}]
        return bool(parts) and all(c.refusal is None for c in parts)

    @property
    def speaking_installable(self) -> bool:
        parts = [c for c in self.components if c.role not in {"whisper_engine", "whisper_model"}]
        return bool(parts) and all(c.refusal is None for c in parts)


def _whisper_backends(hardware: HardwareProfile) -> tuple[str, ...]:
    return tuple(backend for backend in hardware.backends if backend in {"cuda", "metal", "vulkan"}) + ("cpu",)


def _gpu_room(hardware: HardwareProfile) -> int:
    gpu = hardware.gpu_for(hardware.recommended_backend)
    if gpu is None:
        return 0
    return gpu.memory_free_bytes or gpu.memory_total_bytes or 0


def resolve(
    catalogue: Catalogue,
    profile_id: str,
    hardware: HardwareProfile,
    *,
    english_only: bool = False,
    whisper_model: str | None = None,
) -> ResolvedProfile:
    """``profile_id`` as concrete components on this machine."""
    profile = catalogue.profiles[profile_id]
    components: list[Component] = []
    engine = catalogue.engine_for("whisper_engine", hardware.os, hardware.arch, _whisper_backends(hardware))
    if engine is not None:
        components.append(Component("whisper_engine", engine))
    choices = [catalogue.get(item_id) for item_id in profile.listening]
    model: CatalogueItem | None = None
    if whisper_model is not None:
        model = catalogue.get(whisper_model)
    else:
        if english_only:
            model = next((item for item in choices if item.english_only), None)
        if model is None:
            plain = [item for item in choices if not item.english_only]
            # Balanced lists small first and large-v3-turbo second: the bigger
            # one only when a GPU has room for it beside the model (spec §4).
            big = next((item for item in plain if item.tier == "large-v3-turbo"), None)
            if profile_id == "balanced" and big is not None and _gpu_room(hardware) >= 6 * GIB:
                model = big
            else:
                model = plain[0] if plain else (choices[0] if choices else None)
    if model is not None:
        components.append(Component("whisper_model", model))
    if profile.speaking == "piper":
        piper = catalogue.engine_for("piper_engine", hardware.os, hardware.arch)
        if piper is not None:
            components.append(Component("piper_engine", piper))
        for item_id in profile.speaking_items:
            components.append(Component("piper_voice", catalogue.get(item_id)))
    elif profile.speaking == "kokoro":
        for item_id in profile.speaking_items:
            item = catalogue.get(item_id)
            components.append(Component(item.component, item))
    return ResolvedProfile(
        profile_id=profile_id,
        name=profile.name,
        audience=profile.audience,
        speaking=profile.speaking,
        components=tuple(components),
    )


def recommend(hardware: HardwareProfile) -> tuple[str, str]:
    """The profile for this machine, and one sentence saying why.

    Memory decides first, because every engine needs it; a GPU with room moves
    a capable machine up to High quality.
    """
    total = hardware.total_memory_bytes or 0
    gpu = hardware.gpu_for(hardware.recommended_backend)
    gpu_name = gpu.name if gpu is not None else None
    vram = _gpu_room(hardware)
    if total >= 32 * GIB or (gpu is not None and gpu.discrete and vram >= 12 * GIB):
        why = f"{gpu_name} has room for the largest speech model." if gpu_name and vram >= 12 * GIB else (
            "This computer has enough memory for the largest speech models."
        )
        return "high", why
    if total >= 14 * GIB:
        if gpu_name and gpu is not None and gpu.discrete:
            return "balanced", f"Your {gpu_name} can run speech recognition next to a local model."
        return "balanced", "This computer has enough memory for natural-sounding speech."
    return "lite", "The smallest speech engines keep up on this computer without a graphics card."
