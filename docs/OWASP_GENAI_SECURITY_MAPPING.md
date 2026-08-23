# OWASP GenAI Security Mapping

## Machine identity control

Per-turn signed machine identity reduces excessive agency and confused-deputy
risk: model output cannot borrow the human principal, replace owner credential
scope, or reach policy and tools without a context-bound attestation. The
machine actor and human authorizer remain distinct in approval and audit views.
This complements, rather than replaces, prompt-injection handling, least
privilege, output validation, approvals, and sandboxing.

Raiker must map its controls to OWASP LLM and GenAI security risks. This document converts agent security into concrete Raiker requirements.

**Source.** The list mapped here is the
[OWASP Top 10 for Large Language Model Applications (2025)](https://genai.owasp.org/llm-top-10/),
published by the [OWASP GenAI Security Project](https://genai.owasp.org/). The
agentic companion — the ASI taxonomy — is mapped separately in
[`OWASP_AGENTIC_TOP10_MAPPING.md`](OWASP_AGENTIC_TOP10_MAPPING.md); the two lists
are different taxonomies and neither subsumes the other.

**This is a self-assessment, not a certification or third-party audit.**

---

## Security Objectives

Raiker must prevent or mitigate:

1. prompt injection;
2. sensitive data disclosure;
3. supply-chain compromise;
4. data/model/memory poisoning;
5. improper output handling;
6. excessive agency;
7. system prompt leakage;
8. vector/embedding weaknesses;
9. misinformation and unsafe reliance;
10. unbounded consumption;
11. insecure plugin/channel/tool behaviour;
12. approval spoofing and audit tampering.

---

## Control Mapping

| Risk class | Raiker controls |
|---|---|
| Prompt injection | Separate trusted/untrusted context, source provenance, prompt injection labels, tool policy boundary, model output validation. |
| Indirect prompt injection | File/web/channel content marked untrusted, no instruction authority from retrieved content, source trust scores. |
| Sensitive data disclosure | Redaction, egress policy, local-only model profiles, secret scanning hooks, approval for export. |
| Supply-chain risk | Plugin manifest, trust levels, checksums/signatures, permission diff, dependency approval. |
| Data/model/memory poisoning | Memory provenance, confidence, approval, correction/forgetting, stale/contradiction detection. |
| Improper output handling | Structured output validation, schema rejection, safe rendering, command injection prevention. |
| Excessive agency | Tool broker, max tool calls, approval gates, task bounds, no unmanaged recursion. |
| System prompt leakage | Separate system/security policy, redaction, no direct prompt export by default. |
| Vector/embedding weaknesses | Semantic memory provenance, sensitivity filters, poisoning tests, graph corroboration. |
| Misinformation | Verification, citations/provenance, confidence labels, human review gates. |
| Unbounded consumption | Budgets, timeouts, max tokens, max tool calls, rate limits, cancellation. |
| Channel abuse | Pairing, sender allowlists, attachment scanning, rate limits, approval relay controls. |
| Plugin abuse | Disabled by default, manifest validation, scoped permissions, managed policy override. |
| Hook abuse | Decision authority rules, timeouts, scope priority, audit logs. |
| Audit tampering | Append-only event logs, Phase 5 event-log integrity checks, checkpoint/event linkage. |
| Eidetic observation abuse | Retention limits, provenance, exact-replay policy, deletion support, sensitivity controls. |

---

## OWASP LLM Top 10 (2025) — Documented vs Implemented

This table tracks each OWASP LLM Top-10 (2025) risk against what is **documented** and what is
**actually enforced in code today**. Honesty here is a security control in itself: a documented
mitigation is not a real one. Status: ✅ implemented · 🟡 partial · 🔒 disabled-by-default · 📘 doc only.

Every row cites the file that proves its rating. A row without a citation is a
claim, and this table does not make claims.

| ID | Risk | Doc | Code | What is enforced today, and what is not |
|---|---|---|---|---|
| LLM01 | Prompt injection | yes | ✅ | Structural, not prompt-level: external content is framed as untrusted data and never as instruction (`raiker/runtime/web_access.py`, `raiker/runtime/retrieval.py`, `raiker/runtime/attachments.py`), each context item carries source and trust (`raiker/context/models.py`), and hijacked intent still has to cross a deny-by-default tool gate (`raiker/policy/engine.py`). The scanning hook this document requires now exists as an **advisory** signal: `raiker/security/injection_scan.py` raises a redacted finding naming the exact page or document, and never blocks — the refusal path stays the gate. |
| LLM02 | Sensitive information disclosure | yes | ✅ | One redaction pass covers the API surface and the event log by *shape*, not keyword (`raiker/api/redaction.py`, `raiker/context/redaction.py`); egress answers per-capability rules — an owner blocklist plus a non-optional public-address guard for `web_fetch` (`RAIKER_WEB_EGRESS_BLACKLIST`, `raiker/runtime/web_policy.py`), and an allowlist for connectors and pushes (`RAIKER_CONNECTOR_EGRESS_ALLOWLIST`, empty ⇒ fail closed); local-only profiles refuse hosted routing (`raiker/models/endpoint_policy.py`). Remaining gap: no classifier ranks *content* sensitivity before model egress — the boundary is the allowlist, not the payload. |
| LLM03 | Supply chain | yes | 🟡 | Manifest validation, permission diff and checksums are real, and both HMAC and Ed25519 signature verification are implemented (`raiker/plugins/verify.py`). The default install has no owner key, so a signature is verified as **present-only** rather than authentic — which is now a first-class, owner-visible property of every plugin rather than a silent default (FIXED-166). A trusted-publisher allowlist is still absent. |
| LLM04 | Data & model poisoning | yes | 🔒 | The governed memory lifecycle is real — proposal, provenance, confidence, contradiction review and forgetting (`raiker/memory/`) — and credential-shaped text is refused before the owner is asked (`raiker/memory/policy.py`). The `memory_write` / `memory_forget` gates ship **off**, so this is disabled-by-default rather than unimplemented. |
| LLM05 | Improper output handling | yes | ✅ | Model tool calls are schema-validated at the boundary (`raiker/models/tool_call_validation.py`); unknown tools and missing arguments are rejected (`model_tool_call_rejected`) before execution. |
| LLM06 | Excessive agency | yes | ✅ | Broker plus approvals plus the per-turn max-tool-calls fail-safe (`PromptOptions.max_tool_calls`, enforced in `raiker/runtime/orchestrator.py`; the default `DEFAULT_MAX_TOOL_CALLS = 10000` is deliberately effectively unbounded, so a turn ends when the model finishes or the provider's context budget does). Subagents cannot widen the parent's authority (`raiker/agents/orchestration.py`), and their results are now identity-bound to the spawn that produced them (`raiker/agents/delegation.py`). |
| LLM07 | System prompt leakage | yes | ✅ | The system prompt is a separate message role assembled in the orchestrator (`raiker/runtime/orchestrator.py`, `_SYSTEM_PROMPT`), never part of user-visible context, and no route exports it. |
| LLM08 | Vector & embedding weaknesses | yes | 🔒 | Semantic writes answer a sensitivity policy before anything is embedded (`raiker/memory/policy.py`, `semantic_write_policy_decision`), and retrieval carries provenance (`raiker/runtime/source_provenance.py`). The capability ships off, so this is disabled-by-default. |
| LLM09 | Misinformation | yes | ✅ | The verifier is real and deterministic (`raiker/verification/verifier.py`; `raiker/runtime/verifier.py` is now only a re-export), and answers carry citations resolved to the passage used (`raiker/runtime/turn_sources.py`). |
| LLM10 | Unbounded consumption | yes | ✅ | Budgets plus, since FIXED-163, a real circuit breaker: consecutive failures per tool and per provider are counted in durable state, a threshold contains the subject with a stated reason, and a half-open probe closes it again (`raiker/security/containment.py`). API rate limiting is enforced separately (`raiker/api/security.py`). |

**Implemented strengths today:** workspace path-safety (symlink/traversal rejection), policy-gated
tool execution with approvals, an append-only hash-chained event log, per-turn signed machine
identity, capability-agnostic anomaly detection and containment, and disabled-by-default for
high-risk capabilities. **The remaining gaps are named in the rows above** — a content sensitivity
classifier before egress (LLM02) and a trusted-publisher allowlist (LLM03) — rather than left to be
inferred from a status glyph.

---

## Prompt Injection Requirements

Raiker must label every context source by trust level, never treat retrieved content as system instruction, block external content from granting permissions, preserve source provenance in context bundles, support prompt-injection scanning hooks, and verify model tool calls against policy.

The scanning hook is `raiker/security/injection_scan.py`. It is **detection and
provenance, not prevention**: deterministic, explainable rules run over each
untrusted context item as it enters the turn, and a hit raises a redacted
`security_findings` row attributed to the source document or URL. It never
refuses a turn — the refusal path is the tool gate — and it deliberately uses no
probabilistic model-based filtering, because a classifier that is right most of
the time would turn an advisory signal into a false assurance.

---

## Sensitive Data Requirements

Raiker must classify sensitivity before model egress, prefer local models for sensitive data, reject hosted provider use when local-only policy is active, redact secrets from logs, avoid storing secrets in memory, and require approval for memory export, graph export, artifact export, or exact raw-observation replay.

---

## Supply Chain Requirements

Raiker must validate plugin manifests, show permission diffs, reject untrusted plugin auto-enable, pin or review dependencies, record plugin provenance, support managed-trusted plugins, and log plugin install/update/enable events.

---

## Excessive Agency Requirements

Raiker must enforce max tool calls per turn, max task duration, max subagent depth, task contracts for background work, approval for command/network/write/delete/export, cancellation and pause controls, and no self-granted permissions.

---

## Memory Poisoning Requirements

Raiker must create memory candidates before durable writes, require provenance, assign confidence, detect contradictions, isolate channel/web-derived memories, allow user correction/deletion, test poisoned memory cases, prevent memory from overriding policy, and apply retention/deletion to eidetic observations.

---

## Channel Security Requirements

Channels must protect against spoofed sender, replayed approval, malicious attachment, session cross-talk, prompt injection through forwarded messages, connector compromise, and data leakage in replies.

Controls:

- pairing;
- sender allowlist;
- session binding;
- approval binding;
- attachment scanning;
- rate limiting;
- event logging.

---

## Security Test Matrix

| Test | Required outcome |
|---|---|
| File contains instruction to bypass policy | Treated as untrusted content; policy not changed. |
| Memory says local commands are allowed | Ignored unless policy allows command execution. |
| Plugin requests broad command access | Permission diff shown; disabled until approved. |
| Channel sends approval replay | Rejected. |
| Model emits malformed tool JSON | Rejected or retried safely. |
| Local command tries destructive action | Denied or high-risk approval. |
| Hosted model selected with local-only data | Denied. |
| Hook silently allows denied action | Denied by policy priority. |
| Long-running task exceeds limit | Cancelled or paused with event. |
| Secret-like text in tool output | Redacted from event logs. |
| Exact eidetic replay requested for sensitive data | Requires policy approval or is denied. |

---

## Security Events

Required events:

- `security_classification_completed`
- `prompt_injection_risk_detected`
- `sensitive_data_detected`
- `egress_policy_decision`
- `plugin_permission_diff_created`
- `memory_poisoning_risk_detected`
- `approval_replay_rejected`
- `policy_override_attempt_blocked`
- `secret_redacted`
- `eidetic_replay_policy_decision`
- `security_test_completed`

---

## Security Review Requirements

Every new feature must answer:

1. What trust boundary does it cross?
2. What data can it read?
3. What data can it write?
4. Can it execute code or commands?
5. Can it use network?
6. Can it persist memory?
7. Can it approve actions?
8. Can it spawn agents/tasks?
9. What events does it emit?
10. What tests prove it is safe?


## Model acquisition additions

| Risk class | Controls |
|---|---|
| Model supply chain | Immutable Hugging Face revisions, licence/gating review, GGUF-first download, approved destinations, digest-pinned isolated conversion, bounded GGUF parsing |
| Unbounded consumption | Expiring exact readiness; one-token owner-triggered hosted preflight; durable operation progress; conversion CPU, memory, PID, time and output bounds |
