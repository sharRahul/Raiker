"""The supervisor's decisions, with fake processes, a fake clock and fake health."""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.models.llama_cpp import installer
from raiker.models.llama_cpp import supervisor as supervisor_module
from raiker.models.llama_cpp.installer import ResolvedExecutable
from raiker.models.llama_cpp.planner import MemoryBudget, RuntimeSettings
from raiker.models.llama_cpp.process import classify_failure
from raiker.models.llama_cpp.supervisor import (
    MAX_RESTARTS,
    RESTART_AFTER,
    UNHEALTHY_AFTER,
    LaunchRefused,
    LlamaSupervisor,
    ready_budget_seconds,
)
from raiker.models.local_runtime import ManagedLlamaRuntime

GIB = 1024**3


class Proc:
    count = 0

    def __init__(self, argv: list[str]) -> None:
        Proc.count += 1
        self.pid = 1000 + Proc.count
        self.argv = argv
        self.code: int | None = None

    def poll(self) -> int | None:
        return self.code

    def terminate(self) -> None:
        self.code = -15

    def kill(self) -> None:
        self.code = -9

    def wait(self, timeout: float) -> int:
        return self.code or 0


class Harness:
    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, ram_gib: float = 32) -> None:
        self.now = 0.0
        self.health_answer = "ready"
        self.procs: list[Proc] = []
        self.library = tmp_path / "models"
        self.library.mkdir()
        self.workspace = tmp_path / "ws"
        self.workspace.mkdir()

        def launch(argv: list[str]) -> Proc:
            process = Proc(argv)
            self.procs.append(process)
            return process

        self.runtime = ManagedLlamaRuntime(launch, workspace_root=self.workspace)
        monkeypatch.setattr(
            installer, "resolve_executable",
            lambda _ws: ResolvedExecutable(str(tmp_path / "llama-server"), "managed", "cuda"),
        )
        self.ram = ram_gib
        self.sup = LlamaSupervisor(
            self.runtime,
            self.workspace,
            budget_for=lambda backend, committed: MemoryBudget(
                backend, 8 * GIB, False, int(self.ram * GIB), 64 * GIB, committed
            ),
            health=lambda _port, _alias: self.health_answer,
            clock=lambda: self.now,
            sleep=self._advance,
            persist=False,
        )

    def _advance(self, seconds: float) -> None:
        self.now += seconds

    def model(self, name: str = "m.gguf", size: int = 1024) -> Path:
        path = self.library / name
        path.write_bytes(b"\0" * size)
        return path

    def launch(self, name: str = "m.gguf", **kwargs: object) -> None:
        self.sup.launch(
            owner="owner", model_id=name, model_path=self.model(name),
            settings=kwargs.pop("settings", RuntimeSettings()),  # type: ignore[arg-type]
            approved_roots=(self.library,), **kwargs,  # type: ignore[arg-type]
        )

    def crash(self, log: str = "segfault") -> None:
        log_path = self.runtime.log_path("raiker-local-llama-cpp")
        assert log_path is not None
        log_path.write_text(log)
        self.procs[-1].code = 1


