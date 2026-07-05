# Raiker Documentation

Raiker is a security-first AI agent that connects to any backend LLM — local,
home-lab, or hosted — while keeping every capability governed, default-disabled,
and fail-closed. This is the documentation home.

The docs are being reorganized into seven sections (Claude-Code-docs style).
Sections migrate incrementally; until a section's dedicated page lands, the
"Sources" column points at the existing detailed documents.

| Section | Status | Read |
|---|---|---|
| **Getting Started** | ✅ migrated | [getting-started.md](getting-started.md) |
| **Core Concepts** | ✅ migrated | [core-concepts.md](core-concepts.md) |
| **Use Raiker** | ⏳ migrating | `COMMANDS_AND_INTERACTIVE_MODE_SPEC.md`, CLI + web dashboard usage |
| **Platform & Integrations** | ⏳ migrating | `CHANNELS_SPEC.md`, `EXECUTION_ENVIRONMENTS_SPEC.md`, `REFERENCE_PLATFORM_COMPATIBILITY.md`, model/provider config |
| **Capabilities** | ⏳ migrating | [RUNTIME_EXECUTORS_SPEC.md](RUNTIME_EXECUTORS_SPEC.md), `RAIKER_TOOL_AND_PLUGIN_CATALOG.md`, `PLUGIN_SYSTEM_SPEC.md`, [DECISION_MODES_SPEC.md](DECISION_MODES_SPEC.md) |
| **Implementation** | ⏳ migrating | [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md), `GAP_AND_TODO_ANALYSIS.md`, `VERIFICATION_PLAN.md`, `threat-models/` |
| **Best Practices** | ⏳ migrating | [SECURITY_ARCHITECTURE.md](SECURITY_ARCHITECTURE.md), `LOCAL_VALIDATION_GATE.md` |

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
