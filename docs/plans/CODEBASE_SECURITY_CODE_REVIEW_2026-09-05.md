# Raiker Codebase Security Code Review — 2026-09-05

## Purpose

This document records an implementation-focused security review of the Raiker codebase. It is intentionally separate from `SECURITY_COMPLIANCE_GAP_ASSESSMENT_2026-09-05.md`: that document maps Raiker to external standards; this document records concrete source-level findings, bypass primitives, assurance gaps, and positive security patterns.

This is a static source review, not a runtime penetration test. A finding does not automatically mean it is externally exploitable: exploitability may depend on gate state, owner configuration, deployment topology, or another control.

## Scope reviewed

Priority review covered runtime authority and approvals, command/process execution, MCP, plugins, model/provider execution, connectors, attachments, API hardening, executor registration and CI. Representative files reviewed include:

- `raiker/runtime/authority/critical.py`
- `raiker/runtime/authority/router.py`
- `raiker/runtime/executors/registry.py`
- `raiker/runtime/executors/__init__.py`
- `raiker/runtime/executors/tier1_approval.py`
- `raiker/runtime/command_policy.py`
- `raiker/runtime/executors/sandbox.py`
- `raiker/runtime/executors/mcp.py`
- `raiker/runtime/executors/tier4_plugins.py`
- `raiker/runtime/executors/models_runtime.py`
- `raiker/runtime/connectors.py`
- `raiker/runtime/attachments.py`
- `raiker/api/security.py`
- `.github/workflows/ci.yml`

Previously inspected `raiker/security/injection_scan.py`, `raiker/runtime/web_policy.py`, `raiker/context/redaction.py`, and `raiker/api/auth.py` were also considered where relevant.

## Executive judgement

Raiker is significantly more defensive than a typical agent wrapper. The command layer avoids `shell=True`; the approval relay binds execution to stored intent and re-routes approved work through governance; SSRF controls are explicit; attachment parsing is bounded and type-aware; plugin/container trust tiers are separated; and CI pins reviewed GitHub Actions to immutable SHAs.

The main code-level concern is **security-boundary consistency**. Some lower-level primitives can execute or transmit outside the strongest shared wrappers, while several components rely on the caller having already applied governance. These seams are the areas most likely to regress as Raiker gains capabilities.

| ID | Severity | Priority | Finding | Confidence |
|---|---|---:|---|---|
| CR-01 | High | P0 | No mechanical invariant proves every real executor is reachable only through the authority/reference-monitor path | High |
| CR-02 | High | P1 | MCP stdio child processes inherit the Raiker host environment | High |
| CR-03 | High | P1 | `enforce_modes=False` is an in-process connector governance-bypass primitive | High |
| CR-04 | High | P1 | Provider-backed embedding lacks mandatory trusted DLP/classification before provider disclosure | High |
| CR-05 | High | P1 | Bare plugin runtime permits arbitrary owner-allowlisted code with ambient host network access | High |
| CR-06 | High | P1 | API body-size middleware trusts declared `Content-Length` instead of actual bytes received | High |
| CR-07 | Medium | P1 | No enforced Content Security Policy was identified in HTTP middleware | High |
| CR-08 | Medium/High | P1 | Remote MCP HTTP transport does not use the shared public-address/SSRF policy | High |
| CR-09 | Medium | P1 | General-purpose interpreters remain in the governed command allowlist | High |
| CR-10 | Medium | P1/P2 | MCP security monitoring explicitly fails open on monitor/storage exceptions | High |
| CR-11 | Medium | P2 | Critical external-recipient classification relies on flat raw argument keys | Medium/High |
| CR-12 | Medium | P2 | CI lacks explicit minimal workflow permissions and dedicated security/supply-chain gates | High |
| CR-13 | Medium | P2 | Strong attachment parsing still requires universal downstream chunk injection/DLP enforcement | High |

---

## CR-01 — Governance exclusivity is not mechanically enforced

**Severity: High — Priority: P0 — Confidence: High**

`raiker/runtime/executors/__init__.py` exposes `REAL_EXECUTOR_CAPABILITIES` and builds a registry of real side-effecting executors. `ExecutorRegistry` itself simply stores and returns executors. Several lower-level services also document that a caller may already have passed governance.

The `RuntimeAuthority` architecture is strong, but the reviewed code does not make direct executor/service invocation impossible.

**Risk:** a future API handler, scheduled job, plugin, connector or helper can accidentally instantiate/retrieve a real executor and call it without the reference monitor.

