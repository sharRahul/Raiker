# Commands And Equal Interface Mode Specification

Raiker must provide a rich interactive experience across all enabled interfaces, not a set of fragmented or privileged entry points.

CLI, Rich TUI, Desktop, Web, Dashboard, IDE, Voice, Hotkeys, REST, Webhooks, Slack, Teams, Discord, Signal, Email, Browser Extension, Apple mobile app, Android mobile app, Mobile Companion, and other governed clients are equal-status primary interfaces when implemented and enabled. No interface is canonical over another. All actions must enter through the same Agent Gateway, contracts, policy gates, event log, session state, approval binding, task controls, checkpoint model, memory governance, and runtime orchestration.

---

## Global Command Requirement

Raiker must install one human-facing global command named `raiker` as the local terminal entry point.

```bash
raiker
```

Running `raiker` launches the configured local terminal client, which may be implemented as a Rich TUI or a plain terminal client. This terminal client is one primary interface, not the canonical place for normal user actions.

The global command must not require the user to choose separate primary modes such as ask/chat/tui. Those behaviours are actions inside Raiker clients. This rule does not reduce the equal primary status of Desktop, Web, IDE, Voice, Hotkeys, REST, Webhooks, chat channels, Email, Browser Extension, Apple mobile app, Android mobile app, or Mobile Companion.

---

## Equal Interface Action Model

The user can act through any enabled primary interface. Each interface may use its own native UX, but the resulting action contract and runtime behaviour must be equivalent.

| Action surface | Terminal/Rich TUI example | Behaviour |
|---|---|---|
| Normal prompt input | `List files in this project` | Creates a normal prompt turn. |
| Side question input | `? What is it doing now?` | Creates read-only side turn bound to active task. |
| Slash command or action | `/models` | Opens a panel or creates a structured action. |
| Approval card/control | Approve / deny / defer | Resolves exact pending action ID. |
| Model panel/action | `/launch --provider llama.cpp --model local-gguf` | Launches or switches model profile. |
| Channel panel/action | `/channels` | Lists, links, unlinks, and inspects connectors. |
| Memory panel/action | `/memory` | Searches and manages governed memory. |
| Graph panel/action | `/graph query --symbol ToolBroker` | Runs graph/codemap query through policy. |
| Storage lifecycle panel/action | `/storage-lifecycle --summary` | Inspects metadata-only lifecycle records; no runtime writes. |
| Checkpoint panel/action | `/checkpoints` | Inspect, restore, fork, export, or clean up checkpoints. |
| Diagnostics panel/action | `/doctor` | Runs diagnostics through approved checks. |

---

## Provider Launch From Any Interface

Model launch is an interface-neutral Raiker action, not a TUI-only action.

Terminal launch examples:

```text
/launch --provider llama.cpp --model local-gguf
/launch --provider lm-studio --model local-model
/launch --provider openai-compatible --endpoint http://localhost:1234/v1 --model local-model
```

The llama.cpp server is the native default backend and binds automatically when reachable; `/launch` switches profiles or points at a different local endpoint.

Desktop, Web, IDE, mobile, voice, channel, and API clients must map the same launch operation into the same model-launch action contract.

The global local terminal command remains:

```bash
raiker
```

but it is not the only primary interface.

---

## Interface Modes

