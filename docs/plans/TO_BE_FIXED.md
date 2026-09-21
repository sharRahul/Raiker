## Goal

Make Raiker a secure AI product that combines **four** things: a polished AI
assistant, a governed AI agent, **a capable coding/build agent**, and an
extensible governed agent platform.

As an assistant, Raiker should help users understand, reason, decide, and
communicate through a polished conversational experience. As an agent, Raiker
should be able to plan tasks, gather context, use tools, execute approved
actions, verify outcomes, and explain what it did. As a coding agent, Raiker
should read a repository, make the change, run the tests, read the failure and
iterate to green, in one governed session. As a platform, Raiker should provide
the governed runtime foundation for models, tools, plugins, interfaces, memory,
approvals, audit events, checkpoints, and integrations.

Governance, observability, policy awareness, control and security are **inherent
properties** of that runtime, not optional layers added around the agent.

> **Which open work blocks which pillar is in [`PILLAR_MAP.md`](PILLAR_MAP.md),
> and how an action reaches an executor at all is in
> [`GOVERNANCE_ENTRY_PATHS.md`](GOVERNANCE_ENTRY_PATHS.md).** This preamble is
> repeated in several plans because each is read on its own; the pillar map is
> the one place that says what the whole set adds up to.

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
`docs/architecture/SECURITY_AND_POLICY.md` → "Security Philosophy". The rules below still hold
and are compatible with it:

# To be fixed

Defects and gaps found while executing
[the live manual test plan](RAIKER_LIVE_MANUAL_TEST_PLAN.md) against a running
`raiker-web` on **2026-07-26**, hosted Anthropic `claude-haiku-4-5-20251001`.

Each entry states what was observed, the reproduction, the root cause in code,
and the proposed fix. Every deferred item found by the FIXED-01 through FIXED-48
audit is an explicit BUG with a required user-interface outcome, so closing
backend work cannot leave an invisible or misleading product surface.

**Closed entries live in [`FIXED_ITEMS.md`](FIXED_ITEMS.md).** They are still
evidence — what was observed, the root cause, and the user-interface outcome that
had to be true before it could be called closed — but they are no longer mixed in
with the open work, so this document answers one question: what is left.

[`GAP_BUILD_CHAT.md`](GAP_BUILD_CHAT.md) — GAP-BUILD and GAP-CHAT — are not defects. They are the itemised
distance between what Build and Chat ship today and what each is meant to be:
Build as an autonomous coding agent that closes its own loop, Chat as a general
agentic work assistant that acts across the owner's tools and files. They are
written to the same standard as the defects: what exists today with the file
that proves it, what is missing, and the concrete work.

Evidence: `screenshots/not-working/` (defects),
`screenshots/working/` (verified behaviour).

**This list holds only what is still open.** A row marked *Fixed* is kept in the
index so a reader arriving with that number is not left wondering; its full
record — observation, root cause, and the interface outcome that had to be true
first — is in [`FIXED_ITEMS.md`](FIXED_ITEMS.md) under the FIXED number the row
names.

