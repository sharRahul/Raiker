# Raiker Web UI/UX Design Plan: "Control Deck" (corrected)

> **Status:** adopted design plan, corrected against the codebase as of 2026-07-10.
> This document supersedes the draft Control Deck plan and the previous web UI direction.
> Canonical implementation truth remains `docs/IMPLEMENTATION_STATUS.md` and `docs/HANDOFF.md`;
> where this plan and the code disagree, the code wins and this plan must be updated.

---

## 0. Corrections applied to the draft plan

The draft was verified claim-by-claim against the repository. These corrections are
binding for implementation; everything else in the draft carries over.

1. **Sources:** `docs/UI-implementation/*` no longer exists (deleted as superseded).
   The acceptance anchors are the living test suites: `tests/test_security_regression_ui.py`
   (M7 security regression), `tests/test_api_contract_schemas.py`,
   `tests/test_api_m5_security_settings.py`, and `apps/web/src/a11y.test.ts`.
   Risk classes come from `docs/foundation/06_SECURITY_MODEL.md` (which exists).
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
   `test_only`) live in `docs/FEATURE_COVERAGE_MATRIX.md`; `CapabilityGateView` has no such
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
   fonts as local variable-weight woff2 assets under `apps/web/src/assets/fonts/`
   (SIL OFL 1.1, license file alongside). **No external font, CSS, or CDN request of any
   kind** — a Google Fonts fetch would silently break "nothing leaves this machine".
   Manrope carries display and UI text (its geometric, engineered character suits the
   instrument-panel identity); JetBrains Mono carries machine-verbatim output.
9. **Reuse the tested logic layer.** `apps/web/src/lib/` (api client, `apiTypes.ts`,
   `capabilityModel.ts`, `turnPhases.ts` — which already implements the four-phase
   gather→plan→act→verify grouping — `statusMaps.ts`, `reasonCodes.ts`, `theme.ts`,
   `nav.ts`) and the security/a11y/contract test suites are kept. The redesign replaces
   tokens, components, and views on top of that layer; it is not a rewrite.

---

## 1. Purpose and sources

This plan defines the target web UI/UX for Raiker's local single-user web surface
(`raiker-web` + `apps/web`), designed to scale into the Phase 8 multi-surface vision
without redesign.

Verified sources: `README.md`, `SECURITY.md`, `docs/HANDOFF.md`,
`docs/IMPLEMENTATION_STATUS.md`, `docs/FEATURE_COVERAGE_MATRIX.md`,
`docs/foundation/06_SECURITY_MODEL.md`, `docs/DECISION_MODES_SPEC.md`,
`docs/CHANNELS_SPEC.md`, `docs/CHECKPOINTING_AND_REWIND_SPEC.md`,
`docs/MEMORY_AND_CONTEXT_STRATEGY.md`, `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`,
`docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md`, `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md`,
`docs/PLUGIN_SYSTEM_SPEC.md`, `docs/RAIKER_TOOL_AND_PLUGIN_CATALOG.md`,
`docs/SECURITY_ARCHITECTURE.md`, `docs/guide/manifest.json`, the threat-model set, and
the code: `raiker/phase_gates.py` (53 capabilities), `raiker/runtime/executors/__init__.py`
(`REAL_EXECUTOR_CAPABILITIES`, 29 integrated), `raiker/api/routes_*.py` (31 endpoints),
`raiker/control/dtos.py` (gate DTO fields), `raiker/runtime/state_machine.py` (19 states),
`raiker/cli/commands.py` (~80 slash commands), and `apps/web/src` (kept logic layer).

### The goal this design serves (from `docs/HANDOFF.md`)

Raiker is a full-fledged, secure AI agent that connects to **any** backend LLM (local
llama.cpp, Ollama, LM Studio; home-lab vLLM; hosted Anthropic, OpenAI, Gemini,
OpenRouter), where **the choice belongs to the user**, and **every capability is
governed, default-ask, human-governed, and fail-closed where required**. The UI's job is
to make that posture effortless to see, trust, and operate, and to make model choice a
first-class, one-screen experience.

