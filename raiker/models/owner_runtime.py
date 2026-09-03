"""The owner's own model, resolved outside a turn.

A turn resolves its provider and model from the envelope it was given. Work that
is *not* a turn — a hook advising on a lifecycle event, an owner asking for a
range of conversation to be summarised — still has to reach a model, and it must
reach the one the owner chose rather than whichever profile happens to be first
in the registry.

The resolution was written once inside :mod:`raiker.hooks.factory` and is shared
from here because the second caller would otherwise have been a second answer to
"which model is the owner's", and the two would drift. The router this returns
carries the owner's gates as its runtime policy and resolves credentials through
the owner's own connections, so nothing built here can reach a provider the
owner has not configured or a capability their gates refuse.
"""

from __future__ import annotations

from raiker.events.writer import EventLogWriter
from raiker.models.connections import get_model_connection
from raiker.models.policy_state import provider_runtime_policy_from_gates
from raiker.models.registry import ModelProfileRegistry, RegistryError, profile_with_model
from raiker.models.router import ModelRouter
from raiker.models.session_state import TERMINAL_MODEL_SESSION_ID
from raiker.models.subscription_limits import SubscriptionLimitStore
from raiker.storage.sqlite import SQLiteStore


def owner_model_runtime(
    store: SQLiteStore,
    owner_principal_id: str,
    writer: EventLogWriter,
) -> tuple[ModelRouter, tuple[str, str]]:
    """A router bound to *owner_principal_id*, and the provider/model they selected.

    Falls back to the router's own default when the owner has selected nothing, or
    when what they selected no longer resolves — a stale selection is not a reason
    to refuse to answer, and the caller is told which pair it actually got.

    A model id still holding a ``<`` placeholder is a catalogue entry rather than a
    real selection, and is ignored for the same reason.
    """
    registry = ModelProfileRegistry.load()
    router = ModelRouter(
        registry,
        writer,
        runtime_policy=provider_runtime_policy_from_gates(store, owner_principal_id),
        connection_resolver=lambda profile_id: get_model_connection(
            store, owner_principal_id, profile_id
        ),
        # BUG-254 — a subscription states how much of its window is left as part
        # of a turn. This is the one place that knows both the owner and the
        # store, so it is where that statement is recorded.
        limit_window_sink=lambda profile_id, windows: SubscriptionLimitStore(store).record(
            owner_principal_id, profile_id, windows
        ),
    )
    selected = router.default_provider()
    state = store.load_principal_model_state(owner_principal_id) or store.load_model_session_state(
        TERMINAL_MODEL_SESSION_ID
    )
    if state is not None:
        try:
            profile = registry.resolve_profile_id(state.profile_id)
            selected_model = state.model or profile.model
            if selected_model and "<" not in selected_model:
                if selected_model != profile.model:
                    registry.register(profile_with_model(profile, selected_model))
                selected = (profile.provider, selected_model)
        except RegistryError:
            pass
    return router, selected


__all__ = ["owner_model_runtime"]
