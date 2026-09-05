# Raiker Security & Compliance Gap Assessment — 2026-09-05

## Purpose

This plan records Raiker's current security posture against current application-security, AI/GenAI/agent-security, privacy, data-loss-prevention, supply-chain, software-product-security, and AI-governance expectations.

It is a **static architecture/code/documentation assessment and remediation plan**, not a penetration test, legal opinion, certification, production-configuration review, or proof of operational compliance.

The review uses implementation evidence as the primary source. Documentation-only claims are not treated as implemented controls unless a corresponding enforcement path exists.

This revision includes a **second-pass review** focused on issues that were underrepresented in the first pass: agentic AI risks, AI secure development, model/AI supply chain, RAG/vector security, memory poisoning, MCP trust, multimodal injection, model-output rendering, delegated identity, approval integrity, cryptographic/key lifecycle, backup/restore security, coordinated vulnerability disclosure/PSIRT, cross-agent security, AI release evaluations, fail-safe degradation, UK privacy, and EU Cyber Resilience Act readiness.

---

# 1. Benchmark set

## 1.1 Application and API security

Primary application-security baselines:

- OWASP Top 10:2025.
- OWASP ASVS 5.0.0.
- OWASP API Security Top 10:2023.
- OWASP SSRF, authentication, session-management, secrets-management, logging and secure-file-processing guidance where relevant.

## 1.2 AI, GenAI, LLM and agentic security

Primary AI/agent security baselines:

- OWASP GenAI LLM Top 10:2026.
- OWASP Agent Control Standard (ACS), released 2026-09-01.
- OWASP Top 10 for Agentic Applications 2026.
- OWASP GenAI guidance for securely using third-party MCP servers and securely developing MCP servers.
- NIST AI RMF 1.0.
- NIST AI 600-1 Generative AI Profile.
- NIST SP 800-218 SSDF 1.1.
- NIST SP 800-218A, Secure Software Development Practices for Generative AI and Dual-Use Foundation Models.
- MITRE ATLAS, including prompt injection, agent-context poisoning, tool poisoning/tool invocation, credential discovery/misuse, AI-service data access/exfiltration, persistence, AI artifact/supply-chain compromise, and response-rendering attack paths.
- ENISA Multilayer Framework for Good Cybersecurity Practices for AI: cybersecurity foundations, AI-specific cybersecurity, and sector-specific controls.

## 1.3 Leading-provider practices

Provider and platform recommendations considered:

- Google Secure AI Framework (SAIF): input/output validation, contextual least privilege, agent/tool controls, monitoring, red teaming, data governance and supply-chain controls.
- OpenAI agent-security guidance: least privilege, explicit user confirmation for consequential actions, restricted tool/app access, prompt-injection resilience, monitoring and safe delegation.
- Microsoft AI security and Purview DLP practices: sensitive-information classification, contextual policy, monitor/warn/block actions, data-boundary controls and auditability.
- AWS security/DLP patterns: continuous sensitive-data discovery, encryption, findings, coverage reporting, least privilege and retention.
- GitHub secure-use guidance: least-privilege workflow permissions, immutable action pinning, secret protection, code scanning, dependency review and supply-chain controls.

## 1.4 Privacy, AI regulation and product-security regulation

Regulatory/privacy baselines:

- EU GDPR, particularly Arts. 5, 6, 12–22, 24–25, 28, 30, 32–36 and international-transfer obligations where applicable.
- EDPB Opinion 28/2024 on personal-data processing in the context of AI models.
- Regulation (EU) 2024/1689 (EU AI Act), including obligations already applicable by 2026-09-05 and Article 50 transparency requirements.
- UK GDPR and Data Protection Act 2018 for UK operating/distribution contexts.
- Regulation (EU) 2024/2847, Cyber Resilience Act (CRA), where Raiker qualifies as a product with digital elements placed on the EU market.
  - CRA Article 14 reporting obligations apply from **2026-09-11**.
  - General CRA application is from **2027-12-11**.
  - Applicable manufacturers must report actively exploited vulnerabilities and severe security incidents, with an early warning within 24 hours and a fuller notification within 72 hours through the CRA reporting mechanism.
- NIS2/DORA/sectoral rules are **conditional overlays**, not assumed universally applicable to Raiker.

---

# 2. Status vocabulary

- **Aligned** — direct implementation evidence supports the control objective.
- **Partially aligned** — meaningful control exists but coverage, assurance, configuration, lifecycle completeness or evidence is missing.
- **Gap** — no sufficient implementation/governance evidence was identified.
- **Applicability TBD** — legal/product applicability depends on deployment, distribution model, business role, data flows or intended use.
- **Operational evidence required** — implementation support exists, but runtime/process evidence is still required.

Priority:

- **P0** — release/public-exposure blocker or bypass of a core security boundary.
- **P1** — high-value security/compliance remediation for the next hardening cycle.
- **P2** — material defense-in-depth/assurance improvement.
- **P3** — maturity, evidence and operational-quality improvement.

---

# 3. Executive assessment

Raiker already has an unusually strong **governed-agent architecture** for an open AI application: explicit runtime authority/capability mapping, approval and critical-confirmation concepts, tool/service capability gates, credential-aware redaction, event/audit concepts, checkpoint/recovery support, sandbox/container execution paths, web egress policy, source provenance and prompt-injection detection.

The largest remaining risk is **control completeness and demonstrable assurance**, not the absence of a governance layer. A mature Raiker release must prove that every ingress, model call, retrieved chunk, memory write/recall, tool call, plugin, MCP server, subagent, connector, scheduled action, file mutation, credential loan and outbound disclosure crosses enforceable non-model security boundaries.

