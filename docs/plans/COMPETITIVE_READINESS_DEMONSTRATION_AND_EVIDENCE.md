# Competitive readiness — demonstration and evidence

## Decision and scope

**Status: accepted documentation direction, 2026-10-05; implementation and competitive validation remain separately evidenced.** The owner requested detailed demonstration and evidence requirements across `docs/plans/**`. This document is the canonical acceptance contract, not a second defect ledger and not a claim that Raiker matches any competitor.

**Decision.** Assess Raiker against three complementary reference groups (personal-agent scope extended 2026-10-07):

| Reference group | Required dimensions |
|---|---|
| Muse.ai, Claude.ai personal-work surface | Durable goals, personal context, proactive work, confirmed cross-service outcomes and usable artifacts (PA-S01–PA-S06/08; CR-01/03/04/05/07/09–12) |
| OpenClaw, Hermes Agent | Agent autonomy, model/deployment flexibility, integrations, memory, scheduling, extensibility and operational control (CR-01–CR-07) |
| Codex, Cursor, Claude | Coding quality, completed work, ease of use, recovery and overall polish (CR-08–CR-12) |

For coding comparisons, identify the exact Codex surface, Cursor mode and Claude Code release. Use the Claude app only for explicitly identified assistant/usability scenarios. A company or model family is not a sufficiently specific test subject. Product names here establish evaluation scope; they do not assert that each competitor supports every scenario.

**Reason.** Comparable source structures or passing edit helpers cannot establish autonomous completion, reliability or user experience. Competitors also implement governance. Raiker must demonstrate that its controls support useful completed work, alongside model choice and extensibility.

**Alternatives rejected.** Feature checkmarks omit reachability and outcomes; a single percentage obscures unsupported and unrun tasks; treating all tests as live proof confuses scripted fixtures with model behavior; copying another product's permission defaults would override Raiker's owner-authoritative posture. Use outcome-level evidence instead. This does not change capability defaults, accepted quiet-hours/Git OAuth decisions or deployment scope.

**Authority and dependencies.** Existing BUG/ADD/DEC records retain implementation ownership. Defects belong in [TO_BE_FIXED.md](TO_BE_FIXED.md), optional expansion in [TO_BE_ADDED.md](TO_BE_ADDED.md), verified closures in [FIXED_ITEMS.md](FIXED_ITEMS.md), observations in [LIVE_TEST_ROUNDS.md](LIVE_TEST_ROUNDS.md). [The manual plan](RAIKER_LIVE_MANUAL_TEST_PLAN.md) owns execution procedure; [the release review](RELEASE_READINESS_PRODUCT_UX_RUNTIME_REVIEW_2026-09-13.md) owns release decisions. A requirement below does not automatically authorise every proposed feature or make every competitor capability a launch blocker.

## Evidence levels and decision rules

Record the highest **supported level for the named scenario and configuration**, not one global product label:

| Level | Minimum evidence | What it cannot establish |
|---|---|---|
| Planned | Outcome, fixture, validator, dependency and owner role specified | Implementation exists |
| Implemented | Reachable production entry point and executor at a pinned revision | Successful execution |
| Component-verified | Executed focused test, command, output and fixture; all scripted/mocked boundaries disclosed | Autonomous or real-service completion |
| End-to-end verified | Real Raiker entry point to independently checked outcome; actual model/service where required; full trace | Superiority or parity with competitors |
| Competitively benchmarked | Same declared task/validator evaluated across named pinned products with configuration differences disclosed | General superiority beyond the tested suite |

Track outcome separately: **passed, failed, blocked, not run, unsupported, not applicable**. A blocked run has no product pass/fail verdict; unsupported capability remains visible in the coverage denominator. A test file's presence is not evidence it passed. Existing implementation statuses need not be renamed; attach these evidence levels to competitive claims.

Pre-register fixtures, success conditions, timeout, budget, allowed permissions and retry policy before running. Repeat model-driven tasks five times per product/configuration from clean equivalent state, preserving every attempt. Five trials are a screening sample, not statistical proof of equivalence. Deterministic checks must pass every prescribed case; do not average away unauthorised side effects, secret disclosure, cross-owner leakage, duplicate irreversible actions or false completion. Report task success as numerator/denominator with interventions, duration, tokens/cost and recovery separately. Do not invent one overall parity score or a relative threshold after seeing results.

