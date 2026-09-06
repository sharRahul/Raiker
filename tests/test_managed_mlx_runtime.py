from __future__ import annotations

import contextlib
import threading
from pathlib import Path
from typing import Any

from raiker.models.mlx_runtime import ManagedMlxRuntime


class Process:
    pid = 42

    def __init__(self) -> None:
        self.running = True

    def poll(self) -> int | None:
        return None if self.running else 0

    def terminate(self) -> None:
        self.running = False

    def wait(self, timeout: int) -> int:
        del timeout
        return 0


def test_mlx_runtime_targets_declared_slot_and_loopback(tmp_path: Path) -> None:
    model = tmp_path / "model"
    model.mkdir()
    (model / "config.json").write_text("{}", encoding="utf-8")
    calls: list[list[str]] = []

    def launch(argv: list[str]) -> Any:
        calls.append(argv)
        return Process()

    runtime = ManagedMlxRuntime(launcher=launch)
    status = runtime.start(
        model,
        executable=Path("/opt/bin/mlx_lm"),
        profile_id="raiker-local-mlx-3",
        approved_roots=(tmp_path,),
    )

    assert status.slot == "raiker-local-mlx-3"
    assert status.endpoint == "http://127.0.0.1:8092/v1"
    assert calls == [[
        str(Path("/opt/bin/mlx_lm")),
        "server",
        "--model",
        str(model),
        "--host",
        "127.0.0.1",
        "--port",
        "8092",
    ]]


def test_two_simultaneous_mlx_deploys_take_two_different_slots(tmp_path: Path) -> None:
    """GCR-28 — the MLX pool had the llama pool's race, for the same reason.

    Slot selection read the process map and the launch that makes the answer
    true happened afterwards, so two deploys arriving together could both claim
    one slot and one port.
    """
    first = tmp_path / "first"
    second = tmp_path / "second"
    for model in (first, second):
        model.mkdir()
        (model / "config.json").write_text("{}", encoding="utf-8")

    both_inside = threading.Barrier(2, timeout=5)
    lock = threading.Lock()
    launched: list[list[str]] = []

    def launch(argv: list[str]) -> Any:
        with contextlib.suppress(threading.BrokenBarrierError):
            both_inside.wait(timeout=0.5)
        with lock:
            launched.append(argv)
        return Process()

    runtime = ManagedMlxRuntime(launcher=launch)
    results: list[Any] = []
    errors: list[BaseException] = []

    def deploy(model: Path) -> None:
        try:
            results.append(
                runtime.start(
                    model,
                    executable=Path("/opt/bin/mlx_lm"),
                    approved_roots=(tmp_path,),
                )
            )
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
    assert len({result.slot for result in results}) == 2
    assert len({result.endpoint for result in results}) == 2