| Mode | Purpose | User access |
|---|---|---|
| `cli` | Local command-line client and terminal entry path. | `raiker` and approved terminal workflows. |
| `rich_tui` | Full terminal UI with panels and background tasks. | `raiker` default terminal renderer or configured terminal client. |
| `desktop` | Native desktop shell or local webview client. | Desktop app. |
| `web_ui` | Browser client with same gateway and event stream. | Local or authenticated remote web UI. |
| `dashboard` | Operational overview and control surface. | Web/Desktop/Mobile dashboard views. |
| `ide` | Editor extension with project context. | IDE extension side panel and command palette. |
| `voice` | Speech input/output with confirmation gates. | Voice UI. |
| `hotkeys` | Local OS shortcut surface. | Configured hotkey actions. |
| `rest` | Programmatic API surface. | Authenticated local/remote REST API. |
| `webhooks` | Signed inbound automation. | Paired webhook connector. |
| `email` | Mailbox-based interaction. | Paired mailbox connector. |
| `slack` | Workspace chat interaction. | Paired Slack connector. |
| `teams` | Microsoft Teams interaction. | Paired Teams connector. |
| `discord` | Discord server/channel interaction. | Paired Discord connector. |
| `signal` | Signal device/channel interaction. | Paired Signal connector. |
| `browser_extension` | Browser selected-page/context handoff. | Paired extension. |
| `apple_mobile` | iOS/iPadOS mobile app. | Apple mobile app. |
| `android_mobile` | Android mobile app. | Android mobile app. |
| `mobile_companion` | Cross-platform mobile companion capability. | Apple/Android app implementations. |
| `prompt_turn` | One normal prompt action. | Any enabled primary interface. |
| `side_question` | Ask about active task without stopping it. | Any enabled interface that supports side questions. |
| `model_launch` | Launch/switch model provider. | Any enabled interface with model controls. |
| `channel_management` | Link/list/manage connectors. | Any enabled interface with admin/channel settings. |
| `storage_lifecycle_inspection` | Inspect Slice G metadata-only lifecycle summaries. | Any enabled interface with workspace/status panels. |
| `diagnostics` | Run health checks. | Any enabled interface with diagnostics capability. |
| `daemon` | Long-running local service used by channels/webhooks. | Managed from settings, service manager, or admin UI. |
| `headless` | Automation/test-only path. | Internal/test harness, not human UX. |

---

## Rich TUI Requirements

The Rich TUI is one equal-status primary interface. It must support:

1. live transcript panel;
2. active plan panel;
3. task progress panel;
4. tool calls panel;
5. approvals inbox;
6. side-question input box;
7. event log viewer;
8. checkpoint timeline;
9. memory inspector;
10. graph/context inspector;
11. storage lifecycle inspector;
12. notifications panel;
13. command palette;
14. file/reference picker;
15. background task manager;
16. interrupt/steer controls;
17. model/context usage display;
18. model launch/profile panel;
19. channel connector panel;
20. policy decision display;
21. keyboard shortcuts;
22. mouse support where available;
23. fallback plain terminal mode.

---

## TUI Layout

Recommended default layout:

```text
┌──────────────────────── Raiker Session ────────────────────────┐
│ Transcript / Assistant Stream                                   │
├───────────────┬──────────────────────────┬─────────────────────┤
│ Plan          │ Active Tools / Tasks     │ Approvals / Alerts  │
│ Checkpoints   │ Progress / Logs          │ Memory / Context    │
├───────────────┴──────────────────────────┴─────────────────────┤
│ Side question / slash command / normal prompt / file mention     │
└─────────────────────────────────────────────────────────────────┘
```

Panels must be resizable or switchable through keyboard commands.

---

## Side Questions While Work Continues

This is a mandatory feature for every enabled interface that supports side questions.

User must be able to ask:

```text
What is it doing now?
Why is it running tests?
Can you explain the last error?
How far has the task reached?
What files has it changed?
```

without stopping the active task.

Implementation rules:

1. The side question runs as a separate lightweight turn.
2. It reads active task state and event log snapshot.
3. It does not mutate the active task unless escalated.
4. It displays answer in the originating interface using that interface's side-question UX.
5. It can be promoted to steering instruction by user confirmation.
6. It must not reorder events in the main task.
7. It must be cancellable.

---

## Interrupt And Steering Controls

The user can interrupt active work with explicit controls from any enabled primary interface:

| Control | Behaviour |
|---|---|
| `pause` | Pause after current safe boundary. |
| `cancel` | Cancel active task and log cancellation. |
| `steer` | Add new instruction to active task. |
| `approve` | Approve exact pending action. |
| `deny` | Deny exact pending action. |
| `defer` | Move approval/action to deferred queue. |
| `fork` | Fork from checkpoint. |
| `rewind` | Restore previous checkpoint. |
| `summarise` | Summarise current task state. |

Safe boundaries include before tool execution, after tool completion, before file write, before local command execution, before checkpoint creation, before storage lifecycle status mutation, and before subagent handoff.

---

## Shared Input Syntax

Raiker interfaces must support these concepts. Terminal-like interfaces may use text syntax; GUI, mobile, chat, voice, and API clients may use equivalent buttons, cards, forms, commands, menus, voice transcripts, or request fields.

| Syntax | Meaning |
|---|---|
| Plain text | Normal prompt. |
| `/command` | Slash command or equivalent structured action. |
| `!command` | Local command proposal, never direct execution without policy. |
| `@path` | File or directory mention. |
| `#task` | Task reference. |
| `$memory` | Memory reference/search. |
| `%checkpoint` | Checkpoint reference. |
| `?question` | Side question shortcut. |
| `Ctrl+C` | Interrupt/pause flow, not silent crash. |
| `Ctrl+D` | Exit if safe or ask if task running. |

