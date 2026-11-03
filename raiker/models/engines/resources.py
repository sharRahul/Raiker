"""One ledger of the memory local engines hold, shared by models and voice.

Voice spec §7. The llama.cpp supervisor already subtracts what its own slots
have committed before it plans another (``committed_bytes``). Voice engines run
next to those slots, so they register here too: every running engine records
its *planned* footprint in system memory and on each GPU, and every planner
reads what is left after all of them. Neither side plans into memory the other
already holds.

The ledger is per process and per workspace; it holds plans, not
measurements, so it never asks the operating system anything.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Reservation:
    owner: str
    #: ``llm`` for a model slot, ``voice`` for a speech engine.
    kind: str
    ram_bytes: int
    #: The GPU the engine runs on, by the hardware probe's id, or ``None`` on the processor.
    gpu_id: str | None = None
    vram_bytes: int = 0


class ResourceLedger:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._held: dict[str, Reservation] = {}
        #: Read on every total, so the llama.cpp supervisor's own count stays
        #: the one source for its slots rather than being copied in here.
        self._external: dict[str, Callable[[], tuple[int, dict[str, int]]]] = {}

    def reserve(self, reservation: Reservation) -> None:
        with self._lock:
            self._held[reservation.owner] = reservation

    def release(self, owner: str) -> None:
        with self._lock:
            self._held.pop(owner, None)

    def attach(self, name: str, totals: Callable[[], tuple[int, dict[str, int]]]) -> None:
        """Count another holder's memory (RAM, VRAM per GPU) on every total."""
        with self._lock:
            self._external[name] = totals

    def held(self, *, kind: str | None = None) -> list[Reservation]:
        with self._lock:
            return [item for item in self._held.values() if kind is None or item.kind == kind]

    def committed(self, *, excluding: str | None = None) -> tuple[int, dict[str, int]]:
        """RAM in use by every registered engine, and VRAM per GPU."""
        with self._lock:
            held = [item for owner, item in self._held.items() if owner != excluding]
            external = list(self._external.values())
        ram = sum(item.ram_bytes for item in held)
        vram: dict[str, int] = {}
        for item in held:
            if item.gpu_id is not None:
                vram[item.gpu_id] = vram.get(item.gpu_id, 0) + item.vram_bytes
        for totals in external:
            try:
                extra_ram, extra_vram = totals()
            except Exception:  # noqa: BLE001 - a holder that cannot answer counts as nothing
                continue
            ram += extra_ram
            for gpu, amount in extra_vram.items():
                vram[gpu] = vram.get(gpu, 0) + amount
        return ram, vram


_LEDGERS: dict[str, ResourceLedger] = {}
_LEDGERS_LOCK = threading.Lock()


def ledger_for(workspace_root: object) -> ResourceLedger:
    with _LEDGERS_LOCK:
        return _LEDGERS.setdefault(str(workspace_root), ResourceLedger())
