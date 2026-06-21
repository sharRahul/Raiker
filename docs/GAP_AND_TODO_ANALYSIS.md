# Gap & TODO Analysis

Date: 2026-06-21

This document is the canonical "what is still missing" summary produced by the documentation audit.
It replaces the older `REPOSITORY_REVIEW_AND_GAP_ANALYSIS.md`. It separates two kinds of gap:

1. **Missing docs** — code that exists but has no dedicated documentation.
2. **Missing code (TODO)** — behaviour the documentation specifies that is not implemented (or is
   intentionally disabled and awaiting an activation task).

The implementation control ledger is `docs/IMPLEMENTATION_STATUS.md`; this file only tracks gaps.

---

## 1. Missing documentation (code without a dedicated spec)

| Area | Code | State | Suggested doc |
|---|---|---|---|
| Subagent planning | `raiker/agents/subagents.py` | Stub: `SubagentPlan` always returns `can_spawn=False` (`phase4_subagents_disabled_until_parent_policy_and_budget_controls_exist`). Covered only indirectly by `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md`. | Add a short "current state" note to the multi-agent spec, or a dedicated `AGENTS_SPEC.md`. |
| Skill registry | `raiker/skills/__init__.py` | Metadata-only skill-candidate registry (Phase 9), disabled by default. No dedicated spec; only referenced from the self-improvement spec. | Document the skill-candidate lifecycle alongside `docs/SELF_IMPROVEMENT_MODEL.md`. |
| Agent Gateway | `raiker/gateway/agent_gateway.py` | Real metadata/contract surface, but documented only inside `docs/ARCHITECTURE.md` / `docs/RUNTIME_ORCHESTRATION_SPEC.md`. | Optional standalone `GATEWAY_SPEC.md` if the surface grows. |
| Approvals package | `raiker/approvals/` | Real `ApprovalInbox` (list/resolve) + readiness registry; covered by contracts/acceptance docs but no dedicated approvals spec. | Optional `APPROVALS_SPEC.md`. |

All other `raiker/` subsystems have at least one dedicated or clearly-mapped spec under `docs/`.

---

## 2. Missing code / TODO (documentation ahead of implementation)

These are **intentionally disabled** and correctly marked as such in the ledger. They are listed here
so the backlog is explicit. Each requires a named activation task with policy, storage, events,
approval, audit, and acceptance tests before it can be enabled.

| Feature | Spec | Current code reality | Status |
|---|---|---|---|
| Hook handler types `http` / `mcp_tool` / `prompt` / `agent` | `docs/HOOKS_SPEC.md` | `raiker/hooks/` implements only `builtin` + `command` handlers. | `specified_not_implemented` |
| Subagent spawning & multi-agent team execution | `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md` | Contracts/ledgers only; `raiker/agents/subagents.py` cannot spawn. | `phase_scheduled_disabled` |
| Plugin code execution | `docs/PLUGIN_SYSTEM_SPEC.md` | Manifest validation + install records only; no execution. | `phase_scheduled_disabled` |
| Graph/codemap runtime indexing | `docs/GRAPH_MEMORY_AND_CODEMAP_SPEC.md` | Indexer/project-graph modules exist (Phase 9 records) but runtime indexing flags are off. | `phase_scheduled_disabled` |
| Semantic/vector memory writes & embeddings | `docs/EIDETIC_MEMORY_AND_LEARNING_SPEC.md`, `docs/MEMORY_GOVERNANCE_RULES.md` | Status/governance/readiness only; no writes or embeddings. | `phase_scheduled_disabled` |
| External channel transports & notifications | `docs/CHANNELS_SPEC.md` | Connector registry + readiness only; transports inactive. | `phase_scheduled_disabled` |
| Remote/container/cloud execution | `docs/EXECUTION_ENVIRONMENTS_SPEC.md` | Profiles + readiness only; execution disabled. | `phase_scheduled_disabled` |
| Approval execution / approval relay runtime | `docs/CONTRACTS.md`, `docs/SECURITY_AND_POLICY.md` | Approval inbox + previews only; execution disabled. | `phase_scheduled_disabled` |
| Launchable Desktop / Web / Dashboard / Mobile / IDE apps and REST API | `docs/UI_UX_DESIGN_SPEC.md` | Session-model records and read-only contracts only; no launchable apps. | `specified_not_implemented` |
| Scheduled automations / hosted routines runtime | `docs/IMPLEMENTATION_STATUS.md` (Phase 5) | Metadata-only routine records; no execution. | `phase_scheduled_disabled` |

The full list of disabled runtime flags (all `False`) is enforced by
`scripts/validate_repo_truthfulness.py` and documented in `docs/IMPLEMENTATION_STATUS.md`.

---

## 3. Structural notes

- **Phase 8 does not exist.** Phase numbering jumps from Phase 7 to Phase 9; this is intentional and
  is now recorded in `docs/ARCHITECTURE.md` and `docs/IMPLEMENTATION_STATUS.md`.
- **Pre-existing lint/type debt (out of scope for this docs audit):** `ruff check .` and
  `mypy raiker apps tests` currently report errors on the development branch (notably in
  `raiker/tui/textual_app.py` and several tests) that predate this change. They are tracked here so
  they are not forgotten; the repo's documentation-truthfulness gate
  (`scripts/validate_repo_truthfulness.py`, `scripts/validate_phase_status.py`) and `pytest` pass.
