# Per-Turn Machine Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Broker every agentic turn under a short-lived, Ed25519-signed machine identity that is visibly and enforceably distinct from the human owner.

**Architecture:** A local workspace issuer mints canonical signed attestations bound to owner, workspace, session, turn, principal, and broker audience. `AgentGateway` owns the turn identity lifecycle, `RuntimeOrchestrator` passes a trusted identity context, and `ToolBroker` verifies it before policy, credential resolution, approval creation, or execution. Owner resource scope remains explicit while action, approval, checkpoint, and event attribution uses the machine actor.

**Tech Stack:** Python 3.11, `cryptography` Ed25519/Fernet, SQLite migrations, FastAPI, Svelte 5, TypeScript, Vitest/Testing Library, Playwright CLI/test runner.

## Global Constraints

- Keep the embedded issuer local-first; do not require an external SPIRE service.
- Preserve all existing capability gates, decision modes, confirmations, checkpoints, containers, and approvals.
- Never expose private keys, bearer attestations, raw provider keys, OAuth tokens, prompts, tool content, or filesystem paths in identity metadata.
- A machine identity may not mint identities, acquire human-only roles, configure gates, raise decision modes, approve work, satisfy step-up, or retrieve raw credentials.
- Bind every attestation to one workspace, delegated owner, machine principal, session, turn, and `tool_broker` audience.
- Treat owner scope and acting identity as separate required values; never fall back from a delegation mismatch to an unscoped query.
- Delayed approval execution uses the verified immutable proposal plus fresh human authorization; it does not preserve or replay the original bearer attestation.
- Use stable machine-readable refusal codes and fail closed before policy review, credential lookup, or external effects.
- Follow the existing document format and update every maintained document whose architecture statement changes.
- Enter live Anthropic and OpenRouter keys through the UI only; use Ollama `gemma4:31b-cloud`; never commit, log, or screenshot secrets.

---

## File Structure

### New focused modules

- `raiker/runtime/identity/__init__.py` — public machine-identity interfaces.
- `raiker/runtime/identity/contracts.py` — attestation claims, verified context, canonical encoding, and refusal type.
- `raiker/runtime/identity/issuer.py` — encrypted workspace key provisioning and Ed25519 minting.
- `raiker/runtime/identity/verifier.py` — signature and contextual verification.
- `raiker/runtime/identity/lifecycle.py` — turn principal issuance, rotation, and terminal deactivation.
- `tests/test_machine_identity.py` — cryptographic and persistence behavior.
- `tests/test_machine_identity_turns.py` — gateway, broker, approval, resume, scheduled, and subagent integration.
- `apps/web/src/lib/components/AuthorityMatrix.svelte` — read-only Owner/Agent capability explanation.
- `apps/web/src/lib/components/IdentityChip.svelte` — accessible principal attribution used by Approvals and Activity.
- `apps/web/e2e/add-03-machine-identity-providers-live.spec.ts` — three-provider live acceptance.
- `docs/threat-models/machine-identity.md` — ADD-03 threat model and residual risk.

### Existing modules to modify

- `raiker/storage/migrations.py`, `raiker/storage/sqlite.py` — issuer, machine identity, and proposal-attribution persistence.
- `raiker/gateway/agent_gateway.py`, `raiker/runtime/orchestrator.py`, `raiker/runtime/turn_suspension.py`, `raiker/tasks/scheduler.py`, `raiker/agents/orchestration.py` — lifecycle propagation.
- `raiker/tools/broker.py`, connector/provider credential boundaries, and approval execution — verification and scope separation.
- `raiker/control/dtos.py`, `raiker/control/dashboard.py`, API routes/schemas — redacted identity views.
- `apps/web/src/lib/api.ts`, `apps/web/src/lib/apiTypes.ts`, `CapabilitiesView.svelte`, `ApprovalsView.svelte`, `ActivityView.svelte` and tests — visible authority separation.
- Architecture, security, contract, roadmap, guide, live-test, and screenshot documentation named in the approved specification.

---

### Task 1: Signed Identity Contract and Encrypted Workspace Issuer

