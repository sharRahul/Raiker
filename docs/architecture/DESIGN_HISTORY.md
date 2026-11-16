# Design history

**Historical record.** This file keeps superseded design plans in one place so
the current architecture documents stay short. Nothing here is maintained
against the code: for what is implemented now read
[Implementation status](IMPLEMENTATION_STATUS.md), for the components and
governed flow read [Architecture](ARCHITECTURE.md), and for how Raiker compares
with reference platforms read
[Reference platform compatibility](REFERENCE_PLATFORM_COMPATIBILITY.md).

Each section below was a separate document until 2026-11-16 and is kept
verbatim under its original title.

## Build order (implementation sequence)

> Merged from `docs/architecture/DESIGN_HISTORY.md` on 2026-11-16; the original file was removed.

**Historical record.** This document defines the dependency-safe order Raiker
was implemented in. It is not maintained against the code; for what is
implemented now read [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md), and
for per-capability executor status read
[`RUNTIME_EXECUTORS_SPEC.md`](RUNTIME_EXECUTORS_SPEC.md).

It makes the build sequence explicit enough that a builder agent does not
implement UI, tools, memory, plugins, channels, or storage lifecycles before the
contracts and safety rails exist. (It once complemented a
`docs/foundation/09_IMPLEMENTATION_PLAN.md` that predates this repository and was
never committed to it; the phase detail it referred to is now in
[`FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md`](FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md).)

Phase order controls implementation sequencing only. It does not create an interface hierarchy.

---

### Required Reading Order

Every implementation task must start with this sequence:

```text
README.md
  -> docs/architecture/IMPLEMENTATION_STATUS.md
  -> docs/architecture/FEATURE_COVERAGE_MATRIX.md
  -> docs/architecture/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md
  -> docs/architecture/DESIGN_HISTORY.md
  -> docs/architecture/ARCHITECTURE.md
  -> docs/architecture/CONTRACTS.md
  -> docs/architecture/API_AND_CONTRACT_SCHEMAS.md
  -> docs/architecture/EVENT_CATALOG.md
  -> docs/architecture/RUNTIME_STATE_MACHINE.md
  -> docs/architecture/STORAGE_DATABASE_AND_SEARCH_SPEC.md
  -> docs/architecture/SECURITY_AND_POLICY.md
  -> docs/architecture/THREAT_MODEL.md
  -> docs/architecture/NON_GOALS_AND_BOUNDARIES.md
  -> docs/architecture/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md
  -> docs/architecture/FULL_PHASE_IMPLEMENTATION_BLUEPRINT.md
  -> docs/architecture/IMPLEMENTATION_STATUS.md
  -> docs/architecture/IMPLEMENTATION_STATUS.md
  -> docs/architecture/IMPLEMENTATION_STATUS.md
  -> docs/architecture/IMPLEMENTATION_STATUS.md
  -> docs/architecture/IMPLEMENTATION_STATUS.md
  -> docs/architecture/IMPLEMENTATION_STATUS.md
  -> docs/architecture/RUNTIME_ORCHESTRATION_SPEC.md
  -> docs/architecture/TOOLS_AND_PERMISSIONS_SPEC.md
  -> docs/architecture/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md
  -> docs/architecture/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md
  -> docs/architecture/MODEL_PROVIDER_CONTRACT.md
  -> docs/architecture/CHANNELS_SPEC.md
  -> docs/UI_UX_DESIGN_SPEC.md
  -> docs/architecture/MEMORY_AND_CONTEXT_STRATEGY.md
  -> docs/architecture/MEMORY_GOVERNANCE_RULES.md
  -> docs/architecture/PLUGIN_SYSTEM_SPEC.md
  -> docs/architecture/PLUGIN_MANIFEST_SCHEMA.md
  -> docs/architecture/RAIKER_TOOL_AND_PLUGIN_CATALOG.md
  -> docs/architecture/ACCEPTANCE_TESTS_BY_PHASE.md
  -> docs/architecture/DESIGN_HISTORY.md
  -> docs/architecture/VERIFICATION_PLAN.md
  -> docs/architecture/LOCAL_VALIDATION_GATE.md
  -> config/model-profiles.json
  -> config/channel-connectors.json
```

A builder must not skip the status, schema, event, runtime state, storage, security, threat-model, non-goals, acceptance-test, verification, or registry docs because they are the controls that keep the implementation deterministic.

---

### Phase 1 Dependency Graph

```text
RAIKER-0001 scaffold
  -> RAIKER-0002 dev tooling
    -> RAIKER-0101 contracts
      -> RAIKER-0102 IDs/timestamps
        -> RAIKER-0201 SQLite bootstrap
        -> RAIKER-0202 JSONL event writer
        -> RAIKER-0203 built-in registries
          -> RAIKER-0301 static policy config
            -> RAIKER-0302 policy engine
              -> RAIKER-0401 tool broker routing
                -> RAIKER-0402 read_file
                -> RAIKER-0403 list_directory
                -> RAIKER-0404 glob/grep
                -> RAIKER-0405 approval-gated local action placeholder
          -> RAIKER-0501 mock model provider
            -> RAIKER-0502 model router interface
            -> RAIKER-0503 terminal launch profile resolution
          -> RAIKER-0601 runtime states
            -> RAIKER-0602 classifier/planner
            -> RAIKER-0603 verification stub
              -> RAIKER-0701 agent gateway
                -> RAIKER-0702 session manager
                -> RAIKER-0703 checkpoint service
                  -> RAIKER-0801 global raiker launch
                  -> RAIKER-0802 terminal prompt path
                  -> RAIKER-0803 terminal approval behaviour
                  -> RAIKER-0804 terminal registry panels
                    -> RAIKER-0901 end-to-end smoke tests
                    -> RAIKER-0902 documentation/validation report
```

---

### Non-Negotiable Sequencing Rules

1. Contracts before runtime.
2. Event envelope before event writer.
3. SQLite bootstrap before event indexing.
4. Policy engine before tool execution.
5. Tool broker before any filesystem/search/local-command action.
6. Mock model provider before model routing tests.
7. Runtime state machine before terminal prompt orchestration.
8. Agent gateway before any client-specific prompt path.
9. Checkpoint stub before terminal end-to-end completion criteria.
10. Equal-interface metadata before first terminal-specific implementation.
11. Lifecycle metadata contracts before lifecycle metadata storage.
12. Lifecycle metadata storage before lifecycle summaries.
13. Lifecycle summaries before any future lifecycle approval handoff.
14. Lifecycle approval handoff before any future runtime graph/memory/rollback execution work.

If a builder needs to violate this order for bootstrap reasons, it must document the temporary exception in the PR and add a follow-up task that restores the canonical order.

---

### Phase 1 Build Slices

