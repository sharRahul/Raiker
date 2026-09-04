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

   > **Per-principal fail-closed (web dashboard).** The `enabled_runtime` default above
   > is the *static/global* posture — it is what the single-user CLI runtime (a
   > principal with no account row) sees. The web dashboard runs under **per-principal
   > controls**: when the acting principal has an account, every gate reads as
   > `disabled` (`source: principal_fail_closed`) until that owner explicitly turns it
   > on for their own workspace. Nothing is auto-enabled per account. This is why a
   > freshly built `raiker-web` workspace reports **all** gates `disabled` even for
   > integrated capabilities — by design, not a regression. See
   > `RuntimeAuthority.get_effective_capability_gate`.
2. **Activation requirement** (`raiker/runtime/authority/activation.py`) — a gate can
   only transition to an enabled state when its `ActivationRequirement` is satisfied:
   acting principal is HUMAN, the required runtime mode is active, a **real executor is
   registered**, any required threat-model ack exists, and (for sensitive tiers) a
   human confirmation token is supplied. The runtime-enablement modes are
   `local_single_user_runtime` and `multi_user_local_runtime` (see
   `_RUNTIME_ENABLEMENT_MODES`); the default **Development preview**
   (`development_preview`) is *not* one, so while it is active the dashboard does not
   even offer the `enabled_runtime` transition. Activate a runtime mode under
   **Settings → Runtime mode** first.
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

This table covers all 46 members of `REAL_EXECUTOR_CAPABILITIES`
(`raiker/runtime/executors/__init__.py`). A capability that is in that set and
not in this table is a documentation defect, not a hidden feature.


