"""The lifespan worker that keeps indexed attached roots current.

An attached folder is edited by whatever the owner uses — an editor, a build, a
`git checkout` — none of which tell Raiker anything. `reconcile_attached_root`
is the floor that copes with that; this worker only makes it prompt, so an edit
reaches recall in seconds rather than at the next time somebody opens the
project.

Because it is an optimisation over a working floor, its failure mode matters
more than its success: a watcher that quietly stopped would leave recall
answering from a stale index with nothing anywhere to notice. So every outcome
lands in :class:`WatchState`, failures included, and the interface states what
it finds there rather than implying freshness.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from watchfiles import awatch

from raiker.knowledge.reconcile import IGNORED_DIRECTORY_NAMES, reconcile_attached_root
from raiker.storage.sqlite import SQLiteStore

#: Seconds between rebuilding the watched set. A folder attached or indexed
#: while the host is running joins on the next cycle rather than on a restart.
REFRESH_SECONDS = 15


@dataclass(frozen=True)
class WatchState:
    """What the interface may honestly say about one project's freshness."""

    watching: bool
    reason: str
    last_scanned_at: str


class AttachedRootWatcher:
    """Keeps indexed attached roots current, and says when it cannot."""

    def __init__(self, workspace_root: str | Path) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self._state: dict[str, WatchState] = {}

    def state(self, project_id: str) -> WatchState:
        return self._state.get(project_id, WatchState(False, "not_started", ""))

    def record_failure(self, project_id: str, reason: str) -> None:
        """Stop claiming to watch *project_id*, keeping the freshness it earned.

        The last scan's timestamp survives deliberately: the index is not empty
        because watching stopped, it is as fresh as that pass left it, and
        dropping the timestamp would make a degraded watcher look like one that
        never ran.
        """
        previous = self.state(project_id)
        self._state[project_id] = WatchState(False, reason, previous.last_scanned_at)

    def record_scan(self, project_id: str, scanned_at: str) -> None:
        self._state[project_id] = WatchState(True, "watching", scanned_at)

    def indexed_attached_roots(self) -> dict[Path, str]:
        """`{root_path: project_id}` for every attached root worth watching."""
        roots: dict[Path, str] = {}
        for row in SQLiteStore(self.workspace_root).list_indexed_attached_roots():
            path = Path(str(row["path"]))
            if path.is_dir():
                roots[path.resolve()] = str(row["project_id"])
        return roots

    async def run(self, stop: asyncio.Event) -> None:
        """Watch until asked to stop, rebuilding the watched set as it changes.

        Each cycle is suppressed on its own. A folder that becomes unwatchable
        must not stop the loop, because the next cycle is what picks up the
        *other* projects — and the failure it records is what the interface
        needs in order to stop claiming freshness for the one that broke.
        """
        while not stop.is_set():
            with suppress(Exception):
                await self._cycle(stop)
            if stop.is_set():
                return
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=REFRESH_SECONDS)

    async def _cycle(self, stop: asyncio.Event) -> None:
        roots = await asyncio.to_thread(self.indexed_attached_roots)
        if not roots:
            return
        for project_id in roots.values():
            # Reconcile once on adoption: changes made while the host was down
            # are exactly the ones no watcher can have seen.
            await asyncio.to_thread(self._reconcile, project_id)
        cycle_stop = asyncio.Event()
        watching = asyncio.create_task(self._watch(roots, cycle_stop))
        refresh = asyncio.create_task(
            asyncio.wait_for(stop.wait(), timeout=REFRESH_SECONDS)
        )
        try:
            await asyncio.wait({watching, refresh}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            cycle_stop.set()
            for task in (watching, refresh):
                task.cancel()
                with suppress(asyncio.CancelledError, TimeoutError, Exception):
                    await task

    async def _watch(self, roots: dict[Path, str], stop: asyncio.Event) -> None:
        try:
            async for batch in awatch(
                *roots,
                stop_event=stop,
                watch_filter=_not_ignored,
                recursive=True,
            ):
                touched = {
                    project_id
                    for _change, raw in batch
                    for path, project_id in roots.items()
                    if Path(raw).is_relative_to(path)
                }
                for project_id in touched:
                    await asyncio.to_thread(self._reconcile, project_id)
        except (OSError, RuntimeError) as exc:
            # `watchfiles` raises OSError when the platform runs out of watch
            # descriptors, which is the common real failure and the one the
            # owner must be told about rather than left to infer.
            for project_id in roots.values():
                self.record_failure(project_id, f"watch_failed:{type(exc).__name__}")

    def _reconcile(self, project_id: str) -> None:
        store = SQLiteStore(self.workspace_root)
        row = next(
            (
                item
                for item in store.list_indexed_attached_roots()
                if str(item["project_id"]) == project_id
            ),
            None,
        )
        if row is None:
            return
        owner = str(row["owner_principal_id"])
        try:
            report = reconcile_attached_root(
                self.workspace_root, store, store.load_project(project_id), owner
            )
        except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
            self.record_failure(project_id, f"scan_failed:{type(exc).__name__}")
            return
        self.record_scan(project_id, report.scanned_at)


def _not_ignored(_change: object, raw: str) -> bool:
    """Keep the watcher out of the same directories the scan skips.

    Without this a build writing into `node_modules` or `.git` would wake a
    reconcile for every file it touched, to index none of them.
    """
    return not any(part in IGNORED_DIRECTORY_NAMES for part in Path(raw).parts)