The second pass adds an important conclusion:

> **Raiker must treat authority, data, identity and provenance as separate security planes. A safe network destination is not automatically an authorised data destination; a model suggestion is not authority; a trusted agent is not a trusted subagent; a retrieved source is not an instruction; and a successful approval is valid only for the exact action that was previewed.**

## 3.1 Overall judgement

| Domain | Status | Summary |
|---|---|---|
| Agent authority / least privilege | **Aligned / verify exhaustiveness** | Strong central capability mapping and human-confirmation constructs; add machine-enforced no-bypass invariants. |
| OWASP Agentic Top 10 coverage | **Partial** | Architecture addresses several risks implicitly; explicit risk → control → test mapping is missing. |
| Prompt injection / untrusted context | **Partial** | Detection/provenance exists; complete chunk/multimodal/tool-result coverage and adversarial tests are needed. |
| Tool / excessive-agency controls | **Aligned / verify exhaustiveness** | Capability gates are strong; direct-executor escape paths must be continuously disproved. |
| Delegated identity / subagents | **Partial** | Subagent governance exists conceptually; attenuated identity/capability inheritance and anti-laundering invariants need explicit assurance. |
| MCP security | **Partial / gap** | MCP is governed as a capability, but server identity, schema/tool drift, tool poisoning, trust and approval-binding require deeper controls. |
| Web / SSRF | **Strongly aligned** | Public-only address checks and DNS-rebinding-aware logic are strong. |
| Outbound DLP / destination policy | **Partial** | Network reachability is separated from some governance, but a full data-disclosure policy plane is not yet evidenced. |
| RAG/vector/embedding security | **Partial / gap** | Privacy/retention concepts exist; retrieval ACL propagation, poisoning controls and vector namespace isolation require explicit controls/tests. |
| Long-term memory security | **Partial** | Memory is governed, but durable context poisoning, contamination and compaction integrity need dedicated controls. |
| Multimodal input security | **Gap / not fully evidenced** | Text injection handling does not prove equivalent controls for images, PDFs, metadata, OCR/audio or embedded active content. |
| Model-output/rendering security | **Partial** | Browser headers help, but model-generated HTML/Markdown/SVG/URLs/files/terminal output need explicit safe-rendering controls. |
| Browser hardening | **Partial / gap** | Useful security headers exist; CSP was not identified in reviewed middleware. |
| API abuse / resource consumption | **Partial** | Rate/body-size guardrails exist; streamed-byte, token/cost, recursion, CPU/memory and fan-out budgets need strengthening. |
| DLP / sensitive data | **Partial** | Strong credential redaction exists; classify/decide/enforce/block/warn/quarantine controls are incomplete. |
| Secrets lifecycle | **Strong partial** | Runtime redaction is good; vaulting, scope, rotation, child-process inheritance and crash-dump protections need explicit assurance. |
| Cryptographic/key lifecycle | **Partial** | SQLCipher posture is positive; master-key storage, rotation, backup/recovery and crypto agility need a formal design. |
| Backup/restore security | **Partial** | Checkpoints exist; restore must not bypass revocation, GDPR deletion or malicious-state quarantine. |
| Software supply chain | **Partial** | SHA-pinned actions/tests are positive; broaden SAST/SCA/SBOM/provenance/secret scanning. |
| AI/model supply chain | **Gap / partial** | Model provenance, hashes/signatures, unsafe model formats/config/tokenizers/adapters and model registry trust need explicit controls. |
| Logging/audit/observability | **Strong partial** | Good event concepts; integrity, taxonomy, retention, correlation and incident evidence requirements need formalisation. |
| Incident response / PSIRT | **Partial / gap** | Security findings exist; a complete vulnerability intake, coordinated disclosure, emergency revocation and CRA-ready reporting process is needed. |
| GDPR / UK GDPR | **Partial / applicability-dependent** | Strong technical ingredients; operational accountability artifacts remain required. |
| EU AI Act | **Partial / applicability TBD** | Governance architecture is favourable; formal role/risk/transparency applicability register is required. |
| EU CRA | **Applicability TBD / urgent readiness** | Determine manufacturer/product applicability now; Article 14 reporting begins 2026-09-11 where applicable. |
| MITRE ATLAS / adversarial assurance | **Partial** | Multiple ATLAS techniques are addressed architecturally; maintain a live threat-control-test matrix. |
| AI release security evaluation | **Gap / partial** | Standard tests exist; adversarial AI-specific release gates and regression thresholds need formalisation. |

---

# 4. Core Raiker security invariants

These should be treated as non-negotiable architectural invariants and eventually machine-tested.

## INV-01 — Authority can originate only from the governed runtime

> No model, agent, subagent, memory, retrieved document, plugin, MCP server, connector, tool result, scheduled task or external message may create, expand, transfer or exercise authority. Authority may only originate from authenticated human policy or an explicitly delegated, bounded, auditable grant issued by the Raiker runtime.

## INV-02 — Untrusted content is data, never authority

Content from the web, documents, email, chat, repositories, MCP/tool outputs, OCR, images, audio, memory or RAG may inform reasoning but may not change permissions, approvals, policy, credential scope or destination policy.

## INV-03 — Approval is bound to exact intent and exact effects

Every approval must be cryptographically/logically bound to the exact actor, target, tool, arguments, expected effects, destination, data classification, credential scope and expiry shown to the user. Any material change invalidates approval.

## INV-04 — Data disclosure requires a separate DLP decision

