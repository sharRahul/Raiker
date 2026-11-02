"""The managed llama.cpp lifecycle against real processes.

A stand-in ``llama-server`` (``tests/fixtures/llama_cpp/fake_llama_server.py``)
speaks the same HTTP surface and fails the same ways as the real one. Each test
starts real child processes on loopback ports and talks to them over HTTP, so
loading, inference, switching models, recovering from out-of-memory and
crashes, restoring after a restart and shutting down are exercised end to end
on every operating system CI runs — with no model download and no GPU.
"""

from __future__ import annotations

import socket
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from raiker.app.launcher import port_is_free
from raiker.models.contracts import ModelMessage
from raiker.models.library import ModelLibraryService
from raiker.models.llama_cpp import installer
from raiker.models.llama_cpp.installer import ResolvedExecutable
from raiker.models.llama_cpp.planner import MemoryBudget, RuntimeSettings
from raiker.models.llama_cpp.process import spawn
from raiker.models.llama_cpp.supervisor import LaunchRefused, LlamaSupervisor
from raiker.models.local_runtime import LOCAL_SLOTS, ManagedLlamaRuntime
from raiker.models.providers.llama_cpp_server import LlamaCppServerProvider
from raiker.models.slot_runtime import RuntimeSlot
from raiker.storage.sqlite import SQLiteStore
from tests.fixtures.llama_cpp.gguf_writer import llama_metadata, write_gguf

FAKE = Path(__file__).parent / "fixtures" / "llama_cpp" / "fake_llama_server.py"
GIB = 1024**3
OWNER = "principal_owner"


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


class Stack:
    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, persist: bool = False) -> None:
        self.workspace = tmp_path / "ws"
        self.workspace.mkdir(exist_ok=True)
        self.library = tmp_path / "models"
        self.library.mkdir(exist_ok=True)
        self.slots = tuple(RuntimeSlot(slot.profile_id, _free_port(), slot.alias) for slot in LOCAL_SLOTS[:2])
        monkeypatch.setattr(
            installer, "resolve_executable",
            lambda _ws: ResolvedExecutable(str(tmp_path / "llama-server"), "managed", "cuda"),
        )
        self.persist = persist
        self.runtime, self.supervisor = self._build()

    def _build(self) -> tuple[ManagedLlamaRuntime, LlamaSupervisor]:
        by_port = {slot.port: slot.profile_id for slot in self.slots}
        holder: dict[str, ManagedLlamaRuntime] = {}

        def launch(argv: list[str]) -> object:
            # The real executable is this test's stand-in, run by this Python.
            slot = by_port[int(argv[argv.index("--port") + 1])]
            log = holder["runtime"].log_path(slot)
            assert log is not None
            return spawn([sys.executable, str(FAKE), *argv[1:]], log_path=log, pid_path=log.with_suffix(".pid"))

        runtime = ManagedLlamaRuntime(launch, workspace_root=self.workspace, slots=self.slots)
        holder["runtime"] = runtime
        supervisor = LlamaSupervisor(
            runtime,
            self.workspace,
            budget_for=lambda backend, committed: MemoryBudget(
                backend, 8 * GIB, False, 24 * GIB, 32 * GIB, committed
            ),
            interval=0.2,
            persist=self.persist,
        )
        return runtime, supervisor

    def model(self, name: str) -> Path:
        return write_gguf(self.library / name, llama_metadata(layers=32), pad_bytes=4096)

    def launch(self, name: str, slot: str | None = None, settings: RuntimeSettings | None = None) -> str:
        health = self.supervisor.launch(
            owner=OWNER, model_id=name, model_path=self.model(name),
            settings=settings or RuntimeSettings(), approved_roots=(self.library,), profile_id=slot,
        )
        return health.slot_profile_id

    def chat(self, slot: str, text: str = "hello") -> str:
        endpoint = self.runtime.status(slot).endpoint
        assert endpoint is not None
        provider = LlamaCppServerProvider(model=self.runtime.slot(slot).alias, endpoint=endpoint.removesuffix("/v1"))  # type: ignore[union-attr]
        assert provider.health(timeout=2.0)
        return provider.chat([ModelMessage(role="user", content=text)]).text


@pytest.fixture
def stack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Stack]:
    built = Stack(tmp_path, monkeypatch)
    yield built
    built.supervisor.shutdown()


