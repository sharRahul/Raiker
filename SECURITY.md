# Raiker Security Architecture

> Current truth (2026-06-22): Raiker is an AI agent. The launchable local interfaces are the **plain local terminal client** and the **local web dashboard** (`raiker-web` loopback API + the `apps/web` Svelte SPA; single-user, `127.0.0.1` only). The web dashboard adds no authority of its own — every read and mutation routes through the same Agent Gateway, RuntimeAuthority, Policy Engine, Tool Broker, approval, and event-logging path as the CLI, and approval resolution is metadata-only. Rich/native TUI, Desktop, Mobile, IDE, Voice, Browser Extension, and hosted/multi-user REST/API clients are Phase 8 deferred, specified/deferred, not active runtime. Runtime execution capabilities remain disabled unless explicitly implemented, tested, documented, and policy-gated. This document does not claim security coverage for deferred features as if they are implemented.

This document separates claims into four categories:

- **Implemented:** code and tests exist for the current local runtime.
- **Metadata/readiness:** records, previews, plans, or read-only surfaces exist, but execution is not enabled.
- **Specified/deferred:** security requirements are documented for future phases, but no active runtime exists.
- **Missing:** a design or implementation gap remains and must be closed before enablement.

---

## 1. Purpose and Scope

This document describes Raiker's security architecture for the current local runtime. It is intended to be practical and audit-ready: each security claim is tied to the current runtime model and avoids treating planned capabilities as shipped controls.

Scope boundaries:

- Raiker is a **local AI agent**: current runtime state, event logs, approvals, checkpoints, memory records, provider profiles, and workspace operations are designed around a local workspace and local SQLite/JSONL storage.
- The launchable interfaces are the **plain local terminal client** (`raiker`) and the **local web dashboard** (`raiker-web` serves the FastAPI governed API and, when built, the `apps/web` SPA from the same loopback origin). Both are single-user and local-first; the server binds to `127.0.0.1` and must not be exposed on a public interface. Rich/native TUI has been removed/deferred from active launch behavior.
- Rich/native TUI, Desktop, Mobile, IDE, Voice, Browser Extension, and **hosted/multi-user** REST/API interfaces are **Phase 8 deferred** and are specified/deferred, not active runtime surfaces.
- Plugin execution, graph/codemap runtime indexing, semantic/vector memory writes, embeddings, approval execution/relay, cleanup/rollback execution, external channels/notifications, subagents, multi-agent teams, remote/container/cloud execution, shell/process execution, and network/web fetch remain disabled unless a future change explicitly implements, tests, documents, and policy-gates them.
- This document covers the security model of the current implementation and the gates required for future capabilities. It must not be read as a certification that deferred systems are already protected in production.

---

## 2. Security Principles

Raiker's current security principles are:

1. **Local by default:** prefer local workspace state, local providers, and local audit evidence before hosted services; the API server and dashboard are loopback-only and single-user.
2. **Least privilege:** commands, tools, providers, interfaces, and future clients receive only the permissions needed for their scoped action.
3. **Deny-by-default:** unknown tools, unsafe actions, unsupported hook handlers, disabled runtimes, and unconfigured providers fail closed.
4. **No privileged interface:** the web dashboard and API add no authority of their own — they are governed clients of the same core as the CLI and cannot bypass policy, authority, approvals, or disabled gates.
5. **Policy-gated tool execution:** model-suggested tool calls must pass validation, Tool Broker routing, and Policy Engine review.
6. **Human approval before sensitive mutations:** file writes, memory writes/forget operations, destructive operations, external dispatch, and execution capabilities require approval or remain proposal-only/readiness-only. Approval *resolution* records a decision and never executes the action.
7. **Human-only authority for control actions:** session minting, runtime-mode/capability-gate changes, and task interrupts (STOP) are human-only; AI principals are blocked.
8. **Deterministic append-style event recording where applicable:** runtime decisions, tool actions, policy outcomes, approvals, checkpoints, and metadata readiness records are recorded in JSONL and/or SQLite when the relevant path is implemented.
9. **Trust separation:** user prompts, model output, trusted Raiker code, untrusted workspace content, untrusted tool results, and future channel/plugin data are separate trust domains.
10. **No silent unsafe provider fallback:** deterministic/mock providers are test-only, hosted providers require explicit configuration and policy, and local-to-hosted fallback must not happen silently.
11. **No runtime bypass:** enabled paths (CLI and web/API) must not bypass the Agent Gateway, Tool Broker, Policy Engine, approval records, event records, or disabled phase gates.

