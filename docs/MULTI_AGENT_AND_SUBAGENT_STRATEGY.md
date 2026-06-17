# Multi-Agent And Subagent Strategy

Raiker supports subagents and coordinated multi-agent teams through phase-scheduled implementation. The design is fully specified now; phase numbers control when behaviour is wired, not whether behaviour is defined.

Subagents are useful for specialised work, but they increase risk, cost, complexity, and drift. They must be bounded by contracts, permissions, event logs, and explicit task ownership.

---

## Goals

Raiker subagents must support specialised roles, bounded delegation, independent context bundles, tool restrictions, progress reporting, side-question support, verification of subagent output, recursion limits, parent runtime oversight, memory governance, and event logging.

---

## Subagent Profile Schema

```json
{
  "schema_version": "1.0",
  "agent_id": "security-reviewer",
  "name": "Security Reviewer",
  "description": "Reviews changes for security risk.",
  "role": "security_review",
  "build_phase": "phase_4",
  "model_profile": "local-reviewer",
  "allowed_tools": ["read_file", "grep", "graph_query"],
  "denied_tools": ["shell", "write_file", "delete_file"],
  "memory_scope": "project_read_only",
  "max_runtime_seconds": 600,
  "max_tool_calls": 25,
  "can_spawn_subagents": false,
  "can_ask_user": true,
  "can_ask_side_questions": true,
  "output_schema": "SubagentReport"
}
```

---

## Subagent Task Contract

```json
{
  "schema_version": "1.0",
  "subagent_task_id": "subtask_01H...",
  "parent_task_id": "task_01H...",
  "agent_id": "security-reviewer",
  "objective": "Review docs for security gaps.",
  "context_scope": {
    "allowed_files": ["docs/**"],
    "allowed_memory": ["project_memory"],
    "redactions": []
  },
  "constraints": [
    "Do not write files.",
    "Do not run local commands."
  ],
  "expected_output": "Findings with severity and suggested fixes."
}
```

---

## Subagent Lifecycle

```text
parent proposes subagent
  -> policy review
  -> subagent_start event
  -> child context bundle created
  -> child runtime executes bounded task
  -> subagent_report produced
  -> parent verifies report
  -> memory candidates extracted if permitted
  -> subagent_stop event
```

---

## Agent Team Modes

| Mode | Build phase | Behaviour |
|---|---:|---|
| `single_specialist` | Phase 4 | One subagent handles one subtask. |
| `parallel_reviewers` | Phase 4 | Multiple read-only reviewers compare findings. |
| `planner_executor` | Phase 4 | Planner delegates implementation to executor. |
| `critic_refiner` | Phase 4 | Critic reviews and refiner fixes. |
| `red_blue_team` | Phase 4 | Attacker/defender security review. |
| `manager_planner_executor` | Phase 4 | Manager tracks objective, planner decomposes, executor acts. |
| `memory_intelligence_team` | Phase 5 | Memory specialist, graph specialist, and skill specialist refine retrieval and learning. |
| `swarm` | Phase 5 | Many bounded agents collaborate with strict budget, depth, and tool limits. |

Phase 1 does not wire autonomous teams, but contracts and event shapes are preserved so Phase 4/5 teams can be added without redesign.

---

## Delegation Rules

Subagents must not exceed allowed tools, access broader context than delegated, write durable memory directly, spawn other agents unless explicitly allowed, continue after parent cancellation, bypass parent policy, approve their own risky actions, or hide tool results from parent.

---

## Subagent Output Schema

```json
{
  "schema_version": "1.0",
  "subagent_task_id": "subtask_01H...",
  "status": "completed",
  "summary": "No critical issues found.",
  "findings": [
    {
      "severity": "medium",
      "title": "Missing timeout on hook command",
      "evidence": "HOOKS_SPEC requires timeout but implementation missing.",
      "recommendation": "Add timeout enforcement."
    }
  ],
  "tool_calls_used": 5,
  "memory_candidates": [],
  "skill_candidates": []
}
```

---

## Side Questions To Subagents

The Rich TUI may ask a subagent what it is doing, why it flagged something, what evidence supports it, what files it inspected, what confidence it has, and what it needs from the parent.

Subagent side answers are read-only unless parent escalates.

---

## Hermes-Style Delegation And Learning

Raiker must support parallel workstreams and learning loops:

```text
parent task
  -> spawn bounded specialist subagents
  -> collect reports
  -> verify result
  -> create memory/skill candidates
  -> require approval before durable memory or skill update
```

Subagent trajectories can become skill candidates only after verification and approval.

---

## Events

Required events:

- `subagent_proposed`
- `subagent_policy_decision`
- `subagent_started`
- `subagent_context_created`
- `subagent_progress`
- `subagent_tool_proposed`
- `subagent_report_created`
- `subagent_completed`
- `subagent_failed`
- `subagent_cancelled`
- `subagent_side_question_received`
- `subagent_side_question_answered`
- `agent_team_started`
- `agent_team_completed`
- `skill_candidate_created_from_subagent`

---

## Security Requirements

- Subagent output is untrusted until parent verifies it.
- Subagents cannot approve their own tool calls.
- Subagent memory writes become candidates only.
- Parent task cancellation cascades to children.
- Subagent context must be least-privilege.
- Multi-agent teams require budget and recursion limits.
- Skill learning from subagent output requires verification and approval.

---

## Testing Requirements

Tests must prove:

- subagent receives limited context;
- denied tool cannot be used;
- subagent output is validated;
- parent cancellation cancels subagent;
- subagent cannot spawn child unless allowed;
- side question does not mutate subagent task;
- subagent report links to event log;
- parallel reviewers cannot write files when read-only;
- skill candidate requires verified parent task.