---

## Built-In Actions And Slash Commands

Slash commands are terminal syntax for interface-neutral actions. Every command below must have an equivalent action in every primary interface that exposes the relevant capability.

| Command | Purpose |
|---|---|
| `/help` | Show commands/actions. |
| `/status` | Show active session/task status. |
| `/plan` | Show or request plan. |
| `/tasks` | Show background tasks. |
| `/approvals` | Show pending approvals. |
| `/events` | Open event log viewer. |
| `/checkpoints` | Show checkpoint timeline. |
| `/rewind` | Restore checkpoint. |
| `/fork` | Fork from checkpoint. |
| `/memory` | Inspect/search governed memory. |
| `/context` | Show current context bundle. |
| `/tools` | Show tool registry and permissions. |
| `/permissions` | Show/edit permission rules. |
| `/hooks` | Show hook registry and status. |
| `/plugins` | Show plugin registry. |
| `/channels` | Show paired channels and connector registry. |
| `/models` | Show model profiles. |
| `/launch` | Launch or switch model provider profile. |
| `/graph` | Query graph/codemap context. |
| `/storage-lifecycle` | Inspect metadata-only lifecycle records. |
| `/storage-lifecycle --summary` | Inspect aggregate metadata-only lifecycle counts and disabled runtime write flags. |
| `/storage-lifecycle --graph` | Inspect graph/codemap lifecycle metadata only; graph runtime indexing remains disabled. |
| `/storage-lifecycle --memory` | Inspect semantic-memory lifecycle metadata only; semantic/vector writes and embeddings remain disabled. |
| `/compact` | Compact context. |
| `/export` | Export session/task/events. |
| `/doctor` | Run diagnostics. |
| `/config` | Inspect config. |
| `/quit` | Exit safely. |

---

## Command Expansion

Slash commands and equivalent GUI/mobile/API actions expand into structured prompts or actions before reaching the runtime.

Expansion lifecycle:

```text
raw interface input
  -> interface parser or action mapper
  -> UserPromptExpansion hook
  -> command/action permission check
  -> PromptEnvelope, UIActionEnvelope, ChannelMessageEnvelope, or ToolAction proposal
  -> runtime
```

Command expansion must be event-logged and must include the originating interface/client metadata.

---

## Background Task UI

A background task must expose task ID, title, status, current step, progress, started time, elapsed time, last event, pending approvals, side questions, changed files, output artifacts, and cancel/pause/steer controls in every enabled interface that can display task state.

Task statuses:

- `queued`
- `running`
- `waiting_for_approval`
- `waiting_for_user_answer`
- `paused`
- `cancelling`
- `cancelled`
- `completed`
- `failed`

Slice G lifecycle status records are not background tasks. They must not appear as executable jobs unless a later approved phase explicitly adds that with policy, audit, rollback, and tests.

---

## Approval UX

Approvals must show exact tool/action, exact command/path/URL, risk level, policy reasons, file diff if file write/edit, network host if network, command classification, and choices: approve once, approve session, deny, defer, inspect.

No approval should be hidden in a stream of text. It must appear in the approval surface native to the originating or currently active interface: approval inbox, card, drawer, mobile approval control, channel card, or authenticated API approval response.

Slice G lifecycle records are not executable approvals. Approval-preview, approval-audit, rollback-plan, and storage-lifecycle commands remain preview/read-only unless a later phase explicitly enables execution.

---

## File Mentions

`@path` mentions and equivalent file picker, attachment, or selected-file inputs must resolve inside workspace unless allowed, show matched files before loading if ambiguous, require approval for large/binary/sensitive files, record provenance in context bundle, and never bypass policy.

---

## Interface Events

Required terminal/TUI events:

- `tui_started`
- `tui_ready`
- `tui_panel_opened`
- `tui_prompt_submitted`
- `tui_command_submitted`
- `global_command_invoked`
- `tui_exited`

Required interface-neutral events:

