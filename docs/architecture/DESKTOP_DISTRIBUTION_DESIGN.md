# Desktop Distribution Design

## Status

**Implemented, pending signed publication.** Raiker runs as a self-contained
desktop application: a local host, and since 2026-10-17 its own desktop window
(an Electron shell in `desktop/`) as the default way to open it. This document
records the product shape used to distribute it for Windows, macOS, and Linux.

**Since 2026-10-17 the release product is the desktop package** — the window
with the host frozen inside it, so an owner's machine needs no Python — built,
installed, smoke-tested, onboarded and uninstalled on each platform's own
runner. The decisions are in
[ADR-0003](../adr/ADR-0003-desktop-distribution.md) (DIST-01 – DIST-12),
the process in [Releasing](../guide/releasing.md), and the per-platform
evidence in the [release acceptance matrix](../plans/RELEASE_ACCEPTANCE_MATRIX.md).
Where this page describes the payload installers below, that path is retained
for headless servers and is no longer published.

What exists today (FIXED-88 and FIXED-92 in [to be fixed](../plans/TO_BE_FIXED.md)):

- `raiker-app` starts Raiker with platform-appropriate data locations, a free
  loopback port, and Raiker's desktop window — or the default browser with
  `--browser`, or when the window is unavailable, saying why
  (`raiker/app/launcher.py`, `raiker/app/desktop_shell.py`; see
  [Desktop window](#desktop-window-desk-01desk-14)).
- Background start is registered with each platform's own service manager —
  `launchd` LaunchAgent, `systemd --user`, Windows per-user Startup — through
  `raiker-app service install|status|uninstall`.
- The host reports `running` / `paused` / `needs attention` / `stopped` with its
  in-flight background work, and offers Pause, Restart and Quit, from
  `raiker-app status|pause|resume|quit` and from the **Host** control in the web
  app's top bar. Quitting reports waiting work before it stops.
- `raiker-app uninstall` states every path it would remove and everything it
  would keep before removing anything, with a per-instance retain / export /
  securely-erase choice.
- The release pipeline exists (FIXED-92). `raiker/app/release.py` owns the target
  matrix, a reproducible payload build, the schema-1 manifest, and the signed
  channel index; `.github/workflows/release.yml` runs it per target on that
  target's own runner, along with a reproducibility double-build, the packaging
  smoke test below, and the native installer for that platform.
- The signed update channel exists (FIXED-92). `raiker/app/update.py` and
  `raiker/app/updater.py` verify the index against a pinned Ed25519 key, refuse a
  downgrade or an unsigned artifact, create a recovery copy before staging
  migration, swap by sibling-directory rename, and can roll back.
- A running Raiker states its own provenance (`raiker/app/installation.py`,
  `GET /api/host/update`, and the Host control's **Install & updates** section):
  signed release, unsigned build, or source checkout.

- `scripts/build_desktop.py` freezes the service, dashboard assets and tray
  dependencies into the platform payload. The Windows no-console build supplies
  safe null standard streams and resolves its web assets from the frozen bundle.
- A resumable five-stage first-run wizard covers owner creation, model choice and
  readiness, privacy, a verified encrypted backup choice, and completion.
- The native tray exchanges a one-time bootstrap secret for a host-control-only
  session and calls the same Open, Pause/Resume, Restart and Quit routes as the
  web Host control.

**No signed artifact has been published.** The pipeline is complete and refuses
to run without code-signing identities rather than producing something that looks
like a release; the Apple Developer ID, notarisation credentials and Authenticode
certificate are the release owner's to supply as repository secrets. Until then
the **Install** row is buildable but unexercised with a real identity.

## Product decision

Raiker is a self-hosted, multi-user application hosted on one user-owned
device. **It is desktop-first (owner decision, 2026-10-17):** installation runs
a local Raiker service and opens it in Raiker's own desktop window. The web
application is the same one the window shows, and the browser stays a supported
fallback — `raiker-app --browser`, `raiker-web`, headless hosts, and any
machine where the window is not installed.

After first-run setup, the Raiker host runs in the background. Closing the
window or the browser tab does not stop it. Stopping it is an explicit action
in the Host control, the tray/menu-bar control, or the service manager.

The service listens on loopback only by default. Network hosting, if ever
enabled, is an explicit administrator configuration with its own security
review; installation must not expose Raiker on the LAN.

## Per-user operation and isolation

One Raiker host can serve multiple login users on the same device. Each user
logs into a private Raiker instance through the login screen; it is not visible
to other Raiker users on that host. An instance has separate:

- encrypted workspace and database;
- models and provider credentials;
- files, folders, connectors, secrets, and audit events;
- schedules, background work, backup target, and retention settings.

No instance can read another instance's data. The host service must run with
least privilege and must not use a shared workspace between instances. A
desktop installation may run the host in the installing OS user's context; a
home-lab installation may instead run one dedicated Raiker host service for
its authorized local users.

## Lifecycle

| Moment | Required behavior |
|---|---|
| Install | Install signed application files only; do not create an account, model connection, or backup without user action. **Implemented** — `scripts/build_installer.py` writes only application files, and its post-install step creates the environment offline from the bundled wheels. |
| First run | Create a local account/instance, choose a model or defer it, explain privacy, create and verify an optional encrypted backup, then open the workspace. **Implemented** — `raiker/models/setup.py`, `raiker/api/routes_setup.py` (`/api/setup*`), and `SetupWizard.svelte`. |
| Host start | Start the Raiker host automatically and recover unfinished approved background work safely. |
| Window or browser closed | Keep the service running; scheduled work and indexing continue only within their approved policies. The desktop window says so the first time it is closed. |
| Pause / quit | Pause stops new background work; quit stops the service explicitly and reports any waiting work. |
| Update | Verify signature, back up before migration, migrate atomically, and retain a rollback path on failure. **Implemented** — `raiker/app/update.py`, `raiker/app/updater.py`, `raiker-app update --check\|--apply\|--rollback`. |
| Uninstall | Remove application files and service registration; offer to retain, export, or securely erase each local instance and backup configuration. |

Native service managers are preferred over a custom daemon manager:

| Platform | Mechanism | Status |
|---|---|---|
| macOS | `launchd` LaunchAgent for a desktop host; LaunchDaemon for an explicitly configured shared host | LaunchAgent implemented |
| Windows | per-user background/startup registration for a desktop host; Windows service for an explicitly configured shared host | Startup-folder entry implemented |
| Linux | `systemd --user` for a desktop host; system service for an explicitly configured shared host | `--user` unit implemented |

The per-user Windows registration is a Startup-folder entry rather than a `Run`
registry value, so install, inspect and uninstall are the same three file
operations on every platform and nothing survives an uninstall in a registry
hive. The shared-host rows remain specification: each is an explicit,
administrator-made decision with its own review.

The tray/menu-bar control shows `running`, `paused`, `needs attention`, or
`stopped`, and provides Open Raiker, Pause/Resume, Restart, and Quit actions.
`raiker/app/tray.py` is bundled by `scripts/build_desktop.py`; it holds only a
host-control session and reuses the web control's routes. `Restart` is offered only when a background registration exists —
nothing else would start the host again, and offering it otherwise would be a
control that lies.

`Pause` stops *new* background work. A run already parked on an approval the
owner has granted still continues: it is not new work, and abandoning it would
make Pause a way to lose a decision.

## Data, backup, and recovery

Instance data belongs in OS-standard per-user application-data locations, not
the installation directory. Data remains encrypted at rest. Backups are
opt-in and may target a user-selected NAS/mounted drive or supported cloud
storage provider; Raiker must never silently upload workspace data.

Every backup and restore must be encrypted, integrity-verified, attributable
to an instance, and visible in the UI with its retention and deletion status.
Before a database or format migration, Raiker creates a verified local
recovery point. The product must provide export, restore, connector revocation,
account reset, and device-move flows without requiring a terminal.

## Installer and release requirements

The release pipeline — `.github/workflows/release.yml`, started deliberately with
`workflow_dispatch` — calls `.github/workflows/desktop-package.yml` and publishes
the desktop installers (DIST-04):

| Target | Runner | Installers | Signing identity |
|---|---|---|---|
| Windows 10/11 x86-64 | `windows-2022` | NSIS `-setup.exe`, `.msi` | Authenticode (electron-builder) |
| Windows 11 on Arm | `windows-11-arm` (test only) | the x86-64 installer under emulation | — |
| macOS Apple silicon | `macos-14` | `.dmg`, `.zip` | Developer ID + notarisation |
| Linux x86-64 | `ubuntu-22.04` | AppImage, `.deb`, `.rpm` | GPG detached signatures |
| Linux ARM64 | `ubuntu-22.04-arm` | AppImage, `.deb`, `.rpm` | GPG detached signatures |

The desktop table lives in `raiker.app.desktop_release.DESKTOP_TARGETS`. The
payload targets below remain in `raiker.app.release.TARGETS` for the headless
payload and its updater:

| Target | Runner | Installer | Signing identity |
|---|---|---|---|
| macOS Apple Silicon | `macos-14` | `.pkg` | Developer ID + notarytool |
| Windows 10/11 x86-64 (AMD64; AMD or Intel CPU) | `windows-2022` | `.msi` | Authenticode (`signtool`) |
| Linux x86-64 (AMD64; AMD or Intel CPU) | `ubuntu-22.04` | `.deb`, AppImage | GPG detached signature |
| Linux ARM64 | `ubuntu-22.04-arm` | `.deb`, AppImage | GPG detached signature |

The table lives in `raiker.app.release.TARGETS`, so the workflow, the tests and
the product read one list rather than three that can disagree.

Each artifact bundles the service, the built web assets, and that platform's own
dependency wheels resolved on that platform's runner — `sqlcipher3` above
all, because development-machine success is not evidence about any other target.
`scripts/packaging_smoke_test.py` runs on each runner against the artifact that
runner just built: it checks the payload is complete, then opens an encrypted
database *from the extracted tree*, asserts the row is not readable in the file's
bytes, asserts a wrong key is refused, and reads it back with the right one.

Reproducibility is checked rather than asserted: each target builds its payload
twice from one checkout, with `SOURCE_DATE_EPOCH` pinned to the commit, and the
two digests must match.

**A build never claims a signature it does not have.** `signing: require` fails a
target whose identity secrets are absent; `signing: skip` produces artifacts named
`-unsigned` whose `installation.json` records `signing.applied = false`, and the
publish job refuses them. The running product reads that record and says
*unsigned build* — see the Host control's **Install & updates** section.

The first release must still test fresh install, upgrade, restart, offline use,
backup/restore, and uninstall on every supported architecture.

The channel index (`<channel>.json`, signed as `<channel>.json.sig`) maps each
target to its artifact, digest, manifest and signature, and is verified before
any of it is read. An installed Raiker pins the index URL and the release public
key with `raiker-app update --channel-url … --channel-key …`; until it does,
Raiker contacts no update service at all. A version that is not strictly newer is
*no update*, never an install, and an artifact whose build did not run platform
signing is refused rather than installed.

Every update channel manifest uses schema `1` and is signed over its exact JSON
bytes with the release Ed25519 key. The manifest binds the version, artifact
filename, and SHA-256 digest. Verification precedes extraction; extraction
rejects absolute paths, parent traversal, and symlinks. Migration runs only in a
staged sibling tree after the current installation has been copied to its
versioned recovery directory. The installed directory is replaced by rename,
and a failed second rename restores the previous directory immediately. The
recovery point remains until a later, separately governed retention decision.

## First-run experience

The installer and setup wizard do not require Python, Node, a terminal, or
environment-variable editing. The implemented setup order is:

1. create or sign in to the local Raiker instance;
2. select a local model, add a user-owned hosted-provider key, or defer model
   setup;
3. explain local/hosted privacy and test the selected connection;
4. choose no backup, NAS/mounted-drive backup, or a supported cloud provider;
5. open the workspace and show the background-service status.

## Safety and operability

Background operation never bypasses Raiker governance. Scheduled tasks,
connector access, egress, and tool actions retain their instance-specific
capability gates and confirmation requirements. Notifications are reserved for
actionable states such as a blocked task, failed backup, expired credential,
or required approval.

Raiker must expose health checks, readable redacted logs, a restart action,
and a user-generated diagnostic bundle that excludes secrets and workspace
content by default.

## Release bar

Raiker is ready for a non-technical desktop release only when a user can
install it, create a private instance, connect or defer a model, recover their
data, understand whether it is running, and safely control or remove it
without a terminal.

## Desktop window (DESK-01–DESK-14)

### Decision record — 2026-10-17

| Question | Decision | Reason |
|---|---|---|
| Should the native window stay deferred? | No. The desktop window is Raiker's default experience; the browser is a fallback. | Owner request, 2026-10-17: convert the web app into a desktop application, taking the UI/UX of reference personal agent and reference personal agent as references. |
| Which shell technology? | **Electron**, in `desktop/`. | The owner asked which shell the references use. reference personal agent's official desktop app is Electron over the agent's own core, sharing its sessions and configuration; reference personal agent's Mac app is native and its stack is not published. Electron also lets Playwright drive the real window, so the shell is tested end to end rather than only in a browser. |
| Who owns the host? | The host, unchanged. The window is one more loopback client. | Closing a window must not stop scheduled work or approvals, and every governed action must stay on the server. The shell holds no authority and no workspace data. |
| What happens to the browser? | Kept as a fallback (owner decision). | Headless and remote hosts, CI and the web app's own live suites need it, and an owner without the window must never be left without Raiker. |
| Desktop UI/UX adopted | A frameless window whose top bar is the title bar (macOS traffic lights over the navigation; Windows/Linux controls over the top bar's end, coloured to the theme); a native menu with shortcuts for each place; one window that comes forward on relaunch; close-to-background with a one-time notice ("Raiker keeps working after the window closes"); notifications that bring the window forward. | These are standard desktop conventions; none changes what Raiker may do. Cloud-hosted execution and external permission defaults are not adopted. |
| Can the window grant anything? | No. Context isolation, the Chromium sandbox and no Node in the page; one frozen bridge with three operations; navigation pinned to one loopback origin; only notification, clipboard-write and audio-only media permissions, to that origin. | A shell that could act would be a second governance path. |

### Delivery register

Every item is implemented; the evidence for each is in
[fixed items](../plans/FIXED_ITEMS.md) under the entry named.

| ID | Item | Where | Evidence |
|---|---|---|---|
| DESK-01 | Record the shell decision and this register | This section | FIXED-904 |
| DESK-02 | Electron shell that starts or joins the host | `desktop/src/main.ts`, `desktop/src/host.ts` | FIXED-904 |
| DESK-03 | Host handshake: `--ready-file`, readiness by `/api/health` instead of a fixed delay | `raiker/app/launcher.py` | FIXED-905 |
| DESK-04 | Window hardening: isolation, sandbox, origin pin, navigation/permission/window-open guards | `desktop/src/origin.ts`, `desktop/src/main.ts` | FIXED-906 |
| DESK-05 | Preload bridge `window.raikerDesktop` | `desktop/src/preload.ts`, `web/src/lib/desktopShell.ts` | FIXED-904 |
| DESK-06 | Window chrome: top bar as title bar, platform controls, theme-coloured overlay | `web/src/app.css`, `web/src/lib/desktopShell.ts` | FIXED-907 |
| DESK-07 | Window geometry memory and single instance | `desktop/src/windowState.ts` | FIXED-908 |
| DESK-08 | Native menu and shortcuts routed to the page | `desktop/src/menu.ts` | FIXED-909 |
| DESK-09 | Close to background, one-time notice, tray opens the window | `desktop/src/main.ts`, `raiker/app/tray.py` | FIXED-910 |
| DESK-10 | A clicked notification brings the window forward | `web/src/lib/desktopNotice.ts` | FIXED-911 |
| DESK-11 | `raiker-app` opens the window by default; `--browser` and an explained fallback | `raiker/app/desktop_shell.py` | FIXED-904 |
| DESK-12 | Packaging: the frozen host inside the shell | `desktop/electron-builder.yml` | FIXED-912, FIXED-913 |
| DESK-13 | CI for the shell | `.github/workflows/ci.yml` (job `desktop`) | FIXED-915 |
| DESK-14 | Live round against a real host and provider | `desktop/e2e/desktop-live.spec.ts`, `desktop/e2e/packaged-live.spec.ts` | FIXED-916 |

The release work that remained (BUG-343) is done by ADR-0003: the signed
pipeline publishes the desktop package, and the installed window is opened and
onboarded on each platform's runner.

## Deferred

A TUI is an optional later surface. It must reuse the same local service,
authentication, instance boundaries, and governance APIs; it is not a
prerequisite for the first installer release.
