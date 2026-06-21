> **Foundation document.** This is a living design-foundation doc (moved from `docs/completed/` during the 2026-06-21 documentation alignment). For current implementation status see the canonical ledger `docs/IMPLEMENTATION_STATUS.md`; for outstanding work see `docs/GAP_AND_TODO_ANALYSIS.md`. As of that date: Phases 1–9 foundations are in place (no Phase 8), the launchable UI is a local terminal client (native Textual Rich TUI + plain fallback), and all runtime execution remains disabled.

# 09 Implementation Plan — Small Model Friendly

This plan decomposes Phase 1 into small tasks. A constrained model must perform one task at a time.

## Phase 1 Task List

### T01 Create Repository Scaffold
Create directories exactly as specified in `11_DIRECTORY_STRUCTURE.md`. Add placeholder README files in empty directories if required by the language/tooling.

Verification:
- Directory tree exists.
- No extra top-level directories without approval.

### T02 Add Contract Models
Create PromptEnvelope, AgentEvent, PolicyDecision, ToolDescriptor, ToolCallRequest, ToolCallResult.

Verification:
- Unit tests instantiate each contract.
- JSON serialisation/deserialisation works.

### T03 Add Event Log Writer
Implement append-only JSONL event writer.

Verification:
- Writing event appends line.
- Event includes event_id and timestamp.
- Invalid event rejected.

### T04 Add Policy Engine MVP
Implement static allow/ask/deny policy.

Rules:
- read/list/grep/glob = allow.
- shell = ask.
- destructive shell = deny.
- network = ask.
- external upload = deny.

Verification:
- Tests for allow, ask, deny.

### T05 Add Tool Broker Skeleton
Tool registry, descriptor lookup, argument validation placeholder, policy call, event emission.

Verification:
- Registered read tool can be found.
- Unknown tool fails safely.

### T06 Implement read_file
Read text file from workspace scope.

Verification:
- Reads file.
- Blocks path outside workspace.
- Logs event.

### T07 Implement list_directory
List files within workspace.

Verification:
- Lists directory.
- Blocks traversal.

### T08 Implement glob and grep
Implement deterministic search.

Verification:
- glob matches expected.
- grep returns file/line snippets.

### T09 Implement shell with Permission
Shell tool must ask before execution. Denied approval must not execute.

Verification:
- approval path executes harmless command.
- denial path does not execute.
- destructive command denied before ask.

### T10 Add Mock Model Provider
Mock model returns deterministic tool plans for tests.

Verification:
- returns configured response.
- no network.

### T11 Add Runtime State Machine
Implement states with event emission. For skipped states, emit skipped event.

Verification:
- simple prompt follows expected state sequence.

### T12 Add CLI
CLI accepts prompt and workspace path. It can run one turn.

Verification:
- CLI returns mock response.
- events file created.

### T13 Add Checkpoint Stub
Create checkpoint record with session, turn, timestamp, and reason. File snapshots can be TODO.

Verification:
- checkpoint event emitted.

### T14 Add Documentation
Document install, run, test, architecture, and limitations.

### T15 Add Phase 1 End-to-End Test
Test read/search/shell permission flow through CLI or runtime.

## Rule
If any task requires more than five files changed, split it.

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
