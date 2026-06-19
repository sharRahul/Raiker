# Raiker Tool and Plugin Catalog

This catalog is the Raiker-native inventory of tools and plugin components that must be tracked across implementation stages.

It is intentionally written in Raiker terminology. A row in this file is **not** runtime activation approval. Every tool and plugin component must still pass Raiker contracts, policy, storage, event logging, approval, UI parity, security, and acceptance-test gates before it can execute.

---

## Implementation status legend

| Implemented value | Meaning |
|---|---|
| `Yes — Phase N` | Implemented and verified for the named phase scope. |
| `Partial — Phase N` | Some safe/read-only/planning behavior exists, but runtime capability is incomplete or disabled. |
| `No — Phase N planned` | Specified and phase-scheduled, but not implemented. |
| `No — disabled until Phase N` | Must remain disabled until the named phase gates are complete. |
| `Never direct` | Not a direct runtime tool; only available through another brokered contract or manifest boundary. |

---

## Permission vocabulary

These permission labels are used in the inventory below so coding agents know what policy gates are required.

| Permission | Meaning |
|---|---|
| `none` | No additional tool permission; metadata-only/read-only command. |
| `workspace:read` | Read files/directories inside the approved workspace. |
| `workspace:search` | Search filenames or file content inside the approved workspace. |
| `workspace:write` | Create/update/delete/move/copy files; approval required unless a later policy explicitly scopes it. |
| `git:read` | Read Git status/diff/log metadata. |
| `git:write` | Branch/commit/merge/push or other Git mutation; approval required. |
| `command:propose` | Propose a command for approval; does not execute directly. |
| `command:execute` | Execute a command after policy and approval. |
| `process:monitor` | Start/watch/cancel bounded background monitors. |
| `model:read` | Read model/provider/profile status. |
| `model:launch` | Start or switch a local/hosted model provider. |
| `memory:read` | Read governed memory candidates/status. |
| `memory:write` | Persist/update/delete governed memory; approval and governance required. |
| `semantic_memory:write` | Persist semantic/vector memory; disabled until Phase 3 gates complete. |
| `graph:read` | Read graph/codemap status or query existing graph metadata. |
| `graph:plan` | Prepare dry-run graph/codemap plans. |
| `graph:write` | Write graph nodes/edges; disabled until a later explicit gate. |
| `approval:read` | Read approval, approval-preview, audit, or handoff metadata. |
| `approval:resolve` | Approve/deny/defer exact action-bound approvals. |
| `rollback:plan` | Prepare rollback plans; no execution. |
| `rollback:execute` | Execute rollback; disabled until a later explicit gate. |
| `storage_lifecycle:read` | Read Slice G lifecycle metadata. |
| `storage_lifecycle:plan` | Create metadata-only lifecycle/retention/cleanup/handoff plans. |
| `storage_lifecycle:write_metadata` | Write lifecycle metadata tables only; no graph/vector/memory runtime writes. |
| `network:egress` | Access public/private network resources. |
| `mcp:read` | Read MCP resources from trusted configured servers. |
| `mcp:server_start` | Start/wait for MCP servers; disabled until trust and approval gates. |
| `lsp:read` | Read language-server diagnostics/symbol/code intelligence. |
| `lsp:server_start` | Start language servers; disabled until workspace/plugin trust gates. |
| `plugin:validate` | Validate plugin metadata without executing code. |
| `plugin:register` | Register plugin metadata/plans; no code execution. |
| `plugin:execute` | Execute plugin code/entrypoints; disabled until explicit gates. |
| `channel:read` | Read/list configured channel profiles/status. |
| `channel:activate` | Activate external transports; disabled until Phase 4 pairing and trust. |
| `agent:plan` | Plan subagent/team work without spawning. |
| `agent:execute` | Spawn subagents/team workflows; disabled until Phase 4 gates. |
| `remote:plan` | Produce denied/planned remote/container execution profiles. |
| `remote:execute` | Execute remote/container/cloud jobs; disabled until Phase 4/5 gates. |
| `notify:local` | Send local notification. |
| `notify:hosted` | Hosted push/share-link notification; disabled until Phase 5. |
| `config:read` | Read configuration/profile metadata. |
| `config:write` | Write scoped settings/config; approval required. |
| `audit:export` | Export audit/session/security records; approval/redaction required. |
| `marketplace:read` | Discover plugin packages/registry metadata. |
| `marketplace:install` | Install/update marketplace plugins; disabled until Phase 5 supply-chain controls. |

---

## Raiker core tool inventory

