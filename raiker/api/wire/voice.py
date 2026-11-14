# SPDX-License-Identifier: Apache-2.0
"""Voice (voice spec V1/V2): settings, what is installed, and where it runs."""

from __future__ import annotations

from typing_extensions import TypedDict


class VoiceConversationSettings(TypedDict):
    mode: str
    end_silence_ms: int
    barge_in: bool
    speak_tool_progress: bool
    keep_recordings: bool
    labs_hands_free: bool


class VoiceSettingsView(TypedDict):
    profile: str
    english_only: bool
    whisper_model: str | None
    voice: str | None
    speed: float
    idle_unload_minutes: int
    run_on: str
    conversation: VoiceConversationSettings


class VoiceProfileView(TypedDict):
    profile_id: str
    name: str
    audience: str
    speaking: str
    download_bytes: int
    memory_bytes: int
    listening_available: bool
    speaking_available: bool
    recommended: bool


class VoiceComponentView(TypedDict):
    role: str
    item_id: str
    name: str
    licence: str
    size_bytes: int | None
    installed: bool
    installable: bool
    refusal: str | None
    pending_reason: str | None
    source_page: str


class VoiceListeningView(TypedDict):
    #: off, not_installed, installed, ready, paused, unavailable
    state: str
    components: list[VoiceComponentView]
    device: str | None
    #: ``server`` (the catalogue's whisper-server) or ``builtin`` (Raiker's own
    #: listening worker, where no verified build exists for this machine).
    engine: str


class VoiceSpeakingView(TypedDict):
    state: str
    engine: str
    components: list[VoiceComponentView]
    voices: list[str]


class VoicePlacementView(TypedDict):
    engine: str
    device: str
    gpu_name: str | None
    threads: int
    ram_bytes: int
    vram_bytes: int
    reason: str


class VoicePlanView(TypedDict):
    fits: bool
    sentence: str
    smaller_profile: str | None
    placements: list[VoicePlacementView]


class VoiceHardwareView(TypedDict):
    os: str
    arch: str
    total_memory_bytes: int | None
    gpu: str | None


class VoiceRuntimeView(TypedDict):
    """Whether the Python packages each side runs on are importable here."""

    speaking: bool
    listening: bool
    #: A source run that Install may add the hash-locked packages to.
    installable: bool


class VoiceStatus(TypedDict):
    settings: VoiceSettingsView
    recommended_profile: str
    recommendation: str
    profiles: list[VoiceProfileView]
    listening: VoiceListeningView
    speaking: VoiceSpeakingView
    plan: VoicePlanView
    runtime: VoiceRuntimeView
    disk_bytes: int
    hardware: VoiceHardwareView


class VoiceRemoved(TypedDict):
    freed_bytes: int


class VoiceTestResult(TypedDict):
    spoke: bool
    heard: bool
    transcript: str | None
    #: Word error rate of the round trip, 0–1, when both directions ran.
    word_error_rate: float | None
    seconds: float
    reason_code: str | None
