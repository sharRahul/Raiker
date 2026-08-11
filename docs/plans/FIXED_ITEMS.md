# Fixed items

Every defect and gap that has been **closed**, with the evidence that closed
it. Split out of [`TO_BE_FIXED.md`](TO_BE_FIXED.md) so that document reads as
what it is named for — the open work — while the record of what was fixed, and
why it was fixed the way it was, stays intact and citable here.

Nothing was rewritten in the move. Each entry keeps its original number, its
observation, its root cause, and the user-interface outcome that had to be true
before it could be called closed. An entry that superseded or was superseded by
another says so in place.

The security posture these fixes answer to — **owner-authoritative and
monitored, not prevention-by-restriction** — is stated at the top of
[`TO_BE_FIXED.md`](TO_BE_FIXED.md) and in
[`docs/SECURITY_AND_POLICY.md`](../SECURITY_AND_POLICY.md).

Evidence: [`screenshots/working/`](screenshots/working) (verified behaviour),
[`screenshots/not-working/`](screenshots/not-working) (the defects as found).

| ID | Severity | Area | Status |
|---|---|---|---|
| [FIXED-01](#fixed-01-model-connection-showed-a-raw-reason-codey-to-act-on-it) | High | Models | Fixed |
| [FIXED-02](#fixed-02-context-meter-showed-0-nan-nan-token-counts-stripped-from-the-audit-log) | High | Chat / API redaction | Fixed |
| [FIXED-03](#fixed-03-no-token-or-cost-accounting-models-showed-a-meaningless-percentage) | Medium | Models / Chat / Build | Fixed |
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
| FIXED-101 | High | Chat / Build — governed web access | Fixed (was B12/C7) |
| FIXED-102 | High | Chat / Build — stop and steer a running turn | Fixed (was B17/C13) |
| FIXED-103 | Low | Documentation / README known limits are stale | Fixed (was BUG-58) |
| FIXED-115 | Low | Tests / a shipped-skill check breaks after `compileall` | Fixed (was BUG-56) |
| FIXED-104 | Medium | Context / stale capability flags mislead the model | Fixed (was BUG-57) |
| FIXED-105 | Medium | Documentation / the user guide's "Known limits" are entirely stale | Fixed (was BUG-61) |
| FIXED-106 | Medium | Tasks / an approved task is really created | Fixed (was BUG-62) |
| FIXED-159 | Low | Web / a composer permission control shipped unused | Fixed (was BUG-63, closed with FIXED-155) |
| FIXED-107 | High | Chat / Build — source citations and the passage used | Fixed (was C6 and the last of C4) |
| FIXED-108 | Medium | Storage / session-keyed rows outliving the conversation | Fixed (found while implementing FIXED-107) |
| FIXED-109 | High | Build / Chat — the governed git write path | Fixed (was B11) |
| FIXED-110 | Low | Build / git tools and the selected repository | Fixed (was BUG-66) |
| FIXED-111 | Medium | Build / Chat — the governed push | Fixed (was BUG-67) |
| FIXED-112 | Medium | Runtime / an unperformable proposal raised as a decision | Fixed (found while verifying FIXED-111) |
| FIXED-113 | High | Build / Chat — the repository code map | Fixed (was B9) |
| FIXED-114 | Low | Build / stale repository state after a visit elsewhere | Fixed (found while verifying FIXED-113) |
| FIXED-116 | High | Models / first-run default | Fixed (Ollama `gemma4:31b-cloud` is the visible and runtime default) |
| FIXED-117 | High | Container tools / cold start and stdin bridge | Fixed (found during ADD-01 live Docker verification) |
| FIXED-118 | Medium | Web / execution-environment deep link | Fixed (found during ADD-01 Playwright verification) |
| FIXED-119 | Low | Tests / live Ollama leaked into offline scenarios | Fixed (found during ADD-01 baseline verification) |
| FIXED-120 | Low | Activity / machine identity density | Fixed (found during ADD-03 screenshot review) |
| FIXED-121 | Low | Web tests / export download navigation noise | Fixed (found during ADD-03 full verification) |
| FIXED-122 | High | Windows host status / destructive PID probe | Fixed (found during ADD-03 full verification) |
| FIXED-123 | Medium | Plugin execution / invalid fallback turn id | Fixed (found during ADD-03 full verification) |
| FIXED-124 | Medium | Project export / unstable same-second event order | Fixed (found during ADD-03 full verification) |
| FIXED-125 | High | Auto/skip runtime / human principal replaced the signed machine actor | Fixed (found during ADD-03 independent review) |
| FIXED-126 | High | Machine identity / abnormal and delegated paths leaked active principals | Fixed (found during ADD-03 independent review) |
| FIXED-127 | Medium | Activity / contextual turn identity hid the literal event actor | Fixed (found during ADD-03 independent review) |
| FIXED-128 | High | Approvals / resume rotation rewrote proposal identity timestamps | Fixed (found during ADD-03 independent review) |
| FIXED-129 | Low | Permissions / authority matrix ignored readiness failures | Fixed (found during ADD-03 independent review) |
| FIXED-130 | Low | Approvals / identity metadata overlapped at desktop width | Fixed (found during ADD-03 screenshot review) |
| FIXED-131 | High | SQLite bootstrap / concurrent first-use FTS rebuild deadlocked | Fixed (found in ADD-03 GitHub CI) |
| FIXED-132 | Medium | Windows process probe / Linux MyPy rejected guarded ctypes APIs | Fixed (found in ADD-03 GitHub CI) |
| FIXED-154 | Medium | Chat / Build — context meter read `NaN input · NaN output` | Fixed (was BUG-68) |
| FIXED-133 | High | First run / universal exact-model readiness and setup (BUG-69) | Fixed (2026-08-09 live round) |
| FIXED-134 | High | Local library / redaction corrupted path-derived deployment IDs | Fixed (found in BUG-69 live download/deploy) |
| FIXED-135 | Medium | Model Activity / background jobs never refreshed after mount | Fixed (found in BUG-69 screenshot review) |
| FIXED-136 | High | Managed llama.cpp / graceful host shutdown could leave the child alive | Fixed (found in BUG-69 shutdown verification) |
| FIXED-137 | High | API redaction / an unprefixed `path` field was destroyed | Fixed (found in GitHub CI after BUG-69) |
| FIXED-138 | High | Model readiness / an empty account balance was reported as an unreachable provider | Fixed (found in the BUG-69 parity review) |
| FIXED-139 | High | Model readiness / the gate ignored the fallback chain the runtime actually tries | Fixed (found in the BUG-69 parity review) |
| FIXED-140 | High | Models UI / the page counted saved credentials as "set up" and Test proved nothing | Fixed (found in the BUG-69 parity review) |
| FIXED-141 | Medium | Models navigation / three tabs were unreachable by deep link and silently opened Providers | Fixed (found while splitting the Models page) |
| FIXED-155 | Medium | Build / mode chips rewrote global decision modes with no step-up | Fixed (was BUG-70) |
| FIXED-156 | Medium | Memory / a gated capability no turn could ever reach | Fixed (was BUG-71) |
| FIXED-142 | High | Runtime / a tool call that blocked the event loop killed its own turn | Fixed (was BUG-72) |
| FIXED-157 | Medium | Chat / a resumed turn could deny an execution that happened | Fixed (was BUG-73) |
| FIXED-161 | Low | Web build / the main production JavaScript chunk exceeded the 500 kB warning threshold | Fixed (was BUG-74) |
| FIXED-162 | Medium | Model activity / retry, cancellation and partial-file cleanup were record-only for some job types | Fixed (was BUG-75) |
| FIXED-163 | Medium | Runtime / a failing tool or provider was retried until its budget ran out, every turn | Fixed (was BUG-76) |
| FIXED-164 | High | Security monitoring / anomaly detection and containment covered MCP connections only | Fixed (was BUG-77) |
| FIXED-165 | Medium | Subagents / a delegated result carried no identity binding to the spawn that produced it | Fixed (was BUG-78) |
| FIXED-166 | Medium | Plugins / a manifest signature was a presence marker by default and the owner was never told | Fixed (was BUG-79) |
| FIXED-167 | Low | Documentation / the GenAI mapping called the verifier a stub | Fixed (was BUG-80) |
| FIXED-168 | Low | Context / no prompt-injection scanning hook existed, though the security mapping requires one | Fixed (was BUG-81) |
| FIXED-158 | Medium | Model readiness / the advisor model was never readiness-checked or surfaced | Fixed (was BUG-82) |
| FIXED-160 | Low | Models / a throttled read reported only `Unavailable (429)` | Fixed (found while verifying FIXED-158 live) |
| FIXED-169 | Low | Model readiness / one fixed five-minute TTL and no background revalidation | Fixed (was BUG-83) |
| FIXED-170 | Low | Live tests / the BUG-69 acceptance spec could not run with a single provider key | Fixed (was BUG-84) |
| FIXED-171 | Medium | Storage / Windows locked memory | Fixed (was BUG-46) |
| FIXED-172 | Medium | Distribution / setup wizard and native tray | Fixed (was BUG-48) |
| FIXED-173 | Low | Policy / dead `denied_actions` configuration | Fixed (was BUG-51) |
| FIXED-174 | Low | Runtime / governed refusal destination and disclosure | Fixed (was BUG-59 and BUG-60) |
| FIXED-175 | Low | Tasks / creation and execution intent | Fixed (was BUG-64) |
| FIXED-176 | Low | Export / portable citation ledgers | Fixed (was BUG-65) |
| FIXED-177 | Low | Web / loopback and public-bind rate limits | Fixed (was BUG-88) |
| FIXED-178 | Low | Models / remove a provider credential in-app | Fixed (found during live verification) |
| FIXED-179 | Low | CI / immutable release artifact actions | Fixed (was BUG-49) |
| FIXED-180 | Medium | CI / Linux SQLCipher test throughput | Fixed (found during hosted verification) |
| FIXED-181 | Low | Chat / multi-call answer separation | Fixed (was BUG-53) |
| FIXED-182 | Medium | Web e2e / checked-in deterministic model stub | Fixed (was BUG-54) |
| FIXED-183 | Low | Chat / disabled transcript implementation | Fixed (was BUG-55) |
| FIXED-184 | High | Runtime / automatic context compaction | Fixed (former Known Limit) |
| FIXED-185 | Medium | Models / connected-provider rolling usage | Fixed (former Known Limit) |
| FIXED-143 | High | Live tests / the whole live evidence suite could not reach a provider card | Fixed (found while verifying FIXED-142) |
| FIXED-144 | Low | Web / the first-run model sheet rendered Settings underneath it | Fixed (found while verifying FIXED-142) |
| FIXED-149 | Low | Live tests / the BUG-47 scenario expected two Models tabs on screen at once | Fixed (was BUG-85) |
| FIXED-145 | Low | Web / the first-run screen was titled "Workbench" | Fixed (found in the 2026-08-10 visual sweep) |
| FIXED-146 | Low | Knowledge Map / the count pill contradicted the empty state | Fixed (found in the 2026-08-10 visual sweep) |
| FIXED-147 | Medium | Knowledge Map / the graph ignored a system dark preference | Fixed (found in the 2026-08-10 visual sweep) |
| FIXED-148 | Low | Models / "1 models ready" | Fixed (found in the 2026-08-10 visual sweep) |
| FIXED-150 | **Critical** | Storage / SQLCipher ran out of locked memory and locked the owner out | Fixed (was BUG-86) |
| FIXED-151 | Medium | Observability / the audit log showed nothing though governed events were recorded | Fixed (was BUG-87) |
| FIXED-152 | High | Knowledge Map / the source picker browsed the whole Raiker installation | Fixed (reported 2026-08-10) |
| FIXED-153 | Low | Observability / the audit log's turn-identity column rendered mojibake | Fixed (found while verifying FIXED-151) |

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

**Closed subsequently.** The three follow-up defects this work surfaced are now
FIXED-181 (multi-call answer separation), FIXED-182 (the checked-in live stub),
and FIXED-183 (removal of the disabled duplicate transcript block).

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
fails on a compiled artefact it was never meant to see. Recorded as BUG-56, and
closed since as **FIXED-115**.

**UI when closed.** No user-visible change under normal use, and the live run
holds that claim to its word: after the host served 30 more instance workspaces,
every route of the owner's own workspace still rendered with **0 console
errors** and its dashboard status still resolved out of the database the cache
had been evicting around. `working/bug-50-host-before-many-instances.png` and
`working/bug-50-host-after-many-instances.png` are that host on either side of
it. A host that has served many instances for a long time keeps working instead
of eventually failing to open files.

---

## FIXED-101 — The agent could not read a page it was told to read *(was B12/C7)*

**Status: fixed in this change.**

**Observed.** Nothing in the model-facing tool surface reached the web. There was
no `web_fetch` and no search anywhere in `_TOOL_RISK`
(`raiker/models/tool_call_validation.py`), so an agent asked to use a library
could not read that library's documentation — it could only answer from training
and hope. A `WebFetchExecutor` existed under the `web_fetch` *capability*
(`raiker/runtime/executors/tier2_web.py`), reachable only through
`route_action`, and it returned byte counts rather than the page, so even that
path could not have handed a model anything to read.

**Fix applied.** `raiker/runtime/web_access.py` — `WebAccessService`, brokered as
the `web_fetch` and `web_search` tools (`raiker/tools/web_tools.py`). It is
governed exactly like the service connectors beside it, for the same reason: it
is network egress, and here the destination is chosen by a **model**.

Enforced in order, on every call:

1. the `web_fetch` capability gate — disabled ⇒ fail closed;
2. the per-capability decision mode — **default `ask` withholds**, `deny` blocks,
   and `auto` withholds too, because reaching the open internet on a model's
   say-so is never low-risk;
3. the owner egress allowlist `RAIKER_WEB_EGRESS_ALLOWLIST` — empty ⇒ fail
   closed, and deliberately separate from `RAIKER_CONNECTOR_EGRESS_ALLOWLIST`, so
   allowing a connector's API host does not also allow the agent to fetch
   arbitrary pages from it;
4. URL safety, because the URL itself is model-supplied: HTTPS only, no embedded
   credentials, and a destination that resolves to a **public** address — an
   owner can allowlist a *name*, and a name can still point at the loopback
   interface, a metadata service, or a machine on the home network;
5. every redirect hop re-checked against 3 and 4. Redirects are followed manually
   rather than by urllib's handler, because a redirect is a second destination
   the owner never allowlisted.

The page comes back reduced to text — script, style and template bodies dropped
rather than flattened — bounded to 20 000 characters and framed as *untrusted
data, not instructions*, the same framing the connectors use. Broker events keep
the URL, the query and the sizes; the fetched content never enters an audit
payload (`_CONTENT_RESULT_TOOLS`).

`web_search` sits behind the same gate and is **off until the owner configures a
provider**: Raiker ships no search endpoint, so an unconfigured host answers
`web_search_not_configured` rather than quietly reaching somebody's API.

**One policy set had to be reconciled, not added to.** `web_fetch` names a *tool*
and a *capability*, and `allowed_read_actions` is checked before
`approval_required_actions` — leaving the string in both sets would have let the
read branch silently decide the capability path too, which is exactly the "two
lists that have to agree" defect this document keeps finding. The tool name now
lives in `allowed_read_actions` only. The capability path is unchanged by that:
`route_action` gates it on the capability gate and on the decision mode, whose
default `ask` forces approval for any AI-proposed action.

**Live evidence.** Screenshots `working/b12-web-fetch-withheld.png`,
`working/b12-web-fetch-capability.png`, `working/b12-web-fetch-live-page.png` and
`working/b12-web-fetch-egress-denied.png`, from
[`e2e/web-access-turn-control-live.spec.ts`](../../apps/web/e2e/web-access-turn-control-live.spec.ts).
The first attempt is refused with `gate_disabled` and the control that changes
it; after the owner turns the capability on and sets it to Allow, the same
request fetches `https://pypi.org/project/httpx/` and the model quotes the
page's own summary — *"The next generation HTTP client."* — back. A request for
`https://example.com/`, which is not on that host's allowlist, is refused with
`web_egress_denied` before any packet leaves the machine.

**UI when closed.** Permissions lists **Web fetch** with its four decision modes,
its description names the owner egress allowlist, and a withheld call tells the
owner in the transcript which control would change it.

---

## FIXED-102 — A running turn could not be stopped or corrected *(was B17/C13)*

**Status: fixed in this change.**

**Observed.** `POST /api/interrupts` cancels *tasks*, and the top-bar STOP switch
called it — but a Chat or Build turn heading the wrong way had to be waited out
and then re-prompted. The one control that makes an autonomous agent safe to
leave running was the one control the conversation did not have.

**Fix applied.** Three parts, all on the existing governed path:

* **A durable control channel.** A `turn_controls` row per (session, principal)
  holds a stop request and an ordered list of steer messages
  (`RAIKER-1037-turn-controls`). Durable rather than in-process because the
  request that asks for the stop and the loop that honours it need not share a
  worker.
* **A safe boundary that reads it.** `_arun_agent_loop` checks the channel
  between the last tool batch and the next question to the model. A steer is
  appended as a **user message** — the owner's own words, entering their own
  conversation — and a stop ends the turn there. During a long answer the loop
  also polls once a second so Stop feels immediate; the half-streamed tool call
  is discarded rather than reconstructed, because the owner stopped the turn.
  Controls are consumed on read, and cleared at the start of every turn, so one
  stop cannot end two turns and an instruction left between turns is never
  applied to work the owner had not asked for yet.
* **An honest outcome.** `stopped` is now a response status of its own. A turn
  the owner ended did not fail and was not denied: it kept the text it had
  already produced and stopped because it was told to. Reporting that as
  `failed` blamed the runtime for the owner's decision.

The composer is where both live. While a turn streams it becomes the turn's
control surface — a Stop button and a field that queues an instruction — and both
call the same `POST /api/interrupts` the STOP switch uses, still human-only,
still owner-scoped, still applied at a safe boundary rather than as a force-kill.
Steering grants nothing: every call the model makes after reading one is governed
exactly as it was before.

Two small things had to be true first. Every SSE chunk now carries its
`session_id` and `turn_id`, because a brand-new chat had no session id until its
first turn *ended* — which made the very turn most worth stopping the one turn
that could not be. And a stopped turn says so in the transcript, rather than
simply ending early and leaving the owner to wonder whether Raiker stopped or
broke.

**Live evidence.** Screenshots `working/b17-turn-control-visible.png`,
`working/b17-steer-queued.png`, `working/b17-steered-answer.png`,
`working/b17-stop-requested.png` and `working/b17-turn-stopped.png`, from the
same live scenario. The steer is typed while the turn is streaming and the model
obeys it — it answers **STEERED MIDTURN**, which was never in the original
prompt. The stop is pressed mid-turn and the transcript ends with *"Stopped at
your request — this turn ended at a safe boundary and kept what it had already
done."*

**UI when closed.** Chat and Build show a Stop control and a steer field while a
turn is running, and a turn that was stopped reads as stopped rather than as an
answer that trailed off.

---

## FIXED-115 — A shipped-skill check failed after `compileall`, which CI itself runs *(was BUG-56)*

**Status: fixed in this change; reproduced while verifying FIXED-113.**

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

**Fix applied.** The walk skips generated directories (`__pycache__` and the
tool caches) and compiled bytecode, and says in the test's own docstring why. The
rule itself is untouched: an unreferenced *source* file in a skill bundle is
still a defect, which is what the check was written to catch. Verified by running
`compileall` over the three trees and then `pytest tests/test_skills.py` — the
order that used to fail.

**UI when closed.** None — this is a test-suite reliability defect.

---

## FIXED-104 — The context bundle's fixed capability flags talked a model out of tools it can use *(was BUG-57)*

**Status: fixed in this change; found while verifying FIXED-101.**

**Observed.** With the `web_fetch` capability enabled and its decision mode set
to Allow, one live turn declined to call `web_fetch` at all and explained why:

> I cannot call web_fetch because the web_fetch capability gate is disabled in
> the current runtime environment. According to the capability status in the
> workspace context, `network_execution_enabled` is false…

Nothing was disabled. `network_execution` is a **different** capability, and the
model reasoned from it to a neighbouring one.

**Root cause.** `CAPABILITY_FLAGS` in `raiker/context/gatherer.py` is a fixed
list of eighteen `*_enabled` names the gatherer reports as `False` on every turn,
regardless of what the owner has actually enabled. They were added so a model and
the event log could see the runtime was gated, and they are now stale in two
directions at once: they never reflect a gate the owner turned on, and they name
capabilities that no longer correspond one-to-one to the tools in the schema.

**Why it matters.** It is the same failure mode as BUG-51 and FIXED-98 — two
lists that have to agree and nothing holding them together — except this one is
read by the *model*, so the cost is a refusal the owner cannot see the cause of.
A capability an owner has deliberately enabled should not be argued away by
context that has not been true since it was written.

**Required fix.** Report the real, per-principal gate state for the capabilities
the bundle names, or stop naming them. If the flags stay, they must be derived
from the same store the gates live in, and a test must assert that a capability
enabled by the owner is reported as enabled.

**Fix applied.** The bundle now reads the owner's own decisions rather than
asserting a fixed answer, and it says them in the vocabulary the model proposes
in.

* **`CAPABILITY_GATE_TOOLS` replaces `CAPABILITY_FLAGS`.** Twelve capabilities,
  each keyed to the model-exposed tools it governs, read per principal through
  `SQLiteStore.account_scope` → `get_principal_capability_gate_state` /
  `get_principal_capability_decision_mode` — the same resolution
  `raiker/runtime/web_access.py` uses to enforce them, so the bundle cannot
  report one answer while the runtime enforces another. Each line reads
  `web_fetch: enabled (state=enabled_runtime, decision_mode=allow) — governs
  web_fetch, web_search`.
* **Naming the tools is half the fix, not decoration.** The old list gave the
  model eighteen capability names and a schema full of tool names, with nothing
  holding the two vocabularies together — so it bridged them itself, from
  `network_execution` to `web_fetch`. There is now nothing left to infer across,
  and the item's own preamble says so: read each line for the tools it names and
  nothing else. A tool no line names is not gated by a capability.
* **The decision mode is reported beside the gate,** because a gate that is on
  and a mode that withholds are two different refusals and the model was being
  told about neither.
* **A second stale assertion, one function up, was doing the same damage.**
  `_workspace_summary` hardcoded `runtime_mode: local_read_only_planning` and
  `disabled_runtime: all unsafe runtime flags remain false`. The first named one
  of the five modes FIXED-63 replaced with a single runtime; the second told
  every model that everything the owner had switched on was off. Both are now
  one line, `agent_runtime: active|disabled`, resolved the way
  `evaluate_activation_requirement` resolves it.
* **A failed read reports the fail-closed default rather than dropping the
  line,** because silence would read to the model as "not gated".

Three tests hold it: a fresh workspace reports every gate disabled *and* names
its tools; a gate the owner enables is reported as enabled while a neighbouring
one is not; and `ENABLED_GATE_STATES` is asserted equal to the frozensets in
`web_access.py` and `connectors.py`, so the bundle and the tools cannot drift
into two definitions of "on".

**Live evidence.** [`e2e/bug-57-capability-context-live.spec.ts`](../../apps/web/e2e/bug-57-capability-context-live.spec.ts),
run against a `raiker-web` on a fresh workspace holding a real Anthropic
credential entered through the product's own Models page —
`claude-haiku-4-5-20251001` answering every turn.

| Screenshot | What it shows |
|---|---|
| `working/bug-57-model-connected.png` | the credential added through Models, Haiku 4.5 selected |
| `working/bug-57-gate-disabled-named.png` | before the owner touches anything, the model quotes back a `web_fetch` line that says *disabled* — and cannot quote `network_execution_enabled`, because it no longer exists |
| `working/bug-57-runtime-status-live.png` | the model quotes `agent_runtime: active`, not the deleted `local_read_only_planning` |
| `working/bug-57-web-fetch-enabled.png` | the gate turned on and its mode raised to Allow, through the product's own Permissions page |
| `working/bug-57-web-fetch-used.png` | **the defect itself, closed** — the same prompt that used to be refused now calls `web_fetch` and quotes the page back verbatim |
| `working/bug-57-gates-read-back.png` | `web_fetch: enabled (…decision_mode=allow)` and `shell_execution: disabled (…decision_mode=ask)` in one answer: turning one gate on did not read as turning its neighbour on |

**UI when closed.** A tool the owner has enabled is not refused by the model on
the strength of a stale context line, and the transcript's stated reason for any
refusal matches what governance actually decided.

---

## FIXED-103 — README's "Known limits" described behaviour that has since shipped *(was BUG-58)*

**Status: fixed in this change; found while writing FIXED-101.**

**Observed.** `README.md` → **Known limits**, stamped *"As of 2026-07-27"*, still
tells a reader:

> **A model proposing several tool calls at once gets one of them.** The
> orchestrator takes the first and drops the rest without telling the model.

B4 (FIXED-39) made every validated read-only call in a batch run concurrently;
ADD-02 parks the calls behind an approval boundary as an ordered queue; FIXED-99
made a refusal end its own call rather than the batch. The same section's
multi-file patch limit was closed by FIXED-34, and its "approved network actions
still do not run" line predates FIXED-101.

**Why it matters.** This is FIXED-24's defect returning by a different route: a
document that describes shipped behaviour as missing costs a reader trust in
everything around it, and Known limits is the section a careful reader checks
*first*.

**Required fix.** Re-derive the section from the current tree, restamp the date,
and state each remaining limit against the entry that closed or bounded it. Do
not simply delete the lines — a limit that is genuinely still there must survive
the pass.

**Fix applied.** The section is re-derived from the tree, restamped
*"As of 2026-08-04"*, and every line is now a limit that a reader can still hit:

* **The approval line names the two capabilities that really are record-only.**
  `EXECUTABLE_ON_APPROVAL` in `raiker/approvals/execution.py` carries
  `file_write_execution`, `patch_apply_execution`, `shell_execution`,
  `remote_execution_cap` and `cloud_execution_cap`; `network` and `process` map
  to capabilities that are not in it. Shell stopped being record-only in
  FIXED-90, and the same sentence had gone stale twice more in the body of the
  README — the intro paragraph and the "Owner-authoritative and monitored"
  section both still said shell approvals execute nothing. All three now agree,
  and the reason the asymmetry exists is stated rather than asserted: a shell
  command is allowlisted, workspace-contained, time- and output-bounded and
  captured, and the other two are not.
* **The parallel line states what is still bounded, rather than being deleted.**
  "A model proposing several tool calls at once gets one of them" is simply
  false — `_arun_agent_loop` runs a validated read-only batch through
  `asyncio.gather`, and ADD-02/FIXED-99 park the remainder of a mixed batch
  instead of dropping it. What survives the pass is the real bound: the
  concurrent path is taken only when *nothing* in the batch requires approval
  (`read_only = all(not action.requires_approval …)`), so a batch of three edits
  is three decisions.
* **The patching line moves from scope to matching.** Multi-file, create and
  delete patches shipped in FIXED-34; `_patch_candidates` walks every file
  section of one diff and `apply_patch_content` applies them as one transaction
  with rollback. The strictness that genuinely remains is in `_patch_candidate`
  and `_replace_candidate` — one `old_text` match, exact and unambiguous hunk
  context, existing text targets, no duplicate target, no fuzz.
* **A limit the section never carried has been added.** Web access shipped in
  FIXED-101, but it ships *closed*: the gate is off, the decision mode withholds
  at `ask`, an empty `RAIKER_WEB_EGRESS_ALLOWLIST` reaches nothing, and
  `web_search` has no endpoint to call at all. A reader who took "the agent can
  read the web" from the release notes and nothing else would be surprised, and
  Known limits is where that belongs.
* **The closing line no longer over-promises.** It used to say each limit is
  written up with a reproduction and a proposed fix; several of these are
  deliberate boundaries with no such entry. It now says which, and names the
  entries that closed the ones this section used to list.

**Live evidence.** [`e2e/bug-58-known-limits-live.spec.ts`](../../apps/web/e2e/bug-58-known-limits-live.spec.ts),
run against a `raiker-web` on a fresh workspace holding a real Anthropic
credential entered through the product's own Models page —
`claude-haiku-4-5-20251001` answering every turn, not a stub and not a
route-mocked shell. Each test holds up the bullet it is named for:

| Screenshot | What it shows |
|---|---|
| `working/bug-58-model-connected.png` | the credential added through Models, Haiku 4.5 selected |
| `working/bug-58-parallel-read-batch.png` | one turn, three `read_file` calls, all three markers quoted back — the old "gets one of them" line disproved |
| `working/bug-58-multi-file-patch.png` | **one** pending approval, `alpha.md, beta.md`, both file diffs under it |
| `working/bug-58-web-fetch-withheld.png` | `web_gate_disabled` before the owner has touched the gate |
| `working/bug-58-web-search-unconfigured.png` | gate enabled and set to Allow, and search still answers `web_search_not_configured` |
| `working/bug-58-execution-capabilities.png` | Shell commands as an owner control with its four decision modes |

Matching strictness is not live-checked, because the turn parks at the approval
boundary before a hunk is ever resolved; it stays covered by
`tests/test_filesystem_tools.py`, whose `hunk_context_mismatch` case is the
assertion behind that clause.

**Found while verifying this.** Two defects in the refusal the web bullet is
about, recorded as BUG-59 and BUG-60 rather than fixed here.

**UI when closed.** None — this is documentation accuracy for the first thing a
new reader is told about the product's edges.

---

## FIXED-105 — The user guide's "Known limits" were stale in every line *(was BUG-61)*

**Status: fixed in this change; found while writing FIXED-103.**

**Observed.** FIXED-103 re-derived the README's Known limits. The user guide has
two more of these sections, reached from the README's own Documentation list, and
**not one entry in either is still true**:

`docs/guide/working-in-chat.md` → *Known limits* — "Three things do not work yet":

| It says | Actually |
|---|---|
| Markdown is not rendered (BUG-03) — headings, tables, lists and fenced code appear as raw text | shipped in **FIXED-06** |
| No export (BUG-08) — no download, PDF or print control | shipped in **FIXED-12**, superseded by **FIXED-19** |
| an approved file write does not create a file on disk (BUG-06) | shipped in **FIXED-08**, the entry this document calls *Critical* |

`docs/guide/tasks-and-projects.md` → *Known limits*:

| It says | Actually |
|---|---|
| a background-agent run can end `failed` with no user-visible reason (BUG-09) | shipped in **FIXED-13** |
| task runs appear in the sidebar's RECENT CHATS alongside real conversations (BUG-10) | shipped in **FIXED-15** |
| creating a task by asking for one in Chat is specified but not shipped | the one line that still held when FIXED-105 shipped; closed since in **FIXED-106** |

**Why it matters.** This is worse than BUG-58 was. The README's section had drifted
in part; these two have not been touched since the entries that closed them, so a
reader following the README's own link to the user guide is told that Markdown
rendering, transcript export, and — most damagingly — *approved file writes
reaching the disk* are all missing from a product that ships all three. The guide
is where a new owner goes after the README, and it currently reads as an argument
that the product does less than its front page claims.

**Required fix.** Re-derive both sections the way FIXED-103 re-derived the
README's: check each line against the tree, keep what is genuinely still a limit
and say what bounds it, and drop nothing without replacing it with the entry that
closed it. Verify the one unchecked claim — conversational task creation — rather
than carrying it forward on trust. While there, look for the same drift in the
rest of `docs/guide/`; two sections found by inspection is not evidence that the
other pages are current.

**Fix applied.** Both sections are re-derived from the tree, and the rest of
`docs/guide/` was read for the same drift — which found more than the two
sections this entry was opened for.

**`working-in-chat.md` → Known limits.** All three entries had shipped, so all
three are gone and named: Markdown rendering (**FIXED-06**), export
(**FIXED-12**, superseded by **FIXED-19** and **FIXED-54**), and an approved
file write reaching the disk (**FIXED-08**). What replaces them is the set of
edges a Chat user can still hit, each checked against the tree: `network` and
`process` approvals are still record-only (`EXECUTABLE_ON_APPROVAL` in
`raiker/approvals/execution.py` carries neither); a batch runs concurrently only
while nothing in it needs a decision; `web_fetch` ships closed and `web_search`
has no endpoint at all; conversational task creation stops at an approval (below);
and compaction at 90 % and weekly quota remain specified but not shipped. The
duplicate statement of that last one at the foot of the page is gone — one
document stating the same limit twice is how this drift starts.

**`tasks-and-projects.md` → Known limits.** Two of three had shipped
(**FIXED-13**, **FIXED-15**) and are named. The third — *"creating a task by
asking for one in Chat is specified but not shipped"* — was the line this entry
said must be verified rather than carried forward on trust, and verifying it
found it half true in a way worth writing down. It is now the section's only
limit, stated as what actually happens, and recorded separately as **BUG-62**.

**The drift was not confined to the two sections.** Reading the rest of the guide
against the running product found five more:

| Page | Said | Actually |
|---|---|---|
| `permissions-and-runtime-modes.md` | Five runtime modes, activated in *Settings → General*, as a ceiling over every gate | One runtime (**FIXED-63**). Settings → **Runtime configuration** states what is running; the only control is Disable/Enable |
| `permissions-and-runtime-modes.md` | Chat has a **Permissions** control offering *Ask every time* / *Approve safe actions* / *Custom permissions…* | No composer rendered it; the component is deleted — see **FIXED-159** |
| `getting-started.md` | Sidebar: **Sessions** under Work, **Brain** under Knowledge | Sessions is a tab inside Observability; Brain is the **Knowledge Map** |
| `extensions-and-mcp.md` | *"Current limit (BUG-12): a connected server's tools are not offered to the model in Chat"* | Callable since **FIXED-17**, and the page states gate *and* decision mode since **FIXED-96** |
| `troubleshooting.md` | Rows pointing at BUG-03, BUG-06, a runtime-mode picker, and *Settings → Security & Login* | All four shipped or renamed; the section is now *Security & sign-in* and one runtime |

The guide's index page went with them: its "work in this order" list opened with
a runtime mode and a vault key, neither of which an owner has to touch — a
saved credential is the authorization, and the vault key provisions itself.

**Live evidence.** [`e2e/bug-61-guide-accuracy-live.spec.ts`](../../apps/web/e2e/bug-61-guide-accuracy-live.spec.ts),
against a `raiker-web` on a fresh workspace holding a real Anthropic credential
entered through the product's own Models page. Each test holds up a claim the
rewritten guide now makes:

| Screenshot | What it shows |
|---|---|
| `working/bug-61-markdown-rendered.png` | a real turn rendering a heading, a list, and a `TypeScript`-labelled code block with **Copy code** — the "Markdown is not rendered" line disproved |
| `working/bug-61-export-review.png` | **Export conversation…** offering HTML, Markdown and PDF — the "no export" line disproved |
| `working/bug-61-single-runtime.png` | Settings with **Runtime configuration** and no mode picker; none of the five mode names on the page |
| `working/bug-61-navigation.png` | the sidebar the guide's table now lists — no Sessions, no Brain |
| `working/bug-61-mcp-agent-access.png` | Extensions → MCP naming the exact reason the agent cannot call a server, with the link that changes it |
| `working/bug-61-task-not-in-recents.png` | a created task absent from RECENT CHATS |
| `working/bug-61-chat-created-task.png` | asking in Chat raising a real high-risk **Create task** approval |
| `working/bug-61-chat-task-record-only.png` | and approving it answering *"Recorded: approved. The action was NOT executed (metadata-only)"* — the honest half of the claim the guide now makes |

**Found while verifying this.** BUG-62 and BUG-63, recorded rather than fixed
here.

**UI when closed.** None — this is documentation accuracy, in the pages a new
owner reads immediately after the README.

---

## FIXED-106 — The agent could propose a task it could never create *(was BUG-62)*

**Status: fixed in this change; found while verifying FIXED-105.**

**Observed.** Asked in Chat to call `create_task`, the model called it, the
runtime raised a real **Create task** approval at *high* risk naming the task,
and approving it answered:

> Recorded: approved. The action was NOT executed (metadata-only).

No task was created. `working/bug-61-chat-created-task.png` and
`working/bug-61-chat-task-record-only.png`.

**Root cause.** `create_task` reached the approval path correctly — FIXED-98 put
it in `approval_required_actions` precisely so it would stop being answered
`unknown_or_denied_tool`. What it never reached was
`EXECUTABLE_ON_APPROVAL` in `raiker/approvals/execution.py`, whose five members
were the file, patch, shell, remote and cloud capabilities. So the approval was
record-only, and `ToolBroker._create_task` — which is written, returns a receipt
`{"kind": "task", "href": "#/tasks", "label": "Review in Tasks"}`, and would
work — was never called.

**Why it mattered.** This is a worse shape than a missing feature. The owner was
shown a high-risk decision, told what approving would do, approved it, and got
nothing — and the receipt the broker was built to return named a Tasks page that
would not have the task on it. Every other tool in this position either executes
on approval or is honestly described as record-only *before* the decision;
`create_task` was neither, because a task is exactly the kind of local,
reversible, owner-scoped row the relay exists for.

**What shipped.** Both tools now execute on approval, each under a capability
gate of its own that the owner holds:

* **Two capabilities, named for what they govern.** `task_management_runtime`
  and `project_assignment_runtime` (`raiker/phase_gates.py`,
  `CAPABILITY_GATE_MAP` in `raiker/runtime/authority/router.py`) appear in
  **Permissions → Workspace** as *Task creation* and *Project assignment*. An
  unmapped tool has no gate to consult and no capability to relay into, so
  naming them is what makes both the switch and the execution possible.
* **Two real executors** (`raiker/runtime/executors/tier1_tasks.py`). Each goes
  through the same `DashboardService` entry point the **Tasks → Plan work** form
  uses, so a task the agent asked for and a task the owner typed are one row
  with one stop control. Both are added to `EXECUTABLE_ON_APPROVAL`, so the
  relay re-governs them at execution time — gate, decision mode, a fresh policy
  review, and the posture check on the approving session — exactly as it does a
  file write.
* **The proposing conversation is carried, not guessed.** An approval resolved
  from the inbox executes under the *inbox's* session, so
  `assign_session_project` would have had no way to name the chat it was asked
  to move. `GovernedAction.origin_session_id` carries the approval row's own
  session across, so the conversation moved is the one the owner saw named — and
  it still cannot be chosen by the model.
* **The sentence before the decision is per-capability.** The file wording
  promises a checkpointed diff, which a task row does not have.
  `_approval_detail` (`raiker/control/dashboard.py`) and `_expected_effect`
  (`raiker/tools/broker.py`) now state what each one actually does: *"Approving
  this creates the task above in Tasks, once…"*.
* **The surface links to what now exists.** The executor returns the broker's
  receipt, the resolve route passes it through, and the Approvals inbox and
  Build both say *Executed once — “…” now exists* with **Review in Tasks**
  beside it, instead of *Executed once: executed*.
* **The off switch still wins, and says so first.** With *Task creation*
  disabled the approval detail reads *"Approval resolution is metadata-only"*,
  the button reads **Approve (record only)**, and resolving it creates nothing.

**Found while closing it — a capability nobody could turn on.**
`ACTIVATION_REQUIREMENTS` (`raiker/runtime/authority/activation.py`) had no entry
for either new capability, so **Permissions** offered the switch and answered
*"Activation is blocked. Satisfy the activation requirement first."* with no
requirement to satisfy. `checkpoint_restore_execution` — a registered executor
since Workstream B — was in exactly the same position and had been all along. All
three now have entries, and a test asserts the invariant directly: no capability
with a real executor may lack an activation requirement. It is the same failure
mode this document keeps recording — two lists that have to agree, held together
by care rather than by a test. `docs/guide/permissions-and-runtime-modes.md`
listed checkpoint restore among the **deferred** capabilities — *"no governed
executor exists"* — which was never true of it; that page now says what it is,
and its gate count moves 62 → 64 for the two capabilities added here.

**Tests.** [`tests/test_bug_62_task_approval_executes.py`](../../tests/test_bug_62_task_approval_executes.py)
covers the task really existing afterwards, the resumed turn being told so, a
rejection creating nothing, a title-less proposal failing closed, the notice the
owner reads before deciding, the disabled gate returning it to record-only, the
project assignment landing on the proposing conversation, and the two
list-agreement invariants.

**Live evidence.** [`e2e/bug-62-task-approval-executes-live.spec.ts`](../../apps/web/e2e/bug-62-task-approval-executes-live.spec.ts),
run against a `raiker-web` on a fresh workspace holding a real Anthropic
credential entered through the product's own Models page —
`claude-haiku-4-5-20251001` proposing every task.

| Screenshot | What it shows |
|---|---|
| `working/bug-62-model-connected.png` | the credential added through Models, Haiku 4.5 selected |
| `working/bug-62-capability-control.png` | **Task creation** as an owner control on Permissions, turned on through the product |
| `working/bug-62-approval-will-create.png` | the decision stating *"Approving this creates the task above in Tasks, once"*, with **Approve and execute once** |
| `working/bug-62-approved-and-executed.png` | **the defect itself, closed** — *Executed once — “Draft the weekly summary” now exists* with **Review in Tasks** |
| `working/bug-62-task-in-tasks.png` | the task on the Tasks page, carrying the objective the model wrote |
| `working/bug-62-gate-off-record-only.png` | the same prompt with the capability turned off: *metadata-only*, **Approve (record only)** — the owner's off switch, stated before the decision |

**UI when closed.** Approving a **Create task** proposal from Chat puts the task
in **Tasks**, and the inbox that took the decision links straight to it.

---

## FIXED-159 — A composer permission control shipped and was rendered by nothing

**Status: fixed in this change, alongside FIXED-155. Was BUG-63, found while
verifying FIXED-105.**

**Observed.** `apps/web/src/lib/components/PermissionModeControl.svelte` offers
*Permissions: ask* / *Permissions: safe auto* / *Custom permissions…* and writes
every capability's decision mode through `api.setCapabilityDecisionMode`. No
file imports it. The user guide documented it as a Chat control for as long as
it has existed.

**Why it matters.** It is a live component with real authority — one selection
rewrites the decision mode of *every* capability the account has — sitting in the
build with no route to it. That is two risks in one: a documented control an
owner cannot find, and a bulk permission mutation one import away from shipping
unreviewed. It is also how the guide came to describe a control that was never
on screen, which is the same class of defect as BUG-61 itself.

**Fix applied — deleted.** It is the same defect as FIXED-155, one size larger:
a composer control that rewrote decision modes with none of the ceremony the
Permissions page requires, except that this one rewrote *every* capability in a
single selection. Removing the four-capability version while leaving a bulk one
an `import` away would have left the defect in the tree, so it went with it. The
governed path for changing a decision mode is the Permissions page, and the
composer's posture is now per-turn and tightening-only.

**UI when closed.** The tree carries no permission mutation nothing can call,
and no composer writes standing decision modes.

---

## FIXED-107 — An answer drawn from the owner's own material named no source

**Status: fixed in this change. Closes GAP-CHAT C6 and the last of C4.**

**Observed.** Chat reads a workspace file, an email, a calendar entry, a fetched
page, a stored memory or an attached document, and then answers. The transcript
says nothing about which of them the answer rests on. An answer drawn from a real
contract and an answer invented whole are the same shape on screen.

**Reproduce.** Attach a document, or ask a question that makes the agent call
`read_file`. The answer arrives with a correct fact in it and no way to check
where the fact came from short of re-reading the file yourself.

**Why it is a defect and not a nicety.** Everything else in this product is built
so a claim can be checked — FIXED-61 exists because a memory that printed
*"chat — Weekly planning"* and could not open it was *worse* than one that
claimed nothing. An assistant acting on somebody's actual mail and files owes the
same. A claim you cannot check reads exactly like a claim you can.

**Root cause.** There was no per-turn record of what a turn read. The broker
executed the call, the audit trail recorded that it had, and the result went to
the model — but nothing tied the material to the answer, so no surface could name
it and the model had no id to cite even if it wanted to.

**Fix applied — a source ledger, and the two claims kept apart.**

* **The ledger is derived from what really ran.** `raiker/runtime/turn_sources.py`
  turns each executed read call into one `TurnSource` (`source_from_tool_result`),
  and each attachment the context gatherer really included into another
  (`attachment_sources`). A failed call, a tool that reads nothing (`update_plan`,
  `write_file`), and a denied attachment all produce no source, because a citation
  pointing at a call that produced nothing is worse than no citation.
* **One source per executed call.** Not per match or per result row. A call is the
  unit the runtime governed and audited, so it is the unit whose provenance can be
  stated honestly; `detail` carries the count when a call returned several things.
* **The model is handed the ids, not asked to invent them.**
  `RuntimeOrchestrator._cite_result` adds `source_id` and `cite_as` to the tool
  result the model is about to read, an attachment's marker is printed on the very
  context block it names, and one standing system message asks for `[s1]` after a
  sentence that rests on it. The ids are `s1`, `s2`, … per turn, continuing across
  an approval so a resumed turn does not reuse `s1` for something else.
* **A marker the ledger does not know is not a citation.** `renderMarkdown` takes
  an *allowlist* of ids (`apps/web/src/lib/markdown.ts`); anything else stays the
  characters it is. A model that writes `[s9]`, and a file that happens to contain
  `[s1]`, both produce plain text — which is what stops a citation being something
  a model can simply assert.
* **The ledger is a fact; a citation is a claim.** `SourceChips.svelte` shows every
  source the turn recorded under the answer, cited or not, and marks — in words as
  well as colour — the ones the model actually cited. Collapsing the two would be
  the dishonest version of provenance.
* **Content is stored, never broadcast.** `turn_sources`
  (`RAIKER-1038-turn-sources`) keeps each source's bounded `passage`; the streamed
  `turn_sources_recorded` event carries counts, ids, kinds and tool names only.
  Titles and passages reach the client solely over
  `GET /api/sessions/{id}/sources` and the excerpt route, both owner-scoped by the
  row's own `principal_id`, so another account resolves to an empty list rather
  than to a refusal that would confirm the conversation exists.

**The last of C4 — opening a source *at the passage used*.** A chip resolves
through `GET …/sources/{source_id}/excerpt`, and resolution is re-run at read time
rather than served from what was true at capture:

* An **attachment** goes through the attachment reader, so authorisation is
  re-checked against this caller now. It opens in the existing inspector with the
  passage marked.
* A **workspace file** is re-read and the run located inside it. A file that has
  since changed answers `source_changed` and is shown *without* a highlight rather
  than with one near where the passage used to be.
* **Which part of a whole-file read?** Only the sentence carrying the marker knows,
  so the client sends it (`sentenceAround`) and `locate_answer_quote` finds the
  longest run of the answer's *own words* that occurs verbatim in the source.
  Exact runs only, a floor on fragment length, and nothing scored or approximated:
  a paraphrase matches nothing and the pane says so. The needle is cleaned of the
  model's own presentation (the marker, inline emphasis); the haystack is never
  touched, so nothing can be marked that the source does not literally contain.
* **Material Raiker holds no second copy of** — a page, an email, a connector
  response — is shown as the exact text that reached the model, labelled as such.
* Every outcome is one of the named statuses `source_provenance` already
  established, so the inspector renders one vocabulary whether a passage was opened
  from a memory record or from a citation chip.

**Build gets the same account.** Build receives the same markers, so it owed the
same answer. It has no inspector pane (B13/B14), so a cited source opens *inline*
under the citation — `SourceExcerptPanel.svelte`, same bounded text, same slicing
highlight, same named states.

**Found while doing it.** `FileInspector`'s **Open document** offered a link to
`#/new-chat?session=…` for a *file* source — the pane is already the document, so
it sent the owner back to the chat they were standing in. The link is now offered
only for a conversation source, which is the only thing it ever did.

**Deliberately not changed.** A citation is not evidence that the sentence beside
it was drawn from the source — only the model knows that, and it is asked rather
than trusted. That is exactly why the whole ledger is shown alongside the markers,
and why an uncited source is still listed.

**Tests.** [`tests/test_turn_sources.py`](../../tests/test_turn_sources.py) covers
derivation from real results, the tools that must never become sources, attachment
inclusion, id ordering across batches, the per-turn bound, owner scoping, the
client view never carrying a passage, every resolution status, the quote locator
(including the paraphrase and short-fragment refusals), and retention.
[`citations.test.ts`](../../apps/web/src/lib/citations.test.ts),
[`markdown.test.ts`](../../apps/web/src/lib/markdown.test.ts) and
[`SourceChips.test.ts`](../../apps/web/src/lib/components/SourceChips.test.ts)
cover the allowlist, the code-span and fence exclusions, the per-render reset, the
sentence extraction on both sides of a full stop, and the cited/recorded
distinction.

**Live evidence.** [`e2e/c6-c4-source-citations-live.spec.ts`](../../apps/web/e2e/c6-c4-source-citations-live.spec.ts),
run against a `raiker-web` on a fresh workspace holding a real Anthropic
credential entered through the product's own Models page —
`claude-haiku-4-5-20251001`, seven scenarios, all passing.

| Screenshot | What it shows |
|---|---|
| `working/c6-source-ledger-under-answer.png` | the answer with its inline `1` chip, and **SOURCES · contracts/meridian.md** under it |
| `working/c4-source-opened-at-passage.png` | the chip opening the file at the cited sentence, *Located by matching this answer's own words* |
| `working/c4-attachment-opened-at-passage.png` | an attached document previewed **and** marked at the passage it contributed |
| `working/c6-build-source-inline.png` | Build's inline source panel, the same passage marked where Build has no pane |
| `working/c6-uncited-marker-stays-text.png` | **the property the feature rests on** — a model writing `[s7]` for a source that does not exist produces plain text and no strip |

**UI when closed.** An answer drawn from the owner's material names what it read,
under the answer and inline where the model cited it, and one click opens that
source at the words the answer used.

---

## FIXED-108 — A deleted conversation left its plan, its controls and its sources behind

**Status: fixed in this change; found while implementing FIXED-107.**

**Observed.** `SQLiteStore._delete_session_rows` cascades nine tables. Three
session-keyed tables written after that list — `agent_plans` (B6),
`turn_controls` (B17/C13) and `turn_sources` (FIXED-107) — were in none of them,
so deleting a conversation left them in the store.

**Why it matters.** `turn_sources` holds recorded *passages*: real text from the
owner's files, mail and pages. "Delete this conversation" is a claim the product
makes to its owner, and a cascade that silently misses the newest content-bearing
table does not keep it. `agent_plans` and `turn_controls` are smaller — intent and
a parked stop — but they are equally the conversation's, and a stale plan keyed to
a dead session id is a resurrection waiting for a reused id.

**Root cause.** The same shape this document keeps recording: two lists that have
to agree — the tables that are session-keyed, and the tables the cascade names —
with nothing holding them together. `purge_account` does not have the problem
because it sweeps `sqlite_master` generically by column name; the per-session
cascade is hand-written.

**Fix applied.** All three are in the cascade, with a comment saying why the list
exists. Covered by `tests/test_turn_sources.py::TestRetention`, which asserts the
ledger and the plan are both gone after `delete_session`.

**Still worth a maintainer decision:** the per-session cascade should probably be
derived the way `purge_account` derives its sweep, rather than being a list a
future table has to remember to join.

---

## FIXED-109 — The agent could describe a change it could neither commit nor propose

**Status: fixed in this change. Closes GAP-BUILD B11.**

**Observed.** Build's git surface was `git_status`, `git_diff` and `git_log`. The
agent could read a repository, edit files in it through the approved file path,
and then stop: there was no way for it to record what it had done or to put it in
front of anyone. Asking for a commit produced prose about a commit.

**Reproduce.** Connect a repository, have the agent make an approved edit, then
ask it to commit the change. It explains what `git commit` would do.

**Why it is a gap and not a nicety.** Every coding agent this product is measured
against closes its loop with a commit — it is how the work becomes reviewable,
and how an autonomous run leaves something a human can accept or throw away as a
unit. Without it the file writes accumulate in a working tree nobody has agreed
to, which is a *worse* position than not writing at all.

**Root cause.** `raiker/tools/git.py` allowlisted exactly three read
subcommands. There was no write tool, no capability, and no executor — so there
was also nothing for the policy engine or the approval relay to route.

**Fix applied — a proposal that is the same computation as the mutation.**

* **Two tools, one owner switch.** `git_branch` and `git_commit` are high-risk,
  approval-required, and both map to `git_write_execution` — Permissions →
  Workspace → **Git writes**. One control answers "may the agent change my
  repository", and turning it off returns those approvals to record-only with
  the detail view saying so *before* the decision.
* **The preview is the execution's own computation.**
  `proposed_branch_snapshot` / `proposed_commit_snapshot` compute what the
  mutation would do and touch nothing — no staging, no index change, no ref
  written. The transcript, the Approvals inbox and
  `GitWriteExecutor` all read the same function, and the executor re-derives it
  before mutating, so a repository that moved between the approval and the
  execution fails closed with a named reason instead of recording something the
  owner never saw.
* **A commit is reviewed as a diff; a branch is reviewed as its refs.** The
  commit preview carries the exact file list with each file's state and the whole
  diff, *including files git does not track yet* — built against empty, because
  `git diff` has nothing to say about them and a new file shown as a name alone
  is not a review. A branch has no diff, so its preview states the two refs it
  moves between rather than pretending otherwise (`preview_kind: "git_change"`).
* **The commit is the reviewed change set and nothing else.** Execution stages
  the snapshot's own path list and commits path-limited (`git commit -- <paths>`)
  — never `git add --all`. This is not tidiness: the Raiker workspace *contains*
  `.raiker/`, which holds the vault key, the encrypted store and the audit log, so
  a commit that swept the working tree would have written the owner's key
  material into git history. `.raiker/` and `.git/` are dropped from every
  proposal, and a path naming one is refused as `protected_workspace_path`.
* **A governed write is not a code-execution path.** Every invocation carries
  `-c core.hooksPath=raiker-no-such-hooks`. `.git/hooks` is workspace content the
  agent may itself have written; running it on commit would have turned an
  approved commit into arbitrary local execution. Signing is disabled for the
  same class of reason — a configured key would block the commit on a passphrase
  prompt this process can never answer.
* **The owner's identity is kept.** A committer identity is supplied only when
  the repository has none; a configured `user.name`/`user.email` is never
  overridden.
* **Refusals are named.** Not a git repository, a name `git check-ref-format`
  rejects, a branch that exists, an unknown base, an in-progress
  merge/rebase/cherry-pick/revert/bisect, an empty message, nothing to commit, a
  path outside the repository. A branch created *from a named base* moves the
  working tree, so it is refused while there are uncommitted changes; without a
  base there is nothing to move to and the proposal states how many files it
  carries across.
* **A rename is one change, not half of one.** Found while probing the executor:
  a rename's source path has to be committed alongside its destination, or the
  commit records the addition and leaves the old file's deletion staged behind —
  a half-recorded rename the owner was told was one change. The source half is
  already staged by `git mv`, so it is deliberately not re-`add`ed: it matches
  neither the working tree nor the index any more, and asking would fail the
  whole commit.
* **The outward half.** `github_write` proposes the work to the repository —
  `create_pull_request` (new) and `create_comment` (already in the connector
  service, previously reachable only through `connector_write`) — under the
  existing `connector_github_runtime` gate, the env-only owner credential and the
  owner egress allowlist. It is approval-required because it leaves the machine
  and cannot be unsent, and the approval shows the exact redacted outbound
  request.
* **The notice names what now exists.** Approving a git write used to end at
  *"Executed once: executed."* — true and useless. The executor's summary now
  travels with the artifacts, so the inbox reads *"Executed once — Committed 1
  file(s) as 75f310f on feature/subtract."*

**Also fixed here.** `ApprovalDetailView.preview_kind` in
`apps/web/src/lib/apiTypes.ts` declared `"file_diff" | "patch" | "arguments"`
while the server had been returning `connector_request` for a `connector_write`
since FIXED-41. The union now names every shape the server produces, and a
connector request renders as its own labelled block instead of falling through to
the raw-arguments branch.

**Verified live** against a running `raiker-web` on **2026-08-08**, hosted
Anthropic `claude-haiku-4-5-20251001`, with the workspace a real git repository:
the capability control (`working/b11-git-write-capability.png`), the branch
approval naming its refs (`b11-branch-approval.png`) and its execution
(`b11-branch-executed.png`), the commit approval carrying the file list and diff
(`b11-commit-approval.png`) and its execution (`b11-commit-executed.png`), the
GitHub write held at the connector gate (`b11-github-write-approval.png`), and
the off switch returning it honestly to record-only
(`b11-gate-off-record-only.png`). Each claim was then checked against git itself
rather than against the product — branch, log subject, clean status, and
`.raiker` absent from `ls-files`. Spec:
`apps/web/e2e/b11-git-write-path-live.spec.ts`; unit coverage:
`tests/test_git_write_path.py`. Threat model:
`docs/threat-models/git-write.md`.

---

## FIXED-110 — The git tools could not reach a repository connected as a sub-folder

**Status: fixed in this change. Was BUG-66, found while implementing FIXED-109.**

**Observed.** `git_status`, `git_diff`, `git_log`, `git_branch` and `git_commit`
all ran against the workspace root. Build lets an owner connect a repository that
is a *folder inside* the workspace (`POST /api/code/repos`, kind `local`), and no
git tool could see it: they reported the workspace's own repository, or
`not_a_git_repository` when the workspace root was not one.

**Reproduce.** In a workspace that is not itself a repository, connect
`projects/service` in Build and press **Use**. Ask for `git_log`. The answer is
`not_a_git_repository` against the workspace root, while the header says
*"Working in service"*.

**Root cause.** `raiker/tools/git.py` resolved every call with
`resolve_workspace_path(workspace_root, ".")`. The selection Build stores in
`code_repos.selected` was read by the Build view and by nothing else, so the
connection surface and the tools disagreed about what the agent was working in.

**Fix applied.** `selected_repository_subpath` reads the owner's selected
local repository and `resolve_repository_root` resolves it through the *same*
workspace containment check every other path read uses — a stored sub-path that
escapes the workspace, or names a folder that is gone, falls back to the
workspace root rather than widening the tools' reach. The broker
(`ToolBroker.git_root`), the approval preview (`ControlDashboard._git_root`) and
the executor (`GitWriteExecutor`) all resolve it the same way, per call rather
than cached, because the owner can change the selection between turns and a
cached answer would commit into the repository they stopped working in.

**And the approval says which one.** A workspace can hold more than one
repository, so every git proposal now carries a workspace-relative
`repository` label: the commit preview reads *"3 file(s) on main in repository
service"*, the branch and push previews carry a `repository` line, and the
executed summary names it (*"…on main in service."*). A workspace that is its own
repository is labelled `.` and the summary leaves the clause out, because naming
it there would be noise in the one sentence the owner reads after approving.

**UI when closed.** A commit approval states the repository it will be recorded
in, and a connected sub-folder repository is the one the git tools read.

**Verified live** — see FIXED-111 below.

---

## FIXED-111 — A committed branch could not be pushed

**Status: fixed in this change. Was BUG-67. Closes the last of GAP-BUILD B11.**

**Observed.** FIXED-109 let the agent create a branch and record a commit on it.
There was no push. `github_write` opens a pull request through the connector, and
GitHub can only open one for a head branch that already exists on the remote — so
the outward half was only usable for a branch somebody else had pushed.

**Why it matters.** "Make the change, commit it, open the PR" is one motion in
every product this is measured against, and it broke in the middle.

**Fix applied — a push is not a local write, and does not answer to the same
switch.**

* **Its own capability.** `git_push` maps to `git_push_execution` — Permissions →
  Network → **Git push** — not to `git_write_execution`. An owner who let the
  agent commit has not thereby let it publish, and one switch over both would
  have made that a package deal. It is Tier 2 rather than Tier 1 for the reason
  every other Tier-2 capability is: it reaches the network.
* **Two boundaries the gate cannot substitute for.** The remote's host must be on
  the owner's `RAIKER_CONNECTOR_EGRESS_ALLOWLIST`, and `RAIKER_GITHUB_TOKEN` must
  be set. Neither is model-supplied and both are re-checked at execution, against
  the machine as it is then rather than as the approval found it.
* **Only the host the credential belongs to.** `RAIKER_GITHUB_TOKEN` is a GitHub
  credential; sending it to another forge because a remote happens to be HTTPS
  would be a credential leak dressed up as a feature. A non-GitHub host is
  refused as `unsupported_remote_host` naming the host and the credential it
  would have needed. An SSH remote is refused too: it authenticates with a key
  this process does not govern.
* **The preview is computed without touching the network.** Asking the remote for
  its refs would be egress performed *before* the owner approved any, so
  `proposed_push_snapshot` says what this machine last knew — the remote and its
  host, the branch, whether the remote has ever seen it, and the commits it does
  not have. For a branch the remote already tracks that is everything past its
  last known position; for one it has never seen it is what no ref on that remote
  already reaches, so a fork of `main` reports the one commit it adds rather than
  its whole history.
* **It never forces and never deletes.** The refspec is written out in full
  (`refs/heads/<branch>:refs/heads/<branch>`), so a branch name can neither be
  read as an option nor move a ref it does not name. `--force`, `--delete` and
  `--mirror` are not reachable from the tool at all.
* **The credential never reaches the command line.** It is passed in the child's
  environment and read by an inline credential helper, so it is absent from the
  process table and from any captured command. An *empty* helper is configured
  first, so a system keychain cannot quietly supply a different account's
  credential than the one the owner governed. `GIT_TERMINAL_PROMPT=0` keeps a
  failure a named failure rather than a process blocked on a prompt, and git
  output is scrubbed of the token before it is stored or returned.
* **Hooks still never run.** `-c core.hooksPath=raiker-no-such-hooks` on the push
  too: `.git/hooks/pre-push` is workspace content the agent may itself have
  written.
* **Refusals are named.** `not_a_git_repository`, `detached_head`,
  `unknown_branch`, `no_remote_configured`, `unknown_remote`,
  `unsupported_remote_url`, `insecure_remote_url`, `remote_url_has_credentials`,
  `unsupported_remote_host`, `push_egress_denied`, `push_credential_unset`,
  `nothing_to_push`, `push_rejected_non_fast_forward`,
  `push_authentication_failed`, `push_timed_out`.
* **The sentence a push gets is not the sentence a commit gets.** The approval
  reads *"Approving this sends the commits above to the remote shown, once, with
  your own credential. It never forces and never deletes a branch, but it leaves
  this machine and git cannot take it back — undo it on the remote."*

**UI when closed.** After approving a commit, the owner can approve a push to a
named remote and branch, and the pull-request proposal then has a head to point
at.

**Verified live** against a running `raiker-web` on **2026-08-08**, hosted
Anthropic `claude-haiku-4-5-20251001`, with the workspace a real git repository
holding a second repository at `projects/service` and an HTTPS GitHub remote:
the capability standing apart from Git writes
(`working/bug67-git-push-capability.png`); the sub-folder repository connected
and selected (`bug66-subfolder-repository.png`) and `git_log` answering with
*that* repository's history rather than the workspace's
(`bug66-subfolder-git-log.png`); the push approval naming repository, remote,
host, branch and the one commit it would send (`bug67-push-approval.png`); the
execution (`bug67-push-executed.png`); the honest `nothing_to_push` refusal on
the second attempt (`bug67-nothing-to-push.png`); and the off switch returning it
to record-only (`bug67-gate-off-record-only.png`). Each claim was checked against
the remote rather than against the product — `git ls-remote` reported the branch
at exactly the commit this machine held after the approval, and unchanged after
the refused one. Spec: `apps/web/e2e/bug67-git-push-live.spec.ts`; unit coverage:
`tests/test_git_push_path.py`. Threat model: `docs/threat-models/git-push.md`.

---

## FIXED-112 — A proposal the runtime had already refused was raised as a decision

**Status: fixed in this change. Found while verifying FIXED-111.**

**Observed.** Asking for a second `git_push` with nothing left to send parked the
turn on an approval. The owner was asked to decide on a push the runtime had
already established it would not perform, and only learned why *after* approving
it. The same held for every approval-bearing tool whose own proposal refused: a
`write_file` into `.raiker/`, an `edit_file` whose `old_text` no longer matched,
a `git_commit` with a clean tree.

**Root cause, in three layers.** `ToolBroker.execute` computed
`_approval_preview` and then created the approval regardless of what the preview
said. The orchestrator then classified the call by the *policy verdict* alone:
`needs_approval` meant "park the turn", whatever the broker had actually
returned.

**Fix applied.** A proposal whose own precondition check already failed is a
refusal, not a decision:

1. The broker returns the snapshot's named error as the tool result and creates
   no approval row (`_unperformable_proposal`).
2. The orchestrator's boundary is now the *approval*, not the verdict that would
   have raised one: a call answered by the broker itself is an ordinary completed
   call with a failed outcome. Parking on it would have stranded the turn on an
   approval that does not exist; calling it a policy refusal would have replaced
   the named, correctable reason with a verdict that is not what happened.
3. So the model is handed the reason and can correct the call or explain it,
   which is what the owner sees: *"There was nothing to push — the branch is
   already up to date with the remote `origin`."*

Nothing is weakened by refusing earlier: a call that never reaches an approval
never reaches an executor either.

**Verified live** — `bug67-nothing-to-push.png`, and unit coverage in
`tests/test_git_push_path.py::TestUnperformableProposal` and
`tests/test_tool_broker.py`.

---

## FIXED-113 — Every turn started cold: the repository had no index

**Status: fixed in this change. Was GAP-BUILD B9.**

**Observed.** Build knew the workspace root and nothing about what was inside it.
Asked where `reconcile_meridian_ledger` was defined, the agent's only move was to
guess a `grep` pattern and read the misses — and on a repository of any size, a
guess that matches a mention rather than a declaration sends the next several
tool calls to the wrong file. There was no symbol index, no map of the tree, and
nothing in the turn bundle that said what the repository contained.

**Why it matters.** This is the whole distance between an agent that can act in a
codebase and one that has to be told where everything is first. Every capability
Build already had — the governed write (FIXED-08), the hunk-level patch
(FIXED-23), the commit (FIXED-109) — assumes the agent can *find* the code it is
about to change. Finding it by pattern-matching is the step that fails silently:
`grep` returns something, so nothing reports a miss.

**Root cause.** `raiker/graph/indexer.py` held a Python-only AST walker that
persisted nothing and was reachable only through a Phase-3 executor that indexed
into memory and discarded the result. `retrieve_hybrid_memory` searched *approved
memories*, not code. Nothing scanned a repository, nothing stored what it found,
and nothing put any of it in front of the model.

**Fix applied.** A real, governed, incremental code map:

1. **The scan** (`raiker/graph/codemap.py`). A bounded, deterministic walk of one
   repository: dot-directories, vendored trees, symlinks, binaries and oversized
   files are skipped and *counted*; Python is parsed with `ast` (exact) and
   fifteen other languages with bounded per-line patterns (approximate, and each
   file records which extractor produced it). Every limit in `CodeMapLimits` is
   enforced during the walk, and a scan that hits one reports `partial` naming
   the bound — a partial map can never present itself as a complete one.
2. **The store** (`RAIKER-2040-repository-code-map`). Four owner-scoped tables
   keyed by the workspace-relative repository path, so the unselected case — the
   workspace root — has a home rather than a special case. A file row carries its
   `sha256`, which is what makes a refresh incremental.
3. **The switch.** `code_map_indexing` is a capability with a real executor
   (`CodeMapIndexExecutor`), an activation requirement, and a control on
   Permissions → Workspace. It is deliberately **not** `graph_codemap_indexing`:
   that name belongs to the Phase-3 durable governed graph store — records with
   provenance, approval previews, rollback plans — which is still a dry-run
   planner. One switch must not mean two subsystems, so that capability, its
   readiness flags, and every assertion about it are left exactly as they were.
4. **When it is built.** On repository connect, on selecting a repository that
   has never been indexed, and on the owner's own **Rebuild index** control.
   Never on a turn: indexing is the owner's decision, not the runtime's.
5. **Staying honest.** After an approved file mutation really lands,
   `ApprovalExecutionRelay` re-parses exactly the paths it touched
   (`code_map_refreshed`). It is best-effort in the strict sense — a refresh that
   fails changes nothing about the write that succeeded, because an approved
   change is never rolled back for a derived cache.
6. **Reaching the model.** `code_map_search` is advertised, read-shaped in the
   policy engine, delegable to a subagent, and citable as a turn source. It
   returns **coordinates, not code** — path, line range, signature, docstring
   first line — so reading the file still goes through `read_file`, workspace
   containment and the policy engine. The map grants nothing.
7. **Reaching the turn.** A `code_map` context item carries the ranked files and
   their declarations, marked `untrusted_external`: symbol names and docstrings
   are copied out of repository files, which is exactly where an injected
   instruction would sit. A prompt that matches nothing gets the
   most-declaration files as orientation; a gate that is off, or a repository
   never indexed, contributes **nothing** rather than a placeholder.

**Verified live** against a running `raiker-web` on hosted Anthropic
`claude-haiku-4-5-20251001` —
`apps/web/e2e/b9-repository-code-map-live.spec.ts`, six scenarios, all passing —
and by `tests/test_repository_code_map.py` (21 cases) and
`apps/web/src/lib/components/RepoConnector.test.ts`.

| Screenshot | What it shows |
|---|---|
| `working/b9-model-connected.png` | the credential added through Models, Haiku 4.5 selected |
| `working/b9-code-map-off-by-default.png` | the resting state — indexing off, the panel saying so, and nothing to press |
| `working/b9-code-map-built-on-connect.png` | **Code map · ledger-app — 2 files, 3 declarations**, built by connecting the repository |
| `working/b9-code-map-search-answer.png` | **the gap itself, closed** — *"`reconcile_meridian_ledger` is defined in `services/ledger.py` at lines 11–13"*, with the code map in the answer's source ledger |
| `working/b9-code-map-gate-off.png` | the owner's off switch, quoted back verbatim: `{"type": "code_map_gate_disabled", …}` |
| `working/b9-code-map-refreshed-after-write.png` | an approved `write_file`, then the same tool finding `audit_meridian_trail` in `services/audit.py` — the index caught up with the change |

**UI when closed.** Build states what its repository's index holds and offers to
rebuild it; an answer about where code lives names the file and the lines, and
says the code map is where it looked.

---

## FIXED-114 — Build showed repository state as it stood before a visit to Permissions

**Status: fixed in this change; found while verifying FIXED-113.**

**Observed.** Turning **Code map** on in Permissions and returning to Build left
the repositories panel still saying indexing was off. Pressing the control it
offered would have been refused by a gate that was no longer closed.

**Root cause.** `App.svelte` keeps Build mounted and merely `hidden` — that is
deliberate, and it is what preserves a transcript across navigation. But
`loadRepos()` ran only in `onMount`, so everything the panel showed was as it
stood the first time Build was opened, however long ago that was.

**Fix applied.** `App.svelte` passes `visible={current === "build"}` and BuildView
re-reads its repository state whenever it becomes visible. The transcript is
untouched — it is the state read from the server that is refreshed.

**Why it is filed here rather than shipped silently.** It is the same class as the
defects this document keeps recording: a surface stating a posture that stopped
being true, with nothing holding the two together.

---

## FIXED-116 — A fresh workspace silently defaulted to llama.cpp instead of Ollama

**Status: fixed in this change.**

**Observed.** With no saved model selection, the runtime chose the shipped
llama.cpp profile while Chat and Build showed **Not selected**. This contradicted
the requested local-first default and made the model serving a first turn
different from the model presented in the composer.

**Root cause.** Both shipped copies of `model-profiles.json` marked llama.cpp as
`is_native_default`, the Ollama profile still carried the unresolved `<model>`
placeholder, and `ModelRouter.default_provider()` ignored the registry flag and
hard-coded the first llama.cpp profile. `GET /api/models` also returned a null
selection when no row had been persisted, so the UI could not render the
runtime fallback.

**Fix applied.** `ollama-local-openai-compatible` now ships with concrete model
`gemma4:31b-cloud` and is the sole native default. The router resolves the
registry marker instead of naming a provider in code. A fresh Models response
projects that default as the current, selected model without creating a hidden
user preference; an explicit owner selection still wins and persists exactly as
before. Backend, API, context-injection, CLI-listing and turn-binding regression
tests cover the complete path.

**UI when closed.** On a fresh workspace, the Models card, top-bar chip, Chat
composer and Build composer all identify **Gemma 4:31B Cloud · Ollama** before
the owner changes anything.

---

## FIXED-117 — Container tools could not complete a cold, real Docker run

**Status: fixed in this change; found during ADD-01 live Docker verification.**

**Observed.** The injected-runner tests passed, but a clean process could not
import `ContainerToolExecutor`. After that was exposed, the real Docker process
could import the bridge but received an empty stdin stream and returned
`container_bridge_request_invalid`.

**Root cause.** Importing `raiker.runtime.executors.containers` executed the
package initializer, which eagerly imported orchestration and the broker back
into the partially initialized container module. The container command also
mounted the repository without making it the bridge working directory, and
Docker was started without `--interactive`, so its stdin was detached.

**Fix applied.** Broker-dependent orchestration imports are deferred until use;
the bridge starts in `/repository` with bytecode writes disabled; and the shared
Docker/Podman command attaches stdin explicitly. A subprocess cold-import
regression and command-boundary assertions cover all three conditions. A live
`python:3.12-alpine` run read `README.md` through the real no-network bridge and
cleaned its action workspace.

---

## FIXED-118 — The execution-environment badge linked to a route that did not exist

**Status: fixed in this change; found during ADD-01 Playwright verification.**

**Observed.** Clicking the badge, or opening `#/settings/runtime`, silently
returned the owner to Workbench instead of Runtime configuration.

**Root cause.** Settings kept its active section only as component-local state;
the application router knew nothing about Settings tabs, while the badge emitted
an invented nested route.

**Fix applied.** Settings sections are now first-class `?tab=` destinations in
the shared hash parser. The section rail writes that URL, App passes the resolved
tab, and the badge links to `#/settings?tab=runtime`. Unit tests cover both the
router and the rendered destination; the corrected deep link completed the live
container-profile flow.

---

## FIXED-119 — Offline gateway tests changed meaning when local Ollama was running

**Status: fixed in this change; found during ADD-01 baseline verification.**

**Observed.** Tests intended to prove offline failure started succeeding on a
developer machine that had the shipped Ollama default available.

**Root cause.** Those scenarios relied on ambient provider availability instead
of naming the unavailable model boundary they were testing.

**Fix applied.** An opt-in `offline_default_model` fixture gives only those
scenarios a deterministic unreachable default. Ordinary tests and live runs keep
the real Ollama default, so the fixture cannot conceal a product regression.

---

## FIXED-120 — Machine identity chips overwhelmed the Activity actor column

**Status: fixed in this change; found during ADD-03 screenshot review.**

**Observed.** Every event for a signed turn repeated the complete machine turn
ID inside the visible actor chip. At realistic UUID length the actor column
became wider than the event summary and made a dense audit table difficult to
scan.

**Root cause.** `IdentityChip` rendered the API's audit-grade `display_name`
verbatim even though the component already retained the complete principal ID
in its title.

**Fix applied.** Machine chips now render `shortId(turn_id)` while retaining the
full principal in the title and the unchanged API contract. A component test
first reproduced the long-ID layout behavior, then focused Activity/Approvals
tests, Svelte check, ESLint, production build, screenshot review, and all three
provider live turns verified the correction.

---

## FIXED-121 — A passing export test emitted a delayed jsdom navigation error

**Status: fixed in this change; found during ADD-03 full verification.**

**Observed.** The complete Vitest suite passed, but an asynchronous
`Not implemented: navigation` error appeared after its result while the next
quality gate was running.

**Root cause.** The export test called a real temporary anchor's `click()` and
described it as a jsdom no-op. jsdom instead schedules navigation after the
test, even for a download anchor.

**Fix applied.** The test now models the browser download boundary explicitly by
spying on `HTMLAnchorElement.click`, asserts that the download was requested,
and leaves no delayed navigation task. The full 82-file, 706-case web suite then
completed without the console error.

---

## FIXED-122 — Windows host-status checks could interrupt the process they inspected

**Status: fixed in this change; found during ADD-03 full verification.**

**Observed.** The complete Python suite reached `test_app_lifecycle` and ended
with `KeyboardInterrupt` while asking whether its own recorded host PID was
alive. The same status read could affect a real Windows Raiker host.

**Root cause.** `process_is_alive` treated `os.kill(pid, 0)` as a portable
read-only probe. That is the POSIX contract; CPython on Windows maps `os.kill`
to Windows process signaling, so it is not a safe liveness query.

**Fix applied.** Windows now opens a `PROCESS_QUERY_LIMITED_INFORMATION` handle,
checks `GetExitCodeProcess == STILL_ACTIVE`, and always closes the handle. Access
denied still proves existence; malformed PIDs fail closed. POSIX retains signal
zero. A regression proves the Windows dispatch never calls `os.kill`, and all
38 lifecycle tests now pass on Windows without interrupting their host.

---

## FIXED-123 — Plugin execution generated an unsupported fallback turn ID

**Status: fixed in this change; found during ADD-03 full verification.**

**Observed.** Every plugin action without an existing turn failed before its
permission or revocation checks with `unsupported_id_prefix:turn_plugin_`.

**Root cause.** The machine-identity relay added a descriptive ID prefix that
was not part of Raiker's closed ID registry. A plugin fallback is still an
ordinary governed turn; it does not need a new identifier class.

**Fix applied.** Plugin execution now mints the registered `turn_` identifier
and then issues its signed machine identity. Installed, missing, permission-
denied, write-refused, workspace-boundary, and revoked plugin tests all pass.

---

## FIXED-124 — Project exports reversed events created in the same second

**Status: fixed in this change; found during ADD-03 full verification.**

**Observed.** Two audit events appended in order within one timestamp second
were exported as `second`, then `first`.

**Root cause.** Event-index reads sorted only by second-resolution timestamp.
The exporter reverses the newest-first query for chronological output, but rows
with equal timestamps had no deterministic insertion-order tie-breaker.

**Fix applied.** Event-index reads now order equal timestamps by SQLite row ID
descending; the export reversal therefore restores chronological insertion
order. The project export regression and the complete affected test set pass.

---

## FIXED-125 â€” Auto and skip execution replaced the machine actor with the owner

**Status: fixed in this change; found during ADD-03 independent review.**

**Observed.** Tool actions named the signed machine proposer, but the ordinary
auto/skip route constructed downstream authority and execution evidence with the
human owner principal.

**Root cause.** The preapproved helper reused its former human-bypass principal
instead of the verified action proposer.

**Fix applied.** RuntimeAuthority now receives the machine principal. Storage
resolves its delegated owner only for account resources and control settings;
execution posture remains machine-attributed. A regression proves this through
a real file executor.

---

## FIXED-126 â€” Non-terminal exits leaked active machine principals

**Status: fixed in this change; found during ADD-03 independent review.**

**Observed.** Gateway exceptions and abandoned streams, terminal memory
helpers, plugin relays, and subagent completion could leave short-lived
principals active until expiry.

**Root cause.** Those owning paths issued identities without a common terminal
cleanup boundary.

**Fix applied.** Each owner now closes its lifecycle in `finally` or its single
terminal helper. Approval suspension remains deliberately active for rotation.
Exception, stream-close, CLI, plugin, subagent, and resume regressions cover it.

---

## FIXED-127 â€” Activity hid the event actor behind a contextual turn identity

**Status: fixed in this change; found during ADD-03 independent review.**

**Observed.** Every event joined to a turn identity displayed the agent chip in
the Actor column, including broker, executor, issuer, and human-driven events.

**Root cause.** The UI treated turn context as event authorship.

**Fix applied.** Activity now has separate Actor and Turn identity columns. The
literal audit emitter is always visible; the signed identity remains contextual
and copyable.

---

## FIXED-128 â€” Resume rotation could rewrite approval identity metadata

**Status: fixed in this change; found during ADD-03 independent review.**

**Observed.** Approval reads joined the machine principal's current issue and
expiry timestamps, so rotating a suspended turn changed what an old proposal
appeared to have used.

**Root cause.** Only subject and token ID were stored on the action; remaining
claims came from the mutable current identity row.

**Fix applied.** Migration `RAIKER-1041-machine-action-identity-snapshot` stores
key ID, issue time, and expiry with the existing token ID on each proposal.
Approval reads use that immutable snapshot, verified by a rotate-after-proposal
regression.

---

## FIXED-129 â€” Authority matrix ignored failed readiness facts

**Status: fixed in this change; found during ADD-03 independent review.**

**Observed.** An enabled gate with a false readiness fact appeared Direct.

**Root cause.** Derived authority considered gate state and decision mode only.

**Fix applied.** Any false readiness fact now yields owner `Not ready` and agent
`Unavailable`; a component regression covers the distinction.

---

## FIXED-130 â€” Approval identity metadata overlapped at desktop width

**Status: fixed in this change; found during ADD-03 screenshot review.**

**Observed.** The machine proposer chip, expiry timestamp, and batch copy could
overlap in the approval detail grid at 1440 px.

**Root cause.** Auto-fit columns allowed ten-rem cells even though the identity
chip needs a wider intrinsic area.

**Fix applied.** Metadata cells now use a responsive sixteen-rem minimum and a
bounded label/value subgrid with safe wrapping. Provider approval screenshots
were visually reviewed after the change.

---

## FIXED-131 â€” Concurrent first-use store bootstrap deadlocked in FTS repair

**Status: fixed in this change; found in ADD-03 GitHub CI.**

**Observed.** Two first-use identity issuers constructed stores concurrently.
On Linux SQLCipher, both deferred bootstrap transactions reached the memory FTS
rebuild and one failed with `database is locked`.

**Root cause.** Process-local store bootstrap was not serialized, and the FTS
repair handler treated every operational error—including a transient lock—as
legacy projection corruption before attempting a destructive table rebuild.

**Fix applied.** Store construction now serializes schema/FTS bootstrap within
the process, and the repair path re-raises lock errors instead of interpreting
them as corruption. The existing concurrent first-use issuer regression covers
the hosted failure.

---

## FIXED-132 â€” Linux MyPy rejected guarded Windows process APIs

**Status: fixed in this change; found in ADD-03 GitHub CI.**

**Observed.** Runtime tests and Windows MyPy passed, but Linux MyPy rejected
direct references to `ctypes.WinDLL` and `ctypes.get_last_error` in the safe
Windows-only process probe.

**Root cause.** The runtime platform guard does not change the Linux typeshed
surface, where those Windows-only module attributes are intentionally absent.

**Fix applied.** The probe now resolves both APIs dynamically and fails closed
when either is unavailable. MyPy is verified with an explicit Linux platform in
addition to the ordinary local check.

---

## FIXED-154 — The context meter read `NaN input · NaN output`

**Status: fixed in this change. Was BUG-68, found on 2026-08-08 executing §5.5
of the live manual test plan against hosted Anthropic
`claude-sonnet-4-5-20250929`, and closed live on 2026-08-10 against hosted
Anthropic `claude-haiku-4-5-20251001`.**

**Observed.** The Chat context popover renders correct totals and then a line of
nonsense beneath them:

```
Context window                       0.35%
706 tokens used
of 200,000 available
199,294 tokens remaining
NaN input · NaN output
Reported by anthropic · Capacity reported by runtime
```

Every other figure in the panel — used, capacity, remaining, this-chat cost,
provider all-time cost, and all four price components — is right. Only the
per-direction split is `NaN`.

**Reproduction.** Connect Anthropic, run any turn in Chat, open **Context
window** in the composer. Identical in Build.

**Root cause.** `GET /api/sessions/<id>/context-usage` returns:

```json
"session_input_tokens": "***REDACTED***",
"session_output_tokens": "***REDACTED***"
```

`raiker/api/redaction.py` discards any field whose key matches
`SECRET_PATTERNS`, and `"token"` is one of those patterns. The exemption for
counts is an allowlist — `NON_SECRET_TOKEN_COUNT_KEYS` in
`raiker/events/export.py:35` — and it lists `input_tokens` and `output_tokens`
but **not** the two `session_`-prefixed names the context contract actually
emits (`raiker/control/dashboard.py:3818`). The browser then calls
`number.format("***REDACTED***")`
(`apps/web/src/lib/components/ContextMeterPopover.svelte:105`), which is `NaN`.

This is the same failure FIXED-02 closed for `context_window_tokens`, reopened
by two field names added afterwards that the allowlist was never extended to
cover.

**Fix applied.** `session_input_tokens` and `session_output_tokens` are on
`NON_SECRET_TOKEN_COUNT_KEYS` (`raiker/events/export.py`), under the exemption's
existing rule: an exact key name from the set **and** a non-boolean integer
value. A string or a boolean under either name is still redacted, so a
credential can never ride out under a count-shaped key.

Naming the two fields would have fixed the symptom and left the class open — it
is the second time a count added after FIXED-02 was not added to the allowlist.
So the regression is now held by the *contract* rather than by the two names:
`tests/test_token_count_redaction.py` builds a fully populated
`ContextUsageView`, runs it through `redact_response_body`, and asserts that
**every integer field on it** survives. A count added to that view in future
either survives redaction or fails this test on the day it is added.

**UI when closed.** The line reads e.g. `624 input · 82 output`.

**Evidence.** `screenshots/not-working/BUG-r0808-01-context-popover-NaN-io-tokens.png`
(before) and [`working/r0810-bug68-context-meter-real-io-counts.png`](screenshots/working/r0810-bug68-context-meter-real-io-counts.png)
(after, live).

---

## FIXED-133 — A new user's first message failed with a raw reason code

**Status: fixed on 2026-08-09 as FIXED-133. Found on 2026-08-08 on a pristine
workspace. Regression surface introduced by FIXED-116.**

**Observed.** On a brand-new workspace, an owner who registers and immediately
types a message gets, as the entire reply:

```
model_unavailable: provider_error_unclassified
```

No explanation, no named provider, no remedy, no link to Models. It is the first
thing Raiker ever says to that person.

**Reproduction.**

1. `raiker-web --workspace <empty dir> --port 8766 --no-browser` on a machine
   with no Ollama installed (the common case).
2. Register the owner.
3. Type `Say OK.` in Chat and press Enter.

**Root cause.** FIXED-116 deliberately made `ollama-local-openai-compatible`
with model `gemma4:31b-cloud` the sole native default, and projects it as the
selected model before the owner chooses anything. That is correct as a
*preference*, but nothing checks whether Ollama is actually reachable. Three
surfaces then state a readiness that does not exist:

* the Workbench and Chat composers show **Gemma 4:31B Cloud** as the model,
* Models says **1 of 10 providers set up**,
* the Ollama card's only hint is the body copy "Run Ollama locally, then choose
  one of its installed models" — while the card itself reads *Not connected*.

The turn then dies inside the provider adapter and the unclassified error is
rendered verbatim into the transcript.

**Proposed fix.** Three separate outcomes, all required:

1. A default that is only a *preference* must not be counted as a provider that
   is *set up*. The "N of 10 providers set up" counter, and the composer's
   ready-state, should reflect a reachable provider.
2. `provider_error_unclassified` must never reach a transcript. A local provider
   that cannot be reached should say so in the owner's words — which provider,
   that it is not running on this machine, and the one control that fixes it —
   exactly as FIXED-05/BUG-05 did for the Connect dialog.
3. On a first run with no reachable provider, Chat should route the owner to
   Models before they can send, rather than letting the first turn fail.

**UI when closed.** A fresh install either answers, or explains in a sentence
why it cannot and where to go. It never prints a reason code.

**Evidence.** `screenshots/not-working/BUG-r0808-05-fresh-workspace-defaults-to-absent-ollama.png`,
`BUG-r0808-05-models-claims-one-provider-set-up.png`,
`BUG-r0808-05-first-turn-raw-reason-code.png`.

**Implemented.** Readiness is now persisted against the owner, profile, exact
model, and endpoint fingerprint, expires after five minutes, and is invalidated
when any binding changes. Local providers must be reachable and list the exact
model. Hosted providers must additionally pass an owner-triggered one-token
execution preflight, so catalogue access with no billing or execution access is
not presented as ready. The shared gate disables model-backed actions in
Workbench, Chat, Build, Tasks, and Schedule, preserves drafts, and opens a
single setup dialog linking to Models. First run now prompts for provider/local
model setup.

Models now includes official Ollama and LM Studio setup paths, Ollama pull,
approved-root bounded GGUF discovery, managed loopback llama.cpp deployment,
durable operation views, and Hugging Face search with immutable revisions,
licence/gated review, GGUF-first downloads, and explicitly confirmed isolated
Safetensors conversion. No ambient filesystem scan or automatic conversion is
performed.

**Closing evidence.** Live Chromium on 2026-08-09 verified the first-run setup,
cross-surface disabled actions, local Ollama `gemma4:31b-cloud`, OpenRouter
`openai/gpt-4o-mini`, Anthropic catalogue success followed by a correctly
fail-closed account-credit execution preflight, approved-root GGUF discovery,
revision-pinned Hugging Face choices, a real tiny GGUF download, and completed
managed llama.cpp deployment. See the BUG-69 section in
`RAIKER_LIVE_MANUAL_TEST_PLAN.md` and the screenshot evidence index.

---

## FIXED-155 — Build's mode chips rewrote global decision modes with no step-up

**Status: fixed in this change. Was BUG-70, found on 2026-08-08 while exercising
Build's Plan / Edit / Auto control, and closed live on 2026-08-10.**

**Observed.** Pressing **Auto** in the Build composer issues, with no dialog and
no confirmation:

```
POST /api/capability-modes/file_write_execution/auto   200
POST /api/capability-modes/patch_apply_execution/auto  200
POST /api/capability-modes/shell_execution/auto        200
POST /api/capability-modes/process_execution/auto      200
```

Permissions afterwards shows **File writes → Auto** (`aria-pressed="true"`), and
the change is global: it persists across Chat, Tasks, and every later session
until something else changes it.

Making the *identical* change from the Permissions page requires a step-up
dialog — "Set File writes to Auto", the acting principal named, a **required**
reason, and a threat-model acknowledgement where the capability demands one —
with **Confirm change** disabled until they are supplied.

**Reproduction.** Permissions → note File writes is *Ask*. Build → press
**Auto**. Permissions → File writes is now *Auto*, with no recorded reason.

**What is *not* wrong.** The runtime still fails safe: with the mode at `auto` a
Chat `write_file` was still held for approval and no file was written. The
defect is in the authority record, not in the enforcement.

**Root cause.** `POST /api/capability-modes/<cap>/<mode>` is reachable without
the step-up ceremony the Permissions page applies to the same transition. Build
calls it directly, four times, from a chip that is presented as a per-turn
posture rather than as a change to the owner's standing permissions.

**Fix applied — option (b), and the chip says so.** The mode is now the
*conversation's* posture and nothing else. It rides with each prompt as a new
`capability_modes` map on `PromptOptions`, is applied to that turn by the
broker, and is persisted with a parked turn so a resume keeps the posture it was
sent under rather than picking up whatever the standing modes say hours later.
No composer writes `/api/capability-modes/` any more.

What makes that safe is that the map may only ever **tighten**. `ask` and `deny`
are the only values the envelope accepts (`validated_turn_capability_modes`);
`allow` and `auto` are refused with a named reason, because loosening is a change
to standing authority and belongs to the Permissions step-up. The broker refuses
them a second time, independently, so a caller reaching it directly cannot widen
a turn either. A `deny` posture refuses the call under its own reason code —
`denied_by_turn_posture`, kept distinct from `denied_by_decision_mode` so an
audit reader can tell "the owner denied this capability" from "this turn writes
nothing" — and an `ask` posture also forces `approval_mode` back to `manual`, so
a turn that asked to see its decisions cannot have them executed underneath it
by the unattended modes.

That leaves **Auto** doing exactly as much as the owner already allowed. Silently
promising more would be the same lie in the other direction, so the composer
reads the standing modes (read-only) and states what it found: *"Every write
capability is set to Ask, so every change will still be proposed to you."* —
with **Change in Permissions →** beside it, which is where the ceremony lives.

**Found and closed with it.** `PermissionModeControl.svelte` — **BUG-63**, a
composer control that rewrote the decision mode of *every* capability in one
selection and was imported by nothing — is deleted. Leaving a bulk permission
mutation one import away while removing the four-capability one would have kept
the defect in the tree.

**UI when closed.** Pressing a Build mode chip changes no standing permission,
says the posture applies to this conversation's turns only, and — for Auto —
names what the owner's standing permissions actually allow.

**Evidence.** `screenshots/not-working/BUG-r0808-03-build-chip-set-file-writes-auto-without-stepup.png`
(before); [`working/r0810-bug70-build-auto-changes-nothing-standing.png`](screenshots/working/r0810-bug70-build-auto-changes-nothing-standing.png),
[`working/r0810-bug70-permissions-unchanged.png`](screenshots/working/r0810-bug70-permissions-unchanged.png)
and [`working/r0810-bug70-plan-mode-refuses-the-write.png`](screenshots/working/r0810-bug70-plan-mode-refuses-the-write.png)
(after, live). Held by `tests/test_turn_capability_posture.py` and
`apps/web/src/lib/buildModes.test.ts`.

---

## FIXED-156 — Memory could never be written from Chat or Build

**Status: fixed in this change. Was BUG-71, found on 2026-08-08 executing the
memory scenarios, and closed live on 2026-08-10.**

**Observed.** Permissions lists **Memory store** with the description *"Persist
durable memories through the governed broker."* and all four decision modes. It
was turned on (`memory_write_execution` → `enabled_runtime`) and set to
**Allow**. Asked to save a durable fact, the agent answered:

> Here are the exact names of every memory-related tool available to me:
> `memory_get`, `memory_list`, `memory_search`. Unfortunately, none of these
> tools can save or write memories. All three are read-only. … the current mode
> is `read_only`.

After ~30 governed turns, `GET /api/memory` and `GET /api/memory/proposals` are
both `[]`, and the Memory page still reads *0 Approved · 0 Pending review* under
the promise "When Raiker identifies a useful preference or durable fact, it will
propose it for review."

**Root cause.** Not a missing executor — the broker has real ones:
`raiker/tools/broker.py:1422` routes `memory_write` to
`memory_service.write_from_action` and `memory_forget` to
`forget_from_action`, both fully governed. The gap is one layer up:

* **`memory_write` and `memory_forget` are absent from the model tool
  catalogue.** `_TOOL_DESCRIPTIONS` / `_TOOL_RISK` in
  `raiker/models/tool_call_validation.py` expose 39 tools, of which the only
  memory entries are `memory_search`, `memory_list` and `memory_get`. A turn
  therefore cannot propose a write at all, whatever the gate says.
* **`governed_memory_status` hard-codes the read-only posture.**
  `raiker/memory/candidates.py:36` returns
  `{"durable_writes_enabled": False, "mode": "read_only_review"}` as a literal,
  which is what the model reports back to the owner.

So the capability is genuinely broker-governed — reachable from the CLI, which
does call `memory_forget` (`raiker/cli/commands.py:1557`) — and simultaneously
unreachable from the two surfaces the Permissions row is displayed on.

**Why this is a defect and not a deferral.** Raiker already knows how to be
honest about a capability an agent cannot reach: **Remote execution** reads
*"No executor; remote command execution stays fail-closed."* **Memory store**
says the opposite of what a Chat user will experience. An owner can turn it on,
set it to Allow, wait, and never learn that no turn can act on it.

**Fix applied — the capability is real, so it is the surfaces that were wrong.**
Both halves are closed:

* **`memory_write` and `memory_forget` are in the model tool catalogue**
  (`raiker/models/tool_call_validation.py`), in the same band as `create_task`:
  high risk, approval-bound, local, owner-scoped and reversible. Both were
  already mapped to their own capability gates and already had real executors;
  what was missing was any way for a turn to propose one.
* **`governed_memory_status` reads the gate instead of asserting a literal**
  (`raiker/memory/candidates.py`). It now reports the live gate state and
  decision mode for `memory_write_execution` and `memory_forget_execution`, and
  distinguishes the three cases the literal collapsed: `read_only_review` (the
  gate is off), `denied_by_decision_mode` (on, and the owner denied it), and
  `governed_write` / `governed_write_review` (on, and a write is reachable).
  That is the string the model quotes back when a user asks whether it can
  remember something, which is why it contradicted the owner's own Permissions
  page.

Two things had to follow, or the fix would have stopped one layer short of the
owner again:

* **An approved memory write really writes.** `memory_write_execution` and
  `memory_forget_execution` are on `EXECUTABLE_ON_APPROVAL` — the same argument
  that put a task row and a project label there (local, reversible,
  owner-scoped). Without them the model could propose, the owner could approve,
  and nothing would be remembered.
* **The decision is about text, so the owner sees the text.** The approval
  preview carries the exact sentence that would be stored (or the record that
  would go), and credential-like text is refused *before* anyone is asked to
  approve it rather than after. A forget naming a record that does not exist is
  a refusal with a named reason, not a decision — the class FIXED-112 stopped
  raising.

The Memory page no longer promises what it cannot produce: a posture strip reads
the gate and says either "Memory store is off, so no conversation can propose
something to remember" with **Turn on Memory store →**, or what it will do now
that it is on. The capability rows say what the owner will actually experience
rather than naming the broker.

**Evidence.** `screenshots/not-working/BUG-r0808-04-memory-store-capability-has-no-executor.png`
(before); [`working/r0810-bug71-memory-says-the-gate-is-off.png`](screenshots/working/r0810-bug71-memory-says-the-gate-is-off.png),
[`working/r0810-bug71-memory-says-the-gate-is-on.png`](screenshots/working/r0810-bug71-memory-says-the-gate-is-on.png)
and [`working/r0810-bug71-chat-proposes-a-memory-write.png`](screenshots/working/r0810-bug71-chat-proposes-a-memory-write.png)
(after, live). Held by `tests/test_memory_write_path.py`.

---

## FIXED-142 — Enabling Web fetch made every turn that used it fail

**Status: fixed in this change. Was BUG-72, found on 2026-08-08 executing the
network-capability scenarios, reproduced 4 / 4 on that host.**

**Observed.** With `web_fetch` at `enabled_runtime` and decision mode **Allow**,
every turn that called it returned, as the whole answer:

```
model_unavailable: provider_stream_failed
```

The turn was lost. The same prompt with the mode left at **Ask** completed
normally, so the failure appeared only when the tool was actually permitted to
run. Nothing was logged, and the message blamed the model — Anthropic answered
fine on the turn before and the turn after.

**Reproduction.** Permissions → **Web fetch** → Turn on → **Allow**. Chat →
*"Use web_fetch to read https://example.com and quote its main heading
exactly."*

**What this entry does and does not claim.** The 2026-08-10 verification round
could **not** reproduce the symptom: on a host where the fetch completes in
about a second, the same scenario answers correctly on the unfixed code. That is
consistent with the root cause below rather than evidence against it — the
failure is a race whose window is the length of the fetch. So the three defects
below are stated as what they are: one that certainly caused it, and two that
made it impossible to tell. All three are fixed, and all three are now held by
tests rather than by a live run nobody can reproduce on demand.

**Root cause 1 — a tool call ran on the event loop, and web_fetch is the
longest-blocking tool there is.** `ToolBroker.execute` is synchronous, and so is
every tool underneath it: `web_fetch` does a blocking `getaddrinfo` and then a
blocking HTTPS GET with a **fifteen-second** cap
(`raiker/runtime/web_access.py`). The orchestrator moved a call to a worker
thread **only when the batch held more than one read-only call**
(`raiker/runtime/orchestrator.py`, B4's parallel path); the ordinary single call
— exactly what BUG-72's reproduction asks for — ran inline on the asyncio loop.

For the length of that fetch the whole ASGI process was frozen: no other request
served, no Stop control polled, no SSE heartbeat, and — the failure that made
this a defect — no chance for the provider client to process the close of the
pooled keep-alive connection it was about to reuse. The next model request then
went out on a socket the far end had already closed, `httpx` raised
`RemoteProtocolError`, and the adapter turned that into `provider_stream_failed`.
At **Ask** the tool returns without touching the network, which is precisely why
that path never failed.

**Root cause 2 — the adapter destroyed the reason.** Both streaming adapters
ended with

```python
raise ProviderStreamError(type(exc).__name__) from exc
```

for every already-classified provider error, so an expired key, an exhausted
balance, a rate limit and a dropped connection all reached the owner as one
code that says only *a stream ended*.

**Root cause 3 — nothing was written down.** There was no log line at all for a
failed model call, and the turn's whole answer was a raw reason code.

**Fix.**

1. **No brokered tool ever occupies the event loop.** One
   `RuntimeOrchestrator._aexecute_tool` now runs *every* call — lone, batched, or
   drained from the approval queue — through `asyncio.to_thread`. Governance is
   untouched; only where the blocking work happens changed.
2. **A classified failure keeps its own code.** `stream_failure()` in
   `raiker/models/exceptions.py` returns an already-classified provider error
   unchanged and wraps only an unclassified one, carrying its exception *class*
   in the code — `provider_stream_failed:RemoteProtocolError`. The class name is
   metadata, never provider text, so this cannot carry a credential or a body
   fragment into an event.
3. **A transport failure is re-attempted once, on the same model.** A closed
   connection, a timeout, a provider 5xx and an unclassified mid-stream
   exception each earn exactly one immediate retry, recorded as
   `model_request_retried`. A *decision* — a rejected key, an empty balance, a
   missing model — earns none: asking again only spends the owner's quota to be
   told the same thing. Nothing is retried once output has been streamed.
4. **The failure is said in words, and written to the log.** The turn now
   answers *"I could not finish that: the provider rejected the saved
   credential. Update the key on Models, then try again. (model_unavailable:
   provider_auth_failed:http_401)"* — the repair first, the machine code kept
   for support and for the troubleshooting table. A partially streamed answer is
   **kept** and the failure appended, rather than being replaced by a code. Every
   failed model call also writes one `WARNING` naming the provider, the model,
   the exception class and the safe reason code.

**UI when closed.** With Web fetch on, the turn quotes the page. A refused fetch
names the capability and the host and never claims the model is unavailable; a
turn that genuinely cannot reach the provider says which failure it was and what
to do about it.

**Evidence.** `tests/test_bug_72_web_fetch_turn_survives.py` — fifteen tests
across the three defects, including one that runs a blocking tool call and
asserts a concurrently scheduled coroutine keeps ticking, which is the
regression that would let root cause 1 back in.
`apps/web/e2e/web-access-turn-control-live.spec.ts` passes 6 / 6 against a live
Anthropic `claude-haiku-4-5-20251001`:
`screenshots/working/b12-web-fetch-live-page.png` is the agent reading
`https://pypi.org/project/httpx/` and quoting *"The next generation HTTP
client."* with its source chip, and
`screenshots/working/b12-web-fetch-egress-denied.png` is a non-allowlisted host
refused by name.

**Not verified live here.** OpenAI, OpenRouter and Ollama could not be exercised
on the verification host: the sandbox network policy answers `openrouter.ai` and
`api.openai.com` with a proxy 403, and no Ollama daemon was available. The
OpenAI-compatible adapter — which is the path all three take — is covered by the
unit tests above.

---

## FIXED-157 — A conversation could end saying the approved action was not executed

**Status: fixed in this change. Was BUG-73, found on 2026-08-08 — intermittent
(observed once; three targeted reproductions did not recur) — and closed on
2026-08-10 by removing the race rather than by trying to win it.**

**Observed.** A Chat turn proposed `write_file live-round.md`. The approval was
reviewed and **Approve and execute once** reported *"Executed once — wrote
live-round.md. The previous contents were checkpointed."* The file is on disk
with the reviewed contents, and the conversation carries the `live-round.md ·
MD · 303 B` chip that opens it in the inspector.

The conversation's final assistant bubble nonetheless reads:

> Approval required for local action. No command was executed.

That state is durable: reopening the conversation any time later still shows it.

**Reproduction.** Not reliably reproduced. The one occurrence followed
approving from the Approvals page and then navigating to the conversation while
the automatic resume was still in flight, without pressing **Continue the turn**.
Three deliberate attempts to recreate it — with and without a follow-up
instruction in the prompt, and with a navigation away mid-resume — all resumed
correctly and ended with an accurate summary of the write.

**Why it matters anyway.** The transcript is the record a person reads. A
governed action that executed, was checkpointed, and changed the filesystem must
never be described in that record as not executed — and the failure survives a
reload, so nothing corrects it.

**Suspected root cause.** The pre-approval tool-result narration
("Approval required for local action. No command was executed.") is persisted as
the turn's response, and the resumed turn does not always replace it. A race
between the automatic resume and the client re-subscribing to the session is the
likeliest trigger.

**Proposed fix.** Make the pre-approval narration a runtime notice tied to the
paused state rather than a stored assistant response, so a resume replaces it by
construction; and add an invariant test that a session whose approval resolved
`executed` can never close with a response asserting no execution.

**Evidence.** `screenshots/not-working/BUG-r0808-02-post-approval-answer-says-not-executed.png`.

---

## FIXED-134 — Redaction corrupted path-derived local model IDs

**Status: fixed in the BUG-69 live download/deploy round.** A revision-like
numeric segment in the former path-derived `model_id` was correctly redacted in
the API response, but that made the identifier unusable when the UI sent it
back to Deploy. Local models now expose a stable opaque `mdl_…` identifier;
paths remain server-side and redacted. A nested-library API regression proves
the returned identifier deploys unchanged.

---

## FIXED-135 — Model Activity did not refresh background state

**Status: fixed in the BUG-69 screenshot review.** Activity loaded once, so a
deployment that completed server-side remained visibly `running`. The mounted
panel now polls once per second and clears its interval on unmount. The focused
component test uses fake time to prove a second fetch occurs, and screenshot
214 shows the newest deployment as complete.

---

## FIXED-136 — Managed llama.cpp could outlive graceful host shutdown

**Status: fixed in the BUG-69 shutdown verification.** The runtime previously
sent terminate without waiting. Shutdown now waits up to five seconds, kills on
timeout, waits for exit, and only then clears its state. The live test child was
verified stopped after the service closed.

---

## FIXED-137 — Redaction destroyed an approved model library root

**Status: fixed in this change.** Found in GitHub CI after BUG-69 landed:
`tests/test_api_model_library.py::test_owner_adds_and_rescans_an_approved_library`
failed on `main`.

**Observed.** `GET /api/model-library` returned every approved root as:

> `{"path": "/[REDACTED_SECRET]"}`

**Root cause.** The same high-entropy fallback behind FIXED-11 and FIXED-14: any
40+ character run of URL/base64 characters is redacted, and `/` is one of them,
so a filesystem path trips it purely because its segments were joined. Locator
fields are exempted by their key, but `is_locator_field` matched *suffixes*
only — `_path`, `_url`, `_uri`. The model library reports a root as a bare
`path`, which ends with none of them, so it kept the strict scan. The approvals
route's artifact `path` and a prompt attachment's `path` had the same shape.

**Impact.** The owner could add a library root and rescan it, but the roots list
showed an unreadable placeholder, and removal is by path — so a root approved by
mistake could not be withdrawn from the UI.

**Fix.** `_LOCATOR_KEYS` now carries the unprefixed spellings — `path`, `paths`,
`subpath`, `url`, `urls`, `uri`, `uris` — alongside the suffix list. Nothing
else changes: the secret-key sweep still runs first, so `token_path` is still
discarded whole, and every credential shape is still matched before the
fallback, so a key embedded in a path is still its own over-length segment and
is still redacted. Regression tests cover a bare `path` and `url` surviving, a
credential inside a bare `path` still redacting, and the secret-key sweep still
winning.

---

## FIXED-161 — The production web bundle no longer exceeds the chunk warning

**Status: fixed in this change. Was BUG-74, found on 2026-08-09 while running
the BUG-69 production build.**

**Observed.** `npm --prefix apps/web run build` succeeded but Vite reported the
main JavaScript chunk at about 690 kB, above its 500 kB warning threshold. Not a
correctness or security failure, but real download and parse cost: opening Chat
paid for the Knowledge Map's force simulation, the Models acquisition panels and
the whole of Settings.

**Root cause.** `App.svelte` statically imported every view, so the bundler had
one chunk to emit and no seam to split at.

**Implemented.** Route-level code splitting with an intentional policy about
*where*. `apps/web/src/lib/routeComponents.ts` holds one static `import()` per
secondary destination — Search Chat, Memory, Approvals, Tasks, Knowledge Map,
Sessions, Projects, Permissions, Models, Extensions, Observability, Settings and
the first-run model setup — and `LazyRoute.svelte` mounts them. Workbench, Chat
and Build stay statically imported: they are what a session opens with, and Chat
and Build additionally stay mounted across route visits to keep their transcripts
alive.

No-flash navigation is preserved two ways. Every loaded module is cached, so a
second visit to a route resolves on the same tick; and `prefetchRoutes()` warms
the whole map on the browser's next idle callback after sign-in, so in practice
the first visit is synchronous too. The mocked browser coverage is unchanged.

The main chunk is now 237 kB (76 kB gzipped) and the build reports no size
warning; the largest route chunk is Models at 82 kB.

**UI when closed.** The same dashboard loads with no build-size warning and no
loss of first-route responsiveness.

---

## FIXED-162 — Retry, cancellation and partial cleanup do what they say

**Status: fixed in this change. Was BUG-75, found on 2026-08-09 while closing
BUG-69.**

**Observed.** Ollama pull, Hugging Face download, conversion and managed GGUF
deployment start real background workers, but three of their controls were
record-only. **Retry** reset the durable row to `queued` without reconstructing
and dispatching the original worker. **Cancel** recorded `cancel_requested`, but
not every worker polled it. **Clear record** removed the durable row and left an
incomplete destination on disk.

**Root cause.** The operation row carried what an operation *was* but not what it
*ran with*, so nothing could rebuild the job. Cancellation had a state but no
reader inside the workers, and cleanup had a scope — the record — that had never
been separated from the one the owner actually wanted.

**Implemented.** Four parts.

* A secret-safe typed payload is persisted at start (`payload_json`, migration
  `RAIKER-1048-model-operation-payload`). The keys are an allowlist — repository,
  revision, variant, model, source, output, quantization, destination — so a
  caller cannot accidentally store a token by adding a field, and the payload is
  never part of the owner-facing projection.
* **Retry** dispatches by job kind from that payload
  (`_dispatch_operation` in `raiker/api/routes_models.py`), re-reading the
  Hugging Face credential from the vault rather than remembering it. An
  operation with no dispatchable payload — a runtime install — is refused with
  `operation_not_retryable` and the row says so, instead of offering a control
  that only resets state.
* Every worker polls `cancel_requested` at its own tightest bound: the Ollama
  pull on each streamed progress line, the conversion before and after its
  bounded subprocess, the deployment around the llama.cpp readiness wait, the
  Hugging Face download around its snapshot. A cancel on a `queued` operation
  reaches `cancelled` immediately, because there is no worker to co-operate with.
* **Delete partial files** is a separate confirmed action that names the exact
  path, file count and byte size first, and refuses anything that does not
  resolve inside an approved model-library root. **Clear record** stays
  metadata-only.

**UI when closed.** Retry starts real work, cancellation reaches a terminal state
promptly, and deletion names the exact approved path and bytes before the owner
confirms.

---

## FIXED-163 — A failing tool or provider is contained, not retried to exhaustion

**Status: fixed in this change. Was BUG-76, found on 2026-08-09 while mapping
Raiker to the OWASP Agentic Top 10 (ASI08 — cascading agent failures).**

**Observed.** Every bound Raiker enforced on a runaway loop was a *budget*, not a
breaker: `max_tool_calls` per turn, the four-dimension subagent budget, API rate
limiting, and per-job `max_retries`. None of them carried failure state, so a
provider that failed every call consumed its entire budget one failing call at a
time — and the next turn started with a fresh budget and repeated it.

**Root cause.** Nothing durable counted consecutive failures, so every turn began
believing the component was healthy.

**Implemented.** `raiker/security/containment.py` adds `CapabilityBreaker`:
consecutive failures per subject are counted in durable state
(`capability_containment`), a threshold of three **opens** the breaker as a
revocable pause with a stated reason and a raised finding, further calls are
refused with `capability_paused`, and after a 60-second cooldown exactly one call
is let through as a half-open probe. The first success closes the breaker and
clears the streak; a failed probe restarts the cooldown.

It deliberately reuses the containment vocabulary the MCP monitor already had —
`active` / `paused` / `killed`, an owner-visible reason and a one-call resume —
rather than inventing a second one, and the breaker's own pauses are attributed
separately (`capability_breaker`) from an anomaly's, because only the breaker's
may clear itself.

Two seams carry it. `RuntimeOrchestrator._aexecute_tool` is the one place every
governed tool call passes, so a contained tool is refused there before it runs;
and both provider loops step over a contained provider with a stated reason
rather than trying it once per fallback entry. A turn that fails on a provider
keeps that provider's own reason code — the owner's repair is the provider's
fault, not the breaker's — and a turn that finds every model contained says so
(`provider_contained`) instead of stalling.

**UI when closed.** Settings → Security & Login lists every monitored subject
with its state, its stated reason and its consecutive-failure count, and offers
Pause, Stop and Resume. A turn that hits an open breaker says so.

---

## FIXED-164 — Anomaly detection and containment cover every capability

**Status: fixed in this change. Was BUG-77, found on 2026-08-09 while mapping
Raiker to the OWASP Agentic Top 10 (ASI10 — rogue agents).**

**Observed.** `raiker/security/mcp_monitor.py` was a complete behaviour monitor —
a rolling per-connection baseline, five deterministic anomaly rules, redacted
`security_findings`, an audit event, and three containment states — and **none of
it existed for any other capability family.** Plugins, connectors, subagents and
shell/container execution had no baseline, no anomaly rule, no finding, no
auto-pause and no kill switch.

**Root cause.** The machinery was written against one subject type, so extending
it meant copying it.

**Implemented.** The baseline/rule/finding/containment machinery is lifted into a
capability-agnostic substrate keyed by `(principal, capability, subject)`:

* `capability_activity_log` is the generic sibling of `mcp_session_log` — one
  redacted row per governed invocation, forming each subject's rolling baseline.
* `CapabilityMonitor` evaluates the same five rules — new host, volume spike,
  tool-set swap, sensitive-data shape, error/refusal burst — raising a redacted
  finding and a `capability_anomaly_detected` event, and auto-pausing on a
  high-severity hit.
* `CapabilityContainment` carries `active` / `paused` / `killed` with an
  owner-visible reason and a one-call resume, all revocable.

Registration is at one seam rather than in each executor:
`raiker/security/capability_registry.py` maps a brokered tool call to its family
and subject, and `RuntimeOrchestrator._aexecute_tool` observes every call that
passes it — so connectors, plugins, subagents and local execution are covered on
a fresh turn, a parallel read batch and a call drained from the approval queue
alike. Monitored MCP connections keep their own richer per-session monitor.

The hard invariant holds: the monitor only ever receives redacted metadata —
counts, netloc, an operation name and classification labels. A `web_fetch` whose
URL carries userinfo and a token stores `example.com` and a byte count, and the
page text never reaches a row. A local workspace read is deliberately *not*
monitored: giving it a baseline would produce noise, not signal.

**UI when closed.** Settings → Security & Login lists findings and containment
state for every capability, and each contained subject names its reason and
offers the same pause, stop and resume.

---

## FIXED-165 — A delegated subagent result is bound to the spawn that produced it

**Status: fixed in this change. Was BUG-78, found on 2026-08-09 while mapping
Raiker to the OWASP Agentic Top 10 (ASI07 — insecure inter-agent communication).**

**Observed.** Subagents are spawned through the governed `subagents` capability
and bounded on four dimensions, and the result re-entered the parent turn as a
source with no attestation tying it to the spawn that produced it. The parent
performed no verification step before treating it as material.

**Root cause.** Raiker already issues and verifies per-turn machine identity, and
delegation was the one governed hand-off that did not use it. Without the
binding, the audit trail could not prove *which* spawn produced a given result
when several ran in one turn.

**Implemented.** `raiker/agents/delegation.py` mints a spawn-scoped attestation,
signed by the workspace issuer key, binding the subagent id, its child principal,
the owner, the session, the parent turn, the spawn's own turn and subject, and a
SHA-256 digest of the findings the parent is about to read. `spawn_subagent`
attaches it; `RuntimeOrchestrator._verify_delegated_result` verifies it before
the result becomes a turn source, and records the binding on the hash-chained
event (`subagent_result_verified`).

Verification is fail-closed at every step: a missing or malformed attestation, an
unknown issuer key, a bad signature, a mismatched owner, session or turn, a
digest that does not cover the content the parent is holding, or a spawn identity
that does not exist or disagrees — each refuses the result with its own reason
code and a `subagent_result_refused` event. A completed spawn is deliberately not
required to still be *active*: the runner deactivates the child as it finishes,
so requiring it would refuse every result. The attestation carries no findings —
only identifiers and a one-way digest.

**UI when closed.** A turn that used subagents attributes each result to its
spawn in the activity and audit views, and a result that fails verification is
refused with a stated reason rather than silently consumed.

---

## FIXED-166 — A plugin signature states what it actually proved

**Status: fixed in this change. Was BUG-79, found on 2026-08-09 while mapping
Raiker to the OWASP Agentic Top 10 (ASI04 — agentic supply chain).**

**Observed.** `verify_plugin_signature()` reads the owner signing key from
`RAIKER_PLUGIN_SIGNING_KEY`. When that variable is unset — the default — any
non-empty string in the manifest's `signature` field passed as
`signature_present`. On a default install nothing distinguished a genuinely
signed plugin from one carrying the literal string `signature`, and the owner was
never shown which state they were in.

**Root cause.** This is a deliberate local-development baseline, not an
oversight — but an unstated one, which is the part that failed.

**Implemented.** The verification level is now a first-class property.
`signature_verification()` classifies every manifest as `verified`,
`present_only` or `unsigned`, with the reason code that produced it, the method
that ran, a plain-language explanation and the one-step path to a stronger state.
`signing_posture()` reports the workspace's own posture independently of any
manifest. Both ride on `PluginRegistrationPlan`, so the permission diff states the
level beside the permissions, and on `GET /api/plugins` for the installed
records.

The default is **not** silently hardened, in keeping with the posture at the top
of this document: a `present_only` plugin installs exactly as it did before. What
changed is that the owner is told.

**UI when closed.** Extensions → Plugins states the workspace signing posture and
its remediation, and lists each installed plugin with a `Verified` /
`Present only` / `Unsigned` chip that is visibly distinct, plus the explanation
behind it.

---

## FIXED-167 — The GenAI security mapping matches shipped code

**Status: fixed in this change. Was BUG-80, found on 2026-08-09 while mapping
Raiker to the OWASP Agentic Top 10.**

**Observed.** `docs/OWASP_GENAI_SECURITY_MAPPING.md` rated LLM09
(Misinformation) with the note "Verifier is a stub
(`raiker/runtime/verifier.py`)". That had not been true since the real
`Verifier` landed in `raiker/verification/verifier.py`, and several other rows
predated work that had since shipped.

**Root cause.** The table was written once and never re-audited, and this
repository treats doc honesty as a security control: a shipped control recorded
as absent means the next reviewer either rebuilds it or distrusts the rest of the
table.

**Implemented.** Every row of the LLM Top-10 table was re-audited against current
code and now cites the file that proves its rating. LLM01, LLM02, LLM07, LLM09
and LLM10 moved to ✅ with their evidence named; LLM03 is honestly 🟡 (signature
verification is real, the default install has no key — see FIXED-166); LLM04 and
LLM08 are 🔒 *disabled-by-default* rather than unimplemented, which is a different
statement and now made explicitly. The two remaining gaps — a content sensitivity
classifier before egress, and a trusted-publisher allowlist — are named in the
rows rather than left to be inferred from a status glyph. The "Prompt Injection
Requirements" section now names the scanning hook and states what it is and is
not.

**UI when closed.** No user-facing surface; the deliverable is a mapping table
whose every row matches shipped code.

---

## FIXED-168 — Untrusted context is scanned, and a suspicious source is named

**Status: fixed in this change. Was BUG-81, found on 2026-08-09 while mapping
Raiker to the OWASP Agentic Top 10 (ASI01 — agent goal hijack).**

**Observed.** `docs/OWASP_GENAI_SECURITY_MAPPING.md` states that Raiker must
"support prompt-injection scanning hooks". No such hook existed:
`raiker/runtime/classifier.py` is an intent router, not a detector, and nothing
evaluated input at the point it entered the model context.

**Root cause.** The gap was deliberately bounded — the structural controls do the
real work and are in place — but it left no *advisory signal*: the owner was
never told that a fetched page or an attachment contained something shaped like
an injection attempt, so a hijack attempt the tool gate correctly refused left no
trace naming its source.

**Implemented.** `raiker/security/injection_scan.py` is a deterministic,
explainable scanner: eight named rules (instruction override, role
impersonation, secret solicitation, exfiltration request, tool coercion,
approval bypass, hidden instructions, invisible characters), each with a stated
severity and a match count. It runs on untrusted context items as they enter the
turn — every tool result that becomes a source, and every attached file the turn
actually read — and raises one redacted `security_findings` row per source
attributed to the exact document or URL, plus a `prompt_injection_suspected`
event.

It is detection and provenance, not prevention: a finding never blocks a turn,
and the refusal path stays the tool gate. There is deliberately no probabilistic
model-based filtering, because the reference architecture Raiker is measured
against is explicit that prompt-level defence is not a control surface — and a
classifier that is right most of the time would turn an advisory signal into a
false assurance. The finding records which rules matched and how many times,
never the text that matched.

**UI when closed.** A turn whose context included suspicious external content
raises a finding naming the source document or URL in Settings → Security &
Login, and the finding survives in the audit trail whether or not the model acted
on it.

---

## FIXED-138 — Billing exhaustion was reported as an unreachable provider

**Status: fixed in the BUG-69 reference-platform parity review (Task 13).**
Found on 2026-08-09 driving the Models UI with a real Anthropic key that has no
credit.

**Observed.** The catalogue call succeeded and listed ten models, then the
execution preflight failed and the readiness state became `unreachable` with
`provider_execution_refused`. The provider was reachable and the credential was
valid; only the account balance was empty.

**Root cause.** `_map_status` in both `raiker/models/providers/anthropic_messages.py`
and `raiker/models/providers/openai_compatible.py` classified on the HTTP status
alone. Anthropic answers an empty balance with HTTP 400 on a valid key, so it
fell through to `ProviderConnectionError("provider_http_error:http_400")`;
OpenAI's `insufficient_quota` arrives as 429 and became a rate limit, which a
retry appears to be able to fix and cannot.

**Fix.** `is_quota_exhausted(status, body)` in `raiker/models/exceptions.py`
classifies 402 unconditionally and 400/403/429 when the body names money or a
spent allowance. Bare `quota` is deliberately not a marker — it would swallow a
per-minute rate limit. The body is read only to classify; the raised code is
fixed (`provider_quota_exhausted:http_<status>`), so no provider prose reaches
an event, an API response, or the readiness record. Readiness gained
`ModelReadinessState.QUOTA_EXHAUSTED`, and the repair sentence now names credit
and quota instead of the network.

**Evidence.** `tests/test_model_quota_readiness.py`, and the live card reading
**No credit** in `screenshots/working/bug69-models-quota-readiness-live.png`.

---

## FIXED-139 — The readiness gate ignored the fallback chain the runtime uses

**Status: fixed in the BUG-69 reference-platform parity review (Task 13).**

**Observed.** `ModelReadinessService.require_ready()` judged only the primary
model. `RuntimeOrchestrator._provider_chain` builds the primary *plus the
owner's ordered fallback sequence* and really does try each in turn, so the gate
refused work a configured, ready fallback could serve, and admitted work whose
fallbacks had never been probed.

**Root cause, second layer.** The fallback chain was already inert for every
hosted provider. `AgentGateway._resolve_profile_for_turn` resolved a profile's
model from the single `ModelSessionState`, which names one profile only. Every
hosted profile ships a `<model>` placeholder, and the owner's pin for any
*other* profile lives in `principal_configured_models`, which was never read —
so each hosted fallback entry resolved to `<model>` and was dropped.

**Fix.** `resolve_chain()` resolves the same chain the orchestrator builds and
`require_ready()` admits the turn when any entry is ready, with the primary
keeping priority and a refusal still reporting the primary. Both the readiness
service and the gateway now fall back to the per-profile pinned model, and both
read the owner-scoped fallback sequence before the terminal one so a
CLI-bootstrapped owner's sequence is not silently ignored.

**Evidence.** `tests/test_model_readiness_fallback_chain.py`.

---

## FIXED-140 — Models claimed providers were "set up" and Test proved nothing

**Status: fixed in the BUG-69 reference-platform parity review (Task 13).**

**Observed.** In one live session the Models page announced **"1 of 10 providers
set up"** while Chat, correctly, said "No readiness check exists for this exact
model" and refused to send. Clicking **Test** on the same card reported
"Anthropic responded and exposed 10 models." — which reads as success — and
still left every work surface blocked.

**Root cause.** `readyCount` in `apps/web/src/lib/views/ModelsView.svelte` was
`configuredProfiles.length`: profiles with a saved connection, not profiles
proven ready. The server-side `ready_provider_count` and the per-profile
`readiness_state` were already in the payload and unused. `testConnection()`
called `GET …/provider-models`, a catalogue listing that writes no readiness
observation and says nothing about the pinned model.

**Fix.** The headline reads `ready_provider_count` and says "N models ready",
with connection count kept as the secondary figure it always was. Test runs
`POST /api/model-readiness/check` for the pinned model, reports that verdict and
its remediation, and refreshes the page; profiles with no model pinned keep the
catalogue note, the only honest answer available for them. Each card carries a
chip for its exact state.

**Evidence.** Three tests in `apps/web/src/lib/views/ModelsView.test.ts`, and
the live headline reading **0 models ready · 1 of 10 connected** in
`screenshots/working/bug69-models-quota-readiness-live.png`.

---

## FIXED-160 — A throttled read reported only `Unavailable (429)`

**Status: fixed in this change. Found on 2026-08-10 while running the FIXED-158
live scenario.**

**Observed.** Driving several surfaces in quick succession trips the runtime's
own request limiter (`RateLimitMiddleware`, 120 requests per minute). Models then
renders:

```
Couldn't load models
Unavailable (429)
```

**Why it matters.** The limiter is working — this is Raiker protecting itself,
and the condition clears on its own within a minute. But the page says neither of
those things. "Unavailable (429)" reads as a broken page to anyone who does not
know what a 429 is, and it names no way forward, on a page where every other
failure states what is wrong and which control fixes it.

**Fix applied.** A 429 is named for what it is, with the control that resolves
it: *"Too many requests in the last minute. Raiker throttled this read; wait a
moment and press Refresh."* The same wording covers the page's two check
controls — **Test** on a provider card and **Check advisor** — which previously
said only "Raiker could not check …", the same sentence they use for a provider
that genuinely cannot be reached. Every other status keeps the existing wording.

**Found by.** The live suite makes more governed reads per minute than a person
does, so it meets the limiter routinely; `bug-68-71-73-82-live.spec.ts` now waits
and presses **Refresh models** on that message rather than reporting a defect the
product does not have.

---

## FIXED-158 — The advisor model was never readiness-checked

**Status: fixed in this change. Was BUG-82, found on 2026-08-09 in the BUG-69
reference-platform parity review, and closed live on 2026-08-10.**

**Observed.** Raiker runs a second model besides the chat model: the advisor
(`raiker/runtime/advisor.py`, Models → Routing → Advisor model). It is chosen in
the same UI as the chat model but never appears in readiness — no probe, no
state, no chip, and no entry in `GET /api/model-readiness`.

**Impact.** An owner can pin an advisor whose provider has no credential, no
credit, or no running runtime and see nothing wrong until a consult fails
mid-turn. The consult itself does fail closed with a reason code, so this
degrades one tool rather than breaking the turn — which is exactly why it stays
invisible. It is also the one place Raiker sits behind the reference set: Claude
Code surfaces its auxiliary model (`ANTHROPIC_SMALL_FAST_MODEL`) in the same
status output as the primary.

**Root cause.** `AdvisorRuntime.consult()` resolves the advisor profile from the
registry and the single `ModelSessionState` and calls it directly. It never goes
through `ModelReadinessService`, and — the same defect fixed for the chat chain
in FIXED-139 — it does not read `principal_configured_models`, so a hosted
advisor pinned through the UI resolves to `<model>` and is refused with
`advisor_model_unresolved` even when the owner did pin one.

**Fix applied.** Three parts, in the order the defect bites:

* **The advisor resolves the way the chat chain does.**
  `AdvisorService.pinned_model` reads `principal_configured_models`, so a hosted
  advisor pinned through Models → Routing resolves to the model the owner
  actually chose. This was the same defect FIXED-139 closed for the chat chain:
  the single `ModelSessionState` only ever names the *currently selected*
  profile, so an advisor on any other profile fell back to its `<model>`
  placeholder and every consult was refused `advisor_model_unresolved` — even
  for an owner who had pinned one.
* **It has a readiness observation of its own.** `resolved_advisor()` returns the
  exact `(profile, model)` a consult would call, and the Models contract carries
  that model's readiness state, summary, remediation and check time under its own
  key. It is the same `ModelReadinessService` record a provider card reads, so
  the two models this runtime runs are judged by the same evidence.
* **The selector says so.** Models → Routing now shows the advisor's readiness
  chip, the exact model beside it, a **Check advisor** control, and — when the
  last check did not find it ready — the summary and the repair sentence. This
  is the parity item the review named: Claude Code surfaces its auxiliary model
  in the same status output as the primary, and Raiker now does too.

The fail-closed consult path is unchanged: the gate, the decision mode (default
`ask`, which withholds), the provider policy and the untrusted-data framing all
apply exactly as before. Readiness is reporting, not authority.

**UI when closed.** The Advisor model selector shows the same readiness chip and
repair sentence as a provider card, and a hosted advisor pinned in the UI is
actually reachable.

**Evidence.** [`working/r0810-bug82-advisor-readiness.png`](screenshots/working/r0810-bug82-advisor-readiness.png)
(live). Held by the `TestAdvisorReadiness` suite in `tests/test_advisor_model.py`.

---

## FIXED-169 — Readiness has an owner-set window and quiet revalidation

**Status: fixed in this change. Was BUG-83, found on 2026-08-09 in the BUG-69
reference-platform parity review.**

**Observed.** `ModelReadinessService` expired an observation after a hard-coded
five minutes. Nothing re-checked in the background, so a model that was ready
five minutes ago became `stale` and the owner had to press a button before
working again, while a model that stopped thirty seconds ago still read ready
until the window lapsed.

**Root cause.** One fixed timer, no control over it, and nothing watching between
ticks. Both directions are wrong for a long editing session: the reference set
learns about a lost model on the next request rather than on a timer.

**Implemented.** Three parts.

* The TTL is a persisted owner setting (`models.readiness_ttl_minutes`) with a
  five-minute default, clamped to 1–120 minutes. A missing, malformed or
  out-of-range value resolves to the default rather than failing — a preference
  that cannot be read must never be the reason a turn cannot start — and both the
  flat dotted key the settings sections write and the nested object older readers
  use are accepted.
* While a work surface is open and the tab is visible, the selected model is
  re-confirmed in the background as its observation enters the last quarter of
  its own window (`startReadinessRevalidation`). This never *grants* readiness:
  it runs the same owner-triggered check the Models page runs, and a failed
  background check changes nothing.
* The invalidation hooks — connection, selection, pull, endpoint, credential
  change — stay authoritative over any timer, exactly as before.

**UI when closed.** A long session does not spontaneously disable Send. The
readiness chip on Models reads `Ready · confirmed 2 min ago`, and Settings →
Runtime carries the window with its bounds and what still invalidates a check
regardless of it.

---

## FIXED-170 — The BUG-69 live acceptance spec runs with one provider key

**Status: fixed in this change. Was BUG-84, found on 2026-08-09 while re-running
the BUG-69 live evidence.**

**Observed.** `apps/web/e2e/bug-69-model-readiness-live.spec.ts` opened with
`expect(OPENROUTER_KEY, "set RAIKER_LIVE_OPENROUTER_KEY").not.toBe("")`, so the
whole spec failed immediately unless both an Anthropic and an OpenRouter key were
present. It also asserted a specific non-ready outcome for `claude-opus-4-8`,
which is a property of the account that ran it, not of the product.

**Root cause.** The spec was written against one round's exact credentials rather
than against the behaviour those credentials happened to exercise.

**Implemented.** The spec is now driven by a table of provider legs — Anthropic,
OpenRouter, OpenAI and Gemini — each with its own environment variable. A leg
whose key is absent is skipped and annotated; the run fails only when *no*
provider key is set at all, and says which variables would satisfy it.

Each leg that runs asserts the readiness **state machine** rather than an
entitlement: a provider that answers the catalogue either becomes ready and
answers the turn, or produces a *classified* non-ready state that keeps Send
disabled, preserves the owner's draft, and names its own repair. Which of the two
an account earns is recorded as a run annotation rather than asserted. The
first-run gate assertion is unchanged and runs whichever keys are present.

The local leg moved to the same shape with a different precondition: a runtime
is a reachable *process*, not a key, so it runs when `RAIKER_LIVE_OLLAMA_MODEL`
names one and is annotated as skipped otherwise. Local acquisition and deployment
keep their own dedicated specs.

**Evidence.** Run on 2026-08-10 against a fresh workspace holding one Anthropic
key and nothing else: the spec passes end to end, records
`{"Anthropic":"ready"}` as its outcome annotation, and annotates OpenRouter,
OpenAI, Gemini and Ollama as skipped legs.

**UI when closed.** No UI change. `npm --prefix apps/web run test:e2e:live` with a
single provider key produces a complete, honest evidence run for that provider.

---

## FIXED-143 — The live evidence suite could not reach a provider card at all

**Status: fixed in this change. Found on 2026-08-10 running the B12/C7 spec to
verify FIXED-142.**

**Observed.** `apps/web/e2e/web-access-turn-control-live.spec.ts` failed on its
first action, four minutes of timeout before a single assertion about web access
ran:

```
locator.click: Timeout 30000ms exceeded.
  waiting for locator('article.provider-card').filter({ hasText: 'Anthropic' })
```

Eighteen live specs opened `#/models` and reached straight for a provider card.

**Root cause.** Three separate pieces of the product moved and the specs did
not follow:

| What moved | Landed as |
|---|---|
| FIXED-141 split Models into tabs and made **Local** the default | `#/models` renders no `article.provider-card` at all |
| FIXED-133 added the first-run "Choose how to run models" sheet | modal over the workbench on every *load* of a new instance, so skipping it during sign-in does not survive the first navigation |
| FIXED-133 added the readiness gate | **Send** stays disabled until the *exact* model has a check, so a spec that connected, pinned and typed sat on a disabled button |

None of these is a defect on its own; each is a shipped improvement. The defect
is that the live suite is the evidence behind every FIXED entry in this
document, and it had stopped being able to produce any.

**Fix.** One `apps/web/e2e/hosted-provider.ts` now owns all three steps, so the
next change to any of them is one edit rather than eighteen:
`openHostedProviders` navigates to the tab the cards are actually on and settles
the first-run sheet by waiting for *either* the tab or the sheet — the sheet
appears only after the bootstrap reads resolve, so polling for it immediately is
what made a naive skip flaky; `useHostedModel` connects, pins the exact model,
reloads so **Test** probes the pinned model rather than the profile the picker
was opened with, and runs the readiness check; `refreshHostedReadiness` re-runs
it for a scenario that starts after the record's five-minute TTL (BUG-83) has
passed. Every affected spec now calls these instead of inlining a copy.

**Evidence.** `apps/web/e2e/web-access-turn-control-live.spec.ts` passes 6 / 6
against a live Anthropic host; the other seventeen specs are converted to the
same helpers but were not run — they need credentials and hosts this
verification round did not have.

---

## FIXED-144 — The first-run model sheet rendered the Settings page underneath it

**Status: fixed in this change. Found on 2026-08-10 in a Playwright page
snapshot taken while diagnosing FIXED-143.**

**Observed.** On a brand-new instance the first-run "Choose how to run models"
sheet rendered with the entire **Settings** page — section rail, language
combobox, startup behaviour — stacked below it in the same scroll column.

**Root cause.** `apps/web/src/App.svelte` routes through two sibling `{#if}`
chains. The first handles `model-setup`; the second ends in the fallback
`{:else if current !== "new-chat" && current !== "build"}` → `SettingsView`.
`model-setup` was never named in that guard, so the fallback matched and
Settings rendered as well. It is the ordinary cost of a fallback route: every
branch handled elsewhere has to be repeated in its condition.

**Fix.** The fallback now also excludes `model-setup`, with a comment stating
why the list has to be kept in step.

**UI when closed.** The first-run screen is the only thing on the page.

**Evidence.** Verified in the live run of
`apps/web/e2e/web-access-turn-control-live.spec.ts` against a fresh workspace:
the page snapshot holds the setup region and nothing else.

---

## FIXED-149 — The BUG-47 live scenario expected two Models tabs on screen at once *(was BUG-85)*

**Status: fixed in this change. Found on 2026-08-10 while fixing FIXED-143.**

**Observed.** `apps/web/e2e/bug-44-47-live.spec.ts` opened `#/models?tab=local`
and then asserted

```ts
await expect(anthropicCard.getByText("Connected")).toBeVisible({ timeout: 30_000 });
```

Since FIXED-141 split the page, a hosted provider card cannot be on screen at
the same time as the local rows, so the assertion could not pass.

**Root cause.** The scenario was written against the pre-split Models page,
where every provider lived in one scroll. The split did not break BUG-47's
property; it moved where the property can be violated.

**Fix.** The scenario is re-aimed at the pairs that can still contaminate one
another — two cards **on the same tab**:

* on **Hosted**, Anthropic is tested and its result must be the only one on the
  tab; a second hosted card is then tested and each card must hold exactly one
  result, naming its own provider;
* on **Local**, the same for two runtime rows.

Weakening the assertions was rejected in favour of testing a property the
product still has. Each message names its own provider, so a result under the
wrong card contradicts the card it sits under — which is what makes the
assertion mean something rather than merely counting elements.

**Evidence.** `197-BUG-47-local-rows-keep-their-own-live.png` and
`198-BUG-47-hosted-cards-keep-their-own-live.png`.

**UI when closed.** No UI change.

---

## FIXED-145 — The first-run screen was titled "Workbench"

**Status: fixed in this change. Found on 2026-08-10 in the visual sweep, in the
same screenshot as FIXED-144.**

**Observed.** The first-run "Choose how to run models" screen carried the topbar
title **Workbench** and its hint, *"Resume governed work and see what needs
attention"* — on a machine with no work to resume.

**Root cause.** `navItem()` in `apps/web/src/lib/nav.ts` ends
`?? NAV_ITEMS[0]`, which is correct for a typo'd route and wrong for a route
that genuinely exists but has deliberately no sidebar entry. `model-setup` is
the only such route today.

**Fix.** An `OFF_NAV_ITEMS` list gives an off-nav route its own label and hint —
*"Set up models · Choose how Raiker runs models before your first turn"* —
without putting it in the sidebar. A nav test asserts both halves: the title is
its own, and the route is still absent from `NAV_ITEMS`.

---

## FIXED-146 — The Knowledge Map's count pill contradicted its own empty state

**Status: fixed in this change. Found on 2026-08-10 in the visual sweep.**

**Observed.** On a workspace with nothing recorded, the graph showed
*"Build your knowledge graph — Add sources… Relationships will appear
automatically"* while the pill in the same corner read **"3 nodes · 2
relationships"**.

**Root cause.** A workspace with at most one real node is given an instructional
starter graph — three placeholder nodes and two placeholder edges, flagged
`is_real: false`. The overlay tested the *raw* node count; the pill counted the
*rendered* nodes, placeholders included. Two conditions describing the same
state, disagreeing — the failure mode this document keeps recording.

**Fix.** One `showingStarter` derived value now decides all three things that
depend on it: whether the starter graph is built, whether the overlay shows, and
what the pill says. While it is showing the pill reads **"Starter view ·
nothing recorded yet"**, so the two agree by construction.

---

## FIXED-147 — The Knowledge Map ignored a system dark preference

**Status: fixed in this change. Found on 2026-08-10 in the visual sweep.**

**Observed.** With the theme left on **System** and the OS set to dark, every
route rendered dark except the Knowledge Map, whose canvas, pill, controls and
empty-state copy stayed on the light palette inside an otherwise dark shell.

**Root cause.** `apps/web/src/app.css` defines the dark tokens for both the
explicit attribute *and* `@media (prefers-color-scheme: dark)` under
`:root:not([data-theme])`. `BrainView.svelte` does not use those tokens for its
canvas — it hard-codes a light palette and overrides it under
`:global(:root[data-theme="dark"])` only. "System" deliberately removes the
`data-theme` attribute (`lib/theme.ts`), so on the default setting the override
never matched.

**Fix.** The dark override block is now also applied inside
`@media (prefers-color-scheme: dark)` for `:root:not([data-theme="light"])`, so
the three states the rest of the app supports — explicit light, explicit dark,
and system — all reach the Knowledge Map. Verified by screenshot in system-dark
and explicit-light.

---

## FIXED-148 — "1 models ready"

**Status: fixed in this change. Found on 2026-08-10 in the visual sweep.**

**Observed.** The Models page headline read **"1 models ready"** — the number
most owners will ever see there, since one ready provider is enough to work and
the page says so two lines above.

**Fix.** The count is pluralised. It is small, and it is on the first screen a
new owner reaches after setup.

---

## FIXED-150 — SQLCipher ran out of locked memory and locked the owner out *(was BUG-86)*

**Status: fixed in this change. Found on 2026-08-10 during the visual sweep, on
Linux. Reproduced twice.**

**Observed.** After a few minutes of ordinary navigation the sign-in screen
began answering every attempt with

> Runtime verification failed. The workspace remains locked.

while the status strip at the bottom of the same screen read **"Runtime
operational"**. The server was healthy: `GET /api/health` answered 200
throughout, and later requests in the same log succeeded.

**Root cause.** Two independent defects, and a third that made them
unreadable.

1. **The bound on key-bearing connections depended on the thread count.** The
   process ceiling was expressed as *worker-threads-worth* of the per-thread
   limit (`limit × 8`), so with the default limit the process would cache up to
   64 keyed SQLCipher connections. Each holds key material the platform may be
   asked to lock into RAM, and `ulimit -l` on the run was **8 MB**. The host had
   15 GB free — this was never memory exhaustion, it was the *locked-memory
   allowance* being spent. The server log carries eleven occurrences of
   `MemoryError` out of `SQLiteStore.connect`, and because authentication opens
   the store, the first thing to fail is every request.

2. **A cached connection that lost its key pages was returned, not replaced.**
   `connect` probed a cached handle with `SELECT 1` and caught `sqlite3.Error`
   only. In the field log that probe raised `MemoryError`, which escaped
   `connect` entirely, so a worker that hit it failed every subsequent request.

3. **`/api/health` never touched the store.** It answered `{"status": "ok"}`
   unconditionally, which is why the strip could call the runtime operational
   while every sign-in on the same screen failed.

**Fix.**

* **The ceiling is an absolute connection count** (`RAIKER_SQLITE_CONNECTION_CACHE_CEILING`,
  default 16), never a multiple of the thread count. A thread's own allowance is
  still the smaller of the per-thread limit and its share of the ceiling, so a
  request threadpool cannot multiply the population.
* **Memory security is set explicitly on every connection, and it is off unless
  the owner asks for it.** This is the choice the entry asked for, made in the
  open — and it was made twice, because the first answer was wrong. The first
  attempt probed the platform's allowance and turned the pragma **on** wherever
  it looked sufficient. That is defensible on paper and wrong in practice: it
  made a bootstrap plus two hundred reads take **1.14 s instead of 0.17 s**,
  about seven times. The symptom was the test suite: a CI job that normally
  finishes in about eight minutes was past twenty and still running, and the
  full suite locally took over an hour. It was caught by watching the CI job,
  not by a test — no test asserts how long the suite takes.

  The decision that ships weighs the two facts against each other. Locking costs
  a multiple on every store operation, paid by every turn and every page load;
  and when the allowance runs out the failure is not slow work but `MemoryError`
  on *every* request, since authentication opens the store — this bug, and
  BUG-46 before it. A defence whose failure mode is "nobody can sign in" is not
  a default for a local-first product. So the pragma is set to **OFF**, before
  the key, on every connection — set rather than inherited, so the posture never
  depends on how SQLCipher was built — and Raiker **says which posture it is
  on**: `/api/health` reports `cipher_memory_security`,
  `memory_security_reason`, and `memlock_allowance_bytes`, the allowance this
  machine would actually have given.

  `RAIKER_SQLCIPHER_MEMORY_SECURITY=on` is the owner's decision and is honoured
  exactly: the pragma is forced on, and a refused lock fails **closed** by name
  as `store_memory_lock_unavailable`, naming the setting that asked for it,
  rather than surfacing as a bare `MemoryError`.
* **A refusal is recoverable, then named.** On `MemoryError` the thread releases
  every handle it may release — the connection population is the likeliest thing
  to have exhausted the allowance — and retries once. Only then does it raise
  `StoreUnavailableError`, which the API turns into a 503 carrying a reason
  code.
* **The store and the strip now read the same probe.** `/api/health` opens and
  reads the store; `status` is `ok` only while both the server and the store
  are. The lock screen shows **"Encrypted store unavailable"** in the strip and
  says *"Raiker's encrypted store could not be opened, so the workspace stays
  locked"* — naming the store and the machine, not "verification" — and
  disables the credential form, because no password can answer a store that
  will not open.

**Evidence.** `tests/test_sqlcipher_memory_security.py` — the absolute ceiling,
a six-thread pool staying under it, each branch of the policy decision, the
pragma read back off a live connection in both postures, the fail-closed path
when the owner demanded memory security, the health view, and the cached handle
whose key pages were reclaimed.

**Evidence (live).** `apps/web/e2e/critical-bugs-live.spec.ts` against a running
host: [`working/215-FIXED-150-store-healthy-live.png`](screenshots/working/215-FIXED-150-store-healthy-live.png)
and [`working/216-FIXED-150-store-unavailable-live.png`](screenshots/working/216-FIXED-150-store-unavailable-live.png).

**UI when closed.** Sign-in never fails for a reason unrelated to the
credential. When the store genuinely cannot be opened, the screen names that
and the status strip agrees with it.

---

## FIXED-151 — The audit log showed nothing though governed events were recorded *(was BUG-87)*

**Status: fixed in this change. Found on 2026-08-10 during the visual sweep.**

**Observed.** After signing in, connecting an Anthropic credential, pinning a
model and running its readiness check, **Observability → Audit log** showed
*"No events match — Adjust the filters or run a turn first"* with no filters
set, and **Overview → What changed?** showed *"No events recorded yet."*

Events had been recorded. `.raiker/events/terminal-local.jsonl` holds
`model_profile_selected` for the exact profile and model that were pinned, and
`.raiker/events/authz.jsonl` holds `principal_resolved`.

**Root cause.** `DashboardService.list_events` filtered every row against the
set of session ids belonging to the signed-in owner. The governed steps an owner
opens this page to confirm are not taken *inside* a conversation: connecting a
credential, pinning a model and resolving a principal are recorded on runtime
channels (`terminal-local`, `authz`) which are not sessions at all. Every one of
them failed the filter.

**The decision.** The audit log is **account-scoped**, not conversation-scoped.
It carries the owner's own conversations *and* the runtime steps taken outside
them. It does not carry another user's conversation.

**Fix.** A row is visible when its `session_id` belongs to one of the owner's
sessions, **or** when it belongs to no session record at all. The second clause
cannot leak another account's conversation: their sessions *are* session
records, so they fail it and stay filtered. `SQLiteStore.all_session_ids` exists
for that one distinction and carries no ownership, so it is never used to decide
what to show — only what is not a conversation in the first place.

The page's own copy now states the scope rather than claiming "every governed
step the runtime took": *"every governed step in this account… your own
conversations, and the runtime steps taken outside them, such as connecting a
provider or pinning a model. Other people's conversations are never shown
here."*

**Evidence.** `tests/test_accounts.py::test_governed_steps_outside_a_conversation_reach_the_audit_log`
records both halves: the runtime-channel events appear, and the other account's
conversation still does not. The pre-existing isolation test is unchanged and
still passes.

**Evidence (live).** A real Anthropic credential entered through the product's
own dialog, a model pinned and checked, then the page read straight afterwards:
[`working/217-FIXED-151-audit-log-live.png`](screenshots/working/217-FIXED-151-audit-log-live.png).

**UI when closed.** Connecting a provider, pinning a model and running a
readiness check are each visible in the audit log immediately after they happen.

---

## FIXED-152 — The Knowledge Map's source picker browsed the whole Raiker installation

**Status: fixed in this change. Reported on 2026-08-10.**

**Observed.** Knowledge Map → **+** opened a browser rooted at the workspace
root and listed everything under it — Raiker's own source tree, `apps/`,
`docs/`, `scripts/`, the lot — and offered any of it as something to index. The
only way to add a file from the owner's computer was to place it in the
workspace first, which duplicates it into Raiker whether or not the owner wanted
a copy there.

**Root cause.** `DashboardService.browse_brain_sources` resolved every request
against `self.workspace_root` and listed its children, skipping only `.git`,
`.raiker` and `node_modules`. "Inside the workspace" was the entire boundary,
and the workspace is also where Raiker itself lives.

**Fix.** A boundary with three parts, in `raiker/control/knowledge_scope.py`:

1. **Raiker's own data** — each project's files, the files turns generated
   (`.raiker/artifacts`), and approved memory (`.raiker/memory`). Chat, Build,
   Tasks, Schedules and uploaded user files live in the encrypted database and
   are already nodes in the graph, so the picker lists the **database** as a
   root that says exactly that and is not browsable — an owner can see their
   chats are covered instead of hunting for a way to add them.
2. **Folders the owner explicitly granted** — any directory on the machine,
   named by the owner, stored per owner, revocable. Revoking a grant also
   removes every source indexed under it, because leaving them would keep
   reading a folder the owner just closed.
3. **Nothing else.** Addressing is `<root_id>/<relative>`, so there is no path
   that means "the workspace" and no request that can ask for one. Resolution
   happens **before** the containment check, so a `..` segment or a symlink
   cannot leave the root it claims to be in.

**Adding a file from the computer, without duplicating it.** Two routes, and the
difference between them is stated in the dialog rather than implied:

* **Grant the folder** — Raiker reads the file where it is and copies nothing.
* **Add a single file** — this is an upload, so it *is* a copy. `store_copy` has
  no default on the server: a request without an explicit true is refused as
  `brain_upload_copy_not_authorised`. In the UI the button appears only behind a
  tick that says the file will be stored in Raiker. Copies land in one named
  place, `.raiker/artifacts/knowledge-uploads/`, so every copy the Knowledge Map
  holds can be found and deleted.

**Evidence.** `tests/test_knowledge_scope.py` — seventeen tests covering the
picker opening on named places rather than a listing, the database being named
rather than walked, the workspace root not being addressable, traversal and
symlink escapes, grants being read in place, revocation removing what it
indexed, one owner's grant not being another's root, and the upload refusing to
store without consent. `apps/web/src/lib/views/BrainView.test.ts` covers the
same boundary in the dialog, including the tick that gates the copy.

**Evidence (live).** [`working/218-FIXED-152-knowledge-boundary-live.png`](screenshots/working/218-FIXED-152-knowledge-boundary-live.png)
— the picker on a real host, and
[`working/219-FIXED-152-granted-folder-live.png`](screenshots/working/219-FIXED-152-granted-folder-live.png)
— a folder outside the workspace granted, browsed and reviewed without being
copied.

**UI when closed.** The **+** dialog opens on named places — the owner's
projects, what Raiker generated, approved memory, the database, and any folder
they granted. Nothing else on the machine is visible from it, and no file is
copied into Raiker without the owner saying so.

---

## FIXED-153 — The audit log's turn-identity column rendered `â€"`

**Status: fixed in this change. Found on 2026-08-10 while verifying FIXED-151.**

**Observed.** With events finally reaching the page, every row's **Turn
identity** cell read `â€"` where the neighbouring Risk and Summary cells read a
proper em dash.

**Root cause.** `apps/web/src/lib/views/ActivityView.svelte` held the literal
bytes of a UTF-8 em dash decoded as latin-1 — `â€"` — written into the source at
some point and never seen, because until FIXED-151 the table had no rows to
render it in. It is the ordinary cost of a defect hidden behind another defect:
fixing the first is what exposes the second.

**Fix.** The character is an em dash again, matching the two columns beside it.
A search of the whole tree found no other occurrence.

**UI when closed.** Every "nothing here" cell in the audit-log row reads the
same em dash.

---

## FIXED-141 — Three Models tabs were unreachable by deep link

**Status: fixed while splitting the Models page by model origin (Task 14).**
Found on 2026-08-09 driving the tab strip in a browser.

**Observed.** `#/models?tab=library`, `?tab=discover`, and `?tab=downloads` all
opened **Providers**. Clicking the tabs worked, so the panels looked fine; only
the links into them were broken:

| Link | Emitted by | Landed on |
|---|---|---|
| `#/models?tab=library` | "Use models LM Studio already downloaded →" | Providers |
| `#/models?tab=library` | Hugging Face download destination | Providers |
| `#/models?tab=discover` | ModelSetupView "Continue in Models" | Providers |
| `#/models?tab=downloads` | Operation tray "View downloads" | Providers |

Three BUG-69 live specs navigated the same way and were therefore asserting
against the Providers panel while appearing to test Library and Discover.

**Root cause.** `HUB_TABS.models` in `apps/web/src/lib/nav.ts` still listed the
pre-BUG-69 four (`providers`, `routing`, `pricing`, `posture`). `tabFromHash`
falls back to a hub's first tab for an unrecognised id — the correct behaviour
for a typo, and silent for a tab that genuinely exists but was never registered.
Nothing failed loudly: the panel rendered, just the wrong one.

**Fix.** Every Models panel is registered. A new `HUB_TAB_ALIASES` maps
superseded ids onto their replacements (`providers`/`library` → `local`,
`discover` → `huggingface`, `downloads` → `activity`) so bookmarks and older
builds keep working, and every internal link now emits a canonical id.

**Evidence.** Two nav tests covering all seven panels and all four aliases, plus
a live sweep of eleven deep links.

---

## FIXED-171 — Windows SQLCipher memory locking is crash-contained and explicit

**Status: fixed in this change. Was BUG-46.**

**Observed.** This Windows SQLCipher build terminates a process with stack
overflow after `VirtualLock` fails. Encryption remained healthy, but the product
could neither prove locked key pages nor safely inspect the condition in-process.

**Fix.** A disposable child now probes `cipher_memory_security`; the resident
host maps a child crash, timeout, invalid result or unsupported lock to a durable
degraded posture. Frozen GUI builds use private payload/result files and their
own hidden worker entry rather than Python `-m`. Settings → Security reports
database encryption separately from **Locked in memory** or **Degraded**.

**Evidence.** `tests/test_sqlcipher_memory_security.py`, including the real
Windows stack-overflow code and frozen-worker path; packaged health returned
`store=ok` and `auto_probe_host_crash` without terminating. Screenshot:
[`working/bug-46-security-live.png`](screenshots/working/bug-46-security-live.png).

---

## FIXED-172 — First run is guided and the desktop host has a native tray

**Status: fixed in this change. Was BUG-48.**

**Observed.** A fresh owner had separate login and model screens, no complete
privacy/backup flow, and no operating-system tray icon. The release payload did
not contain a self-contained GUI runtime.

**Fix.** Fresh workspaces enter a resumable five-stage wizard: local owner,
model choice or defer, exact readiness and privacy, optional encrypted verified
backup, then completion. `scripts/build_desktop.py` creates the self-contained
payload with dashboard and tray dependencies; Windows uses a no-console
launcher, and WiX installs a Start Menu shortcut. The native tray exchanges a
one-time secret for a host-control-only session and reuses the web Host routes.

**Evidence.** Unit/API/component tests, a successful 75.8 MB frozen Windows
payload smoke (`/` and `/api/health` both 200), and live screenshots:
[`working/bug-48-setup-complete-live.png`](screenshots/working/bug-48-setup-complete-live.png),
[`working/bug-48-setup-mobile-live.png`](screenshots/working/bug-48-setup-mobile-live.png),
and [`working/bug-48-native-tray-menu-live.png`](screenshots/working/bug-48-native-tray-menu-live.png).

---

## FIXED-173 — Policy configuration no longer advertises a dead deny set

**Status: fixed in this change. Was BUG-51.**

**Observed.** `StaticPolicyConfig.denied_actions` looked authoritative and was
never consumed by `PolicyEngine`.

**Fix.** The dead field was removed. Static configuration now rejects an action
classified as both allowed and approval-required, so the two live policy sets
cannot silently contradict one another.

**Evidence.** `tests/test_policy.py` and the full policy/runtime suite.

---

## FIXED-174 — Every governed withheld call is disclosed by the runtime

**Status: fixed in this change. Was BUG-59 and BUG-60.**

**Observed.** Executor-level withheld results were ordinary tool output, leaving
disclosure to the model, and one web refusal sent the owner to a nonexistent
Settings → Capabilities page.

**Fix.** Governed executor refusals emit `model_tool_call_refused` with runtime
attribution, tool, source, reasons and remediation route. Chat and Build render
the refusal card whatever the model says. The destination is the shipped
**Permissions** route, and tool JSON preserves readable Unicode.

**Evidence.** Runtime and Svelte regression tests plus the live refusal and
deep-link check in
[`working/bug-60-runtime-refusal-live.png`](screenshots/working/bug-60-runtime-refusal-live.png).

---

## FIXED-175 — Approving task creation does not schedule execution

**Status: fixed in this change. Was BUG-64.**

**Observed.** Approving a model's **Create task** proposal stamped the current
time and let the scheduler run it, though the approval only promised creation.

**Fix.** `DashboardService.create_task` has explicit `start_immediately`
semantics. Direct owner creation keeps start-now behaviour; approval and model
tool paths park the task with no schedule. `POST /api/tasks/{id}/run` is the
separate execution decision and Tasks exposes **Run now**.

**Evidence.** Service/API/approval tests and live verification that approval
created one parked task, the scheduler ignored it, and only **Run now** produced
a completed run:
[`working/bug-64-parked-task-live.png`](screenshots/working/bug-64-parked-task-live.png).

---

## FIXED-176 — Exported transcripts carry a portable citation ledger

**Status: fixed in this change. Was BUG-65.**

**Observed.** Markdown, HTML and PDF exports retained `[sN]` markers without the
turn source ledger that resolved them in the live conversation.

**Fix.** Each exported turn includes a sanitized source list with marker, title,
locator and kind. Source passages remain local. A marker absent from the ledger
is removed and counted in the export manifest rather than emitted as a broken
citation.

**Evidence.** `tests/test_session_transcript_export.py` covers all formats,
escaping, redaction, resolved markers, unresolved markers and passage omission.

---

## FIXED-177 — Ordinary loopback reads no longer spend the public DoS budget

**Status: fixed in this change. Was BUG-88.**

**Observed.** A fast sweep through normal pages could exhaust the one global
per-IP API window and make Models report a throttled read.

**Fix.** A real socket peer on direct loopback may bypass the rate limit for
safe reads only. Writes remain bounded. A public bind rate-limits all requests,
and forwarded/proxy headers cannot manufacture the loopback exemption.

**Evidence.** `tests/test_api_rest_hardening.py` covers loopback navigation,
write limits, public-bind reads and forged proxy headers; the live desktop sweep
completed without 429 responses.

---

## FIXED-178 — A connected provider credential can be removed in the app

**Status: fixed in this change. Found during live verification.**

**Observed.** Models could save and replace a provider key, while the backend's
empty-connection removal path had no corresponding UI control.

**Fix.** Each connected hosted-provider card exposes **Disconnect**, confirms
the action, removes the encrypted vault credential through the existing API and
returns the card to **Not connected**.

**Evidence.** `ModelsView.test.ts` covers the owner flow. Anthropic, OpenAI and
OpenRouter test credentials were removed through this control after the live
provider run.

---

## FIXED-179 — Release artifact actions are pinned immutably

**Status: fixed in this change. Was BUG-49.**

**Observed.** All six `actions/upload-artifact` and
`actions/download-artifact` uses in the manual Release workflow referenced the
mutable `@v4` major tag while handling the binaries owners install.

**Fix.** Every upload use is pinned to
`ea165f8d65b6e75b540449e92b4886f43607fa02`; every download use is pinned to
`d3f86a106a0bac45b974a628896c90dbdf5c8093`. The same change replaces the macOS
Intel target with native Linux ARM64, installs the Windows desktop build tool,
and makes Debian/AppImage names and appimagetool downloads architecture-aware
while keeping Release manual-only and draft-only. Explicitly unsigned test runs
now stop successfully after their per-target uploads instead of entering the
signed-channel verifier and failing.

**Evidence.** `tests/test_release_workflow.py` parses the workflow and asserts
its sole trigger, signed-draft gate, supported cross-platform runners, desktop
build dependency, native appimagetool selection, and 40-character
artifact-action digests. `tests/test_release_pipeline.py` asserts the exact
four-runner matrix; `tests/test_installer_build.py` covers x86-64 and ARM64 Linux
package metadata and filenames.

---

## FIXED-180 — Linux CI no longer stalls with every test store memory-locked

**Status: fixed in this change. Found during hosted verification.**

**Observed.** The Ubuntu CI runner passed the SQLCipher memory-security probe,
so the complete 3,272-test suite ran with locked key pages. Store-heavy tests
then remained at four percent for more than thirty minutes, while Windows local
verification completed because that host correctly fell back to memory security
off.

**Fix.** CI proves the real Linux SQLCipher memory-lock capability in one
dedicated fail-closed probe, then runs the broad isolation suite with
`RAIKER_SQLCIPHER_MEMORY_SECURITY=off`. Verbose test names, slow-test timings
and a 45-minute job limit make any future stall attributable and bounded. The
dedicated BUG-46 tests continue to exercise enabled, unavailable and explicit
off behavior.

**Evidence.** `tests/test_ci_workflow.py` pins the probe/suite separation,
diagnostic output and job timeout. The focused CI, SQLCipher and API regression
set passes with 55 tests.

---

## FIXED-181 — Multi-call answer passes are separated in Chat *(was BUG-53)*

**Status: fixed in this change.**

**Observed.** A turn that spoke, called a tool, and then answered rendered the
two model passes as one run-on sentence. `collectText` joined every streamed
`text_delta` with an empty string and had no request boundary.

**Fix.** Transcript collection now follows `model_request_started` lifecycle
events and inserts exactly one paragraph boundary before the first text of a
later model request. It inserts nothing for a tool-only pass and preserves an
existing newline, so streaming deltas within one response still join without
breaking words.

**Evidence.** `turnPhases.test.ts` covers successive response passes, a tool-only
pass, and an existing boundary. The deterministic denial live scenario verifies
the visible seam in Chat and Build.

---

## FIXED-182 — The live end-to-end model stub is reproducible *(was BUG-54)*

**Status: fixed in this change.**

**Observed.** The two batched-call live specs referenced a scratch-only
`stub_model.py`; neither the exact response sequence nor their claimed evidence
could be reproduced from a clone.

**Fix.** `apps/web/e2e/fixtures/stub_model.py` is a checked-in, loopback-only,
OpenAI-compatible deterministic server. It implements the exact multi-read,
write-batch, approval-queue and policy-refusal continuations used by both specs,
with bounded request bodies and no credential or external network.

**Evidence.** `tests/test_live_stub_model.py` verifies the scenario contract;
both live specs now resolve the fixture by repository path.

---

## FIXED-183 — Chat has one live transcript implementation *(was BUG-55)*

**Status: fixed in this change.**

**Observed.** `ChatView.svelte` retained roughly ninety lines behind
`{#if false}`, including a complete approval card whose governance copy differed
from the live card.

**Fix.** The disabled transcript tree, its unused imports and helpers, and its
orphaned styles were removed. The one rendered approval path remains the source
of truth.

**Evidence.** Svelte check reports zero errors and warnings; the Chat component
and live transcript regressions pass.

---

## FIXED-184 — Context compacts automatically at 90% *(former Known Limit)*

**Status: fixed in this change.**

**Observed.** History had a coarse replay bound but no runtime compaction. Long
conversations dropped their oldest exchanges rather than preserving a compact
continuity record, even though the README promised a 90% design.

**Fix.** At 90% of a known exact-model capacity, Raiker summarizes older
completed exchanges in a separate tool-free, reasoning-disabled request and
retains the newest two verbatim. The durable record has an exact through-turn
boundary and protected plan, approval, checkpoint, and source IDs. Transcript
rows are never changed. `PreCompact` and `PostCompact` hooks bracket the pass;
unknown capacity or any failure keeps bounded recent history and records the
safe fallback. Compaction requests have their own ledger kind.

**UI when closed.** Chat and Build's Context panel shows **Earlier context
compacted** with before/after estimates or **Recent history retained** when the
pass was unavailable, and states that the transcript is unchanged.

**Evidence.** `tests/test_conversation_compaction.py` covers the threshold,
boundary, owner scope, protected state, failure, bounded replay, tool-free model
call and separate accounting. Runtime history, hooks, dashboard and context
popover regressions pass.

---

## FIXED-185 — Connected providers have a truthful rolling usage view *(former Known Limit)*

**Status: fixed in this change.**

**Observed.** Models showed all-time local accounting but no weekly provider
view. Calling that a quota would have been misleading: ordinary inference keys
do not expose one uniform Anthropic/OpenAI/OpenRouter account limit, and Ollama
has no account service.

**Fix.** Models → Activity now lists connected providers only and presents two
separate seven-day receipts. **Raiker observed** aggregates ledger tokens,
turns, all model requests, compactions, and cost where exact pricing is known.
**Provider reported** uses genuine OpenRouter key data with the ordinary key,
and OpenAI/Anthropic organization usage only when a separate optional admin key
was entered through Models; Ollama truthfully reports no compatible quota API.
Normalized numeric snapshots are owner-scoped and cached for five minutes.
Owners can set an advisory weekly token budget that is explicitly not a provider
subscription limit.

**Evidence.** Provider adapter, bounded snapshot, connection, API, ledger and
Models component tests pass. Playwright live turns cover Anthropic, OpenRouter,
OpenAI and Ollama with credentials entered through Models and dialogs closed
before screenshots.