def _wait(condition: object, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():  # type: ignore[operator]
            return
        time.sleep(0.1)
    raise AssertionError("condition not reached")


def test_load_and_infer_with_planned_offload_and_context(stack: Stack) -> None:
    slot = stack.launch("qwen.gguf")
    answer = stack.chat(slot, "ping")
    # 32 layers + output fit the 8 GiB budget; auto context is 8K of the 128K trained.
    assert answer == "echo:ping model=local-gguf ngl=33 ctx=8192"
    log = stack.runtime.log_path(slot)
    assert log is not None and "server is listening" in log.read_text()


def test_owner_settings_reach_the_server(stack: Stack) -> None:
    slot = stack.launch("m.gguf", settings=RuntimeSettings(gpu_layers=12, context_size=4096))
    assert stack.chat(slot).endswith("ngl=12 ctx=4096")


def test_switching_the_model_in_a_slot_replaces_the_server(stack: Stack) -> None:
    slot = stack.launch("first.gguf")
    first_pid = stack.runtime.status(slot).pid
    stack.launch("second.gguf", slot=slot)
    status = stack.runtime.status(slot)
    assert status.pid != first_pid
    assert status.model_path is not None and status.model_path.endswith("second.gguf")
    assert stack.chat(slot).startswith("echo:hello")


def test_two_models_serve_at_once_and_stopping_one_leaves_the_other(stack: Stack) -> None:
    a = stack.launch("a.gguf")
    b = stack.launch("b.gguf")
    assert a != b
    assert "model=local-gguf " in stack.chat(a) and "model=local-gguf-2 " in stack.chat(b)
    stack.supervisor.stop_slot(a)
    assert not stack.runtime.alive(a)
    assert stack.chat(b).startswith("echo:")


def test_out_of_memory_start_recovers_with_fewer_gpu_layers(stack: Stack) -> None:
    slot = stack.launch("oom.gguf")
    health = stack.supervisor.health(slot)
    # 33 → 24 → 18 fail (the stand-in refuses more than 16), 13 succeeds.
    assert health.plan.gpu_layers == 13
    assert health.last_error == "local_runtime_out_of_memory"
    assert stack.chat(slot).endswith("ngl=13 ctx=8192")


def test_unsupported_model_is_explained_and_frees_the_slot(stack: Stack) -> None:
    with pytest.raises(LaunchRefused, match="llama_cpp_model_unsupported"):
        stack.launch("broken.gguf")
    assert stack.runtime.statuses() == []
    assert stack.supervisor.slots() == []


def test_slow_load_is_waited_for(stack: Stack) -> None:
    slot = stack.launch("slow.gguf")
    assert stack.supervisor.health(slot).state == "ready"


def test_crash_after_ready_is_restarted_by_the_monitor(stack: Stack) -> None:
    slot = stack.launch("crash.gguf")
    first_pid = stack.runtime.status(slot).pid
    stack.supervisor.start()
    _wait(lambda: stack.supervisor.health(slot).restarts >= 1, timeout=20)
    _wait(lambda: stack.supervisor.health(slot).state == "ready", timeout=20)
    assert stack.runtime.status(slot).pid != first_pid
    assert stack.supervisor.health(slot).last_error == "local_runtime_exited"


def test_shutdown_ends_every_server_process(stack: Stack) -> None:
    a = stack.launch("a.gguf")
    b = stack.launch("b.gguf")
    processes = [stack.runtime._processes[a], stack.runtime._processes[b]]
    stack.supervisor.shutdown()
    assert all(process.poll() is not None for process in processes)
    assert port_is_free(stack.slots[0].port)  # nothing is left listening


def test_deployments_are_restored_when_raiker_starts_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = Stack(tmp_path, monkeypatch, persist=True)
    store = SQLiteStore(first.workspace)
    ModelLibraryService(store).add_root(OWNER, first.library)
    store.save_local_runtime_settings(OWNER, "kept.gguf", {"context_size": 4096})
    try:
        slot = first.supervisor.launch(
            owner=OWNER, model_id="kept.gguf", model_path=first.model("kept.gguf"),
            settings=RuntimeSettings(context_size=4096), approved_roots=(first.library,),
        ).slot_profile_id
    finally:
        first.supervisor.shutdown()
    assert store.list_local_runtime_deployments()[0]["slot_profile_id"] == slot

    runtime, again = first._build()
    try:
        again.restore(background=False)
        assert again.health(slot).state == "ready"
        endpoint = runtime.status(slot).endpoint
        assert endpoint is not None
        provider = LlamaCppServerProvider(model="local-gguf", endpoint=endpoint.removesuffix("/v1"))
        assert provider.chat([ModelMessage(role="user", content="x")]).text.endswith("ctx=4096")
        # Stopping on purpose forgets the deployment.
        again.stop_slot(slot)
        assert store.list_local_runtime_deployments() == []
    finally:
        again.shutdown()


def test_restore_failure_is_recorded_not_raised(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    built = Stack(tmp_path, monkeypatch, persist=True)
    store = SQLiteStore(built.workspace)
    ModelLibraryService(store).add_root(OWNER, built.library)
    store.save_local_runtime_deployment(OWNER, LOCAL_SLOTS[0].profile_id, "gone", str(built.library / "gone.gguf"))
    try:
        built.supervisor.restore(background=False)
        failures = built.supervisor.restore_failures()
        assert failures[LOCAL_SLOTS[0].profile_id][0] == "gone"
    finally:
        built.supervisor.shutdown()
