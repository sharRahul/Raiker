# To be fixed

Defects and gaps found while executing
[the live manual test plan](RAIKER_LIVE_MANUAL_TEST_PLAN.md) against a running
`raiker-web` on **2026-07-26**, hosted Anthropic `claude-haiku-4-5-20251001`.

Each entry states what was observed, the reproduction, the root cause in code,
and the proposed fix. Fixed entries remain as evidence; every deferred item
found by the FIXED-01 through FIXED-48 audit is now an explicit BUG with a
required user-interface outcome, so closing backend work cannot leave an
invisible or misleading product surface.

Two entries — GAP-BUILD and GAP-CHAT — are not defects. They are the itemised
distance between what Build and Chat ship today and what each is meant to be:
Build as an autonomous coding agent that closes its own loop, Chat as a general
agentic work assistant that acts across the owner's tools and files. They are
written to the same standard as the defects: what exists today with the file
that proves it, what is missing, and the concrete work.

Evidence: [`screenshots/not-working/`](screenshots/not-working) (defects),
[`screenshots/working/`](screenshots/working) (verified behaviour).

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
| BUG-25 | High | Tasks / approval continuation | Open |
| BUG-26 | Low | File inspector / images | Open |
| BUG-27 | Medium | Memory / provenance | Open |
| BUG-28 | Medium | Chat / artifact download | Open |
| BUG-29 | High | Memory / governed lifecycle | Open |
| BUG-30 | Medium | Knowledge Map / sources and scale | Open |
| BUG-31 | High | Build / remote execution containment | Open |
| BUG-32 | Medium | Terminal / approval execution | Open |
| BUG-33 | Medium | Local models / capacity administration | Open |
| BUG-34 | Medium | Chat / restored approval state | Open |
| BUG-35 | Low | Build / composer attachments | Open |
| BUG-36 | Low | Models / shipped price review cadence | Open |
| GAP-BUILD | — | Build — coding-agent parity | Analysis (B1–B4 complete; 17 items remain) |
| GAP-CHAT | — | Chat — work-assistant parity | Analysis (15 items remain) |

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
separately in FIXED-03 below; automatic 90 % compaction and weekly quota remain
open in `docs/superpowers/plans/2026-07-26-chat-composer-context-controls.md`.

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
right-side pane and no overlay. Matched the implementation note then standing in
`docs/superpowers/plans/2026-07-26-chat-file-inspector.md`: *"This feature is
specified but not implemented."*

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

**UI.** Models → **Pricing** states, per exact model id: the source
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

## BUG-25 — Scheduled work cannot resume after its approval is granted

**Status: open; audited from FIXED-13.**

**Observed.** Scheduler-launched turns remain `waiting_for_approval` because no
client owns their continuation relay.

**Required fix.** Give the scheduler an authenticated, durable, exactly-once
resume worker that revalidates task state, approval scope, expiry, STOP state,
and runtime policy before continuing.

**UI when closed.** Task and Work in action cards show the approval, resolution,
resume attempt, and resulting state. A granted task moves through
**Continuing → Running/Failed/Completed**, with a reason and retry action when
automatic continuation cannot proceed.

---

## BUG-26 — Image inspection has no zoom, pan, or rotation controls

**Status: open; audited from FIXED-10.**

**Required fix.** Add client-side, bounded image transforms that do not mutate
the stored artifact or fetch remote content.

**UI when closed.** The file inspector exposes labelled Zoom in/out, Fit,
Rotate, and Reset controls, keyboard shortcuts, the current zoom level, and a
reduced-motion-safe pan surface. Unsupported media retains the honest existing
state.

---

## BUG-27 — Memory and file provenance cannot open the exact source passage

**Status: open; audited from FIXED-10 and FIXED-45.**

**Observed.** Records expose source metadata, but no endpoint resolves an
authorised source excerpt and no inspector can highlight the passage used.

**Required fix.** Persist immutable source coordinates, authorise them against
the current account/workspace, resolve supported document offsets, and report
deleted, changed, unsupported, or inaccessible sources honestly.

**UI when closed.** Memory **View source** and generated-file provenance open
the existing inspector at a highlighted passage with document title, source
status, and **Open conversation/document**. Missing provenance renders an
explicit unavailable state, never a dead action.

