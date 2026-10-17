# Release acceptance matrix — desktop packages

Per-platform evidence for the desktop installers
([ADR-0003](../adr/ADR-0003-desktop-distribution.md)). A result is **PASS**
only when it was executed and the evidence is named. **NOT TESTED** means it
has not been run. **BLOCKED** names the blocker. Nothing here is inferred from
another platform.

Builds are unsigned until the release owner configures the signing identities
([Releasing](../guide/releasing.md#publishing-a-signed-release)), so every
row below is for an **unsigned** build.

## Matrix

Status as of 2026-10-17. CI evidence comes from `.github/workflows/desktop-package.yml`
on PR #235; local evidence comes from an Ubuntu 24.04 x86-64 container.

| Target | Installers | Build | Install | Installed-host smoke | Window + onboarding | Uninstall keeps data | Update | Evidence |
|---|---|---|---|---|---|---|---|---|
| linux-x86_64 | AppImage, deb, rpm | PASS | PASS (deb via apt) | PASS (20/20) | PASS | NOT TESTED locally | NOT TESTED | Local container, see [Local evidence](#local-evidence-linux-x86-64) |
| linux-x86_64 (CI) | AppImage, deb, rpm | see run | see run | see run | see run | see run | NOT TESTED | CI run summary |
| linux-arm64 | AppImage, deb, rpm | see run | see run | see run | see run | see run | NOT TESTED | CI run summary |
| windows-x86_64 | setup.exe, msi | see run | see run | see run | see run | see run | NOT TESTED | CI run summary |
| Windows on Arm (x86-64 package, emulated) | setup.exe | n/a | see run | see run | NOT TESTED | see run | NOT TESTED | CI run summary |
| macos-arm64 | dmg, zip | see run | see run | see run | see run | see run | NOT TESTED | CI run summary |
| macos-x86_64 | dmg, zip | see run | see run | see run | see run | see run | NOT TESTED | CI run summary |

"see run" rows are filled from the CI run on the PR's head commit; this table
is updated with the result once that run completes.

## Local evidence (Linux x86-64)

Built with `python scripts/build_desktop_app.py --version 0.1.0` at the PR's
first commit:

- `Raiker-0.1.0-linux-x86_64-unsigned.AppImage` (182 MB), `.deb` (150 MB),
  `.rpm` (134 MB); `sha256sum --check SHA256SUMS-linux-x86_64.txt` → all OK.
- Frozen-host smoke before packaging: 20 PASS, 0 FAIL.
- `apt-get install ./Raiker-0.1.0-linux-x86_64-unsigned.deb` → installed to
  `/opt/Raiker`, `/usr/share/applications/raiker.desktop`, `/usr/bin/raiker`.
- `python -m raiker.app.desktop_smoke --host /opt/Raiker/resources/host/Raiker
  --expect-unsigned` → 20 PASS: provenance, ready, health, encrypted store,
  FTS5, web app served, owner registration, setup required, system check (no
  blocking failure), installation check (no failed mandatory component), setup
  saved, quit, restart opens the same profile, sign-in after restart, setup
  progress survives restart. The governed-command runner is present at
  `_internal/raiker/native/linux-x86_64/` and executable.
- `xvfb-run npx playwright test --project=live packaged` with
  `RAIKER_PACKAGED_APP=/opt/Raiker/raiker` → 2 passed: the installed window
  starts its bundled host and opens on first run; an owner registers and
  completes Welcome → This device → Model (Decide later) → Privacy →
  Permissions → Check (no "Needs attention") → Setup saved → Home.
- Reinstalling the rebuilt `.deb` over the first (`apt-get install --reinstall`)
  succeeded and the new build passed the same two window tests: a package
  upgrade in place, not an update through the signed channel.

## Scenario coverage

| Scenario | Status | How |
|---|---|---|
| Fresh install, no developer tools on the profile | PASS on Linux (local); per-target in CI | Smoke test from an empty profile; the host is frozen and uses no system Python |
| Setup wizard completes | PASS on Linux (local) | `packaged-onboarding-live.spec.ts` |
| Backend starts automatically and restarts | PASS on Linux (local) | Window starts the host; smoke test quits and restarts it |
| A supported AI provider answers | NOT TESTED | Needs a provider credential or a local runtime on the runner; the Check stage's model request covers it on a real machine |
| Basic agent task within approved permissions | NOT TESTED in packaged builds | Covered for source builds by the existing live suites |
| No internet during install and first run | PASS by construction on Linux (local) | Installer downloads nothing; smoke test makes no outbound request |
| Interrupted download, corrupted or untrusted update | PASS (unit) | `tests/test_desktop_update.py`: tampered digest, foreign key, wrong version refused |
| Insufficient disk / memory, unsupported architecture or OS | PASS (unit) | `tests/test_system_check.py`; Windows installer `customInit` refuses old and 32-bit Windows |
| Keystore unavailable or locked | PASS (unit) | `tests/test_os_keystore.py`: fail closed, never regenerated, file fallback |
| Missing optional local runtime | PASS (unit and UI) | System check reports it as optional; Models links the official download |
| Uninstall keeping data | Per-target in CI | Uninstall steps assert app removed, data kept |
| Uninstall removing selected data | NOT TESTED in CI | Interactive dialog (Windows) / Settings → Account → Delete my account; keyring removal covered by `tests/test_os_keystore.py` |
| Update through the signed desktop channel | PASS (unit); NOT TESTED end to end | Needs a published signed release and a channel host |
| Failed-update recovery | PASS (unit) | `.previous` rollback for AppImage; NSIS installer is transactional |
| API keys not written to logs | Unchanged existing redaction | Existing log redaction tests; the smoke test sends no key |
| Installer privileges minimised | PASS (config + CI) | `perMachine: false`, `allowElevation: false`; CI installs without elevation |
