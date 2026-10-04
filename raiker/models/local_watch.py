"""Keep checking the models owners chose on a local service Raiker watches.

The owner decided (2026-10-04) that Raiker must not forget: once an Ollama
model is chosen it is checked again on its own, so the Models page, the
readiness line and every composer say *Ready* while the service is running and
serving that model, and say why not — stopped, or the model is gone — the moment
either stops being true. Without this, readiness was a snapshot the owner had to
renew by pressing **Check**, and a service stopped after the check went on
reading Ready until its window ran out.

The pass is one of the host tick's contained passes. For each account it reads
the choices that name a watched local profile — the default model, each
surface's model and each model kept offered — and runs the same exact-model
check **Check** runs. For a local profile that check is a catalogue read on
this machine and nothing else: no generation, no credential, no egress.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from raiker.models import local_service

if TYPE_CHECKING:
    from raiker.storage.sqlite import SQLiteStore


def _watched_profiles() -> dict[str, object]:
    from raiker.models.registry import ModelProfileRegistry

    return {
        profile.profile_id: profile
        for profile in ModelProfileRegistry.load().list_profiles()
        if profile.local_only
        and profile.provider in local_service.WATCHED_RUNTIMES
        and not bool(profile.raw.get("test_only", False))
    }


def owner_targets(store: SQLiteStore, principal_id: str) -> list[tuple[str, str]]:
    """Every ``(profile_id, model)`` this owner chose on a watched local profile."""
    watched = _watched_profiles()
    if not watched:
        return []
    targets: list[tuple[str, str]] = []

    def add(profile_id: str, model: str | None) -> None:
        concrete = (model or "").strip()
        if (
            profile_id in watched
            and concrete
            and "<" not in concrete
            and (profile_id, concrete) not in targets
        ):
            targets.append((profile_id, concrete))

    state = store.load_principal_model_state(principal_id)
    if state is not None:
        add(state.profile_id, state.model)
    for _surface, profile_id, model in store.list_surface_model_defaults(principal_id) or []:
        add(str(profile_id), str(model))
    for profile_id, model in store.list_configured_models(principal_id) or []:
        add(str(profile_id), str(model))
    return targets


async def recheck_local_selections(store: SQLiteStore) -> int:
    """Re-check every owner's watched local choices. Returns how many were checked.

    The liveness cache is refreshed first so the Models page reads the same
    answer this pass acted on. A check that raises is the readiness service's
    to classify; one owner's failure does not stop the next owner's check.
    """
    from raiker.models.readiness import ModelReadinessService, ProviderCatalogueProbe

    checked = 0
    service = ModelReadinessService(store, probe=ProviderCatalogueProbe(store))
    for account in store.list_accounts():
        principal_id = str(account["principal_id"])
        targets = owner_targets(store, principal_id)
        if not targets:
            continue
        local_service.owner_services(store, principal_id, force=True)
        for profile_id, model in targets:
            await service.check_selected(principal_id, profile_id, model)
            checked += 1
    return checked
