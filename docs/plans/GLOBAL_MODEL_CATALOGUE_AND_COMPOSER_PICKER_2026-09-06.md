# Global Model Catalogue + Composer Picker Review — 2026-09-06

## Scope

This follow-up clarifies the intended model-availability contract across Raiker after reviewing the current provider configuration, provider catalogue adapters, local model library, model picker, surface defaults and provider connection storage.

It applies to:

- Chat composer;
- Build composer;
- Design composer/create bar;
- Task and Schedule model pickers where applicable;
- the Models page;
- Anthropic;
- OpenAI API;
- ChatGPT subscription / Codex app server;
- Ollama local and Ollama Cloud where configured;
- GGUF through managed llama.cpp;
- MLX;
- LM Studio;
- other OpenAI-compatible providers using the same catalogue contract.

This is a review/implementation plan only. No production code is changed by this document.

---

# Product decision

Raiker should have **one owner-level global model catalogue**.

> **Once a provider/runtime is connected or a local model is discovered, every compatible model it exposes should become available to every relevant Raiker composer.**

Projects, workspaces, sessions and Work surfaces may choose a **default or current selection**, but they must **not create separate model inventories** and must not hide models merely because the user changed Project, thread or surface.

The hierarchy is:

```text
Raiker owner/account
└── Global model catalogue
    ├── Anthropic models
    ├── OpenAI API models
    ├── ChatGPT subscription models
    ├── Ollama models
    ├── LM Studio models
    ├── GGUF models in approved local library
    ├── MLX models in approved local library
    └── other configured providers

Chat     → chooses a default/current model from the global catalogue
Build    → chooses a default/current model from the same global catalogue
Design   → chooses a default/current compatible model from the same global catalogue
Tasks    → captures a selected model from the same catalogue
Schedule → captures a selected model from the same catalogue
Projects → may remember a preference/default, never define a separate catalogue
```

## Non-negotiable invariant

> **Model visibility is owner/account scoped, not Project/workspace scoped.**

A Project can affect context and default selection. It must not alter which connected models exist.

---

# Direct answer: will the composer dropdown pull all available models?

## Current implementation

Not reliably by itself.

The current `ModelPicker.svelte` does **not** contact Anthropic/OpenAI/Ollama/etc. when the menu opens. It receives a `profiles` array from its parent/store, filters it through `isChoosableModel`, groups the resulting profiles by provider, and renders those choices.

Therefore:

> **The picker can display every model it is given, but completeness depends on the upstream Models snapshot/catalogue population.**

That is why the implementation should not be described as “the composer automatically pulls every model from every connected provider” yet.

## Required implementation

The composer must consume one shared `GlobalModelCatalogue` read model/store populated by provider discovery and the local model library.

Every composer should receive the same global candidate set and apply only:

1. capability compatibility for the requested operation;
2. policy/readiness presentation;
3. ordering/default selection.

It must **not** apply Project/workspace-specific model visibility filters.

---

# Global catalogue contract

Recommended backend shape:

```json
{
  "revision": 42,
  "providers": [
    {
      "profile_id": "anthropic-hosted",
      "provider": "anthropic",
      "connection_state": "connected",
      "catalogue_state": "fresh"
    }
  ],
  "models": [
    {
      "profile_id": "anthropic-hosted",
      "provider": "anthropic",
      "model": "claude-sonnet-...",
      "source": "provider_catalogue",
      "capabilities": ["chat", "tools", "vision"],
      "ready": true,
      "running": null,
      "problem": null
    }
  ]
}
```

The exact DTO name can differ, but there should be one canonical source of model inventory.

### Sources merged into the catalogue

```text
Hosted/API providers  → provider `list_models()` results
ChatGPT subscription  → Codex app-server model list
Ollama                 → runtime `/v1/models`
LM Studio              → runtime `/v1/models`
GGUF                    → approved local model-library index
MLX                     → approved local model-library index
Managed local serving  → readiness/running state layered onto catalogue rows
```

The model library and runtime catalogue are related but not the same thing:

- **library** says what local models exist on disk;
- **runtime** says what is currently serving;
- **catalogue** says what models the owner can choose;
- **selection/default** says what the owner wants to use;
- **effective** says what a turn will actually use.