---

## 3. Assets Protected

| Asset category | Confidentiality concerns | Integrity concerns | Availability concerns |
|---|---|---|---|
| User workspace files | Source code, notes, secrets, and local data may be sensitive. | Unauthorized edits, deletes, patching, or symlink/path escape can corrupt work. | Over-broad scans or destructive actions can block local work. |
| Session state | Prompts, responses, selected model, and context metadata can reveal user intent. | Cross-turn corruption can change decisions or attribution. | Lost session records reduce resumability and audit context. |
| Local API session token | The bearer token minted by `POST /api/auth/session` authorizes the local owner to the governed API. | A leaked token would let a local process drive the governed API as the owner. | Token revocation must invalidate access. |
| SQLite runtime state | Stores sessions, events, approvals, checkpoints, memory, profiles, principals, runtime-mode/gate state, and readiness metadata. | Schema misuse or direct writes can falsify policy/audit state. | DB locks/corruption can prevent local runtime operation. |
| JSONL event logs | Events may include user/model/tool metadata. | Append-style logs can still be edited by local filesystem access; no tamper-proof guarantee is claimed. | Missing logs reduce auditability and recovery evidence. |
| Checkpoints | May include snapshot metadata and future file state. | Incorrect checkpoint metadata can cause unsafe restore/fork planning. | Missing checkpoints reduce rollback/inspection options. |
| Approval records | Reveal sensitive proposed actions and decisions. | Forged or replayed approvals could authorize unsafe changes if not guarded; payload-hash tampering is rejected on resolve. | Missing approvals block governed workflows. |
| Memory candidates and approved memory | May contain preferences, project facts, or sensitive observations. | Memory poisoning can bias future context or decisions. | Lost memory reduces personalized/local continuity. |
| Model profiles and provider configuration | Endpoints, model choices, and future API-key references are sensitive. | Unsafe profile edits can redirect prompts to untrusted endpoints. | Broken profiles prevent inference. |
| Policy decisions | Decisions reveal enforcement posture. | Incorrect allow/deny/approval records undermine least privilege. | Missing decisions reduce audit and troubleshooting. |
| Tool action records | Tool arguments/results can include file paths and observations. | Tampering can hide unauthorized actions. | Missing records reduce reproducibility. |
| User prompts and model responses | May contain private instructions, code, secrets, or business context. | Prompt/response mutation changes intent and audit history. | Lost responses reduce session usefulness. |
| Future secrets/API keys | Hosted provider keys and connector tokens would be high-value secrets if enabled. | Secret substitution can redirect spend/data. | Secret loss can disable providers; leakage can require rotation. |
| Future channel/plugin/remote execution metadata | May reveal remote targets, plugin permissions, or channel recipients. | Tampering can expand permissions or route data externally. | Missing metadata blocks safe activation and audit. |

---

## 4. Trust Boundaries

