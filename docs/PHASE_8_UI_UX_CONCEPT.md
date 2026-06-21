# Phase 8 — UI & Channels: UI/UX Design Concept

> **Status: design concept — specified/deferred, not implemented.** This document is a forward-looking
> Phase 8 ("UI and Channels") UX proposal derived from the foundation docs `docs/foundation/01_PRD.md`
> through `docs/foundation/11_DIRECTORY_STRUCTURE.md`. It describes intended screens and behaviour; it
> does not change current implementation status. The current launchable UI is a local terminal client
> (plain local terminal client only; Rich/native TUI deferred to Phase 8); Desktop/Web/Dashboard/Mobile/IDE/REST surfaces remain
> specified/deferred. Runtime execution remains disabled, and **no UI surface ever executes tools
> directly** — every client routes through the Agent Gateway → Session Manager → Agent Runtime → Tool
> Broker → Policy Engine. Canonical status lives in `docs/IMPLEMENTATION_STATUS.md`.

## Context

Why this document exists: Raiker's foundation defines a daemon-plus-equal-status-clients architecture
where "the user can ask for work from any interface" (`01_PRD.md` §2, PR-001) and every client speaks
the same `PromptEnvelope` in and the same `AgentEvent` stream out (`02_SPEC.md` §2.2, `10_AGENT_CONTRACTS.md`).
Phase 8 of the design roadmap (`04_ROADMAP.md`) is "UI and Channels": Rich TUI, a Desktop/Web UI MVP,
a REST API, a webhook receiver, and chat/voice/hotkey connector stubs. The challenge is that Raiker is
a *governed* agent — it classifies risk, plans, asks permission, verifies, logs everything, and governs
memory (`01_PRD.md` PR-002/PR-008/PR-009, `06_SECURITY_MODEL.md`). A naive UI would drown the user in
that machinery. The intended outcome is an interface where all of that governance is **present but
quiet**: legible when it matters (a high-risk permission prompt), invisible when it does not.

Design philosophy applied throughout:

1. **Radical simplicity / low cognitive load** — one primary surface (the conversation), governance
   rendered as inline cards rather than separate apps, advanced configuration behind progressive
   disclosure.
2. **Intuitive, frictionless workflows** — the primary value ("ask for work") is the first thing you
   see and is reachable in zero-to-one clicks; a command palette gives power users everything else.
3. **Utilitarian aesthetics** — crisp typographic hierarchy, a focused palette that is *semantic*
   (color encodes risk and trust, not decoration), and motion used only as feedback for real state
   changes in the agent loop.

