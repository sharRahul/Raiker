# Governance entry paths

**Canonical** for *how does an action reach an executor, and what does it cross
on the way*. This is the enumeration behind Raiker's central claim:

> No model, tool, skill, plugin, interface, runtime, or execution path reaches an
> action without crossing policy, capability gates, approvals and audit.

That sentence appears in `README.md`, in
[`NESTED_BOUNDARIES_ARCHITECTURE.md`](../NESTED_BOUNDARIES_ARCHITECTURE.md) and in
[`SECURITY_ARCHITECTURE.md`](../SECURITY_ARCHITECTURE.md). Until this document it
was **asserted and never enumerated** — there was no list of the paths, and
therefore no way to tell whether the claim was true, or to notice a new path
appearing beside the governed ones.

It exists because a claim nobody can check is not a control. Written **2026-08-23**,
derived from the code rather than from the other documents.

---

## 1. The finding that motivated this document

**The documentation says one chokepoint. The code has two, plus eight local
re-implementations of one check.**

`NESTED_BOUNDARIES_ARCHITECTURE.md:278` says:

> This is the non-bypass path every tool, command, plugin action, channel action,
> memory write, graph query, checkpoint restore, model control, or execution
> adapter must follow.

Measured against the code, that is **not accurate**, and the inaccuracy is not a
hole — it is an undocumented, defensible design that nobody wrote down:

- A **read** (`read_file`, `grep`, `memory_get`, `knowledge_graph`,
  `code_map_search`, a projected MCP tool) is governed at
  **`PolicyEngine.review`** inside the tool broker. It never reaches
  `RuntimeAuthority.route_action`.
- An **acting capability** is governed at **`RuntimeAuthority.route_action`**,
  which applies eight checks the policy engine does not.
- **Eight modules** re-implement the capability-gate check locally rather than
  routing through the authority, so they get the gate and the decision mode and
  none of the other six checks.

None of that is wrong. All of it should have been written down, because the
difference between the two chokepoints is exactly where a future mistake will
land — and one already did: two egress implementations existed for months, one
of them with none of the address guard, because nothing enumerated the paths that
reach the network. Enumerating them is what found it; deleting the weaker one is
what closed it (BUG-232). There is now one implementation, and it is the one an
owner is told about: [`../threat-models/web-fetch.md`](../threat-models/web-fetch.md).

---

## 2. The two chokepoints, and what each actually checks

### Chokepoint A — `PolicyEngine.review` (`raiker/policy/engine.py`)

Every model-proposed tool call crosses this, without exception. A tool in
neither the allow set nor the deny set is **hard-denied**, which is what makes
"every advertised tool has a verdict" an invariant rather than a hope
(`tests/test_policy_engine.py`).

| Check | Where |
|---|---|
| Managed policy | `_check_managed_policy` |
| Role policy for the acting user | `_check_role_policy` |
| Credential-like text refused before a memory write is offered | `classify_memory_sensitivity` |
| Read/write shape, workspace path containment | path check |
| Risk level and whether approval is required | `PolicyDecision` |

### Chokepoint B — `RuntimeAuthority.route_action` (`raiker/runtime/authority/router.py`)

Everything that *acts* crosses this. In order:

| # | Check | Method |
|---|---|---|
| 1 | Principal is active | `check_principal_active` |
| 2 | Domain scope is valid for this principal | `check_domain_scope` |
| 3 | **An AI principal cannot approve its own action** | `check_self_approval` |
| 4 | **A principal cannot grant itself authority** | `check_self_grant` |
| 5 | The agent runtime is accepting executions | `check_runtime_gate_enable` |
| 6 | The capability gate is open for this principal | `check_capability_gate` |
| 7 | **Critical classification → human-only step-up lifecycle**, before policy review, so critical dominates every other outcome | `classify_critical` |
| 8 | Policy review (chokepoint A, again, at execution time) | `policy_engine.review` |
| 9 | Decision-mode resolution | `resolve_decision_mode` |
| 10 | Executor dispatch and audit events | `executor_registry.get(...).execute(...)` |

