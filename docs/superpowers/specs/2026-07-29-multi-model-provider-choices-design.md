# Multi-provider, multi-model choices

## Goal

Allow one user to save multiple concrete models across multiple providers and use those choices independently in Chat, Build, and unscheduled Tasks. Workbench exposes the same choices for each mode. Scheduled work deliberately resolves whichever global default is active when a run begins.

## Current failure

Provider connections are already stored independently, but a concrete model chosen for a placeholder profile is stored only in the user's single `principal_model_control` row. Selecting a second provider/model replaces that row. When `/api/models` is read, only the current profile receives the stored concrete-model override; all previous placeholder profiles revert to `<model>`, are marked unconfigured, and are removed from `chat_profiles`. Chat and Build therefore cannot see all of the provider/model choices the user configured.

Tasks have a related limitation: the scheduler creates `PromptOptions()` without a profile or model, so every scheduled run uses the current global default rather than a model selected for that task.

## User-visible behavior

- The Models page lets the user add more than one model under any connected provider.
- Adding a model does not remove another saved model from the same or a different provider.
- A saved choice is the pair `(profile_id, model)`. The provider connection continues to belong to the profile.
- One saved pair may be the global default. Changing the default does not remove any saved choices.
- Chat and Build list every saved pair, grouped by provider, and keep independent local selections.
- Chat and Build send both `model_profile` and `model` on every turn when an explicit choice is made.
- The Task composer lists the same saved choices. An unscheduled task stores its chosen pair independently of Chat and Build.
- Scheduled, recurring, and background work stores no model override. Every run resolves the global default active when that run begins.
- Workbench uses the same pair-aware picker for Chat, Build, and Create Task, hands the selected pair to the destination surface, and labels the former “Run work” mode “Build”.
- Workbench Schedule shows the current global default rather than an independent model picker.
- Existing fixed-model profiles remain available without requiring a redundant saved override.

## Persistence model

Add an owner-scoped table for saved concrete model choices:

```sql
CREATE TABLE principal_configured_models (
  principal_id TEXT NOT NULL,
  profile_id TEXT NOT NULL,
  model TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (principal_id, profile_id, model)
);
```

The existing `principal_model_control` row remains the global default and retains reasoning settings. Saving a concrete model inserts or updates `principal_configured_models` and may also make that pair the global default when the user explicitly selects it as the default. Existing current selections are included as configured choices during migration/compatibility reads so users do not lose their present setup.

Tasks gain nullable `model_profile` and `model` columns for unscheduled task intent. Scheduled rows leave both columns null; `TaskScheduler` continues creating empty `PromptOptions`, causing the gateway to resolve the current global default independently for each run.

Account deletion removes the new owner-scoped configured-model rows. Task deletion already removes task rows and therefore their stored model fields.

## API contracts

`GET /api/models` continues returning full provider profiles and gains a saved-choice collection whose entries contain the concrete `profile_id`, `provider`, and `model` plus the profile capability metadata needed by the pickers. The existing `chat_profiles` field remains during the transition and represents concrete saved choices rather than only one override per profile.

The model configuration write accepts a profile and concrete model, validates the effective provider through the existing fail-closed provider factory, and saves the pair without deleting other pairs. Global-default selection remains an explicit action or an explicit flag rather than an accidental side effect of merely saving a choice.

Task creation accepts nullable `model_profile` and `model`. The service validates that an explicit pair forms a saved, concrete, owner-scoped choice before creating an unscheduled task. Scheduled or recurring creation rejects an explicit pair so a stale override cannot defeat dynamic global-default resolution. Task read models return both fields.

Prompt submission already supports `model_profile` and `model`; Chat and Build will use both fields rather than encoding a model into a synthetic profile identifier.

## Components and data flow

1. Models loads the provider catalogue and the user's saved concrete choices.
2. The user connects a provider, opens its catalogue, and saves one or more concrete models.
3. The backend validates each pair and persists it without replacing other pairs.
4. The shared model store publishes the saved choices to all mounted consumers.
5. ModelPicker identifies a choice by both profile and model, groups choices by provider, and returns both values.
6. Chat and Build keep separate local selection state and submit their chosen pair per turn.
7. Workbench keeps separate Chat, Build, and Task draft choices, hands each pair to the corresponding destination, and displays the global default for Schedule.
8. Unscheduled Tasks persist their selected pair. Scheduled Tasks persist no pair, and TaskScheduler resolves the current global default at the start of every run.

No selection made in Chat, Build, or Tasks writes the global default. Consequently, those surfaces cannot conflict with each other.

## Failure and security behavior

- Unknown profiles, placeholder model names, unsaved choices, and choices belonging to another principal are rejected.
- Provider policy, connection, gate, credential, endpoint, and egress validation remains fail-closed through the existing provider factory.
- Removing or disconnecting a provider does not silently redirect an explicitly pinned unscheduled task.
- Scheduled work intentionally follows the current global default. Changing that default is an explicit user action, not a silent fallback.
- API keys and endpoints remain in the encrypted provider connection vault and never enter the configured-model table or response.
- Duplicate saves are idempotent because the saved-choice primary key is `(principal_id, profile_id, model)`.

## Compatibility and migration

- Existing current selections are preserved and surfaced as configured choices.
- Fixed-model profiles continue to work as concrete choices.
- Existing tasks have null model fields and keep using the global default. Existing schedules continue resolving it at run time.
- Existing clients may continue sending only `model_profile`; the runtime retains its current default-resolution behavior.
- The API keeps existing fields while the web client moves to pair-aware choices.

## Testing

- Storage tests prove two models under one provider and models under multiple providers persist simultaneously and remain owner-isolated.
- Dashboard/API tests prove `/api/models` returns every saved concrete pair and saving a new pair does not erase earlier pairs.
- ModelPicker tests prove duplicate-provider choices are distinct and emit both profile and model.
- Chat tests prove a Haiku choice submits Anthropic plus Haiku.
- Build tests prove an Opus choice submits Anthropic plus Opus independently of Chat state.
- Task API tests prove an unscheduled task stores its selected pair and schedules reject or omit pair overrides.
- Scheduler tests prove each run uses empty model options and therefore resolves the then-current global default.
- Workbench tests prove Chat, Build, and Create Task hand off independent pairs, the Build label and route are correct, and Schedule displays the global default without pinning it.
- Compatibility tests cover fixed-model profiles, existing defaults, and legacy tasks with no explicit model.
- Full web tests, focused Python tests, type/lint checks, and the production web build are run before completion.

## Out of scope

- Automatically loading every model from every connected provider into every picker.
- Per-project model defaults beyond a Build composer's explicit selection.
- Automatic model choice based on task content.
- Silent provider switching outside the existing user-configured fallback sequence.
