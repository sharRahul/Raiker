# Governance entry paths

**Canonical** for *how does an action reach an executor, and what does it cross
on the way*. This is the enumeration behind Raiker's central claim:

> No model, tool, skill, plugin, interface, runtime, or execution path reaches an
> action without crossing policy, capability gates, approvals and audit.

That sentence appears in `README.md`, in
[`NESTED_BOUNDARIES_ARCHITECTURE.md`](../architecture/NESTED_BOUNDARIES_ARCHITECTURE.md) and in
[`SECURITY_ARCHITECTURE.md`](../architecture/SECURITY_ARCHITECTURE.md). Until this document it
was **asserted and never enumerated** — there was no list of the paths, and
therefore no way to tell whether the claim was true, or to notice a new path
appearing beside the governed ones.

It exists because a claim nobody can check is not a control. Written **2026-08-23**,
derived from the code rather than from the other documents. **Revised 2026-08-24**:
GEP-04's trace is complete, GEP-01's shared admission helper ships, and both are
recorded below with what the trace found.

---

## 1. The finding that motivated this document

**The documentation says one chokepoint. The code has two, plus eleven callers that
read one of the checks themselves** — eight when this was written, each with its
own copy of the lookup; they now share one (GEP-01).

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
- **Eleven modules** read the capability-gate check locally rather than
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

**Exactly seven call sites enter B**, in six modules, and that is the number to
watch:

| Caller | Line | Why |
|---|---|---|
| `raiker/tools/broker.py` | `:1445` | The auto/skip fast path — an ordinary action the owner pre-authorised for this turn |
| `raiker/approvals/execution.py` | `:197` | `ApprovalExecutionBridge` — a human's *Approve* becoming an execution |
| `raiker/runtime/executors/tier1_approval.py` | `:287` | The relay re-routing the **target** capability, so it re-passes 1–10 at execution time |
| `raiker/control/service.py` | `:492`, `:838` | Governed control-plane mutations (capability gates, runtime state) |
| `raiker/runtime/authority/router.py` | `:1579` | Internal delegation |
| `raiker/memory/query_embedding.py` | `GovernedQueryEmbedder._embed` | MEM-10 query egress after its admission precheck; only Allow/low-risk Auto reach B |

An eighth call site appearing here is an architectural change and should be
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
| 7 | **Owner-stored channel route** | `POST /api/channels/{connector_id}/inbound` → `routes_channels.py` → `AgentGateway` | Authenticated channel secret, enabled pairing, sender allowlist, rate budget, then A and B. External text stays in the assistant/data slot; the runtime authors the instruction | Record only, a governed new turn, a tool-free side question, or an interrupt to the exact owner-selected conversation |

All seven construct `AgentGateway`, and **there are exactly nine construction
sites in five modules** — `routes_prompts.py` (`:327`, `:401`),
`routes_approvals.py` (`:479`, `:495`), `cli/commands.py` (`:1743`, `:3251`) and
`tasks/scheduler.py` (`:142`, `:213`), plus `routes_channels.py`. Nothing else in
the tree constructs one,
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
| 24 | **Plugin install** (GEP-04) | `/plugin-plan <manifest> --install` → `control/service.py::install_plugin` → **B**; human-only. The executor re-validates the manifest's size, JSON shape, plan status and supply-chain fields before it records anything | One install record for a manifest that passed the safe-install policy. Plugin *execution* stays disabled; the contributed hooks, skills and MCP offers are written only after the record exists |

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
| 17 | **Inbound channel message** | Owner secret, sender allowlist, 60/sender/minute, and an owner-stored pairing route | `record_only` grants nothing; `side_question` has no tools; `new_turn` and `interrupt` require the exact paired owner and still use ordinary runtime governance. Message content cannot select the route |
| 18 | **MCP tool call** | **A** (read-shaped), then a **local** gate + decision-mode check in `tools/mcp_tools.py` — see §4 | A bounded stdio JSON-RPC session against an owner-configured server |
| 19 | **Fetched web page** | The `web_fetch` gate, blocklist, address guard, sanitiser | The turn's context as **untrusted data**. Nothing fetched raises a turn's authority |
| 20 | **Hook handler** | `command` or `builtin`, bounded timeout, program resolved inside the workspace | Only `deny` or `ask`. `combine()` refuses `allow` from any handler — **a hook can never grant** |

### 3.5 Paths that exist and are not reachable

