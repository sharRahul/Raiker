# Raiker plans — current-status index

`docs/plans/` contains both **current ledgers** and **historical review/implementation evidence**. Do not assume the newest paragraph inside every old review is the current product state.

## Current status entry point

Start with:

- [`DEEP_CODEBASE_DOCUMENTATION_UI_INSTALLER_AUDIT_2026-09-07.md`](DEEP_CODEBASE_DOCUMENTATION_UI_INSTALLER_AUDIT_2026-09-07.md) — current codebase/UI/installer/CI/competitive audit at `main` commit `ea2f48e70bfa7e68685f9865e9face17d820a61c`.
- [`TO_BE_FIXED.md`](TO_BE_FIXED.md) — unresolved defect ledger.
- [`TO_BE_ADDED.md`](TO_BE_ADDED.md) — future/differentiator proposals; proposals are not defects.
- [`FIXED_ITEMS.md`](FIXED_ITEMS.md) — closure/evidence history.
- [`PILLAR_MAP.md`](PILLAR_MAP.md) — high-level product/pillar dependency map.

When these disagree with an older topic review's current-status prose, re-verify source and use the newer evidence. Preserve the old analysis as history rather than rewriting it as though later work had already existed.

## Topic reviews and implementation records

| Document | Role now |
|---|---|
| `CODEBASE_OPTIMIZATION_AND_LOC_REDUCTION_2026-09-05.md` | Historical optimization review; several architecture recommendations remain active |
| `CODEBASE_SECURITY_CODE_REVIEW_2026-09-05.md` | Historical security findings; current re-verification is in the deep audit |
| `ENVIRONMENT_CONTEXT_TIME_WEATHER_2026-09-07.md` | Design/implementation record; later closure evidence supersedes its original open state |
| `GAP_BUILD_CHAT.md` | Build/Chat gap ledger; row-level status is stronger evidence than old narrative paragraphs |
| `GENERIC_STATIC_CODE_REVIEW_2026-09-05.md` | Historical static review |
| `GENERIC_STATIC_CODE_REVIEW_THIRD_PASS_2026-09-05.md` | Historical deeper review; contains some stale “still open” prose beside later closed rows |
| `GLOBAL_MODEL_CATALOGUE_AND_COMPOSER_PICKER_2026-09-06.md` | Model-catalogue architectural invariant/regression target |
| `GLOBAL_WEB_READ_CAPABILITIES_2026-09-07.md` | Global read-capability design/implementation record |
| `GOVERNANCE_ENTRY_PATHS.md` | Governance entry-path inventory; candidate for registry-backed validation |
| `LIVE_TEST_ROUNDS.md` | Historical live-test evidence by round |
| `MEMORY_RELIABILITY_PLAN.md` | Memory reliability evidence/closure ledger |
| `MODELS_PAGE_UI_BACKEND_REVIEW_2026-09-06.md` | Historical Models review; current five-panel IA is implemented |
| `PAGE_BY_PAGE_IMPLEMENTATION_VERIFICATION_2026-09-07.md` | Historical page-verification snapshot; current status superseded by the deep audit |
| `RAIKER_LIVE_MANUAL_TEST_PLAN.md` | Active manual verification procedure |
| `SECURITY_COMPLIANCE_GAP_ASSESSMENT_2026-09-05.md` | Standards/control mapping evidence, not a certification claim |
| `UNIFIED_COMPOSER_REDESIGN_2026-09-06.md` | Composer design/implementation history |
| `VISUAL_UI_UX_REVIEW_2026-09-06.md` | Visual review history; current audit supersedes 4K/8K capture work |
| `WEB_UI_ADAPTIVE_SHELL_DESIGN.md` | Shell design history |
| `WEB_UI_ADAPTIVE_SHELL_IMPLEMENTATION_PLAN.md` | Shell implementation history |
| `screenshots/` | Legacy screenshot evidence only; canonical current screenshots live under `docs/screenshots/` |

## Documentation governance

1. **Defect:** add/update `TO_BE_FIXED.md`.
2. **Future differentiator:** add/update `TO_BE_ADDED.md`.
3. **Verified closure:** append evidence to `FIXED_ITEMS.md` and update the originating row where useful.
4. **Topic review:** keep the reasoning, evidence and acceptance criteria; do not create another independent master backlog inside it.
5. **Current status:** link from this index to the newest repository-wide audit/verification record.
6. **Screenshots:** use only `docs/screenshots/` for current product evidence. `docs/plans/screenshots/` is historical and may intentionally contain obsolete states.

This structure is intended to stop a later fix from requiring edits to half a dozen historical review files just to keep the meaning of “open” consistent.
