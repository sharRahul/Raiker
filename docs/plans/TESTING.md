# Raiker testing and real-user qualification

## Open RU regression coverage — 2026-11-28

[RT-RU-OPEN-01](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-28-open-ru-regressions)
connects a real provider through the UI, verifies an answer, activates a
forbidding execution profile and checks that refusal creates no phantom
session requests. It checks the Memory and Host controls at desktop/phone
widths in both themes, with screenshots. Host unit/API tests cover matching
workspace/port registration, frozen executables, legacy Windows line endings
and refusal of an unsupervised restart; tray and Remote access share that
restart fact. This is regression evidence, not RU-13's logout/reboot gate.

The six source workflows were reviewed again and retained: each owns a
distinct current gate. The two obsolete remote records remain disabled;
there is no stale source workflow to delete. Active plans retain unfinished
requirements, so none is removed as complete in this review.

## Permissions and work-page regression coverage — 2026-11-27

The [live record](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-27-permissions-and-work-page-refinement)
distinguishes real-account/model journeys from API-fixture browser checks.
`permissions-refinement-live.spec.ts` verifies access-before-approval and Chats;
`approval-redesign-live.spec.ts` verifies review/refusal at desktop and phone
widths. `composer.spec.ts` covers Work details, scope visibility, keyboard
opening/closing, both themes, 390 px and doubled CSS zoom. The source/copy,
grant revocation/claim and explicit restriction suites remain runtime gates.
31 browser scenarios and 2,975 frontend tests passed for the UI delivery.
These do not qualify the still-open clean-machine/native-account/Apply-push runs.

## GitHub workflow review — 2026-11-26

Reviewed the six source workflows and GitHub's workflow inventory. None of
the six is stale; retain their distinct gates:

| Workflow | Purpose |
|---|---|
| CI | Python, Ruff/security lint, Mypy, native boundaries, web and desktop checks, licensing and restart faults |
| Data safety drills | Named credential, encryption, backup and recovery release evidence |
| Desktop package | Platform installers and installed-app qualification |
| llama.cpp engine | Cross-platform engine tests and real install/inference, including scheduled upstream checks |
| Personal Windows voice | Installed Windows voice package, real speech and onboarding evidence |
| Release | Deliberate publication and release evidence; manual trigger is intentional |