These three principles are not decorative: each maps to a concrete architectural fact, summarized in
the [Evaluation](#evaluation--why-this-stays-simple) section.

---

## A. Architectural Alignment & User Journeys

### A.1 Feature → screen mapping

Every Phase 8 screen is a *view onto the same event-sourced runtime*. The table maps foundation
requirements to user-facing surfaces and to the contracts that feed them.

| Foundation source | Capability | Primary screen / component | Backing contract |
|---|---|---|---|
| PR-001, `02_SPEC` §2.2, `03_ARCH` §2.1 | Equal-status interfaces; same envelope/event everywhere | **Conversation** (shared across CLI/TUI/Desktop/Web) | `PromptEnvelope`, `AgentEvent` |
| PR-002, `02_SPEC` §4 | Bounded, interruptible agent loop (13 states) | **Turn Stream** with state ribbon + Pause/Steer/Cancel | `AgentEvent.event_type`, state-skipped events |
| PR-002 (planning), `07_PROMPT_FILES` §4 | Plan-before-risky-work | **Plan card** (goal, files, tools, checkpoints, rollback) | plan_proposed event |
| PR-009, `06_SECURITY_MODEL` §4 | allow / ask / deny, risk classes | **Permission prompt** (focus-trapped inline card) | `PolicyDecision`, `PermissionRequest` |
| PR-003, `02_SPEC` §2.5 | Model router, local-first, privacy/cost | **Model switcher** (status-bar control + drawer) | model registry, capability flags |
| PR-004, `02_SPEC` §2.6 | Tool broker; tools never run from model output | **Tool-call block** (args, risk, policy, result) | `ToolDescriptor`, `ToolCallResult` |
| PR-007, `03_ARCH` §3 | Memory: profile/project/episodic/procedural/semantic/graph + governance | **Memory** view + **Memory-candidate** approval card | `MemoryRecord`, candidate events |
| PR-008, `02_SPEC` §2.10, `03_ARCH` §2.2 | OS-like activity journal, replay, SARIF | **Activity / Timeline** view | append-only `AgentEvent` log |
| `04_ROADMAP` Phase 3, checkpoints | Checkpoint / rewind (code-only, conversation-only, both) | **Checkpoints** rail + rewind dialog | `CheckpointRecord` |
| PR-001 channels, `03_ARCH` §2.1, `11_DIR` `/clients` | Slack/Signal/Teams/Discord/email/voice/hotkeys/REST/webhooks | **Channels** view (pairing, trust, routing) | `channel_manager`, connector profiles |
| `06_SECURITY_MODEL` §2 | Instruction trust hierarchy; untrusted content quarantine | **Trust badges** everywhere + quarantine banner | `client.trust_level`, attachment `trust` |
| PR-006, `04_ROADMAP` Phase 5 | Plugins & skills (manifest, permission-scoped) | **Extensions** view | `PluginManifest` |
| `02_SPEC` §1.3, sessions | resume / continue / fork / close | **Session switcher** (header) | Session Manager |
| budgets (`PromptEnvelope.budget`) | turns/tokens/cost/seconds/subagents | **Budget meter** (status bar) | budget fields |

Design consequence: because all screens read one event stream, they are **the same component set in
different arrangements**. The Desktop/Web MVP is the TUI's component model promoted to a windowed
layout — not a separate product. This is the single most important simplicity lever in the proposal.

### A.2 Primary user journeys

**J1 — First-run onboarding (privacy-first, ≤4 steps).** Goal: a `01_PRD` Home Power User is running
locally in minutes without reading docs.

```
Welcome ──► Pick model ──► Choose workspace ──► Trust & privacy summary ──► Conversation
 (logo)    (local llama.cpp   (folder picker;     (local-only default,      (cursor in
            detected/default;   becomes the         egress = ask; "nothing    composer)
            hosted = opt-in)    policy scope)       leaves this machine
                                                    without approval")
```

Progressive disclosure: only model + workspace are required; policy, providers, channels, and plugins
are all reachable later from the palette. The privacy summary is a single reassuring sentence, not a
settings dump.

**J2 — Execute a core task (the value path).** Goal: prove PR-002 in the UI. The user types one
prompt; the governed loop is rendered as a vertical stream the eye can scan top-to-bottom.

```
Composer: "Add a retry to the API client and run the tests"
  │
  ▼ state ribbon advances: Intent ▸ Risk ▸ Context ▸ Plan ▸ Policy ▸ Act ▸ Verify ▸ Done
  ├─ Plan card        → [Approve plan] [Edit] [Cancel]          (only shown for risky/multi-step)
  ├─ Tool block       read_file / edit_file  ·  trust: trusted  ·  policy: allow
  ├─ Permission card  shell: run tests  ·  risk: HIGH  ·  [Approve once] [Always in workspace] [Deny]
  ├─ Verification card git diff + test result  ·  PASS
  └─ Final answer     summary · files changed · commands used · residual risks · [Save to memory?]
```

One click (Approve) is the only required interaction for the common case; everything else streams
automatically. The high-risk step *cannot* be missed because the permission card focus-traps and the
loop pauses (`06_SECURITY_MODEL` §4; `08_ACCEPTANCE_TESTS` B3/C1).

**J3 — Monitor & audit.** Goal: `01_PRD` Security Professional / Enterprise Admin. The Activity view is
a filterable timeline of `AgentEvent`s with a "replay turn" control (`08_ACCEPTANCE_TESTS` G2) and an
**Export → SARIF / JSONL** action (G3). Security events are visually distinct and filterable in one
click.

**J4 — Memory governance.** Goal: PR-007. After a turn, durable facts surface as **candidate cards**
("Remember: the API base is configured in `config/...`") with source, confidence, sensitivity, and
retention; the user approves/edits/rejects. The Memory view lists records by layer with search, edit,
export, and forget — proving "durable, searchable, editable, exportable, forgettable."

**J5 — Channel pairing (the "Channels" half of Phase 8).** Goal: PR-001 multi-interface. The user links
a channel (e.g. Slack) through a pairing flow that sets sender allowlist + trust level. Inbound chat /
webhook messages are **labelled untrusted** until sender-gated, shown with a quarantine badge
(`08_ACCEPTANCE_TESTS` — webhook injection labelled untrusted; Phase 8 verification).

**J6 — Rewind.** Goal: checkpoints. From any turn, "Rewind here" offers three explicit choices —
*restore code only*, *restore conversation only*, *restore both* — mirroring `08_ACCEPTANCE_TESTS` E2/E3,
so the user is never surprised about what changes.

---

## B. Interface Layout & Component Hierarchy

### B.1 Navigation model — command-palette-first, thin rail

**Choice:** a **command palette as the primary navigator** (planned for the Phase 8 Rich/native TUI; the current plain terminal already supports `/commands` and `/palette` as text output), backed by a **collapsible icon
rail** of at most seven destinations. **Rejected:** a wide always-on sidebar with nested trees.

Why this fits the architecture and the philosophy:

- The runtime is already **command-addressable** — every capability is a slash command validated by
  `handle_slash_command` and enumerated in `docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md`. A palette is the
  literal GUI projection of that surface, so navigation and capability stay in sync for free.
- It keeps the default screen almost empty (radical simplicity): the conversation gets the pixels; the
  palette holds the long tail behind one keystroke (progressive disclosure).
- It is identical in spirit across CLI, TUI, Desktop, and Web, preserving equal-status parity (PR-001).

The thin rail exposes only the destinations a user returns to: **Conversation, Activity, Memory,
Checkpoints, Channels, Models, Settings.** Everything else (policy editor, extensions, budgets, export)
is palette- or context-reachable. The rail collapses to icons by default and never nests.

### B.2 Dashboard / default view (the Conversation)

```
┌───────────────────────────────────────────────────────────────────────────────┐
│  ☰  Raiker      [ Session: api-refactor ▾ ]              ⌘K  ·  ◐ theme  ·  ⚙   │  ← header: session switch, palette, theme
├──┬────────────────────────────────────────────────────────────────────────────┤
│ ▢│                                                                              │
│ ◳│   ┌── Turn ──────────────────────────────────────────────────────────────┐ │
│ ◰│   │ you ›  Add a retry to the API client and run the tests                 │ │
│ ◱│   │ ─────────────────────────────────────────────────────────────────────│ │
│ ⛁│   │ ▸ Plan  ·  3 steps  ·  1 high-risk            [Approve]  [Edit]  [✕]   │ │  ← inline governance cards
│ ⌁│   │ ▸ edit_file  client.py        trusted · allow            ▸ details     │ │
│ ⚙│   │ ⚠ shell: pytest -q            HIGH · ask    [Approve once][Always][Deny]│ │  ← focus-trapped when active
│  │   │ ✓ Verify  diff + 14 passed                              PASS           │ │
│  │   │ Raiker › Added bounded retry (3x, backoff). Tests pass. 1 file changed.│ │
│  │   └───────────────────────────────────────────────────────────────────────┘ │
│  │                                                                              │
├──┴────────────────────────────────────────────────────────────────────────────┤
│  ┃ Ask Raiker…                                              [Ask|Plan|Act ▾] ➤ │  ← composer + mode selector
├───────────────────────────────────────────────────────────────────────────────┤
│  ● local · llama.cpp   │  budget 4/20 turns · $0.00   │  approvals: 0   │ idle  │  ← status bar (model/budget/approvals/state)
└───────────────────────────────────────────────────────────────────────────────┘
```

The composer is the single primary action and holds focus on load (J2). The **mode selector**
(`ask | plan | act | review | security_review | memory | debug`, from `PromptEnvelope.mode`) is a quiet
dropdown — the default `ask`/`act` covers most users; the others are progressive disclosure for
developers and security pros.

### B.3 Key secondary views (wireframe sketches)

- **Activity / Timeline** — left: filter chips (`tool`, `permission`, `memory`, `security`, `error`);
  center: event rows with risk color and parent-child indentation for subagents (`03_ARCH` §2.2);
  right: selected-event detail + **Replay** and **Export SARIF/JSONL**.
- **Approvals** — a queue of pending `ask` decisions (when the user stepped away). Each row: action,
  risk, requesting interface, reason → `[Approve] [Deny]`. Mirrors the inline card so the mental model
  is identical wherever a prompt appears (it can route to the originating *or* an approved control
  interface — PR-001).
- **Memory** — layer tabs (Profile / Project / Episodic / Procedural / Semantic / Graph); search box;
  record cards showing source, confidence, sensitivity, retention, trust, approval; row actions
  `Edit · Export · Forget`. Secret-sensitivity records show a non-copy, non-export lock (`10_AGENT_CONTRACTS`
  MemoryRecord rule).
- **Checkpoints** — vertical timeline of `CheckpointRecord`s; each offers the three-way rewind (B/J6).
- **Channels** — connector grid (CLI/TUI/Desktop/Web + Slack/Signal/Teams/Discord/email/voice/hotkeys/
  REST/webhooks from `11_DIR` `/clients`); each shows enabled/disabled, transport, auth, trust default,
  and a pairing wizard. Inbound items carry a **trust badge**; untrusted ones get a quarantine banner.
- **Models** — provider list with capability badges (context length, tool-calling, JSON, embeddings,
  vision, **privacy class**, latency, est. cost from PR-003); local providers first; hosted ones flagged
  `policy-gated` and require explicit egress/budget approval.
- **Settings / Policy** — plain-language permission matrix (Low/Medium/High/Critical → Allow/Ask/Deny,
  `06_SECURITY_MODEL` §4) with the raw policy file behind an "Advanced" disclosure.

### B.4 Component hierarchy (shared, event-driven)

```
AppShell
├─ Header (SessionSwitcher, PaletteTrigger, ThemeToggle, SettingsGear)
├─ NavRail (7 destinations, collapsible)
├─ ViewSlot
│   └─ ConversationView
│       ├─ TurnStream
│       │   └─ TurnCard*
│       │       ├─ StateRibbon            (loop states from AgentEvent)
│       │       ├─ PlanCard               (approve/edit/cancel)
│       │       ├─ ToolCallBlock          (args · trust · policy · result)   ← reuse raiker/tui ToolCallBlock
│       │       ├─ PermissionCard         (focus-trap; allow/ask/deny)
│       │       ├─ VerificationCard       (PASS/FAIL/PARTIAL + evidence)
│       │       ├─ MemoryCandidateCard    (approve/edit/reject)
│       │       └─ FinalAnswer            (outcome · files · risks · next)
│       └─ Composer (text + ModeSelector + AttachmentTray with trust labels)
└─ StatusBar (ModelChip, BudgetMeter, ApprovalsCount, RuntimeState)
```

Reuse, not reinvention: this hierarchy is the existing TUI's structure generalized. The Desktop/Web MVP
should consume the same `AgentEvent` stream via `AgentGateway.astream_prompt` and the stream event types
already defined in `raiker/contracts/streaming.py` (`LIFECYCLE`, `TEXT_DELTA`, `TOOL`, `FINAL`,
`ERROR`), and the same `handle_slash_command` surface for palette actions. One renderer-agnostic
event→component mapping serves every client.

---

## C. Visual Identity & Interaction Design

### C.1 Theme

- **Typography hierarchy (3 roles, 1 mono):** a single sans family in three weights/sizes — *Display*
  (view titles), *Body* (conversation + UI), *Caption* (metadata: trust, risk, timestamps) — plus one
  monospace for code, diffs, tool args, and event payloads. Three steps keep scanning effortless; the
  mono/sans split signals "machine output vs. human-facing" without extra chrome.
- **Color theory — semantic, not decorative.** A near-neutral base (one background, one surface, one
  border, two text tints) maximizes whitespace and lets two small semantic scales carry all meaning:
  - **Risk:** Low = neutral, Medium = amber, High = orange, Critical = red (`06_SECURITY_MODEL` §4).
  - **Trust:** Trusted = calm green/neutral, Authenticated = blue, Untrusted = hatched amber/quarantine
    (`06_SECURITY_MODEL` §2).
  A single brand **accent** marks the one primary action per screen (the composer's send, the primary
  approve). Color is never the *only* signal — every risk/trust state also carries an icon and a text
  label (accessibility + utilitarian clarity).
- **Dark / light:** dark is the default (terminal-adjacent, the home of `01_PRD`'s power user); light is
  a first-class peer. Both are generated from the same tokens so semantic risk/trust colors keep
  identical meaning and contrast (WCAG AA) in either mode. Theme toggle lives in the header (and the
  palette).
- **Whitespace & density:** generous default spacing with a "compact" density toggle for the developer
  who wants more events on screen — progressive disclosure of density rather than two designs.

### C.2 Interaction mechanics (states & feedback)

- **Hover:** surfaces a subtle elevation + reveals secondary actions (e.g. a tool block's `▸ details`,
  an event row's `Replay`). Hover never *moves* layout — only reveals, so the eye is never chased.
- **Focus:** a single high-contrast focus ring; the app is fully keyboard-drivable (palette = ⌘K,
  Approve = ⏎, Deny = Esc-twice, mode cycle = Tab). Permission cards **trap focus** until resolved so a
  high-risk `ask` cannot be skipped (PR-009 excessive-agency control made visible).
- **Click / active:** the primary action has a visible pressed state and immediately flips the relevant
  governance card to a resolved state with an inline confirmation ("Approved · running…").
- **Disabled:** disabled controls state *why* on hover (e.g. "Hosted model requires egress approval"),
  turning a dead end into guidance.
- **Streaming feedback:** assistant text streams token-by-token (`TEXT_DELTA`); the **state ribbon**
  animates only on real loop transitions, so motion is information, not garnish. A turn that uses no
  tools simply shows a faded "no tools needed" — matching the runtime's state-skipped events
  (`02_SPEC` §4) so the UI never implies work that didn't happen.
- **Interruptibility:** Pause / Steer / Cancel are always one click on an in-flight turn (PR-002,
  `08_ACCEPTANCE_TESTS` B4); cancelling emits and shows the interrupt event.
- **Untrusted content:** anything `untrusted` (web text, chat, webhook, plugin output, retrieved
  memory) renders inside a quarantine container with a persistent badge and instructions-are-inert
  styling, reinforcing the trust hierarchy at the pixel level (`06_SECURITY_MODEL` §2, `07_PROMPT_FILES`).

### C.3 Accessibility & responsiveness

Keyboard-first parity with the TUI; AA contrast in both themes; redundant icon+label encoding for all
risk/trust color; screen-reader live-region announcements for streaming and for permission prompts
(a security control, not a nicety). The Web MVP collapses the rail to a bottom bar on narrow viewports;
the conversation remains the full-width primary surface.

---

## Phase 8 scope, non-goals & acceptance mapping

**In scope (per `04_ROADMAP` Phase 8):** Rich TUI (exists), Desktop/Web UI MVP, REST API, webhook
receiver, chat connector stubs, voice/hotkey stubs — all as the same event-sourced client model.

**Non-goals / guardrails (design-only this phase):**

- This is a UX concept; it is **not implemented** and activates no runtime. Desktop/Web/REST/channels
  remain specified/deferred and disabled until their build tasks land with policy, events, tests, and
  acceptance evidence.
- No UI surface executes tools, writes memory, calls models, or reaches the network directly — every
  action is a `PromptEnvelope`/command through the Gateway → Broker → Policy path.
- Inbound chat and webhook traffic is untrusted until sender-gated.

**Acceptance hooks the design must satisfy** (from `04_ROADMAP` Phase 8 + `08_ACCEPTANCE_TESTS`):

| Acceptance check | UX manifestation |
|---|---|
| Same session receives a CLI and a REST prompt | Session switcher shows interleaved turns tagged by originating `client.type`; the Turn Stream renders both from one event log. |
| Webhook injection labelled untrusted | Quarantine badge + inert-instruction styling on webhook-sourced content; security event surfaced in Activity. |
| Every action emits an event (G1) | Every governance card is a 1:1 reflection of an `AgentEvent`; nothing happens off-timeline. |
| Replay reconstructs the turn (G2) | "Replay turn" control in Activity. |
| SARIF export (G3) | Export action in Activity / security filter. |
| Permission/interrupt (B3/B4, C1) | Focus-trapped permission card; always-available Pause/Cancel. |

---

## Evaluation — why this stays simple

Each simplicity decision is a direct manifestation of the technical architecture, not a cosmetic
preference:

1. **One conversation surface, many views.** Because every client consumes one `AgentEvent` stream
   (PR-001, `02_SPEC` §2.2), the screens are one component set rearranged. Users learn the app once;
   the Desktop/Web MVP inherits the TUI's mental model. → lowest possible cognitive load, maximal
   parity.
2. **Governance as inline cards, not separate apps.** The agent loop (PR-002) already produces discrete,
   ordered events; rendering each as a card turns an invisible control flow into a scannable narrative.
   Plan, permission, verification, and memory governance appear *exactly where and when they occur*, so
   safety is legible without a settings safari.
3. **Command-palette-first navigation.** The runtime is command-addressable (`handle_slash_command`,
   the tool/plugin catalog), so a palette keeps the GUI and the capability surface automatically in
   sync and keeps the default screen empty. → frictionless power-use behind one keystroke; near-zero
   chrome for everyone else.
4. **Semantic, two-axis color (risk × trust).** The security model defines exactly two ordered scales
   (`06_SECURITY_MODEL` §2/§4); binding color to *only* those means the palette is focused and every
   hue carries meaning. Redundant icon+label encoding keeps it honest and accessible.
5. **Progressive disclosure mapped to risk.** Defaults expose the safe, common path (ask/act, local
   model, workspace scope); high-risk and advanced controls (policy editor, hosted models, channels,
   external execution) are deliberately one layer down — matching the foundation's "default deny / ask
   for high risk" posture. The interface is calm because the architecture is conservative, and the UI
   simply tells the truth about it.

In short: the layout is an elegant projection of the runtime. The agent already gathers context,
plans, asks, acts, verifies, logs, and remembers in a fixed order — the UI's job is to make that single
honest loop effortless to watch and to steer, and to disappear when nothing risky is happening.