- `ui_session_opened`
- `ui_prompt_submitted`
- `ui_action_submitted`
- `ui_side_question_submitted`
- `ui_interrupt_requested`
- `ui_task_steer_submitted`
- `ui_approval_selected`
- `ui_checkpoint_selected`
- `ui_connector_link_started`
- `ui_model_launch_requested`
- `model_launch_requested`
- `model_launch_completed`
- `command_expanded`
- `side_question_received`
- `side_question_answered`
- `task_interrupted`
- `task_steered`
- `approval_rendered`
- `approval_selected`
- `checkpoint_selected`
- `storage_lifecycle_rendered`
- `storage_lifecycle_summary_rendered`

---

## Interface Testing Requirements

Tests must prove:

- global `raiker` command launches the local terminal client;
- terminal prompt input creates a PromptEnvelope and reaches the gateway;
- provider launch maps to a model profile regardless of originating interface;
- parser/action mapper handles plain prompts, commands/actions, local proposals, file references, and side questions;
- side question does not stop active task;
- interrupt changes active task state safely;
- approval choice binds to action ID;
- checkpoint selection triggers restore/fork flow;
- storage lifecycle inspection is read-only and interface-equivalent;
- TUI can render with no colour/limited terminal;
- background task progress updates without corrupting transcript;
- every enabled primary interface uses the same gateway, contracts, policy, event log, and session state.

## Implemented Terminal Inspection Commands

The current terminal client exposes these inspection and control commands through shared services rather than terminal-only privileged paths:

| Command | Status | Behaviour |
|---|---|---|
| `/status` | implemented | Shows workspace paths, session count, lifecycle record count, and pending approval count. |
| `/tasks` | implemented | Lists task records from shared task storage. |
| `/events` | implemented | Lists recent indexed events. |
| `/checkpoints` | implemented | Lists checkpoint timeline entries. |
| `/approvals` | implemented | Lists pending action-bound approvals. |
| `/approve <approval_id>` | implemented | Resolves one exact pending approval as approved. |
| `/deny <approval_id>` | implemented | Resolves one exact pending approval as denied. |
| `/memory` | implemented | Shows read-only governed memory candidate status; durable writes remain disabled. |
| `/semantic-memory` | implemented | Shows semantic memory disabled status. |
| `/memory-review` | implemented | Shows governed memory review queue without writes. |
| `/memory-review --summary` | implemented | Shows governed memory review counts. |
| `/graph-status` | implemented | Shows graph/codemap indexing disabled status. |
| `/graph-plan` | implemented | Shows dry-run graph/codemap plan; indexing remains disabled. |
| `/approval-previews` | implemented | Shows preview-only approval records. |
| `/approval-audit` | implemented | Shows preview-only audit records. |
| `/rollback-plan` | implemented | Shows preview-only rollback plans. |
| `/storage-lifecycle` | implemented | Shows metadata-only storage lifecycle records. |
| `/storage-lifecycle --summary` | implemented | Shows metadata-only lifecycle aggregate counts and disabled write flags. |
| `/storage-lifecycle --graph` | implemented | Shows graph/codemap lifecycle metadata only. |
| `/storage-lifecycle --memory` | implemented | Shows semantic-memory lifecycle metadata only. |
| `/doctor` | implemented | Shows local diagnostics, provider health detection, and disabled Phase 3/4 gates. |

Commands described elsewhere in this document for future rich UI panels remain requirements unless listed here as implemented.

## Phase 3 Slice H Lifecycle Retention Commands

| Command | Status | Behavior |
|---|---|---|
| `/storage-lifecycle-retention` | implemented | Lists metadata-only retention policy plans. |
| `/storage-lifecycle-retention --summary` | implemented | Shows retention counts and disabled execution flags. |
| `/storage-lifecycle-cleanup-preview` | implemented | Lists cleanup previews with `can_cleanup_now=false`. |
| `/storage-lifecycle-cleanup-preview --summary` | implemented | Shows cleanup preview counts and disabled cleanup flags. |
| `/storage-lifecycle-handoff` | implemented | Lists future approval handoff plans with `can_execute_now=false`. |
| `/storage-lifecycle-handoff --summary` | implemented | Shows handoff counts and disabled execution flags. |

Unsupported arguments return usage output. These commands are read-only and do not execute lifecycle cleanup, graph indexing, semantic memory writes, embeddings, vectors, rollback, plugins, channels, subagents, remote execution, container execution, or cloud execution.

## Phase 3 Slice I lifecycle evidence reference

Slice I lifecycle evidence bundles, policy simulations, JSON exports, CLI surfaces, SQLite metadata tables, and disabled-runtime validation are centralized in `docs/PHASE_3_SLICE_I_LIFECYCLE_EVIDENCE_SPEC.md`. Slice I is metadata-only/read-only/export-only/simulation-only and does not mark Phase 3 complete.

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

