> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

# Security And Policy Blueprint

Raiker is an agent runtime. Security is not an optional feature; it is part of the execution path.

This document defines Phase 1 security behaviour and phase-scheduled policy boundaries. Phase scheduling controls build order only; the security behaviour for later phases must already be specified before implementation.

---

## Core Security Principle

No agent-controlled action may execute unless it has passed through:

```text
Client / CLI / Future UI / Automation / Agent
  -> Gateway
  -> Runtime Authority / Action Router
  -> Capability Gate
  -> PolicyEngine
  -> Risk Classifier
  -> Approval / Risk Acceptance where required
  -> ToolBroker or Governed Service Executor
  -> EventLog recording
  -> Checkpoint where needed
```

Clients, runtime modules, plugins, models, channels, and subagents must never execute tools directly.

The `RuntimeAuthority` (`raiker/runtime/authority/router.py`) enforces principal validity, domain scoping, AI role restrictions (no self-approval, no self-grant, no gate enablement), human-only role protections, risk level escalation, and risk acceptance validation.

Current backend truth: Approval resolution is metadata-only and does not execute approved actions; integrated executors are governed per action while deferred no-executor capabilities remain disabled/fail-closed. Runtime readiness: runtime_enablement_candidate — controlled_runtime_mode_activation_implemented. Enforcement: strict non-allow blocking, role revoke governed, capability gate per action, and risk acceptance enforced before mutation. Human runtime_gate_manager can activate local_single_user_runtime and enable admin_mutation/role_mutation; AI cannot activate runtime modes or capability gates. Owner bootstrap flow implemented via `/bootstrap-owner` with recovery support. Local single-user production hardening implemented: first-run owner bootstrap, persisted owner principal, acting-principal resolution, runtime-gate-manager authorization, recovery/break-glass flow. Production-ready local single-user runtime: ready. Current production readiness applies only to local single-user runtime.

### AI-Executable Roles

Four AI roles are defined in `raiker/runtime/authority/models.py`:

| Role | Auto-allowed | Requires approval/risk acceptance | Denied |
|------|-------------|-----------------------------------|--------|
| **assistant** | read, search, summarise, draft, plan, recommend, prepare actions, create reports, reminders | send email, delete email, move money, buy/sell stock, share records, medical decisions, grant permissions, enable runtime gates | - |
| **automation** | scheduled summaries, recurring reports, alerts, reminders, monitoring | Must be scoped by task; cannot self-expand scope | buy/sell stock, move money, change portfolio settings |
| **operator** | check runtime status, check backups, diagnostics, maintenance recommendations | delete backups, change CCTV settings, disable monitoring, restart service | enable runtime gates, change security policy, remote execution, delete CCTV footage |
| **developer** | read workspace, inspect git diff, review findings, plans, proposals | write_file, edit_file, apply_patch, run tests, shell commands, memory mutations | approve own action, merge PR, change policy, grant roles, enable runtime gates, install/execute plugins |

AI role rules:
- No AI principal may self-approve its own actions.
- No AI principal may self-grant roles or permissions.
- No AI principal may enable runtime capability gates.
- Human-only roles are enforced at the authority level and cannot be assigned to AI principals.

### Human-Only Roles

`owner`, `admin`, `approver`, `security_admin`, `finance_approver`, `medical_decision_maker`, `runtime_gate_manager` cannot be assigned to AI principals. These roles always require human interaction for any action they take.

### Risk Acceptance Rules

Users may explicitly accept risk for high-risk actions. Rules:
- Risk acceptance records require: `accepted_by`, `accepted_for_principal_id`, `action_id`, `action_type`, `domain_scope`, `risk_level`, `risk_summary`, `data_involved`, `expected_effect`, `one_time_or_reusable`, `expires_at`.
- AI principals cannot use risk acceptance to self-approve actions.
- Critical-risk actions always require human confirmation regardless of risk acceptance state.
- Risk acceptance may be one-time or reusable (scoped by principal + domain + action type).
- Expired risk acceptance records are treated as non-existent.

### Admin Mutation Governance

All admin CLI mutation commands (`/user create`, `/user deactivate`, `/role create`, `/role grant`, `/role revoke`) route through `_govern_admin_mutation` which delegates to `RuntimeAuthority` before mutating. Strict non-allow blocking is enforced: all non-allow decisions block mutation.

---

## Threats Raiker Must Consider

Raiker must be designed around prompt injection, indirect prompt injection, data exfiltration, unsafe command execution, path traversal, hidden instruction leakage, memory poisoning, dependency supply-chain risk, plugin abuse, excessive agency, unbounded cost/resource usage, network egress abuse, user approval spoofing, channel abuse, and event log tampering.

Phase 1 does not solve every threat completely, but it must establish boundaries that every phase preserves.

---

## Phase 1 Trust Boundaries

```text
User input: untrusted
Files read from workspace: untrusted content
Model output: untrusted proposal
ToolAction: untrusted until policy-reviewed
PolicyDecision: trusted only if produced by policy engine
ToolResult: trusted as execution result, but output content may be untrusted
Event log: append-only audit record
```