**Files:**
- Create: `raiker/runtime/identity/__init__.py`
- Create: `raiker/runtime/identity/contracts.py`
- Create: `raiker/runtime/identity/issuer.py`
- Create: `raiker/runtime/identity/verifier.py`
- Modify: `raiker/storage/migrations.py`
- Modify: `raiker/storage/sqlite.py`
- Test: `tests/test_machine_identity.py`

**Interfaces:**
- Produces: `MachineIdentityClaims`, `MachineAttestation`, `VerifiedMachineIdentity`, `MachineIdentityError`, `WorkspaceIdentityIssuer.mint(...)`, and `MachineIdentityVerifier.verify(...)`.
- Produces storage methods: `get_or_create_workspace_identity()`, `get_machine_issuer_key()`, `save_machine_issuer_key()`, `insert_turn_machine_identity()`, `rotate_turn_machine_identity()`, and `deactivate_turn_machine_identity()`.

- [ ] **Step 1: Write failing migration and signing tests**

```python
def test_minted_identity_is_bound_to_workspace_owner_session_turn_and_audience(tmp_path):
    store = SQLiteStore(tmp_path)
    issuer = WorkspaceIdentityIssuer(tmp_path, store)
    token = issuer.mint(
        owner_principal_id="principal_owner",
        session_id="sess_1",
        turn_id="turn_1",
        role_ids=("assistant",),
        ttl_seconds=300,
    )
    verified = MachineIdentityVerifier(tmp_path, store).verify(
        token,
        expected_owner_principal_id="principal_owner",
        expected_session_id="sess_1",
        expected_turn_id="turn_1",
        expected_audience="tool_broker",
    )
    assert verified.claims.principal_type == "ai_agent"
    assert verified.claims.subject.startswith("spiffe://raiker/")
```

Add literal negative cases for tampered payload/signature, unknown key, wrong audience, expiry, inactive principal, owner/workspace/session/turn mismatch, permitted same-context reuse, and refused cross-context use. Add a concurrency test asserting that two first-use issuers produce one active key.

- [ ] **Step 2: Run tests and verify the expected failure**

Run: `.venv\Scripts\python.exe -m pytest tests/test_machine_identity.py -q`

Expected: collection fails because `raiker.runtime.identity` does not exist.

- [ ] **Step 3: Add the `RAIKER-1039-machine-identities` migration**

```sql
CREATE TABLE IF NOT EXISTS machine_identity_issuers (
  workspace_id TEXT PRIMARY KEY,
  key_id TEXT NOT NULL UNIQUE,
  public_key BLOB NOT NULL,
  private_key_encrypted BLOB NOT NULL,
  created_at TEXT NOT NULL,
  rotated_at TEXT,
  is_active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS turn_machine_identities (
  principal_id TEXT PRIMARY KEY,
  owner_principal_id TEXT NOT NULL,
  workspace_id TEXT NOT NULL,
  session_id TEXT NOT NULL,
  turn_id TEXT NOT NULL,
  subject TEXT NOT NULL,
  key_id TEXT NOT NULL,
  token_id TEXT NOT NULL,
  issued_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  parent_principal_id TEXT,
  is_active INTEGER NOT NULL DEFAULT 1
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_turn_machine_identity_context
  ON turn_machine_identities(workspace_id, session_id, turn_id, principal_id);
```

Register the migration in the existing ordered migration table and implement atomic read/write helpers in `SQLiteStore`.

- [ ] **Step 4: Implement canonical claims, signing, and verification**

```python
@dataclass(frozen=True)
class MachineIdentityClaims:
    version: int
    issuer: str
    key_id: str
    subject: str
    principal_id: str
    principal_type: str
    owner_principal_id: str
    workspace_id: str
    session_id: str
    turn_id: str
    role_ids: tuple[str, ...]
    audience: str
    issued_at: str
    expires_at: str
    token_id: str

class MachineIdentityError(ValueError):
    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)
```

Use sorted, separator-minimized UTF-8 JSON for the signed payload; a versioned `payload.signature` URL-safe encoding; Ed25519 raw keys; `app_fernet(workspace_root)` for private-seed encryption; and `hmac.compare_digest` where identifier comparisons need constant-time behavior. The verifier returns only claims plus a SHA-256 token fingerprint, never the bearer token.

