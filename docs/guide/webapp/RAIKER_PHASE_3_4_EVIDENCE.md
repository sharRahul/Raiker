# Raiker-informed web experience - Phase 3 and Phase 4 evidence

> **Verification date:** 2026-07-26
> **Decision:** Phase 3 (context and governed control) and Phase 4
> (observability, recovery, and quality bar) are complete.
> No capability was promoted. Every new endpoint is read-only, and every
> mutation still travels its existing gate, approval, vault, and audit path.

## What Phase 3 and Phase 4 were still missing

The 2026-07-23 audit recorded both phases as *partial*:

| Phase | Outstanding at audit | Status now |
|---|---|---|
| 3 | project context home / file inspect pane | delivered |
| 3 | preflighted checkpoint restore funnel | delivered |
| 3 | one tabbed Extensions hub | delivered |
| 4 | consolidated observability hub | delivered |
| 4 | redacted diagnostic export contract | delivered |
| 4 | offline / reconnect / denial / session-restoration browser evidence | delivered |

An audit of the Phase 0-2 boxes was run first. The shell, grouped navigation,
persistent chat host, session rail and its five cross-links, task cadence
choices, and the server-enforced critical step-up were all confirmed present and
covered by tests. One real gap was found and closed here: the Workbench shipped
two navigation buttons where the plan specifies a natural-language composer.

## New backend read models

`raiker/control/web_read_models.py` adds four read-only aggregates. None of them
mutate the runtime, reach the network, read a credential value, or return
workspace file content.

| Endpoint | What it answers | Safety notes |
|---|---|---|
| `GET /api/extensions` | installed / connected / enabled / usable as four independent facts, plus the first unmet condition | Credential *presence* only. Deferred plugin and channel surfaces are listed as `not_available` rather than hidden. |
| `GET /api/checkpoints/{id}/restore-plan` | which files a restore would rewrite, delete, or skip, and whether any were last changed by another principal | Metadata-only, computed from stored capture entries. Reading a plan performs no restore. Owner-scoped; unknown or foreign checkpoints 404. |
| `GET /api/projects/{id}/files` | a project's files as metadata, plus the governed writes recorded against each path | No file content. Path resolution fails closed outside the workspace, skips symlinks and runtime directories, and caps depth and count. |
| `GET /api/diagnostics/export` | a copyable support bundle of readiness and gate state | Assembled server-side and passed through the same redactor every API response uses. |

`tests/test_api_web_read_models.py` (14 tests) holds them to those promises,
including that `usable` is never true while an earlier condition is unmet, that a
preflight leaves the file on disk untouched, that a path escaping the workspace
is refused, and that no response carries a secret-shaped value.

## Delivered interface

### Phase 3

- **Project context home.** Opening a project shows its instructions and memory
  setting, its sessions, the tasks scoped to it, its files, and its checkpoint
  timeline in one place. Selecting a file opens the shared inspector with size,
  modification time, and provenance: which capability wrote it, whether it was
  created or overwritten, and links back to the session and the turn in the
  audit log. The panel states that Raiker shows what changed and who changed it,
  never the file's contents.
- **Checkpoint restore funnel.** Each checkpoint offers "Preview restore
  impact", which reads the server's plan and shows counts, per-file operations,
  and any cross-principal escalation as a distinct alert. Undo facts and an
  audit-log link precede an explicit acknowledgement; only then does the panel
  explain how to request the restore. The panel says plainly that it cannot
  start one.
- **Extensions hub.** Connectors, MCP servers, plugins, and channels are one
  destination with four tabs. The Connectors tab opens on a readiness overview
  where every row shows the four facts side by side and the inspector names the
  blocking condition in plain language. The plugin and channel tabs say they are
  not available yet and why.

### Phase 4

- **Observability hub.** Overview, audit log, diagnostics, work in action, and
  notification history are one destination with five tabs. The overview is
  organised around four questions — is Raiker ready, is anything waiting for me,
  what changed, can I safely share this — and every card links to the record it
  is derived from rather than showing a colour on its own.
- **Support bundle.** Built by the server on request, rendered verbatim, and
  copyable. A failed build reports the failure instead of showing a partial one.
- **Honest offline behaviour.** A failed read says the runtime is not reachable
  and that nothing was started or changed. It never renders stale readiness as
  current.