Passing authentication, tool policy, SSRF checks or an approval does not by itself authorise disclosure. Sensitive-data movement must pass destination-aware DLP/minimisation policy.

## INV-05 — Delegation only reduces privilege

A subagent, plugin, MCP server or child process may receive equal or lower privilege than its parent grant, never greater privilege. Delegation must be time-bound, purpose-bound and revocable.

## INV-06 — Security-service failure fails safely

Failure/unavailability of DLP, policy evaluation, approval verification, credential brokerage, provenance verification or critical audit functions must not silently convert to `allow`.

## INV-07 — Restore cannot resurrect forbidden state

Restore/checkpoint/backup operations must re-apply current policy, credential revocation, deletion requirements, malware/trust checks and compatibility validation before state becomes active.

---

# 5. Confirmed strengths

## S-01 — Central runtime authority and explicit capability vocabulary

**Status: Aligned**

`raiker/runtime/authority/router.py` maps tools and high-impact services to explicit capability gates, including file/patch writes, memory mutation, git push, shell, remote/cloud execution, web access, plugins, hosted/private model runtimes, connectors, MCP, subagents, external channels and sensitive-domain runtimes. It also defines non-allow decisions and critical human-confirmation structures.

**Recommendation:** preserve this as the mandatory reference-monitor architecture and make its coverage machine-verifiable.

## S-02 — Prompt injection treated as an untrusted-data problem

**Status: Aligned design / partial assurance**

`raiker/security/injection_scan.py` recognises instruction override, role impersonation, credential solicitation, exfiltration, tool coercion, approval bypass, hidden instructions and invisible-character techniques. Findings retain redacted metadata/provenance, and detection is advisory rather than incorrectly being treated as the security boundary.

## S-03 — SSRF and DNS-rebinding-aware web policy

**Status: Strongly aligned**

`raiker/runtime/web_policy.py` denies loopback/private/link-local/multicast/reserved/non-global addresses, handles alternate IP forms, validates all DNS answers and is designed to prevent validate-then-re-resolve DNS rebinding.

## S-04 — Credential-aware redaction

**Status: Aligned for redaction objective**

`raiker/context/redaction.py` covers private keys, common token shapes, bearer credentials, password/API-key assignments, email, card/account-like values and high-entropy tokens. It also supports exact in-use secret registration so known credentials remain redacted even if transformed.

## S-05 — CSRF-aware cookie authentication and scoped sessions

**Status: Partial/positive**

`raiker/api/auth.py` distinguishes explicit bearer headers from browser cookies, applies CSRF controls to the cookie path, checks expiry/revocation/active principals and validates required scopes.

## S-06 — Baseline HTTP hardening

**Status: Partial/positive**

`raiker/api/security.py` includes `X-Content-Type-Options`, frame denial, strict referrer policy, COOP/CORP, Permissions-Policy and optional HSTS, plus API rate limiting and request-size handling.

## S-07 — CI immutability and security-relevant tests

**Status: Partial/positive**

`.github/workflows/ci.yml` pins reviewed GitHub Actions to full commit SHAs and runs Python tests, Ruff, mypy, compilation, native Rust tests and SQLCipher security checks.

---

# 6. First-pass gaps retained

## F-01 — Enforce a machine-verifiable no-authority-bypass invariant

**Priority: P0**  
**Status: Partially aligned**

Create registry/invariant tests that fail CI when a side-effecting capability can execute without:

1. authenticated principal/session context where applicable;
2. capability-gate evaluation;
3. risk classification;
4. policy/decision-mode evaluation;
5. approval/critical confirmation when required;
6. scoped credential loan after authorization;
7. pre/post audit events;
8. output/redaction/DLP handling;
9. cancellation/revocation where technically possible.

**Acceptance criterion:** introducing a deliberately bypassing tool/executor causes CI to fail.

## F-02 — Add a production Content Security Policy

**Priority: P1**  
**Status: Gap in reviewed middleware**

Implement nonce/hash-based CSP where practical. Explicitly constrain `default-src`, `script-src`, `style-src`, `img-src`, `font-src`, `connect-src`, `worker-src`, `frame-ancestors`, `base-uri`, `form-action` and `object-src`. Avoid `unsafe-eval`; minimise `unsafe-inline`.

## F-03 — Enforce request limits on actual streamed bytes

**Priority: P1**  
**Status: Partial**

Do not rely only on declared `Content-Length`. Bound cumulative receive bytes, decompression ratios, archive nesting, parser memory/time, attachment types and base64 expansion.

## F-04 — Make prompt-injection detection chunk-complete for context actually sent to models

**Priority: P1**  
**Status: Partial**

Large-document head/tail sampling can miss middle-of-document attacks. Scan each chunk actually entering model context and preserve provenance.

## F-05 — Build a real DLP decision plane

**Priority: P1**  
**Status: Partial**

Implement common `DataClassification` + `DlpDecision` contracts across prompts, attachments, RAG, memory, model-provider requests, tools/connectors, network egress, email/chat/calendar, exports, telemetry, plugins/MCP and subagents.

Minimum policy actions:

- allow;
- redact/tokenize;
- warn + require confirmation;
- block;
- quarantine;
- require narrower destination/scope;
- explicit time-bound exception.

## F-06 — Separate network reachability from disclosure authorization

**Priority: P1**  
**Status: Partial**

Keep the strong SSRF guard, but add a higher-level destination policy considering destination trust, tool purpose, data classification, user-selected versus untrusted-content-selected destinations, redirects, methods, credential scope and volume anomalies.

## F-07 — Add model/tool/subagent resource and cost budgets

**Priority: P1**  
**Status: Partial**

