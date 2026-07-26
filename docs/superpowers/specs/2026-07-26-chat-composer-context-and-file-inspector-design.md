# Chat composer context controls and file inspector

> Implementation note (2026-07-26): configured-model selection, a labelled
> transcript estimate, and the existing global permission modes are delivered.
> Trusted provider usage/cost/quota data, 90% automatic compaction, and the
> view-only file inspector remain specified work.

## Purpose

Extend the conversational Chat view with truthful, model-aware context and
spend visibility, a compact global permission control, automatic context
compaction, and a view-only document inspector. The normal chat transcript
must remain free of governance cards and technical traces. Sessions and
Checkpoints remain the place for evidence and detailed diagnostics.

## Composer experience

The composer shows three compact controls: the active model, context, and
permissions.

### Configured model selector

The model selector lists only Raiker model profiles that are configured and
usable for the current user. Its label is the configured provider and model.
It does not fetch a provider catalogue, offer an unconfigured model, or expose
a free-text model id field. Changing it selects that profile for the turn.

Each profile exposes its configured `context_window_tokens` through the models
read contract. A profile without a known capacity remains selectable, but its
context control says that the provider has not reported a context window.

### Context popover

Selecting the context control only opens or closes a popover. It never compacts
the conversation.

When data is available, the popover displays:

- a `used / total (percent)` context label and proportional bar;
- an `estimated` qualifier whenever Raiker cannot obtain model-native prompt
  token usage;
- the current chat's API cost when actual token usage and configured pricing
  exist;
- a weekly-usage row and reset time only when an applicable weekly budget or
  quota is available.

The percentage is bounded to 0–100 and the meter has warning styling near the
automatic compaction threshold. Missing model usage, price, quota, or reset
facts are omitted or described as unavailable; the UI must not fabricate them.

Cost is calculated from profile pricing and recorded token usage. It is
formatted with the account's configured locale and display currency. A currency
conversion is displayed only when Raiker has an explicit configured exchange
rate; otherwise the verified source currency is shown. Browser locale is a
fallback for number formatting only, not a basis for an invented exchange rate.

### Global permissions control

The permissions control is an entry point to Raiker's existing, audited
global capability decision modes. It offers:

- **Ask every time** — request approval before governed actions;
- **Approve safe actions** — use Raiker's existing policy to approve only
  actions it classifies as safe;
- **Custom** — open the existing Permissions view for per-capability policies.

It does not offer unrestricted access. The control updates the global policy
through the existing authorization checks and records the standard decision-mode
audit event. A user who lacks authority sees the current state and a disabled
control with an explanation.

## Context accounting and automatic compaction

Raiker maintains per-session context usage for the selected model profile. It
prefers provider-reported prompt usage. If that is unavailable, it uses a
conservative local estimate and labels the result accordingly. The accounting
record is tied to the session, selected profile, model context capacity, source
of the count, and the most recent turn.

At 90% of a known context window, before starting a turn that would otherwise
exceed the safe headroom, Raiker automatically compacts the earlier transcript.
It produces a bounded internal summary, retains the most recent conversation
needed for continuity, and updates the context record before continuing.

The chat transcript shows only a quiet, non-technical “Context compacted”
notice. The compaction decision, summary provenance, exact usage facts, and
checkpoint references are recorded under Sessions and Checkpoints. If
compaction cannot complete safely, the turn fails closed with a concise chat
message and retains the original transcript.

## View-only file inspector

Selecting a file already attached to the current chat or created by Raiker
opens a document inspector.

- On wide screens it is a right-side pane, leaving the chat visible.
- On smaller screens it opens as a dismissible overlay.
- The inspector is view-only and accepts no upload, edit, or execution action.
- It supports PDF, Markdown, XLSX, and DOCX with format-specific, safe
  rendering. It shows the filename, file type, and a close button.
- A new selected file replaces the current preview. Unsupported, unavailable,
  or malformed files report an honest preview-unavailable state.

The backend authorizes every preview against the current session and artifact
ownership. Preview renderers never execute embedded code or macros. Markdown is
sanitized before rendering; office and PDF previews use parsed document content,
not active embedded content. No diagnostics or governance payload is exposed in
the pane.

## Architecture

1. Extend the models read DTO and web `ModelProfile` type with context capacity,
   configuration/availability facts, and optional configured pricing metadata.
   Keep provider catalogue discovery out of the Chat selector.
2. Add a session-scoped context/usage read model containing the active profile,
   context window, exact-or-estimated token count, cost, and applicable weekly
   quota. Reuse existing persisted budget facts where they apply.
3. Add an account preference for locale/display currency and a bounded,
   owner-configured exchange-rate source. Do not make the browser location a
   billing or exchange-rate authority.
4. Add a compaction service that creates a bounded summary and checkpoint before
   the next turn crosses 90% of a known capacity. It has no UI-triggered
   compaction route.
5. Compose the Chat controls from focused Svelte components: model selector,
   `ContextMeterPopover`, and `PermissionModeControl`. The Chat view owns only
   message/session orchestration.
6. Add an artifact-preview read route and focused renderer components behind a
   responsive `FileInspector` shell.

## Error handling and privacy

- Unknown capacity, unavailable token usage, unknown pricing, or missing quota
  never produce guessed figures.
- API credentials, pricing secrets, raw prompts, model reasoning, and internal
  compaction content never enter the normal chat UI.
- Permission changes remain authorized, auditable, and fail closed.
- A failed preview cannot disclose a file outside the active session.
- A compaction failure leaves the original transcript intact and does not start
  the model turn with incomplete context.

## Verification

- Backend tests cover configured-profile filtering, context/usage DTOs, source
  labeling, pricing/currency fallback, weekly quota omission, 90% compaction,
  checkpoint evidence, and session-scoped preview authorization.
- Web tests cover selector filtering, the non-mutating context popover, meter
  labels and bars, unavailable states, locale formatting, global permission
  control authority states, quiet compaction notice, and responsive file-pane
  behavior.
- Renderer tests cover sanitized Markdown plus safe failure states for PDF,
  XLSX, and DOCX.
- Full type checking, web tests, backend tests, and production build run before
  handoff.

## Non-goals

- No arbitrary provider model catalogue in Chat.
- No free-text model entry in Chat.
- No context compaction on clicking the context control.
- No unrestricted permission mode.
- No uploads or file editing in the first file-inspector version.
- No unverified live exchange-rate conversion.