- [ ] **Step 5: Run focused tests to green**

Run: `.venv\Scripts\python.exe -m pytest tests/test_machine_identity.py -q`

Expected: all identity tests pass with no warnings.

- [ ] **Step 6: Commit the identity foundation**

```powershell
git add -- raiker/runtime/identity raiker/storage/migrations.py raiker/storage/sqlite.py tests/test_machine_identity.py
git commit -m "feat: issue signed turn identities"
```

---

### Task 2: Turn Lifecycle and Trusted Context Propagation

**Files:**
- Create: `raiker/runtime/identity/lifecycle.py`
- Modify: `raiker/gateway/agent_gateway.py`
- Modify: `raiker/runtime/orchestrator.py`
- Modify: `raiker/runtime/turn_suspension.py`
- Modify: `raiker/tasks/scheduler.py`
- Modify: `raiker/agents/orchestration.py`
- Modify: `raiker/events/types.py`
- Test: `tests/test_machine_identity_turns.py`

**Interfaces:**
- Consumes: Task 1 issuer/verifier and storage methods.
- Produces: `TurnMachineIdentityLifecycle.start(...)`, `.rotate(...)`, `.finish(...)`, and `TrustedTurnIdentity` carried by the orchestrator.

- [ ] **Step 1: Write failing lifecycle tests**

```python
async def test_gateway_uses_machine_identity_for_every_model_tool_call(workspace, owner):
    gateway = AgentGateway(workspace, principal_id=owner)
    response = await gateway.submit_prompt_async(envelope_with_read_tool())
    action = SQLiteStore(workspace).latest_tool_action(response.turn_id)
    assert action["principal_id"].startswith("principal_turn_agent_")
    assert action["principal_id"] != owner

def test_resumed_turn_rotates_token_without_changing_machine_subject(workspace):
    before = load_identity_for_turn(workspace, "turn_1")
    resume_suspended_turn(workspace, "turn_1")
    after = load_identity_for_turn(workspace, "turn_1")
    assert after["subject"] == before["subject"]
    assert after["token_id"] != before["token_id"]
```

Add scheduled-turn and subagent-parent tests using real stores and local deterministic providers. Assert terminal turns deactivate identities and suspended turns remain attributable.

- [ ] **Step 2: Run tests and verify failure because gateway still brokers as owner**

Run: `.venv\Scripts\python.exe -m pytest tests/test_machine_identity_turns.py -q`

Expected: assertions observe the owner principal or missing identity events.

- [ ] **Step 3: Implement lifecycle ownership in `AgentGateway`**

Create the machine identity in `_prepare_turn`, attach a `TrustedTurnIdentity` to the runtime call, emit `machine_identity_issued`, and call `finish` only for terminal outcomes. Keep the human principal for session ownership, model credential selection, interrupts, and UI authentication.

```python
identity = self.machine_identities.start(
    owner_principal_id=self.owner_principal_id,
    session_id=envelope.session_id,
    turn_id=envelope.turn_id,
    role_ids=self._roles_for_client(envelope.client.type),
)
response = await self.runtime.ahandle(envelope, identity=identity)
```

- [ ] **Step 4: Propagate identity through ordinary, resumed, scheduled, and child turns**

Change orchestrator entry points and every `tool_broker.execute(...)` call to require the trusted identity. Resume rotates the bearer identity before executing queued calls. Scheduler creates a fresh machine identity for each run. Subagents set `parent_principal_id` and remain inside `DELEGABLE_TOOLS`.

- [ ] **Step 5: Declare lifecycle events and verify the static event invariant**

Add `machine_identity_issued`, `machine_identity_rotated`, `machine_identity_refused`, and `machine_identity_deactivated` to the event catalogue in code. Payloads contain IDs, timestamps, audience, and reason codes only.

Run: `.venv\Scripts\python.exe -m pytest tests/test_machine_identity_turns.py tests/test_declared_event_types.py -q`

- [ ] **Step 6: Commit lifecycle propagation**