| Boundary | Current status | Security expectation |
|---|---|---|
| User terminal input | Implemented | Parsed as user-controlled data; slash commands are explicit control input, not trusted code. |
| Slash command parser | Implemented | Must map commands to known handlers and reject unsupported/unknown commands safely. |
| Local web dashboard (SPA) | Implemented (loopback, single-user) | Renders governed backend state only; holds the bearer token in memory (never `localStorage`/`sessionStorage`); adds no authority and cannot bypass the governed core. |
| API server (`raiker-web` / FastAPI) | Implemented (loopback, single-user) | Binds to `127.0.0.1`; serves the SPA static assets and the governed API on the same origin. `/api` responses pass through the redaction middleware; static assets are served untouched. |
| API authentication | Implemented | `POST /api/auth/session` mints an owner bearer token; minting is **human-only** (AI principals rejected). Bearer required on all governed routes; revocation invalidates the session. |
| API authorization | Implemented | Every read/mutation resolves a principal and is enforced by RuntimeAuthority; runtime-mutation, interrupt, and approval routes apply the same human-only / `runtime_gate_manager` rules as the CLI. |
| Agent Gateway | Implemented | Normalizes session/turn inputs and is the entry point for both the CLI and the web/API clients. |
| Runtime Orchestrator | Implemented | Drives gather → plan → act → verify; model output remains untrusted. |
| Context Gatherer | Implemented for bounded local metadata/context | Adds provenance/trust/sensitivity/redaction metadata where implemented; workspace content remains untrusted. |
| Model Router and model providers | Implemented for local/OpenAI-compatible provider pattern plus policy-gated profiles | Provider endpoints are separate trust domains; hosted providers require explicit policy. |
| Tool Broker | Implemented | Only brokered tools may execute; unknown/unsafe actions fail closed. |
| Policy Engine | Implemented | Enforces allow/deny/needs-approval decisions before execution. |
| Approval Inbox | Implemented for approval records/list/resolve; execution relay deferred | Approval resolution is metadata/status only (`executes_action=false`); payload-hash tampering and unknown request fields are rejected. |
| Hook Dispatcher | Implemented for supported handler types | Hooks must not bypass broker/policy/approval/events; unsupported handler types remain deferred. |
| SQLite store | Implemented | Local state store; not claimed encrypted or tamper-proof. |
| Event log writer | Implemented | Append-style JSONL audit evidence; not claimed immutable or cryptographically attested. |
| Workspace filesystem | Implemented boundary target | Read/write proposals must stay workspace-scoped and policy-reviewed. |
| Plugin runtimes | Specified/deferred, not active runtime | Require sandboxing, manifests, permissions, events, and policy gates before execution. |
| External channels | Specified/deferred, not active runtime | Require authentication, recipient binding, egress policy, redaction, and audit before transport. |
| Remote execution | Specified/deferred, not active runtime | Requires isolation, secret handling, artifacts, egress controls, and approval gates. |
| Browser/IDE/native clients | Specified/deferred, not active runtime | Require workspace trust, extension permissions, auth/session isolation, and command parity. |
| Hosted / multi-user REST API | Specified/deferred, not active runtime | Local API is single-user/loopback; hosted/multi-user requires authn/authz, CSRF/CORS, rate limits, per-user session isolation, and event redaction beyond the local model. |
| Hosted model providers | Configurable/policy-gated or deferred depending on profile | External disclosure risk; no silent fallback from local to hosted. |

---

## 4a. Local Web Dashboard Security Model

The local web dashboard (`apps/web`) is a governed client, not a new authority. Its specific controls:

- **Loopback + single-user:** `raiker-web` binds `127.0.0.1` by default; there is no multi-user model and the server must not be exposed publicly.
- **Token in memory only:** the SPA obtains a bearer token from `POST /api/auth/session` and keeps it in memory; it is never written to `localStorage`/`sessionStorage`.
- **Human-only control actions:** session minting, the STOP switch (`POST /api/interrupts`), and runtime-mutation routes are human-only; AI principals receive `403 human_principal_required` / authority denials, exactly as on the CLI.
- **Redaction at the boundary:** the API redaction middleware scrubs secret-like strings (API keys, bearer tokens, passwords, private keys) from `/api` JSON responses; auth and the SSE stream are handled without breaking their function; static SPA assets bypass buffering and are served untouched.
- **Metadata-only approvals:** the approval queue resolves decisions with `executes_action=false`; resolving never executes the proposed action, payload-hash tampering is rejected, and unknown request fields are rejected (`422`).
- **Step-up for mutations:** Security Settings collects the backend-required `reason`, Tier-2 confirmation token, and threat-model acknowledgement and *forwards* them to the existing governed control routes; it grants nothing RuntimeAuthority would not already require, and fail-closed/deferred capabilities are shown un-enableable.
- **No secret store:** there is no secret/credential store; Secret Settings is read-only and labels secret storage as deferred. No secret input fields exist.
- **STOP semantics:** interrupts cancel at the next safe boundary (not an instant force-kill) and emit `interrupt_received` / `safe_boundary_reached` / `task_cancelled`.

---

## 5. Runtime Security Flow

Current safe runtime flow:

