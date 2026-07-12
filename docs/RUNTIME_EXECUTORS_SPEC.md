# Runtime Executors & Capability Activation

> Status banner (kept for the truthfulness validator):
> runtime_enablement_candidate — strict non-allow blocking, role revoke governed,
> capability gate per action.

This document describes how a capability gate becomes flippable, how execution is
wired, and the honest per-capability status. It is the canonical reference for the
executor/activation model added on top of `RuntimeAuthority`.

## Model

1. **Gate state** (`capability_gate_state`) — what the owner / `runtime_gate_manager`
   has turned on. Default posture: **integrated capabilities (those in
   `REAL_EXECUTOR_CAPABILITIES`) default to `enabled_runtime`**; capabilities that are
   not integrated yet (no real executor) default to `disabled` and fail closed. AI
   principals can never flip a gate (enable or disable). An enabled gate does not by
   itself let an AI act — the decision mode (default `ask`), critical-risk human floor,
   PolicyEngine hard-denies, and executor-level env allowlists still apply.
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
| `vector_embedding_runtime` | 3 | Local deterministic embedding (hashing trick; no model download / no network): `embed` persists a `vector_records` row, `list` counts, `search` ranks stored local-model vectors by cosine (returns ids+scores). Metadata-only artifacts; source text/query never emitted. |
| `model_provider_runtime` | 3 | Provider-backed **semantic** embedding via an LLM provider; layered gating (owner egress allowlist + hosted/private gate state + API-key-from-env); persists a `vector_records` row (`embedding_model=<provider>:<model>`). Metadata-only artifacts; text/credentials never emitted. `embed` only. |
| `subagents` | 4 | Bounded, governed, in-process read-only subagent (no model/process/network). |
| `multi_agent_teams` | 4 | Up to 5 bounded subagents in sequence; aggregates metadata-only outcomes. |
| `external_channel_runtime` | 5 | Bounded outbound webhook delivery (owner egress allowlist); metadata-only events. |
| `channel_approval_relay` | 5 | Metadata-only **pending** approval relay for a paired channel (never resolves). |
| `container_execution_cap` | 5 | Local Docker run: owner image allowlist, no network, no host mounts, dropped caps, read-only, resource bounds. |
| `scheduled_routines` | 5 | Local on-demand routine runner (no daemon); runs bounded read-only subagent payloads when due. |
| `hosted_model_runtime` | 5 | Owner-allowlisted HTTPS model endpoint: gate-derived provider policy on the chat path + metadata-only connectivity probe (`RAIKER_MODEL_EGRESS_ALLOWLIST`, empty = fail closed). |
| `private_network_model_runtime` | 5 | Owner-allowlisted home-lab model endpoint (private network); same gate-derived policy + egress allowlist. |
| `advisor_model_runtime` | 5 | One governed advisor consult for local-model turns: default-ask decision mode withholds; the consult re-checks provider policy (hosted/private gate + owner egress allowlist + env-only key) per call. Metadata-only artifacts/events — question/answer text never emitted (lengths only). |
| `connector_github_runtime` | 5 | One governed GitHub issue/PR read (`github_read` tool). Default-ask decision mode withholds; owner credential is env-only (`RAIKER_GITHUB_TOKEN`), host must be on the owner connector egress allowlist (`RAIKER_CONNECTOR_EGRESS_ALLOWLIST`, empty = fail closed); request URL is built server-side from validated components (no model-supplied URL). Fetched content returned as untrusted data; metadata-only artifacts/events — the body text never emitted (repo/number/title/state/length only). Reference slice for Task 4 governed connectors. |
| `connector_gmail_runtime` | 5 | One governed Gmail message/thread read (`gmail_read` tool). Same governed pattern as `connector_github_runtime`: default-ask decision mode withholds; owner credential is env-only (`RAIKER_GMAIL_TOKEN`), host must be on the owner connector egress allowlist (`gmail.googleapis.com`, empty = fail closed); request URL is built server-side (`format=metadata`) from validated components (resource ∈ message/thread, URL-safe id). Fetched snippet+headers returned as untrusted data; metadata-only artifacts/events — the body never emitted (resource/message_id/subject/length only). Second read connector for Task 4. |
| `connector_gcal_runtime` | 5 | One governed Google Calendar event/calendar read (`gcal_read` tool). Same governed pattern: default-ask withholds; owner credential env-only (`RAIKER_GCAL_TOKEN`), host `www.googleapis.com` on the connector egress allowlist; request URL built server-side from validated, path-encoded components (resource ∈ event/calendar, calendar_id, event_id). Fetched summary returned as untrusted data; metadata-only artifacts/events (resource/calendar_id/event_id/title/length only). |
| `connector_slack_runtime` | 5 | One governed Slack channel info/history read (`slack_read` tool). Same governed pattern: default-ask withholds; owner credential env-only (`RAIKER_SLACK_TOKEN`), host `slack.com` on the connector egress allowlist; request URL built server-side against a fixed Web API method (`conversations.info`/`conversations.history`) from a validated channel id; a Slack `ok:false` body is treated as a bad response, never content. Fetched summary returned as untrusted data; metadata-only artifacts/events (resource/channel/title/length only). |
| `plugin_install` | 4 | Local manifest validation + install-record creation only; verifies checksum, safe read-only permissions, dependency pins + owner allowlist (`RAIKER_PLUGIN_DEPENDENCY_ALLOWLIST`), and manifest signature (HMAC-SHA256 vs `RAIKER_PLUGIN_SIGNING_KEY` when set, else presence marker; plus asymmetric Ed25519 vs owner-trusted `RAIKER_PLUGIN_ED25519_PUBLIC_KEY` when set, fail-closed), never runs plugin code. |
| `plugin_execution_cap` | 4 | Installed-plugin brokered read-only tool invocation (`read_file`, `list_directory`, `glob`, `grep`) through ToolBroker/PolicyEngine; no plugin imports, scripts, process, network, or writes. |
| `plugin_revocation_cap` | 4 | Owner revocation off-switch: flips an installed plugin's record status to `revoked` so `plugin_execution_cap` fails closed for it; never deletes records, edits permissions, or runs plugin code. |
| `plugin_runtime_cap` | 4 | Bounded subprocess execution of an installed, owner-allowlisted plugin's entrypoint (`RAIKER_PLUGIN_RUNTIME_ALLOWLIST`, empty = fail closed); interpreter allowlist (`python3`/`python`/`node`), workspace-scoped script + optional per-plugin subpath scope (`RAIKER_PLUGIN_RUNTIME_SCOPES`), timeout + output caps, metadata-only artifacts. No in-process import, no network-namespace jail, no stdout/stderr leakage. |
| `plugin_sandboxed_runtime_cap` | 4 | Network-isolated variant of the above: runs the entrypoint inside an owner-allowlisted container (`RAIKER_PLUGIN_RUNTIME_IMAGE` ∈ `container_image_allowlist()`) with `--network none`, read-only rootfs, dropped caps, and only the single entrypoint file bind-mounted read-only. Same owner plugin allowlist + per-plugin scope; workspace is never mounted; metadata-only artifacts. |