| Tool Name | Descriptions | Permissions | Implemented |
|---|---|---|---|
| `normal_prompt` | Submit a standard user prompt into the Agent Gateway. | `none` | Yes — Phase 1 |
| `ask_user` | Ask a blocking clarification question. | `none` | Partial — Phase 1 runtime conversation path |
| `side_question` | Ask a non-blocking side question while a task continues. | `none` | Yes — Phase 2 contract/runtime path |
| `enter_plan_mode` | Switch a turn into explicit planning mode. | `none` | Partial — Phase 2 planning/status behavior |
| `exit_plan_mode` | Present a plan for review/approval and leave planning mode. | `approval:read` | Partial — Phase 2 planning/status behavior |
| `create_task` | Create tracked task metadata. | `none` | Yes — Phase 2 |
| `update_task` | Update task status, detail, dependencies, or progress. | `none` | Yes — Phase 2 |
| `list_tasks` | List task records. | `none` | Yes — Phase 2 |
| `get_task` | Read details for one task. | `none` | Yes — Phase 2 |
| `stop_task` | Stop/cancel a tracked task at a safe boundary. | `none`; later `process:monitor` if cancelling processes | Partial — Phase 2 metadata only; process cancellation not active |
| `read_file` | Read workspace text files. | `workspace:read` | Yes — Phase 1 |
| `list_directory` | List workspace directories. | `workspace:read` | Yes — Phase 1 |
| `glob` | Find files by workspace-scoped pattern. | `workspace:search` | Yes — Phase 1 |
| `grep` | Search file contents in workspace. | `workspace:search` | Yes — Phase 1 |
| `stat_path` | Read file/directory metadata. | `workspace:read` | Yes — Phase 2 |
| `diff_files` | Compare files or snapshots. | `workspace:read` | Yes — Phase 2 |
| `write_file` | Create or replace a file after approval. | `workspace:write`, `approval:resolve` | Yes — Phase 2 approval-gated proposal path |
| `edit_file` | Targeted file edit after approval. | `workspace:write`, `approval:resolve` | Yes — Phase 2 approval-gated proposal path |
| `apply_patch` | Apply a patch after approval and snapshot. | `workspace:write`, `approval:resolve` | Yes — Phase 2 approval-gated proposal path |
| `delete_file` | Delete a file. | `workspace:write`, `approval:resolve` | No — Phase 2 planned / deny by default |
| `copy_path` | Copy a file or directory. | `workspace:write`, `approval:resolve` | No — Phase 2 planned |
| `move_path` | Rename or move a file/directory. | `workspace:write`, `approval:resolve` | No — Phase 2 planned |
| `notebook_edit` | Modify Jupyter notebook cells by cell ID/index. | `workspace:write`, `approval:resolve` | `deferred_after_phase_3` — outside completed Phase 3 slices A-P |
| `symbol_search` | Search workspace code symbols. | `workspace:search`, later `lsp:read` or `graph:read` | Partial — Phase 3 specified/planning |
| `lsp_diagnostics` | Read language-server diagnostics. | `lsp:read`; server startup needs `lsp:server_start` | `deferred_after_phase_3` — outside completed Phase 3 slices A-P |
| `lsp_definition` | Jump to symbol definition. | `lsp:read` | `deferred_after_phase_3` — outside completed Phase 3 slices A-P |
| `lsp_references` | Find symbol references. | `lsp:read` | `deferred_after_phase_3` — outside completed Phase 3 slices A-P |
| `lsp_type_info` | Read type information for code at position. | `lsp:read` | `deferred_after_phase_3` — outside completed Phase 3 slices A-P |
| `lsp_call_hierarchy` | Trace caller/callee relationships. | `lsp:read` | `deferred_after_phase_3` — outside completed Phase 3 slices A-P |
| `semantic_search` | Search semantic/vector memory index. | `memory:read`; vector backend needs `semantic_memory:write` for index creation | Partial — Phase 3 specified; runtime writes disabled |
| `graph_query` | Query graph/codemap metadata. | `graph:read` | Partial — Phase 3 specified; indexing disabled |
| `graph_plan` | Produce dry-run graph/codemap indexing plan. | `graph:plan` | Yes — Phase 3 Slice C planning only |
| `graph_status` | Show graph/codemap disabled/runtime status. | `graph:read` | Yes — Phase 3 Slice C |
| `web_search` | Search public web. | `network:egress` | `deferred_after_phase_3` — outside completed Phase 3 slices A-P; disabled until egress policy |
| `web_fetch` | Fetch URL contents. | `network:egress` | `deferred_after_phase_3` — outside completed Phase 3 slices A-P; disabled until egress policy |
| `shell` | Propose or execute local shell command through policy. | `command:propose`; later `command:execute` | Partial — Phase 1 approval-gated proposal path; direct execution gated |
| `powershell` | Run native PowerShell command through policy. | `command:propose`, `command:execute` | No — Phase 2 planned/needs validation |
| `python_exec` | Run isolated Python snippet. | `command:execute` | No — Phase 2 planned; sandbox/timeout required |
| `git_status` | Inspect Git status. | `git:read` | Yes — Phase 2 |
| `git_diff` | Inspect Git diff. | `git:read` | Yes — Phase 2 |
| `git_log` | Inspect Git history. | `git:read` | Yes — Phase 2 |
| `git_mutation` | Branch/commit/merge/push Git operations. | `git:write`, `approval:resolve` | No — Phase 3/4 planned |
| `monitor` | Watch a background command/log/process and surface output. | `process:monitor`, `command:execute` | No — disabled until Phase 4 |
| `schedule_create` | Create one-shot or recurring local scheduled prompt/task. | `storage_lifecycle:plan` or future `schedule:write`, `approval:resolve` | `deferred_after_phase_3` — outside completed Phase 3 slices A-P |
| `schedule_list` | List scheduled tasks. | `none` or future `schedule:read` | `deferred_after_phase_3` — outside completed Phase 3 slices A-P |
| `schedule_delete` | Cancel scheduled task. | future `schedule:write`, `approval:resolve` | `deferred_after_phase_3` — outside completed Phase 3 slices A-P |
| `schedule_wakeup` | Internal bounded wakeup scheduling loop. | future `schedule:write` | No — Phase 3/4 planned |
| `routine_remote_trigger` | Hosted/cloud routine create/update/run/list. | `notify:hosted`, `remote:execute` | No — disabled until Phase 5 |
| `mcp_list_resources` | List resources exposed by configured MCP servers. | `mcp:read` | No — Phase 3/4 planned; server startup disabled |
| `mcp_read_resource` | Read an MCP resource URI. | `mcp:read` | No — Phase 3/4 planned; content untrusted |
| `mcp_wait_for_server` | Wait for configured MCP server readiness. | `mcp:server_start` | No — disabled until Phase 3/4 trust gates |
| `tool_search` | Discover/load deferred tools or plugin/MCP tools. | `plugin:validate`, `mcp:read`, `marketplace:read` depending source | No — Phase 3/5 planned |
| `spawn_subagent` | Start a bounded subagent. | `agent:execute` | No — Phase 4 safe planning only; spawning disabled |
| `send_agent_message` | Send/resume message to a teammate/subagent. | `agent:execute` | No — disabled until Phase 4 |
| `workflow_run` | Run a dynamic workflow coordinating tasks/agents. | `agent:execute`, `remote:execute` when remote | No — Phase 4/5 planned |
| `team_onboarding_export` | Generate/share onboarding guide for collaborators. | `audit:export`; hosted share needs `notify:hosted` | No — Phase 5 planned |
| `memory_candidate` | Propose governed memory candidate. | `memory:read` | Yes — Phase 1/2 candidate flow |
| `memory_status` | Show governed memory/semantic-memory disabled status. | `memory:read` | Yes — Phase 2/3 |
| `memory_review` | Inspect governed memory review queue. | `memory:read` | Yes — Phase 3 Slice D review-only |
| `memory_search` | Search governed memory. | `memory:read` | Partial — Phase 2/3 candidate/status search only |
| `memory_write` | Persist governed non-semantic memory. | `memory:write`, `approval:resolve` | No — planned/governed; semantic writes disabled |
| `semantic_memory_write` | Persist semantic/vector memory and embeddings. | `semantic_memory:write`, `approval:resolve` | No — disabled until later Phase 3 gates |
| `memory_update` | Update governed memory. | `memory:write`, `approval:resolve` | No — Phase 2/3 planned |
| `memory_forget` | Delete/forget memory. | `memory:write`, `approval:resolve` | No — Phase 2/3 planned |
| `memory_export` | Export memory records. | `audit:export`, `memory:read`, `approval:resolve` | No — Phase 2/5 planned high-risk |
| `graph_approval_preview` | Preview future graph indexing approval. | `approval:read`, `graph:plan` | Yes — Phase 3 Slice E preview-only |
| `memory_approval_preview` | Preview future semantic memory write approval. | `approval:read`, `memory:read` | Yes — Phase 3 Slice E preview-only |
| `approval_previews` | List approval previews. | `approval:read` | Yes — Phase 3 Slice E preview-only |
| `approval_preview_lookup` | Render one stored/known approval preview by ID. | `approval:read` | Yes — Phase 3 Slice E preview-only |
| `approval_audit` | Preview/render approval audit records. | `approval:read` | Yes — Phase 3 Slice F preview-only |
| `rollback_plan` | Preview rollback plans for graph/memory actions. | `rollback:plan` | Yes — Phase 3 Slice F preview-only |
| `storage_lifecycle` | List/read metadata-only storage lifecycle records. | `storage_lifecycle:read` | Yes — Phase 3 Slice G metadata-only |
| `storage_lifecycle_summary` | Render aggregate lifecycle counts and disabled write flags. | `storage_lifecycle:read` | Yes — Phase 3 Slice G metadata-only |
| `storage_lifecycle_graph` | Render graph/codemap lifecycle metadata only. | `storage_lifecycle:read`, `graph:read` | Yes — Phase 3 Slice G metadata-only |
| `storage_lifecycle_memory` | Render semantic-memory lifecycle metadata only. | `storage_lifecycle:read`, `memory:read` | Yes — Phase 3 Slice G metadata-only |
| `storage_lifecycle_create` | Create lifecycle metadata records. | `storage_lifecycle:write_metadata` | Yes — Phase 3 Slice G internal service; metadata-only |
| `storage_lifecycle_expire` | Mark lifecycle metadata expired. | `storage_lifecycle:write_metadata` | Yes — Phase 3 Slice G internal service; no execution |
| `storage_lifecycle_supersede` | Mark lifecycle metadata superseded. | `storage_lifecycle:write_metadata` | Yes — Phase 3 Slice G internal service; no execution |
| `storage_lifecycle_retention_policy` | Define metadata-only retention policy records for lifecycle records. | `storage_lifecycle:plan` | Yes — Phase 3 Slice H metadata-only |
| `storage_lifecycle_cleanup_preview` | Preview cleanup candidates without deletion/execution. | `storage_lifecycle:plan` | Yes — Phase 3 Slice H preview-only |
| `storage_lifecycle_approval_handoff` | Plan future approval handoff for lifecycle records without approval relay. | `storage_lifecycle:plan`, `approval:read` | Yes — Phase 3 Slice H planning-only |
| `approvals_list` | List pending action-bound approvals. | `approval:read` | Yes — Phase 2 |
| `approve_action` | Approve exact pending action ID. | `approval:resolve` | Yes — Phase 2 for supported approval records |
| `deny_action` | Deny exact pending action ID. | `approval:resolve` | Yes — Phase 2 |
| `checkpoint_list` | List checkpoint timeline entries. | `none` | Yes — Phase 2 |
| `checkpoint_restore` | Restore checkpoint. | `workspace:write`, `approval:resolve` | No — planned/approval required |
| `checkpoint_fork` | Fork from checkpoint. | `workspace:write`, `approval:resolve` | No — planned/approval required |
| `event_list` | List indexed events. | `none` | Yes — Phase 2 |
| `event_read` | Read event payload/details. | `none` | Partial — Phase 2 event viewer behavior |
| `workspace_inspect` | Inspect shared workspace summary. | `none` | Yes — Phase 3 Slice A/B read-only |
| `workspace_view` | Render deterministic workspace views. | `none` | Yes — Phase 3 Slice B read-only |
| `client_capabilities` | Show equal client capability summaries. | `none` | Yes — Phase 3 Slice A/B read-only |
| `capability_list` | List phase-gated capabilities. | `none` | Yes — Phase 3/4 safe foundation |
| `execution_profiles` | List execution profiles and denied plans. | `remote:plan` | Yes — Phase 4 safe foundation; execution disabled |
| `remote_execution_plan` | Produce denied remote/container execution plan. | `remote:plan` | Yes — Phase 4 safe foundation; execution disabled |
| `channel_status` | List disabled channel connector profiles/status. | `channel:read` | Yes — Phase 1 registry / Phase 4 status foundation |
| `channel_activate` | Activate external transport. | `channel:activate`, `approval:resolve` | No — disabled until Phase 4 |
| `model_profiles` | List model profiles. | `model:read` | Yes — Phase 1 |
| `model_launch` | Launch/switch configured model profile. | `model:launch`, possibly `network:egress` for hosted | Partial — mock/local profile path; hosted disabled |
| `doctor` | Run local diagnostics/status inspection. | `config:read`, `model:read`, `channel:read` | Yes — Phase 2/3 inspection |
| `config_read` | Inspect Raiker config/profile metadata. | `config:read` | Partial — profile/registry status surfaces |
| `config_write` | Modify scoped Raiker config. | `config:write`, `approval:resolve` | No — planned |
| `notify_user_local` | Send local user notification. | `notify:local` | No — Phase 4 planned |
| `notify_user_hosted` | Send hosted/mobile push/share notification. | `notify:hosted` | No — disabled until Phase 5 |
| `audit_export` | Export audit/session/event/security records. | `audit:export`, `approval:resolve` | No — Phase 5 planned |
| `marketplace_search` | Discover plugin packages from registry. | `marketplace:read`, `network:egress` | No — Phase 5 planned |
| `marketplace_install` | Install/update marketplace plugin. | `marketplace:install`, `plugin:validate`, `approval:resolve` | No — disabled until Phase 5 |

