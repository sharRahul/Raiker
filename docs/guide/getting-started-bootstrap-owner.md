# Bootstrap the Owner

> Getting Started › Bootstrap the Owner. Back to [Getting Started](getting-started.md).

The first human principal is the **owner** — the only identity that can activate
runtime modes and enable capabilities.

```bash
raiker /bootstrap-owner --display "Your Name"
```

This creates the owner principal, the human-only `runtime_gate_manager` role, and
the initial audit events. A `--force-recover` break-glass path exists if you ever
need to re-bootstrap.

Roles are split into **human-only** (`owner`, `admin`, `runtime_gate_manager`)
and AI-assignable roles; safety-critical operations are reserved for humans. See
[Core Concepts › Principals & Roles](core-concepts-principals-and-roles.md).

## Next

- [Connect a Model](getting-started-connect-a-model.md)
