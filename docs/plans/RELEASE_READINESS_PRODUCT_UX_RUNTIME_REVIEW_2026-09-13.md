# Raiker Release-Readiness, Product, UI/UX and Runtime Review — 2026-09-13

## Status, scope and non-implementation boundary

This is a **documentation-only review** of Raiker at `main` commit
`327610ad0816cb5ce90590e29ef30179b7caa5a5`. It does not implement, fix, enable,
disable, or reconfigure any application, runtime, installer, security control,
workflow, or user interface behavior.

The review covers:

- Permissions;
- Chat, Build and Design;
- Models;
- the Settings popup and every registered Settings page;
- Tasks;
- Memory, including memory age, retention, management and recall usage;
- Messaging;
- Extensions → MCP servers;
- Projects;
- the account-identity symptom reported as
  `The workspace's real owner is principal_user_ac5eb6e5f7620f0d`;
- the common runtime, process, network, credential and authority boundaries these
  surfaces depend on;
- first-release readiness;
- transferable features and security patterns found in two external agent
  implementations, expressed here as Raiker requirements without product or
  repository names.

This is a static source, documentation, test-contract and workflow-state review.
It is not a fresh penetration test, clean-machine installer run, accessibility
audit with assistive technology, cross-platform visual run, or live-provider
acceptance campaign. Recommendations are therefore marked separately from
verified defects and verified implementation.

## Evidence vocabulary

| Label | Meaning |
|---|---|
| **Implemented** | Current source and tests expose the behavior. |
| **Partial** | A useful foundation exists, but the user journey or hard boundary is incomplete. |
| **Observed** | The owner has reproduced the behavior; the exact source path may still require live tracing. |
| **Static finding** | Current source directly exposes the issue without requiring a live run. |
| **Unverified** | The repository suggests the behavior, but this review did not execute the required live scenario. |
| **Recommendation** | Proposed work only; it is not represented as shipped. |

---

# Executive decision

## Release verdict

**Raiker is not ready to be called a generally available, production-stable
first release.** It is credible as a private alpha or tightly controlled
technical preview for its owner, provided that the release notes clearly state
the unsupported and unverified paths.

This conclusion is not based on cosmetic polish. Raiker already has strong
foundations: capability gates, approval modes, re-governance, immutable action
evidence, checkpoints, local account security, model choice, projects, scheduled
work, memory review, MCP management and a substantial test suite. The blockers
are places where the visible product promise is stronger than the proven end-to-
end contract.

### Release classification

| Release label | Decision | Conditions |
|---|---|---|
| Private developer preview | **Ready with caveats** | One trusted owner, backed-up workspace, explicit unsupported-feature list, no assumption that all remote/runtime paths are production hardened. |
| Public alpha | **Nearly, after P0 gates** | Identity leak fixed and regression-tested; MCP/process boundary tightened; clean install/update/uninstall passes on supported OSes; critical live paths re-run. |
| Public beta | **Not yet** | Design and Projects continuity complete; guided Messaging/MCP onboarding; recovery and migration drills; accessibility and responsive evidence; provider matrix verified. |
| Stable v1 | **Not yet** | All release gates below pass, security boundaries are mechanically universal, installers own their dependencies, and support/rollback/provenance contracts are documented and exercised. |

## What blocks a public first release

| ID | Priority | Blocker | Evidence and reason |
|---|---:|---|---|
| RR-IDENTITY-01 | P0 | Internal principal ID reaches owner-facing/model-facing language | The account routes already return a display name, and `UserMetadata` has a `display_name` field, but prompt envelopes populate only `id=principal_id`. The exact rendered sentence is owner-observed and not present as a static literal. |
| RR-AUTHORITY-01 | P0 | Side-effect authority is not yet proven mechanically exclusive across every executor | Raiker has strong governance, but release assurance requires a type/issuer boundary that a future route, plugin, scheduler or connector cannot bypass by convention. |
| RR-MCP-01 | P0/P1 | MCP stdio inherits the Raiker process environment | `raiker/runtime/executors/mcp.py` starts the subprocess without a constructed `env`, creating an ambient-secret exposure class. |
| RR-MCP-02 | P1 | Remote MCP trust and network reach are under-specified | URL parsing is present, but owner-added remote endpoints are treated as authorization without a shared destination trust class, redirect/DNS-rebinding contract and explicit private-network grant. |
| RR-INSTALL-01 | P1 | Linux/macOS installer runtime ownership is incomplete | A normal user must not need to supply a compatible Python toolchain or inherit unmanaged system dependencies for a supported desktop release. |
| RR-PROJECT-01 | P1 | “New chat” from a project does not establish that project for filing | The Projects view routes to `#/new-chat` without setting the work project; the adjacent Build action does set it. The source comment says Chat remains owner-wide, which is correct for retrieval, but that is separate from filing the new session to the selected project. |
| RR-DESIGN-01 | P1 | Design is generation history, not yet the promised persistent design workspace | Real generation and governed research exist; asset filing, versions, selection/masking, edits, compare/revert and canvas state do not. |
| RR-VERIFY-01 | P1 | Required release acceptance runs are not current in this review | Clean-machine installers, upgrades, repair/uninstall, live providers, remote runtimes, MCP adversarial cases and assistive-technology passes need a signed release-candidate evidence bundle. |

## Current CI evidence

All four workflows attached to the reviewed `main` commit completed successfully
on 2026-09-13:

| Workflow | Result | Run |
|---|---|---|
| CI | Success | `34743016638` |
| Web UI | Success | `34743016598` |
| Licensing | Success | `34743016597` |
| Phase Status Validation | Success | `34743016581` |

Green automation establishes a good baseline. It does not prove clean-machine
packaging, usability, live provider behavior, network containment, or the owner-
reported identity symptom.

---

# 1. Product simplification strategy

Raiker's primary usability risk is not lack of functionality. It is that
security, runtime, provider and implementation vocabulary is often visible at
the same level as the user's goal. The product should preserve the depth while
changing the order in which it is revealed.

## Recommended three-layer interaction model

| Layer | User question | What belongs here |
|---|---|---|
| Work | “What do I want Raiker to do?” | Chat, Build, Design, Tasks and Projects; one consistent composer; clear project and runtime context. |
| Review | “What needs my attention?” | Approvals, memory suggestions, failed tasks, disconnected services, security findings and recoverable errors in one attention queue. |
| Manage | “How is Raiker configured?” | Models, Permissions, Memory details, Messaging, MCP, runtimes, credentials, privacy and advanced diagnostics. |

The common rule should be **goal first, boundary second, implementation detail
on demand**. A user should be able to start ordinary work without knowing the
terms principal, profile ID, egress allowlist, MCP transport, embedding space,
fingerprint, containment state or recurrence wire value. Those facts remain
available in advanced drawers and audit evidence.

## Recommended global simplifications

1. Use one stable vocabulary everywhere:
   - permission availability: **On / Off**;
   - what happens when requested: **Ask me / Allow / Automatic / Never**;
   - service lifecycle: **Connected / Needs setup / Paused / Blocked / Error**;
   - destructive memory actions: **Archive**, **Forget**, and **Delete
     permanently**, each with one documented meaning.
2. Replace repeated page-specific setup instructions with a shared readiness
   component that answers: what is missing, why it is needed, and one next
   action.
3. Put the common happy path in the page and move IDs, raw URLs, environment
   variables, JSON, fingerprints and policy snapshots into **Advanced**.
4. Use one global **Needs attention** entry point for approvals, memory review,
   failed tasks, runtime problems and security findings. Keep their specialist
   pages for history and administration.
5. Keep an object continuous across surfaces: a Project selected in Projects
   must remain selected when opening Chat, Build, Design or Tasks; a task or
   conversation opened from a Project must retain an explicit backlink.
6. Provide undo or a recovery path for reversible management actions. Use
   step-up and stronger confirmation only for destructive or authority-loosening
   actions.
7. Never render internal identifiers as normal labels. IDs belong in audit
   details and copyable diagnostic fields only.

---

# 2. Owner identity defect

## Finding RR-IDENTITY-01

**Owner-observed symptom:** Raiker says
`The workspace's real owner is principal_user_ac5eb6e5f7620f0d` instead of using
the User Account name.

**Static evidence:**

- `raiker/contracts/models.py` defines `UserMetadata(id, display_name)`;
- `raiker/api/routes_auth.py` returns the authenticated principal's
  `display_name` from both `/api/auth/whoami` and `/api/auth/session-state`;
- `raiker/api/routes_settings.py` also exposes the account display name;
- `raiker/api/routes_prompts.py`, channel ingress, scheduler runs and approval
  resume construct `UserMetadata(id=principal_id)` without `display_name`;
- internal account identifiers are intentionally formed as `principal_{user_id}`;
- the exact reported sentence is not a source literal, so it is likely composed
  by a model or generated from runtime/tool metadata rather than by a fixed UI
  string. That final origin remains **unverified** until a live trace captures
  the turn context and tool results.

## Root-cause assessment

The repository currently has the right data but an incomplete identity contract.
The internal authorization key and the presentation identity are not carried
together at all agent entry points. A model that receives or discovers only the
principal key can mistake that identifier for the user's name.

This is both a UX defect and an information-boundary defect. Opaque internal IDs
should not be taught to the model or displayed to the owner unless an audit view
explicitly asks for them.

## Required identity contract

| Field | Purpose | Visibility |
|---|---|---|
| `principal_id` | Authorization, ownership joins, audit correlation | Runtime and audit details only |
| `account_username` | Stable sign-in/account handle | Account and recovery UI; not automatically sent to models |
| `display_name` | How Raiker addresses the user | Chat/UI and a sanitized user-identity context block |
| `actor_kind` | Owner, delegated user, channel sender, agent, service | Runtime policy and audit evidence |
| `channel_identity` | Bound external sender/account | Messaging routing details only |

## Documented implementation design

1. Resolve identity server-side from the authenticated principal. Never accept a
   client-supplied display name as authority.
2. Populate `UserMetadata.display_name` on web, scheduled, resumed and messaging
   entry paths from that server-side record.
3. Add a small trusted context item such as `User display name: Rahul`, with a
   strict length, Unicode normalization and control-character removal. Explicitly
   tell the model that internal IDs are not names.
4. Keep authorization decisions keyed only by `principal_id`; display-name
   changes must not change ownership.
5. Strip or replace internal IDs in ordinary tool summaries and generated prose.
   Preserve them in structured audit records.
6. Render the display name in normal UI. Offer “Copy principal ID” only in an
   advanced Account or audit panel.
7. Add regression coverage for web Chat, Build, Design research, Tasks,
   Messaging ingress, approval continuation, Memory explanations and Projects.

## Acceptance criteria

- Changing the account display name changes subsequent salutations without
  moving or duplicating data.
- No ordinary transcript, Project card, Memory card, notification or messaging
  reply contains a `principal_*` identifier.
- A model request cannot overwrite the authenticated display identity.
- Audit exports retain the principal ID and state which presentation identity
  was active at the time.
- A live regression reproduces the original prompt and confirms the reported
  sentence no longer appears.

---

# 3. Page-by-page UI, UX and implementation review

## 3.1 Permissions

### Current strengths

- Capability availability and decision behavior are separate controls, which is
  the correct security model.