---

## Raiker plugin component inventory

| Tool Name | Descriptions | Permissions | Implemented |
|---|---|---|---|
| `plugin_manifest` | Declares plugin metadata, compatibility, entrypoints, permissions, trust, supply-chain details. | `plugin:validate` | Yes — Phase 3 validation/planning |
| `plugin_validate` | Validate plugin manifest/package without executing code. | `plugin:validate` | Partial — manifest validation implemented; full package validation planned |
| `plugin_registration_plan` | Produce plugin registration plan and permission diff. | `plugin:register`, `approval:read` | Yes — Phase 3 planning only |
| `plugin_details` | Show component inventory, permissions, risk, and status. | `plugin:validate`, `plugin:register` | Partial — Phase 3 inspection/planning |
| `plugin_commands` | Add slash commands or prompt shortcuts. | `plugin:register`; execution depends on target tool permissions | `deferred_after_phase_3` — outside completed Phase 3 slices A-P; inert metadata currently |
| `plugin_skills` | Package reusable workflows/procedures. | `plugin:register`; tool-specific permissions at runtime | No — Phase 2/3 planned |
| `plugin_agents` | Package subagent profiles. | `plugin:register`, later `agent:execute` | No — disabled until Phase 4 |
| `plugin_hooks` | Add lifecycle/event handlers. | `plugin:register`; no bypass of policy | `deferred_after_phase_3` — outside completed Phase 3 slices A-P |
| `plugin_mcp_servers` | Bundle MCP server definitions. | `plugin:register`, `mcp:server_start`, `network:egress` | No — disabled until Phase 3/4 trust gates |
| `plugin_lsp_servers` | Bundle LSP/code-intelligence server definitions. | `plugin:register`, `lsp:server_start`, `lsp:read` | `deferred_after_phase_3` — outside completed Phase 3 slices A-P |
| `plugin_monitors` | Declare background monitors/watchers. | `plugin:register`, `process:monitor`, `command:execute` | No — disabled until Phase 4 |
| `plugin_tool_adapters` | Register tool adapters through Tool Broker. | `plugin:register`; target tool permissions required | `deferred_after_phase_3` — outside completed Phase 3 slices A-P; must never execute directly |
| `plugin_channels` | Add external channel connectors. | `plugin:register`, `channel:activate` | No — disabled until Phase 4 |
| `plugin_tui_panels` | Add terminal UI panels. | `plugin:register`; `none` if display-only | `deferred_after_phase_3` — outside completed Phase 3 slices A-P |
| `plugin_web_panels` | Add web/dashboard panels. | `plugin:register`; action-specific permissions | `deferred_after_phase_3` — outside completed Phase 3 slices A-P |
| `plugin_mobile_panels` | Add mobile UI panels/cards. | `plugin:register`; action-specific permissions | No — Phase 4 planned |
| `plugin_output_styles` | Provide output style/rendering rules. | `plugin:register`; no runtime authority | `deferred_after_phase_3` — outside completed Phase 3 slices A-P |
| `plugin_themes` | Provide color/theme definitions. | `plugin:register`; no runtime authority | `deferred_after_phase_3` — outside completed Phase 3 slices A-P |
| `plugin_user_config` | Declare/persist user-configurable plugin values. | `plugin:register`, `config:read`, `config:write` | No — Phase 3/5 planned |
| `plugin_dependencies` | Declare dependent plugins/components. | `plugin:register`, `plugin:validate` | No — Phase 3/5 planned |
| `plugin_permission_diff` | Show permission changes from install/update/dependency expansion. | `plugin:validate`, `approval:read` | Partial — Phase 3 planning |
| `plugin_trust_policy` | Track trust level: unknown/local/project/user/managed/bundled. | `plugin:validate`, `config:read` | Partial — Phase 3 planning |
| `plugin_supply_chain_metadata` | Track source URL, commit, checksum, signature. | `plugin:validate`, `marketplace:read` | Partial — schema documented; full verification Phase 5 |
| `plugin_marketplace` | Discover/install/update plugins from registries. | `marketplace:read`, `marketplace:install`, `network:egress` | No — disabled until Phase 5 |
| `plugin_reload` | Reload changed plugin metadata/components. | `plugin:register` | No — Phase 3/4 planned; must not auto-enable code |
| `plugin_enable` | Enable plugin components after policy/trust approval. | `plugin:register`, `approval:resolve`; later `plugin:execute` if runtime code | No — runtime execution disabled |
| `plugin_disable` | Disable plugin components. | `plugin:register` | `deferred_after_phase_3` — outside completed Phase 3 slices A-P |
| `plugin_remove` | Remove plugin metadata/package. | `plugin:register`, `workspace:write`, `approval:resolve` | No — Phase 3/5 planned |
| `plugin_execute` | Execute plugin code/entrypoint. | `plugin:execute` plus target permissions | No — disabled until explicit Phase 3+ execution gates |