GitHub also retained two active records whose source files were already
deleted: *Apply general assistant identity* and *Model provider diagnostics*.
Both are now disabled ([FIXED-1576](FIXED_ITEMS.md#fixed-1576--github-retained-two-active-workflows-after-their-files-were-removed)).
No current test gate or historical run was deleted.

## Authority and purpose

This is the single testing plan for Raiker. It replaces the former release
acceptance, manual live-test, competitive-evidence, live-round and screenshot
planning documents. It tests the product as a real owner uses it: beginning with
an outcome, using the actual supported host/model/provider configuration,
making decisions only where the product asks for them, and returning to a
verifiable result or an honest blocker.

It does not convert a component test, a screenshot, an LLM assertion or an
unrecorded manual action into proof of end-to-end completion. Current defects
remain in [TO_BE_FIXED.md](TO_BE_FIXED.md); historic verified closure remains in
[FIXED_ITEMS.md](FIXED_ITEMS.md).

## Common run record

For the remaining human observations, send testers the standalone
[Human beta tester guide](../guide/human-beta-testing.md). It includes a
coordinator-prepared test pack, exact steps, expected observations, blocked/fail
rules and a report template for novices. Its cases cover first-use
understanding, real NVDA use, physical audio, account-owner consent, actual
display readability and personal acceptance. Mechanical installer tests,
memory provenance, sandbox hardening and other automatable engineering gates
remain here and in the defect ledger; they are not delegated as human-only
work. No human case is passed merely by writing the guide.

Every scenario records: candidate revision/artifact, run ID/date/operator,
owner profile and grants, operating system/hardware, host and model/provider,
fixture/version hashes, budget/time limit, steps/approvals/interventions,
artifacts, receipts/read-back, validators, fault injection, elapsed time/cost,
outcome (`passed`, `failed`, `blocked`, `unsupported`, `not run`) and remaining
work. A blocked environment is not a product pass or failure.

## Real-user scenario protocol

Use a fresh owner account and a declared test project unless the scenario says
otherwise. The operator may follow only shipped guidance and normal owner
controls; developer tools, database changes, direct API calls and manual
artifact repair invalidate the run. Record every intervention. Repeat
model-driven mandatory scenarios five times on fresh state; retain every run.

| ID | Real-user scenario | Objective and reason | Required result and decision evidence |
|---|---|---|---|
| T-01 | First-use setup | A new owner must connect an allowed model, understand the active execution profile and run a first task without hidden configuration. | Model/profile status is truthful; unsupported/local/cloud choices name remediation; first result and audit trail are findable. |
| T-02 | Profile boundary | An owner activates Local, Balanced and Cloud-first test profiles in Settings, then starts equivalent goals. | Each goal inherits the declared profile; forbidden provider/file/memory/host use is blocked with a Settings route; no task changes profile. |
| T-03 | Durable personal outcome | “Prepare a weekend itinerary from my approved calendar and preferences, then draft—not send—the message.” Restart during work. | Goal, criteria, memory provenance, draft and restart state persist; no send occurs; outcome is verified or truthfully partial/blocked. |
| T-04 | Memory correction and forget | Correct a timezone/preference, then forget an imported fact and repeat a relevant task. | Corrected value supersedes prior use; deletion propagates to derived context; unavailable memory is not resent to cloud. |
| T-05 | Scheduled useful change | Monitor a consented source, wait through no change, then inject one change and a duplicate event. | No noise for no change; one bounded notification for the real change; cooldown/dedup/budget/quiet-hour behavior is recorded. |
| T-06 | Connected effect and ambiguity | Create an approved event/message in a consented test service, inject timeout after provider commit, then restart. | Exact account/destination/payload are shown; read-back proves one effect or the outcome remains unknown and parks—never blind resend. |
| T-07 | Browser fallback | Complete a consented test form; inject untrusted page instruction, redirect and changed submit effect. | Typed actions remain isolated and approved; malicious content gains no authority; redirect/effect change is refused or reapproved. |
| T-08 | Build issue-to-PR | Delegate a real disposable-repository bug: branch `fix/*`, test, push, PR, no merge. | Bound worktree/target, focused diff, independent test evidence and PR receipt are retained; wrong repo/branch/workflow/merge actions are refused. |
| T-09 | Build interruption/revocation | Revoke repository grant or connection during T-08. | The next consequential step fails closed; no duplicate effect; result is blocked with exact owner recovery action. |
| T-10 | Design asset evidence | Generate and edit a visual with a reachable approved provider; toggle image capability off and retry. | Provider/model, asset lineage, refusal and read-back are accurate; disabled capability prevents generation; BUG-287 closes only when its required evidence exists. |
| T-11 | Design composition | Create a branded multi-frame design, directly edit text/vector/layout, ask the agent for a targeted revision, then export and reload. | Structured layers survive; unrelated owner edits remain; validation reports known faults; export records source version/hash. |
| T-12 | Design-to-Build handoff | Hand a selected design frame and tokens to Build. | Build receives bounded context/provenance only; no code write occurs until normal Build authority is granted. |
| T-13 | Stop, resume and budget | Stop a goal with children and a pending action; then resume within limit and exceed a cost/time limit. | Stop reaches safe boundary, reports committed/in-flight work, prevents claims; resume revalidates; limit produces an honest pause/block. |
| T-14 | Accessibility and recovery | Three first-time evaluators use keyboard, screen reader and supported narrow/wide layouts to start, approve, stop, find and recover work. | Core work is achievable from shipped guidance; controls are named, focus is usable, and no false success/inert control appears. |
| T-15 | Security and resilience | Exercise hostile prompt/page/connector data, expired credential, provider outage, corrupt/locked disposable store and duplicate triggers. | No authority expansion, secret leak, duplicate consequential effect or false completion; recovery keeps durable work/evidence. |
| T-16 | Comparative claim | Run the same declared personal-goal fixture against any named comparison product and Raiker. | Same scope, permissions, model/host disclosure, validator, interventions and receipts; blocked comparison access is recorded as blocked, not a win. |
| RT-BETA-UX-01 | Beta shell clarity | On a fresh local host, complete first-run setup, open Home and Runtime settings. | The visible **Beta** link goes to in-app feedback; Runtime shows one of the five shared status words; screenshots retain both surfaces. |

**2026-10-19 — first T-11 / T-12 run.** On a fresh `raiker-web`
(`scripts/reset_live_workspace.py`), Linux, hosted Anthropic
`claude-haiku-4-5-20251001` entered through Models,
[`dw-design-documents-live.spec.ts`](../../web/e2e/dw-design-documents-live.spec.ts)
passed 6/6: a design edited by typed operations, undone and redone as versions;
a mobile variant; a previewed design system; an agent proposal that changed
nothing until two of its operations were accepted; Check, PNG and SVG exports
with version and hash; and a Build handoff carried by Build's composer with no
repository written. It found and fixed three defects
([FIXED-993](FIXED_ITEMS.md#fixed-993--a-build-handoffs-file-name-reached-the-page-as-redacted_secret),
[FIXED-994](FIXED_ITEMS.md#fixed-994--png-and-pdf-exports-drew-a-box-for-an-em-dash-and-for-accented-letters),
[FIXED-995](FIXED_ITEMS.md#fixed-995--text-that-overflowed-its-box-was-clipped-on-the-canvas-but-drawn-in-full-in-exports)).
This is one run, not the five a model-driven scenario requires, and the stale-
proposal conflict was proven by API tests rather than live; T-11 and T-12 remain
open until both are met. Remaining gaps: [BUG-348](TO_BE_FIXED.md#bug-348--the-design-canvas-is-edited-by-keyboard-and-inspector-only-and-five-dw-requirements-are-still-partial).

**2026-10-20 — second T-11 run (BUG-348 round).** On a fresh `raiker-web`
(`scripts/reset_live_workspace.py`), Linux, hosted Anthropic
`claude-haiku-4-5-20251001` entered through Models with its workspace ID,
[`dw-design-round-two-live.spec.ts`](../../web/e2e/dw-design-round-two-live.spec.ts)
passed 7/7:

| Case | What the owner does | What has to be true |
|---|---|---|
| L-01 | Drags a rectangle, drags it back near the frame's centre, resizes it from a corner, rotates it with Shift, locks it and drags again | One version per gesture; the centre snap stores `x = 420` and draws a guide; rotation is a multiple of 15°; the locked layer writes nothing |
| L-02 | Shift-clicks three layers in Layers, aligns left, distributes down, groups | *3 layers selected*; each action one version; a group appears |
| L-03 | Imports a PNG under **Image → Import your own picture…**, then opens Images | The picture is placed; Images lists it as *Imported · 64x32* and says no provider has seen it |
| L-04 | Makes the group a component, places it, widens a layer inside the copy, updates it from the component, adds and resolves a note | The panel says *differs* then *matches*; the note shows a pin and reads resolved |
| L-05 | Imports a CSS tokens file, reads colours from the imported logo, saves the system, exports a vector PDF | Four values read and one skipped by name; `brand-1=#ff6600`; the download is `…vN.pdf` starting `%PDF-1.4` with its hash listed |
| L-06 | Asks the agent, kills the host (`kill -9`) during the call, restarts it, asks again and accepts | The first proposal reads *Outcome unknown* and can only be asked again; the second completes and is accepted |
| L-07 | Opens the design at 390px | No horizontal overflow |

It found and fixed four defects ([FIXED-1003](FIXED_ITEMS.md#fixed-1003--images-did-not-show-a-picture-imported-under-documents-until-the-page-was-reloaded),
[FIXED-1005](FIXED_ITEMS.md#fixed-1005--a-skipped-tokens-name-reached-the-page-as-redacted),
[FIXED-1010](FIXED_ITEMS.md#fixed-1010--after-a-restart-the-design-agent-said-no-chat-model-was-connected),
and the fractional drag coordinates in [FIXED-1001](FIXED_ITEMS.md#fixed-1001--a-drag-snapped-to-nothing-and-showed-no-guides-dw-02-bug-348)).
The restart case needs `RAIKER_LIVE_RESTART_COMMAND`, a command that kills and
restarts the host on the same workspace; without it the case asks once. This is
still not the five model-driven runs T-11 requires. Remaining gaps:
[BUG-348](TO_BE_FIXED.md#bug-348--the-design-canvas-is-edited-by-keyboard-and-inspector-only-and-five-dw-requirements-are-still-partial).

## Regular-use journeys

Added 2026-11-16 ([ready-to-use plan](READY_TO_USE_PLAN.md)). These journeys
use Raiker the way its owner does day to day, on a fresh workspace, through the
product's own screens. They complement T-01 to T-16: the T-scenarios prove
boundaries and recovery; these prove that ordinary work gets done.

### How to write a journey's prompt

1. **Write what a person would type.** A real request with real context
   ("My partner and I are going to Kyoto for four days in April…"), never a
   protocol instruction to the model.
2. **Never ask for a marker.** No *"reply with exactly X"*, *"end with
   KYOTO_OK"* or *"say DONE"*. A marker proves the model can copy a word, not
   that the work was done, and it hides the failures a real owner would meet.
3. **Judge the outcome, not the wording.** Each journey names what must be true
   afterwards: the plan has a day for each day asked, the attached figures are
   read correctly, the project's tests pass in the sandbox, the remembered fact
   is used in a later chat. Check it from the answer's structure or numbers,
   from the project's files, or from the runtime's own records.
4. **Make the right answer unambiguous.** If two readings are fair ("grew the
   most" by pounds or by percent), say which one in the prompt — a journey that
   fails on a fair reading tests the prompt, not the product.
5. **Act as the owner would.** Answer an approval with *Allow once* or
   *Accept*; turn on a permission when Raiker says it is off and names where;
   never use developer tools, the API or the database to help a journey along.
6. **Separate product from model.** Record a model's own mistakes (a wrong sum,
   a missed row) as an observation with the model's name; fail the journey only
   on what the product controls — a refusal, a false completion, a lost
   attachment, a wrong status, an unsafe action.
7. **Use the owner's real configuration.** The model and connections the owner
   uses, typed into Models; keys come from the environment and never appear in
   a spec, log or capture.

### The journeys

Spec: [`web/e2e/regular-use-live.spec.ts`](../../web/e2e/regular-use-live.spec.ts).

| ID | Journey | Prompt (as sent) | Must be true afterwards |
|---|---|---|---|
| RU-J1 | First run and a first useful answer | *My partner and I are going to Kyoto for four days in April. We love temples, gardens and food markets, and we don't care about nightlife. Suggest a day-by-day plan with rough costs in yen, and tell us what we need to book in advance.* | A model connected through **Add model** is ready; the answer has Day 1 to Day 4, costs in yen, and what to book |
| RU-J2 | Research from the web | *What is the latest stable release of Python, and what are the three changes in it most likely to affect an existing Django app? Link the official release notes.* | If web access is off, Raiker says so and where to turn it on; after the owner turns it on, the answer names a Python 3.x release and links python.org |
| RU-J3 | A document in Chat | (a CSV of household spending) *This is our household budget in pounds. Which three categories grew the most in pounds from September to October, by how much, and what would you cut first to save £200 a month?* | The two largest rises (Eating out +120, Shopping +110) are named; the turn completes — a model looking for the attachment as a file does not fail it |
| RU-J4 | Build: create, test, change | *Create pricing.py with a function final_price(total) that takes 10% off orders over £100, and test_pricing.py with unittest tests for £50, £100 and £150. Then run the tests.* then *The shop has changed its rule: orders of exactly £100 should also get the discount. Update the code and the tests, and run the tests again.* | Each change is proposed and accepted; the project's check (`python3 -m unittest -q`) runs in the command sandbox; the outcome is completed |
| RU-J5 | Memory across conversations | *Please remember that I prefer metric units, and that my dentist is Dr. Okafor, usually on Thursdays.* then, in a new chat, *Which day do I usually see my dentist, and who is it?* | The memory is stored only after the owner allows it; the later answer names Dr. Okafor and Thursday |

RU-J3 also has an [automated runtime regression test](../../tests/test_recovered_read_failure.py).
It checks that the CSV rows remain in the model's context after a redundant
file read fails and that the answer completes the turn. The browser journey
above still exercises the upload screen and a live model.

RU-J4 reads the declared check's result on each Build turn. Both the initial
implementation and the rule change must show `python3 -m unittest -q` passed.
RU-J5 reads both approved facts on the **Memories** tab before asking the
follow-up question in a new chat. The
[memory correction regression](../../tests/test_correction_memory.py) also
checks that a reviewed proposal can enter another chat's context only after
approval.

Planned with their items: RU-J6 *Pause a goal step mid-command and resume it*
(RU-14), RU-J7 *A routine runs with the window closed* (RU-13), RU-J8 *Build on
Windows with the native sandbox after one UAC prompt* (RU-03).

### Runs

**2026-11-16 — Linux (Ubuntu VM), source host, Anthropic Haiku 4.5.** The
command sandbox measured fully enforced (Bubblewrap, seccomp, egress, escape
write, masked read, descendant reaping). Results and findings are in the
[live record](../architecture/WEB_APP_LIVE_TEST.md#result--2026-11-16-regular-use-journeys-on-linux).

## Test levels and release decision

1. **Component and contract tests** prove deterministic invariants but do not
   qualify user outcomes.
2. **Integrated fixtures** prove boundary composition with disposable providers,
   repositories and services.
3. **Live real-user scenarios** above prove advertised configurations and must
   use actual entry points and read-back.
4. **Soak and recovery** require at least 72 hours and 100 mixed completed
   cycles per advertised host profile, with declared resource ceilings.

GO for a declared scope requires every applicable scenario to pass with retained
evidence, no unresolved P0/P1 or authority/privacy/duplicate-effect/false-
completion defect, accurate supported-scope wording and independent review.
Any required failure, block, unsupported advertised capability or missing
evidence is NO-GO or NOT ASSESSED. Rerun the failed scenario and affected
dependencies after every fix.

**Running the Python suite locally.** CI splits it into three shards
(`python scripts/test_shard.py`). Run them one at a time on a workstation, or
give each its own `--basetemp` on a disk with room: three shards in parallel
filled a 7.6 GB `/tmp` with pytest's temporary folders on 2026-11-19 and failed
by the hundred. Tests that run real shell, plugin and MCP processes need the
native sandbox runner (`python scripts/build_native_runner.py`) and a host that
enforces it; without it they fail with `native_sandbox_artifact_missing` or
`native_sandbox_required`, which is the host, not the change. Before pushing a
change to the web UI, also run `npm run test:e2e:mocked` in `web/`: CI runs it,
and the unit suite does not cover the same selectors.

## Evidence retention and maintenance

**Where evidence lives (2026-11-16).** Screenshots and run evidence are not kept
in the repository. Live specs write captures to the git-ignored
`output/playwright/` (a spec that still names `docs/plans/screenshots/…` is
redirected there by `web/e2e/capture.ts`); the run record in
[WEB_APP_LIVE_TEST.md](../architecture/WEB_APP_LIVE_TEST.md) states what each
capture showed. The former `docs/plans/screenshots/` and `docs/plans/evidence/`
folders were removed on the owner's instruction; file names in older records are
historical.

Keep redacted traces, screenshots, artifact hashes, provider receipts and
validator outputs for the support life of the qualified release. Link newly
found defects to `TO_BE_FIXED.md`; link verified closure to `FIXED_ITEMS.md`.
When a requirement or product surface changes, update the relevant canonical
specification and this scenario matrix before claiming qualification.

## Appendix — Acceptance tests by phase (historical)

> Merged from `docs/plans/TESTING.md` on 2026-11-16; the original file was removed.

> **Status banner, refreshed 2026-08-22.** The launchable clients are the local
> terminal client (`raiker`) and the local web dashboard (`raiker-app` /
> `raiker-web`, loopback only). Approval resolution **executes** the twelve
> capabilities in `EXECUTABLE_ON_APPROVAL` (`raiker/approvals/execution.py`) —
> file mutations, patches, bounded local `shell`, the git write and push path, a
> GitHub write, the two local planning rows, durable memory writes and forgets,
> and owner-selected SSH and Daytona commands — each re-governed at execution
> time; every other capability keeps decision-only resolution. Runtime execution
> is **not** globally disabled: plugin slices, graph indexing, channels,
> scheduled routines, model providers, MCP, container read tools and governed
> local commands all have real executors and are governed per action. Sensitive
> finance, investment, medical, pregnancy, CCTV, home-security and hardware
> domains have no executor and fail closed. Rich/native TUI, mobile, IDE and
> hosted multi-user clients remain deferred. The canonical statement of what is
> implemented is [`IMPLEMENTATION_STATUS.md`](../architecture/IMPLEMENTATION_STATUS.md); where
> this document and the code disagree, the code wins and this document must be
> updated.


This document defines the acceptance tests that prove Raiker is implemented according to the documentation. It complements `docs/architecture/VERIFICATION_PLAN.md` by grouping tests by phase and by implementation gate.

A feature is not complete until its acceptance tests exist and pass.

---

### Global Acceptance Rules

Every phase must preserve these rules:

1. Every enabled interface enters through the Agent Gateway.
2. No tool executes without a policy decision.
3. Denied actions do not execute.
4. Approval-required actions bind approval to the exact action ID.
5. Events are append-only and indexed in SQLite.
6. Runtime transitions follow the canonical state machine.
7. Checkpoints are written where the phase requires them.
8. Memory writes are governed and auditable.
9. Phase-scheduled features remain disabled until explicitly in scope.
10. No interface becomes privileged because it was implemented earlier.

---

### Phase 1: Secure Local Interface Core

> **File names in this section are the Phase-1 names, and thirteen of them no
> longer exist.** `tests/` has been reorganised and consolidated several times
> since; the criteria in the right-hand column are still the acceptance bar and
> are still covered, but the file that covers one is often named for the
> behaviour rather than for the Phase-1 component. Treat the **assertions** as
> normative and `tests/` as the source of truth for where they live. The names
> known to be stale are `test_id_helpers.py`, `test_equal_interface_invariant.py`,
> `test_event_catalog.py`, `test_path_safety.py`, `test_classifier_planner.py`,
> `test_verification_stub.py`, `test_mock_model_provider.py`,
> `test_model_profile_registry.py`, `test_agent_gateway.py`,
> `test_session_manager.py`, `test_checkpoint_service.py`,
> `test_global_command.py` and `test_terminal_registry_panels.py`.


#### Contract Acceptance

| Test file | Required assertions |
|---|---|
| `tests/test_contracts.py` | PromptEnvelope validates; invalid required fields fail; schema version required; allowed client types accepted; invalid client types rejected. |
| `tests/test_id_helpers.py` | IDs have correct prefixes; timestamps are UTC ISO 8601. |
| `tests/test_equal_interface_invariant.py` | Docs/config do not define terminal/TUI as canonical or exclusive; all enabled clients use shared contracts. |

#### Storage And Events Acceptance

| Test file | Required assertions |
|---|---|
| `tests/test_storage_sqlite.py` | Fresh `.raiker/raiker.db` creates schema tables; migrations table exists; WAL and foreign keys are enabled. |
| `tests/test_event_log.py` | JSONL appends one object per line; events are never rewritten; SQLite indexes event metadata; event order matches runtime order. |
| `tests/test_event_catalog.py` | Required Phase 1 event names are recognised; unknown event names fail unless explicitly versioned. |

#### Policy And Broker Acceptance

| Test file | Required assertions |
|---|---|
| `tests/test_policy_engine.py` | Inside-workspace read/list/glob/grep allowed; outside-workspace access denied; local command returns `needs_approval`; policy reasons included. |
| `tests/test_tool_broker.py` | Unknown tool fails safely; action without policy cannot execute; denied action does not execute; output limits and structured errors are returned. |
| `tests/test_path_safety.py` | Path traversal and symlink escape are blocked unless policy explicitly allows. |

#### Tool Acceptance

| Tool | Required assertions |
|---|---|
| `read_file` | Reads text inside workspace; missing file returns structured error; outside workspace denied; binary handling explicit. |
| `list_directory` | Stable sorted output; bounded entries; outside workspace denied. |
| `glob` | Workspace-scoped; bounded results; deterministic ordering. |
| `grep` | Text-only; bounded results; no secret leakage in logs. |
| `shell` | Proposal only; requires approval; does not execute by default. |

#### Runtime Acceptance

| Test file | Required assertions |
|---|---|
| `tests/test_runtime_state_machine.py` | Valid simple-chat and filesystem transitions reach `CLOSED`; invalid transitions fail; denied and approval-required paths do not execute. |
| `tests/test_classifier_planner.py` | Simple chat requires no tools; filesystem prompt maps to `filesystem_query`; local command maps to approval-gated action; plan-created/skipped events include reasons. |
| `tests/test_verification_stub.py` | Tool success verifies passed; denied/failed actions verify partial/failed with reason; verification event emitted. |

#### Model And Registry Acceptance

| Test file | Required assertions |
|---|---|
| `tests/test_mock_model_provider.py` | Mock provider is deterministic; no network or local model install required. |
| `tests/test_model_profile_registry.py` | Model profiles load; `mock` profile exists; unknown provider fails clearly; disabled hosted providers do not run. |
| `tests/test_channel_connector_registry.py` | Connector profiles load; disabled profiles are listable; Apple and Android mobile profiles exist; disabled connector cannot receive messages. |

#### Gateway, Session, Checkpoint Acceptance

| Test file | Required assertions |
|---|---|
| `tests/test_agent_gateway.py` | Valid envelope reaches runtime; invalid envelope returns structured failure; client metadata preserved. |
| `tests/test_session_manager.py` | Session create/load works; turn IDs tracked; event/checkpoint paths attach to session. |
| `tests/test_checkpoint_service.py` | Checkpoint manifest path deterministic; completed turn writes checkpoint stub; manifest includes last event ID and summary. |

#### Terminal MVP Acceptance

| Test file | Required assertions |
|---|---|
| `tests/test_global_command.py` | Installed `raiker` command opens configured terminal client or documented bootstrap module path. |
| `tests/test_terminal_client_smoke.py` | Terminal prompt creates PromptEnvelope, calls gateway, renders response, creates event log and checkpoint. |
| `tests/test_terminal_approval_execution.py` | Approval requires a live control session, preview does not execute, repeated-id confirmation executes exactly once, revoked sessions fail closed, and web history retains bounded evidence. |
| `tests/test_terminal_registry_panels.py` | `/channels` and `/models` list registry profiles; disabled profiles visible as disabled. |

---

### Phase 2: Rich Local Workspace

#### Phase 2 Foundation Acceptance (Slice: task/status/event/checkpoint inspection)

| Test file | Required assertions |
|---|---|
| `tests/test_phase_2_task_manager.py` | Task rows are created/listed/updated deterministically; task events are appended and indexed; task manager lifecycle works. |
| `tests/test_phase_2_event_viewer.py` | Events can be listed by session, turn, task, type; event index rows are readable; event payload is readable; read-only queries do not mutate. |
| `tests/test_phase_2_checkpoint_timeline.py` | Checkpoints can be listed by session; checkpoint metadata is readable; listing is deterministic. |
| `tests/test_phase_2_terminal_commands.py` | `/status` shows session/workspace state; `/tasks` lists tasks; `/events` lists recent events; `/checkpoints` lists checkpoint metadata; commands do not execute tools. |

#### Phase 2 Full Acceptance

Acceptance tests must prove:

- Task rows are created/listed/updated deterministically.
- Task lifecycle events are appended and indexed.
- Task manager does not execute tools.
- Event viewer queries are read-only and bounded.
- `/status`, `/tasks`, `/events`, `/checkpoints` commands render state without tool execution.
- CI runs on every PR and push to main.
- Rich TUI task panel updates from event stream.
- Background tasks can pause, cancel, steer, and resume at safe boundaries.
- Side questions do not corrupt active task state.
- File edits create snapshots before mutation.
- Checkpoint restore requires approval when files change.
- Local model providers are launched or connected through model profiles.
- Memory writes require governance approval.
- Hooks run only through the hook engine and cannot bypass policy.
- Scoped command allowlists remain auditable.

---

### Phase 3: Desktop, Web, Mobile, Plugins, Graph, Semantic Memory

#### Completed Phase 3 A-P safe foundation/readiness acceptance

Completed Phase 3 A-P acceptance is limited to the non-runtime foundation that is implemented and locally testable now. Tests must prove:

- CLI functional testing covers the implemented terminal/slash-command surfaces.
- Desktop, Web, Dashboard, and future client workspace views are read-only shared contract views and do not mutate state.
- Plugin manifest planning validates manifests, permission diffs, and unsafe metadata without installing, enabling, or executing plugins.
- Approval previews and approval-audit/rollback-plan surfaces are preview-only and cannot execute deferred graph, memory, cleanup, rollback, plugin, channel, remote, or hosted runtime work.
- Readiness metadata is deterministic and JSON-renderable for graph, memory, approval, cleanup, remote, plugin, and channel readiness.
- Storage lifecycle metadata, retention metadata, cleanup previews, handoff records, evidence bundles, and policy simulations remain metadata-only.
- Disabled-runtime validation proves plugin execution, graph/codemap runtime indexing, semantic/vector writes, embeddings, approval execution, cleanup execution, rollback execution, external channels, subagents, remote/container/cloud execution, and hosted routines remain false.

#### Deferred platform acceptance after Phase 3 A-P

The following acceptance criteria are specified for later app/runtime work and are **not required** to claim the current Phase 3 A-P safe foundation/readiness completion:

- Mobile stale approval rejection in launchable Apple/Android clients.
- Web/Dashboard event stream UI reading append-only events and SQLite state in a launchable app.
- Semantic search runtime enforcing provenance, sensitivity, and trust filters.
- Graph/codemap recursive CTE runtime impact analysis and query execution.
- Checkpoint restore/fork UI parity across launchable Desktop/Web/Dashboard/Mobile/IDE/API clients.

---

### Phase 4: Channels, Multi-Agent, Remote Execution

Acceptance tests must prove:

- Unknown channel senders are rejected or forced into pairing.
- Channel messages create ChannelMessageEnvelope and enter the Agent Gateway.
- Channel approval relay is disabled by default and action-bound when enabled.
- Subagents have bounded tools, model profile, memory scope, runtime, and depth.
- Parent runtime verifies subagent outputs.
- Cancellation cascades to subagents and remote jobs.
- Container/SSH/VPS execution profiles enforce resource, egress, and cleanup policy.
- Remote execution artifacts are captured and event logged.

---

### Phase 5: Owner-Governed Personal Agent And Home-Lab Operations

Acceptance tests must prove:

- Owner-managed policy and decision-mode precedence works.
- Event integrity checks detect tampering.
- Signed plugins validate signatures and checksums.
- Owner sessions, projects, linked devices and execution profiles enforce their intended isolation for approvals, memory and secrets.
- Audit export includes events, policy decisions, approvals, tool actions, checkpoints, and config versions.
- Owner-set hosted provider budgets block over-limit requests.
- Personal home-lab or owner-selected remote execution configuration does not weaken local-first defaults.
- Whether a request is local is decided by the listener it arrived on, never by its headers: every request on the remote listener (private network or reverse proxy, chosen in Settings → Security → Remote access) is remote — HTTPS required, no recovery, instances or host control, rate limited, HSTS — with or without forwarding headers, and the local listener refuses any forwarded request. Diagnostics says how the host is reached (`tests/test_proxied_loopback.py`, RT-SEC-01 to 03; [FIXED-1266](FIXED_ITEMS.md#fixed-1266--a-proxy-that-sent-no-forwarding-header-was-still-read-as-local-bug-347-review)).
- Remote access needs two-step sign-in and no shared secret: the remote listener does not open without MFA; a remote session needs the password and a code against the current enrolment; turning MFA off or resetting it suspends remote access and retires older sessions; sensitive changes need a fresh code; local access works without MFA (`tests/test_remote_auth.py`, `tests/test_remote_access.py`, RT-SEC-04 to 12; [FIXED-1267](FIXED_ITEMS.md#fixed-1267--remote-access-was-gated-by-a-token-nothing-read-bug-358), [REMOTE_ACCESS.md](../architecture/REMOTE_ACCESS.md)).

---

### Manual Acceptance Script For Phase 1

After Phase 1 implementation, a human or builder agent must run:

```bash
python -m pytest
python -m ruff check .
python -m mypy raiker apps tests
raiker
```

Manual terminal actions:

```text
Hello Raiker
List files in this project
/launch --provider mock --model anything  # unregistered provider; CLI reports unknown_model_profile:mock:anything
/channels
/models
```

Expected results:

- simple prompt completes;
- filesystem query goes through policy and broker;
- local action prompt pauses for approval;
- event JSONL exists;
- SQLite event index exists;
- checkpoint manifest exists;
- `/channels` and `/models` display disabled/listable profiles;
- no hosted/network/plugin/channel/subagent runtime is active unless explicitly in phase scope.

#### Phase 3 rollout slice A acceptance evidence

| Test file | Required assertions |
|---|---|
| `tests/test_phase_3_capability_states.py` | Phase 3 capability states cannot jump directly to runtime; unknown capabilities are denied; Phase 4 gates remain disabled. |
| `tests/test_phase_3_workspace_inspection.py` | Desktop, web, and dashboard inspection requests return equivalent shared read-only data shapes and do not mutate tasks, approvals, memory, channels, plugins, or execution. |
| `tests/test_phase_3_equal_workspace_clients.py` | Future clients share `UIActionEnvelope` metadata and no client is privileged or allowed direct tool calls. |
| `tests/test_phase_3_plugin_policy.py` | Plugin registration planning validates manifests, denies unsafe prefixes, approval-gates risky permissions, treats entrypoints as metadata, and never enables execution. |
| `tests/test_phase_3_terminal_commands.py` | `/workspace`, `/clients`, `/plugins`, and `/plugin-plan <manifest_path>` are inspection-only and return helpful output. |

#### Phase 3 rollout slice B acceptance evidence

| Test file | Required assertions |
|---|---|
| `tests/test_phase_3_workspace_views.py` | Workspace view summaries are generated from shared inspection output, deterministic, JSON-serialisable, equivalent across terminal/desktop/web/dashboard, read-only, and redact secret-like values. |
| `tests/test_phase_3_workspace_views.py` | `/workspace-view` appears in `/help`, renders a deterministic read-only workspace summary, and leaves tasks and approvals unchanged. |

GitHub Actions are temporarily paused only because the Actions run limit/quota is exhausted. While paused, local validation evidence from `docs/architecture/LOCAL_VALIDATION_GATE.md` is mandatory and full CI must be re-enabled before release tagging or when quota is available again. Full Phase 3 remains incomplete, and plugin execution, graph/codemap runtime indexing, semantic/vector writes, external channels, subagents, multi-agent teams, remote execution, and container execution remain disabled.

### Phase 3 Slice C/D governance update (local validation required)

Current runtime posture update: graph indexing, semantic memory, local vector embedding/search, and provider-backed embedding now have real governed executors; broader graph query/planning automation, learned semantics, external sync, and no-executor extensions remain deferred/fail-closed.

Safety status for this slice:

- GitHub Actions **run on every pull request and push to `main`** (`.github/workflows/`); the claim that they were paused for quota was true in an earlier phase and is not true now. See [`VERIFICATION_PLAN.md`](../architecture/VERIFICATION_PLAN.md).
- Local validation evidence remains mandatory under `docs/architecture/LOCAL_VALIDATION_GATE.md`.
- Plugin execution slices are integrated governed executors; broader plugin extensions remain deferred/fail-closed.
- Graph indexing, semantic memory, local vector embedding/search, and provider-backed embedding are integrated governed executors; broader graph/memory extensions remain deferred/fail-closed.
- The reference external channel runtime, subagent/team executors, and local container executor are integrated and governed.
- Remote/cloud command execution remains no-executor/fail-closed.

New planning/review-only surfaces:

- `/graph-status` reports graph/codemap indexing disabled and dry-run planning available.
- `/graph-plan` renders a dry-run plan with `can_index: false` and `runtime_indexing_enabled: false`.
- `/memory-review` and `/memory-review --summary` inspect governed memory candidates without semantic writes.

#### Phase 3 Slice E: Approval-preview UX/contracts

Required test file: `tests/test_phase_3_approval_previews.py`.

Required assertions:

- Graph approval previews can be created from dry-run graph plans and always report `can_execute_now=false` and `execution_enabled=false`.
- Graph approval previews do not write graph indexes and unsafe graph plans are denied/preview-only.
- Semantic memory approval previews can be created from memory review items and always report `can_execute_now=false` and `execution_enabled=false`.
- Semantic memory approval previews do not write semantic memory, embeddings, or vectors.
- Secret-like memory candidates produce denied high-risk previews with redacted output.
- Preview rendering is deterministic.
- Workspace inspection includes `approval_preview_summary`.
- CLI preview commands are read-only/preview-only.
- Plugin execution, graph runtime indexing, semantic/vector writes, external channels, remote/container execution, subagents, and multi-agent teams remain disabled.


### Phase 3 Slice F — Approval Audit and Rollback Planning

Slice F adds preview-only approval audit and rollback planning contracts for future graph indexing and semantic memory writes. Full Phase 3 is not complete.

Safety invariants for this slice:

- Approval audit records do not execute actions.
- Rollback plans do not execute rollback.
- Legacy preview surfaces do not execute graph writes; the current graph indexing runtime is a separate governed real executor.
- Legacy preview surfaces do not write semantic memory; current semantic memory and vector embedding/search runtimes are separate governed real executors.
- Plugin slices, the reference external channel, subagent/team executors, local container runtime, and owner-configured SSH/Daytona command execution are governed real executors; other remote/cloud providers remain no-executor/fail-closed.

New preview-only CLI surfaces: `/approval-audit`, `/approval-audit --summary`, `/rollback-plan`, `/graph-rollback-plan`, and `/memory-rollback-plan`.

### Phase 3 Slice G — Storage lifecycle preparation

Slice G adds policy-gated storage lifecycle preparation only. Full Phase 3 is not complete. Lifecycle records are metadata-only planning records for graph/codemap indexing, semantic memory review/write previews, approval audit metadata, and rollback plan metadata.

Safety status:

- Lifecycle records do not execute graph indexing.
- Lifecycle records do not write semantic memory.
- Lifecycle records do not create embeddings or vectors.
- Legacy lifecycle/preview surfaces do not write graph data directly; current graph indexing is a governed real executor.
- Legacy preview surfaces do not write semantic memory; current semantic/vector runtimes are governed real executors.
- Rollback execution remains disabled.
- Plugin slices, the reference external channel, subagent/team executors, local container runtime, and owner-configured SSH/Daytona command execution are governed real executors; other remote/cloud providers remain no-executor/fail-closed.

### Phase 3 Slice H lifecycle retention reference

Slice H is metadata-only retention, cleanup-preview, and approval-handoff planning. Keep detailed contract and safety requirements in `docs/architecture/IMPLEMENTATION_STATUS.md`; this document only references Slice H where its local status, validation, command, event, or storage responsibility applies.

### Phase 3 Slice I lifecycle evidence reference

Slice I lifecycle evidence bundles, policy simulations, JSON exports, CLI surfaces, SQLite metadata tables, and disabled-runtime validation are centralized in `docs/architecture/IMPLEMENTATION_STATUS.md`. Slice I is metadata-only/read-only/export-only/simulation-only and does not mark Phase 3 complete.

### Current implementation truth table (Phase 3 reconciliation)

Phase 3 is `implemented_verified` only for safe foundation/readiness slices A-P: CLI functional-test surfaces, read-only shared workspace/view contracts, plugin manifest planning/validation, approval-preview surfaces, readiness metadata, storage lifecycle metadata, and disabled-runtime validation. Full rich UI apps and runtime features remain specified/deferred unless explicitly listed as implemented below. No UI surface may execute tools directly; all future execution must go through the Agent Gateway, ToolBroker, PolicyEngine, approvals, and disabled runtime gates.

| Surface | Current implementation | Functional-testable? | Runtime authority | Next task |
|---|---|---:|---|---|
| CLI / plain terminal | Implemented functional-test surface via `raiker` and slash commands. | Yes | No direct tool authority; routes through gateway/broker/policy where runtime paths exist. | Keep command/catalog parity and local smoke tests current. |
| Plain terminal client | Line-oriented terminal client with `/help`, `/commands`, slash-command routing, and prompt submission. Rich/native TUI is Phase 8 deferred. | Yes | No direct tool authority; prompts route through gateway/broker/policy. | Implement richer clients only in Phase 8. |
| Desktop UI | Read-only shared contract/view foundation only; no launchable desktop app. | Contract-only | None. | Implement app shell after explicit activation scope. |
| Web UI | Launchable local web dashboard: `web` Svelte SPA over the `raiker-web` loopback API. Read-only governed views + governed prompt/turn/approval/runtime-mutation flows (approval resolution metadata-only); single-user, `127.0.0.1` only. | Yes | No direct tool authority; routes through gateway/RuntimeAuthority/broker exactly as the CLI. | Keep API-contract + frontend test parity; broader clients stay deferred. |
| Dashboard | Launchable local web dashboard via web, with governed views, prompt/turn flows, task creation, Connector Store, settings, and approvals. | Yes | No direct authority; every mutation follows the governed API path. | Keep API and frontend tests in parity; native and mobile dashboards remain deferred. |
| IDE extension | Specified/deferred; no extension runtime. | No | None. | Define extension transport and auth. |
| Mobile apps | Specified/deferred; no Apple/Android apps. | No | None. | Build mobile clients after explicit activation scope. |
| Voice UI | Governed turn-based dictation in web Chat/Build plus manual response read-aloud; full-duplex conversation deferred. | Yes — web composer only | Prompt submission uses the existing authenticated gateway; `input_mode` is constrained metadata, raw audio is not retained, and speech never submits or executes by itself. | Add continuous listening, interruption and hands-free task control only with visible state, action-bound confirmation and receipt parity. |
| Browser extension | Specified/deferred. | No | None. | Define extension boundary after explicit activation scope. |
| External chat/channel clients | Metadata/readiness only; transports disabled. | Readiness-only | None. | Implement connectors after explicit activation scope. |
| REST/API | Authenticated single-user raiker-web API, loopback by default with explicit public opt-in. | Yes | No direct authority; requests route through the same gateway, RuntimeAuthority, and broker path. | Hosted multi-user API remains deferred. |



### Plain terminal client acceptance; Rich/native TUI deferred

Plain terminal acceptance: `raiker` launches the line-oriented client; `raiker --prompt` submits one prompt and exits; `/help` and `/commands` are plain text; slash commands route through `handle_slash_command()`; prompts route through `submit_terminal_prompt()`. Rich/native TUI acceptance is deferred to Phase 8.

### Personal-agent delivery and release acceptance

The [PAA plan](PERSONAL_AUTONOMOUS_AGENT_SPEC.md) adds staged
personal-agent work without rewriting historical phase closures. Every new
phase must add and pass the applicable
[release scenarios](TESTING.md).

| PAA stage | Release acceptance dependencies |
|---|---|
| A: contracts and durable goals | RR-02/03/06/13/25/26 plus existing contract/schema/migration tests |
| B: coordinator, context and recovery | RR-05/06/07/10/11/12/14/15/16/20/21/22/23/24/26 |
| C: proactivity, connectors and progress | RR-08/09/17/18/19/22/33/34 |
| D: isolated browser and explicit continuity | RR-29/30 plus identity/permission/egress/recovery cases |
| E: reviewed learning | RR-31/32 plus memory/privacy/activation/revocation cases |
| Release candidate for declared scope | All applicable B+P rows, optional W/C/L claims, RR-01–04/27/28/35/36 and required PA-S scenarios |

This mapping is a future acceptance obligation, not a record of tests run.
Promotion to release requires a complete candidate scorecard and evidence,
not only implementation completion or five documentation validators passing.

### Beta release acceptance

The first beta is a **prerelease to the `beta` channel** for testers who know
it is a beta ([Releasing](../guide/releasing.md#beta-release-checklist)). It is
accepted when every row below has its evidence on the release commit. A row
without evidence blocks the beta; it is not waived by a later one.

| Gate | Evidence on the release commit |
|---|---|
| CI green | `ci.yml` (Python lint, types, scans and docs; three test shards; Web UI; Electron shell; Licensing and SBOM) and, when packaging paths changed, `desktop-package.yml` |
| Installers | The [release acceptance matrix](BETA_RELEASE_PLAN.md#appendix-d--desktop-package-acceptance-matrix) rows for every platform offered; an unsigned beta says so in its notes |
| Live rounds | The most recent result for each area in [WEB_APP_LIVE_TEST.md](../architecture/WEB_APP_LIVE_TEST.md) is ✅ on a hosted provider, and no ✅ there depends on a fix not on the release commit |
| Remote access | RT-SEC-01 to RT-SEC-12 pass on the release commit, in one run on a fresh workspace, on the latest live result; the *Remote access* CI job is green on Windows and macOS; the beta notes say remote access is chosen in **Settings → Security → Remote access** (private network with HTTPS, or a reverse proxy pointed at the remote listener, never at port 8765), needs two-step sign-in on every device, and has no shared secret ([Remote access](../guide/managing-the-host.md#remote-access)); [BUG-359](TO_BE_FIXED.md#bug-359--remote-access-is-verified-live-on-linux-only-and-has-five-known-limits) is named in the notes. The UI rendering and unit tests passing are not enough on their own |
| Data safety | A backup is made and restored from Settings, and the lock screen restores one (recovery stays this-computer-only) |
| Open defects | Every open entry in [TO_BE_FIXED](TO_BE_FIXED.md) is either outside the beta's claims or named in the beta notes; [KNOWN_LIMITS](../architecture/KNOWN_LIMITS.md) is current |
