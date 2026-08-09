from __future__ import annotations

from pathlib import Path

from raiker.models.local_runtime import ManagedLlamaRuntime


class FakeProcess:
    pid = 42

    def poll(self) -> int | None:
        return None

    def terminate(self) -> None:
        self.pid = 0

    def wait(self, timeout: int) -> int:
        return 0


def test_managed_runtime_uses_argv_and_owner_approved_model(tmp_path: Path) -> None:
    model = tmp_path / "model.gguf"
    model.write_bytes(b"GGUF")
    calls: list[tuple[str, ...]] = []
    invalidated: list[str] = []

    def launch(argv: list[str]) -> FakeProcess:
        calls.append(tuple(argv))
        return FakeProcess()

    runtime = ManagedLlamaRuntime(
        launch,
        approved_roots=(tmp_path,),
        on_stopped=lambda path: invalidated.append(path),
    )
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