| Capability | Tier | What it does |
|---|---|---|
| `approval_execution_relay` | 1 | Turns a recorded human approval into a real execution, re-governing the target at execution time. Reached from the Approvals API for the twelve capabilities in `EXECUTABLE_ON_APPROVAL` (`raiker/approvals/execution.py`) — file mutations and patches, bounded local `shell`, the git write and push path, a GitHub write, durable memory writes and forgets, the two local planning rows, and owner-selected SSH and Daytona commands; disabling this gate returns those approvals to metadata-only. |
| `file_write_execution` | 1 | Writes a file in the workspace. Path-safe **and** refuses the `.raiker/` and `.git/` trees; the pre-image is checkpointed first. |
| `patch_apply_execution` | 1 | Writes new file content for an approved change, under the same path rules. |
| `git_write_execution` | 1 | Creates a branch or records a commit in the workspace repository (B11). Re-derives its own proposal before mutating, so a repository that moved since the approval fails closed with a named reason. Stages exactly the paths the owner reviewed — never `--all` — so `.raiker/` and `.git/` can never be swept into a commit, and disables the repository's own hooks for the invocation. |
| `memory_write_execution` | 1 | Durable governed memory write. |
| `memory_forget_execution` | 1 | Durable memory forget. |
| `shell_execution` | 2 | Runs an allowlisted command in the sandbox. |
| `process_execution` | 2 | Sandboxed subprocess through the same `CommandService` lifecycle `shell_execution` uses. An approved `process` action is **not** relayed — it records the decision only. |
| `web_fetch` | 2 | Fetch one page under the owner **blocklist** (`RAIKER_WEB_EGRESS_BLACKLIST` plus the rules stored in Settings → Web access) and a non-optional public-address guard: HTTPS only, no credential in the URL, every resolved address public, re-checked on each redirect and pinned. |
| `telemetry_export` | 2 | Delivers governed events to an owner-named OpenTelemetry collector as OTLP log records (compatibility backlog #18). Its own gate rather than a corner of `audit_export`, because that writes a file beside the log and this leaves the machine. **Metadata by default** — the identifiers and the type, every one a column on `events_index`, and never the summary, which names the object an action acted on. Redacted content is one explicit per-destination opt-in, through the same `redact_event_payload` the screen passes. The credential is an environment-variable *name*, read at send time and never stored; a named-but-absent variable fails closed. The cursor advances only on a delivery that landed, and is insertion order rather than the event id, so nothing is skipped or repeated inside one second. Inert until the owner names a destination. |
| `graph_indexing_runtime` | 3 | Builds the local code graph index. |
| `semantic_memory_runtime` | 3 | Local semantic memory search. |
| `vector_embedding_runtime` | 3 | Local deterministic embedding (hashing trick; no model download / no network): `embed` persists a `vector_records` row, `list` counts, `search` ranks stored local-model vectors by cosine (returns ids+scores). Metadata-only artifacts; source text/query never emitted. |
| `model_provider_runtime` | 3 | Provider-backed **semantic** embedding via an LLM provider; layered gating (owner egress allowlist + hosted/private gate state + API-key-from-env); persists a `vector_records` row (`embedding_model=<provider>:<model>`). Metadata-only artifacts; text/credentials never emitted. `embed` only. |
| `subagents` | 4 | Bounded, governed, in-process read-only subagent (no model/process/network). The gate is what the `spawn_subagent` tool answers to: it decides whether the owner allows delegation at all, while what a subagent may touch once delegated is decided one step at a time by the broker. |
| `multi_agent_teams` | 4 | Up to 5 bounded subagents in sequence; aggregates metadata-only outcomes. |
| `external_channel_runtime` | 5 | Bounded outbound webhook delivery over the owner connector egress allowlist, signed with `X-Raiker-Signature` (HMAC-SHA256 over the exact bytes) when a secret is configured and reported as unsigned on the Channels tab when not. Inbound delivery is recorded, rate-limited to 60 messages per sender per minute, and quarantined: a channel message is untrusted content with a named sender who is not the owner, and never raises a turn's authority. Events stay metadata-only. |
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
| `plugin_install` | 4 | Reached by `RuntimeControlService.install_plugin`, which the terminal's `/plugin-plan <manifest> --install` calls. Local manifest validation + install-record creation only; verifies checksum, safe read-only permissions, dependency pins + owner allowlist (`RAIKER_PLUGIN_DEPENDENCY_ALLOWLIST`), and manifest signature (HMAC-SHA256 vs `RAIKER_PLUGIN_SIGNING_KEY` when set, else presence marker; plus asymmetric Ed25519 vs owner-trusted `RAIKER_PLUGIN_ED25519_PUBLIC_KEY` when set, fail-closed), never runs plugin code. |
| `plugin_execution_cap` | 4 | Installed-plugin brokered read-only tool invocation (`read_file`, `list_directory`, `glob`, `grep`) through ToolBroker/PolicyEngine; no plugin imports, scripts, process, network, or writes. |
| `plugin_revocation_cap` | 4 | Owner revocation off-switch: flips an installed plugin's record status to `revoked` so `plugin_execution_cap` fails closed for it; never deletes records, edits permissions, or runs plugin code. |
| `plugin_runtime_cap` | 4 | Bounded subprocess execution of an installed, owner-allowlisted plugin's entrypoint (`RAIKER_PLUGIN_RUNTIME_ALLOWLIST`, empty = fail closed); interpreter allowlist (`python3`/`python`/`node`), workspace-scoped script + optional per-plugin subpath scope (`RAIKER_PLUGIN_RUNTIME_SCOPES`), timeout + output caps, metadata-only artifacts. No in-process import, no network-namespace jail, no stdout/stderr leakage. |
| `plugin_sandboxed_runtime_cap` | 4 | Network-isolated variant of the above: runs the entrypoint inside an owner-allowlisted container (`RAIKER_PLUGIN_RUNTIME_IMAGE` ∈ `container_image_allowlist()`) with `--network none`, read-only rootfs, dropped caps, and only the single entrypoint file bind-mounted read-only. Same owner plugin allowlist + per-plugin scope; workspace is never mounted; metadata-only artifacts. |
| `checkpoint_restore_execution` | 1 | Rewinds only the files recorded in a checkpoint's capture manifest, recomputing the plan at execution time rather than trusting a caller-supplied file list, refusing any path outside the workspace, and capturing its own pre-image first so a restore is itself reversible. Reached by `POST /api/checkpoints/{id}/restore` and `/checkpoints restore <id> --confirm`, both raising an ordinary approval; a cross-principal restore is classified critical and takes the human-only lifecycle instead. **No model tool proposes a restore**, so an agent can never rewind the workspace on its own say-so. |
| `task_management_runtime` | 1 | Creates the owner-scoped task row an approved `create_task` describes. Local, reversible, relayed on approval. |
| `project_assignment_runtime` | 1 | Moves the active conversation into a project. Local, reversible, relayed on approval. |
| `git_push_execution` | 2 | Publishes a branch to an HTTPS GitHub remote. Its own gate, separate from `git_write_execution`, because a push is egress carrying repository content off the machine; requires the remote's host on `RAIKER_CONNECTOR_EGRESS_ALLOWLIST` and a credential lent for one command under an owner grant. Never forces, never deletes a branch. |
| `code_map_indexing` | 3 | Builds and refreshes the repository symbol index Build points at — a real parser for Python, bounded patterns for fifteen other languages, each file recording which extractor produced it. Deliberately **not** `graph_codemap_indexing`: this is a derived cache, that is the governed durable graph store. A scan that hits a bound reports `partial` and names the bound. |
| `language_intelligence` | 3 | Outlines a file, resolves an exact name to its declaration, and reports parse-level problems (GAP-BUILD B10). A sibling of `code_map_indexing` rather than part of it: the map **writes** a derived index of the machine, this writes nothing at all and every answer is a parse of a file `read_file` would already open. Diagnostics are parse-level, and a language with no parser here is reported as **not checked**, never as clean. |
| `mcp_builder_runtime` | 4 | Writes a reviewed, dependency-free local stdio MCP server from a fixed template into the workspace. Interpreter allowlist, workspace-relative path, no network. |
| `mcp_connector_runtime` | 4 | One bounded MCP session over `stdio` (interpreter allowlist, workspace-relative argument rule) or `http` (an owner-added remote endpoint with an optional owner token — monitored rather than allowlist-blocked, because adding the URL is the authorisation). Tool output returns as redacted metadata; the raw content and any owner token never enter artifacts or the audit event. A projected MCP tool is offered to the model only while the gate is enabled **and** the decision mode permits it. |
| `email_runtime` | 6 | Local governed email store. No outbound send. |
| `calendar_runtime` | 6 | Local governed calendar store. |
| `reminder_runtime` | 6 | Local governed reminder store. |
| `plugin_sandbox_image_pull_cap` | 4 | Pull-only acquisition for a sandbox image. Requires an exact image in `RAIKER_CONTAINER_IMAGE_ALLOWLIST` and its registry in `RAIKER_PLUGIN_IMAGE_REGISTRY_ALLOWLIST`; invokes only `docker pull <image>`, bounds/redacts output, and never builds or executes an image. Docker daemon egress remains an operator-controlled boundary. |
| `run_command` standing grant | 4 | Executes only an exact active session/principal grant inside `RAIKER_COMMAND_SANDBOX_IMAGE`, which must also be owner-allowlisted. Docker uses `--network none`, dropped capabilities, `no-new-privileges`, bounded resources, and a workspace-only bind mount. Missing image/runtime configuration fails closed. |

Tier 2 capabilities additionally require a threat-model ack and a human confirmation
token to enable (`--confirm <token>` / API `confirmation_token`).

### Fail-closed — not implemented (cannot be flipped to a working state)

These have an `ActivationRequirement` but **no real executor**. Activation is blocked;
execution (if forced) fails closed. Each needs its own implementation task (real
integration + threat model + tests) before joining `REAL_EXECUTOR_CAPABILITIES`:

*Corrected 2026-08-22: `remote_execution_cap` and `cloud_execution_cap` are no
longer on this list. Both have real foreground executors — an exact remote
envelope, a pinned host key, a fixed supervisor path, a cumulative cost budget
and no host fallback — and both are relayed by an approval. What is still open
is the supervisor install/upgrade lifecycle and live remote proof, tracked in
[`plans/TO_BE_FIXED.md`](../plans/TO_BE_FIXED.md) → BUG-194. Selecting a profile
that has no installed supervisor still fails closed.*

- **Tier 5 promotions**
  (tracked in `docs/architecture/IMPLEMENTATION_STATUS.md`; each leaves
  this list only with a real integration + threat model + tests. Promoted so
  far: `remote_execution_cap` + `cloud_execution_cap` —
  `docs/threat-models/remote-cloud.md`; `subagents` + `multi_agent_teams` — `docs/threat-models/subagents.md`;
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
  Every remote or cloud command still runs only through an owner-configured,
  owner-selected profile — see `docs/threat-models/remote-cloud.md`.)
- **Tier 6 (sensitive domains):** `finance_runtime`, `investment_runtime`,
  `medical_runtime`, `pregnancy_baby_runtime`, `cctv_runtime`,
  `home_security_runtime`, `hardware_operator_runtime`

### Governance capabilities

`admin_mutation`, `policy_mutation` and `role_mutation` have no separate executor;
they are governed mutations handled through the authority path.

`audit_export` is worth naming separately: it **does** have an executor and a
route now (`AuditExportExecutor`, `POST /api/audit/export`), so it appears in the
real-executor table above. `raiker/events/export.py` produces the redacted export
manifest the executor writes.

Its sibling `telemetry_export` sends the same governed record over OTLP to an
owner-named collector instead of writing a file beside the log — see
[the telemetry-export threat model](../threat-models/telemetry-export.md).

### Gate names that are not executor capabilities

Ten members of `ALL_CAPABILITIES` (`raiker/phase_gates.py`) are not execution
capabilities at all and never appear in the tables above. They are listed here so
the set is complete:

| Gate | What it is |
|---|---|
| `desktop_ui`, `web_ui`, `dashboard` | Read-only interface contracts, `contract_ready` by default |
| `graph_codemap_indexing`, `graph_codemap_planning` | The Phase-3 **durable governed graph store** — nodes and edges with provenance, approval previews, rollback plans. Still a dry-run planner (`raiker/graph/planner.py`); the derived repository index is the separate `code_map_indexing` |
| `semantic_memory_writes`, `semantic_memory_review_queue` | The Phase-3 durable semantic/vector write path, disabled outright (`raiker/memory/semantic.py`) |
| `plugin_execution`, `remote_execution`, `container_execution` | Historical Phase-3/4 gate names superseded by the `*_cap` capabilities in the tables above; they remain declared so an old configuration is refused by name rather than silently ignored |
| `external_channels` | The historical Phase-3 channel readiness gate. The live channel capabilities are `external_channel_runtime` and `channel_approval_relay` |

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

## What each gate actually decides

A capability with a real executor has a gate, and every gate is rendered as a
switch on the Capabilities page. **Having a gate is not the same as that gate
deciding anything**, and until 2026-08-24 the difference was invisible: fifteen
switches an owner could hold on or off changed nothing at all
([FIXED-280](../plans/FIXED_ITEMS.md)).

[`raiker/runtime/authority/entry_paths.py`](../../raiker/runtime/authority/entry_paths.py)
records the answer for all forty-five, and it is the source the DTO and the web
UI read:

| Value | Meaning | Example |
|---|---|---|
| `own_gate` | This gate decides whether the capability runs. The switch means what it says | `shell_execution`, `web_fetch`, `subagents` |
| `governed_elsewhere` | The work happens and a **different named control** governs it. The row carries the sentence saying which | `scheduled_routines` — a scheduled task runs as one whole governed turn, so every action inside answers to its own gate |
| `no_path` | Nothing in the product reaches this executor. The gate is what will be there when something does | `reminder_runtime`, `channel_approval_relay` |

The dataclass requires a sentence for anything that is not `own_gate`, so a row
cannot be added that names the problem without answering it.

## When "nothing persisted" does not mean the same thing everywhere

Three resolutions exist, and the difference is owner-visible. They are named in
`CAPABILITY_UNSET_RESOLUTION`
([`admission.py`](../../raiker/runtime/authority/admission.py)) rather than repeated
at each call site, because the same empty gate table used to mean different
things in the path that enforced a capability and the surface that described it:

| Resolution | With nothing persisted | Used by |
|---|---|---|
| `off` (default) | Off. Nothing decided is not consent | Everything not named below |
| `shipped_default_unscoped` | An account is fail-closed; a caller with no account gets the shipped table — what `RuntimeAuthority.check_capability_gate` does, and the posture the **Model** section above documents | `code_map_indexing`, `language_intelligence`, `subagents` |
| `shipped_default` | Any caller gets the shipped table. An owner who turns it off writes a row, and that row wins | `web_fetch` (RAIKER-2021) |

Every path that reads a gate — enforcing or describing — calls
`capability_admission`, so the resolution is looked up once and the two cannot
disagree ([FIXED-279](../plans/FIXED_ITEMS.md)).

## Adding a new real executor

1. Implement the executor (validate inputs, fail closed on error, redact events).
2. Register it in `build_default_executor_registry` and add the capability to
   `REAL_EXECUTOR_CAPABILITIES`.
3. **Classify it in `entry_paths.py`** — how a governed action for it is
   constructed, and whether its own gate decides whether it runs. A capability
   with no classification fails
   `tests/test_governance_entry_paths.py::test_every_real_executor_capability_is_classified`,
   which is the step nobody took for `network_execution` before it was deleted.
4. Add policy rules / storage / events as needed; record the threat-model ack doc.
5. Add acceptance tests (executes-when-governed, fails-closed-when-disabled) and update
   this file plus `docs/architecture/IMPLEMENTATION_STATUS.md`.
6. Update the validator's `must_not_have_default_executor` set if the capability is
   leaving the sensitive list (only after a real integration + threat model).
