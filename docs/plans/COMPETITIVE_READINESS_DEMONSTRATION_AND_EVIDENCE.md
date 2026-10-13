# Competitive readiness — demonstration and evidence

## Decision and scope

**Status: accepted documentation direction, 2026-10-05; implementation and competitive validation remain separately evidenced.** The owner requested detailed demonstration and evidence requirements across `docs/plans/**`. This document is the canonical acceptance contract, not a second defect ledger and not a claim that Raiker matches any competitor.

**Decision.** Assess Raiker against four explicit reference groups (Meta Muse made a separately testable competitor on 2026-10-12):

| Reference group | Required dimensions |
|---|---|
| **Meta Muse personal AI agent** | Persistent personal goals, owner-aware suggestions, unattended background work, persistent isolated browser/secure VM, cross-app outcomes, delegated subagents/tools, scoped credentials, approvals, privacy and receipts (PA-S01–PA-S06/08; CR-01/03/04/05/07/09–12; RCD-10) |
| Claude.ai / Cowork / ChatGPT Work | Personal assistant usability, project context, connected work and deliverables, scheduling and recovery; name the exact selected product surface (CR-01/03–05/09–12) |
| OpenClaw, Hermes Agent | Agent autonomy, model/deployment flexibility, integrations, memory, scheduling, extensibility and operational control (CR-01–CR-07) |
| Codex, Cursor, Claude Code | Coding quality, completed work, ease of use, recovery and overall polish (CR-08–CR-12) |

For Meta Muse comparisons, identify **the Muse personal agent** (not the Muse Wonder model family or Muse Code), client/device, account tier and available integrations. Meta announced Muse Wonder and Wonder Full on 2026-10-12; new models are not proof of a shipped personal-agent feature. For coding comparisons, identify the exact Codex surface, Cursor mode and Claude Code release. Use the Claude app only for explicitly identified assistant/usability scenarios. A company or model family is not a sufficiently specific test subject. Product names here establish evaluation scope; they do not assert that each competitor supports every scenario.

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
Meta Muse and Claude.ai are explicit personal-work references alongside
OpenClaw/Hermes; Codex/Cursor/Claude Code retain coding scope. Claude's current
help pages describe a gradual unified experience and remote scheduling; record
exact surface/plan/host and distinguish older local schedules.

