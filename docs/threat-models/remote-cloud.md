# Threat Model — Remote / Cloud Execution (SSH and Daytona)

> Status marker: runtime_enablement_candidate — strict non-allow blocking,
> role revoke governed, capability gate per action. Remote and cloud command
> execution have real foreground executors behind an owner-configured,
> owner-selected profile, and are relayed by an approval.

**Corrected 2026-10-20.** This document described both capabilities as
deliberately fail-closed with no executor. That stopped being true on
2026-08-22: both are members of `REAL_EXECUTOR_CAPABILITIES` and of
`EXECUTABLE_ON_APPROVAL` (`raiker/approvals/execution.py`).

| Capability | Executor | What it runs |
|---|---|---|
| `remote_execution_cap` | `RemoteExecutionExecutor` (`raiker/runtime/executors/tier5_network.py`) | One OpenSSH command on the owner's configured host |
| `cloud_execution_cap` | `CloudExecutionExecutor` (same file) | One `daytona exec` in the owner's existing Daytona sandbox |

The historical Phase-3/4 gate name `remote_execution` remains declared only so
an old configuration is refused by name; it has no executor. Hosted and
private-network *model* calls are a separate pair of capabilities — see
[`hosted-models.md`](hosted-models.md).

## Boundaries enforced (fail-closed)

| Control | Mechanism |
|---|---|
| Owner profile, owner-selected | The profile comes from the action's `profile_id` or the owner's selected execution environment, loaded by `(profile_id, owner_principal_id)`. A missing, disabled or wrong-type profile is `execution_profile_unavailable`; an unreadable one `invalid_execution_profile`. A profile record alone runs nothing — the gate, decision mode and approval still apply. |
| No fallback | A refused remote or cloud command never falls back to running on this machine. |
| Destination from the profile, not the action | The SSH host and user, and the Daytona sandbox id, come from the saved profile and are shape-checked; the action supplies only the command. |
| Pinned host key | SSH runs with `BatchMode=yes` and `StrictHostKeyChecking=yes`; saving an SSH profile checks the supplied host public key against its SHA-256 fingerprint (`ssh_host_key_fingerprint_mismatch`). |
| Credentials by reference | The SSH identity file and the Daytona API key are named by environment variable in the profile and read at execution time; they are never action arguments, never stored in events and, for Daytona, passed only in the child's environment. A missing reference is `ssh_profile_not_ready` / `daytona_profile_not_ready`. |
| Bounded execution | Timeout clamped to 1–300 s, output capped at 200 kB, and the runner's program allowlist is exactly `ssh` or `daytona`. |
| Cost ceiling (Daytona) | Each run reserves its estimated cost against the profile's `max_cost` in an append-only ledger before launch (`cloud_execution_budget_exceeded`); provider actuals reconcile reservations when an adapter reports them, and an unavailable billing adapter is explicit (`daytona_spend_api_unavailable`) and keeps the estimate. |
| Metadata-only results | Artifacts carry the profile id, exit code, byte counts and truncation — never command output, credentials or destinations. |
| Approval relay | Both are relayed once by an approval and re-governed at execution time against their own gate and `approval_execution_relay`. AI principals cannot enable either gate. |

The governed command service's remote backend
(`raiker/execution/commands/backends/remote.py`) adds an exact length-prefixed
envelope (`remote_envelope.py`) and a fixed supervisor path
(`remote_supervisor.py`) for the same SSH and Daytona targets.

## Residual risks & open work

- **Supervisor lifecycle and live proof.** Installing and upgrading the remote
  supervisor, and live proof against a real remote host, remain open —
  [BUG-194](../plans/TO_BE_FIXED.md). Selecting a profile with no installed
  supervisor fails closed.
- The remote host itself is the owner's trust decision: a command that reaches
  it can do whatever that account can do there.
- A leaked environment variable leaks the credential it names.
- Other remote or cloud provider types have no executor and fail closed.

## Activation requirements

Default gate state follows the per-principal rule in
[`RUNTIME_EXECUTORS_SPEC.md`](../architecture/RUNTIME_EXECUTORS_SPEC.md):
enabling requires a HUMAN `runtime_gate_manager`, the registered executor, a
`threat_model_acks` row referencing this document and a human confirmation
token (tier 5, `raiker/runtime/authority/activation.py`).
