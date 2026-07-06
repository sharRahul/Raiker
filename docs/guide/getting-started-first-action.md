# Your First Governed Action

> Getting Started › First Action. Back to [Getting Started](getting-started.md).

Every capability ships **disabled**. Enabling one is a deliberate, audited,
human-only act.

```bash
raiker /runtime-mode activate local_single_user_runtime
raiker /capability-gate enable file_write_execution --state enabled_runtime --confirm <token>
raiker /capability-mode file_write_execution auto
raiker --prompt "summarize the changes in the last commit"
```

Higher-risk capabilities additionally require a recorded threat-model
acknowledgement before they can be enabled. Once enabled, the capability's
[decision mode](core-concepts-decision-modes.md) controls how AI-proposed actions
are treated (`ask` by default). Every step is written to the append-only event
log; approval resolution is metadata-only.
