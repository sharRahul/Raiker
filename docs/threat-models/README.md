# Per-capability threat models

**Canonical** for *what could go wrong with one specific capability, and what
stops it*. The repository-wide view — assets, trust boundaries and the threats
that cross them — is [`../THREAT_MODEL.md`](../THREAT_MODEL.md); the standards
mappings are [OWASP GenAI](../OWASP_GENAI_SECURITY_MAPPING.md) and
[OWASP Agentic](../OWASP_AGENTIC_TOP10_MAPPING.md).

A document here is a precondition, not a write-up after the fact. A capability
reaches a runtime-enabled state only through the governed control plane, and
opening a higher-risk gate requires a threat-model acknowledgement recorded
against the acting principal — so the document is what the owner is
acknowledging.

## Execution and approval

| Capability | Threat model |
|---|---|
| `approval_execution_relay` | [Approval execution relay](approval-execution-relay.md) |
| `audit_export` | [Audit export](audit-export.md) |
| Critical approvals (human-only, step-up verified) | [Critical approval lifecycle](critical-approval-lifecycle.md) |
| `file_write_execution`, `patch_apply_execution` | [Workspace file mutation](workspace-file-mutation.md) |
| `checkpoint_restore_execution` | [Checkpoint restore and rewind](checkpoint-restore.md) |
| `shell_execution` | [Governed command execution](shell-execution.md) |
| `process_execution` | [Direct process execution](process-execution.md) |
| `git_write_execution` | [Git writes](git-write.md) |
| `git_push_execution` | [Git push](git-push.md) |
| `container_execution_cap` | [Local container execution](container.md) |
| `remote_execution_cap`, `cloud_execution_cap` | [Remote / cloud execution](remote-cloud.md) |
| `scheduled_routines` | [Scheduled routines](scheduled-routines.md) |
| `subagents`, `multi_agent_teams` | [Subagents and multi-agent teams](subagents.md) |

## Egress

| Capability | Threat model |
|---|---|
| `web_fetch` (the `web_fetch` **and** `web_search` tools) | [Web read](web-fetch.md) |

`network_execution` was a second egress capability with a weaker guard and no
caller. It was deleted — capability, executor and gate — in BUG-232, and its
threat model with it. There is now exactly one answer to "what happens when
Raiker reaches the internet": [Web read](web-fetch.md).

## Memory, knowledge and planning

| Capability | Threat model |
|---|---|
| `memory_write_execution` | [Durable memory write](memory-write.md) |
| `memory_forget_execution` | [Durable memory forget](memory-forget.md) |
| `semantic_memory_runtime` | [Semantic memory search](semantic-memory.md) |
| `graph_indexing_runtime` | [Knowledge-graph indexing](graph-indexing.md) |
| `code_map_indexing` | [Repository code map](code-map-indexing.md) |
| `task_management_runtime` | [Task creation](task-management.md) |
| `project_assignment_runtime` | [Project assignment](project-assignment.md) |

## Models and inference

| Capability | Threat model |
|---|---|
| `model_provider_runtime` | [Model provider runtime](model-provider.md) |
| `hosted_model_runtime`, `private_network_model_runtime` | [Hosted and private-network models](hosted-models.md) |
| `advisor_model_runtime` | [Advisor model runtime](advisor-model.md) |
| `vector_embedding_runtime` | [Vector embedding runtime](vector-embedding.md) |

## Extensions

| Capability | Threat model |
|---|---|
| `plugin_install` | [Plugin install](plugins.md) |
| `plugin_execution_cap` | [Plugin execution](plugin-execution.md) |
| `plugin_runtime_cap` | [Plugin code runtime](plugin-runtime.md) |
| `plugin_sandboxed_runtime_cap` | [Sandboxed plugin code runtime](plugin-sandboxed-runtime.md) |
| `plugin_sandbox_image_pull_cap` | [Sandboxed plugin image pull](plugin-sandbox-image-pull.md) |
| `plugin_revocation_cap` | [Plugin revocation](plugin-revocation.md) |
| `mcp_builder_runtime` | [Local MCP builder](mcp-builder.md) |
| `mcp_connector_runtime` | [Local MCP connector](mcp-connector.md) |
| MCP monitoring and containment | [MCP monitoring](mcp-monitoring.md) |
| Remote MCP transport (fail-closed) | [Remote MCP transport](mcp-remote.md) |
| The connector manifest surface as a whole | [Connector ecosystem](connector-ecosystem.md) |

## Connectors and channels

| Capability | Threat model |
|---|---|
| `external_channel_runtime`, `channel_approval_relay` | [Reference channel](channels.md) |
| `connector_github_runtime` | [GitHub read-only connector](connectors-github.md) |
| `connector_gmail_runtime` | [Gmail read-only connector](connectors-gmail.md) |
| `connector_gcal_runtime` | [Google Calendar read-only connector](connectors-gcal.md) |
| `connector_slack_runtime` | [Slack read-only connector](connectors-slack.md) |

