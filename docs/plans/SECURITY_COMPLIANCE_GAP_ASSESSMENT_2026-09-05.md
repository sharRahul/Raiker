# Raiker Security & Compliance Gap Assessment — 2026-09-05

## Purpose

This plan records Raiker's current security posture against current application-security, AI/GenAI/agent-security, privacy, data-loss-prevention, supply-chain, and AI-governance expectations. It is a **static architecture/code/documentation assessment and remediation plan**, not a penetration test, legal opinion, certification, production configuration review, or proof of operational compliance.

The review uses implementation evidence as the primary source. Documentation-only claims are not treated as implemented controls unless a corresponding enforcement path exists.

## Benchmark set

Primary benchmarks reviewed for this assessment:

- OWASP Top 10:2025 and OWASP ASVS 5.0.0.
- OWASP API Security Top 10:2023.
- OWASP GenAI LLM Top 10:2026 (released 2026-08-03).
- OWASP Agent Control Standard (ACS, released 2026-09-01) and relevant OWASP GenAI/agentic security guidance.
- NIST AI RMF 1.0 and NIST AI 600-1 Generative AI Profile.
- MITRE ATLAS, including prompt-injection, agent-context/tool poisoning, tool invocation, credential discovery/misuse, AI-service data access/exfiltration, and AI supply-chain attack paths.
- Google Secure AI Framework (SAIF): input/output validation, least-privilege agent permissions, observability, red teaming, data controls and governance.
- OpenAI agent-security guidance: least privilege, explicit user confirmation for consequential actions, restricted app/tool access, prompt-injection resilience and monitoring.
- Microsoft AI security and Purview DLP practices: prompt-injection protection, sensitive-information classification, contextual DLP policy, audit/block/warn actions, endpoint/network controls.
- AWS security/DLP patterns including continuous sensitive-data discovery, findings, coverage reporting, encryption and retention.
- GitHub Actions secure-use guidance: least-privilege workflow permissions, immutable SHA pinning, secret protection, code scanning, dependency review and supply-chain controls.
- EU GDPR, particularly Arts. 5, 6, 12–22, 24–25, 28, 30, 32–36 and international-transfer obligations where applicable.
- Regulation (EU) 2024/1689 (EU AI Act), including provisions already applicable and the general application date of 2026-08-02; Article 50 transparency obligations now apply. Exact provider/deployer/GPAI/high-risk obligations depend on Raiker's actual placing-on-market and use cases and therefore require a formal role/applicability determination rather than assumptions from source code.
- EDPB Opinion 28/2024 on personal-data processing in the context of AI models.

## Status vocabulary

- **Aligned** — direct implementation evidence supports the control objective.
- **Partially aligned** — meaningful control exists but coverage, assurance, configuration or lifecycle completeness is missing.
- **Gap** — no sufficient implementation or governance evidence was identified for the stated objective.
- **Applicability TBD** — legal/product applicability depends on deployment, business role, data flows or intended-use facts not provable from the repository.
- **Operational evidence required** — code support exists but runtime configuration/process evidence is still required.

Priority:

- **P0** — release/public-exposure blocker or bypass of a core security boundary.
- **P1** — high-value security/compliance remediation for the next hardening cycle.
- **P2** — material defense-in-depth / assurance improvement.
- **P3** — maturity, evidence and operational-quality improvement.

---

# Executive assessment

Raiker already has an unusually strong **governed-agent architecture** for an open application: explicit runtime authority/capability mapping, approval and critical-confirmation concepts, tool/service capability gates, credential-aware redaction, event/audit concepts, checkpoint/recovery support, sandbox/container execution paths, web egress policy, source provenance and prompt-injection detection. These design choices align well with OWASP ACS, OWASP LLM/agentic guidance, Google SAIF and leading-provider advice that model output must never itself be an authority boundary.

