# Tool and plugin catalog

> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

This catalog is the canonical visible terminal command surface. Commands remain
governed by the acting principal, policy, capability gate, decision mode, and
executor availability.

Approval resolution is `metadata_only` except for an approved local **file
mutation** (`write_file` / `edit_file` / `apply_patch`), which is
executed once through the governed approval execution relay. A supported durable mutation is
`implemented_approval_required`. Strict non-allow blocking, role revoke
governed, and capability gate per action are enforced.

Approval resolution executes an approved local file mutation through the governed relay and is metadata-only for every other capability. Unsupported capabilities are disabled and fail-closed. Strict non-allow blocking, role revoke governed, and capability gate per action are enforced.

## CLI Command Surface

| Tool Name | Descriptions | Permissions | Implemented |
|---|---|---|---|
| `storage_lifecycle_evidence_bundle` | Redacted lifecycle evidence bundle | owner-governed read | Yes, read-only |
| `storage_lifecycle_policy_simulation` | Non-executing policy simulation | owner-governed read | Yes, dry-run only |
| `/storage-lifecycle-evidence` | View lifecycle evidence | governed read | Yes |
| `/storage-lifecycle-evidence --summary` | View evidence summary | governed read | Yes |
| `/storage-lifecycle-evidence --json` | Export evidence metadata | governed read | Yes |
| `/storage-lifecycle-policy-simulation` | Simulate lifecycle policy | governed read | Yes, dry-run only |
| `/storage-lifecycle-policy-simulation --summary` | View simulation summary | governed read | Yes |
| `/storage-lifecycle-policy-simulation --json` | Export simulation metadata | governed read | Yes |

```text
/approval-audit [--summary]
/approval-preview <preview_id> [--json]
/approval-previews [--json] [--status <status>] [--limit <n>]
/approval-readiness [--summary|--json]
/approvals
/approve <id>
/capabilities
/capability-gate <capability>
/capability-gate disable <capability> [--reason <reason>]
/capability-gate enable <capability> --state <state> [--reason <reason>]
/capability-gates
/channel-readiness [--summary|--json]
/channels
/checkpoints
/cleanup-readiness [--summary|--json]
/clients
/deny <id>
/doctor
/events
/execution-profiles
/graph-approval-preview
/graph-plan
/graph-readiness [--summary|--json]
/graph-rollback-plan
/graph-status
/help
/launch --provider <provider> --model <model>
/memory
/memory-approval-preview [--summary]
/memory-forget <memory_id>
/memory-list
/memory-readiness [--summary|--json]
/memory-review [--summary]
/memory-rollback-plan
/memory-search <query>
/memory-store <text>
/model capabilities
/model current
/model health
/model use --provider <provider> --model <model>
/model use <profile_id>
/models
/plugin-plan <manifest_path>
/plugin-readiness [--summary|--json]
/plugins
/proposal <proposal_id> [--json] [--mark <proposed|acknowledged|deferred|rejected|superseded>] [--approval-preview]
/proposals [--json] [--status <proposed|acknowledged|deferred|rejected|superseded>] [--limit <number>]
/providers
/quit
/reasoning
/reasoning off
/reasoning set <mode-or-effort>
/reasoning status
/remote-readiness [--summary|--json]
/review [--summary] [--staged] [--path <path>] [--json] [--limit <number>] [--severity <info|low|medium|high>] [--propose-fixes] [--proposals-only] [--save-proposals]
/rollback-plan
/runtime-mode
/runtime-mode activate <mode_name> [--reason <reason>]
/runtime-mode disable [--reason <reason>]
/runtime-mode status
/runtime-readiness
/semantic-memory
/status
/storage-lifecycle [--summary|--graph|--memory]
/storage-lifecycle-cleanup-preview [--summary]
/storage-lifecycle-evidence [--summary] [--json] [--status <status>] [--target <graph|memory|rollback|storage|plugin|channel|remote>] [--limit <number>]
/storage-lifecycle-handoff [--summary]
/storage-lifecycle-policy-simulation [--summary] [--json] [--status <status>] [--target <graph|memory|rollback|storage|plugin|channel|remote>] [--limit <number>]
/storage-lifecycle-retention [--summary]
/tasks
/trace <session_id> <turn_id>
/workspace
/workspace-view
/approval-relay
/bootstrap-owner
/budgets
/capability-mode
/channel-pair
/export
/graph-index
/plugin-exec
/principal
/principals
/project-graph
/remote-exec
/retention
/role
/roles
/routines
/semantic-write
/skill-candidates
/subagents
/symbol-graph
/teams
/user
/users
/vector-index
/whoami
```

Plugins and external integrations are never an authority bypass. A plugin or
connector capability must be registered, policy-gated, and allowed by the owner
before an executor can act.
