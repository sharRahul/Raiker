from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MlxSlot:
    profile_id: str
    port: int


MLX_SLOTS: tuple[MlxSlot, ...] = tuple(
    MlxSlot(f"raiker-local-mlx{'' if index == 1 else f'-{index}'}", 8090 + index - 1)
    for index in range(1, 5)
)
_SLOTS_BY_PROFILE = {slot.profile_id: slot for slot in MLX_SLOTS}


@dataclass(frozen=True)
class MlxRuntimeStatus:
    running: bool
    pid: int | None
    endpoint: str | None
    model_path: str | None
    slot: str


class ManagedMlxRuntime:
    """Runs one loopback-only ``mlx_lm.server`` process per declared MLX slot."""

    def __init__(self, launcher: Callable[[list[str]], Any] | None = None) -> None:
        self._launcher = launcher or self._launch
        self._processes: dict[str, Any] = {}
        self._model_paths: dict[str, str] = {}

    @staticmethod
    def _launch(argv: list[str]) -> subprocess.Popen[bytes]:
        return subprocess.Popen(  # noqa: S603
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
        )

    def _alive(self, slot_id: str) -> bool:
        process = self._processes.get(slot_id)
        return process is not None and process.poll() is None

    def start(
        self,
        model_path: Path,
        *,
        executable: Path,
        profile_id: str | None = None,
        approved_roots: tuple[Path, ...] = (),
    ) -> MlxRuntimeStatus:
        model = model_path.resolve()
        if not model.is_dir() or not (model / "config.json").is_file():
            raise ValueError("local_mlx_model_not_found")
        roots = tuple(root.resolve() for root in approved_roots)
        if not roots or not any(model.is_relative_to(root) for root in roots):
            raise ValueError("model_outside_approved_library")
        if profile_id is not None:
            slot = _SLOTS_BY_PROFILE.get(profile_id)
            if slot is None:
                raise ValueError("unknown_mlx_runtime_slot")
        else:
            slot = next((candidate for candidate in MLX_SLOTS if not self._alive(candidate.profile_id)), None)
            if slot is None:
                raise ValueError("mlx_runtime_slots_exhausted")
        if self._alive(slot.profile_id):
            self.stop(slot.profile_id)
        argv = [str(executable)]
        if executable.name == "mlx_lm":
            argv.append("server")
        argv.extend(["--model", str(model), "--host", "127.0.0.1", "--port", str(slot.port)])
        self._processes[slot.profile_id] = self._launcher(argv)
        self._model_paths[slot.profile_id] = str(model)
        return self.status(slot.profile_id)

    def stop(self, slot_id: str | None = None) -> MlxRuntimeStatus:
        if slot_id is None:
            stopped = [self.stop(slot.profile_id) for slot in MLX_SLOTS]
            return stopped[0]
        process = self._processes.get(slot_id)
        if process is not None and process.poll() is None:
            process.terminate()
            wait = getattr(process, "wait", None)
            if callable(wait):
                try:
                    wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    wait(timeout=5)
        self._processes.pop(slot_id, None)
        self._model_paths.pop(slot_id, None)
        return self.status(slot_id)

    def status(self, slot_id: str) -> MlxRuntimeStatus:
        slot = _SLOTS_BY_PROFILE.get(slot_id, MLX_SLOTS[0])
        process = self._processes.get(slot.profile_id)
        running = process is not None and process.poll() is None
        return MlxRuntimeStatus(
            running=running,
            pid=getattr(process, "pid", None) if running else None,
            endpoint=f"http://127.0.0.1:{slot.port}/v1" if running else None,
            model_path=self._model_paths.get(slot.profile_id) if running else None,
            slot=slot.profile_id,
        )
