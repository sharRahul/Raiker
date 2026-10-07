# Tools and permissions

Tools are not called directly by clients or models. A proposed action is
validated only after the broker verifies the turn's signed machine identity,
then classified by policy, checked against the acting machine principal and
capability state, and routed only through RuntimeAuthority.

Every agentic call carries two non-interchangeable identities: the verified
machine actor and its authenticated human owner scope. The actor is recorded in
actions, approvals, and events; the owner scope selects account resources and
credential references. A missing or mismatched identity is refused before any
policy, hook, credential, or executor side effect. The Permissions view therefore
shows owner controls separately from the agent's derived `Direct`, `Ask`,
`Denied`, or `Unavailable` authority; the agent cannot edit either column.
Approval proposals snapshot the verified machine key and validity fields at
creation, so key rotation or later turn cleanup cannot change who proposed an
already-reviewed action. Activity preserves the literal event actor and adds the
turn identity only as separate context.

| Tool class | Posture |
|---|---|
| Read-only workspace and diagnostic access | Governed and auditable |
| Local supported executors | Policy-gated; decision mode and approvals apply |
| Approval resolution | Metadata-only by default |
| Repository writes (`git_branch`, `git_commit`) | Approval-required; the reviewed change set is what executes, and repository hooks never run |
| Repository push (`git_push`) | Approval-required under its own capability; the remote's host must be on the owner egress allowlist and the owner's credential must be set; never forces and never deletes |
| Remote/cloud and sensitive domains | Disabled and fail-closed |

Executors must validate arguments, keep output safe for audit, and refuse work
outside their documented scope. The complete visible command surface is in the
[tool and plugin catalog](RAIKER_TOOL_AND_PLUGIN_CATALOG.md).

## Personal delegation and concrete effects

A future personal-goal envelope is an owner-defined restriction of existing
permission, never blanket consent. Accounts, destinations, resource paths,
environment, expiry, version and budget must bind the covered scope. Browser
clicks and connector calls are classified by resulting effects, not tool names.
Changed approved arguments require the current governing decision path again;
revoked authority fails before execution. Existing ask/allow/auto/deny and
critical actions stay authoritative; Muse defaults are not adopted. PAA-05/06
and the [target spec](PERSONAL_AUTONOMOUS_AGENT_SPEC.md) own new workflows.
