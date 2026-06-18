# Raiker Tool and Plugin Catalog

This catalog is the Raiker-native inventory of tool and plugin capabilities that must be tracked across future implementation stages.

It was created after reviewing Raiker's current docs and comparing them against contemporary coding-agent reference surfaces, including the public Claude Code tools and plugins references. The purpose is not to clone another product. The purpose is to ensure Raiker has its own explicit, phase-scheduled tool and plugin catalogue so future builders do not miss major capability classes.

A row in this file is **not** runtime activation approval. Every tool and plugin component must still pass Raiker's contracts, policy, storage, event logging, approval, UI parity, security, and acceptance-test gates before it can execute.

---

## Phase status legend

| Phase | Meaning in this catalog |
|---|---|
| Phase 1 | Core local runtime and safe read-only workspace tools. |
| Phase 2 | Rich local workspace, mutation proposals, task/checkpoint/event UX, local provider discovery, and governed local command/file operations. |
| Phase 3 | Local rich workspace foundations, plugin validation/planning, graph and memory governance, code intelligence, notebook-aware editing, scheduled/local automation planning, and web/network policy gates. |
| Phase 4 | External channels, subagents, multi-agent teams, monitor/watch surfaces, isolated worktrees, remote/container execution planning. |
| Phase 5 | Managed/enterprise controls, hosted/cloud routines, billing/budget policy, marketplace governance, cloud/GPU jobs, organization-wide policy. |

---

## Raiker core tool catalogue

### Conversation, planning, and user-interaction tools

| Raiker tool | Purpose | Status / phase | Required notes |
|---|---|---|---|
| `ask_user` | Ask blocking clarification questions. | Phase 1 | Must not mutate runtime state except conversation events. |
| `side_question` | Ask non-blocking side questions while a task continues. | Phase 2 | Must be bound to task/session and preserve deterministic event order. |
| `enter_plan_mode` | Switch a turn into explicit planning mode. | Phase 2 | Planning output only; no tool execution. |
| `exit_plan_mode` | Present plan for approval and leave plan mode. | Phase 2 | Requires approval if plan enables risky actions. |
| `create_task` | Create task metadata for tracked work. | Phase 2 | No hidden background execution. |
| `update_task` | Update task status, details, dependencies, or progress. | Phase 2 | Must emit task events. |
| `list_tasks` | List task records. | Phase 2 | Read-only. |
| `get_task` | Read full details for one task. | Phase 2 | Read-only. |
| `stop_task` | Cancel/stop a tracked task or background process. | Phase 2 to Phase 4 | Local metadata cancellation in Phase 2; process cancellation requires policy. |
| `notify_user` | Send local desktop/mobile/channel notification. | Phase 4 to Phase 5 | Local notification can be Phase 4; hosted push needs Phase 5 policy and privacy review. |

### File and workspace tools

| Raiker tool | Purpose | Status / phase | Required notes |
|---|---|---|---|
| `read_file` | Read workspace text files. | Phase 1 implemented/verified | Workspace/path policy required. |
| `list_directory` | List workspace directories. | Phase 1 implemented/verified | Stable ordering and path safety required. |
| `glob` | Find files by pattern. | Phase 1 implemented/verified | Must document ignore rules, caps, and truncation. |
| `grep` | Search file contents. | Phase 1 implemented/verified | Must document regex mode, ignored files, caps, and truncation. |
| `stat_path` | Read path metadata. | Phase 2 implemented/verified | Read-only. |
| `diff_files` | Compare files or snapshots. | Phase 2 implemented/verified | Read-only; bounded output. |
| `write_file` | Create or replace a file. | Phase 2 implemented as approval-gated proposal path | Must snapshot and require approval before mutation. |
| `edit_file` | Targeted file edit. | Phase 2 implemented as approval-gated proposal path | Must require read-before-edit or current-content validation. |
| `apply_patch` | Apply unified patch. | Phase 2 implemented as approval-gated proposal path | Must snapshot and provide rollback planning. |
| `delete_file` | Delete a file. | Phase 2 scheduled / deny by default | High-risk; scoped approval only. |
| `copy_path` | Copy a file or directory. | Phase 2 scheduled | Approval required for writes. |
| `move_path` | Rename or move a file/directory. | Phase 2 scheduled | Approval required; rollback note required. |
| `notebook_edit` | Modify Jupyter notebook cells by cell ID or index. | Phase 3 missing explicit mapping before this catalog | Must be separate from plain text edit; approval and notebook structure validation required. |