**Recommendation:** require an opaque `AuthorityContext` issued by `RuntimeAuthority` for every side-effecting executor. Add CI that cross-checks `REAL_EXECUTOR_CAPABILITIES`, `CAPABILITY_GATE_MAP`, tools/connectors/MCP/plugins/scheduled actions and fails if a real executor is not governed.

**Acceptance:** a synthetic direct executor invocation without runtime-issued authority must fail before side effect.

---

## CR-02 — MCP stdio processes inherit host environment secrets

**Severity: High — Priority: P1 — Confidence: High**

`raiker/runtime/executors/mcp.py::_run_session()` launches the MCP server with `subprocess.Popen(...)` but does not supply `env`. The child therefore inherits the complete Raiker process environment.

This differs from `raiker/runtime/executors/sandbox.py::run_command()`, which deliberately constructs a minimal environment through `sandbox_environment()` to avoid leaking owner credentials.

Built-in MCP commands include Python and Node, and the owner can extend the command allowlist.

**Risk:** a malicious or compromised configured MCP server can read unrelated model keys, connector tokens or other process environment secrets.

**Recommendation:** run MCP stdio through the common sanitized process launcher or explicitly pass `sandbox_environment(workspace_root=self._ws)`. Add explicit per-server credential grants rather than ambient inheritance.

**Acceptance:** parent-process canary secrets such as `OPENAI_API_KEY` and `RAIKER_GITHUB_TOKEN` must not be visible inside MCP unless individually granted.

---

## CR-03 — Connector `enforce_modes=False` is a bypass primitive

**Severity: High — Priority: P1 — Confidence: High**

Methods in `raiker/runtime/connectors.py`, including GitHub operations, accept `enforce_modes: bool = True`. Passing `False` deliberately skips service-level gate and decision-mode checks because routed callers are expected to have already applied governance.

Credential, egress and argument checks remain, but authorization enforcement is bypassed by a normal boolean.

**Risk:** a future internal caller can accidentally or deliberately use the lower-level service outside the intended authority route.

**Recommendation:** remove the public boolean. Public service methods should always govern. A private post-authority method should require a runtime-issued typed authority token that ordinary action arguments cannot construct.

**Acceptance:** repository tests must prove `enforce_modes` cannot be supplied from action payloads and direct connector calls cannot skip authorization.

---

## CR-04 — Provider embedding lacks mandatory trusted DLP/classification

**Severity: High — Priority: P1 — Confidence: High**

`ModelProviderExecutor.execute()` accepts action-supplied `text`, `scope` and `sensitivity` for `embed` / `embed_query`. It checks that scope/sensitivity are strings but does not independently classify the text or require a trusted DLP result before a hosted/private provider call.

For `project_memory`, only exact sensitivity labels `secret_like` and `credential_like` are blocked. Other personal, confidential or regulated classes are not universally denied or sent through a destination-aware DLP decision.

The direct embedding path also stores `content_preview=text[:120]`, expanding retained source data.

**Risk:** misclassified sensitive content can be sent to a provider because classification is partly caller-controlled.

**Recommendation:** classify from content + provenance, use a trusted enum, inherit source classification, enforce destination-aware DLP, and minimize/remove plaintext vector previews for sensitive data.

**Acceptance:** data containing credentials, personal data, health data, source code or custom protected identifiers must not reach a hosted provider merely because the action labels it `public`.

---

## CR-05 — Bare plugin runtime has ambient network access

**Severity: High — Priority: P1 — Confidence: High**

`PluginRuntimeExecutor` executes arbitrary code from an installed and owner-allowlisted plugin through the shared subprocess runner. Its own documentation contrasts this with `PluginSandboxedRuntimeExecutor`, which is network-isolated.

The shared runner sanitizes environment variables, but it does not create a network namespace or force network through Raiker's egress broker.

**Risk:** a malicious, compromised or later-substituted allowlisted plugin can use Python/Node socket/network libraries directly and bypass connector/web DLP/egress policy.

**Recommendation:** make the network-isolated sandboxed plugin runtime the default. Treat the bare runtime as an explicitly dangerous/developer capability. Revalidate plugin artifact hash/version immediately before execution.

**Acceptance:** an allowlisted plugin must not be able to perform DNS/TCP/HTTPS unless a separate governed network capability explicitly authorizes it.

---

## CR-06 — Request body limit checks only declared `Content-Length`

**Severity: High — Priority: P1 — Confidence: High**

`MaxBodySizeMiddleware` in `raiker/api/security.py` rejects an excessive declared `Content-Length`, but it does not wrap ASGI `receive()` and count actual `http.request.body` bytes.

Missing or malformed lengths therefore bypass this middleware's intended size boundary; a malformed length is treated as `0`.

