# Model cost and usage accounting

> Implemented 2026-07-26. Verified live against hosted Anthropic
> (`claude-haiku-4-5-20251001`) in both Chat and Build.

## Purpose

Show a user what a conversation has cost and what their providers have cost, in
the composer where they are working and on the Models page where they choose a
backend — without ever showing a number Raiker cannot source.

## Can prices be pulled from providers?

Checked against live APIs rather than assumed:

| Provider | Models endpoint publishes | Price? |
|---|---|---|
| Anthropic | `max_input_tokens`, `max_tokens`, capabilities | **No** |
| OpenAI | `id`, `created`, `owned_by` | **No** (org Costs API exists but needs an *admin* key, not the API key a user pastes into Raiker) |
| Gemini | token limits | **No** |
| OpenRouter | `context_length`, `pricing.prompt` / `pricing.completion` | **Yes**, per single token |

So **capacity is pullable and price mostly is not**. The design follows that
split rather than pretending otherwise.

## Fact resolution

Capacity and price are resolved **independently**, each from the first source
that has it, and the winning source is always named in the UI:

1. **owner** — a rate the owner set. Always wins.
2. **provider** — cached from the provider's own catalogue listing.
3. **config** — a documented list price in `model-profiles.json`, stamped
   `as_of`.

A fact with no source is `None` and is rendered as explicitly unavailable.
Nothing is inferred: a model absent from the price table does **not** inherit a
sibling's rate, because sibling models in the same family differ by roughly 15×.

## What may carry a cost

Only a profile that is **both** off-machine (`endpoint_kind` is `remote_hosted`
or `private_network`) **and** authenticated with an API key. An API key alone is
not sufficient — LM Studio reads `LM_API_TOKEN` and serves from `127.0.0.1`,
where tokens are free. Local profiles report "no API cost" rather than a blank.

## Storage

`model_usage_ledger` holds per-turn token counts, written from the same point
the runtime already emits `model_request_completed`. Counts only: no prompt or
response text, no credential.

**Cost is never stored.** It is derived at read time from the currently resolved
price, so correcting a stale price re-prices history rather than leaving wrong
money on disk. A turn where the provider reported no usage writes no row, so a
missing count can never become a zero that a later read presents as "free".

`model_facts_cache` holds provider-reported facts and owner overrides under
separate `source` values, so one read answers "what do we know, and who told us".

## Display

**Composer popover** (Chat and Build, identical component): the context meter,
then this chat's cost and the provider's all-time total, then a line naming the
model and its price source. Provider-reported prompt tokens replace the
browser's transcript estimate as soon as one turn has run; until then the
estimate is shown and labelled as an estimate.

**Models page**: the headline is a *count* — "1 of 10 providers set up" — not a
percentage. A percentage of every shipped profile was a meaningless denominator:
a user who connects the one provider they want is finished, not 10% finished.
Total API cost sits beside the count. Each provider card carries its models-used
and turn count, its cost, and a bar showing its **share of total spend across
providers**, which needs no configured budget to be meaningful. Providers with
no spend get no bar rather than an empty one.

## Rounding

Amounts below one currency unit render with four decimals, at or above it with
two. Two decimals everywhere would round a real $0.0143 charge to $0.01 and a
smaller one to $0.00 — indistinguishable from free.

Cache reads are billed at the full input rate. Providers discount cached input,
so the figure is a deliberate slight over-estimate: a bill should surprise a
user in the cheap direction, never the expensive one.

## Non-goals

- No invented prices, and no blended per-provider rate.
- No budget or quota enforcement; this is reporting, not a spend limit.
- No live currency conversion — the price's own currency is shown.
- No background price polling yet; facts refresh when a catalogue listing runs.

## Verification

- `tests/test_model_cost_accounting.py` — source precedence, per-model pricing,
  OpenRouter unit scaling, the ledger, owner scoping, and the rule that an
  unpriced model yields `None` rather than `0`.
- `apps/web/src/lib/contextPresentation.test.ts` — currency rounding, source
  labelling, and spend shares (including that an all-zero total yields no
  shares rather than a row of 0% bars).
- Live: a real Anthropic turn produced `2.9K / 200.0K (1%)` against a
  provider-reported capacity, `$0.0030` for the chat, and `$0.0059` all-time
  after a second turn in Build.
