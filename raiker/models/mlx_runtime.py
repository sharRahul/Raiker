from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from raiker.models.slot_runtime import (
    ManagedRuntimeStatus,
    ManagedSlotRuntime,
    RuntimeSlot,
    declared_slots,
)

MlxSlot = RuntimeSlot
MlxRuntimeStatus = ManagedRuntimeStatus

#: Declared in `model-profiles.json`, like the llama.cpp slots.
MLX_SLOTS: tuple[MlxSlot, ...] = declared_slots("mlx")


class ManagedMlxRuntime(ManagedSlotRuntime):
    """Runs one loopback-only ``mlx_lm.server`` process per declared MLX slot."""

    unknown_slot_code = "unknown_mlx_runtime_slot"
    exhausted_code = "mlx_runtime_slots_exhausted"

    def __init__(self, launcher: Callable[[list[str]], Any] | None = None) -> None:
        super().__init__(MLX_SLOTS, launcher)

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
        with self._lock:
            slot = self._named_slot(profile_id) if profile_id is not None else self._free_slot()
            argv = [str(executable)]
            if executable.name == "mlx_lm":
                argv.append("server")
            argv.extend(["--model", str(model), "--host", "127.0.0.1", "--port", str(slot.port)])
            return self._launch_into(slot, str(model), argv, port=slot.port)
