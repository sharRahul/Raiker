# 10 Agent Contracts

This file defines implementation contracts in language-neutral form. The implementation may use Python, TypeScript, Rust, or Go, but the fields must remain equivalent.

## PromptEnvelope Fields

Required:
- prompt_id: UUID.
- session_id: UUID or null.
- client.type: enum.
- client.identity: string.
- client.trust_level: enum.
- user_text: string.
- mode: enum.
- budget: object.
- permission_overrides: object.

Validation:
- user_text cannot exceed configured limit.
- untrusted client cannot request high-risk auto-approval.
- attachments must have type and trust.

## AgentEvent Fields

Required:
- event_id.
- timestamp.
- session_id.
- turn_id.
- actor.
- event_type.
- risk.
- summary.

Validation:
- timestamp must be ISO-8601.
- event_type must be known.
- high/critical event must include reason in summary.

## ToolDescriptor Fields

Required:
- name.
- description.
- risk_class.
- permissions_required.
- schema.
- supports_targets.

Validation:
- high/critical tools cannot default allow.
- plugin tools must include plugin_id.

## PolicyDecision Fields

Required:
- decision: allow, ask, deny.
- risk.
- reason.
- constraints.

Rule:
- deny cannot be overridden by model.
- ask requires user/admin approval event.

## MemoryRecord Fields

Required:
- memory_id.
- type.
- namespace.
- content.
- source_event_id.
- confidence.
- sensitivity.
- retention.
- trust_score.
- user_approved.

Rule:
- secret sensitivity cannot be embedded or sent remote.

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
