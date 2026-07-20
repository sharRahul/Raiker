# Threat Model — Subagents & Multi-Agent Teams (Phase 4, slice 1)

> Status marker: runtime_enablement_candidate — strict non-allow blocking,
> role revoke governed, capability gate per action. The capabilities are now
> integrated and governed/default-ask; they were historically disabled/deferred
> before their executors landed. Approval resolution is metadata-only.

This is the per-capability threat model required by
[`docs/RUNTIME_EXECUTORS_SPEC.md`](../RUNTIME_EXECUTORS_SPEC.md) before the
`subagents` and `multi_agent_teams` capabilities may join
`REAL_EXECUTOR_CAPABILITIES`.

## What the executor does

- `subagents` (`raiker/runtime/executors/orchestration.py::SubagentExecutor`)
  runs a **bounded, in-process** subagent: a fixed, caller-supplied list of
  read-only tool steps, each routed through the same
  `ToolBroker → PolicyEngine` path as any other action.
- `multi_agent_teams` (`MultiAgentTeamExecutor`) runs up to
  `MAX_TEAM_MEMBERS` (5) such subagents in sequence and aggregates their
  metadata-only outcomes.

This is **bounded delegated execution, not autonomous model-driven recursion**.
Subagents do not call the model, do not spawn OS processes, do not open the
network, and cannot widen the parent's authority.

## Boundaries enforced (fail-closed)

| Control | Mechanism |
|---|---|
| Read-only only | Steps restricted to `DELEGABLE_TOOLS` (read/inspection tools); any other tool fails closed with `subagent_tool_not_allowed`. |
| Per-step governance | Every step goes through `ToolBroker`/`PolicyEngine`; a `deny`/`needs_approval` step stops the subagent (`subagent_step_blocked`). |
| Depth bound | `depth < min(max_depth, MAX_SUBAGENT_DEPTH=3)`; else `subagent_depth_exceeded`. |
| Step budget | `len(steps) ≤ min(max_steps, MAX_SUBAGENT_STEPS=25)`; else `subagent_step_budget_exceeded`. |
| Tool-call budget (C1) | Checked before each dispatch against `min(max_tool_calls, MAX_SUBAGENT_TOOL_CALLS=25)`; else `subagent_tool_call_budget_exceeded` (fails closed before the over-budget call runs). |
| Token budget (C1) | Running deterministic ~4-char/token estimate per step against `min(max_tokens, MAX_SUBAGENT_TOKENS=200000)`; else `subagent_token_budget_exceeded`. |
| Time budget | Wall-clock guard per step; else `subagent_time_budget_exceeded`. |
| Budget record (C1) | The four-dimension per-spawn budget (`SubagentBudget`) is clamped down to the hard caps (`effective()` — callers may only shrink) and persisted on the contract (`max_steps`/`max_tool_calls`/`max_tokens`), so a bounded run's enforced envelope is auditable after the fact. |
| Team size | `≤ MAX_TEAM_MEMBERS=5`; else `team_member_budget_exceeded`. |
| AI principals | Capability gate + `route_action` block non-human principals from running or enabling the gate. |
| No fabricated success | Any breach returns `ok=False` with a reason code; never a fake "completed". |

## Activation requirements

Default gate state is **DISABLED**. Enabling requires (per
`raiker/runtime/authority/activation.py`): a HUMAN `runtime_gate_manager`,
the `local_single_user_runtime` mode active, a registered real executor, a
`threat_model_acks` row referencing this document, and a human confirmation
token. AI principals can never flip the gate.

## Residual risks & non-goals

- Step **arguments** are caller-supplied; path-bearing tools remain
  workspace-boundary-checked by the existing policy engine.
- Event payloads carry **metadata only** (counts, tool names, statuses) — never
  file contents, raw tool output, secrets, prompts, or reasoning.
- Out of scope for this slice: autonomous model-driven subagents, mutating
  delegated tools, cross-machine/remote spawning, and external-channel fan-out.
  Those remain gated and fail closed.