The largest remaining risk is **control completeness and demonstrable assurance**, not the absence of a governance layer. A mature release posture now needs to prove that every ingress, model call, retrieved source, tool call, plugin, subagent, connector, network path, file mutation and outbound disclosure crosses enforceable policy boundaries, and that data-protection obligations are handled as lifecycle controls rather than only log redaction.

### Overall judgement

| Domain | Status | Summary |
|---|---|---|
| Agent authority / least privilege | **Aligned / verify exhaustiveness** | Strong central capability mapping and explicit approval constructs; add an automated no-bypass invariant for every executable capability. |
| Prompt injection / untrusted content | **Partially aligned** | Detection + provenance exists and does not pretend regex is a complete prevention layer; scanner sampling and adversarial assurance should be strengthened. |
| Tool / excessive-agency controls | **Aligned / verify exhaustiveness** | Capability gates and human confirmation design are strong; continuously prove new tools cannot execute outside authority routing. |
| Web / SSRF / egress | **Strongly aligned** | Public-address-only resolution and DNS-rebinding-aware transport are strong. Owner web posture is permissive-by-default for public internet and therefore needs outbound DLP/domain-risk policy above network reachability. |
| Authentication / session security | **Partially aligned** | Bearer/cookie distinction, revocation/expiry/scopes and CSRF handling are positive; complete ASVS verification remains required. |
| Browser hardening | **Partial / gap** | Useful response headers and conditional HSTS exist; no Content-Security-Policy was identified in the reviewed security-header middleware. |
| API abuse / resource consumption | **Partial** | Rate and declared body-size limits exist; actual streamed-byte enforcement and model/tool cost quotas need verification/strengthening. |
| DLP / sensitive-data protection | **Partial** | Strong secret/credential redaction exists, but DLP needs a broader classify → decide → block/warn/quarantine → audit lifecycle across prompts, RAG, tools and egress. |
| Secrets / credentials | **Strong partial** | Exact in-use secrets can be registered and redacted; repository/CI secret prevention and provider-secret lifecycle need continuous assurance. |
| Data-at-rest protection | **Strong partial** | SQLCipher-related CI posture is visible; key lifecycle, backup/export behavior, deletion propagation and recovery evidence must be formally controlled. |
| Logging / audit / observability | **Strong partial** | Architecture contains event/audit/security-finding mechanisms; define security-event taxonomy, retention, integrity verification and incident playbooks as measurable release criteria. |
| Supply chain / CI/CD | **Partial** | CI uses full SHA pins for reviewed GitHub actions and runs tests/lint/type checks/native tests; add explicit least-privilege permissions, CodeQL/SAST, dependency review/SBOM/provenance and secret-scanning evidence. |
| GDPR | **Partial / applicability-dependent** | Privacy-preserving technical controls exist, but repository evidence is not a substitute for ROPA, lawful-basis mapping, notices, rights workflows, processor/transfer records, DPIA criteria and breach procedures. |
| EU AI Act | **Partial / applicability TBD** | Human-governance, logging and security architecture are favorable; formal role/risk classification and current transparency/compliance artifacts are required now that most provisions and Article 50 apply. |
| MITRE ATLAS / adversarial assurance | **Partial** | Architecture addresses several ATLAS attack classes; establish a maintained ATLAS threat/control/test matrix and adversarial regression suite. |

---

# Confirmed strengths

## S-01 — Central runtime authority and explicit capability vocabulary

**Status: Aligned**

`raiker/runtime/authority/router.py` maps tools and high-impact services to explicit capability gates, including file/patch writes, memory mutation, git push, shell, remote/cloud execution, web access, plugins, hosted/private model runtimes, connectors, MCP, subagents, external channels and sensitive-domain runtimes. It also defines non-allow decisions and a critical-confirmation object intended to be produced only after human/step-up validation.

**Why this matters:** this is directly consistent with OWASP ACS and SAIF's requirement that agent permissions be bounded outside the model and that runtime actions remain controllable and auditable.

**Recommendation:** preserve this as a mandatory reference-monitor architecture. Make gate coverage machine-verifiable; never rely on developers remembering to add a capability mapping.