### Code intelligence and search tools

| Raiker tool | Purpose | Status / phase | Required notes |
|---|---|---|---|
| `symbol_search` | Search workspace symbols. | Phase 3 partially covered | Must use language-server/code-index boundary. |
| `lsp_diagnostics` | Read language-server diagnostics. | Phase 3 missing explicit mapping before this catalog | Read-only by default; activation depends on trusted workspace/plugin. |
| `lsp_definition` | Jump to definition. | Phase 3 missing explicit mapping before this catalog | Read-only. |
| `lsp_references` | Find references. | Phase 3 missing explicit mapping before this catalog | Read-only. |
| `lsp_type_info` | Read type info at symbol/position. | Phase 3 missing explicit mapping before this catalog | Read-only. |
| `lsp_call_hierarchy` | Trace call hierarchy. | Phase 3 missing explicit mapping before this catalog | Read-only; bounded result size. |
| `semantic_search` | Search semantic/vector index. | Phase 3 specified but runtime writes disabled | Must not create embeddings unless semantic write gate is enabled. |
| `graph_query` | Query graph/codemap. | Phase 3 specified but indexing disabled | Dry-run/planning only until graph runtime gate is enabled. |
| `web_search` | Search public web. | Phase 3 scheduled, disabled until egress policy | Network egress, privacy, and source-citation policy required. |
| `web_fetch` | Fetch URL contents. | Phase 3 scheduled, disabled until egress policy | Domain allowlist, content-size, and prompt-injection controls required. |

### Local execution and shell tools

| Raiker tool | Purpose | Status / phase | Required notes |
|---|---|---|---|
| `shell` | Run local shell command. | Phase 1 approval-gated path; Phase 2 richer policy | Must never run without policy decision and approval where required. |
| `powershell` | Run native PowerShell command. | Phase 2 listed; needs explicit implementation/validation | Windows-first shell path; must respect enterprise execution policy. |
| `python_exec` | Run isolated Python snippet. | Phase 2 scheduled | Requires sandboxing, timeout, output limit, no secret/env dump by default. |
| `git_status` | Inspect Git status. | Phase 2 implemented/verified wrapper class | Read-only. |
| `git_diff` | Inspect Git diff. | Phase 2 implemented/verified wrapper class | Read-only; bounded output. |
| `git_log` | Inspect Git history. | Phase 2 implemented/verified wrapper class | Read-only. |
| `git_mutation` | Branch/commit/merge/push operations. | Phase 3 to Phase 4 scheduled | Must be approval-gated and never bypass PR workflow. |
| `monitor` | Run/watch background command or log stream and surface new lines/events. | Phase 4 missing explicit mapping before this catalog | Same risk class as shell plus background lifecycle, cancellation, and event rate limits. |

### Automation and scheduling tools

| Raiker tool | Purpose | Status / phase | Required notes |
|---|---|---|---|
| `schedule_create` | Create one-shot or recurring local scheduled prompt/task. | Phase 3 partially covered as scheduled automations | Must be local-first by default and session/workspace scoped unless Phase 5 hosted mode is enabled. |
| `schedule_list` | List scheduled tasks. | Phase 3 missing explicit tool mapping before this catalog | Read-only. |
| `schedule_delete` | Cancel scheduled task. | Phase 3 missing explicit tool mapping before this catalog | Requires owner/session/workspace validation. |
| `schedule_wakeup` | Internal self-paced loop wakeup scheduling. | Phase 3 to Phase 4 missing explicit mapping before this catalog | Must have max cadence, cancellation, and no hidden infinite loop. |
| `routine_remote_trigger` | Hosted/cloud routine create/update/run/list. | Phase 5 | Hosted execution, billing, privacy, and auth required; not local default. |

### MCP and external resource tools

