from __future__ import annotations

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
