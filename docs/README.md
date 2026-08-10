# Raiker documentation

This is the entry point for Raiker's current product documentation. The core
references below describe how the runtime behaves today; specialist security,
executor, licensing, and threat-model documents remain available where they
define active constraints or verification requirements. Historical plans,
superseded guides, and screenshots are not maintained here.

## Start here

- [User guide](guide/README.md): task-shaped instructions for running the local
  dashboard — install, connect a model, permissions, Chat, tasks, MCP, and
  troubleshooting by reason code.
- [Architecture](ARCHITECTURE.md): components and governed action flow.
- [Security architecture](SECURITY_ARCHITECTURE.md): trust boundaries and
  fail-closed controls.
- [Commands](COMMANDS_AND_INTERACTIVE_MODE_SPEC.md): terminal command surface.
- [API and contracts](API_AND_CONTRACT_SCHEMAS.md): local web API and data shape.
- [Implementation status](IMPLEMENTATION_STATUS.md): what is available now.
- [User-centric zero-trust policy](USER_CENTRIC_ZERO_TRUST_POLICY.md): the
  owner policy that keeps safe work frictionless without weakening control.

## Reference

- [Build workspace](BUILD_WORKSPACE_SPEC.md): the coding surface, its Plan/Edit/Auto
  modes, repository references, and scheduled agents.
- [Visual design](VISUAL_DESIGN_SPEC.md): the type scale, density modes, empty
  and loading states, iconography, data-visual rules, and motion a new page is
  built from.
- [Desktop distribution](DESKTOP_DISTRIBUTION_DESIGN.md): installation, the
  background host, and the lifecycle around `raiker-app`.
- [Decision modes](DECISION_MODES_SPEC.md)
- [Models](MODEL_RUNTIME_AND_LOCAL_INFERENCE.md)
- [Tools and permissions](TOOLS_AND_PERMISSIONS_SPEC.md)
- [Tool and plugin catalog](RAIKER_TOOL_AND_PLUGIN_CATALOG.md)
- [Events](EVENT_CATALOG.md)
- [Memory governance](MEMORY_GOVERNANCE_RULES.md)
- [Runtime orchestration](RUNTIME_ORCHESTRATION_SPEC.md)
- [Runtime executors](RUNTIME_EXECUTORS_SPEC.md)
- [Security and policy](SECURITY_AND_POLICY.md)
- [OWASP GenAI mapping](OWASP_GENAI_SECURITY_MAPPING.md): the LLM Top 10 (2025)
  against documented and enforced controls.
- [OWASP Agentic mapping](OWASP_AGENTIC_TOP10_MAPPING.md): the Agentic Top 10
  (ASI01–ASI10, 2026), each row citing the code that proves it.
- [Security threat models](threat-models/)
- [Licensing policy](licensing/LICENSING_POLICY.md)
- [Verification](VERIFICATION_PLAN.md)
- [Local validation](LOCAL_VALIDATION_GATE.md)
- [Coverage and open gaps](FEATURE_COVERAGE_MATRIX.md)
- [Live manual test plan](plans/RAIKER_LIVE_MANUAL_TEST_PLAN.md): a repeatable
  end-to-end browser plan, with the last round's recorded results and evidence.
- [To be fixed](plans/TO_BE_FIXED.md): the defects still open, each with a
  reproduction, root cause, and proposed fix.
- [Fixed items](plans/FIXED_ITEMS.md): the same record for everything that has
  been closed, kept separate so the open list answers one question.