---

# Remove workspace/project model scoping

## Current connection scope

Model-provider credentials are already stored **per principal/account**, not per Project. The encrypted connector-vault key is based on `principal_id + profile_id`.

That is the correct base scope for this product.

## Raiker Project/workspace rule

Do not add any of these:

```text
project_id → provider connection
project_id → provider model catalogue
workspace_id → hidden subset of composer models
session_id → separate available-model list
```

A Project may store:

```text
preferred/default profile + model
```

but that is only a starting selection.

Opening the model picker must still expose the same owner-level catalogue.

## Important Anthropic distinction

The current code contains an optional `workspace_id` connection value specifically for an **Anthropic provider credential type that itself may require a provider workspace header**.

That must **not** be confused with a Raiker Project/workspace.

The desired UX is:

1. normal Anthropic connection asks for **API key only**;
2. save → validate → list models;
3. no workspace field is shown for an ordinary key;
4. only if Anthropic itself returns its specific `provider_workspace_required` condition may Raiker expose an advanced provider-account field to make that unusual credential work;
5. that provider account identifier never scopes the Raiker model catalogue or composers.

If product policy is to support only ordinary Anthropic API keys, the optional provider workspace field can be removed entirely. But removing it means identity-linked Anthropic keys that genuinely require the provider header will not work. It should therefore be treated as an exceptional provider-auth detail, never a normal Raiker configuration concept.

---

# Provider-by-provider review

## 1. Anthropic

### Current configuration

The built-in `anthropic-hosted` profile uses:

```text
provider: anthropic
model: <model>
endpoint: https://api.anthropic.com
API key: ANTHROPIC_API_KEY / encrypted saved connection
models path: /v1/models
```

The Anthropic adapter implements `list_models()` by requesting its configured model-list endpoint and parsing every returned model id.

The factory sends `x-api-key` when the connection has a key.

### Assessment

**Core provider discovery is configured correctly for dynamic model listing.**

However, the product flow should be simplified to:

```text
Enter API key
→ Save
→ Validate
→ Fetch provider model catalogue
→ Add returned compatible models to global catalogue
→ Update every composer immediately
```

Do not require the user to manually pin one model before the rest can be seen in composers.

### Workspace recommendation

Ordinary Anthropic setup should not show a workspace field. Keep any provider-required identity-linked workspace handling exceptional/advanced as described above.

---

## 2. OpenAI API

### Current configuration

The built-in `openai-hosted` profile uses:

```text
provider: openai
model: <model>
endpoint: https://api.openai.com/v1
API key: OPENAI_API_KEY / encrypted saved connection
```

OpenAI is handled through the shared OpenAI-compatible adapter. That adapter calls the configured `models_path` (default `/v1/models`) and parses the returned catalogue.

The factory sends the saved API key as a Bearer authorization header.

### Assessment

**Core dynamic discovery is configured correctly.**

Required UX:

```text
Enter OpenAI API key
→ Save + automatic connection check
→ Fetch /v1/models
→ classify/filter capabilities
→ expose compatible returned models in Chat, Build and Design pickers
```

No Raiker workspace/project field should participate in this flow.

---

## 3. ChatGPT subscription / Codex app server

### Current configuration

This is not an API-key provider.

The `chatgpt-codex-subscription` profile uses the local Codex app-server adapter. Its `list_models()` calls the Codex client model-list operation and converts the returned names into provider model entries.

### Assessment

**The dynamic model-list path exists and is the correct abstraction.**

Required UX:

```text
Connect / sign in to ChatGPT subscription
→ Codex app server reports signed-in state
→ list subscription-available models
→ add them to global catalogue
→ expose them in every compatible composer
```

There should be no API-key field and no Raiker workspace/project model scoping.

Capability note: the current Codex subscription adapter is text-oriented and explicitly rejects tools, image inputs and structured-response requests. The model can still appear globally, but a surface requiring unsupported capability must communicate that clearly rather than silently hiding it for unrelated workspace reasons.

---

## 4. Ollama local

### Current configuration

The built-in local profile uses:

```text
provider: ollama
endpoint: http://127.0.0.1:11434/v1
OpenAI-compatible adapter
```

