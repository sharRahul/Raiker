---
name: security-review
description: Audit a change, a branch, or a whole component for exploitable security defects — injection, authentication and authorisation flaws, secret and PII exposure, unsafe deserialisation, weak cryptography, SSRF, path traversal, prompt injection and tool-permission escalation — and report only findings with a real exploit path. Use whenever someone says "security review", "is this safe", "can this be exploited", "audit this for vulnerabilities", "threat model this", "check this before we expose it", or asks about handling untrusted input, credentials, tokens, or file paths that come from a user. Use it as well when a change touches authentication, permissions, an approval gate, a sandbox boundary, an agent tool surface, or anything that parses data from outside the process. Do not use it for ordinary correctness review — code-review is aimed at that.
version: 1.0.0
---

# Security review

A security review that reports everything is indistinguishable from one that
reports nothing: both get skimmed. The output that changes an outcome is a short
list of findings, each with an exploit path someone could walk.

Two disciplines carry the whole review: **read the codebase's own security model
before judging a change against it**, and **require a demonstrable path from an
attacker-controlled input to the damage**.

## 1. Phase one — learn this codebase's security model

Before reading the change, find out how this project already defends itself.
Search for, and read:

- where untrusted input enters (request handlers, CLI arguments, file readers,
  webhook and queue consumers, tool arguments the model can write);
- the sanitisers, validators and escaping helpers that already exist, and where
  they are applied;
- how authentication and authorisation are expressed — decorators, middleware, a
  policy engine, a capability gate;
- how secrets are stored and read;
- the trust boundaries the project believes it has, usually stated in a threat
  model or security doc.

This phase is what stops the two commonest wrong findings: reporting a defence
the project implements elsewhere, and missing a defect precisely because you did
not know the pattern it broke.

## 2. Phase two — compare the change against that model

For each changed file, ask:

- Does it introduce a path that bypasses an existing validator, gate or escape?
- Does it re-implement a defence the project already has, differently — and
  therefore worse in some case?
- Does it widen a trust boundary: a new endpoint, a new parameter reaching a
  sink, a new file path from user data, a new outbound host, a new tool the
  model can call?
- Does it change *who* may do something, or *when* — a permission check moved,
  loosened, or made conditional?

A deviation from an established pattern is the single highest-yield signal in a
diff. Look for it explicitly.

## 3. Phase three — trace the data flow

Findings come from following a value, not from recognising a shape. For each
suspicious sink, trace backwards to a source you can name:

```
source (attacker-controlled)  →  transformations  →  sink (damage)
```

- **Sources**: request bodies, query strings, headers, cookies, path segments,
  uploaded filenames and content, environment on a shared host, database rows
  written by another user, model output, tool results, MCP server responses, and
  any document the agent was asked to read.
- **Sinks**: SQL and other query languages, shell and process execution, file
  paths, deserialisers, template renderers, HTTP clients, redirects, `eval`-alike
  constructs, log statements, and any place a permission is decided.
- **Transformations**: whether the value is validated, escaped, bound as a
  parameter, canonicalised, or type-narrowed — and whether that happens on
  *every* path to the sink, including error and retry paths.

The classes to sweep for are listed in `references/vulnerability-classes.md`,
with the sink shapes and the language-specific spellings. Read it while doing
this phase.

**Agent-specific classes deserve their own pass** and are the ones most often
missed: prompt injection reaching a tool call, a tool description that widens
authority, an approval gate that can be satisfied by model output, a sandbox
escape through a mounted path, an MCP server that can rewrite what the agent
believes it was asked to do. `references/vulnerability-classes.md` covers these
under *Agent and tool-surface classes*.

## 4. Severity and confidence

Severity is about consequence:

| Severity | Meaning |
|---|---|
| **High** | Directly exploitable: remote code execution, authentication bypass, privilege escalation, mass data disclosure. |
| **Medium** | Real impact, but needs specific conditions — a particular configuration, an authenticated foothold, a race won. |
| **Low** | Defence-in-depth: a missing hardening measure whose absence is not itself exploitable here. |

