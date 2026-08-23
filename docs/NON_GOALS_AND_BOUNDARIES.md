# Non-Goals And Boundaries

This document defines what Raiker is not, what Phase 1 must not build, and which behaviours require explicit ADR/spec changes before implementation.

Non-goals are safety rails. They prevent builder agents from adding impressive but misaligned features that weaken Raiker's architecture, security, or local-first model.

---

## Product Non-Goals

Raiker is not:

1. a chatbot-only application;
2. a terminal-only coding agent;
3. a TUI-first architecture;
4. a remote SaaS-first agent platform;
5. a Git replacement;
6. a backup system;
7. an ungoverned shell-command runner;
8. an unrestricted browser/web automation tool;
9. an auto-executing plugin marketplace;
10. a memory system that writes long-term facts without governance;
11. a multi-agent swarm that can spawn arbitrary workers;
12. a hosted-model proxy that silently sends local data to remote providers;
13. a general malware-analysis or offensive automation platform;
14. a system where interface richness decides authority.

> **Read the operative word.** Several non-goals above forbid *silent*,
> *ungoverned*, or *unrestricted* behaviour ("silently sends local data",
> "unrestricted browser automation", "ungoverned shell runner"). The boundary is
> **silent / ungoverned**, not **remote** or **capable**. An owner may connect
> owner-chosen, **monitored, governed** remote services (e.g. a remote MCP
> server) — that is *not* a non-goal. What stays out of scope is doing so
> *silently* or *without monitoring, findings, and an owner stop*. See
> `docs/SECURITY_AND_POLICY.md` → "Security Philosophy".

---

## Architecture Boundaries

| Boundary | Rule |
|---|---|
| Interface boundary | Every enabled client enters through the Agent Gateway. |
| Tool boundary | Every agent-controlled action routes through Tool Broker. |
| Policy boundary | No tool executes before PolicyDecision exists. |
| Approval boundary | Approval binds to exact action ID and current arguments. |
| Storage boundary | JSONL events are append-only; SQLite indexes metadata/state. |
| Model boundary | Model output is an untrusted proposal until parsed and validated. |
| Memory boundary | Long-term memory writes require governance. |
| Channel boundary | External senders are untrusted until paired and scoped. |
| Plugin boundary | Plugins are disabled until manifest, trust, and permission checks pass. |
| Execution boundary | SSH/Daytona execution is unavailable until an owner profile, credential reference, selection, policy, and approval exist; unsupported types fail closed. |

---

## Phase 1 Must Not Build

Phase 1 must not actively wire:

- Desktop UI;
- Web UI;
- Dashboard;
- Apple mobile runtime;
- Android mobile runtime;
- external chat/email/channel transports;
- plugin execution;
- hook execution with decision authority;
- durable vector/semantic memory writes;
- graph/codemap runtime indexing;
- subagent teams;
- autonomous multi-agent orchestration;
- remote/container/SSH/VPS/Kubernetes/cloud execution;
- hosted model calls in tests;
- hosted provider fallback;
- package installation automation;
- direct file writes/edits/deletes;
- network search/fetch;
- secret storage.

Phase 1 may include disabled/listable profiles, schemas, tables, and extension boundaries for these capabilities when required by the blueprint.

---

## Interface Boundaries

The global `raiker` command launches the first local terminal client. That does not make terminal, Rich TUI, or CLI canonical.

Forbidden language in docs/code/comments:

```text
TUI is the primary interface
terminal is the canonical UI
mobile is notification-only
web is secondary
all actions must originate from terminal
only terminal can approve actions
```

Allowed language:

```text
The terminal client is the first implemented client.
All implemented and enabled clients are equal-status primary interfaces through the Agent Gateway.
UI shape can differ, but action contracts, policy, event logging, approvals, sessions, and checkpoints remain shared.
```

---

## Security Boundaries

Builder agents must not:

- call filesystem APIs directly from runtime as an agent action;
- call subprocess/shell APIs outside the brokered command tool;
- hide local command execution behind a model/provider helper;
- perform network calls in Phase 1 runtime/tests;
- log raw secrets;
- write unvalidated model output into persistent memory;
- silently enable plugins, hooks, channels, or hosted providers;
- skip checkpoint creation for completed turns;
- suppress event logging to make tests easier.

---

## Storage Boundaries

Raiker storage is local-first by default:

- `.raiker/raiker.db` for SQLite state and indexes;
- `.raiker/events/*.jsonl` for append-only events;
- `.raiker/checkpoints/` for checkpoint manifests and snapshots;
- `.raiker/artifacts/` for bounded large outputs;
- config registries for model/channel profiles.

Do not introduce a required external database, graph database, vector database, queue, cloud object store, or hosted service in Phase 1.

Later phases may add optional adapters, but SQLite/JSONL local-first operation must remain supported.

---

## Model Provider Boundaries

**There is no offline fallback provider, and that is deliberate.** This section
once named "the deterministic mock provider" as the offline/test fallback; no
such provider exists, and `AsyncProviderFactory.create` refuses `mock`, `test`
and `test_only` profiles with `test_provider_not_available`. A fallback that
answers without a model would defeat the readiness gate, whose whole purpose is
to prove an exact model at an exact endpoint can really answer — so a Raiker with
no configured provider disables every model-backed action and says so, rather
than producing text from nothing.

What the boundary below actually says is that Raiker must not **require** any
*particular* provider. It must not require:

- a llama.cpp server running;
- LM Studio running;
- OpenAI-compatible endpoint;
- OpenRouter/Anthropic/OpenAI keys;
- internet access;
- GPU.

Later model providers must be selected through model profiles and policy, not hard-coded shortcuts.

---

## Memory Boundaries

Phase 1 may create memory candidates only. It must not persist durable memory records automatically.

Later memory writes must include:

- provenance;
- sensitivity;
- confidence;
- approval state;
- retention;
- correction/deletion support;
- memory usage attribution when used in context.

---

## Checkpoint Boundaries

Checkpoints are local agent-runtime safety records. They are not:

- Git commits;
- backup snapshots;
- full disk restore points;
- permission to mutate files without approval.

File restore or file-changing rewind requires a restore plan and approval when files change.

---

## When To Use An ADR

Use `docs/ADR_TEMPLATE.md` before implementation if a change would:

- add a required dependency;
- introduce a new persistence backend;
- enable network egress;
- change event names or schema versions;
- alter policy precedence;
- add plugin/hook/channel execution;
- change equal-interface semantics;
- alter checkpoint restore semantics;
- introduce hosted provider fallback;
- make a non-goal a goal.

---

## Builder Enforcement Checklist

Before coding, confirm:

- [ ] The task is inside the selected phase.
- [ ] The task has a task ID or documented issue.
- [ ] Required contracts are defined.
- [ ] Events are listed in `docs/EVENT_CATALOG.md`.
- [ ] Runtime transitions are legal.
- [ ] Storage tables/paths are specified.
- [ ] Policy decisions are specified.
- [ ] Failure modes are specified.
- [ ] Tests are listed in `docs/ACCEPTANCE_TESTS_BY_PHASE.md`.
- [ ] No non-goal is violated.