---

## Commands mapped to implemented/planned tools

| Tool Name | Descriptions | Permissions | Implemented |
|---|---|---|---|
| `/help` | Show command/action help. | `none` | Yes |
| `/status` | Show workspace/session/task/approval/lifecycle count summary. | `none` | Yes |
| `/tasks` | List task records. | `none` | Yes |
| `/events` | List indexed events. | `none` | Yes |
| `/checkpoints` | List checkpoint timeline. | `none` | Yes |
| `/approvals` | List pending approvals. | `approval:read` | Yes |
| `/approve <id>` | Approve exact pending action ID. | `approval:resolve` | Yes |
| `/deny <id>` | Deny exact pending action ID. | `approval:resolve` | Yes |
| `/memory` | Show governed memory status/candidates. | `memory:read` | Yes |
| `/semantic-memory` | Show semantic-memory disabled status. | `memory:read` | Yes |
| `/memory-review` | Show memory review queue. | `memory:read` | Yes |
| `/memory-review --summary` | Show memory review counts. | `memory:read` | Yes |
| `/capabilities` | List disabled/planned/enabled capability gates. | `none` | Yes |
| `/execution-profiles` | List execution profiles and disabled execution state. | `remote:plan` | Yes — execution disabled |
| `/workspace` | Show workspace inspection summary. | `none` | Yes |
| `/workspace-view` | Render deterministic workspace view. | `none` | Yes |
| `/clients` | Show equal-client capability summary. | `none` | Yes |
| `/plugins` | Show plugin registry/planning status. | `plugin:validate`, `plugin:register` | Yes — planning/inspection only |
| `/plugin-plan <manifest_path>` | Validate/plan plugin registration. | `plugin:validate`, `workspace:read` | Yes — no plugin execution |
| `/graph-status` | Show graph/codemap disabled status. | `graph:read` | Yes |
| `/graph-plan` | Render dry-run graph/codemap plan. | `graph:plan` | Yes — no graph writes |
| `/approval-previews` | List approval previews. | `approval:read` | Yes — preview-only |
| `/graph-approval-preview` | Preview graph indexing approval. | `approval:read`, `graph:plan` | Yes — preview-only |
| `/memory-approval-preview` | Preview semantic-memory write approval. | `approval:read`, `memory:read` | Yes — preview-only |
| `/memory-approval-preview --summary` | Preview semantic-memory write summary. | `approval:read`, `memory:read` | Yes — preview-only |
| `/approval-preview <id>` | Render one approval preview. | `approval:read` | Yes — preview-only |
| `/approval-audit` | Render approval audit records. | `approval:read` | Yes — preview-only |
| `/approval-audit --summary` | Render approval audit summary. | `approval:read` | Yes — preview-only |
| `/rollback-plan` | Render rollback plans. | `rollback:plan` | Yes — preview-only |
| `/graph-rollback-plan` | Render graph rollback plan. | `rollback:plan`, `graph:read` | Yes — preview-only |
| `/memory-rollback-plan` | Render memory rollback plan. | `rollback:plan`, `memory:read` | Yes — preview-only |
| `/storage-lifecycle` | Render storage lifecycle records. | `storage_lifecycle:read` | Yes — metadata-only |
| `/storage-lifecycle --summary` | Render lifecycle aggregate summary. | `storage_lifecycle:read` | Yes — metadata-only |
| `/storage-lifecycle --graph` | Render graph lifecycle metadata. | `storage_lifecycle:read`, `graph:read` | Yes — metadata-only |
| `/storage-lifecycle --memory` | Render memory lifecycle metadata. | `storage_lifecycle:read`, `memory:read` | Yes — metadata-only |
| `/doctor` | Show diagnostics and disabled gates. | `config:read`, `model:read`, `channel:read` | Yes |
| `/channels` | List channel connector profiles. | `channel:read` | Yes — activation disabled |
| `/models` | List model profiles. | `model:read` | Yes |
| `/launch --provider mock --model mock-deterministic` | Test-only deterministic profile launch; normal production CLI policy blocks it with `deterministic_test_provider_requires_test_mode`. | `model:launch` | Test-only/deferred; not a production CLI runtime |
| `/quit` | Exit terminal session safely. | `none` | Yes |

