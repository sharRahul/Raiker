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

import contextlib
import threading
from pathlib import Path
from typing import Any

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


class TestConcurrentDeploys:
    """GCR-28 — selecting a slot and occupying it must be one step."""

    def test_two_simultaneous_deploys_take_two_different_slots(
        self, tmp_path: Path
    ) -> None:
        """Slot selection read the process map; the launch came afterwards.

        Two deploys arriving together both saw the same slot free, both
        launched, and the second overwrote the first's map entry — one process
        orphaned and untracked, two of them contending for one port. The launch
        below blocks until both threads are inside it, which is exactly the
        window the old code left open.
        """

        root = tmp_path / "library"
        root.mkdir()
        first = root / "a.gguf"
        second = root / "b.gguf"
        for model in (first, second):
            model.write_bytes(b"gguf")
        executable = tmp_path / "llama-server"
        executable.write_text("llama-server stub", encoding="utf-8")

        both_inside = threading.Barrier(2, timeout=5)
        launched: list[tuple[str, ...]] = []
        lock = threading.Lock()

        def launch(argv: list[str]) -> FakeProcess:
            # Without serialisation both threads reach here holding the same
            # slot. With it, the second cannot start until the first is recorded.
            with contextlib.suppress(threading.BrokenBarrierError):
                both_inside.wait(timeout=0.5)
            with lock:
                launched.append(tuple(argv))
            return FakeProcess()

        runtime = ManagedLlamaRuntime(launch, approved_roots=(root,))
        results: list[Any] = []
        errors: list[BaseException] = []

        def deploy(model: Path) -> None:
            try:
                results.append(runtime.start(model, executable=executable))
            except BaseException as exc:  # noqa: BLE001 - reported below
                errors.append(exc)

        threads = [
            threading.Thread(target=deploy, args=(first,)),
            threading.Thread(target=deploy, args=(second,)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        assert not errors, errors
        assert len(launched) == 2
        # Two deploys, two slots, two ports — never one slot twice.
        assert len({result.slot for result in results}) == 2
        assert len({result.endpoint for result in results}) == 2
        assert len(runtime.statuses()) == 2

    def test_a_launch_that_fails_gives_its_slot_back(self, tmp_path: Path) -> None:
        """A reservation that is never released costs the pool a slot forever."""
        root = tmp_path / "library"
        root.mkdir()
        model = root / "a.gguf"
        model.write_bytes(b"gguf")
        executable = tmp_path / "llama-server"
        executable.write_text("llama-server stub", encoding="utf-8")

        attempts: list[list[str]] = []

        def launch(argv: list[str]) -> FakeProcess:
            attempts.append(argv)
            if len(attempts) == 1:
                raise OSError("could not exec")
            return FakeProcess()

        runtime = ManagedLlamaRuntime(launch, approved_roots=(root,))
        with pytest.raises(OSError, match="could not exec"):
            runtime.start(model, executable=executable)

        # The same first slot is offered again rather than being burnt.
        status = runtime.start(model, executable=executable)
        assert status.slot == LOCAL_SLOTS[0].profile_id


class TestTheReportedPort:
    """GCR-29 — a runtime must report the port it was actually launched on."""

    def test_a_custom_port_is_reported_not_the_slots_declared_one(
        self, tmp_path: Path
    ) -> None:
        """A port outside the declared table runs on the first slot.

        `status()` read that slot's *declared* port, so a server launched on
        9000 told the owner — and every client that believed the endpoint — that
        it was on 8080.
        """
        root = tmp_path / "library"
        root.mkdir()
        model = root / "a.gguf"
        model.write_bytes(b"gguf")
        executable = tmp_path / "llama-server"
        executable.write_text("llama-server stub", encoding="utf-8")

        calls: list[tuple[str, ...]] = []
        runtime = _runtime(calls, (root,))
        status = runtime.start(model, executable=executable, port=9000)

        assert "9000" in calls[0]
        assert status.endpoint == "http://127.0.0.1:9000/v1"
        assert runtime.status(status.slot).endpoint == "http://127.0.0.1:9000/v1"

    def test_stopping_a_slot_forgets_the_port_it_was_bound_to(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "library"
        root.mkdir()
        model = root / "a.gguf"
        model.write_bytes(b"gguf")
        executable = tmp_path / "llama-server"
        executable.write_text("llama-server stub", encoding="utf-8")

        calls: list[tuple[str, ...]] = []
        runtime = _runtime(calls, (root,))
        started = runtime.start(model, executable=executable, port=9000)
        runtime.stop(started.slot)

        restarted = runtime.start(model, executable=executable)
        assert restarted.endpoint == f"http://127.0.0.1:{LOCAL_SLOTS[0].port}/v1"
