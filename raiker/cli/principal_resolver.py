from __future__ import annotations

from pathlib import Path
from typing import Any

from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import Role, User
from raiker.events.types import make_event
from raiker.events.writer import EventLogWriter
from raiker.runtime.authority.models import Principal, PrincipalType, RuntimeMode
from raiker.storage.sqlite import SQLiteStore

OWNER_ROLE_ID = "rl_owner"
ADMIN_ROLE_ID = "rl_admin"
RUNTIME_GATE_MANAGER_ROLE_ID = "rl_rgm"
APPROVER_ROLE_ID = "rl_approver"

OWNER_BOOTSTRAP_ROLES = (
    OWNER_ROLE_ID,
    ADMIN_ROLE_ID,
    RUNTIME_GATE_MANAGER_ROLE_ID,
    APPROVER_ROLE_ID,
)

HUMAN_ONLY_ROLE_NAMES = {
    "owner",
    "admin",
    "approver",
    "security_admin",
    "finance_approver",
    "medical_decision_maker",
    "runtime_gate_manager",
}

AI_PRINCIPAL_TYPES = frozenset({
    PrincipalType.AI_AGENT,
    PrincipalType.AUTOMATION,
    PrincipalType.SYSTEM,
})


def _ensure_bootstrap_roles(store: SQLiteStore) -> None:
    now = utc_now()
    role_defs = [
        (OWNER_ROLE_ID, "owner", "System role for workspace owner", True),
        (ADMIN_ROLE_ID, "admin", "System role for workspace admin", True),
        (RUNTIME_GATE_MANAGER_ROLE_ID, "runtime_gate_manager",
         "System role for runtime gate management", True),
        (APPROVER_ROLE_ID, "approver", "System role for approval authority", True),
    ]
    for role_id, name, description, is_system in role_defs:
        existing = store.load_role(role_id)
        if existing is None:
            store.insert_role(Role(
                role_id=role_id, name=name, description=description,
                is_system_role=is_system, created_at=now,
            ))


def _owner_exists(store: SQLiteStore) -> bool:
    principals = store.list_principals(active_only=False)
    for p in principals:
        role_ids = p.get("role_ids", ())
        if OWNER_ROLE_ID in role_ids:
            return True
    return False


def _get_active_owner_principals(store: SQLiteStore) -> list[dict[str, Any]]:
    principals = store.list_principals(active_only=True)
    owners = []
    for p in principals:
        role_ids = p.get("role_ids", ())
        if OWNER_ROLE_ID in role_ids:
            owners.append(p)
    return owners


