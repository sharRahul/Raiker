# Conversational Chat Design

## Goal

Make Chat feel like a familiar person-to-person conversation while preserving
the runtime's complete technical record in Sessions and Checkpoints.

## Chat experience

- Render each turn as two messages: the user's prompt right-aligned in a
  Raiker teal-blue bubble, and Raiker's response left-aligned in a quiet neutral
  bubble.
- Use iMessage-inspired bubble radii, tails, spacing, and reaction placement
  without reproducing the iMessage interface or branding.
- Size the transcript according to the available screen: balanced readable
  message widths on wider displays, with bubbles expanding naturally on narrow
  screens.
- Replace lifecycle language in Chat with transient conversational status:
  `Raiker is thinking…` before response text arrives, then `Raiker is typing…`
  while text is streaming. Both disappear on completion or error.
- When meaningful streamed reasoning is available, show a collapsed `Raiker is
  thinking…` disclosure below the in-progress reply. Expanding it shows only
  human-readable progress; it never exposes lifecycle phases, governance
  wording, raw events, tool records, model metadata, cache data, or completion
  status.
- Show one automatic, compact reaction below an applicable Raiker reply. The
  supported repertoire includes smileys, hand gestures, hearts, and related
  conversational emoji. Reactions are optional and never shown as a status.

## Information boundaries

Chat must not render governance panels, phase labels, status badges, cache
chips, model labels, event summaries, or the word "completed" as runtime
metadata. Approval requests remain actionable in Chat when needed, but their
technical trace remains in Sessions and Checkpoints, which are the exclusive
views for detailed runtime diagnostics.

## Implementation shape

`ChatView.svelte` remains the single owner of transcript state and streaming.
It derives response text, a conversational streaming label, and a safe
plain-language thinking summary from existing stream events. A small,
deterministic reaction selector derives at most one emoji from the completed
assistant response, avoiding a backend contract change. Existing persisted
session history continues to render as normal message bubbles.

## Error handling and accessibility

Stream failures render as an accessible chat error without leaving a typing
indicator behind. The thinking disclosure uses native `details`/`summary` (or
equivalent semantic controls), starts collapsed, and keeps a clear accessible
label. Reaction emoji have descriptive accessible text.

## Verification

Add focused component tests that prove the transcript has no governance or
completion metadata, shows each streaming label at the correct time, toggles
the thinking disclosure, renders appropriate automatic reactions, and preserves
history and error behaviour. Run the Chat view tests, the web type check, and
the production web build.