### Posture this design is built on (HANDOFF part 8)

Integrated capabilities (the 29 in `REAL_EXECUTOR_CAPABILITIES`) default to
`enabled_runtime`; non-integrated capabilities stay `disabled` and fail closed. Safety is
per-action: decision modes (default `ask`), the critical-risk human floor, PolicyEngine
hard-denies, and executor-level env allowlists. The primary daily surface is the
per-action decision, not the gate flip.

---

## 2. Design goals and principles

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

## 3. The iconic identity: "Control Deck"

### 3.1 Concept

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

### 3.2 Mark and wordmark

The shipped shield-R monogram stays (it already reads "governed by design" and is
established in the favicon). The wordmark sets RAIKER in Manrope 700 with wide tracking.
State-aware favicon tinting (idle / turn in flight / approvals pending / STOP) is a
polish-phase item.

### 3.3 Motion signature

One easing (`cubic-bezier(0.2, 0, 0, 1)`, 160–240 ms) and three moves only:

1. **Arm:** guarded covers open, then the switch translates with a click highlight.
2. **Advance:** the State Tape's active segment fills 200 ms on each real transition.
   No idle animation, no fake progress.
3. **Settle:** resolved governance cards compress to a one-line receipt.

`prefers-reduced-motion` collapses all three to opacity changes. Nothing loops.

---

## 4. Design tokens

Implemented in `apps/web/src/app.css`. Components consume tokens only — never raw
colours — so both themes stay in lockstep. Existing token *names* are kept so the
component layer needs no changes.

### 4.1 Colour

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

**Risk scale** (from `docs/foundation/06_SECURITY_MODEL.md`): low = neutral;
medium = amber; high = orange; critical = red with a 2 px left rule and shield-alert
icon. **Trust scale:** trusted = calm green; authenticated = blue; untrusted = hatched
amber quarantine border. All pairs meet WCAG AA in both themes; risk and trust are never
colour-only (icon + text label always accompany).

### 4.2 Typography — bundled, offline

- **Display + UI:** **Manrope** (variable 200–800), self-hosted woff2
  (`assets/fonts/manrope-*.woff2`). Wordmark and view titles at 700, UI text 400–600.
- **Mono:** **JetBrains Mono** (variable 100–800), self-hosted woff2. All code, diffs,
  tool arguments, event payloads, ids, and reason codes. The sans/mono split is a trust
  signal: mono means "machine output, verbatim".
- System-font fallback stacks remain in place so the UI degrades gracefully if an asset
  is ever missing.
- Scale (px/line): 28/34 display, 20/28 title, 15/22 body, 13/18 caption, 12.5/18 mono.
  A **compact density** toggle (preferences, polish phase) drops body to 14/20.

### 4.3 Space, radius, elevation, iconography

- 4 px base grid; component paddings 8/12/16/24; page gutters 24 (desktop) / 16 (narrow).
- Radius: 6–8 px controls, 10–12 px cards, full round only for STOP and status dots.
- Elevation by stroke and subtle glow rather than heavy shadows; one shadow token
  reserved for modals.
- Icons: the existing inline SVG set (`icons.ts`) extended with the brand glyphs as
  needed: guarded switch, gate bar, annunciator light, checkpoint flag, quarantine hatch,
  egress valve. Stroke 1.5 px. No external icon fonts.

---

## 5. Information architecture

### 5.1 Navigation model

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

### 5.2 The mutation funnel (unchanged security model)

All runtime mutation (runtime modes, capability gates, decision modes, dangerous-cap
enablement) lives in **one** place — Settings → Security Settings — behind step-up auth.
Everywhere else, capability and gate surfaces are read-only status views with a "Change
in Security Settings →" affordance. Approvals are the separate per-action human gate and
remain metadata-only on resolve.

---

## 6. Screen specifications

Each screen lists purpose, key components, backend mapping, and security invariants.
Endpoints marked **(new)** are catalogued in Section 9; everything else exists today in
`raiker/api/`.

### 6.0 First run: Pre-flight onboarding

