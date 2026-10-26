# Releasing Raiker

This page is for maintainers. It explains how the desktop installers are built
and tested, how a signed release is published, and the rules that keep updates
safe. The decisions behind it are in
[ADR-0003](../adr/ADR-0003-desktop-distribution.md).

## What a release contains

| Target | Runner | Files |
|---|---|---|
| `windows-x86_64` | `windows-2022` | `Raiker-<v>-windows-x86_64-setup.exe`, `Raiker-<v>-windows-x86_64.msi` |
| `macos-arm64` | `macos-14` | `Raiker-<v>-macos-arm64.dmg`, `.zip` |
| `linux-x86_64` | `ubuntu-22.04` | `Raiker-<v>-linux-x86_64.AppImage`, `.deb`, `.rpm` |
| `linux-arm64` | `ubuntu-22.04-arm` | `Raiker-<v>-linux-arm64.AppImage`, `.deb`, `.rpm` |

Windows on Arm uses the x86-64 installer under emulation; CI tests that on a
`windows-11-arm` runner. Beside the installers each release carries a schema-1
manifest and signature per file (`<file>.manifest.json`, `.sig`),
`desktop-<channel>.json` and its `.sig` (the signed update index),
`release-public-key.txt`, the SPDX SBOM `raiker-<v>.spdx.json`, the signed
`release-provenance.json`, and `SHA256SUMS`.

The list of targets is code: `raiker.app.desktop_release.DESKTOP_TARGETS`.
`tests/test_desktop_release.py` fails if the workflow matrix, the
electron-builder file names or the target list disagree.

## What CI proves for every change

`.github/workflows/desktop-package.yml` runs on pull requests that touch the
desktop, the host's app layer, dependencies or the workflow itself, and on
`main`. On each target's own runner it:

1. installs the hash-locked build environment (`requirements/release-build.txt`)
   and builds the governed-command runner;
2. runs `scripts/build_desktop_app.py`, which freezes the host, writes
   `installation.json`, **smoke-tests the frozen host**, compiles the window and
   packages it with the pinned electron-builder;
