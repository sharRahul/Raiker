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
| BUG-49 | Low | CI / release workflow action pinning | Open (found while building the release workflow) |
| BUG-53 | Low | Chat / multi-call answer text runs together | Open (found while verifying FIXED-99) |
| BUG-54 | Medium | Web e2e / the live stub model is not in the repository | Open (found while writing FIXED-99's live scenario) |
| BUG-55 | Low | Chat / a disabled transcript block reads as live code | Open (found while verifying FIXED-99) |
| GAP-BUILD | — | Build — coding-agent parity | Analysis (B1–B9, B11, B12, B17 complete; 10 items remain) |
| GAP-CHAT | — | Chat — work-assistant parity | Analysis (14 items remain) |

---

## BUG-49 — Two release-workflow actions are pinned by tag, not by digest

**Status: open; found while building `.github/workflows/release.yml`.**

**Observed.** Every other action in this repository is pinned to a commit SHA.
`actions/upload-artifact` and `actions/download-artifact` in
`.github/workflows/release.yml` are pinned to `@v4`, because the commit digests
could not be resolved from the environment the workflow was written in. A tag is
mutable: whoever controls it can change what those steps run, and those steps
handle the release artifacts.

**Required fix.** Resolve both actions' commit digests and pin them, with the
version in a comment beside each, exactly as `actions/checkout`,
`actions/setup-python` and `actions/setup-node` are pinned. Then check no other
workflow has acquired a tag pin.

**UI when closed.** None — this is supply-chain hygiene for the pipeline that
produces what owners install.

---

## BUG-53 — A multi-call turn's answer text runs together in Chat

**Status: open; found while verifying FIXED-99.**

**Observed.** A turn in which the model speaks more than once — every turn that
calls a tool and then answers — renders as one unbroken paragraph with no space
between the two utterances:

> Reading ../escape.md and listing the workspace.I could not read ../escape.md —
> policy refused that one call…

`working/bug-52-chat-refusal-does-not-end-the-turn.png` shows it.

**Root cause.** `collectText` in `apps/web/src/lib/turnPhases.ts` joins every
streamed `text_delta` with `""`, which is right *within* one model response and
wrong *between* two of them: the deltas of the second response begin a new
sentence, and nothing marks the seam.

**Required fix.** Separate the text of successive model responses in a turn —
either by paragraph, matching how the model itself wrote them, or by carrying a
response boundary through the stream so `collectText` can break on it. Do not
insert whitespace blindly between deltas; inside one response that would break
words in the middle.

**UI when closed.** A turn that reads a file and then answers reads as two
statements rather than one run-on sentence, in Chat and in Build.

---

## BUG-54 — The live end-to-end stub model is not in the repository

**Status: open; found while writing FIXED-99's live scenario.**

**Observed.** Two live specs —
[`e2e/add-02-batched-approval-queue-live.spec.ts`](../../apps/web/e2e/add-02-batched-approval-queue-live.spec.ts)
and [`e2e/bug-52-first-pass-denial-live.spec.ts`](../../apps/web/e2e/bug-52-first-pass-denial-live.spec.ts)
— name `python <scratch>/stub_model.py` as a prerequisite. That file exists only
in the scratch directory of the session that wrote each spec, so neither
scenario can be re-run by anyone else, and the exact batch each one asserts on
is recorded nowhere but in prose.

**Why it matters.** These two specs are the evidence behind ADD-02 and FIXED-99.
Evidence that cannot be reproduced is a claim. Every other live spec drives a
real provider the reader can also connect; these two do not, and the thing that
replaces the provider is missing.

**Required fix.** Commit the stub under `apps/web/e2e/` (or `scripts/`) as a
checked-in fixture with its own README line, and point both specs at it by
repository path. It is a local, loopback-only HTTP server with no credential and
no network, so it introduces no new boundary — it is the *input* to the run, and
it belongs beside the specs that depend on it.

**UI when closed.** None — this is reproducibility of the evidence behind two
entries in this document.

---

## BUG-55 — A disabled block in the Chat transcript reads as live code

**Status: open; found while verifying FIXED-99.**

**Observed.** `apps/web/src/lib/views/ChatView.svelte` wraps roughly ninety lines
of the transcript — a phase line, an answer paragraph, an error line, a response
metadata row and a **complete second approval card** — in `{#if false}`. All of
it is dead. The live approval card is a separate, later block, and the two say
different things: the disabled one tells the owner to "Review it in the Approvals
inbox", while the live one carries the batch position, the cross-tab resume state
and the **Continue now** control.

**Why it matters.** Someone changing the approval copy will reasonably edit the
first card they find and see no change in the product; a reviewer auditing what
Chat tells an owner about a governed action will read the wrong text. It is the
same failure mode as BUG-51 — configuration that looks load-bearing and is not.

**Required fix.** Delete the disabled block, or, where a fragment is genuinely
being kept for a planned redesign, move it out of the component and say so.
Nothing that renders governance copy should exist twice with two different
wordings.

**UI when closed.** No user-visible change; this is a maintainability and
auditability defect.

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
