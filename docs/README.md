# Raiker documentation

Raiker's documentation is organized by audience and purpose. Start with the
user guide unless you are implementing, reviewing, or auditing the runtime.

## Use Raiker

The **[user guide](guide/README.md)** explains installation, model setup,
permissions, Chat, Build, tasks, extensions, host management, security,
limitations, and troubleshooting. These pages are also served inside Raiker
under **Utilities → Guide**.

Useful starting points:

- [Getting started](guide/getting-started.md)
- [Connecting a model](guide/connecting-a-model.md)
- [Working in Chat](guide/working-in-chat.md)
- [Working in Build](guide/working-in-build.md)
- [Known limits](guide/known-limits.md)
- [Troubleshooting](guide/troubleshooting.md)

## Understand or develop Raiker

The **[architecture and implementation index](architecture/README.md)** covers
components, contracts, governance, storage, models, extensions, security,
verification, current implementation status, and historical design records.

Canonical technical references:

| Question | Document |
|---|---|
| How does a governed action flow? | [Architecture](architecture/ARCHITECTURE.md) |
| What is implemented now? | [Implementation status](architecture/IMPLEMENTATION_STATUS.md) |
| What are the trust boundaries? | [Security architecture](architecture/SECURITY_ARCHITECTURE.md) |
| What can this build not do? | [Known limits](architecture/KNOWN_LIMITS.md) |
| What does the local API expose? | [API and contracts](architecture/API_AND_CONTRACT_SCHEMAS.md) |
| How is Raiker verified? | [Verification plan](architecture/VERIFICATION_PLAN.md) |

## Security reviews

- [Threat-model index](threat-models/README.md) — per-capability threats,
  mitigations, and residual risks.
- [Security architecture](architecture/SECURITY_ARCHITECTURE.md) — trust
  boundaries and fail-closed behavior.
- [Security and policy](architecture/SECURITY_AND_POLICY.md) — security
  philosophy and operational rules.
- [OWASP GenAI mapping](architecture/OWASP_GENAI_SECURITY_MAPPING.md) and
  [OWASP Agentic mapping](architecture/OWASP_AGENTIC_TOP10_MAPPING.md) — control
  coverage tied to the implementation.

## Plans, evidence, and history

- [Open defects](plans/TO_BE_FIXED.md) and [fixed items](plans/FIXED_ITEMS.md)
- [Proposed additions](plans/TO_BE_ADDED.md)
- [Live manual test plan](plans/RAIKER_LIVE_MANUAL_TEST_PLAN.md) and
  [test-round record](plans/LIVE_TEST_ROUNDS.md)
- [Screenshot evidence](plans/screenshots/README.md)
- [Licensing policy](licensing/LICENSING_POLICY.md) and
  [relicensing audit](licensing/APACHE_2_RELICENSING_AUDIT.md)

Plans and screenshots are dated evidence. They do not override the canonical
implementation-status, architecture, security, or known-limits documents.
