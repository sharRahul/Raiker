# Per-turn machine identity threat model

## Scope

ADD-03 separates the authenticated human owner from the machine that proposes
and executes agentic actions. The protected path is:

```text
authenticated owner → embedded workspace issuer → signed turn identity
→ orchestrator trusted context → broker verification → policy and gates
→ owner-scoped executor → machine-attributed evidence
```

The issuer uses an Ed25519 key whose private seed is encrypted with the
workspace application key. An attestation is short-lived and binds its version,
issuer and key IDs, SPIFFE-style subject, machine principal, principal type,
delegated owner, workspace, session, turn, roles, `tool_broker` audience,
issuance/expiry times, and token ID. Bearer tokens and signatures are never
persisted in action, approval, or event records.

## Assets and trust boundaries

- The encrypted issuer seed and public verification key.
- The authenticated human session and its owner-scoped resources and credential
  references.
- The signed turn attestation and the active machine-principal record.
- Immutable approval proposal attribution and proposal hash.
- Actor/owner separation in `ToolExecutionContext` and audit evidence.
- The boundary between untrusted model/tool content and the broker.

The workspace host, issuer, lifecycle, broker, owner-scoped executors, and
SQLite store are trusted components. Model output, provider responses,
repository/email/web content, plugin payloads, client-supplied identity fields,
and tool arguments are untrusted.

## Attacker capabilities and controls

| Threat | Control | Verification evidence |
|---|---|---|
| Spoof a human or another turn | The broker overwrites model proposer fields and verifies owner, workspace, session, turn, principal, and audience against trusted call context | `tests/test_machine_identity.py`, `tests/test_machine_identity_turns.py`, broker boundary tests |
| Tamper with claims or signature | Canonical UTF-8 JSON is Ed25519-signed; malformed payloads and invalid signatures fail closed | identity signing and tamper tests |
| Replay a token across turn/session/workspace/owner | Context binding plus active-principal lookup; terminal identities deactivate and resume rotates the token ID | cross-context, expiry, deactivate, and resume tests |
| Use the owner's credential to gain owner authority | Credential selection receives the verified owner only as internal scope; the machine remains actor and model-controlled principal selectors cannot replace it | connector/provider scope and broker tests |
| Invoke policy, hooks, credentials, or tools without an identity | Identity verification is the first broker boundary; missing or invalid identity returns a stable refusal before downstream side effects | missing-identity and before-policy side-effect tests |
| Let a child agent inherit excessive authority | Each child has a signed child principal, explicit parent principal, and the existing delegable-tool subset | subagent identity and orchestration tests |
| Approve after the original bearer expires | Approval storage retains immutable public proposal attribution and hash, not bearer material; execution re-governs under current human authorization and gates | delayed approval and proposal-integrity tests |
| Exfiltrate bearer or issuer secrets through API/events | Redacted identity DTOs expose public attribution only; secret scanning rejects bearer/signature material | approval, dashboard, event, and redaction tests |
| Concurrent first-use key creation | Atomic storage creation produces one active workspace issuer key | issuer concurrency test |

Stable refusal codes include `machine_identity_missing`,
`machine_identity_malformed`, `machine_identity_unknown_key`,
`machine_identity_invalid_signature`, `machine_identity_workspace_mismatch`,
`machine_identity_wrong_audience`, `machine_identity_delegation_mismatch`,
`machine_identity_session_mismatch`, `machine_identity_turn_mismatch`,
`machine_identity_expired`, `machine_identity_principal_mismatch`, and
`machine_identity_inactive_principal`.

## Rotation, recovery, and delayed work

A suspended turn retains public proposal identity metadata but not its bearer.
Resume rotates the token while preserving the machine subject and principal.
Terminal completion deactivates the principal. If verification cannot establish
the active stored principal or key, the action is refused; there is no owner or
host fallback. Workspace issuer recovery is an operator recovery action, not an
agent capability, and invalidates attestations that cannot verify under the
active key.

## Residual risk

A fully compromised host process can read decrypted secrets in memory, replace
trusted code, or operate as the human outside this boundary. The embedded issuer
does not provide a hardware root of trust, remote attestation, or protection from
an owner-authorized malicious binary. ADD-03 limits confused-deputy and privilege
mirroring inside the Raiker broker; it does not claim to defend a lost operating
system or owner account. Key hardware binding remains ADD-14, and full causal
transaction lineage remains ADD-04.
