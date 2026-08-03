## Goal

Make Raiker a secure AI product that combines an AI assistant, a governed AI
agent, and an extensible agent platform.

As an assistant, Raiker should help users understand, reason, decide, and
communicate through a polished conversational experience. As an agent, Raiker
should be able to plan tasks, gather context, use tools, execute approved
actions, verify outcomes, and explain what it did. As a platform, Raiker should
provide the governed runtime foundation for models, tools, plugins, interfaces,
memory, approvals, audit events, checkpoints, and integrations.

Raiker must support user-owned model choice across LLM backends — local models
such as llama.cpp, Ollama, and LM Studio; home-lab runtimes such as vLLM;
private-network providers; and hosted API providers such as Anthropic, OpenAI,
Gemini, and OpenRouter. No model, interface, plugin, or capability should
bypass governance. Every action must remain policy-aware, observable,
auditable, approval-driven where required, human-governed, user-controlled, and
fail-closed by design.

## Security posture (read before adding any restriction)

Raiker is **owner-authoritative and monitored, not prevention-by-restriction.**
Security is not restricting the user; it is a frictionless system that lets the
owner operate securely without having their access taken away. Do **not** put a
hard block in front of the owner's legitimate choices (e.g. connecting a remote
MCP server) by default — **allow, monitor, surface anomalies as findings +
notifications, and give the owner an instant stop plus an automatic revocable
pause for the irreversible/high-severity cases.** Reserve hard prevention for a
last resort and justify it against this posture. Full statement:
`docs/SECURITY_AND_POLICY.md` → "Security Philosophy". The rules below still hold
and are compatible with it:

# To be added

**Status: proposals, not defects and not parity gaps.** Nothing in this document
is broken and nothing here is required for Raiker to be correct. This is the
capability roadmap: what Raiker would need to gain autonomous self-improvement,
advanced coding routines, and multi-platform reach **without** trading away the
zero-trust architecture it already has.

Every entry is bound by one rule, and an entry that cannot satisfy it does not
ship:

> **Autonomy cannot equal privilege escalation.**

Each entry is written to the same standard as the defects and the gaps: what
exists in the codebase today with the file that proves it, what is missing, the
concrete work, and the governed outcome the owner should see when it lands.
Several entries are **partly shipped** — the original proposal predates work that
has since landed, and the entry now records only the remainder. That is stated
per entry rather than left for a reader to discover.

[`TO_BE_FIXED.md`](TO_BE_FIXED.md) — FIXED and BUG — are defects found while
executing [the live manual test plan](RAIKER_LIVE_MANUAL_TEST_PLAN.md) against a
running `raiker-web`. [`GAP_BUILD_CHAT.md`](GAP_BUILD_CHAT.md) — GAP-BUILD and
GAP-CHAT — is the itemised distance between what Build and Chat ship today and
what each is meant to be. **This document is neither.** A gap is a capability a
class-leading product already has that Raiker lacks; an ADD entry is a capability
that would put Raiker ahead of the field.

| ID | Tier | Area | Status |
|---|---|---|---|
| ADD-01 | Tier 0 | Execution / container backend | Partly shipped (see FIXED-47) |
| ADD-02 | Tier 0 | Runtime / tool queue and gates | Shipped |
| ADD-03 | Tier 0 | Identity / agent attestation | Proposal |
| ADD-04 | Tier 0 | Audit / transaction lineage | Proposal |
| ADD-05 | Tier 1 | Skills / self-evaluation loop | Proposal |
| ADD-06 | Tier 1 | Skills / zero-trust authoring gate | Proposal |
| ADD-07 | Tier 1 | Policy / policy-as-code | Proposal |
| ADD-08 | Tier 1 | Audit / deterministic replay | Proposal |
| ADD-09 | Tier 2 | Models / context and cost tiering | Proposal |
| ADD-10 | Tier 2 | Security / credential cloaking | Proposal |
| ADD-11 | Tier 3 | Channels / inverted gateway | Proposal |
| ADD-12 | Tier 4 | Execution / ephemeral micro-VMs | Proposal |
| ADD-13 | Tier 4 | Extensions / MCP supply chain | Proposal |
| ADD-14 | Tier 4 | Platform / hardware root of trust | Proposal |
| ADD-15 | Tier 5 | Approvals / WebAuthn step-up | Proposal |
| ADD-16 | Tier 5 | Runtime / adversarial intent modelling | Proposal |
| ADD-17 | Tier 5 | Runtime / internal debate core | Proposal |
| ADD-18 | Tier 5 | Agents / relationship-based access control | Proposal |
| ADD-19 | Tier 6 | Build / code provenance watermarking | Proposal |
| ADD-20 | Tier 6 | Verification / continuous chaos injection | Proposal |