---

## Required additions to future phase work

The following items must be picked up by later implementation plans:

1. Add `notebook_edit` as a distinct Phase 3 tool, separate from plain text `edit_file`.
2. Add LSP tools as first-class Phase 3 read-only code-intelligence tools: diagnostics, definition, references, type info, symbols, implementations, and call hierarchy.
3. Add `monitor` as a Phase 4 background watch tool with shell-level risk and cancellation/event-rate controls.
4. Split scheduled automation into explicit Raiker tools: create/list/delete/wakeup, with hosted routines deferred to Phase 5.
5. Add MCP resource tools: list/read/wait/discover, with trust and egress controls.
6. Add explicit plugin components for LSP servers, monitors, output styles, themes, user config, dependencies, details, reload, marketplace, and validation.
7. Add dynamic workflow/team tools to Phase 4/5 with parent/child event linkage, budgets, cancellation, and audit.
8. Add local vs hosted notification semantics: local notifications may be Phase 4; hosted push/share links require Phase 5 privacy/auth controls.
9. Add Slice H lifecycle retention, cleanup-preview, and approval-handoff tools as metadata-only Phase 3 follow-up work.

---

## Non-activation rule

Until the relevant phase gates are fully implemented and verified:

- plugin code execution remains disabled;
- graph/codemap runtime indexing remains disabled;
- graph node/edge writes remain disabled;
- semantic/vector memory writes remain disabled;
- embedding creation/storage remains disabled;
- rollback execution remains disabled;
- external channels remain disabled;
- MCP/LSP/plugin server startup remains disabled unless explicitly trusted and approved;
- monitors/watchers remain disabled;
- subagent and multi-agent runtime execution remains disabled;
- remote/container/cloud execution remains disabled;
- hosted routines, marketplace installs, hosted push notifications, and share links remain disabled.

