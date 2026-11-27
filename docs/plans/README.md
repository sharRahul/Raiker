# Plans

Raiker's plans, consolidated on 2026-11-16. Each document owns one question;
where two used to overlap, one was merged into the other and the original file
removed (the merged section says where it came from).

| Document | Owns |
|---|---|
| [Approval redesign](APPROVAL_REDESIGN.md) | Shared authorization, sandbox autonomy, scoped approvals and owner decisions across every workflow |
| [Ready to use](READY_TO_USE_PLAN.md) | **The work that remains** before the owner uses Raiker every day on a Windows or Linux desktop: publishing, the native command sandbox, permissions, memory, the always-on host, Pause, interoperability ([ADR-0006](../adr/ADR-0006-one-supported-path-per-machine.md)) |
| [Beta release plan](BETA_RELEASE_PLAN.md) | Release gates and their evidence by area, the owner scope (Appendix A), the Linux qualification record (B), data-safety evidence (C) and the desktop package acceptance matrix (D) |
| [Testing](TESTING.md) | How Raiker is tested as a real owner uses it, including the [regular-use journeys](TESTING.md#regular-use-journeys) and their prompts |
| [Personal autonomous-agent architecture](PERSONAL_AUTONOMOUS_AGENT_SPEC.md) | Goals, the coordinator, execution profiles, and the personal-agent UI and UX |
| [Build workspace](BUILD_WORKSPACE_SPEC.md) · [Design workspace](DESIGN_WORKSPACE_SPEC.md) · [Voice conversation](VOICE_CONVERSATION_SPEC.md) | Requirements for each work surface |
| [Quiet UI](QUIET_UI_PLAN.md) | The interface redesign: layout, Home and Chat, the Raiker Browser proposal, quick fixes, brand |
| [Open defects](TO_BE_FIXED.md) · [Fixed items](FIXED_ITEMS.md) | The defect ledgers |

Removed by consolidation on 2026-11-16: `PERSONAL_BETA_SCOPE.md`,
`LINUX_BETA_2026_11_09.md`, `DATA_SAFETY_EVIDENCE.md` and
`RELEASE_ACCEPTANCE_MATRIX.md` (into the beta release plan);
`ACCEPTANCE_TESTS_BY_PHASE.md` (into Testing); `PERSONAL_AGENT_UX_SPEC.md` (into
the personal-agent architecture); the six `quiet-ui/` files (into Quiet UI); and,
in `docs/architecture/`, `BUILD_ORDER.md`, `WEB_UI_CONTROL_DECK_PLAN.md` and
`REFERENCE_REQUIREMENTS_MATRIX.md` (into [Design history](../architecture/DESIGN_HISTORY.md)).
