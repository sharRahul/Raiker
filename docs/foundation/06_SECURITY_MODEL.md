> **Foundation document.** This is a living design-foundation doc (moved from `docs/completed/` during the 2026-06-21 documentation alignment). For current implementation status see the canonical ledger `docs/IMPLEMENTATION_STATUS.md`; for outstanding work see `docs/GAP_AND_TODO_ANALYSIS.md`. As of that date: Phases 1–9 foundations are in place (Phase 8 is the planned UI/client phase), the launchable local UIs are the plain local terminal client and the local web dashboard (Rich/native TUI, desktop, mobile, IDE, voice, browser-extension, and hosted/multi-user REST clients deferred to Phase 8), and all runtime execution remains disabled.

# 06 Security Model

## 1. Security Goal

The agent must be safe to run on a personal or enterprise workstation that contains source code, documents, SSH keys, cloud credentials, browser data, and private memory.

## 2. Instruction Trust Hierarchy

```text
System prompt
  > application/developer policy
  > enterprise/admin policy
  > user instruction
  > trusted local tool result
  > retrieved data and untrusted content
```

Untrusted content includes web pages, repository text, comments, logs, chat messages, webhook payloads, plugin output, external command output, and retrieved memory snippets until validated.

## 3. OWASP-Aligned Threats and Controls

### Prompt Injection
Controls:
- Source labels.
- Instruction hierarchy.
- Prompt-injection detector.
- Retrieved-content quarantine.
- Tool calls require policy decision.
- Security event logging.

### Sensitive Information Disclosure
Controls:
- Secrets scanner.
- Redaction before remote calls.
- Encrypted event payloads.
- Egress policy.
- Local-only default.
- Remote provider approval.

### Supply Chain Risk
Controls:
- Plugin manifests.
- Plugin trust state.
- Signatures where available.
- Dependency pinning.
- No undeclared permissions.
- Quarantine unknown plugins.

### Data, Model, and Memory Poisoning
Controls:
- Memory provenance.
- Trust scores.
- User approval for stable facts.
- Contradiction checks.
- Memory rejection events.

### Improper Output Handling
Controls:
- Schema validation.
- Shell quoting.
- Dry runs where possible.
- Diff review.
- Tests and verifier subagent.

### Excessive Agency
Controls:
- Allow/ask/deny decisions.
- Max turns.
- Max subagents.
- Max runtime.
- Max token/cost.
- Destructive command blocking.

### System Prompt Leakage
Controls:
- Refuse requests for hidden prompts.
- Never send hidden prompts to tools/plugins.
- Redact internal instructions from logs.

### Vector and Embedding Weaknesses
Controls:
- Namespace isolation.
- ACL filters.
- Provenance citation.
- Trust scoring.
- Index rebuild.

### Misinformation
Controls:
- Verification loop.
- Citations/provenance.
- Explicit uncertainty.
- Ask user when unverifiable.

### Unbounded Consumption
Controls:
- Budgets.
- Timeouts.
- Process limits.
- Cloud cost limits.
- Background task supervisor.

## 4. Permission Classes

### Low Risk — Default Allow
- Read approved workspace files.
- List directories.
- Grep/glob.
- Generate plan.

### Medium Risk — Ask or Workspace Allow
- Write files.
- Edit files.
- Update project memory.
- Run tests in trusted workspace.

### High Risk — Default Ask
- Shell.
- Network.
- Remote model with local context.
- Docker write mount.
- SSH.
- Plugin install.
- External execution.
- Git commit/push.
- Memory delete.

### Critical Risk — Default Deny
- Recursive destructive deletion.
- Upload secrets.
- Disable logging or policy.
- Privilege escalation.
- Unsigned plugin with broad access.

## 5. Security Event Requirements

Every blocked, suspicious, or approved high-risk action must emit a security event with risk, actor, reason, and policy decision.

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
