"""The owner's pinned model for a profile, and what an unreadable store means.

A hosted profile ships a ``<model>`` placeholder, so the model it actually runs
is the one the owner pinned. That pin lives in ``principal_configured_models``
and is read on the way into every turn: by the gateway resolving the turn's
profile, by readiness resolving the target it reports on, and by the advisor
resolving the model a consult would call.

``None`` already means *the owner pinned nothing*, which for a placeholder
profile makes it unrunnable and drops it from the fallback chain and from
readiness, so a storage failure must never read as ``None``: it would silently
change which model Raiker runs, and every surface would report that altered
reality as the truth (GCR-46).

The distinction this module exists to keep:

``None``
    The store was read and holds no pin for this profile. A real answer.

:class:`ConfiguredModelStoreUnavailable`
    The store could not be read. Not an answer — the caller must say so rather
    than resolve a model as if it knew.
"""

from __future__ import annotations

from typing import Protocol


class ConfiguredModelStoreUnavailable(RuntimeError):
    """The configured-model store could not be read.

    Deliberately not caught where it is raised. A caller that turns this back
    into ``None`` has reinstated the defect: it would report "no model pinned"
    about an owner who pinned one, and pick a different model than the one they
    chose.
    """

    reason_code = "configured_model_store_unavailable"


class ConfiguredModelStore(Protocol):
    """The one storage method this module needs."""

    def list_configured_models(self, principal_id: str) -> list[tuple[str, str]]: ...


def pinned_model(
    store: ConfiguredModelStore, principal_id: str, profile_id: str
) -> str | None:
    """The owner's most recent pinned model for *profile_id*, or ``None``.

    Raises :class:`ConfiguredModelStoreUnavailable` when the store cannot be
    read, so an unreadable store is never mistaken for an unset one.
    """
    try:
        pairs = store.list_configured_models(principal_id)
    except Exception as exc:  # noqa: BLE001 — re-raised as the named failure
        raise ConfiguredModelStoreUnavailable(
            ConfiguredModelStoreUnavailable.reason_code
        ) from exc
    for candidate_profile, candidate_model in reversed(list(pairs or [])):
        if candidate_profile == profile_id and candidate_model:
            return str(candidate_model)
    return None