---

## BUG-28 — Generated artifacts have no general download surface

**Status: open; audited from FIXED-45.**

**Required fix.** Add an authorised byte-download endpoint with safe filenames,
content disposition, retention checks, audit evidence, and no inline execution
for active formats.

**UI when closed.** Generated artifact cards and the file inspector provide a
**Download** action with size/type, progress, completion, retention-expired,
permission-denied, and unavailable states. Download remains distinct from
Preview and from conversation export.

---

## BUG-29 — Governed memory proposals, scope changes, and history lack APIs

**Status: open; found while implementing FIXED-49.**

**Observed.** The Memory API can list records and mutate text/pin/search/expiry,
but it cannot approve, edit-and-approve, reject, change scope with renewed
consent, report last use, distinguish logical forget from permanent deletion,
or return a complete per-memory audit history.

**Required fix.** Implement exact-record proposal decisions, sensitivity and
scope transitions, usage/review timestamps, stale/conflict checks, logical
forget plus separately governed permanent deletion, and append-only history.

**UI when closed.** Pending cards provide **View source**, **Reject**,
**Edit and approve**, and **Approve**. Approved cards provide **Edit scope**,
**View history**, review/expiry controls, last-used status, **Forget memory**,
and a separately confirmed **Delete permanently** where policy allows.

---

## BUG-30 — Knowledge Map source review and large-workspace persistence are incomplete

**Status: open; found while implementing FIXED-49.**

**Observed.** The redesigned graph now provides force-directed placement,
global/local scopes, depth traversal, relationship inspection, type/status
querying, colour groups, fit/zoom/full-screen controls, and display/force/motion
settings. Server-side containment still validates only a typed
workspace-relative path: the browser has no file/folder chooser or pre-index
review. View settings and pinned positions are not yet persisted per workspace,
and project/date filtering, cluster summaries, indexed-file status, re-index,
and advanced-record disclosure still need richer graph DTOs.

**Required fix.** Add a server-backed contained source browser and review plan
with supported/unsupported counts before indexing. Extend graph DTOs with
project, dates, provenance, relationship metadata, indexing state, and cluster
summaries; preserve selection and viewport across incremental refresh.

**UI when closed.** **Add workspace source** opens Choose file/folder → review
→ Add and index. Sources show indexed counts, warnings, last indexed, Re-index,
and Remove. Saved positions, zoom, groups, filters, motion, and force settings
restore per workspace; project clusters and Standard/Advanced modes expose the
richer records with full keyboard and screen-reader access.

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

## BUG-31 — Remote and cloud execution environments remain unavailable

**Status: open; audited from FIXED-47 and B20.**

**Observed.** Local no-network container execution is shipped, while governed
remote and cloud executor gates remain disabled and have no executor.

**Required fix.** Implement owner-selected remote/cloud isolation with scoped
credentials, immutable environment identity, network/secret/mount policies,
resource budgets, cancellation, artifact return, and complete audit evidence.

**UI when closed.** Settings → Runtime configuration lists Local container,
Remote, and Cloud environments with availability, health, isolation summary,
cost/budget, last change, and role restrictions. Work composers show the
selected environment and block start with actionable configuration guidance.

---

## BUG-32 — Terminal approval remains metadata-only

**Status: open; audited from FIXED-08.**

**Observed.** The terminal client's `/approve` can resolve metadata without an
authenticated web session, so it cannot execute the bounded approval relay or
resume work. Approval-gated `shell` likewise remains record-only.

**Required fix.** Add authenticated terminal approval and exactly-once relay
support without weakening session-revocation, capability, command containment,
or STOP checks.

**UI when closed.** The terminal prints an exact effect preview, requires an
authenticated confirmation, then shows **Executing**, bounded output/result,
and **Continuing turn** or a precise refusal. The web Approvals history records
the terminal principal and identical execution evidence.

---

## BUG-33 — Local context capacity has no scheduled refresh or administrator override UI

**Status: open; found while implementing FIXED-50.**