### Navigation

The Control and Observe groups collapse from seven entries to five. Pre-hub deep
links (`#/activity`, `#/diagnostics`, `#/work`, `#/mcp`, `#/connections`) resolve
to their hub and open the matching tab, so every link already emitted by session
detail, notifications, and the guides keeps working. Tab selection lives in the
hash, so a panel is a shareable location rather than hidden client state.

## Design-system work

Shared primitives replace per-view one-offs: an inspector `SidePanel`, a
`TabStrip` implementing the full ARIA tabs pattern, `StatTile` for a fact plus
its evidence link, and `LifecycleTrack` for the four extension facts. `app.css`
gains `.card-interactive`, `.card-grid`, `.chip` / `.chip-row`,
`.property-list`, and `.sticky-heading`; the Extensions, Projects, Tasks, and
Connections views now use them instead of their own pills and property lists.
`appCss.test.ts` guards that the primitives are token-only — a hex literal or an
`rgb()` call inside them fails the suite — and that the interactive card lift is
dropped under reduced motion.

The connector category strip was converted from `role="tablist"` to pressable
filter chips. It filters a list rather than switching panels, so tabs were the
wrong semantics and produced two competing tablists on the Extensions page.

## Automated evidence

- Web suite: **276 passed, 1 skipped** (was 219 before this change). Lint,
  `svelte-check`, and the production build all pass with zero errors and zero
  warnings.
- New web tests: `ExtensionsView.test.ts`, `ObserveView.test.ts`,
  `WorkbenchView.test.ts`, `TabStrip.test.ts`, `SidePanel.test.ts`, plus new
  cases in `CheckpointsView.test.ts`, `ProjectsView.test.ts`, `nav.test.ts`,
  `format.test.ts`, and `appCss.test.ts`.
- Backend: `tests/test_api_web_read_models.py` (14 tests). Ruff and mypy clean.

## Local browser evidence

A real Chromium session drove a production build served by `raiker-web` against
a disposable loopback workspace. Twenty-one checks passed:

- The owner account was registered and the workspace shell mounted.
- All 15 primary routes rendered with the expected context-bar title.
- Every pre-hub deep link resolved to its hub and opened the right tab.
- The Workbench composer handed its prompt to Chat and the governed turn ran
  there; a prompt typed directly into Chat produced a server-backed state.
- Task cadence chips, both dropdowns, and task creation worked against the API.
- The project context home showed context, scoped work, files, and checkpoints
  together.
- The checkpoint restore preflight behaved as a read-only funnel gated on
  acknowledgement.
- The extension inspector showed the four lifecycle facts and named the blocking
  condition; the filter chips responded; the deferred tabs said so plainly.
- The support bundle was built from the server and contained no
  credential-shaped field.
- All five Observability tabs rendered, and the Home key moved tab selection per
  the ARIA tabs contract.
- Models, Capabilities with its detail expanded, and Settings rendered.
- The notification panel opened from the context bar and closed on Escape,
  restoring focus; the active-project switcher changed scope.
- With the API blocked, the overview failed closed with an honest message and
  recovered on reconnect.
- At 375px every checked route rendered with no horizontal overflow, and the
  bottom navigation, persistent stop control, and More drawer all worked.

The server recorded 164 API calls and **no 4xx or 5xx response**. The browser
console carried six errors, all of them the requests the offline test
deliberately aborted; there were no warnings and no page errors.

Screenshots at 1280x800 and 375x812 were captured for review under an ignored
scratch path and removed before commit. They are verification artifacts, not
release content.

## Known limitation recorded rather than hidden

The API redactor replaces any secret-shaped value, and a randomly generated
session id sometimes matches that rule — the id comes back as
`[REDACTED_SECRET]`. A redacted id addresses nothing, so a link built from it
would be dead. The new surfaces detect this (`isRedacted` in `lib/format.ts`) and
render "session withheld" instead of a link that goes nowhere.

This is a pre-existing runtime behaviour, not something introduced here, and it
still affects other views that link by session id. Loosening the redactor is a
security-sensitive change and is deliberately **not** made as part of a UX
phase; it needs its own contract and threat-model review. Recording it here
keeps the documentation ahead of the implementation claim rather than behind it.
