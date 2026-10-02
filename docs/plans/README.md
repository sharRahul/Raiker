# Raiker plans — current-status index

`docs/plans/` contains **current ledgers** and the **topic reviews that still have
work in them**. Do not assume the newest paragraph inside every old review is the
current product state.

A topic review is removed once every item in it has closed. What survives is its
closure record in [`FIXED_ITEMS.md`](FIXED_ITEMS.md) — the defect, the fix, and
the tests and live evidence behind it — and the reasoning stays in git history
for anyone who needs it. Seven reviews were removed on 2026-09-12 this way:
environment context and weather, global web-read capabilities, the Models page
review, the global model catalogue, the memory-restart closure record, and the
adaptive-shell design and implementation plan. The page-by-page implementation
verification followed on 2026-09-13, its last open item — Design's canvas
workspace — closing as
[FIXED-491](FIXED_ITEMS.md#fixed-491--design-was-a-one-shot-generator-so-most-of-its-composer-had-nothing-to-reach).
The visual UI/UX review went on 2026-09-15, when VIS-19 — a typed output
channel and a chart, the one implementation item left in it — closed as
[FIXED-545](FIXED_ITEMS.md#fixed-545--a-turn-could-only-answer-in-prose). Its
IDs went out of the codebase with it
([FIXED-548](FIXED_ITEMS.md#fixed-548--two-hundred-and-twenty-four-comments-citing-documents-that-are-not-there)
did the same for five earlier removals), so no comment cites a file that is not
in the tree.

The unified composer redesign went on 2026-09-21, when the last of its twenty
items had closed. COMPOSER-01 through COMPOSER-20 are recorded as
[FIXED-454](FIXED_ITEMS.md#fixed-454--the-composer-grew-one-permanent-button-at-a-time),
[FIXED-455](FIXED_ITEMS.md#fixed-455--two-reads-whose-shape-nothing-checked-took-the-page-down),
[FIXED-461](FIXED_ITEMS.md#fixed-461--four-derivations-of-one-fact-about-what-a-turn-can-read),
[FIXED-470](FIXED_ITEMS.md#fixed-470--tasks-asked-to-be-filled-in-rather-than-instructed),
[FIXED-471](FIXED_ITEMS.md#fixed-471--one-primary-action-that-did-not-say-what-it-would-do),
[FIXED-478](FIXED_ITEMS.md#fixed-478--a-work-draft-was-lost-at-every-mode-switch),
[FIXED-479](FIXED_ITEMS.md#fixed-479--a-large-paste-could-hide-the-conversation-it-belonged-to),
[FIXED-491](FIXED_ITEMS.md#fixed-491--design-was-a-one-shot-generator-so-most-of-its-composer-had-nothing-to-reach)
and [FIXED-540](FIXED_ITEMS.md#fixed-540--the-two-surfaces-that-kept-their-own-composer-had-stopped-keeping-it).
The two image controls it lists that are still absent — outpaint and reference
images — are absent *by* its own acceptance test 19: an exposed action that
reaches no runtime path is omitted rather than shipped inert. Proving the three
that did land against a real provider is
[BUG-287](TO_BE_FIXED.md#bug-287--the-image-provider-round-trip-is-unverified-against-a-real-provider),
which is a live-evidence gap and lives in the open ledger.

Four more went on 2026-09-28, each when its last item closed: the generic
static code review and its third pass (GCR-10 by the owner's decision as
[FIXED-618](FIXED_ITEMS.md#fixed-618--construction-time-self-repair-stays-by-the-owners-decision),
GCR-11, GCR-13, GCR-41 and GCR-43 as FIXED-614 to FIXED-617), the security code
review (CR-01 as
[FIXED-619](FIXED_ITEMS.md#fixed-619--a-real-executor-could-be-fetched-and-run-with-nothing-governing-it),
CR-05 and CR-09 with BUG-308, by the owner's decision, as
[FIXED-620](FIXED_ITEMS.md#fixed-620--code-ran-with-this-machines-network-and-nothing-said-so)),
and the memory reliability plan, whose fourteen MEM entries had all closed by
2026-08-29 and whose post-Stage-J backlog is
[ADD-25](TO_BE_ADDED.md#add-25--post-stage-j-memory-expansion). Their IDs stay in
code comments, as COMPOSER-xx did: every closure record names the finding it
closes, so an ID leads to its record.

The optimisation review went on 2026-10-02, when OPT-01 and OPT-02 — every
ordinary JSON route described by OpenAPI and called through a generated
wrapper — finished Stage B as
[FIXED-678](FIXED_ITEMS.md#fixed-678--most-routes-answers-were-described-nowhere-but-the-clients-copy)
and
[FIXED-679](FIXED_ITEMS.md#fixed-679--the-client-still-hand-wrote-the-wrappers-for-routes-openapi-now-describes).
Its other items closed between 2026-09-28 and 2026-10-01 (FIXED-616/617,
FIXED-623 to FIXED-629, FIXED-634 to FIXED-643, FIXED-655 to FIXED-657,
FIXED-664/665). Its OPT-xx IDs stay in code comments on the same terms.

The typed channel's other half closed on 2026-09-16 as
[FIXED-551](FIXED_ITEMS.md#fixed-551--a-declared-table-was-a-table-in-the-conversation-and-json-everywhere-else):
an exported, reopened or spoken answer is the same answer the conversation
showed. Proving it live found
[FIXED-550](FIXED_ITEMS.md#fixed-550--a-turn-that-wrote-anything-before-calling-a-tool-stored-a-different-answer-than-it-showed),
which is wider than the channel — every turn that narrated its work before
calling a tool had been storing a different answer than it showed.

## Current status entry point

Start with:

- [`RELEASE_READINESS_PRODUCT_UX_RUNTIME_REVIEW_2026-09-13.md`](RELEASE_READINESS_PRODUCT_UX_RUNTIME_REVIEW_2026-09-13.md) — documentation-only first-release assessment covering Permissions, Chat, Build, Design, Models, the Settings popup and all Settings pages, Tasks, Memory age/management/usage, Messaging, MCP, Projects, owner identity, runtime convergence and transferable external implementation patterns at `main` commit `327610ad0816cb5ce90590e29ef30179b7caa5a5`.
- [`DEEP_CODEBASE_DOCUMENTATION_UI_INSTALLER_AUDIT_2026-09-07.md`](DEEP_CODEBASE_DOCUMENTATION_UI_INSTALLER_AUDIT_2026-09-07.md) — prior codebase/UI/installer/CI/competitive baseline at `main` commit `ea2f48e70bfa7e68685f9865e9face17d820a61c`; the 2026-09-13 release-readiness review above is newer where their status differs.
- [`TO_BE_FIXED.md`](TO_BE_FIXED.md) — unresolved defect ledger.
- [`TO_BE_ADDED.md`](TO_BE_ADDED.md) — future/differentiator proposals; proposals are not defects.
- [`FIXED_ITEMS.md`](FIXED_ITEMS.md) — closure/evidence history.
- [`PILLAR_MAP.md`](PILLAR_MAP.md) — high-level product/pillar dependency map.

When these disagree with an older topic review's current-status prose, re-verify source and use the newer evidence. While a review still has open items, preserve its old analysis as history rather than rewriting it as though later work had already existed.

## Topic reviews and implementation records

| Document | Role now |
|---|---|
| `GAP_BUILD_CHAT.md` | Build/Chat gap ledger; row-level status is stronger evidence than old narrative paragraphs |
| `GOVERNANCE_ENTRY_PATHS.md` | Canonical governance entry-path inventory; no open item since 2026-09-28 (GEP-02 and GEP-03 closed). Kept as the enumeration, not as a review |
| `LIVE_TEST_ROUNDS.md` | Historical live-test evidence by round |
| `RAIKER_LIVE_MANUAL_TEST_PLAN.md` | Active manual verification procedure |
| `SECURITY_COMPLIANCE_GAP_ASSESSMENT_2026-09-05.md` | Standards/control mapping evidence, not a certification claim |
| `screenshots/` | Legacy screenshot evidence only; canonical current screenshots live under `docs/screenshots/` |

## Documentation governance

1. **Defect:** add/update `TO_BE_FIXED.md`.
2. **Future differentiator:** add/update `TO_BE_ADDED.md`.
3. **Verified closure:** append evidence to `FIXED_ITEMS.md` and update the originating row where useful.
4. **Topic review:** while anything in it is open, keep the reasoning, evidence and acceptance criteria; do not create another independent master backlog inside it. Once every item has closed, delete the file and let its `FIXED_ITEMS.md` entries carry the evidence — and remove its row from the table above, so the index never names a document that is not there.
5. **Current status:** link from this index to the newest repository-wide audit/verification record.
6. **Screenshots:** use only `docs/screenshots/` for current product evidence. `docs/plans/screenshots/` is historical and may intentionally contain obsolete states.

This structure is intended to stop a later fix from requiring edits to half a dozen historical review files just to keep the meaning of “open” consistent.
