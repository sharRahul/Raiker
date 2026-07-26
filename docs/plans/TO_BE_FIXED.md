# To be fixed

Defects and gaps found while executing
[the live manual test plan](RAIKER_LIVE_MANUAL_TEST_PLAN.md) against a running
`raiker-web` on **2026-07-26**, hosted Anthropic `claude-haiku-4-5-20251001`.

Each entry states what was observed, the reproduction, the root cause in code,
and the proposed fix. Six are marked **FIXED** and were resolved on this
branch; the rest are open and deliberately left for a maintainer decision
because they touch security controls or unshipped features.

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
| BUG-04 | High | API redaction | Open |
| BUG-06 | Medium | Approvals | Open (by design — needs a decision) |
| BUG-07 | Medium | Chat | Open (specified, unimplemented) |
| BUG-08 | Medium | Export | Open (not specified) |
| BUG-09 | Medium | Tasks | Open |
| BUG-10 | Low | Chat / Tasks | Open |
| BUG-11 | Medium | Permissions | Open |
| BUG-12 | High | MCP | Open (specified, unimplemented) |
| BUG-13 | Low | Permissions | Open |
| GAP-BUILD | — | Build — coding-agent parity | Analysis (20 items) |
| GAP-CHAT | — | Chat — work-assistant parity | Analysis (18 items) |

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

## BUG-04 — Over-broad redaction destroys legitimate assistant text and chat titles

**Observed.** Attached `sample.md` containing "The secret project code is
ORCHID-9" and asked what the code was. The reply rendered as:

> I can see from the workspace context that there's an attached document
> (sample.md**\*\*\*REDACTED\*\*\*** comes directly from the uploaded markdown
> file that was provided in the attachment.

and the conversation's title in **RECENT CHATS** became literally
`***REDACTED***`. `not-working/BUG-04-response-text-over-redacted.png`.

**Root cause.** `raiker/api/redaction.py::_redact_value`, string branch: after
`redact_text` finds no actual secret pattern, it *still* replaces the **entire
string** if it merely contains the substring `secret`, `token`, `password`,
`bearer`, or `authorization`. Ordinary English prose is destroyed.

**Why this is not fixed here.** The heuristic is a deliberate belt-and-braces
defence and weakening it is a security decision, not a bug fix. It needs an owner
call, so it is written up rather than changed.

**Proposed fix (for review).** Restrict the substring heuristic to values found
**under a secret-like key**, and rely on `redact_text`'s pattern matching (which
recognises real credential shapes) for free-form text. Optionally redact only the
matched span rather than the whole string. Add tests proving `sk-ant-…` in prose
is still caught while "the secret project code is ORCHID-9" survives.

---

## BUG-06 — Nothing in the app can actually write a file

**Observed.** Chat proposes `write_file` → Approvals shows the exact diff →
**Approve (record only)** returns `executes_action: false` and the response says
*"Recorded: approved. The action was NOT executed (metadata-only)."* The file is
never created. Enabling `approval_execution_relay` did not change this.
`not-working/BUG-06-approval-never-executes.png`.

**Assessment.** This is the documented model
(`README.md`: "Approval resolution is metadata only by default"), so it is
honest — but it means "generate a markdown file and view it" is not achievable
today, and Build's premise ("every file write, patch, and command becomes a
decision you accept or reject") cannot complete its loop.

**Needs a decision.** Either wire the approval-execution relay through to real
execution for `file_write_execution` in `local_single_user_runtime`, or state
plainly in Chat/Build that accepted proposals are recorded, not performed.

---

## BUG-07 — No file inspector; attachment chips are not interactive

**Observed.** An uploaded `sample.md` renders as a chip inside the user bubble.
It is not a `button`, has no `role`, and clicking it does nothing. There is no
right-side pane and no overlay.

**Assessment.** Matches the implementation note in
`docs/superpowers/plans/2026-07-26-chat-file-inspector.md`: *"This feature is
specified but not implemented."* Tracked here so the gap is visible from the
product side. The plan's Tasks 1–2 are the fix.

