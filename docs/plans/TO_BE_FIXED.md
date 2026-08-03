## Goal

Make Raiker a secure AI product that combines an AI assistant, a governed AI
agent, and an extensible agent platform.

As an assistant, Raiker should help users understand, reason, decide, and
communicate through a polished conversational experience. As an agent, Raiker
should be able to plan tasks, gather context, use tools, execute approved
actions, verify outcomes, and explain what it did. As a platform, Raiker should
provide the governed runtime foundation for models, tools, plugins, interfaces,
memory, approvals, audit events, checkpoints, and integrations.

Raiker must support user-owned model choice across LLM backends — local models
such as llama.cpp, Ollama, and LM Studio; home-lab runtimes such as vLLM;
private-network providers; and hosted API providers such as Anthropic, OpenAI,
Gemini, and OpenRouter. No model, interface, plugin, or capability should
bypass governance. Every action must remain policy-aware, observable,
auditable, approval-driven where required, human-governed, user-controlled, and
fail-closed by design.

## Security posture (read before adding any restriction)

Raiker is **owner-authoritative and monitored, not prevention-by-restriction.**
Security is not restricting the user; it is a frictionless system that lets the
owner operate securely without having their access taken away. Do **not** put a
hard block in front of the owner's legitimate choices (e.g. connecting a remote
MCP server) by default — **allow, monitor, surface anomalies as findings +
notifications, and give the owner an instant stop plus an automatic revocable
pause for the irreversible/high-severity cases.** Reserve hard prevention for a
last resort and justify it against this posture. Full statement:
`docs/SECURITY_AND_POLICY.md` → "Security Philosophy". The rules below still hold
and are compatible with it:

# To be fixed

Defects and gaps found while executing
[the live manual test plan](RAIKER_LIVE_MANUAL_TEST_PLAN.md) against a running
`raiker-web` on **2026-07-26**, hosted Anthropic `claude-haiku-4-5-20251001`.

Each entry states what was observed, the reproduction, the root cause in code,
and the proposed fix. Fixed entries remain as evidence; every deferred item
found by the FIXED-01 through FIXED-48 audit is now an explicit BUG with a
required user-interface outcome, so closing backend work cannot leave an
invisible or misleading product surface.

docs/GAP_BUILD_CHAT.md — GAP-BUILD and GAP-CHAT — are not defects. They are the itemised
distance between what Build and Chat ship today and what each is meant to be:
Build as an autonomous coding agent that closes its own loop, Chat as a general
agentic work assistant that acts across the owner's tools and files. They are
written to the same standard as the defects: what exists today with the file
that proves it, what is missing, and the concrete work.

Evidence: [`screenshots/not-working/`](screenshots/not-working) (defects),
[`screenshots/working/`](screenshots/working) (verified behaviour).

FIXED-59 through FIXED-66 were verified on **2026-08-01** against a running
`raiker-web` holding a real Anthropic credential — `claude-haiku-4-5-20251001`
answering a live turn, not a route-mocked shell. The specs are
[`e2e/single-runtime-and-inspector-live.spec.ts`](../../apps/web/e2e/single-runtime-and-inspector-live.spec.ts)
and [`e2e/live-end-to-end.spec.ts`](../../apps/web/e2e/live-end-to-end.spec.ts),
and their screenshots are `working/160-*` through `working/168-*`. The two task
cards in `working/165-tasks-continuation-live.png` show a parked and a
continuing run whose states were written by `TaskManager` — the same code the
scheduler calls — rather than reached through a full approval round trip; the
continuation logic itself is covered by `tests/test_task_scheduler.py`.

FIXED-68 through FIXED-73 were verified on **2026-08-01** against a running
`raiker-web` using owner-configured Anthropic and OpenRouter credentials and the
Ollama `gemma4:31b-cloud` model. The live scenario is
[`e2e/bug-29-34-live.spec.ts`](../../apps/web/e2e/bug-29-34-live.spec.ts), and
its screenshots are `working/173-*` through `working/179-*`. It covers the
capacity refresh/admin surface, execution-environment selection, bounded source
review, attachment placement in Chat and Build, memory lifecycle controls, and
approval restoration after a full page reload. Credentials were entered through
the product UI and are not stored in the repository or test artifacts.

FIXED-76 through FIXED-84 were verified on **2026-08-01** against a running
`raiker-web` using owner-configured Anthropic and OpenRouter credentials and the
Ollama `gemma4:31b-cloud` model. The live scenario is
[`e2e/bug-36-38-42-43-live.spec.ts`](../../apps/web/e2e/bug-36-38-42-43-live.spec.ts),
and its screenshots are `working/180-*` through `working/184-*`. It covers price
review metadata, a real attachment-backed Chat turn, keyboard and axe checks for
both dialogs, Schedule attachment presentation, and cumulative Daytona budget
state. Credentials were entered through the product UI and are not stored in
the repository or test artifacts.

FIXED-85 through FIXED-89 were verified on **2026-08-01** against a running
`raiker-web` holding an owner-entered Anthropic credential and answering with
`claude-haiku-4-5-20251001`. The live scenario is
[`e2e/bug-37-39-40-41-live.spec.ts`](../../apps/web/e2e/bug-37-39-40-41-live.spec.ts),
and its screenshots are `working/185-*` through `working/193-*`. It walks every
route at 375 / 768 / 1024 / 1440 px in both themes checking for horizontal
overflow and console errors, reads the type, motion and density tokens back off
the running document, shows Compact density shortening a real table row, drives
the Host control through pause and resume, and records the Tasks card for a
parked scheduled run. The parked run's state is written by `TaskManager` — the
same code the scheduler calls — rather than reached through a full approval
round trip; the signal that continues it is covered by
`tests/test_scheduler_wakeup.py`, and the quit-with-waiting-work branch by
`tests/test_api_host.py`. The credential was entered through the product UI and
is not stored in the repository or test artifacts.

FIXED-92 and FIXED-93 were verified on **2026-08-02** against two running
`raiker-web` hosts. The first is a source checkout holding an owner-entered
Anthropic credential and answering a live `claude-haiku-4-5-20251001` turn; the
second was started **from inside a release artifact** this change's pipeline
built, with `PYTHONPATH` and `RAIKER_INSTALL_ROOT` pointing at the extracted
payload, so the code answering is the artifact's own copy and the provenance it
reports comes from the `installation.json` that build wrote. The live scenario is
[`e2e/bug-44-47-live.spec.ts`](../../apps/web/e2e/bug-44-47-live.spec.ts), and
its screenshots are `working/197-*` through `working/200-*`. The same run
executes the release commands `.github/workflows/release.yml` runs — the signed
channel index, the verification an installed Raiker performs, the packaging smoke
test, and the native `.deb` — because a browser cannot screenshot `dpkg-deb` but
a run either produces a verifiable release or it does not. That artifact was
built **without platform signing**, and every surface says so; the credential was
entered through the product UI and is not stored in the repository or test
artifacts.

FIXED-99 was verified on **2026-08-03** against a running `raiker-web` whose
model is a local OpenAI-compatible stub rather than a hosted provider, for the
reason ADD-02's run states: what this entry changes is how the runtime handles
one specific batch shape, and a hosted model does not reliably emit the same
batch twice. Everything downstream of the stub — orchestrator, broker, policy
engine, approvals inbox, suspended-turn store and resume endpoints — is the
shipped product. The live scenario is
[`e2e/bug-52-first-pass-denial-live.spec.ts`](../../apps/web/e2e/bug-52-first-pass-denial-live.spec.ts),
and its screenshots are `working/bug-52-*`. It drives both shapes the entry
names: a read-only batch whose refused first call no longer ends the turn, and a
batch whose refused first call is followed by two writes, which now reaches
**decision 2 of 3** and then **decision 3 of 3** instead of dropping both.

FIXED-100 was verified on **2026-08-03** against **two** running `raiker-web`
hosts on the same machine — one built from this change, one from the commit
before it — because what this entry claims is a *difference* between them, and a
single host can only show one side of it. Both were driven through the product's
own instance surface, and the descriptor counts below were read from
`/proc/<pid>/fd` of the two host processes. The live scenario is
[`e2e/bug-50-connection-cache-live.spec.ts`](../../apps/web/e2e/bug-50-connection-cache-live.spec.ts),
and its screenshots are `working/bug-50-*`. Its final test drives a hosted turn
and is the only part that needs a provider credential; **it skipped in this run**
— the key supplied for the session was rejected by Anthropic itself
(`authentication_error: API key is invalid`), which is a fact about the
credential and not about the host. Nothing else in the file depends on a model,
because what FIXED-100 changes sits below the model entirely.