Enforce per-turn/session/day ceilings for tokens, spend, retries, web downloads, tool calls, MCP calls, subagent depth/fan-out, scheduled routines, command duration, CPU, memory, storage and output bytes.

## F-08 — Expand CI/CD supply-chain controls

**Priority: P1/P2**  
**Status: Partial**

Add/verify:

- explicit least-privilege workflow `permissions:`;
- CodeQL/SAST;
- dependency review/SCA;
- SBOM generation;
- build provenance/attestation;
- release-artifact signing/verifiability;
- secret scanning and push protection;
- container/image scanning where applicable;
- dependency pinning/update policy;
- protected release workflow and environment approvals.

## F-09 — Maintain MITRE ATLAS + OWASP ACS control/test mappings

**Priority: P1/P2**

For every applicable technique/control, record:

`Threat → Attack path → Raiker boundary → Preventive control → Detective control → Audit event → Automated test → Residual risk`.

## F-10 — Complete GDPR/UK GDPR accountability artifacts

**Priority: P1/P2**  
**Status: Partial / operational**

Maintain:

- ROPA/data inventory;
- lawful-basis mapping;
- special-category conditions where relevant;
- controller/processor/subprocessor mapping;
- privacy notices;
- data-subject-rights workflows;
- deletion propagation through memory, vector indexes, checkpoints, backups and provider copies;
- retention schedules;
- processor/transfer register;
- breach procedure;
- DPIA trigger/template;
- hosted-provider data-minimisation tests.

## F-11 — Formalise EU AI Act applicability

**Priority: P1/P2**  
**Status: Applicability TBD**

Maintain a role/use-case register determining whether a deployment acts as provider, deployer, importer/distributor or other actor; whether it creates/uses high-risk systems; whether Article 50 transparency applies; and whether any GPAI-provider obligations attach to Raiker itself rather than the upstream model provider.

---

# 7. Second-pass findings and required improvements

## SP-01 — Explicitly map OWASP Top 10 for Agentic Applications 2026

**Priority: P1**  
**Status: Partial**

The first pass referenced agentic guidance but did not require an explicit control-by-control crosswalk.

Create `docs/security/OWASP_AGENTIC_TOP10_MAPPING.md` or equivalent mapping each OWASP Agentic risk to:

- applicable Raiker surfaces;
- prevention controls;
- detection/telemetry;
- human-control points;
- abuse cases;
- automated adversarial tests;
- residual risk.

At minimum cover agent goal hijack, tool misuse, identity/privilege abuse, supply-chain compromise, unexpected code execution and unsafe multi-agent/delegation behaviour.

**Acceptance criterion:** no applicable Agentic Top 10 item may be marked aligned without both implementation evidence and an executable test or documented operational evidence requirement.

---

## SP-02 — Adopt NIST SP 800-218A as an AI secure-development baseline

**Priority: P1/P2**  
**Status: Gap in formal benchmark mapping**

Extend Raiker's SSDLC so model/AI-specific artifacts are governed like software artifacts.

Required controls:

- provenance of models, datasets/adapters/configuration used in builds/tests;
- threat modelling before new AI capabilities;
- secure defaults;
- protected build/release environments;
- vulnerability/root-cause analysis;
- AI-specific security tests before release;
- documentation of security-relevant model/tool/provider assumptions.

---

## SP-03 — Establish EU Cyber Resilience Act readiness

**Priority: P1 now**  
**Status: Applicability TBD / time-sensitive**

Raiker must determine whether its distribution model qualifies it as a manufacturer/provider of a product with digital elements under the CRA.

Important dates:

- **2026-09-11:** Article 14 vulnerability/severe-incident reporting obligations begin where applicable.
- **2027-12-11:** general CRA application date.

Required readiness work:

- formal CRA applicability decision and evidence;
- PSIRT/contact ownership;
- actively exploited vulnerability triage;
- severe security incident classification;
- 24-hour early-warning workflow;
- 72-hour main-notification workflow;
- final-report workflow;
- vulnerability remediation/SLA tracking;
- supported-version/security-update policy;
- vulnerability disclosure intake;
- evidence preservation and notification audit trail.

Do not state that Raiker is CRA-compliant until applicability and required operational processes are evidenced.

---

## SP-04 — Add ENISA's multilayer AI cybersecurity framework

**Priority: P2**  
**Status: Gap in formal crosswalk**

Map Raiker against ENISA's three-layer structure:

1. cybersecurity foundations;
2. AI-specific cybersecurity;
3. sector-specific overlays where Raiker is deployed into regulated/high-risk environments.

This helps prevent AI controls from being treated as a replacement for conventional platform security.

---

## SP-05 — Create an AI/model supply-chain trust boundary

**Priority: P1**  
**Status: Gap / partial**

Software dependency controls are not sufficient for downloadable or externally hosted models.

Required controls:

- trusted model registries/sources;
- immutable model/version identifiers where possible;
- hash/signature verification for downloaded artifacts;
- quarantine before activation;
- provenance manifest covering provider/source, licence, model version, hash, format and trust decision;
- block unsafe deserialization formats by default;
- restrict executable/custom-code model loaders;
- inspect/tokenize configuration separately from model weights;
- protect against malicious tokenizers, templates, config hooks, adapters and LoRAs;
- model substitution detection;
- embedding-model provenance;
- rollback/revocation for compromised models;
- explicit trust level shown in the UI/control plane.

Hosted providers also require provenance: endpoint, tenant/account, API version, model version/alias semantics and provider data-handling policy must be captured.

---

## SP-06 — Treat RAG/vector/embedding storage as an authorization boundary