---

## BUG-08 — No export path at all (no PDF, no download, no print)

**Observed.** Swept every `button`/`a` in the app for `pdf|export|download|save
as|print`. The only match anywhere is Memory's JSON import/export. There is no
way to get a chat, a document, or a generated artifact out of Raiker as a file.

**Proposed fix.** Smallest useful version: a per-message "Copy" and a per-chat
"Export as Markdown". "One-click Markdown → PDF" now needs only a print
stylesheet — the rendering half is done (FIXED-06); browser print-to-PDF over
the rendered transcript is the cheapest honest implementation.

---

## BUG-09 — A background-agent run reported `Task failed` with no user-facing reason

**Observed.** The "Manual test Background agent" task produced a real response
and a checkpoint, then the audit log recorded `Task failed` (`task_manager`).
Tasks still showed the task as `queued`; nothing in the UI said what failed or
why.

**Proposed fix.** Surface the task's terminal reason on the task card and in
Observability → Work in action. A run that produced a completed response should
not be able to end `failed` with an empty summary.

---

## BUG-10 — Task runs pollute RECENT CHATS

**Observed.** After creating tasks, an entry titled **Inbox** appeared in the
sidebar's RECENT CHATS beside real conversations, and task-run sessions appear in
Sessions with the task's prompt as the title.

**Proposed fix.** Tag task-created sessions with their origin and exclude them
from the RECENT CHATS list (they remain reachable from Tasks and Sessions).

---

## BUG-11 — A surface blocked by runtime mode does not say so

**Observed.** With `mcp_builder_runtime` and `mcp_connector_runtime` set to
`enabled_policy_gated`, the MCP tab still said *"The MCP builder and connector
capabilities are disabled. Enable them in Capabilities to create or test
servers."* — but they **were** enabled in Capabilities. The real blocker was that
`runtime_enabled` requires `enabled_runtime`, which requires a runtime-enablement
mode (Settings → Runtime mode). Following the message's own advice does not
resolve it.

**Proposed fix.** When a gate is enabled but not at `enabled_runtime`, say so:
*"Enabled, but not at runtime level — activate a runtime mode in Settings →
Runtime mode."* with a link. Applies to every `runtime_enabled` consumer, not
just MCP.

---

## BUG-12 — MCP servers cannot be used by the agent

**Observed.** Created and connected a governed local MCP server from the Sample
echo template; **Test** reported `connected · 2 tool(s)` (`echo`,
`workspace_ping`) and recorded a monitored session. The model can never call
them: `raiker/models/tool_call_validation.py::_MODEL_EXPOSED_TOOLS` is a fixed
frozenset, and there is no `mcp` reference anywhere in
`raiker/runtime/orchestrator.py`, `raiker/tools/broker.py`, or
`tool_call_validation.py`.

**Impact.** MCP is a management/monitoring surface only. A user who follows the
UI to connect a server reasonably expects its tools in Chat.

**Proposed fix.** Project the tools of connected, non-contained MCP servers into
the per-turn tool specification with a namespaced id (`mcp__<server>__<tool>`),
route execution through `ToolBroker` so the existing policy, approval, and audit
path applies unchanged, and treat every result as untrusted data — the same
framing the GitHub/Gmail connectors already use.

---

## BUG-13 — "Confirmation token" is unexplained in the step-up dialog

**Observed.** Enabling a tier-2 capability requires a *"Confirmation token
(required to enable this capability)"* with no hint about where to obtain one.
The backend
(`raiker/runtime/authority/activation.py`) only checks that the field is
non-empty — it is a deliberate human-intent speed bump, not a secret. A user is
likely to stop here believing they lack a credential they never had.

**Proposed fix.** Reword to *"Type any phrase to confirm you intend this change.
It is recorded with your decision."*

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
without the one above it.

### Tier 0 — the blocking three (without these, nothing else matters)

