# Raiker Page-by-Page Implementation Verification — 2026-09-07

## Follow-up — 2026-09-12 (later the same day)

First launch closed, which empties the P1 backlog of everything except the
workspace-shaped work.

| Conclusion | Now |
|---|---|
| 6. First Launch behaves like a configuration wizard | **Closed** — [FIXED-488](FIXED_ITEMS.md#fixed-488--first-launch-taught-infrastructure-before-it-taught-the-product). The stages are Welcome → Model → Privacy → Ready; FIRST-01's secure opening boundary is untouched |

Two defects found while verifying the new global catalogue against a live
provider, and closed with it:
[FIXED-489](FIXED_ITEMS.md#fixed-489--a-remembered-catalogue-outlived-the-connection-that-earned-it) —
disconnecting a provider left its models in every picker, which is the
disappearance defect GLOBAL-MODEL-08 exists to prevent, pointing the other way;
and
[FIXED-490](FIXED_ITEMS.md#fixed-490--a-composer-holding-eleven-choosable-models-said-none-was-set-up) —
a composer with eleven reachable models still told the owner to go and connect a
provider.

What remains in the backlog below is workspace-shaped: VIS2-12 (Build's
workbench composition), COMPOSER-10's remaining Tasks grammar, and the
Extensions and Observability hub passes.

**Follow-up 2026-09-13.** VIS2-19 is closed
([FIXED-491](FIXED_ITEMS.md#fixed-491--design-was-a-one-shot-generator-so-most-of-its-composer-had-nothing-to-reach)).
The image runtime it was blocked on was built first — a generation records what
it was made from — and Design composes a canvas around a selection. VIS2-11's
last clause closed with it: a picture is filed against the project it was made in
([FIXED-492](FIXED_ITEMS.md#fixed-492--a-generated-image-did-not-belong-to-the-project-it-was-made-in)).

## Follow-up — 2026-09-08

The Models, global web-read and environment/time/weather plans were reverified
end to end. Windows timezone data, Ollama cloud-label honesty, Project-scoped
draft continuity and reversible large pastes were corrected. The memory
capability's standing Allow now reaches the executor before the generic
approval queue, and survives a same-workspace server restart. Remaining page
findings below retain their prior status.

## Re-verification — 2026-09-07 (later the same day)

This document's first pass found eight conclusions. Five of them have since been
acted on, and this section records which — a verification document that does not
say when its own findings stopped being true is a snapshot pretending to be a
status.

| First-pass conclusion | Now |
|---|---|
| 7. current date/time/day/timezone is not proven as authoritative runtime context, and weather is not first-class | **Closed** — [FIXED-459](FIXED_ITEMS.md#fixed-459--nothing-in-raiker-told-a-model-what-day-it-was), [FIXED-460](FIXED_ITEMS.md#fixed-460--weather-was-a-page-to-interpret-rather-than-a-reading-to-report) |
| 8. global surface parity, readiness semantics and bounded extraction still need explicit implementation/tests | **Closed** — [FIXED-461](FIXED_ITEMS.md#fixed-461--four-derivations-of-one-fact-about-what-a-turn-can-read) |
| 3. Design is a real route but has no research layer of its own | **Closed** — Design is a prompt surface with a research protocol and the full read catalogue (WEB-06), and the canvas workspace (VIS2-19) landed 2026-09-13 on the image runtime it needed ([FIXED-491](FIXED_ITEMS.md#fixed-491--design-was-a-one-shot-generator-so-most-of-its-composer-had-nothing-to-reach)) |
| Models: MODEL-09 and MODEL-14 partial | **Closed** — [FIXED-462](FIXED_ITEMS.md#fixed-462--the-hugging-face-flow-did-all-six-steps-at-once), [FIXED-463](FIXED_ITEMS.md#fixed-463--come-back-and-press-look-again); the Models review is now complete end to end |
| 1, 2, 4, 5, 6 | Build's workbench pane (2) remains as first recorded. Home parity (1) closed 2026-09-07, the global model catalogue (4) and Permissions UX (5) on 2026-09-12, and First Launch (6) later the same day — see the follow-ups above |

Two findings this re-verification made on its own, both in the evidence harness
rather than the product, and both silent by construction: every live round had
been writing its captures outside the repository since the `apps/web` → `web`
move ([FIXED-464](FIXED_ITEMS.md#fixed-464--every-live-round-had-been-writing-its-evidence-outside-the-repository)),
and every live spec that connects a provider had been waiting for a tab the
Models redesign removed
([FIXED-465](FIXED_ITEMS.md#fixed-465--eighteen-live-specs-waiting-for-a-tab-the-redesign-removed)).
A sweep that reports success while writing nothing is worse than one that fails.

---

## Purpose

This document is the explicit implementation-verification companion to:

- `VISUAL_UI_UX_REVIEW_2026-09-06.md`
- the Models review
- `UNIFIED_COMPOSER_REDESIGN_2026-09-06.md`
- the global model-catalogue review
- the environment-context plan
- the global web-read plan

It answers four questions directly:

1. **Were the documented changes implemented correctly?**
2. **What is the implementation state page by page?**
3. **Is the Permissions page implemented and presented correctly?**
4. **Is the First Launch / onboarding experience implemented and presented correctly?**

The original 2026-09-06 review dates are intentionally preserved. They describe the product at the time of those reviews. This document records the later implementation-verification pass instead of rewriting history.

---

# Verification scale

Each area is classified as:

- **Correct** — the intended product/backend contract is substantially implemented as specified.
- **Mostly correct** — the important architecture is present, with bounded remaining work.
- **Partial** — meaningful implementation exists, but the documented target is not yet reached.
- **Incorrect / reopen** — the implementation conflicts with the newer product decision or a documented item is marked more complete than the code supports.
- **Open** — the intended capability/workspace is not yet implemented.

A `Done` label in an earlier plan is not accepted automatically. This review treats source behaviour as the deciding evidence.

---

# Executive assessment

The current product is materially stronger than the original review state. The main architectural work around shared composers, authoritative model decisions, governed approvals, Projects, Tasks, memory and work-surface navigation is real.

However, the implementation is not uniformly complete.

The most important conclusions are:

1. **Chat is the most complete primary Work surface.**
2. **Build is strong but still lacks the fully resolved artifact/workbench pane described in the visual review.**
3. **Design is a real first-class route with shared composer/model integration, but the intended canvas workspace remains open.**
4. **Models is substantially redesigned, but the current `Keep available`/curated availability path conflicts with the later global-catalogue decision and must be reopened.**
5. **Permissions is technically strong, but its information model is still harder to understand than necessary because capability availability and decision mode are presented as parallel control systems.**
6. **First Launch is secure and honest about runtime/store state, but still behaves too much like a configuration wizard and teaches some model concepts that the new global-catalogue design supersedes.**
7. **Current date/time/day/timezone is not yet proven as authoritative runtime context on every model turn, and weather is not yet a first-class structured capability.**
8. **`web_search` and `web_fetch` are core projected tools, but global surface parity, readiness semantics and bounded structured extraction still need explicit implementation/tests.**

---

# Cross-document implementation verification

## Visual review

| Area | Verification |
|---|---|
| Chat \| Build \| Design as peer Work modes | **Mostly correct** — shell/navigation recognises all three; Home/first-run still do not introduce them with equal clarity |
| Quiet/shared composer | **Correct** for Chat/Build and current Design generation flow |
| Persistent Project context | **Partial** — Project identity/context is carried, but there is no complete Project workspace shell spanning Chat/Build/Design/Tasks/Files/History |
| Build artifact pane | **Open/partial** — constituent views exist, final workbench composition remains open |
| Design canvas workspace | **Open** — the canvas remains prompt → generated image rather than Assets/Canvas/Inspector/Variations. Design's *research* layer landed 2026-09-07 (WEB-06): it is a prompt surface with the global read catalogue, and image generation gained no network authority from it |
| Secondary hub composition | **Partial** — Models improved substantially; Extensions/Observability/Settings remain more tab/admin oriented |
| Theme/4K/8K/overlay/badge sweep | **Partial/Open** according to existing review status |

## Models review

| Area | Verification |
|---|---|
| Selected vs effective model | **Correct** |
| Design persisted default | **Correct** in the newer surface model contract |
| Models IA: Overview / My models / Add model / Runtime & routing / Usage | **Correct** |
| Provider connections separated from runtime state | **Mostly correct** |
| Local library/runtime distinction | **Mostly correct** |
| Provider model discovery | **Correctly shaped** |
| All discovered compatible models globally available | **Incorrect / reopen** — `Keep available`/curated inventory still controls the set surfaced to composers |
| One global owner-level catalogue | **Partial** — shared frontend/model snapshot exists, but the authoritative inventory still derives through filtered/configured profile semantics |

## Unified composer review

| Area | Verification |
|---|---|
| Shared shell | **Correct** |
| Minimal default state | **Correct** |
| One Add menu | **Correct** |
| One Tools menu | **Correct** |
| Compact model/context identity | **Correct** on main Work surfaces |
| Chat composition | **Correct** |
| Build composition | **Mostly correct** |
| Design composition | **Partial** because the underlying Design runtime is still one-shot generation |
| Tasks/Schedule shared composer grammar | **Partial** |
| Project draft/work continuity | **Partial** |
| Build adaptive Run intents | **Partial/Open** |
| Large paste → compact attachment | **Partial/Open** |

---

# Page-by-page review

## 1. Home / Work Dashboard

### What is correct

Home is no longer a decorative landing page. It presents meaningful work state such as running work, standing agents, scheduled work, attention items and continuation paths.

This satisfies the earlier requirement that Home either become useful or be removed.

### What remains wrong/incomplete

The primary start-work vocabulary still does not consistently communicate:

```text
Chat | Build | Design
```

as the three peer Work modes.

If Home prominently offers Chat and Build but treats Design as secondary or absent, the shell and first-launch story disagree with the product model.

### Required improvement

Primary start-work area:

```text
Start work

Chat      Build      Design
```

Tasks/Agents/Projects can remain secondary workflow entries.

**Status: Done 2026-09-07.** Home's start area is the three Work modes as
peers, read from the same list the rest of the product reads (`workSurface.ts`,
`START_WORK`), each described by the object that mode is about. Tasks and
Projects follow on their own quieter row, which is what a workflow entry is.
Recorded as
[FIXED-484](FIXED_ITEMS.md#fixed-484--home-offered-two-of-the-three-work-modes).

---

## 2. Chat

### What is correct

Chat is currently the strongest implementation of the shared Work/composer contract.

It has the intended low-density composer grammar and integrates model selection, context, attachments, tools, citations, plans, approvals, sources, memory/context and task handoff without turning the default UI into an IDE toolbar.

### Remaining issue

The model picker still inherits the global-catalogue defect described in the Models/global-catalogue section: the visible inventory is not yet proven to be the complete owner-level compatible catalogue.

Time/date/weather global context also remains an open platform-level requirement rather than a Chat-only bug.

**Status: Correct with shared-platform dependencies.**

---

## 3. Build

### What is correct

Build appropriately retains mode-specific concepts such as repository context, diffs, files, command/tool activity, execution mode, approvals and plan state while sharing the composer grammar.

The page does not incorrectly force Chat's low-density spatial model onto a coding workspace.

### Remaining issue

The final documented workbench target remains incomplete:

```text
Repository | Conversation/Plan | Changes / Preview / Terminal / Runs
```

The constituent components exist, but the artifact/work object does not yet consistently dominate the third zone as a unified Build workbench.

### Required improvement

Finish VIS2-12 rather than adding more controls:

- automatic focus on changed artifact;
- integrated Changes/Preview/Terminal/Runs object model;
- preserve current repository/selection across Project/Build navigation;
- keep approvals contextual to the action.

**Status: Mostly correct / partial workbench.**

---

## 4. Design

### What is correct

Design is now a first-class Work route and uses the shared visual/composer grammar. It has its own model default and no longer needs to masquerade as Chat.

### What remains open

The documented Design target is not implemented:

```text
Assets/history | Canvas/selected object | Inspector/variations
                         Composer/create bar
```

Current behaviour is still fundamentally:

```text
prompt → generated image → prompt → generated image
```

rather than a persistent visual editing workspace.

Missing product capabilities include:

- persistent canvas;
- selected object/region;
- mask/inpaint;
- outpaint/extend;
- variations;
- reference assets;
- before/after/version compare;
- visual history;
- object/asset inspector;
- first-class Project asset history;
- Design planning/research layer using the global read-tool catalogue.

### Important rule

Do not add dead buttons before the runtime exists. The current omission of unsupported edit/outpaint/variation controls is preferable to fake UI.

**Status: Open at workspace level; foundations implemented.**

---

## 5. Threads

### What is correct

Threads now works as work-history/navigation rather than a generic search form. Search becomes contextual when a query exists, while the empty state presents existing work.

This is coherent with the broader Project/work-history direction.

### Remaining issue

Long-term Project integration should make Threads feel like a global aggregate of Project work rather than a separate mini-product.

**Status: Correct / minor future composition work.**

---

## 6. Tasks / Schedule

### What is correct

Task execution, recurrence, hierarchy, model selection, Project scope, approvals, progress and stopping semantics are real backend-backed capabilities.

### Remaining issue

Task creation still behaves more like a specialised form than the shared instruction grammar described in COMPOSER-10.

Recommended target:

```text
What should Raiker do?
[ instruction ]

[+] [Tools] [Model]

Run
○ Now
○ Once
○ Routine
○ Background

[ Create ]
```

Reveal recurrence/time fields only when the user selects the corresponding mode.

The new environment-context plan also requires execution-time timezone/date context to be regenerated at run time.

**Status: Functionally correct; UX partial.**

---

## 7. Projects

### What is correct

Projects now own real context: folders/files, task scope, conversation association, repository/build starting points and work organisation.

### Remaining issue

Project is not yet the full persistent Work shell envisioned by the visual review.

Target remains approximately:

```text
Project Raiker

Overview
Chat
Build
Design
Tasks
Files
Memory
Activity
```

Switching Chat → Build → Design should preserve Project identity/context without reconstructing it manually.

Design assets should become Project artifacts with versions/history.

**Status: Partial.**

---

## 8. Approvals

### What is correct

Approvals is one of Raiker's strongest product/security surfaces.

Correct behaviours include:

- Pending / Approved / Executed / Denied separation;
- risk ordering;
- immutable proposal detail;
- patch/diff preview;
- partial-hunk decision where supported;
- edited proposal becoming a new approval rather than mutating the approved object;
- receipts/outcomes;
- owner questions not disguised as approvals.

### Remaining issue

Only continued product-wide density/visual consistency work is needed. The core authority semantics should not be simplified away.

**Status: Correct.**

---

## 9. Messaging

### What is correct

External-channel content is treated as untrusted and cannot create authority. Pairing, routing, sender control, budgets and approval relays are meaningfully separated.

### Remaining issue

The page still exposes too much infrastructure/configuration detail in the primary experience.

Recommended hierarchy:

```text
Messaging

Connected channels
Needs attention
[ Add channel ]

Advanced / Troubleshooting
```

Environment variables, secret names and host-level wiring belong deeper unless the user enters advanced diagnostics.

**Status: Backend/security correct; presentation partial.**

---

## 10. Memory

### What is correct

Memory is feature-rich and governance-aware: approved memories, proposals, observations, source/provenance, expiry, pinning, editing, forgetting, embeddings/indexing and lifecycle controls are all present.

### Remaining issue

Too many lifecycle/administrative functions share one visual level.

Recommended composition:

```text
Memory
├ Overview
├ Memories
├ Suggestions
├ Sources
└ Recall & indexing
```

**Status: Done 2026-09-07.** Memory is a hub with exactly that composition —
Overview, Memories, Suggestions, Sources, Recall & indexing — and Overview
answers the two questions people arrive with: what Raiker can recall, and
whether anything is waiting on a decision. `memoryHub.ts` derives both, so the
Overview's counts and the tabs cannot disagree, and only decisions count as
attention: an expired memory has already stopped being recalled. Recorded as
[FIXED-485](FIXED_ITEMS.md#fixed-485--memory-kept-settings-records-and-decisions-at-one-visual-level).

---

## 11. Knowledge Map

### What is correct

The map is already spatial and uses graph interaction, inspectors, filtering, zoom/pan and saved positions rather than rendering graph data as card lists.

**Status: Correct.**

---

## 12. Models

### What is correct

The page has materially improved information architecture:

```text
Overview | My models | Add model | Runtime & routing | Usage
```

The selected/default/effective separation is substantially correct, as are provider connection and local-runtime distinctions.

### Critical reopen

The later owner decision supersedes the old curation concept:

> **Connect once. Discover once. Use everywhere.**

The current `Keep available`/configured-profile path must not determine whether a compatible discovered model exists in the composer inventory.

Correct model flow:

```text
connect provider/runtime
        ↓
discover all compatible models
        ↓
global owner catalogue
        ↓
Chat / Build / Design / Tasks / Schedule
```

Allowed organisational preferences:

- Recent;
- Pinned/Favourite;
- Hide from quick list;
- search/virtualisation.

But search must still reach the complete compatible catalogue, and Project membership must not partition the inventory.

**Status: Mostly correct, but global-catalogue availability contract must be reopened.**

---

## 13. Extensions

### What is correct

Connectors, MCP, Skills, Hooks and Plugins are real lifecycle-backed systems rather than decorative tabs.

### Remaining issue

The page still behaves like an admin taxonomy first.

Recommended composed overview:

```text
Extensions

Needs attention
Connected
Available

[ Add extension ]
```

Then drill down to connector/MCP/plugin categories.

**Status: Functionally correct; hub composition partial.**

---

## 14. Observability

### What is correct

The Overview answers useful operational questions: readiness, attention, change and evidence. Healthy state is less aggressively green than the earlier UI.

### Remaining issue

The page remains a conventional multi-tab observability hub. That is acceptable functionally but not yet the final composed-hub target from VIS2-10.

**Status: Correct content; composition partial.**

---

## 15. Settings

### What is correct

Settings has grouped navigation, explicit save/discard state, rollback behaviour for failed writes and clearer section ownership.

### Remaining issue

It remains an administration surface, which is acceptable, but low-level configuration should continue moving into Advanced/Troubleshooting where possible.

The new environment-context plan should add/confirm:

```text
Timezone
Default weather location (optional)
```

without turning Settings into a runtime diagnostics page.

**Status: Mostly correct.**

---

# Dedicated Permissions review

## Current security implementation

Permissions is technically meaningful. It reads real capability-gate state and performs governed mutations. It supports effective state, decision mode, enable/disable transitions, step-up/human confirmation for sensitive capability classes, search/grouping and explanatory state.

The implementation also correctly handles an important default-state edge case: an empty persisted row does not always mean `Off`. In particular, a capability such as `web_fetch` may resolve from a shipped default, and the page can distinguish `on by default` from an explicit persisted decision.

This is correct and should be preserved.

## Main UX problem

The page exposes two concepts with nearly equal visual weight:

```text
Capability availability
On / Off

Decision mode
Ask / Allow / Auto / Deny
```

Those are valid backend concepts, but they are not self-explanatory when placed side by side.

A user can reasonably ask:

- How can a capability be On and Deny?
- What does Off + Ask mean?
- Is `Allow` another way to turn it on?
- What is the difference between `On`, `Allow` and `Auto`?

## Recommended product language

Frame the controls as two questions.

### 1. Can Raiker use this capability?

```text
Availability
On
Off
```

### 2. What should happen when Raiker wants to use it?

```text
Behaviour
Ask me
Allow
Automatic
Never
```

Internally, `Never` may remain `deny`; the UI should prioritise owner meaning.

## Recommended row

Collapsed:

```text
Run shell commands
On · Ask me                                      ›
```

Expanded:

```text
Run shell commands
Allows Raiker to execute governed commands.

Availability
○ Off
● On

When Raiker wants to use it
● Ask me
○ Allow
○ Automatic
○ Never

Advanced
Effective runtime state
Last changed
Audit/history
```

## Overview hierarchy

Do not begin with dozens of equally weighted capability cards.

Recommended:

```text
Permissions
What Raiker can do and when it must ask you.

Needs attention
...

Common permissions
Web access              On · Ask
File changes            On · Ask
Run commands            On · Ask
Git push                On · Ask
External connectors     On · Ask

All permissions
Workspace
Network
Models
Connectors
MCP
Automation
...
```

## Technical language

Move terminology such as the following to Advanced/diagnostics unless the owner is explicitly inspecting internals:

```text
principal
enabled_runtime
gate resolution
runtime level
```

Prefer owner-facing wording:

```text
This setting cannot be changed for this account.
```

instead of:

```text
not permitted for your principal
```

## Bulk changes

If the safe bulk operations are intentionally limited to `Ask` and `Deny`, describe the action as tightening/reviewing permissions rather than implying every property can be bulk-edited.

## Security invariant

Do not simplify the UX by weakening the authority model.

The UI may become clearer, but the backend must preserve:

> No model, agent, subagent, memory, retrieved document, plugin, MCP server, connector, tool result, scheduled task or external message may create, expand, transfer or exercise authority. Authority may only originate from authenticated human policy or explicitly delegated bounded auditable runtime grant.

**Permissions status: Done 2026-09-07.** The page asks the two questions in the
order their answers depend on — *Can Raiker use this?* then *When Raiker wants
to use it* — and speaks the owner's vocabulary for the second (`Ask me`,
`Allow`, `Automatic`, `Never`), while the store keeps `deny` and every other
mode exactly as it was. A closed row states both facts, so the list can be
scanned; the handful an owner comes to change sits above the registry; and
"not permitted for your principal" is now a sentence about their account.
Nothing in the authority model moved. Recorded as
[FIXED-486](FIXED_ITEMS.md#fixed-486--two-parallel-systems-where-there-were-two-questions).

---

# Dedicated First Launch / onboarding review

## What is correct

The first-launch path correctly separates:

```text
Authentication
Runtime reachability
Encrypted store availability
Runtime verification
```

The workspace remains unavailable until authentication and runtime/bootstrap checks succeed. This fail-closed behaviour is correct.

The opening state can also distinguish a fresh owner-registration state from an existing-owner unlock flow rather than presenting the same form in every situation.

## Main product problem

After the secure opening state, onboarding still behaves too much like a configuration wizard.

The current conceptual flow is approximately:

```text
Create owner / Unlock
Verify runtime
Account
Model
Privacy
Backup
Finish
```

That asks the owner to understand infrastructure before they have experienced the product.

## FIRST-01 — Preserve the secure opening boundary

**Priority: P0**

Keep:

- runtime unreachable state;
- encrypted-store unavailable state;
- owner registration vs unlock distinction;
- MFA/recovery where configured;
- bootstrap verification before mounting the workspace;
- authenticated-session restoration on refresh.

Do not collapse these into one generic `Login failed` path.

## FIRST-02 — Remove redundant Account stage after owner creation

**Priority: P1**

If the owner account is already created on the first screen, the setup wizard should not show `Account` as though another account-configuration step is required.

## FIRST-03 — Teach the product model before configuration

**Priority: P1**

The first experience should establish:

```text
Chat | Build | Design
```

Example:

```text
Meet Raiker
Your governed AI workspace for Chat, Build and Design.
```

The owner should know what the product is before choosing provider/runtime details.

## FIRST-04 — Separate provider connection from model default

**Priority: P1**

Do not teach:

```text
connect provider
→ keep selected models available
→ choose model
```

The intended architecture is:

```text
connect provider/runtime
→ discover all compatible models globally
→ choose a default
```

This means first launch must change together with the global model catalogue and removal of `Keep available` as a visibility gate.

## FIRST-05 — Progressive model setup

**Priority: P1**

Do not begin with the full provider matrix.

Prefer:

```text
Choose how Raiker should think

Recommended
[ easiest detected/connected path ]

Other options
Anthropic
OpenAI
Ollama
LM Studio
Local GGUF / MLX
ChatGPT subscription
More...
```

Advanced provider management remains available but is not the default first-run experience.

## FIRST-06 — Do not require leaving onboarding for the Models page

**Priority: P1**

The normal onboarding flow should be sufficient to connect a provider/runtime and select a default. `Open full Models page` should not be required as an escape hatch.

Use `Advanced setup` if deeper configuration is genuinely needed.

## FIRST-07 — Privacy should describe data travel, not authority

**Priority: P1**

Avoid ambiguous modes where `Privacy` can be mistaken for the Permissions/authority system.

Prefer a question such as:

```text
Where may Raiker send model requests?

Local only
Local + providers I connect
```

Permissions still govern what actions Raiker may take.

## FIRST-08 — Backup should be recommended, not an equal blocking stage

**Priority: P1**

Backup is important, but asking for local/removable/NAS paths before the owner has used Raiker increases first-run friction.

Prefer post-onboarding Home recommendation:

```text
Recommended setup
Protect your workspace with a backup.
[ Set up backup ]
```

## FIRST-09 — Finish into work, not administration

**Priority: P1**

Final screen should reinforce the product model:

```text
Your Raiker is ready.

[ Chat ]   [ Build ]   [ Design ]
```

Optional setup:

```text
Create backup
Review privacy
Review permissions
```

Use `Start using Raiker` rather than legacy vocabulary such as `Open Workbench` if the rest of the product calls the destination Home/Work.

## FIRST-10 — Do not put the full Permissions matrix into onboarding

**Priority: P1**

A concise statement is enough:

```text
Raiker starts conservatively and will ask when governed actions need your decision.
```

Link to Permissions after onboarding rather than asking the user to configure dozens of gates on first launch.

## FIRST-11 — Environment context should require almost no onboarding

**Priority: P1**

Timezone may be detected/proposed, but the user should not have to configure Clock/Date manually.

The runtime should own current time/date/day. Weather location may remain optional until weather is requested.

**First Launch status: Security foundation correct; onboarding information architecture should be simplified.**

---

# Environment/time/weather verification

The separate environment-context plan is required because current implementation cannot yet be described as proving that every model-backed turn receives authoritative:

```text
current UTC
owner-local time
IANA timezone
local date
day of week
```

Likewise, weather is not yet a first-class structured capability with explicit source/freshness semantics.

These are platform-level requirements, not Chat-specific features.

**Status: Closed 2026-09-07.** Every model-backed turn now receives a
runtime-derived bundle carrying current UTC, owner-local time, the IANA
timezone and where it came from, the local date and the day of week — injected
as trusted metadata separate from the untrusted workspace block, recorded as an
`environment_context` event, and derived per turn so a scheduled run and a
delegated subagent each read the clock rather than inherit one. Weather is a
structured read with `observed_at`, forecast validity and `fetched_at` kept
apart and a typed `fresh`/`stale`/`unavailable` state. See
the environment-context plan,
[FIXED-459](FIXED_ITEMS.md#fixed-459--nothing-in-raiker-told-a-model-what-day-it-was)
and
[FIXED-460](FIXED_ITEMS.md#fixed-460--weather-was-a-page-to-interpret-rather-than-a-reading-to-report).

---

# Web-read/search/extraction verification

Current architecture correctly places `web_search` and `web_fetch` in the core projected model-tool set. Tool projection is not an authority grant.

What still needs explicit implementation/verification:

- one canonical global read-tool contract across every agentic surface;
- readiness semantics for web search/provider configuration;
- no Project-specific fragmentation;
- structured bounded `web_extract`;
- Design research-agent integration;
- explicit static-fetch → interactive-browser escalation boundary;
- parity and fail-closed regression tests.

**Status: Closed 2026-09-07.** One typed contract
(`raiker/runtime/read_capabilities.py`) is what every agentic surface derives
from; a subagent receives the delegable subset and administrative pages receive
nothing. `web_extract` adds bounded structured extraction over the same safe
fetch, with explicit truncation and a typed `static_content_insufficient` that
authorises no browser. Readiness is a typed state separate from authority, from
one shared snapshot so a still-mounted composer updates without a reload. The
fail-closed half is asserted directly: every read still refuses when the gate is
off. See the global web-read plan and
[FIXED-461](FIXED_ITEMS.md#fixed-461--four-derivations-of-one-fact-about-what-a-turn-can-read).

---

# Corrected active backlog

Priority outranks effort. Within the same priority, lower effort comes first.

## P0

1. ~~**ENV-01** authoritative per-turn time/date/timezone context.~~ Done 2026-09-07.
2. ~~**ENV-02** one owner-level timezone source of truth.~~ Done 2026-09-07.
3. ~~**ENV-03** fresh environment context at scheduled execution time.~~ Done 2026-09-07.
4. ~~**ENV-04** environment-context parity across all agentic surfaces.~~ Done 2026-09-07.
5. ~~**WEB-01** canonical global read-tool contract.~~ Done 2026-09-07.
6. ~~**WEB-02** surface parity regression coverage.~~ Done 2026-09-07.
7. ~~**WEB-03** prove projection never bypasses authority/policy.~~ Done 2026-09-07.
8. ~~**GLOBAL-MODEL-01/02** authoritative owner-level model catalogue consumed by all composers.~~ Done 2026-09-12 ([FIXED-487](FIXED_ITEMS.md#fixed-487--a-catalogue-that-existed-only-as-long-as-the-response-carrying-it)).
9. ~~**GLOBAL-MODEL-06** remove `Keep available` as a normal availability gate.~~ Done 2026-09-12 ([FIXED-487](FIXED_ITEMS.md#fixed-487--a-catalogue-that-existed-only-as-long-as-the-response-carrying-it)).

## P1

1. ~~**Permissions UX redesign** — Availability + Behaviour with progressive disclosure; preserve backend semantics.~~ Done 2026-09-07 ([FIXED-486](FIXED_ITEMS.md#fixed-486--two-parallel-systems-where-there-were-two-questions)).
2. ~~**FIRST-02 through FIRST-10** simplified first launch/onboarding.~~ Done 2026-09-12 ([FIXED-488](FIXED_ITEMS.md#fixed-488--first-launch-taught-infrastructure-before-it-taught-the-product)).
3. ~~**VIS2-19** Design canvas/workspace.~~ Done 2026-09-13 ([FIXED-491](FIXED_ITEMS.md#fixed-491--design-was-a-one-shot-generator-so-most-of-its-composer-had-nothing-to-reach)) — the image runtime first, the canvas on top of it.
4. ~~**VIS2-12** Build artifact/workbench pane.~~ Done 2026-09-07 ([FIXED-467](FIXED_ITEMS.md#fixed-467--builds-third-pane-showed-tools-not-the-work)).
5. ~~**VIS2-11** persistent Project workspace/context.~~ Done 2026-09-07 ([FIXED-469](FIXED_ITEMS.md#fixed-469--the-project-was-chosen-again-on-every-surface)).
6. ~~**COMPOSER-10** Tasks/Schedule shared composer grammar.~~ Done 2026-09-07 ([FIXED-470](FIXED_ITEMS.md#fixed-470--tasks-asked-to-be-filled-in-rather-than-instructed)).
7. ~~**WEATHER-01/02/03** structured weather + optional location + freshness.~~ Done 2026-09-07.
8. ~~**WEB-04 through WEB-08** search readiness, `web_extract`, Design research integration, shared readiness update, browser escalation.~~ Done 2026-09-07.
9. ~~Home start-work parity for Chat/Build/Design.~~ Done 2026-09-07 ([FIXED-484](FIXED_ITEMS.md#fixed-484--home-offered-two-of-the-three-work-modes)).
10. ~~Extensions/Observability composed-hub pass.~~ Done 2026-09-07 ([FIXED-468](FIXED_ITEMS.md#fixed-468--extensions-opened-on-a-category-instead-of-on-what-raiker-can-reach)); Memory joined them ([FIXED-485](FIXED_ITEMS.md#fixed-485--memory-kept-settings-records-and-decisions-at-one-visual-level)).

## P2

1. ~~Memory hub composition.~~ Done 2026-09-07 ([FIXED-485](FIXED_ITEMS.md#fixed-485--memory-kept-settings-records-and-decisions-at-one-visual-level)).
2. ~~product-wide badge/attention/overlay sweep.~~ Done 2026-09-07 ([FIXED-472](FIXED_ITEMS.md#fixed-472--every-row-wore-the-same-weight-as-the-row-that-needed-you), [FIXED-474](FIXED_ITEMS.md#fixed-474--thirteen-z-index-numbers-and-no-way-to-say-what-was-above-what)).
3. ~~theme-specific optical passes.~~ Done 2026-09-07 ([FIXED-481](FIXED_ITEMS.md#fixed-481--one-elevation-for-two-grounds-and-a-picture-inside-a-card)).
4. ~~4K/8K composition validation.~~ Done 2026-09-07 — verified at 3840×2160 ([FIXED-481](FIXED_ITEMS.md#fixed-481--one-elevation-for-two-grounds-and-a-picture-inside-a-card)).
5. ~~provenance/diagnostic visibility for environment/web-read state.~~ Done 2026-09-07 — `GET /api/environment` and `GET /api/read-capabilities`.

---

# Required documentation-state corrections

The following earlier labels should be interpreted carefully:

| Earlier item | Correct current interpretation |
|---|---|
| VIS2-03 Chat/Build/Design Done | **Mostly correct** — core shell done; Home/first-run parity still needs work |
| VIS2-11 Project context Partial | **Correct** |
| VIS2-12 Build artifact pane Open | **Correct** |
| VIS2-19 Design canvas Open | **Correct when written; closed 2026-09-13** ([FIXED-491](FIXED_ITEMS.md#fixed-491--design-was-a-one-shot-generator-so-most-of-its-composer-had-nothing-to-reach)) |
| COMPOSER-10 Tasks/Schedule Partial | **Correct** |
| COMPOSER-11 Project continuity Partial | **Correct** |
| MODEL global availability / old Keep available behaviour | **Reopen under later global-catalogue decision** |
| Permissions backend | **Correct** |
| Permissions UX | **Needs focused redesign** |
| First Launch security boundary | **Correct** |
| First Launch onboarding flow | **Closed 2026-09-12** (FIXED-488) — Welcome → Model → Privacy → Ready |
| authoritative environment clock/date/day/timezone | **Closed 2026-09-07** (FIXED-459) |
| structured weather | **Closed 2026-09-07** (FIXED-460) |
| global web-read parity | **Closed 2026-09-07** (FIXED-461) |

---

# Definition of done

This page-by-page verification is resolved when:

1. every primary and secondary page has a clearly documented implementation state;
2. earlier `Done` labels no longer hide later product-decision conflicts;
3. Permissions presents the existing authority model in clear owner language without weakening enforcement;
4. First Launch is secure, progressive and teaches Chat/Build/Design before infrastructure;
5. model availability follows one global owner catalogue;
6. current time/date/timezone is runtime truth on every agentic turn;
7. weather is structured, sourced and freshness-aware;
8. web read/search/extraction is globally discoverable across agentic surfaces while remaining governed;
9. Design and Project workspace gaps are not mislabeled as complete.

The product-level standard is:

> **Raiker should be simple at the point of use, explicit at decision boundaries, and technically honest about what is selected, available, ready, permitted, current and actually executed.**