**Exactly six call sites enter B**, in five modules, and that is the number to
watch:

| Caller | Line | Why |
|---|---|---|
| `raiker/tools/broker.py` | `:1445` | The auto/skip fast path — an ordinary action the owner pre-authorised for this turn |
| `raiker/approvals/execution.py` | `:197` | `ApprovalExecutionBridge` — a human's *Approve* becoming an execution |
| `raiker/runtime/executors/tier1_approval.py` | `:287` | The relay re-routing the **target** capability, so it re-passes 1–10 at execution time |
| `raiker/control/service.py` | `:492`, `:838` | Governed control-plane mutations (capability gates, runtime state) |
| `raiker/runtime/authority/router.py` | `:1579` | Internal delegation |

A seventh call site appearing here is an architectural change and should be
reviewed as one.

---

## 3. Every entry path

Read a row as: *something originates an action here; it crosses these; the most
it can reach is this.*

### 3.1 Model-proposed work

| # | Path | Originates at | Crosses | Reaches |
|---|---|---|---|---|
| 1 | **Chat turn** | `POST /api/prompts`, `routes_prompts.py:327` → `AgentGateway` → `orchestrator` → `ToolBroker` | A, then B for acting tools | Any capability its gate and the owner's decision allow |
| 2 | **Build turn** | Same, `surface: "build"`, plus the Build operating protocol and Plan/Edit/Auto posture | A, then B | Same authority as Chat — the surfaces differ in composer and protocol, never in authority |
| 3 | **Streaming turn** | `routes_prompts.py:401` | Identical | Identical |
| 4 | **Turn resumed after an approval** | `routes_approvals.py:479` / `:495` → `AgentGateway` | A, then B; plus the parked-turn single-resumption claim | The remainder of the parked turn, re-governed |
| 5 | **CLI agentic turn** | `cli/commands.py:1743`, `:3251` → `AgentGateway` | Identical | Identical — the terminal client is not a privileged path |
| 6 | **Task cycle / scheduled routine** | `tasks/scheduler.py:142`, `:213` → `AgentGateway` | Identical, plus: unattended, so an action needing a decision **parks** as `task_blocked` | One governed turn per cycle. A task inherits no standing permission from having been approved once |

All six construct `AgentGateway`, and **there are exactly eight construction
sites in four modules** — `routes_prompts.py` (`:327`, `:401`),
`routes_approvals.py` (`:479`, `:495`), `cli/commands.py` (`:1743`, `:3251`) and
`tasks/scheduler.py` (`:142`, `:213`). Nothing else in the tree constructs one,
which is what makes "every interface enters through the Agent Gateway"
(`NESTED_BOUNDARIES_ARCHITECTURE.md:29`) a claim that currently holds. It is
worth asserting, because it is the claim that stops a new surface reaching the
orchestrator directly.

### 3.2 Human-originated action

| # | Path | Crosses | Reaches |
|---|---|---|---|
| 7 | **Approval resolution** | `ApprovalExecutionBridge` → **B**, with TTL, arguments-hash and posture checks first | Only the thirteen in `EXECUTABLE_ON_APPROVAL`; everything else records the decision and executes nothing |
| 8 | **Critical approval resolution** | `resolve_critical_approval` — human-only, step-up verified, **never** the ordinary relay | The critical action, once |
| 9 | **Control-plane mutation** (open a gate, stop the runtime) | `control/service.py` → **B**; plus `runtime_gate_manager` role, reason, typed phrase, threat-model acknowledgement | The gate change, recorded against the principal |
| 10 | **Terminal slash command** | The CLI's own governed command surface | The same capabilities, under the same gates |
| 21 | **Checkpoint restore request** (BUG-230) | `POST /api/checkpoints/{id}/restore` → recomputed preflight → an ordinary approval; a cross-principal restore is marked `critical` and takes path 8 instead | `checkpoint_restore_execution`, once, when a human approves. The route itself performs nothing |
| 22 | **`/checkpoints restore <id> --confirm`** | The same: recomputed preflight, ordinary approval, critical when cross-principal | Identical to 21 — the terminal is not a privileged path |
| 23 | **Audit export** (BUG-231) | `POST /api/audit/export` → `control/service.py::export_audit_log` → **B**; human-only, and the account scope comes from the principal, never from an argument | A redacted JSONL of *this* account's record, written into the workspace. The export is an event in the log it exported |