**Observed.** Runtime capacity is refreshed when an owner explicitly opens a
provider's model catalogue. Raiker preserves an exact profile-level
`context_window_tokens` fallback, but there is no periodic local refresh,
freshness timestamp in Models, or governed browser workflow for setting that
fallback when an older or custom runtime exposes no supported metadata field.

**Required fix.** Add a bounded local-only refresh schedule and last-known-good
capacity history keyed by endpoint identity, provider, model, and relevant
runtime configuration. Add an audited administrator override with validation,
expiry/review, and a clear precedence below a fresh active-runtime report.
Never silently reuse one model's capacity for another model or endpoint.

**UI when closed.** Models → Details shows capacity, source, endpoint identity,
last checked, freshness, and refresh errors. Administrators can select
**Configure fallback capacity**, enter a positive token limit with a reason,
review the exact provider/model/endpoint scope, save or clear it, and inspect
change history. Chat and Build visibly distinguish **reported by runtime**,
**configured in Raiker**, **stale last-known value**, and **unavailable**.

---

## BUG-34 — A reloaded Chat loses the approval a turn is parked on

**Status: open; found while implementing FIXED-56.**

**Observed.** A restored transcript carries only what is persisted — prompt
text, the agent's response message, and the turn status. `restoredTurn` in
`apps/web/src/lib/views/ChatView.svelte` therefore sets `approval: null`, so a
conversation reopened after a reload shows no **Waiting for approval** card for a
turn that is genuinely still parked. Cross-tab continuation (FIXED-56) then has
nothing to attach to in that tab: the watcher only polls while this surface
believes it has a parked turn, so a reloaded Chat cannot continue a turn it can
no longer see is waiting.

**Required fix.** Persist and restore the approval a turn is parked on, keyed to
the turn, and rehydrate it alongside the transcript so a reopened conversation
presents the same parked state a live one does. The read must stay
principal-scoped and metadata-only, exactly like `/api/approvals/resumable`.

**UI when closed.** Reopening a conversation whose turn is parked shows the same
**Waiting for approval** card, with the same **Review approval** and recoverable
**Continue now** actions, and continues automatically once a decision is
recorded anywhere — with no difference in behaviour between a live tab and a
reloaded one.

---

## BUG-35 — The Build composer cannot carry a file

**Status: open; found while reviewing composer parity for FIXED-53 to FIXED-56.**

**Observed.** Chat's composer attaches workspace paths, images, and documents
through the governed attachment store. Build's composer attaches only the
selected repository's local subpath, automatically. An owner working in Build who
wants to hand Raiker a design document, a failing log, or a screenshot has to
start the work in Chat instead, and the two conversation surfaces are otherwise
deliberately identical.

**Required fix.** Give Build the same attachment control Chat has, over the same
governed store and the same fail-closed server-side validation, without
duplicating the composer — the attachment logic is the same code in both places
or it will drift.

**UI when closed.** Build's composer offers the same **+** control, the same
chips with the same inspector behaviour, and the same limits and error copy as
Chat's, so what an owner learns on one surface is true on the other.

---

## BUG-36 — Nothing keeps the two shipped model-profile copies in step

**Status: open; found while fixing BUG-21 (see FIXED-57).**

**Observed.** `config/model-profiles.json` and `raiker/config/model-profiles.json`
are separate files with the same content. `_read_config_text` prefers the
workspace-relative path and falls back to the packaged resource, so the
repository-root copy silently wins. An edit applied to only one of them appears
to do nothing, with no error and no warning — which is exactly how a price
correction could be believed applied while the runtime still charges the old
rate.

**Required fix.** Make one copy authoritative, or add a check that fails the
build when the two diverge. Whichever is chosen, a shipped rate must not be able
to differ from the rate the runtime reads. The same review discipline needs to
extend to the rates themselves: shipped list prices carry an `as_of` date and
now feed a registry that dates them, but nothing yet prompts a human to
re-verify them on a cadence.

**UI when closed.** Models → Pricing states when each shipped documented rate
was last reviewed by a human, distinct from when it was last synchronised, and
flags a rate whose review is overdue.

---

## GAP-BUILD — What Build needs to stand against a class-leading coding agent

**Status: analysis, not a defect.** Nothing below is broken; this is the
distance between what Build ships today and the bar set by the best autonomous
coding agents — the ones that read a repository, make the change, run the tests,
read the failure, and iterate until it is green, in one uninterrupted session.