### Tier order

Tier 0 is the foundation: without a real execution boundary and a distinct agent
identity, everything above it inherits the owner's privileges and the rest of the
list is decoration. Tier 1 is what makes autonomy safe to leave running. Tier 2
and Tier 3 are reach — more context and more surfaces, both of which widen the
blast radius, so neither should precede Tier 0. Tiers 4–6 are the differentiators
that put Raiker beyond the field, and every one of them is expensive; none should
start before the tiers below it are closed.

**Owner decisions, not implementer decisions.** ADD-11, ADD-14 and ADD-18 change
what Raiker *is* — a machine that reaches the public internet, a machine that
requires specific hardware, a machine with more than one principal. They belong
to the owner. `docs/NESTED_BOUNDARIES_ARCHITECTURE.md` is where the multi-
principal question has to be answered.

---

## ADD-01 — Containerised tool execution instead of a record-only mode

**Status: partly shipped — see FIXED-47. This entry records the remainder.**

**Today.** `raiker/runtime/executors/containers.py` already implements the
proposal's core: an owner-allowlisted image, no network, dropped capabilities, no
host mounts, memory/CPU/PID limits, a read-only rootfs, a non-root user derived
from the host uid/gid, and a wall-clock timeout. An empty allowlist denies
everything, so it fails closed. `command_sandbox_image()` refuses to fall back to
the host when `RAIKER_COMMAND_SANDBOX_IMAGE` is unset or unmatched — a standing
grant is not permission to escape the boundary. `raiker/tools/broker.py` routes
granted commands through it.

**Missing.** The boundary covers *commands granted under B5*. It does not yet
cover the general tool surface, and `container_execution_enabled` remains one of
the hardcoded-`False` capability flags in `raiker/context/gatherer.py`. There is
no per-tool container profile, no read-only mount of the repository with a single
writable workspace subdirectory, and no Podman path.

**Work.** Extend `raiker/execution/profiles.py` with per-tool container profiles
so any tool call — not only a granted command — can be routed into an ephemeral
container. Mount the connected repository read-only with one writable workspace
subdirectory rather than handing the container the whole tree. Add Podman as a
runtime alternative behind the same interface, and lift
`container_execution_enabled` to a real gate rather than a constant.

**Governed outcome.** The execution environment selector already shipped by
FIXED-70 names the container profile a tool will run under, and a tool whose
profile is unavailable says so instead of silently running on the host.

---

## ADD-02 — A sequential tool queue with per-call approval gates

**Status: shipped. Delivered by FIXED-39 (B4), FIXED-97, and this change.**

**Today.** The original proposal described a runtime that dropped every tool call
after the first without telling the model. That is no longer true. FIXED-39 (B4)
executes every validated read-only proposal concurrently and returns each result
under its matching call id in one provider-valid batch; mutations stay serial and
stop at the first approval or policy boundary. Budget- or boundary-deferred calls
emit `model_tool_calls_dropped` with proposed/accepted/dropped counts, so no call
disappears without evidence — and FIXED-97 fixed the declared-event gap that made
emitting that evidence kill the turn.

**What was missing.** The loop parked on the *first* approval boundary and
resumed there (FIXED-09). It did not park, surface, and resume **per call**
through a multi-call batch: a batch containing three mutations stopped at the
first one, dropped the other two with an event, and left the owner no way back to
them except a re-prompt. A model that proposed three edits got one edit.

**What shipped.** The suspended turn now carries the rest of the batch, and the
resume walks it:

* **The queue is parked with the turn.** `suspended_turns` gains
  `pending_calls_json`, `queue_position` and `queue_total`
  (`RAIKER-1036-suspended-turn-queue`), so the queue survives the pause — the
  owner may take hours, close the tab, or restart the host between two decisions.
  `raiker/runtime/turn_suspension.py` holds the serialisation, and an unreadable
  queue drains to nothing rather than failing a resume and discarding a decision
  the owner has already made.
* **Calls before the boundary are kept, not lost.** Anything that really executed
  ahead of the parked call now enters the parked conversation with its result and
  its spent budget, so the model resumes into a transcript where its own completed
  work happened.
* **The remainder is queued, not dropped.** An approval boundary emits
  `model_tool_calls_queued` (counts and position only); `model_tool_calls_dropped`
  is now reserved for calls that genuinely will not run.
* **The resume drains the queue before it calls the model.** Each queued call is
  re-validated and re-governed on its own terms — its own decision mode, its own
  policy review — and a call that needs approval parks the same turn again as the
  next decision. The model is not asked again for a call it has already proposed.
* **A refusal skips its own call.** A policy denial inside the queue is reported
  against that call and the queue continues (`DENIED → POLICY_REVIEWED` is now a
  legal runtime transition, because a refusal inside a batch ends a call rather
  than a turn). The model is told which call was refused so it does not read the
  refusal as covering the ones still to come.

**Governed outcome.** Approvals says **Decision 2 of 3** on the row and in the
review pane; resolving one says how many calls are still queued behind it; and
continuing lands on the next decision of the same batch rather than on a new
prompt. A denial reaches the model as a per-call refusal and the batch carries on.

**Evidence.** `tests/test_batched_approval_queue.py` covers parking, queue
ordering, the kept pre-boundary results, draining, per-call re-governance, the
rejection and policy-refusal paths, and the migration defaults for rows written
before the queue existed. The live scenario is
[`e2e/add-02-batched-approval-queue-live.spec.ts`](../../apps/web/e2e/add-02-batched-approval-queue-live.spec.ts),
whose screenshots are `working/add-02-*`. It drives a running `raiker-web` — its
own orchestrator, broker, policy engine, approvals inbox, suspended-turn store
and resume endpoints — with a **local OpenAI-compatible stub as the model**, not
a hosted provider, because what ADD-02 changes is how the runtime handles a
multi-mutation batch and a hosted model does not reliably emit the same batch
twice. In that run the capability gate for file writes is off, so the decisions
resolve metadata-only; a batch whose approvals really *write* is covered by
`test_the_whole_batch_can_be_walked_to_the_end`, which asserts all three files on
disk.

---

## ADD-03 — The agent needs its own identity, not the owner's

**Status: proposal. This is the entry the rest of Tier 0 depends on.**

**Today.** When the owner connects a hosted provider, the agent executes under the
owner's authority. `raiker/runtime/authority/` resolves a principal, and
`PrincipalType` distinguishes principal *kinds*, but the downstream sandbox still
reads a request to write a file or call an endpoint as *the owner asked for this*.

**The vulnerability — privilege mirroring.** An indirect prompt injection — a
hidden instruction inside a repository the agent is reading, an email it is
summarising, an MCP tool result — produces a command. Because the agent mirrors
the owner's identity, the system executes it. Every cage in Tiers 4–6 is useless
against this: the guard believes the owner unlocked the door.

**Work.** Give each spawned agent thread a short-lived, cryptographically signed
machine identity — a SPIFFE ID issued by an embedded SPIFFE/SPIRE-style issuer —
that is *strictly lower-privileged than the human owner* and is minted per turn,
not per session. The broker checks the identity token, not the session, before it
brokers an action. Presenting the owner's OAuth token from a machine identity must
be rejected on the machine identity, so a mirrored credential buys nothing.

**Governed outcome.** Approvals and the audit log state which identity proposed an
action — owner or machine — and the capability matrix shows the two as separate
columns. An owner can see, at a glance, what the agent may do *without* them.

---

## ADD-04 — Bounded transaction lineage and an automatic kill switch

**Status: proposal. Pairs with ADD-03; neither is complete alone.**

**Today.** `raiker/events/integrity.py` already chains events by
`payload_sha256` / `prev_event_sha256` and verifies the chain per session, so the
log is tamper-evident. FIXED-95 gives subagents their own principal and contract,
and FIXED-77 records source coordinates for a passage inside a turn.