## Local personal-data stores (Tier 6)

| Capability | Threat model |
|---|---|
| `reminder_runtime` | [Reminder runtime](reminders.md) |
| `calendar_runtime` | [Calendar runtime](calendar.md) |
| `email_runtime` | [Email runtime](email.md) |

The remaining Tier-6 domains — finance, investment, medical, pregnancy, CCTV,
home security and hardware — have **no executor and no enable path**, so there is
nothing to model until one is proposed. See
[Known limits](../KNOWN_LIMITS.md).

## Platform-wide

| Concern | Threat model |
|---|---|
| Per-turn machine identity | [Machine identity](machine-identity.md) |
| Credential lifecycle and bounded monitoring | [Credential security](credential-security.md) |
| Background integrity sweep | [Integrity sweep](integrity-sweep.md) |
| Local-owner lock screen | [Local lock screen](local-lock-screen.md) |

---

## Coverage — every capability with a real executor has one

Re-derived **2026-08-23** by comparing `REAL_EXECUTOR_CAPABILITIES`
(`raiker/runtime/executors/__init__.py`) against the index above.
**All forty-five are covered**, and every one is reachable from a table on this
page rather than only by knowing a filename.

**A threat model is not the same as a reachable path**, and the 2026-08-24 trace
([GEP-04](../plans/GOVERNANCE_ENTRY_PATHS.md)) is what made the difference
checkable: nine of the forty-five have a real executor that no product path
reaches, and five more have their work governed by a control other than their own
gate. Each keeps its threat model for the reason it keeps its gate — the day
something reaches one of them, the analysis is what is already there.
`raiker/runtime/authority/entry_paths.py` records which is which.

The previous audit recorded eight as missing. Re-deriving it found the count was
**understated**, because a capability was credited to any document that mentioned
its name in passing. Three more had no analysis of their own —
`shell_execution` (the broadest capability in the product), `process_execution`,
and `semantic_memory_runtime` — and `file_write_execution` /
`patch_apply_execution` had only a section of the repository-wide
[`../THREAT_MODEL.md`](../THREAT_MODEL.md) whose central claim had gone stale.
Eleven documents close that:

| Capability | Threat model | Why it needed one |
|---|---|---|
| `shell_execution` | [Governed command execution](shell-execution.md) | The broadest reach in the product, and relayed by an approval |
| `process_execution` | [Direct process execution](process-execution.md) | Same lifecycle, deliberately *not* relayed |
| `file_write_execution`, `patch_apply_execution` | [Workspace file mutation](workspace-file-mutation.md) | Relayed; containment and checkpoint bounds were undocumented per-capability |
| `memory_write_execution` | [Durable memory write](memory-write.md) | Relayed — approving really writes a durable record |
| `memory_forget_execution` | [Durable memory forget](memory-forget.md) | Relayed — approving really removes one |
| `task_management_runtime` | [Task creation](task-management.md) | Relayed, and a task raises unattended turns later |
| `project_assignment_runtime` | [Project assignment](project-assignment.md) | Relayed; the move changes a conversation's standing context |
| `web_fetch` | [Web read](web-fetch.md) | Egress, and where untrusted external text enters a turn |
| `graph_indexing_runtime` | [Knowledge-graph indexing](graph-indexing.md) | Reads the workspace and derives a durable index |
| `code_map_indexing` | [Repository code map](code-map-indexing.md) | Reads the workspace and derives a durable symbol index |

Two findings came out of writing them, and both are recorded in the pages
themselves rather than smoothed over:

- **Two egress implementations existed, and now do not.** `WebFetchExecutor`
  and `NetworkExecutor` both reached the network through `sandbox.fetch_url`,
  whose only control was a hard-coded four-host allowlist — none of
  `WebAccessService`'s address guard. BUG-232 deleted `NetworkExecutor`, the
  `network_execution` capability, and `fetch_url` itself, and repointed the
  `web_fetch` executor at `WebAccessService`, so there is one implementation.
  See [`web-fetch.md`](web-fetch.md).
- **Checkpoint capture is bounded.** A file over 8 MiB is written and recorded
  `oversize`, which means *not restorable*. See
  [`workspace-file-mutation.md`](workspace-file-mutation.md).

Both are tracked in
[the prioritised backlog](../REFERENCE_PLATFORM_COMPATIBILITY.md#5-prioritised-backlog).

A test keeps this honest rather than a promise: see
[`../VERIFICATION_PLAN.md`](../VERIFICATION_PLAN.md).