- The page supports search, grouped permissions, “needs attention”, common/all
  views, real enforcing state, bulk tightening and guarded loosening.
- Narrow layouts retain the relevant verdicts rather than hiding table columns.

### Findings

| ID | Priority | Finding | Simplification |
|---|---:|---|---|
| UX-PERM-01 | P1 | Sixty-plus capabilities create scan and comprehension load. | Lead with task-based presets and “Recently used / Needs attention”; preserve the full registry under Advanced. |
| UX-PERM-02 | P1 | Availability and behavior are visually similar, so users can conflate “can exist” with “what happens when requested.” | Phrase them as two questions: “Can Raiker use this?” and “When Raiker wants to use it”. |
| UX-PERM-03 | P1 | Bulk actions still use “Ask” and “Deny” while other surfaces use “Ask me / Allow / Automatic / Never”. | Adopt the same four terms in buttons, MCP explanations, approvals and documentation. |
| UX-PERM-04 | P2 | Technical capability names are useful for evidence but weak as the first label. | Show plain-language action, consequence and example first; registry key in Details. |
| UX-PERM-05 | P2 | The page does not summarize effective posture by user goal. | Add read-only summaries such as “Can edit project files after asking” and “Cannot send messages”. |

### Recommended interaction

The default view should contain a posture summary, a short attention list and
five task groups: **Files and code, Web and research, Messages and services,
Memory, System and runtimes**. Opening a group reveals individual capabilities.
Every change should preview before/after effective behavior, identify whether
step-up is required and offer a direct link to relevant evidence.

Do not collapse gate and decision mode into one backend field. Simplify the
language and progressive disclosure, not the security model.

## 3.2 Chat

### Current strengths

- Mature streaming conversation with persistent sessions, branching, export,
  printing, citations, source inspection, tool activity, governed-event detail,
  attachments, dictation/read-aloud, approval continuation and background work.
- Honest loading, empty, stopped, blocked and cross-tab continuation states.
- Shared composer conventions with Build and Design reduce mode-switch cost.

### Findings

| ID | Priority | Finding | Recommendation |
|---|---:|---|---|
| UX-CHAT-01 | P1 | `ChatView.svelte` is about 2,825 lines and coordinates history, streaming, citations, approvals, memory, project filing, speech, attachment and menu state. | Split by state machine/domain: session controller, turn renderer, composer controller, citation/source panel and conversation actions. |
| UX-CHAT-02 | P1 | Advanced governance/tool details can visually compete with the answer. | Default to a compact “Used 3 tools · 2 sources · 1 approval” disclosure; retain full evidence on expansion. |
| UX-CHAT-03 | P1 | Project filing and owner-wide Chat retrieval are easy to misunderstand. | Label the distinction: “Filed in Project X; Chat can still use account-wide memory.” |
| UX-CHAT-04 | P2 | Background work is an icon-only rail and may be undiscoverable. | Add a first-use label/badge and surface active count or failure state. |
| UX-CHAT-05 | P2 | Conversation actions, branch/rewind, sources, memory corrections and background work lack a single mental model. | Group them as Conversation, Evidence and Continuity actions; use consistent placement. |

### Simplified happy path

The page should ordinarily show the transcript, one context line and the
composer. Model, project, runtime and permission problems should appear only
when they affect the next turn. Evidence remains one click away. The user should
never need to visit Settings to understand why Send is disabled.

## 3.3 Build

### Current strengths

- Build is a real code-work surface: project/repository boundary, file explorer,
  code map mentions, artifact/preview zones, command output, diffs, selective
  hunk acceptance, edited replacement proposals, checkpoints and governed
  execution.
- It preserves conversation continuity across reload and clearly handles
  approval pauses and safe-boundary stops.

### Findings

| ID | Priority | Finding | Recommendation |
|---|---:|---|---|
| UX-BUILD-01 | P1 | `BuildView.svelte` is about 3,311 lines, the largest requested surface. | Extract repository, conversation, approval review, artifact, command and layout controllers with contract tests. |
| UX-BUILD-02 | P1 | Repository, project, runtime and model are separate concepts but can read as competing “where work happens” selectors. | Present one “Work boundary” summary: Project → repository → environment → model, with only the currently actionable control expanded. |
| UX-BUILD-03 | P1 | The page can expose file tree, transcript, artifact panel, terminal output and approval review simultaneously. | Use task-aware panel priority and one right-side inspector at a time; preserve state when switching. |
| UX-BUILD-04 | P1 | Autonomous completion is not proven by UI sophistication alone. | Release acceptance must cover edit → test → diagnose → retry → green → summary, including failure and approval interruption. |
| UX-BUILD-05 | P2 | “Start in Build” is clear, but later navigation back to the originating Project is weak. | Add a persistent Project breadcrumb and “Open project work” backlink. |

### Runtime expectation

Build should consume one runtime-issued execution context that contains the
selected environment, repository mount, egress class, resource budget,
credential loans, approval authority and cancellation tree. The UI should render
that context as a short sentence; it should not reconstruct it from independent
client state.

## 3.4 Design

### Current strengths

- Real governed image generation and governed research exist.
- The UI correctly omits unsupported edit/outpaint/variation controls rather
  than drawing inert features.
- Model absence and permission/egress failures are surfaced honestly.

### Findings

| ID | Priority | Finding | Recommendation |
|---|---:|---|---|
| UX-DESIGN-01 | P1 | The surface is a prompt plus generation history, not a persistent design workspace. | Add an asset model before adding canvas chrome: Project ownership, versions, source prompt/model/options and durable file reference. |
| UX-DESIGN-02 | P1 | Selecting a Project does not yet guarantee generated assets are filed into it. | Bind every generation to an explicit project or “Unfiled” collection and show the destination before Generate. |
| UX-DESIGN-03 | P1 | Research and generation are adjacent but not a reusable reference workflow. | Let approved research images/text become named references with provenance and explicit consent to send them to the image provider. |
| UX-DESIGN-04 | P2 | Size is visible, while aspect/count/seed/quality are absent because the backend lacks them. | Preserve this honesty; introduce an Options drawer only as governed endpoint fields become real. |

### Required staged design model

1. **Asset foundation:** project-owned asset, version, preview, metadata,
   export and delete/recover lifecycle.
2. **Compare and iterate:** variations, side-by-side compare, favorite, revert,
   prompt reuse and reference images.
3. **Edit:** selection/mask, inpaint, outpaint, crop and transform with immutable
   parent/version lineage.
4. **Canvas:** persistent placement, layers and annotations only after the asset
   and edit contracts are stable.

## 3.5 Models

### Current strengths

- The five-task information architecture—Overview, My models, Add, Runtime and
  Usage—is much clearer than a provider-centric matrix.
- Local, private-network and hosted choices are represented without pretending
  that connection, discovery, selection and availability are the same state.
- Global selection, fallback order, context capacity, provider usage and
  readiness/error states are present.

### Findings

| ID | Priority | Finding | Recommendation |
|---|---:|---|---|
| UX-MODEL-01 | P1 | `ModelsView.svelte` is about 3,235 lines and owns discovery, credentials, catalogue, selection, pricing/usage, runtime setup and modal state. | Split by the existing five tabs; put connection lifecycle and global selection into shared stores/services. |
| UX-MODEL-02 | P1 | “Provider connected”, “models discovered”, “model selected” and “runtime available” still demand expert interpretation. | Use a four-step readiness line and give one primary next action. |
| UX-MODEL-03 | P1 | Users can choose globally and again inside composers without a clear override hierarchy. | State: “Default model” and “This work uses …”; offer Reset to default. |
| UX-MODEL-04 | P1 | Cost, context, privacy and tool support are spread across tabs/cards. | Add a comparable decision table with Locality, Context, Tools, Vision, Estimated cost and Availability. |
| UX-MODEL-05 | P2 | Raw profile/provider identifiers may leak into troubleshooting. | Keep stable IDs in Advanced diagnostics and exports, never as primary labels. |

### Recommended selection journey

Ask one question first: **Where may this work run?** Offer On this device,
Private server and Hosted service. Then show compatible models. Connection and
credential collection belong inside the chosen path. The advanced catalogue,
fallback order and per-surface overrides remain available after setup.

## 3.6 Settings popup (“Settings & pages”)

### Current strengths

- `AllPagesDialog.svelte` is searchable, grouped, keyboard-aware and acts as a
  compact route launcher for destinations not kept in the main sidebar.

### Findings

| ID | Priority | Finding | Recommendation |
|---|---:|---|---|
| UX-SETPOP-01 | P1 | A gear opens both a settings navigator and an all-pages launcher. | Rename the trigger and dialog to “More” or split “More” from direct “Settings”. |
| UX-SETPOP-02 | P1 | It overlaps conceptually with command/search navigation. | Give global search commands/pages and use the popup for stable navigation only, or merge them deliberately. |
| UX-SETPOP-03 | P2 | On mobile, the mental model should be navigation rather than a desktop dialog. | Render as a full-height sheet with Back, recent pages and clear current-location state. |
| UX-SETPOP-04 | P2 | Administrative and everyday destinations receive similar visual weight. | Group into Work, Review, Connect and Settings; put diagnostics/advanced last. |

## 3.7 Settings pages

`SettingsView.svelte` correctly tracks dirty state and rolls back a failed save.
The grouped rail is sound. The main improvement is to organize by user outcome
and reduce the density of Security and Runtime.

| Page | Current assessment | Required simplification / improvement |
|---|---|---|
| General | Clear language, region, weather and startup settings. | Explain which fields affect model context versus UI only; preview locale/time behavior. |
| Notifications | Understandable but sparse. | Include per-event channels, quiet hours, delivery test and failed-delivery history. |
| Personalisation | Clear theme/density/font controls. | Add live preview, system-default explanation and accessibility-safe bounds. |
| Security | Strong breadth but about 764 lines and mixes encryption, vault, MFA, credential scanning, containment, password, sessions and grants. | Split into Sign-in & devices, Secrets & vault, Security findings and Standing access. Put emergency pause at top. |
| Privacy | Useful retained-working controls. | Summarize “what leaves this device” by model, web, messaging and telemetry; link to data inventory. |
| Account | Username/display/delete flow exists. | Make display name the obvious owner-facing identity; explain that account changes do not alter data ownership. Use typed confirmation and step-up for deletion. |
| Web access | Blocklist and destination check are valuable. | Replace raw policy-first presentation with Allow/Block rules, explain private-network behavior, show recent requests and redirects. |
| Git credential | Token and grant controls exist. | Prefer credential-manager/OAuth setup, show repository scope and expiration, never redisplay secrets. |
| Runtime | Rich SSH/remote/container facts but highly technical. | Wizard: choose Local/Container/SSH/Managed remote, test prerequisites, preview access, then Advanced host keys/ports/egress. |
| Updates | Signed-update posture exists. | Show channel, installed/latest version, signature/provenance result, release notes, rollback and retained workspace compatibility. |

`web/src/lib/views/settings/Storage.svelte` exists but is deliberately not
registered, and tests assert that no Storage button is shown. It is dead or
reserved code, not a current page. Before release, documentation and source
ownership should decide whether it is deleted or backed by a real storage API;
it must not be advertised as a shipped setting.

## 3.8 Tasks

### Current strengths