Build already clears part of that bar. It runs a genuine agentic loop
(`raiker/runtime/orchestrator.py`, model → tool call → broker → model, capped by
`max_tool_calls`, default `10_000` in `raiker/contracts/models.py`), its read
tools really execute, and its Plan/Edit/Auto modes are enforced by the runtime
rather than by prompt wording (`apps/web/src/lib/buildModes.ts` sets the
per-capability decision mode server-side, so a write proposed in Plan mode is
refused by the policy engine). The governance, audit and checkpoint story is
*ahead* of the field, not behind it.

The gap is that **Build cannot close a loop.** Everything below follows from
that, and the order is the order they should be done in — each tier is worthless
without the one above it. B1 (FIXED-08), B2 (FIXED-09), and B3's defined core
scope (FIXED-23) have since been completed:
an approved file change is really written, and the turn continues through the
approval instead of ending at it; Build can now make a narrow, hunk-level edit.

### Tier 0 — the blocking three (without these, nothing else matters)

**B1. An approved action must actually execute.** ✅ **Done — see FIXED-08.**
The Approvals resolution path now invokes `ApprovalExecutionRelay` for
`file_write_execution` and `patch_apply_execution`, so an approved file change
is genuinely written, re-governed at execution time, and checkpointed first.
Build is no longer a proposal generator for file work.

**What is left of B1:** `shell` is still metadata-only on resolution, and that
is deliberate — a command is neither local-only nor reversible, so it belongs
with B5 (a narrow, owner-defined command allowlist under its own capability)
rather than with the file relay. The executed/refused outcome is now threaded
back into the transcript as a real tool result by B2 (FIXED-09).

**B2. The turn resumes after an approval.** ✅ **Done — see FIXED-09.** The loop
parks its working state against the approval and picks the same turn up on
resolution, with the real result (or an honest refusal) appended as the tool
result. Build no longer stops dead at its first write.

**B3. Real patch application.** ✅ **Complete — see FIXED-23, FIXED-29, and
FIXED-34.** `edit_file` now replaces
`old_text` only when it occurs exactly once, and `apply_patch` calculates a
unified-diff candidates from exact hunk context before the approval is
displayed or an execution is allowed. A missing, ambiguous, or stale match
fails closed with a machine-readable error; rejected patch hunks are named and
no partial candidate is written.

**B3 expansion scope.** ✅ **Done — see FIXED-29 and FIXED-34.**
Create/delete patches, coordinate-guided context offsets, empty-context
insertions, and `\\ No newline at end of file` are supported with the same
all-or-nothing candidate used for preview and execution. Multi-file diffs now
use one combined approval, an atomic execution transaction, and per-path
checkpoint evidence under the same governed action.

### Tier 1 — loop mechanics

**B4. Parallel tool calls are silently dropped.** ✅ **Done — see FIXED-39.**
Every validated read-only proposal in a model response now runs concurrently
and every result is returned under its matching call id in one provider-valid
batch. Mutations remain serial and stop at the first approval or policy
boundary. Budget- or boundary-deferred calls emit `model_tool_calls_dropped`
with proposed/accepted/dropped counts, so no call disappears without evidence.

**B5. Test/command feedback channel.** ✅ **Done — see FIXED-44 and FIXED-47.**
A standing, expiring, revocable per-session
command-prefix grant now returns bounded stdout/stderr and exit status with the
workspace as cwd and a wall-clock cap. Anything outside the grant falls back to
the approval-gated shell path. Granted commands execute in a no-network,
resource-bounded container and never fall back to the host.

**B6. No task/plan state across the loop.** Nothing tracks what the agent
intends to do next, so a long change has no visible spine and no recovery point
after a failure. **Work:** a lightweight, model-visible plan structure (ordered
steps with a status each), rendered in Build as a live checklist. `raiker/tasks`
already stores tasks; this is a turn-scoped sibling, not a scheduled task.