**Risk:** depending on reverse-proxy/ASGI-server limits, oversized streamed/chunked requests can produce memory, CPU, parser or storage pressure beyond the configured application limit.

**Recommendation:** keep `Content-Length` as an early-reject optimization, but enforce the limit against cumulative bytes actually received.

**Acceptance:** oversized bodies with no length, an understated length, or malformed length must fail at the same path-specific limit.

---

## CR-07 — Browser responses lack Content Security Policy

**Severity: Medium — Priority: P1 — Confidence: High**

`raiker/api/security.py` sets `nosniff`, frame denial, referrer policy, COOP/CORP, Permissions-Policy and optional HSTS. No `Content-Security-Policy` was identified in `_SECURITY_HEADERS` or `SecurityHeadersMiddleware`.

**Risk:** a future XSS/model-output rendering defect has no CSP defense layer restricting scripts, connections, forms, frames and embedded objects.

**Recommendation:** deploy a production nonce/hash-based CSP including explicit `default-src`, `script-src`, `style-src`, `img-src`, `font-src`, `connect-src`, `object-src 'none'`, `base-uri`, `form-action` and `frame-ancestors 'none'`.

---

## CR-08 — Remote MCP transport is weaker than normal web SSRF policy

**Severity: Medium/High — Priority: P1 — Confidence: High**

`raiker/runtime/executors/sandbox.py::post_json_rpc()` validates only an HTTP(S) scheme + netloc. Its documentation intentionally treats “the owner adding the URL” as authorization and applies no destination allowlist/public-address policy.

This is materially weaker than `web_policy.py`, which rejects private/loopback/link-local/metadata/non-global targets and accounts for DNS rebinding.

Remote MCP in `raiker/runtime/executors/mcp.py` uses this transport and may attach an owner bearer token.

**Risk:** an MCP configuration becomes a privileged internal-network path. That can be intentional for local/private MCP, but the trust class is not structurally separated from public remote MCP.

**Recommendation:** distinguish local/private MCP from remote/public MCP. Public remote MCP should use the shared resolve/pin/SSRF policy plus destination trust/DLP. Private MCP should require an explicit private-network grant bound to the approved endpoint.

---

## CR-09 — General-purpose interpreters remain in the command allowlist

**Severity: Medium — Priority: P1 — Confidence: High**

`DEFAULT_ALLOWED_BINARIES` includes `python`, `python3`, `node`, `npm` and `npx`. Inline execution flags are sensibly denied, and paths are confined to the workspace, but running an interpreter against a script in an agent-writable workspace is still arbitrary code execution.

**Risk:** command validation can be mistaken for an execution sandbox even though scripts can perform operations the command parser cannot see.

**Recommendation:** split read-only command capability from arbitrary workspace-code execution. Route interpreter execution through the stronger OS/container sandbox and network policy.

---

## CR-10 — MCP monitoring is explicitly fail-open

**Severity: Medium — Priority: P1/P2 — Confidence: High**

`McpConnectorExecutor._observe()` catches all exceptions from `self._monitor.observe(...)` and continues the successful session.

**Risk:** ordinary telemetry may reasonably fail open, but if monitoring drives security findings/auto-pause containment, the system continues precisely while that security control is unavailable.

**Recommendation:** separate optional observability from security-critical containment. When MCP security monitoring is unhealthy, autonomous execution should degrade to pause/ask rather than silently continue.

---

## CR-11 — Critical recipient logic depends on raw field names

**Severity: Medium — Priority: P2 — Confidence: Medium/High**

`raiker/runtime/authority/critical.py` extracts external destinations only from flat keys: `to`, `recipient`, `recipients`, `attendee`, `attendees`, `cc`, `bcc`.

**Risk:** a future connector using nested/structured recipients or a new field name could produce an empty extracted recipient set and miss critical elevation.

**Recommendation:** normalize every send/invite into a canonical typed destination contract before risk classification. If destinations cannot be resolved, fail closed rather than treating the action as non-critical.

---

## CR-12 — CI lacks explicit least-privilege token permissions and dedicated security gates

**Severity: Medium — Priority: P2 — Confidence: High**

`.github/workflows/ci.yml` positively pins `actions/checkout` and `actions/setup-python` to immutable commit SHAs and runs broad Python/Rust quality and SQLCipher posture checks.

However, the reviewed workflow does not declare explicit top-level/job `permissions:` and does not include dedicated CodeQL/SAST, dependency review, SBOM, dependency vulnerability or provenance/attestation gates.

**Recommendation:** default CI to `permissions: contents: read`, elevate only where necessary, and add dedicated supply-chain/security jobs.