Use two explicitly separate tracks: **matched-model** where every product supports the same model/version and settings, and **native-product** where each uses its documented supported configuration. Native-product results measure the whole product experience and cannot isolate orchestration from model quality. Preserve native system prompts/tool schemas, record differences and avoid blanket approval bypass. Owner-required approvals are expected interventions; count avoidable re-prompts and manual repairs separately.

## CR-01 — Agent autonomy

**What Raiker must demonstrate.** From one outcome request, inspect inputs, form and revise a plan, use multiple tools, complete dependent steps and verify the deliverable. Continue after an approved action without losing context; handle a recoverable tool error; recognise an actual blocker; stop within the configured budget. Delegation must return child outcomes to the parent without silently dropping calls, increasing permissions or declaring success while a child is unresolved.

**Evidence required.** Run a repository repair and a research-to-artifact task through real Chat/Build entry points. Include an injected recoverable command failure and an approval pause. Retain initial request, full tool/approval/child trace, changed artifacts, independent validators, final response and all interventions. Check every requested deliverable, count abandoned steps and show parent/child terminal states. A supplied patch or scripted model response is component evidence only. Owning contracts: GAP_BUILD_CHAT B1–B8/C1–C3 and release DEC-06/DEC-22.

## CR-02 — Model and deployment flexibility

**What Raiker must demonstrate.** Connect, select, readiness-check and complete a tool-using task on each advertised release configuration: local inference, private-network/home-lab inference and hosted API. Distinguish inference location from the Raiker host and tool-execution location. Switching model must preserve applicable permissions and project context; unsupported tool/vision/context features, disconnects and fallback must be accurately explained. Never silently send local-only work to a hosted fallback.

**Evidence required.** Maintain a release support matrix with OS, application deployment, provider/endpoint class, exact model/version, inference location, tool environment, required configuration and tested features. For every claimed combination retain install/setup transcript, readiness result, one real tool-using completion, restart/reconnect and provider-failure result, redacted routing/egress evidence and fallback decision. A loopback stand-in proves protocol behavior, not a real Ollama installation; an Ollama cloud model is not local inference. File blocked hardware/service combinations explicitly. Owning contracts: model-choice pillar, release DEC-08/DEC-11/DEC-17 and BUG-318.

## CR-03 — Integrations

**What Raiker must demonstrate.** A supported integration can authenticate, read, execute an authorised effect and confirm the result. Test inbound-to-outbound channel completion, correct account/recipient routing, revocation, expired credentials, timeout/rate limit and retry ambiguity. A connector card, successful probe or processed model turn is not proof of an externally delivered action.

**Evidence required.** For every integration advertised as supported, record the native setup flow, granted scope, approval intent, redacted request/response IDs and an independent observation at the destination. Use controlled test accounts/recipients. Include denied execution and revoked access with no resulting effect. For messaging preserve separate received/queued/processed/reply-queued/delivered/failed facts, crash-before-send and lost-ACK-after-send traces, retry count and destination send log. Declare the actual delivery guarantee; do not assume universal exactly-once. A fake transport is failure-injection evidence, not a real-channel round trip. Owning contracts: release DEC-14/DEC-15, BUG-315 and GAP_CHAT C2/C10.

## CR-04 — Memory

**What Raiker must demonstrate.** Recall relevant authorised facts after a full restart and in a new conversation, including paraphrased and instruction-heavy queries. Separate owner/project scopes, identify provenance and use the correct revision. Correction, archive, expiry and deletion must affect subsequent retrieval; unavailable embedding services must produce honest degradation rather than silently losing all useful recall.

**Evidence required.** Freeze a labelled corpus with expected relevant records, distractors, obsolete revisions and forbidden-scope records. Record retrieval precision/recall at a declared k, answer correctness, source IDs/revisions, post-restart persistence and exclusions after each lifecycle change. Include BUG-313's instruction-heavy prompt, a second owner/project and a poisoned source containing instructions. Capture actual context supplied to the model, suitably redacted, as well as the answer: a correct answer alone cannot prove forbidden facts were excluded. Use real embeddings for semantic-quality claims; scripted embeddings test mechanics. Owning contracts: release DEC-13, BUG-313 and ADD-25.

