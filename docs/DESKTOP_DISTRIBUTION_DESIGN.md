# Desktop Distribution Design

## Status

**Partly implemented.** Raiker runs as a Python service with a web application.
This document defines the product shape required to distribute it as an
installable application for Windows, macOS, and Linux.

What exists today (FIXED-88 in [to be fixed](plans/TO_BE_FIXED.md)):

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

What does not exist yet (BUG-44): signed installers, a published signed update
channel, the setup wizard, and a native tray icon. The platform-independent
update boundary now exists in `raiker/app/update.py`: it verifies an Ed25519
manifest and artifact digest before changing the installation, creates a
recovery copy before staging migration, and swaps or restores the installation
by sibling-directory rename. Publishing still needs code-signing identities and
per-OS release runners, so the **Install** row, channel delivery, and release
requirements below remain specification rather than description.

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
| Install | Install signed application files only; do not create an account, model connection, or backup without user action. |
| First run | Create a local account/instance, choose a model or defer it, select optional backup, then start the local service. |
| Host start | Start the Raiker host automatically and recover unfinished approved background work safely. |
| Browser closed | Keep the service running; scheduled work and indexing continue only within their approved policies. |
| Pause / quit | Pause stops new background work; quit stops the service explicitly and reports any waiting work. |
| Update | Verify signature, back up before migration, migrate atomically, and retain a rollback path on failure. |
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

The tray/menu-bar control must show `running`, `paused`, `needs attention`, or
`stopped`, and provide Open Raiker, Pause, Restart, and Quit actions. Those
states and the Pause / Restart / Quit actions are implemented in the web app's
top bar and in `raiker-app`; a native tray icon needs the packaged, signed binary
of BUG-44. `Restart` is offered only when a background registration exists —
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

The release pipeline produces signed, reproducible artifacts for:

- macOS: Apple Silicon and Intel (`.dmg` or `.pkg`);
- Windows 10/11: `.msi` or signed installer executable;
- Linux: AppImage and `.deb` initially.

Each artifact bundles the service, web assets, and platform-compatible native
dependencies. The first release must test fresh install, upgrade, restart,
offline use, backup/restore, and uninstall on every supported architecture.
Native encrypted-database dependencies require packaging tests on every target;
development-machine success is insufficient.

Every update channel manifest uses schema `1` and is signed over its exact JSON
bytes with the release Ed25519 key. The manifest binds the version, artifact
filename, and SHA-256 digest. Verification precedes extraction; extraction
rejects absolute paths, parent traversal, and symlinks. Migration runs only in a
staged sibling tree after the current installation has been copied to its
versioned recovery directory. The installed directory is replaced by rename,
and a failed second rename restores the previous directory immediately. The
recovery point remains until a later, separately governed retention decision.

## First-run experience

The installer and setup wizard must not require Python, Node, a terminal, or
environment-variable editing. The setup order is:

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