- One composer supports run-now, one-time, routine and background work.
- Tasks can belong to Projects, use Chat or Build, carry attachments and model
  choice, form parent/child work and resume safely after approvals.
- Polling keeps queued/running states from becoming indefinitely stale.

### Findings

| ID | Priority | Finding | Recommendation |
|---|---:|---|---|
| UX-TASK-01 | P1 | “Now”, “Schedule once”, “Routine” and “Background” combine timing and execution style. | Separate “When” from “Run mode”; explain that background is still governed and may pause for the owner. |
| UX-TASK-02 | P1 | A recurrence select cannot express timezone, weekdays, end conditions, missed-run policy or next-run preview. | Use a human schedule builder with timezone and the next three occurrences. Keep cron/raw recurrence in Advanced. |
| UX-TASK-03 | P1 | Project, parent, priority, work method and model are hidden together under Details despite different importance. | Keep Project and When visible; group orchestration details separately. |
| UX-TASK-04 | P1 | Users need one history of run attempts, approval pauses, retries and deliveries. | Open a task detail timeline with current state, next action, output and evidence. |
| UX-TASK-05 | P1 | Destructive, duplicate, pause, resume, run-now and edit semantics need a consistent lifecycle. | Define Draft → Scheduled/Queued → Running → Waiting → Completed/Failed/Stopped, with retry/idempotency rules. |
| UX-TASK-06 | P2 | Parent/child tasks are powerful but advanced. | Hide hierarchy unless requested; visualize child progress and define parent settlement. |

### Automation reliability requirements

- persistent occurrence ledger with idempotency key;
- explicit timezone and daylight-saving behavior;
- configurable missed-run policy: skip, run once, or catch up within a bound;
- bounded retry with jitter and visible incident state;
- single active claim/lease and restart recovery;
- budget and maximum-runtime enforcement;
- delivery status independent from work success;
- exact authority snapshot plus re-governance at execution time;
- owner pause/stop that reaches the entire process/subagent tree;
- testable “doctor” diagnostics for scheduler, clock, runtime, model and channel.

## 3.9 Memory, age, management and usage

### Current strengths

- Memory has separate Overview, Memories, Suggestions, Sources and Recall tabs.
- Approved memories are searchable/filterable and carry source, edit, scope,
  expiry, pin, history, archive/forget and permanent-delete controls.
- Suggestions and relationships require review; observations expose what was and
  was not captured; incognito disables recall without deleting data.
- Recall backend and embedding readiness are explicit rather than hidden.

### Findings

| ID | Priority | Finding | Recommendation |
|---|---:|---|---|
| UX-MEM-01 | P1 | Each memory card can expose seven actions plus advanced deletion. | Keep Edit, Pin and More; move source/scope/expiry/history/archive/delete into a details drawer. |
| UX-MEM-02 | P1 | Forget, archive, expiry and permanent deletion are close in meaning. | Publish one lifecycle and use the same verbs in UI, API, audit and documentation. |
| UX-MEM-03 | P1 | Retention and “memory age” are record-level concepts, but users need policy-level understanding. | Add a retention summary: permanent, expires soon, stale for review, archived and pending deletion. |
| UX-MEM-04 | P1 | Confidence and trust decimals are technical and can imply precision the user cannot evaluate. | Translate into reasoned labels with “Why?”; retain raw scores in Advanced. |
| UX-MEM-05 | P1 | The product shows what is stored but not enough about actual use. | Add last recalled, recall count, which answer used it, and a direct turn link. |
| UX-MEM-06 | P1 | Sources, observations, suggestions and approved memory require a mental model. | Explain the pipeline: observed → suggested → approved → recalled → reviewed/expired. |
| UX-MEM-07 | P2 | Embedding backend controls sit beside personal-memory controls. | Move engine configuration to Advanced or Models; show only health and repair action in Memory. |
| UX-MEM-08 | P2 | Imports can introduce conflicts, duplicates and foreign provenance. | Require a preview with merge/skip choices, source trust classification and reversible batch receipt. |

### Recommended memory-age model

Age alone must never delete a memory. Compute review priority from:

- explicit retention chosen by the owner;
- sensitivity;
- last verified/edited time;
- last recalled time and recall frequency;
- contradiction or supersession;
- source availability and trust;
- project/account scope;
- pin status and legal/user hold.

Recommended owner-facing states:

| State | Meaning | Default action |
|---|---|---|
| Current | Recently verified or used; no conflict | None |
| Review soon | Near owner-selected expiry or potentially stale | Review, extend or archive |
| Conflicted | Contradicted by newer approved information | Compare and choose |
| Expired | Excluded from recall under retention policy | Restore or archive |
| Archived | Kept for history, excluded from recall | Restore or delete permanently |
| Pending deletion | In recoverable grace period | Undo or complete deletion |

### Memory usage dashboard

Show counts and trends without exposing content to telemetry:

- approved, suggested, expired, archived and conflicted records;
- memories recalled in the last 7/30 days;
- answers using memory and successful source links;
- unused/stale memories needing review;
- storage and embedding size;
- capture refusals by reason;
- import/export/forget receipts;
- recall latency and fallback health.

## 3.10 Messaging

### Current strengths

- Inbound content is explicitly untrusted.
- Pairing and enabling are separate; unknown senders are not silently trusted.
- Routing supports record-only, new turn, side question and interrupt behavior,
  with owner binding and exact approval relay.
- Egress, signing, inbound secret and sender-rate posture are visible.

### Findings

| ID | Priority | Finding | Recommendation |
|---|---:|---|---|
| UX-MSG-01 | P1 | The page asks normal users for environment variables, raw sender/conversation IDs and test destination URLs. | Provide a “Connect channel” wizard with account authorization, sender discovery, test exchange and readiness check. Keep raw fields in Advanced/operator setup. |
| UX-MSG-02 | P1 | “Connectors” here conflicts with Extensions → Connectors. | Call these “Channels” or “Messaging accounts”; reserve Connector for the underlying integration. |
| UX-MSG-03 | P1 | Pairing, enablement, routing and approval relay are separate controls without a clear sequence. | Render a checklist: Connected → owner verified → allowed conversations → routing → test → enabled. |
| UX-MSG-04 | P1 | An arbitrary destination URL for test delivery weakens the channel mental model. | Test through the selected account/conversation and apply the same routing and egress policy as real delivery. |
| UX-MSG-05 | P1 | Group, thread, bot and multi-user behavior is not sufficiently visible. | Show DM/group scope, mention requirement, thread mapping, sender role and bot-loop protection per route. |
| UX-MSG-06 | P2 | Delivery and work outcomes can be conflated. | Track received, accepted, queued, processed, reply queued, delivered and failed separately. |

### Messaging security and reliability contract

- signed requests with key rotation, timestamp and nonce/replay window;
- durable inbound idempotency before invoking the model;
- per-sender, per-channel and global rate/budget limits;
- attachment type/size/decompression limits and malware/content scanning hooks;
- outbound secret/PII scanning and explicit destination binding;
- allowlist/pairing separate from conversation routing;
- bot-loop detection, maximum automated rounds and owner-only activation;
- edits/deletes/reactions/thread replies mapped to explicit events;
- delivery retry ledger with deduplication and dead-letter review;
- safe rendering of untrusted Markdown, mentions, filenames and links;
- one-click containment of an account without deleting its evidence.

## 3.11 MCP servers

### Current strengths

- Server creation, plugin offers, discovery/test, rename, pause/stop and delete
  controls exist.
- Cards expose lifecycle, protocol version, projected tools, recent sessions,
  monitor findings and whether the agent can call the server.
- A safe starter template and honest capability-gate failures are present.

### Findings

| ID | Priority | Finding | Recommendation |
|---|---:|---|---|
| SEC-MCP-01 | P0 | Stdio subprocesses inherit ambient environment. | Launch through the common runtime with a minimal allowlisted environment and scoped secret references. |
| SEC-MCP-02 | P1 | Remote endpoint authorization lacks a shared explicit trust class. | Classify public, loopback, private/LAN and owner-granted private endpoints; revalidate DNS and redirects. |
| SEC-MCP-03 | P1 | Monitoring persistence is best-effort and exceptions do not stop the session. | Separate optional telemetry failure from containment-enforcement failure; the latter must fail closed. |
| UX-MCP-01 | P1 | “Builder/template” is the first journey, which is developer-first. | Offer Add from verified catalogue, plugin, local command or remote URL; show raw template only in Advanced. |
| UX-MCP-02 | P1 | Users cannot assess the blast radius before connecting. | Preview tools, roots/resources, network class, secrets, writable paths and required Permissions before activation. |
| UX-MCP-03 | P1 | Tool names and JSON arguments are insufficient as a trust explanation. | Add plain-language purpose, risk category, source/publisher, last use and recent outcomes. |

### Required MCP implementation contract

1. **Process isolation:** one launcher for stdio with sanitized environment,
   working directory, filesystem roots, process group, resource/output/time
   limits and full-tree cancellation.
2. **Network validation:** HTTPS by default; loopback exception only for local
   development; resolve and pin destination class; validate every redirect;
   reject credential-bearing URLs; enforce response limits on bytes read.
3. **Secrets:** secret handles, not secret values, in server configuration;
   purpose-bound delivery to one process/server; redaction before logs and model
   results; rotation and revocation receipts.
4. **Protocol coverage:** version negotiation; tools, resources, prompts and
   roots; server-initiated sampling/elicitation only through explicit owner-
   facing governance; incremental delivery and reconnection semantics; MCP Apps
   only in an isolated contributed-UI boundary.
5. **Tool projection:** per-server allowlist, schema validation, risk mapping,
   collision-safe names, result-size/content handling and provenance on every
   model-visible result.
6. **Supply chain:** source/publisher identity, immutable version/digest,
   signature or checksum, permission diff on update, vulnerability/advisory
   status and one-click revoke/contain.
7. **Monitoring:** health, latency, error rate, unusual tool/use pattern,
   network/secret violations and a hard distinction between “telemetry missing”
   and “containment unavailable”.

## 3.12 Projects

### Current strengths

- Projects can be managed or attached to an existing folder, with explicit
  writable choice.
- The detail view combines context/instructions, memory mode, files, sessions,
  tasks, checkpoints and provenance.
- Project hierarchy, drag/drop chat filing, archive, export and different delete
  language for managed versus attached folders are meaningful foundations.

### Findings

| ID | Priority | Finding | Recommendation |
|---|---:|---|---|
| UX-PROJ-01 | P1 | “New chat” from a Project does not set the selected work project before routing. | Pass an explicit project handoff or call the same selection contract used by Build. Keep Chat retrieval owner-wide while filing the new session to the project. |
| UX-PROJ-02 | P1 | Five card actions compete: Start Build, New chat, Archive, Move and Delete. | Use Open/Continue as primary, New work as secondary and move lifecycle actions into an overflow menu. |
| UX-PROJ-03 | P1 | Project detail is an information stack rather than a workspace overview. | Lead with Continue work, recent activity and needs attention; place files/tasks/sessions/checkpoints in tabs or grouped sections. |
| UX-PROJ-04 | P1 | Shared attachment IDs can appear as raw identifiers. | Resolve user-facing filenames/type/size; retain IDs only in provenance details. |
| UX-PROJ-05 | P1 | Archive is visible but a clear archive browser/restore journey is not. | Add Active/Archived filter with restore and retention behavior. |
| UX-PROJ-06 | P1 | Moving in a hierarchy needs cycle prevention and a clearer destination picker. | Use a real modal/tree, disable self/descendants and prove backend cycle rejection. |
| UX-PROJ-07 | P1 | Managed-project deletion is materially destructive. | Require step-up, typed project name, exact filesystem impact preview and recoverability statement. |
| UX-PROJ-08 | P2 | Session rows favor short IDs and are not an obvious continuation action. | Show title, last activity, mode and status; make the row open the conversation. |
| UX-PROJ-09 | P2 | “Active” can be confused with selected-for-current-work state. | Distinguish Current project, recently active and archived; use one authoritative work-project store. |