## S-02 — Prompt injection treated as an untrusted-data problem, not only a prompt-filter problem

**Status: Aligned design / partial assurance**

`raiker/security/injection_scan.py` detects instruction override, role impersonation, credential solicitation, exfiltration requests, tool coercion, approval bypass, hidden instructions and invisible-character techniques. Findings store redacted metadata/provenance rather than captured payload text. Importantly, the module states that detection is advisory and that structural authority/tool gates are the actual prevention boundary.

That is the correct security model: prompt injection cannot currently be considered “solved” by a classifier or system prompt.

## S-03 — SSRF and DNS-rebinding-aware web policy

**Status: Strongly aligned**

`raiker/runtime/web_policy.py` denies loopback, private, link-local, multicast, reserved and non-global addresses; handles IPv4-mapped IPv6 / alternate IP forms; blocks metadata/local naming patterns; validates all DNS answers and documents pinned transport to avoid validate-then-re-resolve DNS rebinding.

This is materially stronger than a simple hostname allow/deny check and maps well to OWASP SSRF/API unsafe-consumption controls.

## S-04 — Credential and sensitive-token redaction

**Status: Aligned for redaction objective**

`raiker/context/redaction.py` covers private keys, GitHub/OpenAI/AWS-like token shapes, bearer credentials, password/API-key assignments, email, card/account-style values, selected identifier patterns and a high-entropy fallback. It also supports an in-memory exact-secret registry so known credentials are removed even when their transformed output no longer resembles the original token format.

**Important limitation:** redaction is one DLP control, not a complete DLP programme.

## S-05 — Cookie CSRF handling and session/scoped authorization

**Status: Partial/positive**

`raiker/api/auth.py` distinguishes explicit bearer authorization from automatically attached browser cookies, applies CSRF validation to the cookie path, checks session revocation and expiry, resolves an active principal and validates required session scope.

## S-06 — Baseline HTTP hardening

**Status: Partial/positive**

`raiker/api/security.py` emits `X-Content-Type-Options`, frame denial, strict referrer policy, COOP/CORP and a restrictive Permissions-Policy; HSTS is available when the deployment is configured for it. It also provides API rate limiting and request-size handling.

## S-07 — CI action immutability and security-relevant testing

**Status: Partial/positive**

`.github/workflows/ci.yml` pins reviewed actions to full commit SHAs, runs the Python test suite, Ruff, mypy and compile checks, builds/tests the native runner on Linux and Windows, and verifies SQLCipher-related security characteristics.

This aligns with GitHub's immutable-action recommendation. The workflow still needs the broader CI/CD hardening controls listed below.

---

# Gaps and required improvements

## F-01 — Add an enforceable “no authority bypass” invariant

**Priority: P0 before claiming universal governance**  
**Status: Partially aligned**

A central router exists, but agent platforms regress when a new connector/tool/executor is added and directly invokes a side effect without the reference monitor.

### Required change

Create a generated registry/invariant test that fails CI when any executable capability can be reached without:

1. authenticated principal/session context where applicable;
2. capability-gate evaluation;
3. risk classification;
4. policy/decision-mode evaluation;
5. approval/critical confirmation when required;
6. scoped credential loan only after authorization;
7. audit event before/after execution;
8. output/redaction/DLP handling;
9. revocation/cancellation path where technically possible.

Include tools, MCP, plugins, skills, connectors, subagents, scheduled routines, external channels, shell/process, file/git writes, hosted models, network and future tool registries.

### Acceptance criterion

A deliberately introduced test tool that attempts a direct side effect outside the broker/router must cause CI to fail.

---

## F-02 — Content Security Policy not evidenced

**Priority: P1**  
**Status: Gap in reviewed HTTP middleware**

`raiker/api/security.py` provides several good security headers, but no `Content-Security-Policy` was identified in the reviewed response-header set.

### Required change