1. User submits a prompt or slash command (terminal client) or a request from the local web dashboard.
2. For the web dashboard, the request carries the owner bearer token; the API authenticates the session and resolves the principal.
3. Agent Gateway prepares session/turn context.
4. Context Gatherer collects bounded, provenance-tagged context.
5. Runtime Orchestrator classifies, plans, and requests model output as needed.
6. Model output is treated as untrusted data.
7. Any tool call is schema-validated and checked against the known tool catalog.
8. Tool Broker submits the action to the Policy Engine.
9. Policy Engine allows, denies, or requires approval.
10. Sensitive actions create approval records/proposals/previews instead of executing immediately.
11. Allowed read-only actions execute inside the broker path.
12. Results are observed and verified as untrusted observations.
13. Events/checkpoints/state records are written where the path is implemented.
14. The turn is closed.

**Safety invariant:** neither model output nor any client (CLI or web/API) may directly execute file changes, shell/process/network actions, plugin code, external channel sends, remote jobs, or other sensitive actions outside the Tool Broker + Policy Engine + approval/event path.

---

## 6. Tool Security Model

Current controls:

- Tool calls are brokered through the Tool Broker.
- Unknown tools are denied or rejected.
- Read-only filesystem and Git tools are allowed only within policy/workspace boundaries.
- Mutating tools require approval, create proposals/previews, or remain disabled depending on current implementation.
- Shell/process/network/runtime execution is disabled unless explicitly enabled in a future phase with policy, tests, and documentation.
- Tool results are untrusted observations, not trusted instructions.
- Tool action, policy decision, approval, and event records support auditability.

| Tool category | Current status | Security control |
|---|---|---|
| Read-only filesystem tools | Implemented where present (`read_file`, `list_directory`, `glob`, `grep`, `stat_path`, `diff_files`) | Workspace boundary + policy review |
| Git read-only tools | Implemented where present (`git_status`, `git_diff`, `git_log`) | Read-only + policy review |
| Write/edit/apply patch tools | Approval/proposal-gated where present (`write_file`, `edit_file`, `apply_patch`) | No silent mutation |
| Memory write/forget | Approval-gated where present (`/memory-store`, `/memory-forget`) | Approval + records |
| Shell/process execution | Disabled/deferred except proposal/readiness surfaces; direct execution must remain disabled | Must remain disabled |
| Network/web fetch | Disabled/deferred unless explicitly implemented for provider health/model transport | Must remain disabled for general web fetch |
| Plugin execution | Disabled/deferred | Phase-gated |
| Remote/container/cloud execution | Disabled/deferred | Phase-gated |

---

## 7. Policy and Approval Architecture

- **Static policy configuration:** policy decisions are based on configured capabilities, disabled runtime flags, tool permissions, provider policies, and phase gates.
- **Deny-by-default:** unknown commands/tools/actions and disabled runtime capabilities are rejected or rendered as readiness/proposal-only surfaces.
- **Approval-required categories:** workspace mutations, memory writes/forget operations, destructive operations, plugin/remote/channel activation, hosted provider use, shell/process/network execution, and rollback/cleanup execution require approval and phase enablement.
- **Approval records:** approval inbox, previews, audit summaries, and readiness records provide reviewable metadata for sensitive actions, on both the CLI and the dashboard's approval queue.
- **Approval resolution is metadata-only:** resolving an approval updates approval state/metadata and returns `executes_action=false`; it does not execute the approved action on any interface. Payload-hash tampering and unknown request fields are rejected.
- **Approval metadata vs execution:** metadata readiness, previews, and resolved approvals are not the same as executing a previously blocked action.
- **Deferred approval relay/runtime execution:** channel-mediated approvals, approval workers, durable execution queues, and automatic execution after approval remain specified/deferred unless implemented and tested in a future phase.

---

## 8. Event Logging, Checkpoints, and Auditability

Implemented or partially implemented audit surfaces include:

- JSONL event logs for append-style runtime evidence.
- SQLite state for sessions, turns, approvals, checkpoints, memory, provider/profile metadata, principals, runtime-mode/gate state, tool/action records, and readiness/lifecycle metadata where migrations exist.
- Session/turn records for local runtime continuity.
- Tool action records and policy decision records where brokered tool paths run.
- Approval records, approval previews, and approval audit summaries.
- Checkpoint creation/metadata for resumable and reviewable workflows.
- Governed-API and dashboard actions (auth, prompt turns, interrupts, approval resolutions, runtime mutations) emit the same event records as the CLI.