## Phase 3 Slice H Lifecycle Retention, Cleanup, and Handoff Commands

| Tool Name | Descriptions | Permissions | Implemented |
|---|---|---|---|
| `/storage-lifecycle-retention` | Render metadata-only lifecycle retention policies; never executes cleanup, graph indexing, memory writes, embeddings, vectors, rollback, plugins, channels, subagents, or remote/container work. | `storage_lifecycle:read` | Yes — metadata-only |
| `/storage-lifecycle-retention --summary` | Render aggregate retention policy counts and disabled execution flags. | `storage_lifecycle:read` | Yes — metadata-only |
| `/storage-lifecycle-cleanup-preview` | Render cleanup preview metadata for expired/superseded lifecycle records with `can_cleanup_now=false`. | `storage_lifecycle:read` | Yes — preview-only |
| `/storage-lifecycle-cleanup-preview --summary` | Render aggregate cleanup preview counts and disabled cleanup/runtime flags. | `storage_lifecycle:read` | Yes — preview-only |
| `/storage-lifecycle-handoff` | Render approval-handoff planning metadata without approval relay or execution. | `storage_lifecycle:read`, `approval:read` | Yes — planning-only |
| `/storage-lifecycle-handoff --summary` | Render aggregate approval-handoff counts and disabled execution flags. | `storage_lifecycle:read`, `approval:read` | Yes — planning-only |

## Phase 3 Slice I lifecycle evidence and simulation tools

| Tool Name | Descriptions | Permissions | Implemented |
|---|---|---|---|
| `storage_lifecycle_evidence_bundle` | Create/read deterministic metadata-only lifecycle evidence bundles for export and inspection. | `storage_lifecycle:read`, `audit:export` | Yes — Phase 3 Slice I |
| `storage_lifecycle_policy_simulation` | Create/read deterministic metadata-only policy simulations; no cleanup or approval relay. | `storage_lifecycle:read`, `storage_lifecycle:plan` | Yes — Phase 3 Slice I |
| `/storage-lifecycle-evidence` | List read-only lifecycle evidence bundles. | `storage_lifecycle:read`, `audit:export` | Yes — Phase 3 Slice I |
| `/storage-lifecycle-evidence --summary` | Render evidence bundle summary and disabled runtime flags. | `storage_lifecycle:read`, `audit:export` | Yes — Phase 3 Slice I |
| `/storage-lifecycle-evidence --json` | Export deterministic redacted evidence JSON. | `storage_lifecycle:read`, `audit:export` | Yes — Phase 3 Slice I |
| `/storage-lifecycle-policy-simulation` | List metadata-only policy simulations. | `storage_lifecycle:read`, `storage_lifecycle:plan` | Yes — Phase 3 Slice I |
| `/storage-lifecycle-policy-simulation --summary` | Render simulation summary and disabled runtime flags. | `storage_lifecycle:read`, `storage_lifecycle:plan` | Yes — Phase 3 Slice I |
| `/storage-lifecycle-policy-simulation --json` | Export deterministic redacted policy simulation JSON. | `storage_lifecycle:read`, `storage_lifecycle:plan`, `audit:export` | Yes — Phase 3 Slice I |