Confidence is about whether you are right:

| Confidence | Meaning |
|---|---|
| 0.9–1.0 | You traced source to sink. The exploit path is concrete. |
| 0.8–0.9 | A known-exploitable pattern with the guard demonstrably absent. |
| 0.7–0.8 | A suspicious pattern that needs conditions you have not verified. |
| < 0.7 | Do not report. |

**Report at 0.8 and above.** Below that, verify further or drop it. A wrong
security finding costs more than a missed low-severity one: it burns the
reviewer's credit for the finding that mattered.

## 5. Do not report these

Each is excluded because it reliably generates noise without changing a
decision:

- **Denial of service**, rate limiting, and resource exhaustion — including
  "unbounded loop", "no timeout", "large input could exhaust memory" — unless
  the change is *to* a rate limiter or quota mechanism itself.
- **Secrets that live on disk by design** in a local-first product: a key file
  the owner's own machine holds is the architecture, not a leak. A secret in
  source control, in a log line, in an error message, in a URL, or on a command
  line **is** a finding.
- **Theoretical issues with no exploitation path.** If you cannot name the
  source, it is not a finding.
- **Generic "missing input validation"** with no sink behind it.
- **Open redirects**, absent a concrete credential- or token-stealing path.
- **Vulnerable dependency versions** — a scanner reports those continuously and
  more accurately than a read of the lockfile.

## 6. Report shape

Every finding carries all of these, and a finding missing one of them is not
ready to report:

| Field | Content |
|---|---|
| `file` / `line` | Where the defect is, not where you noticed it |
| `severity` | high / medium / low |
| `category` | The class, e.g. `sql-injection`, `path-traversal`, `prompt-injection-to-tool-call` |
| `description` | The defect in one or two sentences |
| `exploit_scenario` | The concrete walk: what an attacker sends, what happens |
| `recommendation` | The specific fix, in this codebase's own idiom |
| `confidence` | 0.0–1.0, per the table above |

Order by severity, then confidence. State an empty result plainly — "no findings
at or above the reporting threshold", with the classes swept — rather than
padding it with low-severity observations.

`assets/finding-template.md` is the shape to fill in.

## In Raiker

This skill is instruction text: it changes how a review turn reasons and what it
reports. It grants nothing. The controls it works inside are the runtime's:

- **Reading code** stays within the workspace boundary; a path outside it is
  outside the review too.
- **Any write** — posting findings, opening an issue, applying a fix — is an
  approval-gated capability. A review proposes; the owner releases.
- **Findings are governed records**: what a review read and what it reported is
  reconstructable from the audit log afterwards.
- **Never put a live exploit in a finding** that runs against anything but a
  local fixture. Describe the path; do not fire it at a third party.

Raiker's own security specs are the house model this skill should read first
when reviewing Raiker itself: `docs/THREAT_MODEL.md`,
`docs/SECURITY_ARCHITECTURE.md`, `docs/OWASP_AGENTIC_TOP10_MAPPING.md`, and
`docs/USER_CENTRIC_ZERO_TRUST_POLICY.md`.

### Across agent surfaces

| Control | Elsewhere | In Raiker |
|---|---|---|
| Running a security pass | Claude Code `/security-review`; the security-review GitHub action; Codex review | Skills → activate, then ask for a security review |
| Scope of the audit | The PR diff, or a named path | The diff plus the workspace boundary the owner granted |
| Where findings land | PR review comments | The review output, plus the audit log; posting is a gated write |
| False-positive control | Exclusion list and a confidence floor | The same list and floor, in this document |
| Acting on a finding | Agent edits the branch | Fix proposed, approval gate released by the owner |
| Agent-surface classes | Rarely covered | A required pass: prompt injection, tool-permission escalation, sandbox and MCP boundaries |