### Project continuity contract

Every cross-page action must pass a typed intent:

```text
project_id + destination + action(new/open/continue) + optional object_id
```

The destination resolves it server-side, confirms ownership and renders the
selected Project before the user submits work. Chat remains account-wide for
recall if that is the product rule; the session can still be filed to one
Project. Retrieval scope and organizational filing must never be represented by
the same ambiguous boolean.

---

# 4. Runtime convergence design

The requested features cannot work smoothly if each surface grows a private
execution path. Chat, Build, Tasks, Messaging, MCP, plugins and future device
nodes should all submit work through the same runtime contract.

```mermaid
flowchart TD
    A["Work request"] --> B["Identity and scope"]
    B --> C["Policy and approval"]
    C --> D["Runtime-issued authority"]
    D --> E["Isolated executor"]
    E --> F["Evidence and result"]
    F --> G["UI, task or channel delivery"]
```

## Runtime-issued execution context

Each action should receive an opaque, non-user-constructible context containing:

- authenticated principal and actor kind;
- account/project/session/turn/task scope;
- exact approved action hash and expiration;
- capability gate and decision outcome;
- selected runtime/environment identity and measured readiness;
- filesystem mount/read/write scope;
- network destination class and allowlist/grant;
- purpose-bound credential handles;
- CPU, memory, process, time, output and cost budgets;
- cancellation/process-tree handle;
- audit correlation and receipt requirements.

No executor should accept a caller-provided `approved=true`, a loose action
dictionary or a principal ID as a substitute for this context.

## Common runtime services

| Service | Consumers | Required behavior |
|---|---|---|
| Process launcher | Build shell, MCP stdio, plugins, local tools | Sanitized environment, sandbox, resource limits, process tree, cancellation, output caps. |
| Egress broker | Web, models, messaging, MCP, remote runtimes | Shared DNS/IP/redirect classification; per-capability policy; byte limits; receipts. |
| Credential broker | Models, Git, messaging, MCP, remote runtime | Opaque handles, least scope, short lease, no ambient inheritance, revocation and redaction. |
| Work scheduler | Tasks, background turns, retries, maintenance | Durable occurrence/claim ledger, idempotency, budgets, pause/recovery and delivery separation. |
| Session service | Chat, Build, channels, tasks, subagents | Origin, project filing, thread mapping, queue/interrupt behavior, compaction and restart recovery. |
| Evidence service | All actions | Content-safe event schema, source provenance, approval/authority receipt and user-readable summary. |
| Extension host | Skills, plugins, hooks, MCP | Namespaced config/state, compatibility, permissions, failure isolation and lifecycle cleanup. |

## Runtime profiles users can understand

Offer four primary environment types:

1. **This device** — local app-owned runtime; explicit project paths.
2. **Isolated container** — digest-pinned image; mount/network preview.
3. **My server** — SSH with verified host key, remote supervisor and scoped
   workspace.
4. **Managed remote** — named provider, cost limit, region and teardown policy.

The setup wizard should test prerequisites and show a one-sentence boundary.
Advanced fields expose fingerprints, ports, images, supervisors and network
rules. Unsupported environments must fail closed and never fall back silently to
the host.

---

# 5. Transferable feature catalogue

The external implementations demonstrate a broad feature set. Raiker should not
copy weak defaults or duplicate concepts. The table below translates useful
capabilities into Raiker's governed architecture.

## 5.1 Interaction and work

| Capability | Raiker today | Recommended Raiker form | Priority |
|---|---|---|---:|
| Rich terminal/TUI with streaming, multiline input and completion | CLI exists; web is primary; parity not established here | Optional client over the same gateway/session contracts, never a separate authority path | P2 |
| Interrupt, redirect and queue steering during a turn | Safe stop and some interrupt/routing foundations exist | Explicit Queue / Add context / Redirect / Stop actions with durable ordering | P1 |
| Retry, undo, branch and compress commands | Branch/checkpoint/rewind foundations exist | One Conversation menu with retry/branch/restore/compact and consequences | P2 |
| Parallel subagents | Subagent lifecycle exists in runtime evidence | Task graph with scoped child authority, budget, result handoff and parent settlement | P1 |
| Coding-agent closed loop | Substantial Build foundation | Prove change/test/diagnose/retry/verify on supported runtimes | P0/P1 |
| Background and scheduled work | Tasks support several cadences | Durable scheduler semantics, doctor, delivery ledger and missed-run policy | P1 |
| Kanban/standing work | Task hierarchy exists | Optional board view over the same task records; no second task system | P2 |
| Browser/computer use | Proposed/not reviewed as shipped | Narrow typed tools in isolated runtime; visible target and screenshot/action evidence | P2 |
| Device nodes: screen, camera, location, voice | Voice foundations exist; broad nodes not established | Paired device capability registry with per-device grants, foreground indication and instant revoke | P3 |

## 5.2 Models, context and learning

| Capability | Raiker today | Recommended Raiker form | Priority |
|---|---|---|---:|
| Broad local/private/hosted model providers | Strong multi-provider foundation | Compatibility matrix generated from live conformance tests | P1 |
| Profile-based routing and fallback | Global choice/fallback foundations exist | Named work profiles combining model, runtime, budget and privacy—not hidden provider IDs | P2 |
| Context-window compaction | Some context management exists; full user contract not reviewed as complete | Immutable user messages, bounded summaries, tool-call pairing, failure fallback and visible compaction event | P1 |
| Micro-compaction/prompt-cache optimization | Not established here | Optional measurable optimization with cost/quality telemetry and safe failure | P3 |
| Searchable session history with summaries | Conversation search/history exist | Local FTS repair, semantic opt-in, concise session summaries and direct anchors | P1 |
| Durable user model/personality | Personalisation and governed memory exist | Separate explicit user preferences from inferred memory; review and provenance for both | P1 |
| Proactive memory maintenance | Expiry/review foundations exist | Bounded background proposals only; never silent self-approval or deletion | P2 |
| Autonomous skill creation/self-improvement | Skill and proposal foundations exist | Draft → static scan → sandbox test → permission diff → owner approval → signed version | P2 |

## 5.3 Messaging and channels

| Capability | Raiker today | Recommended Raiker form | Priority |
|---|---|---|---:|
| Multiple chat/email channel adapters | Messaging connector registry exists | Adapter contract with shared inbound/outbound envelopes, pairing, media and delivery receipts | P1 |
| Cross-channel session continuity | Routing modes exist | Explicit bind/new-session choice; display where replies will go | P1 |
| Thread and group routing | Partial/unclear in UI | Stable session-key rules, mention/reply policy and group member visibility | P1 |
| Presence, typing and streaming previews | Not established | Optional adapter capabilities; degrade cleanly to final-only delivery | P2 |
| Voice messages and transcription | Local voice foundations exist | Channel media pipeline with consent, local/hosted disclosure and retention | P2 |
| Rich replies, buttons and approval cards | Exact approval relay exists | Signed one-time actions, expiry, fallback text and replay-safe outcomes | P1 |
| Webhooks and API ingress | Some ingress exists | Authenticated, signed, rate-limited, idempotent event gateway | P1 |
| Multi-account/multi-user routing | Product is primarily owner-scoped | Decide product boundary first; if added, bind actor/account/project/agent and isolate memory/credentials | P3/owner decision |

## 5.4 Extensions

| Capability | Raiker today | Recommended Raiker form | Priority |
|---|---|---|---:|
| Skills with command triggers | Implemented foundation | Versioned manifest, declared capabilities, provenance and compatibility status | P1 |
| Plugins with config and durable state | Implemented/partial foundation | Namespace jail, encrypted secrets, quotas, migrations and cleanup hooks | P1 |
| Lifecycle hooks/middleware | Some handlers remain unsupported | Typed ordered stages, timeouts, failure isolation and audit-safe payloads | P2 |
| MCP tools/resources/prompts | Tools strong; broader protocol partial | Complete protocol only through the same governance and projection contracts | P1 |
| Server-contributed UI | Proposed | Isolated origin/frame, narrow bridge, CSP, permission declaration and no ambient app credentials | P3 |
| Compatibility/migration import | Some migration concepts exist | Dry-run, source version, conflict preview, rollback bundle and secret exclusion | P2 |

## 5.5 Operations and reliability

| Capability | Raiker today | Recommended Raiker form | Priority |
|---|---|---|---:|
| Local gateway/control plane | Strong web/API/runtime separation | Formal versioned client contract for web, CLI, channels and future native clients | P1 |
| Restart recovery and clean-shutdown markers | Several recovery paths exist | System-wide recovery matrix for sessions, tasks, commands, MCP and deliveries | P1 |
| Queue depth, stuck-loop and pressure controls | Partial | Bounded queues, watchdogs, memory-pressure eviction and visible recovery reason | P1 |
| Content-safe observability | Strong event foundation | Enforce no-content/no-secret schemas at type and test level; export health independent from containment | P1 |
| Diagnostic “doctor” commands | Partial diagnostics | One support bundle with secrets/content excluded, plus subsystem-specific checks | P1 |
| Backup, migration and repair | Some setup/export flows exist | Versioned encrypted backup, restore drill, rollback compatibility and clean uninstall preservation | P0/P1 |
| App-owned portable dependencies | Windows closest; Linux/macOS incomplete | Ship only runtime dependencies, verify manifests, checksums and clean-machine operation | P0/P1 |

---

# 6. Security synthesis

## Security principles to preserve

- Owner authority does not mean model authority.
- Models, retrieved text, plugins, channels and MCP servers are untrusted inputs.
- Approval is necessary but not a sandbox.
- A stored approval is not permanent execution authority; re-govern at use time.
- Credentials are loaned for one purpose, not inherited from the host.
- Every child process and subagent stays inside the parent's scope and budget.
- Monitoring informs the owner; containment enforces. Failure of enforcement
  cannot be treated like optional telemetry loss.
- Reversible owner actions should be easy; privilege expansion and destructive
  actions require explicit review and, where appropriate, step-up.

## Threat-to-control matrix