```powershell
git add -- raiker/runtime/identity/lifecycle.py raiker/gateway/agent_gateway.py raiker/runtime/orchestrator.py raiker/runtime/turn_suspension.py raiker/tasks/scheduler.py raiker/agents/orchestration.py raiker/events/types.py tests/test_machine_identity_turns.py
git commit -m "feat: bind machine identities to turns"
```

---

### Task 3: Broker Verification, Privilege Separation, and Credential Scope

**Files:**
- Modify: `raiker/tools/broker.py`
- Modify: `raiker/runtime/authority/router.py`
- Modify: `raiker/runtime/connector_ecosystem.py`
- Modify: `raiker/tools/connector_tools.py`
- Modify: `raiker/models/connections.py`
- Modify: `raiker/runtime/executors/connectors.py`
- Test: `tests/test_machine_identity_turns.py`
- Test: `tests/test_tool_broker.py`
- Test: `tests/test_connector_ecosystem.py`
- Test: `tests/test_github_connector.py`
- Test: `tests/test_gmail_connector.py`
- Test: `tests/test_gcal_connector.py`
- Test: `tests/test_slack_connector.py`
- Test: `tests/test_api_model_selection.py`

**Interfaces:**
- Consumes: `TrustedTurnIdentity` and `MachineIdentityVerifier`.
- Produces: `ToolExecutionContext(session_id, turn_id, acting_principal_id, owner_principal_id, verified_identity)` and stable refusal results.

- [ ] **Step 1: Write failing broker boundary tests**

```python
def test_broker_refuses_before_policy_when_identity_is_missing(broker, read_action):
    result, decision = broker.execute(read_action, session_id="sess_1", turn_id="turn_1")
    assert result.status == "denied"
    assert result.error == {"type": "machine_identity_missing"}
    assert decision.reasons == ["machine_identity_missing"]

def test_model_arguments_cannot_replace_owner_credential_scope(broker, identity):
    action = connector_action({"principal_id": "principal_other"})
    result, _ = broker.execute(action, identity=identity)
    assert result.error == {"type": "machine_identity_credential_scope_mismatch"}
```

Assert no hook, policy review, credential read, event content, or tool executor side effect occurs before successful verification. Add explicit tests for all human-only authority operations.

- [ ] **Step 2: Run focused tests and confirm the boundary is absent**

Run: `.venv\Scripts\python.exe -m pytest tests/test_machine_identity_turns.py tests/test_tool_broker.py -q`

Expected: missing identity is accepted or fails with the wrong reason.

- [ ] **Step 3: Make verified identity mandatory at the broker**

```python
@dataclass(frozen=True)
class ToolExecutionContext:
    session_id: str
    turn_id: str
    acting_principal_id: str
    owner_principal_id: str
    verified_identity: VerifiedMachineIdentity
```

Verify at the first line of `execute`. Construct `ToolAction.proposed_by` and tool-action storage from `acting_principal_id`. Route owner-scoped memory, projects, repositories, connections, and attachments through `owner_principal_id`. Remove implicit `self.principal_id` fallbacks from agentic paths.

- [ ] **Step 4: Enforce the strict machine privilege subset in authority routing**

Reject AI attempts to mint identities, manage issuer state, manage gates/modes/grants/roles, resolve approvals, satisfy confirmations, or name a human principal as actor. Preserve existing read/mutation decisions after the new identity gate.

- [ ] **Step 5: Harden credential-backed executors**

Credential lookup receives the verified delegated owner as an internal parameter. Reject any model-controlled credential/principal selector that conflicts with it. Return redacted results; add secret scanning over events and API output.

- [ ] **Step 6: Run broker, authority, connector, provider, and regression suites**

Run: `.venv\Scripts\python.exe -m pytest tests/test_machine_identity_turns.py tests/test_tool_broker.py tests/test_runtime_authority.py tests/test_connector_ecosystem.py tests/test_api_model_selection.py -q`

- [ ] **Step 7: Commit the enforcement boundary**