def bootstrap_owner(
    user_id: str,
    display_name: str,
    email: str | None = None,
    *,
    workspace_root: str | Path = ".",
    is_recovery: bool = False,
    force_recover: bool = False,
    confirm_deactivate_old: bool = False,
    recovery_reason: str = "",
) -> str:
    store = SQLiteStore(workspace_root)
    writer = EventLogWriter(store)

    if is_recovery:
        return _handle_owner_recovery(
            store, writer, user_id, display_name, email,
            force_recover=force_recover,
            confirm_deactivate_old=confirm_deactivate_old,
            recovery_reason=recovery_reason,
        )

    if _owner_exists(store):
        writer.append(make_event(
            session_id="bootstrap",
            turn_id=None,
            event_type="owner_bootstrap_denied",
            actor="system",
            payload={
                "reason": "owner already exists",
                "requested_user_id": user_id,
                "requested_display_name": display_name,
            },
        ))
        return "Bootstrap denied: owner already exists."

    _ensure_bootstrap_roles(store)
    now = utc_now()

    user = User(
        user_id=user_id,
        display_name=display_name,
        email=email,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    store.insert_user(user)

    principal_id = f"principal_{user_id}"
    store.insert_principal(
        principal_id=principal_id,
        principal_type=PrincipalType.HUMAN.value,
        display_name=display_name,
        delegated_by_user_id=None,
        role_ids=OWNER_BOOTSTRAP_ROLES,
        domain_scopes=(),
        max_runtime_mode=RuntimeMode.LOCAL_SINGLE_USER_RUNTIME.value,
        is_active=True,
    )

    for role_id in OWNER_BOOTSTRAP_ROLES:
        from raiker.contracts.models import UserRoleAssignment
        store.insert_user_role_assignment(UserRoleAssignment(
            assignment_id=new_id("ura_"),
            user_id=user_id,
            role_id=role_id,
            granted_at=now,
            granted_by="system_bootstrap",
        ))

    writer.append(make_event(
        session_id="bootstrap",
        turn_id=None,
        event_type="owner_bootstrap_requested",
        actor="system",
        payload={
            "user_id": user_id,
            "display_name": display_name,
            "email": email,
        },
    ))
    writer.append(make_event(
        session_id="bootstrap",
        turn_id=None,
        event_type="owner_bootstrap_created",
        actor="system",
        payload={
            "user_id": user_id,
            "principal_id": principal_id,
            "display_name": display_name,
            "roles": list(OWNER_BOOTSTRAP_ROLES),
        },
    ))

    return (
        f"Owner bootstrap successful.\n"
        f"  User: {user_id}\n"
        f"  Principal: {principal_id}\n"
        f"  Display name: {display_name}\n"
        f"  Roles: owner, admin, runtime_gate_manager, approver\n"
        f"  Max runtime mode: {RuntimeMode.LOCAL_SINGLE_USER_RUNTIME.value}\n"
        f"  You can now use --as {principal_id} for privileged commands."
    )


def _handle_owner_recovery(
    store: SQLiteStore,
    writer: EventLogWriter,
    user_id: str,
    display_name: str,
    email: str | None,
    *,
    force_recover: bool,
    confirm_deactivate_old: bool,
    recovery_reason: str,
) -> str:
    existing_owners = _get_active_owner_principals(store)

    if existing_owners and not force_recover:
        writer.append(make_event(
            session_id="bootstrap",
            turn_id=None,
            event_type="owner_recovery_denied",
            actor="system",
            payload={
                "reason": "active owner exists, use --force-recover",
                "existing_owner_ids": [p["principal_id"] for p in existing_owners],
            },
        ))
        return (
            "Recovery denied: active owner exists.\n"
            "Use --force-recover and --confirm-local-recovery to proceed."
        )

    if not confirm_deactivate_old or not recovery_reason:
        return (
            "Recovery requires:\n"
            "  --confirm-local-recovery (acknowledge local-only recovery)\n"
            "  --reason <reason> (audit reason for recovery)"
        )

    _ensure_bootstrap_roles(store)
    now = utc_now()

    old_owner_ids = []
    if existing_owners and force_recover:
        for p in existing_owners:
            if confirm_deactivate_old:
                store.deactivate_principal(p["principal_id"])
                old_owner_ids.append(p["principal_id"])

    user = User(
        user_id=user_id,
        display_name=display_name,
        email=email,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    store.insert_user(user)

    principal_id = f"principal_{user_id}"
    store.insert_principal(
        principal_id=principal_id,
        principal_type=PrincipalType.HUMAN.value,
        display_name=display_name,
        delegated_by_user_id=None,
        role_ids=OWNER_BOOTSTRAP_ROLES,
        domain_scopes=(),
        max_runtime_mode=RuntimeMode.LOCAL_SINGLE_USER_RUNTIME.value,
        is_active=True,
    )

    writer.append(make_event(
        session_id="bootstrap",
        turn_id=None,
        event_type="owner_recovery_requested",
        actor="system",
        payload={
            "reason": recovery_reason,
            "user_id": user_id,
            "display_name": display_name,
        },
    ))
    writer.append(make_event(
        session_id="bootstrap",
        turn_id=None,
        event_type="owner_recovery_created",
        actor="system",
        payload={
            "user_id": user_id,
            "principal_id": principal_id,
            "recovery_reason": recovery_reason,
        },
    ))

    if old_owner_ids:
        writer.append(make_event(
            session_id="bootstrap",
            turn_id=None,
            event_type="owner_recovery_old_owner_deactivated",
            actor="system",
            payload={
                "deactivated_principal_ids": old_owner_ids,
                "recovery_reason": recovery_reason,
            },
        ))

    return (
        f"Owner recovery successful.\n"
        f"  User: {user_id}\n"
        f"  Principal: {principal_id}\n"
        f"  Recovery reason: {recovery_reason}\n"
        f"  Old owner deactivated: {bool(old_owner_ids)}"
    )


def resolve_local_principal(
    workspace_root: str | Path = ".",
    explicit_principal_id: str | None = None,
) -> tuple[Principal | None, str]:
    store = SQLiteStore(workspace_root)
    writer = EventLogWriter(store)

    if explicit_principal_id is not None:
        raw = store.get_principal(explicit_principal_id)
        if raw is None:
            writer.append(make_event(
                session_id="authz",
                turn_id=None,
                event_type="principal_resolution_failed",
                actor="system",
                payload={
                    "reason": "principal_not_found",
                    "requested_principal_id": explicit_principal_id,
                },
            ))
            return None, f"Principal not found: {explicit_principal_id}"
        raw["principal_type"] = PrincipalType(raw["principal_type"]) if isinstance(raw["principal_type"], str) else raw["principal_type"]
        principal = Principal(**raw)
        if not principal.is_active:
            writer.append(make_event(
                session_id="authz",
                turn_id=None,
                event_type="principal_resolution_failed",
                actor="system",
                payload={
                    "reason": "principal_not_active",
                    "principal_id": explicit_principal_id,
                },
            ))
            return None, f"Principal is not active: {explicit_principal_id}"
        if principal.principal_type in AI_PRINCIPAL_TYPES:
            writer.append(make_event(
                session_id="authz",
                turn_id=None,
                event_type="principal_resolution_failed",
                actor="system",
                payload={
                    "reason": "ai_principal_not_allowed",
                    "principal_id": explicit_principal_id,
                    "principal_type": principal.principal_type.value,
                },
            ))
            return None, f"AI principal cannot be used for gate operations: {explicit_principal_id}"
        writer.append(make_event(
            session_id="authz",
            turn_id=None,
            event_type="principal_resolved",
            actor="system",
            payload={
                "principal_id": principal.principal_id,
                "principal_type": principal.principal_type.value,
                "role_ids": list(principal.role_ids),
                "resolution": "explicit",
            },
        ))
        return principal, ""

    owners = _get_active_owner_principals(store)

    if not owners:
        writer.append(make_event(
            session_id="authz",
            turn_id=None,
            event_type="principal_resolution_failed",
            actor="system",
            payload={
                "reason": "no_owner_configured",
            },
        ))
        return None, "No owner principal is configured. Run /bootstrap-owner first."

    if len(owners) > 1:
        owner_ids = [o["principal_id"] for o in owners]
        writer.append(make_event(
            session_id="authz",
            turn_id=None,
            event_type="principal_resolution_failed",
            actor="system",
            payload={
                "reason": "multiple_owners_require_explicit",
                "owner_ids": owner_ids,
            },
        ))
        return None, (
            f"Multiple owner principals found ({len(owners)}). "
            f"Use --as <principal_id> to specify which principal to act as."
        )

    raw = owners[0]
    if isinstance(raw.get("principal_type"), str):
        raw["principal_type"] = PrincipalType(raw["principal_type"])
    principal = Principal(**raw)
    writer.append(make_event(
        session_id="authz",
        turn_id=None,
        event_type="principal_resolved",
        actor="system",
        payload={
            "principal_id": principal.principal_id,
            "principal_type": principal.principal_type.value,
            "role_ids": list(principal.role_ids),
            "resolution": "default_single_owner",
        },
    ))
    return principal, ""


def get_principal_info(
    workspace_root: str | Path = ".",
    explicit_principal_id: str | None = None,
) -> str:
    principal, err = resolve_local_principal(workspace_root, explicit_principal_id)
    if principal is None:
        return err

    from raiker.runtime.authority import RuntimeAuthority
    store = SQLiteStore(workspace_root)
    writer = EventLogWriter(store)
    authority = RuntimeAuthority(store, writer)
    mode = authority.get_runtime_mode()
    role_names = []
    for rid in principal.role_ids:
        name = store.get_role_name(rid)
        role_names.append(name or rid)

    lines = [
        f"Acting principal: {principal.principal_id}",
        f"  Display name: {principal.display_name}",
        f"  Principal type: {principal.principal_type.value}",
        f"  Roles: {', '.join(role_names)}",
        f"  Domain scopes: {', '.join(principal.domain_scopes) or '(none)'}",
        f"  Max runtime mode: {principal.max_runtime_mode}",
        f"  Active: {principal.is_active}",
        f"  Current runtime mode: {mode.get('mode_name', 'development_preview')}",
    ]
    return "\n".join(lines)


def list_principals_info(workspace_root: str | Path = ".") -> str:
    store = SQLiteStore(workspace_root)
    principals = store.list_principals(active_only=False)
    if not principals:
        return "No principals configured. Run /bootstrap-owner first."
    lines = ["Principals:"]
    for p in principals:
        role_ids = p.get("role_ids", ())
        role_names = []
        for rid in role_ids:
            name = store.get_role_name(rid)
            role_names.append(name or rid)
        active = "active" if p.get("is_active") else "inactive"
        lines.append(
            f"- {p['principal_id']} type={p.get('principal_type', '')} "
            f"roles=[{', '.join(role_names)}] {active}"
        )
    return "\n".join(lines)


def get_principal_detail(principal_id: str, workspace_root: str | Path = ".") -> str:
    store = SQLiteStore(workspace_root)
    raw = store.get_principal(principal_id)
    if raw is None:
        return f"Principal not found: {principal_id}"
    role_names = []
    for rid in raw.get("role_ids", ()):
        name = store.get_role_name(rid)
        role_names.append(name or rid)
    lines = [
        f"Principal: {raw['principal_id']}",
        f"  Display name: {raw.get('display_name', '')}",
        f"  Type: {raw.get('principal_type', '')}",
        f"  Roles: {', '.join(role_names)}",
        f"  Domain scopes: {', '.join(raw.get('domain_scopes', ())) or '(none)'}",
        f"  Max runtime mode: {raw.get('max_runtime_mode', 'development_preview')}",
        f"  Active: {bool(raw.get('is_active', True))}",
        f"  Delegated by user: {raw.get('delegated_by_user_id') or 'N/A'}",
    ]
    if raw.get("expires_at"):
        lines.append(f"  Expires at: {raw['expires_at']}")
    return "\n".join(lines)


def check_owner_bootstrapped(workspace_root: str | Path = ".") -> bool:
    store = SQLiteStore(workspace_root)
    return _owner_exists(store)


def check_runtime_gate_manager_available(workspace_root: str | Path = ".") -> bool:
    store = SQLiteStore(workspace_root)
    principals = store.list_principals(active_only=True)
    for p in principals:
        role_ids = p.get("role_ids", ())
        for rid in role_ids:
            name = store.get_role_name(rid)
            if name == "runtime_gate_manager":
                return True
    return False


def check_acting_principal_available(workspace_root: str | Path = ".") -> bool:
    principal, err = resolve_local_principal(workspace_root)
    return principal is not None


def get_bootstrap_status(workspace_root: str | Path = ".") -> dict[str, Any]:
    return {
        "owner_bootstrapped": check_owner_bootstrapped(workspace_root),
        "acting_principal_available": check_acting_principal_available(workspace_root),
        "runtime_gate_manager_available": check_runtime_gate_manager_available(workspace_root),
    }
