# ADR-0005: `@` personas narrow a turn and never widen it

## Status

Accepted as a design on 2026-11-16. Not built. Answers the five questions
[TO_BE_FIXED § Composer agent personas for `@`](../plans/TO_BE_FIXED.md#composer-agent-personas-for-)
said a design must settle before any code; the build slices at the end are the
order it will be built in.

## Date

2026-11-16

## Context

On 2026-11-07 the owner decided that `@` in the composer routes a prompt to a
named specialist (`@DataAnalyst`, `@Copywriter`) as part of the composer control
deck ([03](../plans/quiet-ui/03_WELCOME_HOME_AND_CHAT.md#2026-11-07--composer-control-deck)).
Raiker has no persona today, and `@` already mentions a file from the code map.

The reference products were read for the shape, not copied:

- **Claude Code subagents** are Markdown files with front matter (`name`,
  `description`, `tools`, `model`) whose body is the system prompt. A subagent
  gets only the tools it lists, and a missing list inherits the parent's. The
  strength is that the definition is a reviewable file; the weakness for
  Raiker is the inheriting default.
- **Cursor custom modes** bind instructions to a tool set and a model, chosen
  from the composer. A mode is a selection, not an @-mention, and is not
  recorded per message.
- **ChatGPT GPTs** carry instructions, knowledge files and actions, and can be
  @-mentioned into a conversation; the answer is labelled with the GPT's name.
  Actions widen what a conversation can reach, which Raiker must not allow.
- **Hermes Agent** personalities are prompt presets switched by command; they
  change voice, not authority.
- **Meta's assistant** personas are character voices; they change nothing a
  turn may do.

What every one of them shares is *instructions plus a default model*. What
Raiker adds is that authority is the runtime's, never the prompt's
([ADR-0001](ADR-0001-personal-autonomous-agent.md)); a persona that could
widen a turn would be a second permission system written in prose.

## Decision

### 1. What a persona is

A persona is an owner-authored record with: a **name** (letters and digits,
unique per account, the text after `@`), a one-line **description**, **standing
instructions** (at most 4,000 characters), an optional **default model**
(profile and model), and an optional **tool ceiling**: a subset of the tool
families the turn would otherwise have (files, web, messages, memory, Git,
commands). It has no knowledge files of its own in the first slice; files are
attached to the turn as today.

### 2. How it maps onto profiles and Permissions — it can only narrow

A persona is applied as one more **narrowing override**, the same mechanism
the conversation's Careful profile uses (QUI-P02): the turn's authority is the
intersection of Permissions, the active execution profile, the conversation's
profile and the persona's tool ceiling. A persona with no ceiling inherits the
turn's tools — unlike a Claude Code subagent it never inherits *more* than the
turn, because there is nothing above the turn to inherit. Its default model is
held to the execution profile exactly like a model chosen in the composer: a
profile that refuses the provider refuses the turn as *Not sent* (FIXED-1475),
and the persona never selects a fallback the owner has not configured. Its
instructions are sent as a system message marked as owner-authored
configuration, beneath Raiker's own standing instructions, so they cannot
restate or relax a rule those set.

### 3. Where personas are created and listed

**Settings › Personalisation › Personas**: a list with **Add persona**, each row
opening a form dialog (QUI-L03). A persona can also be saved from a turn's
**⋯ › Save as persona** with the turn's instructions prefilled. They are owner
data under the account, exported with Settings and never synced to a provider.

### 4. How `@` keeps file mentions reachable

The `@` menu lists **Personas** first, then **Files** (the code map, as now),
in two labelled groups; typing narrows both. A persona is chosen once per turn
and shows as a chip in the composer's input row (*@DataAnalyst ×*), not as
text in the prompt, so a file named `DataAnalyst.md` stays mentionable and a
prompt that merely contains an `@` word is never reinterpreted. One persona per
turn.

### 5. What the transcript records

The turn stores the persona's id, name and a SHA-256 of the instructions it
ran with; the answer's header reads *Raiker as @DataAnalyst*; the context
inspector names the persona, its ceiling and its model. Editing a persona
later does not rewrite history: an older turn shows *ran with an earlier
version*. Memory proposals from a persona turn are reviewed like any other.

## Consequences

- No new authority path: the governance entry paths are unchanged and the
  authority router needs no persona case, because a persona arrives as an
  override it already intersects.
- The `@` menu gains a group; the file mention keeps its behaviour.
- Build and Design can adopt the same composer chip later; the first slice is
  Chat only.

## Build slices

1. Storage and API: the record, owner-scoped CRUD, validation of the ceiling
   against known families; tests that a ceiling never adds a family.
2. The turn: persona id on the prompt envelope, the narrowing override, the
   system message, transcript fields; refusal tests for a model the profile
   refuses.
3. The UI: Settings list and dialog, the `@` group and chip, the answer header
   and inspector fact; a live round with a real provider.
