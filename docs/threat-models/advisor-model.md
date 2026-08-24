# Threat Model — Advisor Model Runtime (web-app task 2)

> Status marker: runtime_enablement_candidate — real executor, gate-derived
> provider policy, default-ask decision mode, metadata-only events.

Per-capability threat model required by
[`docs/architecture/RUNTIME_EXECUTORS_SPEC.md`](../architecture/RUNTIME_EXECUTORS_SPEC.md) before
`advisor_model_runtime` may join `REAL_EXECUTOR_CAPABILITIES`.

## What this capability is

A user running a **local** model can attach a single "advisor" model —
typically a hosted provider (ref: the Anthropic advisor-tool pattern) — that
the local model may consult mid-turn through a brokered tool,
`consult_advisor(question)`. The advisor's answer is returned to the local
model as **untrusted data, never instructions**. The owner picks the advisor
profile on the Models view (`PUT /api/model-advisor`, gate-manager only) and
the choice is persisted like the fallback sequence.

Two surfaces, one governance:

1. **Chat-path tool** (`raiker/runtime/advisor.py::AdvisorService`, brokered as
   `consult_advisor`): enforces, in order — the `advisor_model_runtime` gate
   (disabled ⇒ fail closed), the per-capability decision mode (**default
   `ask` ⇒ the consult is withheld**; `deny` ⇒ blocked; `auto` withholds too,
   because sending prompt content off-machine is never low-risk), a configured
   advisor profile (unset ⇒ fail closed), and finally the provider call through
   `ModelRouter.achat`, where the provider factory **re-checks** the
   hosted/private gate, the owner egress allowlist, and the API key exactly as
   for any chat turn.
2. **Governed-action executor**
   (`raiker/runtime/executors/models_runtime.py::AdvisorModelRuntimeExecutor`,
   operation `consult`): the activation anchor for the gate. Reached only
   through `route_action` (which applies the gate, decision mode, and approval
   flow); artifacts are **metadata only** — profile id, provider, model,
   question/answer lengths — never the question or answer text.

## Boundaries enforced (fail-closed)

| Control | Mechanism |
|---|---|
| Gate off ⇒ nothing runs | `advisor_model_runtime` state read from the persisted control plane; absent/disabled ⇒ `advisor_gate_disabled`. |
| Default `ask` withholds | Decision mode `ask` (the default) and `auto` return `advisor_withheld:*` without contacting any provider; only an explicit owner `allow` lets the consult run unprompted. |
| No advisor ⇒ no call | Unset/unknown/test-only advisor profile ⇒ `advisor_not_configured` / `advisor_profile_unknown` / `advisor_profile_not_allowed`. Placeholder-`<model>` profiles are rejected at set time (`model_required_for_profile`). |
| Provider policy re-checked | The consult goes through the provider factory: hosted/private gate state (`provider_runtime_policy_from_gates`), owner egress allowlist (`RAIKER_MODEL_EGRESS_ALLOWLIST`, empty ⇒ deny), and env-only API keys are enforced per construction — enabling the advisor gate alone opens nothing. |
| Bounded exchange | Question capped (8 000 chars), answer truncated (16 000 chars), single non-streamed call, no tools offered to the advisor. |
| Untrusted output | The answer is wrapped as an untrusted-data block before it reaches the local model; assistant/tool content is never instruction authority (existing runtime invariant). |
| No data leakage in audit | Broker events and stored tool actions for `consult_advisor` are scrubbed to metadata (`question_length`, answer length, profile/provider/model); executor artifacts are metadata-only. The advisor prompt/answer never enter event payloads. Credentials never leave owner env vars. |
| AI principals | Capability gate + `route_action` block non-human principals from enabling the gate; the setter (`PUT /api/model-advisor`) is human gate-manager only. |

## Activation requirements

Enabling `advisor_model_runtime` requires a HUMAN `runtime_gate_manager`, the
`local_single_user_runtime` mode, the registered executor, a
`threat_model_acks` row referencing this document, and a human confirmation
token. Because the advisor is typically hosted, a *working* consult
additionally requires the hosted (or private-network) egress path from
[`hosted-models.md`](hosted-models.md): that gate, the owner egress allowlist,
and the provider key — none of which this capability grants.

## Residual risks & non-goals

- A consult sends the local model's **question text** to the advisor provider —
  that content leaves the machine and is subject to the provider's data
  handling. The default-ask decision mode exists so this never happens without
  a standing owner decision; the egress allowlist bounds *where* it can go.
- A malicious or compromised advisor could return adversarial text. It is
  labelled untrusted data and cannot execute anything by itself; every action
  the local model proposes afterwards still flows through the broker, policy,
  and approvals.
- Out of scope: multiple advisors, advisor tool-use, streaming advisor
  answers, and letting the advisor see workspace context beyond the question
  it was asked.