## CR-05 — Scheduling

**What Raiker must demonstrate.** Create and run one-off and recurring work in the owner's chosen time zone, including DST transitions, missed-run policy, restart, overlapping ticks, approval wait/resume, cancellation, bounded failure retries and visible terminal history. Report run completion separately from delivery. Quiet-hours behavior follows the already accepted opt-in/no-bypass default and explicit owner exceptions.

**Evidence required.** Retain schedule inputs, expected local/UTC slots, controlled-clock tests for both DST boundaries, scheduler claim/run IDs and durable state before/after crash/restart. Verify one claim per slot under concurrent ticks and inspect destination side effects separately; an atomic claim alone is not end-to-end exactly-once delivery. Run at least one real host-triggered routine without a browser triggering it, one approval resume and one failure-limit pause/continue scenario. Match card/history/notifications to stored outcomes. Owning contracts: release DEC-12/DEC-21a/DEC-24 and task lifecycle procedure.

## CR-06 — Extensibility

**What Raiker must demonstrate.** An independently authored extension can be installed through documented interfaces, discover its tools, declare scope, perform useful governed work and be updated, disabled and removed cleanly. Exercise each extension family claimed for release: tools, skills, MCP, hooks and plugins. Changed permissions/tool definitions require the documented review; disabling must prevent subsequent execution. Contributed UI must not gain its own execution authority.

**Evidence required.** Retain a minimal external extension fixture, manifest/schema, installation steps, granted scope, discovery and execution traces, result validator, negative authority tests and update/revocation/uninstall behavior after restart. Include an incompatible protocol/schema and malicious instructions in extension output. Record which lifecycle callbacks and UI modes actually execute. Independent authorship means the fixture does not call private Raiker internals to bypass installation. Optional MCP Apps, hook handlers and deployment expansions remain subject to their existing decisions. Owning contracts: ADD-21/ADD-24, BUG-226/BUG-228/BUG-234 and DEC-15/DEC-23.

## CR-07 — Operational control

**What Raiker must demonstrate.** The owner can understand what is running, who/what initiated it, which resource and environment it can affect, why approval is needed and what stopping it means. Exercise existing ask/allow/auto/deny decisions at their real boundaries; re-check authority on resume/retry. Stop must reach streaming turns, tasks and delegated descendants according to the accepted contract; diagnostics, audit export and restoration must be usable without exposing secrets.

**Evidence required.** Map initiator → capability → policy decision → approval/grant → executor → effect → receipt for model, human, scheduled, delegated and contributed paths. Include off/deny, changed-since-approval, revoked credential/grant, Stop and restart tests. Retain audit correlations, process/transport observations and immutable before/after file/effect records. Measure cancellation acknowledgement and cessation separately; document effects already committed before Stop. Record boundaries that cannot be forcibly cancelled and cleanup behavior. A UI disabled button or central router's existence is insufficient proof. Owning contracts: GOVERNANCE_ENTRY_PATHS, security INV-01–INV-07, DEC-16/DEC-24.

## CR-08 — Coding quality

**What Raiker must demonstrate.** Independently solve repository bug fixes, multi-file feature changes, bounded refactors and test additions. Understand the selected repository and working directory, preserve public contracts, use failing-test feedback, produce focused changes and avoid weakening tests to claim success. Review and apply patches safely when targets are ambiguous or stale.

**Evidence required.** Freeze identical repository snapshots and natural-language requests across products. Include at least one task in each class above; keep independent behavioral/regression validators outside the agent's write scope. Retain original failing state, full diff, command/exit-code logs, lint/type/build results relevant to the task, reviewer findings and final commit/artifact. Count task-level success, regressions, unwanted changes and manual corrections. Do not supply the solution patch. Text-edit helper scores and three predetermined repairs do not qualify. Owning contracts: GAP_BUILD B1–B5/B9–B15, DEC-06 and BUG-316.

