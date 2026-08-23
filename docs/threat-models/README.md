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
| Critical approvals (human-only, step-up verified) | [Critical approval lifecycle](critical-approval-lifecycle.md) |
| `checkpoint_restore_execution` | [Checkpoint restore and rewind](checkpoint-restore.md) |
| `git_write_execution` | [Git writes](git-write.md) |
| `git_push_execution` | [Git push](git-push.md) |
| `container_execution_cap` | [Local container execution](container.md) |
| `remote_execution_cap`, `cloud_execution_cap` | [Remote / cloud execution](remote-cloud.md) |
| `scheduled_routines` | [Scheduled routines](scheduled-routines.md) |
| `subagents`, `multi_agent_teams` | [Subagents and multi-agent teams](subagents.md) |

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

## Capabilities with a real executor and no threat model

Recorded 2026-08-24 by comparing `REAL_EXECUTOR_CAPABILITIES`
(`raiker/runtime/executors/__init__.py`) against every document in this
directory. **Eight of the forty-five are not named in any threat model**, here or
in [`../THREAT_MODEL.md`](../THREAT_MODEL.md):

| Capability | Why it matters that it is missing |
|---|---|
| `memory_write_execution` | In `EXECUTABLE_ON_APPROVAL` — approving really writes a durable record |
| `memory_forget_execution` | In `EXECUTABLE_ON_APPROVAL` — approving really removes one |
| `task_management_runtime` | In `EXECUTABLE_ON_APPROVAL` — approving really creates a task row |
| `project_assignment_runtime` | In `EXECUTABLE_ON_APPROVAL` — approving really writes a project label |
| `web_fetch` | Egress, and the point at which untrusted external text enters a turn |
| `network_execution` | Egress. Approval is decision-only, but the gate is real |
| `graph_indexing_runtime` | Reads the workspace and derives a durable index |
| `code_map_indexing` | Reads the workspace and derives a durable symbol index |

This is a **documentation** gap, not a control gap: each of the eight is gated,
policy-reviewed and audited exactly like the capabilities that do have a
document, and the four relayed ones re-pass their own gate at execution time.
What is missing is the written analysis the owner acknowledges when opening the
gate. Tracked in
[the prioritised backlog](../REFERENCE_PLATFORM_COMPATIBILITY.md#5-prioritised-backlog)
and [Known limits](../KNOWN_LIMITS.md).
