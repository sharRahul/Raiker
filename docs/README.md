# Raiker documentation

Raiker's documentation is organized by audience and purpose. Start with the
user guide unless you are implementing, reviewing, or auditing the runtime.

**Product identity:** Raiker serves an individual owner as a local-first,
personalised, all-purpose AI agent. It brings Chat, research, coding, memory,
tasks, automation and approved tools into one personal experience, helping the
owner carry an outcome from idea through verified delivery. Its reach is broad,
but never unlimited: it acts only through the models, services, permissions and
approvals that are actually available. Goal-level autonomy is being delivered in
stages; see [implementation status](architecture/IMPLEMENTATION_STATUS.md)
before claiming that a proposed workflow has shipped.

## Use Raiker

The **[user guide](guide/README.md)** explains installation, model setup,
permissions, Chat, Build, tasks, extensions, host management, security,
limitations, and troubleshooting. These pages are also served inside Raiker
under **Utilities → Guide**.

Raiker's personal autonomous-agent direction brings these workflows together
around durable goals and useful verified outcomes. Start with the
[current personal-agent workflow](guide/tasks-and-projects.md#using-raiker-as-a-personal-agent),
then the [target architecture](plans/PERSONAL_AUTONOMOUS_AGENT_SPEC.md)
and [staged delivery plan](plans/PERSONAL_AUTONOMOUS_AGENT_SPEC.md).

Useful starting points:

- [Getting started](guide/getting-started.md)
- [Connecting a model](guide/connecting-a-model.md)
- [Working in Chat](guide/working-in-chat.md)
- [Working in Build](guide/working-in-build.md)
- [Troubleshooting](guide/troubleshooting.md)

## Understand or develop Raiker

The **[architecture and implementation index](architecture/README.md)** covers
components, contracts, governance, storage, models, extensions, security,
verification, current implementation status, and historical design records.

Canonical technical references:

| Question | Document |
|---|---|
| How should personal-agent UI/UX be implemented? | [UX specification](plans/PERSONAL_AUTONOMOUS_AGENT_SPEC.md#personal-agent-ui-and-ux) and [task decisions](plans/PERSONAL_AUTONOMOUS_AGENT_SPEC.md) |
| How are standing permissions, action approvals and work-page details presented? | [Current UI record](architecture/PERMISSIONS_UI_REFINEMENT.md) and [Permissions guide](guide/permissions-and-runtime-modes.md) |
| What is the Quiet UI redesign for laptop and desktop? | [Quiet UI redesign plan](plans/QUIET_UI_PLAN.md) |
| What makes Raiker ready to use on any machine? | [Ready-to-use plan](plans/READY_TO_USE_PLAN.md) and [ADR-0006](adr/ADR-0006-one-supported-path-per-machine.md) |
| What stands between Raiker and its first beta? | [First beta release plan](plans/BETA_RELEASE_PLAN.md) and the [beta guide](guide/beta.md) |
| How will Raiker hold a spoken conversation on-device? | [Native voice conversation](plans/VOICE_CONVERSATION_SPEC.md) |
| How should the personal agent coordinate goals, context and proactive work? | [Personal-agent architecture](plans/PERSONAL_AUTONOMOUS_AGENT_SPEC.md) |
| How does a governed action flow? | [Architecture](architecture/ARCHITECTURE.md) |
| What is implemented now? | [Implementation status](architecture/IMPLEMENTATION_STATUS.md) |
| What are the trust boundaries? | [Security architecture](architecture/SECURITY_ARCHITECTURE.md) |
| What does the local API expose? | [API and contracts](architecture/API_AND_CONTRACT_SCHEMAS.md) |
| How is Raiker verified? | [Verification plan](architecture/VERIFICATION_PLAN.md) |

## Security reviews

- [Threat-model index](threat-models/README.md) — per-capability threats,
  mitigations, and residual risks.
- [Security architecture](architecture/SECURITY_ARCHITECTURE.md) — trust
  boundaries and fail-closed behavior.
- [Security and policy](architecture/SECURITY_AND_POLICY.md) — security
  philosophy and operational rules.
- [RAIKER.md instructions](architecture/RAIKER_MD_INSTRUCTIONS.md) — reviewed
  global and project-root instruction files for Build: discovery, review,
  limits and what they can never grant.
- [Remote access](architecture/REMOTE_ACCESS.md) — how another device reaches
  Raiker: the remote listener, mandatory two-step sign-in, sessions, and the
  configuration lifecycle.
- [Model destination authorization](adr/ADR-0004-connection-bound-model-authorization.md)
  — why a saved model connection, not an environment allowlist, decides where a
  model request may go.
- [Composer personas narrow a turn](adr/ADR-0005-composer-personas.md) — a
  persona can only narrow what a turn may do.
- [One supported path per machine](adr/ADR-0006-one-supported-path-per-machine.md)
  — the native command sandbox on each desktop (no WSL2 needed on Windows),
  postures, Health, an always-on host, Pause and published releases.
- [OWASP GenAI mapping](architecture/OWASP_GENAI_SECURITY_MAPPING.md) and
  [OWASP Agentic mapping](architecture/OWASP_AGENTIC_TOP10_MAPPING.md) — control
  coverage tied to the implementation.

## Plans, evidence, and history

- **[Plans index](plans/README.md)** — what each plan owns after the
  2026-11-16 consolidation.
- [Ready to use](plans/READY_TO_USE_PLAN.md) — the remaining work before daily
  use, and [Testing](plans/TESTING.md) — how it is tested with real prompts.
- [Open defects](plans/TO_BE_FIXED.md) and [fixed items](plans/FIXED_ITEMS.md)
- [Live test record](architecture/WEB_APP_LIVE_TEST.md) — every live round's
  scenarios, results and captures.
- [Design history](architecture/DESIGN_HISTORY.md) — superseded design plans.
- [Licensing policy](licensing/LICENSING_POLICY.md) and
  [relicensing audit](licensing/APACHE_2_RELICENSING_AUDIT.md)

Plans and screenshots are dated evidence. They do not override the canonical
implementation-status, architecture, security, or known-limits documents.