Use the [reference source index](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md)
and [design adaptations](../architecture/PERSONAL_AUTONOMOUS_AGENT_SPEC.md#reference-ideas-and-raiker-adaptations).
Apply all existing CR evidence rules, five-trial protocol and authority/privacy
zero-tolerance checks. Run only supported equivalent scopes; file unavailable
accounts/regions/models/effects as blocked or unsupported. No Meta Muse or new Claude
comparison has been executed for this documentation update.


## Meta Muse — explicit competitive evidence contract (2026-10-12)

**Reference:** Meta [Muse product](https://ai.meta.com/muse/) and Meta's [safety architecture](https://research.meta.ai/blog/security-and-safety-for-ai-agents-our-approach-with-muse), published September 8, 2026. This is **Meta Muse, the personal agent**, not a generic AI model or a third-party service that happens to use the word Muse. It is an explicit first-tier competitor for **personal autonomous-agent outcomes**, alongside OpenClaw and Hermes; do not assess Muse solely as an LLM.

**What Raiker must demonstrate to be competitive.** A personal goal persists across sessions, breaks into monitored steps, gains relevant and owner-correctable context, takes consented actions through real providers and an isolated browser, can continue on a selected always-on host when the primary UI closes, proposes reusable workflows without increasing its own privileges, and returns independently verified outcomes. Meta's product description states dedicated cloud VM, browser, app connectors, background goals, approvals and agent-generated tools; its engineering post describes host-isolated runtime/credential separation and the independent Sentinel for network and connector actions. Meta's safety design sets a comparison target, **not** evidence that Raiker implements identical kernel- or VM-level controls.

**Evidence required:** PA-S01–PA-S08 must include a **Meta Muse track** in the frozen comparison suite. Record product version/date, actual supported client and plan, region/availability, task permissions, approved accounts, external outcome receipt and read-back, interruptions, time/cost, provider evidence and independent validator verdict. Do *not* score inaccessible plans or undisclosed configurations as competitive failures. Compare real behavior on security cases: prompt injection from an email/page, exfiltration through an MCP tool or browser navigation, credential exposure, SSRF, changed approval arguments, unknown provider commit, revoked grant, Stop and failed/offline host. Distinguish Meta's documented protections from our own executed exploit/fault tests.

**Specific release consequences:** PAA-01/02/03/04 (goal, coordinator, personal context, proactivity), PAA-05/06 (verified integrations and isolated browser), PAA-08 (independent outcomes), PAA-09 (reviewed learning), PAA-10 (cross-device host) and ADD-01/10/12/13 (execution and credential isolation) are the canonical owners. If a feature is not advertised, it need not block a narrower release; if it is advertised, it needs live proof. Source mapping and individual gaps: [Meta Muse comparison](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#9-meta-muse-competitive-track--2026-10-12).

## Competitive decision gap review — 2026-10-12

**Status: recommendations for owner acceptance; not an accepted DEC, an implemented feature, or a benchmark result.** Reviewed against Raiker §CR-01–12, PAA-01–12, current BUG/ADD ledgers and selected executable paths at baseline `23cb971c0065ceadb1ea4d49d3ffbbbb10a9dee3`. Record subsequent code changes before promoting any status. This section narrows decisions about the *next useful product outcomes*, not a second implementation backlog; existing BUG, PAA, ADD, DEC and release gates remain the authoritative work owners.

**Source comparison:** **Meta Muse** [official personal-agent introduction](https://about.fb.com/news/2026/09/introducing-muse-personal-ai-agent/), [security and VM](https://research.meta.ai/blog/security-and-safety-for-ai-agents-our-approach-with-muse/), [product](https://ai.meta.com/muse/), and [Muse Wonder model release, 2026-10-12](https://about.fb.com/news/2026/10/introducing-muse-wonder-models/); Cursor [Cloud Agents](https://prod.cursor.com/help/ai-features/background-agents) and [Bugbot](https://cursor.com/docs/bugbot); OpenAI [Codex remote/worktrees/steering](https://developers.openai.com/blog/mastering-codex-remote-for-engineering) and [repository-specific review rules](https://developers.openai.com/blog/custom-code-review-rules-for-codex); Hermes [cron lifecycle, skill-bound scheduled jobs and delivery](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron/) and [skills](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/creating-skills.md); Claude Code [subagents](https://code.claude.com/docs/en/sub-agents), [hooks](https://code.claude.com/docs/en/hooks) and [checkpointing](https://code.claude.com/docs/en/checkpointing); OpenClaw [architecture](https://docs.openclaw.ai/concepts/architecture) and [sandboxing](https://docs.openclaw.ai/gateway/sandboxing). These are public product descriptions, not matched live tests. Features may vary by plan, provider, version and host; the corresponding CR criterion controls competitive claims.

### Decision gap triage (priority then effort)

| Recommendation | Priority / estimated effort | Verified Raiker boundary or documentation state | Canonical implementation owner | What better must mean |
|---|---|---|---|---|
| RCD-00: reconcile evidence and status | P0 / S | This plan previously used older evidence baselines; the GitHub spec header called a partially implemented feature wholly planned | CR-01–12, PAA-11, implementation-status / release ledgers | One current code-revision-supported product claim, not competing stale statuses |
| RCD-01: verify before declaring complete | P0 / M | `raiker/verification/verifier.py` exists, but [reference matrix §2.1](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#21-agent-runtime-and-execution-loop) describes turn-level verification as advisory; PAA-08 is planned | PAA-08, CR-09/11, DEC-06 | Independently checked artifact/effect and an honest partial/unknown result |
| RCD-02: complete delegated GitHub workflow | P0 / M | `raiker/github/routines.py` is explicitly a template; `raiker/runtime/executors/scheduled.py` executes read-only subagents; BUG-337, BUG-338 and BUG-339 are open | [BUG-337–339](TO_BE_FIXED.md), ADD-27, PAA-12 | Scoped issue → tested change → authorised branch/push → PR with receipt, never implicit merge |
| RCD-03: finish the cross-channel reply loop | P0 / M | [BUG-315](FIXED_ITEMS.md#fixed-888--a-telegram-turns-answer-never-went-back-over-telegram-was-bug-315) records Telegram inbound work without outbound answer | BUG-315, DEC-14, PAA-10 | One authorised inbound instruction leads to one correlated delivery or an explicit failure |
| RCD-04: bind Build to an isolated working tree | P1 / M | [BUG-316](FIXED_ITEMS.md#fixed-890--builds-working-in-named-a-project-whose-folder-build-does-not-work-in-was-bug-316) records project-label vs execution-folder mismatch; no named worktree implementation file was found in this focused tree audit | BUG-316, DEC-04/06, CR-08/11 | Clear path, branch and change isolation before command execution, without mixing concurrent tasks |
| RCD-05: add outcome-validated review automation | P1 / M | Build already has diff review and a code-review skill; an independent continuously verified PR-quality gate was **not established** in this review | DEC-06, ADD-27, CR-08/09 | Precise review findings, reproducible checks, no duplicate noise, human-controlled fixes/merge |
| RCD-06: unify owner-consented proactive triggers | P1 / M | `raiker/tasks/schedule.py` supports timezone-aware slots; PAA-04 event-backed intentions remain planned, and the scheduled executor is read-only | PAA-04, DEC-12/21a, BUG-339 | One lifecycle for time/event triggers, dedup, cooldown, budget and delivery |
| RCD-07: prove memory freshness and correction | P1 / M | `raiker/memory/retrieval.py` preserves source/scope/trust metadata; the owner-facing explicit/inferred personal profile remains PAA-03 work | PAA-03, ADD-25, CR-04 | Relevant, sourced, updatable memory with safe forget propagation |
| RCD-10: demonstrate Meta Muse-style personal-agent outcomes | P1 / M | PAA-01–08/10 define goals, context, proactivity, effects, secure browser and host continuity but remain planned; no Meta Muse matched live test | PAA-01/02/03/04/05/06/07/08/10, CR-01/03/04/05/07/09–12 | A useful goal finishes across trusted apps with durable progress, isolation, approval, verification and accessible handoff |
| RCD-08: learn reusable procedures only after proof | P2 / M | Skill install/review surfaces exist; generating a skill from verified successful personal work is PAA-09 planned scope | PAA-09, ADD-05/06/21, CR-06 | A versioned suggestion that improves later performance without increasing permission |
| RCD-09: remote continuity with honest host semantics | P2 / L | Local-first execution and selected SSH/Daytona adapters exist; general paired-device control/always-on personal agent is PAA-10/ADD-11 future work | PAA-10, ADD-11, DEC-20, CR-05/10/11 | A reachable owner-controlled host, scoped pairing and visible offline behavior |

**Ordering rule:** Within a priority do smaller verified tasks before larger ones; dependencies can override ordering only with a recorded explanation. P0 means important to an *advertised autonomy/completion claim*, not automatically a blocker to a narrower single-user Chat/Build release. An optional browser or 24/7 claim is gated only when advertised. Do not relabel the established BUG severities based on this comparative prioritisation.

### RCD-00 — A product claim must match one current implementation baseline

**Recommended decision:** Treat the newest *executable entry point + test/live outcome + revision* as the status authority; treat older compatibility matrix rows as dated research, not proof of today's implementation. Revise the canonical status and user guide when implementation changes, or tag the precise contradiction as documentation drift. Never replace a closed BUG with an open feature request or count a planned PAA item as shipped.

**Why:** GitHub sign-in, credentials, repositories, delegation and Settings reached implementation in October, while the opening banner in `GITHUB_CONNECTION_SPEC.md` still said “Implementation Planned”. Conversely `IMPLEMENTATION_STATUS.md` contained an old “checkpoint restore is a known gap” paragraph after the route and CLI restore work closed in August. Stale readiness is itself a product risk.

**Rejected:** Duplicating feature truth in another master spreadsheet; counting component tests as live provider validation.

**Acceptance:** Automated cross-check of named entry points, capability flags, test pointers, open BUG links and candidate revision. Assertions distinguish implemented against fakes from tested against GitHub/Ollama/Telegram. CR evidence levels and RR scenarios stay explicit.

### RCD-01 — Completion requires independent verification, not a confident answer

**Recommended decision:** A consequential task may report `completed_verified` only after checking its declared acceptance conditions against the actual destination. Keep `completed_unverified`, `partially_completed`, `blocked` and `outcome_unknown` distinct in the durable run ledger, API and UI. A validator cannot be the same model statement that claimed success; use test execution, read-back, hashes, external IDs and independent checks as appropriate. Preserve evidence of both successful and failed attempts.

**Why / competition:** Codex and Cursor are judged by tested code and reviewable artifacts, not merely produced patches. Raiker already has verification classes but lacks proof that their verdict gates all user-visible completion paths. This is a strengthening of PAA-08 and CR-09, **not** a request for a second runtime.

**Rejected:** Marking a task done on the final LLM text; automatic retry of an external effect with an ambiguous first outcome.

**Acceptance:** A failing hidden test, a file saved to the wrong location, a provider timeout after a write and a missing read-back each prevent `completed_verified`. Inject restart between effect and receipt; reconcile without repeating an irreversible action. Show the exact remaining work on Chat, Build and Tasks.

### RCD-02 — GitHub autonomy is a reviewable, bounded workflow

**Recommended decision:** Implement BUG-337, BUG-338 and BUG-339 in that dependency order: bind local branch/commit authority to a selected remote when applicable; re-check repository/installation identity with the provider before consequential delegated steps; then execute a narrow issue-to-PR flow under an **owner-created** repository delegation. The flow must reserve a dedicated branch/workspace, inspect the issue as untrusted content, apply a focused change, run required tests, inspect the diff, request a push/PR action covered by the delegation and verify the PR ID/URL. Merge, repository settings and protected-branch actions remain human-only.

**Why / competition:** Cursor Cloud Agents can produce PRs, and Codex workflows can lead to reviewable changes. Raiker has most primitives but an explicit missing runner. A feature named “issue-to-PR automation” is not delivered by the existence of `ISSUE_TO_PR_STEPS` alone.

**Rejected:** Using the owner's broad OAuth connection as consent; letting a schedule mint or widen its own delegation; treating git push output as proof a PR exists.

**Acceptance:** RR-39/40 and PA-S07 on a consented repository with wrong repository, transferred repository, expired installation, branch collision, hidden failing tests, approval pause, interrupted push, retry, and duplicate webhook. An owner can revoke before execution and prove no further write; no scheduled agent merges.

### RCD-03 — An inbound channel turn must have an independently verified outbound result

**Recommended decision:** Model inbound receipt, processing, outbound send and provider acknowledgement as separate correlated effects. Carry owner and sender scope across the turn; enforce destination policy and quiet hours before delivery; after an ambiguous timeout reconcile by provider message ID where supported, otherwise report unknown instead of blindly resending. A parked approval must not look like a delivered answer.

**Why / competition:** OpenClaw and Hermes are used through messaging gateways. Raiker's inbound Telegram path is real while BUG-315 says the answer is not sent back. Fixing this improves autonomy more than another decorative channel integration.

**Rejected:** Copying the final answer into a “sent” audit event with no provider acknowledgement; allowing a different chat/account to receive a delegated result.

**Acceptance:** A real paired Telegram test produces one same-thread answer and linked delivery ID. Exercise duplicate inbound updates, replay, send refusal, provider outage, receiver disconnect, quiet hours and an owner Stop. Reopen the dashboard and see exactly whether it was delivered, held or unknown.

### RCD-04 — Project selection must select where code *actually* runs

**Recommended decision:** Name and enforce an execution target (host, workspace root, repository identity, branch/worktree and sandbox posture) **before** a Build turn starts. For parallel write-capable tasks prefer separate worktrees with branch ownership and safe cleanup; for a single task use the owner-selected existing checkout if explicitly chosen. Bind commands, file reads, diffs, checkpoints and PR receipts to the same target; refuse path traversal or a stale/moved target. This extends BUG-316 instead of obscuring it with a label change.

**Why / competition:** Codex remote control exposes host/worktree choice; Cursor isolates cloud coding runs. Showing “Working in Project X” while running commands elsewhere is a correctness problem and defeats reliable multi-task coding.

**Rejected:** Silently changing the process working directory; one shared mutable checkout for concurrent agents; cleaning up a branch containing unreviewed owner changes.

**Acceptance:** Two concurrent tasks touching the same filename never overwrite one another; the displayed location matches actual executor and diff; a resume validates the workspace fingerprint; owner changes outside the worktree survive cancel/rollback. First run against Linux and Windows-supported paths.

### RCD-05 — Code review must detect problems without fabricating quality

**Recommended decision:** Define a review pipeline over an exact commit/diff and repository instructions: static and secret checks, policy/architecture rule checks, independent test/validator runs, model review where selected, severity and confidence, linked line/range and fix proposal. Store findings per patch fingerprint and deduplicate across repeated review; allow a bounded *proposed* repair on a fresh branch, but require existing policy/approval and never merge automatically. **Discovery prerequisite:** first inventory the existing code-review skill, Build diff view and GitHub connector to avoid adding a parallel reviewer.

**Why / competition:** Cursor Bugbot offers event-triggered PR review and bounded autofix; Codex supports repository-specific review rules. Raiker's human diff review is useful but does not by itself establish parity with a verified PR reviewer.

**Rejected:** Treating model-generated findings as proven vulnerabilities; spamming duplicate PR comments; infinite review↔fix loops; privileging a repository instruction over Raiker policy.

**Acceptance:** Seed known correctness, regression, secret and prompt-injection cases plus false-positive controls. Measure precision, recall on the fixed set, duplicate rate, runtime and useful accepted fixes, with exact model/version/budget. Confirm no GitHub comment or patch appears without selected authority.

### RCD-06 — Triggers should reuse one governed routine engine

**Recommended decision:** Extend PAA-04 with one trigger envelope across scheduled times, supported provider events and owner-authorised manual re-runs. Use stable deduplication keys, local zone/DST rules, missed-run policy, lease/claim, max attempts, per-run model/skill selection, aggregate spend, cooldown and delivery target. Start with read/draft tasks; enable a write-capable routine only through the exact delegation design of RCD-02. A simple no-model script is optional and must still pass the same host/tool policy.

**Why / competition:** Hermes supports skill-bound scheduled jobs, event triggers and delivery options. Raiker's timezone-aware scheduler is substantially stronger than the old four-cadence comparison row suggests, but the personal proactive effect path is not yet one end-to-end verified product.

**Rejected:** A new cron daemon separate from Tasks; recursive routine creation by a routine; interpreting missing host power/network as a successful run; spending beyond approval pauses (BUG-325).

**Acceptance:** Duplicate/out-of-order events produce one outcome, DST works, an offline host reports missed slots, quiet hours hold or digest notices, retries respect spend and Stop, and a revoked connector prevents the next effect. Include real provider event/delivery receipts before calling it end to end.

### RCD-07 — Persistent personal context must be correctable and provenance-rich

**Recommended decision:** PAA-03 should separate explicit owner-stated facts, inferred observations, project-scoped preferences and stale third-party data. Store source, observation time, last validation, confidence, sensitivity, scope, retention and supersession chain. An inferred fact may help rank a suggestion but must not become permission. Show why a memory was retrieved; owner correction/forget must invalidate derived summaries and embeddings according to retention policy.

**Why / competition:** Hermes and OpenClaw emphasize persistent memory; Raiker already has hybrid retrieval and governance metadata. The differentiator is **demonstrable correctness and user control**, not simply longer retention.

**Rejected:** Automatically promoting every chat assertion to global profile truth; treating stale memories as source-of-truth; a hidden model-only “forget” instruction.

**Acceptance:** Conflicting facts, changed timezone, wrong project, revoked source, deletion and restore cases. Measure contextual retrieval quality and latency on a frozen corpus; demonstrate that forbidden/forgotten facts do not reappear in summaries or generated tasks.

### RCD-10 — Match Meta Muse on finished personal goals, not marketing features

**Recommended decision:** Treat [Meta Muse](https://ai.meta.com/muse/) as a **first-class, separately named personal-agent competitor**. Its documented product journey includes persistent goals, proactive assistance, background continuation after closing an app, long-lived isolated browser/VM, cross-application actions, owner permissions and auditable actions. The agent should be compared to Raiker's personal-goal orchestration (PAA-01–08), while Muse Code and the newly announced Muse Wonder models remain separate products/model offerings and cannot stand in for the agent in a parity claim.

**Why / code and product boundary:** Meta's [September 8 product introduction](https://about.fb.com/news/2026/09/introducing-muse-personal-ai-agent/) describes the end-user agent and [engineering security description](https://research.meta.ai/blog/security-and-safety-for-ai-agents-our-approach-with-muse/) describes the Sentinel-enforced secure VM and separate credential handling. Meta's [October 12 Muse Wonder announcement](https://about.fb.com/news/2026/10/introducing-muse-wonder-models/) newly claims Active Memory and Active Focus in its models; these are **model claims**, not measured performance of Muse personal-agent workflows. Raiker's durable-goal coordinator, user-editable context, proactive event triggers, browser executor, verified external effects and always-on pairing remain distinct planned PAA slices; a basic tool registry or memory index does not close those gaps.

**Recommended implementation and integration direction:** Reuse the existing Raiker policy/broker, tasks, approvals, memory, connectors, event journal and budget/Stop controls. Build a small governed goal journey before introducing broad new integrations: goal acceptance/plan, personal-context lookup with provenance, background scheduler with truthful host readiness, safe read/plan via browser or connector, exact-effect human approval, destination read-back and a clear progress/receipt view. Compare authorization trade-offs explicitly: Raiker's local-first/owner-chosen models versus Meta's cloud-hosted Secure VM; neither architecture alone proves better security. A sensitive domain (finance, legal/health decisions, purchases) stays outside executable scope until independently approved; do not enable payment or credential-sharing features merely to mimic Muse.

**Rejected:** Copying Meta's deployment/cloud data model into Raiker without owner choice; replacing exact approval with inferred intent; calling a model memory claim verified cross-session recall; treating browser click success as a confirmed provider effect; shipping unreviewed self-modifying tools; making all Muse capabilities a mandatory first-release blocker.

**Evidence required:** Add an **explicit Meta Muse track** to PA-S01 (consented inbox/calendar briefing), PA-S02 (multi-day persistent goal), PA-S03 (connector create/read-back), PA-S04 (proactive monitor), PA-S05 (isolated browser), and PA-S08 (channel and offline continuity); include approvals, privacy, app closure/reopen, changed instructions, denied actions and host loss. For each scenario, pin Muse app/client/version/tier and Raiker SHA/model/host, same achievable fixture and independent success validator. Record permission prompts, provider receipts, completion quality, duration, interventions and cost where observable, with platform-side measurement gaps marked unknown. Run five trials where possible; use blocked/unsupported for unavailable Muse accounts/features, not invented results. Claims of parity or superiority need both products' real runs plus CR-01/03/04/05/07/09–12 scorecards. **No live Meta Muse run or benchmark was executed in this documentation change.**

**Security and isolation evidence:** In addition to goal success, compare effective protections against untrusted page/email input, network exfiltration, SSRF, raw-token exposure, changed approval scope, cross-account action and ambiguous external commit. Meta's documented Sentinel, credential surrogation and isolated runtime are reference requirements, not Raiker features without executable fault tests. Tie implementation to PAA-06, ADD-01/10/12/13/23 and BUG-194; record the actual OS/host/isolation mode.

### RCD-08 — Self-improvement is a suggested skill, never self-granted authority

**Recommended decision:** Capture a reproducible successful procedure and propose a versioned skill with inputs, output validator, minimal permissions, evidence links and a rollback point. Require explicit owner activation when code, new tools, schedule or permissions are introduced; suggestions may be inspected or dismissed. Run the candidate on a separate held-out fixture before declaring it better. Do not enable self-authored hooks or scripts through a trusted-sounding skill description.

**Why / competition:** Hermes exposes reusable skills and suggestion/blueprint workflows. Raiker has Agent Skills support and governed skill controls, but PAA-09 remains planned for learning from verified personal work.

**Rejected:** Unreviewed skill auto-install, autonomous authority expansion, evaluation on only the example used to generate the skill.

**Acceptance:** A repeated workflow demonstrably improves success/cost/latency on fresh inputs, and malicious skill metadata, revoked permission, rollback, plugin update and schedule creation are handled through their existing boundaries.

### RCD-09 — Remote control is an explicit deployment decision, not a false promise of 24/7

**Recommended decision:** Preserve local-first single-owner deployment. Later offer a selected always-on private host and explicitly paired remote control device, with identity-bound sessions, end-to-end authenticated commands, queue/steer/Stop and live host health. Disclose where code and data actually run and what cannot happen when the host is offline. Keep hosted multi-user service out of scope until DEC-20 is revisited.

**Why / competition:** Codex remote, Cursor Cloud Agents and OpenClaw/Hermes gateway patterns reduce the need to leave a laptop open; Raiker has pieces of a host/execution foundation but not a validated comparable personal remote-control experience.

**Rejected:** Calling a locally scheduled task a cloud task; silently routing private work to a third-party host; exposing the owner control plane unauthenticated.

**Acceptance:** Pair, revoke, reconnect, failed host, stale approval, cross-account spoof, network partition, resume and Stop on each declared OS/device. An offline test must show a trustworthy unavailable state, not a fabricated completed job.

### Implementation and claim discipline

* **No duplicate backlog IDs.** RCD is a decision-gap reference, **not** a second implementation task identifier. File newly observed failures in `TO_BE_FIXED.md`, extensions in `TO_BE_ADDED.md` or the owning PAA plan, and verified closures in `FIXED_ITEMS.md`. If a proposal needs a separate task, link it from its canonical owner and put the acceptance evidence there.
* **Do not claim product parity yet.** Each RCD must close with a production reachability check, negative/authority checks, a real applicable provider/host outcome and the CR matched-task benchmark. An external provider stand-in is component proof only.
* **No broad security regression.** Approval, capability gates, owner identity, scoped credentials, revocation, cost ceilings, audits, isolation, provenance and Stop remain enforced. Connecting a model, GitHub account, plugin or channel **never** grants a write by itself.
* **Owner sign-off pending.** This review records recommended choices, reasons and rejected alternatives; existing accepted DEC/PAA/BUG statuses remain unchanged. Promote a proposed choice to accepted only with an explicit owner decision and update its canonical plan accordingly.
