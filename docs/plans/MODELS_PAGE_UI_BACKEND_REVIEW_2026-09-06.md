# Raiker Models Page UI + Backend Review — 2026-09-06

## Implementation status — 2026-09-07

Waves 0 to 4 are implemented and verified against a live runtime holding real
Anthropic, OpenAI and OpenRouter credentials, each connected through the
product's own flow rather than seeded into the store. Recorded as
[FIXED-451](FIXED_ITEMS.md#fixed-451--five-stores-five-read-paths-and-no-way-to-say-which-was-wrong),
[FIXED-452](FIXED_ITEMS.md#fixed-452--design-had-no-model-default-of-its-own)
and
[FIXED-453](FIXED_ITEMS.md#fixed-453--the-models-page-was-a-filing-system-for-its-own-rows).

| Item | State |
|---|---|
| MODEL-01 authoritative selection/effective contract | Done — `raiker/models/decision.py`, `GET /api/model-decision(s)` |
| MODEL-02 Design surface default | Done |
| MODEL-03 Overview replaces the six-tab first impression | Done |
| MODEL-04 compact My models inventory | Done |
| MODEL-05 local runtime as its own subsection | Done |
| MODEL-06 simplified local library | Done — `Deploy` left the library |
| MODEL-07 Hosted as connections | Done — Test moved to the row's overflow |
| MODEL-08 one model picker per provider | Already satisfied by `AvailableModels`; the row no longer repeats `Use` beside it |
| MODEL-09 Hugging Face as "Add local model" | Partial — it lives under Add model; its internal flow is not yet step-oriented |
| MODEL-10 exception- and progress-led Activity | Done |
| MODEL-11 combined routing, defaults and effective model | Done — Default and Effective are separate columns |
| MODEL-12 Pricing merged with Usage | Done |
| MODEL-13 health as exceptions | Done — the Overview shows only what needs a person |
| MODEL-14 return-and-detect for vendor links | Partial — connect and validate happen inside Raiker; the runtime installers still open a vendor page |
| MODEL-15 page/action budget | Done — one primary action and one overflow per repeated row |

The acceptance tests under *Backend/state acceptance tests* are covered by
`tests/test_model_decision.py`, `tests/test_surface_model_defaults.py` and the
live round in `apps/web/e2e/composer-models-redesign-live.spec.ts`.

---

## Scope

This is a focused review of the Models experience at `main` commit `ac32915101de6b6562b09b1e09c4f76a24b00878`.

It reviews the Models page as one end-to-end product flow, not just as a collection of panels:

- current Models navigation and information architecture;
- current model-selection semantics;
- local runtimes and local model library;
- hosted-provider configuration;
- Hugging Face discovery/download/conversion;
- durable model operations/activity;
- routing/fallbacks and per-surface defaults;
- pricing/usage;
- readiness/health;
- the API/state contract that determines which model is selected, available, running and effective;
- how this should work across the first-class Work surfaces: **Chat | Build | Design**.

This is a review/plan only. No production code is changed here.

---

# Executive assessment

The Models area has accumulated many individually useful controls, but the product model is no longer clear enough.

The central problem is that several different ideas are exposed with overlapping language and controls:

1. **Selected model** — the model the owner has chosen.
2. **Surface default** — where Chat/Build/Design/Tasks should start when there is no explicit per-turn choice.
3. **Available model** — a model kept in a provider's chooser.
4. **Configured provider/profile** — credentials or endpoint are configured.
5. **Ready model** — the provider/runtime can answer now.
6. **Running/served model** — a managed local runtime process is actually running.
7. **Fallback/effective model** — the model Raiker will really use when routing/fallback policy changes the answer.

Those are not synonyms. The current page often makes them look like variations of “active”. That creates two user-visible symptoms:

- there are too many buttons because each subsystem exposes its own lifecycle control;
- a model can appear to “stop being active” even though one underlying state was persisted, because the UI is showing a different state or re-deriving it from another view.

The Models experience should therefore be redesigned around one question first:

> **What model will Raiker use for the work I am doing now, and why?**

Everything else is management detail.

---

# Verified implementation observations

## 1. The page has six top-level tabs

The current Models view declares:

```text
Local
Hosted
Hugging Face
Activity
Routing
Pricing
```

That split is logically defensible, but it exposes implementation categories rather than starting from the user's main decision: which model is answering now.

## 2. Model selection is persisted through a backend endpoint

The UI's `select()` path calls the model-selection API, closes the picker, reloads the Models snapshot and notifies the shell. So the current implementation is not simply “selection exists only in frontend state”.

The dashboard read model also marks model profiles as selected from persisted model state, and the Models view deliberately keeps the selected profile visible even when readiness has failed.

Therefore the reported “models do not stay active” issue should **not** be fixed by merely adding another localStorage flag or another frontend selected state. That would create a second source of truth.

## 3. Global selection and surface defaults are separate concepts

There is a global model-selection path and a separate `/api/surface-models` preference path.

The surface-default endpoint explicitly says it is only a preference for where a surface's picker starts; it does not grant readiness and the actual turn still identifies the exact profile/model.

That separation is reasonable, but the UI must explain it.

## 4. Design is missing from the backend surface-default allowlist

The current backend declares:

```text
chat
build
tasks
schedule
```

as the supported model-default surfaces.

**Design is absent.**

That is inconsistent with Raiker's corrected Work model of:

```text
Chat | Build | Design
```

and should be fixed before Design becomes a first-class work surface. A Design model choice should not silently depend on a generic/global default while Chat and Build have explicit surface state.

## 5. Local-runtime controls combine too many jobs in one row

A local framework row currently exposes, depending on state:

```text
Test
Details
Select
Scan folders
Serve selected
```

plus up to four model-slot selectors.

This is too much simultaneous action vocabulary for a single repeated row. `Select` and `Serve` are also different concepts but visually adjacent, which makes it easy to interpret “selected” as “running”.

## 6. Local library repeats scan/deploy actions

The local library contains:

```text
Scan now
Browse
Add and scan
Remove
Deploy
```

Scanning is offered in more than one local-model context, while deployment can also be initiated from local-framework controls. The repeated controls make the user learn backend topology instead of a single model-management flow.

## 7. Provider setup mixes installation, connection and model acquisition

The local provider setup includes vendor installer links and Ollama pull controls, while the local library separately manages approved folders/deployment. These are legitimate capabilities, but they should not all have equal visual priority.

## 8. Hugging Face is a full multi-step workflow inside one page

The Hugging Face panel includes:

- optional access-token setup;
- trending content;
- catalogue search;
- repository selection;
- variant selection;
- download preview;
- download/cancel;
- optional conversion preview;
- conversion;
- destination/library integration.

That workflow is valuable, but it is large enough to be treated as an **Add model flow**, not as one of six equal Models tabs.

## 9. Activity already polls automatically but still exposes manual Refresh

The model-operations panel uses adaptive polling while work is active/idle, yet also exposes a persistent `Refresh` button.

Manual refresh should be an error-recovery affordance, not a primary normal-state control when the page is already following the durable operation stream.

## 10. Usage has its own provider-data Refresh button

Usage similarly exposes `Refresh provider data`. Provider-native quota reads may legitimately be on-demand, but this should be secondary because it is not the primary model-management task.

---

# State model that the UI should use

The Models page should stop using “active” as an umbrella term.

Use these exact concepts consistently:

| Term | Meaning | Persisted? | Can be unavailable? |
|---|---|---:|---:|
| **Selected** | Owner's explicit model choice for current scope | Yes | Yes |
| **Default** | Starting choice for Chat/Build/Design/Task surface | Yes | Yes |
| **Available** | Kept in the model chooser | Yes | Yes |
| **Configured** | Credentials/endpoint/profile exist | Yes | Yes |
| **Ready** | Current readiness check says a turn can use it | Evidence/state | No — by definition |
| **Running** | Managed local model process is serving | Runtime state | No — by definition |
| **Effective** | Model this turn will actually use after explicit choice/default/routing/fallback | Derived | Must be explainable |

### UI invariant

> A selected/default model must never disappear merely because it is not currently ready or running.

Instead show:

```text
Selected · unavailable
```

with the reason and the fix.

Do not silently replace it with the first ready model in the UI. If routing actually uses a fallback, state that explicitly:

```text
Selected: Claude Sonnet 4.6
Using: GPT-5.6 because Anthropic is unavailable
```

That makes persistence observable instead of mysterious.

---

# MODEL-01 — Create one authoritative selection/effective-model contract

**Priority: P1 — Effort: Medium — Impact: Very high**

The current persistence machinery exists, but the product surfaces global selection, provider-level defaults, surface defaults, readiness, fallback and local runtime state through different read paths.

The backend should expose one normalized read model for the current model decision.

Recommended response shape:

```json
{
  "scope": {
    "surface": "build",
    "project_id": "..."
  },
  "selected": {
    "profile_id": "...",
    "model": "...",
    "source": "explicit|project|surface_default|global_default"
  },
  "effective": {
    "profile_id": "...",
    "model": "...",
    "reason": "selected|fallback|routing_policy"
  },
  "ready": true,
  "running": null,
  "problem": null,
  "revision": 17
}
```

The exact endpoint name is less important than the invariant: Models page, top-bar/composer model picker, Chat, Build, Design and task creation must all read the same authoritative decision contract.

### Acceptance

- select a hosted model;
- reload the app;
- navigate Models → Chat → Build → Models;
- selected model remains selected;
- if unavailable, it remains visible as selected/unavailable;
- effective fallback is separately shown rather than rewriting the selection.

---

# MODEL-02 — Add Design to surface model defaults

**Priority: P1 — Effort: Low — Impact: High**

Add `design` to the supported model surfaces and test the complete persistence round trip.

The intended Work defaults become:

```text
Chat       default conversational model
Build      default coding/agent model
Design     default image/design-capable model
Tasks      captured task model
Schedule   captured scheduled-task model
```

Design may eventually need capability-aware filtering rather than the same catalogue as Chat, but it still needs a persisted surface-level default.

---

# MODEL-03 — Replace the six-tab first impression with an Overview

**Priority: P1 — Effort: Medium — Impact: Very high**

Recommended primary navigation:

```text
Overview | My models | Add model | Runtime & routing | Usage
```

`Activity` should become a global/Models activity drawer or subsection of Runtime & routing rather than a peer to “Local”. Pricing belongs under Usage or model details.

## Proposed Overview

```text
Models
Choose what powers Chat, Build and Design.
                                      [ Add model ]

CURRENT WORK
Build
Claude Sonnet 4.6                 Ready
Anthropic · Hosted
Selected explicitly for this project
                         [ Switch model ]

WORK DEFAULTS
Chat        GPT-5.6          Ready
Build       Claude Sonnet    Ready
Design      GPT Image        Ready
Tasks       Use project/default
                                      [ Edit defaults ]

NEEDS ATTENTION                only if non-empty
Ollama is configured but not running             [ Fix ]
OpenRouter credential expired                    [ Reconnect ]

READY ALTERNATIVES
Gemini 3 Pro
GPT-5.6
Local Qwen ...
```

No provider-admin detail should appear above the fold unless it changes the user's model choice.

---

# MODEL-04 — Redesign “My models” as a compact inventory

**Priority: P1 — Effort: Medium — Impact: Very high**

Use list/table rows instead of control-heavy provider cards.

Recommended row:

```text
Claude Sonnet 4.6
Anthropic · Hosted              Ready      Build default
                                            [ Use ] [ ⋯ ]
```

For local:

```text
Qwen 3 30B Q4_K_M
llama.cpp · Local              Stopped     Available
                                            [ Start ] [ ⋯ ]
```

### Visible row actions

At most **one primary contextual action**:

- `Use` if ready and not selected;
- `Start` if selected/local but stopped;
- `Fix` if configured but not usable;
- no primary action if already selected and ready.

### Overflow menu

Put lower-frequency actions in `⋯`:

- Details
- Test connection
- Set as Chat default
- Set as Build default
- Set as Design default
- Configure provider
- Start/Stop local runtime
- Remove model / disconnect

Do not show `Test`, `Details`, `Select`, `Scan folders`, and `Serve selected` simultaneously on every local framework row.

---

# MODEL-05 — Make local runtime management a separate operational subsection

**Priority: P1 — Effort: Medium — Impact: High**

The current local framework UI combines library selection, runtime slots, connection testing and current model selection.

Recommended split:

## My models

Shows local models just like hosted models.

## Runtime & routing → Local serving

```text
llama.cpp
Running · 2/4 slots

Slot 1   Qwen 30B       127.0.0.1:....   Running
Slot 2   Llama 8B       127.0.0.1:....   Running
Slot 3   Empty
Slot 4   Empty

[ Manage serving ]
```

Inside manage serving:

- assign model to slot;
- start/stop/restart;
- inspect endpoint/logs;
- rescan model library only when needed.

Selection must remain independent from serving. A local model can be:

```text
Selected + stopped
Running + not selected
Selected + running
```

and the UI must represent those combinations correctly.

---

# MODEL-06 — Simplify the local library

**Priority: P1/P2 — Effort: Low/Medium — Impact: Medium/high**

Current controls include `Scan now`, `Browse`, `Add and scan`, per-folder `Remove`, and per-model `Deploy`.

Recommended page:

```text
Local library                                [ Add folder ]
2 approved folders · Last scanned 3 min ago  [ Rescan ]

Qwen 30B Q4_K_M         18.4 GB · GGUF       Ready to serve
Llama 8B Q5             5.1 GB · GGUF        Ready to serve
```

Clicking **Add folder** opens the path picker immediately. Manual absolute-path entry can live in an advanced option.

Do not expose `Deploy` here. Library answers “what is on disk”; Runtime answers “what is serving”.

This removes one of the main state-conflation problems.

---

# MODEL-07 — Treat Hosted as connections, not as a model-control dashboard

**Priority: P1 — Effort: Medium — Impact: High**

Hosted page should answer:

```text
Which providers are connected?
Are their credentials valid?
Which models from each provider are kept available?
```

Recommended provider row:

```text
Anthropic
Connected · last checked 4 min ago
12 models available · 3 kept in Raiker
                                      [ Manage ]
```

Inside Manage:

```text
Connection
Available models
Advanced endpoint
Usage/admin key if supported
Disconnect
```

Do not put permanent Test/Details/Select controls on every provider card. Test should be:

- automatic after connect/save;
- available in Manage for troubleshooting;
- surfaced as `Retry`/`Fix` only after failure.

---

# MODEL-08 — Replace “Keep available + Use on every catalogue row” with one model picker

**Priority: P1 — Effort: Medium — Impact: High**

`AvailableModels` currently needs both a checkbox/switch and a `Use` button beside models because “available” and “default” are different concepts.

The concepts are valid but the row becomes interaction-heavy.

Recommended pattern:

```text
Provider: OpenAI
Models shown in Raiker                         [ Manage list ]

✓ GPT-5.6
✓ GPT-5.6 mini
✓ o4-mini
```

`Manage list` opens the searchable checkbox picker.

Choosing the **current/default model** happens from the global model picker / Work defaults, not inside the provider's catalogue-management list.

This removes dozens/hundreds of repeated `Use` controls from large catalogues.

---

# MODEL-09 — Reframe Hugging Face as “Add local model”

**Priority: P2 — Effort: Medium — Impact: High**

Hugging Face should live under:

```text
Add model
  Hosted provider
  Local runtime
  Hugging Face
  Existing local file/folder
```

Its internal flow should become a step-oriented master/detail experience:

```text
1 Find model
2 Choose variant
3 Review download
4 Download
5 Convert if required
6 Add to My models
```

Keep the current safety properties—immutable revision, size/license preview, gated token handling, conversion review—but reduce simultaneous controls.

The access-token button should appear when a selected repository requires auth or under an Advanced/account section, not as a permanent equal-weight hero action.

---

# MODEL-10 — Make Activity exception- and progress-led

**Priority: P2 — Effort: Low/Medium — Impact: Medium**

The durable-operation implementation is useful and already adaptively polls.

Recommended behavior:

- no permanent Refresh button during normal polling;
- show manual `Retry status` only after polling/read failure;
- running operations stay at the top;
- failed/cancelled next;
- completed operations collapse into recent history;
- `Clear record` goes to overflow;
- `Delete partial files` remains explicit because it destroys disk content;
- `Retry` remains visible only when valid.

Activity should answer “what is happening?” rather than expose all maintenance actions at once.

---

# MODEL-11 — Combine Routing, defaults and effective-model explanation

**Priority: P1 — Effort: Medium — Impact: Very high**

Routing currently risks becoming another control matrix disconnected from the model the user sees in Chat/Build/Design.

Recommended Runtime & routing page:

## Work defaults

```text
Surface    Default               Fallback
Chat       GPT-5.6               Gemini 3 Pro
Build      Claude Sonnet 4.6     GPT-5.6
Design     GPT Image             —
Tasks      Project/default        —
```

## Fallback order

Show the ordered fallback sequence only when fallback is enabled/relevant.

## Advisor/routing policy

Explain in plain language before exposing IDs/rules.

### Critical rule

The page must distinguish:

```text
Default
Selected
Effective
Fallback
```

Do not label all four “active”.

---

# MODEL-12 — Merge Pricing with Usage

**Priority: P2 — Effort: Medium — Impact: Medium/high**

Pricing alone does not need equal top-level weight.

Recommended Usage page:

```text
Last 7 days
Total turns
Tokens
Known cost

By model
By provider
By Work surface

Budgets
Pricing source / last reviewed
```

Provider-native quota refresh remains an explicit secondary action because it may make network/admin API calls.

Technical profile IDs should move to row details.

---

# MODEL-13 — Add a real Health/Needs-attention model rather than many Test buttons

**Priority: P1 — Effort: Medium — Impact: High**

The best health UX is not “Test” on every card.

Use background/known readiness plus explicit user-triggered checks when needed.

Health categories:

```text
Connection       credential / endpoint
Catalogue        provider can list models
Model            named model exists
Runtime          local process is running
Readiness        complete turn-readiness decision
Capacity         context window known
```

Overview should show only exceptions:

```text
Needs attention
Anthropic — credential rejected           [ Reconnect ]
Qwen local — selected but runtime stopped [ Start ]
OpenRouter — catalogue stale              [ Refresh ]
```

Healthy providers do not need a green card plus a Test button.

---

# MODEL-14 — Do not use backend/vendor links as the normal integration contract

**Priority: P1/P2 — Effort: Medium — Impact: High**

Vendor download links are appropriate when the user genuinely must install software outside Raiker, but the product should never depend on “open this website, come back, press several refresh/test buttons” as its normal connected-state lifecycle.

For every integration:

1. Raiker opens the reviewed official destination only if required.
2. Returning to Raiker should trigger/re-offer detection automatically.
3. Saved connection should be validated immediately.
4. Validation result should persist as evidence/status.
5. Failure should produce one `Fix` action with a specific reason.

For API-key providers, setup should remain fully inside Raiker except for obtaining the key/account itself.

---

# MODEL-15 — Page/action budget

**Priority: P1 — Effort: Low — Impact: High**

Add this Models-specific visual rule:

> **A repeated model/provider row gets at most one visible primary action and one overflow menu.**

Exceptions:

- destructive confirmation dialogs;
- active operation rows where Cancel is time-sensitive;
- explicit two-choice decision UI.

Examples:

### Current local framework tendency

```text
[Test] [Details] [Select] [Scan folders] [Serve selected]
```

### Target

```text
Qwen local · Stopped · Selected
                                      [ Start ] [ ⋯ ]
```

### Current activity tendency

```text
[Retry] [Delete partial files] [Clear record]
```

### Target

```text
Failed · conversion
                                      [ Retry ] [ ⋯ ]
```

with `Delete partial files` and `Clear record` inside detail/overflow, except when deletion itself is the current recovery task.

---

# Proposed final Models information architecture

## Overview

Primary purpose: “What is powering my work now?”

Contains:

- current Work surface and selected/effective model;
- Work defaults for Chat/Build/Design;
- needs-attention list;
- ready alternatives;
- active model operation only if one exists;
- one primary `Add model` action.

## My models

Primary purpose: inventory of models the owner can use.

Contains:

- hosted + local models in one consistent list;
- filters: All / Hosted / Local / Ready / Needs attention;
- one row action + overflow;
- selection/default/runtime states shown separately.

## Add model

Primary purpose: acquisition/setup.

Contains:

- Connect hosted provider;
- Add local runtime;
- Search Hugging Face;
- Add existing model folder/file.

## Runtime & routing

Primary purpose: operational configuration.

Contains:

- local serving slots/processes;
- Work defaults;
- fallback order;
- advisor/routing rules;
- recent operations/activity.

## Usage

Primary purpose: economics/limits.

Contains:

- usage ledger;
- known cost;
- provider quota where supported;
- budgets;
- pricing metadata/details.

---

# Improved desktop wireframe

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Models                                                     [ + Add model ]  │
│ Choose what powers Chat, Build and Design.                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│ Overview   My models   Add model   Runtime & routing   Usage                │
├──────────────────────────────────────────────────────────────────────────────┤
│ CURRENT WORK                                                                │
│ Build                                                                        │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ ◉ Claude Sonnet 4.6                                  Ready              │ │
│ │ Anthropic · Hosted                                                       │ │
│ │ Selected for Project Raiker · Effective model matches selection          │ │
│ │                                               [ Switch model ]           │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│ WORK DEFAULTS                                                               │
│ Chat        GPT-5.6                         Ready                            │
│ Build       Claude Sonnet 4.6               Ready                            │
│ Design      GPT Image                       Ready                            │
│                                                   [ Edit defaults ]          │
│                                                                              │
│ NEEDS ATTENTION                                               only if needed │
│ Ollama local model selected but server is stopped                [ Start ]  │
│                                                                              │
│ READY ALTERNATIVES                                                          │
│ Gemini 3 Pro                                  [ Use ] [ ⋯ ]                 │
│ GPT-5.6 mini                                  [ Use ] [ ⋯ ]                 │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

# Backend/state acceptance tests

These should be added before claiming the “active model” problem fixed.

## Persistence

1. Select hosted profile/model → reload browser → same selection.
2. Select local profile/model → stop runtime → reload → remains **Selected · stopped**, not unselected.
3. Restart Raiker host → selected profile/model persists.
4. Selected custom model override remains selected, not only its provider profile.
5. Disconnected/unavailable selected provider remains visible as **Selected · unavailable**.

## Work-surface defaults

6. Set Chat default → reload → persists.
7. Set Build default → reload → persists.
8. Set **Design default** → reload → persists.
9. Switch Chat → Build → Design and verify each picker initializes from its own default.
10. Explicit per-turn model selection does not silently rewrite another surface's default.

## Effective/fallback

11. Selected model healthy → selected == effective.
12. Selected model unavailable + fallback allowed → selection remains unchanged; effective shows fallback + reason.
13. Fallback disabled → selected unavailable produces a clear blocked state rather than silently switching.

## Local lifecycle

14. Running local model can be non-selected.
15. Selected local model can be stopped.
16. Start/Stop affects runtime state only, not persistent selection/default.
17. Restart recovery accurately reports process/runtime state without deleting selection.

## Cross-surface UI consistency

18. Models Overview, composer model picker and top-bar model indicator show the same selection/effective decision.
19. Provider catalogue refresh cannot silently change selection.
20. A model removed from “Keep available” while currently selected remains represented until the owner chooses another model or explicitly clears it.

---

# Implementation order

Priority first, then effort.

## Wave 0 — prove the state problem

1. Add the persistence/effective-model tests above.
2. Instrument/read the exact selection state before and after reload/restart.
3. Confirm whether the user's current failure is selection loss, surface-default mismatch, local-runtime restart, or UI representation drift.

Do not add another frontend persistence mechanism.

## Wave 1 — P1 low/medium effort

1. **MODEL-02** add Design surface default.
2. **MODEL-15** enforce one visible primary action per repeated row.
3. Rename state labels to Selected / Default / Ready / Running / Effective.
4. Move Test/Details/maintenance actions into overflow/detail.
5. Remove normal-state Activity Refresh where adaptive polling is healthy.
6. Remove Deploy from Local Library; deploy/start belongs to Runtime.

## Wave 2 — authoritative model decision

1. **MODEL-01** normalized selection/effective model read contract.
2. Use it in Models Overview, Chat, Build, Design, composer picker and top bar.
3. Make fallback explicit rather than silently changing the displayed selection.
4. Preserve unavailable selected models visibly.

## Wave 3 — page redesign

1. **MODEL-03** Overview.
2. **MODEL-04** unified My models inventory.
3. **MODEL-05/06** local library vs runtime split.
4. **MODEL-07/08** hosted connections and provider catalogue simplification.
5. **MODEL-11/13** routing + health exception model.

## Wave 4 — acquisition/usage cleanup

1. **MODEL-09** Add model / Hugging Face guided flow.
2. **MODEL-12** merge Pricing into Usage.
3. **MODEL-14** improve external/vendor setup return-and-detect flow.

---

# Final recommendation

Do not try to improve the current Models page by only changing spacing, colours or button variants.

The page needs one conceptual correction first:

> **Selection, default, availability, readiness, runtime and fallback are separate states and must be represented separately.**

Once that is enforced, the UI can become much simpler because many buttons stop belonging on the same screen.

The desired result is a Models area where the owner can answer, in seconds:

1. What model is selected for this work?
2. What model will actually run?
3. Is it ready?
4. If not, what single action fixes it?
5. What are the defaults for Chat, Build and Design?
6. Where do I add/manage models when I intentionally want deeper configuration?

Everything else should be secondary.