**Missing — the lineage chain.** When a turn spawns subagents, the resulting file
write arrives as a flat operation. The chain proves *the log was not edited*; it
does not prove *which subagent produced this text, from which input*. A subagent
that reads a contaminated web page and inserts a backdoor is indistinguishable, at
the point of write, from one that did the work correctly.

**Work.** Append an immutable signature to every API call, file read, and
generation that traces the full parent execution tree, so any proposed write can
be walked back: owner → orchestrator → subagent → the exact untrusted input that
triggered it. When the walk reaches an untrusted source, freeze that execution
branch automatically and raise it as a finding rather than a silent denial — the
posture is *revocable pause plus notification*, not prevention.

**Governed outcome.** Every approval carries a "where did this come from" trail
the owner can expand, and a frozen branch appears in notifications with the
untrusted source named and a one-click resume.

---

## ADD-05 — A self-evaluation loop over the audit log

**Status: proposal.**

**Today.** `raiker/skills/service.py` is a real owner-scoped skill service:
install, rename, activate, download, delete, with `raiker/skills/package.py`
validating every stored document and `raiker/skills/builtin/` shipping three
skills. A skill is instruction text — it grants no capability, opens no gate, and
Raiker never executes anything a skill ships. `docs/SELF_IMPROVEMENT_MODEL.md`
describes procedural memory that is never consulted at turn time.

**Missing.** Every skill is authored by a human. Nothing reads execution traces
back and proposes a skill from them, so Raiker repeats the same mistake as often
as it is asked to.

**Work.** A background worker that periodically reads execution traces from the
append-only event log, clusters repeated failure/retry shapes, and drafts a
candidate `SKILL.md` describing the procedure that worked. It writes a *candidate*
only — the existing memory-candidate posture (the model proposes, the owner
accepts) is the right precedent, not silent learning.

**Governed outcome.** A "Raiker noticed a pattern" candidate appears in Skills
with the traces that produced it, and the owner accepts, edits, or discards it.

---

## ADD-06 — A zero-trust gate for self-authored skills

**Status: proposal. Do not ship ADD-05 without it.**

**Today.** Human-authored skills are validated by `raiker/skills/package.py`, and
`SkillsService.import_from_url` reads over HTTPS through the existing sandbox
egress boundary, so it fails closed unless the owner allowlisted the host. Other
agent platforms solve skill distribution with a public marketplace and inherit
supply-chain malware injection with it. Raiker should not.

**Missing.** There is no *pending* state for a skill the agent wrote itself, and
no step-up before its first use.

**Work.** Treat an agent-authored skill as untrusted code even though it is only
text — text is the injection surface. Write it into `.raiker/skills/` in a
`pending` state that no turn may load. Tie its first activation to the existing
Runtime Gate Manager step-up so the owner must read the proposed optimisation in
the web UI and type the intent phrase before it can influence a single turn.
Re-gate on edit, not only on creation.

**Governed outcome.** Skills shows pending agent-authored skills separately from
installed ones, with a diff of what the agent wants to teach itself and an
explicit "never generated by a human" label that survives activation.

---

## ADD-07 — A policy-as-code engine

**Status: proposal.**

**Today.** `raiker/policy/engine.py` and `raiker/policy/config.py` hold the policy
sets in Python. `PolicyEngine.review` hard-denies anything in neither set — the
invariant FIXED-98 now tests. Decision modes are per-capability and enforced
server-side. But the *content* of policy is code, and widening it for a legitimate
workflow means a code change.

**Missing.** A declarative, owner-editable contract. Today an owner who wants "npm
install and web search may run unattended, but anything touching `production/` or
fetching an un-allowlisted domain needs step-up" has to write Python.