| Slice | Task IDs | Output | Must not do |
|---|---|---|---|
| Foundation | RAIKER-0001 to RAIKER-0002 | Package, tests, dev tooling | No runtime behaviour. |
| Contracts | RAIKER-0101 to RAIKER-0102 | Versioned schemas and ID helpers | No tool execution. |
| Storage/events | RAIKER-0201 to RAIKER-0203 | SQLite, JSONL, registries | No active channels or hosted providers. |
| Policy | RAIKER-0301 to RAIKER-0302 | Static allow/deny/needs_approval decisions | No command execution. |
| Tools | RAIKER-0401 to RAIKER-0405 | Brokered read/list/glob/grep plus approval placeholder | No direct file access from runtime. |
| Models | RAIKER-0501 to RAIKER-0503 | Mock provider and profile resolution | No network or hosted provider calls. |
| Runtime | RAIKER-0601 to RAIKER-0603 | Deterministic state machine and verifier stub | No parallel agent teams. |
| Gateway/session/checkpoint | RAIKER-0701 to RAIKER-0703 | Shared gateway and checkpoint stub | No client bypass path. |
| Terminal MVP | RAIKER-0801 to RAIKER-0804 | First terminal client through gateway | No terminal-only architecture. |
| Validation | RAIKER-0901 to RAIKER-0902 | Smoke tests and report | No unverified completion claim. |

---

### Phase 2 Dependency Graph

```text
RAIKER-1001 Phase 2 plan
  -> RAIKER-1002 CI baseline
    -> RAIKER-1101 task contract + storage
      -> RAIKER-1102 task manager
        -> RAIKER-1103 task events
    -> RAIKER-1601 event query service
      -> RAIKER-1602 /events command
    -> RAIKER-1701 /status and /tasks
    -> RAIKER-1501 checkpoint timeline
  -> RAIKER-1201 side-question contract
    -> RAIKER-1202 side-question runtime
  -> RAIKER-1301 interrupt/steer contracts
    -> RAIKER-1302 safe-boundary handling
  -> RAIKER-1401 approval inbox
    -> RAIKER-1402 approval commands
  -> RAIKER-1502 checkpoint restore/fork
  -> RAIKER-1801 stat_path/diff_files
    -> RAIKER-1802 write/edit/patch with snapshots
  -> RAIKER-1901 git wrappers
  -> RAIKER-2001 provider health check
    -> RAIKER-2002 llama.cpp server detection
  -> RAIKER-2101 memory candidate listing
    -> RAIKER-2201 integration validation
```

---

### Phase 2 Build Slices

| Slice | Task IDs | Output | Must not do |
|---|---|---|---|
| Foundation | RAIKER-1001 to RAIKER-1002 | CI, status ledger, build plan | No runtime behaviour change. |
| Task management | RAIKER-1101 to RAIKER-1103 | Task storage, manager, events | No tool execution. |
| Event viewer | RAIKER-1601 to RAIKER-1602 | Event query service and /events | No event log mutation. |
| Terminal inspection | RAIKER-1701, RAIKER-1501 | /status, /tasks, /checkpoints | No restore/fork execution. |
| Side questions | RAIKER-1201 to RAIKER-1202 | Child-turn contract and runtime | No active task mutation. |
| Interrupt/steer | RAIKER-1301 to RAIKER-1302 | Interrupt contracts and safe-boundary | No silent cancellation. |
| Approvals | RAIKER-1401 to RAIKER-1402 | Approval inbox and commands | No auto-approval. |
| File tools | RAIKER-1801 to RAIKER-1802 | stat_path, diff_files, write/patch proposal | No unrestricted file mutation. |
| Git wrappers | RAIKER-1901 | Git status/diff/log with policy | No git push/merge without approval. |
| Model providers | RAIKER-2001 to RAIKER-2002 | Health check, llama.cpp server detection | No hosted model calls. |
| Memory | RAIKER-2101 | Memory candidate listing | No durable memory writes. |
| Validation | RAIKER-2201 | Integration tests and status update | No unverified completion claim. |

---

### Phase 3 Storage Lifecycle Build Order

Slice G is the current deepest Phase 3 storage lifecycle preparation slice. Future agents must follow this sequence:

```text
Slice C graph/codemap dry-run planning
  -> Slice D semantic-memory review queue
    -> Slice E approval preview contracts
      -> Slice F approval audit + rollback planning
        -> Slice G storage lifecycle metadata
          -> Slice H metadata-only retention/cleanup-preview/approval-handoff planning
```

Slice G may create and inspect metadata records only. It must not be used as a trigger for graph indexing, semantic/vector memory writes, embeddings, rollback execution, plugin execution, channels, subagents, or remote/container/cloud execution.

---

### Builder Stop Conditions

A builder must stop and update documentation before coding if:

- a contract field is missing or ambiguous;
- an event name is not in `docs/architecture/EVENT_CATALOG.md`;
- a state transition is not allowed by `docs/architecture/RUNTIME_STATE_MACHINE.md`;
- a storage table or column is missing from the storage spec;
- a tool lacks policy, failure modes, or output limits;
- an approval flow is not action-bound;
- a lifecycle metadata record would imply runtime execution;
- a later-phase feature would need active runtime wiring;
- a client would bypass the Agent Gateway;
- a change would make terminal/TUI canonical over another enabled primary interface.

---

### PR Completion Gate

Every implementation PR must include:

```markdown
## Task IDs
- RAIKER-....

## Build order position
- Slice: ...
- Depends on: ...

## Contracts/events/storage/policy affected
- Contracts: ...
- Events: ...
- Storage: ...
- Policy: ...

## Validation
- [ ] python -m pytest
- [ ] python -m ruff check .
- [ ] python -m mypy raiker apps tests
- [ ] python scripts/validate_phase_status.py
- [ ] raiker smoke test, if terminal path affected

## Invariants
- [ ] No client bypasses Agent Gateway
- [ ] No tool executes without policy decision
- [ ] Equal primary-interface invariant preserved
- [ ] Phase-scheduled features remain disabled unless this task explicitly enables them
- [ ] Slice G lifecycle metadata remains metadata-only unless a later approved task explicitly changes that with docs, tests, policy, rollback, and CI evidence
```

### Phase 3 Slice H lifecycle retention reference

Slice H is metadata-only retention, cleanup-preview, and approval-handoff planning. Keep detailed contract and safety requirements in `docs/architecture/IMPLEMENTATION_STATUS.md`; this document only references Slice H where its local status, validation, command, event, or storage responsibility applies.

### Phase 3 Slice I lifecycle evidence reference

Slice I lifecycle evidence bundles, policy simulations, JSON exports, CLI surfaces, SQLite metadata tables, and disabled-runtime validation are centralized in `docs/architecture/IMPLEMENTATION_STATUS.md`. Slice I is metadata-only/read-only/export-only/simulation-only and does not mark Phase 3 complete.

## Web UI Control Deck plan (superseded by the Quiet UI plan)

> Merged from `docs/architecture/DESIGN_HISTORY.md` on 2026-11-16; the original file was removed.

> **Status:** adopted design plan, corrected against the codebase as of 2026-07-10.
> This document supersedes the draft Control Deck plan and the previous web UI direction.
> Canonical implementation truth remains `docs/architecture/IMPLEMENTATION_STATUS.md` and `docs/architecture/HANDOFF.md`;
> where this plan and the code disagree, the code wins and this plan must be updated.

---

### Personal-agent interaction direction — 2026-10-08