**B1. An approved action must actually execute.** *(depends on BUG-06)*
Today `write_file`, `edit_file`, `apply_patch` and `shell` are all
`("high", True)` in `raiker/models/tool_call_validation.py`, and approval
resolution is metadata-only, so no file is ever written and no command ever
runs. `ApprovalExecutionRelay`
(`raiker/runtime/executors/tier1_approval.py`) already implements the hard part
correctly — TTL check, argument-hash TOCTOU check, posture check, atomic
`pending → executing → executed` transition, and re-routing through
`RuntimeAuthority` so the target re-passes its own gate and policy review at
execution time. **Work:** wire the Approvals resolution path to invoke the relay
for `file_write_execution` and `patch_apply_execution` when the owner has
enabled it, and surface the executed/refused outcome in the transcript. Until
this lands, Build is a proposal generator.

**There is already a working precedent in the codebase.** A model-proposed
`connector_write` is parked as a `connector_write_intents` row and, on approval,
is genuinely executed by `ConnectorInvoker.invoke`
(`raiker/api/routes_approvals.py`), returning `executes_action: true`. File
writes take the other branch and report *"Approval resolution is metadata-only
and does not execute the action"* (`raiker/tools/broker.py`). So the question is
not whether the architecture can execute an approved action — it demonstrably
can, through the audited path — but whether the owner wants that door open for
the filesystem and the shell as well.

**B2. The turn must resume after an approval.** The loop `break`s on
`needs_approval` (`raiker/runtime/orchestrator.py`) and the turn returns. Even
once B1 lands, the agent stops dead at its first write and the user must
re-prompt to continue — which discards the model's working state and re-pays for
the context. **Work:** persist the suspended loop state against the approval id,
and on resolution resume the same turn with the tool result appended (approved →
the real result; rejected → a refusal the model can react to). This is the
single highest-value change in this document: it converts a one-shot proposer
into an agent.

**B3. Real patch application.** `edit_file_content` is literally
`return write_file_content(...)`, and `apply_patch_content` writes `new_text`
over the whole file (`raiker/tools/filesystem.py`). Despite the names, there is
no hunk-level editing: the model must reproduce an entire file to change one
line, which is slow, expensive, and the dominant source of accidental deletion
in long files. **Work:** a `str_replace`-style tool (old string + new string +
uniqueness check, failing closed on an ambiguous match) and a true unified-diff
applier with context matching and a rejected-hunk report. Both are already
covered by the existing approval preview, which renders a diff.

### Tier 1 — loop mechanics

**B4. Parallel tool calls are silently dropped.** The orchestrator takes
`response.tool_calls[0]` and ignores the rest. A model that asks to read six
files in one round gets one read and no signal that five were discarded.
**Work:** execute every proposed call in the response — concurrently for
read-only tools, serially for anything mutating — and return all results in one
batch. Emit a `model_tool_calls_dropped` event in the interim so the current
behaviour is at least auditable.

**B5. No test/command feedback channel.** The only way to run anything is
`shell`, which is approval-gated per call, so "run the tests" costs a round trip
through a human on every iteration. **Work:** a standing, per-session grant for
a *narrow* command allowlist the owner defines per repository (e.g. `pytest`,
`npm test`, `ruff`) with the workspace as cwd, no network, and a wall-clock
cap — governed by a new capability so it is opt-in, revocable, and logged, and
falling back to per-call approval for anything outside the list.

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

**B20. No sandboxed execution environment.** `container_execution_enabled`,
`remote_execution_enabled` and `cloud_execution_enabled` are all `False`, so
even after B5 every command runs on the host.
`docs/EXECUTION_ENVIRONMENTS_SPEC.md` specifies the alternative. **Work:**
implement at least the container executor so Auto mode can be genuinely
autonomous without the host as the blast radius.

### Suggested order

B1 → B2 → B3 make Build an agent. B4–B6 make it efficient. B13–B16 make the
result reviewable. Everything else is depth. B1 and B20 are both *policy*
decisions before they are engineering ones and belong to the owner, not to an
implementer.

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