Audit value:

- Append-style JSONL and SQLite records make actions reviewable and testable.
- Deterministic IDs and readiness summaries support reproducible local validation.
- Metadata-only readiness records document disabled gates without activating them.

Known limitations:

- Raiker does **not** claim tamper-proof logs, immutable storage, cryptographic attestation, or comprehensive non-repudiation for the local JSONL/SQLite stores unless a specific future implementation proves it.
- Local filesystem owners can edit or delete local logs/databases outside Raiker.
- Deferred clients/channels/plugins/remote execution require additional audit coverage before enablement.

---

## 9. Model Provider Security

Raiker prefers local model operation and exposes providers through an async OpenAI-compatible provider pattern where applicable.

Current model security properties:

- Local preference: llama.cpp is the native local profile when configured/reachable.
- Ollama, LM Studio, vLLM, and generic OpenAI-compatible profiles are configurable local/home-lab or endpoint-compatible profiles according to `config/model-profiles.json`.
- OpenRouter/hosted profiles are external and require explicit configuration, policy, and budget/egress consideration.
- Deterministic/mock providers are test-only and must not be documented or used as production fallback.
- There is no silent fallback to hosted providers.
- Model output is untrusted and cannot directly grant tool authority.
- Prompt/context leakage is a risk when hosted or network endpoints receive prompts, context bundles, file summaries, tool results, or memory.
- Provider endpoints and API-key handling are security-sensitive; future secret storage/redaction controls are required before broad hosted-provider use.

| Provider type | Current role | Security note |
|---|---|---|
| llama.cpp | Local/native profile if configured | Preferred local runtime profile |
| Ollama | Local provider profile if configured | Local endpoint risk |
| LM Studio | Local provider profile if configured | Local endpoint risk |
| vLLM | Local/network-compatible profile if configured | Endpoint trust required |
| Generic OpenAI-compatible | Configurable profile | Depends on endpoint trust |
| OpenRouter/hosted | Policy-gated/deferred or explicit opt-in | External data disclosure risk |
| Deterministic/mock | Test-only | Not production fallback |

---

## 10. Context and Memory Security

- Context gathering is bounded by item and character budgets.
- Context items carry provenance, trust level, sensitivity, and redaction metadata where implemented.
- Workspace content is untrusted and may contain prompt injection.
- Memory candidates are separate from approved memory; governed memory writes/forget operations require approval where implemented.
- Semantic/vector memory writes and embeddings remain deferred when disabled by runtime flags.
- Prompt injection risks exist in files, tool outputs, event logs, memory records, model responses, and future channel/plugin data.
- Required safety rule: retrieved context may inform the model, but it must never grant authority, waive policy, approve actions, override disabled gates, or instruct the runtime to bypass broker/policy checks.

---

## 11. Hook and Extension Security

- The Hook Dispatcher is a security boundary: hooks observe or handle lifecycle events only through configured handler types and must not bypass policy, approval, event logging, or disabled runtime gates.
- Current supported hook handler types are `builtin` and `command` according to the current hook implementation and gap ledger.
- Unsupported handler types are missing/deferred and must fail closed.
- HTTP, MCP/tool, prompt, and agent hook handlers are deferred if not implemented.
- Future hook expansion must include handler allowlists, path/workspace scoping, timeout/cancellation behavior, event records, approval binding for sensitive effects, and tests proving no broker/policy bypass.

---

## 12. Deferred Capability Security Requirements

Before any deferred capability can move from specified/deferred or metadata/readiness into runtime-enabled, it must have: threat model, policy gates, storage schema, event/audit coverage, approval flow, tests, validation script coverage, documentation update, and an explicit disabled-to-enabled phase transition.

The **local web dashboard** has completed this bar for its scope (read-only governed views, governed prompt/turn/approval/runtime-mutation flows, metadata-only approval resolution) and is implemented and launchable. The clients below remain deferred.

