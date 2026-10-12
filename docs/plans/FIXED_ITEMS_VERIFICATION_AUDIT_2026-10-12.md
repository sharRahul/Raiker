# FIXED_ITEMS verification audit — 2026-10-12

## Executive verdict

**NOT fully verified; do not certify every FIXED item as currently corrected.** This is a complete *record-by-record evidence-inventory review*, not 887 independently executed acceptance tests. A `FIXED` heading is a historical closure claim; a passing test file demonstrates a narrower behavior and cannot alone establish live, cross-platform, or real-service correctness. These classes are evidence strength, **not a fix-pass/fail verdict**.

**Baseline:** main commit `23cb971c0065ceadb1ea4d49d3ffbbbb10a9dee3`; `FIXED_ITEMS.md` as retrieved on 2026-10-12, with documentation-only link repairs on PR #232. Main [Python CI](https://github.com/sharRahul/Raiker/actions/runs/38285671581) completed successfully (6,902 tests passed and 11 skipped according to the runner on the PR, which failed for links); main [Web UI CI](https://github.com/sharRahul/Raiker/actions/runs/38285671680) passed including **mocked** Playwright E2E. Rust/native jobs also passed on Linux and Windows, but that is not equivalent to all Python/UI workflows running on Windows. The historical closure text often references real live trials; those trials were not repeated for this audit.

### Per-item evidence classification (all 887 numeric ID slots)

| Evidence class | Individual FIXED sections | Meaning |
|---|---:|---|
| PY — referenced Python test file appeared with passing test cases in main CI log | 393 | Stronger component evidence; individual claimed behavior and live provider still need independent assertion review |
| WEB — existing web/e2e or UI test source cited, with main Web UI workflow passing | 75 | UI/source evidence; the workflow's E2E job is **mocked**, not real provider proof; individual case not correlated to the CI log |
| CODE — existing implementation source cited but no directly correlated passing test | 29 | Static code-presence evidence only |
| REVIEW — no directly cited executed test file or current implementation path identified by this conservative parser | 379 | Requires manual evidence tracing; **not** a finding that no tests exist |
| EXTERNAL — `FIXED-39…42` indexed to an older GAP_BUILD_CHAT record, without a section here | 4 | Historical delegated record, independently inspect canonical destination |
| ABSENT — no dedicated heading or index record | 7 | Identifier gap in this ledger; **not** evidence of an open bug |

**Ledger integrity:** 883 index rows (880 unique), 876 individual FIXED sections; repeated index IDs: 141, 133, 133; indexed only elsewhere: 39, 40, 41, 42; absent identifiers: 194, 196, 197, 205, 206, 207, 208. These numbering discrepancies should not be silently counted as independently verified fixes. Reference tests discovered in the source tree were not missing; some matches are fixture/helper files, not collected tests.

## Findings requiring action

1. **No blanket completion assertion.** A green historical CI run shows a broad regression suite passed at that SHA, but it cannot prove the real-world outcomes of all historical closures. Each item with missing direct trace needs reproducible steps, acceptance criterion, exact test name/CI job, and, when appropriate, actual host/provider proof.
2. **Closed-ledger links broke on PR #232.** [The PR CI run](https://github.com/sharRahul/Raiker/actions/runs/38304109063) finished with 6,902 passed, 11 skipped and one failed test, `test_documentation_links_and_anchors_resolve`. It found 30 broken links after closed BUG sections were removed from `TO_BE_FIXED.md`. The links were subsequently redirected to `FIXED_ITEMS.md` on the PR branch. **No post-repair full CI green run is claimed here.**
3. **Partial closures are valid only within stated boundaries.** For example, `FIXED-886` contains delegated GitHub push governance tests, while open `BUG-338` separately records lack of live GitHub repository-identity revalidation at each consequential step. `FIXED-229` and `FIXED-239` cover selected shell/container modes; `BUG-194` retains wider execution/host limitations. These are not universal platform-level closures.
4. **Coverage priorities.** Critical/High entries without a directly cited passing Python regression file merit targeted independent test review first; **45** such records were found by the conservative filename-evidence classifier. These may have appropriate unreferenced tests or web tests; absence of a direct citation is an evidence gap, not proven regression.
5. **Evidence retention matters.** The ledger itself states older screenshot sets were removed from the repository, so a screenshot filename is not a retrievable artifact. Historical live-test assertions should be tied to accessible run IDs, fixture hashes and results before being promoted to current certified evidence.

### Priority Critical/High records lacking a directly correlated passing Python test

`FIXED-199`, `FIXED-200`, `FIXED-201`, `FIXED-202`, `FIXED-204`, `FIXED-223`, `FIXED-249`, `FIXED-297`, `FIXED-335`, `FIXED-338`, `FIXED-340`, `FIXED-341`, `FIXED-344`, `FIXED-356`, `FIXED-358`, `FIXED-398`, `FIXED-399`, `FIXED-402`, `FIXED-403`, `FIXED-405`, `FIXED-410`, `FIXED-420`, `FIXED-421`, `FIXED-422`, `FIXED-424`, `FIXED-430`, `FIXED-432`, `FIXED-446`, `FIXED-453`, `FIXED-454`, `FIXED-455`, `FIXED-464`, `FIXED-465`, `FIXED-473`, `FIXED-475`, `FIXED-476`, `FIXED-480`, `FIXED-493`, `FIXED-494`, `FIXED-499`, `FIXED-506`, `FIXED-550`, `FIXED-684`, `FIXED-721`, `FIXED-880`

## Reproducible validation and required closure evidence

For every `FIXED-n`: (a) confirm current code path and feature reachability; (b) reproduce the previous failure or assert its negative invariant; (c) run an independently judged regression test, including the rejection/bypass case; (d) verify user-visible outcome on each claimed OS/client; (e) for outbound, model, GitHub, messaging, browser and hardware claims, use a **real** provider/account/host and destination receipt; (f) inject restart/retry/revocation and record absence of unintended effects; and (g) attach commit, test name, CI run, fixture, model/OS and artifact. An unrun or inaccessible test is `not_verified`, never `pass`.

**Release use:** Do not change closed status solely because audit evidence is indirect, but do not claim “all 887 fixes independently verified” until the checks above pass. Track failed reproductions or new regressions in `TO_BE_FIXED.md`, or correct an overstated historical closure with a dated amendment. Preserve `FIXED_ITEMS.md` history rather than editing away past findings.

## Exhaustive ID-by-ID evidence index

This table lists every numeric `FIXED` ID from 1 through 887. **PY/WEB/CODE/REVIEW are evidence-locator grades, not software-health judgments.** Links and references in the original entry are the authoritative detail.