**Work.** Add a machine-readable YAML policy layer in front of `PolicyEngine`,
evaluated as middleware and reconciled with the existing sets rather than layered
beside them — the third-policy-set failure mode is already recorded as BUG-51 and
must not be repeated. Declarative rules bind action, path scope, egress domain,
and required decision mode. Frameworks such as Microsoft's
[Agent Governance Toolkit](https://github.com/microsoft/agent-governance-toolkit)
are a reference for the contract shape, not a dependency to adopt blind.

**Governed outcome.** Capabilities gains a policy editor that shows the effective
verdict for any (tool, path, domain) triple before it is saved, and a rule that
would widen egress says so in the diff.

---

## ADD-08 — Event-sourced deterministic replay

**Status: proposal. Builds directly on ADD-04.**

**Today.** `raiker/events/` writes an append-only, hash-chained log and
`raiker/checkpoints/` records restorable state. FIXED-94 makes the turn plan a
recovery point rather than a progress bar, and B18 (`GAP_BUILD_CHAT.md`) asks for
a per-turn rewind in Build.

**Missing.** Checkpoints restore *state*. They do not let anyone re-run the
decision. Raiker can show what changed and cannot prove why the model chose it,
which is exactly the property that matters over a multi-hour run.

**Work.** Treat the audit log as a sequence of immutable, signed state mutations
rather than as text, and build a replay kernel that rewinds memory, workspace, and
tool environment to point X and re-runs forward deterministically. The value is
not the rewind — it is being able to force the agent down a different reasoning
path from a known-good state and compare.

**Governed outcome.** A failed run offers "rewind to before this turn and retry
differently", and the audit view can step through the exact token generation and
file change that preceded a failure.

---

## ADD-09 — Context-compaction tiering with model asymmetry

**Status: proposal.**

**Today.** Raiker supports owner-chosen local and hosted models, and FIXED-53
synchronises provider pricing into a historical registry so cost is real rather
than notional. Routing exists; **security does not vary with the route.** A hosted
model and a local one are trusted identically with context.

**Missing.** The premium hosted model sees the whole project scope. For an owner
whose reason for running locally is that the project should not leave the machine,
that is the wrong default.

**Work.** Route structural planning and task-state fidelity through a deterministic
**local** model that acts as a standing "cortex guard" holding the high-level task
memory, and use the hosted model only for bounded generation — a snippet, a
rewrite, a long passage — with a compacted, scoped slice of context. The local
model never leaves the machine, so the hosted model never gains full contextual
visibility over the repository.

**Governed outcome.** Models shows which tier holds task memory and which tier is
being handed generation work, and the context popover states exactly how much of
the project the hosted model can see.

---

## ADD-10 — Credential cloaking and AST-level sanitisation

**Status: proposal.**

**Today.** `raiker/context/redaction.py` redacts secrets, tokens, emails, and
private keys out of gathered context, and the FIXED-02/07/11/14 series tightened
it so it stops destroying legitimate values. `raiker/runtime/connector_ecosystem.py`
requires a Fernet vault key before it will encrypt a credential.

**Missing.** Redaction is pattern-based over text. When a code file is fed to the
model, an active `.env`, an SSH key, or a cloud token in an unusual shape can
still reach the context window — and once redacted, the *tool* cannot use the real
value either, so the sanitisation and the execution paths are at odds.

**Work.** Add an AST-level sanitisation layer to the file-reading path that
understands the file it is reading rather than pattern-matching it, and replace
every intercepted secret with a dynamic, non-functional mock token
(`REDACTED_RAIKER_TOKEN_01`). Map the mock tokens back to the real environment
variables **inside the isolated container session only** (ADD-01), so the host's
secrets never enter the model's text context and the tool still works.

**Governed outcome.** The file inspector shows which values were cloaked in a file
the model read, and a tool run that consumed a cloaked value records that it did
without recording the value.

---

## ADD-11 — The inverted gateway: reaching the owner off the machine

**Status: proposal. This is an owner decision before it is an engineering one.**

**Today.** `config/channel-connectors.json` declares cli, tui, rest, web_ui,
desktop, dashboard, ide, apple_mobile, android_mobile and webhooks, and
`raiker/channels/registry.py` loads them — but `external_channels_enabled` and
`notifications_enabled` are both hardcoded `False` in
`raiker/context/gatherer.py`. Raiker binds to the local host. Scheduled routines
run and finish with nobody told (GAP-CHAT C10).

**Missing.** Any surface where the assistant reaches the owner who is not at the
machine — WhatsApp, Telegram, Discord, or a phone notification.

**The constraint.** Moving Raiker to a public server, or fronting it with a
reverse proxy, is the failure mode that has produced the worst incidents in
comparable agent platforms. It must not be the answer.

**Work.** Invert the direction: a local polling daemon that reaches *out*. A
lightweight, isolated bot process holds a long-poll or authenticated WebSocket
connection to the platform API, pulls messages down to the local machine, maps the
incoming platform user id to a specific acting principal in the local database,
and forces every remote command through the same capability gates, decision modes
and audit path as the local interface. Raiker never accepts an inbound connection.

**Governed outcome.** Settings shows each connected channel, the principal each
remote identity maps to, and a per-channel stop. An unmapped sender reaches
nothing.

---

## ADD-12 — Ephemeral micro-VMs instead of shared-kernel containers

**Status: proposal. Supersedes ADD-01's boundary; do not start it first.**

**Today.** ADD-01's container boundary shares the host kernel. That is a real
boundary and it is the right first step, but a kernel vulnerability reached
through a prompt injection is a container breakout, and a breakout is the whole
machine.

**Work.** Execute commands inside micro-VMs with their own kernel — Firecracker or
gVisor — behind the same executor interface `raiker/runtime/executors/` already
defines, so the boundary can be swapped without rewriting the broker. Firecracker
boots an isolated VM in single-digit milliseconds, which is what makes per-tool
isolation affordable rather than theoretical: a malicious script or a runaway loop
is trapped in a disposable kernel that vanishes when the task ends.

**Governed outcome.** The execution environment selector names the isolation class
— host, container, micro-VM — and a profile that cannot provide the requested
class fails closed and says which one it could provide.

---

## ADD-13 — An MCP analysis gateway and a supply-chain kill switch

**Status: proposal.**

**Today.** FIXED-17 made a connected server's tools callable as
`mcp__<server>__<tool>`, and FIXED-96 made the surface honest about whether the
agent can reach them. `raiker/security/mcp_monitor.py` exists and MCP tool output
is treated as untrusted data. Connecting a remote MCP server is an owner choice
Raiker deliberately allows rather than blocks.

**Missing.** Nothing inspects what a server *is* before it is called, and nothing
compares what it does against what it declared. An extension whose metadata hides
a prompt injection is indistinguishable from a legitimate one.

**Work.** Run every external extension through a local static analysis pass before
first execution, looking for injection-shaped metadata and structural
manipulation. Then hold the running server to its declared manifest signature: if
it attempts a behaviour it never declared — reading paths outside its scoped
workspace, an egress it did not register — break the circuit, terminate the
execution thread, and freeze the extension pending owner review.

**Governed outcome.** Extensions shows each server's analysis verdict and its
declared surface, and a frozen server appears in notifications with the exact
deviation that froze it and a one-click restore.

---

## ADD-14 — A hardware root of trust

**Status: proposal. Owner decision — it constrains what hardware can run Raiker.**

**Today.** If the host operating system is compromised, an attacker can reach
Raiker's local credentials, edit its memory, or take its OAuth tokens. Every
software boundary in this document assumes the host is honest.

**Work.** Run the core daemon inside a hardware-enforced trusted execution
environment — AMD SEV-SNP or Intel TDX — so its data stays encrypted in memory.
An attacker with full root on the host is then barred by the CPU, not by policy,
from scraping the reasoning loop, the secrets vault, or an active session token.

**The cost, stated plainly.** This restricts Raiker to specific CPUs and
complicates local development. It should be an opt-in deployment profile with a
documented non-TEE fallback, not a requirement — the owner chooses their hardware.

**Governed outcome.** Diagnostics reports attestation state, and a Raiker running
without a TEE says so rather than implying a guarantee it does not have.

---

## ADD-15 — WebAuthn step-up instead of a typed phrase

**Status: proposal.**

**Today.** High-risk actions require the owner to type an intent phrase into the
web UI (`confirmation_token` in `raiker/api/schemas.py`, enforced through
`routes_control.py`). It works, it is auditable, and FIXED-18 made it
self-explanatory.

**Missing.** A typed phrase is shoulder-surfable, replayable from a captured
session, and tedious enough that a busy owner will look for a way around it —
which is its own security failure.

**Work.** Move the Runtime Gate Manager to a WebAuthn passkey or platform
authenticator (Touch ID, Windows Hello, a hardware key), keeping the typed phrase
as the documented fallback for headless and CLI use. Bind the assertion to the
exact action payload so it authorises *that* block of instructions and cannot be
replayed against another.

**Governed outcome.** Approving a high-risk action prompts for the passkey and
records which authenticator satisfied it, so the audit trail shows a
hardware-backed human decision rather than a string that matched.

---

## ADD-16 — A Safety Critic running alongside the turn

**Status: proposal.**

**Today.** Raiker trusts the model's intent until a downstream gate refuses it.
That catches the single dangerous call. It does not catch the ten-step drift where
an injected instruction slowly walks the agent toward changing a setting, each
step individually reasonable.

**Work.** Run a low-latency local guardrail model — a Llama-Guard-class instance —
asynchronously beside the main orchestration loop in `raiker/runtime/`. Its only
job is continuous threat modelling over inputs and outputs: memory poisoning,
feedback-loop attacks, privilege-escalation shapes. When the main agent starts
producing commands that resemble an escalation vector, the critic flags intent
drift and pauses the execution queue **before** the tool is brokered.

**Governed outcome.** A paused turn tells the owner which pattern the critic
matched and over which steps, and the owner can resume it — the critic pauses and
explains, it does not silently veto.

---

## ADD-17 — An internal debate core

**Status: proposal. The most speculative entry here; cost it before building it.**

**Today.** A single reasoning loop. If the model hallucinates or takes an injected
instruction, the whole turn follows it, and the first thing that notices is a
human reading the result.

**Work.** Before a major execution path reaches the owner, generate three bounded,
hidden sub-instances over the same plan — an **Architect** that proposes the
fastest correct solution, a **Skeptic** that attacks it for bugs and
vulnerabilities, and an **Adversary** that looks for hidden instructions and
prompt drift in the input data. Require programmatic consensus before the plan is
surfaced. `raiker/tools/subagent_tools.py` and the FIXED-95 subagent contract are
the mechanism; the debate is a policy on top of them.

**The honest caveat.** This triples token cost and latency on every major path,
and three instances of one model share its blind spots. Gate it to high-risk paths
and measure whether consensus actually catches anything a single pass missed
before widening it.

**Governed outcome.** A surfaced plan shows the objections that were raised and
resolved, so the owner reads a reviewed plan rather than a first draft.

---

## ADD-18 — Relationship-based access control between agents

**Status: proposal. Owner decision — it introduces multiple principals.**

**Today.** FIXED-95 already refuses to let a subagent write, run a command, call a
connector, reach an MCP tool, or nest another spawn: only read-only, local,
non-egress tools are delegable, and every step is re-brokered. That is a strong
default and it is coarse — one rule for all subagents.

**Missing.** No way to express that *this* agent may read what *that* agent
produced. As pipelines grow — an editor agent writing, a tester agent running the
result — the only expressible answers are "read-only" or "as privileged as the
parent".

**Work.** A relationship-based access control engine (OpenFGA-shaped) in the
workspace broker, so inter-agent trust is declared rather than inherited: the
tester may read files the editor generated and may not reach the network; the
editor may not execute. Least privilege between agents, so one compromised
subagent cannot carry the whole workflow with it.

**Governed outcome.** The agent view shows the trust graph for a running pipeline,
and a refused cross-agent read names the missing relationship rather than failing
generically.

---

## ADD-19 — Code provenance watermarking and signed commits

**Status: proposal.**

**Today.** Approved writes are checkpointed and audited, and FIXED-77 records
source coordinates inside a turn. But once the change is on disk and the session
is closed, nothing in the working tree distinguishes a line the agent wrote from a
line the owner wrote.

**Missing.** Weeks later, across hundreds of files, there is no way to answer
"which of this is machine-written?" — which is exactly the condition under which a
backdoor planted in an ignored file survives review.

**Work.** A commit hook and watermarking pass in the file-writing path that signs
agent-generated changes with a dedicated local key held by Raiker's machine
principal (ADD-03), so provenance is verifiable rather than remembered. Prefer
signed commit metadata over invisible in-file syntax traits: a watermark that
survives a reformat is a watermark that survives review, and hiding marks inside
source that a human is expected to read is its own hazard.

**Governed outcome.** An editor extension and the Build diff view can highlight
which regions are machine-written and which are human-verified, from the signature
rather than from a memory of who typed what.

---

## ADD-20 — Continuous chaos injection

**Status: proposal. This is what proves the rest of the list works.**

**Today.** Guardrails are tested when a test exercises them and when a real failure
finds them. The FIXED-97 and FIXED-98 pattern — two lists that must agree, with
nothing holding them together — is the recurring failure mode across this
codebase, and both were found by hand.

**Work.** A background chaos daemon that, while Raiker is idle, injects fake
malicious prompts, simulates privilege-escalation commands, and drops mock
credential files into the workspace, then measures how fast the capability gates,
the policy engine, and the container boundary catch each one. It runs against the
same governed path as real work and asserts on the durable log rather than on
return values — which is precisely what the unit tests missed in FIXED-97.

**Governed outcome.** Diagnostics carries a standing "when did each guardrail last
demonstrate that it works" panel, and a guardrail that stops catching its own
drill raises a finding before an attacker finds it first.

---

## Appendix A — Reference sketch: the zero-trust executor wrapper

The shape ADD-01 describes, as originally sketched. It is a sketch, not the
implementation — the shipped version lives in
`raiker/runtime/executors/containers.py` and differs in the ways ADD-01 records
(no host mount of the repository, an image allowlist, a read-only rootfs).

```python
import docker


def execute_agent_tool_securely(command, workspace_path):
    client = docker.from_env()

    # Enforcing strict container sandboxing rules
    container = client.containers.run(
        image="python:3.11-slim",
        command=command,
        volumes={workspace_path: {"bind": "/workspace", "mode": "rw"}},
        working_dir="/workspace",
        cap_drop=["ALL"],   # Zero elevated privileges
        user="1000:1000",   # Explicitly non-root execution
        mem_limit="512m",   # Guarding against infinite resource drainage
        nano_cpus=1_000_000_000,
        detach=True,
    )

    # Enforce strict hard timeout ceilings
    try:
        container.wait(timeout=60)
        return container.logs()
    except Exception:
        container.kill()
        raise RuntimeError("Zero-Trust Boundary Triggered: Execution Timeout exceeded.")
```

---

## Appendix B — How the posture changes, tier by tier

```
[ Traditional agents ] ──► Perimeter trust
                           (past the prompt, it runs wild)

[ Raiker today ]       ──► Owner-authoritative, monitored, fail-closed
                           (governed execution, human approval, audited)

[ Tier 0–1 complete ]  ──► Distinct agent identity + policy-as-code
                           (autonomy without privilege escalation)

[ Tier 4–6 complete ]  ──► Hardware and continuous behavioural attestation
                           (never assumes trust, always verifies)
```

The request path each tier adds, in the order a turn passes through it:

```
              [ Incoming owner task ]
                        │
                        ▼
   [ ADD-17  Internal debate core ]  ──► Architect vs. Skeptic vs. Adversary
                        │
                        ▼
   [ ADD-16  Safety Critic ]         ──► Continuous intent-drift check
                        │
                        ▼
   [ ADD-07  Policy-as-code gates ]  ──► Declarative guardrail verdict
                        │
                        ▼
   [ ADD-03  Machine identity ]      ──► Agent rights, not owner rights
                        │
                        ▼
   [ ADD-12  Ephemeral micro-VM ]    ──► Isolated-kernel execution
                        │
                        ▼
   [ ADD-19  Signed provenance ]     ──► Provable, auditable output
                        │
                        ▼
   [ ADD-04  Lineage + kill switch ] ──► Traceable to the input that caused it
```

---

## The fundamental realisation

It is possible to build every cage in this document — micro-VMs, microkernels,
policy-as-code, debate engines — and still be exploitable, because none of them
answer the only question that matters at the moment of execution: **who is asking,
and where did the instruction come from?**

Without identity (ADD-03) and lineage (ADD-04), security is an illusion. A sandbox
is only as strong as its ability to verify who is requesting an action. Build
Tier 0 first, or the rest is decoration on an open door.
