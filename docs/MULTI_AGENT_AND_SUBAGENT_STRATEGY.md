# Multi-Agent And Subagent Strategy

Raiker supports subagents and, in later phases, coordinated multi-agent teams.

Subagents are useful for specialised work, but they increase risk, cost, complexity, and drift. They must be bounded by contracts, permissions, event logs, and explicit task ownership.

---

## Goals

Raiker subagents must support:

1. specialised roles;
2. bounded delegation;
3. independent context bundles;
4. tool restrictions;
5. progress reporting;
6. side-question support;
7. verification of subagent output;
8. no uncontrolled recursion;
9. parent runtime oversight;
10. event logging.

---

## Subagent Profile Schema

```json
{
  "schema_version": "1.0",
  "agent_id": "security-reviewer",
  "name": "Security Reviewer",
  "description": "Reviews changes for security risk.",
  "role": "security_review",
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
    "Do not run shell."
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
  -> subagent_stop event
```

---

## Agent Team Modes

Future phases may support teams:

| Mode | Behaviour |
|---|---|
| `single_specialist` | One subagent handles one subtask. |
| `parallel_reviewers` | Multiple read-only reviewers compare findings. |
| `planner_executor` | Planner delegates implementation to executor. |
| `red_blue_team` | Attacker/defender security review. |
| `critic_refiner` | Critic reviews and refiner fixes. |
| `swarm` | Many agents collaborate; future only and high risk. |

Phase 1 must not implement autonomous teams.

---

## Delegation Rules

Subagents must not:

- exceed allowed tools;
- access broader context than delegated;
- write durable memory directly;
- spawn other agents unless explicitly allowed;
- continue after parent cancellation;
- bypass parent policy;
- approve their own risky actions;
- hide tool results from parent.

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
  "memory_candidates": []
}
```

---

## Side Questions To Subagents

The Rich TUI may ask a subagent:

- what are you doing?;
- why did you flag this?;
- what evidence supports this?;
- what files did you inspect?;
- what is your confidence?

Subagent side answers are read-only unless parent escalates.

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

---

## Security Requirements

- Subagent output is untrusted until parent verifies it.
- Subagents cannot approve their own tool calls.
- Subagent memory writes become candidates only.
- Parent task cancellation cascades to children.
- Subagent context must be least-privilege.
- Multi-agent teams require budget and recursion limits.

---

## Testing Requirements

Tests must prove:

- subagent receives limited context;
- denied tool cannot be used;
- subagent output is validated;
- parent cancellation cancels subagent;
- subagent cannot spawn child unless allowed;
- side question does not mutate subagent task;
- subagent report links to event log.
