# Raiker testing and real-user qualification

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

## Evidence retention and maintenance

Keep redacted traces, screenshots, artifact hashes, provider receipts and
validator outputs for the support life of the qualified release. Link newly
found defects to `TO_BE_FIXED.md`; link verified closure to `FIXED_ITEMS.md`.
When a requirement or product surface changes, update the relevant canonical
specification and this scenario matrix before claiming qualification.
