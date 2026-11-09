# Release acceptance matrix — desktop packages

> Owner scope update: personal use for at most five users, PC first and
> phone/iPad later; no commercial-grade distribution/signing prerequisite.
> Piper is removed in favor of Kokoro-82M. The earlier `6c211b60` signed
> candidate/audit precede this change and retain their original SHA.
> [Authoritative scope and remaining engineering checks](PERSONAL_BETA_SCOPE.md).


Per-platform evidence for the desktop installers
([ADR-0003](../adr/ADR-0003-desktop-distribution.md)). A result is **PASS**
only when it was executed and the evidence is named. **NOT TESTED** means it
has not been run. **BLOCKED** names the blocker. Nothing here is inferred from
another platform.

Builds are unsigned until the release owner configures the signing identities
([Releasing](../guide/releasing.md#publishing-a-signed-release)), so every
row below is for an **unsigned** build.

## Matrix

Status as of 2026-10-20. CI evidence: `.github/workflows/desktop-package.yml`,
[run 39327713463](https://github.com/sharRahul/Raiker/actions/runs/39327713463)
(attempt 2) on commit `9c65e86` on `main` (PR #236) — all seven jobs green: the
four build targets, the emulated Windows-on-Arm install, web assets and the
release acceptance summary. Earlier runs 39051611755 on `808409c` (PR #235),
39044354934 on `6758e64` and 39041854653 on `914b60a` passed before it. Each
target runs on its own GitHub-hosted runner, unsigned, version stamp `0.0.0`,
and its artifact holds its installers and the evidence files named below. The
workflow runs on pull requests and pushes to `main` that touch packaging paths,
on demand, and from `release.yml`; a change outside those paths (such as the 2026-10-20 model
transport work) does not re-run it.

**What a release carries.** A draft GitHub release has exactly one installer
per platform (`RELEASE_ASSETS`, `raiker/app/desktop_release.py`;
`scripts/select_release_assets.py`): `windows-x86_64-setup.exe`, the same
installer as `windows-arm64-setup.exe`, `macos-arm64.dmg`,
`linux-x86_64.AppImage` and `linux-arm64.AppImage`, with `SHA256SUMS.txt`. The
`.msi`, `.zip`, `.deb` and `.rpm` formats in the table are built and tested on
every run but are not attached to a release. No release has been published
yet.

| Target (runner) | Installers | Build + frozen-host smoke | Install | Installed-host smoke | Window + onboarding | Uninstall keeps data | Signed-channel update |
|---|---|---|---|---|---|---|---|
| windows-x86_64 (`windows-2022`) | setup.exe, msi | PASS | PASS — NSIS `/S` per user, Start-menu shortcut present; MSI `/qn` per user | PASS (NSIS and MSI) | PASS | PASS — NSIS uninstall; MSI `/x` | NOT TESTED |
| Windows on Arm (`windows-11-arm`, x86-64 package under emulation) | setup.exe (x86-64) | n/a — no native build | PASS — NSIS `/S` per user | PASS | NOT TESTED | PASS — NSIS uninstall | NOT TESTED |
| macos-arm64 (`macos-14`) | dmg, zip | PASS | PASS — app copied from the mounted dmg to ~/Applications | PASS | PASS | PASS — app removed, ~/Library/Application Support/Raiker kept | NOT TESTED |
| linux-x86_64 (`ubuntu-22.04`) | AppImage, deb, rpm | PASS | PASS — `apt-get install ./…deb` | PASS (deb and AppImage) | PASS | PASS — `apt-get remove raiker`, ~/.local/share/raiker kept | NOT TESTED |
| linux-arm64 (`ubuntu-22.04-arm`) | AppImage, deb, rpm | PASS | PASS | PASS (deb and AppImage) | PASS | PASS | NOT TESTED |

"Installed-host smoke" is `raiker.app.desktop_smoke` from an empty profile:
provenance (unsigned), ready, health, encrypted store, FTS5, web app served,
owner registration, setup required, system check with no blocking failure,
installation check with no failed mandatory component, setup saved, quit,
restart over the same profile, sign-in and setup progress after restart.
"Window + onboarding" is `packaged-live.spec.ts` and
`packaged-onboarding-live.spec.ts` against the installed executable: the
**Raiker Setup** window opens first (Finish installing → *Checking this
computer* lists what it found → host started → verified → *Raiker is ready*),
**Open Raiker** opens the window on first run, and an owner registers and walks
Welcome → Model (Decide later) → Privacy → Permissions → Setup saved → Home.

**Installation-time checks.** Windows: every NSIS install in CI is silent
(`/S`), which runs the same memory and free-space measurement in `customInit`
and installs only when it passes — PASS on both Windows rows. The interactive
*Checking this computer* page itself is NOT TESTED (no GUI driver for the NSIS
wizard in CI); it compiles in electron-builder's include order. Linux: the
`.deb` pre-install check ran and passed in each `apt-get install` (and
locally: "Raiker: checking this computer before installing … memory: 16093
MB"). The refusal paths (too little memory or disk) are NOT TESTED on a real
machine.

**Windows on Arm** — there is no native arm64 package (`cryptography` ships
no win_arm64 wheel, so the host cannot be frozen there). The x86-64 installer
was installed, smoke-tested from an empty profile and uninstalled on a
`windows-11-arm` runner under Windows' x64 emulation (evidence
`smoke-installed-windows-arm64.txt`, `uninstall-windows-arm64.txt`). The
window tests were not run there.

**.rpm** packages are built and checksummed on both Linux runners but are not
installed in CI (the runners are Debian-based); NOT TESTED beyond `rpm -qp`
inspection locally (package name `raiker`).

**Not covered by any row:** signed builds (no identities configured),
Gatekeeper on a quarantined download, SmartScreen, a real model provider, and
an update through a published signed channel.

## Beta readiness — host checks (2026-10-26)

What a beta tester's host does that the installer rows above do not cover,
checked on a source build served by `raiker-web`:

| Check | Status | How |
|---|---|---|
| A forwarded request on the local listener is refused and says what to change | PASS | RT-SEC-01; `tests/test_proxied_loopback.py` |
| Diagnostics names a refused proxy, with flags kept on one line | PASS | RT-SEC-02 |
| Every request on the proxy listener is remote, with no forwarding header or a misleading one: recovery refused, rate limited, HSTS over HTTPS | PASS (live, unit, and a real uvicorn server) | RT-SEC-03; `test_a_real_server_tells_its_listeners_apart` |
| The proxy listener as a Unix socket (`--proxy-socket`), mode `0660` | PASS (by hand and unit) | `test_a_real_unix_socket_listener_is_remote`; [WEB_APP_LIVE_TEST.md](../architecture/WEB_APP_LIVE_TEST.md), BUG-347 review round |
| The host refuses to start while `RAIKER_TRUSTED_PROXY` is set, and refuses `--allow-public` or a non-loopback `--host`; `RAIKER_OWNER_TOKEN` is not read | PASS (unit and by hand) | `tests/test_proxied_loopback.py`, `tests/test_remote_auth.py` |
| Remote access is chosen, checked, applied with fresh MFA, restarted into, rolled back and turned off from Settings; the UI shows only what the running host reports | PASS (live, Linux) | RT-SEC-04 to RT-SEC-07, RT-SEC-11, RT-SEC-12 |
| Another device needs the password and a code over HTTPS; password-only and local sessions are refused; MFA off suspends at once | PASS (live, Linux; unit on all three) | RT-SEC-08 to RT-SEC-10; `tests/test_remote_auth.py` |
| Real listeners (TCP, TLS, Unix socket), port claims and restart status on Windows and macOS | PASS (CI job *Remote access*) | `tests/test_remote_access.py`, `tests/test_proxied_loopback.py`; no live browser round on either ([BUG-359](TO_BE_FIXED.md#bug-359--remote-access-is-verified-live-on-linux-only-and-has-five-known-limits)) |
| The packaged desktop host behind a proxy | NOT TESTED | The desktop app binds loopback for its own window; it is not meant to sit behind a proxy |

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

## Linux hardening qualification — 2026-11-09

[Detailed run record and limits](LINUX_BETA_2026_11_09.md). The source-host
onboarding test passed after explicitly deferring Voice, and keyboard traversal
and 200% zoom passed 2/2 with inspected screenshots. Real llama.cpp b12223 CPU
inference and slot lifecycle passed; fifteen native containment/resource tests
passed. Real ENOSPC on a 98.02%-full dedicated tmpfs retained the Apply journal
and restored every original after space returned. These are not clean-machine
or signed installed-candidate acceptance.

The RPM failure reproduced with FPM's level-9 multithreaded compressor; a
512 MiB controlled comparison passes with the newly selected level-6
single-threaded compressor. Accept AppImage, DEB and RPM together only after
the full wrapper and artifact checks succeed. Keep signed update/rollback,
packaged managed speech, all seven real-model journeys, full local-only
egress qualification and exact-commit release evidence open until measured.

**Local all-format follow-through:** Python 3.12 freeze and frozen smoke passed;
the complete wrapper now produced AppImage, DEB and RPM. All three SHA-256
checks pass, and RPM's header confirms `xz 6`; payload digests pass. These
unsigned `0.0.0` working-tree artifacts have no exact-commit provenance claim.
RPM's extracted frozen host/window checks and native Fedora installation are
separate from successful package creation. The corrected-source 1,805.76-second
trace retains a **not approved** verifier result and does not close MM-5; see
the [receipts](LINUX_BETA_2026_11_09.md#artifact-and-audit-receipts).

**RPM payload checks:** extracted frozen-host smoke, restart and setup
persistence passed. Extracted-window onboarding passed; the independent
first-run window test crashed its renderer on its first attempt and passed an
isolated fresh-profile retry. This is Ubuntu payload evidence, not Fedora RPM
installation acceptance. Both attempts are retained in the run record.

FIXED-1375 prevents unconnected ChatGPT status reads from starting Codex App
Server. Candidate egress qualification must include that correction and a
fresh recording; earlier failed reports are not superseded by unit tests.

**Exact runtime qualification:** `8a053a90` passed CI, data-safety drills and
all llama.cpp engine/live jobs. The exact Release Plan script passed locally.
The signed non-published candidate dispatch was refused by GitHub (403,
Actions access), so signed candidate artifacts and generated release evidence
remain **BLOCKED**, not passed. The earlier desktop matrix on `91b07ce2` is
green on every target, including Windows-on-Arm emulation.
[Receipts and workflow links](LINUX_BETA_2026_11_09.md#github-qualification-and-release-dispatch-access).

The full installed-shell capture also found Electron startup resolver traffic
that the host-only trace missed. FIXED-1376 disables automatic DoH and
non-loopback shell resource requests; 36 unit and 13 UI tests pass. Chromium's
non-sending IPv6 UDP route probe remains explicitly recorded. A fresh candidate
with this shell correction needs its own CI, package and egress evidence.
[Follow-through](LINUX_BETA_2026_11_09.md#electron-network-process-follow-through).

## 2026-11-09 — Completed bounded installed-shell audit

The `6c211b60` installed unsigned Linux shell/host audit passes its predeclared
fresh-profile scope: 1,862 seconds of actual destination activity, 4,115
observations, no unexpected hosts. The 30-minute navigation driver completed
62 visits without failure; screenshot states were inspected. Chromium's 135
non-sending IPv6 UDP route probes and native control probes remain explicit
in the scope and receipts. Earlier failed captures remain failed.

**MM-5 remains partial:** no selected useful model, managed speech, enabled
external connector, owner-machine full-feature sign-off or signed-artifact
capture is inferred. All four qualification workflows for runtime `6c211b60`
are green; downloaded CI Linux artifact hashes and RPM digests verify.
[Evidence and limits](LINUX_BETA_2026_11_09.md#completed-installed-shell-audit-and-ci-artifact-verification).

## 2026-11-09 — Signed candidate output verified

[Release 42650624663](https://github.com/sharRahul/Raiker/actions/runs/42650624663)
passed for exact runtime `6c211b60`, version `0.9.0`, beta channel,
`require-except-macos`, publication disabled. Independent checks passed for
all 10 installer hashes/Ed25519 manifests, six Linux GPG signatures, signed
channel/provenance, SBOM binding, repository lock hash and checksum files.
The product verifier and generated evidence inventory pass. The owner's
manual dispatch supplied the needed access; this candidate is no longer
blocked on candidate creation. Windows native checks passed in the workflow;
macOS retains its platform-signing exception.

This establishes CI-1/CI-5 candidate-output evidence, not beta sign-off.
Full Voice/licence/packaged-speech, seven real-model journeys, live connector
revocation/reconnect, full-feature signed-artifact egress and owner-machine
acceptance remain open. The reporting fix preserves that candidate's SHA; the subsequent owner-requested
Kokoro/Piper runtime change requires a new personal candidate.
[Artifact, signatures and receipts](LINUX_BETA_2026_11_09.md#verified-non-published-signed-candidate).