The shared adapter lists models from `/v1/models` and also has Ollama-specific metadata enrichment through native local endpoints.

### Assessment

**Local model discovery is fundamentally configured correctly.**

Desired behavior:

```text
Detect running Ollama
→ read /v1/models
→ every installed/served chat-capable Ollama model enters global catalogue
→ every composer updates
```

Do not make the user “Keep available” one model at a time before it becomes visible in a composer.

If Ollama is stopped, previously known models should not vanish. They should remain visible as:

```text
Available locally · Ollama stopped
```

with `Start/Fix` as appropriate.

### Ollama Cloud

Ollama Cloud is a separate hosted profile with an API key and `/v1/models`. If configured, it follows the same global-catalogue rule as other hosted providers.

---

## 5. LM Studio

### Current configuration

The built-in profile uses:

```text
provider: lm-studio
endpoint: http://127.0.0.1:1234/v1
model: <model>
OpenAI-compatible adapter
```

The shared adapter requests `/v1/models`; it also has LM Studio-specific metadata enrichment from its native local model API.

The profile can accept `LM_API_TOKEN`, but it is not inherently required for a normal local LM Studio server unless the endpoint is configured to require it.

### Assessment

**The runtime discovery path is correctly shaped for showing all LM Studio-served models.**

Desired behavior:

```text
Detect/connect LM Studio
→ list /v1/models
→ add every compatible model to global catalogue
→ expose in all composers
```

Do not require a separate model pin just to make other returned models visible.

---

## 6. GGUF / managed llama.cpp

### Current configuration

GGUF is different from hosted provider discovery.

Raiker scans **owner-approved local library folders**, reads GGUF metadata without executing model code, indexes complete models, and can deploy them into managed llama.cpp slots.

The built-in llama.cpp profiles expose four local slots/endpoints.

### Assessment

The underlying library/runtime separation is sound, but **composer availability should be improved**.

Do not make a GGUF model invisible until it is already running in one slot.

Instead:

```text
approved folder scan
→ GGUF model indexed
→ model enters global catalogue as Local · Stopped / Ready to serve
→ selecting it from any composer can initiate/start an appropriate managed slot
   (subject to the normal explicit action/approval contract)
```

This gives the composer one inventory rather than forcing the user to visit Models → Local → choose slot → Serve → return to composer.

The global row should carry:

```text
model id/name
format = GGUF
architecture
quantization
size
runtime = llama.cpp
running state
readiness state
```

but the composer itself should show only the human model name + provider/runtime + concise state.

---

## 7. MLX

### Current configuration

The model library indexes MLX-compatible directories that contain `config.json` plus safetensors weights. Four managed MLX runtime slots exist, restricted to supported Apple platforms.

### Assessment

Use the same contract as GGUF:

```text
approved library scan
→ MLX model indexed
→ enters global owner catalogue
→ visible in every compatible composer
→ selecting/using it starts or assigns a managed MLX slot when required
```

On unsupported platforms, MLX inventory may remain inspectable in Models if the files exist, but it should not be presented as a runnable composer choice.

This is a **platform capability restriction**, not workspace scoping.

---

# What must change from the earlier “Keep available” design

The earlier Models review preserved a concept where a user could manage a subset of provider models as “kept available”. The owner's clarification supersedes that as the default model-visibility contract.

## Updated decision

> **All discovered compatible models are available by default.**

Remove `Keep available` as a prerequisite for composer visibility.

If curation is still useful for providers that expose hundreds of models, make it optional and non-destructive:

```text
Favourite / Pin
Recent
Hide from quick list
```

but:

- search must still be able to find the full provider catalogue;
- hidden models are an explicit owner preference, not a Project/workspace filter;
- a hidden selected/default model must still remain visible in its selected state;
- provider refresh must not silently hide a previously selected model.

Recommended picker grouping:

```text
Search models…

Recent / Pinned
  Claude Sonnet ...
  GPT-...

Anthropic
  all compatible models returned by connected account

OpenAI
  all compatible models returned by connected account

ChatGPT
  all models returned by connected subscription

Ollama
  all discovered local models

LM Studio
  all served/discovered models

Local library
  all GGUF / MLX models runnable on this host
```