| Threat | Required controls | Release evidence |
|---|---|---|
| Prompt injection from web/files/messages/tools | Untrusted-data labeling, instruction/data separation, tool authority outside model, output validation | Adversarial fixtures across Chat, Build, Messaging and MCP |
| Ambient credential theft by subprocess | Minimal environment, scoped secret handles, sandbox, redaction | Child process cannot enumerate host/provider/channel secrets |
| SSRF/DNS rebinding/redirect pivot | Shared resolver, IP class validation, DNS pin/recheck, redirect validation, port/scheme rules | Public→private redirect and rebinding tests |
| Approval replay or mutation | Action hash, one-time/expiring authority, actor/session binding, re-governance | Replay, changed-args and expired-decision tests |
| Channel spoof/replay | Signed body, timestamp/nonce, pairing, idempotency and sender binding | Duplicate, stale and forged events refused |
| Bot loops and runaway automation | Round/runtime/cost caps, loop detection, owner stop, task lease | Two bots and repeated webhook tests stop within bound |
| Extension supply-chain compromise | Immutable source/digest, signature/checksum, scan, permission diff, revoke | Tampered/update-permission-change fixtures |
| Cross-project/account leakage | Server-side scope, ownership checks, separate filing/retrieval concepts | Negative matrix for every read/write/search/export route |
| Sensitive telemetry | Content-free schema, field allowlist, redaction, local preview | Contract test rejects content/secret fields |
| Destructive project/memory action | Step-up, exact impact preview, typed confirmation, grace/backup where feasible | Restore/irreversibility acceptance tests |

## Security ideas not to copy

Do not adopt any external behavior that runs tools directly on the host by
default, treats an owner click as a substitute for isolation, allows plugins to
inherit all process secrets, merges external sender identity with the owner, or
lets autonomous learning publish its own new privileges. Raiker's governance
model is stronger when it remains the only authority plane.

---

# 7. Code quality and maintainability findings

## Large view modules

| File | Approximate lines | Risk |
|---|---:|---|
| `BuildView.svelte` | 3,311 | Layout, runtime, approvals, repository and streaming state are hard to change independently. |
| `ModelsView.svelte` | 3,235 | Five product journeys share one stateful module. |
| `ChatView.svelte` | 2,825 | Conversation, evidence, memory, speech, project and streaming concerns are coupled. |
| `ProjectsView.svelte` | 912 | List, hierarchy, destructive lifecycle and detail workspace are coupled. |
| `TasksView.svelte` | 837 | Creation, schedule semantics, runtime/model setup and run operations are coupled. |
| `MemoryView.svelte` | 812 | Five tabs and multiple record lifecycles share one module. |
| `CapabilitiesView.svelte` | 799 | Registry, filters, bulk actions and step-up flows are coupled. |
| `settings/SecurityLogin.svelte` | 764 | Multiple distinct security domains share one form/module. |

Large line count is not itself a defect. Here it correlates with multiple
independent state machines and makes regression ownership unclear. Refactoring
should follow domain boundaries already visible in the UI, with no behavior
change bundled into the extraction.

## Contract recommendations

1. Generate ordinary frontend request/response types from one backend API
   schema, while keeping security-sensitive validators explicit.
2. Make route/tab registries the source for navigation, guides, screenshots and
   accessibility smoke coverage.
3. Register every side-effecting executor and assert it requires runtime-issued
   authority.
4. Use shared lifecycle enums for task, delivery, MCP, model and runtime status;
   render unknown future values safely.
5. Separate user-facing labels from stable internal identifiers in every DTO.
6. Add component/domain contracts around extracted Svelte controllers before
   changing visual behavior.
7. Remove or explicitly quarantine dead/reserved UI such as the unregistered
   Storage page.

---

# 8. Detailed release gates

## Gate A — Identity and account

- No internal principal ID appears in ordinary UI or model prose.
- Display-name change, password change, MFA, recovery, device revocation and
  account deletion pass live tests.
- Single-owner and any supported delegated/channel identity are documented.

## Gate B — Authority and containment

- Repository-wide executor registry proves all side effects require opaque
  runtime authority.
- Approval mutation/replay/expiry and posture-change tests pass.
- Stop/pause reaches spawned process, MCP and subagent trees.
- Ambient environment and credentials are absent from child processes.

## Gate C — Install, update, repair and uninstall

- Fresh supported Windows, macOS and Linux machines without Python/Node/dev
  tools can install and start Raiker.
- Offline first launch works for the documented local path.
- Upgrade and rollback preserve encrypted workspace, account, projects, memory,
  tasks and key material.
- Repair replaces application files without deleting owner data.
- Uninstall clearly distinguishes application removal from workspace deletion.
- Package manifests prove no build/test tools, source credentials or caches ship.

## Gate D — Core user journeys

- First launch → choose model/privacy → Chat succeeds.
- Create Project → start Chat/Build/Design/Task → return to Project with every
  object filed correctly.
- Build completes a real change/test/retry/green loop.
- Design assets persist, version and export under the stated product scope.
- A task survives restart, approval pause, retry and delivery.
- Memory proposal → approval → recall → explanation → archive/delete works.

## Gate E — Models and runtimes

- Supported provider/runtime matrix is generated from real conformance runs.
- Connection, discovery, selection, outage, credential rejection, quota, context
  limit and fallback states have distinct messages.
- Container, SSH and managed remote boundaries pass negative tests and never
  silently fall back to the host.
- Cost/budget cutoff and cancellation are enforced under load.

## Gate F — Messaging and MCP

- Channel pairing, forged sender, replay, duplicate, group, thread, attachment,
  bot-loop, approval relay and delivery retry tests pass.
- MCP stdio environment isolation and full-tree stop pass.
- Remote MCP public/private/redirect/rebinding/body-limit tests pass.
- Protocol interoperability covers every capability Raiker advertises; absent
  features remain honestly absent.

## Gate G — UX, accessibility and evidence

- Keyboard-only, screen-reader and reduced-motion passes cover every route,
  dialog and destructive flow.
- 390px and 1920px light/dark screenshots are current; content-populated states
  are included, not only empty pages.
- Loading, empty, blocked, partial, error and recovery states are tested.
- No important verdict depends on color, hover or truncated text alone.

## Gate H — Supply chain and operations

- Dependency/advisory, secret scanning and SAST gates are active.
- Release inputs are immutable; third-party tools are pinned and checksummed.
- SBOM, signature and provenance/attestation are retained with releases.
- Backup/restore, database/FTS repair and support-bundle runbooks are exercised.
- Security response, key rotation and vulnerable-extension revocation are
  documented.

---

# 9. Implementation decision records

This section converts every material recommendation in the review into an
implementation-ready decision. These are **recommended product decisions**, not
claims that the work has been approved or implemented. The owner can accept,
amend or decline a record before engineering begins. Once accepted, its
acceptance criteria become the closure contract.

## 9.1 How to use these records

Every implementation PR should name one or more decision IDs and must include:

1. the user journey and failure states it changes;
2. the server-side authority or data contract it changes;
3. migration and rollback behavior;
4. security and privacy effects;
5. automated and live acceptance evidence;
6. documentation and screenshot updates.

Do not combine an unrelated visual redesign, database migration and runtime
security change merely because they appear in the same record. Land the smallest
vertically complete slice that has an honest UI and a fully enforcing backend.

## 9.2 Decision register

| Decision | Recommended disposition | Priority | Covers |
|---|---|---:|---|
| DEC-01 | Adopt | P0 | Owner display identity and internal principal isolation |
| DEC-02 | Adopt incrementally | P1 | Navigation, Needs attention and progressive disclosure |
| DEC-03 | Adopt | P1 | Permissions vocabulary and task-based presentation |
| DEC-04 | Adopt | P1 | Project continuity, filing and retrieval boundaries |
| DEC-05 | Adopt incrementally | P1/P2 | Chat simplification and module boundaries |
| DEC-06 | Adopt | P0/P1 | Build closed loop and execution-boundary presentation |
| DEC-07 | Adopt in stages | P1/P2 | Design asset, version, edit and canvas model |
| DEC-08 | Adopt | P1 | Models setup, selection hierarchy and comparison |
| DEC-09 | Adopt | P1/P2 | Settings popup and Settings information architecture |
| DEC-10 | Adopt | P1 | Account, privacy, security and destructive-action UX |
| DEC-11 | Adopt | P1 | Runtime setup wizard and authoritative runtime facts |
| DEC-12 | Adopt | P1 | Task scheduling, recovery, lifecycle and delivery |
| DEC-13 | Adopt | P1 | Memory lifecycle, age, review, usage and import |
| DEC-14 | Adopt | P1 | Messaging onboarding, routing, delivery and channel safety |
| DEC-15 | Adopt | P0/P1 | MCP onboarding, isolation, network trust and interoperability |
| DEC-16 | Adopt | P0 | Common authority, process, egress and credential services |
| DEC-17 | Adopt before public release | P0/P1 | Installer ownership, updates, rollback and provenance |
| DEC-18 | Adopt without behavior changes | P1/P2 | Large-view decomposition and contract generation |
| DEC-19 | Adopt as release gate | P1 | Accessibility, responsive, empty/error and evidence coverage |
| DEC-20 | Defer pending explicit owner decision | P3 | Multi-user/team mode and paired device expansion |

## DEC-01 — Separate presentation identity from authorization identity

**Decision:** Keep `principal_id` as the immutable security key and use a
server-resolved `display_name` for all ordinary UI and model-facing references
to the owner. Do not rename principal IDs or use display names in authorization
queries.

**Why:** The reported sentence exposes an internal identifier and teaches the
model that an authorization key is a human name. The account service already
holds the correct display name, so the missing part is propagation and output
hygiene rather than a new identity store.

**Implementation sequence:**

1. Add one server-side identity resolver that accepts an authenticated
   `principal_id` and returns a typed presentation object. It must never accept a
   browser or channel display name as trusted input.
2. Populate `UserMetadata.display_name` in web prompts, scheduled runs, channel
   ingress and approval continuation. Keep `UserMetadata.id` unchanged.
3. Add a trusted, bounded `user_identity` context item containing only the
   normalized display name and actor kind. Do not include username, email,
   principal ID or channel identifiers unless a tool specifically needs them.
4. Audit model-visible tool results, memory summaries, Project context,
   notifications and error text. Replace principal IDs with display labels; keep
   IDs in structured evidence.
5. Add an advanced Account diagnostic that can copy the principal ID with an
   explanation that it is an internal support/audit identifier.
6. Trace the exact reported phrase live. Capture the provider request context,
   tool result and rendered response with sensitive values redacted so closure
   proves the real path, not only the likely one.

**Contract and data decision:** Extend presentation DTOs rather than database
ownership keys. A display-name update affects future rendering only. Historical
audit events retain the principal ID and may retain the then-current display
label as non-authoritative metadata.

**Migration and rollback:** No ownership migration is required. Old records
without a display label render “Owner” in normal UI and remain resolvable by
principal ID internally. Rolling back presentation propagation must not alter
accounts or data scope.

**Verification:** Unit-test normalization and server-side resolution; contract-
test all four envelope construction paths; search rendered UI/evidence fixtures
for `principal_`; run the owner's reproduction through Chat, Build, Design
research, Tasks and Messaging.

**Done when:** No ordinary output exposes an internal ID, display-name changes
are reflected without changing ownership, and the original live symptom is
closed with captured evidence.

## DEC-02 — Organize the product as Work, Review and Manage

**Decision:** Preserve specialist pages but simplify first-level navigation into
three concepts: Work, Review and Manage. Create one aggregated Needs attention
view rather than placing every subsystem alert in permanent navigation.

**Why:** Raiker's depth is valuable, but every feature currently competes for
navigation weight. Users primarily need to start work, respond to something, or
change configuration.

**Implementation sequence:**

1. Extend the route registry with a stable `product_area`, `attention_provider`
   and `advanced` classification. Do not hard-code a second navigation list.
