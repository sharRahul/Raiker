# Per-Turn Machine Identity Design

**Roadmap item:** ADD-03 — The agent needs its own identity, not the owner's

**Status:** Approved design, pending implementation

**Date:** 2026-08-08

## Purpose

Raiker currently authenticates the human at the API boundary and carries that
principal into the agent loop. Although the authority model already distinguishes
human, AI-agent, automation, and system principals, an ordinary Chat or Build turn
still brokers model-proposed work as the human owner. This mirrors the owner's
authority across the most important trust boundary in the product.

ADD-03 gives every agent turn its own short-lived, cryptographically verifiable
machine identity. The identity is strictly less privileged than the owner, is bound
to one workspace, owner, session, turn, and broker audience, and cannot be supplied
or changed by model output. Owner scope and acting identity become separate facts:
the agent can work within resources the owner delegated without being recorded or
governed as the owner.

## Goals

- Mint an Ed25519-signed machine attestation for every Chat, Build, scheduled, and
  resumed agent turn.
- Represent the subject with a SPIFFE-shaped identifier while keeping the issuer
  embedded and local-first.
- Verify the attestation at the Tool Broker before policy review or execution.
- Preserve the machine proposer and human authorizer as separate identities across
  tool actions, approvals, checkpoints, execution evidence, and audit events.
- Prevent a machine identity from receiving human-only authority, changing its own
  controls, approving its own work, or retrieving the owner's raw credentials.
- Show the human/agent authority distinction in Permissions, Approvals, and
  Observability.
- Preserve all existing capability gates, decision modes, confirmations, and
  owner-authoritative controls.

## Non-goals

- Running an external SPIRE control plane.
- Replacing local account authentication or API sessions.
- Implementing ADD-04 transaction lineage or automatic branch freezing.
- Creating a general-purpose certificate authority.
- Giving model code access to signing keys, raw attestations, or owner credentials.
- Changing which capabilities are enabled by default.
- Weakening approval or execution-time re-governance.

## Considered approaches

### Embedded per-turn Ed25519 issuer — selected

An embedded workspace issuer signs a bounded canonical payload for each turn. The
broker verifies the signature and every contextual binding. This is local-first,
creates the required cryptographic boundary, and leaves a narrow verifier interface
that can support an external SPIFFE/SPIRE implementation later.

### Per-session signed identity — rejected

This reduces issuance churn but makes a captured identity useful for the lifetime of
a conversation and weakens attribution when a session contains many turns.

### Database-only AI principal — rejected

The existing principal row is useful durable metadata, but a caller that knows its
identifier could impersonate it. A database lookup alone does not prove that the
trusted runtime minted the identity for this execution context.

## Architecture

### Embedded issuer

A focused identity module owns key provisioning, canonical serialization, signing,
verification, and reason codes. It uses Ed25519 from the existing `cryptography`
dependency. The workspace has one active issuer key at a time:

- the private seed is encrypted with Raiker's existing application-key encryption;
- the public key and opaque key ID are stored separately for verification;
- the private seed is never returned through an API, event, or model context;
- key creation is atomic and safe under concurrent first use;
- the verifier accepts only the explicitly active local issuer key.

The implementation exposes a small issuer/verifier protocol so a future external
SPIFFE provider can replace local signing without changing the broker contract.

### Attestation contract

The signed payload uses deterministic canonical JSON and contains only governance
metadata:

- schema version;
- issuer and key ID;
- SPIFFE-shaped subject;
- machine principal ID and principal type;
- delegated owner principal ID;
- workspace identity;
- session ID and turn ID;
- runtime role IDs;
- broker audience;
- issued-at and expires-at timestamps;
- unique token ID.

The subject has the logical form
`spiffe://raiker/<workspace-id>/agent/turn/<turn-id>`. The workspace component is a
stable opaque identifier rather than a filesystem path. No prompt, response, tool
arguments, credential, username, or file content enters the attestation.

### Turn lifecycle