```powershell
git add -- raiker/tools/broker.py raiker/runtime/authority/router.py raiker/runtime/connector_ecosystem.py raiker/tools/connector_tools.py raiker/models/connections.py raiker/runtime/executors/connectors.py tests/test_machine_identity_turns.py tests/test_tool_broker.py tests/test_runtime_authority.py tests/test_connector_ecosystem.py tests/test_github_connector.py tests/test_gmail_connector.py tests/test_gcal_connector.py tests/test_slack_connector.py tests/test_api_model_selection.py
git commit -m "feat: enforce machine identity at broker"
```

---

### Task 4: Approval, Checkpoint, Audit, and API Attribution

**Files:**
- Modify: `raiker/storage/migrations.py`
- Modify: `raiker/storage/sqlite.py`
- Modify: `raiker/api/routes_approvals.py`
- Modify: `raiker/approvals/execution.py`
- Modify: `raiker/control/dtos.py`
- Modify: `raiker/control/dashboard.py`
- Modify: `raiker/api/schemas.py`
- Modify: `raiker/api/routes_dashboard.py`
- Test: `tests/test_machine_identity_turns.py`
- Test: `tests/test_api_approvals.py`
- Test: `tests/test_approval_execution_wiring.py`
- Test: `tests/test_api_dashboard.py`

**Interfaces:**
- Produces: `IdentityView`, machine identity fields on approval/event/turn DTOs, and proposal metadata persisted without bearer material.

- [ ] **Step 1: Write failing proposer/authorizer attribution tests**

```python
def test_approval_keeps_machine_proposer_and_human_authorizer(client, machine_turn):
    pending = client.get(f"/api/approvals/{machine_turn.approval_id}").json()
    assert pending["approval"]["proposed_by"]["principal_type"] == "ai_agent"
    resolved = resolve_as_owner(client, machine_turn.approval_id)
    assert resolved["approved_by"]["principal_type"] == "human"
    assert resolved["proposed_by"]["principal_id"] != resolved["approved_by"]["principal_id"]
```

Add delayed approval after bearer expiry, proposal-hash mismatch, revoked human session, disabled gate, checkpoint actor, redaction, and cross-account visibility cases.

- [ ] **Step 2: Run attribution tests and verify current DTOs lack the fields**

Run: `.venv\Scripts\python.exe -m pytest tests/test_machine_identity_turns.py tests/test_api_approvals.py tests/test_api_dashboard.py -q`

- [ ] **Step 3: Persist immutable proposal identity metadata**

Extend approvals/tool actions with machine principal, subject, key ID, token ID, and attestation expiry. Do not store the bearer or signature. Preserve `resolved_by` as the human authorizer and execution evidence as the runtime relay.

- [ ] **Step 4: Add redacted API identity DTOs**

```python
@dataclass(frozen=True)
class IdentityView:
    principal_id: str
    principal_type: str
    display_name: str
    subject: str | None
    turn_id: str | None
    key_id: str | None
    issued_at: str | None
    expires_at: str | None
    state: str
```

Add `proposed_by`, `approved_by`, and `machine_identity` fields to approval, turn, and event views. Ensure owner delegation details are returned only inside the authenticated account boundary.

- [ ] **Step 5: Keep delayed execution independent of expired bearer state**

The relay validates immutable proposal identity metadata and proposal hash, then re-governs under the current human authorization and current gates. It never deserializes or verifies a stored bearer token because none is stored.

- [ ] **Step 6: Run approval and dashboard integration suites**

Run: `.venv\Scripts\python.exe -m pytest tests/test_machine_identity_turns.py tests/test_api_approvals.py tests/test_approval_execution_wiring.py tests/test_api_dashboard.py -q`

- [ ] **Step 7: Commit attribution contracts**

```powershell
git add -- raiker/storage raiker/api raiker/approvals raiker/control tests
git commit -m "feat: expose machine action attribution"
```

---

### Task 5: Owner/Agent Authority Matrix and Identity Presentation