2. Keep Chat, Build, Design, Tasks and Projects in Work. Place approvals,
   proposed memories, failed/blocked tasks, disconnected services and security
   findings in a server-backed Needs attention feed.
3. Keep Models, Permissions, Memory, Messaging, Extensions and Settings under
   Manage/More, with search and recent destinations.
4. Define an attention-item contract with stable ID, severity, plain-language
   title, reason, originating object, primary action, timestamp and resolved
   state. It must contain references, not copied sensitive content.
5. Make each item deep-link to the exact record and mark itself resolved only
   from the authoritative subsystem state.
6. Preserve existing route aliases and browser history during navigation
   migration.

**Non-goal:** Do not merge approval, memory, task and security records into one
database lifecycle. Aggregate their projections while each subsystem remains
authoritative.

**Verification:** Registry tests ensure every route appears once; accessibility
tests cover keyboard and mobile navigation; contract tests ensure stale
attention items disappear after authoritative resolution.

## DEC-03 — Simplify Permissions without weakening its two-control model

**Decision:** Keep capability availability and decision mode separate. Present
them as “Can Raiker use this?” and “When Raiker wants to use it”. Standardize
decision words to `Ask me`, `Allow`, `Automatic` and `Never` throughout the
product.

**Why:** Combining the fields would weaken governance. Showing sixty-plus
technical rows first makes a correct system difficult to understand.

**Implementation sequence:**

1. Create one shared copy/enum map used by Permissions, MCP, composers,
   approvals, guides and tests. Remove local aliases such as `Ask` and `Deny`
   from owner-facing copy while preserving wire values through adapters.
2. Add registry metadata for user group, plain-language action, consequence,
   common example, risk tier and advanced status.
3. Default to Posture, Needs attention and Common task groups. Keep searchable
   All permissions as the complete authoritative registry.
4. Add non-authoritative presets that compile into a visible list of proposed
   individual changes. Never store a preset name as the enforcing decision.
5. Before applying bulk changes, show exact old/new effective state, which
   changes loosen authority, which require step-up and which active work may be
   interrupted.
6. After save, read enforcing state back from the server and show a receipt or
   partial failure per capability.

**Migration:** Existing gate and decision values remain unchanged. UI adapters
translate legacy labels. Deep links to a capability continue to open its row.

**Verification:** Exhaustive registry test, copy consistency test, preset
expansion test, step-up/bulk partial-failure tests, narrow-screen and screen-
reader passes.

## DEC-04 — Make Project continuity explicit and typed

**Decision:** Every Project action that opens Chat, Build, Design or Tasks must
send a typed work intent. Organizational filing and retrieval scope remain
separate fields.

**Why:** The current Project “New chat” action navigates without establishing
the Project. Chat's account-wide retrieval can remain intentional while the new
conversation is still filed to the Project.

**Implementation sequence:**

1. Define `WorkIntent { project_id, destination, action, object_id?, nonce }`.
   Prefer a server-created short-lived intent or validated route state over a
   freely trusted client object.
2. Projects creates the intent for New Chat, Start Build, Start Design, Plan task
   and Continue work.
3. The destination verifies ownership, consumes or idempotently reuses the
   intent, sets visible project context and files the new object on first
   persistence.
4. Store `project_id` as filing/ownership context. Store retrieval policy
   separately as `account`, `project` or another explicit scope; never infer it
   from whether a selector is visible.
5. Add Project breadcrumbs/backlinks to Chat, Build, Design and Task detail.
6. Replace raw attachment/session IDs with server-resolved display DTOs.
7. Add Active/Archived filtering and restore. Move archive/move/delete into an
   overflow menu.
8. Implement hierarchy move validation on the server: owner scope, target
   existence, no self-parent, no descendant cycle and one atomic update.
9. For managed deletion, enumerate filesystem/database effects, require recent
   step-up and typed project name, create a recoverable backup or state clearly
   why deletion is irreversible. Attached-folder removal must not delete the
   external folder.

**Migration:** Existing sessions/tasks/projects remain filed as stored.
Unassigned records stay unassigned. Do not silently infer projects from paths.
Old links without an intent open the destination with no project and an honest
label.

**Verification:** Cross-product matrix for new/open/continue across four
destinations; negative ownership and hierarchy tests; attached versus managed
deletion tests; reload/deep-link and two-tab behavior.

## DEC-05 — Simplify Chat and separate its state machines

**Decision:** Keep the normal Chat surface to transcript, one context line and
composer. Collapse evidence into a concise per-turn summary by default, while
retaining full source, tool and governance inspection.

**Implementation sequence:**

1. Characterize current behavior with tests before extracting code from
   `ChatView.svelte`.
2. Extract a session controller for load/new/branch/rewind/export and URL state.
3. Extract a turn-stream controller with explicit Idle, Submitting, Streaming,
   WaitingForApproval, Stopping, Completed and Failed states.
4. Extract turn rendering, source inspection, conversation actions, speech and
   background-work rail into focused components/services.
5. Render a settled evidence summary such as “3 tools · 2 sources · governed”;
   expansion shows the existing ordered evidence.
6. State Project filing and retrieval scope separately in the context summary.
7. Add visible count/error state to the background-work control and a labelled
   first-use affordance.
8. Preserve draft, attachments, selected model override and Project context on
   recoverable readiness failures.

**Non-goal:** Do not remove governance evidence, source provenance, branching,
memory correction or stopping behavior for visual simplicity.

**Verification:** Snapshot/state-machine tests for every turn state; stream
reconnect and cross-tab claim tests; keyboard/screen-reader flow; no regression
in source anchors, approvals, copy, speech, export and Project filing.

## DEC-06 — Make Build prove a closed governed coding loop

**Decision:** Treat Build readiness as an end-to-end runtime outcome, not the
presence of file, diff and terminal components. Present one authoritative Work
boundary summary and prioritize one inspector at a time.

**Implementation sequence:**

1. Create a server-returned `ExecutionBoundaryView` containing Project,
   repository, environment, model, writable roots, egress posture, credential
   grants, budget and readiness/refusal reason.
2. Render the view as Project → repository → environment → model. Client
   selectors propose a change; they do not independently declare the boundary.
3. Extract repository/file, conversation, approval review, artifact/preview,
   command output and responsive layout domains from `BuildView.svelte` after
   contract coverage exists.
4. Define panel priority: approval review overrides normal inspector; selected
   file/artifact/command occupies one inspector; switching preserves state.
5. Define the completion contract: requested change, changed files, commands
   run, tests and outcomes, unresolved failures, approvals used, checkpoint and
   final verification statement.
6. Ensure test failure returns to the model within the same bounded task until
   green, explicit stop, budget exhaustion or a truthful blocked state.
7. Add Project breadcrumb and persist the exact session/project/repository
   coordinate in the URL and server record.

**Verification:** Run representative repositories through read-only analysis,
single-file edit, multi-file edit, failed test/retry, approval rejection,
network-denied dependency attempt, stop and restart recovery. Evidence must show
no silent host fallback.

## DEC-07 — Build Design from durable assets upward

**Decision:** Do not create a cosmetic canvas first. Implement durable,
Project-owned asset/version lineage, then iteration/editing, then a canvas.

**Implementation sequence:**

1. Add `design_assets` with owner, optional Project, title, status, current
   version, created/updated time and deletion state.
2. Add immutable `design_asset_versions` with parent version, local blob/file
   reference, prompt, provider/model, normalized options, input references,
   provenance, safety/refusal metadata and generation receipt.
3. Require an explicit Project or visibly labelled Unfiled destination before
   generation. Store the destination server-side with the generation.
4. Add asset detail, version history, compare, favorite, revert-as-new-version,
   export and governed delete/restore.
5. Add reference inputs with a disclosure of which content will leave the
   device. Preserve research provenance and never silently feed research output
   into a provider.
6. Add variation and prompt reuse using the same immutable version contract.
7. Add mask/selection operations as new version-producing actions with bounded
   raster/vector payloads and exact parent lineage.
8. Add canvas documents only after versions are stable; store placements,
   layers and annotations separately from asset bytes.

**Migration:** Existing generations should import as Unfiled assets with one
version where the source record is complete. Records that cannot be resolved
remain viewable legacy history and are not fabricated into Projects.

**Verification:** Persistence across restart, Project filing, exact provider
disclosure, version/revert lineage, export fidelity, delete/restore and failure
without orphan blobs.

## DEC-08 — Make model selection a readiness journey

**Decision:** Ask where work may run before asking for a provider/model. Define
one selection hierarchy: global default, optional work/project default, and
explicit per-composer override.

**Implementation sequence:**

1. Split `ModelsView.svelte` along its existing Overview, My models, Add,
   Runtime and Usage boundaries without changing behavior.
2. Define a model readiness DTO separating connection configured, credentials
   valid, catalogue known, model selected, runtime reachable, capability support
   and current refusal.
3. In Add, start with On this device, Private server or Hosted service, then
   show compatible setup paths.
4. Add a comparison projection for locality, context capacity, tools, vision,
   image support, estimated cost, availability and privacy boundary. Unknown
   facts render Unknown, never a guessed default.
5. Label global selection “Default model”. Composer selection reads “This work
   uses …” and offers Reset to default.
6. Keep fallback order advanced. Validate each candidate's availability and
   capability at execution time and record why fallback occurred.
7. Use display labels everywhere; expose provider/profile IDs only in Advanced
   diagnostics.

**Migration:** Existing selected profile becomes the global default. Existing
composer values remain explicit overrides. Unknown catalogue entries remain
visible but unavailable until revalidated.

**Verification:** State matrix for no provider, connected/no catalogue,
catalogue/no selection, ready, outage, invalid credential, quota, unsupported
tools/vision and fallback. Test draft preservation through every setup path.

## DEC-09 — Clarify the Settings popup and Settings structure

**Decision:** Rename the mixed page launcher to **More** and reserve Settings for
configuration. Group routes as Work, Review, Connect and Settings. On mobile,
render navigation as a full-height sheet.

**Implementation sequence:**

1. Change route metadata, labels and accessibility names from “Settings &
   pages” to the agreed More/navigation term. Keep the gear only if it opens
   Settings directly; otherwise use a menu/grid icon and text tooltip.
2. Decide whether global command search owns page discovery. If yes, More shows
   stable groups and recent destinations; if no, More keeps search but uses the
   shared route index.
3. Mark current location, preserve keyboard focus/trap/return and support Escape
   and browser Back consistently.
4. On mobile, use a sheet with Back/Close, scroll containment and safe-area
   padding rather than a desktop-sized dialog.
5. In Settings, retain dirty-state rollback but add per-section save outcome and
   warn before navigation with unsaved changes.
6. Decide the unregistered Storage component explicitly: remove it as dead code
   or write a backed specification and register it later. Do not expose it until
   its API is real.

**Verification:** Route completeness, focus return, deep links, unsaved-change
navigation, mobile viewport/zoom, screen-reader landmarks and no duplicate page
entries.

## DEC-10 — Separate Account, Privacy and Security responsibilities

**Decision:** Split the dense Security page into Sign-in & devices, Secrets &
vault, Security findings and Standing access. Make Privacy answer “what leaves
this device?” and Account own presentation identity and account lifecycle.

**Implementation sequence:**

