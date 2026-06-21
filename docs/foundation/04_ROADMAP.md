> **Foundation document.** This is a living design-foundation doc (moved from `docs/completed/` during the 2026-06-21 documentation alignment). For current implementation status see the canonical ledger `docs/IMPLEMENTATION_STATUS.md`; for outstanding work see `docs/GAP_AND_TODO_ANALYSIS.md`. As of that date: Phases 1–9 foundations are in place, the launchable UI is a local terminal client (native Textual Rich TUI + plain fallback), and all runtime execution remains disabled.

# 04 Roadmap

> **Two phase-numbering schemes exist.** This foundation roadmap uses the *original design*
> numbering below (Phase 0–9, where Phase 8 = "UI and Channels"). The **build/ledger** scheme used by
> `docs/IMPLEMENTATION_STATUS.md` and `docs/ARCHITECTURE.md` is different and has **no Phase 8**
> (build phases jump 7 → 9). When reconciling status, the ledger's build-phase scheme is canonical.

## Roadmap Rules

The build agent must implement phases in order. Future-phase features may have interfaces or stubs only. The build agent must not implement a future-phase production feature early unless the user explicitly changes the roadmap.

## Phase 0 — Documentation and Scaffolding

Outputs:
- Directory scaffold.
- Contract definitions.
- ADR template.
- README for local development.
- Empty module skeletons.

Verification:
- Project imports or compiles.
- Directory structure matches `11_DIRECTORY_STRUCTURE.md`.

## Phase 1 — Minimal Local Agent Loop

Outputs:
- CLI client.
- In-process or daemon runtime.
- PromptEnvelope and AgentEvent contracts.
- Mock model provider.
- Event log JSONL.
- Policy engine allow/ask/deny.
- Tool broker.
- read_file, list_directory, glob, grep, shell with approval.
- Checkpoint stub.
- ask_user.
- Unit tests.

Verification:
- CLI can answer with mock model.
- read_file works.
- grep works.
- shell requires approval.
- denied shell does not execute.
- events are written.

## Phase 2 — Model Providers

Outputs:
- llama.cpp server provider (native default backend).
- LM Studio/OpenAI-compatible provider.
- Hosted API provider stub.
- Provider capability registry.
- Privacy-aware routing.

Verification:
- Provider can be switched.
- Remote model call with sensitive marker is blocked or asks approval.

## Phase 3 — Checkpoints and File Edits

Outputs:
- edit_file tool.
- write_file tool.
- checkpoint before edit.
- restore code only.
- git diff verification.

Verification:
- file edit creates checkpoint.
- restore reverts file.
- diff is shown.

## Phase 4 — Memory MVP

Outputs:
- Markdown memory store.
- SQLite metadata.
- memory_search basic keyword.
- memory_write governed.
- memory_forget.

Verification:
- approved memory persists after restart.
- forget removes memory.
- untrusted memory poisoning candidate is rejected.

## Phase 5 — Plugins, Skills, Hooks

Outputs:
- plugin manifest parser.
- signed/trusted flag.
- skill loader.
- hook event dispatcher.
- command registry.

Verification:
- unsigned plugin cannot run high-risk hook.
- skill can be loaded and listed.

## Phase 6 — Subagents

Outputs:
- spawn_agent interface.
- researcher subagent.
- verifier subagent.
- parent-child events.

Verification:
- subagent returns structured result.
- subagent tools are scoped.

## Phase 7 — External Execution

Outputs:
- Docker adapter.
- SSH adapter.
- Daytona adapter stub.
- Modal adapter stub.
- external hosting deployment guide.

Verification:
- Docker command runs with read-only mount.
- SSH host must be allowlisted.
- Daytona/Modal stubs require approval and log egress.

## Phase 8 — UI and Channels

Outputs:
- Rich TUI.
- Desktop or Web UI MVP.
- REST API.
- Webhook receiver.
- Chat connector stubs.
- Voice/hotkey stubs.

Verification:
- same session receives CLI and REST prompt.
- webhook injection is labelled untrusted.

## Phase 9 — Advanced Memory and Graph

Outputs:
- vector index.
- graph index.
- project graph extraction.
- procedural memory to skill candidate.

Verification:
- graph query can answer dependency questions.
- repeated workflow can be proposed as a skill.

## Non-Deviation Contract for Small/Local Models

The build agent must treat these documents as the source of truth. If implementation context conflicts with these documents, the build agent must stop and report the conflict instead of inventing a new architecture. The build agent must not introduce unplanned services, unplanned data stores, unplanned network calls, unplanned plugin permissions, or unplanned model providers without creating an ADR and asking for approval.

Mandatory behaviour for all implementation tasks:

1. Restate the exact requirement being implemented.
2. Identify the source document and section that authorises the work.
3. List files expected to change before editing.
4. Make the smallest reversible change.
5. Add or update tests.
6. Run verification.
7. Record residual risks and TODOs.
8. If unsure, ask a question or create a clearly labelled assumption. Do not hallucinate.

The intended implementation should work with constrained models such as a local 9B class model on a 16GB GPU. Therefore tasks must be small, explicit, schema-driven, and testable. Long, vague implementation leaps are forbidden.