| Raiker tool | Purpose | Status / phase | Required notes |
|---|---|---|---|
| `mcp_list_resources` | List resources exposed by connected MCP servers. | Phase 3 plugin/MCP planning; runtime disabled | Must require server trust and resource visibility policy. |
| `mcp_read_resource` | Read a specific MCP resource URI. | Phase 3 plugin/MCP planning; runtime disabled | Treat connector content as untrusted input. |
| `mcp_wait_for_server` | Wait for configured MCP server readiness. | Phase 3 to Phase 4 missing explicit mapping before this catalog | Must be cancellable and bounded. |
| `tool_search` | Discover/load deferred tools or plugin/MCP tools. | Phase 3 to Phase 5 missing explicit mapping before this catalog | Discovery does not equal permission grant. |

### Subagent, team, and workflow tools

| Raiker tool | Purpose | Status / phase | Required notes |
|---|---|---|---|
| `spawn_subagent` | Start a bounded subagent. | Phase 4 safe planning only | Runtime spawning disabled until lifecycle and approval controls exist. |
| `send_agent_message` | Send/resume message to a teammate/subagent. | Phase 4 missing explicit mapping before this catalog | Requires parent/child event linkage and bounded roles. |
| `workflow_run` | Run a dynamic workflow that coordinates multiple agents/tasks. | Phase 4 to Phase 5 missing explicit mapping before this catalog | High-risk orchestration; requires budget, audit, cancellation, and verification. |
| `team_onboarding_export` | Generate/share onboarding guide for collaborators. | Phase 5 missing explicit mapping before this catalog | If share link or hosted upload is used, requires hosted privacy/auth policy. |

### Memory, graph, and approval-preview tools

| Raiker tool | Purpose | Status / phase | Required notes |
|---|---|---|---|
| `memory_candidate` | Propose a memory candidate. | Phase 1/2 implemented as governed candidate flow | Does not imply durable semantic write. |
| `memory_search` | Search governed memory. | Phase 2 scheduled/partially implemented by candidate listing | Scope and sensitivity filters required. |
| `memory_write` | Persist governed memory. | Phase 2 for non-semantic; Phase 3 semantic writes disabled | Semantic/vector writes remain disabled until full governance/backend gates pass. |
| `memory_update` | Update governed memory. | Phase 2 scheduled | Audit and approval required. |
| `memory_forget` | Delete/forget memory. | Phase 2 scheduled | Audit and retention policy required. |
| `memory_export` | Export memory. | Phase 2 scheduled high-risk | Approval required. |
| `graph_plan` | Dry-run graph/codemap indexing plan. | Phase 3 implemented/verified planning only | Must not write graph records. |
| `graph_approval_preview` | Preview future graph indexing approval. | Phase 3 Slice E implemented preview-only | Not executable approval. |
| `memory_approval_preview` | Preview future semantic memory write approval. | Phase 3 Slice E implemented preview-only | Must redact secret-like values. |
| `approval_audit` | Preview/render approval audit records. | Phase 3 Slice F in PR #24 | Preview-only until merged and validated. |
| `rollback_plan` | Preview rollback plans for graph/memory actions. | Phase 3 Slice F in PR #24 | Preview-only; rollback execution disabled. |

---

## Raiker plugin component catalogue