**Files:**
- Create: `apps/web/src/lib/components/AuthorityMatrix.svelte`
- Create: `apps/web/src/lib/components/IdentityChip.svelte`
- Create: component tests beside each component
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/apiTypes.ts`
- Modify: `apps/web/src/lib/views/CapabilitiesView.svelte`
- Modify: `apps/web/src/lib/views/CapabilitiesView.test.ts`
- Modify: `apps/web/src/lib/views/ApprovalsView.svelte`
- Modify: `apps/web/src/lib/views/ApprovalsView.test.ts`
- Modify: `apps/web/src/lib/views/ActivityView.svelte`
- Modify: `apps/web/src/lib/views/ActivityView.test.ts`

**Interfaces:**
- Consumes: Task 4 identity DTOs.
- Produces: accessible derived authority states `Direct`, `Ask`, `Denied`, `Unavailable`; machine/human identity chips.

- [ ] **Step 1: Write failing UI behavior tests**

```typescript
it("shows owner controls separately from the agent's derived authority", async () => {
  stubFetch({ "GET /api/capability-gates": [makeGate({ decision_mode: "ask" })] });
  render(CapabilitiesView, { principal: "principal_owner" });
  expect(await screen.findByRole("columnheader", { name: "Owner" })).toBeInTheDocument();
  expect(screen.getByRole("columnheader", { name: "Raiker agent" })).toBeInTheDocument();
  expect(screen.getByText("Ask")).toBeInTheDocument();
});

it("names machine proposer and human authorizer", async () => {
  render(ApprovalsView);
  expect(await screen.findByText("Raiker agent · turn_1")).toBeInTheDocument();
  expect(screen.getByText("Approved by owner")).toBeInTheDocument();
});
```

Add keyboard, accessible-name, narrow viewport, dark/light theme, and no-secret rendering assertions. Expected values must be literal and tests must render real components rather than mocks.

- [ ] **Step 2: Run UI tests and verify missing matrix/chips**

Run: `npm --prefix apps/web test -- src/lib/views/CapabilitiesView.test.ts src/lib/views/ApprovalsView.test.ts src/lib/views/ActivityView.test.ts`

- [ ] **Step 3: Add TypeScript DTOs and derived authority helper**

```typescript
export interface IdentityView {
  principal_id: string;
  principal_type: "human" | "ai_agent" | "automation" | "system";
  display_name: string;
  subject: string | null;
  turn_id: string | null;
  key_id: string | null;
  issued_at: string | null;
  expires_at: string | null;
  state: "active" | "expired" | "inactive";
}

export type AgentAuthority = "Direct" | "Ask" | "Denied" | "Unavailable";
```

Derive the state from the server's gate state, executor availability, and decision mode; do not create a second permission control.

- [ ] **Step 4: Implement Permissions matrix and reusable identity chips**

Keep existing owner mutations unchanged. The matrix explains that the agent cannot modify its authority. Use semantic table/list markup that collapses legibly on mobile and remains readable in both themes.

- [ ] **Step 5: Add proposer/authorizer to Approvals and actor identity to Activity**

Pending rows name the machine proposer and turn. Resolved detail adds the human decision maker. Activity rows display the identity label and preserve raw IDs in a disclosure/title for audit correlation.

- [ ] **Step 6: Run focused and full web checks**

Run: `npm --prefix apps/web test -- src/lib/views/CapabilitiesView.test.ts src/lib/views/ApprovalsView.test.ts src/lib/views/ActivityView.test.ts`

Run: `npm run check`

Run: `npm run lint`

Run: `npm run build`

- [ ] **Step 7: Commit the user-facing identity controls**

```powershell
git add -- apps/web/src
git commit -m "feat: show owner and agent authority"
```

---

### Task 6: Documentation and Threat Model Synchronization

**Files:**
- Create: `docs/threat-models/machine-identity.md`
- Modify: `docs/plans/TO_BE_ADDED.md`
- Modify: `docs/plans/TO_BE_FIXED.md` if defects are found
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/SECURITY_AND_POLICY.md`
- Modify: `docs/THREAT_MODEL.md`
- Modify: `docs/TOOLS_AND_PERMISSIONS_SPEC.md`
- Modify: `docs/API_AND_CONTRACT_SCHEMAS.md`
- Modify: `docs/EVENT_CATALOG.md`
- Modify: `docs/MULTI_AGENT_AND_SUBAGENT_STRATEGY.md`
- Modify: `docs/NESTED_BOUNDARIES_ARCHITECTURE.md`
- Modify: `docs/FEATURE_COVERAGE_MATRIX.md`
- Modify: `docs/IMPLEMENTATION_STATUS.md`
- Modify: `docs/guide/permissions-and-runtime-modes.md`
- Modify: `docs/guide/working-in-chat.md`
- Modify: `docs/guide/tasks-and-projects.md`