---

## Policy Decisions

Every `ToolAction` receives one decision:

| Decision | Meaning | Implemented |
|---|---|---|
| `allow` | Broker may execute immediately. | Phase 1 |
| `deny` | Broker must not execute. Return denied result. | Phase 1 |
| `needs_approval` | Broker must pause and request user approval. | Phase 1 |
| `defer` | Put action into deferred queue. | Phase 2 (scheduled) |
| `allow_once` | Allow one exact action ID only. | Phase 2 (scheduled) |
| `allow_for_session` | Allow matching action pattern for current session. | Phase 2 (scheduled) |
| `allow_for_project` | Allow matching action pattern for current project config. | Phase 2 (scheduled) |
| `allow_managed` | Allow by administrator/managed policy. | Phase 5 (scheduled) |

Phase-scheduled decisions such as `defer`, `allow_once`, `allow_for_session`, `allow_for_project`, and `allow_managed` are defined in `docs/TOOLS_AND_PERMISSIONS_SPEC.md`.

### Policy resolution and authority chain

Policy decisions are produced within the Runtime Authority chain:

```text
Action -> RuntimeAuthority (principal, role, scope, risk, capability gates)
       -> PolicyEngine (allow/deny/needs_approval)
       -> Approval or Risk Acceptance where required
       -> GovernedAction record with full decision provenance
```

Approval resolution is metadata-only: `/approve` and `/deny` update one pending approval record and do not execute the approved action. Strict non-allow blocking is enforced: all non-allow decisions (`deny`, `needs_approval`, `needs_risk_acceptance`, `needs_human_confirmation`, `disabled_by_capability_gate`) block mutation. Each governed action checks its relevant capability gate before execution.

---

## Default Phase 1 Policy Matrix

| Action | Default decision | Notes |
|---|---:|---|
| Simple chat | allow | No tool execution. |
| Read file inside workspace | allow | Text files only unless explicitly handled. |
| List directory inside workspace | allow | Stable sorted output. |
| Glob inside workspace | allow | Bounded results. |
| Grep inside workspace | allow | Bounded results; text files only. |
| Read outside workspace | deny | Prevent path traversal. |
| Write file | deny | Phase 2 implements approval-gated file writes. |
| Delete file | deny | Phase 2 implements tightly scoped approval flow. |
| Local command execution | needs_approval | Never auto-run in Phase 1. |
| Network request | deny | Phase 3 implements egress-policy-gated web access. |
| Memory write | deny/defer | Phase 1 creates candidates; Phase 2 writes governed memory. |
| Plugin execution | deny | Phase 3 implements plugin lifecycle and permission diff. |
| Remote execution | deny | Phase 4/5 implement execution profiles. |
| Channel approval relay | deny | Disabled by default in all channels unless explicitly configured. |

---

## Path Safety Requirements

All filesystem tools must:

1. resolve requested path to an absolute path;
2. resolve workspace root to an absolute path;
3. verify requested path is inside workspace root;
4. reject path traversal attempts;
5. reject symlink escapes unless explicitly allowed by a phase-scheduled policy rule;
6. return structured errors instead of raw tracebacks.

---

## Command Safety Requirements

Phase 1 local command behaviour:

- command actions are proposed, logged, and policy-reviewed;
- policy returns `needs_approval`;
- command is not executed unless an explicit approval object exists;
- CLI MVP may stop at approval-required response;
- no silent background execution is allowed.

Phase 2 adds scoped allowlists, sandboxing rules, timeout enforcement, environment restrictions, command previews, and kill/cancel controls according to `docs/TOOLS_AND_PERMISSIONS_SPEC.md`.

---

## Event Logging Security Requirements

Every security-relevant decision must be logged:

- action proposed;
- policy decision;
- approval requested;
- approval received or denied;
- tool started;
- tool completed;
- tool failed;
- denied action;
- error;
- checkpoint.

Event log records must not include secrets unless explicitly redacted. Raiker does not currently claim tamper-proof storage, immutable storage, or cryptographic non-repudiation for the local audit log.

---

## Secret Handling Requirements

Phase 1 must not require secrets.

Phase-scheduled tasks that introduce secret references must:

- never commit secrets;
- load from environment or OS secret store;
- redact values in logs;
- store only references, not secret values;
- use fake secrets in tests.

---

## Memory Governance Requirements

Phase 1 must not write long-term memory automatically. It may produce memory candidates.

```json
{
  "candidate_id": "memcand_01H...",
  "source_event_id": "evt_01H...",
  "text": "User prefers local-first models.",
  "sensitivity": "normal",
  "confidence": 0.8,
  "decision": "deferred"
}
```

Phase-scheduled memory writes must include provenance, confidence, sensitivity, retention, approval state, deletion support, and poisoning controls.

---

## Approval Requirements

Approval prompts must include action ID, tool name, exact arguments, risk level, policy reasons, expected effect, and whether the action changes files, runs a command, uses network, exports data, persists memory, or may cost money.

