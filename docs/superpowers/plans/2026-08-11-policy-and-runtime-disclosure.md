# Policy and Runtime Disclosure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove dead deny configuration and make every runtime-withheld tool call appear as a runtime-authored refusal, with navigation-safe remediation copy.

**Architecture:** Static policy has one classification path: allow, approval-required, or fail-closed unknown. Tool-result envelopes that represent a runtime denial are converted to the same `model_tool_call_refused` event used by pre-execution policy refusals; the model receives a short safe fact, never the authority to narrate the denial.

**Tech Stack:** Python policy engine and orchestrator, Svelte event presentation, pytest, Vitest.

## Global Constraints

- Runtime events, not model prose, are authoritative for denied or withheld actions.
- Preserve approval semantics and never expose raw tool arguments, connector content, or secrets in refusal payloads.
- Use route identifiers in runtime payloads; let the UI resolve human labels from navigation metadata.

---

### Task 1: Delete `denied_actions` and enforce exhaustive policy classification (BUG-51)

**Files:**
- Modify: `raiker/policy/config.py`
- Modify: `raiker/policy/engine.py`
- Modify: `tests/test_policy_engine.py`
- Modify: `tests/test_tool_broker.py`

- [ ] Add a failing test asserting `StaticPolicyConfig` has no `denied_actions` field and every built-in model tool name is either read-allowed or approval-required, with the two sets disjoint.

```python
def test_builtin_tool_policy_is_exhaustive():
    config = StaticPolicyConfig(workspace_root=Path.cwd())
    names = ToolBroker.builtin_tool_names()
    assert not (config.allowed_read_actions & config.approval_required_actions)
    assert names <= config.allowed_read_actions | config.approval_required_actions
```

- [ ] Run the focused tests and verify they fail because the dead field remains and the broker exposes no registry helper.
- [ ] Expose `ToolBroker.builtin_tool_names()` from the same handler registry used by execution, without instantiating external clients.
- [ ] Delete `denied_actions`. Keep unknown actions denied by `StaticPolicyEngine` and add an invariant check with a precise error when configured allow/approval sets overlap.
- [ ] Run `python -m pytest tests/test_policy_engine.py tests/test_tool_broker.py -q` and verify it passes.

### Task 2: Convert withheld results into runtime refusals (BUG-60)

**Files:**
- Modify: `raiker/runtime/orchestrator.py`
- Modify: `tests/test_model_tool_call_loop.py`
- Modify: `tests/test_model_tool_call_batch.py`

- [ ] Add failing single-call and batch tests where the broker returns a denied/withheld envelope. Assert exactly one `model_tool_call_refused` event per call id, no ordinary tool-result presentation event, and only a short safe refusal record is added to model context.

```python
events = list(run_model_turn(broker=withheld_broker("call_1")))
refusals = [event for event in events if event.event_type == "model_tool_call_refused"]
assert [event.payload["call_id"] for event in refusals] == ["call_1"]
assert "raw_result" not in refusals[0].payload
```

- [ ] Run the focused tests and verify they fail because withheld results remain batch results.
- [ ] Add one predicate that recognizes denied/withheld tool envelopes from stable status and reason-code fields. Route both pre-policy and post-broker denial through `_refusal_event`.
- [ ] Deduplicate by model call id and retain order in batches. Include `authority="runtime"`, `reason_code`, safe summary, tool display name, and optional `remediation_route="capabilities"`.
- [ ] Serialize model-safe tool exchange JSON with `ensure_ascii=False` so refusal copy and international text are not escaped into unreadable surrogate sequences.
- [ ] Run the focused tests and verify they pass.

### Task 3: Resolve remediation copy through navigation metadata (BUG-59)

**Files:**
- Modify: `apps/web/src/lib/nav.ts`
- Modify: `apps/web/src/lib/chatPresentation.ts`
- Modify: `apps/web/src/lib/chatPresentation.test.ts`
- Modify: `apps/web/src/lib/turnPhases.test.ts`
- Modify: `raiker/runtime/web_access.py`
- Modify: `tests/test_web_access.py`

- [ ] Add failing UI tests asserting a refusal with `remediation_route="capabilities"` renders the current navigation label and link from `nav.ts`, and Python tests asserting web-access denial returns the route identifier rather than stale “Settings → Capabilities” copy.
- [ ] Run the focused tests and verify failure.
- [ ] Export a route lookup helper from `nav.ts`; make refusal presentation resolve the link and label there. Change the runtime denial to stable factual text plus `remediation_route`.
- [ ] Verify refusal cards remain visually distinct, keyboard accessible, and do not attribute the message to the assistant.
- [ ] Run `python -m pytest tests/test_web_access.py tests/test_model_tool_call_loop.py tests/test_model_tool_call_batch.py -q` and `npm test -- --run src/lib/chatPresentation.test.ts src/lib/turnPhases.test.ts` from `apps/web`; verify all pass.