Implement a production CSP appropriate to the Vite/web application, preferably nonce/hash based and without `unsafe-eval`; minimize or remove `unsafe-inline`. Define explicit `default-src`, `script-src`, `style-src`, `img-src`, `font-src`, `connect-src`, `frame-ancestors`, `base-uri`, `form-action`, `object-src` and any worker/media needs. Keep `frame-ancestors 'none'` even though `X-Frame-Options: DENY` remains useful legacy defense.

Start in report-only mode only for migration/telemetry, then make enforcement a release criterion.

---

## F-03 — Request-size enforcement must cover actual streamed bytes

**Priority: P1**  
**Status: Partial**

The reviewed middleware rejects an excessive declared `Content-Length`, but a security boundary cannot assume every request supplies a truthful length. Chunked/streamed bodies and base64 expansion must be bounded by bytes actually consumed.

### Required change

- enforce cumulative receive-body limits independent of `Content-Length`;
- define separate caps for JSON, attachments, images/audio and connector payloads;
- apply decompression limits and expansion ratios;
- reject archive bombs/nested archives where archives are supported;
- enforce parser time/memory budgets;
- test missing, malformed and conflicting length/transfer encodings.

---

## F-04 — Prompt-injection scanning coverage can miss middle-of-document attacks

**Priority: P1**  
**Status: Partial**

The scanner intentionally examines a bounded window and for large text uses the head and tail. This can miss an indirect injection located in the middle of a long document.

### Required change

Use chunk-aware scanning tied to source provenance/RAG chunking. Every chunk actually offered to a model should be assessed, not necessarily every byte of a huge source. Preserve the current principle that a detector is advisory and never the authority boundary.

Add adversarial regression cases for:

- multilingual/encoded/obfuscated injection;
- Markdown/HTML comments and CSS-like hidden content;
- Unicode confusables/invisible characters;
- indirect injection in PDFs/web pages/code/issues/email;
- tool-result and MCP-result injection;
- context poisoning across memory/RAG;
- instruction splitting across chunks/turns;
- attempts to extract system instructions, credentials or connected-app data;
- approval social engineering.

---

## F-05 — Build a real DLP decision plane, not only redaction

**Priority: P1**  
**Status: Partial**

Raiker has useful sensitive-value redaction, but modern DLP requires classification and policy decisions before disclosure, not only masking data after it reaches a logging/output surface.

### Required control model

Implement a common `DataClassification` + `DlpDecision` layer used by:

- user prompt ingress;
- attachment/document ingestion;
- knowledge/RAG indexing and retrieval;
- memory writes and recall;
- model-provider requests;
- tool/connector arguments;
- web/network egress;
- email/chat/calendar payloads;
- clipboard/export/download where supported;
- logs, traces, crash reports and telemetry;
- plugin/MCP/subagent context sharing.

Minimum classifications should support configurable organization policy rather than hard-code legal conclusions: public, internal, confidential, restricted; credentials/secrets; personal data; special-category/high-sensitivity personal data; financial/payment data; health data; source code/IP; organization-defined exact/custom identifiers.

Minimum actions: allow, redact/tokenize, warn + require confirmation, block, quarantine, require a narrower destination/scope, or require explicit exception with reason and expiry.

### DLP design requirements

- destination-aware policy: local model vs approved private provider vs external SaaS must not be equivalent;
- purpose/context-aware disclosure minimization;
- per-field structured inspection rather than only regex over concatenated strings;
- custom data identifiers and allowlists/exceptions;
- detection confidence and false-positive handling;
- audit only metadata/classification, never unnecessarily persist the matched secret;
- policy simulation/dry-run mode;
- exception expiry and review;
- tests proving data cannot travel through a less-obvious alternate channel.

---

## F-06 — Outbound internet policy protects networks but not data destinations

**Priority: P1**  
**Status: Partial**

The public-address SSRF boundary is strong, but the owner blocklist posture means any public destination is network-reachable unless specifically blocked. For an agent capable of reading sensitive local/connected data, network reachability and disclosure authorization must be separate decisions.