| Deferred capability | Minimum gates before runtime enablement |
|---|---|
| Rich/native TUI, Desktop, Mobile, IDE, Voice, Browser Extension, and hosted/multi-user REST/API clients | Client threat model; authenticated/authorized session model where applicable; per-user session isolation for multi-user; gateway-only routing; approval UX parity; event redaction; parity tests; Phase 8 enablement record. |
| Plugin execution | Manifest permissions; signature/trust model; sandbox/isolation design; per-tool policy; install/activate approvals; plugin audit events; abuse tests. |
| External channels | Connector auth; recipient/session binding; egress allowlists; redaction; anti-replay for approvals; transport audit events; opt-in enablement. |
| Remote/container/cloud execution | Isolation/sandboxing; secret injection controls; artifact storage; egress limits; job cancellation; cost/budget policy; approval and audit coverage. |
| Shell/process execution | Command allowlists or scoped policy; cwd/workspace isolation; timeout/resource limits; approval; stdout/stderr redaction; no silent execution. |
| Network/web fetch | URL/domain policy; egress controls; content-type/size limits; SSRF defenses; result provenance; prompt-injection labeling; audit events. |
| Graph/codemap runtime indexing | Storage migrations; workspace boundary checks; incremental indexing policy; redaction; rollback/cleanup plan; indexing tests. |
| Semantic/vector writes and embeddings | Embedding provider policy; vector storage schema; sensitivity/redaction rules; approval flow; deletion/forget semantics; leakage tests. |
| Subagents and multi-agent teams | Agent identity; delegated authority limits; budget/cancellation policy; event causality; approval ownership; cross-agent memory isolation tests. |
| Approval relay/runtime execution | Human binding; replay protection; durable queue design; execution worker policy; event chain; rollback/error handling; relay abuse tests. |
| Scheduled automations/hosted routines | Owner consent; schedule storage; budget/egress policy; cancellation; stale approval handling; audit export; hosted abuse tests. |
| Secret/credential storage | Encrypted-at-rest design; access policy; redaction/no-log handling; rotation; per-provider scoping; leakage tests. (No secret store exists today.) |

---

## 13. Threat Model