At the trusted gateway/runtime boundary, starting a Chat, Build, scheduled, or
background turn creates an expiring `ai_agent` principal delegated by the authenticated
owner and mints its attestation. The model sees neither the signing input nor the
resulting token.

`ToolExecutionContext` carries the attestation alongside the session, turn, and
principal identifiers. Every broker call verifies the token before hooks, policy
review, credential resolution, approval creation, or execution. The verifier checks
signature, issuer, key ID, audience, time window, active principal, principal type,
owner delegation, workspace, session, and turn. A caller cannot override these values
through tool arguments.

A suspended turn may outlive a token. On continuation, the trusted runtime issues a
new short-lived attestation for the same turn-bound machine principal and records the
rotation. The token ID changes; the session, turn, delegated owner, and subject do not.
Reuse within the same live turn is expected because one turn brokers multiple tools.
Use in another workspace, session, turn, audience, or principal context is refused as
cross-context replay.

The principal becomes inactive when the turn reaches a terminal state. Durable audit,
approval, checkpoint, and source records continue to refer to its immutable identity.

### Owner scope and acting identity

The authenticated owner remains the resource owner and the only human authority. The
machine identity is the actor. Code that currently overloads one principal ID for both
purposes is split into explicit values:

- `acting_principal_id` identifies who proposed or performed work;
- `owner_principal_id` identifies the delegated resource scope.

Owner-scoped reads occur only after attestation verification and normal capability
governance. Storage queries receive the owner scope explicitly; audit and action rows
retain the machine actor. A missing or mismatched delegation fails closed instead of
falling back to an unscoped query.

### Credential boundary

Machine code never receives a provider API key, OAuth token, vault plaintext, or
connector credential. A governed provider or connector executor may use an owner's
credential internally only after:

1. the machine attestation verifies;
2. the delegation matches the credential owner;
3. the capability gate and decision mode permit the requested operation;
4. any required approval has been resolved by a human; and
5. the executor re-checks ownership immediately before use.

Supplying an owner credential or owner principal ID in model-controlled arguments does
not change the trusted scope and is rejected with a stable reason code when it conflicts
with the verified identity.

## Privilege model

The machine identity is always a strict subset of owner authority.

The machine may:

- use model-visible tools projected by the existing runtime;
- perform safe reads when existing gates and decision modes allow them;
- propose governed mutations and wait for human approval;
- use internal credential-backed executors without seeing credential material;
- create read-only child subagents within the already shipped delegation ceiling.

The machine may never:

- mint, rotate, export, or select an issuer key;
- create or activate its own principal;
- receive a human-only role;
- enable a capability gate or raise a decision mode;
- grant or widen a standing grant;
- resolve, approve, or reject an approval;
- satisfy human confirmation or step-up authentication;
- retrieve, echo, or directly present an owner's raw credential;
- change its owner, workspace, session, turn, role set, or audience;
- use an expired, inactive, invalid, or cross-context attestation.

Existing policy remains authoritative. Identity verification is an additional required
boundary, not a replacement for gates, policy review, approvals, containers,
checkpoints, or audit.

## Approvals and delayed execution

Approval creation records the machine principal, SPIFFE subject, token ID, issuer key
ID, turn, and attestation expiry as metadata. It stores no bearer token or signature.
The proposal hash continues to bind the immutable action.

Approval resolution records the human principal and approving API session separately.
A delayed approval does not require the original short-lived token to remain valid: the
token was verified when the immutable proposal was brokered. Execution trusts the
proposal hash, fresh human authorization, and execution-time governance. Events and UI
therefore state both facts without conflating them:

- proposed by the Raiker agent for turn X;
- approved by the human owner;
- executed through the approval relay under current gates and policy.

An altered proposal, inactive owner, revoked approval session, disabled gate, or failed
execution-time check remains a refusal even when the original proposal was valid.

## Subagents and scheduled work