### Required change

Keep the current SSRF guard, but add a higher-level egress policy that considers:

- destination trust/category;
- tool purpose;
- data classification being sent;
- user-requested destination vs destination originating in untrusted content;
- redirect chain;
- request method/content type;
- credential scope;
- approved domains for high-sensitivity disclosures;
- volume/rate anomaly.

A URL found inside untrusted content must never become sufficient authority to transmit user data to that URL.

---

## F-07 — Extend resource-consumption controls to model/tool economics and concurrency

**Priority: P1**  
**Status: Partial**

Per-IP fixed-window API limiting is useful but does not address LLM/API cost exhaustion or recursive agent/tool loops.

Add principal/session/turn limits for:

- concurrent runs;
- model tokens/cost and retries;
- tool calls;
- recursive subagent depth/fan-out;
- MCP/plugin calls;
- downloads and attachment expansion;
- web requests and redirects;
- command CPU/memory/time/disk/process counts;
- scheduled-run budgets.

On limit failure, fail closed for side effects and return a clear owner-visible reason.

---

## F-08 — Formalize supply-chain security beyond SHA-pinned Actions

**Priority: P1**  
**Status: Partial**

SHA-pinned actions are good. The repository should additionally make the following release controls explicit and machine-enforced:

- top-level/job-level minimal `permissions:` for `GITHUB_TOKEN`;
- CodeQL/SAST including GitHub Actions workflow analysis;
- dependency review on pull requests;
- Dependabot or equivalent dependency monitoring/update policy;
- secret scanning + push protection (repository setting evidence, not source only);
- Python/Rust/Node vulnerability scanning;
- SBOM for release artifacts;
- provenance/attestation and signed releases/artifacts where practical;
- locked/reproducible dependency inputs and documented update policy;
- plugin/MCP/skill package integrity, signature/hash/provenance policy;
- container base-image digest pinning and vulnerability scanning;
- protections for privileged workflow triggers and untrusted PR artifacts.

---

## F-09 — Formalize AI/agent red-team and MITRE ATLAS regression coverage

**Priority: P1**  
**Status: Gap in assurance artefacts**

Create `docs/threat-models/` and test mappings that explicitly cover relevant MITRE ATLAS and OWASP attack paths, including:

- direct and indirect LLM prompt injection;
- agent context poisoning;
- agent tool-data/tool poisoning;
- malicious MCP/plugin/tool metadata;
- unauthorized agent tool invocation;
- system/configuration discovery;
- credential discovery and alternate-authentication abuse;
- sensitive-data collection from AI services;
- exfiltration over web, connector, tool output, Git push and covert/encoded channels;
- model/provider supply-chain compromise;
- poisoned RAG/knowledge/memory;
- unsafe model output passed to shell/code/HTML/SQL/path interpreters;
- excessive agency / confused-deputy cases;
- recursive agents/self-replication/persistence;
- denial of wallet/service/resource exhaustion.

Every high-risk scenario needs a deterministic expected outcome: deny, approval, sanitize, isolate, alert or bounded safe execution.

---

## F-10 — GDPR accountability artifacts are incomplete/not established by code

**Priority: P1 if Raiker processes EU personal data in an applicable role**  
**Status: Applicability TBD / governance gap**

Technical controls such as encryption, redaction, access control and retention support help meet GDPR security/privacy-by-design objectives, but GDPR compliance cannot be inferred from them.

Create and maintain:

1. processing inventory / ROPA mapping data categories, purposes, data subjects, recipients, providers, locations and retention;
2. controller/processor/subprocessor role mapping for each operating model;
3. lawful-basis and, where relevant, special-category condition mapping;
4. privacy notice(s) and just-in-time disclosures;
5. data-subject rights workflow for access, correction, deletion, restriction, portability and objection where applicable;
6. retention/deletion schedule including derived indexes, memory, vector stores, audit logs, checkpoints, backups and provider copies;
7. processor contract/subprocessor and international-transfer register;
8. personal-data breach detection, assessment and notification procedure;
9. DPIA trigger and template; AI processing likely to create high risk must be assessed before use;
10. privacy-by-default verification tests, including minimization before sending context to hosted models/connectors.