| Threat | Risk | Current mitigation | Current limitation | Future requirement |
|---|---|---|---|---|
| Prompt injection from workspace files | Files may instruct model to ignore policy or leak data. | Workspace content is untrusted context with provenance; tools remain policy-gated. | Semantic detection of malicious instructions is limited. | Add prompt-injection regression corpus and stronger context labeling. |
| Prompt injection from tool outputs | Tool results may include malicious instructions. | Tool results are observations, not authority. | Model may still be influenced. | Add output sanitization/labeling tests and verifier checks. |
| Malicious/hallucinated model tool calls | Model may invent tools or unsafe args. | Tool-call schema validation, Tool Broker, Policy Engine, unknown-tool denial. | Complex semantic intent may be hard to classify. | Expand adversarial tool-call tests. |
| Unauthorized file modification | Writes could alter user code without consent. | Write/edit/patch paths are approval/proposal-gated; read-only tools separated. | Future tools could regress if bypassing broker. | Enforce broker-only mutation tests. |
| Workspace boundary escape | Path traversal/symlinks could read/write outside workspace. | Workspace boundary checks in implemented file/readiness paths. | Coverage must be maintained for every new tool. | Centralize and fuzz path canonicalization. |
| UI/API attempts to bypass governance | A client could try to enable a fail-closed cap, resolve-and-execute, interrupt as AI, or smuggle fields. | RuntimeAuthority enforces all mutations; approvals are metadata-only; interrupts/mutations are human-only; unknown request fields rejected. Covered by `tests/test_security_regression_ui.py`. | Coverage must grow with each new route. | Keep the security-regression suite exhaustive per route. |
| Local API token leakage | A leaked bearer token lets a local process drive the governed API as the owner. | Loopback-only bind; token minted human-only and held in memory; sessions revocable; responses redacted. | Any local process on the host could read a token from memory; no per-action re-auth. | Optional token scoping/expiry hardening; OS-level process isolation guidance. |
| Secret leakage to external providers | Prompts/context may expose secrets to hosted endpoints. | Local preference; hosted providers explicit/policy-gated; redaction where implemented. | No complete secret manager/redaction guarantee; no secret store. | Secret storage/redaction design and hosted-provider DLP tests. |
| Unsafe fallback to hosted models | Local failure could route data externally. | No silent local-to-hosted fallback; deterministic/mock test-only. | Profile misconfiguration can still be risky. | Provider allowlist and egress audit controls. |
| Plugin abuse | Plugins could run code or request excessive permissions. | Plugin execution disabled; manifest planning/validation only. | No runtime sandbox because runtime is deferred. | Sandboxing, signatures, permission prompts, abuse tests. |
| Hook abuse | Hooks could run commands or exfiltrate data. | Supported handlers constrained; unsupported handlers deferred; hooks must not bypass policy. | Command hook safety depends on policy and future expansion. | Handler allowlist, sandbox/timeout, network restrictions, tests. |
| Approval bypass | Sensitive action executes without human decision. | Needs-approval policy creates records/previews; approval resolution is metadata-only; approval execution relay disabled. | Approval runtime execution not complete for deferred surfaces. | Replay-resistant approval binding and execution workers. |
| Event log tampering | Local actor can edit logs to hide actions. | Append-style records support review. | No tamper-proof/immutable/attested logs claimed. | Hash chaining/tamper evidence and external audit export policy. |
| Memory poisoning | Bad memory alters future context. | Candidates/approved memory separation; approval gates where implemented. | Semantic/vector memory deferred; poisoning detection limited. | Memory review policy, provenance scoring, poisoning tests. |
| Cross-session data leakage | One session may expose another session's context. | Session records and local state boundaries exist; the local API is single-user. | Future multi-user sessions need stronger isolation. | Secure session isolation and authz tests for hosted/multi-user clients. |
| Remote execution abuse | Jobs could run untrusted code or exfiltrate data. | Remote/container/cloud execution disabled. | No runtime sandbox implemented. | Remote sandboxing, secrets, egress, artifact and approval design. |
| Hosted/multi-user API authz risks | Unauthenticated/cross-user clients could control runtime. | Local API is single-user and loopback-only with human-only control actions. | No multi-user authz, CSRF/CORS, or rate limiting because no hosted server exists. | Phase 8 hosted authn/authz, CSRF/CORS, rate limit, per-user session isolation tests. |
| Browser/IDE/native extension trust risks | Extensions can access workspace/browser data. | Browser/IDE/native clients deferred. | No extension trust model implemented. | Workspace trust prompts, permission minimization, signed extension policy. |

---

## 14. Security Control Matrix