**B7. No subagents at the model's disposal.** `raiker/agents/subagents.py`
implements bounded subagent contracts, and `raiker/agents/orchestration.py`
already defines a narrower tool set for them, but no spawn tool is exposed in
`_MODEL_EXPOSED_TOOLS`. **Work:** expose a governed `spawn_subagent` (bounded
tokens, tool subset, no egress widening, results returned as untrusted data) so
wide searches stop consuming the main context.

**B8. MCP tools are unreachable.** See BUG-12 — connected servers are a
monitoring surface only. Every third-party capability the ecosystem offers is
therefore unavailable to Build.

### Tier 2 — what the agent can see

**B9. No repository index.** Every turn starts cold: no symbol index, no code
map, no embeddings over the tree. `graph_indexing_enabled` and
`semantic_memory_writes_enabled` are hardcoded `False`
(`raiker/context/gatherer.py`), and `retrieve_hybrid_memory` — lexical + vector
+ graph, already written in `raiker/memory/retrieval.py` — is called only by the
evaluation harness. On a large repository the agent greps blind.
**Work:** build the code map described in
`docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md` on repository connect, refresh it
incrementally on approved writes, and inject the top-ranked slices into the turn
bundle as scoped, untrusted context.

**B10. No language intelligence.** No symbol lookup, no
definition/reference navigation, no type or lint feedback loop. **Work:** an
LSP-backed read tool set (`find_definition`, `find_references`,
`document_symbols`, `diagnostics`) — read-only, so it needs no approval path.

**B11. No git write path.** `git_status`, `git_diff` and `git_log` are exposed;
branch, commit, push and pull-request creation are not. The agent can describe a
change it can neither commit nor propose. **Work:** governed
`git_branch` / `git_commit` (high risk, approval, diff preview) and a
`github_write` bound to the existing connector credential and egress allowlist.

**B12. No web access.** No fetch and no search anywhere in `_TOOL_RISK`, so the
agent cannot read the documentation for a library it is being asked to use.
**Work:** an egress-allowlisted `web_fetch` returning sanitised text as
untrusted data; search behind the same gate, off by default.

### Tier 3 — the workspace surface (UI/UX)

Build's transcript is a chat column plus a background-work rail
(`BuildSidePanel.svelte`) and a "Waiting on you" decisions block. A coding agent
needs a workbench.

**B13. No file tree and no editor.** `ProjectTreeNode.svelte` exists but Build
mounts no explorer, so a user cannot see the repository the agent is working in,
open a file, or read the result of a change without leaving the app.
**Work:** a resizable left explorer over the connected repository plus a
read-only viewer with syntax highlighting, promoted to an editor once B1 lands.

**B14. No diff review surface in Build.** The unified diff lives in the
Approvals inbox, in a different route — so the core act of coding review is a
context switch away, and it is all-or-nothing: no per-hunk accept, no edit
before accept, no partial rejection. **Work:** an inline side-by-side diff in
the Build transcript with per-hunk accept/reject and an "edit then accept" path,
resolving straight into the existing approval record.

**B15. No terminal or output pane.** Command output, once B5 lands, has nowhere
to stream. **Work:** a collapsible output pane with live streaming, exit status,
and a jump-to-failure affordance.

**B16. Tool activity is buried.** Tool events render inside a collapsed
governance `details`, so during a long turn the transcript looks idle.
**Work:** promote tool calls to first-class transcript rows — file read, files
matched, command started — with a progress affordance, keeping the full
governed record in the disclosure.

**B17. No way to stop or steer a running turn.** `POST /api/interrupts` exists
and `api.interrupt` is already in `apps/web/src/lib/api.ts`, but no view calls
it. A turn heading the wrong way must be waited out. **Work:** a Stop control on
the composer while streaming, and a queued-steer input that appends to the
running turn at the next safe boundary.

**B18. No checkpoint or rewind control where the work happens.** Checkpoints are
recorded and browsable in their own route, but Build offers no "rewind to before
this turn" — the one control that makes an autonomous agent safe to let run.
**Work:** a per-turn rewind in the transcript, restoring workspace and
conversation state from the existing checkpoint manifest.

**B19. Composer ergonomics.** No `@`-mention autocomplete for workspace files
(attaching a path means typing it exactly), no slash commands, no keyboard
shortcut map, no copy button on code blocks, no syntax highlighting in
transcript code (deliberately deferred in FIXED-06), no message edit-and-resend,
no regenerate. Each is small; together they are most of the felt difference in
daily use.

