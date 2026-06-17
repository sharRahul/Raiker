# Security And Policy Blueprint

Raiker is an agent runtime. Security is not an optional feature; it is part of the execution path.

This document defines Phase 1 security behaviour and future policy boundaries.

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

Clients, runtime modules, plugins, models, and subagents must never execute tools directly.

---

## Threats Raiker Must Consider

Raiker must be designed around these risks:

- prompt injection;
- indirect prompt injection from files or web content;
- data exfiltration;
- unsafe shell execution;
- path traversal;
- hidden instruction leakage;
- memory poisoning;
- dependency supply-chain risk;
- plugin abuse;
- excessive agency;
- unbounded cost or resource usage;
- network egress abuse;
- user approval spoofing;
- event log tampering.

Phase 1 does not solve every future threat, but it must establish the boundaries that future phases preserve.

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

## Phase 1 Policy Decisions

Every `ToolAction` receives one decision:

- `allow` — broker may execute;
- `deny` — broker must not execute;
- `needs_approval` — broker must pause and request user approval.

---

## Default Phase 1 Policy Matrix

| Action | Default decision | Notes |
|---|---:|---|
| Simple chat | allow | No tool execution |
| Read file inside workspace | allow | Text files only unless explicitly handled |
| List directory inside workspace | allow | Stable sorted output |
| Glob inside workspace | allow | Bounded results |
| Grep inside workspace | allow | Bounded results; text files only |
| Read outside workspace | deny | Prevent path traversal |
| Write file | deny | Future phase unless task explicitly adds it |
| Delete file | deny | Future phase |
| Shell command | needs_approval | Never auto-run in Phase 1 |
| Network request | deny | Future phase |
| Memory write | deny/defer | Only memory candidate review in Phase 1 |
| Plugin execution | deny | Future phase |
| Remote execution | deny | Future phase |

---

## Path Safety Requirements

All filesystem tools must:

1. resolve requested path to an absolute path;
2. resolve workspace root to an absolute path;
3. verify requested path is inside workspace root;
4. reject path traversal attempts;
5. reject symlink escapes unless explicitly allowed by future policy;
6. return structured errors instead of raw tracebacks.

---

## Shell Safety Requirements

Phase 1 shell behaviour:

- shell actions are proposed, logged, and policy-reviewed;
- policy returns `needs_approval`;
- command is not executed unless an explicit approval object exists;
- CLI MVP may stop at approval-required response;
- no silent background execution is allowed.

Future phases may add allowlists, sandboxing, timeout, environment restrictions, command previews, and kill controls.

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

If future tasks introduce secrets:

- never commit secrets;
- load from environment or OS secret store;
- redact values in logs;
- store only references, not secret values;
- tests must use fake secrets.

---

## Memory Governance Requirements

Phase 1 must not write long-term memory automatically.

It may produce memory candidates:

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

Future memory writes must include:

- provenance;
- confidence;
- sensitivity;
- retention;
- approval state;
- deletion support.

---

## Approval Requirements

Approval prompts must include:

- action ID;
- tool name;
- exact arguments;
- risk level;
- policy reasons;
- expected effect;
- whether action changes files, runs shell, uses network, or may cost money.

Approvals must be bound to action ID. A user approving one action must not approve a different action accidentally.

---

## Security Tests Required In Phase 1

Minimum tests:

- outside-workspace file read is denied;
- path traversal is denied;
- shell action requires approval;
- denied action is not executed;
- policy decision is logged;
- tool output failure is logged;
- event log does not contain raw secret-like test values;
- invalid tool name fails safely;
- action without policy decision cannot execute.

---

## Security Non-Deviation Rules

Builder agents must not:

- call `subprocess` outside the shell tool implementation;
- read files directly from runtime code as an agent action;
- add network libraries for Phase 1;
- add plugin execution in Phase 1;
- add memory writes in Phase 1;
- bypass approval for shell;
- suppress security events;
- hide failures behind vague messages.