The [personal-agent UX specification](../plans/PERSONAL_AUTONOMOUS_AGENT_SPEC.md#personal-agent-ui-and-ux) and
[UX-01–UX-12 implementation plan](../plans/PERSONAL_AUTONOMOUS_AGENT_SPEC.md)
now own target intake, Home, goals/tasks, approvals, background readiness,
results, personal context, recovery and continuity. Each task records a reason,
decision, alternatives, dependencies, state behavior and acceptance evidence.
[ADR-0002](../adr/ADR-0002-personal-agent-user-experience.md) explains the choice.

For future implementation, that target supersedes conflicting conceptual screen
names/interaction flows below; shared shell, tokens, tested logic, existing
navigation IDs and authority contracts remain. This is not a visual rewrite or
a claim new goal/profile controls exist. ADD-26's implemented responsive shell
is reused. Current implementation status and real API/lifecycle contracts govern
what can be displayed and acted on.

### 0. Corrections applied to the draft plan

The draft was verified claim-by-claim against the repository. These corrections are
binding for implementation; everything else in the draft carries over.

1. **Sources:** `docs/UI-implementation/*` no longer exists (deleted as superseded).
   The acceptance anchors are the living test suites: `tests/test_security_regression_ui.py`
   (M7 security regression), `tests/test_api_contract_schemas.py`,
   `tests/test_api_m5_security_settings.py`, and `web/src/a11y.test.ts`.
   Risk classes come from `RISK_LEVELS` (`raiker/contracts/models.py`) and
   [`SECURITY_ARCHITECTURE.md`](SECURITY_ARCHITECTURE.md).
2. **The turn state machine has 19 states, not 16** (`raiker/runtime/state_machine.py`,
   `RUNTIME_STATES`). Copy referring to the expanded State Tape says "the full state
   detail", never a hardcoded count.
3. **Checkpoint types:** the seven-type taxonomy (`turn`, `tool`, `file_snapshot`, `task`,
   `session`, `manual`, `fork`) is the *spec ceiling* (`CHECKPOINTING_AND_REWIND_SPEC.md`).
   The implemented `CheckpointService` emits **turn checkpoints only**. The Recorder renders
   what the backend returns and describes the rest as specified-but-not-yet-emitted; no
   empty lanes for types that cannot occur.
4. **Session fork is not an API operation.** Resume works by passing `session_id` to
   `POST /api/prompts`. The session switcher offers resume only until a governed fork
   endpoint exists (added to Section 9 as an explicit optional item).
5. **Honesty labels are documentation vocabulary, not backend data.** The nine labels
   (`implemented_read_only`, `implemented_policy_gated`, `implemented_approval_required`,
   `metadata_only`, `readiness_only`, `dry_run_only`, `contract_only`, `disabled_deferred`,
   `test_only`) live in `docs/architecture/FEATURE_COVERAGE_MATRIX.md`; `CapabilityGateView` has no such
   field. The UI derives *only* from real gate fields (`state`, `allowed_transitions`,
   `can_current_principal_change`, `blocked_reason_code`, `decision_mode`), as
   `capabilityModel.ts` already does. If per-capability implementation labels are wanted
   in the UI, a backend field must ship first (Section 9, optional item).
   `no_executor` is a `blocked_reason_code`, not a label.
6. **Per owner decision (PR #104), decision modes stay the primary control** on every
   capability row — Ask / Allow / Auto / Deny first, gate state and any implementation
   detail in the expandable row detail. This plan does not reverse that. The gates board
   keeps the single-read pattern (`decision_mode` rides on `GET /api/capability-gates`);
   no per-capability fan-out (it previously tripped the 120/min rate limit).
7. **SSE replay-from-cursor does not exist.** `POST /api/prompts/stream` is a fetch-based
   POST stream (deliberate: the bearer token rides in a header, which `EventSource`
   cannot do). Reconnect-with-replay is a backend addition (Section 9, optional);
   until then the UI reconciles a dropped stream by re-reading `GET /api/turns/{id}`.
8. **Typography: Manrope + JetBrains Mono, bundled, offline-first.** The app ships its
   fonts as local variable-weight woff2 assets under `web/src/assets/fonts/`
   (SIL OFL 1.1, license file alongside). **No external font, CSS, or CDN request of any
   kind** — a Google Fonts fetch would silently break "nothing leaves this machine".
   Manrope carries display and UI text (its geometric, engineered character suits the
   instrument-panel identity); JetBrains Mono carries machine-verbatim output.
9. **Reuse the tested logic layer.** `web/src/lib/` (api client, `apiTypes.ts`,
   `capabilityModel.ts`, `turnPhases.ts` — which already implements the four-phase
   gather→plan→act→verify grouping — `statusMaps.ts`, `reasonCodes.ts`, `theme.ts`,
   `nav.ts`) and the security/a11y/contract test suites are kept. The redesign replaces
   tokens, components, and views on top of that layer; it is not a rewrite.

---

### 1. Purpose and sources

This plan defines the target web UI/UX for Raiker's local single-user web surface
(`raiker-web` + `web`), designed to scale into the Phase 8 multi-surface vision
without redesign.

Verified sources: `README.md`, `SECURITY.md`, `docs/architecture/HANDOFF.md`,
`docs/architecture/IMPLEMENTATION_STATUS.md`, `docs/architecture/FEATURE_COVERAGE_MATRIX.md`,
`docs/architecture/SECURITY_AND_POLICY.md`, `docs/architecture/DECISION_MODES_SPEC.md`,
`docs/architecture/CHANNELS_SPEC.md`, `docs/architecture/CHECKPOINTING_AND_REWIND_SPEC.md`,
`docs/architecture/MEMORY_AND_CONTEXT_STRATEGY.md`, `docs/architecture/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`,
`docs/architecture/GRAPH_MEMORY_AND_CODEMAP_SPEC.md`, `docs/architecture/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md`,
`docs/architecture/PLUGIN_SYSTEM_SPEC.md`, `docs/architecture/RAIKER_TOOL_AND_PLUGIN_CATALOG.md`,
`docs/architecture/SECURITY_ARCHITECTURE.md`, `docs/guide/`, the threat-model set, and
the code: `raiker/phase_gates.py` (53 capabilities), `raiker/runtime/executors/__init__.py`
(`REAL_EXECUTOR_CAPABILITIES`, 29 integrated), `raiker/api/routes_*.py` (31 endpoints),
`raiker/control/dtos.py` (gate DTO fields), `raiker/runtime/state_machine.py` (19 states),
`raiker/cli/commands.py` (~80 slash commands), and `web/src` (kept logic layer).

#### The goal this design serves (from `docs/architecture/HANDOFF.md`)

Raiker is a full-fledged, secure AI agent that connects to **any** backend LLM (local
llama.cpp, Ollama, LM Studio; home-lab vLLM; hosted Anthropic, OpenAI, Gemini,
OpenRouter), where **the choice belongs to the user**, and **every capability is
governed, default-ask, human-governed, and fail-closed where required**. The UI's job is
to make that posture effortless to see, trust, and operate, and to make model choice a
first-class, one-screen experience.

#### Posture this design is built on (HANDOFF part 8)

Integrated capabilities (the 29 in `REAL_EXECUTOR_CAPABILITIES`) default to
`enabled_runtime`; non-integrated capabilities stay `disabled` and fail closed. Safety is
per-action: decision modes (default `ask`), the critical-risk human floor, PolicyEngine
hard-denies, and executor-level env allowlists. The primary daily surface is the
per-action decision, not the gate flip.

---

### 2. Design goals and principles

1. **One honest control center.** Every card is a 1:1 projection of an `AgentEvent` or a
   governed API response; nothing happens off-timeline.
2. **Governance present but quiet.** The safe local turn needs zero interaction; the risky
   path (approval, gate change, hosted egress) is impossible to miss and reasoned in plain
   English from real `reason_code`s.
3. **No privileged interface, no client authority.** No policy logic, no gate logic, no
   secrets, no localStorage tokens in the SPA. It renders backend truth
   (`can_current_principal_change`, `allowed_transitions`, `blocked_reason_code`) and
   never fakes success. Fail-closed states are designed, not error pages.
4. **The user's model, the user's choice.** Local providers are visually "home"; anything
   that leaves the machine is visibly gated before it can be selected.
5. **Command-addressable parity.** Every CLI slash command gets a palette equivalent.
6. **Iconic, not decorative.** One strong metaphor executed with restraint, a semantic
   two-axis colour system (risk × trust), and one signature interaction (the Guarded
   Switch).
7. **Offline-complete.** The built app makes zero external requests: fonts, icons, CSS,
   and scripts are all bundled. Loopback is the only network surface.

---

### 3. The iconic identity: "Control Deck"

#### 3.1 Concept

Raiker behaves like certified avionics, not a chatbot: fail-closed, guarded controls, an
append-only recorder, a master stop, checklists before dangerous actions, a human always
in command. The design language makes that literal, with the discipline of a modern glass
cockpit:

| Runtime concept | Control Deck metaphor | UI expression |
|---|---|---|
| Capability gate enable (threat ack + confirmation token) | Guarded switch with a flip cover | **Guarded Switch**: cover lifts, checklist completes, switch arms |
| STOP (safe-boundary interrupt) | Master stop | Round, guarded, always visible; two-stage engage |
| Decision modes ask/allow/auto/deny | Mode selector | Segmented **Mode Dial** per capability with floor annotations — the primary row control |
| Approval inbox | Annunciator panel | **Annunciator Strip**: glanceable pending-approval lights |
| Turn state machine (19 states) | Flight director tape | **State Tape**: four-phase ribbon (gather→plan→act→verify per `turnPhases.ts`), full state detail on expand |
| Append-only events + checkpoints | Data recorder | **Recorder**: unified timeline of events and checkpoints |
| Runtime readiness / diagnostics | Pre-flight checklist | **Pre-flight** panel: readiness items with pass/attention states |
| Egress allowlist / hosted models | External feed valves | Egress status chip on every hosted profile; "nothing leaves this machine" indicator |
| Trust levels on inbound content | Unverified traffic advisory | Quarantine container with hatched border, inert-instruction styling |

The tone is **calm precision**: low-glare surfaces, thin luminous strokes, dense but
ordered data, motion only when state genuinely changes.

#### 3.2 Mark and wordmark

The shipped shield-R monogram stays (it already reads "governed by design" and is
established in the favicon). The wordmark sets RAIKER in Manrope 700 with wide tracking.
State-aware favicon tinting (idle / turn in flight / approvals pending / STOP) is a
polish-phase item.

#### 3.3 Motion signature

One easing (`cubic-bezier(0.2, 0, 0, 1)`, 160–240 ms) and three moves only:

1. **Arm:** guarded covers open, then the switch translates with a click highlight.
2. **Advance:** the State Tape's active segment fills 200 ms on each real transition.
   No idle animation, no fake progress.
3. **Settle:** resolved governance cards compress to a one-line receipt.

`prefers-reduced-motion` collapses all three to opacity changes. Nothing loops.

---

### 4. Design tokens

Implemented in `web/src/app.css`. Components consume tokens only — never raw
colours — so both themes stay in lockstep. Existing token *names* are kept so the
component layer needs no changes.

#### 4.1 Colour

Reset on **2026-08-16** to the owner's three-colour palette. Three colours per
theme, named on `:root` as `--brand-gold` `#ecd06f`, `--brand-blue` `#2779a7`,
`--brand-grey` `#9c9c9c`, `--brand-black` `#000000`, `--brand-white` `#ffffff`;
every other token derives from one of them.

**Dark ("deck", flagship):** app background `#000000`, surfaces `#0b0b0c` /
`#17171a`, hairline `#2a2a2c`, text `#ffffff` / `#b6b6b8` / `#9c9c9c`, accent gold
`#ecd06f` family with `--text-inverse` black.

**Light ("paper", first-class peer):** paper `#f4f4f5`, surfaces white, ink
`#1b1c1e`, neutral scaffold from grey `#9c9c9c`, accent steel blue `#2779a7`
family with `--text-inverse` white; gold `#ecd06f` carries the brand mark and the
pending/ask state. The default follows `prefers-color-scheme`; the explicit choice
persists in `localStorage` (theme preference only — the bearer token stays
memory-only).

**Risk scale** (from `RISK_LEVELS`, `raiker/contracts/models.py`): low = neutral;
medium = amber; high = orange; critical = red with a 2 px left rule and shield-alert
icon. **Trust scale:** trusted = calm green; authenticated = blue; untrusted = hatched
amber quarantine border. All pairs meet WCAG AA in both themes; risk and trust are never
colour-only (icon + text label always accompany).

#### 4.2 Typography — bundled, offline

- **Display + UI:** **Manrope** (variable 200–800), self-hosted woff2
  (`assets/fonts/manrope-*.woff2`). Wordmark and view titles at 700, UI text 400–600.
- **Mono:** **JetBrains Mono** (variable 100–800), self-hosted woff2. All code, diffs,
  tool arguments, event payloads, ids, and reason codes. The sans/mono split is a trust
  signal: mono means "machine output, verbatim".
- System-font fallback stacks remain in place so the UI degrades gracefully if an asset
  is ever missing.
- Scale (px/line): 28/34 display, 20/28 title, 15/22 body, 13/18 caption, 12.5/18 mono.
  A **compact density** toggle (preferences, polish phase) drops body to 14/20.

#### 4.3 Space, radius, elevation, iconography

- 4 px base grid; component paddings 8/12/16/24; page gutters 24 (desktop) / 16 (narrow).
- Radius: 6–8 px controls, 10–12 px cards, full round only for STOP and status dots.
- Elevation by stroke and subtle glow rather than heavy shadows; one shadow token
  reserved for modals.
- Icons: the existing inline SVG set (`icons.ts`) extended with the brand glyphs as
  needed: guarded switch, gate bar, annunciator light, checkpoint flag, quarantine hatch,
  egress valve. Stroke 1.5 px. No external icon fonts.

---

### 5. Information architecture

#### 5.1 Navigation model

**Command palette first, thin rail second.** The runtime is command-addressable
(`handle_slash_command`, ~80 commands), so the palette (⌘K / Ctrl-K) is the GUI
projection of the whole capability surface with inline argument prompts and the same
fail-closed answers the CLI gives. Typing `/` in the composer opens the palette scoped to
commands.

The rail evolves from the current grouped nav toward seven destinations plus Settings as
the new read surfaces land (each destination ships only when its backend exists):

```
◇ Deck        (conversation: the primary surface — today's Chat)
▤ Ops         (tasks today; plans, proposals, review, subagents & teams, routines as reads land)
◉ Approvals   (annunciator: pending decisions; previews & audit as reads land)
⌗ Memory      (new: memory layers, review queue, vectors, graph/codemap — needs Section 9 reads)
⛁ Models      (providers, profiles, health, budgets, egress status)
⌁ Extend      (new: plugins, channels, execution environments — needs Section 9 reads)
▣ Recorder    (events + checkpoints today; storage lifecycle, exports as reads land)
⚙ Settings    (Security Settings incl. gates/modes, principals & roles, diagnostics, docs, preferences)
```

Global chrome on every screen:

- **Top bar:** view title, the **model chip** (`● Local · <profile>` or
  `▲ Hosted · <provider> · egress open/closed`), runtime readiness, acting principal,
  theme toggle, and **STOP**. The Annunciator Strip and session switcher join as they are
  built.
- **STOP:** round red guarded control, two-stage (press lifts the cover and explains
  "ends all active tasks at the next safe boundary — not an instant force-kill"; confirm
  issues `POST /api/interrupts`). Keyboard reachable, screen-reader announced.

#### 5.2 The mutation funnel (unchanged security model)

All runtime mutation (runtime modes, capability gates, decision modes, dangerous-cap
enablement) lives in **one** place — Settings → Security Settings — behind step-up auth.
Everywhere else, capability and gate surfaces are read-only status views with a "Change
in Security Settings →" affordance. Approvals are the separate per-action human gate and
remain metadata-only on resolve.

---

### 6. Screen specifications

Each screen lists purpose, key components, backend mapping, and security invariants.
Endpoints marked **(new)** are catalogued in Section 9; everything else exists today in
`raiker/api/`.

#### 6.0 First run: Pre-flight onboarding

From zero to a governed first turn in four steps: bootstrap owner (guided
`/bootstrap-owner` equivalent — **(new)** `POST /api/bootstrap`, console fallback remains
canonical) → connect a model (local cards first; hosted section visually gated, showing
exactly what enabling costs: gate + threat ack + confirmation token + egress allowlist +
key env) → confirm workspace → trust summary ("Local by default. Nothing leaves this
machine unless you open an egress valve. Every AI action defaults to ask."). Mirrors
`docs/guide/getting-started-*`.

#### 6.1 Deck (the conversation)

- **Turn cards** render the governed loop:
  - **State Tape**: the four-phase ribbon from `turnPhases.ts`; expanding shows the full
    state detail (19-state machine) with skipped states faded. Advances only on real
    `AgentEvent`s.
  - **Retrieval chip** at `CONTEXT_READY`: honest render of the `retrieval_augmentation`
    event — `withheld (ask)` amber chip, `augmented` count with vector ids, nothing when
    the gate is off.
  - **Plan card**, **tool blocks** (mono args, trust badge, policy result; one line when
    allowed-and-succeeded, auto-expanded on deny/failure with `reason_code` translated by
    `reasonCodes.ts`).
  - **Permission card** for `ask` decisions: focus-trapped, risk-coded, three honest
    choices — **Approve once**, **Deny**, **Change standing mode…** (deep link to the
    Mode Dial in Security Settings; never an inline silent "always"). Critical risk shows
    the human-floor annotation.
  - **Verification card**, **checkpoint flag** (links to Recorder), **memory candidate
    cards** post-turn, and the final answer.
- **Composer:** text, `/` command entry, mode hint. Send is the single accent action.
- Backend: `POST /api/prompts`, `POST /api/prompts/stream` (fetch-based SSE),
  `GET /api/turns/{id}`, `GET /api/sessions`, `POST /api/interrupts`, approvals routes.
  A dropped stream reconciles via `GET /api/turns/{id}` (no replay-from-cursor yet).
- Invariants: nothing executes client-side; streamed text renders as untrusted model
  output; channel-sourced turns carry the quarantine container.

#### 6.2 Ops

Tasks (list, status, safe-boundary cancel — `GET /api/tasks`) today; proposals & review
(**(new)** `GET /api/proposals`, `GET /api/review/{id}`), subagents & teams (**(new)**
`GET /api/subagents`, `GET /api/teams`), and routines (**(new)** `GET /api/routines`,
with the "no background daemon" note) as those reads land. No run/execute buttons for
anything the backend cannot execute.

#### 6.3 Approvals (the Annunciator)

Risk-sorted queue with age, capability, source turn; permanent banner: *"Approval
resolution is metadata-only. Recording a decision does not execute the action."* Where
`approval_execution_relay` applies, the detail view states precisely what the relay
executor will and will not do. Detail: metadata preview, diff where applicable, resolve
with mandatory reason. Previews & audit tabs (**(new)** reads mirroring
`/approval-previews`, `/approval-audit`). Backend: `GET /api/approvals`,
`GET /api/approvals/{id}`, `POST /api/approvals/{id}/resolve`. AI principals cannot
resolve (server-enforced; controls hidden when not permitted); no payload editing; no
force execution.

#### 6.4 Memory

Layer tabs (Profile · Project · Episodic · Procedural · Eidetic · Gist · Semantic ·
Graph · User model) with source, confidence, sensitivity, retention, trust, and approval
provenance per record; secret-sensitivity records render with a non-copy, non-export
lock. Search / store / forget as governed brokered requests that create approvals (the UI
submits, then routes to the approval card). Vectors: local embedding store list/search +
`vector_get` previews; provider-space vectors shown separately with the "cross-space
search is not ranked" note; a **Retrieval augmentation** panel surfaces gate state,
decision mode, and last-turn outcomes (the handoff's named "expose retrieval
toggles/status in the web dashboard" item). Graph/codemap and skill-candidate views
read-only. Backend: **(new)** memory/vector/graph/skill-candidate reads (Section 9);
mutations only through the existing brokered/approval path. Memory writes never bypass
approval.

#### 6.5 Models

- **Provider board:** local first (llama.cpp default, Ollama, LM Studio, vLLM) with live
  health, detected models, capability flags, one-click governed **Use**. Hosted section
  (Anthropic, OpenAI, Gemini, OpenRouter) separated by the **egress valve** motif: gate
  state, threat-ack status, egress allowlist configured yes/no (never values), key env
  configured yes/no (never the key), and honest verification status per provider docs.
- **Active model panel:** current profile, model, endpoint class, tool-call mode, "no
  silent fallback" statement. **Budgets:** meters from the budget records store
  (**(new)** `GET /api/budgets`).
- Backend: `GET /api/models` (already carries hosted gate/egress metadata); **(new)**
  `POST /api/models/use`, `GET /api/models/health`.
- Invariants: selecting a hosted profile with unmet preconditions fails closed and
  renders the exact `reason_code` (`hosted_api_key_missing`, `model_connection_required`, gate
  disabled) as guidance with a deep link into the Security Settings Guarded Switch flow.

#### 6.6 Extend (plugins, channels, execution environments)

Plugins (id, version, status, permissions, signature posture, dependency pins,
install-plan viewer, runtime grants, execution records, governed **Revoke**; honest
isolation labels including the bare-subprocess ambient-network limit — **(new)** reads).
Channels: the real webhook channel + approval relay with pairing state, sender allowlist,
trust default, inbound activity (quarantined, linked to turns); every deferred connector
shown as specified-but-deferred, never enableable (`POST /api/channels/{id}/inbound`
exists; **(new)** `GET /api/channels`). Execution environments: local sandbox tiers,
container execution (image allowlist status), fail-closed remote/SSH/cloud rows with
`activation_blocked:no_executor` (**(new)** `GET /api/execution-profiles`). Allowlist and
key values are never displayed.

#### 6.7 Recorder (events, checkpoints, lifecycle)

Append-only timeline with filter chips, risk colouring, parent-child indentation for
subagents, raw payload in mono (`GET /api/events`). Checkpoints rail renders what the
backend emits — **turn checkpoints today** — with the spec taxonomy documented as the
ceiling; rewind affordances appear only where the backend supports execution, otherwise
explicitly metadata-only (`GET /api/checkpoints`, `GET /api/checkpoints/{id}`). Storage
lifecycle and exports as governed reads land (**(new)** Section 9). No edit/delete
affordances anywhere.

#### 6.8 Settings

- **Security Settings** (step-up auth wraps everything):
  - **Runtime mode** via the Guarded Switch with readiness prerequisites listed.
  - **Capability board:** all 53 capabilities grouped by tier and domain. Each row leads
    with the **Mode Dial** (ask/allow/auto/deny — owner decision, PR #104); the
    expandable detail carries gate state, `allowed_transitions`, the Guarded Switch
    (disabled with explanation when `can_current_principal_change=false` or
    `blocked_reason_code` says no executor), and readiness. Dangerous caps run the full
    checklist inside the switch cover: threat-model doc link, ack checkbox, confirmation
    token, arm. Fail-closed domains (finance, investment, medical, pregnancy/baby, CCTV,
    home security, hardware operator, remote/cloud execution) render as sealed rows:
    visible, honest, un-armable. One read populates the whole board.
  - **Decision-mode floors** always visible: critical always human; hard-denies precede
    modes; auto is deterministic by risk; permissive modes require a real executor.
    Backend: `GET/POST /api/capability-modes/{cap}/{ask|allow|auto|deny}`; tightening
    (ask/deny) applies immediately, loosening (allow/auto) goes through step-up with a
    reason — as shipped.
  - **Environment posture (read-only):** configured/not-configured indicators for
    provider key envs, plugin allowlists and scopes,
    signing keys, container image allowlist. Values never shown.
  - **Secrets:** the truthful notice — redaction/deny-secrets policy shown; *"Secret
    storage is not implemented (deferred)."*
- **Principals & Roles:** owner, principals, AI-executable and human-only roles, domain
  scopes, risk acceptances with expiry; recovery/break-glass surfaced as status
  (**(new)** `GET /api/principals` read).
- **Diagnostics (Pre-flight):** readiness checklist (`GET /api/runtime-readiness`,
  `GET /api/diagnostics`) with plain-language remediation. Never claims readiness beyond
  local single-user.
- **Docs & Help:** **shipped, and at different routes than this plan proposed.**
  Utilities → **Guide** renders the sections in `docs/guide/` through
  `GET /api/guide` and `GET /api/guide/{slug}` (`raiker/api/routes_guide.py`,
  `raiker/guide/`), resolved as a product asset rather than from a manifest file,
  with "Learn why" links from reason codes and disabled controls.
- **Preferences:** theme, density, reduced motion, State Tape verbosity. Local only.

---

### 7. Signature component library

| Component | Role | Notes |
|---|---|---|
| `GuardedSwitch` | All dangerous mutations | Cover → checklist (threat ack, token, reason) → arm; renders backend denial verbatim |
| `ModeDial` | Decision modes | Segmented ask/allow/auto/deny with floor annotations; the primary capability-row control |
| `StateTape` | Turn phases | Event-driven four-phase ribbon (`turnPhases.ts`); expand shows full state detail |
| `AnnunciatorStrip` | Pending approvals | Top-bar lights by risk; deep-links; screen-reader live region |
| `PermissionCard` | Inline `ask` decisions | Focus-trapped; approve-once / deny / change-standing-mode |
| `ReasonCode` | Every denial/block | Mono code + plain-English catalogue entry (`reasonCodes.ts`) + docs link |
| `TrustFrame` | Untrusted content | Hatched quarantine container, inert-instruction styling, source label |
| `RiskBadge` / `TrustBadge` | Everywhere | Icon + label + colour, never colour-only |
| `DiffViewer` | Proposals, approvals, verification | Inline unified diff |
| `RecorderRow` | Events | Dense mono metadata, expandable payload |
| `CheckpointFlag` | Transcript ↔ Recorder link | Rewind affordance only when backend-supported |
| `EgressValve` | Hosted providers | Closed/open state; allowlist-configured indicator |
| `PreflightList` | Readiness | Pass / attention / blocked items with remediation |
| `StopControl` | Interrupts | Two-stage guarded engage; app-wide engaged state |
| `Palette` | Navigation + commands | Slash-command parity, argument prompts, fail-closed results |
| `EmptyState` | Everywhere | Explains what would appear and how to cause it; never an endless spinner |

(The draft's `HonestyLabel` component is deferred until a backend field exists —
correction 5. Capability status derives from real gate fields only.)

---

### 8. Coverage matrix

The draft's capability-to-UI-home matrix carries over unchanged except: checkpoint rows
say "turn checkpoints today, taxonomy is spec ceiling"; the sessions row says
"resume today, fork pending a governed endpoint"; the state-machine row says 19 states;
and capability-status rows derive from gate fields, not honesty labels.

---

### 9. API additions required (read-heavy, no new authority)

Every addition is a typed read projection of an existing service through the same
auth/redaction middleware, or a thin governed pass-through to an existing service method.
Mutations reuse existing governed paths only.

1. `GET /api/docs`, `GET /api/docs/{slug}` — guide manifest + rendered markdown.
2. `POST /api/models/use`, `GET /api/models/health` — parity with `/model use|health`.
3. `GET /api/budgets` — projects `store.list_budget_records()`.
4. `GET /api/memory` (+ `/search`, `/review`, `/candidates`, `/rollback-plans`).
5. `GET /api/vectors`, `GET /api/vectors/search`, `GET /api/vectors/{id}`.
6. `GET /api/graph/status|plan|symbols|project|rollback-plan`.
7. `GET /api/skill-candidates`.
8. `GET /api/plugins`, `GET /api/plugins/{id}/records`.
9. `GET /api/channels` (connector matrix + pairing state).
10. `GET /api/execution-profiles`.
11. `GET /api/subagents`, `GET /api/teams`, `GET /api/routines`.
12. `GET /api/proposals`, `GET /api/review/{id}`, approvals previews/audit reads.
13. `GET /api/storage-lifecycle*`, `POST /api/export` (governed, evented).
14. `GET /api/principals` (+ roles, risk acceptances).
15. Optional: `POST /api/bootstrap` (guided first-run; console remains canonical).
16. Optional: governed session-fork endpoint (until then, resume only — correction 4).
17. Optional: stream replay-from-cursor on `POST /api/prompts/stream` (until then, the
    UI reconciles via `GET /api/turns/{id}` — correction 7).
18. Optional: per-capability implementation-status field on the gate read, if
    implementation labels are ever wanted in the UI (correction 5).

Frontend stack: **Vite + Svelte 5 + TypeScript** (proven in-repo, tested, CI-wired).
Token in memory only; fetch-based SSE; single loopback origin; no CORS surface; all
assets bundled (fonts included) — the built app runs fully offline.

---

### 10. Cross-cutting UX rules

- **Truthfulness:** UI copy renders only backend-confirmed states; anything deferred says
  deferred; nothing implies email sends, calendar sync, remote execution, secret storage,
  or multi-user.
- **Reason codes:** `reasonCodes.ts` maps every `reason_code` to one plain-English
  sentence, one remediation, one docs link. Unknown codes render verbatim in mono.
- **Empty/loading/error:** skeletons never exceed 800 ms without a status word; empty
  states teach; errors show the code, the human line, and a retry only where idempotent.
- **Keyboard:** ⌘K palette; ⏎ approves the focused permission card; Esc-Esc denies;
  full tab order; single high-contrast focus ring.
- **Accessibility:** WCAG AA both themes; icon+label redundancy for all risk/trust
  colour; aria-live for streaming text, annunciator changes, and STOP; permission cards
  announced as alerts; reduced-motion honoured (`a11y.test.ts` is the regression gate).
- **Responsiveness:** rail collapses under 900 px; dense tables scroll horizontally with
  pinned first columns.
- **Performance:** virtualised event and gate lists; graceful degradation when the API is
  unreachable (grey instruments, not fake green).

---

### 11. Implementation plan

Follows the repo's slice discipline (tests + validators + docs per slice; commit and push
per phase). Each workstream ships behind the web validation gate (`lint`, `check`,
`vitest`, `build`) plus `tests/test_security_regression_ui.py` and the API contract
tests.

- **W0 · Foundations (this slice):** bundled Manrope + JetBrains Mono (offline), Control
  Deck token retheme (both themes, same token names), shell polish (model/egress chip,
  wordmark), a11y re-verify. No backend change.
- **W1 · Deck:** State Tape ribbon, permission cards, retrieval chip, tool-block
  collapse/expand, settle animation.
- **W2 · Approvals + Security Settings:** annunciator strip, GuardedSwitch checklist
  flow, capability board (mode-dial-first rows, sealed rows), environment posture.
- **W3 · Models:** provider board with egress-valve motif, governed use/health, budgets
  (needs Section 9 items 2–3).
- **W4 · Recorder:** filters, checkpoint rail (turn checkpoints, honest), payload panes.
- **W5 · Memory:** layers, review queue, vectors + retrieval panel, graph views (needs
  Section 9 items 4–7).
- **W6 · Ops + Extend:** proposals/review, subagents/teams/routines, plugins, channels,
  execution environments (needs Section 9 items 8–12).
- **W7 · Onboarding + Docs & Help + polish:** pre-flight flow, `/api/docs` panel,
  contextual help links, command palette, density mode, state-aware favicon.

---

### 12. Non-goals and guardrails

- No client-side policy, gates, or authority; no secrets entry or storage; no
  localStorage tokens.
- No surface implies working email send, calendar sync, external reminders,
  finance/investment/medical/pregnancy/CCTV/home-security/hardware runtimes,
  remote/cloud execution, hosted multi-user, or in-process plugin import. Sealed means
  sealed.
- No external network request of any kind from the built app: no CDN fonts, no remote
  icons, no analytics. Loopback single-user remains the deployment truth.
- Allowlist values, keys, raw memory of secret sensitivity, and event-redacted content
  are never rendered.

**Design north star in one line:** Raiker should look like what it is — the flight deck
of a governed agent, where every switch is guarded, every action is recorded, and the
human is always the pilot in command.

### Personal-agent goal overview target

PAA-07 adds goal references/progress to existing Chat/Build/Tasks/Projects,
Approvals and Activity rather than a new authority-bearing work mode. Home
should answer what is progressing, waiting on the owner, completed, failed and
due next. Goal detail shows success criteria, plan/tasks, usable artifacts,
verified receipts, named blockers, budgets and pause/resume/stop. Delivery
failure is distinct from work failure. Planned controls stay hidden until their
routes and executors exist. See [the target spec](../plans/PERSONAL_AUTONOMOUS_AGENT_SPEC.md).

## Reference requirements matrix (superseded by reference platform compatibility)

> Merged from `docs/architecture/DESIGN_HISTORY.md` on 2026-11-16; the original file was removed.

This document maps reference agent-platform concepts into Raiker requirements. It exists to prevent shallow imitation: if Raiker borrows an idea from coding agents, local-first tools, model runtimes, memory systems, plugin systems, channel gateways, graph/codemap tools, or OWASP GenAI controls, the requirement must be mapped to a Raiker contract, event, storage location, policy rule, test, and build phase.

Reference systems are inspiration only. Raiker's source of truth is this repository's documentation.

---

### Mapping Rules

Each reference capability must map to:

1. Raiker capability name;
2. build phase;
3. canonical spec file;
4. contracts affected;
5. storage affected;
6. events emitted;
7. policy/security controls;
8. acceptance tests;
9. out-of-scope notes.

If any field is missing, the requirement is not builder-proof.

---

### Core Agent Runtime Requirements

| Reference capability | Raiker requirement | Phase | Canonical docs | Acceptance proof |
|---|---|---:|---|---|
| Agentic loop: gather context, act, observe, verify | Deterministic runtime state machine with context, planning, policy, execution, observation, verification, response, checkpoint | Phase 1 | `docs/architecture/RUNTIME_STATE_MACHINE.md`, `docs/architecture/RUNTIME_ORCHESTRATION_SPEC.md` | State transition and event sequence tests |
| Tool-mediated local work | Tool Broker is the only path to filesystem/search/command actions | Phase 1 | `docs/architecture/TOOLS_AND_PERMISSIONS_SPEC.md` | Broker tests prove no tool runs without policy |
| Permissioned actions | Static policy returns `allow`, `deny`, or `needs_approval` | Phase 1 | `docs/architecture/SECURITY_AND_POLICY.md` | Policy tests for allow/deny/approval |
| Approval-gated risky actions | Approval request bound to exact action ID | Phase 1 | `docs/architecture/API_AND_CONTRACT_SCHEMAS.md` | Approval mismatch tests |
| Append-only audit | JSONL events plus SQLite index | Phase 1 | `docs/architecture/EVENT_CATALOG.md`, `docs/architecture/STORAGE_DATABASE_AND_SEARCH_SPEC.md` | Event append/index tests |
| Checkpoint/resume | Checkpoint manifest after completed turn; later restore/fork | Phase 1-2 | `docs/architecture/CHECKPOINTING_AND_REWIND_SPEC.md` | Checkpoint write/read and restore approval tests |
| Interruptible work | Pause/cancel/steer and side questions at safe boundaries | Phase 2 | `docs/architecture/RUNTIME_ORCHESTRATION_SPEC.md` | Side question and safe-boundary tests |

---

### Interface And Client Requirements

| Reference capability | Raiker requirement | Phase | Canonical docs | Acceptance proof |
|---|---|---:|---|---|
| Terminal coding agent | `raiker` launches first local terminal client | Phase 1 | `README.md`, `docs/architecture/COMMANDS_AND_INTERACTIVE_MODE_SPEC.md` | Global command smoke test |
| Rich local workspace | TUI panels for task, approval, checkpoint, event, memory, model, permission, diagnostics | Phase 2 | `docs/architecture/DESIGN_HISTORY.md`, `docs/architecture/VISUAL_DESIGN_SPEC.md` | TUI event-driven panel tests |
| Desktop/web dashboard | Local app surfaces for sessions, tasks, approvals, events, memory, graph, plugins, channels | Phase 3 | `docs/architecture/DESIGN_HISTORY.md`, `docs/architecture/VISUAL_DESIGN_SPEC.md` | Gateway parity and event stream tests |
| Mobile app control | Apple/Android apps are equal primary interfaces, not notification-only companions | Phase 3 | `docs/architecture/DESIGN_HISTORY.md`, `docs/architecture/VISUAL_DESIGN_SPEC.md`, `docs/architecture/CHANNELS_SPEC.md` | Stale mobile approval rejection tests |
| Chat/channel access | External messages normalise into ChannelMessageEnvelope and gateway path | Phase 4 | `docs/architecture/CHANNELS_SPEC.md` | Pairing, sender trust, rate-limit tests |
| Interface parity | Every enabled interface uses same action contracts and policy path | Phase 1-5 | `docs/architecture/FEATURE_COVERAGE_MATRIX.md` | Equal-interface invariant tests |

---

### Model Runtime Requirements

| Reference capability | Raiker requirement | Phase | Canonical docs | Acceptance proof |
|---|---|---:|---|---|
| Deterministic test model | `mock` model provider for offline tests | Phase 1 | `docs/architecture/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` | Mock provider deterministic tests |
| Local model providers | Ollama (native default profile; no model shipped — the owner chooses one of the models a running Ollama serves, FIXED-737), llama.cpp server, LM Studio, OpenAI-compatible local endpoints | Phase 2 | `docs/architecture/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md`, `raiker/config/model-profiles.json` | Provider profile and chat/tool-call tests |
| Hosted provider controls | Hosted providers disabled until privacy/egress/budget policy allows | Phase 3-5 | `docs/architecture/SECURITY_AND_POLICY.md`, `docs/architecture/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` | Hosted fallback denied tests |
| Tool-call parsing | Model output parsed as untrusted structured proposal | Phase 1-2 | `docs/architecture/API_AND_CONTRACT_SCHEMAS.md` | Invalid model tool call tests |
| Context limits | Context budget and source priority before model calls | Phase 2 | `docs/architecture/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` | Truncation priority tests |

---

### Memory, Graph, And Learning Requirements

| Reference capability | Raiker requirement | Phase | Canonical docs | Acceptance proof |
|---|---|---:|---|---|
| Working memory | Current-turn scratchpad and task context | Phase 1 | `docs/architecture/MEMORY_AND_CONTEXT_STRATEGY.md` | Context gatherer tests |
| Durable memory | Profile/project/episodic/procedural memory with governance | Phase 2 | `docs/architecture/MEMORY_AND_CONTEXT_STRATEGY.md` | Memory approval and provenance tests |
| Eidetic observation | Raw observation metadata with retention and gist memory | Phase 2 | `docs/architecture/EIDETIC_MEMORY_AND_LEARNING_SPEC.md` | Retention and gist creation tests |
| Semantic search | Local vector metadata with sensitivity/provenance filters | Phase 3 | `docs/architecture/STORAGE_DATABASE_AND_SEARCH_SPEC.md` | Sensitivity-filtered retrieval tests |
| Graph/codemap | SQLite graph nodes/edges plus recursive CTEs | Phase 3 | `docs/architecture/GRAPH_MEMORY_AND_CODEMAP_SPEC.md`, `docs/architecture/STORAGE_DATABASE_AND_SEARCH_SPEC.md` | Impact-analysis CTE tests |
| Skill learning | Verified task trajectory may become proposed skill only after tests and approval | Phase 2-3 | `docs/architecture/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`, `docs/architecture/PLUGIN_SYSTEM_SPEC.md` | Skill proposal/approval tests |

---

### Plugin, Hook, And Extension Requirements

| Reference capability | Raiker requirement | Phase | Canonical docs | Acceptance proof |
|---|---|---:|---|---|
| Lifecycle hooks | Hook events with bounded decision authority | Phase 2 | `docs/architecture/HOOKS_SPEC.md` | Hook cannot bypass managed deny |
| Plugin manifest | Explicit manifest, permissions, trust, supply-chain metadata | Phase 3 | `docs/architecture/PLUGIN_SYSTEM_SPEC.md` | Manifest validation tests |
| Permission diff | Show expanded permissions before enable/update | Phase 3 | `docs/architecture/PLUGIN_SYSTEM_SPEC.md` | Permission diff tests |
| Plugin tools | Plugin tools register through broker only | Phase 3 | `docs/architecture/TOOLS_AND_PERMISSIONS_SPEC.md` | Plugin tool broker-route tests |
| Plugin channels | Channel plugins require pairing/sender policy | Phase 3-4 | `docs/architecture/CHANNELS_SPEC.md` | Unknown sender rejection tests |

---

### Execution And Multi-Agent Requirements

| Reference capability | Raiker requirement | Phase | Canonical docs | Acceptance proof |
|---|---|---:|---|---|
| Subagents | Bounded specialist agents with parent verification | Phase 4 | `docs/architecture/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md` | Parent verification and cancellation tests |
| Multi-agent teams | Planner/executor/critic patterns with limits | Phase 4-5 | `docs/architecture/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md` | Budget/depth/runtime tests |
| Worktree/container execution | Explicit execution profiles with snapshots/artifacts | Phase 4 | `docs/architecture/EXECUTION_ENVIRONMENTS_SPEC.md` | Profile and cleanup tests |
| SSH/VPS/Kubernetes/cloud execution | Policy-gated remote execution with resource/cost controls | Phase 4-5 | `docs/architecture/EXECUTION_ENVIRONMENTS_SPEC.md` | Egress/resource/budget tests |

---

### OWASP GenAI Security Requirements

| Risk area | Raiker requirement | Phase | Canonical docs | Acceptance proof |
|---|---|---:|---|---|
| Prompt injection | Treat prompts/files/tool outputs/channel messages as untrusted | Phase 1-5 | `docs/architecture/THREAT_MODEL.md`, `docs/architecture/OWASP_GENAI_SECURITY_MAPPING.md` | Injection fixture tests |
| Sensitive information disclosure | Redact secrets and block unsafe egress | Phase 1-5 | `docs/architecture/SECURITY_AND_POLICY.md` | Secret redaction and hosted-deny tests |
| Supply chain | Dependencies/plugins/providers need provenance and trust controls | Phase 3-5 | `docs/architecture/PLUGIN_SYSTEM_SPEC.md` | Signature/checksum and permission-diff tests |
| Excessive agency | Bounded tools, approvals, subagent limits, budgets | Phase 1-5 | `docs/architecture/THREAT_MODEL.md` | Approval, depth, budget, cancellation tests |
| Insecure output handling | Model output is parsed, validated, and policy-reviewed | Phase 1-5 | `docs/architecture/API_AND_CONTRACT_SCHEMAS.md` | Invalid structured output tests |
| Data poisoning | Memory and graph writes require provenance and trust labels | Phase 2-5 | `docs/architecture/MEMORY_AND_CONTEXT_STRATEGY.md` | Poisoned memory candidate tests |

---

### Builder Use

When implementing a feature, use this matrix to answer:

- Which reference concept am I implementing?
- Which Raiker requirement owns it?
- Which build phase allows active wiring?
- Which contract/event/storage/policy docs apply?
- Which tests prove it is complete?
- Which phase-scheduled boundaries must remain disabled?

If the answer is unclear, update the docs before coding.
