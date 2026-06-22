# Flows (no privileged bypass)

> Planning document. ASCII diagrams (no mermaid) so they render everywhere with zero tooling/drift.
> The single invariant these diagrams exist to prove: **the SPA holds no policy logic and never
> touches SQLite.** Every read and every mutation crosses the same governed boundary as the CLI.

## 1. Prompt-turn path (submit a prompt)

```
 Browser (Svelte SPA)
   |  POST /api/prompts            (Bearer token; ClientMetadata.type = "web_ui")
   v
 FastAPI route  raiker/api/routes_prompts.py
   |  build PromptEnvelope -> AgentGateway.submit_prompt_async()
   v
 AgentGateway  raiker/gateway/agent_gateway.py
   |  _prepare_turn (prompt_received) -> RuntimeOrchestrator.ahandle()
   v
 RuntimeOrchestrator  (gather -> plan -> act -> verify)
   |  per tool action:
   v
 RuntimeAuthority.route_action()  raiker/runtime/authority/router.py
   |   principal active? domain scope? self-approval? gate enabled?
   |   policy review -> decision
   |
   +--[allow]------------> Executor (only if registered)   --> action_executed / action_failed
   +--[needs_approval]---> ApprovalInbox (metadata-only)     --> approval_requested
   +--[deny / disabled]--> (no execution)                    --> policy_decision / denial
   |
   v
 Event log (JSONL + events_index, SHA-256 chained)  +  Checkpoint (turn_closed)
   |
   v
 AgentResponse  (returned to SPA, or streamed via GET /api/prompts/{turn_id}/stream as SSE)
```

Key points:
- The SPA only sends a prompt and renders the streamed `StreamEvent`s + final `AgentResponse`.
- Approval-required actions do **not** execute; resolving them later is metadata-only.
- No executor registered ⇒ `execution_unavailable:no_executor` (fail-closed), never faked success.

## 2. Governed-mutation path (enable/disable a runtime mode or capability gate)

```
 Browser (Settings -> Security Settings)
   |  StepUpAuthDialog: re-confirm human principal,
   |  collect reason / Tier-2 confirmation_token / threat-model ack
   v
 POST /api/runtime-mode/{activate|disable}  OR  /api/capability-gates/{cap}/{set|disable}
   |  (existing control routes — NO new authority path)
   v
 RuntimeControlService  raiker/control/service.py
   |  delegates to ->
   v
 RuntimeAuthority  raiker/runtime/authority/router.py
   |   _check_human_runtime_gate_manager (human + runtime_gate_manager role)
   |   evaluate_activation_requirement (executor present? mode active? ack? token?)
   |
   +--[ok]----> upsert state (runtime_mode_state / capability_gate_state) + emit event
   +--[blocked]-> 403 { ok:false, reason_code }   (rendered as plain English)
   v
 SQLiteStore (state)  +  Event log (capability_enabled / runtime_mode_activated / ...)
```

Key points:
- The step-up dialog **collects and forwards** what the backend already requires — it grants nothing.
- AI principals are rejected server-side (`ai_cannot_manage_runtime_gates`); the UI also hides the
  controls when `can_current_principal_change=false`.
- Fail-closed / deferred capabilities cannot be enabled (no executor) and show the explainer.

## 3. STOP switch (interrupt active tasks)

```
 Browser (top bar STOP) -> confirm dialog
   |  POST /api/interrupts { all:true, action_type:"cancel", reason }
   v
 RuntimeControlService / route -> InterruptController.apply_at_safe_boundary()
   |  (and/or TaskManager.cancel_task)
   v
 events: interrupt_received -> safe_boundary_reached -> task_cancelled
```

Semantics: cancellation applies at the **next safe boundary**, not an instant hard-kill. Human-only.

## Optional wireframes (low-fidelity)

Home (Chat):
```
+--------------------------------------------------------------+
| RuntimeStatusBanner: mode | readiness | principal   ( STOP ) |
+----------+---------------------------------------------------+
| Nav      | ChatTurnTimeline                                  |
| Home     |  [gather] [plan] [act] [verify]   (status badges) |
| Tasks    |  ActionProposalCard: write_file  [Approval-req]   |
| Approvals|    risk: high | diff preview | Why blocked?        |
| ...      | [ prompt input ........................ ] [Send]  |
+----------+---------------------------------------------------+
```

Settings -> Security Settings (after step-up):
```
+--------------------------------------------------------------+
| Security Settings  (step-up confirmed as: owner)             |
+--------------------------------------------------------------+
| Runtime Mutations                                            |
|  graph_indexing_runtime   [disabled v] (enable) reason[___]  |
|  shell_execution          [disabled]  un-enableable          |
|     -> activation_blocked:no_executor (deferred)             |
| Secret Settings (read-only)                                  |
|  Redaction policy: ON    Secret storage: NOT IMPLEMENTED     |
+--------------------------------------------------------------+
```