EDPB Opinion 28/2024 should be considered for any model-development/deployment scenario involving personal data, including anonymity claims, legitimate-interest analysis and consequences of unlawfully processed training/deployment data.

---

## F-11 — EU AI Act role, risk and transparency classification must be explicit

**Priority: P1 now**  
**Status: Applicability TBD / governance gap**

The AI Act generally applies from **2026-08-02**, with earlier/later staged provisions. Article 50 transparency obligations also apply from 2026-08-02. Raiker must therefore have a documented applicability decision rather than a generic “AI Act compliant” statement.

### Required artifact

Create an AI Act applicability register that answers, per distribution/deployment mode:

- Is the project/entity a provider, deployer, importer/distributor, product manufacturer, downstream provider, or more than one role?
- Does Raiker place a GPAI **model** on the market, or does it consume third-party/local models as an AI **system**? Do not incorrectly inherit GPAI-model-provider duties merely because Raiker can call GPAI models.
- What intended uses are supported/prohibited?
- Can configuration produce a high-risk use under Annex III or Art. 6? If so, what product boundary/disclaimer/technical prevention applies?
- Are any prohibited-practice scenarios technically possible and how are they blocked by product policy?
- What Art. 50 transparency duties apply (e.g. informing people they are interacting with AI; generated/altered content obligations where applicable)?
- Which logging, human oversight, technical documentation, quality/risk management, robustness/cybersecurity, incident/post-market obligations apply to each role/use?
- Who owns AI literacy/training obligations and evidence?

Raiker's visible agent/governance UX should make human control and AI identity clear, but legal applicability must be signed off using actual product/distribution facts.

---

## F-12 — Complete ASVS/API verification instead of relying on framework defaults

**Priority: P2**  
**Status: Partial**

Run and document an ASVS 5.0-focused verification for the exposed web/API surface. At minimum verify:

- authentication/session lifecycle, MFA/step-up, password hashing, recovery/bootstrap;
- authorization on every object/function, not only route authentication;
- CSRF/CORS/origin controls;
- CSP and browser injection defenses;
- request parsing/content types/schema validation;
- file upload MIME/signature/size/decompression/path handling and malware policy;
- command/path/template/HTML injection boundaries;
- error handling with no secrets/internal stack exposure;
- cache behavior for sensitive pages/API data;
- TLS/HSTS public deployment rules;
- logging and alerting;
- API inventory/versioning/deprecation;
- resource consumption and SSRF;
- unsafe third-party API/connector consumption.

---

## F-13 — Define operational security evidence and release gates

**Priority: P2**  
**Status: Gap / operational evidence required**

A safe architecture can be deployed unsafely. Add a release/security evidence checklist covering:

- public bind/TLS/reverse-proxy posture;
- HSTS/CSP validation;
- secret-scanning/push-protection status;
- dependency/code/container scans;
- SBOM/provenance/signature verification;
- database encryption and key permissions;
- backup encryption + restore test;
- retention/deletion test;
- DLP/adversarial test results;
- event-integrity/audit verification;
- incident-response contact/process;
- approved provider/subprocessor list;
- data residency/transfer configuration;
- AI Act/GDPR applicability review date/owner.

---

# DLP control architecture target

Raiker should converge on the following invariant:

> **No sensitive datum is disclosed merely because a model generated a tool call or because untrusted content supplied a destination.** Every outbound transfer is authorized from trusted user intent, current capability authority, destination policy and data classification.

Suggested pipeline:

`SOURCE → provenance → normalize → classify → minimize → injection/content signals → policy decision → model/tool projection → authority gate → destination/egress DLP → execute → output validation → redact/log metadata`

