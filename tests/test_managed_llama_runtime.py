"""The managed llama.cpp runtime serves several GGUF models at once.

A single managed server meant deploying a second GGUF silently replaced the
first, so a local-only owner could never put Chat on a small model and Build on
a large one. The runtime now manages a bounded set of numbered slots, each with
its own port, its own served alias, and its own shipped profile, so each is an
ordinary selectable model everywhere a model can be selected.

Bounded on purpose: every slot is a resident process holding model weights in
memory, and an unbounded pool is a way to exhaust a laptop by clicking Deploy.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.models.local_runtime import LOCAL_SLOTS, ManagedLlamaRuntime


class FakeProcess:
    def __init__(self) -> None:
        self.pid = 42
        self.alive = True

    def poll(self) -> int | None:
        return None if self.alive else 0

    def terminate(self) -> None:
        self.alive = False

    def wait(self, timeout: int) -> int:
        return 0


def _runtime(
    calls: list[tuple[str, ...]], roots: tuple[Path, ...], stopped: list[str] | None = None
) -> ManagedLlamaRuntime:
    def launch(argv: list[str]) -> FakeProcess:
        calls.append(tuple(argv))
        return FakeProcess()

    return ManagedLlamaRuntime(
        launch,
        approved_roots=roots,
        on_stopped=(lambda path: stopped.append(path)) if stopped is not None else None,
    )


def test_managed_runtime_uses_argv_and_owner_approved_model(tmp_path: Path) -> None:
    model = tmp_path / "model.gguf"
    model.write_bytes(b"GGUF")
    calls: list[tuple[str, ...]] = []
    invalidated: list[str] = []
    runtime = _runtime(calls, (tmp_path,), invalidated)

    status = runtime.start(model, executable=Path("llama-server"), port=18080)

    assert status.running is True
    assert calls == [
        (
            "llama-server",
            "--model",
            str(model.resolve()),
            "--alias",
            "local-gguf",
            "--host",
            "127.0.0.1",
            "--port",
            "18080",
        )
    ]
    assert runtime.stop().running is False
    assert invalidated == [str(model.resolve())]


def test_two_models_serve_at_once_on_their_own_ports_and_aliases(tmp_path: Path) -> None:
    small = tmp_path / "small.gguf"
    large = tmp_path / "large.gguf"
    small.write_bytes(b"GGUF")
    large.write_bytes(b"GGUF")
    calls: list[tuple[str, ...]] = []
    runtime = _runtime(calls, (tmp_path,))

    first = runtime.start(small, executable=Path("llama-server"))
    second = runtime.start(large, executable=Path("llama-server"))

    assert first.slot != second.slot
    assert first.model_path == str(small.resolve())
    # The first server is still up: a second deployment adds, it does not replace.
    assert runtime.status(first.slot).running is True
    assert runtime.status(second.slot).running is True
    ports = sorted(call[call.index("--port") + 1] for call in calls)
    aliases = sorted(call[call.index("--alias") + 1] for call in calls)
    assert len(set(ports)) == 2, "each slot binds its own port"
    assert len(set(aliases)) == 2, "each slot serves its own model name"


def test_redeploying_the_same_model_reuses_its_slot(tmp_path: Path) -> None:
    model = tmp_path / "model.gguf"
    model.write_bytes(b"GGUF")
    runtime = _runtime([], (tmp_path,))

    first = runtime.start(model, executable=Path("llama-server"))
    again = runtime.start(model, executable=Path("llama-server"))

    assert again.slot == first.slot
    assert len(runtime.statuses()) == 1


def test_a_full_pool_refuses_rather_than_evicting_a_running_model(tmp_path: Path) -> None:
    runtime = _runtime([], (tmp_path,))
    for index in range(len(LOCAL_SLOTS)):
        model = tmp_path / f"model-{index}.gguf"
        model.write_bytes(b"GGUF")
        runtime.start(model, executable=Path("llama-server"))
    overflow = tmp_path / "one-too-many.gguf"
    overflow.write_bytes(b"GGUF")

    with pytest.raises(ValueError, match="local_runtime_slots_exhausted"):
        runtime.start(overflow, executable=Path("llama-server"))

    # Nothing was evicted to make room.
    assert len(runtime.statuses()) == len(LOCAL_SLOTS)


def test_stopping_one_slot_leaves_the_others_serving(tmp_path: Path) -> None:
    small = tmp_path / "small.gguf"
    large = tmp_path / "large.gguf"
    small.write_bytes(b"GGUF")
    large.write_bytes(b"GGUF")
    stopped: list[str] = []
    runtime = _runtime([], (tmp_path,), stopped)
    first = runtime.start(small, executable=Path("llama-server"))
    second = runtime.start(large, executable=Path("llama-server"))

    runtime.stop(first.slot)

    assert stopped == [str(small.resolve())]
    assert runtime.status(first.slot).running is False
    assert runtime.status(second.slot).running is True


def test_shutdown_stops_every_slot(tmp_path: Path) -> None:
    for name in ("a", "b"):
        (tmp_path / f"{name}.gguf").write_bytes(b"GGUF")
    stopped: list[str] = []
    runtime = _runtime([], (tmp_path,), stopped)
    runtime.start(tmp_path / "a.gguf", executable=Path("llama-server"))
    runtime.start(tmp_path / "b.gguf", executable=Path("llama-server"))

    runtime.stop()

    assert len(stopped) == 2
    assert all(not status.running for status in runtime.statuses())


def test_a_model_outside_the_approved_library_is_still_refused(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.gguf"
    outside.write_bytes(b"GGUF")
    runtime = _runtime([], (tmp_path,))

    with pytest.raises(ValueError, match="model_outside_approved_library"):
        runtime.start(outside, executable=Path("llama-server"))


def test_every_slot_has_a_shipped_profile() -> None:
    """A slot nobody can select is a server running for nothing."""
    from raiker.models.registry import ModelProfileRegistry

    registry = ModelProfileRegistry.load()
    for slot in LOCAL_SLOTS:
        profile = registry.resolve_profile_id(slot.profile_id)
        assert profile.model == slot.alias
        assert str(slot.port) in str(profile.raw["endpoint"])