### 3.3 Delegated and contributed execution

| # | Path | Crosses | Reaches |
|---|---|---|---|
| 11 | **Subagent** (`spawn_subagent`) | `SubagentRunner` → `ToolBroker` → **A**, per step, against a **read-only delegable allowlist** | Reads only. A mutation can be *proposed*; the broker parks it for the owner. A tool outside the allowlist fails closed |
| 12 | **Multi-agent team** | `TeamCoordinator`, same broker path per member | Same as 11 |
| 13 | **Plugin brokered call** | `tier4_plugins.py:320` → `ToolBroker.execute` → **A**, against the plugin's validated, allowlisted read-only set | Reads only. `plugin_tool_not_brokered:<tool>` otherwise. **No plugin code runs** |
| 14 | **Plugin-contributed hook rule** | Loaded at `plugin` scope, **below every scope the owner controls** | Can only make an action stricter |
| 15 | **Plugin-contributed skill** | Validated by the same reader an upload uses; installed **switched off** | Instruction text. Raiker runs nothing a skill ships |
| 16 | **Plugin-contributed MCP server** | An **offer**. Nothing is a server until the owner adds it | Nothing, until path 18 |

### 3.4 External input

| # | Path | Crosses | Reaches |
|---|---|---|---|
| 17 | **Inbound channel message** | Owner secret, sender allowlist, 60/sender/minute, recorded and quarantined | **Nothing.** It is untrusted content with a named sender who is not the owner. Routing modes are not built: an inbound message never becomes work on its own |
| 18 | **MCP tool call** | **A** (read-shaped), then a **local** gate + decision-mode check in `tools/mcp_tools.py` — see §4 | A bounded stdio JSON-RPC session against an owner-configured server |
| 19 | **Fetched web page** | The `web_fetch` gate, blocklist, address guard, sanitiser | The turn's context as **untrusted data**. Nothing fetched raises a turn's authority |
| 20 | **Hook handler** | `command` or `builtin`, bounded timeout, program resolved inside the workspace | Only `deny` or `ask`. `combine()` refuses `allow` from any handler — **a hook can never grant** |

### 3.5 Paths that exist and are not reachable

Recorded because an unreachable registered executor is the shape a future hole
takes.

| Capability | State |
|---|---|
| `process_execution` | Real executor, registered, no `process` tool, not relayed by an approval. It runs the same `CommandService` lifecycle `shell_execution` does, so it is an *unused* path rather than a *weaker* one — which is why it survived the 2026-08-23 cut and `network_execution` did not |

**Three of the four rows this section held are gone, and each left for a
different reason.** `network_execution` was deleted outright (capability,
executor and gate): it was a second implementation of "reach the network" whose
only control was a hard-coded four-host netloc glob, and a registered executor
with a weaker guard is one call site away from making the no-bypass claim false.
`checkpoint_restore_execution` gained its callers — `POST
/api/checkpoints/{id}/restore` and `/checkpoints restore <id> --confirm`, both
raising an ordinary approval (paths 21 and 22 in §3.2). `audit_export` gained an
executor and `POST /api/audit/export` (path 23). What remains is one row, and it
is recorded rather than removed for the reason this section exists.

### 3.6 Every capability with a real executor, and the path that reaches it

