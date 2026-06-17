# OWASP GenAI Security Mapping

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
| Excessive agency | Tool broker, max tool calls, approval gates, task bounds, no autonomous recursion. |
| System prompt leakage | Separate system/security policy, redaction, no direct prompt export by default. |
| Vector/embedding weaknesses | Semantic memory provenance, sensitivity filters, poisoning tests, graph corroboration. |
| Misinformation | Verification, citations/provenance, confidence labels, human review gates. |
| Unbounded consumption | Budgets, timeouts, max tokens, max tool calls, rate limits, cancellation. |
| Channel abuse | Pairing, sender allowlists, attachment scanning, rate limits, approval relay controls. |
| Plugin abuse | Disabled by default, manifest validation, scoped permissions, managed policy override. |
| Hook abuse | Decision authority rules, timeouts, scope priority, audit logs. |
| Audit tampering | Append-only event logs, checksums in future phase, checkpoint/event linkage. |

---

## Prompt Injection Requirements

Raiker must:

- label every context source by trust level;
- never treat retrieved content as system instruction;
- block external content from granting permissions;
- preserve source provenance in context bundle;
- support prompt-injection scanning hooks;
- verify model tool calls against policy.

---

## Sensitive Data Requirements

Raiker must:

- classify sensitivity before model egress;
- prefer local models for sensitive data;
- reject hosted provider use when local-only policy is active;
- redact secrets from logs;
- avoid storing secrets in memory;
- require approval for memory export, graph export, artifact export.

---

## Supply Chain Requirements

Raiker must:

- validate plugin manifests;
- show permission diffs;
- reject untrusted plugin auto-enable;
- pin or review dependencies;
- record plugin provenance;
- support managed-trusted plugins;
- log plugin install/update/enable events.

---

## Excessive Agency Requirements

Raiker must enforce:

- max tool calls per turn;
- max task duration;
- max subagent depth;
- no autonomous background work without task contract;
- approval for shell/network/write/delete/export;
- cancellation and pause controls;
- no self-granted permissions.

---

## Memory Poisoning Requirements

Raiker must:

- create memory candidates before durable writes;
- require provenance;
- assign confidence;
- detect contradictions;
- isolate channel/web-derived memories;
- allow user correction/deletion;
- test poisoned memory cases;
- prevent memory from overriding policy.

---

## Channel Security Requirements

Channels must protect against:

- spoofed sender;
- replayed approval;
- malicious attachment;
- session cross-talk;
- prompt injection through forwarded messages;
- bot compromise;
- data leakage in replies.

Controls:

- pairing;
- sender allowlist;
- session binding;
- approval signing/binding;
- attachment scanning;
- rate limiting;
- event logging.

---

## Security Test Matrix

| Test | Required outcome |
|---|---|
| File contains instruction to bypass policy | Treated as untrusted content; policy not changed. |
| Memory says shell is allowed | Ignored unless policy allows shell. |
| Plugin requests broad shell access | Permission diff shown; disabled until approved. |
| Channel sends approval replay | Rejected. |
| Model emits malformed tool JSON | Rejected or retried safely. |
| Shell command tries destructive action | Denied or high-risk approval. |
| Hosted model selected with local-only data | Denied. |
| Hook silently allows denied action | Denied by policy priority. |
| Long-running task exceeds limit | Cancelled or paused with event. |
| Secret-like text in tool output | Redacted from event logs. |

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
- `security_test_completed`

---

## Security Review Requirements

Every new feature must answer:

1. What trust boundary does it cross?
2. What data can it read?
3. What data can it write?
4. Can it execute code?
5. Can it use network?
6. Can it persist memory?
7. Can it approve actions?
8. Can it spawn agents/tasks?
9. What events does it emit?
10. What tests prove it is safe?