Each subagent retains its distinct `ai_agent` principal and receives its own signed
attestation. The child identity records its parent machine principal and cannot exceed
the shipped read-only delegation subset. ADD-04 will later extend this relationship into
full input-to-output lineage; ADD-03 records identity ancestry only.

Scheduled work starts from an owner-authored task but executes under a fresh machine
identity for each run. The task owner remains the resource scope and approval recipient.
No durable automation row is treated as a human actor.

## API and event contract

API responses expose redacted identity metadata, never bearer material:

- principal ID and type;
- display label;
- SPIFFE subject;
- turn ID;
- issuer key ID;
- issued-at and expires-at times;
- active/expired state;
- delegated owner display label where authorized.

Stable refusal codes cover at least:

- `machine_identity_missing`;
- `machine_identity_malformed`;
- `machine_identity_unknown_issuer`;
- `machine_identity_unknown_key`;
- `machine_identity_invalid_signature`;
- `machine_identity_wrong_audience`;
- `machine_identity_expired`;
- `machine_identity_inactive_principal`;
- `machine_identity_principal_mismatch`;
- `machine_identity_delegation_mismatch`;
- `machine_identity_workspace_mismatch`;
- `machine_identity_session_mismatch`;
- `machine_identity_turn_mismatch`;
- `machine_identity_cross_context_replay`;
- `machine_identity_credential_scope_mismatch`.

Events record issuance, rotation, verification refusal, terminal deactivation, and the
machine/human identities attached to governed actions. Event payloads contain metadata
and reason codes only. Signature bytes, private keys, bearer tokens, credentials, prompt
text, and tool content are excluded and covered by redaction tests.

## User experience

### Permissions

Permissions presents an Owner/Agent authority matrix. The owner column shows that the
human may configure or approve a capability. The agent column derives one honest state
from the existing gate and decision mode: `Direct`, `Ask`, `Denied`, or `Unavailable`.
These are explanatory states, not a second set of controls. All mutations remain on the
owner's existing controls.

The page also shows the current/most recent machine identity with its turn, expiry, and
active state, and explains that an agent cannot alter its own authority.

### Approvals

Approval list and detail views display separate proposer and authorizer identity chips.
Pending approvals name the machine proposer and originating turn. Resolved approvals
also name the human decision maker. The raw principal IDs remain available in the
governance disclosure for correlation.

### Observability

Activity and session detail show machine identity metadata for each turn and distinguish
agent proposals, human decisions, and runtime execution. An identity refusal is visible
as a governed refusal with a plain-language next step and the stable reason code.

All new controls and disclosures are keyboard accessible, screen-reader labelled, and
usable at the existing responsive breakpoints and themes.

## Failure handling

Identity verification fails closed before any action, credential lookup, or external
effect. Refusals return a normal governed tool result so one invalid call is visible to
the model and owner instead of terminating the stream without explanation. The runtime
emits bounded metadata, not the rejected token.

Issuer provisioning failures prevent agent execution and direct the owner to Settings
or Diagnostics. They never fall back to the human principal or an unsigned machine
principal. A corrupted or missing private key cannot invalidate historic audit metadata;
it prevents new issuance until the owner repairs or rotates the issuer through a
human-only recovery path.

## Testing strategy

### Unit and integration tests

Tests follow red-green-refactor and cover:

- deterministic signing and successful verification;
- tampered payloads and signatures;
- unknown issuer/key and wrong audience;
- expiry and clock-boundary behavior;
- workspace, owner, principal, session, and turn mismatches;
- permitted same-turn reuse and refused cross-context replay;
- concurrent first-use key provisioning;
- encrypted private-key storage and redaction;
- trusted `ToolExecutionContext` binding that model arguments cannot override;
- machine privilege subset and every human-only operation;
- explicit owner-scoped resource resolution with no unscoped fallback;
- credential isolation and delegation mismatch;
- approval proposer/authorizer separation and delayed execution;
- scheduled, resumed, and subagent identity lifecycle;
- API/event serialization and secret scanning;
- Permissions, Approvals, and Observability accessibility and responsive rendering.