**C1. It cannot produce a file.** *(depends on BUG-06)* Every route to a durable
artifact runs through `write_file`, which is approval-gated and — unlike
`connector_write`, see C2 — metadata-only on resolution, so "draft the report and
save it" cannot complete. The assistant can compose a
document in the transcript and nothing more. **Work:** as B1 — wire approval
resolution to `ApprovalExecutionRelay` for file writes — then add first-class
document output (Markdown now; DOCX/XLSX/PDF generation behind a capability),
written into the session's workspace and listed in the chat.

**C2. Acting in the owner's tools works, but only through one narrow door.**
This is the one place the approval loop is already closed end to end, and it
should be read as the precedent for C1 rather than as a gap in itself:
`github_read`, `gmail_read`, `gcal_read`, `slack_read` and `connector_read`
execute directly; a `connector_write` proposed by the model is parked as a
`connector_write_intents` row (`raiker/tools/broker.py`) with the honest
`expected_effect` *"Approving executes this exact connector mutation once"*, and
resolving that approval really does call `ConnectorInvoker.invoke`, returning
`"status": "executed", "executes_action": true`
(`raiker/api/routes_approvals.py`). Approved connector mutations are sent.

What is missing around it: **coverage and confidence.** Only
manifest-declared operations of an enabled, credentialed connector are
reachable, so "reply to that email", "put it on my calendar" and "post the
summary to the channel" depend entirely on which operations each shipped
manifest declares — and that inventory is not stated anywhere a user can see.
There is also no pre-send preview of the exact outbound request body, no
per-operation standing grant in the UI (`/api/standing-grants` exists as a
route), and no undo window for operations that support one. **Work:** publish
and complete the per-connector write-operation inventory, add the outbound
preview to the approval card, and expose standing grants per operation so a
routine the owner has already blessed does not stop for an approval every
cycle.

**C3. It cannot recall anything outside the current chat.** The turn bundle
(`raiker/context/gatherer.py`) injects session-scoped events, tasks, checkpoints
and approvals plus — only when the session is filed under a project with memory
enabled and incognito off — up to ten approved `project:<id>` memories. There is
no profile-scope memory, no retrieval across chats, and the memory tools
(`memory_search`, `memory_list`, `memory_get`, `memory_write`) exist in
`ToolBroker` but are **absent from `_MODEL_EXPOSED_TOOLS`**, so the model cannot
search its own memory even when the answer is sitting in it. `retrieve_hybrid_memory`
— lexical + vector + graph, in `raiker/memory/retrieval.py` — is called only by
`raiker/memory/evaluation.py`. **Work, in three steps:**
1. expose the read-side memory tools to the model (read-only, no approval);
2. call `retrieve_hybrid_memory` during context gathering, scoped to the owner,
   budgeted, labelled untrusted, with every injected memory attributed in the UI
   so recall is visible and correctable;
3. decide the durable-write posture — today `durable_writes_enabled` is `False`
   and a `memory_write` becomes a candidate awaiting approval. Silent
   remembering is a real privacy decision and belongs to the owner; the
   defensible default is *propose, show, one-click accept*.

Cross-surface recall — "what did we decide in that other chat", "what is that
scheduled routine finding" — is the single largest felt gap versus the field,
and step 2 is most of it.

### Tier 1 — working with the owner's material

**C4. No file inspector.** See BUG-07: attachment chips are inert `span`s. An
assistant that reads documents must be able to show the owner what it read, with
the passage it used. **Work:** the plan in
`docs/superpowers/plans/2026-07-26-chat-file-inspector.md`, Tasks 1–2, reusing
the sanitising renderer shipped in FIXED-06 for the Markdown case.

**C5. No export.** See BUG-08 — no download, print, or PDF anywhere. FIXED-06
removed the blocker on the rendering side; a print stylesheet plus a per-chat
"Export as Markdown" and a per-message copy is now a small change.

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

C1 and C2 make Chat capable of work; C3 makes it feel like it knows the owner;
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
