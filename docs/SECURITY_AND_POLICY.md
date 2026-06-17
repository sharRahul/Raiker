# Security And Policy Blueprint

Raiker is an agent runtime. Security is not an optional feature; it is part of the execution path.

This document defines Phase 1 security behaviour and phase-scheduled policy boundaries. Phase scheduling controls build order only; the security behaviour for later phases must already be specified before implementation.

---

## Core Security Principle

No agent-controlled action may execute unless it has passed through:

```text
ToolAction proposal
  -> PolicyEngine review
  -> optional user approval
  -> ToolBroker dispatch
  -> EventLog recording
```

Clients, runtime modules, plugins, models, channels, and subagents must never execute tools directly.

---

## Threats Raiker Must Consider

Raiker must be designed around prompt injection, indirect prompt injection, data exfiltration, unsafe command execution, path traversal, hidden instruction leakage, memory poisoning, dependency supply-chain risk, plugin abuse, excessive agency, unbounded cost/resource usage, network egress abuse, user approval spoofing, channel abuse, and event log tampering.

Phase 1 does not solve every threat completely, but it must establish boundaries that every phase preserves.

---

## Phase 1 Trust Boundaries

```text
User input: untrusted
Files read from workspace: untrusted content
Model output: untrusted proposal
ToolAction: untrusted until policy-reviewed
PolicyDecision: trusted only if produced by policy engine
ToolResult: trusted as execution result, but output content may be untrusted
Event log: append-only audit record
```

---

## Policy Decisions

Every `ToolAction` receives one decision:

- `allow` — broker may execute;
- `deny` — broker must not execute;
- `needs_approval` — broker must pause and request user approval.

Phase-scheduled decisions such as `defer`, `allow_once`, `allow_for_session`, `allow_for_project`, and `allow_managed` are defined in `docs/TOOLS_AND_PERMISSIONS_SPEC.md`.

---

## Default Phase 1 Policy Matrix

| Action | Default decision | Notes |
|---|---:|---|
| Simple chat | allow | No tool execution. |
| Read file inside workspace | allow | Text files only unless explicitly handled. |
| List directory inside workspace | allow | Stable sorted output. |
| Glob inside workspace | allow | Bounded results. |
| Grep inside workspace | allow | Bounded results; text files only. |
| Read outside workspace | deny | Prevent path traversal. |
| Write file | deny | Phase 2 implements approval-gated file writes. |
| Delete file | deny | Phase 2 implements tightly scoped approval flow. |
| Local command execution | needs_approval | Never auto-run in Phase 1. |
| Network request | deny | Phase 3 implements egress-policy-gated web access. |
| Memory write | deny/defer | Phase 1 creates candidates; Phase 2 writes governed memory. |
| Plugin execution | deny | Phase 3 implements plugin lifecycle and permission diff. |
| Remote execution | deny | Phase 4/5 implement execution profiles. |
| Channel approval relay | deny | Disabled by default in all channels unless explicitly configured. |

---

## Path Safety Requirements

All filesystem tools must:

1. resolve requested path to an absolute path;
2. resolve workspace root to an absolute path;
3. verify requested path is inside workspace root;
4. reject path traversal attempts;
5. reject symlink escapes unless explicitly allowed by a phase-scheduled policy rule;
6. return structured errors instead of raw tracebacks.

---

## Command Safety Requirements

Phase 1 local command behaviour:

- command actions are proposed, logged, and policy-reviewed;
- policy returns `needs_approval`;
- command is not executed unless an explicit approval object exists;
- CLI MVP may stop at approval-required response;
- no silent background execution is allowed.

Phase 2 adds scoped allowlists, sandboxing rules, timeout enforcement, environment restrictions, command previews, and kill/cancel controls according to `docs/TOOLS_AND_PERMISSIONS_SPEC.md`.

---

## Event Logging Security Requirements

Every security-relevant decision must be logged:

- action proposed;
- policy decision;
- approval requested;
- approval received or denied;
- tool started;
- tool completed;
- tool failed;
- denied action;
- error;
- checkpoint.

Event log records must not include secrets unless explicitly redacted.

---

## Secret Handling Requirements

Phase 1 must not require secrets.

Phase-scheduled tasks that introduce secret references must:

- never commit secrets;
- load from environment or OS secret store;
- redact values in logs;
- store only references, not secret values;
- use fake secrets in tests.

---

## Memory Governance Requirements

Phase 1 must not write long-term memory automatically. It may produce memory candidates.

```json
{
  "candidate_id": "memcand_01H...",
  "source_event_id": "evt_01H...",
  "text": "User prefers local-first models.",
  "sensitivity": "normal",
  "confidence": 0.8,
  "decision": "deferred"
}
```

Phase-scheduled memory writes must include provenance, confidence, sensitivity, retention, approval state, deletion support, and poisoning controls.

---

## Approval Requirements

Approval prompts must include action ID, tool name, exact arguments, risk level, policy reasons, expected effect, and whether the action changes files, runs a command, uses network, exports data, persists memory, or may cost money.

Approvals must be bound to action ID. A user approving one action must not approve a different action accidentally.

---

## Security Tests Required In Phase 1

Minimum tests:

- outside-workspace file read is denied;
- path traversal is denied;
- local command action requires approval;
- denied action is not executed;
- policy decision is logged;
- tool output failure is logged;
- event log does not contain raw secret-like test values;
- invalid tool name fails safely;
- action without policy decision cannot execute.

---

## Security Non-Deviation Rules

Builder agents must not:

- call command execution APIs outside the approved command tool implementation;
- read files directly from runtime code as an agent action;
- add network libraries for Phase 1;
- add plugin execution in Phase 1;
- add durable memory writes in Phase 1;
- bypass approval for local commands;
- suppress security events;
- hide failures behind vague messages.