| Raiker plugin component | Purpose | Status / phase | Required notes |
|---|---|---|---|
| `plugin_manifest` | Declares metadata, compatibility, entrypoints, permissions, trust, supply-chain data. | Phase 3 validation/planning implemented | Runtime entrypoints are inert metadata until execution gates pass. |
| `plugin_commands` | Add slash commands or prompt shortcuts. | Phase 3 specified/planning | Commands must expand into Raiker action contracts, not arbitrary execution. |
| `plugin_skills` | Package reusable procedural workflows. | Phase 2 to Phase 3 specified | Skills propose tools through broker and must include verification criteria. |
| `plugin_agents` | Package subagent profiles. | Phase 4 scheduled | Spawning remains disabled until subagent lifecycle controls exist. |
| `plugin_hooks` | Add lifecycle/event handlers. | Phase 3 specified/planning | Hooks cannot override managed denies or bypass policy. |
| `plugin_mcp_servers` | Bundle MCP server definitions. | Phase 3 to Phase 4 missing explicit mapping before this catalog | Server activation requires trust, approval, egress policy, and resource controls. |
| `plugin_lsp_servers` | Bundle LSP/code-intelligence server definitions. | Phase 3 missing explicit mapping before this catalog | Starts only after workspace/plugin trust. |
| `plugin_monitors` | Start plugin-declared background monitors/watchers. | Phase 4 missing explicit mapping before this catalog | Disabled by default; high-risk shell/background lifecycle. |
| `plugin_tool_adapters` | Register tool adapters through Tool Broker. | Phase 3 specified | Never execute directly from plugin code. |
| `plugin_channels` | Add external channel connectors. | Phase 4 scheduled | Pairing, sender allowlist, prompt-injection controls required. |
| `plugin_tui_panels` | Add terminal panels. | Phase 3 specified | Display-only unless action permissions granted. |
| `plugin_web_panels` | Add web/dashboard panels. | Phase 3 missing explicit mapping before this catalog | Same shared workspace view/action contracts as other UI clients. |
| `plugin_mobile_panels` | Add mobile UI panels/cards. | Phase 4 missing explicit mapping before this catalog | Approval UX must remain action-bound and secure. |
| `plugin_output_styles` | Provide output style/personality rendering rules. | Phase 3 missing explicit mapping before this catalog | Must not alter policy, hide warnings, or suppress citations/events. |
| `plugin_themes` | Provide color/theme definitions. | Phase 3 missing explicit mapping before this catalog | Visual-only; no runtime authority. |
| `plugin_user_config` | Prompt/store user-configurable plugin values. | Phase 3 to Phase 5 missing explicit mapping before this catalog | Sensitive config must be classified, redacted, and scoped. |
| `plugin_dependencies` | Declare plugin dependencies. | Phase 3 to Phase 5 missing explicit mapping before this catalog | Dependency enablement must show permission diff. |
| `plugin_marketplace` | Discover/install/update plugins from registries. | Phase 5 missing explicit mapping before this catalog | Supply-chain signing, checksum, review, and managed policy required. |
| `plugin_reload` | Reload changed plugin metadata/components. | Phase 3 to Phase 4 missing explicit mapping before this catalog | Reload must not auto-enable runtime code. |
| `plugin_details` | Show component inventory, permissions, risk, and token/context cost. | Phase 3 missing explicit mapping before this catalog | Read-only inspection command. |
| `plugin_validate` | Validate plugin package and manifest. | Phase 3 implemented for manifest planning; full package validation scheduled | Must report warnings/errors without executing plugin code. |

---

## Required additions to future phase work

The following items were not explicit enough in the existing Raiker docs before this catalog and should be picked up by later implementation plans:

1. Add `notebook_edit` as a distinct Phase 3 tool, separate from plain text `edit_file`.
2. Add LSP tools as first-class Phase 3 read-only code-intelligence tools: diagnostics, definition, references, type info, symbols, implementations, and call hierarchy.
3. Add `monitor` as a Phase 4 background watch tool with shell-level risk and cancellation/event-rate controls.
4. Split scheduled automation into explicit Raiker tools: create/list/delete/wakeup, with hosted routines deferred to Phase 5.
5. Add MCP resource tools: list/read/wait/discover, with trust and egress controls.
6. Add explicit plugin components for LSP servers, monitors, output styles, themes, user config, dependencies, details, reload, marketplace, and validation.
7. Add dynamic workflow/team tools to Phase 4/5 with parent/child event linkage, budgets, cancellation, and audit.
8. Add local vs hosted notification semantics: local notifications may be Phase 4; hosted push/share links require Phase 5 privacy/auth controls.

---

## Non-activation rule

Until the relevant phase gates are fully implemented and verified:

- plugin code execution remains disabled;
- graph/codemap runtime indexing remains disabled;
- semantic/vector memory writes remain disabled;
- external channels remain disabled;
- MCP/LSP/plugin server startup remains disabled unless explicitly trusted and approved;
- monitors/watchers remain disabled;
- subagent and multi-agent runtime execution remains disabled;
- remote/container/cloud execution remains disabled;
- hosted routines, marketplace installs, hosted push notifications, and share links remain disabled.
