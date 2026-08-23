"""Production critical-risk classification (User-Centric Zero Trust, ZT-7 / F6).

Historically ``RiskLevelValue.CRITICAL`` was assigned only in tests, so the
router's critical floor had no production callers. This module is the canonical,
in-code classification table that makes ``critical`` a real production tier: the
router (:mod:`raiker.runtime.authority.router`) calls :func:`classify_critical`
during risk resolution and elevates any matching action to the critical floor —
where its resting state is deny and only a notified human may resolve it.

The table is **data, not scattered conditionals**. An action is critical when it
matches any of the five criteria from the plan (each carries a stable code and a
ZT reference so coverage is traceable):

* **(a)** enabling or relaxing Tier-2 execution (shell / process / network /
  web-fetch), including threat-model acknowledgments and confirmation-token
  issuance — :data:`CRITICAL_TIER2_RELAXATION`;
* **(b)** an external send or calendar invite to any recipient/attendee not on
  the account's allowlist — :data:`CRITICAL_EXTERNAL_SEND_UNLISTED`;
* **(c)** a checkpoint restore that would overwrite changes made by a *different*
  principal since the checkpoint — :data:`CRITICAL_CROSS_PRINCIPAL_RESTORE`;
* **(d)** creating or broadening a standing approval grant (F3) —
  :data:`CRITICAL_GRANT_MUTATION`;
* **(e)** any operation on vault/credential material or on an egress allowlist —
  :data:`CRITICAL_VAULT_OR_EGRESS`.

**Extension-only invariant:** this table may only be *extended* (never narrowed)
without a threat-model note — the F5 readiness validator mechanically enforces
that "documentation never runs ahead of code". Removing a criterion or a member
of one of the frozen sets below weakens the floor and is a governance change.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

# ── criterion codes (stable; referenced by tests and audit events) ────────────
CRITICAL_TIER2_RELAXATION = "tier2_execution_relaxation"
CRITICAL_EXTERNAL_SEND_UNLISTED = "external_send_to_non_allowlisted_recipient"
CRITICAL_CROSS_PRINCIPAL_RESTORE = "cross_principal_checkpoint_restore"
CRITICAL_GRANT_MUTATION = "standing_grant_creation_or_broadening"
CRITICAL_VAULT_OR_EGRESS = "vault_credential_or_egress_allowlist_operation"


@dataclass(frozen=True)
class CriticalMatch:
    """A matched critical criterion — the *why* behind an elevation.

    ``code`` is the stable criterion id; ``zt_ref`` ties it to the normative
    policy; ``detail`` is a short, metadata-only reason safe for the audit log
    (never a recipient address, secret, or file content).
    """

    code: str
    zt_ref: str
    detail: str


# The three Tier-2 execution capabilities whose *relaxation* is critical. Note
# this is the set of capabilities being enabled/relaxed — not the everyday act of
# running an already-enabled Tier-2 executor (that is governed by its own gate +
# threat-ack + confirmation token, unchanged).
TIER2_CAPABILITIES: frozenset[str] = frozenset({
    "shell_execution",
    "process_execution",
    "web_fetch",
})

# Action types that *relax* a capability gate or issue the tokens that unlock a
# Tier-2 capability. Elevation is conditional on the target being a Tier-2
# capability (checked against TIER2_CAPABILITIES from the arguments).
_TIER2_GATE_ACTIONS: frozenset[str] = frozenset({
    "enable_runtime_gate",
    "capability_transition",
    "capability_enable",
    "threat_model_ack",
    "tier2_threat_ack",
    "confirmation_token_issue",
    "tier2_confirmation_token",
})

# Non-disabled gate states — relaxing *to* one of these is what makes a Tier-2
# gate transition critical. Transitioning a gate to disabled/planned tightens and
# is never critical.
_RELAXED_GATE_STATES: frozenset[str] = frozenset({
    "enabled",
    "enabled_runtime",
    "allow",
    "auto",
    "ready",
})

# External send / calendar-invite action types whose recipients are checked
# against the account allowlist (Workstream E). An empty allowlist means every
# recipient is non-allowlisted → fail-closed critical.
_EXTERNAL_SEND_ACTIONS: frozenset[str] = frozenset({
    "email_send",
    "email_send_execution",
    "calendar_invite",
    "calendar_sync",
    "calendar_sync_execution",
})

# Argument keys that carry one or more recipient/attendee identities.
_RECIPIENT_KEYS: tuple[str, ...] = ("to", "recipient", "recipients", "attendee", "attendees", "cc", "bcc")

# Standing-grant mutation action types (F3). Grants are *born* from a critical,
# human-decided action — that is what makes their later unprompted use legitimate.
_GRANT_MUTATION_ACTIONS: frozenset[str] = frozenset({
    "standing_grant_create",
    "standing_grant_broaden",
    "grant_create",
    "grant_broaden",
})

# Vault / credential / egress-allowlist operations. Matched on either the action
# type or the tool/service name so a connector-shaped credential op is caught too.
_VAULT_EGRESS_TOKENS: frozenset[str] = frozenset({
    "vault_write",
    "vault_delete",
    "vault_rotate",
    "vault_export",
    "credential_write",
    "credential_store",
    "credential_rotate",
    "credential_delete",
    "credential_export",
    "egress_allowlist_add",
    "egress_allowlist_remove",
    "egress_allowlist_update",
    "egress_allowlist_set",
})


def _recipients(arguments: Mapping[str, Any]) -> list[str]:
    """Flatten every recipient/attendee identity found in the arguments."""
    found: list[str] = []
    for key in _RECIPIENT_KEYS:
        value = arguments.get(key)
        if isinstance(value, str) and value.strip():
            found.append(value.strip())
        elif isinstance(value, (list, tuple)):
            found.extend(str(item).strip() for item in value if str(item).strip())
    return found


def _on_allowlist(recipient: str, allowlist: Sequence[str]) -> bool:
    """True when ``recipient`` matches any glob on the allowlist (case-insensitive)."""
    target = recipient.lower()
    return any(fnmatch.fnmatch(target, str(pattern).lower()) for pattern in allowlist)


def classify_critical(
    action_type: str,
    tool_or_service_name: str,
    arguments: Mapping[str, Any] | None,
    *,
    recipient_allowlist: Sequence[str] = (),
) -> CriticalMatch | None:
    """Return the matched critical criterion, or ``None`` when not critical.

    Pure and side-effect-free: the router uses the return value to elevate risk
    to ``critical`` (routing the action to the human-confirmation floor). The
    checks are ordered by the plan's (a)-(e) enumeration; the first match wins.
    """
    args: Mapping[str, Any] = arguments or {}

    # (a) Tier-2 execution relaxation.
    if action_type in _TIER2_GATE_ACTIONS:
        target = str(
            args.get("capability")
            or args.get("target_capability")
            or args.get("gate")
            or tool_or_service_name
        )
        if target in TIER2_CAPABILITIES:
            # A gate transition is critical only when it relaxes (enables). Acks
            # and token issuance are always in service of relaxation → critical.
            target_state = str(args.get("target_state") or args.get("state") or "").lower()
            relaxing = (
                action_type not in {"enable_runtime_gate", "capability_transition", "capability_enable"}
                or target_state == ""
                or target_state in _RELAXED_GATE_STATES
            )
            if relaxing:
                return CriticalMatch(
                    code=CRITICAL_TIER2_RELAXATION,
                    zt_ref="ZT-7",
                    detail=f"relaxes Tier-2 capability {target}",
                )

    # (b) External send / calendar invite to a non-allowlisted recipient.
    if action_type in _EXTERNAL_SEND_ACTIONS:
        recipients = _recipients(args)
        unlisted = [r for r in recipients if not _on_allowlist(r, recipient_allowlist)]
        if unlisted:
            return CriticalMatch(
                code=CRITICAL_EXTERNAL_SEND_UNLISTED,
                zt_ref="ZT-7",
                detail=f"{len(unlisted)} recipient(s) not on the account allowlist",
            )

    # (c) Cross-principal checkpoint restore.
    if action_type in {"checkpoint_restore", "checkpoint_restore_execution"} and any(
        bool(args.get(flag))
        for flag in ("touches_other_principal", "cross_principal", "overwrites_other_principal")
    ):
        return CriticalMatch(
            code=CRITICAL_CROSS_PRINCIPAL_RESTORE,
            zt_ref="ZT-7",
            detail="restore overwrites changes made by a different principal",
        )

    # (d) Standing-grant creation or broadening.
    if action_type in _GRANT_MUTATION_ACTIONS:
        return CriticalMatch(
            code=CRITICAL_GRANT_MUTATION,
            zt_ref="ZT-7",
            detail="creates or broadens a standing approval grant",
        )

    # (e) Vault / credential / egress-allowlist operation.
    if action_type in _VAULT_EGRESS_TOKENS or tool_or_service_name in _VAULT_EGRESS_TOKENS:
        return CriticalMatch(
            code=CRITICAL_VAULT_OR_EGRESS,
            zt_ref="ZT-7",
            detail="operates on vault/credential material or an egress allowlist",
        )

    return None
