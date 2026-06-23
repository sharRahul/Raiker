# Capability Registry & Risk Tiers

> The canonical map of every capability gate to its risk tier, executor target,
> runtime mode, and activation requirements. Source of truth for the capability
> set is `raiker/phase_gates.py` (`ALL_CAPABILITIES = PHASE_3_CAPABILITIES |
> PHASE_4_DISABLED_CAPABILITIES | RUNTIME_DOMAIN_CAPABILITIES`). All ship
> `disabled`.

Legend — **Tier**: 1 lowest risk … 6 most sensitive; `gov` = governance mutation;
`ui` = UI-contract capability (no executor, surfaced as client contract).
**HC** = `requires_human_confirmation_to_enable`. **Mode** = required active
runtime mode to reach `enabled_runtime`.

## Runtime-domain capabilities (`RUNTIME_DOMAIN_CAPABILITIES`)

| Capability | Tier | HC | Mode | Executor target / notes |
|---|---|---|---|---|
| `approval_execution_relay` | 1 | no | local_single_user_runtime | Execute approved proposals. **First slice.** |
| `file_write_execution` | 1 | no | local_single_user_runtime | `raiker/tools/filesystem.py` write/edit under gate. |
| `patch_apply_execution` | 1 | no | local_single_user_runtime | apply_patch under gate. |
| `memory_write_execution` | 1 | no | local_single_user_runtime | Durable memory write (governed path exists). |
| `memory_forget_execution` | 1 | no | local_single_user_runtime | Durable memory forget. |
| `shell_execution` | 2 | yes | local_single_user_runtime | Sandbox, allowlist, timeout, output cap. |
| `process_execution` | 2 | yes | local_single_user_runtime | Sandboxed subprocess. |
| `web_fetch` | 2 | yes | local_single_user_runtime | Egress allowlist, no SSRF, redact body. |
| `network_execution` | 2 | yes | local_single_user_runtime | Egress allowlist. |
| `graph_indexing_runtime` | 3 | no | local_single_user_runtime | Real graph writes (`raiker/graph/`). |
| `semantic_memory_runtime` | 3 | no | local_single_user_runtime | Semantic writes (`raiker/memory/`). |
| `vector_embedding_runtime` | 3 | no | local_single_user_runtime | Embeddings + vector store (`raiker/vector/`). |
| `plugin_install` | 4 | yes | local_single_user_runtime | Signature/checksum verify, permission diff. |
| `plugin_execution_cap` | 4 | yes | local_single_user_runtime | Sandbox, revocation. |
| `external_channel_runtime` | 5 | yes | multi_user_local_runtime | Connector auth, outbound allowlist. |
| `channel_approval_relay` | 5 | yes | multi_user_local_runtime | Approval relay over channels. |
| `remote_execution_cap` | 5 | yes | hosted_or_networked_runtime | Isolation, secrets, egress, budget. |
| `container_execution_cap` | 5 | yes | hosted_or_networked_runtime | Container isolation. |
| `cloud_execution_cap` | 5 | yes | hosted_or_networked_runtime | Cloud isolation, budget. |
| `model_provider_runtime` | 3 | no | local_single_user_runtime | Local provider calls (largely active via gateway; confirm gate). |
| `hosted_model_runtime` | 5 | yes | hosted_or_networked_runtime | Egress + budget policy. |
| `private_network_model_runtime` | 5 | yes | hosted_or_networked_runtime | Network + egress policy. |
| `scheduled_routines` | 5 | yes | local_single_user_runtime | Scheduler storage, owner consent, budget. |
| `email_runtime` | 6 | yes | local_single_user_runtime | Domain: `email`. Per-domain threat model. |
| `calendar_runtime` | 6 | yes | local_single_user_runtime | Domain: `calendar`. |
| `reminder_runtime` | 6 | yes | local_single_user_runtime | Domain: `reminders`. |
| `finance_runtime` | 6 | yes | local_single_user_runtime | Domain: `finance`. |
| `investment_runtime` | 6 | yes | local_single_user_runtime | Domain: `investments`. |
| `medical_runtime` | 6 | yes | local_single_user_runtime | Domain: `medical`. |
| `pregnancy_baby_runtime` | 6 | yes | local_single_user_runtime | Domain: `pregnancy_baby`. |
| `cctv_runtime` | 6 | yes | local_single_user_runtime | Domain: `cctv`. |
| `home_security_runtime` | 6 | yes | local_single_user_runtime | Domain: `home_security`. |
| `hardware_operator_runtime` | 6 | yes | local_single_user_runtime | Domain: `hardware`. |
| `admin_mutation` | gov | yes | local_single_user_runtime | Governed mutation path (`_govern_admin_mutation`). |
| `policy_mutation` | gov | yes | local_single_user_runtime | Governed policy change. |
| `role_mutation` | gov | yes | local_single_user_runtime | Governed role change. |
| `audit_export` | gov | no | local_single_user_runtime | Export with redaction + integrity. |

## Phase-3 / Phase-4 capabilities

| Capability | Tier | Notes |
|---|---|---|
| `desktop_ui`, `web_ui`, `dashboard` | ui | Client contracts; no executor. Surfaced to the UI program, not Workstream D. |
| `plugin_execution`, `graph_codemap_indexing`, `semantic_memory_writes` | — | Aliased to the runtime caps above; correct the Phase 7 overclaim when those land. |
| `graph_codemap_planning`, `semantic_memory_review_queue` | — | Already `policy_ready`; planning/review only. |
| `subagents`, `multi_agent_teams` | 5 | Spawning/team runtime; isolation + budgets (see `raiker/agents/subagents.py` stub). |
| `remote_execution`, `container_execution`, `external_channels` | 5 | Aliases for the runtime caps above. |

## Activation requirement defaults (Workstream C)

Every capability starts **unsatisfiable**: `requires_executor=True` while no
executor is registered. As each Workstream D executor lands, its
`ActivationRequirement` becomes satisfiable. Tiers ≥2 and all Tier 6 / `gov`
set `requires_human_confirmation_to_enable=True` and
`requires_threat_model_ack=True`.

## Scheduling note

Assign concrete `RAIKER-D1xx … D6xx` task numbers per row when you start each tier.
Build strictly in tier order; do not begin a tier until the previous tier's
executors pass the §5 gate and their status is recorded in
`docs/IMPLEMENTATION_STATUS.md`.
</content>
