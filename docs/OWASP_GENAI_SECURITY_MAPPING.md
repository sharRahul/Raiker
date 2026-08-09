# OWASP GenAI Security Mapping

## Machine identity control

Per-turn signed machine identity reduces excessive agency and confused-deputy
risk: model output cannot borrow the human principal, replace owner credential
scope, or reach policy and tools without a context-bound attestation. The
machine actor and human authorizer remain distinct in approval and audit views.
This complements, rather than replaces, prompt-injection handling, least
privilege, output validation, approvals, and sandboxing.

Raiker must map its controls to OWASP LLM and GenAI security risks. This document converts agent security into concrete Raiker requirements.

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

| ID | Risk | Doc | Code | Highest-value control to add |
|---|---|---|---|---|
| LLM01 | Prompt injection | yes | 🟡 | Tag every context item with source + trust; never grant instruction authority to file/tool/channel content. |
| LLM02 | Sensitive information disclosure | yes | 🟡 | `redact_secret_like_text()` exists for approval previews; apply one redaction pass to **all** persisted text and model egress; add egress classifier. |
| LLM03 | Supply chain | yes | 🔒 | Manifest validation real; add signing/checksums + trusted-publisher allowlist + dependency policy. |
| LLM04 | Data & model poisoning | yes | 🔒 | Memory writes disabled; enforce provenance + contradiction checks when enabled. |
| LLM05 | Improper output handling | yes | ✅ | Model tool calls are schema-validated at the boundary (`raiker/models/tool_call_validation.py`); unknown tools / missing args are rejected (`model_tool_call_rejected`) before execution. |
| LLM06 | Excessive agency | yes | ✅ | Broker + approvals + per-turn max-tool-calls fail-safe (`PromptOptions.max_tool_calls`, enforced in the orchestrator loop; the default is effectively unbounded — `DEFAULT_MAX_TOOL_CALLS = 10000` — so a turn ends when the model finishes or the provider's context/token budget runs out; the counter only stops runaway loops, and callers may pass a lower explicit bound). Add time/token budgets next. |
| LLM07 | System prompt leakage | yes | 📘 | Separate system/security prompt from user-visible context; implement with first real provider. |
| LLM08 | Vector & embedding weaknesses | yes | 🔒 | Vector writes disabled; apply sensitivity/provenance filters on retrieval when enabled. |
| LLM09 | Misinformation | yes | 🟡 | Verifier is a stub (`raiker/runtime/verifier.py`); implement verification + citation/provenance gating. |
| LLM10 | Unbounded consumption | yes | 🟡 | Per-turn tool-call fail-safe enforced (default is deliberately effectively unbounded; the provider's context/token budget is the practical per-turn bound). Add token/time budgets and rate limits next. |

**Implemented strengths today:** workspace path-safety (symlink/traversal rejection), policy-gated
tool execution with approvals, append-only event log, and disabled-by-default for high-risk
capabilities. **Four controls (LLM01, LLM05, LLM06, LLM10)** are small, local orchestrator/broker
changes that would convert documented-only mitigations into enforced ones — do these first.

---

## Prompt Injection Requirements

Raiker must label every context source by trust level, never treat retrieved content as system instruction, block external content from granting permissions, preserve source provenance in context bundles, support prompt-injection scanning hooks, and verify model tool calls against policy.

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