1. Move password, MFA, recovery and device sessions into Sign-in & devices.
2. Move encryption/vault/credential health and rotation into Secrets & vault.
3. Move scanner and containment findings into Security findings with severity,
   evidence, affected object, safe remediation and containment action.
4. Move standing grants into Standing access with capability, scope, creator,
   reason, last use, expiry and revoke.
5. Put emergency pause/containment at the Security landing page, state its exact
   scope and distinguish it from deleting configuration.
6. Build a Privacy data-flow summary for local models, hosted models, web,
   messaging, MCP and telemetry. Each line names data category, destination,
   retention and control link.
7. Make display name the main Account identity. Keep sign-in username and
   principal ID semantically distinct.
8. Require recent step-up and typed confirmation for account deletion; show
   exact data/files removed, external data not removed, backup/restore options
   and irreversibility.

**Migration:** Settings keys may remain stable behind new sections. Route aliases
must preserve old `?tab=security` links and focus the correct subsection.

**Verification:** Authorization and CSRF tests for every mutation, MFA/recovery
and session-revocation live tests, secret non-disclosure checks, privacy summary
contract tests and account-delete restore/irreversibility evidence.

## DEC-11 — Turn Runtime settings into a guided boundary setup

**Decision:** Offer four user-facing runtime types—This device, Isolated
container, My server and Managed remote—and keep fingerprints, ports, image
digests and raw egress in Advanced.

**Implementation sequence:**

1. Define a runtime-provider interface for probe, configure, verify, select,
   suspend, resume, delete and capability reporting.
2. The wizard first selects type, then prerequisites, connection details,
   filesystem/network/credential scope, cost/resource limits, verification and
   final boundary preview.
3. Verification must be measured server-side: executable/supervisor version,
   host key, sandbox features, filesystem probe, network enforcement,
   cancellation and cleanup. A configuration value is not proof.
4. Persist a versioned runtime profile and latest verification receipt. Mark it
   stale when relevant software, key, image, host or policy changes.
5. Render one readiness state and next action. Advanced shows exact refusal
   codes, host keys, network class and receipts.
6. Disabling a runtime stops new claims, requests bounded cancellation for
   active work and preserves evidence. Deletion requires no active references or
   an explicit migration choice.

**Non-goal:** Never fall back from an unavailable isolated/remote profile to the
host for convenience.

**Verification:** Clean local, unavailable daemon, changed SSH key, remote
supervisor mismatch, egress denial, cost exhaustion, cancellation, restart and
cleanup tests for every supported runtime type.

## DEC-12 — Define Tasks as a durable scheduler and run history

**Decision:** Separate timing from execution style, use a human schedule builder
and make each task open a durable occurrence/run timeline.

**Implementation sequence:**

1. Model task definition separately from occurrences and attempts. A definition
   holds objective, Project, method, schedule, policy and delivery; each
   occurrence has an idempotency key; each attempt has lease and outcome.
2. Present When as Now, Once or Repeating. Present Run mode separately as
   foreground/background if that distinction remains meaningful.
3. Store IANA timezone, local schedule expression, next occurrence, DST policy,
   start/end bounds and missed-run policy. Preview the next three occurrences.
4. Claim with a single bounded lease and heartbeat. On restart, reconcile
   expired claims and never execute one occurrence twice.
5. Record separate work and delivery states. A completed task with failed
   notification remains completed with Delivery failed.
6. Add bounded retry/backoff, maximum runtime/tool/cost limits and a visible
   incident after exhaustion.
7. Propagate pause/stop through child tasks, subagents and process trees.
8. Add a doctor/readiness endpoint for scheduler tick, clock/timezone, model,
   runtime, permissions and delivery target.
9. Open task detail as a timeline with next run, current action, approvals,
   attempts, outputs, delivery and audit evidence.

**Migration:** Convert existing recurrence values into the new schedule schema
with an explicit version. If conversion is ambiguous, preserve the old task as
paused and request review; never guess a future time.

**Verification:** DST forward/back, DST backward, host downtime, duplicate
claim, approval pause, restart, retry exhaustion, parent/child settlement,
delivery failure and owner cancellation.

## DEC-13 — Give Memory one explicit lifecycle and review policy

**Decision:** Use the lifecycle Observed → Suggested → Approved →
Reviewed/Expired → Archived → Deleted. Age raises review priority but does not
delete by itself.

**Implementation sequence:**

1. Publish one state-transition table and enforce it in the memory service.
   Define precisely whether Forget means archive/exclude or deletion; recommended
   UI is Archive for reversible exclusion and Delete permanently for erasure.
2. Add retention policy fields: policy kind, review/expiry time, last verified,
   last recalled, pin/hold, superseded-by and deletion grace time.
3. Calculate review priority from retention, sensitivity, use, verification,
   conflict, provenance and pin—not from one opaque score.
4. Add server-side recall-use receipts linking memory ID, session/turn, rank,
   reason and timestamp without copying the answer. Update counters atomically
   after actual context use.
5. Simplify cards to Edit, Pin and More. Put source, scope, expiry, history,
   archive and permanent deletion in a details drawer.
6. Translate confidence/trust into explainable labels and reasons. Raw values
   remain advanced diagnostic data.
7. Move embedding-engine configuration to Advanced/Models while Memory shows
   health, indexed/pending counts and one repair action.
8. Import into a staging batch; validate schema/version/ownership, classify
   source trust, detect exact and semantic duplicates, preview merge/skip/new,
   apply atomically and issue a reversible receipt where possible.
9. Run background maintenance only as proposals. It may suggest merge,
   supersession, expiry or deletion; it cannot approve itself or expand recall.

**Migration:** Map current approved/expired/archived records without changing
recall eligibility. Backfill use counters from available source ledgers only;
unknown stays unknown. Never fabricate provenance or last-used dates.

**Verification:** Full transition matrix, incognito, scope isolation,
contradiction, expiry/restore, source deletion, import rollback, recall receipt,
permanent deletion and backup behavior.

## DEC-14 — Make Messaging a guided, durable channel service

**Decision:** Users connect a Messaging account/channel through a wizard.
Connector is an implementation term under Extensions. Routing, pairing and
delivery use shared durable contracts.

**Implementation sequence:**

1. Define adapter capabilities: authentication method, DMs/groups/threads,
   streaming, media, reactions, edits/deletes, buttons, presence/typing and
   maximum payloads.
2. Build Connect channel: choose service, authenticate or enter an advanced
   secret reference, verify owner, discover/select conversations, choose routing
   policy, send/receive test, then enable.
3. Replace normal raw sender/conversation IDs with discovered labels plus IDs in
   Advanced. If discovery is unsupported, validate manual IDs with a test before
   enabling.
4. Persist inbound events before model execution with provider event ID,
   normalized sender/conversation/thread, signature time, content reference and
   idempotency result.
5. Verify signature, timestamp/nonce, account and pairing before routing. Pairing
   does not itself enable a channel or grant tools.
6. Map each inbound event to an explicit new/bound/side-question/interrupt
   decision. Show the bound session and reply destination.
7. Create outbound delivery records before send; update attempts, provider IDs,
   delivered/failed state and dead-letter review independently from task status.
8. Enforce per-sender/channel/global rate and cost limits, attachment bounds,
   malware/content scan hooks, outbound secret/PII checks and destination
   binding.
9. Detect bot loops using actor identity, repeated content/event lineage and a
   maximum automated-round budget. Activation in shared rooms is owner-only.
10. Provide Pause/Contain account that blocks new processing and delivery while
    preserving events and evidence.

**Migration:** Import existing connector profiles as disabled or current state
without inventing verified senders. Convert raw secrets to secret references
through an explicit rotation flow.

**Verification:** Adapter conformance suite plus forged/stale/duplicate events,
DM/group/thread routing, media limits, approval buttons, edit/delete, bot loop,
delivery retry/dead letter, pause and secret-redaction tests.

## DEC-15 — Put every MCP server behind explicit trust and isolation

**Decision:** All MCP transports use the common runtime services. Provide a
catalogue/plugin/manual Add server journey with a permission and trust preview.
Do not enable a server merely because its configuration parses.

**Implementation sequence:**

1. Route stdio through the common process launcher. Construct a minimal
   environment, fixed working directory, filesystem mounts, resource limits,
   output caps and full process-group cancellation.
2. Replace inline secrets/environment values with purpose-bound secret handles.
   Deliver only declared values to that server process and redact before
   persistence/model exposure.
3. Normalize remote endpoints and classify loopback, public and private/LAN.
   Require HTTPS except an explicit loopback development profile.
4. Resolve DNS, reject or explicitly grant private/link-local/metadata ranges,
   validate the connected peer where possible, revalidate every redirect and
   defend against DNS rebinding.
5. Enforce request/response limits on actual streamed bytes, decompressed bytes,
   event count, duration and reconnect attempts—not only headers.
6. Complete initialize/version negotiation and store advertised capabilities.
   Project tools/resources/prompts/roots separately; unsupported capabilities
   stay visible as unsupported and cannot be invoked.
7. Map each tool to a collision-safe name, JSON schema, capability/risk class,
   per-server allow state and result-content policy before showing it to a model.
8. Route sampling, elicitation and any server-initiated request through explicit
   governance and owner UI. Never treat it as the response to Raiker's request.
9. Separate monitor telemetry from containment health. Telemetry write failure
   may degrade observability; inability to enforce containment, limits or
   revocation must stop the call/session.
10. For catalogue/plugin installation, record source, publisher, immutable
    version/digest, signature/checksum and declared permissions. Updates show a
    permission diff and require review when authority grows.
11. The Add wizard shows server source, transport, endpoint/network class,
    processes, writable paths, secrets, projected tools and Permissions changes;
    then Test; then explicit Enable.
12. Add one-click Pause and Kill. Resume re-runs readiness, integrity and policy
    checks rather than restoring old trust blindly.

**Migration:** Existing servers remain configured but should enter `review
required` when their environment, endpoint trust, digest or projected authority
cannot be proven. Do not silently break local development servers; offer an
explicit loopback development classification.

**Verification:** Ambient-secret enumeration, filesystem escape, forked child
stop, oversized/decompression bomb, slow stream, redirect to private address,
DNS rebinding, metadata address, schema collision, malicious tool description,
server-initiated request, reconnect storm, monitor failure and update-permission
diff tests.

## DEC-16 — Require one opaque runtime authority context

**Decision:** Every side-effecting executor accepts a runtime-issued,
non-serializable authority context. Process, egress and credential access are
services on that context, not utilities a caller can invoke independently.

**Implementation sequence:**

1. Inventory every executor and entry path: web, CLI, Tasks, Messaging,
   approvals, plugins, hooks, MCP and subagents. Classify reads, reversible
   changes, external effects, destructive effects and critical actions.
2. Define `AuthorityContext` in the runtime authority package. Its constructor
   is private/internal; an issuer creates it only after identity, scope,
   capability, policy, approval and containment checks.
3. Bind the context to action hash, subject, scope, principal/actor, expiry,
   runtime profile, limits and audit correlation. It cannot be serialized and
   replayed as a bearer token.
4. Change executor interfaces to require the context. Remove direct helpers that
   can cause the same side effect without it or make them private to the
   executor.
5. Make process, network and secret broker methods require context-derived
   grants. A principal ID, boolean approval or client-supplied mode is
   insufficient.
