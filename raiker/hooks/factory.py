"""One way to build a :class:`HookDispatcher` outside the gateway (BUG-223).

The gateway owns a dispatcher because it owns a turn. The lifecycle events added
by BUG-223 do not all belong to a turn: a task is created by a scheduler, a
conversation is archived from a dashboard route, and neither of those has a
gateway to borrow from. Without a shared way to build one, each call site would
invent its own — and the odds of all of them remembering the owner's off switch
are poor.

So the switch is applied *here*, once. A dispatcher this function returns is
already correct about whether the owner has turned hooks off; a caller cannot
forget, because there is nothing for it to remember.

Resolution of the owner follows :func:`resolve_owner_principal_id`: the switch is
an owner setting, and a background caller has no acting principal to read it
from, so the instance's original account is the one asked.
"""

from __future__ import annotations

from pathlib import Path

from raiker.events.writer import EventLogWriter
from raiker.hooks.dispatcher import HookDispatcher
from raiker.hooks.owner_switch import hooks_disabled
from raiker.hooks.registry import HooksRegistry
from raiker.storage.sqlite import SQLiteStore


def dispatcher_for_workspace(
    store: SQLiteStore,
    *,
    writer: EventLogWriter | None = None,
    acting_principal_id: str | None = None,
) -> HookDispatcher:
    """A dispatcher for this workspace with the owner's off switch already applied."""
    from raiker.notify.approval_notifier import resolve_owner_principal_id

    workspace_root = Path(store.paths.workspace_root)
    dispatcher = HookDispatcher(
        HooksRegistry.load(workspace_root),
        workspace_root=workspace_root,
        writer=writer if writer is not None else EventLogWriter(store),
    )
    owner = resolve_owner_principal_id(store, acting_principal_id)
    dispatcher.set_disabled(owner is not None and hooks_disabled(workspace_root, owner))
    return dispatcher


__all__ = ["dispatcher_for_workspace"]