## Current implementation truth table (Phase 3 reconciliation)

Phase 3 is `implemented_verified` only for safe foundation/readiness slices A-P: CLI functional-test surfaces, read-only shared workspace/view contracts, plugin manifest planning/validation, approval-preview surfaces, readiness metadata, storage lifecycle metadata, and disabled-runtime validation. Full rich UI apps and runtime features remain specified/deferred unless explicitly listed as implemented below. No UI surface may execute tools directly; all future execution must go through the Agent Gateway, ToolBroker, PolicyEngine, approvals, and disabled runtime gates.

| Surface | Current implementation | Functional-testable? | Runtime authority | Next task |
|---|---|---:|---|---|
| CLI / plain terminal | Implemented functional-test surface via `raiker` and slash commands. | Yes | No direct tool authority; routes through gateway/broker/policy where runtime paths exist. | Keep command/catalog parity and local smoke tests current. |
| Rich TUI panels | Minimal terminal shell/status rendering only; rich panels are specified, not implemented as a full app. | Partial/minimal | None. | Build panel framework only in a future approved slice. |
| Desktop UI | Read-only shared contract/view foundation only; no launchable desktop app. | Contract-only | None. | Implement app shell after explicit activation scope. |
| Web UI | Read-only shared contract/view foundation only; no launchable web app. | Contract-only | None. | Implement web client/API server after explicit activation scope. |
| Dashboard | Read-only shared contract/data-parity foundation only; no launchable dashboard. | Contract-only | None. | Implement dashboard views after explicit activation scope. |
| IDE extension | Specified/deferred; no extension runtime. | No | None. | Define extension transport and auth. |
| Mobile apps | Specified/deferred; no Apple/Android apps. | No | None. | Build mobile clients after explicit activation scope. |
| Voice UI | Specified/deferred. | No | None. | Define voice contracts after explicit activation scope. |
| Browser extension | Specified/deferred. | No | None. | Define extension boundary after explicit activation scope. |
| External chat/channel clients | Metadata/readiness only; transports disabled. | Readiness-only | None. | Implement connectors after explicit activation scope. |
| REST/API | Contracts specified/deferred; no launchable REST API server. | No | None. | Build authenticated API after explicit activation scope. |


## Phase 2.5 local code-review command (`/review`)

`/review` is the Phase 2.5 local code-review workflow MVP: a CLI-only, read-only, bounded local
diff reviewer using deterministic rule-based findings and metadata-only events.

Forms:

```text
/review
/review --summary
/review --staged
/review --path <path>
/review --json
/review --limit <number>
/review --severity <info|low|medium|high>
/review --propose-fixes
/review --proposals-only
```

Behavior:

- Default `/review` reviews unstaged changes. If there are no unstaged changes but staged changes
  exist, it reports that and suggests `/review --staged`. With no changes it returns a clean result.
- `/review --staged` reviews staged changes only; it never mutates the Git index or commits.
- `/review --path <path>` reviews only changes under a workspace-scoped path; traversal/absolute
  escape is rejected safely.
- `/review --summary` returns summary, severity counts, and finding titles only.
- `/review --json` returns a parseable, secret-free `ReviewResult`.
- `/review --limit <number>` and `/review --severity <info|low|medium|high>` filter findings
  after review, and rebuild the user-visible summary (`findings_count`, `severity_counts`,
  `categories`) from the filtered findings only.
- `/review --propose-fixes` additionally generates safe, in-memory `ReviewActionProposal`
  records from the (filtered) findings and renders them in text/JSON output. Filtering applies
  before proposal generation, so proposals align with visible findings.
- `/review --proposals-only` implies `--propose-fixes` and shows proposals with finding
  references while omitting detailed finding text.
- Unknown flags fail safely with usage text.

Untracked-file detection:

- `/review` detects untracked files through `git status` (via `ToolBroker`/`PolicyEngine`) and
  emits an `untracked-files` info finding.
- Untracked file contents are never read or leaked. Event payloads include a safe
  `untracked_count` integer; file contents are never in findings, proposals, events, or rendered
  output.
- If only untracked files exist (no tracked diff), `/review` reports the untracked finding
  and does not say "No local changes found."

Proposal generation (Phase 2.6):

