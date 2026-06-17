# Local Sovereign Agent v3 — Maximum Detail Blueprint

This package is a detailed build blueprint for a standalone, local-first AI agent platform. The content is designed to be precise enough for a smaller local model, such as a 9B class coding model running on a 16GB GPU, or a free hosted model, to follow without drifting away from the intended design.

## What This Package Contains

```text
README.md
01_PRD.md
02_SPEC.md
03_ARCHITECTURE.md
04_ROADMAP.md
05_MASTER_BUILD_PROMPT.md
06_SECURITY_MODEL.md
07_PROMPT_FILES.md
08_ACCEPTANCE_TESTS.md
09_IMPLEMENTATION_PLAN.md
10_AGENT_CONTRACTS.md
11_DIRECTORY_STRUCTURE.md
12_ADR_TEMPLATE.md
nested_layered_architecture.png
nested_layered_architecture.svg
nested_layered_architecture_mermaid.mmd
component_interaction_mermaid.mmd
agent_loop_mermaid.mmd
deployment_mermaid.mmd
```

## Core Product Idea

Local Sovereign Agent is a local-first AI agent daemon with equal-status clients. The user can interact through CLI, Chat, Rich TUI, Desktop, Web, IDE, Voice, Hotkeys, REST, or Webhooks. Every client talks to the same gateway. The gateway normalises all inputs into a shared PromptEnvelope. The agent runtime executes a controlled loop: gather context, plan, policy review, act, verify, checkpoint, log, and memory governance.

## Diagram Style

The main diagram follows a nested boundary style:

1. **Interface layer** at the top.
2. **Event logging boundary** as an OS-like observability shell.
3. **Security and privacy boundary** for OWASP GenAI and LLM risk controls.
4. **Agent core boundary** containing the loop, tool broker, hooks, memory, model router, and execution adapters.
5. **Storage and external execution surfaces** as governed capabilities.

## How to Use This Package with Claude Code or a Local Coding Agent

Use this exact instruction first:

```text
Read every file in local_sovereign_agent_v3_max_detail. Start with 05_MASTER_BUILD_PROMPT.md. Follow 09_IMPLEMENTATION_PLAN.md task-by-task. Do not skip phases. Do not invent components. If anything is unclear, ask a question or create an ADR using 12_ADR_TEMPLATE.md. Implement Phase 1 only unless explicitly told otherwise.
```

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
