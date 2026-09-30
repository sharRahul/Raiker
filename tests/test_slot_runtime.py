"""OPT-10 / OPT-20 — one lifecycle for managed local servers, one slot declaration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from raiker.models.local_runtime import LOCAL_SLOTS, ManagedLlamaRuntime
from raiker.models.mlx_runtime import MLX_SLOTS, ManagedMlxRuntime
from raiker.models.registry import ModelProfileRegistry
from raiker.models.slot_runtime import ManagedSlotRuntime, declared_slots

PROFILES = Path(__file__).resolve().parents[1] / "raiker" / "config" / "model-profiles.json"


def test_the_slots_are_the_profiles_marked_as_slots() -> None:
    """The pools and the picker read one declaration, so they cannot disagree."""
    registry = {p.profile_id: p for p in ModelProfileRegistry.load().list_profiles()}
    for slots in (LOCAL_SLOTS, MLX_SLOTS):
        assert len(slots) == 4
        for slot in slots:
            profile = registry[slot.profile_id]
            assert profile.raw["endpoint"] == f"http://127.0.0.1:{slot.port}"
            assert profile.model == slot.alias
    # The first llama.cpp slot keeps the original single-server identity.
    assert (LOCAL_SLOTS[0].profile_id, LOCAL_SLOTS[0].alias, LOCAL_SLOTS[0].port) == (
        "raiker-local-llama-cpp",
        "local-gguf",
        8080,
    )


def test_every_marked_profile_is_a_loopback_local_one() -> None:
    data = json.loads(PROFILES.read_text(encoding="utf-8"))
    marked = [entry for entry in data["profiles"] if entry.get("managed_slot")]
    assert {entry["provider"] for entry in marked} == {"llama.cpp", "mlx"}
    for entry in marked:
        assert entry["endpoint"].startswith("http://127.0.0.1:"), entry["profile_id"]
        assert entry["local_only"] is True, entry["profile_id"]


def test_a_provider_with_no_slots_is_refused() -> None:
    with pytest.raises(ValueError, match="managed_slots_invalid"):
        declared_slots("anthropic")


def test_both_pools_share_the_lifecycle_and_keep_their_refusal_codes() -> None:
    llama, mlx = ManagedLlamaRuntime(), ManagedMlxRuntime()
    assert isinstance(llama, ManagedSlotRuntime) and isinstance(mlx, ManagedSlotRuntime)
    with pytest.raises(ValueError, match="^unknown_local_runtime_slot$"):
        llama._named_slot("nope")  # noqa: SLF001
    with pytest.raises(ValueError, match="^unknown_mlx_runtime_slot$"):
        mlx._named_slot("nope")  # noqa: SLF001


def test_an_id_that_is_not_a_slot_is_never_reported_as_the_first_slots_state(
    tmp_path: Path,
) -> None:
    class _Alive:
        pid = 7

        def poll(self) -> None:
            return None

    model = tmp_path / "m.gguf"
    model.write_bytes(b"GGUF")
    pool = ManagedLlamaRuntime(lambda _argv: _Alive(), approved_roots=(tmp_path,))
    pool.start(model, executable=Path("llama-server"))

    assert pool.status(LOCAL_SLOTS[0].profile_id).running is True
    assert pool.status("not-a-slot").running is False