## CR-09 — Completed work

**What Raiker must demonstrate.** Convert the whole request into an accessible, usable result: implementation plus validation and an accurate handoff, or a clearly stated blocker with preserved progress. Fulfil acceptance criteria beyond producing code; verify generated documents and integration outputs at their destination. Never imply tests ran, publishing succeeded or a task completed when those steps were skipped or failed.

**Evidence required.** Use a requirement-to-artifact checklist independent of the final answer. Open the produced artifact in its intended consumer, exercise the requested behavior, compare completion claims with tool results, and record residual work. Track full completion, partial completion, false completion and time to usable result separately. A patch, a plan or a prose claim alone is insufficient. Owning contracts: GAP_BUILD_CHAT, DEC-06 and DEC-26.

## CR-10 — Ease of use

**What Raiker must demonstrate.** A first-time user can connect a model, reach readiness, start an appropriate Chat/Build task, understand a permission request, correct an error and find the result without undocumented setup or repeated re-prompting. Model/deployment choices and approvals must state concrete consequences in user language.

**Evidence required.** Use a fixed script with at least three first-time evaluators, reporting the small sample explicitly. Record task success, time to first useful result, navigation actions, help requests, avoidable re-prompts and comprehension of model location/permissions. Use identical goals and equivalent initial state across products; separate researcher coaching from independent completion. Retain consented recordings or redacted step logs and exact UI version. Automated clicks alone cannot establish human ease of use. Owning contracts: DEC-02/DEC-03/DEC-05/DEC-08/DEC-09 and current UI procedures.

## CR-11 — Recovery

**What Raiker must demonstrate.** Preserve coherent work after tool failure, provider interruption, refresh/reopen, process restart, approval pause and partial writes. Resume from authoritative state, re-check permissions, avoid replaying already committed effects blindly and explain uncertainty. Checkpoint restore must respect excluded/revoked state and preserve unrelated owner changes; inability to restore must be an actionable state.

**Evidence required.** Inject faults at named barriers: before effect, after effect/before receipt, while waiting for approval, during streaming and during restart. Retain durable pre/post state, process logs, action IDs, file hashes, external-effect log, resume trace and owner-facing message. Assert correct terminal state and no unauthorised replay; explicitly measure ambiguous effects. Include unrelated owner edits and a revoked permission between pause and resume. Run actual process restarts for restart claims. Owning contracts: DEC-24, GAP_BUILD B18, BUG-194/BUG-323 and the security restore invariant.

## CR-12 — Overall polish

**What Raiker must demonstrate.** Consistent navigation, status, terminology and interaction across Chat, Build, Tasks, Approvals, Models and Settings. Loading, empty, error, offline, approval, completion and recovery states must be clear. Keyboard access, focus restoration, accessible names, responsive layout and theme contrast must hold while work is actually running; overlays must not obscure the action they ask the owner to take.

**Evidence required.** Capture the same named journeys at 390, 768, 1440 and 1920 CSS-pixel widths, light/dark themes, keyboard-only use and a declared screen-reader/browser combination. Pair screenshots with interaction assertions, accessibility checks, console/network errors, focus order and task completion. Measure run progress and duplicate/stale notifications through transitions, not only static pages. Keep current evidence under `docs/screenshots/` with a linked run/revision. Static screenshots cannot prove backend completion or overall parity. Owning contracts: DEC-19/DEC-26, ADD-26 and manual global-chrome/responsive procedures.

## Source review and existing evidence baseline

The documentation review used Raiker revision `66ed653b1be33ec0cd35ab9fb7c2405880b82052`. The following are implementation/test anchors, not newly executed test results:

| Criteria | Production anchor | Supporting source/test | Review implication |
|---|---|---|---|
| CR-01, CR-07, CR-11 | [raiker/agents/orchestration.py](https://github.com/sharRahul/Raiker/blob/66ed653b1be33ec0cd35ab9fb7c2405880b82052/raiker/agents/orchestration.py) | [tests/test_turn_resume_after_approval.py](https://github.com/sharRahul/Raiker/blob/66ed653b1be33ec0cd35ab9fb7c2405880b82052/tests/test_turn_resume_after_approval.py) | ScriptedRouter explicitly isolates the loop; real-model competence requires a separate run. |
| CR-02 | [raiker/models/registry.py](https://github.com/sharRahul/Raiker/blob/66ed653b1be33ec0cd35ab9fb7c2405880b82052/raiker/models/registry.py) | [raiker/models/providers/openai_compatible.py](https://github.com/sharRahul/Raiker/blob/66ed653b1be33ec0cd35ab9fb7c2405880b82052/raiker/models/providers/openai_compatible.py) | Registry/transport support is not proof of every endpoint, model or deployment. |
| CR-03 | [raiker/api/routes_channels.py](https://github.com/sharRahul/Raiker/blob/66ed653b1be33ec0cd35ab9fb7c2405880b82052/raiker/api/routes_channels.py) | [raiker/channels/adapters.py](https://github.com/sharRahul/Raiker/blob/66ed653b1be33ec0cd35ab9fb7c2405880b82052/raiker/channels/adapters.py) | _settle_receipt distinguishes processed from delivered; Telegram reply work remains BUG-315. |
| CR-04 | [raiker/memory/retrieval.py](https://github.com/sharRahul/Raiker/blob/66ed653b1be33ec0cd35ab9fb7c2405880b82052/raiker/memory/retrieval.py) | [tests/test_hybrid_memory_retrieval.py](https://github.com/sharRahul/Raiker/blob/66ed653b1be33ec0cd35ab9fb7c2405880b82052/tests/test_hybrid_memory_retrieval.py) | Owner/scope inputs and hybrid retrieval exist; BUG-313 remains relevant to natural-language recall. |
| CR-05 | [raiker/tasks/scheduler.py](https://github.com/sharRahul/Raiker/blob/66ed653b1be33ec0cd35ab9fb7c2405880b82052/raiker/tasks/scheduler.py) | [tests/test_task_scheduler.py](https://github.com/sharRahul/Raiker/blob/66ed653b1be33ec0cd35ab9fb7c2405880b82052/tests/test_task_scheduler.py) | Claim, missed-run and approval-resume paths exist; external side effects need independent receipts. |
| CR-05 | [raiker/tasks/scheduler.py](https://github.com/sharRahul/Raiker/blob/66ed653b1be33ec0cd35ab9fb7c2405880b82052/raiker/tasks/scheduler.py) | [tests/test_routine_failure_limit.py](https://github.com/sharRahul/Raiker/blob/66ed653b1be33ec0cd35ab9fb7c2405880b82052/tests/test_routine_failure_limit.py) | Tests describe bounded repeated failure and owner-scoped continuation; presence is not a fresh passing run. |
| CR-06, CR-07 | [raiker/runtime/authority/entry_paths.py](https://github.com/sharRahul/Raiker/blob/66ed653b1be33ec0cd35ab9fb7c2405880b82052/raiker/runtime/authority/entry_paths.py) | [tests/test_governance_entry_paths.py](https://github.com/sharRahul/Raiker/blob/66ed653b1be33ec0cd35ab9fb7c2405880b82052/tests/test_governance_entry_paths.py) | Inventory and governance tests are the starting point for every new extension/initiator. |
| CR-07, CR-11 | [raiker/runtime/authority/router.py](https://github.com/sharRahul/Raiker/blob/66ed653b1be33ec0cd35ab9fb7c2405880b82052/raiker/runtime/authority/router.py) | [tests/test_stop_all_work.py](https://github.com/sharRahul/Raiker/blob/66ed653b1be33ec0cd35ab9fb7c2405880b82052/tests/test_stop_all_work.py) | The test contract distinguishes owner-scoped active work from already completed effects. |
| CR-08, CR-09 | [raiker/tools/filesystem.py](https://github.com/sharRahul/Raiker/blob/66ed653b1be33ec0cd35ab9fb7c2405880b82052/raiker/tools/filesystem.py) | [web/src/lib/views/BuildView.svelte](https://github.com/sharRahul/Raiker/blob/66ed653b1be33ec0cd35ab9fb7c2405880b82052/web/src/lib/views/BuildView.svelte) | Unique matching and a Build surface do not alone prove autonomous repository repair or correct execution location. |

Existing live rounds include a real Anthropic failing-test → repair → green Build run on 2026-10-03 (third), memory and import work on 2026-10-02 (second), and scheduler/Stop/operational work on 2026-10-05. Preserve their stated scope, stand-ins and limitations in [LIVE_TEST_ROUNDS.md](LIVE_TEST_ROUNDS.md). They are valuable Raiker evidence, not identical cross-product benchmarks; do not reset them to “never tested.”

The earlier external comparison used Raiker `1784b0a42f4e902e852ae08965a966e9f7a7e82f`, OpenClaw `2d3a5c7bbced6f56b4bab7a869415177601ccc4f` and Hermes `7157422022ff06f3e632d1dd394ee1253b17ad37`. It recorded 36 editing component invocations plus nine predetermined repair replays. Those narrow results do not establish live-agent parity, and their raw bundle is not committed here. They must not be cited as release evidence until an accessible immutable artifact/run record is linked. No Codex/Cursor/Claude comparison was executed in that work. This documentation update runs no new product or competitor tests.

## Required evidence record

For each CR criterion and scenario, link one record containing:

- Scenario ID/version; owning BUG/ADD/DEC or explicit no-linked-defect; acceptance conditions; evaluator and reviewer roles.
- Product/version/commit, date, OS/hardware/deployment, interface/mode, model/provider/version/settings, inference and execution locations, enabled extensions and redacted policy configuration.
- Original prompt, fixture hashes, starting state/reset method, expected outcome, validator revision, permissions, time/token/cost limits and declared differences between products.
- Trial count and all outcomes; exact commands, exit codes, traces, approvals, artifacts, independent destination observations, interventions, failures and missing evidence.
- Evidence level plus outcome, unsupported/blocked reason and next action, narrow conclusion, residual risk and the reviewer/date accepting it.

No credentials, tokens, private prompts or sensitive destination content belong in committed evidence. Store redacted artifacts with integrity hashes and an accessible retained location. Redaction must preserve the facts needed to assess the outcome.

## Release and claim gates

1. The release owner declares supported configurations, in-scope CR scenarios, accepted exclusions and success thresholds before execution. Existing release/security gates remain in force; these criteria do not silently expand release scope.
2. Every in-scope release scenario requires end-to-end evidence on the target candidate, or an explicit documented release exception that narrows the claim. Unrun/blocked is not passed. Changed execution paths/configurations require relevant revalidation; old evidence remains historical.
3. Any claim of competitive parity requires the competitive track, disclosed differences, all trial outcomes and a reviewer-approved conclusion limited to measured tasks. Missing comparative evidence blocks that claim, not automatically all product releases.
4. File a reproduced defect once in TO_BE_FIXED; link it here or from its owning plan. Optional expansion remains in TO_BE_ADDED. Do not turn every unmeasured dimension into an invented product bug.
5. Preserve completed implementation and historical evidence. A new validation requirement does not reopen a fixed defect without a reproduction and does not close an existing one by adding documentation.

## Personal-agent qualification — 2026-10-07

[PA-S01–PA-S08](PERSONAL_AUTONOMOUS_AGENT_DELIVERY_PLAN.md#scenarios-to-demonstrate)
add personal briefing, goal persistence, connector effects, proactive usefulness,
isolated browser, reusable workflow, coding and channel continuity scenarios.
Muse.ai and Claude.ai are now explicit personal-work references alongside
OpenClaw/Hermes; Codex/Cursor/Claude Code retain coding scope. Claude's current
help pages describe a gradual unified experience and remote scheduling; record
exact surface/plan/host and distinguish older local schedules.

Use the [reference source index](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md)
and [design adaptations](../architecture/PERSONAL_AUTONOMOUS_AGENT_SPEC.md#reference-ideas-and-raiker-adaptations).
Apply all existing CR evidence rules, five-trial protocol and authority/privacy
zero-tolerance checks. Run only supported equivalent scopes; file unavailable
accounts/regions/models/effects as blocked or unsupported. No Muse or new Claude
comparison has been executed for this documentation update.