All forty-five, so the enumeration is complete rather than illustrative. The
first column is computed (`CAPABILITY_GATE_MAP` over `TOOL_DEFINITIONS`,
`EXECUTABLE_ON_APPROVAL`); the rest is read from the code and marked where it was
not fully traced.

**Reached by a model tool** — fifteen, each entering chokepoint B by name:

| Capability | Tool(s) |
|---|---|
| `file_write_execution` | `write_file`, `edit_file`, `create_document` |
| `patch_apply_execution` | `apply_patch` |
| `shell_execution` | `shell` |
| `git_write_execution` | `git_branch`, `git_commit` |
| `git_push_execution` | `git_push` |
| `connector_github_runtime` | `github_write` |
| `memory_write_execution` | `memory_write` |
| `memory_forget_execution` | `memory_forget` |
| `task_management_runtime` | `create_task` |
| `project_assignment_runtime` | `assign_session_project` |
| `code_map_indexing` | `code_map_search`, `code_map_references` |
| `graph_indexing_runtime` | `knowledge_graph` |
| `web_fetch` | `web_fetch`, `web_search` |
| `remote_execution_cap` | `remote_execute` |
| `cloud_execution_cap` | `cloud_execute` |

Twelve of these fifteen are also **relayed by an approval**
(`EXECUTABLE_ON_APPROVAL`); `code_map_indexing`, `graph_indexing_runtime` and
`web_fetch` are not. The thirteenth relayed capability,
`checkpoint_restore_execution`, has no model tool at all: only paths 21 and 22
propose a restore, so an agent can never rewind the workspace on its own say-so.

**Reached by a tool that checks its own gate** — the §4 pattern:

| Capability | Where the gate is read |
|---|---|
| `mcp_connector_runtime` | `raiker/tools/mcp_tools.py` |
| `advisor_model_runtime` | `raiker/runtime/advisor.py` |
| `connector_gmail_runtime`, `connector_gcal_runtime`, `connector_slack_runtime` | `raiker/runtime/connectors.py` |
| `vector_embedding_runtime` | `raiker/runtime/retrieval.py` |
| `hosted_model_runtime`, `private_network_model_runtime`, `model_provider_runtime` | `raiker/models/policy_state.py` |

**Reached by the control plane**, which enters chokepoint B like everything else:

| Capability | Where |
|---|---|
| `approval_execution_relay` | `ApprovalExecutionBridge`, `raiker/approvals/execution.py:197` |
| `audit_export` | `control/service.py::export_audit_log` (path 23) |
| `mcp_builder_runtime` | `control/service.py::_route_mcp` (`:492`) |
| `external_channel_runtime` | `control/service.py:838` |

**Not traced to a `GovernedAction` construction** — recorded honestly rather
than assumed. Each has a real executor and a real gate; what has *not* been
established is whether any path builds a governed action for it, or whether it is
reached through a control-plane service method that authorises differently:

`plugin_install` · `plugin_execution_cap` · `plugin_runtime_cap` ·
`plugin_revocation_cap` · `plugin_sandboxed_runtime_cap` ·
`plugin_sandbox_image_pull_cap` · `container_execution_cap` ·
`scheduled_routines` · `subagents` · `multi_agent_teams` ·
`channel_approval_relay` · `semantic_memory_runtime` · `calendar_runtime` ·
`email_runtime` · `reminder_runtime`

