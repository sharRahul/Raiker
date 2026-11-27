# RU-11 — Memory as a summary

**Status:** proposed design, 2026-11-27; implementation and live acceptance pending.
**Parent:** [Ready to use](READY_TO_USE_PLAN.md#d-memory-ahead-on-control-behind-on-ease).
**Validation:** [Testing](TESTING.md#regular-use-journeys),
[live evidence](../architecture/WEB_APP_LIVE_TEST.md).

## Selection

RU-11 is P1 with medium estimated effort. It improves an everyday interaction
and builds on existing memory editing, forgetting, recall modes and indexing.
RU-12 and RU-15 are P2; RU-13 and RU-14 require larger runtime and platform
changes. RU-17 needs a separate portability and secret-handling review.
The clean-machine timing gate for RU-09 cannot be established by this checkout.

The current plan already records the Windows MXC measurement on 2026-11-26
and WSL2 Build preparation on 2026-11-27. Those measurements do not close the
native-account qualification or the complete Apply/push journey.

## Current behavior

- `MemoryView.svelte` opens on Overview: counts, a pipeline, retention and
  suggestions. The approved memory text is on the Memories tab.
- Editing and forgetting already use governed API operations, with reloads
  after mutations and confirmation for forgetting.
- Memory Controls holds recall modes and global Incognito. The backend and
  index-building UI lives in Settings → Memory engine.
- `recall_mode=off` disables ambient recall but explicitly allows a requested
  lookup. It is insufficient as the implementation of a switch promising that
  memory is not used at all.
- Global Incognito overrides recall modes. Conversation memory use is a
  separate runtime concern and must remain distinct in labels and behavior.

## Approaches

| Approach | Benefit | Cost or limitation |
|---|---|---|
| Make the existing Overview a readable summary; reuse governed operations | Smallest change that meets the landing-page requirement; preserves deep links | Requires a careful integration of the global switch and local indexing |
| Replace Memory with one long page | Fewer tabs | Reintroduces the density the Quiet UI split removed |
| Generate a prose summary with a model | Fluent narrative | Adds inference cost, stale summaries and another editable representation |

Use the first approach. Render stored, approved text directly. A generated
summary must not become an independent source of memory truth.

## Proposed behavior

Memory opens on **What Raiker knows about you**. Show active approved records
grouped by their existing memory type, with human-readable topic labels and a
fallback label for unknown types. Keep project scope visible so a project fact
does not read as an account-wide preference. Archived, forgotten, expired and
unapproved records do not enter the summary.

Each row offers Edit and Forget in place. Reuse the existing edit/forget
operations, confirmation and error handling. Saving reloads the canonical
records; a failed save preserves the draft. Forgetting removes the record from
the summary only after the server confirms it. The Suggestions link carries
the count of pending memory and relationship decisions.

Put one **Use memory** switch above the summary. Its off state must withhold
memory from both automatic recall and requested memory searches; implement it
through the existing account-level Incognito boundary only after verifying
that boundary across both paths. Turning it on must preserve the owner's
chosen recall mode. An existing Off recall mode must remain visibly explained
in Controls rather than being silently changed by the switch. Keep the
conversation-level opt-out separate and verify its effect on a new turn.

Move recall configuration into Memory → Controls, reusing the existing engine
component where practical. Existing Settings links should open the new
destination. Offer **Find by meaning (stays on this computer)** only for a
verified local embedding profile. The server must enforce the loopback profile
restriction, rather than relying on UI filtering or model names. Continue to
show word-only recall until query embeddings and a usable index are confirmed.
Index building retains provider authorization, approvals and audit records.
If no local embedding model is available, explain how to add one without
claiming that meaning-based recall is enabled.

Keep lifecycle, retention and indexing mechanics under Controls or a disclosure;
retain the existing Memories tab for filtering and detailed administration.
Keep old tab/deep-link compatibility during the move.

## Quiet UI

Use the existing spacing, typography, surface, focus and color tokens. A topic
heading and a list of memory sentences carry the hierarchy; avoid another grid
of counters or a card around every sentence. Actions wrap at narrow widths.
Use labeled controls, visible keyboard focus, polite save feedback, and an
inline error that preserves the owner's draft. Check light and dark appearance
at 1440 and 390 px, keyboard use and enlarged text.

Apply the requested [Apple design skill](https://github.com/dickwu/apple-design-skill)
and [Impeccable](https://github.com/pbakaus/impeccable) during implementation and
visual review. Treat Apple guidance as cross-platform design principles for
the Svelte UI; preserve Raiker's existing visual system.

## Acceptance and evidence

1. Component tests cover grouping, scope labels, unknown types, exclusion of
   inactive records, suggestion counts, editing failures and successful forget.
2. Backend tests prove owner isolation, the global opt-out across ambient and
   explicit retrieval, conversation opt-out and rejection of nonlocal profiles
   by the local meaning-search operation.
3. A live Playwright journey imports reviewed facts in an isolated workspace,
   edits and forgets from the landing page, toggles memory off and on, and
   verifies recall in subsequent conversations. It visits neither Permissions
   nor Settings to complete the Memory journey.
4. A live local embedding journey verifies indexing and meaning-based recall,
   including the unavailable-model and refused-authorization states. A fake
   model or mocked API cannot qualify this part.
5. Capture and inspect desktop/mobile screenshots in both appearances. Add the
   cases and actual results to the live test document; distinguish passes from
   unavailable host or model prerequisites.
6. Update the guide, parent plan and FIXED_ITEMS only for behavior actually
   implemented and verified. Record unresolved defects in TO_BE_FIXED.
7. Run the relevant unit/API tests, web lint, Svelte checks and build; commit
   and push the implementation, then monitor all triggered GitHub workflows
   through their terminal results and repair failures.

## Repository housekeeping review

The GitHub inventory on 2026-11-27 has six active workflows, matching the six
files in `.github/workflows`: CI, Data safety drills, Desktop package,
llama.cpp engine, Personal Windows voice and Release. Two historical workflows
are already disabled: Apply general assistant identity and Model provider
diagnostics. No additional active stale workflow was found in that inventory.
The ready-to-use plan retains open items and must remain. No plan deletion is
justified by the RU-11 review alone.

## Review boundary

This document is a proposed design, not implementation or test evidence.
RU-11 remains open until the acceptance checks above pass.
