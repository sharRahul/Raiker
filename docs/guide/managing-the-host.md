# Managing the Raiker host

`raiker-app` is the normal way to start and manage a local Raiker instance. It
chooses an available loopback port, starts the API and dashboard, and opens your
default browser. If the same instance is already running, it opens that host
instead of starting another process over the same encrypted workspace.

## Instance data and workspaces

Without `--workspace`, Raiker stores application data where the operating
system expects it:

| Platform | Default location |
|---|---|
| Windows | `%LOCALAPPDATA%\Raiker` |
| macOS | `~/Library/Application Support/Raiker` |
| Linux | `$XDG_DATA_HOME/raiker`, or the platform default when `XDG_DATA_HOME` is unset |

Set `RAIKER_HOME` to override the platform default. To keep the instance beside
a project, pass `--workspace PATH`; Raiker then uses `PATH/.raiker/`.

```bash
raiker-app --print-paths
raiker-app --workspace . --print-paths
```

Use the same `--workspace` value for every command that refers to that
instance. The option may appear before or after a subcommand.

## Start and inspect Raiker

```bash
raiker-app                         # start the default instance
raiker-app --workspace .           # start a project-local instance
raiker-app status                  # host and background-work status
raiker-app --workspace . status    # status for a project-local instance
```

`status` reports whether the host is running, paused, waiting for attention, or
stopped, and summarizes background work in flight.

## Start automatically at sign-in

```bash
raiker-app service install
raiker-app service status
raiker-app service uninstall
```

The service command uses the platform's user-level startup mechanism: launchd
on macOS, `systemd --user` on Linux, and the Startup folder on Windows. It does
not install a system-wide privileged service. Include `--workspace PATH` when
the service should operate a non-default instance.

The registration points to the current Raiker executable and workspace. If you
move or delete the source checkout, virtual environment, or workspace later,
remove the registration first and install it again from the new location.

## Pause, resume, and stop

```bash
raiker-app pause
raiker-app resume
raiker-app quit
```

Pausing prevents new background work from starting. Work that is already
approved may finish. `quit` reports waiting work before stopping the host. The
**Host** menu in the dashboard top bar exposes the same lifecycle controls.

The dashboard's **STOP** control is different: it requests cancellation of
queued, running, paused, and approval-waiting tasks at the next safe boundary.
It is governed and audited; it is not a process force-kill.

## Update and roll back

```bash
raiker-app update
raiker-app update --check
raiker-app update --apply
raiker-app update --rollback VERSION
```

The first command identifies whether this instance came from a signed release,
an unsigned build, or a source checkout. Checking for an update makes an
outbound request only after an update channel has been configured. No signed
Raiker artifact has been published yet, so source-checkout users normally
update through Git and rebuild the dashboard.

## Uninstall

Start with a preview:

```bash
raiker-app uninstall
```

The preview states what will be removed and retained. To proceed, add `--yes`
and explicitly choose what happens to instance data:

```bash
raiker-app uninstall --yes --data keep
raiker-app uninstall --yes --data export --export-to PATH
raiker-app uninstall --yes --data erase
```

Use `--print-paths` first and keep or export data unless you are certain the
owner account, conversations, configuration, audit records, and credentials are
no longer needed. `--data export` requires `--export-to`; the preview prints the
resolved destination before anything changes.

For a source checkout, uninstall removes the per-user startup registration and
applies the selected data disposition. It does not delete a repository checkout
or virtual environment it does not own; the preview tells you to run
`python -m pip uninstall raiker` when package removal is still needed.

## Explicit web-server control

`raiker-web` is the lower-level service entry point:

```bash
raiker-web --workspace . --no-browser
```

It binds to `127.0.0.1:8765` by default. Binding beyond loopback requires both
`--allow-public` and a hardened `RAIKER_OWNER_TOKEN`. Put TLS and appropriate
network controls in front of any non-loopback deployment. This does not turn
Raiker into a supported hosted multi-user service.

For installation failures or stale dashboard builds, see
[Troubleshooting](troubleshooting.md).
