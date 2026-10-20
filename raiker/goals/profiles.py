"""Settings-owned execution profiles (PA-D02).

A profile is the reusable ceiling a goal's work runs under: which kinds of model
it may reach (on this machine, hosted, or both), optionally which providers,
whether personal memory may travel to a hosted model with it, and the budget a
goal inherits. Settings is the only place that creates, changes, activates or
binds one; a prompt, memory, schedule, connector or agent cannot.

Every field here is enforced by :mod:`raiker.goals.coordinator`. A field that
nothing would enforce does not belong in the record — BUG-345 removed a
first-run *Local only* answer for exactly that reason.

Versioned the way a design system is: a change writes the next version, and a
goal pins the id and version it was accepted under, so a later change is
detected and revalidated rather than silently applied to work in flight.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from raiker.contracts.ids import new_id, utc_now

#: The comprehensible starting points Settings offers. Each becomes an ordinary
#: owner-inspectable profile; none is a hidden provider fallback.
TEMPLATES: dict[str, dict[str, Any]] = {
    "private_local": {
        "name": "Private local",
        "summary": "Only models on this machine. Nothing a goal does is sent to a hosted model.",
        "allow_local": True,
        "allow_hosted": False,
        "memory_to_hosted": False,
    },
    "balanced": {
        "name": "Balanced",
        "summary": "Local and hosted models. Personal memory stays off hosted models.",
        "allow_local": True,
        "allow_hosted": True,
        "memory_to_hosted": False,
    },
    "cloud_first": {
        "name": "Cloud-first",
        "summary": "Local and hosted models, and personal memory may go to the hosted model doing the work.",
        "allow_local": True,
        "allow_hosted": True,
        "memory_to_hosted": True,
    },
}

DEFAULT_MAX_STEP_RUNS = 10
MAX_STEP_RUNS_CEILING = 100
MAX_COST_CEILING_USD = 1000.0
MAX_PROVIDERS = 20


class ProfileError(ValueError):
    """A profile change refused, with the reason code the route answers with."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ExecutionProfile:
    profile_id: str
    version: int
    name: str
    template: str
    allow_local: bool
    allow_hosted: bool
    allowed_providers: tuple[str, ...]
    memory_to_hosted: bool
    max_step_runs: int
    max_cost_usd: float | None
    created_at: str

    def view(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "version": self.version,
            "name": self.name,
            "template": self.template,
            "allow_local": self.allow_local,
            "allow_hosted": self.allow_hosted,
            "allowed_providers": list(self.allowed_providers),
            "memory_to_hosted": self.memory_to_hosted,
            "max_step_runs": self.max_step_runs,
            "max_cost_usd": self.max_cost_usd,
            "created_at": self.created_at,
        }

    def allows(self, *, provider: str, local: bool) -> bool:
        """Whether a model of this provider and placement may do the goal's work."""
        if local and not self.allow_local:
            return False
        if not local and not self.allow_hosted:
            return False
        return not self.allowed_providers or provider in self.allowed_providers


def _profile(row: Mapping[str, Any]) -> ExecutionProfile:
    try:
        providers = json.loads(row["allowed_providers_json"] or "[]")
    except ValueError:
        providers = []
    return ExecutionProfile(
        profile_id=str(row["profile_id"]),
        version=int(row["version"]),
        name=str(row["name"]),
        template=str(row["template"]),
        allow_local=bool(row["allow_local"]),
        allow_hosted=bool(row["allow_hosted"]),
        allowed_providers=tuple(str(p) for p in providers if isinstance(p, str)),
        memory_to_hosted=bool(row["memory_to_hosted"]),
        max_step_runs=int(row["max_step_runs"]),
        max_cost_usd=None if row["max_cost_usd"] is None else float(row["max_cost_usd"]),
        created_at=str(row["created_at"]),
    )