Recorded because an unreachable registered executor is the shape a future hole
takes.

**Nine rows, not one.** The 2026-08-23 pass recorded `process_execution` here and
left the question of the other fifteen open as GEP-04. Tracing them found that
nine capabilities have a real, registered executor that **no product path
reaches**, and the table below is now generated from the same source the runtime
and the Capabilities page read —
[`raiker/runtime/authority/entry_paths.py`](../../raiker/runtime/authority/entry_paths.py)
— rather than maintained by hand.

| Capability | Why nothing reaches it |
|---|---|
| `process_execution` | No `process` tool, not relayed by an approval. It runs the same `CommandService` lifecycle `shell_execution` does, so it is an *unused* path rather than a *weaker* one — which is why it survived the 2026-08-23 cut and `network_execution` did not |
| `plugin_runtime_cap` | Running an installed plugin's entrypoint has no owner surface |
| `plugin_sandboxed_runtime_cap` | The container-isolated plugin runtime has no owner surface |
| `plugin_sandbox_image_pull_cap` | Nothing runs a sandboxed plugin, so nothing pulls its image |
| `plugin_revocation_cap` | Revocation is performed by the plugin registry directly; no governed action is constructed for it |
| `channel_approval_relay` | Separately off by default. Queueing requires an enabled pairing with an explicit owner binding; response requires the exact owner, relay id and immutable action id and is single-use. Critical and connector-write approvals stay local ([FIXED-298](FIXED_ITEMS.md#fixed-298--a-paired-channel-could-still-only-record-a-message)) |
| `reminder_runtime` | No owner surface and no model tool. Nothing creates, lists or delivers a reminder |
| `calendar_runtime` | No owner surface and no model tool. Nothing syncs and nothing creates an event |
| `email_runtime` | No owner surface and no model tool. Nothing drafts, and nothing has ever sent |

**None of the nine is a hole.** An executor nothing constructs an action for
cannot run at all; the risk it carries is the opposite one, and it is the reason
this section exists — an unreachable registered executor is the shape a future
hole takes, because the day something *does* reach it, nobody re-reads the guard.
What the nine did cost the owner is recorded in §6 under GEP-04: each has a
switch on the Capabilities page that governed nothing.

**Three of the four rows this section held on 2026-08-23 are gone, and each left
for a different reason.** `network_execution` was deleted outright (capability,
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

**Reached by a model tool** — seventeen, each entering chokepoint B by name:

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
| `language_intelligence` | `document_symbols`, `find_definition`, `diagnostics` |
| `graph_indexing_runtime` | `knowledge_graph` |
| `web_fetch` | `web_fetch`, `web_search` |
| `remote_execution_cap` | `remote_execute` |
| `cloud_execution_cap` | `cloud_execute` |
| `subagents` | `spawn_subagent` |

Twelve of these seventeen are also **relayed by an approval**
(`EXECUTABLE_ON_APPROVAL`); `code_map_indexing`, `language_intelligence`,
`graph_indexing_runtime`, `web_fetch` and `subagents` are not. The thirteenth relayed capability,
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
| `model_provider_runtime` query embedding | `raiker/memory/query_embedding.py` — reads admission so Ask can fall back without parking a passive read, then routes Allow/Auto through chokepoint B |

**Reached by the control plane**, which enters chokepoint B like everything else:

| Capability | Where |
|---|---|
| `approval_execution_relay` | `ApprovalExecutionBridge`, `raiker/approvals/execution.py:197` |
| `audit_export` | `control/service.py::export_audit_log` (path 23) |
| `mcp_builder_runtime` | `control/service.py::_route_mcp` (`:492`) |
| `external_channel_runtime` | `control/service.py:838` |

**Traced 2026-08-24 — the fifteen that had no traced path.** GEP-04 asked
whether each was benign (reached through a control-plane method that authorises
differently) or a gap (a registered executor nothing constructs an action for).
The answer was neither of the two readings the question offered. It was three:

| Capability | What the trace found |
|---|---|
| `plugin_install` | **A gap, and closed.** `/plugin-plan <manifest> --install` called `record_plugin_install` directly — it wrote the install record, the trust level and the permission set without ever reading the `plugin_install` gate. It now builds a governed action through `RuntimeControlService.install_plugin` (path 24) |
| `subagents` | **A switch that governed nothing, and closed.** Delegation ran through path 11 whatever the gate said. `spawn_subagent` now answers to it |
| `container_execution_cap` | **Governed elsewhere, and correctly.** Running a tool in a container is chosen by enabling a container execution profile, and each call inside it is brokered under its own gate. Configuring the profile is the owner's act of authorisation |
| `scheduled_routines` | **Governed elsewhere.** A scheduled task runs as one whole governed turn through the Agent Gateway (path 6), so every action inside it answers to that action's gate |
| `semantic_memory_runtime` | **Governed elsewhere.** Recall answers to `vector_embedding_runtime`, which is the gate the retrieval path reads and the Memory page shows |
| `plugin_execution_cap` | **Governed elsewhere.** A plugin's brokered tool call runs through the ordinary broker against its validated read-only set (path 13), so each call answers to the gate of the tool it names |
| `multi_agent_teams` | **Governed elsewhere, prospectively.** No surface offers a team; when one does, each member runs as a subagent under the `subagents` gate |
| The other eight | **No path at all** — §3.5 |

**What the gate does is now a field, not an inference.**
[`entry_paths.py`](../../raiker/runtime/authority/entry_paths.py) records
`own_gate` / `governed_elsewhere` / `no_path` for all forty-five, the capability
DTO carries it, and the Capabilities page renders it beside the switch. A
capability whose switch does not decide whether it runs says so, and says what
does.

---

## 4. The twelve modules that check the gate themselves

These read the capability gate directly rather than calling
`RuntimeAuthority.check_capability_gate` through `route_action`. **Since
2026-08-24 they no longer each carry a copy of the lookup**: all of them call
`capability_admission` in
[`raiker/runtime/authority/admission.py`](../../raiker/runtime/authority/admission.py),
which is GEP-01 closed.

| Module | Capability | Shape |
|---|---|---|
| `raiker/runtime/web_access.py` | `web_fetch` | **Egress** |
| `raiker/runtime/connectors.py` | `connector_github_runtime` and the three other read connectors | **Egress** |
| `raiker/runtime/advisor.py` | `advisor_model_runtime` | **Egress** |
| `raiker/tools/mcp_tools.py` | `mcp_connector_runtime` | **Subprocess + egress** |
| `raiker/graph/codemap_service.py` | `code_map_indexing` | Local read-derived |
| `raiker/graph/language_service.py` | `language_intelligence` | Local read; derives nothing durable |
| `raiker/runtime/retrieval.py` | `vector_embedding_runtime` | Local read |
| `raiker/memory/candidates.py` | memory candidates | Local read |
| `raiker/models/policy_state.py` | provider gate state | Local read |
| `raiker/tools/subagent_tools.py` | `subagents` | Local delegation (GEP-04) |
| `raiker/context/gatherer.py` | every gate it reports | **Describes rather than enforces** |
| `raiker/memory/query_embedding.py` | `model_provider_runtime` | **Egress admission precheck, followed by chokepoint B** |
| `raiker/control/service.py` | every gate it reports | **Describes rather than enforces** (BUG-239) |

**This is defensible and it is not free.** The design intent is stated in
`raiker/policy/engine.py:132–138`: a projected MCP tool is *read-shaped at the
policy layer* because what actually governs it is enforced inside the tool. The
same argument covers the others.

**The two describing modules are here for the opposite reason to the rest.**
`context/gatherer.py` and, since 2026-08-30, `control/service.py` decide nothing
at all — they *report* a gate, to the model and to the owner respectively. They
read `capability_admission` precisely because a description that resolves an
empty gate table its own way is a description that can contradict the thing it
describes, and both of them once did: the gatherer told the model
`web_fetch: disabled` on an install where the tool would have fetched, and the
gate view told the owner the same thing on the Permissions page
([FIXED-322](FIXED_ITEMS.md#fixed-322--permissions-said-off-about-a-capability-that-would-have-run)).
Holding a description to the enforcing path's own answer is the only way to
close that, and it is why a *read* belongs in a list of modules that skip
chokepoint B.

**Two drifts were live in the original eight copies, and neither was visible from any one
of them.** Both are closed by the shared helper:

* **Scope.** `RuntimeAuthority` resolves the control scope with
  `store.account_scope`, which maps a delegated AI-agent principal onto the owner
  account that delegated it. The eight used `store.get_account(pid) is not None`,
  which does not — so the same capability could read the owner's gate at
  chokepoint B and the workspace-wide gate inside the tool. No shipped path
  passed an AI-agent principal to any of the eight, so this was **latent, not
  live**.
* **What an empty gate table means.** Three different answers. Seven read "no row"
  as off. `codemap_service.py` fell back to the shipped table for a caller with
  no account, matching `check_capability_gate`. `web_access.py` fell back for
  *any* caller (RAIKER-2021). This one **was live, and it was visible to the
  model**: the context bundle reported `web_fetch: disabled` on a fresh install
  while `WebAccessService` would have allowed the fetch. The three resolutions
  still exist — unifying them would either loosen seven paths or tighten one —
  but they are now one table, `CAPABILITY_UNSET_RESOLUTION`, read by the
  enforcing path *and* by every surface that describes it.

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

## 5. Invariants asserted by test

**All of them are asserted**, in
[`tests/test_governance_entry_paths.py`](../../tests/test_governance_entry_paths.py)
unless another file is named. Each is cheap, and each would have caught a real
defect this repository has already had.

| # | Invariant | Would have caught |
|---|---|---|
| I1 | `route_action` has exactly six call sites, in the five modules named in §2 | A seventh entry path appearing unreviewed |
| I2 | `AgentGateway` is constructed in exactly the five modules named in §3.1 | A surface that reaches the orchestrator without the gateway |
| I3 | Every capability in `REAL_EXECUTOR_CAPABILITIES` is named in this document **and** classified in `entry_paths.py` | **The two-egress problem** and the unreachable checkpoint restore, both since closed; the invariant is what keeps a new registered executor from repeating either |
| I3b | The tool-reachable set is exactly sixteen | A capability moving between §3.6's categories without the document moving |
| I4 | Every module reading a capability gate itself calls `capability_admission`, and is listed in §4 | A further local gate check appearing silently. **The original form of this — "has a local `_ENABLED_GATE_STATES`" — already missed one**: `context/gatherer.py` spelled the constant without the leading underscore and was absent from §4 for that reason alone |
| I4b | No module outside `admission.py` declares its own enabled-state set | The three-way fork in what an empty gate table means |
| I5 | `combine()` never returns `allow` for a hook decision | A hook gaining grant authority |
| I6 | Every tool in `MODEL_EXPOSED_TOOLS` has a `PolicyEngine` verdict | `tests/test_policy_engine.py` |
| I7 | Every `own_gate` claim matches `TOOL_DEFINITIONS` / `EXECUTABLE_ON_APPROVAL`, and every non-`own_gate` row carries a sentence naming what really governs it | A gate labelled as governing something it does not, which is the whole of GEP-04 |

**I4's first form is the lesson worth keeping.** It watched for a *marker* — a
constant with a particular name — rather than for the *behaviour*. A module could
drop the marker and keep the drift, and one module never had the marker in the
first place. It now watches for callers of the shared helper, which is the actual
seam.

---

## 6. Open items

### GEP-01 — Eight modules re-implement the gate check

**Severity: Low. Area: governance architecture.
Status: Closed 2026-08-24 — [FIXED-279](FIXED_ITEMS.md#fixed-279--eight-copies-of-one-governance-check-and-two-of-them-had-already-drifted).**

**Observed.** Eight modules carried their own `_ENABLED_GATE_STATES` and read the
gate state directly from the store. Four of them are egress or subprocess paths.

**Why it mattered.** Not because any of them was *wrong* — each enforced its gate
and its decision mode correctly. It mattered because eight independent copies of
a governance check is the precondition for drift, and this repository had already
produced one instance of exactly that pattern in the two egress implementations.

**And it had already drifted, twice.** Reading the eight side by side is what
found it; neither is visible from any one of them. §4 records both. One was
latent (scope, for a delegated AI principal). **One was live and visible to the
model**: three different answers to "what does an empty gate table mean", so the
context bundle told the model `web_fetch: disabled` on a fresh install while the
tool would have allowed the fetch. That is the same class of defect as GEP-04 —
a stated control that is not the enforced one — arrived at from the other end.

**What shipped.** `capability_admission(store, principal_id, capability)` in
`raiker/runtime/authority/admission.py`, returning gate state, decision mode,
control scope and the runtime status. All eight call it, and so do the two paths
added since (`subagent_tools.py`, `context/gatherer.py`). The three unset
resolutions survive as a named table, `CAPABILITY_UNSET_RESOLUTION`, because
collapsing them would either loosen seven paths or tighten one — an owner-visible
change, not a refactor — but every surface that *describes* a gate now reads the
same rule the enforcing path does. Invariants I4 and I4b assert it.

**What did not ship, and why.** The helper reports `runtime_active` and nothing
consults it. Whether stopping the agent runtime should also stop a read that
leaves the machine is GEP-02 below — an owner's decision, not an implementer's.
Making the helper carry the answer costs nothing and decides nothing; flipping it
is now a one-line change in one place, which is the most this item should do
before that question is answered.

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
[`NESTED_BOUNDARIES_ARCHITECTURE.md`](../architecture/NESTED_BOUNDARIES_ARCHITECTURE.md),
then make the code match.

**GEP-01's helper is now where it lands, and it is already carrying the answer.**
`CapabilityAdmission.runtime_active` reports whether the runtime is accepting
executions; no call site consults it. Choosing the wider reading is a one-line
change in one place — which is deliberately as far as an implementer should take
an owner's decision.

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

**Severity: Unknown when raised; Medium once traced. Area: governance
architecture. Status: Closed 2026-08-24 — [FIXED-280](FIXED_ITEMS.md#fixed-280--fifteen-capability-switches-that-governed-nothing-and-one-that-should-have).**

**The trace is in §3.6 and §3.5. What it found is that neither of the two
readings below was right, and the thing they both missed is the finding.**

Both readings asked whether an *action* could reach an executor ungoverned. For
fourteen of the fifteen the answer was no. But every one of the fifteen has a
gate, the Capabilities page renders every gate as a switch, and for all fifteen
**flipping that switch changed nothing**. Nine had no executor path at all. Five
had their work governed by a different control the gate never consults. One —
`plugin_install` — was the gap the second reading described.

An owner holding a switch that governs nothing is not a smaller version of an
ungoverned action. It is a different defect, and for a product whose claim is
that the owner is in control, a worse one: the ungoverned action is a hole in the
implementation, and the inert switch is a hole in what the owner believes.

**What shipped.**

* `plugin_install` is a governed action (§3.2 path 24). The terminal's
  `/plugin-plan --install` went straight to `record_plugin_install`; an owner who
  had deliberately held that capability off could install a plugin anyway.
* `subagents` governs delegation. `spawn_subagent` had `capability=None` on the
  argument that spawning is no more authority than the parent already held —
  true of *what a subagent may touch*, never true of *whether the owner wanted
  delegation at all*.
* `entry_paths.py` records `own_gate` / `governed_elsewhere` / `no_path` for all
  forty-five, with a required sentence for the last two. The DTO carries it and
  the Capabilities page renders it beside the switch, so a gate that does not
  decide whether its capability runs says so, and says what does.
* Invariant I7 checks every claim in that table against `TOOL_DEFINITIONS` and
  `EXECUTABLE_ON_APPROVAL`, so a new executor cannot ship without classifying
  itself.

**What was deliberately not changed.** `container_execution_cap`,
`scheduled_routines`, `semantic_memory_runtime`, `plugin_execution_cap` and
`multi_agent_teams` are labelled, not gated. Each is already governed — per
action, per turn, or by the owner's act of configuring a profile — and adding a
second switch in front of a choice the owner already made is the wall
[`SECURITY_AND_POLICY.md`](../architecture/SECURITY_AND_POLICY.md) → "Security Philosophy"
exists to refuse. The nine with no path keep their gates for the same reason
§3.5 keeps its list: the day something reaches one of them, the gate is what is
already there.

**The original question, kept because it is what was actually asked:**

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

**Doing this before GEP-01 was the right call, and for the reason given.** Two of
the fifteen did need the shared helper — `subagents` reads its gate through
`capability_admission`, and so does the context bundle that describes it — so the
helper was designed once with both in view rather than twice.

---

## 7. What this document is not

It is not a threat model. It says *what is crossed*, not *what could go wrong* —
that is [`../threat-models/`](../threat-models/README.md), one document per
capability with a real executor.

It is not the backlog. Items found here are raised as GEP-nn above and belong in
[`REFERENCE_PLATFORM_COMPATIBILITY.md §5`](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#5-prioritised-backlog)
once they are prioritised.

**It must be updated when a path is added.** A new `route_action` call site, a
new `AgentGateway` construction, a new local gate check, or a new capability with
an executor is a change to this document as much as to the code.