| FIXED ID | Grade | First matched test or source (when explicit) |
|---:|---|---|
| 1 | CODE | raiker/models/policy_state.py |
| 2 | PY | tests/test_token_count_redaction.py |
| 3 | CODE | raiker/models/pricing.py |
| 4 | PY | tests/test_owner_consent_and_history.py |
| 5 | PY | tests/test_owner_consent_and_history.py |
| 6 | REVIEW | No directly cited executed test or current implementation path |
| 7 | PY | tests/test_over_broad_redaction.py |
| 8 | PY | tests/test_approval_execution_wiring.py |
| 9 | PY | tests/test_turn_resume_after_approval.py |
| 10 | PY | tests/test_attachment_preview.py |
| 11 | PY | tests/test_over_broad_redaction.py |
| 12 | REVIEW | No directly cited executed test or current implementation path |
| 13 | PY | tests/test_task_scheduler.py |
| 14 | PY | tests/test_over_broad_redaction.py |
| 15 | PY | tests/test_session_origin.py |
| 16 | PY | tests/test_api_web_read_models.py |
| 17 | PY | tests/test_mcp_agent_tools.py |
| 18 | CODE | raiker/runtime/authority/activation.py |
| 19 | REVIEW | No directly cited executed test or current implementation path |
| 20 | PY | tests/test_approval_execution_wiring.py |
| 21 | REVIEW | No directly cited executed test or current implementation path |
| 22 | PY | tests/test_approval_execution_wiring.py |
| 23 | PY | tests/test_filesystem_tools.py |
| 24 | REVIEW | No directly cited executed test or current implementation path |
| 25 | PY | tests/test_build_workspace.py |
| 26 | REVIEW | No directly cited executed test or current implementation path |
| 27 | REVIEW | No directly cited executed test or current implementation path |
| 28 | REVIEW | No directly cited executed test or current implementation path |
| 29 | PY | tests/test_filesystem_tools.py |
| 30 | REVIEW | No directly cited executed test or current implementation path |
| 31 | REVIEW | No directly cited executed test or current implementation path |
| 32 | REVIEW | No directly cited executed test or current implementation path |
| 33 | REVIEW | No directly cited executed test or current implementation path |
| 34 | REVIEW | No directly cited executed test or current implementation path |
| 35 | REVIEW | No directly cited executed test or current implementation path |
| 36 | REVIEW | No directly cited executed test or current implementation path |
| 37 | REVIEW | No directly cited executed test or current implementation path |
| 38 | REVIEW | No directly cited executed test or current implementation path |
| 39 | EXTERNAL | Index links to GAP_BUILD_CHAT; no individual FIXED section |
| 40 | EXTERNAL | Index links to GAP_BUILD_CHAT; no individual FIXED section |
| 41 | EXTERNAL | Index links to GAP_BUILD_CHAT; no individual FIXED section |
| 42 | EXTERNAL | Index links to GAP_BUILD_CHAT; no individual FIXED section |
| 43 | REVIEW | No directly cited executed test or current implementation path |
| 44 | REVIEW | No directly cited executed test or current implementation path |
| 45 | REVIEW | No directly cited executed test or current implementation path |
| 46 | REVIEW | No directly cited executed test or current implementation path |
| 47 | REVIEW | No directly cited executed test or current implementation path |
| 48 | REVIEW | No directly cited executed test or current implementation path |
| 49 | REVIEW | No directly cited executed test or current implementation path |
| 50 | REVIEW | No directly cited executed test or current implementation path |
| 51 | REVIEW | No directly cited executed test or current implementation path |
| 52 | REVIEW | No directly cited executed test or current implementation path |
| 53 | CODE | raiker/models/price_registry.py |
| 54 | CODE | raiker/sessions/transcript.py |
| 55 | REVIEW | No directly cited executed test or current implementation path |
| 56 | REVIEW | No directly cited executed test or current implementation path |
| 57 | REVIEW | No directly cited executed test or current implementation path |
| 58 | REVIEW | No directly cited executed test or current implementation path |
| 59 | PY | tests/test_task_scheduler.py |
| 60 | REVIEW | No directly cited executed test or current implementation path |
| 61 | PY | tests/test_source_provenance.py |
| 62 | PY | tests/test_attachment_preview.py |
| 63 | REVIEW | No directly cited executed test or current implementation path |
| 64 | REVIEW | No directly cited executed test or current implementation path |
| 65 | REVIEW | No directly cited executed test or current implementation path |
| 66 | PY | tests/test_app_launcher.py |
| 67 | REVIEW | No directly cited executed test or current implementation path |
| 68 | REVIEW | No directly cited executed test or current implementation path |
| 69 | REVIEW | No directly cited executed test or current implementation path |
| 70 | REVIEW | No directly cited executed test or current implementation path |
| 71 | REVIEW | No directly cited executed test or current implementation path |
| 72 | REVIEW | No directly cited executed test or current implementation path |
| 73 | REVIEW | No directly cited executed test or current implementation path |
| 74 | REVIEW | No directly cited executed test or current implementation path |
| 75 | REVIEW | No directly cited executed test or current implementation path |
| 76 | REVIEW | No directly cited executed test or current implementation path |
| 77 | PY | tests/test_source_provenance.py |
| 78 | PY | tests/test_execution_environments.py |
| 79 | REVIEW | No directly cited executed test or current implementation path |
| 80 | PY | tests/test_task_scheduler.py |
| 81 | REVIEW | No directly cited executed test or current implementation path |
| 82 | REVIEW | No directly cited executed test or current implementation path |
| 83 | REVIEW | No directly cited executed test or current implementation path |
| 84 | REVIEW | No directly cited executed test or current implementation path |
| 85 | REVIEW | No directly cited executed test or current implementation path |
| 86 | WEB | web/e2e/bug-37-39-40-41-live.spec.ts |
| 87 | PY | tests/test_scheduler_wakeup.py |
| 88 | PY | tests/test_app_lifecycle.py |
| 89 | WEB | web/e2e/composer.spec.ts |
| 90 | PY | tests/test_terminal_approval_execution.py |
| 91 | PY | tests/test_sqlite_connection_cache.py |
| 92 | PY | tests/test_release_pipeline.py |
| 93 | REVIEW | No directly cited executed test or current implementation path |
| 94 | CODE | raiker/models/tool_call_validation.py |
| 95 | CODE | raiker/agents/orchestration.py |
| 96 | REVIEW | No directly cited executed test or current implementation path |
| 97 | PY | tests/test_agent_plan_and_subagents.py |
| 98 | PY | tests/test_policy_engine.py |
| 99 | PY | tests/test_batched_approval_queue.py |
| 100 | PY | tests/test_sqlite_connection_cache.py |
| 101 | WEB | web/e2e/web-access-turn-control-live.spec.ts |
| 102 | REVIEW | No directly cited executed test or current implementation path |
| 103 | PY | tests/test_filesystem_tools.py |
| 104 | WEB | web/e2e/bug-57-capability-context-live.spec.ts |
| 105 | WEB | web/e2e/bug-61-guide-accuracy-live.spec.ts |
| 106 | PY | tests/test_bug_62_task_approval_executes.py |
| 107 | PY | tests/test_turn_sources.py |
| 108 | PY | tests/test_turn_sources.py |
| 109 | PY | tests/test_git_write_path.py |
| 110 | CODE | raiker/tools/git.py |
| 111 | PY | tests/test_git_push_path.py |
| 112 | PY | tests/test_git_push_path.py |
| 113 | PY | tests/test_repository_code_map.py |
| 114 | REVIEW | No directly cited executed test or current implementation path |
| 115 | PY | tests/test_skills.py |
| 116 | REVIEW | No directly cited executed test or current implementation path |
| 117 | REVIEW | No directly cited executed test or current implementation path |
| 118 | REVIEW | No directly cited executed test or current implementation path |
| 119 | REVIEW | No directly cited executed test or current implementation path |
| 120 | REVIEW | No directly cited executed test or current implementation path |
| 121 | REVIEW | No directly cited executed test or current implementation path |
| 122 | REVIEW | No directly cited executed test or current implementation path |
| 123 | REVIEW | No directly cited executed test or current implementation path |
| 124 | REVIEW | No directly cited executed test or current implementation path |
| 125 | REVIEW | No directly cited executed test or current implementation path |
| 126 | REVIEW | No directly cited executed test or current implementation path |
| 127 | REVIEW | No directly cited executed test or current implementation path |
| 128 | REVIEW | No directly cited executed test or current implementation path |
| 129 | REVIEW | No directly cited executed test or current implementation path |
| 130 | REVIEW | No directly cited executed test or current implementation path |
| 131 | REVIEW | No directly cited executed test or current implementation path |
| 132 | REVIEW | No directly cited executed test or current implementation path |
| 133 | REVIEW | No directly cited executed test or current implementation path |
| 134 | REVIEW | No directly cited executed test or current implementation path |
| 135 | REVIEW | No directly cited executed test or current implementation path |
| 136 | REVIEW | No directly cited executed test or current implementation path |
| 137 | PY | tests/test_api_model_library.py |
| 138 | PY | tests/test_model_quota_readiness.py |
| 139 | PY | tests/test_model_readiness_fallback_chain.py |
| 140 | REVIEW | No directly cited executed test or current implementation path |
| 141 | REVIEW | No directly cited executed test or current implementation path |
| 142 | PY | tests/test_bug_72_web_fetch_turn_survives.py |
| 143 | WEB | web/e2e/web-access-turn-control-live.spec.ts |
| 144 | WEB | web/e2e/web-access-turn-control-live.spec.ts |
| 145 | REVIEW | No directly cited executed test or current implementation path |
| 146 | REVIEW | No directly cited executed test or current implementation path |
| 147 | REVIEW | No directly cited executed test or current implementation path |
| 148 | REVIEW | No directly cited executed test or current implementation path |
| 149 | WEB | web/e2e/bug-44-47-live.spec.ts |
| 150 | PY | tests/test_sqlcipher_memory_security.py |
| 151 | PY | tests/test_accounts.py |
| 152 | PY | tests/test_knowledge_scope.py |
| 153 | REVIEW | No directly cited executed test or current implementation path |
| 154 | PY | tests/test_token_count_redaction.py |
| 155 | PY | tests/test_turn_capability_posture.py |
| 156 | PY | tests/test_memory_write_path.py |
| 157 | REVIEW | No directly cited executed test or current implementation path |
| 158 | PY | tests/test_advisor_model.py |
| 159 | REVIEW | No directly cited executed test or current implementation path |
| 160 | REVIEW | No directly cited executed test or current implementation path |
| 161 | REVIEW | No directly cited executed test or current implementation path |
| 162 | CODE | raiker/api/routes_models.py |
| 163 | CODE | raiker/security/containment.py |
| 164 | CODE | raiker/security/mcp_monitor.py |
| 165 | CODE | raiker/agents/delegation.py |
| 166 | REVIEW | No directly cited executed test or current implementation path |
| 167 | CODE | raiker/runtime/verifier.py |
| 168 | CODE | raiker/runtime/classifier.py |
| 169 | REVIEW | No directly cited executed test or current implementation path |
| 170 | WEB | web/e2e/bug-69-model-readiness-live.spec.ts |
| 171 | PY | tests/test_sqlcipher_memory_security.py |
| 172 | REVIEW | No directly cited executed test or current implementation path |
| 173 | PY | tests/test_policy_engine.py |
| 174 | REVIEW | No directly cited executed test or current implementation path |
| 175 | REVIEW | No directly cited executed test or current implementation path |
| 176 | PY | tests/test_session_transcript_export.py |
| 177 | PY | tests/test_api_rest_hardening.py |
| 178 | REVIEW | No directly cited executed test or current implementation path |
| 179 | PY | tests/test_release_workflow.py |
| 180 | PY | tests/test_ci_workflow.py |
| 181 | REVIEW | No directly cited executed test or current implementation path |
| 182 | PY | tests/test_live_stub_model.py |
| 183 | REVIEW | No directly cited executed test or current implementation path |
| 184 | PY | tests/test_conversation_compaction.py |
| 185 | REVIEW | No directly cited executed test or current implementation path |
| 186 | REVIEW | No directly cited executed test or current implementation path |
| 187 | PY | tests/test_conversation_recall.py |
| 188 | PY | tests/test_conversation_recall.py |
| 189 | REVIEW | No directly cited executed test or current implementation path |
| 190 | PY | tests/test_code_map_references.py |
| 191 | PY | tests/test_edit_whitespace_tolerance.py |
| 192 | PY | tests/test_tray_icon.py |
| 193 | REVIEW | No directly cited executed test or current implementation path |
| 194 | ABSENT | No FIXED section or index entry |
| 195 | REVIEW | No directly cited executed test or current implementation path |
| 196 | ABSENT | No FIXED section or index entry |
| 197 | ABSENT | No FIXED section or index entry |
| 198 | PY | tests/test_tool_registry.py |
| 199 | REVIEW | No directly cited executed test or current implementation path |
| 200 | REVIEW | No directly cited executed test or current implementation path |
| 201 | REVIEW | No directly cited executed test or current implementation path |
| 202 | REVIEW | No directly cited executed test or current implementation path |
| 203 | REVIEW | No directly cited executed test or current implementation path |
| 204 | WEB | web/e2e/review-first-run-honesty-live.spec.ts |
| 205 | ABSENT | No FIXED section or index entry |
| 206 | ABSENT | No FIXED section or index entry |
| 207 | ABSENT | No FIXED section or index entry |
| 208 | ABSENT | No FIXED section or index entry |
| 209 | WEB | web/e2e/guide-surface-live.spec.ts |
| 210 | REVIEW | No directly cited executed test or current implementation path |
| 211 | REVIEW | No directly cited executed test or current implementation path |
| 212 | REVIEW | No directly cited executed test or current implementation path |
| 213 | PY | tests/test_bug_206_207_tool_rows_and_reasoning.py |
| 214 | PY | tests/test_bug_206_207_tool_rows_and_reasoning.py |
| 215 | REVIEW | No directly cited executed test or current implementation path |
| 216 | REVIEW | No directly cited executed test or current implementation path |
| 217 | REVIEW | No directly cited executed test or current implementation path |
| 218 | REVIEW | No directly cited executed test or current implementation path |
| 219 | PY | tests/test_bug_215_reasoning_retention.py |
| 220 | WEB | web/e2e/composer-parity-and-turn-honesty-live.spec.ts |
| 221 | REVIEW | No directly cited executed test or current implementation path |
| 222 | PY | tests/test_event_log.py |
| 223 | WEB | web/e2e/wizard-workbench-composer-live.spec.ts |
| 224 | PY | tests/test_over_broad_redaction.py |
| 225 | REVIEW | No directly cited executed test or current implementation path |
| 226 | REVIEW | No directly cited executed test or current implementation path |
| 227 | PY | tests/test_api_web_read_models.py |
| 228 | REVIEW | No directly cited executed test or current implementation path |
| 229 | PY | tests/test_background_execution.py |
| 230 | PY | tests/test_memory_embedding_backend.py |
| 231 | PY | tests/test_text_search_fts5.py |
| 232 | PY | tests/test_model_facing_memory_graph.py |
| 233 | PY | tests/test_model_facing_memory_graph.py |
| 234 | PY | tests/test_model_facing_memory_graph.py |
| 235 | PY | tests/test_knowledge_map_graph.py |
| 236 | PY | tests/test_reference_graph.py |
| 237 | PY | tests/test_eidetic_capture_runtime.py |
| 238 | PY | tests/test_command_supervisor_reattach.py |
| 239 | PY | tests/test_persistent_command_container.py |
| 240 | PY | tests/test_windows_internal_paths.py |
| 241 | PY | tests/test_memory_entity_extraction.py |
| 242 | PY | tests/test_execution_environments.py |
| 243 | PY | tests/test_background_execution.py |
| 244 | REVIEW | No directly cited executed test or current implementation path |
| 245 | REVIEW | No directly cited executed test or current implementation path |
| 246 | PY | tests/test_credential_overlay.py |
| 247 | PY | tests/test_api_prompts.py |
| 248 | REVIEW | No directly cited executed test or current implementation path |
| 249 | REVIEW | No directly cited executed test or current implementation path |
| 250 | REVIEW | No directly cited executed test or current implementation path |
| 251 | PY | tests/test_build_operating_protocol.py |
| 252 | PY | tests/test_hooks_surface.py |
| 253 | PY | tests/test_hooks_surface.py |
| 254 | PY | tests/test_hooks_surface.py |
| 255 | PY | tests/test_hooks_lifecycle.py |
| 256 | PY | tests/test_plugin_contributions.py |
| 257 | REVIEW | No directly cited executed test or current implementation path |
| 258 | REVIEW | No directly cited executed test or current implementation path |
| 259 | PY | tests/test_plugin_contributions.py |
| 260 | PY | tests/test_plugin_contributions.py |
| 261 | REVIEW | No directly cited executed test or current implementation path |
| 262 | PY | tests/test_model_tool_call_loop.py |
| 263 | WEB | web/e2e/bug-219-decline-mode-live.spec.ts |
| 264 | REVIEW | No directly cited executed test or current implementation path |
| 265 | PY | tests/test_channel_owner_surface.py |
| 266 | PY | tests/test_channel_owner_surface.py |
| 267 | PY | tests/test_channel_owner_surface.py |
| 268 | PY | tests/test_channel_owner_surface.py |
| 269 | PY | tests/test_plugin_contributions.py |
| 270 | PY | tests/test_checkpoint_restore_route.py |
| 271 | PY | tests/test_audit_export.py |
| 272 | PY | tests/test_vertical_slice_e2e.py |
| 273 | PY | tests/test_approval_oversize_notice.py |
| 274 | PY | tests/test_mcp_protocol_version.py |
| 275 | PY | tests/test_checkpoint_restore_route.py |
| 276 | PY | tests/test_over_broad_redaction.py |
| 277 | PY | tests/test_cli_output_encoding.py |
| 278 | PY | tests/test_model_readiness_stale_recheck.py |
| 279 | PY | tests/test_capability_admission.py |
| 280 | PY | tests/test_governance_entry_paths.py |
| 281 | PY | tests/test_skill_standard_conformance.py |
| 282 | PY | tests/test_auto_alignment_check.py |
| 283 | PY | tests/test_memory_semantic_index.py |
| 284 | PY | tests/test_memory_controls.py |
| 285 | REVIEW | No directly cited executed test or current implementation path |
| 286 | PY | tests/test_task_delegation_ownership.py |
| 287 | PY | tests/test_turn_tool_rows_survive_reload.py |
| 288 | REVIEW | No directly cited executed test or current implementation path |
| 289 | PY | tests/test_managed_knowledge_files.py |
| 290 | REVIEW | No directly cited executed test or current implementation path |
| 291 | PY | tests/test_path_authority.py |
| 292 | PY | tests/test_memory_semantic_index.py |
| 293 | PY | tests/test_memory_semantic_index.py |
| 294 | PY | tests/test_memory_semantic_index.py |
| 295 | REVIEW | No directly cited executed test or current implementation path |
| 296 | WEB | web/e2e/memory-semantic-live.spec.ts |
| 297 | REVIEW | No directly cited executed test or current implementation path |
| 298 | PY | tests/test_phase_4_channels.py |
| 299 | PY | tests/test_skills.py |
| 300 | PY | tests/test_managed_mlx_runtime.py |
| 301 | PY | tests/test_memory_vector_index_cache.py |
| 302 | WEB | web/e2e/memory-vector-index-live.spec.ts |
| 303 | PY | tests/test_hooks.py |
| 304 | PY | tests/test_routes_settings.py |
| 305 | PY | tests/test_hooks_lifecycle.py |
| 306 | PY | tests/test_owner_guided_compaction.py |
| 307 | PY | tests/test_risk_model.py |
| 308 | PY | tests/test_owner_question.py |
| 309 | WEB | web/e2e/bug-242-build-restore-mem-09-live.spec.ts |
| 310 | PY | tests/test_memory_integrity.py |
| 311 | PY | tests/test_memory_controls.py |
| 312 | REVIEW | No directly cited executed test or current implementation path |
| 313 | WEB | web/e2e/capture.ts |
| 314 | PY | tests/test_hybrid_memory_retrieval.py |
| 315 | WEB | web/e2e/b18-mem08-rewind-and-turn-anchor-live.spec.ts |
| 316 | REVIEW | No directly cited executed test or current implementation path |
| 317 | PY | tests/test_turn_sources.py |
| 318 | REVIEW | No directly cited executed test or current implementation path |
| 319 | PY | tests/test_memory_controls.py |
| 320 | REVIEW | No directly cited executed test or current implementation path |
| 321 | PY | tests/test_code_repo_files_api.py |
| 322 | PY | tests/test_capability_admission.py |
| 323 | PY | tests/test_turn_sources.py |
| 324 | REVIEW | No directly cited executed test or current implementation path |
| 325 | WEB | web/e2e/ui-sweep-clipping-live.spec.ts |
| 326 | PY | tests/test_docs_consistency.py |
| 327 | REVIEW | No directly cited executed test or current implementation path |
| 328 | REVIEW | No directly cited executed test or current implementation path |
| 329 | REVIEW | No directly cited executed test or current implementation path |
| 330 | REVIEW | No directly cited executed test or current implementation path |
| 331 | PY | tests/test_phase_3_slice_q3_streaming.py |
| 332 | REVIEW | No directly cited executed test or current implementation path |
| 333 | PY | tests/test_code_repo_files_api.py |
| 334 | PY | tests/test_api_codex_subscription.py |
| 335 | REVIEW | No directly cited executed test or current implementation path |
| 336 | REVIEW | No directly cited executed test or current implementation path |
| 337 | REVIEW | No directly cited executed test or current implementation path |
| 338 | REVIEW | No directly cited executed test or current implementation path |
| 339 | REVIEW | No directly cited executed test or current implementation path |
| 340 | REVIEW | No directly cited executed test or current implementation path |
| 341 | REVIEW | No directly cited executed test or current implementation path |
| 342 | REVIEW | No directly cited executed test or current implementation path |
| 343 | PY | tests/test_available_models.py |
| 344 | REVIEW | No directly cited executed test or current implementation path |
| 345 | REVIEW | No directly cited executed test or current implementation path |
| 346 | REVIEW | No directly cited executed test or current implementation path |
| 347 | REVIEW | No directly cited executed test or current implementation path |
| 348 | REVIEW | No directly cited executed test or current implementation path |
| 349 | REVIEW | No directly cited executed test or current implementation path |
| 350 | REVIEW | No directly cited executed test or current implementation path |
| 351 | REVIEW | No directly cited executed test or current implementation path |
| 352 | PY | tests/test_api_host.py |
| 353 | PY | tests/test_routes_auth.py |
| 354 | PY | tests/test_subscription_limits.py |
| 355 | REVIEW | No directly cited executed test or current implementation path |
| 356 | REVIEW | No directly cited executed test or current implementation path |
| 357 | PY | tests/test_api_codex_subscription.py |
| 358 | REVIEW | No directly cited executed test or current implementation path |
| 359 | REVIEW | No directly cited executed test or current implementation path |
| 360 | REVIEW | No directly cited executed test or current implementation path |
| 361 | PY | tests/test_api_host.py |
| 362 | PY | tests/test_routes_auth.py |
| 363 | PY | tests/test_api_speech_runtime.py |
| 364 | PY | tests/test_reset_live_workspace.py |
| 365 | PY | tests/test_local_runtime_presence.py |
| 366 | PY | tests/test_language_intelligence.py |
| 367 | PY | tests/test_task_conversation_thread.py |
| 368 | PY | tests/test_work_threads.py |
| 369 | PY | tests/test_partial_change_acceptance.py |
| 370 | PY | tests/test_provider_workspace_required.py |
| 371 | REVIEW | No directly cited executed test or current implementation path |
| 372 | PY | tests/test_provider_workspace_named.py |
| 373 | REVIEW | No directly cited executed test or current implementation path |
| 374 | PY | tests/test_task_finished_notification.py |
| 375 | PY | tests/test_edited_change_proposal.py |
| 376 | PY | tests/test_tool_schema_projection.py |
| 377 | PY | tests/test_mcp_declared_schemas.py |
| 378 | PY | tests/test_mcp_streamable_http.py |
| 379 | PY | tests/test_telemetry_export.py |
| 380 | PY | tests/test_hook_http_handler.py |
| 381 | PY | tests/test_task_surface_routing.py |
| 382 | REVIEW | No directly cited executed test or current implementation path |
| 383 | REVIEW | No directly cited executed test or current implementation path |
| 384 | REVIEW | No directly cited executed test or current implementation path |
| 385 | PY | tests/test_docs_consistency.py |
| 386 | PY | tests/test_telemetry_export.py |
| 387 | PY | tests/test_mcp_content_blocks.py |
| 388 | PY | tests/test_provider_workspace_named.py |
| 389 | REVIEW | No directly cited executed test or current implementation path |
| 390 | REVIEW | No directly cited executed test or current implementation path |
| 391 | REVIEW | No directly cited executed test or current implementation path |
| 392 | REVIEW | No directly cited executed test or current implementation path |
| 393 | REVIEW | No directly cited executed test or current implementation path |
| 394 | REVIEW | No directly cited executed test or current implementation path |
| 395 | REVIEW | No directly cited executed test or current implementation path |
| 396 | REVIEW | No directly cited executed test or current implementation path |
| 397 | REVIEW | No directly cited executed test or current implementation path |
| 398 | REVIEW | No directly cited executed test or current implementation path |
| 399 | REVIEW | No directly cited executed test or current implementation path |
| 400 | REVIEW | No directly cited executed test or current implementation path |
| 401 | REVIEW | No directly cited executed test or current implementation path |
| 402 | REVIEW | No directly cited executed test or current implementation path |
| 403 | REVIEW | No directly cited executed test or current implementation path |
| 404 | REVIEW | No directly cited executed test or current implementation path |
| 405 | REVIEW | No directly cited executed test or current implementation path |
| 406 | CODE | raiker/channels/adapters.py |
| 407 | PY | tests/test_python_version_guard.py |
| 408 | REVIEW | No directly cited executed test or current implementation path |
| 409 | CODE | raiker/app/tray.py |
| 410 | REVIEW | No directly cited executed test or current implementation path |
| 411 | PY | tests/test_mcp_server_initiated.py |
| 412 | PY | tests/test_mcp_event_stream.py |
| 413 | REVIEW | No directly cited executed test or current implementation path |
| 414 | REVIEW | No directly cited executed test or current implementation path |
| 415 | REVIEW | No directly cited executed test or current implementation path |
| 416 | REVIEW | No directly cited executed test or current implementation path |
| 417 | REVIEW | No directly cited executed test or current implementation path |
| 418 | REVIEW | No directly cited executed test or current implementation path |
| 419 | REVIEW | No directly cited executed test or current implementation path |
| 420 | CODE | raiker/models/conversion.py |
| 421 | REVIEW | No directly cited executed test or current implementation path |
| 422 | REVIEW | No directly cited executed test or current implementation path |
| 423 | REVIEW | No directly cited executed test or current implementation path |
| 424 | REVIEW | No directly cited executed test or current implementation path |
| 425 | REVIEW | No directly cited executed test or current implementation path |
| 426 | REVIEW | No directly cited executed test or current implementation path |
| 427 | REVIEW | No directly cited executed test or current implementation path |
| 428 | REVIEW | No directly cited executed test or current implementation path |
| 429 | REVIEW | No directly cited executed test or current implementation path |
| 430 | REVIEW | No directly cited executed test or current implementation path |
| 431 | REVIEW | No directly cited executed test or current implementation path |
| 432 | CODE | raiker/runtime/executors/sandbox.py |
| 433 | CODE | raiker/models/configured_models.py |
| 434 | REVIEW | No directly cited executed test or current implementation path |
| 435 | REVIEW | No directly cited executed test or current implementation path |
| 436 | PY | tests/test_config_path_resolution.py |
| 437 | PY | tests/test_model_local_operations.py |
| 438 | PY | tests/test_managed_llama_runtime.py |
| 439 | PY | tests/test_managed_llama_runtime.py |
| 440 | PY | tests/test_connector_ecosystem.py |
| 441 | PY | tests/test_event_log.py |
| 442 | PY | tests/test_local_runtime_presence.py |
| 443 | REVIEW | No directly cited executed test or current implementation path |
| 444 | REVIEW | No directly cited executed test or current implementation path |
| 445 | REVIEW | No directly cited executed test or current implementation path |
| 446 | REVIEW | No directly cited executed test or current implementation path |
| 447 | REVIEW | No directly cited executed test or current implementation path |
| 448 | REVIEW | No directly cited executed test or current implementation path |
| 449 | REVIEW | No directly cited executed test or current implementation path |
| 450 | REVIEW | No directly cited executed test or current implementation path |
| 451 | PY | tests/test_model_decision.py |
| 452 | PY | tests/test_surface_model_defaults.py |
| 453 | REVIEW | No directly cited executed test or current implementation path |
| 454 | REVIEW | No directly cited executed test or current implementation path |
| 455 | REVIEW | No directly cited executed test or current implementation path |
| 456 | REVIEW | No directly cited executed test or current implementation path |
| 457 | REVIEW | No directly cited executed test or current implementation path |
| 458 | REVIEW | No directly cited executed test or current implementation path |
| 459 | PY | tests/test_environment_context.py |
| 460 | PY | tests/test_weather_capability.py |
| 461 | PY | tests/test_global_read_capabilities.py |
| 462 | WEB | web/src/lib/huggingFaceSteps.test.ts |
| 463 | WEB | web/src/lib/returnAndDetect.test.ts |
| 464 | REVIEW | No directly cited executed test or current implementation path |
| 465 | REVIEW | No directly cited executed test or current implementation path |
| 466 | REVIEW | No directly cited executed test or current implementation path |
| 467 | PY | tests/test_code_repo_files_api.py |
| 468 | WEB | web/src/lib/extensionsOverview.ts |
| 469 | WEB | web/src/lib/workProject.svelte.ts |
| 470 | WEB | web/src/lib/taskComposer.ts |
| 471 | WEB | web/src/lib/buildModes.ts |
| 472 | WEB | web/src/lib/rowTokens.ts |
| 473 | REVIEW | No directly cited executed test or current implementation path |
| 474 | WEB | web/e2e/overlay-layers-live.spec.ts |
| 475 | REVIEW | No directly cited executed test or current implementation path |
| 476 | REVIEW | No directly cited executed test or current implementation path |
| 477 | REVIEW | No directly cited executed test or current implementation path |
| 478 | REVIEW | No directly cited executed test or current implementation path |
| 479 | REVIEW | No directly cited executed test or current implementation path |
| 480 | REVIEW | No directly cited executed test or current implementation path |
| 481 | WEB | web/e2e/display-and-theme-live.spec.ts |
| 482 | REVIEW | No directly cited executed test or current implementation path |
| 483 | WEB | web/src/lib/workSurface.ts |
| 484 | WEB | web/src/lib/workSurface.ts |
| 485 | WEB | web/src/lib/memoryHub.ts |
| 486 | WEB | web/src/lib/permissionLanguage.ts |
| 487 | PY | tests/test_provider_catalogue_memory.py |
| 488 | PY | tests/test_setup_state.py |
| 489 | PY | tests/test_provider_catalogue_memory.py |
| 490 | WEB | web/src/lib/modelReadinessGating.test.ts |
| 491 | PY | tests/test_image_lineage.py |
| 492 | WEB | web/src/lib/views/ProjectsView.test.ts |
| 493 | WEB | web/src/lib/views/CapabilitiesView.test.ts |
| 494 | WEB | web/src/lib/permissionViewModel.test.ts |
| 495 | WEB | web/src/lib/components/AuthorityMatrix.test.ts |
| 496 | WEB | web/src/lib/views/ProjectsView.test.ts |
| 497 | WEB | web/src/lib/views/ProjectsView.test.ts |
| 498 | WEB | web/src/lib/views/settings/Account.test.ts |
| 499 | WEB | web/src/lib/views/SettingsView.test.ts |
| 500 | PY | tests/test_mcp_process_environment.py |
| 501 | PY | tests/test_owner_identity_presentation.py |
| 502 | WEB | web/src/lib/components/WorkMeta.test.ts |
| 503 | REVIEW | No directly cited executed test or current implementation path |
| 504 | PY | tests/test_mcp_endpoint_policy.py |
| 505 | PY | tests/test_capability_permissions_copy.py |
| 506 | WEB | web/src/lib/freshness.ts |
| 507 | REVIEW | No directly cited executed test or current implementation path |
| 508 | REVIEW | No directly cited executed test or current implementation path |
| 509 | PY | tests/test_knowledge_source_review_budget.py |
| 510 | REVIEW | No directly cited executed test or current implementation path |
| 511 | PY | tests/test_work_thread_index.py |
| 512 | REVIEW | No directly cited executed test or current implementation path |
| 513 | WEB | web/e2e/removal-review-permissions-2026-09-14-live.spec.ts |
| 514 | REVIEW | No directly cited executed test or current implementation path |
| 515 | PY | tests/test_api_updates.py |
| 516 | REVIEW | No directly cited executed test or current implementation path |
| 517 | REVIEW | No directly cited executed test or current implementation path |
| 518 | REVIEW | No directly cited executed test or current implementation path |
| 519 | REVIEW | No directly cited executed test or current implementation path |
| 520 | REVIEW | No directly cited executed test or current implementation path |
| 521 | REVIEW | No directly cited executed test or current implementation path |
| 522 | REVIEW | No directly cited executed test or current implementation path |
| 523 | REVIEW | No directly cited executed test or current implementation path |
| 524 | PY | tests/test_governance_entry_paths.py |
| 525 | PY | tests/test_model_decision.py |
| 526 | WEB | web/src/lib/providerErrors.test.ts |
| 527 | PY | tests/test_api_huggingface_models.py |
| 528 | REVIEW | No directly cited executed test or current implementation path |
| 529 | REVIEW | No directly cited executed test or current implementation path |
| 530 | REVIEW | No directly cited executed test or current implementation path |
| 531 | REVIEW | No directly cited executed test or current implementation path |
| 532 | REVIEW | No directly cited executed test or current implementation path |
| 533 | WEB | web/src/lib/taskLifecycle.ts |
| 534 | REVIEW | No directly cited executed test or current implementation path |
| 535 | PY | tests/test_task_attempt_history.py |
| 536 | WEB | web/src/lib/views/settings/Notification.test.ts |
| 537 | REVIEW | No directly cited executed test or current implementation path |
| 538 | WEB | web/src/lib/views/DesignView.test.ts |
| 539 | WEB | web/e2e/bug-280-clock-from-a-real-turn-live.spec.ts |
| 540 | WEB | web/src/lib/views/TasksView.test.ts |
| 541 | REVIEW | No directly cited executed test or current implementation path |
| 542 | PY | tests/test_governance_entry_paths.py |
| 543 | REVIEW | No directly cited executed test or current implementation path |
| 544 | CODE | raiker/runtime/authority/baseline.py |
| 545 | CODE | raiker/runtime/typed_parts.py |
| 546 | REVIEW | No directly cited executed test or current implementation path |
| 547 | REVIEW | No directly cited executed test or current implementation path |
| 548 | REVIEW | No directly cited executed test or current implementation path |
| 549 | WEB | web/e2e/naming.ts |
| 550 | CODE | raiker/runtime/orchestrator.py |
| 551 | REVIEW | No directly cited executed test or current implementation path |
| 552 | REVIEW | No directly cited executed test or current implementation path |
| 553 | REVIEW | No directly cited executed test or current implementation path |
| 554 | REVIEW | No directly cited executed test or current implementation path |
| 555 | REVIEW | No directly cited executed test or current implementation path |
| 556 | REVIEW | No directly cited executed test or current implementation path |
| 557 | REVIEW | No directly cited executed test or current implementation path |
| 558 | CODE | raiker/events/summaries.py |
| 559 | REVIEW | No directly cited executed test or current implementation path |
| 560 | REVIEW | No directly cited executed test or current implementation path |
| 561 | REVIEW | No directly cited executed test or current implementation path |
| 562 | REVIEW | No directly cited executed test or current implementation path |
| 563 | REVIEW | No directly cited executed test or current implementation path |
| 564 | REVIEW | No directly cited executed test or current implementation path |
| 565 | REVIEW | No directly cited executed test or current implementation path |
| 566 | REVIEW | No directly cited executed test or current implementation path |
| 567 | PY | tests/test_owner_consent_and_history.py |
| 568 | PY | tests/test_owner_consent_and_history.py |
| 569 | PY | tests/test_connector_ecosystem.py |
| 570 | PY | tests/test_bug_206_207_tool_rows_and_reasoning.py |
| 571 | PY | tests/test_sqlite_connection_cache.py |
| 572 | PY | tests/test_redaction_middleware_content_types.py |
| 573 | PY | tests/test_attached_root_watcher.py |
| 574 | PY | tests/test_release_workflow.py |
| 575 | PY | tests/test_api_contract_schemas.py |
| 576 | PY | tests/test_work_thread_index.py |
| 577 | WEB | web/src/lib/components/SessionMenu.test.ts |
| 578 | PY | tests/test_git_credential_grant.py |
| 579 | WEB | web/src/lib/views/settings/WebAccess.test.ts |
| 580 | WEB | web/src/lib/views/settings/Runtime.test.ts |
| 581 | WEB | web/src/lib/components/TurnEvidence.test.ts |
| 582 | WEB | web/src/lib/buildArtifacts.test.ts |
| 583 | WEB | web/src/lib/modelReadinessGating.test.ts |
| 584 | PY | tests/test_task_schedule_preview_contract.py |
| 585 | WEB | web/src/lib/views/ProjectsView.test.ts |
| 586 | WEB | web/src/lib/views/DesignView.test.ts |
| 587 | WEB | web/src/lib/views/settings/MemoryEngine.test.ts |
| 588 | PY | tests/test_governed_execution_off_the_loop.py |
| 589 | PY | tests/test_web_workflow.py |
| 590 | WEB | web/src/lib/turnFailure.ts |
| 591 | WEB | web/src/lib/conversationCommands.ts |
| 592 | PY | tests/test_knowledge_sources_inventory.py |
| 593 | PY | tests/test_instance_runtime_lifecycle.py |
| 594 | PY | tests/test_instance_runtime_lifecycle.py |
| 595 | PY | tests/test_storage_sqlite.py |
| 596 | PY | tests/test_provider_client_pool.py |
| 597 | PY | tests/test_model_registry_resolve_fallback.py |
| 598 | WEB | web/src/lib/buildIdentity.test.ts |
| 599 | PY | tests/test_api_rest_hardening.py |
| 600 | WEB | web/src/lib/nav.test.ts |
| 601 | REVIEW | No directly cited executed test or current implementation path |
| 602 | PY | tests/test_docs_consistency.py |
| 603 | PY | tests/test_stop_all_work.py |
| 604 | PY | tests/test_routed_authority.py |
| 605 | PY | tests/test_mcp_monitor_fail_safe.py |
| 606 | PY | tests/test_critical_recipient_normalization.py |
| 607 | PY | tests/test_embedding_trusted_classification.py |
| 608 | PY | tests/test_attachment_chunk_invariant.py |
| 609 | PY | tests/test_api_rest_hardening.py |
| 610 | PY | tests/test_prompt_turn_preparation.py |
| 611 | PY | tests/test_ci_workflow.py |
| 612 | REVIEW | No directly cited executed test or current implementation path |
| 613 | REVIEW | No directly cited executed test or current implementation path |
| 614 | PY | tests/test_redaction_middleware_content_types.py |
| 615 | PY | tests/test_release_workflow.py |
| 616 | CODE | raiker/storage/sqlite.py |
| 617 | PY | tests/test_internal_path_audit.py |
| 618 | REVIEW | No directly cited executed test or current implementation path |
| 619 | PY | tests/test_executor_authority_boundary.py |
| 620 | PY | tests/test_bug_308_code_placement.py |
| 621 | WEB | web/src/lib/components/ApprovalPrompt.test.ts |
| 622 | WEB | web/src/lib/noticeDestination.ts |
| 623 | PY | tests/test_api_request_models.py |
| 624 | PY | tests/test_api_dependencies.py |
| 625 | PY | tests/test_migration_registry.py |
| 626 | PY | tests/test_readiness_failure_classifier.py |
| 627 | PY | tests/test_provider_display_names.py |
| 628 | PY | tests/test_documentation_validators.py |
| 629 | PY | tests/test_measure_loc.py |
| 630 | PY | tests/test_docs_consistency.py |
| 631 | PY | tests/test_sqlite_connection_cache.py |
| 632 | REVIEW | No directly cited executed test or current implementation path |
| 633 | WEB | web/src/lib/views/settings/Personalisation.test.ts |
| 634 | PY | tests/test_provider_http_transport.py |
| 635 | PY | tests/test_slot_runtime.py |
| 636 | PY | tests/test_model_decision.py |
| 637 | PY | tests/test_operation_worker_harness.py |
| 638 | CODE | raiker/contracts/views.py |
| 639 | CODE | raiker/control/project_migration.py |
| 640 | PY | tests/test_store_query_helpers.py |
| 641 | PY | tests/test_reason_code_catalogue.py |
| 642 | REVIEW | No directly cited executed test or current implementation path |
| 643 | REVIEW | No directly cited executed test or current implementation path; additional Python path not correlated to passing test |
| 644 | PY | tests/test_local_runtime_presence.py |
| 645 | REVIEW | No directly cited executed test or current implementation path |
| 646 | PY | tests/test_web_workflow.py |
| 647 | PY | tests/test_project_lifecycle.py |
| 648 | PY | tests/test_project_lifecycle.py |
| 649 | PY | tests/test_project_lifecycle.py |
| 650 | PY | tests/test_project_lifecycle.py |
| 651 | PY | tests/test_project_lifecycle.py |
| 652 | PY | tests/test_project_lifecycle.py |
| 653 | REVIEW | No directly cited executed test or current implementation path |
| 654 | PY | tests/test_instance_runtime_lifecycle.py |
| 655 | PY | tests/test_tool_registry.py |
| 656 | PY | tests/test_comment_policy.py |
| 657 | WEB | web/e2e/live.ts |
| 658 | REVIEW | No directly cited executed test or current implementation path |
| 659 | REVIEW | No directly cited executed test or current implementation path |
| 660 | REVIEW | No directly cited executed test or current implementation path |
| 661 | WEB | web/src/lib/layoutWatch.ts |
| 662 | REVIEW | No directly cited executed test or current implementation path |
| 663 | PY | tests/test_instance_runtime_lifecycle.py |
| 664 | PY | tests/test_api_contract_responses.py |
| 665 | PY | tests/test_web_api_routes.py |
| 666 | REVIEW | No directly cited executed test or current implementation path |
| 667 | REVIEW | No directly cited executed test or current implementation path |
| 668 | REVIEW | No directly cited executed test or current implementation path |
| 669 | REVIEW | No directly cited executed test or current implementation path |
| 670 | PY | tests/test_routes_auth.py |
| 671 | PY | tests/test_api_contract_responses.py |
| 672 | PY | tests/test_api_contract_responses.py |
| 673 | PY | tests/test_api_contract_responses.py |
| 674 | REVIEW | No directly cited executed test or current implementation path |
| 675 | PY | tests/test_token_count_redaction.py |
| 676 | REVIEW | No directly cited executed test or current implementation path |
| 677 | REVIEW | No directly cited executed test or current implementation path |
| 678 | PY | tests/test_api_contract_responses.py |
| 679 | PY | tests/test_web_api_routes.py |
| 680 | PY | tests/test_api_contract_responses.py |
| 681 | REVIEW | No directly cited executed test or current implementation path |
| 682 | PY | tests/test_context_surface_scoping.py |
| 683 | PY | tests/test_api_contract_responses.py |
| 684 | REVIEW | No directly cited executed test or current implementation path |
| 685 | REVIEW | No directly cited executed test or current implementation path |
| 686 | REVIEW | No directly cited executed test or current implementation path |
| 687 | PY | tests/test_memory_lifecycle_usage_import.py |
| 688 | REVIEW | No directly cited executed test or current implementation path |
| 689 | REVIEW | No directly cited executed test or current implementation path |
| 690 | WEB | web/src/lib/memoryEvidence.ts |
| 691 | PY | tests/test_memory_lifecycle_usage_import.py |
| 692 | CODE | raiker/runtime/retrieval.py |
| 693 | REVIEW | No directly cited executed test or current implementation path |
| 694 | PY | tests/test_memory_lifecycle_usage_import.py |
| 695 | WEB | web/src/lib/permissionGoals.ts |
| 696 | PY | tests/test_task_schedule_terms.py |
| 697 | REVIEW | No directly cited executed test or current implementation path |
| 698 | REVIEW | No directly cited executed test or current implementation path |
| 699 | REVIEW | No directly cited executed test or current implementation path |
| 700 | PY | tests/test_task_lifecycle_phases.py |
| 701 | REVIEW | No directly cited executed test or current implementation path |
| 702 | REVIEW | No directly cited executed test or current implementation path |
| 703 | REVIEW | No directly cited executed test or current implementation path |
| 704 | REVIEW | No directly cited executed test or current implementation path |
| 705 | REVIEW | No directly cited executed test or current implementation path |
| 706 | REVIEW | No directly cited executed test or current implementation path |
| 707 | REVIEW | No directly cited executed test or current implementation path |
| 708 | REVIEW | No directly cited executed test or current implementation path |
| 709 | REVIEW | No directly cited executed test or current implementation path |
| 710 | REVIEW | No directly cited executed test or current implementation path |
| 711 | REVIEW | No directly cited executed test or current implementation path |
| 712 | REVIEW | No directly cited executed test or current implementation path |
| 713 | REVIEW | No directly cited executed test or current implementation path |
| 714 | REVIEW | No directly cited executed test or current implementation path |
| 715 | REVIEW | No directly cited executed test or current implementation path |
| 716 | REVIEW | No directly cited executed test or current implementation path |
| 717 | REVIEW | No directly cited executed test or current implementation path |
| 718 | REVIEW | No directly cited executed test or current implementation path |
| 719 | REVIEW | No directly cited executed test or current implementation path |
| 720 | REVIEW | No directly cited executed test or current implementation path |
| 721 | REVIEW | No directly cited executed test or current implementation path |
| 722 | REVIEW | No directly cited executed test or current implementation path |
| 723 | REVIEW | No directly cited executed test or current implementation path |
| 724 | REVIEW | No directly cited executed test or current implementation path |
| 725 | PY | tests/test_model_readiness_steps.py |
| 726 | PY | tests/test_api_dashboard.py |
| 727 | REVIEW | No directly cited executed test or current implementation path |
| 728 | REVIEW | No directly cited executed test or current implementation path |
| 729 | REVIEW | No directly cited executed test or current implementation path |
| 730 | WEB | web/e2e/round-2026-10-03-models-build-design-live.spec.ts |
| 731 | PY | tests/test_image_lifecycle.py |
| 732 | REVIEW | No directly cited executed test or current implementation path |
| 733 | PY | tests/test_image_references.py |
| 734 | PY | tests/test_approval_execution_wiring.py |
| 735 | REVIEW | No directly cited executed test or current implementation path |
| 736 | REVIEW | No directly cited executed test or current implementation path |
| 737 | PY | tests/test_local_model_service.py |
| 738 | CODE | raiker/models/local_service.py |
| 739 | REVIEW | No directly cited executed test or current implementation path |
| 740 | PY | tests/test_build_boundary.py |
| 741 | PY | tests/test_mcp_stdio_bounds.py |
| 742 | REVIEW | No directly cited executed test or current implementation path |
| 743 | PY | tests/test_design_revert.py |
| 744 | REVIEW | No directly cited executed test or current implementation path |
| 745 | REVIEW | No directly cited executed test or current implementation path |
| 746 | REVIEW | No directly cited executed test or current implementation path |
| 747 | REVIEW | No directly cited executed test or current implementation path |
| 748 | REVIEW | No directly cited executed test or current implementation path |
| 749 | REVIEW | No directly cited executed test or current implementation path |
| 750 | PY | tests/test_provider_http_transport.py |
| 751 | PY | tests/test_provider_http_transport.py |
| 752 | PY | tests/test_ingress_body_deadline.py |
| 753 | PY | tests/test_mcp_tool_review.py |
| 754 | PY | tests/test_mcp_tool_review.py |
| 755 | WEB | web/src/lib/leaveGuard.ts |
| 756 | REVIEW | No directly cited executed test or current implementation path |
| 757 | PY | tests/test_routine_failure_limit.py |
| 758 | REVIEW | No directly cited executed test or current implementation path |
| 759 | REVIEW | No directly cited executed test or current implementation path |
| 760 | REVIEW | No directly cited executed test or current implementation path |
| 761 | REVIEW | No directly cited executed test or current implementation path |
| 762 | PY | tests/test_store_key_guard.py |
| 763 | PY | tests/test_text_index_damage.py |
| 764 | REVIEW | No directly cited executed test or current implementation path |
| 765 | REVIEW | No directly cited executed test or current implementation path |
| 766 | REVIEW | No directly cited executed test or current implementation path |
| 767 | REVIEW | No directly cited executed test or current implementation path |
| 768 | REVIEW | No directly cited executed test or current implementation path |
| 769 | REVIEW | No directly cited executed test or current implementation path |
| 770 | REVIEW | No directly cited executed test or current implementation path |
| 771 | REVIEW | No directly cited executed test or current implementation path |
| 772 | PY | tests/test_ingress_body_encoding.py |
| 773 | REVIEW | No directly cited executed test or current implementation path |
| 774 | REVIEW | No directly cited executed test or current implementation path |
| 775 | REVIEW | No directly cited executed test or current implementation path |
| 776 | PY | tests/test_notification_quiet_hours.py |
| 777 | REVIEW | No directly cited executed test or current implementation path |
| 778 | REVIEW | No directly cited executed test or current implementation path |
| 779 | REVIEW | No directly cited executed test or current implementation path |
| 780 | REVIEW | No directly cited executed test or current implementation path |
| 781 | REVIEW | No directly cited executed test or current implementation path |
| 782 | REVIEW | No directly cited executed test or current implementation path |
| 783 | PY | tests/test_search_index_health.py |
| 784 | PY | tests/test_search_index_health.py |
| 785 | PY | tests/test_routine_run_limit_and_doctor.py |
| 786 | PY | tests/test_routine_run_limit_and_doctor.py |
| 787 | REVIEW | No directly cited executed test or current implementation path |
| 788 | REVIEW | No directly cited executed test or current implementation path |
| 789 | PY | tests/test_workspace_backups.py |
| 790 | REVIEW | No directly cited executed test or current implementation path |
| 791 | REVIEW | No directly cited executed test or current implementation path |
| 792 | REVIEW | No directly cited executed test or current implementation path |
| 793 | PY | tests/test_settings_revision.py |
| 794 | PY | tests/test_notification_quiet_hours.py |
| 795 | REVIEW | No directly cited executed test or current implementation path |
| 796 | PY | tests/test_scheduler_queue_health.py |
| 797 | PY | tests/test_routine_run_limit_and_doctor.py |
| 798 | WEB | web/e2e/capture.ts |
| 799 | REVIEW | No directly cited executed test or current implementation path |
| 800 | PY | tests/test_setup_backup.py |
| 801 | PY | tests/test_lock_screen_recovery.py |
| 802 | PY | tests/test_lock_screen_recovery.py |
| 803 | PY | tests/test_lock_screen_recovery.py |
| 804 | PY | tests/test_model_tool_call_loop.py |
| 805 | PY | tests/test_environment_context.py |
| 806 | PY | tests/test_environment_context.py |
| 807 | REVIEW | No directly cited executed test or current implementation path |
| 808 | PY | tests/test_api_decision_modes.py |
| 809 | PY | tests/test_idempotency_keys.py |
| 810 | PY | tests/test_model_cost_accounting.py |
| 811 | REVIEW | No directly cited executed test or current implementation path |
| 812 | PY | tests/test_lock_screen_recovery.py |
| 813 | PY | tests/test_mcp_tool_review.py |
| 814 | PY | tests/test_mcp_runtime.py |
| 815 | PY | tests/test_channel_owner_surface.py |
| 816 | PY | tests/test_projects.py |
| 817 | PY | tests/test_channel_owner_surface.py |
| 818 | REVIEW | No directly cited executed test or current implementation path |
| 819 | PY | tests/test_routes_settings.py |
| 820 | PY | tests/test_api_updates.py |
| 821 | PY | tests/test_workspace_backups.py |
| 822 | PY | tests/test_release_pipeline.py |
| 823 | PY | tests/test_scan_secrets.py |
| 824 | PY | tests/test_recovery_matrix.py |
| 825 | PY | tests/test_task_scheduler.py |
| 826 | PY | tests/test_git_credential_grant.py |
| 827 | REVIEW | No directly cited executed test or current implementation path |
| 828 | PY | tests/test_signed_updates.py |
| 829 | PY | tests/test_signed_updates.py |
| 830 | PY | tests/test_signed_updates.py |
| 831 | PY | tests/test_signed_updates.py |
| 832 | PY | tests/test_signed_updates.py |
| 833 | PY | tests/test_task_scheduler.py |
| 834 | PY | tests/test_phase_4_plugin_install_runtime.py |
| 835 | PY | tests/test_scan_sast.py |
| 836 | PY | tests/test_document_attachments.py |
| 837 | PY | tests/test_scan_containers.py |
| 838 | PY | tests/test_phase_4_channels.py |
| 839 | PY | tests/test_phase_4_channels.py |
| 840 | PY | tests/test_model_tool_call_loop.py |
| 841 | PY | tests/test_model_provider_contract_regressions.py |
| 842 | PY | tests/test_storage_space_health.py |
| 843 | REVIEW | No directly cited executed test or current implementation path |
| 844 | PY | tests/test_channel_inbound_dedup.py |
| 845 | PY | tests/test_channel_inbound_dedup.py |
| 846 | PY | tests/test_channel_enable_needs_test.py |
| 847 | PY | tests/test_memory_pressure_health.py |
| 848 | PY | tests/test_scan_images.py |
| 849 | PY | tests/test_task_scheduler.py |
| 850 | PY | tests/test_due_work_beside_the_tick.py |
| 851 | PY | tests/test_turn_stop_and_steer.py |
| 852 | PY | tests/test_turn_model_fallback.py |
| 853 | PY | tests/test_ingress_body_concurrency.py |
| 854 | PY | tests/test_hook_fail_closed.py |
| 855 | PY | tests/test_channel_outbound_receipts.py |
| 856 | PY | tests/test_channel_inbound_dedup.py |
| 857 | PY | tests/test_execution_environment_off.py |
| 858 | REVIEW | No directly cited executed test or current implementation path |
| 859 | REVIEW | No directly cited executed test or current implementation path |
| 860 | REVIEW | No directly cited executed test or current implementation path |
| 861 | PY | tests/test_hf_repo_id_redaction.py |
| 862 | PY | tests/test_hf_repo_id_redaction.py |
| 863 | PY | tests/test_scan_containers.py |
| 864 | PY | tests/test_mcp_server_secrets.py |
| 865 | PY | tests/test_execution_environment_remove.py |
| 866 | PY | tests/test_channel_delivery_review.py |
| 867 | PY | tests/test_channel_delivery_review.py |
| 868 | PY | tests/test_channel_delivery_review.py |
| 869 | PY | tests/test_channel_delivery_review.py |
| 870 | PY | tests/test_memory_forget_suppression.py |
| 871 | PY | tests/test_turn_retry_link.py |
| 872 | PY | tests/test_stopped_stream_usage.py |
| 873 | PY | tests/test_attention_feed.py |
| 874 | PY | tests/test_memory_review_priority.py |
| 875 | PY | tests/test_control_command_sequence.py |
| 876 | PY | tests/test_channel_inbound_signature.py |
| 877 | PY | tests/test_memory_forget_suppression.py |
| 878 | REVIEW | No directly cited executed test or current implementation path |
| 879 | REVIEW | No directly cited executed test or current implementation path |
| 880 | REVIEW | No directly cited executed test or current implementation path |
| 881 | CODE | raiker/models/tool_registry.py |
| 882 | PY | tests/test_git_push_path.py |
| 883 | PY | tests/test_git_credential_grant.py |
| 884 | PY | tests/test_git_push_binding.py |
| 885 | PY | tests/test_repository_delegations.py |
| 886 | PY | tests/test_repository_delegations.py |
| 887 | PY | tests/test_api_contract_responses.py |

## Scope limitations

This audit read GitHub repository content and successfully completed GitHub Actions logs; no complete Raiker workspace was available locally, no provider credentials were supplied, and no real services, browsers, Windows Python suite, integration environments or live competitor products were exercised anew. GitHub `main` CI is valid for its exact SHA; subsequent code changes would require new evidence. A row labeled PY establishes a linked passing test **file**, not that every assertion promised in the prose was verified.