**Interfaces:**
- Consumes: verified implementation and exact API/event names from Tasks 1–5.
- Produces: one consistent shipped architecture statement and an ADD-03 evidence record.

- [ ] **Step 1: Update the machine-identity threat model**

Document trust boundaries, assets, attacker capabilities, spoofing, tampering, replay, key theft, owner-credential mirroring, delayed approvals, rotation/recovery, residual host-compromise risk, and the exact tests that demonstrate each control.

- [ ] **Step 2: Update architecture and contracts in their existing formats**

State the complete path:

```text
authenticated owner -> per-turn issuer -> machine principal + attestation
-> orchestrator trusted context -> broker verification -> policy/gates
-> owner-scoped executor -> machine-attributed evidence
```

Record DTO fields, refusal codes, lifecycle events, Owner/Agent matrix semantics, subagent ancestry, and the credential boundary.

- [ ] **Step 3: Close ADD-03 and update status/coverage documents**

Mark ADD-03 shipped only after Tasks 1–5 tests pass. Record exact files, UI outcome, tests, and known residual risks. Add every newly found defect to `TO_BE_FIXED.md` immediately; close it in the same run if fixed.

- [ ] **Step 4: Search for and correct stale owner-mirroring claims**

Run: `rg -n -i "executes? as the owner|owner's authority|owner authority|principal mirroring|agent identity|machine identity" README.md docs`

Review every match manually. Preserve historical observations where explicitly labelled as prior behavior; update current-state claims.

- [ ] **Step 5: Verify documentation formatting**

Run: `git diff --check`

Run: `.venv\Scripts\python.exe -m pytest tests/test_docs_consistency.py -q`

- [ ] **Step 6: Commit synchronized documentation**

```powershell
git add -- README.md docs
git commit -m "docs: record machine identity architecture"
```

---

### Task 7: Three-Provider Live Playwright Acceptance and Screenshots

**Files:**
- Create: `apps/web/e2e/add-03-machine-identity-providers-live.spec.ts`
- Modify: `docs/WEB_APP_LIVE_TEST.md`
- Modify: `docs/plans/screenshots/README.md`
- Add: reviewed screenshots under `docs/plans/screenshots/working/`
- Modify: `docs/plans/TO_BE_FIXED.md` for issues discovered during live testing

**Interfaces:**
- Consumes: running `raiker-web`, UI credential forms, Anthropic/OpenRouter environment variables, local Ollama `gemma4:31b-cloud`.
- Produces: provider-independent identity evidence in Permissions, Approvals, and Observability.

- [ ] **Step 1: Write the live scenario before starting the server**

```typescript
const ANTHROPIC_KEY = process.env.RAIKER_LIVE_ANTHROPIC_KEY ?? "";
const OPENROUTER_KEY = process.env.RAIKER_LIVE_OPENROUTER_KEY ?? "";

for (const provider of ["Anthropic", "OpenRouter", "Ollama"] as const) {
  test(`${provider} turn is attributed to a machine identity`, async () => {
    await selectProviderThroughUi(provider);
    const turn = await runGovernedTurn(provider);
    await expectMachineIdentityInPermissions(turn);
    await expectMachineProposerInApproval(turn);
    await expectMachineIdentityInActivity(turn);
  });
}
```

Use the repository's existing UI login and provider helpers. Never echo keys. Screenshots begin only after credential dialogs close and must be reviewed for secrets.

- [ ] **Step 2: Stop any Raiker service and start an isolated live workspace**

Resolve listeners and owning processes first. Stop only the Raiker process confirmed to belong to this workspace. Start `raiker-web` hidden on a free loopback port with a temporary workspace and the required egress/vault configuration. Keep Ollama running for its provider test.