**Priority: P1**  
**Status: Partial / gap**

Required invariants:

> Retrieval must never return content the requesting principal could not have directly read.

Controls:

- source ACLs propagated into chunks/embeddings;
- project/user/tenant namespace isolation;
- retrieval-time authorization, not ingestion-time authorization only;
- source trust/provenance on every chunk;
- poisoning detection/quarantine;
- stale/superseded source handling;
- deletion propagation into vectors/indexes/caches;
- no cross-project similarity leakage;
- restricted metadata filters cannot be model-controlled without validation;
- embedding model/version changes trigger safe re-index/revalidation;
- exact source links retained for audit/explanation.

Adversarial tests must attempt cross-project retrieval, deleted-document retrieval, metadata filter bypass and poisoned-chunk influence.

---

## SP-07 — Add durable-memory poisoning and contamination controls

**Priority: P1**  
**Status: Partial**

Memory creates persistence and therefore deserves a dedicated threat model.

Controls:

- provenance for every memory;
- classify source as user assertion, verified fact, model inference, tool result or external content;
- untrusted external content may not silently become durable instruction/policy;
- memory writes remain governed actions;
- confidence/expiry/supersession metadata;
- project/user isolation;
- safe compaction/summarisation with provenance preservation;
- rollback/forget capability;
- detect repeated self-reinsertion/self-replication;
- security-sensitive memories require stronger write policy;
- memory recall cannot increase authority.

Test indirect prompt injection → memory write → later privileged action as a full multi-turn attack chain.

---

## SP-08 — Deepen MCP security beyond capability gating

**Priority: P1**  
**Status: Partial**

MCP must be treated as an untrusted integration boundary even when the user intentionally connects a server.

Controls:

- strong MCP server identity and origin display;
- explicit trust state;
- tool catalogue/schema snapshot at approval/connection time;
- detect tool-description/schema changes;
- require reapproval for security-relevant tool drift;
- protect against tool-name collisions/confusable names;
- tool descriptions are untrusted data, not policy;
- narrow OAuth/API scopes and audience-bound tokens;
- credentials never exposed to tool descriptions/results;
- per-tool capability mapping rather than blanket server trust;
- outbound destination/DLP controls still apply to MCP-triggered actions;
- confused-deputy protections;
- server revocation/kill switch;
- audit server identity + tool schema version/hash with each consequential invocation where practical;
- remote MCP transports must receive the same SSRF/TLS/DLP scrutiny as other external services.

**Approval integrity:** if a tool definition changes after approval, the old approval must not authorize the new semantics.

---

## SP-09 — Extend prompt-injection controls to multimodal and embedded content

**Priority: P1/P2**  
**Status: Gap / not fully evidenced**

Treat as untrusted instruction-bearing surfaces:

- images;
- PDFs and hidden text/OCR layers;
- document metadata/comments;
- Office files;
- HTML/SVG;
- QR codes;
- audio and transcripts;
- EXIF/XMP metadata;
- code comments/issues/commit messages;
- generated thumbnails/previews.

Controls:

- maintain source/layer provenance;
- strip or isolate active content before parsing;
- detect mismatches between visible and hidden text where possible;
- never execute embedded macros/scripts;
- separate extraction from interpretation;
- scan model-bound extracted chunks, not only raw container files.

---

## SP-10 — Secure model-output rendering and generated artifacts

**Priority: P1**  
**Status: Partial**

Model output is attacker-influenced data and must not be rendered/executed as trusted UI content.

Controls:

- sanitize HTML/Markdown;
- reject dangerous URL schemes (`javascript:`, unsafe `data:` use, file/custom protocols unless explicitly required); 
- sanitize SVG and active content;
- prevent automatic remote-resource fetching from rendered model output unless governed;
- safe link previews;
- phishing/external-domain indicators for generated links where useful;
- filename/path canonicalization;
- generated downloads treated as untrusted until scanned/validated;
- terminal/ANSI/control-sequence sanitization;
- escape logs and diagnostics for terminal/web viewers;
- diagram/Markdown extensions must not create script execution paths.

This should be mapped to MITRE ATLAS response-rendering/exfiltration techniques.

---

## SP-11 — Formalise agent/subagent/service identity

**Priority: P1**  
**Status: Partial**

Required identity chain:

`human → session → agent → subagent/plugin/MCP/tool → external service`

Every hop should carry an auditable principal/delegation identity.

Controls:

- no implicit credential inheritance;
- attenuated capabilities;
- audience/purpose-bound credential grants;
- short expiry;
- explicit delegator identity;
- maximum delegation depth;
- revocation propagation;
- human-only roles can never be assumed by AI principals;
- downstream agents cannot assert that approval occurred; the runtime must verify it.

---

## SP-12 — Adversarially test human approvals

**Priority: P1**  
**Status: Partial**

Test and prevent:

- approval fatigue;
- misleading/truncated summaries;
- preview/execute argument mismatch;
- target/path/destination substitution;
- TOCTOU changes after approval;
- replay/reuse;
- expired approvals;
- cross-session approval theft;
- nested approvals hiding consequential actions;
- bulk approvals that exceed intended scope;
- model-generated social engineering around the approval UI;
- post-approval tool/schema drift.

**Acceptance criterion:** the execution broker recomputes a canonical action digest/fingerprint and rejects execution when the approved intent no longer matches.

---

## SP-13 — Expand secrets management from redaction to lifecycle controls

**Priority: P1**  
**Status: Strong partial**

Required controls:

- use OS keychain/secure vault abstractions where practical;
- no plaintext persistence;
- provider-specific isolation;
- least-privilege OAuth scopes;
- short-lived tokens/workload identity where available;
- rotation and revocation UX;
- credential use only after policy approval;
- child processes receive only explicitly loaned secrets;
- scrub unnecessary inherited environment variables;
- prevent secrets from crash reports, telemetry and core dumps where practical;
- exact-secret redaction remains active for the whole loan lifetime;
- credential compromise creates immediate revoke-and-disable workflow.

---

## SP-14 — Formalise cryptographic and key-management architecture

**Priority: P1/P2**  
**Status: Partial**

Document and test:

- master-key generation/entropy;
- KDF parameters;
- OS-bound key storage (DPAPI/Keychain/Secret Service/TPM where suitable);
- separation between data-encryption keys and wrapping keys;
- key rotation;
- migration/re-encryption;
- secure deletion limitations;
- backup/recovery key process;
- encryption for attachments, vector data, checkpoints, audit exports and sensitive caches;
- nonce/IV correctness;
- crypto library/version policy;
- crypto agility and algorithm deprecation plan.

No custom cryptography.

---

## SP-15 — Make backup/checkpoint restore a governed security event

**Priority: P1/P2**  
**Status: Partial**

Restore is potentially more privileged than a normal write because it can resurrect old state.

Before activation of restored state, re-evaluate:

- revoked credentials/tokens;
- deleted personal data;
- revoked plugins/MCP servers/models;
- malware/quarantine state;
- policy version compatibility;
- principal/role changes;
- secrets rotation;
- schema/data migrations.

Backups must have retention, encryption, integrity and deletion policy. Restores must be fully audited.

---

## SP-16 — Establish PSIRT, coordinated vulnerability disclosure and emergency control paths

**Priority: P1**  
**Status: Partial / gap**

Maintain:

- `SECURITY.md` with supported versions and reporting method;
- private vulnerability reporting where available;
- severity taxonomy;
- triage/ownership SLAs;
- patch/release process;
- emergency kill switches for plugins/MCP/connectors/models/providers;
- credential-compromise playbooks;
- dependency/model compromise playbooks;
- evidence preservation;
- user notification criteria;
- CVE/CNA process if/when appropriate;
- CRA reporting decision tree where applicable.

---

## SP-17 — Threat-model abuse through Raiker, not only attacks against Raiker

**Priority: P1/P2**  
**Status: Gap / partial**

Because Raiker can act, the security model must include misuse of legitimate capabilities.

Define high-risk capability classes and controls for:

- destructive commands/filesystem actions;
- credential attacks;
- bulk external messaging/spam;
- high-volume crawling/scanning;
- surveillance/home-security capabilities;
- financial/medical/high-impact domains;
- privacy-invasive aggregation;
- persistence/autorun/service installation;
- downloading/executing untrusted binaries;
- large-scale automation.

Apply proportional friction: deny, sandbox, require step-up, narrow scope, explicit confirmation, rate/budget constraints and audit.

---

## SP-18 — Add cross-agent and multi-agent trust controls

**Priority: P1**  
**Status: Partial**

Prevent:

- delegation loops;
- privilege amplification;
- trust laundering (`agent B says user approved`);
- malicious inter-agent messages;
- uncontrolled fan-out;
- self-spawning persistence;
- duplicated side effects;
- unbounded spend;
- collusion between agents/tools to bypass single-control limits.

All agent-to-agent claims about permission must be treated as untrusted assertions and verified against the runtime authority store.

---

## SP-19 — Introduce AI-specific security evaluation gates

**Priority: P1/P2**  
**Status: Gap / partial**

Create a maintained adversarial evaluation suite covering:

- OWASP LLM Top 10:2026;
- OWASP Agentic Top 10:2026;
- OWASP ACS controls;
- MITRE ATLAS attack chains;
- DLP exfiltration cases;
- MCP/tool poisoning;
- RAG/memory poisoning;
- multimodal injection;
- approval manipulation;
- delegated privilege escalation;
- unsafe output rendering;
- resource exhaustion;
- compromised model/provider/tool simulations.

Each release should produce machine-readable evidence: tests executed, pass/fail, known exceptions, residual risk and versioned baseline.

Do not measure only refusal rate. Measure whether **authority boundaries remain intact even when the model is fully compromised**.

---

## SP-20 — Define fail-safe degradation for every security-critical dependency

**Priority: P1**  
**Status: Partial / operational evidence required**

Explicitly define behaviour when:

- policy engine unavailable;
- DLP classifier unavailable;
- audit store unavailable;
- model provider unavailable;
- vector index corrupted;
- memory store corrupted;
- MCP server unreachable/drifts;
- credential vault unavailable;
- sandbox runner fails;
- checkpoint capture fails;
- network/DNS validation fails;
- security scanner times out.

Security-critical enforcement failures should fail closed. Availability-only features may degrade safely if doing so does not weaken authority or disclosure controls.

---

## SP-21 — Add UK privacy/regulatory overlay

**Priority: P2**  
**Status: Applicability-dependent**

Maintain a UK GDPR/Data Protection Act 2018 mapping alongside EU GDPR for UK operations/users/distribution. Keep EU and UK transfer mechanisms, regulator references and legal bases distinct where necessary.

NIS2, DORA and sectoral requirements should remain optional deployment overlays unless Raiker or a customer deployment is actually in scope.

---

# 8. DLP target architecture

Recommended common pipeline:

`Source → provenance → normalization → classification → minimization → injection/content signals → policy → model/tool projection → runtime authority → destination DLP → execution → output validation → redaction/audit`

## 8.1 DLP principles