| ID | Severity | Area | Status |
|---|---|---|---|
| [BUG-194](#bug-194--the-governed-shell-has-an-os-boundary-but-no-interactive-background-or-remote-execution) | Low | Shell / sandbox / recovery | Open — reduced again 2026-08-21; foreground SSH/Daytona and safeguarded egress/credential/trust foundations ship, while live container and external trust-anchor proofs remain |
| [MEM-08](FIXED_ITEMS.md#fixed-316--every-turn-coordinate-was-a-dead-end) | Medium | Memory reliability | **Closed 2026-08-29 (FIXED-316)** — a turn coordinate opens the exchange. With it, every MEM entry raised by the 2026-08-11 memory audit is closed: MEM-06 as FIXED-241, MEM-07 as FIXED-284, MEM-09 as FIXED-310, MEM-10 as FIXED-283/292/293/294. |
| [BUG-220](FIXED_ITEMS.md#fixed-286--a-task-reported-done-while-the-work-it-delegated-was-still-open) | Medium | Tasks / delegation | **Closed 2026-08-25 (FIXED-286)** — a parent parks as `waiting_for_children` and settles on the last child. Its routing half is now [backlog #23](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#medium-priority-high-effort) |
| [BUG-225](FIXED_ITEMS.md#fixed-298--a-paired-channel-could-still-only-record-a-message) | Medium → Low | Channels / extensibility | **Closed 2026-08-27 (FIXED-298)** — owner-stored routing and exact, single-use approval responses now ship; record-only remains the default |
| [BUG-226](#bug-226--three-of-the-five-hook-handler-types-do-not-exist) | Low | Hooks / handlers | Open remainder — reduced again 2026-09-04; `prompt` closed as FIXED-303 and `http` as [FIXED-380](FIXED_ITEMS.md#fixed-380--three-of-the-five-hook-handler-types-did-not-exist-now-two), while `mcp_tool` and `agent` stay refused with their reasons |
| [BUG-227](FIXED_ITEMS.md#fixed-366--build-could-read-a-repository-and-not-understand-it) | Low | Plugins / language intelligence | **Closed 2026-09-03 (FIXED-366)** — its first question was a scope decision, and the answer is no: Raiker does not want an LSP client. B10's tool set ships without one and both plugin specs state what that costs |
| [BUG-228](#bug-228--a-plugin-panel-has-no-route-permission-or-accessibility-contract) | Low | Plugins / web UI | Open — raised 2026-08-22, split out of BUG-221 |
| [BUG-229](FIXED_ITEMS.md#fixed-324--thirty-seven-live-specs-each-carried-their-own-sign-in) | Low | Live test harness | **Closed 2026-08-30 (FIXED-324)** — every live spec with a sign-in function delegates to the shared helper. The per-spec password that stops two specs sharing a workspace is a different defect, [BUG-247](#bug-247--every-live-spec-brings-its-own-owner-password) |
| [BUG-234](#bug-234--the-remainder-what-raiker-does-not-use-of-the-mcp-revision-it-now-speaks) | Medium → Low | MCP / interoperability | Open — reduced twice on 2026-09-04 ([FIXED-378](FIXED_ITEMS.md#fixed-378--raiker-spoke-the-current-mcp-revision-and-did-not-use-its-transport), [FIXED-387](FIXED_ITEMS.md#fixed-387--a-tool-result-had-one-shape-and-the-revision-defines-six)) and twice again on 2026-09-05 ([FIXED-411](FIXED_ITEMS.md#fixed-411--a-server-initiated-request-was-filed-as-the-answer-to-raikers-own), [FIXED-412](FIXED_ITEMS.md#fixed-412--an-event-stream-was-read-one-line-at-a-time-and-the-rest-was-dropped)). The transport conforms, the card names what a server offers and Raiker does not use, every content-block shape reaches the model, a server-initiated request is answered rather than mistaken for a response, and an event stream is read and resumed correctly; **incremental** delivery, remote OAuth, MCP Apps and elicitation's owner-facing half remain |
| [GEP-02](GOVERNANCE_ENTRY_PATHS.md#gep-02--the-stop-switchs-scope-is-undefined-for-read-paths), [GEP-03](GOVERNANCE_ENTRY_PATHS.md#gep-03--nested_boundaries_architecturemd278-overstates-the-architecture) | Low | Governance architecture / documentation | Open — not duplicated here. GEP-02 is **an owner decision** and the helper now carries the answer at no cost |
| [BUG-239](#bug-239--an-empty-gate-table-means-three-different-things) | Low | Capability gates / owner decision | Open remainder — the live half closed 2026-08-30 as [FIXED-322](FIXED_ITEMS.md#fixed-322--permissions-said-off-about-a-capability-that-would-have-run): Permissions now reports what the enforcing path answers. Unifying the three resolutions is still **an owner decision** |
| [BUG-240](FIXED_ITEMS.md#fixed-292--semantic-memory-built-a-space-the-question-never-entered) | Medium → Low | Memory / retrieval | **Closed 2026-08-26 (FIXED-292, FIXED-294)** — both the provider half and the managed-file half ship; the row is kept so a reader arriving with the number is not left wondering |
| [BUG-241](FIXED_ITEMS.md#fixed-313--fullpage-evidence-captures-stopped-at-the-first-viewport) | Low | Live test harness / evidence | **Closed 2026-08-29 (FIXED-313)** — one shared capture helper; all 56 live specs go through it |
| [BUG-242](FIXED_ITEMS.md#fixed-309--build-opened-an-empty-conversation-after-a-reload) | Medium | Build / web UI | **Closed 2026-08-29 (FIXED-309)** — the conversation rides in the URL and Build restores it |
| [BUG-243](FIXED_ITEMS.md#fixed-314--a-question-could-not-recall-the-memory-that-answered-it) | High | Memory / retrieval | **Closed 2026-08-29 (FIXED-314)** — raised while verifying FIXED-311: a question was being used as a filter |
| [BUG-244](FIXED_ITEMS.md#fixed-319--importing-the-same-memory-twice-stored-it-twice) | Low | Memory / import | **Closed 2026-08-29 (FIXED-319)** — the review step says what is new before anything is written, and the import reports what it changed |
| [BUG-245](FIXED_ITEMS.md#fixed-323--a-cited-past-conversation-named-its-exchanges-and-could-not-open-one) | Low | Memory / citations | **Closed 2026-08-30 (FIXED-323)** — one `anchors` column, built from the tool result the runtime read, and a link per exchange |
| [BUG-246](FIXED_ITEMS.md#fixed-320--the-authority-matrix-hid-its-own-verdicts-on-a-phone) | Low | Permissions / web UI | **Closed 2026-08-29 (FIXED-320)** — raised and closed in the same run; a narrow window gets the same verdicts as stacked cards |
| [BUG-247](FIXED_ITEMS.md#fixed-328--one-owner-for-the-whole-live-suite) | Low | Live test harness | **Closed 2026-08-30 (FIXED-328)** — `OWNER_CREDENTIALS` is the only owner credential in the suite |
| [BUG-276](FIXED_ITEMS.md#fixed-386--governed-events-only-left-when-somebody-pressed-a-button) | Low | Observability / telemetry export | **Closed 2026-09-04 ([FIXED-386](FIXED_ITEMS.md#fixed-386--governed-events-only-left-when-somebody-pressed-a-button))** — a cadence on the host tick, under the same pause switch and the same governed route as the button. The entry's *routine* half was declined with a reason: a task cycle is a model turn, and delivery is not a model's judgement |
| [BUG-277](FIXED_ITEMS.md#fixed-388--a-valid-key-was-answered-with-check-your-network) | **High** | Models / provider errors | **Closed 2026-09-04 ([FIXED-388](FIXED_ITEMS.md#fixed-388--a-valid-key-was-answered-with-check-your-network))** — raised on this round's first live press of **Test**. The identity-linked classifier matched three sentences the provider does not send, so FIXED-370 and FIXED-372 were both unreachable |
| [BUG-278](FIXED_ITEMS.md#fixed-389--twenty-six-connectors-said-they-were-installed-under-a-card-saying-none-were) | Medium | Extensions / accessibility | **Closed 2026-09-04 ([FIXED-389](FIXED_ITEMS.md#fixed-389--twenty-six-connectors-said-they-were-installed-under-a-card-saying-none-were))** — met/unmet was carried by colour alone, so the rows contradicted their own counters and said nothing at all in greyscale |
| [BUG-279](FIXED_ITEMS.md#fixed-390--three-surfaces-said-next-and-printed-a-full-timestamp) | Low | Web UI / time formatting | **Closed 2026-09-04 ([FIXED-390](FIXED_ITEMS.md#fixed-390--three-surfaces-said-next-and-printed-a-full-timestamp))** — `relativeTime` is a past formatter; three surfaces showing a future instant printed a locale string |
| [BUG-280](FIXED_ITEMS.md#fixed-391--one-tab-in-the-observability-hub-answered-an-empty-list-with-a-grey-line) | Low | Web UI / consistency | **Closed 2026-09-04 ([FIXED-391](FIXED_ITEMS.md#fixed-391--one-tab-in-the-observability-hub-answered-an-empty-list-with-a-grey-line))** — the one list surface in the product that did not use the shared empty state |
| [BUG-281](FIXED_ITEMS.md#fixed-392--the-source-said-a-gate-ships-enabled-the-product-said-it-was-off) | Low | Documentation / capability defaults | **Closed 2026-09-04 ([FIXED-392](FIXED_ITEMS.md#fixed-392--the-source-said-a-gate-ships-enabled-the-product-said-it-was-off))** — a docstring described the shipped gate table and called it the product; the account resolves `unset` to off |
| [BUG-282](FIXED_ITEMS.md#fixed-393--the-guide-described-a-boundary-the-product-removed-nine-days-earlier) | Medium | Documentation / memory | **Closed 2026-09-04 ([FIXED-393](FIXED_ITEMS.md#fixed-393--the-guide-described-a-boundary-the-product-removed-nine-days-earlier))** — the guide told owners semantic recall was half-built, nine days after FIXED-292 finished it |
| [BUG-283](FIXED_ITEMS.md#fixed-394--thirty-destinations-and-two-of-them-were-copies-of-the-others) | Low | Web UI / information architecture | **Closed 2026-09-04 ([FIXED-394](FIXED_ITEMS.md#fixed-394--thirty-destinations-and-two-of-them-were-copies-of-the-others))** — 244 words of explanation to the guide, one contract that was stated twice, and two tabs that were copies of other surfaces |
| [BUG-284](FIXED_ITEMS.md#fixed-395--three-mobile-bleeds-that-only-existed-once-the-workspace-held-anything) | Medium | Web UI / responsive layout | **Closed 2026-09-04 ([FIXED-395](FIXED_ITEMS.md#fixed-395--three-mobile-bleeds-that-only-existed-once-the-workspace-held-anything))** — found by running the width sweep against a workspace that had been worked in; reproduced on unmodified `main` |
| [BUG-285](FIXED_ITEMS.md#fixed-590--a-turn-that-failed-blamed-the-local-runtime-for-it) | Medium | Models / Ollama cloud chat | **Closed 2026-09-20 ([FIXED-590](FIXED_ITEMS.md#fixed-590--a-turn-that-failed-blamed-the-local-runtime-for-it))** — the entry's second interface outcome: a failed turn reports the refusal the runtime named. The message was the surface's, not the provider's |
| [BUG-289](FIXED_ITEMS.md#fixed-526--an-owner-was-told-to-check-that-openrouter-was-running) | Low | Models / provider errors | **Closed 2026-09-14 ([FIXED-526](FIXED_ITEMS.md#fixed-526--an-owner-was-told-to-check-that-openrouter-was-running))** — a hosted provider gets a remedy an owner can act on |
| [BUG-290](#bug-290--three-of-the-four-providers-this-round-was-given-keys-for-cannot-be-reached-from-this-host) | Low | Live evidence / providers | Open — the same egress limit as [BUG-273](#bug-273--three-live-scenarios-of-the-2026-09-03-round-are-written-and-unrun), reconfirmed 2026-09-13 with three keys |
| [BUG-291](FIXED_ITEMS.md#fixed-534--a-live-helper-that-found-nothing-let-a-later-assertion-take-the-blame) | Low | Live test harness | **Closed 2026-09-14 ([FIXED-534](FIXED_ITEMS.md#fixed-534--a-live-helper-that-found-nothing-let-a-later-assertion-take-the-blame))** |
| [BUG-292](FIXED_ITEMS.md#fixed-534--a-live-helper-that-found-nothing-let-a-later-assertion-take-the-blame) | Low | Live test harness | **Closed 2026-09-14 ([FIXED-534](FIXED_ITEMS.md#fixed-534--a-live-helper-that-found-nothing-let-a-later-assertion-take-the-blame))** — `chooseModelForTurn` is the helper every turn-sending spec uses |
| [BUG-293](FIXED_ITEMS.md#fixed-542--every-side-effect-capability-now-says-what-it-would-cost-and-one-of-them-had-no-gate-at-all) | Medium | Governance / release assurance | **Closed 2026-09-15 ([FIXED-542](FIXED_ITEMS.md#fixed-542--every-side-effect-capability-now-says-what-it-would-cost-and-one-of-them-had-no-gate-at-all))** — and it found `image_generation` with no gate at all |
| [BUG-294](FIXED_ITEMS.md#fixed-511--threads-described-a-hundred-rows-and-called-it-a-workspace) | Medium | Threads / work index | **Closed 2026-09-14 ([FIXED-511](FIXED_ITEMS.md#fixed-511--threads-described-a-hundred-rows-and-called-it-a-workspace))** — raised and closed in the same run: the work index filters, facets over everything that matched, and pages |
| [BUG-273](FIXED_ITEMS.md#fixed-541--three-scenarios-blocked-on-a-key-for-six-rounds-and-on-three-stale-selectors-for-one-more) | Low | Live test harness / evidence | **Closed 2026-09-15 ([FIXED-541](FIXED_ITEMS.md#fixed-541--three-scenarios-blocked-on-a-key-for-six-rounds-and-on-three-stale-selectors-for-one-more))** — six rounds blocked on a key, then three stale selectors |
| [BUG-271](FIXED_ITEMS.md#fixed-375--a-reviewer-could-narrow-a-change-and-could-not-correct-one) | Low | Build / Approvals / code review | **Closed 2026-09-04 ([FIXED-375](FIXED_ITEMS.md#fixed-375--a-reviewer-could-narrow-a-change-and-could-not-correct-one))** — an edit is a new proposal with its own preview, hash and approval; the original resolves as denied with the replacement named. Closes GAP-BUILD B14 |
| [BUG-274](FIXED_ITEMS.md#fixed-372--the-answer-to-an-identity-linked-key-was-go-and-get-another-one) | Medium | Models / provider connection | **Closed 2026-09-04 ([FIXED-372](FIXED_ITEMS.md#fixed-372--the-answer-to-an-identity-linked-key-was-go-and-get-another-one))** — raised and closed in this round: FIXED-370 classified the refusal and left the owner a dead end. The connection now carries the workspace |
| [BUG-248](#bug-248--twenty-seven-live-specs-still-sign-in-inside-a-test-body) | Low | Live test harness | Open remainder — reduced again 2026-09-04 to **twelve**; eight more converted and each re-run against a used workspace, three must keep their own |
| [BUG-249](FIXED_ITEMS.md#fixed-326--a-fixed_items-link-pointed-at-a-heading-that-does-not-exist) | Low | Documentation / CI | **Closed 2026-08-30 (FIXED-326)** — one line, and `test_docs_consistency` is green |
| [BUG-250](FIXED_ITEMS.md#fixed-549--a-spec-that-had-to-disambiguate-its-own-subject) | Low | Live test harness | **Closed 2026-09-15 ([FIXED-549](FIXED_ITEMS.md#fixed-549--a-spec-that-had-to-disambiguate-its-own-subject))** — `roundName()` gives each round its own subject |
| [BUG-251](FIXED_ITEMS.md#fixed-352--every-path-an-owner-typed-was-a-path-they-had-to-know) | Medium | Web UI / file and folder selection | **Closed 2026-09-03 (FIXED-352)** — the host lists directory names and one `PathPicker` serves all four fields |
| [BUG-252](FIXED_ITEMS.md#fixed-350--dropping-a-file-worked-in-one-place-and-was-ignored-in-four) | Low | Web UI / attachments | **Closed 2026-09-03 (FIXED-350)** — one drop target, on every surface that already accepted an upload |
| [BUG-253](FIXED_ITEMS.md#fixed-353--reloading-the-page-signed-the-owner-out) | Medium | Authentication / web UI | **Closed 2026-09-03 (FIXED-353)** — an HttpOnly session cookie with a double-submit CSRF token and an origin check |
| [BUG-254](FIXED_ITEMS.md#fixed-354--a-subscriptions-own-usage-and-limits-were-not-shown) | Medium | Models / Observability | **Closed 2026-09-03 (FIXED-354)** — the limit windows a provider volunteers with a turn, and nothing when it volunteers none |
| [BUG-255](FIXED_ITEMS.md#fixed-351--a-decision-raised-while-raiker-was-in-the-background-reached-nobody) | Low | Approvals / notifications | **Closed 2026-09-03 (FIXED-351)** — the already-permissioned browser notification, only while Raiker is not the visible window |
| [BUG-256](FIXED_ITEMS.md#fixed-363--dictation-was-the-last-surface-that-was-not-local) | Medium | Voice / privacy posture | **Closed 2026-09-03 (FIXED-363)** — a speech runtime on this machine, and a security header that had been denying the microphone to Raiker's own page all along |
| [BUG-266](FIXED_ITEMS.md#fixed-364--a-live-round-could-start-on-the-previous-rounds-data) | Low | Live test harness / host lifecycle | **Closed 2026-09-03 (FIXED-364)** — the reset waits for the process, not the response, and reads the directory back |
| [BUG-267](FIXED_ITEMS.md#fixed-362--an-expected-answer-was-written-to-the-console-as-a-failure) | Low | Authentication / web UI | **Closed 2026-09-03 (FIXED-362)** — the boot question gets a route that answers it rather than refusing it |
| [BUG-269](FIXED_ITEMS.md#fixed-373--read-aloud-was-the-half-of-voice-that-was-still-not-local) | Low | Voice / privacy posture | **Closed 2026-09-04 ([FIXED-373](FIXED_ITEMS.md#fixed-373--read-aloud-was-the-half-of-voice-that-was-still-not-local))** — Raiker speaks only with a voice it can see is on this device, and names the language when there is none |
| [BUG-270](FIXED_ITEMS.md#fixed-365--a-fresh-install-named-a-model-nobody-had) | Medium | Models / first-run default | **Closed 2026-09-03 (FIXED-365)** — option **B**, detect before claiming: a PATH lookup cached in a row, never a connection. Option A was declined because it removes the runtime's out-of-box fallback |
| [BUG-268](FIXED_ITEMS.md#fixed-361--the-folder-picker-handed-back-redacted_secret-instead-of-a-path) | High | Web UI / redaction | **Closed 2026-09-03 (FIXED-361)** — found by Linux CI; the picker returned `[REDACTED_SECRET]` for an ordinary folder |
| [BUG-257](FIXED_ITEMS.md#fixed-355--a-rejected-key-was-reported-as-a-network-failure) | Medium | Models / provider errors | **Closed 2026-09-03 (FIXED-355)** — raised while verifying BUG-251 against live providers |
| [BUG-258](FIXED_ITEMS.md#fixed-356--a-picker-offered-and-defaulted-to-a-model-that-cannot-answer) | High | Models / every picker | **Closed 2026-09-03 (FIXED-356)** — the default was `text-embedding-ada-002` |
| [BUG-259](FIXED_ITEMS.md#fixed-357--a-fresh-raiker-adopted-whichever-chatgpt-account-codex-was-signed-in-to) | High | Models / ChatGPT subscription | **Closed 2026-09-03 (FIXED-357)** — a status *read* was performing a connection |
| [BUG-260, BUG-263, BUG-264](FIXED_ITEMS.md#fixed-358--choosing-among-four-hundred-models-was-a-dropdown-with-no-search) | High | Models / web UI | **Closed 2026-09-03 (FIXED-358)** — no dropdown; one picker with a search, on both surfaces |
| [BUG-261, BUG-262](FIXED_ITEMS.md#fixed-359--first-run-could-detect-a-missing-runtime-and-not-offer-to-install-it) | Medium | Models / first run | **Closed 2026-09-03 (FIXED-359)** — install a runtime and choose a model without leaving first run |
| [BUG-265](FIXED_ITEMS.md#fixed-360--a-policy-refusal-was-reported-as-a-wrong-password) | Medium | Authentication / web UI | **Closed 2026-09-03 (FIXED-360)** — "Authentication failed." for a one-owner-per-instance refusal |
| [BUG-295](FIXED_ITEMS.md#fixed-534--a-live-helper-that-found-nothing-let-a-later-assertion-take-the-blame) | Low | Live test harness | **Closed 2026-09-14 (FIXED-534)** |
| [BUG-296](FIXED_ITEMS.md#fixed-527--an-outage-raiker-had-already-reported-also-reported-itself-to-the-console) | Low | Models / Hugging Face | **Closed 2026-09-14 (FIXED-527)** |
| [BUG-297](FIXED_ITEMS.md#fixed-524--three-authority-gates-decided-their-own-capability-by-default-rather-than-by-classification) | Low | Governance / Permissions | **Closed 2026-09-14 (FIXED-524)** |
| [BUG-298](FIXED_ITEMS.md#fixed-543--a-routed-gate-nothing-could-propose) | Low | Governance / policy | **Closed 2026-09-15 (FIXED-543)** |
| [BUG-299](FIXED_ITEMS.md#fixed-535--a-tasks-history-of-attempts-pauses-and-retries-had-nowhere-to-be-read) | Medium | Tasks | **Closed 2026-09-15 (FIXED-535)** |
| [BUG-300](FIXED_ITEMS.md#fixed-551--a-declared-table-was-a-table-in-the-conversation-and-json-everywhere-else) | Low | Chat / typed output / export | **Closed 2026-09-16 (FIXED-551)** — and running it live found [FIXED-550](FIXED_ITEMS.md#fixed-550--a-turn-that-wrote-anything-before-calling-a-tool-stored-a-different-answer-than-it-showed), which is wider than this row |
| [BUG-301](FIXED_ITEMS.md#fixed-557--the-guides-own-cross-references-were-punctuation) | Low | Guide / web UI | **Closed 2026-09-18 (FIXED-557)** |
| [BUG-302](FIXED_ITEMS.md#fixed-558--four-events-describing-themselves-with-one-borrowed-sentence) | Low | Observability / audit summaries | **Closed 2026-09-18 (FIXED-558)** |
| [BUG-303](FIXED_ITEMS.md#fixed-576--the-conversation-library-lived-in-the-evidence-inspector) | Low | Sessions / Threads | **Closed 2026-09-20 ([FIXED-576](FIXED_ITEMS.md#fixed-576--the-conversation-library-lived-in-the-evidence-inspector))** — the work index grew `pinned`, `archived` and tags first, so Archive could move without becoming a control nothing could undo |
| [BUG-304](FIXED_ITEMS.md#fixed-577--delete-was-off-the-bottom-of-the-menu-it-lived-in) | Medium | Sessions / web UI | **Closed 2026-09-20 ([FIXED-577](FIXED_ITEMS.md#fixed-577--delete-was-off-the-bottom-of-the-menu-it-lived-in))** — raised and closed in the same run, found while capturing BUG-303's evidence: the row menu was clipped by the card it opened inside, so Delete could not be clicked |
| [BUG-305](FIXED_ITEMS.md#fixed-592--two-kinds-of-source-and-nowhere-that-answered-what-can-raiker-read) | Low | Memory / Knowledge Map | **Closed 2026-09-20 ([FIXED-592](FIXED_ITEMS.md#fixed-592--two-kinds-of-source-and-nowhere-that-answered-what-can-raiker-read))** — one inventory and one revoke door over both controllers, with the folder that survives its own revocation asserted |
| [BUG-306](FIXED_ITEMS.md#fixed-591--retry-looked-the-same-whether-the-turn-had-sent-an-email-or-nothing) | Low → Medium | Chat / Threads / Sessions | **Closed 2026-09-20 ([FIXED-591](FIXED_ITEMS.md#fixed-591--retry-looked-the-same-whether-the-turn-had-sent-an-email-or-nothing))** — the inventory found a defect rather than only duplication: **Retry** re-ran a turn's effects with no warning |
| [GAP-BUILD](GAP_BUILD_CHAT.md#gap-build--what-build-needs-to-stand-against-a-class-leading-coding-agent) | — | Build — coding-agent parity | Analysis (18 complete, 2 partial; B14 closed 2026-09-04 as [FIXED-375](FIXED_ITEMS.md#fixed-375--a-reviewer-could-narrow-a-change-and-could-not-correct-one), B10 2026-09-03 as FIXED-366, B13 2026-08-30 as FIXED-321, B18 2026-08-29 as FIXED-315, B16 by BUG-206 slice D. B15 and B20 remain partial on [BUG-194](#bug-194--the-governed-shell-has-an-os-boundary-but-no-interactive-background-or-remote-execution)) |
| VIS | — | Visual / information hierarchy | **Complete.** 24 findings; the document was removed 2026-09-15 when its last implementation item closed |
| [GAP-CHAT](GAP_BUILD_CHAT.md#gap-chat--what-chat-needs-to-work-as-a-class-leading---agentic-work-assistant) | — | Chat — work-assistant parity | Analysis (16 complete, 1 partial, 1 open; C15 closed by C1/C4, C11 2026-09-03 as FIXED-367, C18 as FIXED-368, C17 2026-08-29 as FIXED-311. C10 is partial — the notification half ships as [FIXED-374](FIXED_ITEMS.md#fixed-374--a-routine-ran-all-night-and-told-nobody); C12 stays an architecture decision) |

The memory audit of **2026-08-11** has its own document,
[`MEMORY_RELIABILITY_PLAN.md`](MEMORY_RELIABILITY_PLAN.md), written to this
standard. Its MEM-01 and MEM-02 are closed in
[`FIXED_ITEMS.md`](FIXED_ITEMS.md) as FIXED-187 and FIXED-188, and MEM-03 and
MEM-05 as FIXED-230 and FIXED-231, MEM-11, MEM-12 and MEM-13 as FIXED-232,
FIXED-233 and FIXED-234, MEM-14 as FIXED-236, and MEM-04 as FIXED-237. Two were
raised in their place. MEM-10: closing MEM-03 built the *selection* of an
embedding space, and a default install still has nothing semantic to select.
MEM-06, the binding constraint on the graph leg MEM-12 made reachable, closed
2026-08-21 as FIXED-241. MEM-07 closed 2026-08-25 as FIXED-284, and MEM-10's
first leg — the one that made a semantic space *producible* rather than only
selectable — as FIXED-283. **As of 2026-08-29 that document holds no open
entry**: MEM-09 closed as FIXED-310, MEM-10's remainder as FIXED-301, and MEM-08
— the last of them — as FIXED-316. It stays as the record of the audit and of
how each entry closed, not as open work.

The generic static code review of **2026-09-05** has its own pair of documents,
[`GENERIC_STATIC_CODE_REVIEW_2026-09-05.md`](GENERIC_STATIC_CODE_REVIEW_2026-09-05.md)
(GCR-01 … GCR-18) and
[`GENERIC_STATIC_CODE_REVIEW_THIRD_PASS_2026-09-05.md`](GENERIC_STATIC_CODE_REVIEW_THIRD_PASS_2026-09-05.md)
(GCR-19 … GCR-47). Its findings are engineering defects rather than product
defects, so they are not duplicated here; the third-pass document carries its own
remediation order and states what is closed against it. **Ten are closed as of
2026-09-05** — GCR-19 (its one P0) as [FIXED-420](FIXED_ITEMS.md#fixed-420--a-failed-conversions-cleanup-could-delete-every-model-beside-it),
GCR-20/23 as [FIXED-421](FIXED_ITEMS.md#fixed-421--a-cancellation-could-be-overwritten-by-the-worker-it-cancelled),
GCR-21 as [FIXED-422](FIXED_ITEMS.md#fixed-422--retry-checked-the-kind-and-the-payload-and-never-the-state),
GCR-22 as [FIXED-423](FIXED_ITEMS.md#fixed-423--a-multi-gigabyte-download-ran-inside-the-request-that-asked-for-it),
GCR-27 as [FIXED-424](FIXED_ITEMS.md#fixed-424--two-models-one-folder-apart-were-indexed-as-one),
GCR-30 as [FIXED-425](FIXED_ITEMS.md#fixed-425--a-method-whose-contract-was-to-return-health-raised-instead),
GCR-31 as [FIXED-426](FIXED_ITEMS.md#fixed-426--a-thinking-budget-that-left-the-answer-nothing),
and GCR-38/39 as [FIXED-427](FIXED_ITEMS.md#fixed-427--a-background-pass-could-fail-every-fifteen-seconds-in-silence).

**Six more closed 2026-09-06**, taken in the order the third-pass remediation
table gives — its next four entries, plus the two dead parameters that live in
the same two methods: GCR-01/02 as
[FIXED-430](FIXED_ITEMS.md#fixed-430--five-surfaces-asked-would-this-model-run-by-building-one-and-dropping-it),
GCR-03 as [FIXED-431](FIXED_ITEMS.md#fixed-431--a-reasoning-setting-judged-against-whichever-profile-was-first-in-the-file),
GCR-06 as [FIXED-432](FIXED_ITEMS.md#fixed-432--two-commands-running-at-once-could-be-judged-against-each-others-workspace),
GCR-46 as [FIXED-433](FIXED_ITEMS.md#fixed-433--a-database-raiker-could-not-read-was-reported-as-a-model-the-owner-never-chose),
and GCR-04/18 as [FIXED-434](FIXED_ITEMS.md#fixed-434--two-public-parameters-that-changed-nothing).
Running the live evidence for them found one product defect, closed the same day
as [FIXED-435](FIXED_ITEMS.md#fixed-435--the-models-page-said-a-gate-was-on-above-providers-it-would-refuse):
the Models page reported the hosted gate from its capability *row* rather than
from the enforcing path, so it said **Off** above a connected provider it had
just accepted a model for — and **On** above providers it would refuse.

**Six more closed later the same day**, again in the order the third-pass
remediation table gives, plus the startup path issue that sits underneath the
first of them: GCR-45 as
[FIXED-436](FIXED_ITEMS.md#fixed-436--the-registry-raiker-loaded-depended-on-the-folder-it-was-started-from),
GCR-25 as [FIXED-437](FIXED_ITEMS.md#fixed-437--a-download-the-host-restarted-away-from-stayed-running-for-ever),
GCR-28 as [FIXED-438](FIXED_ITEMS.md#fixed-438--two-deploys-at-once-could-take-the-same-slot-and-the-same-port),
GCR-29 as [FIXED-439](FIXED_ITEMS.md#fixed-439--a-runtime-on-a-custom-port-reported-the-slots-declared-one),
GCR-33 as [FIXED-440](FIXED_ITEMS.md#fixed-440--two-expired-calls-presented-the-same-refresh-token-and-one-was-already-retired),
and GCR-40 as [FIXED-441](FIXED_ITEMS.md#fixed-441--an-event-the-index-never-heard-of-was-invisible-to-the-check-for-exactly-that).
Verifying them found a defect in the test suite rather than the product, closed
as [FIXED-442](FIXED_ITEMS.md#fixed-442--seven-tests-asserted-facts-about-the-laptop-running-them):
seven tests asserted what Raiker reports when no local runtime is installed and
obtained that condition by assuming the host had none, so they passed on CI and
failed on any machine with Ollama.

The visual UI/UX review of **2026-09-06** had its own document, and it is
**complete**. All twenty-four findings are accounted for: twenty-two closed on
2026-09-06, VIS-07 was an owner decision rather than a defect — its three
suggestions invent brand behaviours the product does not have, and two overlap
work already done — and VIS-19, the typed output vocabulary, closed on
2026-09-15 as
[FIXED-545](FIXED_ITEMS.md#fixed-545--a-turn-could-only-answer-in-prose).

Two of the twenty-two closed without a code change, and each said so for its own
reason: the Knowledge Map was already 94% of its page with zero cards, and every
infinite animation in the product is a progress indicator already covered by the
global `prefers-reduced-motion` guard.

The document was removed on 2026-09-15 under the governance rule in
[`README.md`](README.md): a topic review goes once every item in it has closed,
and what survives is its `FIXED_ITEMS.md` entries plus git history. The
catalogue of what the visual vocabulary contains is
[`VISUAL_DESIGN_SPEC.md`](../architecture/VISUAL_DESIGN_SPEC.md), which is a
specification rather than a review and stays.

**Both remaining P1 entries closed 2026-09-16:** GCR-24 as
[FIXED-555](FIXED_ITEMS.md#fixed-555--cancel-on-a-conversion-could-go-unanswered-for-six-hours)
— a conversion that could not be cancelled while its subprocess ran, for up to
six hours, and was the largest remaining piece of owner-visible work in that set
— and GCR-26 as
[FIXED-556](FIXED_ITEMS.md#fixed-556--a-source-fingerprint-that-did-not-hash-the-source),
which hashed a file's path and length and called the result a content
fingerprint.

**Nine more closed 2026-09-20**, which is every P2 in that set but two. Taken
by consequence rather than by list order — the two that could change a model's
answer first, then the two that could change a stored or served one, then the
observability and build-integrity work:
GCR-35 as [FIXED-567](FIXED_ITEMS.md#fixed-567--a-follow-up-to-a-long-answer-arrived-with-no-conversation-at-all),
GCR-36 as [FIXED-568](FIXED_ITEMS.md#fixed-568--a-transcript-that-could-not-be-read-looked-exactly-like-one-that-was-empty),
GCR-34 as [FIXED-569](FIXED_ITEMS.md#fixed-569--a-large-json-answer-from-a-connector-became-a-short-string),
GCR-32 as [FIXED-570](FIXED_ITEMS.md#fixed-570--one-endpoints-refusal-rewrote-every-other-endpoints-request),
GCR-37 as [FIXED-571](FIXED_ITEMS.md#fixed-571--a-new-worker-could-adopt-an-exited-workers-database-connection),
GCR-44 as [FIXED-572](FIXED_ITEMS.md#fixed-572--every-pdf-and-every-attachment-was-copied-through-a-json-redactor),
GCR-47 as [FIXED-573](FIXED_ITEMS.md#fixed-573--a-watcher-failing-every-fifteen-seconds-said-every-folder-was-fresh),
GCR-41's build-tool and provenance halves as
[FIXED-574](FIXED_ITEMS.md#fixed-574--two-builds-of-one-commit-could-contain-different-build-tool-bytes),
and GCR-42 as
[FIXED-575](FIXED_ITEMS.md#fixed-575--the-guard-against-contract-drift-was-a-second-hand-written-copy-of-the-contract).
Two of them were reproduced on unmodified `main` before being fixed: GCR-37,
where six sequential worker threads shared one database connection because
CPython gave all six the same identifier, and GCR-42's own gate, checked by
removing a field the browser reads and watching it name the drift.

**Still open in the third-pass document:** GCR-43 (the ~400 KB dashboard
module) and the remainder of GCR-41 — a hash-locked constraints set for the
Python dependencies, which is a per-target lockfile pipeline rather than a
change to the release job. Both are P2.

---

## BUG-194 — The governed shell has an OS boundary, but no interactive, background or remote execution

**Severity: Low (was Medium, was High). Area: shell / sandbox / recovery.
Status: Open — reduced three times.**

**2026-08-28 verification.** Docker is installed but its daemon is unavailable
on this host, and Podman is not installed. Raiker therefore continues to refuse
container-network execution rather than claim unverified direct-DNS/direct-TCP
bypass, active-stream revocation, or copy-on-write credential-delivery proof.
The container proof and a production signing anchor remain open.

**2026-08-21 update.** Foreground SSH and Daytona now enter the same
`CommandService` lifecycle through a canonical length-prefixed envelope, exact
SSH host-key pin, Daytona cost reservation and fixed remote supervisor path;
neither falls back to the host. Container egress has normalized domain/port
policy, public-address pinning, HMAC-scoped grants, revocation state and a real
CONNECT proxy. Credential work has a disposable workspace/Git snapshot,
failure-closed scanner, discard-only quarantine API and review UI. Runner trust
distinguishes publisher-verified, package-relative and developer-unverified
postures, and placeholder supervisor digests were removed.

The item remains open for unproved parts: this host had no Docker/Podman daemon
for live direct-DNS/direct-TCP bypass, active-stream revocation or credential
copy-on-write delivery/merge tests, and no production signing anchor. Windows
PTY and restart reattachment remain explicitly unsupported. Configuration
never turns any of these capabilities on.

**What changed, 2026-08-15.** A governed command now runs inside a real
operating-system boundary, and what that boundary enforces is **measured rather
than declared**. Closed as [FIXED-195](FIXED_ITEMS.md).

**What changed, 2026-08-17.** The two rows this entry called the smallest are
closed as [FIXED-229](FIXED_ITEMS.md), and they were built the way the entry said
they had to be — as components, together, with the enforcer.

The 2026-08-16 review declined to advance them on the grounds that background
execution needs "a supervisor that outlives the turn together with the
agent-facing tool that makes a background run observable; shipping either half
alone is worse than refusing." That reasoning was right and is what this round
followed. Both halves shipped in one change:

* **The enforcer.** Every background run holds a lease. A thread renews it only
  while the process it is watching is alive and this runtime is up, so a lease
  that keeps moving forward *is* the evidence of a live run and a lease that
  stops is evidence of the opposite — including on a hard kill, where no handler
  of ours runs at all. `reconcile_leases` terminates and finalises any run whose
  lease lapsed, with a receipt naming `command_background_lease_expired`. A
  foreground run holds no lease and is never swept, so a missing lease is never
  read as an expired one. A background run is also bounded by a hard two-hour
  ceiling, because a run with no deadline is a run whose lease renews forever and
  the reclaim path would never fire.
* **The observing half.** `background_run` — `list`, `poll`, `log`, `wait`,
  `kill`, `input` — owner-scoped on every action, reading the durable run row and
  the already-redacted output chunks. It starts nothing and grants nothing: a run
  it can see is one the session's command grant already authorised.

**The tool is not called `process`, and that matters.** The original entry named
it `process`. That name already routes to the `process_execution` capability —
arbitrary host process control, which the runtime classifies as critical and the
policy holds for approval. Registering an observation tool under it would have
attached a read verdict to host process control. The collision surfaced as a
hard `policy actions cannot have conflicting verdicts: process` failure rather
than a silent widening, which is the invariant working.

**PTY and raw input are closed on POSIX and stay open on Windows.** `openpty`
gives the child a controlling terminal and `background_run action=input` types
into it; the proof is that the *program* read the bytes, not that the terminal
echoed them. Windows is unchanged and the reason is unchanged: `CreatePseudoConsole`
builds its console objects in the caller's context, unreachable from an
AppContainer token, and `PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE` is documented as
incompatible with the handle-list attribute the boundary requires.
`pty_supported()` reports the platform's real answer, and input to a run without
a terminal is refused as `command_input_requires_pty` rather than written to a
pipe where the bytes would arrive and the effect would not.

**What changed, 2026-08-17 (second pass).** The two rows this entry had left as
the largest components are closed as [FIXED-238](FIXED_ITEMS.md) and
[FIXED-239](FIXED_ITEMS.md), and they were built the way the entry said they had
to be — together, because each alone is worse than neither.

* **Restart reattachment.** A background run is started inside a detached
  supervisor that is a module of the Raiker package, so it is packaged by
  construction. It holds the child in its own session, the deadline that bounds
  it, the redactor, and an append-only journal, and it is reached over an
  `AF_UNIX` socket speaking the authenticated frames the protocol codec already
  had cross-language vectors for. The socket path and the instance key live
  encrypted in `command_runs.encrypted_backend_handle`, so **reattachment is an
  authentication rather than a pid lookup** — which is precisely the objection
  this entry raised against building it on a pid file. Every case the runtime
  cannot prove — no handle, a locked vault, a socket that is gone, a socket that
  fails the key — still produces the honest `lost` receipt.
* **Persistent environment.** The container's name is a function of owner,
  session and profile rather than of the run, so a session's second command
  lands in the boundary its first one left behind. Persistence shipped with its
  reset, because an environment that accumulates state and can never be cleared
  is worse than one that never persists.

**Still observed.** Select `native_sandbox` and request network, credential, SSH
or Daytona execution and the backend fails closed with the corresponding named
reason; the native sandbox additionally still refuses background, PTY and
persistence, because its capability set comes from the host probe and none has
been measured inside an AppContainer — and per-run AppContainer profiles stay
deliberate, since the container SID is a pure function of the name. On
**Windows**, restart reattachment is refused by name
(`command_supervisor_platform_unsupported`) and a background run is still
reconciled to `lost` across a restart.

**Root cause, per item.** Each of these is a component rather than a flag, which
is why none of them was half-built:

| Remaining item | Why it is not built |
|---|---|
| ~~**Background start/poll/wait/log/kill**~~ | **Closed 2026-08-17** as [FIXED-229](FIXED_ITEMS.md#fixed-229--a-governed-command-could-not-outlive-its-turn-and-nothing-could-be-typed-into-one) on the `local_native` backend, with the lease, the reclaim path and the `background_run` tool shipped together. Not claimed for `native_sandbox`, whose capabilities come from the host probe. |
| ~~**PTY and raw input**~~ | **Closed on POSIX 2026-08-17** as [FIXED-229](FIXED_ITEMS.md#fixed-229--a-governed-command-could-not-outlive-its-turn-and-nothing-could-be-typed-into-one). Windows unchanged: `CreatePseudoConsole` builds its console objects in the caller's context; they are not reachable from an AppContainer token without an explicit capability, and `PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE` is documented as incompatible with the handle-list attribute the boundary requires. A PTY that only works outside the sandbox is not the control the row describes. |
| ~~**Restart reattachment**~~ | **Closed on POSIX 2026-08-17** as [FIXED-238](FIXED_ITEMS.md#fixed-238--a-background-run-could-not-survive-the-restart-of-the-runtime-that-started-it), with the detached supervisor, the authenticated `AF_UNIX` control channel and the encrypted restart-safe handle shipped together. Windows unchanged and refused by name: a named pipe is reachable by name from any session on the machine, so the equivalent needs its own design and its own proof rather than the same code with a different transport. |
| ~~**Persistent environment**~~ | **Closed for the container backend 2026-08-17** as [FIXED-239](FIXED_ITEMS.md#fixed-239--the-command-container-was-rebuilt-around-every-command-so-nothing-could-persist), together with the owner's reset and reset-and-clear-cache controls. Per-run AppContainer profiles are still created and deleted around each command, deliberately: a predictable container name is a hole, because the container SID is a pure function of the name. |
| **Filtered domain egress** | The AppContainer loopback exemption needs elevation, and a Linux proxy-only namespace is a separate netns build. Refused with a named reason on every backend rather than partially claimed. |
| **Credential delivery and delta quarantine; SSH; Daytona** | Unchanged. None is a Codex or Claude Code control; all three remain storage contracts and selectable-but-refused profiles. |
| ~~**Container session supervisor**~~ | **Closed 2026-08-17** as part of [FIXED-239](FIXED_ITEMS.md#fixed-239--the-command-container-was-rebuilt-around-every-command-so-nothing-could-persist): the session's container is created once and reused, liveness is asked of the runtime rather than assumed, and the backend is held for the life of the service so there is somewhere to remember it. |
| **Signature verification of the runner** | The runner's SHA-256 is recorded at build time, checked before use, and carried into the receipt. That detects corruption and casual replacement; it is **not** protection against an attacker with write access to the install directory, who could replace Raiker itself. Authenticode chain verification is not implemented. |

**Required fix.** For each remaining row: Windows PTY and Windows restart
reattachment once the ConPTY/AppContainer and named-pipe-authorisation questions
are settled by a spike; an authenticated domain proxy with DNS/address checking
and active revocation; purpose-bound credential delivery plus two-pass delta
quarantine; and SSH/Daytona supervisor adapters. Prove every backend
independently and preserve the no-fallback and honest-`lost` rules.

**Required user-interface outcome.** Further met. Runtime shows the exact probed
boundary and its six measured observations, and Build shows the boundary a
command ran in plus failure navigation. Background and PTY are agent-facing
controls rather than interface ones — an agent starts and observes a background
run through `run_command`/`background_run`, and the run appears in the same
owner-visible command list, with the same receipt, as a foreground one. Each
environment card now lists the capabilities that boundary really has, built from
the backend's own `CommandFeatures` rather than from configuration, and carries
the **Reset environment** and **Reset and clear cache** controls where — and
only where — the boundary persists. **Filtered network remains absent** rather
than disabled: an absent control is the honest projection of an unbuilt
capability, where a disabled one implies it is a setting away. No row may turn
green from configuration or specification alone.

## Verified working (no action needed)

Recorded so the fixes above are read against the right baseline. Re-verified end
to end on **2026-08-08** against hosted Anthropic (see
[the live manual test plan](RAIKER_LIVE_MANUAL_TEST_PLAN.md) for the full round):

first-run bootstrap and owner sign-in; **all 14 routes and 22 hub tabs with 0
console errors**; connecting a hosted provider from the web app and pinning a
model from the live catalogue; **all ten Anthropic models answering a live turn**;
a real streamed turn with sanitised Markdown (headings, lists, GFM tables,
fenced code); conversation memory within a chat and isolation between chats;
per-chat and provider all-time cost; recent-chat list; chat search over titles
and message text; the four task types (immediate, scheduled, daily routine,
background agent) with parent nesting, priority, counters and stop; the approval
lifecycle end to end — proposal, unified diff, **Approve and execute once**, the
file on disk, and the resumed turn; the file inspector for a generated Markdown
file and for a generated PDF; **Export conversation… in HTML, Markdown and PDF**
plus **Print / Save as PDF**; markdown → PDF through `create_document`; document
and image attachments reaching the model with source citations; MCP server
create / connect / discover / **call from Chat** under the owner's decision mode,
with the result marked untrusted; Build repository connect, code-map build and
`code_map_search`; `update_plan` checklists and `spawn_subagent`; capability
step-up (reason required, Confirm disabled until supplied); the deferred domains
CCTV, finance, medical and home security offering no row at all; Observability's
seven tabs on real data; Settings' sections; theme cycling system → light → dark;
the notification centre and Mark all read; the STOP switch; and adaptive
navigation at 375 / 768 / 1024 / 1440 px with no horizontal overflow, correct
`aria-expanded`, and focus returned to the trigger.

---

## BUG-239 — An empty gate table means three different things

**Closed 2026-09-15 as
[FIXED-544](FIXED_ITEMS.md#fixed-544--a-new-account-was-fail-closed-about-reading-its-owners-own-repository).**

The owner's decision was that the three resolutions stay — each is individually
justified, and collapsing either way changes behaviour without looking at what
each capability is for. What was worth acting on was the *other* question the
entry raised: a brand-new account could not read symbols out of a file the agent
was already authorised to open.

So fresh-account defaults expanded **selectively and explicitly**, through a
versioned baseline written at account creation rather than through a change to
what a missing row means: `language_intelligence` and `code_map_indexing` first,
then `task_management_runtime`, `project_assignment_runtime` and `audit_export`.
It runs at account creation only, never replaces a row an owner wrote, writes
gates and nothing else so every one of them still asks, and cannot admit anything
classified external, destructive or critical. Build is a preset rather than a
default, because writing to somebody's files is a decision. The full record,
including the Permissions copy that had to change with it, is in the closure
entry.

---

## BUG-220 — Nothing owns a set of delegated child tasks

**Severity: Medium. Area: tasks / delegation. Status: closed 2026-08-25 as
[FIXED-286](FIXED_ITEMS.md#fixed-286--a-task-reported-done-while-the-work-it-delegated-was-still-open),
raised 2026-08-21 while reviewing Cowork Dispatch.**

**What closed.** The ownership: a parent no longer reports `completed` over an
open child. It parks as `waiting_for_children` and settles when the last child
lands — completed if all completed, failed if any did not — and a child still
carries its own approvals, which was the first of the three requirements below.

**What is left, and where it lives now.** The other two — a visible,
re-decidable Chat-or-Build routing decision per child, and one conversation that
briefs the split — are the *composition* half of Dispatch rather than the
ownership half, and they are tracked as
[backlog #23](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#medium-priority-high-effort).
The original entry is kept below because its governance requirements still bind
that work.

**Observed.** Raiker has every component of
[Cowork's Dispatch](https://claude.com/docs/cowork/guide/dispatch): read-only
subagents (`spawn_subagent`), background agents, nested tasks with a parent id,
per-task sessions, and a live work board in Observability. What is missing is the
one conversation that briefs the work, decides how to split it, and owns the
children — and the routing decision that sends each child to Chat or to Build.

Today the owner does the splitting by hand, one task form at a time, and nothing
connects the resulting runs to the intent that produced them.

**Root cause.** `parent_task_id` records structure but no surface composes it. No
route lists a task's children as a group, and no turn can create more than one
task at a time.

**Proposed fix, with the governance requirements that are not optional.**

- The routing decision (Chat or Build, and which project or repository) must be
  **visible and re-decidable** before the child starts, not inferred silently.
- Each child must carry **its own approvals**. A child inheriting the parent
  conversation's approvals would turn one decision into an unbounded number, which
  is the exact failure the per-turn capability envelope exists to prevent.
- A forwarded approval must not expire silently. Cowork auto-denies an unanswered
  prompt after ten minutes; if Raiker adopts that, the expiry has to be a
  **recorded decision with its reason**, not a dropped request.

---

## BUG-225 — A channel can be described and never reached

**Closed 2026-08-27 as
[FIXED-298](FIXED_ITEMS.md#fixed-298--a-paired-channel-could-still-only-record-a-message).**
The full observation, authority contract, anti-phishing controls, UI outcome,
and evidence moved to the closed-work ledger.

---

## BUG-226 — Three of the five hook handler types do not exist

**Severity: Low. Area: hooks / handlers. Status: Open remainder — reduced
2026-08-28 (FIXED-303).**

**Observed.** The hooks reference Raiker maps itself against documents five
handler types: `command`, `http`, `mcp_tool`, `prompt` and `agent`. Before
FIXED-303, `HANDLER_TYPES` accepted only `command` and Raiker's own `builtin`.
It now also accepts a bounded `prompt` and, since
[FIXED-380](FIXED_ITEMS.md#fixed-380--three-of-the-five-hook-handler-types-did-not-exist-now-two),
an `http` handler behind a named, revocable egress grant. A rule naming
`mcp_tool` or `agent` is still refused at parse time, which is the right failure
until each has a governed resource path.

The title has undercounted twice and is kept as raised. After FIXED-303 three
remained; after FIXED-380, **two** — `mcp_tool` and `agent`.

**Corrected 2026-08-22.** This entry used to say `command` is the only handler
type Claude Code's own hooks have, and that the gap was therefore against
Raiker's own reference document rather than against Claude Code. That was wrong:
[the Claude Code hooks reference](https://code.claude.com/docs/en/hooks)
documents and specifies all five — `command`, `http`, `mcp_tool`, `prompt` and
`agent` — with per-type fields. **This is a real gap against Claude Code.** It
stays Low because each missing type needs a resource the hook path deliberately
does not have (below), not because the reference lacks them.

This is the remainder of the hooks gap after BUG-223 — and the *events* are not
at parity either: Raiker emits seventeen of the thirty-one Claude Code documents.
See
[`../REFERENCE_PLATFORM_COMPATIBILITY.md`](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#25-extensibility--hooks).

**Root cause.** Each originally missing type needs a resource the hook path deliberately
does not have:

* `http` needs egress. A hook has no implicit network access by design, and
  giving one an outbound request is a capability decision, not a handler type.
* `mcp_tool` needs the MCP broker inside the hook path, which would let a hook
  reach a tool the turn's own policy might have refused — the exact inversion the
  hook model forbids.
* `agent` needs a multi-turn model loop and tools, which means its own budget,
  capability set and answer to inherited authority. The single-turn `prompt`
  case no longer shares that blocker.

**Completed first slice.** FIXED-303 adds `prompt` with a per-handler token
budget and timeout, the owner-selected governed provider, no tools, no nesting,
redacted bounded event data and advisory-only output.

**Completed second slice (2026-09-04).**
[FIXED-380](FIXED_ITEMS.md#fixed-380--three-of-the-five-hook-handler-types-did-not-exist-now-two)
adds `http` behind exactly the grant this entry named:
`RAIKER_HOOK_EGRESS_ALLOWLIST`, empty by default, revoking every `http` rule at
once when cleared, read live by the Hooks page, and refusing with the host in the
reason. It sends the same bounded, redacted event body the `prompt` handler
already sends, from the same function; a remote responder can deny or ask and can
never permit, and a non-2xx is not a deny.

`mcp_tool` and `agent` stay refused until there is a stated answer to a hook
reaching authority the turn did not have.

**Not a regression, and visible today.** A rule naming an unsupported type is
refused at parse time rather than accepted and ignored, and the Hooks tab reports
the file as failed with the reason — so an owner writing one is told, rather than
believing a guard is in place.

---


---

## BUG-228 — A plugin panel has no route, permission or accessibility contract

**Severity: Low. Area: plugins / web UI. Status: Open — raised 2026-08-22, split
out of BUG-221 as the last remaining contribution kind.**

**Observed.** Extensions → Plugins lists four contribution kinds. Three are now
available (hooks, skills, MCP-server offers). **Panels** is the fourth and reads
"Not yet — needs a route, permission and accessibility contract that does not
exist", which is accurate and has been the stated blocker since BUG-221 was
raised. Splitting it out means BUG-221 can close when the reasoning it carries is
no longer needed, and this can be worked on its own terms.

**Root cause.** Unlike the other three, there is no existing surface that already
governs "a page a plugin drew". A hook had an execution model; a skill had a
validator; an MCP server had a create path. A panel needs all of the following to
be decided before any code:

* **A route.** Where a plugin's page lives in the hash router, how it is
  addressed, and what stops two plugins claiming one path.
* **A rendering boundary.** Raiker renders no third-party code in the browser
  today, and "no plugin code runs in this browser" is a claim the Plugins tab
  makes in those words. A panel either breaks that claim or is declarative —
  a described layout Raiker renders — and that choice decides everything else.
* **A permission model.** What data a panel may read, and how it asks; a panel
  that can read the session list is a very different object from one that cannot.
* **An accessibility contract.** Every other surface meets the same keyboard,
  contrast and landmark bar. A plugin-supplied page cannot be exempt from it, so
  it has to be *checkable*, which is easiest if it is declarative.

**Proposed fix.** Take the declarative route: a panel is a described layout from
a fixed component vocabulary, rendered by Raiker, reading only data the plugin's
own contributions produced. That keeps "no plugin code runs in this browser"
literally true, makes the accessibility contract enforceable at render time
rather than by review, and matches the pattern the other three kinds established.

**Not blocking anything.** No other work depends on this, and the surface already
states it is unavailable rather than offering a control that does nothing.

---

## BUG-229 — Most live specs sign in only on an empty workspace

**Closed 2026-08-30 as
[FIXED-324](FIXED_ITEMS.md#fixed-324--thirty-seven-live-specs-each-carried-their-own-sign-in).**
Every live spec that had a sign-in *function* delegates to
`signInAsOwner`, and two robustness steps only one spec carried — waiting for the
username field to become enabled, and accepting the navigation rail as proof of a
session — are now the helper's, so all of them get them.

The record stays here rather than moving, because what is left is a *different*
defect and reads best against the one it came out of: each spec still hardcodes
its own owner password, so two specs cannot share one workspace. That is
[BUG-247](#bug-247--every-live-spec-brings-its-own-owner-password).

---

## BUG-234 — The remainder: what Raiker does not use of the MCP revision it now speaks

**Severity: Low (was Medium). Area: MCP / interoperability.
Status: Open — reduced 2026-08-23, twice on 2026-09-04 (transport, result
shapes), and twice again on 2026-09-05 (server-initiated requests, event-stream
framing).**

**Reduced again 2026-09-05, and the first of the two was a defect rather than a
gap.** Reading this entry's *streaming* bullet led to the code that reads a
stream, and two things there were wrong rather than merely unbuilt:

* **[FIXED-411](FIXED_ITEMS.md#fixed-411--a-server-initiated-request-was-filed-as-the-answer-to-raikers-own)
  — a server that asked Raiker anything could not be connected at all.** Both
  transports filed every message carrying an `id` into the response map, and a
  server-initiated request carries an id from the *server's* numbering space.
  One numbered 1 — the ordinary choice — landed on top of the `initialize`
  answer, and the connection failed as `mcp_initialize_failed`: Raiker's own
  request named, and the server blamed for not answering it. Reproduced on
  unmodified `main`. Direction is read from `method` now, `ping` is answered,
  and everything else is refused with `-32601` and **named on the card** rather
  than met with silence.
* **[FIXED-412](FIXED_ITEMS.md#fixed-412--an-event-stream-was-read-one-line-at-a-time-and-the-rest-was-dropped)
  — an event stream was read one line at a time.** One event's payload may span
  several `data:` lines, which is what a server that pretty-prints its JSON-RPC
  produces; each line was parsed alone, failed, and was dropped. `id:` was
  dropped too, so the single re-handshake after a dropped session restarted from
  nothing. There is a real event-stream parser now, and `Last-Event-ID` on the
  one request that resumes.

Neither closes the *streaming* bullet below, and neither pretends to: Raiker
still reads a bounded response whole and holds no connection between turns, and
the card still says so.

**What changed.** Raiker negotiated revision `2024-11-05` for five revisions,
which meant a server implementing only the current one could not be connected at
all. It now offers
[`2026-07-28`](https://modelcontextprotocol.io/specification/versioning), accepts
`2025-06-18`, `2025-03-26` and `2024-11-05` when a server answers with one, and
refuses a revision it does not implement rather than continuing on a framing it
cannot trust. **Extensions → MCP** states the revision each server negotiated.
Closed as [FIXED-274](FIXED_ITEMS.md).

**Reduced again 2026-09-04**
([FIXED-378](FIXED_ITEMS.md#fixed-378--raiker-spoke-the-current-mcp-revision-and-did-not-use-its-transport)).
The transport now conforms where a real server would have refused it: `Accept`
carries both framings (a conformant server may answer 406 to a POST offering only
JSON), a session is released with `DELETE`, a dropped session re-handshakes once,
and a `401` with `WWW-Authenticate` is named as the OAuth requirement it is
rather than as a network failure. **The interface outcome below is met**: what a
connected server offers and Raiker does not use is named on its card.

**What is left.** Negotiating a revision is not implementing it. Each of the
following was previously *blocked* by the version pin and is now ordinary work:

* **Streamable HTTP streaming.** Raiker's `http` transport is its own bounded
  JSON-RPC client. It reads an `text/event-stream` answer whole rather than
  streaming it, and holds no open connection between turns: no incremental
  delivery. A server that answers this way is **named as such on its card**
  rather than silently degraded. **Two of the four things this bullet listed are
  now done** — the framing is read correctly and resumably
  ([FIXED-412](FIXED_ITEMS.md#fixed-412--an-event-stream-was-read-one-line-at-a-time-and-the-rest-was-dropped))
  and server-initiated messages are answered rather than mis-filed
  ([FIXED-411](FIXED_ITEMS.md#fixed-411--a-server-initiated-request-was-filed-as-the-answer-to-raikers-own)).
  Incremental delivery and a connection that outlives the turn are what is left,
  and both are a different object from a bounded governed read: a stream held
  open between turns is a standing inbound channel, and it needs its own answer
  to what may arrive on it while nobody is looking.
* **Remote OAuth.** The authorisation flow the current revision defines. Raiker's
  remote transport takes an owner token from an env var named by `auth_ref`.
* **MCP Apps ([SEP-1865](https://modelcontextprotocol.io/seps/1865-mcp-apps-interactive-user-interfaces-for-mcp)).**
  Sandboxed server-contributed UI, and the better answer to
  [BUG-228](#bug-228--a-plugin-panel-has-no-route-permission-or-accessibility-contract).
  Carried as [ADD-24](TO_BE_ADDED.md).
* ~~**Structured tool output and resource links.**~~ **Done 2026-09-04 —
  [FIXED-387](FIXED_ITEMS.md#fixed-387--a-tool-result-had-one-shape-and-the-revision-defines-six).**
  Raiker read one of the six shapes a result may carry: the `text` of every
  block. All five block types and `structuredContent` now reach the model, with
  two rules that are governance rather than formatting — a `resource_link` is
  *named and never followed*, because a tool result must not cause a read the
  owner's policy never saw; and an inline image is named by media type and size
  rather than decoded into the turn.
* **Elicitation.** Its blocker is gone — the mid-turn question surface shipped as
  [FIXED-308](FIXED_ITEMS.md#fixed-308--raiker-could-ask-permission-and-could-not-ask-what-you-meant)
  — and it is still not built. What it needs is an answer to *whose* question a
  server's elicitation is: `ask_owner_question` carries no authority because
  Raiker's own runtime raised it, and a question a connected server composes is a
  different object. **The wire half is now in place and deliberately stops
  short**: since
  [FIXED-411](FIXED_ITEMS.md#fixed-411--a-server-initiated-request-was-filed-as-the-answer-to-raikers-own)
  an `elicitation/create` reaches Raiker as the request it is, is answered
  `-32601`, and is named on the server's card — so an owner can see a server
  asking and see that it was refused. Wiring it to a person is the part that
  still needs the answer above, and `sampling/createMessage` needs the same one
  about a turn the owner's policy never reviewed.
* **`server/discover`.** Not implemented, and not urgent: every server an owner
  can add today is added by the owner naming it.

**Why Low.** Nothing is broken and nothing is unreachable: every server Raiker
could talk to before, it can still talk to, and a current-revision server now
connects. What remains is capability Raiker has chosen not to build yet, stated
rather than implied.

**Interface outcome that has to be true before this closes.** A connected server
that offers a `ui://` resource, an SSE stream, or an OAuth authorisation
requirement is either supported or **named on its card as unsupported** — never
silently degraded. **Met 2026-09-04 (FIXED-378):** the server's own `initialize`
capabilities and what its transport was observed doing are stored as feature
names and rendered as one sentence each, and a capability Raiker has never heard
of is still named by its own key rather than dropped for not being on a list.

---

## BUG-240, BUG-241, BUG-242 and BUG-243 — closed

Their full records — what was observed, the root cause, and the interface
outcome that had to be true before each could be called closed — are in
[`FIXED_ITEMS.md`](FIXED_ITEMS.md):

* **BUG-240** — a semantic space could be built and the question was never
  embedded into it. Closed 2026-08-26 as
  [FIXED-292](FIXED_ITEMS.md#fixed-292--semantic-memory-built-a-space-the-question-never-entered)
  (approved memory) and
  [FIXED-294](FIXED_ITEMS.md#fixed-294--managed-documents-could-only-be-recalled-with-shared-words)
  (managed knowledge files). The index row above was still marked open after the
  second half landed; that was a stale row, not remaining work.
* **BUG-241** — `fullPage` evidence captures stopped at the first viewport.
  Closed 2026-08-29 as
  [FIXED-313](FIXED_ITEMS.md#fixed-313--fullpage-evidence-captures-stopped-at-the-first-viewport).
* **BUG-242** — Build opened an empty conversation after a reload. Closed
  2026-08-29 as
  [FIXED-309](FIXED_ITEMS.md#fixed-309--build-opened-an-empty-conversation-after-a-reload).
* **BUG-243** — a question could not recall the memory that answered it. Raised
  and closed 2026-08-29 as
  [FIXED-314](FIXED_ITEMS.md#fixed-314--a-question-could-not-recall-the-memory-that-answered-it),
  found while verifying FIXED-311 against a live turn.

---

## BUG-245 — A cited conversation names its exchanges and cannot open one

**Closed 2026-08-30 as
[FIXED-323](FIXED_ITEMS.md#fixed-323--a-cited-past-conversation-named-its-exchanges-and-could-not-open-one).**
One nullable `anchors_json` column on `turn_sources`, built from the tool result
the runtime read and never from anything the model wrote, and a link per exchange
in both source panels. The ledger's rule survives: one source per executed call,
with the anchors as that source's own contents rather than as ten sources.

---

## BUG-247 — Every live spec brings its own owner password

**Closed 2026-08-30 as
[FIXED-328](FIXED_ITEMS.md#fixed-328--one-owner-for-the-whole-live-suite).**
`OWNER_CREDENTIALS` is the only owner credential in the live suite. Thirty specs
stopped passing an explicit credential to `signInAsOwner`; the twenty-two that
still sign in inline point their own constants at it, so *who* a spec signs in as
and *how* it signs in stayed separate changes. The three specs that are about
signing in keep their own.

Closing it found the thing that had actually been stopping a whole round from
running against one workspace:
[FIXED-327](FIXED_ITEMS.md#fixed-327--the-setup-wizard-trapped-every-live-spec-after-the-first-one),
a shared helper that knew one of the setup wizard's five stages.

---

## BUG-248 — Twenty-seven live specs still sign in inside a test body

**Severity: Low. Area: live test harness. Status: Open remainder — raised
2026-08-30 while closing [BUG-229](FIXED_ITEMS.md#fixed-324--thirty-seven-live-specs-each-carried-their-own-sign-in),
reduced from twenty-seven to twenty the same day
([FIXED-328](FIXED_ITEMS.md#fixed-328--one-owner-for-the-whole-live-suite)), and
to **twelve** on 2026-09-04.**

**2026-09-04 — eight more, each re-run against a *used* workspace.**
`guide-surface`, `review-chat-surface`, `containment-surface`, `visual-refresh`,
`knowledge-map-work`, `reference-graph`, `bug-69-local-model-library` and
`bug-69-huggingface`. Re-running each against a workspace that already had an
owner, a scan and a connection is what made the conversions evidence rather than
substitutions: three of the eight failed *after* the sign-in, for reasons that
were nothing to do with it, and each of those is a defect this round fixed rather
than an assertion it relaxed —

* `containment-surface` documented its seeding as a shell block for a person to
  run by hand, so a round that did not run it met a red assertion about a list
  that was empty *because the product was behaving correctly*. It now performs
  its own precondition and skips with the reason when it cannot.
* `bug-69-local-model-library` asserted `getByText("Raiker Live GGUF")` against
  the whole page. Its own scan puts that name into every model picker on the
  screen, so the assertion passed exactly once — on a workspace where nothing had
  been scanned before — and then failed as a strict-mode violation naming four
  elements. Scoped to the inventory the test is about.
* `bug-69-huggingface` answered "no network to huggingface.co" with a
  three-minute timeout on a click, and blamed the click. It now states the
  precondition after the sign-in and the search have both actually happened, so
  what it still verifies on such a host is real.

**One conversion was reverted rather than committed unverified.**
`c17-b14-recall-and-inline-diff-live` needs a provider that answers, and this
round's key does not ([BUG-273](#bug-273--three-live-scenarios-of-the-2026-09-03-round-are-written-and-unrun)).
The rule this entry states — *a blind bulk edit would replace verified sign-ins
with unverified ones* — applies to a careful edit that cannot be re-run just as
much as to a blind one.

**Observed.** Thirty-seven live specs delegate to `signInAsOwner`. Twenty-seven
others sign in *inline* in a test body, and those copies are the ones BUG-229
described: several still key on the empty-workspace greeting.

**Seven are done, each re-run as it was converted** — `all-pages`,
`all-pages-theme`, `observability`, `default-ollama`, `memory-knowledge-context`,
`memory-semantic` and `memory-vector-index`. That found three pieces of drift
nothing else would have, including a spec still driving a Vite dev server on port
5174; they are recorded in FIXED-328. **Twelve are left** after the 2026-09-04 pass, and the reason they
are left is unchanged.

**Why they were left.** They vary in a way the function-shaped ones did not —
different bases, different landing routes, some navigating to the route under
test *before* signing in. And `page.goto` with only the hash changed does not
re-render this app (recorded in `real-work-chat-build-live.spec.ts`), so
replacing "go to Models, sign in there" with "sign in on the workbench, then go
to Models" is a behaviour change per spec rather than a substitution. A blind
bulk edit would replace twenty-seven verified sign-ins with unverified ones.

**Three of them must keep their own.** `review-first-run-honesty-live`,
`wizard-workbench-composer-live` and `workbench-live` sign in *as the thing under
test*; sharing the helper there would hide the behaviour they exist to check.

**Proposed fix.** One spec at a time, each re-run as it is converted — which is
how the evidence behind its FIXED entry is refreshed rather than invalidated.

**Required user-interface outcome.** None; this is harness-only.

---

## BUG-249 — A FIXED_ITEMS link points at a heading that does not exist

**Closed 2026-08-30 as
[FIXED-326](FIXED_ITEMS.md#fixed-326--a-fixed_items-link-pointed-at-a-heading-that-does-not-exist).**
One line, and `test_docs_consistency` is green. The guard did its job: an anchor
written from memory is exactly the drift it exists to catch.

---

## BUG-250 — A shared live workspace carries state between specs

**Closed 2026-09-15 as
[FIXED-549](FIXED_ITEMS.md#fixed-549--a-spec-that-had-to-disambiguate-its-own-subject).**

Both halves of the original proposal shipped on 2026-09-04 —
`requireFirstRunWorkspace` for the specs that genuinely need their own instance,
and re-runnable assertions for the rest. The third half was naming: a spec that
creates **Overnight research** and asserts on **Overnight research** is asserting
on its own leftovers too. `web/e2e/naming.ts` gives the round one rule and the
seven specs that create a named record now use it.

---

## BUG-251 — Every path an owner types is a path they have to know

**Closed 2026-09-03 as
[FIXED-352](FIXED_ITEMS.md#fixed-352--every-path-an-owner-typed-was-a-path-they-had-to-know).**
A host-side `GET /api/host/paths` lists directory names, and one `PathPicker`
dialog serves all four fields. The record — including why a browser cannot
answer this on its own — is in `FIXED_ITEMS.md`.

---

## BUG-252 — Attaching by drag and drop works in one place only

**Closed 2026-09-03 as
[FIXED-350](FIXED_ITEMS.md#fixed-350--dropping-a-file-worked-in-one-place-and-was-ignored-in-four).**
One drop target, used by every surface that already accepted an upload.

---

## BUG-253 — Reloading the page signs the owner out

**Closed 2026-09-03 as
[FIXED-353](FIXED_ITEMS.md#fixed-353--reloading-the-page-signed-the-owner-out).**
An `HttpOnly`, `SameSite=Strict` session cookie, paired with a double-submit
CSRF token and an origin check on every state-changing request. The bearer
header path is unchanged and exempt.

---

## BUG-254 — A subscription's own usage and limits are not shown

**Closed 2026-09-03 as
[FIXED-354](FIXED_ITEMS.md#fixed-354--a-subscriptions-own-usage-and-limits-were-not-shown).**
Raiker records the limit windows a provider volunteers as part of a turn, and
shows nothing at all for a provider that volunteers none.

---

## BUG-255 — Nothing announces an approval outside the browser

**Closed 2026-09-03 as
[FIXED-351](FIXED_ITEMS.md#fixed-351--a-decision-raised-while-raiker-was-in-the-background-reached-nobody).**
The already-permissioned browser notification, raised only while Raiker is not
the window the owner is looking at.

---

## BUG-256 — Dictation sends audio to the browser's speech service

**Closed 2026-09-03 as
[FIXED-363](FIXED_ITEMS.md#fixed-363--dictation-was-the-last-surface-that-was-not-local).**
A local speech-to-text runtime, configured beside the other local runtimes and
used automatically when it is there. Fixing it also uncovered that
`Permissions-Policy: microphone=()` had been denying the microphone to Raiker's
own page, so the control could never have worked in a served build.

---

## BUG-266 — A live workspace directory cannot be deleted while the host holds it

**Closed 2026-09-03 as
[FIXED-364](FIXED_ITEMS.md#fixed-364--a-live-round-could-start-on-the-previous-rounds-data).**
`scripts/reset_live_workspace.py` waits for the process to exit, retries the
removal, reads the directory back, and refuses the round if any of the three
fails.

---

## BUG-267 — The boot session probe logs a 401 to the console on every locked load

**Closed 2026-09-03 as
[FIXED-362](FIXED_ITEMS.md#fixed-362--an-expected-answer-was-written-to-the-console-as-a-failure).**
`GET /api/auth/session-state` answers the page's boot question with `200` both
ways, and clears the stale cookie so the next load does not ask at all.

---

## BUG-269 — Read aloud is the half of voice that is still not local

**Severity: Low. Area: voice / privacy posture. Status: Closed 2026-09-04 as
[FIXED-373](FIXED_ITEMS.md#fixed-373--read-aloud-was-the-half-of-voice-that-was-still-not-local).
The filter turned out to be enough; no local synthesis runtime was needed.**

**Observed.** Dictation can now be made to run entirely on this machine.
**Read aloud** cannot: it calls the browser's `speechSynthesis`, and nothing in
the product lets an owner keep it on the device the way a transcription runtime
now does for the microphone.

**Why it is lower than BUG-256 was.** What crosses the boundary is the
*response text*, not a recording of the owner, and on most platforms the browser
speaks with an OS voice that never leaves the device at all. But "most" is doing
work in that sentence: Chrome ships remote voices for several languages and
picks one without saying so, and Raiker cannot tell which kind it got. The
asymmetry is also its own defect — an owner who has just set on-device
transcription up has no reason to expect the other direction to behave
differently, and nothing tells them it does.

**Proposed fix.** The same shape as BUG-256, one size smaller. `speechSynthesis`
exposes `voice.localService`; a *Use only on-device voices* choice in
Raiker could prefer those and say plainly when a language has none, rather than
silently using a remote one — with no setting, exactly as dictation now works. A local
synthesis runtime — Piper or equivalent, pointed at the way the transcription
server now is — is the fuller answer and is worth doing only if the filter turns
out not to be enough.

**Required user-interface outcome.** Read-aloud either uses a voice that stays on
this machine or says that it could not find one, without asking the owner to
configure anything.

---

## BUG-271 — A reviewer can narrow a change, and cannot correct one

**Severity: Low. Area: Build / Approvals / code review. Status: Closed 2026-09-04
as [FIXED-375](FIXED_ITEMS.md#fixed-375--a-reviewer-could-narrow-a-change-and-could-not-correct-one),
which is what "What it would take" below describes; GAP-BUILD B14 closes with
it.**

**Observed.** Per-hunk accept and reject ship. *Edit then accept* — the reviewer
changing a line in the proposed diff and approving the result — does not, and is
still not offered rather than being shown as a control the server would refuse.

**Why it did not come with the other half.** A narrowing and an edit are
different kinds of thing, and the difference is exactly the one the approval
boundary is built on:

* A **narrowing** is a subset of what was approved. `select_hunks` copies bytes
  out of the approved patch and copies nothing else in, so the A1 immutable-intent
  hash still covers the whole approved change and the executed change is provably
  inside it.
* An **edit** is a *different action*. Its bytes were never approved, so it
  cannot ride that hash — and the one thing the relay must never do is execute
  arguments no human read. `ResolveApprovalRequest` sets `extra="forbid"`
  precisely to stop an edited payload arriving on a resolve.

**What it would take.** An edit has to become a **new proposal** rather than an
amended one: the owner's edited patch is submitted as a fresh action, gets its
own preview, its own hash and its own approval, and the original resolves as
rejected-with-a-replacement so the audit trail says what happened. That is a
proposal path, not a field on the decision — which is why it is a separate entry
rather than the unfinished tail of FIXED-369.

**Required user-interface outcome.** Either an edit control that produces a
second decision the owner makes on their own text, or nothing. What must not
appear is a control that looks like an amendment to the approval in front of it.

---

## BUG-273 — Three live scenarios of the 2026-09-03 round are written and unrun

**Severity: Low. Area: live test harness / evidence. Status: Closed 2026-09-15
as [FIXED-541](FIXED_ITEMS.md#fixed-541--three-scenarios-blocked-on-a-key-for-six-rounds-and-on-three-stale-selectors-for-one-more).
Raised 2026-09-03; blocked on the key for five rounds after that.**

**They ran.** The seventh key authenticates, so the entry's own instruction —
set `RAIKER_LIVE_ANTHROPIC_KEY` and run the spec — finally had an answer. All
three scenarios pass: the meter reads **1 model set up** once a provider is
connected, a routine's cycle runs inside its own conversation and the card links
to it, and that thread is on the board under **Routines**.

**What the unblocking found.** The spec had been unrunnable for so long that it
encoded three controls the product no longer has, and each one failed as though
Raiker had stopped doing something — the harness drift
[FIXED-534](FIXED_ITEMS.md#fixed-534--a-live-helper-that-found-nothing-let-a-later-assertion-take-the-blame)
records. All three are in
[FIXED-541](FIXED_ITEMS.md#fixed-541--three-scenarios-blocked-on-a-key-for-six-rounds-and-on-three-stale-selectors-for-one-more).

**Observed.** `priority-round-real-turn-live.spec.ts` covers the three claims of
that round which need a model to actually answer:

* the setup meter reading **1 model ready** once a provider is connected, which
  is the other half of [FIXED-365](FIXED_ITEMS.md#fixed-365--a-fresh-install-named-a-model-nobody-had)
  — the *no* case is proven, the *yes* case is not;
* a routine's cycle running **inside its own conversation**
  ([FIXED-367](FIXED_ITEMS.md#fixed-367--background-work-finished-into-a-status-line));
* that same thread appearing on the board
  ([FIXED-368](FIXED_ITEMS.md#fixed-368--where-did-i-say-that-was-answered-what-am-i-working-on-was-not)).

None of the three ran. The key supplied for the round is identity-linked and
cannot authenticate without a workspace id — which is
[FIXED-370](FIXED_ITEMS.md#fixed-370--a-valid-key-was-reported-as-a-bare-http-status),
raised from this very attempt — so no turn could be sent.

**What *is* proven meanwhile**, and it is not nothing: all three behaviours are
covered by unit and API tests
(`test_task_conversation_thread.py`, `test_work_threads.py`,
`TasksView.test.ts`, `SearchChatView.test.ts`, `WorkbenchView.test.ts`), and the
surfaces themselves were walked live at four widths with no console error. What
is missing is the end-to-end evidence a FIXED entry is normally held to: a real
turn, in a real thread, on a real provider.

**Re-attempted 2026-09-06 (fifth round), and blocked on the same value for the
fifth time.** Same two commands, same two answers: `/v1/models` replies `400`
with *"This API key is not scoped to a workspace…"*, and
`/v1/organizations/workspaces`, `/v1/organizations/me` and
`/v1/organizations/api_keys` all reply `403 Missing permissions`. There is no
local runtime on this host either — neither Ollama nor llama.cpp is installed and
nothing answers on `:11434` — so no provider on this machine can complete a turn,
and the three scenarios stayed unrun.

What the attempt *did* buy, keeping the entry's own rule that the attempt is
cheap: the connection was driven through the interface end to end and the
refusal reads as itself in the picker —
*"This key is identity-linked, so it acts inside one workspace. Add the workspace
ID to this connection…"* — with no *Provider unreachable* anywhere, so FIXED-370,
FIXED-372, FIXED-382 and FIXED-388 all still hold under a fifth key. And the
screenshot taken as evidence for
[FIXED-430](FIXED_ITEMS.md#fixed-430--five-surfaces-asked-would-this-model-run-by-building-one-and-dropping-it)
showed the Models page reporting the hosted gate as **Off** above the connected
provider it had just accepted a model for, which is
[FIXED-435](FIXED_ITEMS.md#fixed-435--the-models-page-said-a-gate-was-on-above-providers-it-would-refuse).

**Re-attempted 2026-09-05 (fourth round), and blocked on the same value for the
fourth time — but the check is now two commands rather than a round.** The key
supplied for this round is identity-linked as well:

```
$ curl -s -o /dev/null -w '%{http_code}' https://api.anthropic.com/v1/models \
    -H "x-api-key: $KEY" -H 'anthropic-version: 2023-06-01'
400   # "This API key is not scoped to a workspace, so this request must
      #  include the anthropic-workspace-id header…"
$ curl -s -o /dev/null -w '%{http_code}' \
    https://api.anthropic.com/v1/organizations/workspaces -H "x-api-key: $KEY"
403   # "Missing permissions."
```

Same shape as the second and third rounds, and the same conclusion: **the id
cannot be recovered from the credential**, so the workspace id has to come from
whoever issued the key. Raiker's half is done —
[FIXED-372](FIXED_ITEMS.md#fixed-372--the-answer-to-an-identity-linked-key-was-go-and-get-another-one)
gives the connection a **Workspace ID** field and
[FIXED-388](FIXED_ITEMS.md#fixed-388--a-valid-key-was-answered-with-check-your-network)
makes the refusal read as itself. What is missing is a value only the key's
owner has.

This round did not attempt the three scenarios blind. It confirmed the block in
two requests, said so, and spent the round on work that could be finished — which
is what the entry's own note that *"the blocked scenario is expensive; the
attempt is not"* is for.

**Re-attempted 2026-09-04 (third round), and still blocked on the same value —
but the attempt was not wasted.** The key supplied for this round is
identity-linked too: `/v1/models` answers it `400` with *"This API key is not
scoped to a workspace…"*, and `/v1/organizations/me`, `/v1/organizations/workspaces`
and `/v1/organizations/api_keys` all answer `403`, so the id is again not
recoverable from the credential. What the attempt *did* find is
[FIXED-388](FIXED_ITEMS.md#fixed-388--a-valid-key-was-answered-with-check-your-network):
Raiker had been answering that exact refusal with *"Anthropic could not be
reached. Check that it is running and reachable from this device."* Two rounds of
repair — the classification (FIXED-370) and the Workspace ID field (FIXED-372) —
were sitting behind three string literals the provider does not send, and only a
third live attempt with a third key was ever going to show that. **The blocked
scenario is expensive; the attempt is not.**

**Re-attempted 2026-09-04 (second round), and still blocked on the same value.**
The key was connected through the interface again and the refusal now reads as
itself on the picker as well as under **Test**
([FIXED-382](FIXED_ITEMS.md#fixed-382--the-model-picker-said-unreachable-about-a-provider-that-had-just-answered)).
What was also established this round is that **the id cannot be recovered from
the key**: `/v1/organizations/me` and `/v1/organizations/workspaces` answer a key
of this kind with `403`, so there is no path from the credential to the workspace
it acts in. Nothing further is Raiker's to build.

**Reduced 2026-09-04.** The fix is still not code *in the product* — that half
is done. [FIXED-372](FIXED_ITEMS.md#fixed-372--the-answer-to-an-identity-linked-key-was-go-and-get-another-one)
gives the connection a **Workspace ID**, so the identity-linked key supplied for
that round is now usable by Raiker; what is still missing is the id itself, which
only the key's owner has. Set `RAIKER_LIVE_ANTHROPIC_KEY` to a key that
authenticates — a standard console key, or an identity-linked one **with**
`RAIKER_LIVE_ANTHROPIC_WORKSPACE_ID` set to its workspace — and run:

```
npx playwright test --project=live e2e/priority-round-real-turn-live.spec.ts
```

The spec skips itself when the variable is unset, so it neither fails CI nor
claims a scenario it did not run.

---

## BUG-276 — Governed events only leave when somebody presses a button

**Closed 2026-09-04 as
[FIXED-386](FIXED_ITEMS.md#fixed-386--governed-events-only-left-when-somebody-pressed-a-button).**
A destination carries a cadence drawn from the scheduler's own interval table,
claimed exactly once on the host tick, under the same pause switch and the same
governed route as **Deliver now**. The card states the cadence and the next run,
or states that it is on demand only.

**The entry's proposal was followed half way, and the other half was declined
with a reason.** It asked for a *routine* on the Tasks board. The cadence, the
pause switch and the audit trail are indeed the ones that already exist — that is
what shipped. But a task cycle is a governed **turn**: a model reads a prompt and
decides what to call. Putting a model in the path of "did the record leave the
machine" makes delivery a judgement where it is arithmetic over a cursor, and
every other authority path in this product keeps the model out. The record of
that decision is in `deliver_due_telemetry`'s own docstring, where the next
reader will be.

The original entry follows, unchanged.

---

**Severity: Low. Area: Observability / telemetry export. Status: Open — raised
2026-09-04, while closing
[backlog item 18](FIXED_ITEMS.md#fixed-379--raiker-recorded-more-than-anyone-exports-and-could-not-export-it).**

**Observed.** `telemetry_export` delivers governed events to an owner-named OTLP
collector, and it delivers them **only on demand**: **Deliver now** on the
destination's card, or `POST /api/telemetry/destinations/{id}/export`. There is
no background sender. Events accumulate behind the cursor until someone looks,
which the card states honestly (`N delivered`, `Last run …`) rather than implying
a live feed.

For the use this exists for that is half a wire. An owner running Raiker beside
a dashboard wants the record to *arrive*, and a collector that receives only
while its operator is watching is not something a dashboard can be built on.

**Why it shipped this way, and why that was right.** The alternative on the table
was a daemon, and this codebase has refused one before for the same reason:
`scheduled_routines` is an on-demand runner and the retention sweep
([FIXED-284](FIXED_ITEMS.md)) is an owner-confirmed action, both deliberately.
A background process that reaches the network on a timer is a different security
object from a button, and it needs its own answer to: what happens when the
collector is unreachable for a day, what bounds the retry, and what the owner
sees while it is failing. None of those were worth guessing at to make a first
version feel finished.

**Proposed fix.** The scheduler already exists and already runs governed work on
a cadence a task carries. A delivery is a governed action with an executor, so
the honest shape is a **routine** — an owner-created schedule that runs the
export, visible on the Tasks board like every other recurring thing, with its
failures landing in the same places every other task's do. That reuses the
cadence, the pause switch, the notifications and the audit trail rather than
inventing a second scheduler beside them.

**Interface outcome that has to be true before this closes.** A destination
either states the cadence it is delivered on, or states that it is delivered only
on demand. It must never be possible to read the card and believe events are
flowing when nothing has run since the owner last pressed the button.

---

## BUG-277 — Design is a one-shot generator, so most of its composer has nothing to reach

**Closed 2026-09-13
([FIXED-491](FIXED_ITEMS.md#fixed-491--design-was-a-one-shot-generator-so-most-of-its-composer-had-nothing-to-reach)).**
The runtime first, the interface second, as the entry set out. A generation
records `source_generation_id` and `kind`, so an edit has a subject, a variation
set has siblings and a version strip has versions; Design composes Assets │
Canvas │ Inspector around a selection, and the primary action says **Edit** while
one is selected. The subject is resolved owner-scoped in the executor, after
policy and the credential.

**One half is not closed with it** and is carried as
[BUG-287](#bug-287--the-image-provider-round-trip-is-unverified-against-a-real-provider):
this host's egress policy blocks the image providers, so what a provider actually
returns for an edit or a set of variations has not been seen.

---

## BUG-278 — Two Work surfaces still keep their own composer

**Severity: Low. Area: composer. Status: Closed 2026-09-15 as
[FIXED-540](FIXED_ITEMS.md#fixed-540--the-two-surfaces-that-kept-their-own-composer-had-stopped-keeping-it).
Raised while implementing
[COMPOSER-10 and COMPOSER-11](UNIFIED_COMPOSER_REDESIGN_2026-09-06.md).**

Closed by the work it was raised beside, and recorded late. COMPOSER-10 rebuilt
task creation on `Composer.svelte`, and both surfaces this entry names — `tasks`
and `schedule`, which the cadence chips switch between in the same form — have
carried the shared `+` menu, Tools menu, context line and model picker since.
What was missing was the assertion, which is now in `TasksView.test.ts`: a test
that would fail if any of the four drifted back to a copy of its own.

**Observed.** Chat, Build and Design share one composer shell, one Add menu, one
Tools menu, one context line and one model control. Tasks and Schedule do not:
task creation still carries its own model picker, its own environment badge and
its own capacity chip, in the layout it had before.

The consequence is small but real, and it is the one the redesign exists to
prevent: a person who has learned the composer in Chat meets a different
arrangement of the same controls when they schedule the same work.

**Why it was left.** The task form is not only a composer — it also collects a
cadence, a recurrence and a notification rule, and COMPOSER-10 describes those
as progressive disclosure behind `Schedule ▾`. That is a redesign of the task
surface rather than an application of the composer, and doing it badly would
trade a consistent composer for a worse scheduling flow.

**Proposed fix.** Apply `Composer.svelte` with `+` and Tools to Tasks, and move
the cadence and notification rules behind the primary action's own disclosure,
as COMPOSER-10 sets out. The typed registry already declares `tasks` as a
surface, so the menus exist the moment a handler is supplied.

**Interface outcome that has to be true before this closes.** Creating a task
uses the same composer grammar as asking a question, and the timing details
appear only once the owner asks for them.

---

## BUG-280 — Weather and the environment clock are unmeasured against a real provider and a real model

**Severity: Low. Area: runtime / environment context, weather. Raised while
implementing ENV-01…05 and WEATHER-01…03.**

**Half of this closed 2026-09-15 as
[FIXED-539](FIXED_ITEMS.md#fixed-539--a-real-turn-now-answers-from-raikers-clock-and-the-weather-half-still-cannot-be-measured-here).**
The clock half was measurable the moment a host had a working key: a real
Anthropic turn names the runtime's date and day, and follows the owner's zone
when it changes. The spec reads the expectation from `/api/environment` rather
than hardcoding a date, so it measures agreement between the runtime and the
model rather than agreement with whatever day it was written on.

**The weather half is still open, and still for the same reason.** Every attempt
to reach `api.open-meteo.com` from this host is cut by the environment's egress
policy — verified again on 2026-09-15, `curl` returns no status through the
proxy's tunnel — so the tool answers `weather_provider_unavailable`, which is the
correct typed answer to an unreachable provider and is not evidence that a
reachable one is read correctly. Closing it needs a host with egress, not a
change to Raiker.

**Observed.** The 2026-09-07 round proved the whole of the environment and
weather contract against the runtime: the bundle a turn is given, the event it
records, the precedence, the DST behaviour, the stale-refresh note, and every
governed refusal. Two halves of it were not measured, and neither is a code gap.

*No model reasoned from the bundle.* The round's key is identity-linked, as the
previous six were, and this host has no local runtime, so no provider on it can
complete a turn. The bundle is asserted against the messages the orchestrator
builds — which is the right place, since it is derived before any provider is
called — but "the model answered `tomorrow` correctly" is a claim only a real
turn can support.

*No weather request left the machine.* The provider path is asserted against a
stand-in that answers as Open-Meteo does, and every governed refusal is asserted
against the real gate, decision mode and blocklist. What is unmeasured is the
real HTTP round trip. `api.open-meteo.com` resolves from this host and every
attempt to reach it — with or without the environment's proxy — is refused with
`403` by that environment's own egress policy, so the tool returns
`weather_provider_unavailable`. That is the correct typed answer to an
unreachable provider; it is not evidence that a reachable one is read correctly.

**Why it was left.** Both need something the round did not have — a working
provider credential and outbound egress — rather than something Raiker is
missing. Recording it here is what stops the plan's `Done` reading as a claim
about evidence that was never taken.

**Proposed check.** On a host with egress and a working model: ask *"what day is
it, and what is the weather here?"* in Chat, and confirm the answer names today's
real date in the owner's zone and cites the weather provider with its observation
time. Then set the timezone to another continent and ask *"what time is it?"*
again.

**Interface outcome that has to be true before this closes.** A real turn
answers a relative-time question from the runtime's clock rather than from
training knowledge, and a real weather answer names its provider and how old the
reading is.

---

## BUG-281 — Design's research findings are text, not sources

**Severity: Low. Area: Design. Status: Closed 2026-09-15 as
[FIXED-538](FIXED_ITEMS.md#fixed-538--designs-research-findings-were-text-and-the-pages-behind-them-were-already-recorded).
Raised while implementing WEB-06.**

Closed without waiting for VIS2-19. The deferral's reasoning was that Design's
workspace shape is still open and a source list built into a panel about to be
replaced would be work done twice — but what landed is not a panel: it is the
same `SourceChips` and `SourceExcerptPanel` Chat and Build already use, reading
the ledger the turn already wrote. Whatever shape the canvas takes, the chips
move with it as one line.

**Observed.** Design's Tools menu runs a real governed research turn on the
`design` surface: it searches, reads and extracts through the global read
catalogue, and the findings appear above the composer for the owner to write a
prompt from. What comes back is the model's prose. The turn *records* its
sources — every governed read enters the turn-source ledger, which is what
Chat's citation chips are drawn from — but the Design panel does not render
them, so the owner cannot open the page a reference came from without going to
the conversation.

**Why it was left.** The ledger and the reader both exist; what is missing is
the panel that shows them here, and Design's own workspace shape is still open
under the Design-canvas row of the visual review. Building a source list into
a panel that is about to be replaced by a canvas would be work done twice.

**Proposed fix.** Render the research turn's sources as the same chips Chat
uses, so a reference can be opened at the passage that produced it — and carry
them into the canvas when VIS2-19 lands.

**Interface outcome that has to be true before this closes.** Every claim in a
Design research result can be opened at the page it came from, without leaving
Design.

---

## BUG-282 — A generated image does not belong to the project it was made in

**Closed 2026-09-13
([FIXED-492](FIXED_ITEMS.md#fixed-492--a-generated-image-did-not-belong-to-the-project-it-was-made-in)).**
The deferral held until the shape it was waiting on existed. BUG-277's lineage
work changed the same row and the same request, so `project_id` travelled with
it: Design's composer sends the project it names, the row carries it, and the
project's page shows its pictures beside its files. The context line no longer
needs the words *not filed to it yet*.

---

## BUG-285 — An Ollama Cloud model tests and runs in Ollama but Chat cannot use it

**Closed 2026-09-20 as
[FIXED-590](FIXED_ITEMS.md#fixed-590--a-turn-that-failed-blamed-the-local-runtime-for-it).**
The entry offered two interface outcomes and the second is the one that was
reachable: a failed turn reports the specific refusal rather than a generic
reachability message. The message turned out to be the *surface's* — Chat and
Build reduced an `ApiError` to its HTTP status and everything else to "Could not
reach the local runtime", while the runtime had already named the refusal and
carried the code. Proving the first outcome — that a cloud-tagged Ollama model
completes a turn — still needs a host running Ollama with such a profile, which
this round did not have; it is no longer *hidden* by a message that blames a
service that is running.

---

## BUG-286 — A fresh composer names an unreachable default it was never given

**Severity: Low. Area: Chat/Build composer, model decision. Status: Closed
2026-09-14 as
[FIXED-525](FIXED_ITEMS.md#fixed-525--a-composer-with-no-default-chosen-opened-naming-a-model-nobody-had-chosen).
Raised 2026-09-12 during the global-catalogue live round.**

**Observed.** On a workspace with Anthropic connected and no default chosen, the
Chat picker's trigger reads **Not selected** — correct — while the menu above it
opens with a decision note naming `Gemma 4:31B Cloud` as **Selected ·
unavailable**. Nothing selected that model; it is the shipped Ollama profile's
declared model, on a host with no Ollama. The two statements are in the same menu
and disagree with each other.

**Why it was left.** It predates the global catalogue and is not caused by it.
`GET /api/model-decision` resolves a selection from the profile registry when the
owner has stored none, and the picker reports that resolution honestly — the
defect is in what the decision answers, not in what the menu draws. Changing it
is a contract change with its own tests (`tests/test_model_decision.py`) and
belongs with that contract rather than inside a picker change.

**Proposed fix.** Have the decision report no selection when the owner has stored
none, rather than a registry default, so the **Selected · unavailable** note
appears only when a selection exists and cannot serve.

**Interface outcome that has to be true before this closes.** A composer with no
default chosen says only that, and no model the owner never chose is described as
selected.

---

## BUG-287 — The image provider round trip is unverified against a real provider

> **2026-09-15 — what the round trip now has to prove changed.**
> [FIXED-542](FIXED_ITEMS.md#fixed-542--every-side-effect-capability-now-says-what-it-would-cost-and-one-of-them-had-no-gate-at-all)
> found that `image_generation` had no key in `CAPABILITY_GATE_MAP`, so the
> owner's switch reached no gate: the action was approval-required by policy and
> nothing else. The row is there now, which means a live round has a second thing
> to measure — that turning **Image generation** off actually refuses a
> generation, not only that a key produces an image.

**Severity: Medium. Area: Design / image runtime / live evidence. Raised while
closing [BUG-277](#bug-277--design-is-a-one-shot-generator-so-most-of-its-composer-has-nothing-to-reach),
2026-09-13.**

**Observed.** The lineage runtime and the canvas were built and verified, but
no picture has been generated or edited through a real provider from this host.
The egress policy answers 403 to `CONNECT api.openai.com`, and a live generate
run through the product's own composer refuses with `fetch_failed:URLError`,
which is the environment rather than the code.

**What *was* exercised against the running server.** The governed route, the
owner-scoped subject resolution, the count bound and its zero case, lineage
recorded on refusals, `project_id` carried from the composer through to the
stored row, and the canvas composing real rows read back through `GET /api/images`.
The multipart wire format is proven against a real socket — a live HTTP server
parses the body with Python's own MIME parser and the image comes back byte for
byte (`tests/test_multipart_egress.py`).

**What is not known.** What OpenAI's `/v1/images/edits` and Gemini's inline-data
edit actually return: the response shape on success, how a provider refusal reads
when the *source* image is the thing refused rather than the prompt, and whether
a request for four pictures comes back as four images or as one with a count the
decoder has to split. `_decode_images` handles the shapes the providers document;
none of them has been seen.

**Proposed fix.** One live round against a reachable image provider. Gemini is
the cheaper route — `generativelanguage.googleapis.com` is reachable from this
host, so a Gemini API key alone would close it — covering generate, edit,
variations and a provider refusal of a source image, with the lineage read back
through `GET /api/images`.

**Interface outcome that has to be true before this closes.** A picture generated
through a real provider, edited into a second version, and both shown on the
canvas as the chain they are — with the captures to prove it.

---

## BUG-288 — A turn can only answer in prose, and the components to answer otherwise already exist

**Closed 2026-09-15 as
[FIXED-545](FIXED_ITEMS.md#fixed-545--a-turn-could-only-answer-in-prose).**
VIS-19, and the last implementation item in
the visual UI/UX review of 2026-09-06, which was removed when it closed.

The channel came first, as it did for Design: a turn declares a part with a
` ```raiker:table ` or ` ```raiker:chart ` fence, the runtime validates it the
way it validates any action argument — bounded, and refused rather than repaired
— and the response carries typed parts the client renders directly. A real
Anthropic turn answers with a sortable table and a bar chart that carries its own
numbers.

---

## BUG-289 — A hosted provider this machine cannot reach is told to "check that it is running"

**Severity: Low. Area: Models / provider errors. Status: Closed 2026-09-14 as
[FIXED-526](FIXED_ITEMS.md#fixed-526--an-owner-was-told-to-check-that-openrouter-was-running).
Raised 2026-09-13 while verifying
[FIXED-501](FIXED_ITEMS.md#fixed-501--raiker-knew-its-owners-authorisation-key-and-not-their-name).**

**Observed.** Pressing **Test connection** on an OpenRouter card, on a host whose
egress policy refuses `CONNECT openrouter.ai`, reports:

> OpenRouter could not be reached. Check that it is running and reachable from
> this device.

The sentence is honest about *what* happened and slightly wrong about *what to
do*. This is `ModelsView.testNote`'s last-resort branch, which is correct here —
a proxy's `connect_rejected` is genuinely unclassified, and
[BUG-272](FIXED_ITEMS.md#fixed-388--a-valid-key-was-answered-with-check-your-network)
is why anything classifiable no longer lands in it. But the advice it carries was
written for a *local* runtime: "check that it is running" is a thing an owner can
do about llama.cpp on their own machine and not a thing they can do about
OpenRouter.

**Root cause.** One fallback sentence for two kinds of destination. The branch
does not distinguish a hosted provider from a local one, so both get the local
remedy.

**Proposed fix.** Split the last-resort sentence by provider kind. A local
runtime keeps today's wording. A hosted one names the remedy that is actually
available: this device's network access, and any proxy or firewall between it and
the provider. Neither should guess at a cause — the point of this branch is that
there is no classified one.

**Interface outcome that has to be true before this closes.** A hosted provider
that cannot be reached offers a remedy an owner can act on, and a local one still
offers the one that applies to it — with a capture of each.

---

## BUG-290 — Three of the four providers this round was given keys for cannot be reached from this host

**Severity: Low. Area: Live evidence / providers. Raised 2026-09-13. The same
limit as [BUG-273](#bug-273--three-live-scenarios-of-the-2026-09-03-round-are-written-and-unrun),
reconfirmed with three fresh keys.**

**Observed.** The 2026-09-13 release-readiness round was given working keys for
Anthropic, OpenAI and OpenRouter, and asked to use a local Ollama cloud model as
a fourth. Only Anthropic answered:

| Provider | Outcome on this host |
|---|---|
| Anthropic | **Real round trip.** Connected, Haiku 4.5 pinned, readiness confirmed, and a real turn answered — the evidence behind [FIXED-501](FIXED_ITEMS.md#fixed-501--raiker-knew-its-owners-authorisation-key-and-not-their-name). |
| OpenAI | `connect_rejected` — the egress proxy denies `CONNECT api.openai.com`. |
| OpenRouter | `connect_rejected` — the egress proxy denies `CONNECT openrouter.ai`. |
| Ollama (cloud model) | No Ollama on this machine, and no way to install one from here. |

**What was proven anyway.** Raiker's half, for all three. Each key was entered
through the product's own dialog, each connection was stored, and each readiness
check reported its own outcome as a sentence rather than as a bare status or a
wrong diagnosis — which is [FIXED-388](FIXED_ITEMS.md#fixed-388--a-valid-key-was-answered-with-check-your-network)'s
rule holding under three more keys. `web/e2e/owner-identity-live.spec.ts` runs all
three and skips with the reason when a key is absent.

**What is still unverified.** A real turn through OpenAI, OpenRouter or a local
Ollama cloud model, and therefore the identity block, the citation ledger and the
tool loop against any provider but Anthropic.

**Interface outcome that has to be true before this closes.** The same question
the owner reported — *who is the owner of this workspace* — asked and answered
through each of the four providers, with a capture of each answer.

---

## BUG-291 — A live spec asserts a refusal that a working key will never produce

**Severity: Low. Area: Live test harness. Status: Closed 2026-09-14 as
[FIXED-534](FIXED_ITEMS.md#fixed-534--a-live-helper-that-found-nothing-let-a-later-assertion-take-the-blame).
Raised 2026-09-13 while running the RR-MCP-02 round.**

**Observed.** `web/e2e/anthropic-key-live.spec.ts` fails against the Anthropic key
this round was given. Nothing is wrong with the key or with Raiker: the spec was
written for the *previous* round's key, which was identity-linked and could only
authenticate with the id of the workspace it acts inside, and it asserts that the
model dialog says so —

```ts
await expect(dialog.getByText(/identity-linked/i)).toBeVisible({ timeout: 90_000 });
```

This round's key authenticates normally. `/v1/models` answers 200 with eleven
models, the connection saves, the picker fills, and the spec spends ninety seconds
waiting for a refusal that is not coming.

**Root cause.** The spec encodes a property of one *credential* as though it were
a property of the *product*. Raiker's half — that an identity-linked refusal is
classified and stated in words beside the field that fixes it — is worth keeping;
what is not is a scenario that only passes when the key is broken in one specific
way.

**Proposed fix.** Split it. Assert the classification against a stubbed provider
response, where an identity-linked refusal can be produced on demand, and leave
the live spec asserting what a *working* key does: models listed, a model pinned,
a turn answered. A live spec that passes only with a key nobody would want is a
spec that will be deleted rather than fixed the next time it fails.

**Interface outcome that has to be true before this closes.** The spec passes
against a working key and against an identity-linked one, and says which it is
looking at.

---

## BUG-292 — A live spec sends a turn without choosing a model, and the composer is right to refuse

**Severity: Low. Area: Live test harness. Status: Closed 2026-09-14 as
[FIXED-534](FIXED_ITEMS.md#fixed-534--a-live-helper-that-found-nothing-let-a-later-assertion-take-the-blame).
Raised 2026-09-13 while running the RR-MCP-02 round.**

**Observed.** `web/e2e/bug-206-207-tool-rows-and-reasoning-live.spec.ts` connects
Anthropic, pins Haiku 4.5 on the provider card, goes to `#/new-chat`, types a
prompt and presses **Send**. On a workspace where no global model has ever been
chosen, Send is disabled and the composer says so: *"No model is chosen. Choose
one from the model menu beside Send."* The spec waits out its timeout on a
disabled button, and the five scenarios behind it never run.

The product is behaving correctly — a composer that guessed a model would be the
defect — and the spec is asserting a step it never takes. Pinning a model on a
provider card is what makes it *available*; choosing it in the composer's picker
is what makes it the model for the turn, and they are two different decisions by
design.

**Root cause.** The same drift as [FIXED-503](FIXED_ITEMS.md#fixed-503--the-live-harness-looked-for-provider-controls-that-had-moved-into-a-menu):
the harness encodes where a control used to be, or what state a workspace used to
be left in. `useHostedModel` returns a card with a pinned model and no scenario
using it chooses one for the turn.

**Proposed fix.** A `chooseModelForTurn` helper beside `useHostedModel`, opening
the composer's own picker and selecting the model by name — which is what
`web/e2e/rr-mcp-02-live-provider-turn-live.spec.ts` does inline, and what every
spec that sends a turn needs. One place, so the next change to the picker is one
edit rather than a sweep.

**Interface outcome that has to be true before this closes.** Every live spec
that sends a turn passes against a workspace where no global model was ever
chosen.

---

## BUG-293 — A side-effect capability's threat model and bypass test are not mechanically required

**Closed 2026-09-15 as
[FIXED-542](FIXED_ITEMS.md#fixed-542--every-side-effect-capability-now-says-what-it-would-cost-and-one-of-them-had-no-gate-at-all).**

`CAPABILITY_AUTHORITY` carries the two columns that had no home — what a
capability would cost if it ran ungoverned, and what stands in the way — beside a
per-capability negative bypass test, and CI asserts the table complete against
`REAL_EXECUTOR_CAPABILITIES` in both directions. Permissions renders both, and a
reach chip on the closed row.

Writing it out found `image_generation`: a real executor, an owner-facing switch,
an activation requirement and a docstring promising the gate applied, with **no
key in `CAPABILITY_GATE_MAP`** — so the gate check found nothing to check and the
owner's off switch decided nothing. Measured, fixed, and kept closed by a general
assertion.

**What remains of [RR-AUTHORITY-01](RELEASE_READINESS_PRODUCT_UX_RUNTIME_REVIEW_2026-09-13.md#what-blocks-a-public-first-release)**
is its other half: the opaque runtime authority context DEC-16 asks for, which is
a type/issuer boundary rather than a registry column. That is not this entry.

---

## BUG-294 — Threads filters describe a hundred rows and are called a workspace

**Severity: Medium. Area: Threads / work index. Raised 2026-09-14 as
[NEW-THREAD-01](RELEASE_READINESS_PRODUCT_UX_RUNTIME_REVIEW_2026-09-13.md#new-thread-01--filters-only-cover-a-truncated-list-and-disappear-during-search)
of the removal and simplification review. Closed the same day as
[FIXED-511](FIXED_ITEMS.md#fixed-511--threads-described-a-hundred-rows-and-called-it-a-workspace).**

Raised here because the fix was an API change rather than a view fix and was not
expected to land in the run that found it. It did: `GET /api/work-threads/page`
filters, facets over everything that matched with each facet's own filter
lifted, and pages behind a scope-bound cursor. The full record — what was
observed, why a browser could not be the index, and the sixteen server cases
behind it — is in
[`FIXED_ITEMS.md`](FIXED_ITEMS.md#fixed-511--threads-described-a-hundred-rows-and-called-it-a-workspace).

With it, every finding in §18.5 of that review is closed.

---

## BUG-295 — Three live-test helpers waited for strings the product had stopped printing

**Severity: Low. Area: Live test harness. Raised and partly fixed 2026-09-14.**

Found while running the live suite against the Permissions overhaul, and worth a
row of its own because the failure mode is the one that makes a live suite stop
being evidence: a helper that cannot find its element does not always fail — it
times out and walks on, and the assertion that fails is two hundred lines later
and reads as a product defect.

Three were found and fixed in this pass:

* `enableCapability` waited on `getByPlaceholder(/Search capabilities/)`. The
  placeholder has read *“Search permissions, actions or groups…”* since the
  page's vocabulary changed, so every live spec that turns a capability on spent
  sixty seconds waiting for a string the product does not print. It waits on the
  field's **label** now, which is the stable half. Three specs waited on the same
  stale placeholder directly and were changed with it.
* `bug-239-unset-gate-honesty-live` asserted an exact `Off` element inside a
  row. Availability and the mode were merged into one summary some time ago, so
  the element it wanted no longer exists and the spec had been failing on the
  harness rather than on the product. It reads the row's summary now.
* `first-launch-live` and `dismissFirstRunModelSetup` both waited for *“Your
  Raiker is ready”*, which is now *“Setup saved”* on a run that defers the model
  ([FIXED-514](FIXED_ITEMS.md#fixed-514--first-run-called-an-instance-ready-above-a-summary-that-said-decide-later)).

**Fixed since, on the same day.** Ten further specs waited on the same dead
placeholder directly — `getByPlaceholder("Search capabilities…")` — and every one
of them now waits on the field's label. They were found by grepping for the
string rather than by a failing run, which is the point: a wait that finds
nothing does not fail, it expires.

**Closed 2026-09-14** as
[FIXED-534](FIXED_ITEMS.md#fixed-534--a-live-helper-that-found-nothing-let-a-later-assertion-take-the-blame),
with the round that gave the helper a failing spec to prove itself against.

**What remained open until then.** `offeredModelIds` and `keepOffered` read the
model picker's checkboxes immediately after opening the dialog, before the
provider's list has arrived, so they saw an empty fieldset and a spec then asked
for `value="undefined"`. The helper was not changed in the 2026-09-14 morning
pass because no committed spec failed on it, and changing a shared helper without
a failing spec to prove it is how the next stale wait gets introduced. The
simplification round's own live spec is that proof: it reads the Anthropic
catalogue, keeps a model offered and sends a turn with it, and before the fix it
asked for `input[value="undefined"]`.

`openModelDialog` waits for the *"Loading models from …"* note to clear;
`offeredModelIds` throws with the note the dialog is showing rather than
returning an empty list; and `keepOffered` refuses a non-string model id.

**Interface outcome that has to be true before this closes.** A live helper that
cannot find what it is waiting for fails saying so, rather than timing out and
letting a later assertion take the blame. The suite's own selectors are label-
and role-based wherever the product offers one, so a wording change cannot
silently disarm a scenario.

---

## BUG-296 — Models reports a Hugging Face 503 into the browser console on every visit

**Severity: Low. Area: Models / Hugging Face. Status: Closed 2026-09-14 as
[FIXED-527](FIXED_ITEMS.md#fixed-527--an-outage-raiker-had-already-reported-also-reported-itself-to-the-console).
Raised 2026-09-14.**

**Observed.** Opening Models on a host with no route to `huggingface.co` puts
`GET /api/hugging-face/trending — 503` in the browser console. The page itself
handles it correctly and says *“Hugging Face could not be reached. Search and
download need a route to huggingface.co. Everything already in your local
library still works.”* — which is the right sentence in the right place.

The console entry is the problem, and only because of what depends on it: the
live manual test plan requires a round to end with **zero uncaught console
errors**, and several live specs assert exactly that. An expected, handled,
correctly-reported unreachable service therefore spends the budget that exists
to catch real ones, and a round that learns to ignore one console error has
learned to ignore the next.

**Interface outcome that has to be true before this closes.** A service Raiker
has already told the owner it cannot reach does not also report itself as an
uncaught error to the console, and a console-error assertion in a live spec
means what it says.


---

## BUG-297 — Three authority gates were never classified by the entry-path audit

**Severity: Low. Area: Governance / Permissions. Status: Closed 2026-09-14 as
[FIXED-524](FIXED_ITEMS.md#fixed-524--three-authority-gates-decided-their-own-capability-by-default-rather-than-by-classification).
Raised 2026-09-14.**

**Observed.** `admin_mutation`, `policy_mutation` and `role_mutation` are absent
from `CAPABILITY_ENTRY_PATHS` in `raiker/runtime/authority/entry_paths.py`. That
table is what GEP-04 built so no capability could ship without answering "what
constructs a governed action for this, and does its own gate decide whether it
runs". `RuntimeControlService` falls back to `OWN_GATE` for a capability with no
entry, so all three report themselves as deciding their own capability **by
default rather than by classification**, and the Permissions page renders each
with a full set of decision-mode buttons.

They may well be `own_gate`: `router.py` maps `user_create`, `user_deactivate`,
`role_create`, `role_grant` and `role_revoke` onto them, so a governed action of
those kinds does check them. What is missing is the finding rather than the
answer — nothing has traced whether any surface or model tool constructs one of
those actions, which is the difference between a decision an owner makes and a
row that looks like one.

The entry-path test asserts the table against `REAL_EXECUTOR_CAPABILITIES`, and
these three are not in that set, so the invariant that would have caught this
does not reach them.

They were deliberately left on the page when
[FIXED-523](FIXED_ITEMS.md#fixed-523--a-quarter-of-the-permissions-page-was-controls-that-control-nothing)
removed the fourteen gates the product itself declares inert. Removing a real
authority gate from the only page that shows it, on a guess, would be the
opposite of what that change was for.

**Interface outcome that has to be true before this closes.** Every capability
the Permissions page offers a control for has a traced entry path and a recorded
reality, and `OWN_GATE` is something a capability is classified as rather than
something it defaults to.

---

## BUG-298 — `policy_mutation` has a gate, a name in the router, and nothing that proposes one

**Closed 2026-09-15 as
[FIXED-543](FIXED_ITEMS.md#fixed-543--a-routed-gate-nothing-could-propose).**

The owner's decision was the first of the two the entry named: state the
boundary and remove the gate. Policy is process configuration the runtime reads,
on the same footing as the model egress allowlist and deliberately not editable
from a browser session; a switch over a change nothing can construct was a switch
over nothing. Two tests hold the name out rather than merely not mentioning it,
so re-adding it is a decision somebody makes.

---

## BUG-299 — A task's history of attempts, pauses and retries has nowhere to be read

**Severity: Medium. Area: Tasks. Status: Closed 2026-09-15 as
[FIXED-535](FIXED_ITEMS.md#fixed-535--a-tasks-history-of-attempts-pauses-and-retries-had-nowhere-to-be-read).
Raised 2026-09-14 while implementing REM-TASK-02.**

Closed as a *read* rather than a new store: every transition a task makes was
already a governed event carrying its `task_id`, so the attempts are the audit
log grouped at the scope of one task. Two beginnings were genuinely missing and
were added — `task_started`, which was in the event vocabulary and never
written, and `task_cycle_landed`, without which a routine's every cycle read as
still running because a recurring task is rescheduled rather than completed.
`#/tasks?task=…` is the address; Home's rows, the Tasks board, Build's side
panel and the `outcome_unknown` notice all point at it.

**Observed.** [FIXED-533](FIXED_ITEMS.md#fixed-533--one-run-three-stop-buttons-and-two-of-them-threw-the-reason-away)
gave one run one Stop, Resume and Run-now meaning across Home, Tasks and Build,
and reports three settlements rather than two — including `outcome_unknown`,
whose remedy is *"refresh to see the run's current state"*.

There is nowhere to refresh *to*. A task has a status and a current step, and no
per-task destination: no `#/tasks?task=…`, no attempt list, no record of the
approval it paused on or the retry that followed. So the controller can now tell
an owner honestly that it does not know what happened, and cannot then show them.

REM-HOME-01 ran into the same wall from the other side: its acceptance asks a
deduplicated row to "link to the canonical Tasks detail", and the dedupe landed
without the link because there is no such route.

This is UX-TASK-04 of the release-readiness review, and it is recorded here as a
defect rather than only as a recommendation because two implemented changes now
depend on it: one promises a place to look and the other promises a link.

**Interface outcome that has to be true before this closes.** A task has one
address that shows its attempts in order — each with its outcome, the approval it
waited on, the retry that followed and the evidence it produced — and the rows on
Home and in Build link to it.

---

## BUG-300 — A typed answer is typed in Chat and Build, and is characters everywhere else

**Closed 2026-09-16 as
[FIXED-551](FIXED_ITEMS.md#fixed-551--a-declared-table-was-a-table-in-the-conversation-and-json-everywhere-else).**

Four media, four answers, as the entry said it needed: a real `<table>` in an
HTML export, a GFM table in a Markdown one, a page-width Courier table in a PDF,
and — for read aloud — *"Table: Cost by provider. 2 columns, 3 rows."* rather
than a payload read out. A chart is exported as the numbers behind it in all
three files. A reopened turn carries parts derived server-side by the same
splitter, so Threads, the Sessions inspector and a reloaded conversation cannot
produce a different reading of one answer.

**Running it live found the reason it had nothing to render.** The model
declared its table in the round *before* it called `update_plan`, and
`final_text` only ever kept the last round's text — so every turn that narrated
its work stored a different answer than it showed.
[FIXED-550](FIXED_ITEMS.md#fixed-550--a-turn-that-wrote-anything-before-calling-a-tool-stored-a-different-answer-than-it-showed)
is that fix, and it is wider than this entry: it is why a reopened conversation
had been losing paragraphs all along.

---

## BUG-301 — The guide's own cross-references are not links

**Closed 2026-09-18 as
[FIXED-557](FIXED_ITEMS.md#fixed-557--the-guides-own-cross-references-were-punctuation).**
Resolved at the guide layer, exactly as the entry set out: `guideLinks.ts`
rewrites a chapter reference against the chapter list the page already loaded,
and the renderer accepts an in-app `#/…` address only for the one caller that
opts in — so a model-authored answer still cannot produce a link the renderer
would not have made before. A `.md` target that is *not* a chapter is a
repository document a reader inside the app cannot open however it is marked up,
and it renders as its label with the path named once rather than as punctuation.

---

## BUG-302 — Four audit summaries quote the whole answer, including a payload

**Closed 2026-09-18 as
[FIXED-558](FIXED_ITEMS.md#fixed-558--four-events-describing-themselves-with-one-borrowed-sentence).**
The decision the entry asked for, written down in `raiker/events/summaries.py`:
`response_created` is the one event whose subject *is* the answer and keeps it
verbatim; the other three say what they did. The facts that used to ride in the
`summary` column travel under their own keys, so the per-task attempt timeline
still reads a completion's outcome.

---

## BUG-303 — The conversation-library controls are still in the evidence inspector

**Closed 2026-09-20 as
[FIXED-576](FIXED_ITEMS.md#fixed-576--the-conversation-library-lived-in-the-evidence-inspector).**
Taken in the order the entry set out. The work index grew first — `pinned`,
`archived` and `tags` on `WorkThreadView`, a pin-first sort, an `archived`
*scope* on the page request with both counts returned in either one — so
Archive could move without becoming a control whose effect an owner could not
undo from the surface they used it on. Then the lifecycle menu and the tag
editor moved to Threads, and Sessions kept **Delete**, exactly as the entry
said it should: it removes the audit record, and it belongs beside the evidence
it removes.

---


## BUG-304 — Delete was off the bottom of the menu it lived in

**Closed 2026-09-20 as
[FIXED-577](FIXED_ITEMS.md#fixed-577--delete-was-off-the-bottom-of-the-menu-it-lived-in).**
The session row's menu was absolutely positioned inside a card that scrolls, so
on a workspace holding one conversation it opened below the card's own bottom
and was clipped. The menu is `position: fixed` now, measured from its trigger,
and closes on scroll rather than being left pointing at a row that has moved.

---

## BUG-305 — Two source controllers, and nothing that owns both

**Closed 2026-09-20 as
[FIXED-592](FIXED_ITEMS.md#fixed-592--two-kinds-of-source-and-nowhere-that-answered-what-can-raiker-read).**
The two controllers stay two, for the reason this entry gives — the lifecycles
genuinely differ. What they now share is the owner's question: one inventory
over both, and one door that stops a source, each handled by the controller that
owns it. The property the entry asks for is asserted in both directions:
revoking a granted folder drops everything indexed under it and leaves the
owner's file on disk, and revoking a managed file takes Raiker's own copy with
it.

---

## BUG-306 — Three surfaces carry their own conversation menu

**Closed 2026-09-20 as
[FIXED-591](FIXED_ITEMS.md#fixed-591--retry-looked-the-same-whether-the-turn-had-sent-an-email-or-nothing).**
The inventory this entry asked for found a defect rather than only duplication.
**Retry** re-sends the prompt, so a turn that wrote a file, ran a command or
sent a message does it again — and the control looked identical whether the
first attempt had done nothing or had pushed a branch. It now reads the turn's
own settled calls and asks, naming what would happen twice, while a turn that
only read is not asked about at all. The commands themselves moved behind one
set that owns each one's label, its confirmation and its failure sentence.

---
