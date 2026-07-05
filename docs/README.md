# Raiker Documentation

Raiker is a security-first AI agent that connects to any backend LLM — local,
home-lab, or hosted — while keeping every capability governed, default-disabled,
and fail-closed. This is the documentation home.

The docs are organized into seven sections (Claude-Code-docs style). Each section
below has a dedicated landing page that orients you and links the canonical
detailed documents (executor spec, threat models, implementation ledger, etc.),
which remain the source of truth.

| Section | Status | Read |
|---|---|---|
| **Getting Started** | ✅ migrated | [getting-started.md](getting-started.md) |
| **Core Concepts** | ✅ migrated | [core-concepts.md](core-concepts.md) |
| **Use Raiker** | ✅ migrated | [use-raiker.md](use-raiker.md) |
| **Platform & Integrations** | ✅ migrated | [platform-integrations.md](platform-integrations.md) |
| **Capabilities** | ✅ migrated | [capabilities.md](capabilities.md) |
| **Implementation** | ✅ migrated | [implementation.md](implementation.md) |
| **Best Practices** | ✅ migrated | [best-practices.md](best-practices.md) |

## Start here

1. **[Getting Started](getting-started.md)** — install, bootstrap the owner,
   connect a model, enable your first capability, run.
2. **[Core Concepts](core-concepts.md)** — the governed action path, principals
   and roles, runtime modes, capability gates, decision modes, executors, and
   audit.

## Canonical references

- **[Implementation Status](IMPLEMENTATION_STATUS.md)** — the control ledger of
  what is built, verified, or intentionally deferred (source of truth).
- **[Runtime Executors Spec](RUNTIME_EXECUTORS_SPEC.md)** — per-capability truth
  about what can execute today.
- **[Handoff](HANDOFF.md)** — where the current build effort stands and what is
  next.