1. Detect before disclosure, not only after logging.
2. Data classification travels with the datum/chunk/artifact.
3. Model prompts do not strip source ACLs.
4. Local/private/hosted models have different destination trust levels.
5. Tool arguments and connector payloads are DLP-inspected independently from natural-language responses.
6. Credentials are never treated as ordinary sensitive text; use stricter non-disclosure defaults.
7. High-sensitivity transfers require explicit approved destinations and, where appropriate, confirmation.
8. Untrusted content cannot select an exfiltration destination and thereby authorize the transfer.
9. DLP exceptions are time-bound, scoped and auditable.
10. Security telemetry stores classification metadata rather than unnecessary raw sensitive content.

## 8.2 DLP test cases

Required regression cases include:

- secret in user prompt → hosted model;
- secret in attachment → model context;
- secret in RAG chunk → tool argument;
- PII in memory → external connector;
- source code → unapproved web endpoint;
- malicious document instructs upload to webhook;
- model encodes secret in URL/query/base64/JSON/header;
- agent splits sensitive value across multiple calls;
- data hidden in filename/path/metadata;
- data exfiltration through Markdown image/link rendering;
- subagent attempts disclosure using parent context;
- MCP tool attempts unexpected network transmission.

---

# 9. MITRE ATLAS / threat-control-test programme

Maintain an executable threat matrix rather than documentation-only mapping.

Minimum attack families:

- direct/indirect prompt injection;
- agent-context poisoning;
- RAG/vector poisoning;
- memory persistence poisoning;
- tool/MCP poisoning;
- model/artifact supply-chain compromise;
- credential discovery and misuse;
- AI-service/data-store discovery;
- data exfiltration via tools/network/rendering;
- malicious code execution;
- excessive agency/privilege escalation;
- model/provider substitution;
- approval manipulation;
- unsafe response rendering;
- multi-agent delegation abuse.

For each, maintain preventive, detective and recovery tests.

---

# 10. GDPR / privacy target state

Technical privacy controls are necessary but do not establish compliance by themselves.

Required evidence/artifacts:

1. ROPA/data-flow inventory.
2. Purpose and lawful-basis mapping.
3. Controller/processor/subprocessor roles.
4. Special-category/high-sensitivity processing conditions where applicable.
5. Privacy notices and just-in-time disclosures.
6. Data-subject rights workflow.
7. Retention/deletion schedule.
8. Deletion propagation across chat, memory, indexes/vectors, caches, checkpoints, backups and provider copies.
9. International-transfer register/mechanism.
10. DPIA triggers and templates.
11. Personal-data breach workflow.
12. Hosted-model/provider minimisation tests.
13. Privacy-by-default configuration tests.
14. UK GDPR/DPA 2018 overlay for UK contexts.

---

# 11. EU AI Act target state

Maintain an **AI Act applicability register** per product/deployment/use case covering:

- Raiker's legal role(s);
- intended purpose;
- prohibited-practice screening;
- high-risk classification where relevant;
- transparency duties;
- human oversight;
- logging/record keeping;
- cybersecurity/robustness obligations;
- provider/deployer operational duties;
- downstream responsibilities;
- whether Raiker itself qualifies for any GPAI-provider obligations (do not assume this merely because it integrates GPAI APIs/models).

Do not claim generic "EU AI Act compliant" status from architecture alone.

---

# 12. EU Cyber Resilience Act target state

## 12.1 Immediate action

Before 2026-09-11, determine and record whether Raiker's current/future EU distribution qualifies for Article 14 reporting obligations.

## 12.2 If applicable

Prepare:

- security contact/PSIRT ownership;
- single-reporting-platform readiness;
- 24-hour early-warning template;
- 72-hour notification template/process;
- final-report process;
- evidence/log preservation;
- supported product/version register;
- actively exploited vulnerability decision criteria;
- severe-incident decision criteria;
- coordinated communications/legal review workflow.

## 12.3 Longer-term CRA readiness

Before general application on 2027-12-11, maintain product-security requirements, secure development, vulnerability handling, update/support lifecycle, technical documentation and conformity evidence appropriate to Raiker's actual CRA category and distribution model.

---

# 13. Recommended implementation order

Order by **priority first, then effort/value**.

## Wave 0 — Immediate governance blockers

1. **P0:** no-authority-bypass invariant and CI enforcement.
2. **P1:** CRA applicability decision + Article 14 incident/vulnerability reporting readiness before 2026-09-11 if applicable.

## Wave 1 — High-priority / relatively bounded engineering

3. CSP.
4. streamed request-body limits/decompression limits.
5. canonical approval fingerprint + TOCTOU/replay protection tests.
6. explicit workflow permissions + CodeQL/dependency review/secret-scanning evidence.
7. PSIRT/`SECURITY.md`/emergency revocation procedures.

## Wave 2 — Core AI/data security planes

8. common DLP classification/decision layer.
9. destination-aware outbound DLP.
10. chunk-complete + multimodal injection scanning for model-bound context.
11. RAG/vector authorization + deletion/poisoning controls.
12. memory provenance/poisoning controls.
13. MCP identity/schema-drift/tool-poisoning controls.

## Wave 3 — Delegation and supply-chain hardening

14. explicit agent/subagent delegated-identity model.
15. multi-agent anti-amplification/fan-out controls.
16. AI/model supply-chain provenance/signature/quarantine controls.
17. secrets lifecycle + OS vault integration.
18. cryptographic/key-management architecture.
19. secure restore/checkpoint revalidation.

## Wave 4 — Assurance and governance evidence