| Control | Current status | Evidence in repo | Gap / future work |
|---|---|---|---|
| Workspace boundary checks | Implemented for current workspace/file planning paths | `raiker/tools/`, `docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md` | Fuzz and centralize across future tools. |
| Policy review | Implemented | `raiker/policy/`, `raiker/tools/`, catalog permissions | Expand policies for future clients/providers. |
| Approval-required sensitive actions | Implemented/metadata-readiness depending on path | `raiker/approvals/`, `raiker/approval_previews.py`, catalog approval rows | Approval relay/runtime execution deferred. |
| Approval resolution is metadata-only | Implemented | `raiker/approvals/__init__.py`, `raiker/api/routes_approvals.py`, `tests/test_api_approvals.py` | Keep `executes_action=false`; relay deferred. |
| Local API authentication/authorization | Implemented (loopback, single-user) | `raiker/api/auth.py`, `raiker/api/sessions.py`, `raiker/api/routes_*`, `tests/test_api_security.py` | Hosted/multi-user authz deferred. |
| API response redaction | Implemented | `raiker/api/redaction.py`, `raiker/api/app.py`, `tests/test_api_security.py` | Extend patterns as needed; no secret store yet. |
| Human-only control actions (mint/interrupt/gates) | Implemented | `raiker/api/routes_prompts.py`, `routes_control.py`, `tests/test_security_regression_ui.py` | Keep AI principals blocked on every new control route. |
| UI/API security regression suite | Implemented | `tests/test_security_regression_ui.py`, `tests/test_api_contract_schemas.py`, `tests/test_api_web_ui_serving.py` | Add a guard per new route/property. |
| Event logging | Implemented append-style records | `raiker/events/`, `raiker/storage/sqlite.py`, event docs | Tamper-evidence missing/deferred. |
| SQLite state records | Implemented | `raiker/storage/sqlite.py` | Encryption/backup/hardening not claimed. |
| Checkpoints | Implemented metadata/service paths | `raiker/checkpoints/` | Restore/fork execution remains approval-gated/deferred where applicable. |
| Deterministic test provider gating | Implemented | `config/model-profiles.json`, catalog `/launch --provider mock --model mock-deterministic` | Keep test-only; no production fallback. |
| Provider policy gating | Implemented for profiles/policy markers | `config/model-profiles.json`, `raiker/models/` | Secret manager and hosted DLP controls missing. |
| Disabled runtime flags | Implemented validation/readiness markers | `scripts/validate_repo_truthfulness.py`, `docs/IMPLEMENTATION_STATUS.md` | Maintain for every deferred runtime. |
| Tool broker validation | Implemented | `raiker/tools/`, `raiker/models/tool_call_validation.py` | Add adversarial model-call corpus. |
| Context provenance | Implemented for bounded local context | `raiker/context/` | Full repo intelligence and semantic context remain deferred. |
| Memory approval | Implemented for current memory write/forget surfaces; semantic/vector deferred | `raiker/memory/`, catalog memory rows | Poisoning/DLP tests need expansion. |
| Hook handler allowlist | Implemented for current handler types | `raiker/hooks/`, gap ledger | HTTP/MCP/prompt/agent handlers missing/deferred. |
| Plugin execution disabled | Metadata/readiness only | `raiker/plugins/`, `docs/GAP_AND_TODO_ANALYSIS.md` | Sandbox/signature model missing. |
| Remote execution disabled | Metadata/readiness only | `raiker/remote/`, `raiker/workspace/views.py`, catalog readiness rows | Remote sandboxing missing. |
| External channel disabled | Metadata/readiness only | `raiker/channels/`, catalog channel rows | Connector auth/egress controls missing. |
| Secret/credential storage | Not implemented (deferred) | Secret Settings is read-only in the dashboard; redaction only | Encrypted secret store + rotation design required. |
| Native/hosted/multi-user clients deferred to Phase 8 | Specified/deferred | `README.md`, `docs/ARCHITECTURE.md`, validation scripts | Phase 8 client security design required. |

---

## 15. Security Roadmap

### Current implemented controls

- Keep both launchable surfaces — the plain terminal client and the loopback single-user web dashboard — as governed clients of the same core; no new authority in either.
- Preserve Tool Broker + Policy Engine + RuntimeAuthority enforcement for model tool calls and all mutations.
- Maintain approval/proposal gates for sensitive mutations; keep approval resolution metadata-only.
- Keep API auth human-only, loopback-only, token-in-memory, with response redaction.
- Keep JSONL/SQLite audit records for implemented paths.
- Keep deterministic/mock provider test-only and production-policy-blocked.
- Keep disabled runtime flags covered by truthfulness validation, and keep the UI/API security-regression suite green.

### Phase 8 native/hosted client security requirements

TODOs:

- Define authn/authz for hosted/multi-user REST/API and remote-capable clients.
- Define secure per-user session isolation for multi-user modes.
- Add client identity to policy decisions and event records.
- Add CSRF/CORS/rate-limit requirements for any hosted REST/API surface.
- Add browser/IDE workspace trust and permission-minimization model.
- Add approval UX parity tests across every enabled client.

### Future plugin/execution security requirements

TODOs:

- Design plugin sandboxing, signing, manifest permission diffing, and revocation.
- Design shell/process execution sandboxing, command policy, timeouts, and output redaction.
- Design remote/container/cloud isolation, egress, artifact, budget, and secret injection controls.
- Add security regression tests for every newly enabled execution adapter.

### Future hosted/API security requirements

TODOs:

- Design secret storage, API-key redaction, rotation guidance, and no-log handling.
- Add provider data-leakage controls, endpoint allowlists, and hosted egress audit events.
- Add budget and rate controls for hosted providers.
- Add tests proving local provider failures do not silently fall back to hosted providers.

### Future enterprise/security-hardening requirements

TODOs:

- Add enterprise policy profiles and managed policy overrides.
- Add log integrity/tamper-evidence design if required.
- Add audit export verification and retention policy tests for security-critical records.
- Add formal threat-model review per deferred capability before each disabled-to-enabled transition.
