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

Meaning-based recall works for approved memories and managed files when the
owner has selected and built a provider or local embedding space. Query
embedding uses the same governed consent and falls back to lexical search when
the owner denies it or the backend is unavailable.

One limit remains, and it is a deliberate one: an install with no provider key
and no local embedding model has only the lexical fallback—nothing is bundled,
by design. Lexical recall matches words, not meaning, and requires every word
that carries meaning to appear in the stored text; the words a question is built
from (*where*, *what*, *the*, *about*) are dropped before the match, so an
ordinary question reaches the memory that answers it, but a question phrased in
words the memory does not use will not. That is what the meaning-based index is
for.

Vector recall no longer scans linearly: small spaces are ranked exactly and
larger ones use a bounded approximate lookup with exact score re-ranking.

Conversation context is also bounded by the selected model. Raiker compacts
older exchanges near a known context limit while preserving the visible
transcript. When a provider does not publish or expose a trustworthy limit,
Raiker reports that capacity is unknown instead of inventing one.

## Checkpoints and undo

File pre-images are capped at 8 MiB. A larger file can still be changed, but the
approval warns that this particular change cannot be rewound. Git commits and
pushes are not undone by file checkpoints; use Git and the remote repository.

Checkpoint restore itself is governed. It requires the checkpoint-restore and
approval-relay capabilities and is re-checked when it runs. **Rewind to before
this** on your own message and *Preview rewind* on Observability → Checkpoints
open the same preflight; neither restores anything, and both raise an approval a
human resolves.

## Recall and citations

A recalled past conversation appears under **Sources** as *Past conversations*,
and opening it shows each exchange with its conversation title and date. Those
exchanges are text, not links: to open one, search its title in **Search Chat**
and use *Open the match*. A chat-search hit, a checkpoint's **Turn** field, and a
turn opened from Observability → Sessions all open the exchange directly.

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

- Hooks cover 20 of the 31 lifecycle events in the reference format. The 11
  that remain are refused, not applicable to a single-owner product, or
  blocked behind a mid-turn question surface Raiker does not have.
- Hook execution supports `command` plus Raiker's `builtin` handler; other
  reference handler types (`http`, `mcp_tool`, `agent`) are not implemented;
  bounded tool-free `prompt` handlers are implemented.
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
