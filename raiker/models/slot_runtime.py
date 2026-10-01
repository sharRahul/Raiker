"""Loopback model servers Raiker starts and stops itself, one per declared slot.

OPT-10. The llama.cpp and MLX pools each kept a slot table, a process map, a
reservation set, a lock, the terminate → wait → kill sequence and a status
projection — the same lifecycle twice, including the GCR-28 race fix applied
separately to each. What differs is the command line and what counts as a
model, and those stay in ``local_runtime.py`` and ``mlx_runtime.py``.

OPT-20. Which slots exist is declared once, in ``model-profiles.json``: a profile
marked ``managed_slot`` *is* a slot, its endpoint's port is the slot's port and
its model is the name the server is asked to serve. A slot is an ordinary
shipped profile, which is what makes a second local model selectable anywhere a
model can be.
"""

from __future__ import annotations

import json
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from raiker.models.registry import _read_config_text


@dataclass(frozen=True)
class RuntimeSlot:
    """One managed server: its profile, its loopback port, and its served name."""

    profile_id: str
    port: int
    alias: str


@dataclass(frozen=True)
class ManagedRuntimeStatus:
    running: bool
    pid: int | None
    endpoint: str | None
    model_path: str | None
    slot: str


def declared_slots(provider: str) -> tuple[RuntimeSlot, ...]:
    """The slots ``model-profiles.json`` declares for ``provider``, in order.

    Order matters: the first slot keeps the original single-server id, port and
    alias, so an existing deployment, selection or fallback entry is untouched.
    """
    data = json.loads(_read_config_text("config/model-profiles.json"))
    slots = tuple(
        RuntimeSlot(
            profile_id=str(entry["profile_id"]),
            port=int(urlsplit(str(entry["endpoint"])).port or 0),
            alias=str(entry["model"]),
        )
        for entry in data.get("profiles", [])
        if entry.get("managed_slot") and entry.get("provider") == provider
    )
    if not slots or any(not 1024 <= slot.port <= 65535 for slot in slots):
        raise ValueError(f"managed_slots_invalid:{provider}")
    return slots


class ManagedSlotRuntime:
    """Starts, stops and reports loopback servers across a fixed slot table.

    Selecting a slot, reserving it and launching into it are one step under one
    lock (GCR-28), so two deploys arriving together cannot both see a slot free,
    both launch, and orphan one process contending for one port.
    """

    #: Refusal codes, so each pool keeps the reason code its callers know.
    unknown_slot_code = "unknown_runtime_slot"
    exhausted_code = "runtime_slots_exhausted"

    def __init__(
        self,
        slots: tuple[RuntimeSlot, ...],
        launcher: Callable[[list[str]], Any] | None = None,
        *,
        on_stopped: Callable[[str], None] | None = None,
    ) -> None:
        self.slots = slots
        self._by_profile = {slot.profile_id: slot for slot in slots}
        self._launcher = launcher or self._launch
        self._on_stopped = on_stopped
        self._processes: dict[str, Any] = {}
        self._model_paths: dict[str, str] = {}
        # GCR-29 — the port a slot was actually launched on, which an explicit
        # port can make differ from the declared one; status reports this one.
        self._bound_ports: dict[str, int] = {}
        self._lock = threading.RLock()
        self._reserved: set[str] = set()

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

    def _occupied(self, slot_id: str) -> bool:
        """Alive, or reserved by a deploy that is launching right now."""
        return slot_id in self._reserved or self._alive(slot_id)

    def _named_slot(self, profile_id: str) -> RuntimeSlot:
        slot = self._by_profile.get(profile_id)
        if slot is None:
            raise ValueError(self.unknown_slot_code)
        return slot

    def _free_slot(self) -> RuntimeSlot:
        """The first slot nothing holds; a full pool refuses rather than evicting."""
        free = next((slot for slot in self.slots if not self._occupied(slot.profile_id)), None)
        if free is None:
            raise ValueError(self.exhausted_code)
        return free

    def _launch_into(
        self, slot: RuntimeSlot, model: str, argv: list[str], *, port: int
    ) -> ManagedRuntimeStatus:
        """Replace whatever the slot runs with ``argv``. Call with the lock held."""
        if self._alive(slot.profile_id):
            self._stop_locked(slot.profile_id)
        self._reserved.add(slot.profile_id)
        try:
            process = self._launcher(argv)
        except Exception:
            # Rolled back, so a launch that could not start does not cost the
            # pool a slot for the life of the host.
            self._reserved.discard(slot.profile_id)
            raise
        self._processes[slot.profile_id] = process
        self._model_paths[slot.profile_id] = model
        self._bound_ports[slot.profile_id] = port
        self._reserved.discard(slot.profile_id)
        return self.status(slot.profile_id)

    def stop(self, slot_id: str | None = None) -> ManagedRuntimeStatus:
        """Stop one slot, or every slot when none is named (host shutdown)."""
        with self._lock:
            return self._stop_locked(slot_id)

    def _stop_locked(self, slot_id: str | None) -> ManagedRuntimeStatus:
        if slot_id is None:
            return [self._stop_locked(slot.profile_id) for slot in self.slots][0]
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
        self._bound_ports.pop(slot_id, None)
        if model_path is not None and self._on_stopped is not None:
            self._on_stopped(model_path)
        return self.status(slot_id)

    def status(self, slot_id: str | None = None) -> ManagedRuntimeStatus:
        # An id that is not a slot is reported as not running, never as the
        # first slot's state.
        resolved = slot_id or self.slots[0].profile_id
        slot = self._by_profile.get(resolved, self.slots[0])
        running = self._alive(resolved)
        process = self._processes.get(resolved)
        port = self._bound_ports.get(resolved, slot.port)
        return ManagedRuntimeStatus(
            running=running,
            pid=getattr(process, "pid", None) if running else None,
            endpoint=f"http://127.0.0.1:{port}/v1" if running else None,
            model_path=self._model_paths.get(slot.profile_id) if running else None,
            slot=slot.profile_id,
        )

    def statuses(self) -> list[ManagedRuntimeStatus]:
        """Every slot that is currently serving a model."""
        return [
            self.status(slot.profile_id) for slot in self.slots if self._alive(slot.profile_id)
        ]