From zero to a governed first turn in four steps: bootstrap owner (guided
`/bootstrap-owner` equivalent — **(new)** `POST /api/bootstrap`, console fallback remains
canonical) → connect a model (local cards first; hosted section visually gated, showing
exactly what enabling costs: gate + threat ack + confirmation token + egress allowlist +
key env) → confirm workspace → trust summary ("Local by default. Nothing leaves this
machine unless you open an egress valve. Every AI action defaults to ask."). Mirrors
`docs/guide/getting-started-*`.

### 6.1 Deck (the conversation)

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

### 6.2 Ops

Tasks (list, status, safe-boundary cancel — `GET /api/tasks`) today; proposals & review
(**(new)** `GET /api/proposals`, `GET /api/review/{id}`), subagents & teams (**(new)**
`GET /api/subagents`, `GET /api/teams`), and routines (**(new)** `GET /api/routines`,
with the "no background daemon" note) as those reads land. No run/execute buttons for
anything the backend cannot execute.

### 6.3 Approvals (the Annunciator)

Risk-sorted queue with age, capability, source turn; permanent banner: *"Approval
resolution is metadata-only. Recording a decision does not execute the action."* Where
`approval_execution_relay` applies, the detail view states precisely what the relay
executor will and will not do. Detail: metadata preview, diff where applicable, resolve
with mandatory reason. Previews & audit tabs (**(new)** reads mirroring
`/approval-previews`, `/approval-audit`). Backend: `GET /api/approvals`,
`GET /api/approvals/{id}`, `POST /api/approvals/{id}/resolve`. AI principals cannot
resolve (server-enforced; controls hidden when not permitted); no payload editing; no
force execution.

### 6.4 Memory

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

### 6.5 Models

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
  renders the exact `reason_code` (`hosted_api_key_missing`, `model_egress_denied`, gate
  disabled) as guidance with a deep link into the Security Settings Guarded Switch flow.

### 6.6 Extend (plugins, channels, execution environments)

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

### 6.7 Recorder (events, checkpoints, lifecycle)

Append-only timeline with filter chips, risk colouring, parent-child indentation for
subagents, raw payload in mono (`GET /api/events`). Checkpoints rail renders what the
backend emits — **turn checkpoints today** — with the spec taxonomy documented as the
ceiling; rewind affordances appear only where the backend supports execution, otherwise
explicitly metadata-only (`GET /api/checkpoints`, `GET /api/checkpoints/{id}`). Storage
lifecycle and exports as governed reads land (**(new)** Section 9). No edit/delete
affordances anywhere.

### 6.8 Settings

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
    `RAIKER_MODEL_EGRESS_ALLOWLIST`, provider key envs, plugin allowlists and scopes,
    signing keys, container image allowlist. Values never shown.
  - **Secrets:** the truthful notice — redaction/deny-secrets policy shown; *"Secret
    storage is not implemented (deferred)."*
- **Principals & Roles:** owner, principals, AI-executable and human-only roles, domain
  scopes, risk acceptances with expiry; recovery/break-glass surfaced as status
  (**(new)** `GET /api/principals` read).
- **Diagnostics (Pre-flight):** readiness checklist (`GET /api/runtime-readiness`,
  `GET /api/diagnostics`) with plain-language remediation. Never claims readiness beyond
  local single-user.
- **Docs & Help:** renders `docs/guide/manifest.json` via **(new)** `GET /api/docs` +
  `GET /api/docs/{slug}`, with "Learn why" links from every reason code and disabled
  control.
- **Preferences:** theme, density, reduced motion, State Tape verbosity. Local only.

---

## 7. Signature component library

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

## 8. Coverage matrix

The draft's capability-to-UI-home matrix carries over unchanged except: checkpoint rows
say "turn checkpoints today, taxonomy is spec ceiling"; the sessions row says
"resume today, fork pending a governed endpoint"; the state-machine row says 19 states;
and capability-status rows derive from gate fields, not honesty labels.

---

## 9. API additions required (read-heavy, no new authority)

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

## 10. Cross-cutting UX rules

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

## 11. Implementation plan

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

## 12. Non-goals and guardrails

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
