"""Voice for one owner: what they chose, what is installed, and using it.

The settings live in the owner's settings blob under ``voice_engines`` (the
older ``voice`` key holds the hand-configured transcription server from
BUG-256 and is left alone, so an owner who set one up keeps it). Reading the
status contacts nothing and starts nothing; installing runs as a model
operation; using listening or speaking starts the engine on demand.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from raiker.contracts.ids import utc_now
from raiker.models.llama_cpp.hardware import HardwareProfile, detect
from raiker.voice import installer
from raiker.voice.catalogue import Catalogue, CatalogueItem, load
from raiker.voice.engines import VoiceEngineError, VoiceEngines, engines_for
from raiker.voice.planner import VoicePlan, plan
from raiker.voice.profiles import PROFILE_ORDER, ResolvedProfile, recommend, resolve

PROFILES = ("off", *PROFILE_ORDER)
SETTINGS_KEY = "voice_engines"


@dataclass(frozen=True)
class ConversationSettings:
    #: ``push_to_talk`` ships; ``hands_free`` is Labs in beta (spec §6.2).
    mode: str = "push_to_talk"
    end_silence_ms: int = 500
    barge_in: bool = True
    speak_tool_progress: bool = False
    keep_recordings: bool = False
    labs_hands_free: bool = False


@dataclass(frozen=True)
class VoiceSettings:
    profile: str = "off"
    english_only: bool = False
    whisper_model: str | None = None
    voice: str | None = None
    speed: float = 1.0
    idle_unload_minutes: int = 10
    run_on: str = "auto"
    conversation: ConversationSettings = field(default_factory=ConversationSettings)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clamp(value: Any, low: float, high: float, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def parse_settings(raw: Any, catalogue: Catalogue | None = None) -> VoiceSettings:
    """Read the stored section back; anything malformed falls back to its default."""
    if not isinstance(raw, dict):
        return VoiceSettings()
    catalogue = catalogue or load()
    convo_raw = raw.get("conversation")
    convo: dict[str, Any] = convo_raw if isinstance(convo_raw, dict) else {}
    whisper_model = raw.get("whisper_model")
    if not isinstance(whisper_model, str) or whisper_model not in {
        item.item_id for item in catalogue.of("whisper_model")
    }:
        whisper_model = None
    voice = raw.get("voice") if isinstance(raw.get("voice"), str) and len(raw["voice"]) <= 40 else None
    profile = str(raw.get("profile")) if raw.get("profile") in PROFILES else "off"
    run_on = str(raw.get("run_on")) if raw.get("run_on") in {"auto", "cpu", "gpu"} else "auto"
    mode = str(convo.get("mode")) if convo.get("mode") in {"push_to_talk", "hands_free"} else "push_to_talk"
    return VoiceSettings(
        profile=profile,
        english_only=bool(raw.get("english_only")),
        whisper_model=whisper_model,
        voice=voice,
        speed=_clamp(raw.get("speed"), 0.5, 2.0, 1.0),
        idle_unload_minutes=int(_clamp(raw.get("idle_unload_minutes"), 1, 120, 10)),
        run_on=run_on,
        conversation=ConversationSettings(
            mode=mode,
            end_silence_ms=int(_clamp(convo.get("end_silence_ms"), 250, 1500, 500)),
            barge_in=bool(convo.get("barge_in", True)),
            speak_tool_progress=bool(convo.get("speak_tool_progress", False)),
            keep_recordings=bool(convo.get("keep_recordings", False)),
            labs_hands_free=bool(convo.get("labs_hands_free", False)),
        ),
    )


class VoiceService:
    def __init__(
        self,
        workspace_root: str | Path,
        principal_id: str,
        *,
        catalogue: Catalogue | None = None,
        hardware: HardwareProfile | None = None,
        engines: VoiceEngines | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root)
        self.principal_id = principal_id
        self.catalogue = catalogue or load()
        self._hardware = hardware
        self.engines = engines or engines_for(workspace_root)

    # ── settings ───────────────────────────────────────────────────────

    def _blob(self) -> dict[str, Any]:
        from raiker.storage.sqlite import SQLiteStore

        row = SQLiteStore(self.workspace_root).get_user_settings(self.principal_id)
        if row is None:
            return {}
        try:
            parsed = json.loads(row["settings_json"])
        except (ValueError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def settings(self) -> VoiceSettings:
        return parse_settings(self._blob().get(SETTINGS_KEY), self.catalogue)

    def save(self, changes: dict[str, Any]) -> VoiceSettings:
        from raiker.storage.sqlite import SQLiteStore

        current = self.settings().to_dict()
        conversation = dict(current["conversation"])
        if isinstance(changes.get("conversation"), dict):
            conversation.update({k: v for k, v in changes["conversation"].items() if v is not None})
        merged = {**current, **{k: v for k, v in changes.items() if v is not None and k != "conversation"}}
        merged["conversation"] = conversation
        if "whisper_model" in changes and changes["whisper_model"] in {"", None}:
            merged["whisper_model"] = None
        settings = parse_settings(merged, self.catalogue)
        blob = self._blob()
        blob[SETTINGS_KEY] = settings.to_dict()
        SQLiteStore(self.workspace_root).put_user_settings(self.principal_id, json.dumps(blob), utc_now())
        if settings.profile == "off":
            self.engines.stop_all(reason="off")
        return settings

    # ── what this machine gets ─────────────────────────────────────────

    @property
    def hardware(self) -> HardwareProfile:
        if self._hardware is None:
            self._hardware = detect()
        return self._hardware

    def resolved(self, settings: VoiceSettings | None = None, profile_id: str | None = None) -> ResolvedProfile | None:
        settings = settings or self.settings()
        chosen = profile_id or settings.profile
        if chosen == "off" or chosen not in self.catalogue.profiles:
            return None
        return resolve(self.catalogue, chosen, self.hardware, english_only=settings.english_only,
                       whisper_model=settings.whisper_model)

    def voice_plan(self, settings: VoiceSettings | None = None) -> VoicePlan | None:
        settings = settings or self.settings()
        profile = self.resolved(settings)
        if profile is None:
            return None
        return plan(profile, self.hardware, self.engines.ledger, run_on=settings.run_on)

    def _component_view(self, role: str, item: CatalogueItem) -> dict[str, Any]:
        installed = item.bundled or installer.is_installed(self.workspace_root, item)
        refusal = None if installed else item.refusal()
        return {
            "role": role,
            "item_id": item.item_id,
            "name": item.name,
            "licence": item.licence,
            "size_bytes": item.display_size,
            "installed": installed,
            "installable": item.installable,
            "refusal": refusal,
            "pending_reason": item.raw.get("pending_reason"),
            "source_page": item.source_page,
        }

    def status(self) -> dict[str, Any]:
        settings = self.settings()
        recommended, why = recommend(self.hardware)
        profiles = []
        for profile_id in PROFILE_ORDER:
            resolved = resolve(self.catalogue, profile_id, self.hardware, english_only=settings.english_only)
            profiles.append({
                "profile_id": profile_id,
                "name": resolved.name,
                "audience": resolved.audience,
                "speaking": resolved.speaking,
                "download_bytes": resolved.download_bytes,
                "memory_bytes": resolved.memory_bytes,
                "listening_available": resolved.listening_installable,
                "speaking_available": resolved.speaking_installable,
                "recommended": profile_id == recommended,
            })
        chosen = self.resolved(settings)
        components = [self._component_view(c.role, c.item) for c in chosen.components] if chosen else []
        listening = [c for c in components if c["role"] in {"whisper_engine", "whisper_model"}]
        speaking = [c for c in components if c["role"] not in {"whisper_engine", "whisper_model"}]
        engines = self.engines.status()
        voice_plan = self.voice_plan(settings)

        def state(parts: list[dict[str, Any]], engine: str) -> str:
            if not chosen or not parts:
                return "off"
            if engines[engine]["running"]:
                return "ready"
            if all(part["installed"] for part in parts):
                return "paused" if engines[engine]["paused_reason"] in {"idle", "memory"} else "installed"
            if any(part["refusal"] for part in parts if not part["installed"]):
                return "unavailable"
            return "not_installed"

        voices: list[str] = []
        if chosen and chosen.speaking == "kokoro":
            voices_item = chosen.part("kokoro_voices")
            voices = list(voices_item.voices) if voices_item else []
        return {
            "settings": settings.to_dict(),
            "recommended_profile": recommended,
            "recommendation": why,
            "profiles": profiles,
            "listening": {"state": state(listening, "whisper"), "components": listening,
                          "device": engines["whisper"]["device"]},
            "speaking": {"state": state(speaking, "speaker"), "engine": chosen.speaking if chosen else "system",
                         "components": speaking, "voices": voices},
            "plan": {
                "fits": voice_plan.fits if voice_plan else True,
                "sentence": voice_plan.sentence if voice_plan else "Voice is off.",
                "smaller_profile": voice_plan.smaller_profile if voice_plan else None,
                "placements": [asdict(p) for p in voice_plan.placements] if voice_plan else [],
            },
            "disk_bytes": installer.installed_bytes(self.workspace_root),
            "hardware": {
                "os": self.hardware.os, "arch": self.hardware.arch,
                "total_memory_bytes": self.hardware.total_memory_bytes,
                "gpu": (g.name if (g := self.hardware.gpu_for(self.hardware.recommended_backend)) else None),
            },
        }

    # ── installing ─────────────────────────────────────────────────────

    def installable_items(self, profile_id: str | None = None) -> list[CatalogueItem]:
        """What an install downloads: each side (listening, speaking) only when
        every part of it can be installed. An engine without its model, or a
        model without its engine, is disk spent on nothing."""
        resolved = self.resolved(profile_id=profile_id)
        if resolved is None:
            return []
        listening_roles = {"whisper_engine", "whisper_model"}
        items: list[CatalogueItem] = []
        if resolved.listening_installable:
            items += [c.item for c in resolved.components if c.role in listening_roles]
        if resolved.speaking_installable:
            items += [c.item for c in resolved.components if c.role not in listening_roles]
        return items

    def remove(self) -> int:
        self.engines.stop_all(reason="removed")
        return installer.remove_all(self.workspace_root)

    # ── using ──────────────────────────────────────────────────────────

    def _path(self, item: CatalogueItem | None) -> Path | None:
        return installer.installed_path(self.workspace_root, item) if item is not None else None

    def _placement(self, settings: VoiceSettings, engine: str) -> Any:
        voice_plan = self.voice_plan(settings)
        if voice_plan is None:
            raise VoiceEngineError("voice_off")
        if not voice_plan.fits:
            raise VoiceEngineError(voice_plan.reason_code or "voice_profile_does_not_fit")
        return next((p for p in voice_plan.placements if p.engine == engine), None)

    def listening_endpoint(self) -> str:
        """Start (or reuse) the managed Whisper engine and return its address."""
        settings = self.settings()
        resolved = self.resolved(settings)
        if resolved is None:
            raise VoiceEngineError("voice_off")
        executable = self._path(resolved.part("whisper_engine"))
        model = self._path(resolved.part("whisper_model"))
        if executable is None or model is None:
            raise VoiceEngineError("voice_listening_not_installed")
        placement = self._placement(settings, "whisper")
        self.engines.idle_seconds = settings.idle_unload_minutes * 60.0
        engine = self.engines.ensure_whisper(
            executable, model, threads=placement.threads if placement else 4,
            device=placement.device if placement else "cpu",
            ram=placement.ram_bytes if placement else 0, vram=placement.vram_bytes if placement else 0,
            gpu=placement.gpu_name if placement else None,
        )
        return engine.endpoint

    def listening_ready(self) -> bool:
        resolved = self.resolved()
        if resolved is None:
            return False
        return all(installer.is_installed(self.workspace_root, c.item)
                   for c in resolved.components if c.role in {"whisper_engine", "whisper_model"}) and any(
            c.role == "whisper_model" for c in resolved.components)

    def speak(self, text: str) -> bytes:
        """Start (or reuse) the speaking engine and return ``text`` as WAV audio."""
        settings = self.settings()
        resolved = self.resolved(settings)
        if resolved is None:
            raise VoiceEngineError("voice_off")
        placement = self._placement(settings, resolved.speaking)
        self.engines.idle_seconds = settings.idle_unload_minutes * 60.0
        threads = placement.threads if placement else 2
        ram = placement.ram_bytes if placement else 0
        if resolved.speaking == "kokoro":
            model = self._path(resolved.part("kokoro_model"))
            voices = self._path(resolved.part("kokoro_voices"))
            if model is None or voices is None:
                raise VoiceEngineError("voice_speaking_not_installed")
            self.engines.ensure_speaker("kokoro", model=model, voices=voices, threads=threads, ram=ram)
        elif resolved.speaking == "piper":
            piper = self._path(resolved.part("piper_engine"))
            voice = self._path(resolved.part("piper_voice"))
            if piper is None or voice is None:
                raise VoiceEngineError("voice_speaking_not_installed")
            self.engines.ensure_speaker("piper", model=voice, piper=piper, threads=threads, ram=ram)
        else:
            raise VoiceEngineError("voice_speaking_system")
        return self.engines.synthesise(text, voice=settings.voice, speed=settings.speed)


def with_profile(settings: VoiceSettings, profile: str) -> VoiceSettings:
    return replace(settings, profile=profile)
