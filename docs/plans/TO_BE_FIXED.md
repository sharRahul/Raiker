# To be fixed

Defects and gaps found while executing
[the live manual test plan](RAIKER_LIVE_MANUAL_TEST_PLAN.md) against a running
`raiker-web` on **2026-07-26**, hosted Anthropic `claude-haiku-4-5-20251001`.

Each entry states what was observed, the reproduction, the root cause in code,
and the proposed fix. Two were fixed in the same change and are marked
**FIXED**; the rest are open and deliberately left for a maintainer decision
because they touch security controls or unshipped features.

Evidence: [`screenshots/not-working/`](screenshots/not-working) (defects),
[`screenshots/working/`](screenshots/working) (verified behaviour).

| ID | Severity | Area | Status |
|---|---|---|---|
| FIXED-01 | High | Models | Fixed |
| FIXED-02 | High | Chat / API redaction | Fixed |
| BUG-02 | **Critical** | Chat orchestration | Open |
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

**Remaining work (not done here).** The meter is still labelled *"Estimated from
this chat's text"* because no configured profile supplies provider-reported
prompt usage. `docs/superpowers/plans/2026-07-26-chat-composer-context-controls.md`
Task 2 (session usage ledger, cost, weekly quota, 90 % compaction) is still open.

---

## BUG-02 — Chat has no conversation memory at all *(critical)*

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

**Proposed fix.** Load the session's prior turns in the gateway and append them
as alternating `user`/`assistant` `ModelMessage`s before the current prompt,
bounded by the profile's context window, with the existing checkpoint and
compaction machinery trimming the head. This is the natural consumer of Task 2 in
the composer-context plan and should land with it.

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