def clean_fields(fields: Mapping[str, Any], *, base: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one profile's fields over ``base``; refuse rather than coerce."""
    merged = {**base, **{k: v for k, v in fields.items() if v is not None or k == "max_cost_usd"}}
    name = str(merged.get("name") or "").strip()
    if not name or len(name) > 60:
        raise ProfileError("profile_name_invalid")
    allow_local = bool(merged.get("allow_local"))
    allow_hosted = bool(merged.get("allow_hosted"))
    if not allow_local and not allow_hosted:
        # A profile that admits no model would block every goal under it with
        # a reason the owner did not intend; say so where it is set.
        raise ProfileError("profile_allows_no_model")
    providers_raw = merged.get("allowed_providers") or []
    if not isinstance(providers_raw, (list, tuple)) or len(providers_raw) > MAX_PROVIDERS:
        raise ProfileError("profile_providers_invalid")
    providers: list[str] = []
    for entry in providers_raw:
        text = str(entry).strip()
        if not text or len(text) > 60 or not all(ch.isalnum() or ch in "-_." for ch in text):
            raise ProfileError("profile_providers_invalid")
        if text not in providers:
            providers.append(text)
    try:
        max_step_runs = int(merged.get("max_step_runs") or DEFAULT_MAX_STEP_RUNS)
    except (TypeError, ValueError):
        raise ProfileError("profile_budget_invalid") from None
    if not 1 <= max_step_runs <= MAX_STEP_RUNS_CEILING:
        raise ProfileError("profile_budget_invalid")
    cost = merged.get("max_cost_usd")
    if cost is not None:
        try:
            cost = round(float(cost), 2)
        except (TypeError, ValueError):
            raise ProfileError("profile_budget_invalid") from None
        if not 0 < cost <= MAX_COST_CEILING_USD:
            raise ProfileError("profile_budget_invalid")
    return {
        "name": name,
        "allow_local": allow_local,
        "allow_hosted": allow_hosted,
        "allowed_providers": providers,
        # Memory can only travel to a hosted model a profile admits.
        "memory_to_hosted": bool(merged.get("memory_to_hosted")) and allow_hosted,
        "max_step_runs": max_step_runs,
        "max_cost_usd": cost,
    }


def _insert(connection: Any, owner: str, profile_id: str, version: int, template: str, f: Mapping[str, Any]) -> None:
    connection.execute(
        """INSERT INTO execution_profiles
           (profile_id, version, owner_principal_id, name, template, allow_local, allow_hosted,
            allowed_providers_json, memory_to_hosted, max_step_runs, max_cost_usd, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            profile_id, version, owner, f["name"], template, int(f["allow_local"]), int(f["allow_hosted"]),
            json.dumps(list(f["allowed_providers"])), int(f["memory_to_hosted"]), int(f["max_step_runs"]),
            f["max_cost_usd"], utc_now(),
        ),
    )


def create_profile(store: Any, *, owner: str, template: str, fields: Mapping[str, Any]) -> ExecutionProfile:
    spec = TEMPLATES.get(template)
    if spec is None:
        raise ProfileError("profile_template_unknown")
    base = {key: spec[key] for key in ("name", "allow_local", "allow_hosted", "memory_to_hosted")}
    clean = clean_fields(fields, base={**base, "max_step_runs": DEFAULT_MAX_STEP_RUNS, "max_cost_usd": None})
    profile_id = new_id("xprof_")
    with store.connect() as connection:
        _insert(connection, owner, profile_id, 1, template, clean)
    found = get_profile(store, owner=owner, profile_id=profile_id)
    assert found is not None
    return found


def update_profile(
    store: Any, *, owner: str, profile_id: str, base_version: int, fields: Mapping[str, Any]
) -> ExecutionProfile:
    """Write the next version, only over the version the owner was looking at."""
    current = get_profile(store, owner=owner, profile_id=profile_id)
    if current is None:
        raise ProfileError("execution_profile_unknown")
    if current.version != base_version:
        raise ProfileError("execution_profile_version_stale")
    clean = clean_fields(fields, base=current.view())
    with store.connect() as connection:
        _insert(connection, owner, profile_id, current.version + 1, current.template, clean)
    found = get_profile(store, owner=owner, profile_id=profile_id)
    assert found is not None
    return found


def get_profile(
    store: Any, *, owner: str, profile_id: str, version: int | None = None
) -> ExecutionProfile | None:
    """One profile at ``version``, or its latest. Another owner's id reads as unknown."""
    with store.connect() as connection:
        if version is None:
            row = connection.execute(
                "SELECT * FROM execution_profiles WHERE owner_principal_id = ? AND profile_id = ? "
                "ORDER BY version DESC LIMIT 1",
                (owner, profile_id),
            ).fetchone()
        else:
            row = connection.execute(
                "SELECT * FROM execution_profiles WHERE owner_principal_id = ? AND profile_id = ? AND version = ?",
                (owner, profile_id, version),
            ).fetchone()
    return _profile(dict(row)) if row is not None else None


def list_profiles(store: Any, *, owner: str) -> list[ExecutionProfile]:
    """Each profile at its latest version, oldest first."""
    with store.connect() as connection:
        rows = connection.execute(
            """SELECT p.* FROM execution_profiles p
               JOIN (SELECT profile_id, MAX(version) AS v FROM execution_profiles
                     WHERE owner_principal_id = ? GROUP BY profile_id) latest
                 ON latest.profile_id = p.profile_id AND latest.v = p.version
               WHERE p.owner_principal_id = ? ORDER BY p.profile_id""",
            (owner, owner),
        ).fetchall()
    profiles = [_profile(dict(row)) for row in rows]
    first_seen = _first_created(store, owner)
    return sorted(profiles, key=lambda p: (first_seen.get(p.profile_id, ""), p.profile_id))


def _first_created(store: Any, owner: str) -> dict[str, str]:
    with store.connect() as connection:
        rows = connection.execute(
            "SELECT profile_id, MIN(created_at) AS at FROM execution_profiles WHERE owner_principal_id = ? "
            "GROUP BY profile_id",
            (owner,),
        ).fetchall()
    return {str(r["profile_id"]): str(r["at"]) for r in rows}


def bindings(store: Any, *, owner: str) -> dict[str, str]:
    """``project_id`` → ``profile_id``; the key ``""`` is the owner's active profile."""
    with store.connect() as connection:
        rows = connection.execute(
            "SELECT project_id, profile_id FROM execution_profile_bindings WHERE owner_principal_id = ?",
            (owner,),
        ).fetchall()
    return {str(r["project_id"]): str(r["profile_id"]) for r in rows}


def bind(store: Any, *, owner: str, project_id: str, profile_id: str | None) -> None:
    """Bind ``profile_id`` as active (``project_id`` "") or for one project; ``None`` unbinds."""
    if profile_id is not None and get_profile(store, owner=owner, profile_id=profile_id) is None:
        raise ProfileError("execution_profile_unknown")
    with store.connect() as connection:
        if profile_id is None:
            connection.execute(
                "DELETE FROM execution_profile_bindings WHERE owner_principal_id = ? AND project_id = ?",
                (owner, project_id),
            )
            return
        connection.execute(
            """INSERT INTO execution_profile_bindings (owner_principal_id, project_id, profile_id, bound_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(owner_principal_id, project_id)
               DO UPDATE SET profile_id = excluded.profile_id, bound_at = excluded.bound_at""",
            (owner, project_id, profile_id, utc_now()),
        )


def resolve_for(store: Any, *, owner: str, project_id: str | None) -> tuple[ExecutionProfile | None, str]:
    """The profile new work in ``project_id`` inherits, and where it came from.

    A project's own binding wins; otherwise the owner's active profile. ``None``
    means Settings has not chosen one, which blocks a goal rather than letting
    it run under an unstated boundary.
    """
    bound = bindings(store, owner=owner)
    if project_id and project_id in bound:
        return get_profile(store, owner=owner, profile_id=bound[project_id]), "project"
    if "" in bound:
        return get_profile(store, owner=owner, profile_id=bound[""]), "active"
    return None, "none"


@dataclass(frozen=True)
class ChainEntry:
    profile_id: str
    provider: str
    local: bool
    allowed: bool


def model_chain(
    store: Any, owner: str, profile: ExecutionProfile, model_profile: str | None = None, model: str | None = None
) -> list[ChainEntry]:
    """Every model a goal step's turn could actually run on, judged by ``profile``.

    The runtime tries the goal's chosen model (``model_profile``/``model``) and
    then the owner's saved fallback sequence, so judging the primary alone would let a fallback carry the work
    somewhere the profile forbids. A profile that cannot be resolved reads as
    disallowed: an unknown model is never assumed to be local.
    """
    from raiker.models.readiness import ModelReadinessService, ProviderCatalogueProbe
    from raiker.models.registry import ModelProfileRegistry

    readiness = ModelReadinessService(store, probe=ProviderCatalogueProbe(store))
    registry = ModelProfileRegistry.load()
    ids: list[str] = []
    try:
        primary, _model = readiness.resolve_request_target(owner, model_profile, model)
        ids.append(primary)
    except Exception:  # noqa: BLE001 - an unreadable selection is an unresolved entry
        ids.append("")
    for candidate in readiness._fallback_profile_ids(owner):  # noqa: SLF001
        if candidate not in ids:
            ids.append(candidate)
    entries: list[ChainEntry] = []
    for profile_id in ids:
        try:
            resolved = registry.resolve_profile_id(profile_id)
        except Exception:  # noqa: BLE001
            entries.append(ChainEntry(profile_id or "unselected", "unknown", False, False))
            continue
        local = bool(resolved.local_only)
        entries.append(
            ChainEntry(
                resolved.profile_id,
                resolved.provider,
                local,
                profile.allows(provider=resolved.provider, local=local),
            )
        )
    return entries


def chain_refusal(entries: Iterable[ChainEntry]) -> str:
    """The first entry the profile refuses, as ``provider (where)``; "" when none."""
    for entry in entries:
        if not entry.allowed:
            where = "on this machine" if entry.local else "hosted"
            return f"{entry.provider} ({where})"
    return ""