## Phase 3 Slice J Graph/Codemap Readiness Command

| Command | Mode | Runtime effects | Notes |
|---|---|---|---|
| `/graph-readiness` | Read-only metadata | None | Shows metadata-only readiness blockers. Does not enable graph indexing, codemap indexing, graph writes, workers, schedulers, file watchers, daemons, indexing jobs, or runtime execution/jobs. |
| `/graph-readiness --summary` | Read-only metadata | None | Shows deterministic readiness counts and disabled runtime flags only. |
| `/graph-readiness --json` | Read-only metadata export | None | Emits deterministic JSON-safe readiness summary only. |


## Phase 3 Slice K — Semantic Memory Write Readiness — Metadata Only
- Adds deterministic metadata-only semantic memory readiness contracts, registry, optional SQLite metadata table, CLI, and workspace surfaces.
- Semantic memory writes, vector writes, embeddings, jobs, workers, schedulers, watchers, daemons, and runtime execution remain disabled.
- Reserved Slice K metadata-only events: `phase3.semantic_memory_readiness.metadata_created`, `phase3.semantic_memory_readiness.summary_viewed`, `phase3.semantic_memory_readiness.exported`. No runtime memory write events are enabled.
- Slice K did not by itself mark Phase 3 complete. Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`. Phase 4 remains blocked.

## Phase 3 Slice L — approval preview persistence readiness

| Command | Mode | Execution authority | Notes |
| --- | --- | --- | --- |
| `/approval-readiness` | Read-only metadata | None | Shows metadata-only approval preview persistence readiness blockers and disabled runtime flags. |
| `/approval-readiness --summary` | Read-only metadata | None | Shows deterministic readiness counts and disabled approval execution, relay, queue, worker, scheduler, watcher, daemon, and runtime flags. |
| `/approval-readiness --json` | Read-only metadata export | None | Emits deterministic JSON-safe readiness summary only. |

Slice L does not enable approval preview persistence, approval execution, approval relay runtime, durable approval queues, workers, schedulers, watchers, daemons, or runtime execution. Slice L did not by itself mark Phase 3 complete. Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`. Phase 4 remains blocked.


## Phase 3 Slice M cleanup readiness surface

`/cleanup-readiness [--summary|--json]` is a read-only, metadata-only CLI surface. It does not execute cleanup, deletion, purge, tombstone, rollback, jobs, workers, schedulers, watchers, daemons, plugins, or runtime execution. Slice M did not by itself mark Phase 3 complete. Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`. Phase 4 remains blocked.

## Phase 3 Slice N: Plugin/Server Startup Readiness — Metadata Only

Slice N reserves metadata-only readiness surfaces and events for future plugin/server startup. Reserved metadata-only events: `phase3.plugin_server_readiness.metadata_created`, `phase3.plugin_server_readiness.summary_viewed`, `phase3.plugin_server_readiness.exported`. No plugin execution, plugin installation, plugin activation, MCP/LSP/plugin server startup, monitor daemon startup, marketplace install, hosted routine, external channel, worker, scheduler, watcher, daemon, relay, or runtime execution events are enabled. Slice N did not by itself mark Phase 3 complete. Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`. Phase 4 remains blocked.

## Phase 3 Slice O channel readiness surface

- `/channel-readiness [--summary|--json]`: read-only metadata surface for future external channels and notifications. It exposes disabled runtime flags and blockers only; it does not activate external channels, send notifications, create push notifications or share links, dispatch webhooks, start relays, create hosted channels/routines, create workers/schedulers/watchers/daemons, or enable runtime execution.

## Phase 3 Slice P — Remote/Container/Cloud Execution Readiness — Metadata Only

Slice P adds deterministic metadata-only readiness contracts, registry, optional SQLite metadata table, `/remote-readiness [--summary|--json]`, workspace summaries, and reserved metadata-only events for future remote/container/cloud execution. No remote execution, container execution, cloud execution, hosted routines, runtime jobs, job dispatch, worker queues, workers, schedulers, file watchers, daemons, client transport, external dispatch, credential materialization, secret injection, provider integrations, sandbox runtime, process execution, shell execution, network execution, or runtime execution are enabled. Slice P did not by itself mark Phase 3 complete. Phase 3 is now complete per `docs/PHASE_3_COMPLETION_AUDIT.md`. Phase 4 remains blocked.


## Implemented slash command catalog (Phase 3 truthfulness)

