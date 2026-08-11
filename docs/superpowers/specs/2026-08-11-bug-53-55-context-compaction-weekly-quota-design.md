# Chat Transcript, Context Compaction, and Weekly Quota Design

**Status:** Approved by the owner on 2026-08-11

## Goal

Close BUG-53, BUG-54, and BUG-55; ship automatic context compaction at 90%;
and add honest weekly usage and quota controls for every connected provider.
Disconnected providers must not appear in the weekly usage surface.

The work must preserve Raiker's existing authority boundary. Compaction may
change what conversation history is sent to a model, and quota data may add a
new provider read, but neither operation may widen a capability gate, execute a
tool, expose a credential, or block an owner from using a connection unless an
existing provider limit does so.

## Existing state and root causes

1. `collectText` in `apps/web/src/lib/turnPhases.ts` concatenates all
   `text_delta` events with an empty separator. That is correct inside one
   streamed response, but it loses the seam between successive model responses
   in one tool-using turn. The existing `model_request_started` lifecycle event
   already identifies that seam.
2. The ADD-02 and BUG-52 live Playwright scenarios require a deterministic,
   loopback OpenAI-compatible model. Their documented `stub_model.py` exists
   only in an old scratch directory, so the repository cannot reproduce the
   evidence those scenarios claim.
3. `ChatView.svelte` contains a large `{#if false}` transcript implementation
   immediately before the live one. The dead branch includes different answer,
   governance, and approval copy and therefore reads as authoritative code to a
   maintainer or auditor.
4. `conversation_messages` drops the oldest completed exchanges once its
   character budget is exhausted. It neither summarizes the dropped exchanges
   nor records a compaction boundary, event, source count, or owner-visible
   status.
5. `model_usage_ledger` stores owner-scoped, timestamped per-turn token counts,
   but its public reads aggregate only by session and all time. Models displays
   no connected-only weekly view, no owner budget, and no normalized provider
   quota data.

## Product decisions

### Connected providers only

The weekly surface contains one row for each configured connection, not one row
for every profile in the catalogue.

- A hosted or private-network provider is connected when its encrypted
  credential-backed connection is configured.
- A credential-free local provider is connected when its configured endpoint
  has unexpired successful readiness evidence.
- A disconnected, never-configured, or currently unverified local provider is
  omitted rather than displayed as zero usage.
- Two distinct configured connections to the same provider family remain
  distinct quota rows when they have different credentials or endpoints.

Disconnecting a provider removes its row immediately but does not erase its
historical usage ledger.

### Native data first, local truth always available

Each weekly row may contain two independent layers:

1. **Reported by provider** — authenticated usage, allowance, remaining value,
   and reset time returned by a documented provider API.
2. **Observed by Raiker** — the turns, tokens, and cost Raiker itself recorded
   during the preceding seven days for that exact connection.

Native values win only for fields the provider actually supplies. They never
overwrite the local ledger, and a failed native refresh leaves the local layer
visible with a timestamped `Provider data unavailable` note. Units are never
silently converted: provider currency limits remain currency; token budgets
remain tokens; request-rate windows remain request-rate windows.

The rolling seven-day provider-usage view is therefore the universal baseline:
tokens, turns, and cost where exact pricing is known. Ordinary provider keys and
local runtimes do not expose one uniform account-quota contract, so the UI must
clearly distinguish Raiker-observed usage from provider subscription or key
limits even when both are present.

An owner may configure a weekly token budget for any connected provider. It is
an advisory control and is labelled **Owner budget**, not provider quota. It
does not block requests. A provider-enforced native limit is labelled
**Provider limit** and its enforcement behavior is described from the returned
contract. This distinction keeps Raiker owner-authoritative while still giving
every connection a useful weekly control.

### Provider telemetry capability matrix

The implementation follows documented contracts rather than provider-name
guessing:

| Provider kind | Native source | Behavior |
|---|---|---|
| OpenRouter | `GET /api/v1/key` using the configured inference key | Read `usage_weekly`, `limit`, `limit_remaining`, and `limit_reset`; show a provider limit only when its reset contract applies to the current weekly window. |
| OpenAI | Organization usage API when a separately authorized admin credential is configured | Query the current seven-day time range and normalize token/request buckets. A normal project inference key continues to use only Raiker-observed data. |
| Anthropic | Admin usage/cost API when a separately authorized admin credential is configured | Query daily buckets covering the current seven-day window. A normal Messages API key continues to use only Raiker-observed data. |
| Ollama and other local runtimes | Per-response usage already returned by inference | Use Raiker-observed turns and tokens; show `Runs locally · no provider quota` unless the configured endpoint documents and returns a quota contract. |
| Other hosted/private providers | A registered quota adapter only when the endpoint has a documented authenticated contract | Otherwise show observed usage and the optional owner budget. |

Admin telemetry credentials are optional, separately named, encrypted in the
existing vault, and never inferred from an inference key. Connecting a provider
must not start an unexpected organization-wide read. Native telemetry is
fetched when the owner opens or refreshes **Usage & limits**, with a bounded
cache and a visible last-checked time.

