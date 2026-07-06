# Raiker Documentation

Raiker is a security-first AI agent that connects to any backend LLM — local,
home-lab, or hosted — while keeping every capability governed, integrated gates default-ask,
and no-executor capabilities fail-closed. This is the documentation home.

The user-facing guide lives under [`guide/`](guide/) and is organized into seven
sections (Claude-Code-docs style). Each section has an index page plus focused
sub-pages; the machine-readable navigation is [`guide/manifest.json`](guide/manifest.json),
which the web dashboard's Docs/Help panel can render. The canonical detailed
documents (executor spec, threat models, implementation ledger, …) stay at the
`docs/` root and remain the source of truth.

| Section | Index | About |
|---|---|---|
| **Getting Started** | [guide/getting-started.md](guide/getting-started.md) | Install → bootstrap → model → first governed action |
| **Core Concepts** | [guide/core-concepts.md](guide/core-concepts.md) | The governance model, one concept per page |
| **Use Raiker** | [guide/use-raiker.md](guide/use-raiker.md) | Surfaces, commands, and everyday workflows |
| **Platform & Integrations** | [guide/platform-integrations.md](guide/platform-integrations.md) | Models, channels, execution environments, plugins |
| **Capabilities** | [guide/capabilities.md](guide/capabilities.md) | The capability model, tiers, and catalog |
| **Implementation** | [guide/implementation.md](guide/implementation.md) | Sources of truth, slice discipline, validation |
| **Best Practices** | [guide/best-practices.md](guide/best-practices.md) | Staying safe as you grant power |

## Start here

1. **[Getting Started](guide/getting-started.md)** — install, bootstrap the
   owner, connect a model, enable your first capability, run.
2. **[Core Concepts](guide/core-concepts.md)** — the governed action path,
   principals and roles, runtime modes, capability gates, decision modes,
   executors, and audit.

## Canonical references

- **[Implementation Status](IMPLEMENTATION_STATUS.md)** — the control ledger of
  what is built, verified, or intentionally deferred (source of truth).
- **[Runtime Executors Spec](RUNTIME_EXECUTORS_SPEC.md)** — per-capability truth
  about what can execute today.
- **[Handoff](HANDOFF.md)** — where the current build effort stands and what is
  next.
