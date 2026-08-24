# Desktop Distribution Design

## Status

**Implemented, pending signed publication.** Raiker runs as a self-contained
desktop payload with a web application. This document records the product shape
used to distribute it for Windows, macOS, and Linux.

What exists today (FIXED-88 and FIXED-92 in [to be fixed](../plans/TO_BE_FIXED.md)):

- `raiker-app` starts Raiker with platform-appropriate data locations, a free
  loopback port, and the default browser (`raiker/app/`, `apps/api/launcher.py`).
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
device. It is web-first: installation runs a local Raiker service and opens
the web application in the user's default browser. A native desktop shell is
not required for the first packaged release.

After first-run setup, the Raiker host runs in the background. Closing the
browser tab does not stop it. Stopping it is an explicit action in the
tray/menu-bar control or service manager.

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
| Browser closed | Keep the service running; scheduled work and indexing continue only within their approved policies. |
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
`workflow_dispatch` — produces reproducible artifacts for:

| Target | Runner | Installer | Signing identity |
|---|---|---|---|
| macOS Apple Silicon | `macos-14` | `.pkg` | Developer ID + notarytool |
| Windows 10/11 x86-64 (AMD64; AMD or Intel CPU) | `windows-2022` | `.msi` | Authenticode (`signtool`) |
| Linux x86-64 (AMD64; AMD or Intel CPU) | `ubuntu-22.04` | `.deb`, AppImage | GPG detached signature |
| Linux ARM64 | `ubuntu-22.04-arm` | `.deb`, AppImage | GPG detached signature |

The table lives in `raiker.app.release.TARGETS`, so the workflow, the tests and
the product read one list rather than three that can disagree.

Each artifact bundles the service, the built web assets, and that platform's own
dependency wheels resolved on that platform's runner — `sqlcipher3-wheels` above
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

## Deferred

A TUI and a native desktop window are optional later surfaces. They must reuse
the same local service, authentication, instance boundaries, and governance
APIs; they are not prerequisites for the first installer release.