**B20. Sandboxed execution environment.** ✅ **The local container slice is
implemented; remote and cloud execution remain separate future capabilities.**
Owner-granted B5 commands now use the same Docker boundary principles with
networking disabled and fail closed when its approved image is unavailable.

### Suggested order

B1 → B2 → B3 make Build an agent. **B1, B2, and B3's defined core scope are
now landed**: an approved change is really made, the turn continues through
it, and B3 uses strict, hunk-level editing instead of a whole-file rewrite.
B3's multi-file patch transaction has landed. B4–B6 make
the loop efficient. B13–B16 make the result
reviewable. Everything else is depth. B20 is a *policy* decision before it is an
engineering one and belongs to the owner, not to an implementer.

---

## GAP-CHAT — What Chat needs to work as a general agentic work assistant

**Status: analysis, not a defect.** Chat is intended to be more than a chat box:
an assistant that works across the owner's documents, mail, calendar, chat
tools and schedule, produces real files, and keeps working while the owner is
away. This entry states the distance to that bar.

Chat already clears real parts of it. Turns stream with conversational status;
conversation memory within a chat works (FIXED-04); documents and images upload
and reach the model; projects carry instructions and approved memory; chat
search covers titles and message text; and — genuinely ahead of the field —
`raiker/tasks/scheduler.py` runs *due tasks as governed turns* on `continuous`
(20 min), `hourly`, `daily` and `weekly` cadences, re-arming after each cycle,
so standing routines are already real rather than aspirational.

Three things stop it being a work assistant: it cannot produce an artifact, it
cannot act on the tools it can read, and it cannot remember across the work.

### Tier 0 — the blocking three

**C1. First-class document output.** ✅ **Done — see FIXED-40 and FIXED-43.**
`create_document` creates Markdown, DOCX, XLSX, and PDF artifacts locally
without a file-creation approval prompt. The completed document is preserved in
the owner-scoped attachment store, bound to its exact trusted session/turn, and
shown by the existing Chat inspector.

**C2. Acting in the owner's tools.** ✅ **Complete for repeated manifest-driven
execution — see FIXED-37 and FIXED-41.**
This is the one place the approval loop is already closed end to end, and it
should be read as the precedent for C1 rather than as a gap in itself:
`github_read`, `gmail_read`, `gcal_read`, `slack_read` and `connector_read`
execute directly; a `connector_write` proposed by the model is parked as a
`connector_write_intents` row (`raiker/tools/broker.py`) with the honest
`expected_effect` *"Approving executes this exact connector mutation once"*, and
resolving that approval really does call `ConnectorInvoker.invoke`, returning
`"status": "executed", "executes_action": true`
(`raiker/api/routes_approvals.py`). Approved connector mutations are sent.

Only manifest-declared operations of an enabled, credentialed connector are
reachable. That boundary is now visible: the Connector Store publishes each
registered read/write operation and its confirmation posture, and approvals
show the exact redacted outbound arguments before execution. The existing
standing-grant manager supports connector/operation-shaped scope patterns, and
FIXED-38 adds explicit manifest compensation metadata without inventing undo for
operations that do not declare it. Multiple read calls execute together; write
calls remain ordered and each consumes its own approval exactly once.

**C3. Recall outside the current chat.** ✅ **Done — see FIXED-42.** The
read-side `memory_search`, `memory_list`, and `memory_get` tools are model-visible
without approval. Context gathering runs owner-scoped hybrid retrieval and adds
bounded, attributed metadata for old Chat and Build sessions and Projects,
including archived work; approved memory text is labelled untrusted. Incognito
is an absolute opt-out. Durable writes retain the existing privacy posture: the
model proposes a candidate and the owner accepts it rather than Raiker silently
remembering.

### Tier 1 — working with the owner's material

**C4. File inspector — done for attachments and generated files.** FIXED-10 shipped Tasks 1–2 of
`docs/superpowers/plans/2026-07-26-chat-file-inspector.md`: chips are buttons and
open a session-authorized, view-only pane, reusing the sanitising renderer from
FIXED-06 for the Markdown case. FIXED-19 and FIXED-20 record a supported,
newly generated file against its exact session and turn so it uses that same
pane. FIXED-45 revalidated uploaded and newly generated files across supported,
unsupported, unavailable, cross-account, and cross-session cases. **Remaining
work:** an assistant that reads a document should also be able to show and
highlight *the passage it used*.

