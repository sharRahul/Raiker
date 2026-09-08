# Raiker Environment Context: Time, Date, Timezone and Weather — 2026-09-07

## Implementation status — 2026-09-08

Every item in this plan is implemented and verified against a live runtime
holding a real Anthropic credential connected through the product's own flow.
Recorded as
[FIXED-459](FIXED_ITEMS.md#fixed-459--nothing-in-raiker-told-a-model-what-day-it-was)
and
[FIXED-460](FIXED_ITEMS.md#fixed-460--weather-was-a-page-to-interpret-rather-than-a-reading-to-report).

| Item | State |
|---|---|
| ENV-01 authoritative per-turn clock bundle | Done — `raiker/runtime/environment.py`, injected as its own trusted system message |
| ENV-02 one owner-level timezone source of truth | Done — `general.timezone`, with the documented four-step precedence |
| ENV-03 fresh context at scheduled execution | Done — derived per turn, so a scheduled run cannot replay its creation time |
| ENV-04 surface parity | Done — Chat, Build, Design, Tasks, Schedule, agents; a subagent derives its own rather than inheriting |
| ENV-05 provenance/diagnostic visibility | Done — an `environment_context` event per turn, and `GET /api/environment` |
| WEATHER-01 structured `weather_lookup` | Done — Open-Meteo through the existing egress boundary |
| WEATHER-02 owner weather location preference | Done — `general.weather_location`, held separately from the timezone |
| WEATHER-03 freshness and stale-state semantics | Done — typed `fresh` / `stale` / `unavailable`, with the age of a stale reading |

All 28 required tests below are covered by `tests/test_environment_context.py`,
`tests/test_environment_context_turns.py`, `tests/test_weather_capability.py`,
`web/src/lib/environment.test.ts` and the live round
`web/e2e/env-web-read-live.spec.ts`.

The 2026-09-08 Windows verification added `tzdata` as a runtime dependency.
This keeps an IANA setting such as `Europe/London` authoritative on hosts whose
Python installation has no system timezone database, instead of silently
falling back to UTC ([FIXED-476](FIXED_ITEMS.md#fixed-476--a-valid-owner-timezone-became-utc-on-windows)).

---

## Purpose

This plan closes a foundational context gap: a model must never have to guess the current time, date, day of week, timezone or freshness of weather data from training knowledge, conversation history or a provider-specific system prompt.

The product rule is:

> **Raiker owns environmental facts; models consume them. Models must not invent them.**

This document defines the owner/account-level environment context contract shared by Chat, Build, Design planning, Tasks, Schedule, agents and delegated subagents. It complements `GLOBAL_WEB_READ_CAPABILITIES_2026-09-07.md`, which defines governed external web-read/search/extraction availability.

---

## Historical pre-implementation conclusion

This assessment describes the initial baseline before ENV-01 through ENV-05
and WEATHER-01 through WEATHER-03 were delivered. It is retained to explain
the work and does not describe an outstanding gap. The product contracts and
acceptance criteria below continue to apply.

The initial repository had mature model/tool projection and authority controls,
but lacked a dedicated deterministic per-turn clock/date/day/timezone contract.
Weather was expected to be obtained indirectly through web capabilities.

That baseline could not claim authoritative environment context on every
agentic surface. The implementation above supplies it; weather still requires
resolvable location and permitted provider access.

This is a product correctness issue rather than a cosmetic enhancement. Relative-time requests such as `tomorrow`, `this Friday`, `tonight`, `in two hours`, `yesterday`, recurring schedules and weather-sensitive tasks all depend on fresh deterministic context.

---

# Product decisions

## ENV-DECISION-01 — One authoritative runtime environment context

Create one runtime-owned `EnvironmentContext` for each turn/execution. It is derived by Raiker, not by the selected model.

Minimum contract:

```text
EnvironmentContext
├── generated_at_utc
├── timezone
├── local_datetime
├── local_date
├── local_time
├── day_of_week
├── utc_offset
├── locale?                 optional presentation preference
├── location?               only when explicitly available/allowed
└── freshness
```

Example:

```text
Current environment
Generated UTC: 2026-09-07T09:06:21Z
Timezone: Europe/London
Local datetime: 2026-09-07T10:06:21+01:00
Date: 7 September 2026
Day: Monday
UTC offset: +01:00
Source: Raiker runtime clock
```

The context is regenerated for every new turn or scheduled execution. It is not a long-lived conversation fact.

## ENV-DECISION-02 — Time/date is inherent read-only context, not delegated authority

Reading the runtime clock creates no authority and does not require an approval flow. The model receives the result as trusted runtime metadata.

Time/date context must therefore not disappear because:

- a Project changed;
- a model changed;
- a provider changed;
- a web capability is disabled;
- a network connection is unavailable;
- an external connector is disconnected.

The environment context is local runtime truth.

## ENV-DECISION-03 — Always supply UTC and owner-local time

UTC alone is insufficient for natural-language scheduling. Local time alone is insufficient for auditing and cross-system execution.

Every turn must receive both:

```text
UTC timestamp
owner-local timestamp
IANA timezone
UTC offset
local date
day of week
```

Audit/event records should continue to use an unambiguous UTC timestamp while user-facing reasoning may use owner-local time.

## ENV-DECISION-04 — Timezone precedence is deterministic

Recommended precedence:

```text
1. explicit owner/account timezone
2. trusted device/browser timezone captured as an owner preference
3. host operating-system timezone
4. UTC fallback
```

The selected timezone must be visible and changeable in Settings. A browser/device timezone may propose a value but should not silently overwrite an explicit owner preference.

Use an IANA identifier such as `Europe/London`, not only `BST`, `GMT`, `EST` or a numeric offset. DST transitions must be resolved by the timezone database.

## ENV-DECISION-05 — Locale is presentation, timezone is meaning

Locale affects wording such as `7 September 2026` versus `September 7, 2026`; it must not determine the timezone or scheduling semantics.

Store/derive them separately.

---

# Weather contract

## WEATHER-DECISION-01 — Weather becomes a first-class structured read capability

Add a governed read capability conceptually named:

```text
weather_lookup
```

It should return structured, source-attributed data rather than asking the model to scrape an arbitrary weather page and infer values.

Suggested response contract:

```text
WeatherResult
├── location
│   ├── display_name
│   ├── latitude?          provider/runtime internal where appropriate
│   ├── longitude?
│   └── timezone
├── current?
│   ├── observed_at
│   ├── temperature
│   ├── feels_like?
│   ├── condition
│   ├── precipitation?
│   ├── wind?
│   └── visibility?
├── forecast[]?
│   ├── valid_from
│   ├── valid_to
│   ├── min/max temperature?
│   ├── condition
│   └── precipitation probability?
├── provider
├── fetched_at
└── freshness/status
```

A response must distinguish **observed at**, **forecast valid for**, and **fetched at**. These are different timestamps.

## WEATHER-DECISION-02 — Weather is available globally but execution remains governed

The capability should be discoverable from every relevant agentic surface, but the external request must pass the same network/authority policy used for other read-only external calls.

Availability does not mean unrestricted egress.

```text
weather_lookup visible
        ↓
request validated
        ↓
network/egress policy
        ↓
provider request
        ↓
structured result + source + freshness
```

## WEATHER-DECISION-03 — Never silently infer persistent precise location

Location precedence should be:

```text
1. explicit location in the current instruction
2. explicit owner default location, if configured
3. current device/browser location only after the product has obtained the relevant permission
4. no location → ask/resolve from context rather than guessing
```

Do not infer a persistent precise location from IP address and store it as owner truth.

A broad manually configured city/region is sufficient for normal weather use.

## WEATHER-DECISION-04 — No stale-weather illusion

If weather refresh fails:

- a previous result may be shown only if its age is visible;
- do not represent it as current;
- do not silently substitute model knowledge;
- scheduling/automation logic that depends on weather must be able to identify `stale`, `unavailable` and `fresh` distinctly.

Example:

```text
London weather
Last successful observation: 08:55 BST
Refresh failed at: 10:06 BST
State: stale
```

---

# Surface contract

The same environment context must apply to all model-backed/agentic work surfaces.

| Surface | Time/date/timezone | Weather tool | Notes |
|---|---|---|---|
| Chat | Always injected | Available | normal conversational use |
| Build | Always injected | Available | useful for time-sensitive research/tests/releases |
| Design planner/research | Always injected | Available | only planning/research layer; image model does not gain arbitrary network authority |
| Tasks | Always injected at creation and execution | Available | execution-time context must be fresh |
| Schedule | Always injected at creation and execution | Available | timezone is mandatory for recurrence semantics |
| Agents | Always injected | Available | same owner-level context contract |
| Subagents | Fresh derived context | Delegated only if policy permits | do not copy a stale parent timestamp |
| Models/Settings/Approvals admin UI | UI may display clock where useful | no general model tool requirement | these are not generic agentic surfaces |

Important rule:

> **Projects provide work context; they do not create a separate clock, timezone, weather provider or environmental truth.**

---

# Scheduling semantics

Time context is especially important for Tasks and Schedule.

## Relative instructions

When an owner says:

```text
Remind me tomorrow at 9
```

Raiker should resolve against:

```text
EnvironmentContext.local_datetime
EnvironmentContext.timezone
```

and store an absolute/recurring schedule with explicit timezone semantics.

The model must not rely on a provider's hidden current-date prompt.

## DST

Recurring schedules should retain the owner's IANA timezone so `08:00 Europe/London` remains 08:00 local time across GMT/BST transitions unless the owner explicitly requested a fixed UTC time.

## Scheduled executions

A scheduled job must generate a **new** `EnvironmentContext` at execution time. It must not replay the timestamp from task creation.

---

# Trust and prompt-injection boundary

The runtime environment bundle is trusted metadata. External weather output is not.

The model-facing context should preserve this distinction:

```text
TRUSTED RUNTIME CONTEXT
- current UTC/local time
- timezone
- local date/day

UNTRUSTED EXTERNAL DATA
- weather provider response
- web content
- connector content
```

Weather text/descriptions returned by an external provider must never be treated as policy or instructions.

---

# UI requirements

## Settings

Add/confirm an owner-level setting:

```text
Timezone
Europe/London
[ Change ]
```

Optional supporting setting:

```text
Default weather location
London, United Kingdom
```

Do not expose technical provider metadata in the normal settings flow.

## Composer

Do **not** permanently add Clock, Date or Weather buttons.

The shared composer remains simple. Weather is reached from Tools or naturally invoked by the instruction. Time/date context is implicit runtime metadata and needs no button.

Examples:

```text
What's the weather this afternoon?
```

```text
Schedule this for next Friday at 16:00.
```

The user should not have to attach the date/time manually.

## Transparency

Where a response depends materially on current time/weather, Raiker should be able to expose the source/freshness in provenance/details without cluttering the normal answer.

---

# Failure behaviour

## Clock failure

A local runtime clock failure is exceptional. Fail explicitly rather than fabricating a date.

Do not use model training knowledge as fallback.

## Unknown timezone

Use UTC as a deterministic final fallback and make that visible when local-time interpretation matters.

For an ambiguous scheduling instruction, ask for/require timezone resolution before committing the schedule rather than silently selecting a region.

## Weather provider unavailable

Return a typed unavailable state. Preserve last-known data only with age/freshness clearly visible.

## No location

If the request requires location and none can be resolved from the instruction or explicit owner preference, request the minimum missing location context. Do not silently use host/IP geography.

---

# Implementation findings

Priority outranks effort. Within the same priority, lower-effort work should be executed first.

## ENV-01 — Authoritative per-turn clock bundle

**Priority: P0 — Effort: Low/Medium — Impact: Critical**

Generate and inject `generated_at_utc`, IANA timezone, local datetime/date/time, day of week and UTC offset into every model-backed turn.

Acceptance:

- independent of model/provider;
- independent of Project;
- refreshed per turn;
- trusted runtime provenance;
- no network dependency.

## ENV-02 — One owner-level timezone source of truth

**Priority: P0 — Effort: Medium — Impact: Critical**

Persist explicit owner timezone and implement deterministic fallback precedence.

## ENV-03 — Scheduled execution rehydrates fresh environment context

**Priority: P0 — Effort: Medium — Impact: Critical**

Task/schedule execution must derive current runtime context at execution time.

## ENV-04 — Surface parity

**Priority: P0 — Effort: Medium — Impact: Very high**

Chat, Build, Design planner, Tasks, Schedule, agents and delegated model turns consume the same context contract.

## WEATHER-01 — Structured `weather_lookup`

**Priority: P1 — Effort: Medium — Impact: High**

Implement a source-attributed, timestamped structured weather read path.

## WEATHER-02 — Owner weather location preference

**Priority: P1 — Effort: Low/Medium — Impact: Medium**

Optional city/region default, separate from timezone.

## WEATHER-03 — Freshness and stale-state semantics

**Priority: P1 — Effort: Medium — Impact: High**

Never represent cached weather as current without age.

## ENV-05 — Provenance/diagnostic visibility

**Priority: P2 — Effort: Low/Medium — Impact: Medium**

Expose runtime context source and weather source/freshness through diagnostics/provenance rather than permanent composer chrome.

---

# Required tests

At minimum add regression coverage for the following.

1. Chat turn receives current UTC timestamp.
2. Chat turn receives owner-local timestamp and IANA timezone.
3. Build receives the same environment-context schema.
4. Design planning agent receives the same schema.
5. Task creation receives current environment context.
6. Scheduled execution receives a newly generated context rather than creation-time context.
7. Switching Projects does not change timezone/environment source.
8. Switching model providers does not change environment source.
9. Explicit owner timezone wins over browser/device timezone.
10. Browser/device timezone can initialize/propose a value when no explicit owner setting exists.
11. Host timezone is used only after explicit/device sources are unavailable.
12. UTC is the final deterministic fallback.
13. DST transition uses IANA timezone semantics.
14. `tomorrow` resolves from owner-local date, not UTC date when those differ.
15. `this Friday` resolves from owner-local calendar.
16. subagent receives fresh current environment context.
17. no web capability is required to know the current date/time.
18. weather request with explicit location does not require owner default location.
19. owner default weather location is used only when current instruction omits a location.
20. missing weather location produces a typed missing-context result/request rather than an IP-location guess.
21. weather result includes provider/source and fetch timestamp.
22. current conditions include observation timestamp where the provider supplies one.
23. forecasts include validity period.
24. failed refresh never labels stale cached weather as current.
25. disabled network policy prevents the external weather request without removing clock/date context.
26. weather text is handled as untrusted external data.
27. changing Project does not create a separate weather configuration.
28. administrative pages do not receive a generic composer merely to expose weather/time.

---

# Definition of done

This plan is complete when Raiker can truthfully state:

> Every model-backed Raiker execution receives a fresh, authoritative runtime date/time/timezone context. Weather is a globally discoverable structured read capability with explicit location, source and freshness semantics, while external execution remains governed.

And when the following invariant is tested:

> **No model, provider, Project or external webpage is the source of truth for Raiker's current clock, date, day or timezone.**
