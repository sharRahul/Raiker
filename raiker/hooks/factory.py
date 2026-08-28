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
from raiker.hooks.handlers.prompt import prompt_runner
from raiker.hooks.owner_switch import hooks_disabled
from raiker.hooks.registry import HooksRegistry
from raiker.models.connections import get_model_connection
from raiker.models.policy_state import provider_runtime_policy_from_gates
from raiker.models.registry import ModelProfileRegistry, RegistryError, profile_with_model
from raiker.models.router import ModelRouter
from raiker.models.session_state import TERMINAL_MODEL_SESSION_ID
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
    event_writer = writer if writer is not None else EventLogWriter(store)
    dispatcher = HookDispatcher(
        HooksRegistry.load(workspace_root),
        workspace_root=workspace_root,
        writer=event_writer,
    )
    owner = resolve_owner_principal_id(store, acting_principal_id)
    if owner is not None:
        registry = ModelProfileRegistry.load()
        router = ModelRouter(
            registry,
            event_writer,
            runtime_policy=provider_runtime_policy_from_gates(store, owner),
            connection_resolver=lambda profile_id: get_model_connection(store, owner, profile_id),
        )
        default_provider = router.default_provider()
        state = store.load_principal_model_state(owner) or store.load_model_session_state(
            TERMINAL_MODEL_SESSION_ID
        )
        if state is not None:
            try:
                profile = registry.resolve_profile_id(state.profile_id)
                selected_model = state.model or profile.model
                if selected_model and "<" not in selected_model:
                    if selected_model != profile.model:
                        registry.register(profile_with_model(profile, selected_model))
                    default_provider = (profile.provider, selected_model)
            except RegistryError:
                pass
        dispatcher.prompt_runner = prompt_runner(router, default_provider)
    dispatcher.set_disabled(owner is not None and hooks_disabled(workspace_root, owner))
    return dispatcher


__all__ = ["dispatcher_for_workspace"]
