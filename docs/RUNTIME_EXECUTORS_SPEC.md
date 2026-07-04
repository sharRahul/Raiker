# Runtime Executors & Capability Activation

> Status banner (kept for the truthfulness validator):
> runtime_enablement_candidate — strict non-allow blocking, role revoke governed,
> capability gate per action.

This document describes how a capability gate becomes flippable, how execution is
wired, and the honest per-capability status. It is the canonical reference for the
executor/activation model added on top of `RuntimeAuthority`.

## Model

1. **Gate state** (`capability_gate_state`, default `disabled`) — what the owner /
   `runtime_gate_manager` has turned on. AI principals can never flip a gate.
2. **Activation requirement** (`raiker/runtime/authority/activation.py`) — a gate can
   only transition to an enabled state when its `ActivationRequirement` is satisfied:
   acting principal is HUMAN, the required runtime mode is active, a **real executor is
   registered**, any required threat-model ack exists, and (for sensitive tiers) a
   human confirmation token is supplied.
3. **Executor registry** (`raiker/runtime/executors/registry.py`) — maps a capability
   to an `Executor`. `RuntimeAuthority.route_action()` executes the registered executor
   **only** on an `allow` decision; otherwise it returns the gate/policy reason and runs
   nothing. If no executor is registered it fails closed with
   `execution_unavailable:no_executor`.

### Single source of truth for "is there a real executor?"

`has_executor(capability, registry)` queries the **live registry** — there is no
static allowlist. The default registry is built by
`build_default_executor_registry()` and contains exactly
`REAL_EXECUTOR_CAPABILITIES`. A capability absent from that set:

- cannot be activated (`activation_blocked:no_executor`), and
- if somehow reached at execution time, fails closed.

This is enforced by `scripts/validate_runtime_enablement_readiness.py` (checks 13-14):
no static `_SATISFIED_CAPS`, `has_executor` must be registry-backed, and deferred
sensitive capabilities may not have a default executor.

## No silent runtime

A capability without a genuine integration **must fail closed**, never fabricate
success. Stub executors return `not_implemented:<capability>` (see
`raiker/runtime/executors/base.py::not_implemented`). Reporting "operation completed"
for an action that did nothing — especially for finance/medical/security domains — is
prohibited and guarded by tests (`tests/test_executor_default_registry.py`).

## Per-capability status

### Real executors — governed-flippable (`REAL_EXECUTOR_CAPABILITIES`)

| Capability | Tier | What it does |
|---|---|---|
| `approval_execution_relay` | 1 | Executes an approved file-write proposal. |
| `file_write_execution` | 1 | Writes a file in the workspace (path-safe). |
| `patch_apply_execution` | 1 | Writes new file content for an approved change. |
| `memory_write_execution` | 1 | Durable governed memory write. |
| `memory_forget_execution` | 1 | Durable memory forget. |
| `shell_execution` | 2 | Runs an allowlisted command in the sandbox. |
| `process_execution` | 2 | Sandboxed subprocess. |
| `web_fetch` | 2 | Fetch over the egress allowlist. |
| `network_execution` | 2 | Network call over the egress allowlist. |
| `graph_indexing_runtime` | 3 | Builds the local code graph index. |
| `semantic_memory_runtime` | 3 | Local semantic memory search. |
| `subagents` | 4 | Bounded, governed, in-process read-only subagent (no model/process/network). |
| `multi_agent_teams` | 4 | Up to 5 bounded subagents in sequence; aggregates metadata-only outcomes. |
| `external_channel_runtime` | 5 | Bounded outbound webhook delivery (owner egress allowlist); metadata-only events. |
| `channel_approval_relay` | 5 | Metadata-only **pending** approval relay for a paired channel (never resolves). |
| `container_execution_cap` | 5 | Local Docker run: owner image allowlist, no network, no host mounts, dropped caps, read-only, resource bounds. |
| `scheduled_routines` | 5 | Local on-demand routine runner (no daemon); runs bounded read-only subagent payloads when due. |
| `hosted_model_runtime` | 5 | Owner-allowlisted HTTPS model endpoint: gate-derived provider policy on the chat path + metadata-only connectivity probe (`RAIKER_MODEL_EGRESS_ALLOWLIST`, empty = fail closed). |
| `private_network_model_runtime` | 5 | Owner-allowlisted home-lab model endpoint (private network); same gate-derived policy + egress allowlist. |
| `plugin_install` | 4 | Local manifest validation + install-record creation only; verifies checksum/signature presence marker and safe read-only permissions, never runs plugin code. |

Tier 2 capabilities additionally require a threat-model ack and a human confirmation
token to enable (`--confirm <token>` / API `confirmation_token`).

### Fail-closed — not implemented (cannot be flipped to a working state)

These have an `ActivationRequirement` but **no real executor**. Activation is blocked;
execution (if forced) fails closed. Each needs its own implementation task (real
integration + threat model + tests) before joining `REAL_EXECUTOR_CAPABILITIES`:

- **Tier 3 (partial):** `vector_embedding_runtime`, `model_provider_runtime`
- **Tier 4:** `plugin_execution_cap`
- **Tier 5:** `remote_execution_cap`, `cloud_execution_cap`
  (Phase 4 promotions tracked in `docs/IMPLEMENTATION_STATUS.md`; each leaves
  this list only with a real integration + threat model + tests. Promoted so
  far: `subagents` + `multi_agent_teams` — `docs/threat-models/subagents.md`;
  `external_channel_runtime` + `channel_approval_relay` —
  `docs/threat-models/channels.md`; `container_execution_cap` —
  `docs/threat-models/container.md`; `scheduled_routines` —
  `docs/threat-models/scheduled-routines.md`; `hosted_model_runtime` +
  `private_network_model_runtime` — `docs/threat-models/hosted-models.md`;
  `plugin_install` — `docs/threat-models/plugins.md`.
  Remote/cloud command execution stays fail-closed by design — see
  `docs/threat-models/remote-cloud.md`.)
- **Tier 6 (sensitive domains):** `email_runtime`, `calendar_runtime`,
  `reminder_runtime`, `finance_runtime`, `investment_runtime`, `medical_runtime`,
  `pregnancy_baby_runtime`, `cctv_runtime`, `home_security_runtime`,
  `hardware_operator_runtime`

### Governance capabilities

`admin_mutation`, `policy_mutation`, `role_mutation`, `audit_export` have no separate
executor; they are governed mutations handled through the authority path.

## How a UI flips a gate (end to end)

1. `GET /api/capability-gates` → each gate's state, `allowed_transitions`, and
   `can_current_principal_change`.
2. (If needed) `POST /api/runtime-mode/activate` → `local_single_user_runtime`.
3. (Sensitive tiers) record a threat-model ack; supply `confirmation_token`.
4. `POST /api/capability-gates/{cap}/set` → `enabled_runtime`. Real-executor caps
   succeed; fail-closed caps return `activation_blocked:no_executor`.
5. Actions then route through `route_action`; the registered executor runs and emits a
   redacted `action_executed` / `action_failed` event.

## Adding a new real executor

1. Implement the executor (validate inputs, fail closed on error, redact events).
2. Register it in `build_default_executor_registry` and add the capability to
   `REAL_EXECUTOR_CAPABILITIES`.
3. Add policy rules / storage / events as needed; record the threat-model ack doc.
4. Add acceptance tests (executes-when-governed, fails-closed-when-disabled) and update
   this file plus `docs/IMPLEMENTATION_STATUS.md`.
5. Update the validator's `must_not_have_default_executor` set if the capability is
   leaving the sensitive list (only after a real integration + threat model).