Approvals must be bound to action ID. A user approving one action must not approve a different action accidentally.

Pending approval records are also bound to a stored action payload hash. If the stored tool payload is tampered with before resolution, resolution fails closed.

---

## Security Tests Required In Phase 1

Minimum tests:

- outside-workspace file read is denied;
- path traversal is denied;
- local command action requires approval;
- denied action is not executed;
- policy decision is logged;
- tool output failure is logged;
- event log does not contain raw secret-like test values;
- invalid tool name fails safely;
- action without policy decision cannot execute.

---

## Security Non-Deviation Rules

Builder agents must not:

- call command execution APIs outside the approved command tool implementation;
- read files directly from runtime code as an agent action;
- add network libraries for Phase 1;
- add plugin execution in Phase 1;
- add durable memory writes in Phase 1;
- bypass approval for local commands;
- suppress security events;
- hide failures behind vague messages.

## Async model-provider runtime update

Raiker now owns a true asynchronous model-provider runtime. `httpx>=0.27` is the only runtime HTTP dependency added for model transport; the OpenAI SDK, Pydantic, requests, and aiohttp are intentionally not used. Provider contracts remain Raiker dataclasses, and model outputs/tool calls remain untrusted proposals that must pass validation, policy, and approval.

Provider status labels are used honestly: `implemented_verified` for mocked/offline-tested adapter behavior, `implemented_unverified` for real servers not contacted in CI, `profile_defined_only` for profile metadata, `policy_gated_disabled` for hosted/egress providers, `test_only` for deterministic test provider, and `specified_not_implemented` for future work.

Provider matrix: llama.cpp server is Raiker's native local-first OpenAI-compatible backend; Ollama and LM Studio are local OpenAI-compatible profiles; vLLM is a home-lab/server OpenAI-compatible profile requiring network and egress policy; OpenRouter is hosted and requires egress plus budget policy; custom OpenAI-compatible gateways are profile based; the deterministic provider is tests/offline CI only and is never a production fallback.

UI commands now include `/providers`, `/models`, `/model current`, `/model use <profile_id>`, `/model use --provider <provider> --model <model>`, `/model health`, `/model capabilities`, `/reasoning`, `/reasoning status`, `/reasoning set <mode-or-effort>`, and `/reasoning off`. Reasoning controls are model/profile-dependent, unsupported values are rejected, and private chain-of-thought is never exposed. Reasoning summaries, when supported by metadata, are safe summaries rather than raw chain-of-thought.

Security rules: `local_only=true` allows only local-machine endpoints. Private home-lab endpoints require `local_only=false`, network permission, and egress policy. Hosted/VPS endpoints require network and egress policy; paid hosted providers also require budget policy. OpenRouter always requires egress and budget policy and is disabled by default. There is no silent fallback from local to hosted or from production to deterministic test provider. Events and errors must not include raw prompts, completions, streamed chunks, API keys, Authorization headers, sensitive extra headers, file contents, or tool output contents.

Validation commands: `python -m pytest`, `python -m ruff check .`, and `python -m mypy raiker apps tests`.


## Async model runtime status (verified)

Raiker uses `httpx.AsyncClient` for async model transport and does not use the OpenAI SDK or Pydantic. FastAPI, LangChain, and LlamaIndex are deferred because no governed API, agent-framework, or retrieval integration is implemented in this change. llama.cpp is local-first through the async OpenAI-compatible path; Ollama, LM Studio, vLLM, generic endpoints, and OpenRouter are OpenAI-compatible profiles. OpenRouter is hosted and policy-gated. The deterministic provider is test-only, and production does not fall back to deterministic providers or silently switch from local to hosted providers.

Event/status labels distinguish `implemented_verified`, `implemented_unverified`, `offline_mock_verified`, `profile_defined_only`, `policy_gated_disabled`, `test_only`, and `specified_not_implemented`. Emitted model events must contain only safe metadata: provider, profile_id, model, endpoint_kind, duration_ms, finish_reason, tool_call_count, text_length, usage summary, error_class, safe_error_code, capability booleans, and reasoning settings. Raw prompts, completions, streamed chunks, Authorization headers, API keys, file contents, and tool outputs are not event payload material.

## Current limitations

- Approval resolution remains metadata-only and never executes actions; `approval_execution_relay` is a separate integrated governed executor for approved file-write proposals.
- Shell/process/network/web-fetch, plugin slices, external channel, local container, graph/semantic/vector/model-provider, and local email/calendar/reminder runtimes are integrated real executors and remain governed per action with independent fail-closed controls.
- Remote/cloud command execution remains no-executor/fail-closed.
- Finance/investment/medical/pregnancy/CCTV/home-security/hardware runtime remains no-executor/fail-closed.
- Email/calendar/reminder are local-only stores/drafts; no external send/sync/invites.
- Hosted/multi-user/cloud production runtime is future implementation work.
- Current production readiness applies only to local single-user runtime.