**C5. Chat file output — done.** FIXED-19 keeps per-response copy but removes
per-chat Markdown download and browser print/Save as PDF. Generated artifacts
and stored attachments use the right-hand inspector rather than a general
download surface; FIXED-20/FIXED-22 preserve artifacts once without automatic
deletion. FIXED-45 adds the response-linked generated-document card and explicit
preview action.

**C6. No citations on tool-derived answers.** When an answer comes from an
email, a calendar entry or an attached document, the transcript does not say
which one. For an assistant acting on the owner's real data this is a
correctness feature, not a nicety. **Work:** carry source ids through the tool
result into the response and render an inline, clickable provenance chip.

**C7. No web access.** As B12 — the assistant cannot look anything up. For a
work assistant this is the difference between answering and guessing.

**C8. MCP tools unreachable.** As BUG-12/B8. Every connector the owner adds
through the ecosystem stays a monitoring entry.

**C9. No skills or reusable procedures.** `raiker/skills/` holds a candidate
store and nothing else; `docs/SELF_IMPROVEMENT_MODEL.md` describes procedural
memory that is never consulted at turn time. A work assistant should learn "how
we do the weekly report here" once. **Work:** promote approved procedural
memories into a named, model-selectable skill set, injected only when relevant.

### Tier 2 — presence and continuity

**C10. The assistant lives in one browser tab.** `config/channel-connectors.json`
declares cli, tui, rest, web_ui, desktop, dashboard, ide, apple_mobile,
android_mobile and webhooks — but `external_channels_enabled` and
`notifications_enabled` are both hardcoded `False`
(`raiker/context/gatherer.py`), so there is no mail, chat-tool or mobile surface
where the assistant reaches the owner. Scheduled routines therefore run and
finish with nobody told. **Work:** enable the notification path first (it is the
cheapest and it makes routines useful), then one external channel end to end.

**C11. Background work is not conversational.** Scheduled and background tasks
run as isolated turns; their output lands in a task record, not in a thread the
owner can reply to. **Work:** file each routine's cycle into a durable
conversation, so "what did the overnight run find?" is answerable in Chat and a
reply steers the next cycle.

**C12. No collaboration.** No sharing of a chat, a project, or a document; no
second participant; no per-recipient scoping. Governance is built for a single
owner, so this is a genuine architectural decision rather than a missing screen —
`docs/NESTED_BOUNDARIES_ARCHITECTURE.md` is the place it has to be answered.

### Tier 3 — conversation surface (UI/UX)

**C13. No stop or steer.** As B17: `POST /api/interrupts` and `api.interrupt`
exist; nothing calls them. A long turn cannot be stopped.

**C14. No message-level actions.** No copy, no edit-and-resend, no regenerate,
no branch-from-here, no per-message feedback. Editing a prompt and re-running is
the most-used control in an assistant of this kind.

**C15. Attachments are one-way.** The composer uploads; the transcript cannot
hand a file back (C1), preview one (C4), or let the owner drag one out.

**C16. Voice is a label.** The control is present and marked "(coming soon)" —
honest, but a work assistant used from a phone needs dictation and, ideally,
read-back.

**C17. Recall is invisible.** Once C3 lands, the owner must be able to see what
was remembered, why it was injected, and correct or forget it inline. The
Memory route exists for management; the *moment of use* is in Chat.

**C18. No cross-chat surface.** Chat search covers titles and message text only.
There is no "what am I working on", no cross-project view, no resumption of the
threads a routine is advancing.

### Suggested order

C1 and C2 make Chat capable of work — C1's blocking half has landed (FIXED-08),
leaving document output; C3 makes it feel like it knows the owner;
C10/C11 make it present when the owner is not watching. C4–C6 and C13–C15 are
the daily-use polish that determines whether any of it gets used. C2, C3(3),
C10 and C12 are owner policy decisions before they are implementation tasks.

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
