# The Governed Action Path

> Core Concepts › Governed Action Path. Back to [Core Concepts](core-concepts.md).

Every action — human, AI, model tool call, plugin, or background task — passes
through one path:

```
Principal -> RuntimeAuthority -> PolicyEngine -> ToolBroker -> Executor -> Event log
```

No component executes work off this path. If any stage returns a non-allow
decision, execution stops (**strict non-allow blocking**). Approval resolution is
**metadata-only**: resolving an approval records an immutable decision; it does
not itself execute the action.

See also: [Capability Gates](core-concepts-capability-gates.md),
[Decision Modes](core-concepts-decision-modes.md),
[Events & Audit](core-concepts-events-and-audit.md).