| Command | Purpose | Permissions | Implementation status | Runtime effect | Safety boundary |
|---|---|---|---|---|---|
| `/help` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/providers` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/models` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/model current` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/model use <profile_id>` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | session metadata only | No private chain-of-thought exposed. |
| `/model use --provider <provider> --model <model>` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | session metadata only | No private chain-of-thought exposed. |
| `/model health` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/model capabilities` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/reasoning` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | session metadata only | No private chain-of-thought exposed. |
| `/reasoning status` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | session metadata only | No private chain-of-thought exposed. |
| `/reasoning set <mode-or-effort>` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | session metadata only | No private chain-of-thought exposed. |
| `/reasoning off` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | session metadata only | No private chain-of-thought exposed. |
| `/status` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/tasks` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/events` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/checkpoints` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/approvals` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/approve <id>` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | approval metadata status update only | Does not execute approved action. |
| `/deny <id>` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | approval metadata status update only | Does not execute approved action. |
| `/memory` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/semantic-memory` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/capabilities` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/execution-profiles` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/workspace` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/workspace-view` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/clients` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/plugins` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/plugin-plan <manifest_path>` | Inspection/control command exposed by terminal CLI. | local_terminal | `planning_only_implemented_verified` | planning/simulation only | No direct tool execution; unsafe runtime disabled. |
| `/graph-status` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/graph-plan` | Inspection/control command exposed by terminal CLI. | local_terminal | `planning_only_implemented_verified` | planning/simulation only | No direct tool execution; unsafe runtime disabled. |
| `/graph-readiness [--summary|--json]` | Inspection/control command exposed by terminal CLI. | local_terminal | `metadata_only_implemented_verified` | metadata summary/export only | No direct tool execution; unsafe runtime disabled. |
| `/memory-readiness [--summary|--json]` | Inspection/control command exposed by terminal CLI. | local_terminal | `metadata_only_implemented_verified` | metadata summary/export only | No direct tool execution; unsafe runtime disabled. |
| `/approval-readiness [--summary|--json]` | Inspection/control command exposed by terminal CLI. | local_terminal | `metadata_only_implemented_verified` | metadata summary/export only | No direct tool execution; unsafe runtime disabled. |
| `/cleanup-readiness [--summary|--json]` | Inspection/control command exposed by terminal CLI. | local_terminal | `metadata_only_implemented_verified` | metadata summary/export only | No direct tool execution; unsafe runtime disabled. |
| `/remote-readiness [--summary|--json]` | Inspection/control command exposed by terminal CLI. | local_terminal | `metadata_only_implemented_verified` | metadata summary/export only | No direct tool execution; unsafe runtime disabled. |
| `/plugin-readiness [--summary|--json]` | Inspection/control command exposed by terminal CLI. | local_terminal | `metadata_only_implemented_verified` | metadata summary/export only | No direct tool execution; unsafe runtime disabled. |
| `/channel-readiness [--summary|--json]` | Inspection/control command exposed by terminal CLI. | local_terminal | `metadata_only_implemented_verified` | metadata summary/export only | No direct tool execution; unsafe runtime disabled. |
| `/memory-review [--summary]` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/approval-previews` | Inspection/control command exposed by terminal CLI. | local_terminal | `preview_only_implemented_verified` | approval card/preview output only | No direct tool execution; unsafe runtime disabled. |
| `/graph-approval-preview` | Inspection/control command exposed by terminal CLI. | local_terminal | `preview_only_implemented_verified` | approval card/preview output only | No direct tool execution; unsafe runtime disabled. |
| `/memory-approval-preview [--summary]` | Inspection/control command exposed by terminal CLI. | local_terminal | `preview_only_implemented_verified` | approval card/preview output only | No direct tool execution; unsafe runtime disabled. |
| `/approval-preview <preview_id>` | Inspection/control command exposed by terminal CLI. | local_terminal | `preview_only_implemented_verified` | approval card/preview output only | No direct tool execution; unsafe runtime disabled. |
| `/approval-audit [--summary]` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/rollback-plan` | Inspection/control command exposed by terminal CLI. | local_terminal | `planning_only_implemented_verified` | planning/simulation only | No direct tool execution; unsafe runtime disabled. |
| `/graph-rollback-plan` | Inspection/control command exposed by terminal CLI. | local_terminal | `planning_only_implemented_verified` | planning/simulation only | No direct tool execution; unsafe runtime disabled. |
| `/memory-rollback-plan` | Inspection/control command exposed by terminal CLI. | local_terminal | `planning_only_implemented_verified` | planning/simulation only | No direct tool execution; unsafe runtime disabled. |
| `/storage-lifecycle [--summary|--graph|--memory]` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/storage-lifecycle-retention [--summary]` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/storage-lifecycle-cleanup-preview [--summary]` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/storage-lifecycle-handoff [--summary]` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/storage-lifecycle-evidence [--summary] [--json] [--status <status>] [--target <graph|memory|rollback|storage|plugin|channel|remote>] [--limit <number>]` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/storage-lifecycle-policy-simulation [--summary] [--json] [--status <status>] [--target <graph|memory|rollback|storage|plugin|channel|remote>] [--limit <number>]` | Inspection/control command exposed by terminal CLI. | local_terminal | `planning_only_implemented_verified` | planning/simulation only | No direct tool execution; unsafe runtime disabled. |
| `/doctor` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/channels` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
| `/launch --provider mock --model mock-deterministic` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | test-only policy-block smoke | Deterministic mock provider is test-only; normal CLI must not imply production launch support. |
| `/quit` | Inspection/control command exposed by terminal CLI. | local_terminal | `implemented_verified` | read-only output | No direct tool execution; unsafe runtime disabled. |