For very large catalogues, virtualize/search instead of removing models from availability.

---

# Composer-wide behavior

## Same catalogue everywhere

The following must read the same catalogue revision:

```text
Chat composer
Build composer
Design composer
Task creation
Schedule creation
Models → My models
Models → Overview
Top-bar/current model indicator
```

No surface should independently reconstruct a model list.

## Surface defaults do not filter the list

Example:

```text
Chat default   = Claude Sonnet
Build default  = GPT-...
Design default = image-capable model
```

Opening any model picker still shows the global catalogue.

The default only determines what starts selected.

## Project preference does not filter the list

Example:

```text
Project Raiker prefers Claude Sonnet for Build
```

When Build opens in that Project, Claude may be selected initially.

The dropdown still contains all globally available compatible models.

## Per-turn override

A user can choose another compatible model for the current turn without rewriting:

- the provider catalogue;
- the global inventory;
- other surfaces' defaults;
- another Project's preference.

The UI should say when the selection is temporary vs when the user explicitly chooses “Set as default”.

---

# Capability handling — all models vs usable models

“All models available to all composers” should not mean Raiker pretends an incompatible model can perform an impossible operation.

Use this distinction:

## Global inventory

Contains **every discovered model**.

## Composer picker

Shows every model compatible with the composer's requested operation as selectable.

For transparency, an optional `All models`/search result can show incompatible models disabled with a one-line reason, for example:

```text
text-embedding-3-small   Not a conversational model
whisper-...              Speech only
GPT Image ...            Image generation only
```

Do not silently convert embedding/moderation/speech models into Chat defaults.

### Surface examples

Chat/Build:

- text/chat model required;
- tool/vision limitations shown as capability metadata when relevant;
- a model need not support every optional tool to be globally visible.

Design:

- image generation/edit operation requires matching capability;
- text-only models can still be globally known but should not be selectable for a pure image-generation action;
- if Design later uses a text model for planning plus an image model for rendering, present those as two explicit roles rather than hiding either catalogue.

---

# Connection flow requirement

For every hosted/API provider:

```text
1. Owner enters credential / signs in.
2. Raiker saves credential in encrypted owner-scoped storage.
3. Raiker automatically validates the connection.
4. Raiker automatically calls provider model discovery.
5. Successful catalogue replaces/refreshes that provider's global model inventory.
6. Shared model store emits a new revision.
7. Every mounted composer updates without a page reload.
```

No extra `Test`, `Refresh catalogue`, `Keep available`, Project setup or model pin should be required for the normal happy path.

Manual Test/Refresh remain troubleshooting controls under provider Manage / overflow.

---

# Failure behavior

## API key valid, catalogue fails

Do not erase the previous catalogue.

Show:

```text
Anthropic
Connected · catalogue refresh failed
Last known models retained
[Retry]
```

## API key invalid

Show provider-level authentication failure. Keep any selected model visibly selected but unavailable until fixed.

## Provider drops a model

Do not silently switch the selected/default model.

Show:

```text
Selected · no longer reported by provider
```

and separately show any effective fallback.

## Local runtime stops

Do not remove Ollama/LM Studio/GGUF/MLX models from the catalogue merely because the process stopped.

Retain last-known local inventory and layer stopped/unavailable state onto it.

---

# Recommended implementation work

## GLOBAL-MODEL-01 — One global model catalogue DTO/store

**Priority: P0/P1 — Effort: Medium — Impact: Very high**

Create one owner-scoped catalogue that merges provider catalogues and local library models.

## GLOBAL-MODEL-02 — Every composer reads the same catalogue

**Priority: P0/P1 — Effort: Medium — Impact: Very high**

Replace per-surface candidate reconstruction with one shared model store/read.

## GLOBAL-MODEL-03 — Surface/Project defaults are selection only

**Priority: P1 — Effort: Low/Medium — Impact: Very high**

No model-list filtering based on surface, session, Project or workspace.

## GLOBAL-MODEL-04 — Add Design to persisted surface defaults

**Priority: P1 — Effort: Low — Impact: High**

Keep Chat | Build | Design first-class while sharing the same catalogue.