### Live provider acceptance

The live Playwright scenario starts a real `raiker-web`, enters credentials using the UI,
and exercises all providers requested for acceptance:

- Anthropic with the supplied short-lived API key;
- OpenRouter with the supplied short-lived API key;
- local Ollama using `gemma4:31b-cloud`.

For each provider, the scenario starts a genuine turn and verifies that:

1. the answer completes through the selected provider;
2. the turn has an active or completed machine identity bound to its session and turn;
3. a governed proposal, or a safe read where deterministic, is attributed to the machine;
4. Permissions shows the distinct Owner/Agent authority columns;
5. Approvals shows the machine proposer and human authorizer when the scenario raises an
   approval;
6. Observability shows issuance and action attribution without secret material; and
7. screenshots contain no API key or bearer token.

Screenshots are stored under `docs/plans/screenshots/working/` and indexed using the
existing screenshot documentation structure. Test-only keys are entered at runtime,
never written to source, shell history artifacts, fixtures, screenshots, or commits.

## Documentation contract

Implementation is not complete until current architecture and user documentation agrees
with the shipped identity boundary. The change updates every document whose facts are
affected, including:

- `docs/plans/TO_BE_ADDED.md` — mark ADD-03 shipped and record evidence;
- `docs/plans/TO_BE_FIXED.md` — record any defects found and their outcomes;
- `docs/ARCHITECTURE.md` — turn identity, broker boundary, and data flow;
- `docs/SECURITY_AND_POLICY.md` — privilege separation and owner authority;
- `docs/THREAT_MODEL.md` — spoofing, replay, key compromise, credential mirroring, and
  residual risks;
- `docs/TOOLS_AND_PERMISSIONS_SPEC.md` — identity verification and authority matrix;
- `docs/API_AND_CONTRACT_SCHEMAS.md` — redacted identity DTOs and refusal codes;
- `docs/EVENT_CATALOG.md` — issuance, rotation, refusal, and deactivation events;
- `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md` and
  `docs/NESTED_BOUNDARIES_ARCHITECTURE.md` — parent/child identity ancestry;
- `docs/FEATURE_COVERAGE_MATRIX.md` and `docs/IMPLEMENTATION_STATUS.md` — shipped state;
- `docs/WEB_APP_LIVE_TEST.md` — commands, provider evidence, screenshots, and results;
- relevant files under `docs/guide/` — the Owner/Agent distinction visible to users;
- `docs/plans/screenshots/README.md` — new visual evidence.

Documentation must retain each file's existing format and terminology. A final repository
search for stale claims that agent turns execute as the owner is part of verification.

## Security properties and residual risk

This design stops principal mirroring inside the governed Raiker runtime: model-proposed
work is no longer accepted merely because the API request began with an owner session.
It does not protect against a fully compromised host that can read both the encrypted
issuer seed and its application key, replace runtime code, or control the process. That
boundary belongs to later hardware and isolation roadmap items.

The embedded issuer is intentionally smaller than a SPIRE deployment. It provides local
cryptographic identity, contextual binding, expiry, and auditable attribution without
claiming network workload attestation or hardware-rooted key custody.

## Completion criteria

ADD-03 is complete only when:

- every agentic turn type uses a verified machine identity at the broker;
- no ordinary agent tool action is brokered as a human owner;
- human-only authority and raw credentials remain unreachable to machine identities;
- approvals and audit preserve separate proposer and authorizer identities;
- Permissions exposes the Owner/Agent authority matrix;
- focused tests, the full Python/web test suites, lint, type checks, and production build
  pass;
- Anthropic, OpenRouter, and Ollama live Playwright scenarios pass with reviewed
  screenshots;
- relevant documentation contains no stale owner-mirroring architecture claim;
- changes are committed and pushed to `origin/main`; and
- GitHub workflows for the pushed commit are green.