For retrieved or connected data, preserve provenance and classification through transformations. Derived summaries should inherit the strongest relevant classification unless an approved declassification rule proves otherwise.

---

# Security test programme to add

## P1 automated suites

- authority-bypass/meta-registry test;
- indirect prompt-injection corpus test;
- RAG/memory context-poisoning test;
- sensitive-data exfiltration tests across **every** outbound-capable tool;
- malicious MCP/plugin schema/description/output test;
- SSRF redirect/DNS-rebinding/address-encoding test;
- streamed-body/decompression/resource-exhaustion test;
- shell/path/tool-argument injection test;
- approval replay/TOCTOU/intent-change test;
- credential-scope/loan/revocation/logging test;
- subagent capability-escalation and fan-out test;
- hosted-model context-minimization/DLP test;
- audit integrity and security-event test.

## P2 periodic/manual suites

- OWASP ASVS 5.0 verification;
- OWASP LLM Top 10:2026 + ACS control review;
- MITRE ATLAS adversarial exercise;
- provider-specific prompt injection/exfiltration testing;
- container/native sandbox escape assumptions review;
- backup/restore and deletion propagation exercise;
- incident-response tabletop including leaked provider token and prompt-injection-driven connector misuse.

---

# Priority execution order

The project should preserve the existing priority/effort principle: high-priority, low-effort controls first.

| Order | Work item | Priority | Effort |
|---:|---|---|---|
| 1 | Add explicit CSP and CSP tests | P1 | Low–Medium |
| 2 | Add streamed/body byte enforcement tests/fix | P1 | Medium |
| 3 | Add no-authority-bypass registry invariant | P0 | Medium |
| 4 | Add DLP decision contract and outbound enforcement points | P1 | High |
| 5 | Expand injection scanning to every model-consumed chunk + adversarial corpus | P1 | Medium |
| 6 | Add model/tool/subagent resource budgets | P1 | Medium |
| 7 | CI: explicit permissions, CodeQL/dependency/security scanning, SBOM/provenance | P1 | Medium |
| 8 | Add MITRE ATLAS/OWASP ACS threat-control-test matrix | P1 | Medium |
| 9 | Create GDPR processing/DPIA/rights/retention accountability pack | P1 if applicable | Medium |
| 10 | Create EU AI Act role/risk/transparency applicability register | P1 | Medium |
| 11 | Complete ASVS 5.0/API verification and evidence | P2 | High |
| 12 | Formalize release operational-security evidence | P2 | Medium |

---

# Release safety criteria

Raiker should not describe itself as “secure”, “GDPR compliant”, “EU AI Act compliant”, or “OWASP compliant” solely from this assessment. A defensible statement is narrower: the architecture implements controls aligned with specified framework objectives, while remaining gaps and applicability items are tracked here.

Before a security-focused release, require at minimum:

- no known path around runtime authority for side effects;
- all critical/high-impact actions have tested approval/step-up behavior;
- CSP and actual request-size limits enforced;
- public web/API exposure passes ASVS-focused checks;
- outbound-sensitive-data DLP exists at model/tool/connector/network boundaries;
- prompt-injection adversarial regression suite passes while authority remains fail-closed;
- CI/release supply-chain security controls pass;
- no exposed secrets and repository secret protection enabled;
- threat model current against OWASP LLM Top 10:2026, ACS and MITRE ATLAS;
- GDPR/EU AI Act role/applicability decisions documented for the intended release/distribution model;
- security incident and vulnerability disclosure paths tested/documented.

---

# Review cadence

Re-run this assessment:

- before each major release;
- whenever a new tool, connector, provider, plugin/MCP capability, subagent mode or external channel is introduced;
- when an execution boundary changes;
- following a material security incident;
- at least quarterly for OWASP/MITRE/provider guidance drift;
- on material EU AI Act/GDPR/EDPB guidance or legal changes.

The control matrix must be evidence-based: a documentation statement is not enough; cite the implementation and its tests, or mark the control as documentation-only/operational evidence required.