@pytest.fixture
def h(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Harness:
    return Harness(tmp_path, monkeypatch)


def test_launch_passes_the_plan_and_reports_ready(h: Harness) -> None:
    h.launch()
    health = h.sup.health("raiker-local-llama-cpp")
    assert health.state == "ready" and health.pid == h.procs[0].pid
    argv = h.procs[0].argv
    assert "--jinja" in argv and "-ngl" in argv and "-c" in argv
    assert argv[argv.index("-ngl") + 1] == str(health.plan.gpu_layers)


def test_missing_engine_is_refused_before_anything_starts(h: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(installer, "resolve_executable", lambda _ws: ResolvedExecutable(None, "none", None))
    with pytest.raises(LaunchRefused, match="llama_server_missing"):
        h.launch()
    assert h.procs == []


def test_insufficient_memory_is_refused_before_a_process_exists(h: Harness) -> None:
    h.ram = 1.5
    h.model("big.gguf", size=8 * 1024 * 1024)
    with pytest.raises(LaunchRefused, match="local_runtime_insufficient_memory"):
        h.launch("big.gguf", settings=RuntimeSettings(gpu_layers=0))
    assert h.procs == []


def test_overcommit_lets_the_owner_start_anyway(h: Harness) -> None:
    h.ram = 1.5
    h.launch(settings=RuntimeSettings(gpu_layers=0, allow_overcommit=True))
    assert h.sup.health("raiker-local-llama-cpp").plan.verdict == "insufficient_memory"


def test_start_that_never_becomes_ready_is_stopped(h: Harness) -> None:
    h.health_answer = "loading"
    with pytest.raises(LaunchRefused, match="local_server_not_ready"):
        h.launch()
    assert h.procs[0].code is not None
    assert h.sup.slots() == []


def test_cancel_while_loading_stops_the_process(h: Harness) -> None:
    h.health_answer = "loading"

    class Cancelled(Exception):
        pass

    calls = {"n": 0}

    def check() -> None:
        calls["n"] += 1
        if calls["n"] > 3:
            raise Cancelled

    with pytest.raises(Cancelled):
        h.launch(check_cancelled=check)
    assert h.procs[0].code is not None and h.sup.slots() == []


def test_crash_is_restarted_with_backoff_then_gives_up(h: Harness) -> None:
    h.launch()
    for attempt in range(1, MAX_RESTARTS + 1):
        h.crash()
        h.sup.tick()
        health = h.sup.health("raiker-local-llama-cpp")
        assert health.state == "restarting" and health.last_error == "local_runtime_exited"
        h.now += 2.0**attempt - 0.1
        h.sup.tick()
        assert len(h.procs) == attempt  # not yet: still backing off
        h.now += 0.2
        h.sup.tick()
        assert len(h.procs) == attempt + 1
        h.sup.tick()
        assert h.sup.health("raiker-local-llama-cpp").state == "ready"
    h.crash()
    h.sup.tick()
    assert h.sup.health("raiker-local-llama-cpp").state == "failed"
    h.now += 1000
    h.sup.tick()
    assert len(h.procs) == MAX_RESTARTS + 1


def test_out_of_memory_crash_restarts_with_fewer_gpu_layers(h: Harness) -> None:
    h.launch()
    before = h.sup.health("raiker-local-llama-cpp").plan.gpu_layers
    h.crash("ggml_backend_cuda_buffer_type_alloc_buffer: allocating 4096 MiB on device 0: cudaMalloc failed: out of memory")
    h.sup.tick()
    assert h.sup.health("raiker-local-llama-cpp").last_error == "local_runtime_out_of_memory"
    h.now += 1.5
    h.sup.tick()
    argv = h.procs[-1].argv
    assert int(argv[argv.index("-ngl") + 1]) < before


def test_unanswered_health_checks_mark_unhealthy_then_restart(h: Harness) -> None:
    h.launch()
    h.health_answer = "down"
    for _ in range(UNHEALTHY_AFTER):
        h.sup.tick()
    assert h.sup.health("raiker-local-llama-cpp").state == "unhealthy"
    for _ in range(RESTART_AFTER - UNHEALTHY_AFTER):
        h.sup.tick()
    health = h.sup.health("raiker-local-llama-cpp")
    assert health.state == "restarting" and health.last_error == "local_runtime_unresponsive"
    assert h.procs[0].code is not None
    h.health_answer = "ready"
    h.now += 5
    h.sup.tick()
    h.sup.tick()
    assert h.sup.health("raiker-local-llama-cpp").state == "ready"


def test_a_relaunch_that_hangs_while_loading_is_restarted(h: Harness) -> None:
    h.launch()
    h.crash()
    h.sup.tick()
    h.now += 3
    h.health_answer = "loading"
    h.sup.tick()
    assert h.sup.health("raiker-local-llama-cpp").state == "starting"
    h.now += ready_budget_seconds(1024) + 1
    h.sup.tick()
    assert h.sup.health("raiker-local-llama-cpp").last_error == "local_server_not_ready"


def test_stop_slot_forgets_and_restart_slot_relaunches(h: Harness) -> None:
    h.launch()
    restarted = h.sup.restart_slot("raiker-local-llama-cpp")
    assert restarted.restarts == 1 and len(h.procs) == 2 and h.procs[0].code is not None
    h.sup.stop_slot("raiker-local-llama-cpp")
    assert h.sup.slots() == [] and h.procs[1].code is not None
    with pytest.raises(LaunchRefused, match="local_runtime_slot_not_deployed"):
        h.sup.restart_slot("raiker-local-llama-cpp")


def test_second_model_plans_against_memory_the_first_holds(h: Harness) -> None:
    h.launch("a.gguf", settings=RuntimeSettings(gpu_layers=0))
    assert h.sup.committed_bytes() > 0
    assert h.sup.committed_bytes(excluding="raiker-local-llama-cpp") == 0


def test_shutdown_stops_everything(h: Harness) -> None:
    h.launch("a.gguf")
    h.launch("b.gguf")
    assert len(h.sup.slots()) == 2
    h.sup.shutdown()
    assert all(process.code is not None for process in h.procs)
    assert h.sup.slots() == []


@pytest.mark.parametrize(
    ("log", "code"),
    [
        ("CUDA error: out of memory", "local_runtime_out_of_memory"),
        ("ggml_vulkan: vk::Device::allocateMemory: ErrorOutOfDeviceMemory", "local_runtime_out_of_memory"),
        ("error loading model: unknown model architecture: 'newarch'", "llama_cpp_model_unsupported"),
        ("couldn't bind HTTP server socket, address already in use", "local_runtime_port_in_use"),
        ("error while loading shared libraries: libvulkan.so.1", "llama_cpp_libraries_missing"),
        ("something else entirely", "local_runtime_exited"),
    ],
)
def test_failure_logs_are_classified(log: str, code: str) -> None:
    assert classify_failure(log) == code


def test_ready_budget_scales_with_model_size() -> None:
    assert ready_budget_seconds(0) == 60
    assert ready_budget_seconds(10 * GIB) == 260
    assert ready_budget_seconds(1000 * GIB) == 900


def test_supervisor_module_exports_bounded_reasons() -> None:
    assert supervisor_module.LaunchRefused.bounded_reason is True
