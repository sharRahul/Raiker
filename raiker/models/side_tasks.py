"""Separate models for side tasks — Hermes Agent's ``auxiliary.<task>`` models.

Two side tasks a turn may need a different model for:

* **summarise** — compacting a long conversation. A cheaper or faster model is
  often the better choice; the chain is tried in order and the turn's own model
  is the last resort, so compaction never becomes impossible because a side
  model is down.
* **vision** — describing an attached image when the turn's model cannot see.
  Only models that accept images may be in this chain; there is no fallback to
  the turn's model, because it is the model that could not see.

Each chain is at most three ``(profile_id, model)`` pairs, stored per owner in
their settings document under :data:`SETTINGS_KEY`. A pair that no longer
resolves is skipped, never guessed at.
"""

from __future__ import annotations

import json
from typing import Any

from raiker.contracts.ids import utc_now

TASKS: tuple[str, ...] = ("summarise", "vision")
SETTINGS_KEY = "models.side_tasks"
MAX_CHAIN = 3


class SideTaskError(ValueError):
    """A chain the owner asked for that cannot be stored, with a reason code."""


def _settings(store: Any, principal_id: str) -> dict[str, Any]:
    row = store.get_user_settings(principal_id)
    if row is None:
        return {}
    try:
        parsed = json.loads(row["settings_json"])
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def load(store: Any, principal_id: str) -> dict[str, list[tuple[str, str]]]:
    """Every task's chain, ``[]`` for a task with none."""
    raw = _settings(store, principal_id).get(SETTINGS_KEY)
    chains: dict[str, list[tuple[str, str]]] = {task: [] for task in TASKS}
    if not isinstance(raw, dict):
        return chains
    for task in TASKS:
        entries = raw.get(task)
        if not isinstance(entries, list):
            continue
        for entry in entries[:MAX_CHAIN]:
            if isinstance(entry, dict) and isinstance(entry.get("profile_id"), str) and isinstance(entry.get("model"), str):
                chains[task].append((entry["profile_id"], entry["model"]))
    return chains


def save(store: Any, principal_id: str, task: str, chain: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Validate and store one task's chain; returns what was stored."""
    if task not in TASKS:
        raise SideTaskError("side_task_unknown")
    if len(chain) > MAX_CHAIN:
        raise SideTaskError("side_task_chain_too_long")
    from raiker.models.registry import ModelProfileRegistry

    registry = ModelProfileRegistry.load()
    cleaned: list[tuple[str, str]] = []
    for profile_id, model in chain:
        model = model.strip()
        try:
            profile = registry.resolve_profile_id(profile_id)
        except Exception as exc:  # noqa: BLE001 — an unknown profile fails closed
            raise SideTaskError("side_task_profile_unknown") from exc
        if bool(profile.raw.get("test_only", False)):
            raise SideTaskError("side_task_profile_unknown")
        if not model or "<" in model:
            raise SideTaskError("side_task_model_required")
        if task == "vision" and not model_sees(profile, model, store=store, principal_id=principal_id):
            raise SideTaskError("side_task_model_lacks_vision")
        if (profile.profile_id, model) not in cleaned:
            cleaned.append((profile.profile_id, model))
    document = _settings(store, principal_id)
    stored = document.get(SETTINGS_KEY)
    chains = dict(stored) if isinstance(stored, dict) else {}
    chains[task] = [{"profile_id": p, "model": m} for p, m in cleaned]
    document[SETTINGS_KEY] = chains
    store.put_user_settings(principal_id, json.dumps(document, sort_keys=True), utc_now())
    return cleaned


def model_sees(profile: Any, model: str, *, store: Any = None, principal_id: str | None = None) -> bool:
    """Whether ``model`` on ``profile`` accepts images.

    A profile that declares vision says so for all its models; a local runtime
    Raiker can ask (Ollama) says so per model in its own catalogue.
    """
    if bool(profile.raw.get("supports_vision", False)):
        return True
    from raiker.models import local_service

    if not profile.local_only or profile.provider not in local_service.WATCHED_RUNTIMES:
        return False
    from raiker.models.readiness import effective_endpoint

    connection = None
    if store is not None and principal_id:
        from raiker.models.connections import get_model_connection

        connection = get_model_connection(store, principal_id, profile.profile_id)
    answer = local_service.liveness(profile.provider, effective_endpoint(profile, connection))
    return bool(answer and answer.has_capability(model, "vision"))


def candidates(
    store: Any,
    principal_id: str,
    task: str,
    *,
    main: tuple[str, str] | None = None,
) -> list[tuple[str, str]]:
    """``(provider, model)`` pairs to try for ``task``, in order.

    The owner's chain first, resolved from profile ids to the provider names the
    router takes; then, for summarising only, the turn's own model.
    """
    from raiker.models.registry import ModelProfileRegistry

    registry = ModelProfileRegistry.load()
    ordered: list[tuple[str, str]] = []
    for profile_id, model in load(store, principal_id).get(task, []):
        try:
            profile = registry.resolve_profile_id(profile_id)
        except Exception:  # noqa: BLE001 — a stale pair is skipped, not guessed at
            continue
        pair = (profile.provider, model)
        if pair not in ordered:
            ordered.append(pair)
    if task == "summarise" and main is not None and main not in ordered:
        ordered.append(main)
    return ordered