Official contract references used for this design:

- OpenAI organization usage API:
  <https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/usage>
- Anthropic Messages usage report:
  <https://docs.anthropic.com/en/api/admin-api/usage-cost/get-messages-usage-report>
- OpenRouter current-key usage and limits:
  <https://openrouter.ai/docs/api/api-reference/api-keys/get-current-key>
- OpenRouter per-response usage accounting:
  <https://openrouter.ai/docs/cookbook/administration/usage-accounting>
- Ollama response usage fields:
  <https://docs.ollama.com/api/usage>

## Architecture

### 1. Response-boundary-aware transcript text

`collectText` scans the event sequence rather than filtering first. Ordinary
text deltas remain byte-for-byte adjacent. When `model_request_started` occurs
after at least one text delta, the next non-empty text delta begins a new model
response and receives exactly one blank-line boundary unless the text already
contains an equivalent boundary.

Other lifecycle events do not create whitespace. A model request that emits no
text before a tool call does not create an empty paragraph. Chat and Build both
receive the behavior from the shared helper.

### 2. Checked-in live batching model

Add `apps/web/e2e/fixtures/stub_model.py`, a dependency-free, loopback-only
OpenAI-compatible server with:

- `GET /v1/models` returning only `raiker-batch-stub`;
- streaming and non-streaming chat-completion responses;
- deterministic three-write, refusal-then-read, and refusal-then-write batches
  selected from the existing live-spec prompts;
- deterministic tool-result follow-up answers; and
- a positional port argument defaulting to `8811`.

The fixture refuses non-loopback binding, requires no credential, stores no
prompt, and logs no request body. A focused Python contract test launches it on
a free loopback port and verifies catalogue, streaming text, and all declared
batch shapes. Both live specs name the repository path in their prerequisites.

### 3. Remove the disabled Chat transcript

Delete the entire `{#if false}` branch. Remove only imports, helper functions,
and styles proven unused after the deletion. The live Markdown answer,
governance timeline, refusal card, approval card, cross-tab continuation, and
error display remain unchanged.

### 4. Automatic context compaction at 90%

Add an owner-scoped durable compaction record:

```text
compaction_id / owner_principal_id / session_id
through_turn_id / summary
source_turn_count / source_character_count
estimated_input_tokens_before / estimated_summary_tokens
provider / model / status / reason_code / created_at
```

Before a model request, `ContextBudgetPlanner` estimates the complete pending
input using the exact known context capacity: system instructions, current
prompt, attachment/retrieval/workspace context, active plan, latest successful
compaction, and replayable completed turns. Compaction triggers when the
estimate is at least 90% of capacity.

The selected provider receives one bounded, tool-free summary request over the
oldest eligible completed exchanges. The compaction request cannot itself
compact, use tools, enter fallback sequences, or mutate memory. It uses the
same configured provider connection so data does not cross a new provider
boundary.

The summary prompt requires retention of:

- user requirements, decisions, constraints, and named people or systems;
- active objectives, plans, unresolved questions, and errors;
- named files, generated artifacts, and changed-file references;
- approval outcomes and still-relevant action or source identifiers; and
- exact values the owner explicitly asked the conversation to remember.

Raiker then appends a locally generated protected-state block from authoritative
stores. The model summary cannot alter that block. At minimum it preserves the
current plan, unresolved approvals and batch positions, active task objective,
checkpoint references, and source identifiers required by ongoing work.

The original transcript is never modified or deleted. Subsequent provider
requests contain the latest successful compacted summary followed by completed
turns after `through_turn_id`. Success emits `compacted_context_created`; failure
emits `compacted_context_failed`. Both events carry counts and reason codes, not
conversation text.

A UI-only 90% warning is not an acceptable implementation: it would report the
runtime limit while leaving it unfixed. The trigger must create and use the
durable compacted context described above.

If summary generation fails, the user turn continues with the existing bounded
recent-history fallback when it can fit safely. The UI must call this
`Recent history retained`; it must not claim truncation was compaction. If the
current prompt plus protected state alone cannot fit, Raiker fails before model
egress with a plain-language capacity error and remediation.

The Chat and Build context popovers display the latest successful compaction
time, number of source turns, and before/after token estimates. Transcript
history and exports still contain the original messages.

### 5. Weekly ledger and quota normalization

Extend `ModelUsageLedger` with a timestamp-bounded aggregate keyed by owner and
connection identity. The default observed window is the preceding seven days
ending at read time. The response includes exact `window_started_at` and
`window_ends_at` values so the UI never implies a provider billing week.

Add a normalized read model:

```text
connection_id / profile_id / provider / display_name / endpoint_kind
connected_at / readiness_checked_at
observed_window_start / observed_window_end
turns / input_tokens / output_tokens / cache_read / cache_write
observed_cost / currency / price_source / price_as_of
owner_weekly_token_budget
native_usage[] / native_limits[] / native_checked_at / native_status
```

