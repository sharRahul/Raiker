from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from raiker.models.slot_runtime import (
    ManagedRuntimeStatus,
    ManagedSlotRuntime,
    RuntimeSlot,
    declared_slots,
)

LocalSlot = RuntimeSlot
LocalRuntimeStatus = ManagedRuntimeStatus

# Four is a judgement, not a limit of the design: every slot is a resident
# process holding model weights in memory, and an unbounded pool is a way to
# exhaust a laptop by clicking Deploy. Declared in `model-profiles.json`.
LOCAL_SLOTS: tuple[LocalSlot, ...] = declared_slots("llama.cpp")

_SLOTS_BY_PROFILE = {slot.profile_id: slot for slot in LOCAL_SLOTS}


def slot_for_profile(profile_id: str) -> LocalSlot | None:
    return _SLOTS_BY_PROFILE.get(profile_id)


class ManagedLlamaRuntime(ManagedSlotRuntime):
    """Runs up to `LOCAL_SLOTS` llama.cpp servers, one model each.

    A single managed server meant a second Deploy silently replaced the first,
    so a local-only owner could never put Chat on a small model and Build on a
    large one. Each slot holds its own process, port, and served alias.

    The approved-library check applies to every slot: a model outside an
    owner-approved root is refused before any process is launched.
    """

    unknown_slot_code = "unknown_local_runtime_slot"
    exhausted_code = "local_runtime_slots_exhausted"

    def __init__(
        self,
        launcher: Callable[[list[str]], Any] | None = None,
        *,
        approved_roots: tuple[Path, ...] = (),
        on_stopped: Callable[[str], None] | None = None,
        workspace_root: Path | None = None,
        slots: tuple[LocalSlot, ...] = LOCAL_SLOTS,
    ) -> None:
        super().__init__(slots, launcher, on_stopped=on_stopped)
        self._approved_roots = tuple(root.resolve() for root in approved_roots)
        #: Where each slot's log and pid file go. Without it (tests, embedders)
        #: the server's output is discarded, as it always was.
        self.workspace_root = workspace_root

    def log_path(self, slot_id: str) -> Path | None:
        if self.workspace_root is None:
            return None
        from raiker.models.llama_cpp.process import log_dir

        return log_dir(self.workspace_root) / f"{slot_id}.log"

    def _spawn(self, slot: LocalSlot, argv: list[str]) -> Any:
        log_path = self.log_path(slot.profile_id)
        if self._custom_launcher or log_path is None:
            return super()._spawn(slot, argv)
        from raiker.models.llama_cpp.process import spawn

        return spawn(argv, log_path=log_path, pid_path=log_path.with_suffix(".pid"))

    def _stop_locked(self, slot_id: str | None) -> LocalRuntimeStatus:
        status = super()._stop_locked(slot_id)
        if slot_id is not None:
            log_path = self.log_path(slot_id)
            if log_path is not None:
                log_path.with_suffix(".pid").unlink(missing_ok=True)
        return status

    def _assign_slot(
        self, model_path: str, requested_port: int | None, profile_id: str | None = None
    ) -> LocalSlot:
        """Pick the slot this model should occupy.

        Re-deploying a model that is already serving reuses its slot rather than
        starting a duplicate. An explicit port names a slot, which is what keeps
        the original single-server call shape working; a port outside the table
        still runs, on the first slot. Otherwise the first free slot is used.
        """
        for slot in self.slots:
            if self._model_paths.get(slot.profile_id) == model_path and self._alive(
                slot.profile_id
            ):
                return slot
        if profile_id is not None:
            return self._named_slot(profile_id)
        if requested_port is not None:
            return next((slot for slot in self.slots if slot.port == requested_port), self.slots[0])
        return self._free_slot()

    def start(
        self,
        model_path: Path,
        *,
        executable: Path,
        port: int | None = None,
        profile_id: str | None = None,
        approved_roots: tuple[Path, ...] | None = None,
        extra_args: Sequence[str] = (),
    ) -> LocalRuntimeStatus:
        model = model_path.resolve()
        if not model.is_file():
            raise ValueError("local_model_not_found")
        roots = (
            tuple(root.resolve() for root in approved_roots)
            if approved_roots is not None
            else self._approved_roots
        )
        if not roots or not any(model.is_relative_to(root) for root in roots):
            raise ValueError("model_outside_approved_library")
        if port is not None and not 1024 <= port <= 65535:
            raise ValueError("invalid_runtime_port")
        with self._lock:
            slot = self._assign_slot(str(model), port, profile_id)
            bound_port = port if port is not None else slot.port
            argv = [
                str(executable),
                "--model",
                str(model),
                "--alias",
                slot.alias,
                "--host",
                "127.0.0.1",
                "--port",
                str(bound_port),
                # The planner's sizing (GPU layers, context, KV cache, threads)
                # and `--jinja`, without which llama-server refuses tool calls.
                *extra_args,
            ]
            return self._launch_into(slot, str(model), argv, port=bound_port)