**This is the open question, not a finding.** `GovernedAction(` is constructed in
exactly four modules outside the executor package — `control/service.py` (×2),
`tools/broker.py`, `tools/mcp_tools.py` and `approvals/execution.py` — and none
of them names these fifteen. Plugin installation, for instance, goes through
`record_plugin_install` from the CLI and the dashboard: a human, owner-scoped,
control-plane action that is authorised, but **not** through the capability's own
gate. Whether that is correct is [GEP-04](#gep-04--fifteen-capabilities-have-no-traced-governed-action-path).

---

## 4. The eight modules that check the gate themselves

These re-implement the capability-gate lookup rather than calling
`RuntimeAuthority.check_capability_gate` through `route_action`. Each is
identified by a local `_ENABLED_GATE_STATES` constant.

| Module | Capability | Shape |
|---|---|---|
| `raiker/runtime/web_access.py` | `web_fetch` | **Egress** |
| `raiker/runtime/connectors.py` | `connector_github_runtime` | **Egress** |
| `raiker/runtime/advisor.py` | `advisor_model_runtime` | **Egress** |
| `raiker/tools/mcp_tools.py` | `mcp_connector_runtime` | **Subprocess + egress** |
| `raiker/graph/codemap_service.py` | `code_map_indexing` | Local read-derived |
| `raiker/runtime/retrieval.py` | `vector_embedding_runtime` | Local read |
| `raiker/memory/candidates.py` | memory candidates | Local read |
| `raiker/models/policy_state.py` | provider gate state | Local read |

**This is defensible and it is not free.** The design intent is stated in
`raiker/policy/engine.py:132–138`: a projected MCP tool is *read-shaped at the
policy layer* because what actually governs it is enforced inside the tool. The
same argument covers the other seven.

What each of them therefore does **not** get, because it never enters chokepoint B:

- `check_self_approval` — the AI-cannot-approve-its-own-action rule
- `check_self_grant`
- `check_principal_active`
- `check_domain_scope`
- `check_runtime_gate_enable` — **the agent-runtime stop switch**
- `classify_critical` — the critical-action floor
- the posture check
- `route_action`'s own audit events

The one worth arguing about is `check_runtime_gate_enable`. **Stopping the agent
runtime does not, by this reading, stop a `web_fetch` or an MCP tool call**,
because those paths never consult it. Whether that is correct depends on what the
stop switch is *for*: if it means "accept no new executions", a read that reaches
the network is an execution. This document does not resolve it — it records that
the question exists and has never been asked.

**Proposed action:** give these eight a single shared helper that performs the
gate lookup *and* the runtime-gate check, so the eight cannot drift from each
other or from the authority. Tracked as [GEP-01](#gep-01--eight-modules-re-implement-the-gate-check).

---

## 5. Invariants worth asserting by test

None of these are asserted today. Each is cheap, and each would have caught a
real defect this repository has already had.

| # | Invariant | Would have caught |
|---|---|---|
| I1 | `route_action` has exactly six call sites, in the five modules named in §2 | A seventh entry path appearing unreviewed |
| I2 | `AgentGateway` is constructed in exactly the four modules named in §3.1 | A surface that reaches the orchestrator without the gateway |
| I3 | Every capability in `REAL_EXECUTOR_CAPABILITIES` is reachable from a named path in §3, or listed in §3.5 | **The two-egress problem** and the unreachable checkpoint restore, both since closed; the invariant is what keeps a new registered executor from repeating either |
| I4 | Every module with a local `_ENABLED_GATE_STATES` is listed in §4 | A ninth local gate check appearing silently |
| I5 | `combine()` never returns `allow` for a hook decision | A hook gaining grant authority |
| I6 | Every tool in `MODEL_EXPOSED_TOOLS` has a `PolicyEngine` verdict | Already asserted — `tests/test_policy_engine.py` |

I3 is the one to build first: it is the invariant whose absence produced the
finding at the top of this document.

---

## 6. Open items

### GEP-01 — Eight modules re-implement the gate check

**Severity: Low. Area: governance architecture. Status: Open — raised 2026-08-23.**

**Observed.** Eight modules carry their own `_ENABLED_GATE_STATES` and read the
gate state directly from the store. Four of them are egress or subprocess paths.

**Why it matters.** Not because any of them is currently wrong — each was read
and each enforces its gate and its decision mode correctly. It matters because
*eight independent copies of a governance check* is the precondition for drift,
and this repository has already produced one instance of exactly that pattern in
the two egress implementations. It also means the agent-runtime stop switch does
not reach them (§4).

**Proposed work.** One shared `capability_admission(store, principal_id, capability)`
helper returning gate state, decision mode **and** the runtime-gate answer.
Replace all eight call sites with it. Add invariant I4.

**Governed outcome.** An owner who stops the agent runtime stops every path, and
a ninth local gate check cannot appear without failing a test.

### GEP-02 — The stop switch's scope is undefined for read paths

**Severity: Low. Area: governance semantics. Status: Open — raised 2026-08-23.**

**Observed.** `check_runtime_gate_enable` is applied in `route_action` only.
A `web_fetch`, an MCP tool call, an advisor consult and a GitHub connector read
do not consult it.

**The question, which is an owner decision and not an implementer's.** Does
"stop the agent runtime" mean *accept no new acting executions* — the current
behaviour — or *accept nothing that leaves this machine*? Both are defensible.
Only one is currently true, and no document says which.

**Proposed work.** Answer it in
[`NESTED_BOUNDARIES_ARCHITECTURE.md`](../NESTED_BOUNDARIES_ARCHITECTURE.md),
then make the code match. If the answer is the wider one, GEP-01's shared helper
is where it lands.

### GEP-03 — `NESTED_BOUNDARIES_ARCHITECTURE.md:278` overstates the architecture

**Severity: Low. Area: documentation. Status: Open — raised 2026-08-23.**

**Observed.** It names one non-bypass path that "every tool, command, plugin
action, channel action, memory write, graph query, checkpoint restore, model
control, or execution adapter must follow". A graph query and a memory write do
not follow it; they are governed at chokepoint A.

**Proposed work.** Rewrite that section against §2 of this document — two
chokepoints, what each applies, and which kind of action takes which. The claim
becomes weaker-sounding and true, which is the trade this repository makes
everywhere else.

### GEP-04 — Fifteen capabilities have no traced governed-action path

**Severity: Unknown — that is the point. Area: governance architecture.
Status: Open — raised 2026-08-23.**

**Observed.** `GovernedAction(` is constructed in four modules outside the
executor package. Between them they name `mcp_builder_runtime`,
`mcp_connector_runtime`, `external_channel_runtime`, `approval_execution_relay`,
and whatever tool the broker is dispatching. The fifteen capabilities listed at
the end of §3.6 are named by none of them.

**Why it is recorded rather than claimed.** Two readings, and this pass did not
establish which is true:

1. **Benign.** Each is reached through a control-plane service method that
   authorises differently — human-only, owner-scoped, `runtime_gate_manager`
   where required. Plugin installation is demonstrably like this. The capability
   gate then governs *activation*, not each action, which is a coherent design.
2. **A gap.** A registered executor that nothing constructs an action for is the
   shape `network_execution` had, and that one turned out to be a weaker
   duplicate of a guarded path that nobody noticed for months.

**Proposed work.** Trace each of the fifteen to its caller and record the answer
in §3.6. Where the answer is (1), say which control-plane method and what
authorises it. Where it is (2), it belongs in
[`TO_BE_FIXED.md`](TO_BE_FIXED.md) as a defect.

**Do this before GEP-01.** GEP-01 proposes a shared admission helper for the
eight local gate checks; if some of these fifteen also need it, the helper should
be designed once with both in view.

---

## 7. What this document is not

It is not a threat model. It says *what is crossed*, not *what could go wrong* —
that is [`../threat-models/`](../threat-models/README.md), one document per
capability with a real executor.

It is not the backlog. Items found here are raised as GEP-nn above and belong in
[`REFERENCE_PLATFORM_COMPATIBILITY.md §5`](../REFERENCE_PLATFORM_COMPATIBILITY.md#5-prioritised-backlog)
once they are prioritised.

**It must be updated when a path is added.** A new `route_action` call site, a
new `AgentGateway` construction, a new local gate check, or a new capability with
an executor is a change to this document as much as to the code.