Native snapshots contain a unit, used value, optional limit, optional remaining
value, reset interval, reset time, scope, and source label. Invalid, negative,
secret-shaped, or contradictory values are rejected rather than displayed.
Provider responses are cached for five minutes per connection and redacted
before diagnostics.

The API returns connected rows only and is owner scoped. Writes may set or clear
an owner weekly token budget only for a connection the owner controls. A budget
change creates an audit event and does not contact the provider.

### 6. Models UI

Add a compact **Usage & limits** section above the provider catalogue. Each
connected provider row shows:

- provider and connection name;
- `Observed by Raiker · last 7 days` token, turn, and cost totals;
- an owner weekly token-budget meter and edit/clear control;
- provider-reported usage or limits when available, with source and reset time;
- `Runs locally · no API cost` for local connections; and
- last refreshed state plus an explicit refresh action.

Disconnected providers do not render. With no connected provider, an empty
state says `Connect a provider to see usage and limits.` Loading one native
adapter cannot blank the other rows. A provider error remains confined to that
row.

The section reuses the existing cards, chips, meters, form controls, spacing,
responsive breakpoints, dark theme, and focus styles. Meters expose accessible
names, values, units, and reset details. Currency and token figures use locale
formatting, while exact source labels remain visible rather than tooltip-only.

## Security and failure handling

- Live-test credentials are entered through Models UI only. They are never
  placed in source files, command arguments, screenshots, traces, or reports.
- Native quota reads use only the configured endpoint and the same egress policy
  as the provider connection. Optional admin telemetry credentials authorize
  only documented read endpoints.
- Provider quota payloads are untrusted network data. They pass bounded schema
  validation, response-size limits, redaction, timeouts, and safe error
  classification before persistence or rendering.
- Compaction summaries are untrusted model output framed as conversation
  history. System policy, capability state, approvals, and protected state are
  added outside the summary and cannot be overridden by it.
- Compaction and telemetry failures are non-fatal to unrelated providers and
  ordinary local operation.
- No quota surface claims zero cost, unlimited quota, or provider enforcement
  when the source data is absent.

## Test strategy

Implementation follows red-green-refactor in these slices:

1. BUG-53 response seams without intra-response whitespace changes.
2. BUG-54 fixture contract and repository-relative live-spec prerequisites.
3. BUG-55 dead-branch removal with live transcript behavior unchanged.
4. Timestamp-bounded ledger aggregation, owner isolation, connection identity,
   and connected-provider filtering.
5. OpenRouter native weekly data, optional OpenAI/Anthropic admin adapters,
   Ollama observed usage, schema validation, cache, and adapter failure states.
6. Owner budget create/update/clear, auditing, and provider-independent behavior.
7. Compaction threshold, summary boundary, protected state, transcript
   preservation, event order, failure fallback, and owner isolation.
8. Models UI connected-only rows, budget editing, honest source labels,
   accessibility, responsive layout, and secret non-rendering.

Focused tests are followed by the complete Python gate, web unit suite,
Svelte check, ESLint, production build, mocked Playwright suite, licensing and
documentation validators, and workflow-equivalent commands.

## Live acceptance and screenshots

Use a fresh local workspace and enter all credentials through the UI. Test
Anthropic, OpenRouter, OpenAI, and Ollama `gemma4:31b-cloud` separately:

1. connect through Models and select a live catalogue model;
2. pass exact-model readiness;
3. stream a normal Chat answer;
4. run a tool-using turn that produces more than one model response and verify
   the paragraph seam;
5. open **Usage & limits** and verify only connected providers appear;
6. verify OpenRouter native weekly data when the key endpoint supplies it;
7. verify the other providers show observed values and clearly explain whether
   administrative provider telemetry is available;
8. set, edit, and clear an owner weekly token budget;
9. disconnect one provider and prove its row disappears without deleting its
   historical ledger; and
10. inspect console errors, failed requests, keyboard behavior, dark theme, and
    responsive layouts.

The checked-in stub separately proves deterministic multi-call seams and batch
behavior. Playwright artifacts live under `output/playwright/`. Screenshots are
visually inspected before any durable copy; credential dialogs, request headers,
auth callbacks, and full key labels must be absent.

## Documentation and closure

- Move BUG-53, BUG-54, and BUG-55 from `docs/plans/TO_BE_FIXED.md` into the
  existing `docs/plans/FIXED_ITEMS.md` format without losing observed behavior,
  root cause, required outcome, fix, and verification.
- Add fixed-item records for automatic compaction and connected-provider weekly
  quota controls.
- Remove their stale Known Limit from `README.md` and
  `docs/guide/working-in-chat.md`, then re-derive the remaining Known Limits
  against the shipped tree.
- Update API contracts, architecture, memory/context strategy, security model,
  user guide, troubleshooting, and live-test records in their existing style.
- Record any issue discovered but not fixed in this run as an actionable entry
  in `TO_BE_FIXED.md` and name it in the final summary.
- Commit and push the implementation to `origin/main`, then monitor every
  GitHub Actions workflow for that SHA until green. Repository-owned failures
  are fixed and re-pushed before completion.