---

## CR-13 — Attachment parser safety does not complete semantic content safety

**Severity: Medium — Priority: P2 — Confidence: High**

`raiker/runtime/attachments.py` is strong on file safety: media allowlists, magic checks, size caps, PDF validation, bounded OOXML decompression, DTD rejection, bounded XLSX extraction and macro-enabled formats excluded.

Extracted content is intentionally marked untrusted. The residual issue is downstream: file-format validation does not neutralize prompt injection or data-classification risk.

**Recommendation:** make it a tested invariant that every extracted chunk actually supplied to a model receives provenance, injection signals, data classification and destination-aware DLP, regardless of source format.

---

# Positive observations to preserve

## CR-P01 — Approval relay has strong replay/TOCTOU controls

`ApprovalExecutionRelay` implements approval TTL, immutable action payload hashing, degraded/revoked posture checks, an atomic `pending → executing` claim, critical lifecycle enforcement, re-routing through `RuntimeAuthority` at execution time, and narrowing-only partial patch acceptance. This is a strong pattern for all delayed approved actions.

## CR-P02 — Shared command runner intentionally strips ambient credentials

`command_policy.py` and `sandbox.py` provide strong controls: argv execution without shell, shell syntax/expansion/chaining rejection, dangerous binary flag denial, workspace containment, protection for `.raiker`/`.git`, constructed child environment, Git config suppression, timeout and output caps.

CR-02 is important specifically because MCP stdio does not currently reuse this boundary.

---

# Cross-cutting recommendations

1. **Typed authority context:** replace “caller already governed” conventions and boolean bypasses with a runtime-issued `AuthorityContext`.
2. **Single process launcher:** MCP, plugin, shell/process and future code runtimes should converge on one launcher controlling env, filesystem, network, process tree, resource budgets, credential loans and cancellation.
3. **Unified egress broker:** web, connectors, model providers, MCP and plugins should share a destination-class/DLP layer even if each retains different allow rules.
4. **Canonical action schemas:** risk classification should consume typed destinations/targets, not loosely inspect arbitrary dictionaries.
5. **Security monitor health:** if monitoring participates in containment, its health must influence whether autonomous execution is permitted.

# Priority / effort order

Following Raiker's priority/effort rule:

| Order | Finding | Priority | Effort |
|---:|---|---:|---|
| 1 | CR-02 sanitize MCP environment | P1 | Low |
| 2 | CR-06 enforce actual streamed body bytes | P1 | Low-Medium |
| 3 | CR-07 CSP | P1 | Low-Medium |
| 4 | CR-03 remove boolean connector bypass | P1 | Medium |
| 5 | CR-01 authority-only executor invariant | **P0** | Medium |
| 6 | CR-04 trusted embedding DLP/classification | P1 | Medium-High |
| 7 | CR-08 MCP endpoint network-class policy | P1 | Medium |
| 8 | CR-05 default plugin execution to isolated runtime | P1 | Medium |
| 9 | CR-09 split read commands from arbitrary code | P1 | Medium |
| 10 | CR-10 monitor-health fail-safe | P1/P2 | Medium |
| 11 | CR-11 canonical recipient normalization | P2 | Medium |
| 12 | CR-12 CI security/supply-chain gates | P2 | Medium |
| 13 | CR-13 universal attachment chunk injection/DLP | P2 | Medium-High |

CR-01 remains the highest release-significance item even though several lower-effort P1 hardening changes can be completed immediately while the P0 invariant is designed.

# Proposed release-blocking invariants

Before claiming universal governed execution, CI should prove:

1. no side-effecting executor runs without runtime-issued authority;
2. no child process inherits the Raiker host environment wholesale;
3. no off-machine disclosure of non-public data occurs without a destination-aware DLP decision;
4. plugin/MCP/tool code cannot gain uncontrolled network access by selecting a different execution path;
5. executed actions remain structurally bound to what the human approved and current posture is re-evaluated;
6. actual bytes/tokens/processes/tool calls are bounded, not only declared metadata;
7. failure of security-critical monitoring cannot silently increase autonomous authority;
8. critical risk classification consumes canonical typed targets/destinations.

# Review limitations and next verification stage

This source review should not be represented as exhaustive proof that no other defects exist. The next verification stage should include automated repository-wide queries for unsafe process/network/deserialization primitives, call-graph proof of executor routing, negative egress tests, approval concurrency/replay testing, fuzzing of paths/URLs/redirects/recipient schemas, resource-exhaustion tests, dependency/SBOM analysis, native sandbox review on Linux/Windows, and authenticated API dynamic security testing.