20. OWASP Agentic Top 10 mapping.
21. NIST SP 800-218A SSDLC mapping.
22. MITRE ATLAS threat-control-test matrix.
23. ENISA multilayer AI cybersecurity mapping.
24. GDPR/UK GDPR accountability artifacts.
25. EU AI Act role/risk/transparency register.
26. full ASVS 5.0 verification.
27. adversarial AI security release suite and regression thresholds.

---

# 14. Release security gates

A production/public release should not be labelled "secure", "hardened" or broadly "compliant" unless the following evidence exists.

## Required technical gates

- no-authority-bypass CI invariant passes;
- security-critical capability registry is complete;
- CSP enabled for production web builds;
- actual streamed body limits enforced;
- DLP policy covers every outbound disclosure path;
- RAG retrieval authorization tests pass;
- memory-poisoning regression tests pass;
- MCP schema/tool-drift tests pass;
- approval replay/TOCTOU tests pass;
- subagent privilege attenuation tests pass;
- secret leakage regression suite passes;
- SSRF/DNS-rebinding regression suite passes;
- model-output rendering sanitization tests pass;
- resource/cost/fan-out limits are enforced;
- SAST/SCA/secret scanning/SBOM run clean or have approved exceptions;
- release artifacts have integrity/provenance evidence;
- backup/restore security tests pass.

## Required governance/operational gates

- supported security versions defined;
- vulnerability disclosure/PSIRT route active;
- incident-response playbooks maintained;
- CRA applicability recorded and time-sensitive duties operational where applicable;
- GDPR/UK GDPR data inventory + retention/deletion evidence maintained;
- AI Act role/risk applicability recorded;
- known security exceptions have owner, rationale and expiry.

---

# 15. Recommended documentation additions

Create/maintain the following under appropriate `docs/` locations (keeping planning documents under `docs/plans/`):

- `docs/security/SECURITY_ARCHITECTURE.md`
- `docs/security/AUTHORITY_INVARIANTS.md`
- `docs/security/DLP_ARCHITECTURE.md`
- `docs/security/OWASP_AGENTIC_TOP10_MAPPING.md`
- `docs/security/OWASP_LLM_TOP10_2026_MAPPING.md`
- `docs/security/OWASP_ACS_MAPPING.md`
- `docs/security/MITRE_ATLAS_MAPPING.md`
- `docs/security/MCP_SECURITY.md`
- `docs/security/RAG_MEMORY_SECURITY.md`
- `docs/security/MODEL_SUPPLY_CHAIN.md`
- `docs/security/SECRETS_AND_KEY_MANAGEMENT.md`
- `docs/security/AI_SECURITY_TESTING.md`
- `docs/compliance/GDPR_UK_GDPR_DATA_GOVERNANCE.md`
- `docs/compliance/EU_AI_ACT_APPLICABILITY.md`
- `docs/compliance/EU_CRA_APPLICABILITY.md`
- repository-root `SECURITY.md`

Architecture implementation plans should remain outside public GitHub if that is the repository documentation policy; public docs should contain the stable security contract and user/developer expectations, while `docs/plans/` contains remediation planning.

---

# 16. Reference sources

Authoritative/current reference set used for the assessment:

- OWASP GenAI Security Project — https://genai.owasp.org/
- OWASP Top 10 for Agentic Applications 2026 — https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
- OWASP Agent Control Standard — https://genai.owasp.org/resource/agent-control-standard-acs/
- OWASP GenAI data/MCP security resources — https://genai.owasp.org/initiatives/gen-ai-data-security/
- NIST SP 800-218 — https://csrc.nist.gov/pubs/sp/800/218/final
- NIST SP 800-218A — https://csrc.nist.gov/pubs/sp/800/218/a/final
- NIST AI RMF / GenAI Profile — https://www.nist.gov/itl/ai-risk-management-framework
- MITRE ATLAS — https://atlas.mitre.org/
- ENISA Multilayer Framework for Good Cybersecurity Practices for AI — https://www.enisa.europa.eu/publications/multilayer-framework-for-good-cybersecurity-practices-for-ai
- Google SAIF — https://saif.google/
- EU AI Act (Regulation (EU) 2024/1689) — https://eur-lex.europa.eu/eli/reg/2024/1689/oj
- EU GDPR — https://eur-lex.europa.eu/eli/reg/2016/679/oj
- EDPB — https://www.edpb.europa.eu/
- EU Cyber Resilience Act (Regulation (EU) 2024/2847) — https://eur-lex.europa.eu/eli/reg/2024/2847/oj
- European Commission CRA reporting guidance — https://digital-strategy.ec.europa.eu/en/policies/cra-reporting
- UK ICO — https://ico.org.uk/
- GitHub secure use of Actions — https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions

---

# 17. Final assessment

Raiker's strongest differentiator is already present: it is being built around an externalized authority/governance layer rather than relying on the model to decide what is safe.

The next maturity step is to **prove completeness across every authority, identity, data and provenance boundary** and to make those proofs regression-testable.

The second pass therefore changes the security roadmap from a conventional application/LLM hardening exercise into a broader **Raiker Security & Trust Baseline** covering:

- web/API security;
- agentic authority;
- DLP/privacy;
- RAG/memory security;
- MCP/plugin trust;
- delegated identity;
- model/software supply chain;
- multimodal/input/output security;
- cryptography/secrets/backup;
- incident/vulnerability response;
- GDPR/UK GDPR;
- EU AI Act;
- EU CRA;
- adversarial AI assurance.

Until the P0/P1 items have implementation evidence, the correct posture is **strong architecture with material assurance gaps**, not a claim of complete security or regulatory compliance.
