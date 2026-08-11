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

# To be fixed

Defects and gaps found while executing
[the live manual test plan](RAIKER_LIVE_MANUAL_TEST_PLAN.md) against a running
`raiker-web` on **2026-07-26**, hosted Anthropic `claude-haiku-4-5-20251001`.

Each entry states what was observed, the reproduction, the root cause in code,
and the proposed fix. Every deferred item found by the FIXED-01 through FIXED-48
audit is an explicit BUG with a required user-interface outcome, so closing
backend work cannot leave an invisible or misleading product surface.

**Closed entries live in [`FIXED_ITEMS.md`](FIXED_ITEMS.md).** They are still
evidence — what was observed, the root cause, and the user-interface outcome that
had to be true before it could be called closed — but they are no longer mixed in
with the open work, so this document answers one question: what is left.

docs/GAP_BUILD_CHAT.md — GAP-BUILD and GAP-CHAT — are not defects. They are the itemised
distance between what Build and Chat ship today and what each is meant to be:
Build as an autonomous coding agent that closes its own loop, Chat as a general
agentic work assistant that acts across the owner's tools and files. They are
written to the same standard as the defects: what exists today with the file
that proves it, what is missing, and the concrete work.

Evidence: [`screenshots/not-working/`](screenshots/not-working) (defects),
[`screenshots/working/`](screenshots/working) (verified behaviour).

| ID | Severity | Area | Status |
|---|---|---|---|
| [OPT-01](#opt-01--adding-one-tool-takes-twelve-edits-across-seven-files) | Medium | Codebase structure | Open |
| MEM-03 … MEM-09 | High → Low | Memory reliability | Open — see [`MEMORY_RELIABILITY_PLAN.md`](MEMORY_RELIABILITY_PLAN.md) |
| GAP-BUILD | — | Build — coding-agent parity | Analysis (B1–B9, B11, B12, B17 complete; 10 items remain) |
| GAP-CHAT | — | Chat — work-assistant parity | Analysis (14 items remain) |

The memory audit of **2026-08-11** has its own document,
[`MEMORY_RELIABILITY_PLAN.md`](MEMORY_RELIABILITY_PLAN.md), written to this
standard. Its MEM-01 and MEM-02 are closed in
[`FIXED_ITEMS.md`](FIXED_ITEMS.md) as FIXED-187 and FIXED-188; MEM-03 through
MEM-09 are open there rather than duplicated here.

---

## OPT-01 — Adding one tool takes twelve edits across seven files

**Severity: Medium. Area: codebase structure. This is the measured
line-reduction opportunity, not a defect.**

**Observed.** Registering `conversation_search` and `code_map_references` this
round required the same tool name to be written into **seven files at twelve
sites**, none of which fails loudly when one is missed:

| File | What it decides | Sites |
|---|---|---|
| `models/tool_call_validation.py` | risk band, required args, list args, arg schemas, optional args, description | 5 |
| `contracts/models.py` | the name is known at all | 1 |
| `runtime/turn_sources.py` | what kind of source a result is | 2 |
| `runtime/authority/router.py` | which capability the tool answers to | 1 |
| `policy/config.py` | whether the proposal is read-shaped | 1 |
| `agents/orchestration.py` | whether a subagent may be delegated it | 1 |
| `tools/broker.py` | the executor | 1 |

Inside `tool_call_validation.py` alone, **43 tools produce 148 key lines across
six parallel dictionaries** keyed by the same string. Every tool appears in more
than one. A tool registered in six of the seven files does not raise an error —
it silently behaves as an unknown tool, or as one with no description, or as one
a subagent may not use.

**Root cause.** Each table was added where it was needed, by a change that was
correct in isolation. Nothing forces a new tool to be complete, because
completeness is not represented anywhere.

**Proposed fix.** One declarative `ToolDefinition` per tool in a single registry
module — name, risk band, approval requirement, arguments (required, list,
optional, schemas), description, capability, source kind, delegable, read-shaped
— and derive the existing tables from it. Every current consumer keeps its
current shape, so the change is additive and reviewable a file at a time; the
tables become one-line comprehensions over the registry. A dataclass with
required fields is what makes a half-registered tool a construction error rather
than a runtime surprise.

**Estimated reduction.** ~105 of the 148 key lines in
`tool_call_validation.py`, and 11 of the 12 edit sites for each future tool. The
descriptions and the explanatory comments are the file's value and are kept
verbatim — the saving is duplication, not prose.

**Applied instance (proof the method works).** The same shape of problem in the
web app was fixed this round as **FIXED-193**: eight views re-declared the same
control styling four different ways, and thirty-seven `<select>` elements had
twenty different appearances. Declaring the control appearance once against the
*element* inside `:where()` — zero specificity, so nothing had to be unpicked —
deleted all eight declarations and, more importantly, removed the drift for every
view written after it. The principle both share: **when correctness depends on
remembering to repeat something, move the requirement into one place that cannot
be forgotten** — a registry that fails construction, or a rule that applies
without being named.

**Required user-interface outcome.** None directly; this is internal. The
outcome that matters is that a tool cannot ship half-registered, which is what
produced the `conversation` source kind and the delegable-set entry being
separate manual steps this round.

**Not done in this session.** The registry touches the validation path every turn
runs through, and this session's remaining budget was committed to verifying the
memory work live. It is written up here rather than half-applied.

---

## Verified working (no action needed)

Recorded so the fixes above are read against the right baseline. Re-verified end
to end on **2026-08-08** against hosted Anthropic (see
[the live manual test plan](RAIKER_LIVE_MANUAL_TEST_PLAN.md) for the full round):

first-run bootstrap and owner sign-in; **all 14 routes and 22 hub tabs with 0
console errors**; connecting a hosted provider from the web app and pinning a
model from the live catalogue; **all ten Anthropic models answering a live turn**;
a real streamed turn with sanitised Markdown (headings, lists, GFM tables,
fenced code); conversation memory within a chat and isolation between chats;
per-chat and provider all-time cost; recent-chat list; chat search over titles
and message text; the four task types (immediate, scheduled, daily routine,
background agent) with parent nesting, priority, counters and stop; the approval
lifecycle end to end — proposal, unified diff, **Approve and execute once**, the
file on disk, and the resumed turn; the file inspector for a generated Markdown
file and for a generated PDF; **Export conversation… in HTML, Markdown and PDF**
plus **Print / Save as PDF**; markdown → PDF through `create_document`; document
and image attachments reaching the model with source citations; MCP server
create / connect / discover / **call from Chat** under the owner's decision mode,
with the result marked untrusted; Build repository connect, code-map build and
`code_map_search`; `update_plan` checklists and `spawn_subagent`; capability
step-up (reason required, Confirm disabled until supplied); the deferred domains
CCTV, finance, medical and home security offering no row at all; Observability's
seven tabs on real data; Settings' six tabs; theme cycling system → light → dark;
the notification centre and Mark all read; the STOP switch; and adaptive
navigation at 375 / 768 / 1024 / 1440 px with no horizontal overflow, correct
`aria-expanded`, and focus returned to the trigger.