## GLOBAL-MODEL-05 — Automatic provider catalogue refresh after connect

**Priority: P1 — Effort: Medium — Impact: Very high**

API key/sign-in success should populate the global catalogue immediately and update mounted composers.

## GLOBAL-MODEL-06 — Remove `Keep available` as normal visibility gate

**Priority: P1 — Effort: Medium — Impact: High**

All discovered compatible models available by default. Optional favourites/hide are owner-level conveniences only.

## GLOBAL-MODEL-07 — Merge local library models into global catalogue

**Priority: P1 — Effort: Medium — Impact: High**

GGUF/MLX become visible before serving, with accurate stopped/ready-to-serve state.

## GLOBAL-MODEL-08 — Last-known catalogue persistence

**Priority: P1 — Effort: Medium — Impact: High**

Temporary provider/runtime failure must not make model lists disappear.

## GLOBAL-MODEL-09 — Capability-aware picker, not workspace-aware picker

**Priority: P1 — Effort: Medium — Impact: High**

Only genuine operation incompatibility may make a model non-selectable.

## GLOBAL-MODEL-10 — Search/virtualization for large catalogues

**Priority: P2 — Effort: Medium — Impact: High**

Do not solve 100–500 model catalogues by manually curating visibility.

---

# Required tests

1. Connect Anthropic with ordinary API key → returned models appear in Chat composer.
2. Same Anthropic catalogue appears in Build composer.
3. Same Anthropic catalogue appears in Design where capability-compatible.
4. Switch Project → catalogue does not change.
5. Switch Chat → Build → Design → catalogue identity/revision remains the same.
6. Connect OpenAI key → `/v1/models` result updates every mounted composer without reload.
7. Sign in ChatGPT subscription → Codex model list appears globally.
8. Start Ollama with multiple installed models → all compatible models appear globally.
9. Stop Ollama → models remain listed with stopped/unavailable state.
10. Start LM Studio with multiple models → all appear globally.
11. Restart LM Studio → last-known list does not disappear during transition.
12. Scan approved folder with two GGUF files → both appear globally before deployment.
13. Scan valid MLX model on supported host → appears globally before deployment.
14. MLX on unsupported platform → not selectable as runnable, with platform reason; no workspace-based hiding.
15. Chat default changes → Build and Design catalogue contents remain unchanged.
16. Project preferred model changes → global catalogue remains unchanged.
17. Per-turn model choice does not rewrite provider visibility.
18. Provider catalogue refresh adds new model → every composer receives it.
19. Provider catalogue refresh temporarily fails → previous catalogue retained.
20. Provider removes selected model → selection remains visible as unavailable; fallback is shown separately.
21. Large OpenAI/OpenRouter-style catalogue remains searchable without `Keep available` prerequisite.
22. Embedding/speech-only model is globally inventoried but cannot become a Chat text default.
23. Ordinary Anthropic API key flow contains no mandatory workspace field.
24. Provider-specific Anthropic workspace identifier, if supported, never changes Raiker Project/model visibility.
25. Credentials remain principal/account scoped and are not copied into Project/session records.

---

# Updated acceptance criteria

The model system is correct only when all of the following are true:

- entering a valid Anthropic/OpenAI-style API key automatically discovers provider models;
- ChatGPT subscription sign-in automatically discovers subscription models;
- Ollama and LM Studio automatically expose all discovered runtime models;
- GGUF and MLX library models participate in the same catalogue without requiring prior manual deployment;
- every compatible discovered model is available in every composer;
- no Project/workspace has its own provider catalogue;
- Project/surface settings affect selection/default only;
- composer model lists update live after provider connect/discovery;
- provider/runtime outages do not erase last-known selected or available models;
- the picker remains visually simple through search, grouping, Recent/Pinned and progressive disclosure rather than model suppression;
- capability restrictions are explicit and semantic, never disguised as workspace filtering.

---

# Final decision

The model picker should not be a collection of surface-specific model lists.

It should be a **view onto one global owner model catalogue**.

The desired mental model is:

> **Connect once. Discover once. Use everywhere.**

For Raiker specifically:

> **Projects provide context. Work modes provide defaults. Providers provide models. None of them should fragment the owner's model inventory.**
