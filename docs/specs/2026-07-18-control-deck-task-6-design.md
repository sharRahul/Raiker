# Control Deck Task 6: Shared Web Primitives

## Scope

Task 6 supplies the shared primitives and Control Deck shell required by the
later route work. It rewrites the shared application shell to consume the
responsive page primitive, but does not rebuild individual route bodies or
change backend authority.

## Reuse first

`Sidebar.svelte` and `NotificationCenter.svelte` already exist and are used by
the current shell/MCP monitor. Task 6 keeps them, makes notification copy
source-neutral, and applies the approved Control Deck wordmark treatment to the
existing sidebar. It does not create duplicate replacements.

## Components

- `PageState` renders a compact loading, error, or empty state from server truth.
- `ResponsivePage` provides a title/lead wrapper and an optional action slot for
  route migrations.
- `SessionMenu` renders the six specified session actions. Share only copies the
  current loopback hash URL; rename, project move, pin, archive, and delete are
  exposed as callbacks so the parent route remains the authenticated API owner.
- `ToolControlBoard` renders only executable, server-changeable capability rows;
  decision controls call the supplied callback and are absent for deferred or
  non-executable rows.

## Shell migration

`App.svelte` adopts `ResponsivePage` around the active route and keeps the
existing authenticated bootstrap, sidebar, topbar, hash routing, project
selection, skip link, and main landmark. The responsive shell owns mobile-safe
content padding and width; individual routes keep their current markup until
Tasks 7-9 migrate them. This prevents the shared layout from being missed while
avoiding a duplicate rewrite of every view in Task 6.

## Constraints

No new dependencies, client-side authorization, fabricated state, generic
settings framework, or individual route-body migration. Each new component gets
a focused Vitest check; the existing typed API/client contracts are extended
only when a new primitive needs an existing endpoint not already represented.

## Verification

Component tests cover all six menu actions, loopback-only share, notification
read filtering, and omitted controls. The web check/lint/test/build gates, an
authenticated browser drive, full Python gate, repository validators, and CI
remain required before release.

## Implementation record — 2026-07-18

The shared shell migration is complete: `App.svelte` uses `ResponsivePage`
without changing individual route bodies. At the verified 390px viewport the
sidebar becomes an accessible icon rail; the original full-width mobile sidebar
was found in the browser drive and repaired before release. `SessionMenu` stays
an authority-neutral primitive until Task 8 integrates it into Sessions; its
callbacks, loopback-only sharing predicate, and unavailable-control omission
are verified in component tests rather than represented by a temporary route.