6. Re-govern immediately before effect. Reject changed arguments, expired
   approval, changed posture, inactive containment or mismatched scope.
7. Issue a result receipt bound to action and authority, recording effect,
   runtime, limit use and cleanup without sensitive content.
8. Add a CI registry check: every real side-effect capability has an executor,
   threat model, Permissions description, authority requirement and negative
   bypass test.

**Migration:** Introduce adapters around current governed paths, migrate one
executor family at a time and keep a deny-by-default registry for unconverted
side effects. Do not retain a compatibility flag that bypasses authority.

**Verification:** Attempt direct calls from every entry path, forge context-like
objects, reuse expired/other-action contexts, change arguments and revoke posture
between approval and execution. All must fail before effect.

## DEC-17 — Make installers own the supported application runtime

**Decision:** Supported desktop installers carry or install into an app-owned,
versioned runtime and only the dependencies needed to run Raiker. Host Python or
developer tools are not release prerequisites.

**Implementation sequence:**

1. Define supported OS/architecture/version matrix and install scope per
   platform before packaging changes.
2. Resolve release dependencies from `uv.lock` or an exported hashed platform
   lock. Build in clean pinned images/runners with no resolver drift.
3. Bundle an app-owned interpreter/runtime and native dependencies under one
   package-owned directory. Do not write unmanaged launchers outside the package
   manifest.
4. Produce and verify a complete file manifest. Exclude tests, caches, source
   credentials, development tools and build-only dependencies.
5. Pin and checksum every external packaging tool; never fetch a mutable
   `latest`/`continuous` asset during a release build.
6. Separate application binaries from owner data, keys and workspace. Define
   paths and permissions for install, update, repair and uninstall.
7. Make update staged and atomic: download, verify signature/provenance, check
   compatibility/free space, stop safely, swap, migrate, health-check and roll
   back on failure.
8. Back up database/schema state before irreversible migration. Declare the
   oldest supported rollback and refuse unsafe downgrade honestly.
9. Uninstall removes package-owned files only by default. Workspace deletion is
   a separate step-up flow with exact preview.
10. Publish SBOM, checksums, signature, provenance/attestation and release notes
    beside each artifact.

**Verification:** Clean VMs with no Python/Node/toolchain; offline local first
launch; spaces/non-ASCII paths; standard and non-admin install where supported;
upgrade from previous release; interrupted update; repair; rollback; uninstall;
workspace preservation; artifact diff/reproducibility and malware-signing checks.

## DEC-18 — Decompose large UI modules around domain contracts

**Decision:** Refactor the largest Svelte views without changing behavior first.
Do not combine extraction with redesign unless a vertically complete user
outcome requires it.

**Implementation sequence:**

1. Record current public props, route/query state, API calls, events, stores,
   accessibility roles and visual states for each large view.
2. Add characterization tests for the behavior being moved.
3. Extract pure formatting/selectors first, then API/domain controllers, then
   presentational components. Keep one owner for each state machine.
4. Use generated API types for ordinary DTOs and explicit runtime validators at
   trust boundaries. Do not generate away security checks.
5. Extract by current product boundaries: Models tabs; Chat session/turn/source;
   Build repository/conversation/approval/artifact; Memory lifecycle tabs;
   Project list/detail/hierarchy; Security subsections.
6. Measure bundle size, render/update frequency and test duration before and
   after. A lower line count without clearer ownership is not success.
7. Remove obsolete code only after route, screenshot and repository searches
   prove it has no supported entry point.

**Verification:** Existing unit/E2E suite unchanged, route/deep-link parity,
keyboard/focus parity, no duplicate API requests, no lost draft/state and a
documented module ownership map.

## DEC-19 — Make accessibility and evidence release criteria

**Decision:** A release candidate is incomplete until populated and failure
states pass automated and manual accessibility/responsive review. Screenshots
are evidence, not the test itself.

**Implementation sequence:**

1. Generate the route/state matrix from the route registry: loading, empty,
   populated, blocked, error and recoverable states where applicable.
2. Run automated semantic/accessibility checks, then keyboard-only and screen-
   reader manual scripts for primary journeys and destructive dialogs.
3. Verify focus order, visible focus, dialog trap/return, landmarks, headings,
   names, live regions, reduced motion, zoom/reflow and color independence.
4. Capture current 390×844 and 1920×1080 light/dark screenshots from seeded,
   non-sensitive data. Include long names, many records and active errors so
   density/overflow defects are visible.
5. Store screenshot manifest with commit, viewport, theme, state/fixture and
   capture command. Do not treat historical screenshots as current product
   truth.
6. Add visual-diff thresholds for stable chrome and manual review for dynamic
   content. Never approve an inaccessible change because its pixels match.
7. Attach release evidence to the candidate commit, not a later branch.

**Verification:** Every supported route/state has a named result; all P0/P1
accessibility defects are closed or explicitly block release; screenshots carry
traceable metadata and contain no credentials or personal content.

## DEC-20 — Defer multi-user and paired-device expansion until explicitly chosen

**Decision:** Do not infer a team/multi-user product from Messaging or future
device nodes. Keep the current owner-scoped model until the owner approves a
tenancy, delegation and support model.

**Why:** Multi-user identity changes memory, Project, credential, approval,
notification, audit, deletion and legal/privacy boundaries. Device nodes add
camera, screen, location and device-local action risk. They cannot be safely
added as ordinary connectors.

**Decision required before implementation:**

- personal assistant with paired devices only, or collaborative workspace;
- tenant/account/workspace relationship and data controller;
- roles, invitation, removal and ownership transfer;
- per-user versus shared Projects/memory/credentials;
- whose approval authorizes which effect;
- channel sender-to-user binding and guest behavior;
- device enrollment, attestation, foreground indication and remote revoke;
- audit visibility, export, retention and deletion rights.

**If approved:** Write a separate threat model and schema migration, introduce
delegated scopes with deny-by-default cross-principal access, and require
negative isolation tests across every API and retrieval path before exposing the
feature.

---

# 10. Traceability from findings to decisions

| Review area/findings | Governing decision(s) |
|---|---|
| RR-IDENTITY-01 | DEC-01 |
| RR-AUTHORITY-01 | DEC-16 |
| RR-MCP-01, RR-MCP-02, SEC-MCP-01..03, UX-MCP-01..03 | DEC-15, DEC-16 |
| RR-INSTALL-01 | DEC-17 |
| RR-PROJECT-01, UX-PROJ-01..09 | DEC-04, DEC-10 |
| RR-DESIGN-01, UX-DESIGN-01..04 | DEC-07 |
| RR-VERIFY-01 | DEC-19 and the release gates |
| UX-PERM-01..05 | DEC-03 |
| UX-CHAT-01..05 | DEC-01, DEC-02, DEC-04, DEC-05, DEC-18 |
| UX-BUILD-01..05 | DEC-04, DEC-06, DEC-11, DEC-16, DEC-18 |
| UX-MODEL-01..05 | DEC-08, DEC-18 |
| UX-SETPOP-01..04 and all Settings-page recommendations | DEC-09, DEC-10, DEC-11 |
| UX-TASK-01..06 and automation reliability requirements | DEC-04, DEC-12, DEC-16 |
| UX-MEM-01..08 and memory-age/usage recommendations | DEC-13 |
| UX-MSG-01..06 and messaging security requirements | DEC-01, DEC-04, DEC-14, DEC-16 |
| Runtime convergence services | DEC-06, DEC-11, DEC-15, DEC-16 |
| Large view modules and contract recommendations | DEC-18 |
| Accessibility, responsive and screenshot evidence | DEC-19 |
| Multi-user and paired device proposals | DEC-20 |

Any finding added later must be assigned to a decision record or receive a new
one. This prevents recommendations from existing without an implementation and
closure contract.

---

# 11. Prioritized documentation backlog

This ordering is a recommendation, not an implementation claim.

## P0 — required before public alpha

1. RR-IDENTITY-01: separate internal principal identity from display identity.
2. RR-AUTHORITY-01: prove one mechanically exclusive authority path.
3. SEC-MCP-01: eliminate ambient environment inheritance.
4. RR-INSTALL-01: app-owned supported runtime and clean-machine proof.
5. Complete the release acceptance evidence bundle for the candidate build.

## P1 — required before public beta

1. Project handoff and full cross-surface continuity.
2. Remote MCP destination/containment hardening and guided onboarding.
3. Messaging wizard and durable secure delivery contract.
4. Task schedule/recovery/delivery timeline.
5. Memory lifecycle, age/review and usage simplification.
6. Models readiness and comparison journey.
7. Settings Security/Runtime decomposition.
8. Design asset/version foundation.
9. Build closed-loop and runtime negative acceptance suite.
10. Large-view domain extraction with behavior-preserving tests.

## P2 — strong v1 quality

1. Unified Needs attention queue.
2. Advanced conversation steering and compaction controls.
3. Rich channel capabilities with graceful adapter degradation.
4. Governed self-authored skills and background memory maintenance.
5. Optional board view and richer subagent/task graph.
6. Content-free operational monitoring and diagnostic doctor.

## P3 — post-v1 expansion

1. Paired device nodes and computer-use surfaces.
2. Server-contributed extension UI inside a dedicated isolation boundary.
3. Multi-user/team mode only after explicit product and tenancy decisions.
4. Advanced context/prompt-cache optimization after measurable baselines.

---

# 12. Recommended documentation set for implementation

Before implementation starts, split this review into authoritative, testable
specifications rather than letting one long audit become a permanent backlog:

1. `IDENTITY_PRESENTATION_AND_AUTHORITY_CONTRACT.md`
2. `COMMON_RUNTIME_EXECUTION_CONTEXT.md`
3. `PROJECT_CONTINUITY_AND_RETRIEVAL_SCOPE.md`
4. `MEMORY_LIFECYCLE_RETENTION_AND_USAGE.md`
5. `MESSAGING_CHANNEL_ADAPTER_AND_DELIVERY_CONTRACT.md`
6. `MCP_TRUST_ISOLATION_AND_INTEROPERABILITY.md`
7. `TASK_SCHEDULER_RECOVERY_AND_DELIVERY.md`
8. `RELEASE_CANDIDATE_ACCEPTANCE_MATRIX.md`

Each specification should contain state diagrams, API schemas, refusal codes,
threat cases, migration rules, UI copy, telemetry constraints and executable
acceptance tests. Close an item only from code plus passing evidence, not from a
document status label.

---

# Final assessment

Raiker's direction is coherent: one governed agent platform presented through
Chat, Build, Design, Tasks, Projects, Messaging and extensions. The strongest
parts are the approval/governance model, honest unavailable states, source and
action evidence, project-aware Build, memory review and breadth of runtime
concepts.

The simplest product is not a smaller Raiker. It is a Raiker that shows the goal
first, carries Project/model/runtime context automatically, presents one next
action when blocked, and keeps security depth in an inspectable second layer.
The runtime must then guarantee that every surface reaches tools, credentials,
networks and child processes through the same authority and containment plane.

Until the P0 gates and current live acceptance matrix are complete, publish as a
private technical preview rather than a stable first release. The green current
CI baseline is encouraging, but it is evidence of repository health—not yet
evidence that every advertised installation, identity, runtime and integration
boundary is ready for general users.