3. checks the checksums;
4. **installs** the package as an owner would (NSIS silently per user; the
   `.dmg`'s app into `~/Applications`; the `.deb` through apt), then
   smoke-tests the installed host from an empty profile with
   `python -m raiker.app.desktop_smoke`, and on Linux the AppImage too;
5. opens the **installed window**, reaches first run, and completes the whole
   onboarding (`desktop/e2e/packaged-live.spec.ts`,
   `packaged-onboarding-live.spec.ts`);
6. **uninstalls** and checks the application is gone and the owner's data is
   kept; on Windows x86-64 it also installs, smoke-tests and removes the MSI.

The run summary is a per-target acceptance table; each target's artifact holds
its installers and the evidence files (`smoke-*.txt`, `uninstall-*.txt`,
screenshots). Python on the runner is build tooling and test harness only; the
installed product never uses it.

## Building installers locally

On the platform you are building for:

```bash
uv sync --extra dev            # or pip install -e ".[dev]"
npm --prefix web ci && npm --prefix web run build
npm --prefix desktop ci
python scripts/build_native_runner.py
python scripts/build_desktop_app.py --version 0.1.0
```

Output goes to `desktop-release/`. Linux `.rpm` needs `rpmbuild` (`apt install
rpm`). A local build is always unsigned; its `installation.json` records
`signing.applied = false`, and its filename is the same as a signed build's
(`Raiker-<version>-<target>[-setup].<ext>`). To smoke-test a
build or an installation: `python -m raiker.app.desktop_smoke --host <path to
resources/host/Raiker>`.

## Publishing a signed release

1. Configure the repository secrets once:

   | Secret | For |
   |---|---|
   | `APPLE_DEVELOPER_ID_CERTIFICATE`, `APPLE_DEVELOPER_ID_CERTIFICATE_PASSWORD` | Developer ID Application certificate (base64 `.p12`) |
   | `APPLE_NOTARY_KEY_ID`, `APPLE_NOTARY_ISSUER_ID`, `APPLE_NOTARY_PRIVATE_KEY` | App Store Connect API key for notarisation (base64 `.p8`) |
   | `WINDOWS_AUTHENTICODE_CERTIFICATE`, `WINDOWS_AUTHENTICODE_PASSWORD` | Authenticode certificate (base64 `.pfx`) |
   | `LINUX_PACKAGE_SIGNING_KEY`, `LINUX_PACKAGE_SIGNING_KEY_PASSWORD` | GPG key for detached package signatures |
   | `RAIKER_RELEASE_SIGNING_KEY` | Raw Ed25519 private key (hex) for manifests, the update index and provenance |

   Optionally set the repository variable `RAIKER_DESKTOP_CHANNEL_URL` to the
   HTTPS URL where `desktop-stable.json` will be served. Signed builds then
   carry it, so owners can check for updates from Settings without pinning a
   channel. The host must serve files directly: redirects are refused, so a
   GitHub Releases download URL does not work. GitHub Pages or any static host
   does.

2. Run **Actions → Release → Run workflow** with the version (`X.Y.Z`), channel
   (`stable` or `beta`), `signing: require`, and `publish: true`.
3. The workflow builds and tests every target with its identity, refuses a
   target whose identity is missing, builds and signs `desktop-<channel>.json`,
   the SBOM and the provenance, verifies all of it the way an installed Raiker
   will, and creates a **draft** release.
4. Review the draft, then publish it. The draft carries exactly **one
   installer per platform**, named for the platform, with their SHA-256 in the
   notes:

   | Platform | Release asset |
   |---|---|
   | Windows x86-64 | `Raiker-<version>-windows-x86_64-setup.exe` |
   | Windows on Arm | `Raiker-<version>-windows-arm64-setup.exe` — the x86-64 setup program, installed, smoke-tested and uninstalled on a Windows on Arm runner; it runs under Windows' built-in emulation |
   | macOS (Apple silicon) | `Raiker-<version>-macos-arm64.dmg` |
   | Linux x86-64 | `Raiker-<version>-linux-x86_64.AppImage` |
   | Linux ARM64 | `Raiker-<version>-linux-arm64.AppImage` |

   The other formats (`.msi`, macOS `.zip`, `.deb`, `.rpm`) are still built,
   installed and tested on every run and stay in the workflow artifacts
   (`scripts/select_release_assets.py` chooses the five). Copy the run's
   `release-channel` artifact — `desktop-<channel>.json` and its `.sig`, every
   installer the updater replaces an installation with, and their manifests and
   signatures — to the channel host.

`signing: skip` exercises the whole pipeline without identities. Every build
records `signing.applied = false`, no channel index is made, and with
`channel: beta` and `publish: true` the workflow creates a beta draft carrying
the same five files; it refuses to publish an unsigned stable release.

## Prerelease, stable, rollback and patches

- **Prerelease:** release to the `beta` channel. Only installations pinned to
  `desktop-beta.json` are offered it.
- **Stable:** release the same commit again to `stable` with a new version, or
  promote by publishing a stable release of the version that soaked on beta.
- **Rollback:** the updater never installs a version that is not strictly
  newer, so a bad release is withdrawn by publishing a fixed **patch** version
  (`X.Y.Z+1`), not by re-pointing the channel at an older one. An owner can
  return to the previous build locally: macOS and AppImage keep a `.previous`
  copy, and Windows reinstalls the earlier installer. An older build refuses to
  open data a newer one migrated, which is why rollback of a migrating release
  needs the backup taken before the update.
- **Patch:** branch from the release tag, fix, and release `X.Y.Z+1` to the
  same channel.

## Beta release checklist

A beta goes to the `beta` channel as a **draft**, and is published only when
the [beta release acceptance](../plans/ACCEPTANCE_TESTS_BY_PHASE.md#beta-release-acceptance)
rows hold on its commit:

1. CI is green on the commit, including `desktop-package.yml` when packaging
   paths changed since the last run.
2. The [release acceptance matrix](../plans/RELEASE_ACCEPTANCE_MATRIX.md) is
   current for every platform the beta offers.
3. The latest live rounds in
   [WEB_APP_LIVE_TEST.md](../architecture/WEB_APP_LIVE_TEST.md) pass on that
   commit, RT-SEC-01 to RT-SEC-12 among them.
4. The release notes say what a tester needs:
   - that it is a beta, and whether the installers are signed;
   - to back up the workspace before updating (Settings → Account), because an
     older build refuses data a newer one migrated;
   - how to reach a remote host: an SSH tunnel, or **Settings → Security →
     Remote access** (a private network with HTTPS, or a reverse proxy pointed
     at the remote listener, never at port 8765)
     ([Remote access](managing-the-host.md#remote-access));
   - that remote access needs two-step sign-in on every device and has no
     shared secret: `RAIKER_OWNER_TOKEN`, `--allow-public` and a non-loopback
     `--host` are retired, and an old service unit using them must be updated;
   - what remote access has not been verified on
     ([BUG-359](../plans/TO_BE_FIXED.md#bug-359--remote-access-is-verified-live-on-linux-only-and-has-five-known-limits));
   - the open defects that bound what the beta claims
     ([TO_BE_FIXED](../plans/TO_BE_FIXED.md)) and
     [known limits](../architecture/KNOWN_LIMITS.md).
5. Run **Release** with `channel: beta` and `publish: true`, review the draft,
   then publish it.

## Compatibility and migration policy

- Application files and owner data are separate: nothing in the profile folder
  is written by an installer or an update.
- The database carries a schema generation. A release may migrate it forward
  when it first opens; it must never require a migration to run before the
  owner can export or back up their data.
- A build refuses to open a database whose generation is newer than its own
  (`store_schema_newer`), so a downgrade cannot corrupt data. Settings →
  Updates says which recovery point can open the current data.
- An update never enables a capability, changes a permission's decision mode,
  or grants anything. New capabilities ship off or ask first, as the
  [permissions model](permissions-and-runtime-modes.md) requires.
- The update index and manifest schemas are versioned (`schema: 1`). A new field
  is only added together with a reader that accepts it, published in an earlier
  release than any index that uses it.
- Desktop and payload installations read separate indexes (`desktop-<channel>.json`
  and `<channel>.json`), so neither can be offered the other's artifact.
