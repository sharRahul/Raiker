from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LocalRuntimeStatus:
    running: bool
    pid: int | None
    endpoint: str | None
    model_path: str | None


class ManagedLlamaRuntime:
    def __init__(self, launcher: Callable[[list[str]], Any] | None = None, *, approved_roots: tuple[Path, ...] = (), on_stopped: Callable[[str], None] | None = None) -> None:
        self._launcher = launcher or self._launch
        self._approved_roots = tuple(root.resolve() for root in approved_roots)
        self._on_stopped = on_stopped
        self._process: Any | None = None
        self._model_path: str | None = None
        self._endpoint: str | None = None

    @staticmethod
    def _launch(argv: list[str]) -> subprocess.Popen[bytes]:
        return subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False)  # noqa: S603

    def start(self, model_path: Path, *, executable: Path, port: int = 8080) -> LocalRuntimeStatus:
        model = model_path.resolve()
        if not model.is_file():
            raise ValueError("local_model_not_found")
        if self._approved_roots and not any(model.is_relative_to(root) for root in self._approved_roots):
            raise ValueError("model_outside_approved_library")
        if not 1024 <= port <= 65535:
            raise ValueError("invalid_runtime_port")
        argv = [str(executable), "--model", str(model), "--host", "127.0.0.1", "--port", str(port)]
        self._process = self._launcher(argv)
        self._model_path = str(model)
        self._endpoint = f"http://127.0.0.1:{port}/v1"
        return self.status()

    def stop(self) -> LocalRuntimeStatus:
        model_path = self._model_path
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
        self._process = None
        self._endpoint = None
        self._model_path = None
        if model_path is not None and self._on_stopped is not None:
            self._on_stopped(model_path)
        return self.status()

    def status(self) -> LocalRuntimeStatus:
        running = self._process is not None and self._process.poll() is None
        return LocalRuntimeStatus(running, getattr(self._process, "pid", None) if running else None, self._endpoint if running else None, self._model_path if running else None)