- Proposals are generated deterministically by `raiker/review/proposals.py` from finding ids
  (`missing-tests`, `secret-introduced`, `scope-expansion`, `unsafe-runtime`, `docs-only`,
  `test-only`, `review-truncated`, `untracked-files`). Unknown findings produce no proposal.
- Each proposal carries `proposal_id` (prefix `rap_`), `finding_id`, `title`, `action_type`,
  `risk_level`, `requires_approval`, `would_modify_files`, `files`, `summary`, `rationale`,
  and `safety_notes`.
- Proposals that could change files have `requires_approval=True` and `would_modify_files=True`;
  info-only/no-action proposals have both false.
- A metadata-only `review_proposals_created` event records `proposal_count`,
  `requires_approval_count`, `would_modify_files_count`, and `risk_counts`. No raw diff, file
  contents, secrets, prompt text, private reasoning, chain-of-thought, or raw tool output is
  placed in proposals or event payloads.

Safety guarantees:

- `/review` never modifies files, stages/unstages the Git index, commits, runs tests, applies
  fixes, executes shell/process/network calls, or enables any disabled runtime flag.
- `/review --propose-fixes` is proposal-only: it never applies fixes, mutates files, runs tests,
  or executes shell/process/network calls.
- Raw diffs and secrets are never placed in findings, proposals, or event payloads; secret-like
  content is redacted before findings/events.

Boundaries: local CLI code review only. Not a review UI/web/dashboard/IDE/REST/API surface and not
GitHub PR review automation. Review never mutates files, stages/unstages, commits, runs tests, applies
fixes, executes shell/process/network calls, or enables any disabled runtime flag. Raw diffs and
secrets are never placed in findings, proposals, or event payloads.

## Phase 3 Slice A proposal lifecycle commands (`/proposals`, `/proposal`)

Phase 3 Slice A proposal lifecycle foundation adds local metadata-only lifecycle tracking for
review action proposals generated by `/review --propose-fixes`. It is metadata-only and
proposal-only; no proposal execution, no auto-fix, no patch application, no file mutation, no
staging/unstaging, no test execution, no GitHub PR automation, no UI/API/IDE/dashboard/mobile, no
approval execution, and no Phase 4.

Forms:

```text
/review --propose-fixes --save-proposals
/proposals
/proposals --json
/proposals --status <proposed|acknowledged|deferred|rejected|superseded>
/proposals --limit <number>
/proposal <proposal_id>
/proposal <proposal_id> --json
/proposal <proposal_id> --mark <proposed|acknowledged|deferred|rejected|superseded>
```

Behavior:

- `/review --propose-fixes --save-proposals` runs the existing review proposal generation and
  persists generated proposals as `ProposalLifecycleRecord` rows (status `proposed`) in the local
  SQLite `proposal_lifecycle_records` table. It returns normal review/proposal output and includes
  `saved_proposal_count` and `saved_proposal_ids` in `ReviewResult.event_metadata`. If no proposals
  exist, no records are created.
- `/proposals` lists saved records newest first (default limit 20). `--json` returns a parseable
  JSON array. `--status <status>` filters by lifecycle status. `--limit <number>` bounds the result
  count (must be >= 0). Text output shows proposal id, status, title, finding id, and risk level.
- `/proposal <proposal_id>` shows one record. `--json` returns a parseable JSON object.
  `--mark <status>` transitions the record's status (metadata only).
- Allowed statuses: `proposed`, `acknowledged`, `deferred`, `rejected`, `superseded`. No status
  implies execution approval; `approved`/`approved_for_execution`/`ready_to_apply`/`execute` are
  deliberately excluded.
- Unknown proposal ids fail safely with "Proposal not found." Invalid statuses fail safely with
  usage text. Unknown flags fail safely with usage text.

Safety guarantees:

- These commands never execute proposals, apply fixes, mutate files, stage/unstage the Git index,
  commit, run tests, execute shell/process/network calls, or enable any disabled runtime flag.
- `--mark` changes metadata only; it never executes, applies, or mutates anything.
- No raw diff, raw file contents, secrets, prompt text, private reasoning, chain-of-thought, raw
  tool output, or patch content is stored in records or event payloads.

Boundaries: metadata-only and proposal-only. Not a proposal execution surface, not auto-fix, not
patch application, not GitHub PR automation, not a UI/API/IDE/dashboard/mobile surface, and not
approval execution. `approval_execution_enabled` remains false. No Phase 3 runtime execution is
implemented by this slice. No Phase 4. Disabled runtime flags remain false.