- [ ] **Step 3: Run Playwright against Anthropic, OpenRouter, and Ollama**

Use `RAIKER_LIVE_ANTHROPIC_KEY` and `RAIKER_LIVE_OPENROUTER_KEY` only in the launched test process environment. Enter both through Models UI. Select `gemma4:31b-cloud` for Ollama.

Run: `npm --prefix apps/web run test:e2e:live -- e2e/add-03-machine-identity-providers-live.spec.ts`

Expected: three real provider turns complete and each identity assertion passes.

- [ ] **Step 4: Inspect screenshots visually and fix every issue found**

Open every screenshot at original detail. Verify distinct Owner/Agent columns, machine proposer, human authorizer, turn-bound Activity identity, responsive layout, and absence of credentials. For each defect: add a failing automated test, fix it, rerun focused tests, and rerun the affected live scenario.

- [ ] **Step 5: Promote reviewed evidence and update live-test documentation**

Copy only approved screenshots from `output/playwright/` into `docs/plans/screenshots/working/` using the existing naming/index format. Record server command, environment shape without values, providers/models, test command, results, screenshots, and discovered/fixed issues in `docs/WEB_APP_LIVE_TEST.md`.

- [ ] **Step 6: Commit live acceptance evidence**

```powershell
git add -- apps/web/e2e/add-03-machine-identity-providers-live.spec.ts docs/WEB_APP_LIVE_TEST.md docs/plans/screenshots docs/plans/TO_BE_FIXED.md
git commit -m "test: verify turn identities across providers"
```

---

### Task 8: Full Verification, Push, and GitHub Workflow Monitoring

**Files:**
- Modify only files required by failures found during verification.

**Interfaces:**
- Produces: a clean `main`, pushed commit, and green GitHub workflows.

- [ ] **Step 1: Run fresh full Python quality gates**

Run: `.venv\Scripts\python.exe -m ruff check .`

Run: `.venv\Scripts\python.exe -m mypy raiker apps tests`

Run: `.venv\Scripts\python.exe -m pytest`

- [ ] **Step 2: Run fresh full web quality gates**

Run: `npm run check`

Run: `npm run lint`

Run: `npm test`

Run: `npm run build`

Run: `npm run test:e2e:mocked`

- [ ] **Step 3: Review requirements, secrets, diff, and workspace state**

Run: `git diff --check`

Run: `git status --short --branch`

Run: `git log --oneline origin/main..HEAD`

Run a secret scan over tracked changes and confirm neither supplied key appears in Git objects, source, test output, screenshots, or docs. Re-read the approved specification completion criteria line by line.

- [ ] **Step 4: Fix every verification failure test-first**

For each newly observed bug, first add the smallest failing regression test, verify the failure, implement the fix, rerun focused tests, then rerun the full gate that found it. Record unresolved issues in `docs/plans/TO_BE_FIXED.md`; do not claim completion while an in-scope issue remains fixable.

- [ ] **Step 5: Commit any final verified corrections**

```powershell
git add -A
git commit -m "fix: close machine identity verification gaps"
```

Skip this commit when the tree is already clean.

- [ ] **Step 6: Push `main` to origin**

Run: `git push origin main`

- [ ] **Step 7: Monitor GitHub Actions to a terminal green state**

Run: `gh run list --branch main --commit <pushed-sha> --limit 20`

For every associated run, use `gh run watch <run-id> --exit-status`. If a workflow fails, inspect with `gh run view <run-id> --log-failed`, reproduce locally where possible, add a regression test, fix, rerun all affected gates, commit, push, and monitor the new SHA. Continue until all required workflows for the pushed SHA are successful.

---

## Plan Self-Review Checklist

- Every approved design requirement maps to Tasks 1–8.
- Machine identity is mandatory before policy, credentials, approvals, or tools.
- Owner scope and acting identity remain separate through storage and UI.
- Delayed approvals do not retain bearer tokens.
- Scheduled, resumed, and subagent paths are included.
- UI, API, audit, docs, all three providers, screenshots, push, and CI monitoring are included.
- Every production task starts with a failing behavioral test and a verified red run.
- No task weakens existing governance or changes default capability state.
