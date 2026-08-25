# Known limits

This page summarizes the limits a user should understand before relying on the
current build. The exhaustive, implementation-level ledger is
[Architecture: Known limits](../architecture/KNOWN_LIMITS.md); where details
differ, that ledger is canonical.

## Availability

- Raiker currently supports a local, single-owner dashboard and terminal
  client from a source checkout.
- No signed desktop artifact has been published.
- Hosted multi-user, IDE, and dedicated mobile clients are deferred. The web
  dashboard is responsive and can be opened from another device only through a
  deliberately secured non-loopback deployment.
- The product does not implement governed finance, medical, CCTV,
  home-security, pregnancy/baby, or hardware executors.

## Memory and recall

**Recall matches words, not meaning.** The default “vector” representation is
feature hashing over tokens, so both retrieval paths are lexical in practice and
a paraphrase with few shared words may not recall the relevant record.

**Memory → Recall backend** always says which of three states you are in, and
offers **Build a meaning-based index** where an embedding model is available: one
governed run over your approved memories, with the model named and the count
stated before anything leaves the machine. That builds the space and stores your
memories as learned embeddings.

**It does not yet make a paraphrase work.** Comparing a *question* against that
space means embedding the question too — a provider call on every search — and
that path needs its own permission rather than a shortcut, so it is not
connected. The card says so rather than implying otherwise. Tracked as BUG-240.

Two further limits. An install with no provider key and no local embedding model
has only the lexical fallback — nothing is bundled, by design. And recall over
the chosen space is a linear scan, so its cost grows with the number of memories.

Conversation context is also bounded by the selected model. Raiker compacts
older exchanges near a known context limit while preserving the visible
transcript. When a provider does not publish or expose a trustworthy limit,
Raiker reports that capacity is unknown instead of inventing one.

## Checkpoints and undo

File pre-images are capped at 8 MiB. A larger file can still be changed, but the
approval warns that this particular change cannot be rewound. Git commits and
pushes are not undone by file checkpoints; use Git and the remote repository.

Checkpoint restore itself is governed. It requires the checkpoint-restore and
approval-relay capabilities and is re-checked when it runs.

## Approvals and execution

Not every approval executes an action. The approval detail says whether it will
execute once or only record the decision. A target capability and the governed
approval relay must both remain enabled at execution time. Network and process
approvals without a supported executor are record-only.

Build's Plan/Edit/Auto posture and the composer approval policy are additional
turn controls, not replacements for capability gates or runtime policy. “Skip
all approvals” skips an ordinary UI prompt; it does not bypass policy,
confinement, sandboxing, or critical holds.

## Hooks, plugins, and MCP

- Hooks cover 16 of the 31 lifecycle events in the reference format.
- Hook execution supports `command` plus Raiker's `builtin` handler; other
  reference handler types are not implemented.
- A plugin runs no code merely because it is installed. It contributes governed
  hook rules, disabled-by-default skills, and offered—not automatically
  connected—MCP servers.
- Raiker negotiates MCP revision `2026-07-28` and accepts three older revisions,
  but implements a bounded subset. Streamable-HTTP behavior, remote OAuth,
  `server/discover`, and MCP Apps are not available.

## Voice and interaction

Voice is turn-based dictation and manual playback. Continuous listening,
hands-free control, and full-duplex conversation are not available. Dictated
text remains editable, and only pressing **Send** creates a turn.

The agent cannot ask a structured clarification question in the middle of a
tool-running turn. If an instruction is ambiguous, clarify it before starting
high-impact work.

## Execution environments

The native sandbox supports foreground commands only. It has no PTY,
background execution, network grant, or persisted environment between runs.
Container, SSH, and cloud paths have separate setup, credential, capability,
and approval requirements and are not escape hatches around local policy.

## Web and external services

Web access is a sanitized text fetcher, not a general interactive browser. It
enforces HTTPS, safe public addresses, and redirect re-checks. Hosted-model and
connector availability remains subject to the external provider's network,
quota, model catalogue, and account terms.

## Evidence and open defects

The documentation does not treat a plan as an implementation. Current behavior
is recorded in [Implementation status](../architecture/IMPLEMENTATION_STATUS.md),
open reproducible defects in [To be fixed](../plans/TO_BE_FIXED.md), and tested
browser behavior in the
[live manual test plan](../plans/RAIKER_LIVE_MANUAL_TEST_PLAN.md). Screenshots
are supporting evidence for a dated run, not proof that later builds remain
unchanged.