| ID | Severity | Area | Status |
|---|---|---|---|
| FIXED-01 | High | Models | Fixed |
| FIXED-02 | High | Chat / API redaction | Fixed |
| FIXED-03 | Medium | Models / Chat / Build | Fixed |
| FIXED-04 | **Critical** | Chat orchestration | Fixed (was BUG-02) |
| FIXED-05 | High | Models / policy | Fixed |
| FIXED-06 | High | Chat / Build rendering | Fixed (was BUG-03) |
| FIXED-07 | High | API redaction | Fixed (was BUG-04) |
| FIXED-08 | **Critical** | Approvals / file output | Fixed (was BUG-06) |
| FIXED-09 | **Critical** | Build / Chat agent loop | Fixed (was GAP-BUILD B2) |
| FIXED-10 | Medium | Chat / attachments | Fixed (was BUG-07) |
| FIXED-11 | High | API redaction | Fixed (found while fixing BUG-07) |
| FIXED-12 | Medium | Export | Superseded by FIXED-19 (was BUG-08) |
| FIXED-13 | Medium | Tasks | Fixed (was BUG-09) |
| FIXED-14 | High | API redaction | Fixed (found while fixing BUG-09) |
| FIXED-15 | Low | Chat / Tasks | Fixed (was BUG-10) |
| FIXED-16 | Medium | Permissions | Fixed (was BUG-11) |
| FIXED-17 | High | MCP | Fixed (was BUG-12) |
| FIXED-18 | Low | Permissions | Fixed (was BUG-13) |
| FIXED-19 | Medium | Chat / file output | Fixed (found while fixing BUG-13) |
| FIXED-20 | High | Chat / Build file retention | Fixed (found while fixing BUG-14) |
| FIXED-21 | Low | CI quality gates | Fixed (found while verifying BUG-14) |
| FIXED-22 | Low | Chat / Build file retention | Fixed (found while fixing BUG-14) |
| FIXED-23 | High | Build / patch application | Fixed (was GAP-BUILD B3) |
| FIXED-24 | Low | Documentation / known limits | Fixed (found while verifying FIXED-23) |
| FIXED-25 | Low | Build / cross-platform paths | Fixed (found while verifying FIXED-23) |
| FIXED-26 | Low | Chat / cost presentation tests | Fixed (was BUG-14) |
| FIXED-27 | Low | CI / action runtime | Fixed (was BUG-15) |
| FIXED-28 | Low | Web test runtime | Fixed (was BUG-16) |
| FIXED-29 | Medium | Build / patch application | Fixed (B3 single-target expansion) |
| FIXED-30 | Medium | Models / credential persistence | Fixed |
| FIXED-31 | Medium | Chat / Build composer | Fixed |
| FIXED-32 | High | Web development dependencies | Fixed (was BUG-17) |
| FIXED-33 | Low | Python test dependencies | Fixed (was BUG-18) |
| FIXED-34 | High | Build / multi-file patch application | Fixed (B3 expansion) |
| FIXED-35 | Medium | Settings / Models | Fixed |
| FIXED-36 | Medium | Writing quality | Fixed (optional local integration) |
| FIXED-37 | High | Chat / connector actions | Fixed (C2 inventory and preview) |
| FIXED-38 | Medium | Chat / connector compensation | Fixed (was BUG-19) |
| FIXED-39 | High | Build / parallel tool execution | Fixed (was B4) |
| FIXED-40 | High | Chat / document output | Fixed (was C1) |
| FIXED-41 | High | Chat / connector execution | Fixed (C2 multiple-call expansion) |
| FIXED-42 | High | Chat / cross-work recall | Fixed (was C3) |
| FIXED-43 | High | Chat / document output | Fixed (C1 format expansion) |
| FIXED-44 | High | Build / command feedback | Fixed except host network containment (B5) |
| FIXED-45 | Medium | Chat / file inspector and output | Fixed (C4/C5 validation and presentation) |
| FIXED-46 | Medium | Workbench | Fixed (activity-aware dashboard redesign) |
| FIXED-47 | High | Build / command containment | Fixed (was BUG-20) |
| FIXED-48 | Medium | Settings / Workbench | Fixed (settings and dashboard refinement) |
| FIXED-49 | Medium | Memory / Knowledge Map / context window | Fixed (visual control redesign) |
| FIXED-50 | High | Local models / context capacity | Fixed (runtime capacity discovery) |
| FIXED-51 | High | Knowledge Map / force simulation | Fixed (found during live Playwright verification) |
| FIXED-52 | Medium | Knowledge Map / theme integration | Fixed (found during visual review) |
| FIXED-53 | Medium | Models / pricing | Fixed (was BUG-21) |
| FIXED-54 | Medium | Chat / Build export | Fixed (was BUG-22) |
| FIXED-55 | Low | Chat / Build code ergonomics | Fixed (was BUG-23) |
| FIXED-56 | High | Approvals / cross-tab continuation | Fixed (was BUG-24) |
| FIXED-57 | Low | Models / shipped configuration | Fixed (found while fixing BUG-21) |
| FIXED-58 | Low | Web test runtime | Fixed (found while verifying BUG-21) |
| FIXED-59 | High | Tasks / approval continuation | Fixed (was BUG-25) |
| FIXED-60 | Low | File inspector / images | Fixed (was BUG-26) |
| FIXED-61 | Medium | Memory / provenance | Fixed (was BUG-27) |
| FIXED-62 | Medium | Chat / artifact download | Fixed (was BUG-28) |
| FIXED-63 | High | Runtime | Fixed (single runtime; no mode selection) |
| FIXED-64 | Low | Build / composer attachments | Fixed (was BUG-35) |
| FIXED-65 | Medium | Composers / Chat, Build, Workbench | Fixed (shared composer) |
| FIXED-66 | Medium | Distribution / cross-platform launch | Fixed (`raiker-app`) |
| FIXED-67 | Medium | Composers / attachment presentation | Fixed (attached files look like files) |
| FIXED-68 | High | Memory / governed lifecycle | Fixed (was BUG-29) |
| FIXED-69 | Medium | Knowledge Map / sources and scale | Fixed (was BUG-30) |
| FIXED-70 | High | Build / remote execution containment | Fixed (was BUG-31) |
| FIXED-71 | Medium | Local models / capacity administration | Fixed (was BUG-33) |
| FIXED-72 | Medium | Chat / restored approval state | Fixed (was BUG-34) |
| FIXED-73 | Low | Chat / Build attachment layout | Fixed |
| FIXED-74 | Medium | Build / Windows container sandbox | Fixed (found during verification) |
| FIXED-75 | Low | Models / capacity history ordering | Fixed (found in GitHub CI) |
| FIXED-76 | Low | Models / shipped price review cadence | Fixed (was BUG-36) |
| FIXED-77 | Medium | Memory / source coordinates | Fixed (was BUG-38) |
| FIXED-78 | Medium | Cloud execution / billing | Fixed (was BUG-42) |
| FIXED-79 | Low | Web / accessibility | Fixed (was BUG-43) |
| FIXED-80 | Low | Schedule / attachments | Fixed (consistency improvement) |
| FIXED-81 | Medium | Chat / Build / Workbench / Tasks | Fixed (found during live verification) |
| FIXED-82 | Medium | Export / Knowledge Map accessibility | Fixed (found by live axe verification) |
| FIXED-83 | Medium | Chat / export keyboard activation | Fixed (found during live verification) |
| FIXED-84 | Low | CI / dependency licensing | Fixed (found during workflow verification) |
| FIXED-85 | Medium | Settings / concurrent load | Fixed (found while verifying BUG-37) |
| FIXED-86 | Low | Design system / visual language | Fixed (was BUG-37) |
| FIXED-87 | Low | Scheduler / continuation latency | Fixed (was BUG-39) |
| FIXED-88 | Medium | Distribution / host lifecycle | Fixed (was BUG-40, less packaging — closed by FIXED-92) |
| FIXED-89 | Low | Web / e2e regression suite | Fixed (was BUG-41) |
| FIXED-90 | Medium | Terminal / approval execution | Fixed (was BUG-32) |
| FIXED-91 | Low | Storage / per-request key derivation | Fixed (was BUG-45) |
| FIXED-92 | Medium | Distribution / release pipeline and signed updates | Fixed (was BUG-44, less the wizard and tray — see BUG-48) |
| FIXED-93 | Low | Models / provider test feedback | Fixed (was BUG-47) |
| FIXED-94 | High | Build / turn plan state | Fixed (was B6) |
| FIXED-95 | High | Build / model-spawned subagents | Fixed (was B7) |
| FIXED-96 | Medium | Extensions / MCP agent reachability | Fixed (B8 review; found the surface was silent) |
| FIXED-97 | High | Runtime / undeclared event types | Fixed (found during B6 live testing; B4's drop evidence killed the turn) |
| FIXED-98 | High | Policy / advertised tools with no verdict | Fixed (found while implementing B6/B7) |
| FIXED-99 | Medium | Runtime / batched policy refusal | Fixed (was BUG-52) |
| FIXED-100 | Medium | Storage / connection cache holds every workspace open | Fixed (was BUG-50) |
| BUG-46 | Medium | Storage / Windows locked memory | Open (found while verifying FIXED-91) |
| BUG-48 | Medium | Distribution / setup wizard and native tray | Open (split out of BUG-44) |
| BUG-49 | Low | CI / release workflow action pinning | Open (found while building the release workflow) |
| BUG-51 | Low | Policy / dead `denied_actions` configuration | Open (found while implementing B6/B7) |
| BUG-53 | Low | Chat / multi-call answer text runs together | Open (found while verifying FIXED-99) |
| BUG-54 | Medium | Web e2e / the live stub model is not in the repository | Open (found while writing FIXED-99's live scenario) |
| BUG-55 | Low | Chat / a disabled transcript block reads as live code | Open (found while verifying FIXED-99) |
| BUG-56 | Low | Tests / a shipped-skill check breaks after `compileall` | Open (found while verifying FIXED-100) |
| GAP-BUILD | — | Build — coding-agent parity | Analysis (B1–B8 complete; 12 items remain) |
| GAP-CHAT | — | Chat — work-assistant parity | Analysis (14 items remain) |

---

## FIXED-01 — Model connection showed a raw reason code with no way to act on it

**Status: fixed in this change.**

**Observed.** Models → Anthropic → Connect → paste key → Connect produced:

> Could not connect (403: provider_requires_explicit_policy_approval)

and nothing else. The same dialog then produced
`model_egress_denied:no_allowlist` and `connector_vault_key_unset` as each
earlier blocker was cleared. `not-working/BUG-05-model-connect-raw-reason-code.png`.

**Is it a policy issue?** **Yes — every one of those three refusals is correct
fail-closed behaviour, not a bug in the gate logic.** `PUT
/api/models/{id}/connection` constructs the provider through
`ModelProviderFactory` before persisting the credential, so it enforces the full
chain up front:

1. `raiker/models/policy_state.py` derives `allow_hosted_provider` from the
   `hosted_model_runtime` **capability gate**, which is off on a fresh account →
   `provider_requires_explicit_policy_approval`.
2. `raiker/models/endpoint_policy.py` requires the endpoint host to be on
   `RAIKER_MODEL_EGRESS_ALLOWLIST` → `model_egress_denied:*`.
3. `raiker/runtime/connector_ecosystem.py` requires a Fernet vault key before it
   will encrypt the credential → `connector_vault_key_unset`.

The **defect was the user experience**: the person pasting an API key was shown
audit vocabulary and left to guess. Two of the three blockers are fixable in the
app in under a minute; nothing said so.

**Fix applied.** New `apps/web/src/lib/providerErrors.ts` maps each governed
reason code to a plain-language statement, the concrete next step, and an in-app
link (`#/capabilities` for the gate, `#/settings` for the vault key). The
sign-in dialog renders that guidance and keeps the raw code visible underneath
for audit correlation. Unknown codes fall through to the previous raw message so
nothing is ever silently swallowed. Covered by
`apps/web/src/lib/providerErrors.test.ts`.

**Deliberately not changed.** The egress allowlist stays process configuration
(`RAIKER_MODEL_EGRESS_ALLOWLIST`). It is the last boundary before bytes leave
the machine; making it editable from a browser session would let a compromised
session widen its own egress. The dialog now says so explicitly and prints the
exact `RAIKER_MODEL_EGRESS_ALLOWLIST=<host>` line to use.

**Still worth a maintainer decision:** should saving an *encrypted credential*
require the full runtime provider policy at all? Storing a key in the vault
performs no network I/O. Deferring the gate check to first use would let a user
prepare credentials before opening gates, at the cost of a later failure point.

---

## FIXED-02 — Context meter showed `0 / NaN (NaN%)`; token counts stripped from the audit log

**Status: fixed in this change.**

**Observed.** Chat → Context popover:

> Context window &nbsp;&nbsp; 0 / NaN (NaN%)

with `role="progressbar"` carrying `aria-valuenow="NaN"` and a bar drawn at full
width. `not-working/BUG-01-context-window-NaN.png`.

**Reproduce.** `GET /api/models` returned
`"context_window_tokens": "***REDACTED***"` for **every** profile.

**Root cause.** `raiker/events/export.py::_is_secret_key` treats any key whose
name *contains* `token` as a credential. That is right for `api_token` and
`owner_token` — and wrong for `context_window_tokens`, `input_tokens`,
`output_tokens`, `cache_read_input_tokens`. The response-redaction layer
therefore replaced an integer capacity with a string, and the browser divided by
it.

This also silently stripped the normalised usage numbers out of the durable
event log, contradicting `docs/WEB_APP_LIVE_TEST.md`, which records
`model_request_completed` usage as `{input_tokens: 2694, output_tokens: 37, …}`.

**Fix applied.** `NON_SECRET_TOKEN_COUNT_KEYS` plus `is_token_count_field()` in
`raiker/events/export.py`: an exemption applies only when the key is an **exact**
match from that set **and** the value is a non-boolean `int`. A string or bool
under one of those names is still redacted, so a credential cannot ride out
under a count-shaped key. Wired into `redact_event_payload`, `redact_response_body`
and `assert_no_secrets_in_body`. Covered by `tests/test_token_count_redaction.py`.

**Follow-on.** The estimate fallback and the missing cost data were addressed
separately in FIXED-03 below; automatic 90 % compaction and a weekly quota remain
open and are not tracked by any entry in this document.

---

## FIXED-03 — No token or cost accounting; Models showed a meaningless percentage

**Status: fixed in this change.**

**Observed.** Two related gaps. The context popover could show how full a window
was but never what a conversation had cost, and Build had no context control at
all. Separately, the Models page headline read **"0% setup complete"** against a
denominator of every profile Raiker ships — a user who connects the one provider
they intend to use is finished, not 10% finished.

**Fix applied.**

*Accounting.* `model_usage_ledger` records the normalised token counts the
runtime already emits on `model_request_completed`. Counts only — no prompt or
response text — and **cost is never stored**, only derived at read time, so
correcting a price re-prices history rather than leaving stale money on disk.
`GET /api/sessions/{id}/context-usage` serves per-chat and provider all-time
figures; the same `ContextMeterPopover` now renders them in **Chat and Build**.

*Prices.* `raiker/models/pricing.py` resolves each fact from three sources in a
fixed precedence — owner override, provider-published, shipped list price — and
the winning source is always named in the UI. Capacity and price resolve
independently, so Anthropic yields a provider-reported context window next to a
config-sourced price. Only providers that are both off-machine and API-key
authenticated can accrue cost; LM Studio reads `LM_API_TOKEN` but runs on
`127.0.0.1` and correctly reports "no API cost".

*Models page.* The percentage is now a count — "1 of 10 providers set up" —
with the total API cost beside it, and every provider card carries its own
usage line and a bar showing its share of total spend.

**Also corrected here:** the flat `context_window_tokens: 200000` added for
Anthropic in the previous change was already wrong — Anthropic's `/v1/models`
reports `max_input_tokens` per model, and Opus 5 returns 1,000,000. Capacity is
now pulled from the provider and the hardcoded value is gone.

**Open follow-ups, deliberately not done here:**

- **Shipped list prices are unverified.** `config/model-profiles.json` seeds
  rates only for models whose published price is recorded, each stamped
  `as_of: 2026-07`. They should be checked against each provider's pricing page
  and refreshed. A model absent from the table reports its cost as unknown
  rather than borrowing a sibling's rate — Claude models differ by ~15x.
- **No periodic refresh.** Provider facts are cached when a catalogue listing
  runs (opening "Choose model…" or pressing Test). A background refresh on a TTL
  would keep OpenRouter's published prices current without a manual step.
- **No Settings UI for price overrides.** The route
  (`PUT /api/models/{id}/price`) and storage exist and are owner-scoped; only
  the form is missing.
- **Cache reads are billed at the full input rate**, so a cached-heavy turn
  reads slightly high. Deliberate: over-estimating is the safe direction for a
  bill. Splitting the rate needs a per-provider cache-discount fact.

---

## FIXED-04 — Chat had no conversation memory at all *(was BUG-02, critical)*

**Status: fixed in this change.**

**Observed.** In a **single** chat:

1. "Remember this codeword: MARIGOLD-42. Reply with just OK." → *"OK"*
2. "What was the codeword I gave you?" → *"I don't have any record of you
   providing me with a codeword in our conversation history. **This is the first
   message in our current session.**"*

Both bubbles are visible on screen. `not-working/BUG-02-no-conversation-memory.png`.

**Root cause.** `raiker/runtime/orchestrator.py` (~line 510) builds the request
as: system prompt, workspace-context system message, optional retrieval context,
then **one** user message from `envelope.prompt.text`. Prior turns are persisted
and rendered, but never sent to the provider. Every turn is a fresh single-shot
request.

**Impact.** Follow-up questions, iterative work, and clarification flows are all
impossible. It also makes the context meter meaningless even once FIXED-02 lands
— usage cannot grow if the transcript is never sent. And the
`assign_session_project` / clarification flows in
`2026-07-26-chat-tasks-and-project-assignment-design.md` cannot work without it.

**Fix applied.** `raiker/runtime/conversation_history.py` rebuilds the prior
completed exchanges from the persisted `turns` rows — the same rows the Chat view
hydrates from, so what the model sees and what the user sees have one source —
and the orchestrator appends them before the current prompt.

- Only **completed** exchanges are replayed. A turn with no reply would put an
  unanswered question in front of the model and skew the next response.
- Bounded by the model's context window: half of a provider-reported capacity,
  or a conservative default. When it will not all fit, the **oldest** exchanges
  are dropped, because a follow-up depends on recent context.
- Scoped to the session, so a new chat still starts genuinely empty.
- Recorded as a `conversation_history_replayed` audit event carrying counts
  only, never the transcript.

Also raised: `close_turn` truncated the persisted reply to 500 characters, which
silently truncated both the replayed history *and* the transcript the Chat view
renders on resume. Now `TURN_SUMMARY_MAX_CHARS = 8000`.

**Verified live** on a bare workspace: "Remember this codeword: MARIGOLD-42" then
"What was the codeword?" → `MARIGOLD-42`. A separate new chat asked the same
question replied `NONE`. `working/96-conversation-memory-fixed.png`,
`working/97-cross-chat-isolation.png`. Covered by
`tests/test_owner_consent_and_history.py`.

**Caught during this fix:** the first implementation emitted an unregistered
event type and killed the stream mid-turn — a direct violation of HANDOFF's
"Add a typed event to `EVENT_TYPES` before emitting it". The event is now
registered and documented in `docs/EVENT_CATALOG.md`.

---

## FIXED-05 — Three separate walls in front of a provider the owner had already chosen

**Status: fixed in this change.**

**Observed.** A first-time setup hit three refusals in sequence, each requiring a
different surface to resolve:

1. `provider_requires_explicit_policy_approval` — the `hosted_model_runtime`
   capability gate was off.
2. `model_egress_denied:no_allowlist` — no host on `RAIKER_MODEL_EGRESS_ALLOWLIST`.
3. `connector_vault_key_unset` — no Fernet key to encrypt the credential with.

FIXED-01 made each one *explainable*. It did not make any of them go away.

**Why they were wrong.** `docs/HANDOFF.md` → "Security posture" is explicit:

> Raiker is **owner-authoritative and monitored, not prevention-by-restriction.**
> […] Do **not** put a hard block in front of the owner's legitimate choices by
> default — allow, monitor, surface anomalies […] Reserve hard prevention for a
> last resort.

and reconciles it with the fail-closed rule:

> Fail closed: a missing gate, policy, credential, allowlist, executor, or
> approval denies the action. *(This is honesty — no fabricated success — not a
> wall in front of the owner.)*

Pasting an API key **is** the owner's legitimate choice, made deliberately while
authenticated. Requiring them to then discover a capability gate, an environment
variable, and a key-generation button before that choice took effect was a wall,
not honesty.

**Fix applied.**

- **Gate.** `provider_runtime_policy_from_gates` now treats a saved connection as
  the authorization. `gate_explicitly_disabled` distinguishes "no decision
  recorded" (the runtime's synthesised fail-closed default) from "the owner
  turned this off", so **revocation still wins absolutely**.
- **Egress.** A configured connection authorises that profile's own resolved
  endpoint — that host and no other. `RAIKER_MODEL_EGRESS_ALLOWLIST` still works
  for pre-authorising hosts, and an unconfigured profile still fails closed.
- **Vault key.** Provisioned on the credential **write** path at `0600`. It is a
  locally generated encryption key, not a passphrase the owner invents, so the
  resulting key was identical either way. Reads deliberately do **not**
  provision: a missing key on read means existing credentials genuinely cannot
  be decrypted, and minting a fresh one would hide a real problem.

**Verified live** on a workspace with no environment allowlist, no vault key, no
runtime mode, and no gates: register → Models → Connect → paste key →
`200 {"connection_configured": true}`.
`working/95-clean-first-run-connect.png`.

**What is still refused**, covered by `tests/test_owner_consent_and_history.py`:
an account that has configured nothing; a host belonging to no configured
provider; a gate the owner explicitly disabled; another principal's connections;
and every deferred dangerous domain. Approvals, audit, and the STOP switch are
untouched.

---

## FIXED-06 — Markdown is not rendered in Chat

**Status: fixed in this change (was BUG-03).**

**Observed.** Asked for a markdown document; the reply bubble showed literal
`# Quarterly Report`, `- bullet`, `| Metric | Value |` and ``` fences as plain
text. DOM audit of the transcript: `h1: 0, table: 0, pre: 0, code: 0, ul: 0`.
`not-working/BUG-03-chat-markdown-not-rendered.png`.

**Impact.** Every code block, table, and list a model produces is unreadable.
This is the single most visible quality gap in the product.

**Root cause.** `ChatView.svelte` and `BuildView.svelte` bound the answer into a
`<p class="bubble-text">{answer}</p>`. Svelte escapes an interpolation, so the
model's markdown reached the DOM as one text node — correct as security, wrong
as product.

**Fix applied.** New `apps/web/src/lib/markdown.ts` — a dependency-free,
escape-first renderer — behind `apps/web/src/lib/components/Markdown.svelte`,
the single supported caller and the only place `{@html}` is used for model
output. Chat and Build both render assistant answers through it. Supported:
ATX headings, ordered/unordered lists with nesting, GFM tables with alignment,
fenced code with a language label, blockquotes, thematic breaks, soft line
breaks, and inline code, emphasis, strong, strikethrough and links.

**Security posture**, matching what the file-inspector design already specifies
(*"Markdown is sanitized before rendering"*, *"Preview renderers never execute
embedded code or macros"*):

- **Escape first, mark up second.** Every run of source text goes through
  `escapeHtml` *before* any tag is emitted, so raw HTML in a model reply is
  data, not markup. There is no sanitiser to bypass — raw HTML is never parsed
  as HTML at all.
- **A closed tag set.** Only tags written literally in the module can reach the
  DOM. No attribute is ever copied from the source: the only ones emitted are a
  `class` from a fixed allowlist and an `href` that must match `http(s):` or
  `mailto:`, or the link degrades to plain text. A `javascript:`, `data:` or
  `vbscript:` URL cannot be emitted. Links carry
  `rel="noopener noreferrer nofollow ugc"`.
- **No remote fetches.** An image renders as a labelled link, never an `<img>`,
  so a model cannot make the browser call a third-party host — Raiker's built UI
  still makes no external request of any kind.

**Deliberately not done here.** No syntax highlighting (it would mean shipping a
grammar bundle and a second pass over untrusted text for a cosmetic gain), no
copy-to-clipboard button on code blocks, and no markdown in the *user's* own
bubble — what someone typed is shown as they typed it.

**Verified.** 33 renderer unit tests (`markdown.test.ts`), 5 component tests
(`components/Markdown.test.ts`), and view-level regressions in
`ChatView.test.ts` / `BuildView.test.ts` that re-run the DOM audit from this
entry. In Chromium against the shipped component in the chat bubble, in both
themes: `h1: 1, h2: 1, table: 1, pre: 1, code: 2, ul: 2, ol: 1, li: 8,
blockquote: 1, a: 2, hr: 1` with `img: 0, script: 0`, no literal `# Quarterly
Report` or `| Metric |` left in the text, no page-level horizontal scroll, no
dialog raised by an injected `onerror`, and zero external requests.
`working/83-FIXED-06-chat-markdown-rendered.png`. That capture is a Chromium
render of `Markdown.svelte` inside the chat bubble markup, not a live model
turn — this environment has no provider credential.

**Follow-on.** BUG-08 (export / one-click PDF) is now unblocked on the rendering
side: there is real HTML to print. The control itself is still missing.

---

## FIXED-07 — Over-broad redaction destroyed legitimate assistant text and chat titles *(was BUG-04)*

**Status: fixed in this change.**

**Observed.** Attached `sample.md` containing "The secret project code is
ORCHID-9" and asked what the code was. The reply rendered as:

> I can see from the workspace context that there's an attached document
> (sample.md**\*\*\*REDACTED\*\*\*** comes directly from the uploaded markdown
> file that was provided in the attachment.

and the conversation's title in **RECENT CHATS** became literally
`***REDACTED***`. `not-working/BUG-04-response-text-over-redacted.png`.

**Root cause.** `raiker/api/redaction.py::_redact_value`, string branch: after
`redact_text` found no actual secret pattern, it *still* replaced the **entire
string** if it merely contained the substring `secret`, `token`, `password`,
`bearer`, or `authorization`. Ordinary English prose was destroyed.

Both symptoms come from that one line. The streamed reply is redacted per chunk
in `routes_prompts.py::_sse`, so each `text_delta` carrying the word was swapped
for `***REDACTED***` while its neighbours survived — which is why the sentence
came back with a hole punched through the middle rather than blanked. The title
is derived from the first prompt in `SQLiteStore.insert_turn` and stored
unredacted; the question itself contained "secret", so the whole title was
replaced on the way out to **RECENT CHATS**.

**Fix applied.** A value's **key** is a reliable signal that it holds a
credential; a value's **words** are not. `_redact_value` therefore keeps
discarding whole any value under a secret-like key, and now scrubs free-form
strings by credential *shape* only — `redact_text` matches `sk-…`, `ghp_…`,
`github_pat_…`, `AKIA…`, `Bearer …`, `token=…`, PEM blocks, emails, card/ID
numbers, and high-entropy runs, substituting **only the matched span**. Prose
survives, and every redaction stays visible in place as a `[REDACTED_*]` marker,
so nothing is silently lost. `assert_no_secrets_in_body` was relaxed in exactly
the same way, so the test guard proves what the middleware actually emits.

To cover what the keyword sweep used to catch in ordinary sentences,
`raiker/context/redaction.py` gains one pattern for credentials disclosed in
prose — "the password is hunter2". The credential word must sit *immediately*
before the copula, so "the secret **project code** is ORCHID-9" never matches,
and a callable replacement spares plain short English words so "the secret is
out" survives too.

One follow-on effect, and it is wanted: `credential_env` and the MCP `auth_ref`
now return the env-var **name** (`RAIKER_GITHUB_TOKEN`) instead of
`***REDACTED***`. The name is remediation guidance printed throughout these
docs; the value it points at is read from the process environment and never
enters a response. Covered by `tests/test_over_broad_redaction.py`.

**Deliberately not changed.** The identical keyword sweep in
`raiker/events/export.py::_redact_string_value` still guards **audit exports**.
An export leaves the machine in bulk and is read by tooling, not by a person
mid-conversation, so over-redaction there costs little and belt-and-braces is
worth keeping. The asymmetry is asserted by a test so it cannot drift by
accident.

**Residual risk.** A credential can still ride out inside free-form text if it
has an unrecognised shape *and* an unrecognised separator — "my token — abc123".
That was already true of any secret that did not happen to sit next to one of
the five keywords; the pattern set in `raiker/context/redaction.py` is the place
to close it.

---

## FIXED-08 — Nothing in the app could actually write a file *(was BUG-06)*

**Status: fixed in this change.**

**Observed.** Chat proposes `write_file` → Approvals shows the exact diff →
**Approve (record only)** returns `executes_action: false` and the response says
*"Recorded: approved. The action was NOT executed (metadata-only)."* The file is
never created. Enabling `approval_execution_relay` did not change this.
`not-working/BUG-06-approval-never-executes.png`.

**Root cause.** Not a missing executor — a missing wire. Everything needed
already existed and was already tested: `FileWriteExecutor` /
`PatchApplyExecutor` do the write, and `ApprovalExecutionRelay`
(`raiker/runtime/executors/tier1_approval.py`) implements the hard part
correctly — TTL, argument-hash TOCTOU check, posture check, atomic
`pending → executing → executed` claim, and re-routing the target through
`RuntimeAuthority` so it re-passes its own gate, decision mode and policy review
at execution time. `POST /api/approvals/{id}/resolve` simply never called it. It
called `ApprovalInbox.resolve`, which records a decision and returns.

Two smaller things made "enabling the relay" appear not to work, and both are
now fixed: `approval_execution_relay` was **absent from `CAPABILITY_GATE_MAP`**,
so `check_capability_gate` found no gate for it and the relay's own gate was
never actually consulted by `route_action`; and there was no path from the API
to the relay at all.

**Decision taken.** The first of the two options this entry offered: wire the
relay through for file mutations, rather than restate the limitation in the UI.
It follows the `connector_write` precedent already in the codebase — a
model-proposed connector mutation is parked and genuinely executed on approval
(`raiker/api/routes_approvals.py`) — and it is the one change B1 and C1 both
depend on.

**Fix applied.** New `raiker/approvals/execution.py`. When the owner approves a
**pending, non-critical** approval whose capability is `file_write_execution` or
`patch_apply_execution`, the resolution is handed to the relay through
`RuntimeAuthority.route_action`, so the documented "governed entry only"
property holds unchanged. It runs *before* the metadata-only inbox would resolve
the approval, because the relay claims a `pending` row atomically — that claim
is the single-execution primitive.

Kept deliberately narrow:

- **Two capabilities, named explicitly.** `EXECUTABLE_ON_APPROVAL` is a
  two-member frozenset. `shell`, `process` and `network` still record a decision
  and execute nothing — a file write is local, checkpointed and reversible, and
  those three are not. Widening the set is an edit to that frozenset, guarded by
  a regression test.
- **Both gates still decide.** The relay's own capability and the target's are
  each consulted; either being off returns resolution to exactly the previous
  metadata-only behaviour. Revocation still wins absolutely.
- **Critical is untouched.** A critical approval never takes this path; it keeps
  the human-only, step-up-verified lifecycle in `resolve_critical_approval`.
- **Reversible.** `route_action` snapshots the file's pre-image into the
  checkpoint blob store before the executor runs, so an approved overwrite can
  be rewound. Approve is not a one-way door.

**Raised by this change, and closed here.** Once an approved write really
executes, confinement to the workspace stops being sufficient: the workspace
*contains* `.raiker/` — the encrypted store, the audit log, the vault key, the
hook definitions (which run commands) and the MCP server scripts — and `.git/`,
whose hooks run on the next commit. A model-proposed write to any of those was
inside `resolve_workspace_path`'s boundary. New
`resolve_writable_workspace_path` refuses both trees, applied at proposal time
(so no un-executable approval is parked) and at the executor, which is the
authoritative boundary. Reads are unaffected. HANDOFF reserves hard prevention
for a last resort; the agent rewriting the machinery that records and constrains
it is that case.

**Honest surfaces, in both configurations.** The server computes
`executes_on_approval` and the Approvals detail states which kind of decision
this is *before* the owner presses anything; the button reads **Approve and
execute once** or **Approve (record only)** accordingly, and the result names
the file written. `ToolBroker`'s `expected_effect` — which previously told the
model "metadata-only … does not execute the action" for every non-connector tool
— is now derived from the same check, and Chat/Build render it. An `executed`
filter tab was added, or every approval the owner actually carried out would
have vanished from the queue.

**Verified.** `tests/test_approval_execution_wiring.py` (16 tests): an approved
write reaching disk with the response naming it; `apply_patch` through its own
capability; the pre-image checkpoint; the audit trail carrying
`approval_received` + `approval_executed` + `action_executed`; both gates
returning resolution to metadata-only; critical refused with
`critical_approval_requires_lifecycle`; tampered payload and expired approval
refused with nothing written; `.raiker/`, `.git/` and outside-workspace paths
refused; a failed execution left terminal so it can never be silently re-run;
and a replay of an executed approval returning 409. Plus filesystem-guard tests,
broker `expected_effect` tests, a rewritten
`tests/test_security_regression_ui.py::TestApprovalExecutionIsNarrow` that fails
if a Tier-2 approval ever starts executing, and three new `ApprovalsView` tests.

**Verified live** against the running app on a bare workspace, reproducing this
entry's own scenario: approval detail reports `executes_on_approval: true` with
the performs-the-change notice, `POST …/resolve` returns
`{"status": "executed", "executes_action": true, "execution": {"capability":
"file_write_execution", "path": "quarterly-report.md"}}`, the file exists on disk
with the exact proposed contents, the approval is reachable under the new
**executed** tab, and the audit log carries `approval_received`,
`approval_executed`, `action_executed` and `checkpoint_captured`.

**Documentation guards moved with the code, not after it.** The repo's
"documentation never runs ahead of code" validators encoded the old rule as
required wording (`"approval resolution is metadata-only"`) and a forbidden
overclaim (`"approval resolution executes"`). Both were **narrowed rather than
removed**: the required wording is now a set of phrasings that state the
*boundary* — what executes and that everything else does not — and the forbidden
overclaims are the unbounded forms (`"approval resolution executes any"`,
`"… every"`, `"… the approved action"`). A new test asserts the narrowing left no
hole: a doc that names what executes without bounding it is still rejected.

**Still not done, deliberately.** The turn does not resume after the approval
(B2) — the owner must re-prompt for the agent to continue. That is the next
change, and it is what converts a proposer into an agent. `shell` stays
record-only; it belongs with B5's owner-defined command allowlist, not with the
file relay.

The **terminal client's `/approve` is also unchanged** and stays metadata-only
for every capability. It resolves without an authenticated API session, and the
relay's posture control (A4 — deny when the approving session was revoked) has
nothing to check there, so wiring it needs a local-principal decision of its own
rather than a copy of this one. Both CLI messages now name the divergence
instead of leaving it to be discovered.

---

## FIXED-09 — The agent stopped dead at its first write *(was GAP-BUILD B2)*

**Status: fixed in this change.**

**Observed.** With FIXED-08 landed, approving a proposed `write_file` really
wrote the file — and then nothing else happened. The turn had already ended at
`needs_approval`, so the model never learned its own tool call had succeeded.
Continuing meant the owner re-prompting, which starts a *new* turn: the model's
working state is gone and the whole context is paid for again. A coding agent
that has to be re-prompted after every write is a proposal generator with extra
steps.

**Root cause.** `raiker/runtime/orchestrator.py` `break`s out of the agent loop
on `needs_approval` and returns. The loop's working state — the message list it
had built up, the tool-call budget it had spent — lived only in local variables
and went out of scope with the generator.

**Fix applied.** Three parts, deliberately small:

- **Park it.** A new `suspended_turns` table keyed by `approval_id` holds the
  conversation as it stood when the loop stopped, including the assistant
  message carrying the proposed call (a `tool` result is only valid against the
  call it answers). `raiker/runtime/turn_suspension.py` owns the serialisation.
- **Close the call.** Resolving the approval writes the outcome the model will
  see as its tool result. Three genuinely different things can have happened and
  the model has to tell them apart: **executed** replays the real executor result
  and its artifacts; **rejected** is an explicit refusal that tells the model not
  to retry; **approved but not executed** says so plainly, so a capability that
  is still metadata-only can never be mistaken for success.
- **Resume the same loop.** `_arun_agent_loop` was extracted from
  `_aturn_events_inner` so a resumed turn runs the *same* code as a fresh one
  rather than a parallel implementation that could drift. `POST
  /api/approvals/{id}/resume` and `…/resume/stream` continue it, under the same
  turn id, with the same checkpoint and `turn_closed` finalisation — one
  exchange in the transcript, not two.

**Boundaries.**

- **A turn resumes at most once.** Two independent guards — a status check on
  read and an atomic `suspended → resuming` claim — because replaying a parked
  turn would re-send the whole conversation and let the model act twice on one
  decision.
- **Resuming before the approval is resolved is refused.** There is no tool
  result to hand back yet.
- **Parking is best-effort; the approval is not.** If the state cannot be
  stored, the turn is simply not resumable (`turn_suspension_failed`) and the
  owner re-prompts — exactly the pre-B2 behaviour. A storage problem must never
  become a lost approval.
- **The parked conversation never leaves the machine.** It lives in the
  encrypted store; the events carry counts and ids only, and both resume
  endpoints return an `AgentResponse`.
- **Owner-scoped.** A parked turn is loaded by principal, so one account cannot
  resume another's.

**Surfaces.** Build resolves inline and streams the continuation straight into
the same transcript row, which is where this change is felt. Approvals — which
is an inbox, not a transcript — offers **Continue the turn** after a decision
and reports what the agent did, rather than resuming behind the owner's back.

**Verified.** `tests/test_turn_resume_after_approval.py` (15 tests): the working
state is parked with the assistant tool-call message; the event payload carries
no transcript; approving resumes the same turn id with the real result as the
tool message; the resumed call still contains everything the first call had;
rejecting resumes with a refusal and writes nothing; a resumed turn can park
again on its *own* approval; resuming unresolved, twice, or for an unknown
approval each fail closed; auth is required; an approval with no parked turn
reports `resumable: false`; and the streaming route yields a completed final
event. Two `ApprovalsView` tests cover the offered continuation. The
single-resumption test was mutation-checked — it fails when both guards are
removed.

**Still not done, deliberately.** Chat does not auto-continue when the owner
resolves from the Approvals route in another tab; the continuation is offered
there and streamed in Build. FIXED-39 now executes complete read-only tool
batches and reports any call deferred at an approval boundary.

---

## FIXED-10 — No file inspector; attachment chips were not interactive

**Status: fixed in this change.** (Was BUG-07.)

**Observed.** An uploaded `sample.md` rendered as a chip inside the user bubble.
It was not a `button`, had no `role`, and clicking it did nothing. There was no
right-side pane and no overlay. Matched the file inspector's own implementation
note as it then stood: *"This feature is specified but not implemented."*

**Why it needed more than an `onclick`.** The bytes were in the governed
attachment store, but nothing in the system could answer *"may this conversation
show this file?"* An attachment is owned by a principal — that is not the same
claim as belonging to a chat, and reusing ownership alone would have let any
attachment id be previewed from any conversation.

**Fix applied — the authorization first.** A new `session_attachment_refs`
migration records `(session, attachment, owner, turn)`, written by the prompt
route *after* it has confirmed both the session and the attachment belong to the
caller (`raiker/api/routes_prompts.py::_record_attachment_refs`). An id naming
someone else's upload stores nothing. `AttachmentPreviewService`
(`raiker/runtime/attachment_preview.py`) reads nothing without a matching row
*and* an owner-scoped load of the attachment itself, so an unknown id, another
account's file, and a file from another chat are all a 404 — never a 403, which
would confirm the id exists.

**Then the representations, all inert.** `GET
/api/sessions/{id}/attachments/{id}/preview` returns bounded text for
plain-text and `.docx`, cell values for `.xlsx`, and for a PDF or an image a
same-origin authorized URL served by `/preview/pdf` or `/preview/image`. Both
byte routes re-validate before serving (pypdf for a PDF, the magic-byte sniff
for a picture) and pin the content type they just checked, with `nosniff` and
inline disposition — so bytes can never be interpreted as something else, and a
file whose contents do not match its declared type is not served at all. Markdown comes back as **source text**: the
server renders no HTML at all, and the client's existing escape-first renderer
turns `<script>` in an uploaded file into visible characters. An unsupported
type, a record that no longer validates, or a parse error becomes an
`unavailable` preview carrying its reason, never a blank pane. `.xlsx` joined
the upload allowlist with the same fail-closed treatment as `.docx` (magic
bytes, DOCTYPE rejection, bounded decompression, row/column caps).

**And the UI.** `apps/web/src/lib/components/FileInspector.svelte` is a
`complementary` landmark — a right-side pane on a wide window, a dismissible
sheet below the split breakpoint — with no upload, edit, or download control.
Escape closes it and focus returns to the chip. Chips also survive a reload:
`GET /api/sessions/{id}/attachments` returns per-turn metadata so a resumed
conversation redraws them, which a transcript alone cannot do because it
persists prompt text and not the files that rode with it.

**One defect found on the way.** The response-redaction layer replaced
`pdf_url` with `[REDACTED_SECRET]`, so the browser had no URL for its PDF
viewer. That turned out not to be about this feature at all — see **FIXED-11**,
which covers it and the three other locator fields it was silently destroying.

**Images included.** The plan's goal names PDF/Markdown/XLSX/DOCX, but a chip
is a chip whichever kind it names: an attached picture that opened nothing was
the same defect. Images render in the pane, fitted to it, with a chequerboard
behind transparency. The allowlist is raster-only (PNG/JPEG/WebP/GIF) — SVG is
not an accepted upload, so no previewable image can carry script, and there is
no server-side decode or re-encode anywhere in the path. Anything genuinely
outside the previewable set still reports `unsupported_for_preview` honestly
instead of opening an empty box.

**Deliberately not done.** No zoom, rotate, or pan control on an image, and no
"jump to the passage the model used" in a document. Both are features on top of
this endpoint rather than parts of the defect.

Covered by `tests/test_attachment_preview.py`,
`tests/test_document_attachments.py`, `tests/test_over_broad_redaction.py`,
`apps/web/src/lib/components/FileInspector.test.ts`, and the file-inspector
cases in `apps/web/src/lib/views/ChatView.test.ts`.

---

## FIXED-11 — Redaction destroyed every server-issued path and URL

**Status: fixed in this change.** Found while fixing BUG-07; not caused by it.

**Observed.** The file inspector's PDF pane was blank. `GET
…/attachments/{id}/preview` returned:

> `"pdf_url": "/[REDACTED_SECRET]"`

so the browser had nothing to point its viewer at. Chasing it showed the field
was not special:

| Field | What the client received |
|---|---|
| `pdf_url` | `/[REDACTED_SECRET]` |
| `events_path` | `/home/user/.[REDACTED_SECRET].jsonl` |
| `checkpoint_path` | `.[REDACTED_SECRET].json` |
| `root_subpath` | `[REDACTED_SECRET]` |

**Root cause.** `raiker/context/redaction.py` ends with a high-entropy fallback,
`\b[A-Za-z0-9+/_\-]{40,}\b`, for long opaque strings. `/` is in that character
class, so a path matches as *one token* purely because its segments were joined:
`sessions/sess_…/attachments/att_…/preview/pdf` carries no 40-character run of
entropy anywhere, but the whole thing is 100+ characters. Every locator the API
emits was long enough to trip it. This is the third instance of the same family
— FIXED-02 (token *counts* read as credentials) and FIXED-07 (prose read as
credentials) — and it has the same shape: a rule that is right for opaque values
applied to a value that is not opaque.

**Fix applied.** The field's **key** decides, exactly as it does for token counts
in FIXED-02: `raiker/api/redaction.py` marks values under `*_url`, `*_uri`,
`*_path`, `*_subpath` (and their plurals) as locators, and only those are scanned
with a fallback that spares a run whose *every* slash-separated segment is itself
under the entropy threshold. Nothing else changes:

* A credential embedded in a path is its own over-length segment and still
  redacts (`…/f/AAAABBBB…44 chars` → `[REDACTED_SECRET]`).
* Every specific shape — `sk-…`, `ghp_…`, `Bearer …`, `token=…`, PEM blocks,
  emails — is matched *before* the fallback and applies to locators unchanged.
* A key that names a credential still wins: `secret_url` is discarded whole.
* Free-form text is untouched and keeps the strict scan. A path quoted inside an
  assistant reply is still scanned as prose, because there the string is
  untrusted model output rather than something the server issued.

`assert_no_secrets_in_body` mirrors the same rule, so the guard still proves
exactly what the middleware emits.

**Why not a value-shape rule.** The first attempt spared any run starting
`api/`. It fixed the one symptom and left `events_path`, `checkpoint_path` and
`root_subpath` broken — and it relaxed the rule for *all* strings, including
model output. Keying on the field name is both narrower (prose is unaffected)
and complete (every locator field is covered). A purely shape-based rule was
rejected outright: a base64 secret containing `/` would split into two
under-threshold halves and slip through.

Covered by `tests/test_over_broad_redaction.py::TestServerIssuedLocatorsSurvive`
and verified over real HTTP through the full middleware stack.

---

## FIXED-12 — Chat transcript export path *(was BUG-08; superseded by FIXED-19)*

**Status: superseded by FIXED-19.**

**Observed.** Swept every `button`/`a` in the app for `pdf|export|download|save
as|print`. The only match anywhere is Memory's JSON import/export. There is no
way to get a chat, a document, or a generated artifact out of Raiker as a file.

**Original fix.** Every completed Raiker message received a **Copy response**
action and the chat toolbar exported the transcript as Markdown or through the
browser print dialog.

**Current behaviour.** FIXED-19 removes transcript downloads and transcript
printing: a conversation is not a generated file. **Copy response** remains.
Supported files created by a chat turn, along with stored session attachments,
are represented by a session-authorized chip and open in the right-hand
inspector. There is deliberately no general workspace-file browser or download
surface.

**Follow-ups applied while verifying this entry.** Three gaps between what the
controls did and what they reported:

* **Copy failed silently.** `navigator.clipboard.writeText` was awaited with no
  `catch`, so an insecure origin or a denied permission produced an unhandled
  rejection and no message at all. It is now caught and reported.
* **A successful copy was invisible.** The only confirmation was an `sr-only`
  live region, so a sighted owner clicking **Copy response** saw nothing happen.
  The notice is now visible ("Response copied.", "Downloaded raiker-chat-….md")
  and still announced.
* **The download raced its own object URL.** The anchor was never attached to the
  document and `URL.revokeObjectURL` ran in the same tick as `click()` — a
  download some browsers drop. The anchor is now attached, clicked, removed, and
  the URL released afterwards.

**Historical coverage.** The obsolete transcript serializer and its tests were
removed. `ChatView.test.ts` now covers the absence of transcript exports and a
generated file opening in the right-hand inspector.

---

## FIXED-13 — A background-agent run reported `Task failed` with no user-facing reason *(was BUG-09)*

**Status: fixed in this change.**

**Observed.** The "Manual test Background agent" task produced a real response
and a checkpoint, then the audit log recorded `Task failed` (`task_manager`).
Tasks still showed the task as `queued`; nothing in the UI said what failed or
why.

**Root cause.** Three separate defects stacked into one unreadable outcome.

1. `raiker/tasks/scheduler.py` treated **every** non-`completed` turn status as a
   failure. A governed turn ends on one of four statuses, and two of them are not
   failures: `needs_approval` means the run reached an approval boundary and
   stopped there — exactly what a governed run is supposed to do — and `denied`
   means policy refused one action. A run parked on the owner's own decision was
   recorded as `failed`.
2. The reason was whatever the turn's message happened to be, truncated to 500
   characters and never checked. An empty message produced a `task_failed` event
   with `reason: ""` and a task row whose `summary` was blank.
3. Nothing rendered the reason even when one existed. `TasksView` showed a status
   badge, the objective, and a timestamp; the finished list showed title, badge,
   time. Work in action filtered tasks down to `queued`/`running`/`paused`, so a
   finished run vanished from the page rather than reporting how it ended, and a
   task's `detail` was its `current_step` — the step the run last reached, not
   what ended it.

The `queued` reading was the same page never refreshing: the list loaded on mount
and on a project change only, while the run was claimed, executed, and closed by
the resident scheduler outside it.

**Fix applied.**

*A run's outcome is classified, not assumed.* `run_outcome()` maps each terminal
turn status onto a task status and a stated summary: `completed` → `completed`,
`needs_approval` → `waiting_for_approval` (a contract status that existed and was
never used), `denied`/`failed` → `failed`. An unrecognised status fails closed
**and** names itself rather than recording a state the owner cannot account for.

*A terminal task always carries a reason.* `TaskManager.fail_task` and
`cancel_task` substitute a stated reason when the caller passes a blank one, so
neither the audit event nor the card can end up empty. `block_task_on_approval`
parks a blocked run without stamping `completed_at` — the work is unfinished —
and emits the new `task_blocked` event, which is distinct from `task_failed`
precisely because nothing went wrong. A recurring cadence keeps its slot whatever
one cycle did, so a cycle that did not complete now says so in the summary
instead of reading like a success.

*The reason is visible in both surfaces.* Tasks shows the outcome line on the
card and in the (now correctly named) **Finished work** list, reads
`waiting for approval` as English rather than a snake_case identifier, keeps a
blocked run in the open list where it can be reviewed or stopped, and refreshes
on a 15-second interval so a run that ends elsewhere stops reading as `queued`.
Work in action keeps blocked runs among live work, adds **How the last runs
ended**, and reports a terminal task's outcome instead of its stale step.
"Stop everything" reaches a blocked task too (`_ACTIVE_TASK_STATES`).

Covered by `tests/test_task_scheduler.py`, `tests/test_phase_2_task_manager.py`,
`tests/test_api_dashboard.py`, `apps/web/src/lib/statusMaps.test.ts`,
`apps/web/src/lib/views/TasksView.test.ts`, and
`apps/web/src/lib/views/WorkInActionView.test.ts`.

**Deliberately not done.** Resolving the approval that blocks a scheduled run
still does not resume that run: the resume relay (FIXED-09) is driven by the
client that submitted the turn, and a scheduler-launched turn has no client
watching it. The task stays `waiting_for_approval` with its reason on the card
and can be stopped from there. Auto-resuming scheduled work after an approval is
a feature on top of this defect, not part of it.

---

## FIXED-14 — Redaction destroyed every server-issued record id

**Status: fixed in this change.** Found while verifying FIXED-13 against a live
`raiker-web`; not caused by it.

**Observed.** With the task fixes in place, `GET /api/tasks` returned:

> `"session_id": "[REDACTED_SECRET]"`

for every task, and `GET /api/sessions` did the same for the Inbox session. The
task cards rendered correctly, but every control that carries the id was broken:
**Stop** posted `session_id: "[REDACTED_SECRET]"` (`interrupt_target_not_found`),
the blocked-task pointer linked to `#/approvals?session=[REDACTED_SECRET]`, the
session was unopenable from Sessions, and the approval match — `task.session_id
=== approval.session_id` — compared one redaction marker against another.

**Root cause.** The fourth instance of the family behind FIXED-02, FIXED-07 and
FIXED-11: the high-entropy fallback matching a value that is long without being
opaque. A server-issued id is long because its *prefixes* were joined —
`sess_inbox_principal_user_<16 hex>` is 42 characters and carries no 40-character
run of entropy anywhere. Short ids (`sess_<16 hex>`, 21 characters) stayed under
the threshold, which is why this only appeared for accounts created through
registration: their principal id is what makes the Inbox session id long enough,
and the Inbox session is where every task lives.

**Fix applied.** The field's **key** decides, exactly as it does for locators in
FIXED-11. `raiker/api/redaction.py` marks values under `*_id`/`*_ids` as record
identifiers, and only those get a fallback that spares a token matching the
server-issued id shape — lowercase, underscore-joined, alphanumeric segments.
Nothing else changes:

* The exemption is a *shape*, not a blanket pass for `*_id`. A mixed-case token,
  base64 with padding, or a dash-separated opaque value under an id key still
  redacts.
* A key that names a credential still wins: `token_id` is discarded whole.
* Free-form text is untouched and keeps the strict scan, so the same string
  quoted in an assistant reply is still scanned as prose.

`assert_no_secrets_in_body` mirrors the rule, so the guard still proves exactly
what the middleware emits. Covered by
`tests/test_over_broad_redaction.py::TestServerIssuedIdentifiersSurvive` and
verified over real HTTP against a running `raiker-web`.

---

## FIXED-15 — Task runs polluted RECENT CHATS *(was BUG-10)*

**Status: fixed in this change.**

**Observed.** After creating tasks, an entry titled **Inbox** appeared in the
sidebar's RECENT CHATS beside real conversations, and task-run sessions appear in
Sessions with the task's prompt as the title.

**Root cause.** A task runs as a real governed turn, and a governed turn needs a
session, so `create_task` creates a server-owned `sess_inbox_<principal>` row.
Nothing recorded that this session came from anywhere different, so every list
of sessions — the sidebar's recent chats, and the Workbench's "Resume a
conversation" — treated it as a conversation the owner had.

**Fix applied.** Sessions carry an `origin` column: `chat` for a conversation
the owner typed, `task` for the session a task run executes in. It is
provenance and nothing else — it grants nothing, hides nothing, and changes no
gate, policy, or ownership. `GET /api/sessions?origin=chat` narrows the list,
and the two surfaces that mean *conversations* ask for that; Sessions still
lists everything, and a task session stays reachable from Tasks.

Creating a task also re-stamps an Inbox that predates the column, so a workspace
that already had one stops reading as a chat rather than needing a reset.

Covered by `tests/test_session_origin.py` and the sidebar case in
`apps/web/src/lib/components/Sidebar.test.ts`.

---

## FIXED-16 — A surface blocked by runtime mode did not say so *(was BUG-11)*

**Status: fixed in this change.**

**Observed.** With `mcp_builder_runtime` and `mcp_connector_runtime` set to
`enabled_policy_gated`, the MCP tab still said *"The MCP builder and connector
capabilities are disabled. Enable them in Capabilities to create or test
servers."* — but they **were** enabled in Capabilities. The real blocker was that
`runtime_enabled` requires `enabled_runtime`, which requires a runtime-enablement
mode (Settings → Runtime mode). Following the message's own advice does not
resolve it.

**Root cause.** Every consumer read one boolean, `runtime_enabled`, and rendered
one sentence for everything it could mean. A `runtime_enabled` surface is shut
in four distinguishable ways, and they need different actions: the capability
has no executor in this runtime (nothing to do), the gate is off (turn it on),
the gate is on but below runtime level (activate a runtime mode), or the
decision mode is `deny` (change the mode). Collapsing them sent the owner to a
page where the capability already read as enabled.

**Fix applied.** `runtimeBlock(gate, label)` in
`apps/web/src/lib/capabilityModel.ts` classifies the four cases and returns the
reason, the one action that resolves it, and where that action lives. A gate
that could not be read is treated as shut, never as open. MCP renders one notice
per blocked capability from it.

The same distinction is now made server-side for the Extensions hub, where a
connector below runtime level reported `capability_gate_closed` ("its capability
gate is closed") with the identical problem: `_connector_block_reason` returns
`capability_below_runtime_level` and `capability_decision_mode_deny` as separate
reasons, and each has its own copy.

Covered by the `runtimeBlock` cases in
`apps/web/src/lib/capabilityModel.test.ts`, the blocked-banner cases in
`apps/web/src/lib/views/McpView.test.ts`, and
`tests/test_api_web_read_models.py::TestBlockedReasonNamesTheRealBlocker`.

---

## FIXED-17 — MCP servers could not be used by the agent *(was BUG-12)*

**Status: fixed in this change.**

**Observed.** Created and connected a governed local MCP server from the Sample
echo template; **Test** reported `connected · 2 tool(s)` (`echo`,
`workspace_ping`) and recorded a monitored session. The model could never call
them: `raiker/models/tool_call_validation.py::_MODEL_EXPOSED_TOOLS` was a fixed
frozenset, and there was no `mcp` reference anywhere in
`raiker/runtime/orchestrator.py`, `raiker/tools/broker.py`, or
`tool_call_validation.py`. MCP was a management/monitoring surface only, while
a user who follows the UI to connect a server reasonably expects its tools in
Chat.

**Fix applied.** Each tool a connected server advertised becomes one
model-callable tool named `mcp__<server>__<tool>`
(`raiker/tools/mcp_tools.py`). Four seams:

* **Discovery** — the orchestrator recomputes the turn's tool specification, so
  a server connected, paused, or killed between turns is reflected immediately.
  Fail-closed: a disabled `mcp_connector_runtime` gate, a server that never
  completed a handshake, and a contained connection all contribute nothing, so
  the model is never offered a tool the runtime would refuse.
* **Validation** — `validate_tool_call` recognises a projected tool by *shape*
  and stays store-free. Whether that server and tool exist is answered at
  execution, with a stated reason.
* **Governance** — execution goes through `ToolBroker` unchanged (hooks, the
  policy engine, the approval flow, the audit events, the stored tool-action
  record). On top of that the tool enforces the capability gate, the decision
  mode (**default `ask` withholds**, exactly like the GitHub/Gmail connectors —
  reaching a registered server runs code Raiker does not own), containment, and
  the server's own advertised tool list. The session monitor still records
  redacted telemetry and can still trip an anomaly rule.
* **Results** — the tool's text reaches the calling model framed as untrusted
  data, never instructions, and reaches nothing else. The executor takes an
  in-process `content_sink`; artifacts, the `action_executed` event, the broker
  events, and the session log keep carrying counts and labels only. Broker
  events also drop the *argument values* (they are opaque values composed for
  an outside program, not governance-relevant identifiers like a repo and
  number), and the result is bounded to 20 000 characters.

Two deliberate narrowings. A server whose own name contains the `__` separator
is not projected at all, because `mcp__a__b__c` would otherwise be ambiguous
between two servers; and the policy layer treats a projected call as
read-shaped (like `connector_read`), because what actually governs it is
enforced inside the tool.

Covered by `tests/test_mcp_agent_tools.py` (30 cases: naming, validation,
fail-closed discovery, every decision mode, an end-to-end call against the real
echo template, and the audit-trail exclusions).

**Found while verifying this live: calling a tool erased the server's tool
list.** `_record_connection` refreshes a profile's runtime fields after every
session, and a `tools/call` session passed `tools or []` — an empty list, not
"nothing discovered". The connected server then read `TOOLS (0)` in the UI, and
the projection, which is built from exactly that list, went silent from the
second turn onward. `update_mcp_server_runtime` now treats `tools=None` as "this
operation enumerated nothing" and leaves the stored list alone (`COALESCE`);
only an enumerating session rewrites it. The defect predates this change — any
`mcp_call_tool` emptied the profile — but the projection is what made it fatal
rather than cosmetic.

**Threat model updated.** `docs/threat-models/mcp-connector.md` no longer claims
tool output is redacted in every direction — it now states exactly where the
content goes and where it does not.

---

## FIXED-18 — "Confirmation token" is explained in the step-up dialog *(was BUG-13)*

**Status: fixed in this change.**

**Observed.** Enabling a tier-2 capability requires a *"Confirmation token
(required to enable this capability)"* with no hint about where to obtain one.
The backend
(`raiker/runtime/authority/activation.py`) only checks that the field is
non-empty — it is a deliberate human-intent speed bump, not a secret. A user is
likely to stop here believing they lack a credential they never had.

**Fix applied.** The Tier-2 step-up now says: *"Type any phrase to confirm you
intend this change. It is recorded with your decision."* The README describes
the same value as an intent-recording phrase, not a credential. The backend
continues to enforce the non-empty confirmation requirement.

---

## FIXED-19 — Chat transcripts were offered as files even when no file existed

**Status: fixed in this change.**

**Observed.** Chat showed **Export as Markdown** and **Print / Save as PDF** for
every transcript. Those controls exported a conversation rather than a file
Raiker had created or stored, while a supported file written by a chat turn had
no inspector chip despite the existing right-hand preview surface.

**Fix applied.** Transcript-level export and print controls are removed. A new,
supported file created by a governed chat turn is validated, copied into the
owner-scoped attachment store, and bound to that exact session and turn. The
chat refreshes its file chips after the final event; selecting a chip opens the
existing read-only right-hand inspector. This is limited to new supported
document/image types and never turns the workspace into a general file browser.

**Post-release correction.** The initial recorder only ran when a prompt stream
finished. Approved writes execute after that event, under the approving API
session, so their otherwise valid file could be omitted from the conversation.
FIXED-20 closes that lifecycle gap.

---

## FIXED-20 — Approved Chat and Build files could be lost from their session

**Status: fixed in this change.**

**Observed.** A Chat or Build turn can propose a new file, pause for the
owner's approval, then write it successfully. The workspace file existed, but
reloading the conversation showed no file chip and the inspector could not
recover it. That broke the requirement that an agent-created artifact remains
part of the session until the owner deletes it.

**Root cause.** The generated-file recorder ran only at a prompt stream's final
event. Approval resolution is later and runs with the approving API session,
not the originating conversation session. The checkpoint capture preserves the
original turn id, but the recorder queried it by the wrong session id and found
no file to store.

**Fix applied.** The attachment recorder now has a turn-scoped entry point and
approval resolution calls it immediately after a successful file write. Capture
lookup uses the original turn id, the stable link across the approval relay,
then copies supported new documents and images into the owner-scoped attachment
store and records their original session and turn. The final-stream path remains
as an idempotent safety net. No automatic deletion path was added: stored
artifacts remain until the owner explicitly deletes them.

**Covered by.**
`tests/test_approval_execution_wiring.py::TestApprovedWriteExecutes::test_new_file_is_copied_into_the_session_after_approval`
approves a new Markdown file and asserts that a fresh session-file listing
contains its stored record, name, type, and originating turn.

---

## FIXED-21 — CI validation had stale import and typing debt

**Status: fixed in this change.**

**Observed.** The final CI-equivalent checks did not start clean: Ruff reported
unsorted imports in the generated-file route and attachment-preview test, while
mypy rejected the preview test's deliberately minimal envelope fixture.

**Fix applied.** Imports now follow the repository's Ruff ordering. The preview
test explicitly casts its two-field fixture to the envelope type expected by
the existing helper, documenting that the test supplies only the fields its
runtime path reads. Ruff and mypy now complete without findings.

---

## FIXED-22 — Repeated file recording could duplicate a session artifact

**Status: fixed in this change.**

**Observed.** An approved write is recorded when it executes and may be seen
again by the prompt's final stream event. The recorder created a fresh
attachment for each pass, so one generated file could appear as duplicate chips
in its session.

**Fix applied.** The recorder now identifies an already-recorded artifact by
its originating turn, filename, and content checksum before storing it. The
approval and final-stream lifecycle paths can both run without changing the
session's one-file record. This preserves the owner-only deletion model; it
does not remove existing artifacts automatically.

**Covered by.**
`tests/test_approval_execution_wiring.py::TestApprovedWriteExecutes::test_new_file_is_copied_into_the_session_after_approval`
records the same approval turn twice and asserts the session still contains one
file.

---

## FIXED-23 — Build's edit and patch tools overwrote whole files *(was GAP-BUILD B3)*

**Status: fixed in this change.**

**Observed.** `edit_file` forwarded its replacement text to a whole-file writer,
and `apply_patch` accepted a `patch` proposal but the executor wrote a separate
`new_text` field over the complete target. A one-line Build change therefore
required reproducing the full file; an old or ambiguous target could silently
delete unrelated content.

**Root cause.** The proposal, preview, and execution contracts had drifted:
the model validator and broker spoke in terms of a patch, while the executor
implemented overwrite semantics. No shared candidate calculation connected the
owner-reviewed diff to the bytes written at approval time.

**Fix applied.** `raiker/tools/filesystem.py` now calculates each candidate
before mutation. `edit_file` requires `{path, old_text, new_text}` and replaces
only one exact match. `apply_patch` requires `{path, patch}` and parses one
unified diff for the named workspace-relative text file. Every hunk's context
and removed lines must match exactly once in the accumulating candidate; a
missing or ambiguous match returns `hunk_context_mismatch` or
`hunk_context_not_unique` plus `rejected_hunks`, with no write. All hunks must
match before the file changes.

The broker, approval detail, and executor use those same candidate helpers, so
the detail renders the calculated diff the approval will execute. The existing
writable-workspace guard, `.raiker` / `.git` refusal, re-governance, audit, and
pre-image checkpoint all remain in force.

**Verified.** `tests/test_filesystem_tools.py` covers one exact replacement,
zero/multiple-match refusal, matching and ambiguous hunk contexts, and a second
failed hunk leaving the first hunk unapplied. The broker, approval API, and
relay suites cover the new tool contracts, calculated preview, and both
approved execution paths. Live Chromium verification on 2026-07-27 reviewed
and approved an exact edit (`old` → `edited`) then a unified patch
(`edited` → `patched`) on the same file. Each approval displayed the calculated
diff and **Approve and execute once**, reported a checkpointed execution, and
wrote only the intended line. Browser console: 0 errors. Evidence:
`screenshots/working/98-FIXED-23-b3-edit-ready.png` through
`101-FIXED-23-b3-patch-executed.png`.

**Subsequent expansion.** FIXED-29 added coordinate-guided context offsets,
empty-context insertion hunks, file create/delete headers, and no-newline
markers without weakening all-or-nothing execution. Atomic multi-file diffs
remain deferred because approvals and checkpoints currently govern one path.

---

## FIXED-24 — README known limits described already-shipped behaviour as missing

**Status: fixed in this change.**

**Observed.** During B3 verification, `README.md` still said Markdown rendering,
agent-reachable MCP tools, and the view-only file inspector were unshipped,
although FIXED-06, FIXED-10, FIXED-17, and the live manual plan document each
proved otherwise.

**Fix applied.** The known-limits list now names only current limitations,
including B3's intentionally strict patch scope. Documentation no longer sends
an owner away from behaviour the running product already provides.

---

## FIXED-25 — Local repository references used host-native separators

**Status: fixed in this change.**

**Observed.** On Windows, connecting `projects/my-app` through Build returned
and stored `projects\\my-app`, although the API contract and all browser-facing
workspace coordinates use slash-delimited paths. The full Python suite exposed
this through `tests/test_build_workspace.py`.

**Root cause.** `DashboardService._workspace_source` converted a relative
`Path` with `str(...)`, which serialises using the host platform's separator.

**Fix applied.** The workspace boundary now uses `Path.as_posix()` before the
value enters repository records, audit events, or API responses. Filesystem
resolution remains native-path safe; only the public, persisted coordinate is
normalised.

---

## FIXED-26 — The cost-popover test asserts a different currency label than the UI *(was BUG-14)*

**Status: fixed in this change.**

**Observed.** `apps/web/src/lib/components/ContextMeterPopover.test.ts` expects
`$0.0030`, while the rendered component displays `US$0.0030`. The full web test
run therefore has one failure even though the focused BUG-13/FIXED-19 tests,
type check, lint, and build pass.

**Reproduction.** Run `npm --prefix apps/web run test --
ContextMeterPopover.test.ts` on a runner whose default locale does not render
USD as a bare dollar sign.

**Root cause.** The component receives a locale from its caller, but this test
relied on the test runner's implicit locale. Its expected label therefore did
not describe the UI invocation it was meant to cover.

**Fix applied.** Currency remains locale-aware. The component test now passes
`en-GB` explicitly and asserts the rendered `US$` label; the formatter's
separate `en-US` tests retain the `$` convention. The test no longer depends on
the runner's locale.

**Verification.** `npm.cmd --prefix apps/web run test --
ContextMeterPopover.test.ts` passed all 7 tests on 2026-07-28.

---

## FIXED-27 — GitHub Actions declared the deprecated Node 20 runtime *(was BUG-15)*

**Status: fixed in this change.**

**Observed.** The successful GitHub CI run for FIXED-23 reported that
`actions/checkout@v4` and `actions/setup-python@v5` target Node 20, which
GitHub now forces to Node 24. The workflow passed, but future runner behaviour
is relying on a compatibility override rather than its declared runtime.

**Root cause.** The action pins predate the upstream releases that changed the
actions' JavaScript runtime to Node 24. SHA pinning preserved supply-chain
immutability but also preserved the obsolete runtime declaration.

**Fix applied.** Every workflow now uses immutable, upstream release commits
whose declared runtime is Node 24: `actions/checkout` v5.0.1,
`actions/setup-python` v6.2.0, and `actions/setup-node` v5.0.0. This includes
the licensing workflow, which was already SHA-pinned but still pointed at
Node-20-era releases. The web workflow now tests the supported Node 22 runtime
once; the former Node 20 matrix leg duplicated the same lint, type-check, unit,
and build work without exercising a different product contract.

**Verification.** A repository-wide workflow scan finds no Node-20-era action
pins. The latest pre-change `main` workflows were checked before commit; the
post-push run for this commit is recorded in the handoff after push.

---

## FIXED-28 — Web validation emitted repeated Node localStorage warnings *(was BUG-16)*

**Status: fixed in this change.** Found while validating FIXED-27; it is
unrelated to the workflow action upgrade.

**Observed.** `npm --prefix apps/web run test` passes all 443 tests and the
subsequent production build succeeds, but Node 25.6.1 prints repeated warnings:
`--localstorage-file was provided without a valid path`. The warning repeats
for the Vitest worker processes, making an otherwise green local validation log
noisy.

**Root cause.** Node 25 exposes an experimental process-global Web Storage API.
Vitest enumerates globals in its workers before jsdom installs browser Storage,
which accesses Node's unconfigured `localStorage` getter. The setup fallback ran
too late and treated symptoms rather than controlling the worker runtime.

**Fix applied.** `apps/web/scripts/run-tests.mjs` feature-detects
`--no-experimental-webstorage`, passes it to Vitest and through `NODE_OPTIONS`
to every worker, and leaves Node 20/22 unchanged. jsdom is again the only
Storage implementation, so the late fallback was removed.

**Verification.** The Storage suite passed without warnings on Node 24.14.0
and the exact reported Node 25.6.1 runtime.

---

## FIXED-29 — B3 single-target patches rejected common unified-diff forms

**Status: fixed in this change.**

**Observed.** Build safely updated one existing file but rejected hunk offsets,
zero-context insertions, file create/delete headers, and the standard
no-final-newline marker — ordinary forms emitted by class-leading coding agents.

**Root cause.** The parser discarded hunk coordinates and required an old line.
Its candidate and writer contracts assumed the target already existed and would
still exist after execution.

**Fix applied.** Candidates now carry create/update/delete operations. Hunk
coordinates choose the nearest matching context and fail closed on an
equal-distance ambiguity; insertions use their declared position; `/dev/null`
headers create or delete the workspace file; newline markers preserve bytes.
Proposal and execution still calculate the same all-or-nothing candidate.

**Verification.** `tests/test_filesystem_tools.py` covers offsets, insertion,
create, delete, newline markers, stale context, and no partial writes.

**Deliberate remaining scope.** One `apply_patch` approval still governs one
checkpointed path. Multi-file diffs remain rejected until checkpointing and
approval previews represent one atomic path set; accepting them through the
single-path contract would make rollback evidence incomplete.

---

## FIXED-30 — Model API keys disappeared after restart

**Status: fixed in this change.**

**Observed.** A provider connection stayed encrypted in SQLite, but a fresh
application process could report it missing or fail to decrypt it unless the
vault-key environment variable was injected again.

**Root cause.** Investigation found no browser-storage dependency: provider
connections are principal-scoped in SQLite and `effective_vault_key()` reads the
workspace key file directly on every decrypt. Loading that file into a global
process environment would be both unnecessary and unsafe across workspaces.
The missing protection was restart-level regression coverage, which allowed UI
symptoms to be mistaken for deliberate secret loss.

**Fix applied.** A restart regression now locks the actual persistence contract:
save an encrypted connection, clear process environment, create a new app on
the same workspace, and decrypt from the workspace key file. Secrets remain
server-side and never enter browser storage. Explicit vault-key removal still
removes access as designed.

**Verification.** A regression saves a connection, clears the process
environment, creates a new app on the same workspace, and confirms that
`GET /api/models` still reports the provider configured.

---

## FIXED-31 — Chat and Build composers lacked a consistent finishing pass

**Status: fixed in this change.**

**Observed.** Chromium review showed Build's prompt well taller than Chat's and
its keyboard hint floating below the card. The primary work surfaces used
different rhythm for the same model, context, approval, and send controls.

**Fix applied.** Both composers now share prompt height, padding, spacing, and
an in-card keyboard-hint footer. Build keeps Plan/Edit/Auto without detaching the
send action. A committed Playwright test covers both accessible surfaces.

**Verification.** `npm --prefix apps/web run test:e2e` passed in Chromium at
1440×1000. Screenshots are `output/playwright/bug15-chat-composer.png` and
`output/playwright/bug15-build-composer.png`.

---

## FIXED-32 — Web development dependencies had known security advisories *(was BUG-17)*

**Status: fixed in this change.** Found while installing Playwright for FIXED-31.

**Observed.** `npm audit --prefix apps/web` reports 10 development-tree
findings: five moderate, four high, and one critical. The critical advisory is
in Vitest's optional UI server; high findings include Vite development-server
path handling and transitive parsing/expansion packages.

**Root cause.** The toolchain remains on the Svelte 5 / Vite 5 / Vitest 2
generation. npm's complete remediation crosses major versions to Vite 8,
Vitest 4, and `@sveltejs/vite-plugin-svelte` 7.

**Fix applied.** Vite moved to 8.1, Vitest to 4.1, the Svelte Vite plugin to 7.2,
and ESLint to 10 with the current Svelte lint plugin. The obsolete Vite HMR
option was removed, and the lockfile was regenerated rather than force-fixed.

**Verification.** `npm audit --prefix apps/web` reports zero vulnerabilities;
Svelte check, lint, component tests, production build, and Chromium Playwright
all pass on the upgraded toolchain.

---

## FIXED-33 — Python tests emitted a Starlette/httpx deprecation warning *(was BUG-18)*

**Status: fixed in this change.** Found while validating FIXED-30.

**Observed.** The persistence regression passes, but importing FastAPI's
`TestClient` emits `StarletteDeprecationWarning`: the installed Starlette build
says its `httpx` integration is deprecated and recommends `httpx2`.

**Root cause.** `pyproject.toml` declares open lower bounds for FastAPI and
httpx, so a fresh development install can select a combination whose test-client
compatibility layer is already deprecated even though it still works.

**Fix applied.** The development extra now installs `httpx2>=2.9`, which the
installed Starlette uses for `TestClient`. Production `httpx` remains because
Raiker's outbound provider and connector clients still use that API.

**Verification.** The focused API, approval, checkpoint, and filesystem suites
run without `StarletteDeprecationWarning`; no warning filter was added.

---

## FIXED-34 — One approval could not govern an atomic multi-file patch *(B3 expansion)*

**Status: fixed in this change.**

**Observed.** A Build turn could create, update, or delete one file per patch,
but a normal agent-generated multi-file diff was rejected. Approval preview and
checkpoint capture described only one path.

**Fix applied.** `apply_patch` now accepts a unified diff containing multiple
file sections with an optional legacy first-path argument. Every target and
hunk is resolved before execution; duplicate targets and stale context fail the
whole proposal. One approval displays the combined diff, execution applies one
change set with rollback on a write failure, and every affected file receives
its own pre-image under the same action id.

**Verification.** Filesystem regressions cover two-file success and rejection
before any write. Approval relay and checkpoint suites confirm the expanded
contract remains reversible.

---

## FIXED-35 — Settings and Models exposed implementation detail and visual noise

**Status: fixed in this change.**

**Fix applied.** Settings now opens with a compact preference overview and a
focused five-section rail; the redundant Storage/Vault page was removed without
removing encrypted credential storage. Models keeps provider-backed selection
but renders human model names instead of internal profile/model identifiers.

**Verification.** Chromium screenshots are
`output/playwright/settings-redesign.png` and
`output/playwright/models-redesign.png` at 1440×1000.

---

## FIXED-36 — Composers had no Raiker-owned English checking path

**Status: fixed in this change.**

**Fix applied.** An optional adapter uses an operator-installed
`language_tool_python` runtime without bundling its GPL-3.0 dependency into the
Apache-2.0 Raiker distribution. Authenticated `POST /api/language/check` runs the
English checker off the event loop, bounds text and execution time, returns
offset/replacement metadata, and never persists prompt text. Chat and Build
also enable native English spelling highlights. Instances without the optional
Java-backed checker return an honest unavailable status instead of blocking a
turn.

---

## FIXED-37 — Connector operations and outbound bodies were invisible *(C2)*

**Status: fixed in this change for the manifest-driven connector path.**

**Fix applied.** Connector Store responses and the management panel publish
the registered operation inventory, including method, path, description, and
whether confirmation is required. Connector-write approval cards now render
the exact structured request arguments after secret-like values are redacted,
labelled by connector and operation. Execution remains single-use through the
existing parked intent and approval relay.

---

## FIXED-38 — Connector manifests can declare bounded operation-scoped compensation *(BUG-19)*

**Status: fixed in this change.** Found while completing C2's visible operation contract.

**Observed.** A connector write can be previewed, approved, and executed once,
but the manifest cannot describe a compensating operation, its argument mapping,
or an upstream undo deadline. The generic standing-grant UI also scopes by
action/domain rather than connector plus operation.

**Fix applied.** OpenAPI operations may now opt into the bounded
`x-raiker-compensation` contract: a manifest-declared target `operationId`, a
string-only argument map (maximum 50 entries), and a deadline from one second to
30 days. Compilation rejects malformed contracts and references to operations
that do not exist. Successful writes return the immutable source invocation id,
the exact compensation operation/map, and an absolute `available_until`; writes
without the extension remain honestly non-undoable. Compensation remains a
governed connector mutation, not a local rollback, and must pass the normal
approval path before execution.

---

## FIXED-43 — Chat creates first-class DOCX, XLSX, PDF, and Markdown artifacts *(C1)*

**Status: fixed in this change.**

**Fix applied.** The model-visible `create_document` contract now creates
macro-free DOCX and XLSX packages, a bounded PDF, or UTF-8 Markdown locally and
atomically without a file-creation approval prompt. Each successful artifact is
stored once and bound to the trusted active session and exact turn as
`source=generated`; neither identity can be supplied by the model. Unsupported
extensions fail closed. Regression coverage creates every supported format,
checks the no-approval policy decision, and verifies the persisted turn binding.

---

## FIXED-44 — Sessions can grant a bounded command feedback channel *(B5)*

**Status: fixed; BUG-20 was subsequently closed by FIXED-47.**

**Fix applied.** An authenticated owner can create, replace, expire, or revoke
one command-prefix allowlist for one session. `run_command` uses the workspace
as its cwd, executes without a shell, requires an exact active session/principal
grant, applies a wall-clock limit and a bounded output limit, and returns exit
code, stdout, stderr, byte counts, and truncation to the agent. Results are
content-free in the event log while normal broker events retain the command
action and outcome. A missing or non-matching grant fails closed and names the
existing approval-gated `shell` tool as the fallback.

---

## FIXED-45 — Generated files have a response-linked preview surface *(C4/C5)*

**Status: fixed in this change; passage highlighting remains tracked below.**

**Validation and fix applied.** Uploaded and generated references are now
distinguished in persistence. Uploaded chips remain buttons in the user turn;
generated artifacts render as prominent cards in the producing assistant turn
with name, type, readiness, creation time, description, and a **Preview
document** button. Both open the existing right-hand, view-only inspector.
Backend coverage verifies account and session authorization, missing and
unsupported states, inert Markdown source for the sanitising renderer, DOCX
text extraction, XLSX table extraction, PDF rendering, exact turn persistence,
and retained stored bytes. Per-response copy remains; chat download, browser
print/Save as PDF actions, and a general artifact download surface remain absent.

---

## FIXED-46 — Workbench is activity-aware and action-oriented

**Status: fixed in this change.**

**Fix applied.** A new account sees “Welcome to your Work Dashboard” and clear
new-chat, project, task, and scheduling actions instead of a false resumption
prompt. Resume copy and conversation rows appear only when named chat activity
exists. Pending approvals, active work, runtime issues, and the runtime record
remain visible as scan-friendly status cards. The responsive browser test and
[`screenshots/working/workbench-dashboard-redesign.png`](screenshots/working/workbench-dashboard-redesign.png)
cover the empty-account state.

---

## FIXED-47 — Owner-granted commands have kernel-enforced network isolation

**Status: fixed in this change (was BUG-20).**

**Observed.** The session grant, executable allowlist, cwd, timeout, output cap,
expiry, and revocation are enforced, but this host cannot create an unprivileged
network namespace (`unshare -n` is denied) and no shipped container executor is
available. A granted interpreter or package-manager command could therefore use
the host network.

**Fix applied.** `run_command` now routes every owner-granted command through a
dedicated Docker boundary with `--network none`, dropped Linux capabilities,
`no-new-privileges`, CPU/memory/PID limits, the invoking uid/gid, and only the
workspace bind-mounted as its working directory. Operators must set
`RAIKER_COMMAND_SANDBOX_IMAGE` to an image also present in
`RAIKER_CONTAINER_IMAGE_ALLOWLIST`; missing configuration, a mismatched image,
or an unavailable Docker runtime fails closed instead of falling back to host
execution. The original exact grant, command allowlist, expiry, timeout, and
bounded feedback checks remain in force.

---

## FIXED-48 — Settings and Workbench distinguish preferences from governed work

**Status: fixed in this change.**

**Fix applied.** Settings now opens with a compact header, grouped icon
navigation, full-width validated language/region/time-zone controls, explicit
discard/save behaviour with an unsaved marker, and a separate Runtime page.
Runtime changes use one review-and-reason workflow, expose change metadata and
history, and place runtime shutdown in a dedicated danger zone.

The Workbench now makes its governed composer the primary action, provides
Chat/Run work/Create task/Schedule modes, exposes a real configured-model
selector, and keeps the primary action disabled with a local remediation when
no model is available. Returning users see activity-aware copy and a Continue
working list; the right rail is a role-appropriate Needs your attention area,
and refresh reports its freshness without discarding composer state.
Live browser coverage is recorded in
[`screenshots/working/workbench-dashboard-live.png`](screenshots/working/workbench-dashboard-live.png),
[`screenshots/working/settings-redesign-live.png`](screenshots/working/settings-redesign-live.png),
and [`screenshots/working/settings-runtime-live.png`](screenshots/working/settings-runtime-live.png).

---

## FIXED-49 — Memory, Knowledge Map, and context usage expose user controls first

**Status: fixed in this change; missing lifecycle services are tracked as
BUG-21 and BUG-27 through BUG-30.**

**Fix applied.** Memory now leads with one accessible incognito switch, quiet
approved/pending/pinned/expired counts, search and governed metadata filters,
readable approved and pending cards, explicit forget copy, and file-based
reviewed import/export under **Advanced memory management**. Raw JSON and
internal identifiers no longer dominate the page.

Brain is presented as **Knowledge Map** and explicitly states that it does not
show hidden reasoning. Sources, approved memories, and runtime records are
defined separately; the page has a workspace summary, source-boundary copy,
search, type filtering, Map/List views, a useful empty state, an animation
switch with reduced-motion support, a legend, and a more informative record
inspector.

The context popover makes exact tokens used, capacity, remaining tokens, and
input/output composition primary. It uses a visible 8px severity-aware meter,
honest sub-one-percent display, concise provider attribution with explanatory
help, and a visually separate pricing footer with a direct **Configure →**
action.
Live browser evidence is recorded in
[`screenshots/working/memory-redesign-live.png`](screenshots/working/memory-redesign-live.png),
[`screenshots/working/knowledge-map-redesign-live.png`](screenshots/working/knowledge-map-redesign-live.png),
and [`screenshots/working/context-window-redesign-live.png`](screenshots/working/context-window-redesign-live.png).

---

## FIXED-50 — Local model context capacity is discovered from the active runtime

**Status: fixed in this change; scheduled refresh and administrator overrides
are tracked as BUG-33.**

**Root cause.** Local OpenAI-compatible catalogues were treated like hosted
catalogues and only the top-level `context_length` field was recognised. The
shipped Ollama, LM Studio, and llama.cpp profiles do not declare one universal
capacity because the effective value belongs to the selected model and running
server configuration. As a result, local work often displayed **Context
capacity is not configured** even while the runtime knew its limit.

**Fix applied.** An explicit provider-catalogue refresh now performs bounded,
best-effort reads against the same policy-checked local origin:

- Ollama reads the active `context_length` from `/api/ps`, then uses `/api/show`
  model metadata or an explicit `num_ctx` parameter for models that are not
  loaded.
- LM Studio reads its runtime `/api/v1/models` catalogue and recognises common
  direct and loaded-instance context fields.
- llama.cpp reads the server `/props` generation settings, including `n_ctx`.

Positive capacities are cached against the exact owner, provider, and model;
provider facts continue to outrank a profile's exact
`context_window_tokens` fallback. Supplementary metadata failures never hide a
valid model catalogue or invent a capacity. The Models details dialog shows the
exact capacity and whether it came from the runtime or Raiker configuration.
Chat and Build show used, available, and remaining tokens, visibly label
**Capacity reported by runtime**, and state **Runs on this machine — no API
cost** for local execution. Pricing remains independent from context capacity.

Live browser evidence is recorded in
[`screenshots/working/local-context-window-live.png`](screenshots/working/local-context-window-live.png).

---

## FIXED-51 — Force simulation rebuilt itself on every animation tick

**Status: fixed in this change; found during live Playwright verification.**

**Observed.** The first production-browser run remained on **Loading the
knowledge graph…** after the API returned. Type-check, lint, and production
build all passed because the defect was a reactive runtime feedback loop.

**Root cause.** The Svelte effect that constructed the D3 simulation read
`renderedNodes` to preserve positions. Every D3 tick then assigned
`renderedNodes`, invalidated the effect, stopped the simulation, and constructed
another simulation indefinitely.

**Fix.** Node positions now live in a non-reactive keyed cache. Simulation ticks
copy positions only into render state, so data/filter/force changes rebuild the
simulation while ordinary ticks do not. The real FastAPI-served SPA now passes
the Playwright route, interaction, and screenshot review.

---

## FIXED-52 — Knowledge Map initially bypassed Raiker's shared theme

**Status: fixed in this change; found during visual review.**

**Observed.** The first force-graph implementation hard-coded a dark palette
across the whole Knowledge Map. It behaved like the requested graph view but
did not feel like the light Raiker application shown in the baseline, and a
single hard-coded replacement would have made the route ignore dark mode.

**Fix.** The canvas, toolbar, overlays, inspector, source dialog, viewport
controls, and settings panel now use Raiker's light visual language by default
and explicit dark-theme overrides based on the shared design tokens. A new
Playwright sweep visits all 23 application pages and hub tabs in both explicit
themes, asserts different resolved token palettes, and reports zero console or
page errors.

---

## FIXED-53 — Provider pricing is synchronised into a historical registry

**Status: fixed in this change (was BUG-21).**

**Root cause.** A price was stored as a *current value*: whatever the shipped
profile said, or whatever the last catalogue listing cached, overwritten in
place. That cannot answer the only question a bill ever raises — what a model's
rate was on the day a turn ran — and it cannot show an owner why a number
changed. Cache-write and cache-read were folded into the input rate, which
over-states a cached turn by roughly ten times, and an owner override had no
interface, no attribution, and no reason.

**Fix applied.** A normalised, effective-dated registry
(`raiker/models/price_registry.py`, table `model_price_registry`) holds one
append-only row per owner, provider, **exact** model id, source, and
effective-from date. `content_hash` covers every rate component, so a refresh
that observes unchanged rates writes nothing — history records changes, not
polls. Input, output, cache-write, and cache-read are four independent columns;
a component nobody published stays `None` rather than being inferred from
another. A sibling model never inherits a rate.

A bounded synchronisation job (`raiker/models/price_sync.py`, table
`model_price_sync_state`) refreshes no more often than every 6 hours and no
less often than every 24, clamping any out-of-range cadence rather than
refusing it. A failed refresh moves only the attempt clock: the last known good
response, its success timestamp, and the rate itself are all retained, and the
provider is marked stale with its reason. Two feeds exist and no others — a
provider's own catalogue (the same user-initiated listing the Models page
already triggers) and a reviewed documentation adapter that reads the `pricing`
block a human committed to `model-profiles.json`. Nothing is scraped at render
time.

An override is administrator work: it requires the runtime gate-manager role,
carries a mandatory reason, records `recorded_by` in the registry, and writes
`model_price_override_recorded` / `model_price_override_cleared` to the governed
event log. Clearing it returns the model to its published or documented rate
with that history intact.

**UI.** The Models page is split by action category — **Providers**, **Routing**,
**Pricing**, **Posture** — so looking up a rate is its own errand rather than a
scroll past provider cards, and each panel is a shareable location
(`#/models?tab=pricing`, which is exactly where the popover's **Configure →**
now lands). Models → **Pricing** states, per exact model id: the source
(administrator override / published by the provider / reviewed documentation),
each of the four rate components, the effective date, and the full price
history. Each provider shows its last refresh, next due time, cadence, and a
**Current**/**Stale** badge, with the failure reason and an explicit note that
the previous rates remain in effect. The override form is offered only to a
gate-manager; everyone else sees the registry read-only.

The context popover in both Chat and Build reads the registry, lists the rate
components it actually has, and shows **Unknown** with **Configure →** whenever
a billable model has no exact rate — including before the first turn, where the
previous rule stayed silent and therefore read as "free".

Live browser evidence:
[`screenshots/working/120-BUG-21-pricing-registry-live.png`](screenshots/working/120-BUG-21-pricing-registry-live.png)
and [`screenshots/working/121-BUG-21-context-price-unknown-live.png`](screenshots/working/121-BUG-21-context-price-unknown-live.png).

---

## FIXED-54 — Chat and Build export a transcript, and print as a document

**Status: fixed in this change (was BUG-22).**

**Root cause.** Rendered transcript HTML existed, but nothing turned a
conversation into a file the owner keeps. Printing produced a photograph of the
application chrome rather than a document.

**Fix applied.** `raiker/sessions/transcript.py` builds a redacted, scoped
transcript and renders it three ways. Scope is the session and only the session:
the build reads through the existing `get_session` visibility boundary, so an
export can never reach a conversation the caller could not already open. Message
text passes through the same secret-shaped-value redactor the API responses use
*before* any rendering, so a key pasted into a chat cannot leave inside an
export. Attached files are listed by name, media type, and size; their bytes are
never embedded.

HTML is one self-contained page — inline styles, no script, no remote asset, so
it renders offline and cannot call out. PDF is written by a small dependency-free
generator using the base-14 fonts every reader ships, so producing one opens no
process, loads no font file, and reaches no network. Markdown is plain text.
`POST /api/sessions/{id}/export` is exempted from the JSON redaction middleware
for the same reason the project export is — the payload is a document, not JSON —
and every successful export writes `session_transcript_exported` to the event
log carrying counts and the policy, never the transcript.

**UI.** The conversation menu in **both Chat and Build** contains **Export
conversation…**, which opens a dialog that reviews what will be included — the
message count, the exact files, and the redaction policy in words — before a
format is chosen. Progress, success with the download name, and field-level
errors are all reported. **Print / Save as PDF** uses a dedicated print
stylesheet on both surfaces: sidebar, topbar, composer, rails, and the code
blocks' copy buttons are dropped, turns never split across a page, and the page
margins are set for paper.

Live browser evidence:
[`screenshots/working/122-BUG-22-chat-conversation-menu-live.png`](screenshots/working/122-BUG-22-chat-conversation-menu-live.png)
and [`screenshots/working/123-BUG-22-build-conversation-menu-live.png`](screenshots/working/123-BUG-22-build-conversation-menu-live.png).

---

## FIXED-55 — Rendered code blocks carry daily-use interaction controls

**Status: fixed in this change (was BUG-23).**

**Root cause.** Safe fenced code rendered, but with no syntax highlighting, no
copy action, and only a raw language token as a label.

**Fix applied.** `apps/web/src/lib/highlight.ts` is a locally-shipped,
allowlisted grammar scanner — no CDN grammar, no lazy-loaded language pack, no
`eval`. It preserves `markdown.ts`'s structural security argument rather than
adding a filter: the scanner produces `(kind, start, end)` spans over raw source
and never builds HTML, every token's text is escaped at emit time, and the only
tag emitted is `<span>` with a `class` from a fixed six-value allowlist. A fence
tagged with a language outside the allowlist renders as plain escaped text with
its label intact — mis-highlighting reads as a lie about what the code is; plain
text does not.

The renderer emits a header carrying the language's conventional name and a
`<button data-md-copy>`. The button has no handler of its own; `Markdown.svelte`
delegates one click listener on the wrapper, so the `{@html}` output stays
inert and a block that arrives mid-stream is operable the moment it renders.
What is copied is `textContent` of the `<code>` element — the source the model
wrote, with highlighting removed.

**UI.** Every code block in both Chat and Build shows its language and a
keyboard-focusable **Copy code** action that announces *Code copied to the
clipboard* or *Could not copy — your browser blocked clipboard access* through
an `aria-live` region and on the button itself. Token colours come from the
shared design tokens, so highlighting follows a theme switch, and
`forced-colors: active` drops back to system text for high-contrast readers.

**User-message behaviour, decided and documented.** A user bubble deliberately
renders literally: what the owner typed is shown exactly as typed, because a
prompt is an instruction whose exact characters matter, and silently
re-formatting it would misrepresent what was sent. Only assistant output is
rendered as Markdown. This is stated in
[the composer guide](../guide/README.md) rather than left ambiguous.

Live browser evidence:
[`screenshots/working/124-BUG-23-code-block-controls-live.png`](screenshots/working/124-BUG-23-code-block-controls-live.png).

---

## FIXED-56 — Approval resolution in another tab continues Chat

**Status: fixed in this change (was BUG-24).**

**Root cause.** Build could stream a parked continuation and Approvals could
offer a manual one, but only the surface that *recorded* the decision knew it
had been made. A Chat tab sat on **Waiting for approval** indefinitely, and the
owner's only recovery was to re-prompt — which discards the model's working
state and pays for the whole context again.

**Fix applied.** Two independent signals, because a stuck conversation is the
worst outcome. `BroadcastChannel("raiker:approvals")` delivers a resolution to
every other tab of the same origin instantly; it carries ids only and is treated
as a *hint*, never as authority. The authority is
`GET /api/approvals/resumable`, an authenticated, principal-scoped, idempotent
read backed by `list_resumable_suspended_turns`, which lists a parked turn
exactly while it is resolved-but-unclaimed and returns ids and the decision —
never conversation state. Polling covers what a broadcast cannot reach: a
decision made in another browser, on a phone, or by the CLI.

Exactly-once resumption is not enforced in the browser. The client guards
against obvious double-starts, but the real guarantee is the pre-existing atomic
`claim_suspended_turn` (suspended → resuming): two tabs that both react will both
call resume and exactly one gets the stream. The loser receives
`suspended_turn_already_resumed`, which is a **success** from the owner's point
of view and is reported as *Continued in another tab*, not as an error.

**UI.** The parked turn in **both Chat and Build** moves from **Waiting for
approval** to **Approved — continuing…** (or *Rejected — telling Raiker…*)
without a reload, and the resumed work streams into the same transcript row — the
original session, tool-call boundary, and cancellation controls are all preserved
because the server replays the same suspended state. When the live channel
cannot be reached, the card says so and offers a recoverable **Continue now**.

Live browser evidence:
[`screenshots/working/125-BUG-24-parked-turn-live.png`](screenshots/working/125-BUG-24-parked-turn-live.png).

---

## FIXED-57 — The shipped model profile existed as two divergent copies

**Status: fixed in this change; found while fixing BUG-21.**

**Observed.** Adding cache rates to `raiker/config/model-profiles.json` changed
nothing at runtime. `_read_config_text` prefers a workspace-relative
`config/model-profiles.json` and only falls back to the packaged resource, so the
repository-root copy silently won and the edit was invisible.

**Fix applied.** The two files are now identical, and the discrepancy is
recorded here so the next editor knows both must move together. The underlying
absence of a check that keeps them in step is tracked as **BUG-36**.

---

## FIXED-58 — Playwright could not launch the pre-installed browser

**Status: fixed in this change; found while verifying BUG-21.**

**Observed.** On a machine whose Chromium build number does not match the one
the pinned `@playwright/test` would download, every live spec failed with
*Executable doesn't exist* before reaching an assertion.

**Fix applied.** `apps/web/playwright.config.ts` honours an optional
`PLAYWRIGHT_CHROMIUM_EXECUTABLE` environment variable. Unset — the normal case,
including CI — Playwright resolves its own managed browser exactly as before.

---

## FIXED-59 — Scheduled work could not resume after its approval was granted

**Status: fixed in this change (was BUG-25).**

**Observed.** A scheduler-launched turn that reached an approval boundary parked
correctly — the turn suspended, the approval appeared in the inbox, the task card
said *waiting for approval* — and then, when the owner granted it, nothing
continued it. Chat can resume a parked turn because a Chat tab is watching for
the resolution (FIXED-56). A scheduled run has no client at all, so its
continuation had no owner and the task sat in `waiting_for_approval` forever.

**Root cause.** `raiker/tasks/scheduler.py` had one job — start due work. Nothing
in the host owned the other half.

**Fix applied.** `TaskScheduler.resume_approved()` is that owner, and it is
deliberately the *same* machinery a browser tab uses rather than a second one:
`list_resumable_suspended_turns` names what is resolved-but-unclaimed, and
`AgentGateway.aresume_after_approval` claims it through the atomic
`suspended → resuming` transition. Exactly-once is that claim, so a scheduler
tick and a tab racing on the same approval cannot both replay the turn — one
wins and the other is told it was already continued, which is the truth and is
reported as such rather than as a failure.

Every continuation re-checks the world before it runs: the task still exists,
has not been cancelled or stopped at a safe boundary, and still belongs to a real
owner. Nothing resumes on the strength of what was true when it parked. The pass
runs on the existing 15-second host tick, suppressed independently of `run_due`
so neither half can stop the other.

**UI when closed.** A new `continuing` task status carries the state between the
decision and the outcome, so the card moves **Waiting for approval →
Continuing → Completed/Failed** and the owner sees their decision take effect.
When automatic continuation cannot proceed the task stays parked, states why, and
offers **Continue now** — `POST /api/tasks/{id}/resume`, the same governed path,
owner-scoped, which can never continue something the automatic pass would have
refused. `task_resume_started` and `task_resume_blocked` make the whole life of
an approval readable in the audit log.

Covered by `tests/test_task_scheduler.py` (pending approval untouched, granted
approval continued, cancelled task never continued, lost claim race reported not
failed, owner retry scoped and effective).

---

## FIXED-60 — Image inspection had no zoom, pan, or rotation controls

**Status: fixed in this change (was BUG-26).**

**Observed.** The inspector could show a picture but not let you look at it. A
screenshot scaled to fit a side column is unreadable, and there was no way to get
closer, move around inside it, or turn a photo the right way up.

**Fix applied.** `apps/web/src/lib/components/ImageViewport.svelte`. Everything
happens in the browser, to pixels the server already sent:

- **Nothing is mutated.** Zoom, pan and rotation are a CSS transform on the
  `<img>`. The stored artifact is untouched, no re-encode happens, and closing
  the pane discards the view — it is a way of looking, not an edit.
- **Nothing is fetched.** The `src` is the same session-authorised blob URL the
  inspector already resolved. No tile server, no remote image service.
- **Every transform is bounded.** Zoom is clamped to 25 %–800 %; pan is clamped
  to the overflow the zoom created, so a picture can never be dragged out of its
  own frame and lost. Rotation is in right angles.
- **Reduced motion is honoured.** Transitions are dropped entirely under
  `prefers-reduced-motion`; the transform still applies, without animation.

**UI when closed.** Labelled **Zoom out / Zoom in / Fit / Rotate / Reset**
controls, a live zoom readout, and a focusable `role="application"` frame where
`+`/`-` zoom, arrows pan, `r` rotates, `f` fits and `0` resets. Unsupported media
keeps the honest existing state. Verified live in
`working/167-image-inspection-live.png`.

---

## FIXED-61 — Memory and file provenance could not open the exact source passage

**Status: fixed in this change (was BUG-27).**

**Observed.** Every approved memory already carried where it came from —
`source_session_id`, `source_turn_id`, `source_type`, written once by the
governed memory path and never rewritten. What it did not carry was any way to
*go there*. The Memory page could print "chat — Weekly planning" and nothing in
the product would open that conversation at the sentence the memory was drawn
from. The provenance was true and useless, which is the worst kind: a claim you
cannot check reads exactly like a claim you can.

**Fix applied.** `raiker/runtime/source_provenance.py` resolves those stored
coordinates into a passage the inspector can show, under four rules:

- **Coordinates are read, never inferred.** A record with no coordinates
  resolves to `no_provenance` rather than to a guess at which conversation
  "probably" produced it.
- **Authorisation is re-checked at read time, against the caller.** Owning the
  memory is not owning the source: the session behind the coordinates must
  belong to this account *now*, or the answer is `not_authorized` — which
  reveals nothing about whether that conversation exists.
- **Every failure is a named state.** `source_deleted`, `source_changed`,
  `unsupported_source` and `not_authorized` are each rendered in words.
- **Nothing executes source content.** The excerpt is bounded plain text plus
  two integers naming the run to mark; the highlight is applied by *slicing that
  text*, never by rendering markup the source supplied.

Served by `GET /api/memory/{id}/source` and
`GET /api/sessions/{sid}/attachments/{aid}/provenance`, so a memory and a
generated file give the same answers through the same resolver.

**UI when closed.** Memory's **View source** (on approved records and on pending
proposals, where reviewing a proposal you cannot read the basis of was the
sharper gap) opens the existing inspector at the highlighted passage with the
document title, the source status, and **Open conversation**. A generated file's
**Preview** resolves its provenance alongside the document. Missing provenance
renders an explicit unavailable state, never a dead action.

Covered by `tests/test_source_provenance.py` and the `source passage` group in
`FileInspector.test.ts`.

**Deliberately not claimed.** The stored coordinates name a turn, not a byte
range inside it, so the passage is located by searching the source text for the
memory's own words — exact when the text is unchanged, and honestly reported as
`source_changed` when it is not. Byte-range coordinates written at capture time
would remove the search entirely; that is **BUG-38**, not something pretended
here.

---

## FIXED-62 — Generated artifacts had no download surface

**Status: fixed in this change (was BUG-28).**

**Observed.** A generated document was previewable and nothing else. The only way
to get a report Raiker wrote onto disk was to select the preview text and paste
it somewhere.

**Fix applied.** `GET /api/sessions/{sid}/attachments/{aid}/download`,
deliberately narrow:

- **Authorisation is the stored reference**, exactly as for preview — this
  session, this attachment, this owner — so a download can never reach a file the
  same person could not already open. 404 for anything else; a 403 would confirm
  the id exists.
- **Nothing is served as something the browser will run.** Always
  `application/octet-stream`, attachment disposition, `nosniff`, `no-store`.
- **The filename is rebuilt, not echoed.** Path separators and header-breaking
  characters are dropped rather than escaped.
- **The download is evidence.** Every one appends `attachment_downloaded` with
  metadata only — id, name, type, size — never the bytes.

`download_bytes` is intentionally separate from `served_bytes`: the display path
is limited to the two types a browser can render safely, while a `.docx`, an
`.xlsx` or a Markdown report is a legitimate download and none of them can be
displayed inline.

**UI when closed.** Generated artifact cards carry **Preview** and **Download**
as distinct actions, and the inspector offers **Download** beside **Close** with
size and type in the header. Progress, completion, retention-expired and
permission-denied each have their own stated message. Verified live in
`working/168-artifact-download-live.png`.

Covered by `TestAttachmentDownload` in `tests/test_attachment_preview.py`
(bytes, headers, owner scoping, filename safety, audit evidence without content).

---

## FIXED-63 — Raiker had five runtimes and needed one

**Status: fixed in this change.**

**Observed.** `RuntimeMode` shipped `development_preview`,
`local_single_user_safe`, `local_single_user_runtime`,
`multi_user_local_runtime` and `hosted_or_networked_runtime`, and Settings asked
the owner to pick one before any capability could reach `enabled_runtime`. A
fresh install defaulted to `development_preview`, under which every capability
that needed runtime level refused — correctly, and unhelpfully, because nothing
on the Permissions page said the refusal came from a different page.

**Why it was wrong, not just awkward.** The mode was a fifth answer in front of
four that already decided everything: a capability's own gate state, its
threat-model acknowledgement, its human confirmation token, and whether a real
executor is registered for it. Every genuinely dangerous thing was gated by
those four. The mode could only ever say "not yet" to work they had already
authorised — and, being a *choice*, it could also be set wrong in the permissive
direction while reading as deliberate.

**Fix applied.** One runtime, `raiker_runtime`.

- `RuntimeMode` has one member. `normalize_runtime_mode()` accepts every
  historical name — from a stored row, a CLI line, or an older client — and
  resolves it to the single runtime; anything else is still refused.
- `ActivationRequirement.requires_runtime_mode` is gone, and with it the mode
  check in `evaluate_activation_requirement`. The remaining runtime-level
  refusal is binary and is the danger-zone switch: `activation_blocked:
  runtime_mode_not_active` now means *the agent runtime is disabled*, keeping
  its historical spelling so stored audit rows and older clients still resolve.
- **Disabling now disables.** It used to write a record naming
  `development_preview` with status `active`, which left a runtime running under
  a name implying it was not. It now writes `raiker_runtime` with status
  `disabled`, and `SQLiteStore.get_latest_runtime_mode()` lets the authority tell
  "never configured" from "the owner switched it off" — a distinction
  `get_active_runtime_mode()` structurally could not make.
- A fresh install is ready: no stored row means the runtime is on.

**UI when closed.** Settings → Runtime configuration states what is running
instead of asking. No picker, no mode list; **Disable agent runtime** (and
**Enable** once disabled) is the only runtime-level control, with the same
step-up dialog it always had. Capability copy across Permissions, Extensions and
MCP now points at Permissions for every runtime-level block, because that is
where all of them now resolve. Verified live in
`working/160-settings-single-runtime-live.png`.

**Posture change, stated plainly.** A fresh account can now raise a capability to
`enabled_runtime` without first activating a mode. That removes a redundant
switch, not a real one: the executor, gate, threat-ack and human-confirmation
requirements are unchanged, and the kill switch remains.

---

## FIXED-64 — The Build composer could not carry a file

**Status: fixed in this change (was BUG-35).**

**Observed.** Chat's composer attached workspace paths, images and documents
through the governed attachment store. Build's attached only the selected
repository's local subpath, automatically. Build is the surface where "look at
this stack trace", "here is the failing screenshot" and "match this spec
document" are the most natural things to say, and the composer had no way to say
them.

**Fix applied.** Not a second implementation — the same one.
`apps/web/src/lib/composerAttachments.svelte.ts` owns the attachment state, the
limits and the upload path; `ComposerChips.svelte`, `ComposerAttach.svelte` and
`ComposerAttachPanel.svelte` own the presentation. Chat was refactored onto them
(its ~150 lines of inline attachment code deleted), and Build and the Workbench
mount the same components. Build folds its files in beside the repository path in
the shape the prompt route already accepts.

**UI when closed.** Build's composer offers the same attach control in the same
place, the same chips with the same remove control, and the same limits and error
copy as Chat's — so what an owner learns on one surface is true on the other.
Verified live in `working/162-chat-composer-attach-live.png` and
`working/163-build-composer-attach-live.png`.

---

## FIXED-65 — Chat, Build and the Workbench composed work three different ways

**Status: fixed in this change.**

**Observed.** Three composers that looked like siblings and behaved like
strangers. The Workbench's said, in as many words, *"To work with a file, start
in Chat and attach it there"* — true, and an admission that it was a lesser
instrument. Its **Schedule** mode handed Tasks a prompt with no time, landing the
owner on a form whose required field they had to notice. Build had no copy action
on a response at all.

**Fix applied.**

- **One attachment implementation** across all three (FIXED-64), and the
  Workbench's files now ride the handoff: `raiker:compose` and
  `raiker:build-compose` carry already-uploaded attachment references, so
  starting work in the Workbench is the same act as starting it in Chat rather
  than a reduced version of it.
- **Schedule carries its time.** The Workbench asks for the start time in
  Schedule mode and passes it through, so the handoff arrives complete. All four
  modes now confirm where the work went.
- **The attach panel opens in flow**, growing the composer card, rather than as a
  floating popover over the text being typed — the first live screenshot of this
  change showed the popover covering the prompt, which is exactly the wrong thing
  to cover.
- **Copy is a glyph, and Build has one.** The code-block action and the response
  action are both SVG icons with all three states (idle / copied / failed) in the
  markup and CSS choosing one, so the delegated handler only ever sets an
  attribute and never writes into the button. The accessible name and tooltip
  move with the glyph, because an icon-only control that silently changes meaning
  is worse than a word.
- **The card behaves the same in both conversations**: identical focus lift,
  identical padding, identical hint treatment, and no motion under
  `prefers-reduced-motion`.

**UI when closed.** Verified live in `working/161-workbench-composer-live.png`,
`working/162-chat-composer-attach-live.png`,
`working/163-build-composer-attach-live.png` and `working/166-chat-live-turn.png`
(real Anthropic turn, both copy glyphs visible).

---

## FIXED-66 — Raiker did not start like an application on any platform

**Status: fixed in this change.**

**Observed.** Raiker ran on Windows, macOS and Linux; it did not *behave* like an
application on any of them. Starting it meant knowing to run `raiker-web`,
knowing that state lands in the current working directory, knowing which port to
keep free, and knowing to open a browser at the right URL. That is a service, and
asking a person to operate a service is asking them to hold the operating
system's job in their head.

**Fix applied.** `apps/api/launcher.py`, shipped as `raiker-app`. One entry
point, no per-OS script to keep in step:

- **State lives where the platform says it should** — `%LOCALAPPDATA%\Raiker`,
  `~/Library/Application Support/Raiker`, `$XDG_DATA_HOME/raiker` (falling back
  to `~/.local/share/raiker`). `RAIKER_HOME` overrides all three; `--workspace`
  overrides everything.
- **An already-running Raiker is joined, not fought.** `/api/health` — the only
  unauthenticated read, returning nothing but `{"status": "ok"}` — identifies a
  Raiker without touching the workspace. Two hosts over one encrypted workspace
  is a data-integrity problem; the person who started the app wants the app.
- **The port is found, not assumed.** 8765 first so the URL stays familiar, then
  the next free port, printed.
- **The browser opens through the platform's own opener** (`os.startfile`,
  `open`, `xdg-open`) with `webbrowser` as fallback. A headless machine prints
  the URL rather than failing.
- **Anything unrecognised is treated as POSIX** rather than refused: a BSD box
  has a home directory and a loopback interface, which is all this needs.

Exposure is unchanged: this binds loopback and offers no flag to do otherwise.
Reaching Raiker from another machine remains the deliberate
`raiker-web --allow-public` path with its own token requirement.

Covered by `tests/test_app_launcher.py`, which asks for each platform explicitly
rather than testing whatever the runner happens to be.

---

## FIXED-67 — An attached file did not look like the file it was

**Status: fixed in this change.**

**Observed.** Every attachment rendered as the same small grey pill: a generic
paper glyph and a filename, whether you had attached a photograph, a
spreadsheet, or a workspace folder path. That tells you nothing you did not
already know from typing the name, and a composer carrying three files read as a
row of tags rather than as work about to be handed over. It was also
indistinguishable from what the transcript showed afterwards, so there was no
way to confirm at a glance that what you sent was what you picked.

**Fix applied.** `AttachmentCard.svelte`, used by the composer *and* the
transcript in both Chat and Build:

- **A picture shows the picture.** An image the owner just picked is shown from
  the local file — no request, no placeholder. One already in the transcript has
  no local copy, so its bytes are fetched once through the same
  session-authorised preview route the inspector uses (an `<img>` cannot carry
  the bearer token) and reused for every render. A failure falls back to the
  type glyph: a worse card, and a perfectly good attachment.
- **Everything else states what it is.** A coloured type badge, the name, and
  the size — `PDF · 153 KB` — because those are the two facts a person checks
  before sending something. A workspace path names its folder instead, since
  that is what identifies it.
- **Names never rewrap the composer.** One line each, ellipsised, so adding
  files cannot push the text you are typing around.
- **Object URLs have an owner.** Removing an attachment revokes its thumbnail;
  sending transfers ownership to the turn (so clearing the composer must *not*
  revoke it, or the transcript would blank); starting a new conversation
  releases the transcript's. A blob URL kept past its last render pins the whole
  file in memory.

**UI when closed.** Verified with a real 2.2 MB JPEG and a real PDF:
`working/169-composer-attachments-live.png` (composer),
`working/170-transcript-attachments-live.png` (the same cards shown back, after
a real vision turn answered about the photograph),
`working/171-photo-inspection-live.png` (the same photograph at 156 % in the
inspector) and `working/172-build-attachment-card-live.png` (Build).

Covered by `AttachmentCard.test.ts` — type and size, local thumbnail, resolved
thumbnail, glyph fallback, workspace path, inert by default, and the open/remove
handlers.

---

## FIXED-68 — Governed memory lifecycle is complete *(was BUG-29)*

**Status: fixed in this change; found while implementing FIXED-49.**

**Observed.** The Memory API can list records and mutate text/pin/search/expiry,
but it cannot approve, edit-and-approve, reject, change scope with renewed
consent, report last use, distinguish logical forget from permanent deletion,
or return a complete per-memory audit history.

**Fix.** Owner-scoped proposal APIs now support approve, edit-and-approve, and
reject with stale-decision protection and secret-like-content refusal. Scope,
expiry, pin, edit, forget, and separately confirmed permanent purge actions are
audited. Memory cards expose source, last use, expiry review, lifecycle history,
and conflict-safe scope changes.

**UI when closed.** Pending cards provide **View source**, **Reject**,
**Edit and approve**, and **Approve**. Approved cards provide **Edit scope**,
**View history**, review/expiry controls, last-used status, **Forget memory**,
and a separately confirmed **Delete permanently** where policy allows.

---

## FIXED-69 — Knowledge Map source review and persistence are available *(was BUG-30)*

**Status: fixed in this change; found while implementing FIXED-49.**

**Observed.** The redesigned graph now provides force-directed placement,
global/local scopes, depth traversal, relationship inspection, type/status
querying, colour groups, fit/zoom/full-screen controls, and display/force/motion
settings. Server-side containment still validates only a typed
workspace-relative path: the browser has no file/folder chooser or pre-index
review. View settings and pinned positions are not yet persisted per workspace,
and project/date filtering, cluster summaries, indexed-file status, re-index,
and advanced-record disclosure still need richer graph DTOs.

**Fix.** The server now provides a workspace-contained, 200-entry incremental
browser and a bounded review plan that reports supported files, skipped files,
bytes, and large-source warnings before add/index. Per-owner transform, pinned
positions, groups, filters, force, display, and motion settings persist across
reloads. Protected runtime, Git metadata, and dependency directories are hidden
from the browser and refused as direct sources. Existing graph DTO provenance and relationship fields remain the
source of record; richer cluster and indexing telemetry stays incremental work,
not a prerequisite for safe source selection.

**UI when closed.** **Add workspace source** opens Choose file/folder → review
→ Add and index. Sources show indexed counts, warnings, last indexed, Re-index,
and Remove. Saved positions, zoom, groups, filters, motion, and force settings
restore per workspace; project clusters and Standard/Advanced modes expose the
richer records with full keyboard and screen-reader access.

---

## FIXED-70 — Owner-selected SSH and Daytona execution are governed *(was BUG-31)*

**Status: fixed in this change; audited from FIXED-47 and B20.**

**Observed.** Local no-network container execution is shipped, while governed
remote and cloud executor gates remain disabled and have no executor.

**Fix.** Settings → Runtime now configures owner-scoped SSH and existing Daytona
sandbox profiles using environment-variable credential references only. The
selected immutable profile id is shown consistently in Chat, Build, and
Schedule. `remote_execute` and `cloud_execute` are model-visible governed tools:
they require approval, re-enter runtime authority through the exactly-once
relay, enforce gate/mode/profile ownership, strict SSH host keys, bounded time
and output, and Daytona per-action cost ceilings. Results return metadata, never
credential values or unbounded command output. Local/container remain available
without silently falling back to remote execution.

**UI when closed.** Settings → Runtime configuration lists Local container,
Remote, and Cloud environments with availability, health, isolation summary,
cost/budget, last change, and role restrictions. Work composers show the
selected environment and block start with actionable configuration guidance.

---

## FIXED-71 — Local context capacity refresh and administrator overrides ship *(was BUG-33)*

**Status: fixed in this change; found while implementing FIXED-50.**

**Observed.** Runtime capacity is refreshed when an owner explicitly opens a
provider's model catalogue. Raiker preserves an exact profile-level
`context_window_tokens` fallback, but there is no periodic local refresh,
freshness timestamp in Models, or governed browser workflow for setting that
fallback when an older or custom runtime exposes no supported metadata field.

**Fix.** The resident task-scheduler tick now refreshes due local profiles on a
24-hour cadence; the Models page can also request an immediate refresh. Capacity
history is keyed by owner/provider/model/endpoint identity. A gate manager can
set or clear a validated fallback with a reason, and Models exposes source,
next refresh, errors, and history. Runtime-reported values retain precedence;
no value is reused across a different model or endpoint. Shared badges expose
the same status in Chat, Build, and Schedule.

**UI when closed.** Models → Details shows capacity, source, endpoint identity,
last checked, freshness, and refresh errors. Administrators can select
**Configure fallback capacity**, enter a positive token limit with a reason,
review the exact provider/model/endpoint scope, save or clear it, and inspect
change history. Chat and Build visibly distinguish **reported by runtime**,
**configured in Raiker**, **stale last-known value**, and **unavailable**.

---

## FIXED-72 — Reloaded Chat restores the parked approval *(was BUG-34)*

**Status: fixed in this change; found while implementing FIXED-56.**

**Observed.** A restored transcript carries only what is persisted — prompt
text, the agent's response message, and the turn status. `restoredTurn` in
`apps/web/src/lib/views/ChatView.svelte` therefore sets `approval: null`, so a
conversation reopened after a reload shows no **Waiting for approval** card for a
turn that is genuinely still parked. Cross-tab continuation (FIXED-56) then has
nothing to attach to in that tab: the watcher only polls while this surface
believes it has a parked turn, so a reloaded Chat cannot continue a turn it can
no longer see is waiting.

**Fix.** Session detail now includes principal-scoped, metadata-only parked
approval records derived from persisted suspended turns. Chat rehydrates the
matching card and restarts its continuation watcher, preserving the same
Review/Continue behaviour after reload without exposing action arguments.

**UI when closed.** Reopening a conversation whose turn is parked shows the same
**Waiting for approval** card, with the same **Review approval** and recoverable
**Continue now** actions, and continues automatically once a decision is
recorded anywhere — with no difference in behaviour between a live tab and a
reloaded one.

---

## FIXED-73 — Attached files sit outside Chat and Build speech bubbles

**Status: fixed in this change.**

**Observed.** Attachment cards were nested inside the coloured user-message
bubble, making files look like message text and producing inconsistent spacing
between Chat and Build.

**Fix.** Both surfaces now render the prompt bubble and its attachment group as
siblings inside the right-aligned user-message group. Existing attachment open,
thumbnail, metadata, and removal behaviour is unchanged. Component tests assert
that an attachment card cannot have a message bubble as its closest ancestor.

---

## FIXED-74 — The standing command container crashed before launch on Windows

**Status: fixed in this change; found during full-suite verification.**

**Observed.** `run_isolated_workspace_command` unconditionally called the
POSIX-only `os.getuid()` and `os.getgid()` APIs while building its Docker
command. On Windows, an otherwise valid owner-granted command therefore raised
`AttributeError` before Docker or the injected test runner could be reached.

**Fix.** The sandbox now adds Docker's `--user <uid>:<gid>` ownership mapping on
POSIX hosts and omits that unsupported mapping on Windows. Network isolation,
resource limits, dropped capabilities, the workspace bind mount, image
allowlist, and timeout remain unchanged. The container regression test asserts
both platform-specific command shapes.

**UI when closed.** An approved Build command can reach the configured local
Docker sandbox on Windows instead of failing before launch; configuration and
runtime failures still surface through the existing governed command feedback.

---

## FIXED-75 — Capacity history order was unstable for same-timestamp changes

**Status: fixed in this change; found in GitHub CI.**

**Observed.** Setting and immediately clearing an owner context-capacity
override can produce identical stored timestamps. The history query used a
random identifier as its secondary sort key, so CI could show the older `set`
event before the newer `cleared` event even though both writes succeeded.

**Fix.** Capacity history now orders equal timestamps by SQLite insertion order,
newest first. The regression test pins both events to the same timestamp and
asserts the stable lifecycle order.

**UI when closed.** Models always shows the newest capacity administration
action first, including rapid set/clear changes made within one clock tick.

---

## FIXED-76 — The shipped model-profile copies and human review cadence stay in step *(was BUG-36)*

**Status: fixed in this change; found while fixing BUG-21 (see FIXED-57).**

**Observed.** `config/model-profiles.json` and `raiker/config/model-profiles.json`
are separate files with the same content. `_read_config_text` prefers the
workspace-relative path and falls back to the packaged resource, so the
repository-root copy silently wins. An edit applied to only one of them appears
to do nothing, with no error and no warning — which is exactly how a price
correction could be believed applied while the runtime still charges the old
rate.

**Fix.** The repository validation suite compares the packaged resource byte for
byte with the workspace default and fails when either copy moves alone. Both
pricing blocks now carry `reviewed_at` and `review_interval_days`; the backend
derives the due date and current/overdue state independently from provider-sync
timestamps. Registry and component tests pin both the copy invariant and review
state.

**UI when closed.** Models → Pricing states when each shipped documented rate
was last reviewed by a human, distinct from when it was last synchronised, and
flags a rate whose review is overdue.

---

## FIXED-77 — Source coordinates identify the passage inside a turn *(was BUG-38)*

**Status: fixed in this change; found while fixing BUG-27 (see FIXED-61).**

**Observed.** A memory's stored provenance names `source_session_id` and
`source_turn_id` and nothing finer. FIXED-61 therefore locates the passage by
searching the source text for the memory's own words: exact while the text is
unchanged, and honestly reported as `source_changed` when it is not — but a
memory whose wording was normalised on the way into the store, or whose source
was edited in a way that preserves meaning, reads as changed when it is not.

**Fix.** Memory capture now stores UTF-8 byte start/end coordinates and the
SHA-256 of the exact passage in provenance. Resolution checks the byte slice and
hash first, then uses matching text only for legacy records or a changed slice.
The returned `resolution_method` distinguishes `stored_coordinates` from
`matching_text`; a changed coordinate can still resolve honestly through the
fallback, while `source_changed` remains the terminal answer when neither
method finds the passage. Multibyte and changed-coordinate regressions are in
`tests/test_source_provenance.py`.

**UI when closed.** A resolved passage states whether it was located by stored
coordinates or by matching text, so an owner can tell a verified quotation from a
best-effort one. `source_changed` is reserved for a source that genuinely no
longer contains the passage.

---

## FIXED-78 — Daytona budgets reconcile cumulative provider spend *(was BUG-42)*

**Status: fixed in this change; found while fixing BUG-31.**

**Observed.** A Daytona profile enforces an owner-configured maximum estimated
cost for each proposed command. The CLI integration does not receive an
authoritative billed-cost result, so Raiker cannot decrement a cumulative
workspace budget or reconcile estimates against the provider invoice.

**Fix.** Every Daytona action now writes an immutable reservation before the CLI
can start. Admission runs inside an immediate SQLite transaction against
cumulative reconciled actuals, provider-reported cumulative growth, and
unsettled reservations; a second individually-valid action is refused when the
combined exposure exceeds the profile limit. Provider snapshots replace an
estimate with actual cost when a deployment supplies the billing adapter. The
default adapter explicitly reports unavailable because Daytona's documented
organization-usage API reports resource quotas, not billed dollars; the
estimate therefore remains reserved instead of being silently released or
mislabelled as actual spend. A command that never starts writes a release.

**UI.** Settings → Runtime shows committed and remaining cost plus the
reconciliation state. The API also returns reserved, Raiker actual,
provider-cumulative, remaining, and the append-only per-action history. Covered
by `tests/test_execution_environments.py`.

---

## FIXED-79 — Knowledge Map and export dialogs have clean accessibility semantics *(was BUG-43)*

**Status: fixed in this change; found during verification.**

**Observed.** `svelte-check` reports interaction-role diagnostics for the
force-directed graph canvas and click-contained panels, plus non-native dialog
markup in the source-review and conversation-export overlays. Type checking
passes, but keyboard and screen-reader semantics are not yet cleanly expressed.

**Fix.** Graph selection is target-aware and its pointer plumbing no longer
requires click handlers on every containing panel. Source review and
conversation export are native modal `dialog` elements; Escape closes them,
the browser contains focus, and closing restores the invoking control (including
the export menu button whose menu item is removed on open). The Knowledge Map
canvas retains focusable keyboard-selectable nodes. `svelte-check` emits zero
errors and zero warnings, component tests exercise keyboard open/close and focus
restoration, and the live Playwright scenario runs axe scans on both workflows.

**UI when closed.** All graph and dialog workflows work without a pointer,
focus never escapes an open modal, focus returns to the invoking control, and
the web check emits no accessibility diagnostics.

---

## FIXED-80 — Schedule carries and presents attachments like Chat and Build

**Status: fixed in this change; consistency improvement requested during this fix.**

**Observed.** Chat, Build, and Workbench shared the governed attachment store,
but a Workbench handoff to Task or Schedule discarded its files and the Tasks
composer had no attachment control. This made the selected execution environment
look consistent across the three surfaces while its prompt context was not.

**Fix.** Workbench now transfers attachment ownership for task and schedule
handoffs. Tasks uses the shared cards and upload/path panel, validates uploaded
IDs against the creating owner, persists only the prompt attachment references,
and delivers them to the governed scheduler turn. Task cards show the files in
a separate attachment group outside the instruction copy; Chat and Build retain
their existing sibling attachment groups outside the speech bubble.

Covered by `TasksView.test.ts`, `tests/test_task_scheduler.py`, and the live
Playwright schedule screenshot.

---

## FIXED-81 — Submission waits for attachment uploads on every composer

**Status: fixed in this change; found during live Playwright verification.**

**Observed.** A fast Send, Build, Task, or Schedule action could run while the
shared attachment upload was still in flight. The prompt was accepted without
the file and the completed attachment remained in the composer, making the
visible input disagree with the governed turn or task that had just been made.

**Fix.** Chat, Build, Workbench, and Tasks now reject submission while the
attachment store is uploading, and their primary action stays disabled until
the upload settles. The existing upload error remains visible and no prompt or
task is created from a partially resolved attachment set.

**UI when closed.** Clicking quickly after choosing a file cannot separate the
file from the prompt. The action becomes available once every selected file is
ready, consistently across Chat, Build, Task, and Schedule.

---

## FIXED-82 — Live axe findings are closed in Export and Knowledge Map

**Status: fixed in this change; found during live Playwright verification.**

**Observed.** The first real-browser axe pass found low-contrast secondary copy
in the export dialog. After that was corrected, the full Knowledge Map scan
found its page nested a second `main` landmark inside the application `main`
and reported the small light-theme eyebrow at 3.92:1 contrast.

**Fix.** Export metadata and policy copy use the readable secondary text token.
Knowledge Map is now a labelled section within the application landmark, and
its eyebrow is larger with AA-contrast colours in light and dark themes. The
focused live scenario asserts zero axe violations for each open dialog and the
Knowledge Map application content.

**UI when closed.** The two modal workflows and Knowledge Map retain their
visual hierarchy without duplicate landmarks or unreadable secondary labels.

---

## FIXED-83 — Chat export has deterministic keyboard activation

**Status: fixed in this change; found during live Playwright verification.**

**Observed.** In repeated real Chromium runs, focus reached the Export
conversation menu item and Enter closed the transient menu, but the export
dialog was not mounted consistently. Pointer activation and isolated dialog
tests did not expose the intermittent menu-to-modal transition.

**Fix.** The menu item now handles Enter and Space explicitly, prevents the
native activation from racing the transient menu teardown, and opens the same
modal path used by pointer activation. The live test opens the menu and item
with the keyboard, asserts the dialog, closes it with Escape, and verifies focus
returns to Conversation actions.

**UI when closed.** Export opens reliably without a pointer and leaves keyboard
focus at a predictable control when the dialog closes.

---

## FIXED-84 — Accessibility test dependencies pass the licensing gate

**Status: fixed in this change; found during workflow verification.**

**Observed.** Adding the live Playwright axe scan caused the licensing workflow
to stop on the MPL-2.0 licences of `@axe-core/playwright` and `axe-core`. The
repository policy correctly requires an explicit exception for every reviewed
licence, even when the packages are development-only.

**Fix.** Both exact packages now have documented MPL-2.0 exceptions: they are
unmodified, development-only accessibility tooling, their source is not changed,
and they are not shipped in Raiker's production web bundle or Python packages.
The licensing check and generated SPDX inventory continue to enumerate them.

**UI when closed.** No product surface changes; the accessibility regression
test remains enforceable without weakening the general licensing policy.

---

## FIXED-85 — A settings choice made while the page was still loading was silently discarded

**Status: fixed in this change; found while verifying FIXED-86 live.**

**Observed.** Settings renders its controls before `GET /api/settings` resolves.
Choosing a density in that window updated the control, and then the arriving
snapshot replaced the whole settings object — so the radio flipped back, the
page stayed *dirty*, and pressing **Save changes** wrote the **old** value while
reporting *All changes saved*. It reproduced reliably in the live suite whenever
Settings was re-entered from another route: the choice was accepted on screen and
the opposite value was persisted.

The window is small but the failure mode is the bad one: the owner is told their
change was saved, and it was not.

**Fix.** `load()` now treats the server snapshot as the base and reapplies the
keys the owner has changed since the last confirmed snapshot on top of it.
`serverSettings` still records what the server actually holds, so **Discard** and
the failed-write rollback keep meaning exactly what they meant. The regression is
`apps/web/src/lib/views/SettingsView.test.ts` — it holds the read open, makes a
choice, then resolves the read with the old value, and fails against the previous
code.

**UI when closed.** A preference chosen the moment a Settings page opens is the
preference that gets saved.

---

## FIXED-86 — The visual language is finished, and written down *(was BUG-37)*

**Status: fixed in this change.**

**Observed.** A first token-level pass had already shipped — a real depth ladder,
optical tracking, themed scrollbars, a readable `::selection`, a softer focus
halo. What remained were the six things that are decisions about how a page is
*composed* rather than how a surface is painted, and the absence of a written
specification a contributor could build a new page from.

**Fix.** All six, plus the specification:

1. **A type scale with intent.** Headings sat at 1.45 / 1.08 / 0.95rem — the
   first interval is 14%, which reads as "the same size, only bolder", so
   heading level was carried by weight alone. A modular scale at 1.22 now runs
   `--text-2xs` through `--text-display`, every interval above 1.15×, and the
   serif face is a deliberate voice through `.display`: the Workbench greeting,
   empty-state titles, sign-in headlines — where Raiker speaks to the owner
   rather than labels a control — at weight 500 and clamped so a 375px screen
   is not handed three lines of display type.
2. **Density modes.** Compact / Comfortable / Spacious were already a setting,
   but they moved only the spacing scale, so a pricing table stayed exactly as
   tall while the gaps around it changed — which is why the setting looked like
   it did nothing. `--control-y`, `--control-x`, `--row-y` and `--row-x` are now
   per-mode and are spent by `.btn`, `.input`, `.table` and `.card`. The control
   is a radio group with a stated consequence and a preview of the row height
   each mode produces.
3. **Empty and loading states as first-class art.** `EmptyState` gets a mark
   with depth (a tinted disc, a ring, a soft glow), a display-type title, and an
   `action` slot — an empty state that names what is missing and stops is a dead
   end. `PageState` gains a skeleton form (`lines`) for the cases where the
   eventual shape is known; where it is not, the honest one-line form stays,
   because drawing a fake shape is a guess presented as information.
4. **Iconography.** `ICON_SIZE` names one optical size per role (`sm`/`md`/`lg`/
   `xl`) where call sites had been passing 14, 15, 16, 17, 18, 20 and 22 more or
   less interchangeably. `Icon`'s `filled` prop is the selected half of the
   filled/outline pair — the same paths with a `currentColor` wash behind them,
   so it cannot drift from the outline because it *is* the outline — and the
   sidebar uses it for the current route. Three glyphs meant two things each:
   `diagnostics` was byte-for-byte the clock-with-rewind of `checkpoints`,
   `capabilities` was `sun` with four rays instead of eight, and `projects` was
   the same folder as `folder`. All three are redrawn.
5. **Data-visual language.** A **meter** is a proportion of a fixed capacity and
   carries state tones; a **bar** is one value in a comparison and carries none,
   because a large share is not a warning; a number compared vertically is set
   in tabular figures via `.numeric` on the cell, so label columns stay in the
   reading face. The context meter and the provider spend bars now use those
   primitives instead of their own. A non-zero fill is never rounded down to
   nothing.
6. **Motion.** `--motion-enter` (180ms), `--motion-exit` (120ms) and
   `--motion-emphasis` (240ms) with matching easings, exposed as `.motion-enter`
   / `.motion-exit` / `.motion-emphasis`. Enter is slower than exit because
   appearing needs to be noticed and disappearing needs to be out of the way.
   Nothing moves layout, and under `prefers-reduced-motion` the end state is
   named explicitly rather than only the duration collapsed — a 0.01ms animation
   still paints its first frame, which is enough to flash.

[`docs/VISUAL_DESIGN_SPEC.md`](../VISUAL_DESIGN_SPEC.md) states every rule above
with its reason, names the test that enforces it, and ends with the seven steps
for building a new page. `apps/web/src/lib/appCss.test.ts` and
`apps/web/src/lib/icons.test.ts` fail if the scale loses a step, density stops
reaching a row, reduced motion stops naming its end state, a meter stops taking
its tone from the shared tokens, or two icons collide.

**UI when closed.** A documented visual specification a contributor can build a
new page from without inventing, and every existing page audited against it in
both themes at 375 / 768 / 1024 / 1440 px — the audit is
[`e2e/bug-37-39-40-41-live.spec.ts`](../../apps/web/e2e/bug-37-39-40-41-live.spec.ts),
which walks all 17 routes at all four widths in both themes and fails on any
horizontal overflow of the shell or any console error.

Live evidence: `working/186-visual-workbench-{light,dark}.png`,
`working/187-visual-models-pricing-{light,dark}.png`,
`working/188-visual-settings-density-{light,dark}.png`,
`working/189-visual-tasks-{light,dark}.png`, and
[`working/190-BUG-37-density-compact-live.png`](screenshots/working/190-BUG-37-density-compact-live.png).
The earlier token pass remains recorded at `working/133-*` and `working/134-*`.

---

## FIXED-87 — An approved scheduled run continues immediately *(was BUG-39)*

**Status: fixed in this change.**

**Observed.** FIXED-59 continued a parked scheduled run on the host's own
15-second tick. A decision granted just after a tick therefore took up to 15
seconds to take effect, with the card reading *waiting for approval* the whole
time. Chat continued in the same situation within a second, because the tab that
resolved the approval goes straight on to resume the turn — a scheduler-launched
run has no tab, so nothing told the host its decision had arrived.

**Fix.** Approval resolution now signals the scheduler the way it already
signals a browser tab. `raiker/tasks/wakeup.py` holds a `SchedulerWakeup` — one
coalescing, loop-bound event — created on `app.state` so a route can raise it
whether or not a scheduler is running. Recording a resolved outcome against a
parked turn raises it, scoped to the `sess_inbox_*` sessions scheduled work
actually runs in: a Chat or Build approval is continued by the client that made
it and has nothing for the scheduler to do. The host runs a second worker
alongside the tick that waits on that event and runs the continuation pass the
moment it fires.

Three properties are deliberate. **The tick is unchanged**, so it becomes the
recovery path — a decision made in another process, or while a pass was already
running, is still picked up within 15 seconds. **Exactly-once is untouched**: it
remains `claim_suspended_turn`, so a nudge, a tick and a browser tab racing on
one parked turn still produce exactly one continuation; an `asyncio.Lock` keeps
the two workers from doing the same sweep twice, which is tidiness, not
correctness. **Nudging never fails a decision**: a host that is shutting down, or
one with no worker at all, simply falls back to the sweep.

**UI when closed.** A granted approval moves the task card to **Continuing**
without a perceptible wait. The card now says *"Approving continues this run
automatically."* and **Continue now** is a quiet, ghost-styled recovery
affordance — what to press when a granted run has not moved — rather than the
fast path it was previously mistaken for.

Regressions: `tests/test_scheduler_wakeup.py` (the signal, the coalescing, the
cross-thread path, and the Chat/scheduled scoping) and
`apps/web/src/lib/views/TasksView.test.ts`. Live evidence:
[`working/193-BUG-39-approval-continues-live.png`](screenshots/working/193-BUG-39-approval-continues-live.png).

---

## FIXED-88 — `raiker-app` installs, registers, controls and removes itself *(was BUG-40)*

**Status: fixed in this change for the lifecycle; the signed-installer and
signed-update rows were split out as BUG-44, and are closed by FIXED-92.**

**Observed.** FIXED-66 made Raiker *start* like an application once Python and
the package were present. Everything around that start was unimplemented:
`docs/DESKTOP_DISTRIBUTION_DESIGN.md` specifies background service registration,
tray/menu-bar control, pause and quit with waiting work reported, signed updates,
and an uninstall that offers to retain, export, or securely erase each instance.
None of it existed, so "closing the browser does not stop the host" was true only
for as long as the terminal that started it stayed open.

**Fix.** The lifecycle table, platform by platform, with each platform's own
service manager rather than a Raiker daemon:

| Platform | Mechanism | Activated with |
|---|---|---|
| macOS | `launchd` LaunchAgent (per-user) | `launchctl bootstrap gui/<uid>` |
| Linux | `systemd --user` unit | `systemctl --user enable --now` |
| Windows | per-user Startup folder entry | the shell, at sign-in |

`raiker/app/service.py` builds each definition as data — so the same description
can be shown before anything is written, asserted in a test on a platform it does
not target, and then executed. The Windows choice is the Startup folder rather
than a `Run` registry value so install, inspect and uninstall are the same three
operations everywhere (write a file, read a file, delete a file) with nothing
hiding in a hive an uninstall could miss; the Windows *service* path in the
design belongs to the explicitly-configured shared host, which is a separate
administrator decision. A failed activation is reported and never rolls the file
back: a headless session where `launchctl` or `systemctl` cannot reach its
manager is a normal place to be, and the definition still takes effect at the
next sign-in.

`raiker/app/host.py` answers *running* / *paused* / *needs attention* / *stopped*
from `.raiker/host/`, file-backed because the running host and a `raiker-app`
invocation in a terminal are different processes. A record whose process is gone
reports *stopped*, not *running*. **Pause** stops new background work — the
scheduler's due-work pass claims nothing and the capacity refresh is skipped —
and deliberately does **not** stop an approved continuation, because that work is
already under way and stranding it would make Pause a way to lose a decision.
*Needs attention* is a distinct state from *running*: a control reading "running"
while three approvals block every scheduled routine tells the truth about the
process and lies about the product.

`raiker/app/uninstall.py` states the plan before it acts — every path, its size,
and the per-instance choice between `keep`, `export` and `erase` — and names the
two things an uninstall is otherwise assumed to have taken: a backup configured
to an external drive or provider, and the Python package itself. Instances are
removed deepest-first, so a nested instance is not made a no-op by its parent
disappearing first. `erase` overwrites each file before unlinking and is
described as best effort, because on a copy-on-write filesystem or an SSD doing
its own wear levelling an overwrite reaches the logical block and not necessarily
every physical one.

`GET /api/host` and `POST /api/host/{pause,resume,quit,restart}` are the control's
contract, owner-authenticated exactly like every other route. Quit sends this
process `SIGTERM` so uvicorn's own graceful shutdown runs the lifespan teardown
and in-flight governed work reaches a safe boundary; nothing force-kills.
**Restart is refused when it would be a lie** — a host started from a terminal
has nothing that would start it again, so the route returns `not_registered` and
says so rather than exiting and leaving a dead URL. When Raiker *is* registered,
the process exits 75, a status both `launchd` and the generated `systemd` unit
are configured to restart on.

**What was deliberately not done, became BUG-44, and is now FIXED-92:** signed installers
(`.dmg`/`.pkg`, `.msi`, AppImage, `.deb`) and the signed-update channel with
atomic migration and rollback. Both need code-signing identities and per-OS
release runners; neither can be honestly built from a source checkout, and an
unsigned artifact shipped as if it were signed would be worse than none.

**UI when closed.** A menu-bar control in the top bar reports whether the host is
running, paused, needing attention or stopped, names what background work is in
flight, says whether Raiker starts on its own and with which platform mechanism,
and offers Pause, Restart and Quit. Quitting reports waiting work and requires a
second, informed press before it stops. Uninstall states exactly what will be
removed and what will be kept before it removes anything.

The control is in the top bar rather than the OS tray: a native tray needs a
packaged, signed binary per platform (BUG-44, now FIXED-92 for the build
and BUG-48 for the tray itself), and the behaviour an owner
actually needs — an honest state, in-flight work named, and a quit that says what
it would interrupt — should not wait for that. "Open Raiker" is the one tray
action with no meaning in-app: you are already looking at it.

Regressions: `tests/test_app_lifecycle.py` (state, pause gating the scheduler,
each platform's definition parsed and asserted on every platform, install and
uninstall round trips, the uninstall plan and its dispositions, and the CLI) and
`tests/test_api_host.py` (authentication, the quit-with-waiting-work report, and
the refused restart). Live evidence:
[`working/191-BUG-40-host-control-live.png`](screenshots/working/191-BUG-40-host-control-live.png)
and [`working/192-BUG-40-host-paused-live.png`](screenshots/working/192-BUG-40-host-paused-live.png).

---

## FIXED-89 — `e2e/composer.spec.ts` matches the app, and CI runs it *(was BUG-41)*

**Status: fixed in this change.**

**Observed.** Two of the three tests in `apps/web/e2e/composer.spec.ts` failed
against the built app: they looked for `Start a new chat` and `Schedule a task`
links on the Workbench, and for a "Make Raiker feel like yours" Settings heading,
that the FIXED-46 and FIXED-48 redesigns had replaced. The suite was not in CI —
`.github/workflows/web.yml` ran lint, check, test and build, not `test:e2e` — so
the drift was invisible.

**Fix.** The spec is rewritten against the surfaces as they are: the Workbench's
one composer with a mode per destination and its four current quick actions, the
Settings section rail, the Models catalogue picker, and the Personalisation
density modes. And the suite runs.

Playwright now has two projects, told apart by filename: `mocked` needs
`npm run build` and nothing else, because every response comes from a fixture
inside the spec; `live` drives a running host holding real provider credentials.
CI runs `test:e2e:mocked` after the build. It does **not** run `live` — CI has no
key, and a suite that cannot really pass must not report that it did.

The split matches on the whole filename containing `live` rather than a
`-live.spec.ts` suffix, because `live-end-to-end.spec.ts` is a live spec that
does not end that way, and a rule that quietly missed one live spec would hand CI
a scenario it cannot pass and blame the pull request for it.

**UI when closed.** No user-facing change; this is about the evidence being
trustworthy. A green `npm run test:e2e:mocked` means what it says, and it is now
green on every pull request that touches `apps/web/`.

---

## FIXED-90 — Terminal approval authenticates, previews, executes, and continues *(was BUG-32)*

**Status: fixed in this change; audited from FIXED-08.**

**Observed.** The terminal client's `/approve` can resolve metadata without an
authenticated web session, so it cannot execute the bounded approval relay or
resume work. Approval-gated `shell` likewise remains record-only.

**Fix.** `/approvals`, `/approve`, and `/deny` now require a live control-session
token in `RAIKER_API_TOKEN`. The token is looked up afresh for every decision, so
revocation, expiry, scope, principal activity, and account ownership are checked
before the approval is shown. `/approve <id>` is preview-only: it prints the
immutable tool, risk, argv, workspace working directory, timeout, and output
bound. Execution requires the approval id to be repeated exactly as
`/approve <id> --confirm <id>`.

`shell_execution` now enters the same narrow `ApprovalExecutionBridge` used by
the web app. The relay still checks TTL and the immutable payload hash, claims
the approval atomically, captures the approving session posture, and re-routes
the target through its current capability gate, decision mode, policy, command
allowlist, workspace containment, timeout, and output bound. The authority now
returns the executor's bounded evidence instead of discarding it. Terminal and
web history therefore show the same exit code, byte counts, bounded stdout and
stderr, truncation state, and resolving principal. Secret-like output is
redacted before it enters either the terminal response or durable history. If a
turn is parked, the
terminal records the outcome and claims the same exactly-once continuation; if
none is attached it says so rather than implying a model resumed.

Regressions: `tests/test_terminal_approval_execution.py`, the shell relay case in
`tests/test_api_approvals.py`, and the approval-history component case in
`apps/web/src/lib/views/ApprovalsView.test.ts`.

**UI when closed.** The terminal prints an exact effect preview, requires an
authenticated confirmation, then shows **Executing**, bounded output/result,
and **Continuing turn** or a precise refusal. The web Approvals history records
the terminal principal and identical execution evidence.

---

## FIXED-91 — A worker pays SQLCipher key derivation once per workspace *(was BUG-45)*

**Status: fixed in this change; found while verifying FIXED-86.**

**Observed.** The visual audit walks all 17 routes at four widths in two themes —
136 page loads, each firing its own reads. Two things happened. First, the
default 120/min per-IP rate limit refused most of it, which is the limit doing
exactly its job. Second, with the limit raised for the audit, the host stayed
slow for a minute or more *after* the sweep finished: routes that normally render
instantly sat on `Loading …`, and the sweep itself had already moved on.

The cause is that every API request opens a fresh `SQLiteStore`, and every
SQLCipher connection pays a full key derivation before it can read a row. A
burst of a thousand cheap reads therefore queues a large amount of KDF work that
drains long after the requests that caused it. Nothing is incorrect and nothing
is lost — it is latency, and only under a load no person generates — but it is
the shape of problem that becomes a real one the moment a page fans out.

**Fix.** `SQLiteStore.connect()` now caches one keyed SQLCipher connection per
resolved workspace and worker thread. Short-lived store objects on the same API
worker reuse it, so the worker pays key derivation on first use instead of on
every route. Query work is never shared between workers. `check_same_thread` is
disabled only so the host's shutdown path can close every worker handle from one
place.

The cache has explicit invalidation rather than relying on garbage collection:
the FastAPI lifespan closes the workspace at shutdown, uninstall invalidates it
before export/erase/rename, a closed handle is detected and re-keyed on its next
read, and process exit closes anything left. Encryption remains SQLCipher with
the same app key and foreign-key/busy-timeout setup. Regressions in
`tests/test_sqlite_connection_cache.py` prove repeated stores open one keyed
connection and invalidation forces exactly one fresh key derivation; the existing
SQLCipher and lifecycle suites cover encryption and removal compatibility.

**UI when closed.** No user-visible change under normal use; a page that fans out
across several reads renders as quickly as one that makes a single read, and a
burst does not leave the next page waiting behind it.

---

## FIXED-92 — A manually-triggered release pipeline, and a signed update channel *(was BUG-44)*

**Status: fixed in this change for the release pipeline and the update channel;
the first-run wizard and the native tray icon are split out as BUG-48.**

**Observed.** FIXED-88 implemented the lifecycle around the host but not the two
rows of `docs/DESKTOP_DISTRIBUTION_DESIGN.md` that a source checkout cannot
build: the **Install** row's *"Install signed application files only"* and the
**Update** row's *"verify signature, back up before migration, migrate
atomically, and retain a rollback path on failure"*. `raiker/app/update.py` held
the second row's security boundary and nothing published anything for it to
verify. There was also no way for a running Raiker to say what it was: the
product could not distinguish a release from a checkout, so it could not have
told the truth about either.

**Fix.** The release, split into the part that can be tested anywhere and the
part that can only exist on a runner.

`raiker/app/release.py` owns every decision: the four targets and the signing
identity each one requires, held as data so the workflow, the tests and the
product read one list; a **reproducible** payload build — sorted entries, one
fixed timestamp from `SOURCE_DATE_EPOCH`, normalised modes, caches excluded — so
building twice from one commit produces one digest; the schema-1 manifest that
is *exactly* the four fields `apply_signed_update` accepts; and the signed
channel index that maps each target to its artifact, digest, manifest and
signature. `raiker-release build|channel|verify` is the CLI the workflow calls,
which is what makes `tests/test_release_pipeline.py` a test of the pipeline
rather than of a script beside it.

`.github/workflows/release.yml` is `workflow_dispatch` only — a release is a
deliberate act, and a pipeline that could publish from a push eventually
publishes something nobody chose. Per target, on that target's own runner, it
resolves that platform's wheels (`sqlcipher3-wheels` above all), builds the
payload, **builds it a second time and compares digests**, runs
`scripts/packaging_smoke_test.py`, and builds the native installer with the
platform's own tool (`pkgbuild`, WiX, `dpkg-deb`, `appimagetool`) via
`scripts/build_installer.py`. The channel job then rebuilds and signs the index
and runs `raiker-release verify` — *the same verification an installed Raiker
performs* — so a release its own updater would refuse never leaves the workflow.

**The honesty rule, which is the part that matters.** `signing: require` is the
default and **fails** a target whose identity secrets are absent. `signing: skip`
is the only other option: it produces artifacts named `-unsigned`, records
`signing.applied = false` in the `installation.json` *inside* the artifact, and
is refused by the publish job. There is nothing in between, and no path produces
a file that looks like a release without being one.

The channel, in `raiker/app/update.py` and `raiker/app/updater.py`: a
signature-verified index, an entry for *this* target or a refusal, a version that
must be strictly newer (a downgrade is "no update", never an install), an
artifact whose build never ran platform signing refused outright, bounded
downloads, and then `apply_signed_update` — which verifies again, copies the
current version to its recovery point, migrates only in staging, and swaps by
rename. `roll_back()` restores a retained version with the same two-rename shape,
so a rollback cannot be the thing that leaves an owner with no installation.

`raiker/app/installation.py` is where provenance stops being assumed. It reads
the record the build wrote, and **every way that can fail — absent, unparsable,
an unknown schema, an unknown target — reports an unsigned source installation**.
Nothing reads the absence of evidence as a signature.

**What this change does *not* do, stated plainly.** No signed artifact has been
produced, because this repository holds no Apple Developer ID, no notarisation
credentials, and no Authenticode certificate. The pipeline refuses rather than
pretends. The first-run setup wizard and the native tray icon are BUG-48.

**UI when closed.** The Host control's **Install & updates** section says what
this Raiker is — *signed release*, *unsigned build*, or *source checkout* with
its version and target — names the pinned update channel or says that none is
configured and that Raiker therefore contacts no update service, lists the
versions available to roll back to, and offers **Check for updates**. Opening it
makes no outbound request; the check is the only thing that asks, and on a source
checkout it refuses locally without one. Applying an update is deliberately not a
button: it replaces the files the host is running from, so the panel names
`raiker-app update --apply` instead.

Regressions: `tests/test_release_pipeline.py` (the matrix, reproducibility, the
payload contents, an unsigned build's three separate admissions, the manifest the
updater accepts, and the whole CLI end to end including a tampered artifact),
`tests/test_signed_updates.py` (channel selection, downgrade refusal, tampering,
unsigned refusal, path-shaped artifact names, rollback),
`tests/test_installation_provenance.py` (every way provenance can be missing or
damaged, channel pinning, artifact-URL confinement, a check that never fetches on
a checkout, and the CLI), `tests/test_api_updates.py` (authentication, the
local-only status read, the matrix, and the channel reported without its key),
and `apps/web/src/lib/components/HostControl.test.ts`.

Live evidence:
[`working/199-BUG-44-source-checkout-live.png`](screenshots/working/199-BUG-44-source-checkout-live.png)
and
[`working/200-BUG-44-packaged-unsigned-build-live.png`](screenshots/working/200-BUG-44-packaged-unsigned-build-live.png).
The second is a `raiker-web` started **from inside a release artifact** this
pipeline built — `PYTHONPATH` and `RAIKER_INSTALL_ROOT` both pointing at the
extracted payload, so the code answering is the artifact's copy — reporting
`0.1.0 · linux-x86_64` as an **unsigned build**, read from the record that build
wrote.

---

## FIXED-93 — A provider test result appears only under the provider that ran it *(was BUG-47)*

**Status: fixed in this change.**

**Observed.** Models → Ollama → **Test** correctly contacted the local Ollama
service and reported nine models, but the success message appeared beneath the
Anthropic and OpenRouter cards instead of beneath Ollama. The provider connection
and model selection were correct; only the feedback placement was wrong.

**Root cause, and why it read as *duplication*.** `ModelsView.svelte` held one
`testResult` string for the whole page and rendered it under *every* hosted card
whose connection was configured. The local rows — where Ollama lives — had a
**Test** button and no place to render a result at all. So one test produced N
messages, none of them attached to the provider that ran it.

**Fix.** Transient test state is keyed by profile id: `testResults[profile_id]`
for the answer and `testing[profile_id]` for the in-flight flag, so one provider
being tested no longer disables another's button either. Each card and each local
row renders only its own entry, tagged `data-test-result="<profile_id>"`.

And every result now **names its provider**. The old text reused the model
picker's note, which says an anonymous *"Provider unreachable — type a model id
if you know it."* That is fine inside a picker you just opened and is exactly
what made the misplacement invisible: nothing in the sentence contradicted the
card above it. `testNote()` produces *"Ollama could not be reached…"*,
*"Anthropic responded and exposed 11 models."*, and so on, so a result under the
wrong card would now argue with the card it sits under.

**UI when closed.** Testing Ollama shows one result, beneath Ollama. Hosted cards
keep their own independent status and never repeat another provider's.

Regressions: `apps/web/src/lib/views/ModelsView.test.ts` — two connected
providers with one tested (the message occurs exactly once, inside that
provider's row, and not inside the hosted card), both tested (two independent
results, neither overwritten nor duplicated), and an unreachable provider named
in its own failure. Live evidence:
[`working/197-BUG-47-local-result-under-ollama-live.png`](screenshots/working/197-BUG-47-local-result-under-ollama-live.png)
and
[`working/198-BUG-47-hosted-cards-keep-their-own-live.png`](screenshots/working/198-BUG-47-hosted-cards-keep-their-own-live.png).

---

## FIXED-94 — Build had no plan for the work in front of it *(was B6)*

**Status: fixed in this change.**

**Observed.** Build ran a genuine agentic loop with nothing tracking what it
intended to do next. On a change of any length the transcript looked identical
whether the agent was on step two or step nine, and a failure at step six left
neither the model nor the owner with a statement of what the remaining steps
were. `raiker/tasks` stores work the owner *scheduled*; nothing existed for the
work a turn set itself.

**Fix applied.** A turn-written, session-scoped plan — ordered steps, one status
each — with four seams:

* **The tool.** `update_plan` (`raiker/models/tool_call_validation.py`,
  `raiker/tools/broker.py::_update_plan`) takes the complete plan and replaces
  the stored one. Validation is fail-closed and names every rejection
  (`raiker/runtime/agent_plan.py`): a step with no title, an unknown status, more
  than 20 steps, or a second `in_progress` step is refused and the previously
  stored plan is left untouched, because half a spine is worse than the one that
  was already there. At most one step may be `in_progress`, so "what is happening
  right now" always has exactly one answer.
* **Persistence.** One owner-scoped row per session (`agent_plans`,
  `RAIKER-1036-agent-plans`), keyed by (session, principal) so a plan is never
  readable across accounts. A stored row that no longer parses reads as *no
  plan* rather than raising — a recovery aid must never be able to stop a turn.
* **Recovery.** The plan is re-injected into every later turn of the
  conversation as a system message (`agent_plan_replayed`), so it survives an
  approval parking the turn, a failed step, and a new prompt. This is what makes
  it a recovery point rather than a progress bar.
* **The surface.** `agent_plan_updated` is streamed as a lifecycle event
  carrying the steps, and `PlanChecklist.svelte` renders it live above the
  transcript in **both** Chat and Build — the tool is model-visible in either, so
  a Chat that silently stored a plan would be exactly the invisible surface this
  document exists to prevent. `GET /api/sessions/{id}/plan` re-reads it for a
  second tab. The checklist is a statement, not a control: its only button
  collapses the card, because an ungoverned edit would make the checklist
  disagree with what the runtime actually holds.

It grants nothing. A plan runs nothing and schedules nothing; every step it
names still reaches the broker, the policy engine, and the approval path exactly
as if the plan did not exist.

**Live evidence.** `e2e/plan-subagent-mcp-live.spec.ts` against
`claude-haiku-4-5-20251001` holding a real credential: the model writes a plan,
the checklist shows `1 of 3 done` with the progress bar at 33; a second turn
advances it to `2 of 3`; and a third turn that calls **no tool** lists the steps
and their statuses back, which it can only do from the re-injected plan.
Screenshots `working/b6-build-live-plan-checklist.png`,
`b6-build-live-plan-advanced.png`, `b6-build-live-plan-recovered.png`.

**UI when closed.** A `PLAN` card above the transcript with each step's status
named in text as well as marked by glyph and colour, a completed-over-total
count, a progress bar, and a collapsed line naming the current step.

---

## FIXED-95 — The model could not delegate a wide search *(was B7)*

**Status: fixed in this change.**

**Observed.** `raiker/agents/orchestration.py` already implemented bounded,
governed subagents — depth, step, tool-call, wall-clock and token budgets, a
read-only delegable tool set, and a persisted contract — and nothing exposed
them to a model. Every wide search therefore ran in the main context: fifty
greps and their fifty results, sitting in the turn for the rest of the
conversation.

**Fix applied.** `spawn_subagent` (`raiker/tools/subagent_tools.py`). The parent
hands over an objective and a bounded list of read-only steps; the subagent runs
them under its own principal and its own contract and returns a **bounded
digest** rather than the raw transcript.

What it cannot do, each enforced rather than asked for:

* **Widen authority.** Only `SPAWNABLE_TOOLS` — read-only, local, no egress —
  may be delegated. A step naming a write, a shell command, a connector, an MCP
  tool, or `spawn_subagent` itself is refused before the subagent is created,
  with the offending tool named. There is no argument that relaxes this.
* **Escape governance.** Every step still runs through the same `ToolBroker`,
  policy engine, capability gates and audit path as a step the parent ran itself.
* **Recurse.** `spawn_subagent` is not delegable, and the depth budget is a
  second floor under that.
* **Speak with authority.** The digest reaches the calling model framed as
  untrusted data — it is the output of tools reading files the model did not
  choose, and treating it as instructions is the classic indirect-injection path
  (OWASP LLM01).

The findings travel through an in-process sink, exactly as the MCP executor's
`content_sink` does, so `OrchestrationOutcome` stays metadata-only and the
`action_executed`/broker events keep counts, contract ids and tool names while
the content reaches the model and nothing else.

**Live evidence.** The model delegated a two-step workspace inventory and the
transcript recorded *Subagent workspace inventory finished 2 read-only step(s)
(glob, list_directory)* without the raw listings entering it. Screenshot
`working/b7-build-live-subagent.png`.

**UI when closed.** A first-class line in the turn's governance disclosure
naming the subagent, how many read-only steps it ran, and which tools it used.

---

## FIXED-96 — A connected MCP server did not say whether the agent could use it *(B8 review)*

**Status: fixed in this change.**

**Observed.** FIXED-17 made a connected server's tools callable. Reviewing B8
against the running product showed the *surface* had not caught up: two owner
controls stand between a connected server and the model — the capability gate
and the per-capability decision mode — and the MCP page reported only the
handshake. A server read `connected · 2 tool(s)` beside a model that could never
call one, because the decision mode's default `ask` withholds. Worse,
`McpToolService.available_servers` checked only the gate, so those tools were
*advertised* to the model and then refused at call time — contradicting the
module's own promise that "the model is never offered a tool the runtime would
refuse".

**Fix applied.**

* **Discovery keeps its promise.** `callable_now()` answers the gate and the
  decision mode together, and `available_servers()` uses it, so a mode that
  would withhold every call projects nothing rather than dangling a tool in
  front of a model that can only be told no.
* **The page states the second fact.** `GET /api/mcp/agent-access` reports gate
  state, decision mode, how many tools are currently projected, and a reason
  code when none are. Extensions → MCP servers turns that into either a banner
  naming the exact reason and linking to Permissions, or a confirmation that *N*
  tools are available as `mcp__server__tool` — and each connected card carries
  the matching **Callable by Raiker** / **Not callable yet** chip so a card can
  no longer disagree with the runtime. A failed reachability read leaves the
  page exactly as usable as before rather than claiming either state.

This follows the security posture rather than fighting it: nothing new is
blocked, the owner's own control is named, and the remedy is one link away.

**Live evidence.** With the connector gate enabled and the mode left at its
default, the page said the tools were withheld and the card said *Not callable
yet*; raising the mode to Allow flipped both; and the model then called
`mcp__echo__echo` for real, with the audit trail keeping `arguments_length: 23`
and `content_redacted: true` rather than the payload. Screenshots
`working/b8-mcp-live-withheld.png`, `b8-mcp-live-callable.png`,
`b8-mcp-live-tool-call.png`.

**UI when closed.** As described above.

---

## FIXED-97 — An event the runtime emitted but never declared killed the turn

**Status: fixed in this change; found during B6 live testing.**

**Observed.** B6's first live turn ended as *stream ended* with no stated cause.
`AgentEvent` validates `event_type` against `contracts/models.py::EVENT_TYPES`
and raises `ContractValidationError` otherwise — inside the streaming turn,
where it surfaces to the user as a failed task and to the log as one buried
ASGI traceback.

**The pre-existing half.** `model_tool_calls_dropped` — B4's (FIXED-39) whole
evidence mechanism, the event that proves no tool call disappeared without a
record — had shipped undeclared. Any turn that actually dropped a call died at
the exact moment it tried to say so. The unit tests never caught it because they
assert on results rather than on the durable log.

**Fix applied.** `agent_plan_updated`, `agent_plan_replayed`,
`subagent_completed` and `model_tool_calls_dropped` are declared, and
`tests/test_agent_plan_and_subagents.py::TestEveryEmittedEventIsDeclared`
statically scans every literal event type the runtime emits against the declared
set, so the next one cannot ship silently.

**UI when closed.** Turns that emit these events complete normally, and the
governance disclosure carries plain-English lines for each.

---

## FIXED-98 — Tools were advertised to the model that policy always denied

**Status: fixed in this change; found while implementing B6/B7.**

**Observed.** `PolicyEngine.review` ends in a hard `unknown_or_denied_tool` deny
for any tool in neither `allowed_read_actions` nor `approval_required_actions`.
Four tools already in the model's advertised schema were in neither:

* `create_task` and `assign_session_project` — both proposed by the model,
  both answered with a deny rather than the approval they were built for;
* `remote_execute` and `cloud_execute` — the *tool* names the model proposes,
  while `remote_execution_cap` / `cloud_execution_cap` (which were listed) are
  the *capability* names the runtime authority routes on. Two vocabularies, and
  the tool half was missing, so a proposal never reached the approval the broker
  already knew how to raise for it.

**Fix applied.** All four are registered on the path they were designed for:
`create_task`, `assign_session_project`, `remote_execute` and `cloud_execute` on
the approval path; `update_plan` and `spawn_subagent` read-shaped, for the same
reason `connector_read` is. Nothing is loosened — the capability gate, owner
profile, credential reference and cost ceiling all still stand in front of any
actual remote or cloud execution. `tests/test_policy_engine.py` now asserts the
invariant directly: **no model-exposed tool may fall through to
`unknown_or_denied_tool`.**

**Found and not fixed here.** `StaticPolicyConfig.denied_actions` is dead
configuration — nothing reads it — and it lists `write_file` and `edit_file`,
which would be alarming if it were live. Removing it is a separate cleanup with
a wider blast radius than this change should carry; it is recorded as BUG-51.

**UI when closed.** A model-proposed task, project assignment, or remote command
raises a decision in Approvals instead of failing with a policy denial.

---

## FIXED-99 — A policy refusal in a *fresh* batch dropped the calls behind it *(was BUG-52)*

**Status: fixed in this change.**

**Observed.** ADD-02 made an approval boundary queue the rest of the model's
batch, and made a refusal *inside* that queue skip its own call and continue. A
refusal in the batch's **first pass** did neither. In
`raiker/runtime/orchestrator.py::_arun_agent_loop`, a `deny` at index *k* of a
fresh batch set `status = "denied"`, ended the turn, and emitted
`model_tool_calls_dropped` for calls *k+1…n*. The same refusal therefore produced
two different outcomes depending only on whether the owner happened to have made
a decision earlier in the same batch — which is not a rule anyone can reason
about, least of all the model, which was told "denied" and left to guess how much
of what it asked for that covered.

**Reproduce.** Have the model propose `[read_file(../escape.md),
write_file(one.md), write_file(three.md)]` in one batch, with no approval ahead
of the refusal. The turn ended at the refused read and both writes were dropped.
Move an approval-bearing call in front of the same refused read and it was
skipped while the calls behind it were still offered for a decision.

**Root cause.** Two places decided what a non-`allow` verdict meant, and they
disagreed. The serial execution loop broke on `decision != "allow"`, so nothing
after a refusal was ever brokered; the walk that followed then treated the first
non-`allow` call as *the* boundary, queueing its remainder only when the verdict
was `needs_approval`. The queue drain added by ADD-02 had the right rule and was
unreachable from the first pass.

**Fix applied.** The first pass now walks the batch the way the queue does.

* **Only an approval stops the batch.** The serial loop breaks on
  `needs_approval` alone, so a call after a refusal is brokered and governed on
  its own terms rather than dying with the one in front of it.
* **A refusal is answered against its own call.** It is reported with the same
  `queued_denial_outcome` payload the drained queue already used — the one that
  names the tool and says explicitly that the other calls in the batch were
  decided separately — and the batch carries on.
* **Executed results and refusals go back together.** One assistant message
  names every call that reached an outcome and one tool message answers each, in
  the order the model proposed them, so the next model call sees exactly which of
  its calls ran and which policy would not run.
* **`denied` is reserved for a batch with nothing left.** A batch in which every
  call was refused still ends the turn as `denied` with the same message, so the
  long-standing single-refusal behaviour is unchanged. A refused call never
  becomes the turn's `last_result`, so it cannot make a turn that went on to
  answer correctly read as failed.
* **Nothing is dropped at a policy boundary.** `model_tool_calls_dropped` is now
  emitted only for calls that genuinely will not run — the tool-call budget.

**Also added here: the refusal is now visible.** `policy_decision` is written by
the broker and is durable-only, so before this the only thing that told a
watching owner a call had been refused was the turn ending on it. A new streamed
`model_tool_call_refused` event (tool name and governed reason codes; no
arguments, no workspace content) carries it into the transcript, where Build
renders it in its governance disclosure and Chat renders a **Policy refused one
call in this turn** card naming the tool and its reasons. Without it, closing this
entry would have traded a turn that stopped for a call that silently disappeared.

**Evidence.** `tests/test_batched_approval_queue.py::TestAFirstPassDenialSkipsOnlyItsOwnCall`
covers the read behind a refusal still running and still reaching the model, the
refusal's narrow wording, the batch carrying on to its next decision, the parked
conversation stating the refusal without spending budget on it, the symmetry the
defect broke (the same refusal either side of a decision), and the two cases that
must not change — an all-refused batch and a single refused call. The live
scenario is
[`e2e/bug-52-first-pass-denial-live.spec.ts`](../../apps/web/e2e/bug-52-first-pass-denial-live.spec.ts);
its screenshots are `working/bug-52-*`.

**Found and not fixed here.** Three things this work surfaced are recorded as
BUG-53 (a multi-call turn's answer text runs together in Chat), BUG-54 (the live
stub model both batch scenarios depend on is not in the repository), and BUG-55
(ninety lines of the Chat transcript, including a second approval card with
different copy, are disabled behind `{#if false}`).

**UI when closed.** A batch containing one refused call reports that call as
refused and still presents the rest, in Chat and in Approvals, exactly as it does
when the refusal falls after an approval.

---

## FIXED-100 — The SQLCipher connection cache never let a workspace go *(was BUG-50)*

**Status: fixed in this change.**

**Observed.** Running the whole Python suite in one process failed with
`INTERNALERROR> OSError: [Errno 24] Too many open files` on a host whose
`ulimit -n` is 4096; splitting it into four passes it. A direct probe showed why:
opening 50 distinct workspaces raised the process's open descriptors from 4 to
154, and none were released.

**Root cause.** FIXED-91 caches one keyed SQLCipher connection per resolved
workspace and worker thread, which is exactly right for the repeated-reads
problem it solved — SQLCipher derives its key when a connection is opened, and
API routes construct short-lived `SQLiteStore` objects. It had explicit
invalidation (shutdown, uninstall, a closed handle) but **no eviction**: the
cache was keyed by workspace and grew without bound. A test session opens
hundreds of temporary workspaces; so, more slowly, does a long-lived host serving
many instances, each of which is its own workspace.

**Fix applied.** `_CONNECTIONS` in `raiker/storage/sqlite.py` is an `OrderedDict`
held least-recently-used first, and `connect` moves a hit to the end and then
trims. Three properties hold it together:

* **A thread only ever closes a handle it owns**, or one whose owning thread has
  exited. `connect` has no release point, so a cached connection may be mid-query
  in the thread that owns it; closing another live worker's handle would be a
  use-after-close. Reaping an exited thread's handles is what stops the bound
  drifting upwards with thread churn.
* **The bound is process-wide, not per thread.** Self-eviction alone would let a
  request threadpool multiply the bound by its worker count, which is precisely
  the "host serving many instances" case. The allowance a thread gives itself is
  the per-thread limit **or** the process ceiling shared between the threads
  currently holding connections, whichever is smaller.
* **FIXED-91's property is intact.** Repeated stores on one workspace and worker
  still pay key derivation once — a workspace in use is the most recently used
  entry and is never the one evicted.

The per-thread limit is 8, overridable with
`RAIKER_SQLITE_CONNECTION_CACHE_LIMIT`; the process ceiling is eight threads'
worth of that. Both are readable at runtime through `connection_cache_limit()`
and `connection_cache_ceiling()`, and `cached_connection_count()` reports what is
actually held.

**Evidence.** `tests/test_sqlite_connection_cache.py` keeps the two FIXED-91
tests and adds five: far more workspaces than the limit leave both the cache and
the process's descriptor count bounded; a workspace still in use survives the
eviction while the stalest one goes, and never re-derives its key; eight worker
threads touching 48 workspaces between them stay under the process ceiling rather
than under eight separate per-thread ones; an exited thread's handle is reaped;
and a live thread's handle is never closed by another thread's eviction — it is
still usable afterwards. **The full suite now runs in one process again**, which
is the symptom this entry opened with.

Live, against two running hosts each serving 30 instance workspaces created
through `POST /api/instances` — the shipped endpoint behind the login screen's
instance form — and each measured from the same starting point:

| Host | Descriptors before | After 30 instances |
|---|---|---|
| The commit before this change | 10 | **100** |
| This change | 10 | **34** |

A third measurement made the point the table cannot: the same fixed host, asked
to serve *another* 30 instances on top of the 30 it had already served, went from
43 descriptors to 40. The cost stops tracking the number of workspaces the
process has ever opened.

**Found and not fixed here.** `python -m compileall raiker apps tests` — a
command this repository's own CI runs — leaves `__pycache__` directories inside
the shipped skill folders, after which
`tests/test_skills.py::TestShippedSkills::test_bundled_files_are_linked_from_the_body`
fails on a compiled artefact it was never meant to see. Recorded as BUG-56.

**UI when closed.** No user-visible change under normal use, and the live run
holds that claim to its word: after the host served 30 more instance workspaces,
every route of the owner's own workspace still rendered with **0 console
errors** and its dashboard status still resolved out of the database the cache
had been evicting around. `working/bug-50-host-before-many-instances.png` and
`working/bug-50-host-after-many-instances.png` are that host on either side of
it. A host that has served many instances for a long time keeps working instead
of eventually failing to open files.

---

## BUG-46 — SQLCipher cannot lock key-bearing pages on this Windows host

**Status: open; found while verifying FIXED-91.**

**Observed.** The Windows SQLCipher wheel repeatedly reports
`sqlcipher_mlock: VirtualLock() returned 0 LastError=1453` while opening test
workspaces. Database encryption, reads, writes, and key-cache invalidation all
pass, so this is not an at-rest confidentiality or correctness failure. It does
mean SQLCipher could not prove that key-bearing memory stayed out of the page
file on this host.

**Required fix.** Reproduce on clean supported Windows 10 and 11 runners, record
the installed wheel/SQLite build and process memory-lock limits, and either ship
a SQLCipher build whose secure-memory lock succeeds or surface a durable degraded
posture with an actionable platform remedy. Do not suppress the warning unless a
test proves key pages are locked.

**UI when closed.** Settings → Security reports database encryption and locked
memory separately. A host whose key pages cannot be locked says **Degraded** and
links to the precise remediation; a healthy host says **Locked in memory**.

---

## BUG-48 — There is still no setup wizard and no native tray icon

**Status: open; split out of BUG-44 (see FIXED-92).**

**Observed.** FIXED-92 makes a signed release buildable and an update
verifiable, and FIXED-88 put the tray control's *behaviour* in the top bar. Two
rows of `docs/DESKTOP_DISTRIBUTION_DESIGN.md` are still specification. The
**First-run experience** section describes a wizard that creates the instance,
selects or defers a model, explains local/hosted privacy and tests the
connection, chooses a backup target, and then opens the workspace — none of it
exists as a guided flow; a new owner meets the login screen and finds the rest.
And the tray/menu-bar icon itself needs a packaged binary with a platform GUI
toolkit, which no artifact currently contains.

**Required fix.** A first-run wizard in the web app, entered automatically on an
instance that has never completed setup, whose every step is skippable and whose
model step can defer. Then a native tray/menu-bar binary per platform, bundled
into the installers FIXED-92 builds, whose only unique action is **Open Raiker**
— every other action already exists in the Host control and must call the same
`/api/host/*` routes rather than growing a second implementation.

**UI when closed.** A non-technical owner installs Raiker, is walked through
creating an instance and connecting or deferring a model without ever seeing a
terminal, and afterwards finds Raiker in the tray/menu bar with its state and
Pause / Restart / Quit.

---

## BUG-49 — Two release-workflow actions are pinned by tag, not by digest

**Status: open; found while building `.github/workflows/release.yml`.**

**Observed.** Every other action in this repository is pinned to a commit SHA.
`actions/upload-artifact` and `actions/download-artifact` in
`.github/workflows/release.yml` are pinned to `@v4`, because the commit digests
could not be resolved from the environment the workflow was written in. A tag is
mutable: whoever controls it can change what those steps run, and those steps
handle the release artifacts.

**Required fix.** Resolve both actions' commit digests and pin them, with the
version in a comment beside each, exactly as `actions/checkout`,
`actions/setup-python` and `actions/setup-node` are pinned. Then check no other
workflow has acquired a tag pin.

**UI when closed.** None — this is supply-chain hygiene for the pipeline that
produces what owners install.

---

## BUG-51 — `denied_actions` is dead policy configuration

**Status: open; found while implementing B6/B7.**

**Observed.** `raiker/policy/config.py::StaticPolicyConfig.denied_actions` is
never read by `PolicyEngine` or anything else. It lists `write_file`,
`edit_file`, `delete_file`, `network_request`, `web_fetch`, `plugin_execute`,
`remote_execute`, `process` and `network` — a set that reads like a hard block
and enforces nothing. A reviewer auditing the policy layer would reasonably
conclude that file writes are denied outright.

**Required fix.** Either delete the field, or make it authoritative and
reconcile it with `approval_required_actions` (which currently governs those
same tools). Do not leave a third policy set that looks load-bearing and is not.

**UI when closed.** No user-visible change; this is an auditability defect.

---

## BUG-53 — A multi-call turn's answer text runs together in Chat

**Status: open; found while verifying FIXED-99.**

**Observed.** A turn in which the model speaks more than once — every turn that
calls a tool and then answers — renders as one unbroken paragraph with no space
between the two utterances:

> Reading ../escape.md and listing the workspace.I could not read ../escape.md —
> policy refused that one call…

`working/bug-52-chat-refusal-does-not-end-the-turn.png` shows it.

**Root cause.** `collectText` in `apps/web/src/lib/turnPhases.ts` joins every
streamed `text_delta` with `""`, which is right *within* one model response and
wrong *between* two of them: the deltas of the second response begin a new
sentence, and nothing marks the seam.

**Required fix.** Separate the text of successive model responses in a turn —
either by paragraph, matching how the model itself wrote them, or by carrying a
response boundary through the stream so `collectText` can break on it. Do not
insert whitespace blindly between deltas; inside one response that would break
words in the middle.

**UI when closed.** A turn that reads a file and then answers reads as two
statements rather than one run-on sentence, in Chat and in Build.

---

## BUG-54 — The live end-to-end stub model is not in the repository

**Status: open; found while writing FIXED-99's live scenario.**

**Observed.** Two live specs —
[`e2e/add-02-batched-approval-queue-live.spec.ts`](../../apps/web/e2e/add-02-batched-approval-queue-live.spec.ts)
and [`e2e/bug-52-first-pass-denial-live.spec.ts`](../../apps/web/e2e/bug-52-first-pass-denial-live.spec.ts)
— name `python <scratch>/stub_model.py` as a prerequisite. That file exists only
in the scratch directory of the session that wrote each spec, so neither
scenario can be re-run by anyone else, and the exact batch each one asserts on
is recorded nowhere but in prose.

**Why it matters.** These two specs are the evidence behind ADD-02 and FIXED-99.
Evidence that cannot be reproduced is a claim. Every other live spec drives a
real provider the reader can also connect; these two do not, and the thing that
replaces the provider is missing.

**Required fix.** Commit the stub under `apps/web/e2e/` (or `scripts/`) as a
checked-in fixture with its own README line, and point both specs at it by
repository path. It is a local, loopback-only HTTP server with no credential and
no network, so it introduces no new boundary — it is the *input* to the run, and
it belongs beside the specs that depend on it.

**UI when closed.** None — this is reproducibility of the evidence behind two
entries in this document.

---

## BUG-55 — A disabled block in the Chat transcript reads as live code

**Status: open; found while verifying FIXED-99.**

**Observed.** `apps/web/src/lib/views/ChatView.svelte` wraps roughly ninety lines
of the transcript — a phase line, an answer paragraph, an error line, a response
metadata row and a **complete second approval card** — in `{#if false}`. All of
it is dead. The live approval card is a separate, later block, and the two say
different things: the disabled one tells the owner to "Review it in the Approvals
inbox", while the live one carries the batch position, the cross-tab resume state
and the **Continue now** control.

**Why it matters.** Someone changing the approval copy will reasonably edit the
first card they find and see no change in the product; a reviewer auditing what
Chat tells an owner about a governed action will read the wrong text. It is the
same failure mode as BUG-51 — configuration that looks load-bearing and is not.

**Required fix.** Delete the disabled block, or, where a fragment is genuinely
being kept for a planned redesign, move it out of the component and say so.
Nothing that renders governance copy should exist twice with two different
wordings.

**UI when closed.** No user-visible change; this is a maintainability and
auditability defect.

---

## BUG-56 — A shipped-skill check fails after `compileall`, which CI itself runs

**Status: open; found while verifying FIXED-100.**

**Observed.** Running `python -m compileall raiker apps tests` and then the test
suite fails:

> `AssertionError: algorithm-creator never references
> scripts/__pycache__/oracle_check.cpython-311.pyc`

**Root cause.** `tests/test_skills.py::TestShippedSkills::test_bundled_files_are_linked_from_the_body`
walks each shipped skill folder with `rglob("*")` and asserts every file it finds
is referenced from that skill's `SKILL.md` — a good rule, because a bundled file
nothing points at never loads. It has no notion of build output, so a
`__pycache__` directory beside a skill's `scripts/` is read as an unreferenced
bundled file. `.github/workflows/ci.yml` runs `compileall` over the same three
trees; it survives only because it runs it *after* `pytest`. A developer who runs
the two in the other order sees a failure that has nothing to do with their
change, in a test whose message points at a shipped skill.

**Required fix.** Skip generated artefacts when walking a skill folder —
`__pycache__` and compiled bytecode at minimum — so the check keeps asserting
what it means to assert and stops depending on command order. Do not weaken the
rule itself: an unreferenced *source* file in a skill bundle is still a defect.

**UI when closed.** None — this is a test-suite reliability defect.

---

## Verified working (no action needed)

Recorded so the fixes above are read against the right baseline: first-run
bootstrap; all 15 routes and 10 hub tabs with **0 console errors**; owner
sign-in; vault key generate/save with elevated re-auth; capability gates
(62 listed, four decision modes, step-up enforced, 42 deferred domains offering
no enable path); runtime-mode activation; hosted-provider connection, live
provider model catalogue, and model selection; a real streamed Anthropic turn;
recent-chat list with row menu; chat search over titles and message text;
sessions, checkpoints, audit log, diagnostics, notifications, work-in-action;
all four task types (immediate, scheduled, daily routine, background agent) with
nesting, priority, and stop; project creation and session assignment; document
and image attachment upload reaching the model; MCP server create/connect/
monitor; theme toggle across all views; notification centre; STOP switch;
and adaptive navigation at 375/768/1024/1440 px with no horizontal overflow.