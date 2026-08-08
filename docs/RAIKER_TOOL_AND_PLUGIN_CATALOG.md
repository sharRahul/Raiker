# Tool and plugin catalog

> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

This catalog is the canonical visible terminal command surface. Commands remain
governed by the acting principal, policy, capability gate, decision mode, and
executor availability.

Approval resolution is `metadata_only` except for an approved local file
mutation (`write_file` / `edit_file` / `apply_patch`), an approved repository
change (`git_branch` / `git_commit`), an approved GitHub write (`github_write`),
or an owner-configured
SSH/Daytona command, which is executed once through the governed approval execution relay.
A supported durable mutation is
`implemented_approval_required`; unsupported capabilities are disabled and
fail-closed. Strict non-allow blocking, role revoke governed, and capability gate per action
are enforced.
Approval remains metadata-only for every other capability.

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

## Model-facing skill read

| Tool Name | Descriptions | Permissions | Implemented |
|---|---|---|---|
| `skill_load` | Read one installed, active skill's instructions by name, or one file from its bundle via the optional `file` argument | owner-scoped read; no approval | Yes, read-only |

`skill_load` is a read like `memory_get`: it returns the owner's own stored
instruction document to the calling model and mutates nothing. It is
owner-scoped, refuses a deactivated skill so turning one off actually withholds
it, and resolves a requested bundle file against the archive's own listing so a
model-supplied name cannot escape the bundle. Only the skill *index* — one line
per active skill — enters a turn's system context; bodies and bundled references
load through this tool on the turns that need them.

A skill grants no capability and Raiker executes nothing a skill ships.
Installing and managing skills is owner-scoped CRUD (Extensions → Skills), not a
governed execution path.

## Model-facing loop tools

| Tool Name | Descriptions | Permissions | Implemented |
|---|---|---|---|
| `update_plan` | Record or revise the agent's ordered plan for a conversation, one status per step | owner-scoped write of the model's own intent; no approval | Yes |
| `spawn_subagent` | Delegate a bounded, read-only investigation and return only its findings | read-shaped; each delegated step is re-brokered | Yes, read-only |
| `mcp__<server>__<tool>` | Call one tool on a connected MCP server | `mcp_connector_runtime` gate + decision mode + containment | Yes |

`update_plan` is read-shaped at the policy layer because it executes nothing: it
writes one owner-scoped row naming what the model intends to do next, which the
workspace renders as a live checklist. Every step it names is governed again when
it is actually attempted, so a plan grants no authority and creates no standing
permission. It is fail-closed — a malformed plan is refused by name and the
stored plan is left untouched.

`spawn_subagent` is read-shaped for the same reason `connector_read` is: the
subagent's steps are each re-brokered through the policy engine, gates and audit
path, and only read-only, local, non-egress tools are delegable. A step naming a
write, a command, a connector, an MCP tool, or a nested spawn is refused before
the subagent is created. Its findings reach the calling model as untrusted data,
never as instructions, and the audit trail keeps the contract, the steps, and the
tools used rather than the content.

## Model-facing web reads

| Tool Name | Descriptions | Permissions | Implemented |
|---|---|---|---|
| `web_fetch` | Read one web page and return it as bounded text | `web_fetch` gate + decision mode (default `ask` withholds) + owner egress allowlist | Yes, read-only |
| `web_search` | Query the owner-configured search endpoint for pages to read | same gate and mode; **off** until the owner configures an endpoint | Yes, read-only |

Both are read-shaped at the policy layer for the same reason `connector_read` is:
what governs them is enforced inside the tool. `raiker/runtime/web_access.py`
checks, in order, the `web_fetch` capability gate (disabled ⇒ fail closed), the
per-capability decision mode (**default `ask` ⇒ withheld**; `auto` withholds too,
because reaching the open internet on a model's say-so is never low-risk), and
the owner egress allowlist `RAIKER_WEB_EGRESS_ALLOWLIST` (empty ⇒ fail closed).

This is the one egress boundary where the URL itself is **model-supplied**, so
the URL is checked as well as the host: HTTPS only, no embedded credentials, and
a destination that resolves to a public address — an allowlisted *name* can still
point at the loopback interface or a home network, and that is refused. Every
redirect hop is re-checked the same way, because a redirect is a second
destination the owner never allowlisted. The allowlist is deliberately separate
from `RAIKER_CONNECTOR_EGRESS_ALLOWLIST`: allowing a connector's API host must
not also allow the agent to fetch arbitrary pages from it.

Raiker ships no search provider. `web_search` refuses with
`web_search_not_configured` until the owner sets `RAIKER_WEB_SEARCH_ENDPOINT`
(and, if the provider needs one, `RAIKER_WEB_SEARCH_KEY`) and allowlists that
host. Both tools return their content framed as untrusted data, never
instructions, and broker events keep the URL, the query, and the sizes rather
than the fetched content.

A projected MCP tool is callable only while the `mcp_connector_runtime` gate is
enabled **and** the decision mode permits it; a mode that would withhold every
call projects no tools at all, so the model is never offered one the runtime
would refuse. Extensions → MCP servers states which of those two conditions is
unmet.

Every tool advertised to a model must have a policy verdict: `PolicyEngine`
hard-denies anything in neither `allowed_read_actions` nor
`approval_required_actions`, so a tool present in the schema and absent from both
is unreachable. `tests/test_policy_engine.py` asserts this invariant.

Plugins and external integrations are never an authority bypass. A plugin or
connector capability must be registered, policy-gated, and allowed by the owner
before an executor can act.
