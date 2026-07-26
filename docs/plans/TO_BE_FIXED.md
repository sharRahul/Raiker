# To be fixed

Defects and gaps found while executing
[the live manual test plan](RAIKER_LIVE_MANUAL_TEST_PLAN.md) against a running
`raiker-web` on **2026-07-26**, hosted Anthropic `claude-haiku-4-5-20251001`.

Each entry states what was observed, the reproduction, the root cause in code,
and the proposed fix. Three are marked **FIXED** and were resolved on this
branch; the rest are open and deliberately left for a maintainer decision
because they touch security controls or unshipped features.

Evidence: [`screenshots/not-working/`](screenshots/not-working) (defects),
[`screenshots/working/`](screenshots/working) (verified behaviour).

| ID | Severity | Area | Status |
|---|---|---|---|
| FIXED-01 | High | Models | Fixed |
| FIXED-02 | High | Chat / API redaction | Fixed |
| FIXED-03 | Medium | Models / Chat / Build | Fixed |
| FIXED-04 | **Critical** | Chat orchestration | Fixed (was BUG-02) |
| FIXED-05 | High | Models / policy | Fixed |
| BUG-03 | High | Chat rendering | Open |
| BUG-04 | High | API redaction | Open |
| BUG-06 | Medium | Approvals | Open (by design — needs a decision) |
| BUG-07 | Medium | Chat | Open (specified, unimplemented) |
| BUG-08 | Medium | Export | Open (not specified) |
| BUG-09 | Medium | Tasks | Open |
| BUG-10 | Low | Chat / Tasks | Open |
| BUG-11 | Medium | Permissions | Open |
| BUG-12 | High | MCP | Open (specified, unimplemented) |
| BUG-13 | Low | Permissions | Open |

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

## BUG-03 — Markdown is not rendered in Chat

**Observed.** Asked for a markdown document; the reply bubble showed literal
`# Quarterly Report`, `- bullet`, `| Metric | Value |` and ``` fences as plain
text. DOM audit of the transcript: `h1: 0, table: 0, pre: 0, code: 0, ul: 0`.
`not-working/BUG-03-chat-markdown-not-rendered.png`.

**Impact.** Every code block, table, and list a model produces is unreadable.
This is the single most visible quality gap in the product.

**Proposed fix.** Render assistant text through a sanitising markdown renderer.
The file-inspector design already specifies the security posture to reuse:
*"Markdown is sanitized before rendering"* and *"Preview renderers never execute
embedded code or macros."* Escape first, allow a fixed tag set (headings, lists,
tables, `pre`/`code`, links with `rel="noopener noreferrer"`), never `innerHTML`
of raw model output.

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
"Export as Markdown". "One-click Markdown → PDF" additionally needs BUG-03
(rendering) and a print stylesheet; browser print-to-PDF over the rendered
transcript is the cheapest honest implementation.

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
