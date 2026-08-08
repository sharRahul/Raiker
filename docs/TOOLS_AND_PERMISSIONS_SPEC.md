# Tools and permissions

Tools are not called directly by clients or models. A proposed action is
validated, classified by policy, checked against the acting principal and
capability state, and routed only through RuntimeAuthority.

| Tool class | Posture |
|---|---|
| Read-only workspace and diagnostic access | Governed and auditable |
| Local supported executors | Policy-gated; decision mode and approvals apply |
| Approval resolution | Metadata-only by default |
| Repository writes (`git_branch`, `git_commit`) | Approval-required; the reviewed change set is what executes, and repository hooks never run |
| Remote/cloud and sensitive domains | Disabled and fail-closed |

Executors must validate arguments, keep output safe for audit, and refuse work
outside their documented scope. The complete visible command surface is in the
[tool and plugin catalog](RAIKER_TOOL_AND_PLUGIN_CATALOG.md).