Tier 2 capabilities additionally require a threat-model ack and a human confirmation
token to enable (`--confirm <token>` / API `confirmation_token`).

### Fail-closed — not implemented (cannot be flipped to a working state)

These have an `ActivationRequirement` but **no real executor**. Activation is blocked;
execution (if forced) fails closed. Each needs its own implementation task (real
integration + threat model + tests) before joining `REAL_EXECUTOR_CAPABILITIES`:

- **Tier 5:** `remote_execution_cap`, `cloud_execution_cap`
  (Phase 4 promotions tracked in `docs/IMPLEMENTATION_STATUS.md`; each leaves
  this list only with a real integration + threat model + tests. Promoted so
  far: `subagents` + `multi_agent_teams` — `docs/threat-models/subagents.md`;
  `external_channel_runtime` + `channel_approval_relay` —
  `docs/threat-models/channels.md`; `container_execution_cap` —
  `docs/threat-models/container.md`; `scheduled_routines` —
  `docs/threat-models/scheduled-routines.md`; `hosted_model_runtime` +
  `private_network_model_runtime` — `docs/threat-models/hosted-models.md`;
  `advisor_model_runtime` — `docs/threat-models/advisor-model.md`;
  `connector_github_runtime` — `docs/threat-models/connectors-github.md`;
  `connector_gmail_runtime` — `docs/threat-models/connectors-gmail.md`;
  `connector_gcal_runtime` — `docs/threat-models/connectors-gcal.md`;
  `connector_slack_runtime` — `docs/threat-models/connectors-slack.md`;
  `plugin_install` — `docs/threat-models/plugins.md`;
  `plugin_execution_cap` — `docs/threat-models/plugin-execution.md`;
  `plugin_revocation_cap` — `docs/threat-models/plugin-revocation.md`;
  `plugin_runtime_cap` — `docs/threat-models/plugin-runtime.md`;
  `plugin_sandboxed_runtime_cap` — `docs/threat-models/plugin-sandboxed-runtime.md`.
  Remote/cloud command execution stays fail-closed by design — see
  `docs/threat-models/remote-cloud.md`.)
- **Tier 6 (sensitive domains):** `finance_runtime`, `investment_runtime`,
  `medical_runtime`, `pregnancy_baby_runtime`, `cctv_runtime`,
  `home_security_runtime`, `hardware_operator_runtime`

### Governance capabilities

`admin_mutation`, `policy_mutation`, `role_mutation`, `audit_export` have no separate
executor; they are governed mutations handled through the authority path.

## How a UI flips a gate (end to end)

1. `GET /api/capability-gates` → each gate's state, `allowed_transitions`, and
   `can_current_principal_change`.
2. (If needed) `POST /api/runtime-mode/activate` → `local_single_user_runtime`.
3. (Sensitive tiers) record a threat-model ack; supply `confirmation_token`.
4. `POST /api/capability-gates/{cap}/set` → `enabled_runtime` when a gate was
   explicitly disabled or persisted in a non-default state. Integrated real-executor
   caps may already be `enabled_runtime` by default; the explicit enable flow still
   applies for re-enabling or migrated state where activation requirements are met.
   Fail-closed caps return `activation_blocked:no_executor`.
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
