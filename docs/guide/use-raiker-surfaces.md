# Surfaces

> Use Raiker › Surfaces. Back to [Use Raiker](use-raiker.md).

Two surfaces are launchable today; both route through the same governed backend
and add no authority of their own:

- **Terminal client** — `raiker --prompt "..."`, interactive stdin, or
  `RAIKER_TUI=plain`. The primary way to run governed turns.
- **Local web dashboard** — the `apps/web` Svelte SPA over the `raiker-web`
  loopback API (single-user, `127.0.0.1` only): read-only governed views plus the
  same governed prompt / turn / approval / runtime-mutation flows, with a
  step-up-gated Security Settings panel.

Desktop, mobile, IDE, voice, and browser-extension clients are specified but
deferred.
