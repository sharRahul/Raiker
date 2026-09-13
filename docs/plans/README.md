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

## Current status entry point

Start with:

- [`DEEP_CODEBASE_DOCUMENTATION_UI_INSTALLER_AUDIT_2026-09-07.md`](DEEP_CODEBASE_DOCUMENTATION_UI_INSTALLER_AUDIT_2026-09-07.md) — current codebase/UI/installer/CI/competitive audit at `main` commit `ea2f48e70bfa7e68685f9865e9face17d820a61c`.
- [`TO_BE_FIXED.md`](TO_BE_FIXED.md) — unresolved defect ledger.
- [`TO_BE_ADDED.md`](TO_BE_ADDED.md) — future/differentiator proposals; proposals are not defects.
- [`FIXED_ITEMS.md`](FIXED_ITEMS.md) — closure/evidence history.
- [`PILLAR_MAP.md`](PILLAR_MAP.md) — high-level product/pillar dependency map.

When these disagree with an older topic review's current-status prose, re-verify source and use the newer evidence. While a review still has open items, preserve its old analysis as history rather than rewriting it as though later work had already existed.

## Topic reviews and implementation records

| Document | Role now |
|---|---|
| `CODEBASE_OPTIMIZATION_AND_LOC_REDUCTION_2026-09-05.md` | Historical optimization review; several architecture recommendations remain active |
| `CODEBASE_SECURITY_CODE_REVIEW_2026-09-05.md` | Historical security findings; current re-verification is in the deep audit |
| `GAP_BUILD_CHAT.md` | Build/Chat gap ledger; row-level status is stronger evidence than old narrative paragraphs |
| `GENERIC_STATIC_CODE_REVIEW_2026-09-05.md` | Historical static review |
| `GENERIC_STATIC_CODE_REVIEW_THIRD_PASS_2026-09-05.md` | Historical deeper review; contains some stale “still open” prose beside later closed rows |
| `GOVERNANCE_ENTRY_PATHS.md` | Governance entry-path inventory; candidate for registry-backed validation |
| `LIVE_TEST_ROUNDS.md` | Historical live-test evidence by round |
| `MEMORY_RELIABILITY_PLAN.md` | Memory reliability evidence/closure ledger |
| `RAIKER_LIVE_MANUAL_TEST_PLAN.md` | Active manual verification procedure |
| `SECURITY_COMPLIANCE_GAP_ASSESSMENT_2026-09-05.md` | Standards/control mapping evidence, not a certification claim |
| `UNIFIED_COMPOSER_REDESIGN_2026-09-06.md` | Composer design/implementation history |
| `VISUAL_UI_UX_REVIEW_2026-09-06.md` | Visual review history; current audit supersedes 4K/8K capture work |
| `screenshots/` | Legacy screenshot evidence only; canonical current screenshots live under `docs/screenshots/` |

## Documentation governance

1. **Defect:** add/update `TO_BE_FIXED.md`.
2. **Future differentiator:** add/update `TO_BE_ADDED.md`.
3. **Verified closure:** append evidence to `FIXED_ITEMS.md` and update the originating row where useful.
4. **Topic review:** while anything in it is open, keep the reasoning, evidence and acceptance criteria; do not create another independent master backlog inside it. Once every item has closed, delete the file and let its `FIXED_ITEMS.md` entries carry the evidence — and remove its row from the table above, so the index never names a document that is not there.
5. **Current status:** link from this index to the newest repository-wide audit/verification record.
6. **Screenshots:** use only `docs/screenshots/` for current product evidence. `docs/plans/screenshots/` is historical and may intentionally contain obsolete states.

This structure is intended to stop a later fix from requiring edits to half a dozen historical review files just to keep the meaning of “open” consistent.
