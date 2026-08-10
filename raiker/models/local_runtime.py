from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LocalSlot:
    """One managed llama.cpp server: its profile, its port, and its served name.

    Slots are declared rather than allocated so each one is an ordinary shipped
    profile. That is what makes a second local model selectable everywhere a
    model can be selected — the picker, the fallback sequence, a task, a
    surface default — with no dynamic registry and no new policy surface.
    """

    profile_id: str
    alias: str
    port: int


# Four is a judgement, not a limit of the design: every slot is a resident
# process holding model weights in memory, and an unbounded pool is a way to
# exhaust a laptop by clicking Deploy. The first keeps the original id, port,
# and alias so an existing deployment, selection, or fallback entry is untouched.
LOCAL_SLOTS: tuple[LocalSlot, ...] = (
    LocalSlot("raiker-local-llama-cpp", "local-gguf", 8080),
    LocalSlot("raiker-local-llama-cpp-2", "local-gguf-2", 8081),
    LocalSlot("raiker-local-llama-cpp-3", "local-gguf-3", 8082),
    LocalSlot("raiker-local-llama-cpp-4", "local-gguf-4", 8083),
)

_SLOTS_BY_PROFILE = {slot.profile_id: slot for slot in LOCAL_SLOTS}


def slot_for_profile(profile_id: str) -> LocalSlot | None:
    return _SLOTS_BY_PROFILE.get(profile_id)


@dataclass(frozen=True)
class LocalRuntimeStatus:
    running: bool
    pid: int | None
    endpoint: str | None
    model_path: str | None
    slot: str = LOCAL_SLOTS[0].profile_id


class ManagedLlamaRuntime:
    """Runs up to `LOCAL_SLOTS` llama.cpp servers, one model each.

    A single managed server meant a second Deploy silently replaced the first,
    so a local-only owner could never put Chat on a small model and Build on a
    large one. Each slot now holds its own process, port, and served alias.

    The approved-library check is unchanged and applies to every slot: a model
    outside an owner-approved root is refused before any process is launched.
    """

    def __init__(
        self,
        launcher: Callable[[list[str]], Any] | None = None,
        *,
        approved_roots: tuple[Path, ...] = (),
        on_stopped: Callable[[str], None] | None = None,
    ) -> None:
        self._launcher = launcher or self._launch
        self._approved_roots = tuple(root.resolve() for root in approved_roots)
        self._on_stopped = on_stopped
        self._processes: dict[str, Any] = {}
        self._model_paths: dict[str, str] = {}

    @staticmethod
    def _launch(argv: list[str]) -> subprocess.Popen[bytes]:
        return subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
        )  # noqa: S603

    def _alive(self, slot_id: str) -> bool:
        process = self._processes.get(slot_id)
        return process is not None and process.poll() is None

    def _assign_slot(self, model_path: str, requested_port: int | None) -> LocalSlot:
        """Pick the slot this model should occupy.

        Re-deploying a model that is already serving reuses its slot rather than
        starting a duplicate. An explicit port names a slot, which is what keeps
        the original single-server call shape working. Otherwise the first free
        slot is used, and a full pool refuses — evicting a model somebody may be
        mid-turn on is never the right answer to "deploy another one".
        """
        for slot in LOCAL_SLOTS:
            if self._model_paths.get(slot.profile_id) == model_path and self._alive(
                slot.profile_id
            ):
                return slot
        if requested_port is not None:
            named = next((slot for slot in LOCAL_SLOTS if slot.port == requested_port), None)
            if named is not None:
                return named
            # A port outside the declared slots still runs, on the first slot,
            # so an operator-chosen port keeps its original meaning.
            return LOCAL_SLOTS[0]
        free = next(
            (slot for slot in LOCAL_SLOTS if not self._alive(slot.profile_id)),
            None,
        )
        if free is None:
            raise ValueError("local_runtime_slots_exhausted")
        return free

    def start(
        self,
        model_path: Path,
        *,
        executable: Path,
        port: int | None = None,
        approved_roots: tuple[Path, ...] | None = None,
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
        slot = self._assign_slot(str(model), port)
        bound_port = port if port is not None else slot.port
        if self._alive(slot.profile_id):
            self.stop(slot.profile_id)
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
        ]
        self._processes[slot.profile_id] = self._launcher(argv)
        self._model_paths[slot.profile_id] = str(model)
        return self.status(slot.profile_id)

    def stop(self, slot_id: str | None = None) -> LocalRuntimeStatus:
        """Stop one slot, or every slot when none is named (host shutdown)."""
        if slot_id is None:
            stopped = [self._stop_slot(slot.profile_id) for slot in LOCAL_SLOTS]
            return stopped[0]
        return self._stop_slot(slot_id)

    def _stop_slot(self, slot_id: str) -> LocalRuntimeStatus:
        process = self._processes.get(slot_id)
        model_path = self._model_paths.get(slot_id)
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
        if model_path is not None and self._on_stopped is not None:
            self._on_stopped(model_path)
        return self.status(slot_id)

    def status(self, slot_id: str | None = None) -> LocalRuntimeStatus:
        resolved = slot_id or LOCAL_SLOTS[0].profile_id
        slot = _SLOTS_BY_PROFILE.get(resolved, LOCAL_SLOTS[0])
        process = self._processes.get(resolved)
        running = process is not None and process.poll() is None
        return LocalRuntimeStatus(
            running,
            getattr(process, "pid", None) if running else None,
            f"http://127.0.0.1:{slot.port}/v1" if running else None,
            self._model_paths.get(resolved) if running else None,
            slot.profile_id,
        )

    def statuses(self) -> list[LocalRuntimeStatus]:
        """Every slot that is currently serving a model."""
        return [
            self.status(slot.profile_id)
            for slot in LOCAL_SLOTS
            if self._alive(slot.profile_id)
        ]
