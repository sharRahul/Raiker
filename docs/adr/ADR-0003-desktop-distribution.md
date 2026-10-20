# ADR-0003: Raiker as an installable desktop application

## Status

Accepted and implemented on 2026-10-17 (DIST-01 – DIST-12). Platform
verification is recorded per target in the
[release acceptance matrix](../plans/RELEASE_ACCEPTANCE_MATRIX.md). No signed
release has been published, because the signing identities are the release
owner's to configure; see [Known limitations](#known-limitations).

## Date

2026-10-17

## Context

The owner asked for Raiker to become an application an ordinary person can
download, install, set up through guided screens, and use, on Windows, macOS
and Linux, with no Python, Node.js, Git, package manager or terminal.

The audit of the repository at `a50790d` found most of the parts already
there, and one large gap:

| Already present | Where |
|---|---|
| An Electron desktop window that starts or joins the local host, hardened (context isolation, sandbox, one loopback origin, narrow permissions) | `desktop/src/*.ts`, DESK-01 – DESK-14 |
| A PyInstaller build of the host with its own interpreter | `raiker/app/desktop_build.py`, `scripts/build_desktop.py` |
| An electron-builder config that puts that frozen host inside the window | `desktop/electron-builder.yml` |
| Platform data directories, single-host-per-workspace joining, host lifecycle (status, pause, quit), background registration | `raiker/app/launcher.py`, `host.py`, `service.py` |
| A first-run wizard (Welcome, Model, Privacy, Ready) | `web/src/lib/views/ModelSetupView.svelte`, `raiker/api/routes_setup.py` |
| A signed update channel (Ed25519 index and manifests, downgrade refusal, recovery points, `store_schema_newer`) | `raiker/app/update.py`, `updater.py`, `installation.py` |
| A manual signed-release workflow with identity gating and provenance | `.github/workflows/release.yml`, `raiker/app/release.py` |
| An uninstall plan that states what it keeps and offers keep / export / erase | `raiker/app/uninstall.py` |

| Gap | Consequence |
|---|---|
| The release published `raiker-<v>-<target>.zip` wrapped by `scripts/build_installer.py` into `.pkg`, `.msi`, `.deb` and AppImage installers whose post-install step ran `python3 -m venv` | Every published installer needed a system Python 3.11 on the owner's machine. On a clean Windows or macOS it could not install. |
| Nothing built, signed or tested the Electron package in CI | BUG-343: the window had been exercised on Linux only, by hand |
| The release never built the governed-command runner (`raiker/native/`) | A released host would report `native_sandbox_artifact_missing` and Build could not run commands |
| No Intel-Mac, Windows-on-Arm or `.rpm` target | Two supported hardware families and one package family had no installer |
| A frozen host could not start the update helper (`sys.executable -m …`) | The in-app update would fail on every packaged build |
| Provider credentials' encryption key lived only in a 0600 file | No use of DPAPI, the Keychain or the Secret Service |
| First run had no device check, no permission summary, no installation check | An owner learned that something was missing only when it failed |

## Decisions

Each decision below states the current implementation and problem, the
alternatives, the choice and why, its security, user-experience and
compatibility effects, dependencies, the implementation tasks, the tests, the
acceptance criteria, and references.

### D1 — Desktop framework: keep Electron

- **Problem.** A desktop runtime already exists and is tested. The question is
  whether to keep it or migrate.
- **Alternatives.** *Tauri* — smaller bundle and a Rust core, but a rewrite of
  every `desktop/src` module, a second compiled toolchain on every runner, the
  platform WebView (WebKitGTK on Linux renders the Svelte app differently from
  Chromium, which the web app's Playwright suites test against), and no
  Playwright driver for the real window. *Native per OS* — three UIs.
  *Browser only* — no native window, menu, notifications or installer
  integration. *Electron (keep)*.
- **Choice.** Keep Electron 44.5.1 in `desktop/`, unchanged in architecture.
- **Justification.** It meets every requirement here; migration would replace
  working, tested code to save download size, which the owner did not ask for.
- **Security.** Unchanged: context isolation, Chromium sandbox, no Node in the
  page, one origin, narrow permissions. One bridge operation is added
  (`quitForUpdate`, D8), which can only close the window.
- **UX.** Same window, menu, shortcuts and tray behaviour.
- **Compatibility.** No API or data change.
- **Dependencies.** `electron` (pinned in `desktop/package-lock.json`),
  `electron-builder@26.17.0` (pinned by exact version in
  `raiker/app/desktop_build.py`).
- **Tasks.** None beyond D2–D12.
- **Tests.** `desktop/test/*.test.ts`, `desktop/e2e/shell.spec.ts` (unchanged).
- **Acceptance.** The window works on every target (D10).
- **References.** `desktop/src/main.ts`, [desktop distribution design](../architecture/DESKTOP_DISTRIBUTION_DESIGN.md#desktop-window-desk-01desk-14).

### D2 — Backend packaging and lifecycle: the frozen host inside the window (DIST-01)

- **Problem.** The published installers needed a system Python (see Context).
- **Alternatives.** *Bundle a CPython and create a venv at install time* —
  still runs `pip` on the owner's machine, slow and fragile offline.
  *Embedded Python distribution plus wheels* — the same, by hand. *PyInstaller
  one-dir host inside the Electron package* — already built and working for
  DESK-12. *Nuitka* — a compiler toolchain on every runner for no gain here.
- **Choice.** The desktop package is the release product: electron-builder
  wraps `desktop/` around `desktop-dist/Raiker/` (PyInstaller one-dir), placed
  at `resources/host/`. `scripts/build_desktop_app.py`
  (`raiker.app.desktop_build.build_app`) builds it per target: freeze the host,
  write `installation.json` beside it, smoke-test it, package, write manifests
  and checksums. The venv-based installers from `scripts/build_installer.py` are
  no longer published (the script stays for headless servers that already have
  Python).
- **Lifecycle.** Unchanged and already right: the window starts the host
  detached (`desktop/src/host.ts`) and waits for its ready file; a second start
  joins a running host on the same workspace rather than starting another
  (`raiker/app/launcher.py`, `choose_port`/`raiker_is_running`); the host keeps
  running when the window closes and stops through Host → Quit, the tray, or
  `raiker-app quit`. A host that stops before it is ready, or never becomes
  ready, is shown in the window with the reason. The host binds `127.0.0.1` only.
- **Security.** No installer runs `pip` or fetches code. The host keeps its
  loopback bind and its authentication. The governed-command runner is now
  built per target (`scripts/build_native_runner.py`) and its digest is checked
  at use, as before.
- **UX.** One installer, no prerequisites. First start takes a few seconds while
  the host opens its encrypted store.
- **Compatibility.** Same data directories as `raiker-app`, so a source install
  and a desktop install of one owner share a profile.
- **Dependencies.** PyInstaller from the hash-locked `requirements/release-build.txt`.
- **Tasks.** `raiker/app/desktop_build.py`, `raiker/app/desktop_release.py`,
  `desktop/electron-builder.yml`, `scripts/build_desktop_app.py`.
- **Tests.** `tests/test_desktop_release.py`; `raiker.app.desktop_smoke` on the
  frozen host before packaging and on the installed host after installing.
- **Acceptance.** On each target the installed host passes every smoke check
  from an empty profile with no Python of its own on `PATH`.
- **References.** `raiker/app/desktop_smoke.py`, `.github/workflows/desktop-package.yml`.

### D3 — Dependency provisioning (DIST-02)

- **Problem.** Each dependency needs a stated provisioning class.
- **Choice.**

  | Dependency | Class | How |
  |---|---|---|
  | Python interpreter and every Python package, including SQLCipher with FTS5 | Bundled | Frozen into `resources/host/` from the hash-locked set |
  | Built web app | Bundled | `--add-data web` |
  | Governed-command runner | Bundled | `raiker/native/<platform>/`, digest-checked |
  | Electron/Chromium runtime | Bundled | electron-builder |
  | GTK, NSS, libsecret and the other system libraries every Electron app needs (Linux) | Bundled by the OS | `.deb`/`.rpm` dependencies resolved by the package manager; the AppImage expects a desktop distribution |
  | Ollama, LM Studio, llama.cpp | Optional | Detected (`PATH` and the official install location); installed only by the owner from the vendor's official download, which Models links to (`raiker/models/runtime_installers.py`) |
  | Local model weights | Optional | Downloaded only on the owner's explicit choice, with size shown |
  | Hosted providers (OpenAI, Anthropic, OpenRouter, Gemini, …) | External service | The owner's key, stored encrypted (D6) |
  | Git, GitHub, messaging connectors | Optional / external | As today, behind their capability gates |
  | 32-bit systems, Windows before 10 1809, macOS before 12, glibc before 2.35 | Unsupported | Refused by the installer (Windows) or the system check, with the reason |

- **Security.** Nothing is downloaded at install time. Optional runtimes come
  only from the vendor's official URL, which the owner opens.
- **UX.** The installer needs no network. Local models are an informed choice.
- **Compatibility.** Unchanged runtime detection.
- **Tests.** `tests/test_system_check.py`; the frozen-host smoke test asserts FTS5.
- **Acceptance.** Installation succeeds offline on a clean machine.

### D4 — Local model installation (DIST-03)

- **Problem.** The request asked for consent-based automatic Ollama installation.
- **Alternatives.** *Download and run Ollama's installer from Raiker* — runs a
  third party's installer with the owner's privileges from inside an agent
  host, and its Windows installer is signed by Ollama, not verifiable against
  Raiker's release key. *Package-manager install* — needs elevation and
  differs per distribution. *Detect, recommend, and open the official download*.
- **Choice.** Detect (D3), recommend a model size from measured memory
  (`raiker.app.system_check.recommended_local_model`), and keep the existing
  reviewed-source preview (`RuntimeInstallerRegistry.preview`) that opens the
  vendor's own download. Raiker never runs a downloaded runtime installer
  itself. Model downloads remain an explicit act on Models, with size shown.
- **Security.** No privileged action is taken on the owner's behalf; UAC,
  Gatekeeper and package-manager prompts are the vendor's and are never bypassed.
- **UX.** One extra step for local models (the vendor installer), stated plainly
  rather than claimed to be automatic.
- **Tests.** `tests/test_system_check.py::test_the_local_model_advice_scales_with_memory`.
- **Acceptance.** Nothing large is downloaded without the owner choosing it.

### D5 — OS-specific packaging (DIST-04)

- **Choice.**

  | Target | Runner | Installers | Update artifact |
  |---|---|---|---|
  | `windows-x86_64` | `windows-2022` | NSIS `-setup.exe`, `.msi` | `-setup.exe` |
  | Windows on Arm | `windows-11-arm` (test only) | the x86-64 NSIS installer, under emulation | — |
  | `macos-arm64` | `macos-14` | `.dmg`, `.zip` | `.zip` |
  | `linux-x86_64` | `ubuntu-22.04` | `.AppImage`, `.deb`, `.rpm` | `.AppImage` |
  | `linux-arm64` | `ubuntu-22.04-arm` | `.AppImage`, `.deb`, `.rpm` | `.AppImage` |

  Windows on Arm has no native target: `cryptography` publishes no
  `win_arm64` wheel and building it needs an OpenSSL toolchain the runner
  lacks (found by the first CI run). Windows 11 on Arm runs the x86-64
  package under its built-in emulation, and CI installs, smoke-tests and
  uninstalls exactly that on a `windows-11-arm` runner. MLX is pinned to
  Apple silicon only, because it publishes no Intel-Mac wheels.

  Names: `Raiker-<version>-<target>[-setup].<ext>`, signed or not (owner
  decision 2026-10-19: signing state is recorded in `installation.json` and the
  manifest, not the filename). A draft release carries one installer per
  platform — Windows x86-64 and Arm (the emulated x86-64 setup program under
  its own name), macOS Apple silicon `.dmg`, Linux x86-64 and ARM64
  `.AppImage`. Windows
  installs per user (`%LOCALAPPDATA%\Programs\Raiker`), never elevates, adds
  Start-menu and desktop shortcuts, and refuses Windows before 10 1809 and
  32-bit Windows (`desktop/build-resources/installer.nsh`). macOS uses the
  hardened runtime with the entitlements Electron and the frozen host need
  (`build-resources/entitlements.mac.plist`) and requires macOS 12. Linux
  `.deb`/`.rpm` install to `/opt/Raiker` with a desktop entry.
- **Justification.** Each format is the one that platform's owners expect, and
  each is built and tested on that platform's own runner.
- **Security.** Least privilege on Windows; signed and notarised on macOS when
  identities exist; GPG detached signatures on Linux packages.
- **Tests.** `tests/test_desktop_release.py` keeps the names, the matrix and the
  workflow in step; `desktop-package.yml` installs each format.
- **Acceptance.** Each format installs, starts, completes onboarding and
  uninstalls on its runner.

### D6 — Secrets management (DIST-08)

- **Problem.** Provider keys are Fernet-encrypted under a vault key kept in a
  0600 file.
- **Alternatives.** *Move every key to the OS store, including the app key* —
  the app key derives the database key and is the backup custody root
  (`raiker/storage/backup.py`); a keyring reset would destroy every
  conversation. *Store each provider key in the OS store individually* — many
  prompts, and a second credential store beside the governed vault. *Protect the
  vault key with the OS store*.
- **Choice.** `raiker/auth/os_keystore.py`: the vault key is kept with DPAPI on
  Windows, in the login Keychain on macOS and in the Secret Service on Linux
  (`keyring`), and the key file holds only a reference. A plain key is moved on
  first read once the store returns it. On by default in packaged builds
  (`RAIKER_KEYSTORE=auto|off`).
- **Fallback policy.** No usable store (headless Linux, a locked or refusing
  keyring) keeps the 0600 file, and the system check says "Credential
  protection: private file". A protected key whose store cannot be read fails
  with `vault_keystore_unavailable` and is never regenerated. The app key
  remains a 0600 file; wrapping it is later work.
- **Security.** Provider keys are no longer recoverable from a copied profile
  without the owner's OS login on that machine. Removing an instance on
  uninstall removes its keyring item.
- **UX.** No prompt on Windows; macOS may ask once to allow Keychain access.
- **Compatibility.** Existing plain key files migrate in place; an older build
  reading a reference cannot use it (documented downgrade limit).
- **Dependencies.** `keyring>=25.6` (macOS/Linux only), hash-locked.
- **Tests.** `tests/test_os_keystore.py`.
- **Acceptance.** Every case above, and the smoke test's vault check.

### D7 — Desktop permissions and first run (DIST-05, DIST-06)

- **Problem.** First run did not say what the device can do, what Raiker may do,
  or whether the installation works.
- **Alternatives.** *An eight-screen wizard per the request, including a
  capability-enable step* — conflicts with FIRST-10 ("one sentence about
  permissions, instead of the matrix") and would make onboarding an
  authorisation step. *Leave first run as it was*. *Add read-only stages*.
- **Choice.** Seven stages: Welcome → **This device** → Model → Privacy →
  **Permissions** → **Check** → Ready. This device shows locally measured OS,
  architecture, memory, processor, graphics acceleration (never required),
  storage, network route (no packet sent), credential protection, local
  runtimes, data locations and a recommended local model size
  (`GET /api/setup/system`). Permissions shows the existing goal summary from
  the live gates and explains Ask / Allow within a scope / Automatic within
  policy / Never; it changes nothing. Check verifies the host, interface,
  encrypted database, data format, memory storage, permission registry,
  command runner and credential vault (`POST /api/setup/verify`), and takes one
  real readiness request to the chosen model.
- **Security.** Completing setup grants nothing; every gate keeps its default
  and fails closed.
- **UX.** Every stage can go back; a failure names its remedy; a deferred model
  says "Setup saved", not "ready". Setup does not repeat once complete.
- **Compatibility.** Stored stages from older builds still render; new stage
  names need no migration (no column constraint).
- **Tests.** `web/src/lib/views/ModelSetupView.test.ts` (DIST-05/06 block),
  `web/src/lib/firstRun.test.ts`, `tests/test_system_check.py`,
  `desktop/e2e/packaged-onboarding-live.spec.ts`.
- **Acceptance.** An owner completes onboarding in the installed window on each
  target.

### D7a — The system check runs during installation (DIST-05, revised)

- **Problem.** D7 put the device check and the installation check inside the
  in-app wizard, after the owner account existed. An owner could install
  Raiker, create an account, and only then learn the computer could not run
  it; and a check after sign-in reads as configuration, not installation.
- **Reference.** reference personal agent's installer (a separate signed Tauri app) runs a
  fixed list of named stages with live elapsed time, a hidden-by-default log,
  one plain sentence on failure with Retry beside it, and a completion receipt;
  it has no pre-flight check of memory or disk at all.
- **Alternatives.** *A separate installer application* like reference platform' — Raiker
  downloads nothing at install time (every dependency is bundled), so a second
  application would add a signing and update surface for no download it needs
  to drive. *Checks only in the native installers* — a dragged Mac app and an
  AppImage have no installer step, and an MSI cannot run custom UI from
  electron-builder. *Keep D7*.
- **Choice.** Two layers, both before any account exists. (1) Native
  pre-install checks where an installer can run code: the NSIS page
  *Checking this computer* (`customPageAfterChangeDir`: Windows build, 64-bit,
  memory, free space for the program and the data; a ✖ disables **Next**, a
  silent install exits 2) and a deb/rpm `--before-install` memory check; the
  floors are `system_check.py`'s. (2) **Raiker Setup**, a window of the shell
  shown on the first start of each installed version (`desktop/src/setup.ts`,
  `desktop/static/setup.*`): *Checking this computer* (the host's new
  `system-check --output` command, which creates nothing), *Preparing
  encrypted storage and starting Raiker*, *Verifying the installation*
  (`/api/health` store + text search, interface served). A receipt in the
  shell profile records completion per version; a later failed start opens it
  as a repair; `--repair` forces it. The in-app wizard drops **This device**
  and **Check** for `distribution: desktop` and keeps them for source and
  server installs.
- **Security.** The Setup page is packaged (`default-src 'none'`), has its own
  preload with two operations (hear progress; ask for one of five named
  actions), and the shell ignores messages from any other sender. The check
  sends no packet.
- **UX.** reference platform' patterns: step list with live timers, *N of M steps
  complete*, *Show details* log capped at 2,000 lines, failure as one sentence
  with Try again / Open logs / Quit and "Nothing here deletes your
  conversations or settings". The in-app wizard is a focused sheet without the
  app's navigation, with a segmented progress bar; branded NSIS sidebar/header
  and a drag-to-Applications dmg background share the Setup palette.
- **Tests.** `desktop/test/setup.test.ts`, `tests/test_system_check.py`
  (installation-time check creates nothing), `tests/test_desktop_release.py`
  (installer floors match the app's; artwork present),
  `web/src/lib/firstRun.test.ts`, `ModelSetupView.test.ts` (DIST-05 desktop
  block), `desktop/e2e/packaged-*.spec.ts` (Setup window on every target).
- **Not verified in CI.** The NSIS *Checking this computer* page itself (CI
  installs silently, which runs the same measurement in `customInit`) and the
  dmg background as rendered by Finder.

### D8 — Application updates (DIST-10)

- **Problem.** The signed updater swaps a payload directory; a desktop package
  is an NSIS install, an `.app` or an AppImage.
- **Alternatives.** *electron-updater* — a second update trust model (YAML
  metadata over HTTPS, no Ed25519 check on Linux) beside the one Raiker already
  verifies. *Reuse the signed channel and replace per platform*.
- **Choice.** The release publishes `desktop-<channel>.json`, the same schema-1
  signed index, mapping each target to its update artifact with a signed
  manifest. `raiker/app/desktop_update.py` verifies the download against that
  manifest, then: NSIS runs silently for the user (`/S --updated --force-run`);
  macOS unpacks with `ditto`, verifies the code signature when the install is
  signed, swaps `Raiker.app` by rename and keeps `Raiker.app.previous`; an
  AppImage is replaced atomically keeping `.previous`. `.deb`, `.rpm` and `.msi`
  are reported (`desktop_update_manual`): Raiker does not modify files the
  system package manager owns. The frozen host reaches the helper through a
  launcher entry (`--update-handoff`), and the window closes itself
  (`quitForUpdate`) so the new version can open.
- **Security.** Index signature, version strictly newer, manifest signature and
  SHA-256 all precede any execution; unsigned builds never update; data never
  moves.
- **UX.** Settings → Updates, as before. No check happens until the owner pins
  the channel and presses Check.
- **Compatibility.** The payload channel and its tests are unchanged.
- **Tests.** `tests/test_desktop_update.py`, `tests/test_desktop_release.py`.
- **Acceptance.** Verified installer applied per kind; tampered, unsigned,
  older or foreign-key artifacts refused.

### D9 — User data migration and downgrade (DIST-12)

- **Choice.** Binaries and data are separate by construction: the installation
  holds no profile data; the profile lives in `%LOCALAPPDATA%\Raiker`,
  `~/Library/Application Support/Raiker` or `$XDG_DATA_HOME/raiker`. Schema
  migrations run when the store opens (`raiker/storage/migrations.py`); a build
  refuses a database a newer build migrated (`store_schema_newer`), so a
  downgrade cannot corrupt data. The Check stage reports the data generation.
- **Security / UX.** A failed update leaves the old installation and the data in
  place; a downgrade is refused with a reason rather than opened.
- **Tests.** Existing migration tests; the smoke test's restart checks prove the
  profile survives a host restart.
- **Policy.** See [release process](../guide/releasing.md#compatibility-and-migration-policy).

### D10 — Cross-platform release automation (DIST-11)

- **Choice.** `.github/workflows/desktop-package.yml` builds, installs,
  smoke-tests, opens the window, completes onboarding and uninstalls on each
  native runner, on pull requests and `main` (unsigned) and from
  `release.yml` (signed, `secrets: inherit`). `release.yml` collects the signed
  installers, builds and signs `desktop-<channel>.json`, the SBOM and provenance,
  verifies them the way the product will, and creates a draft release only when
  signing was required.
- **Security.** Actions pinned by commit; identities only from secrets; a
  required identity that is absent fails the target.
- **Tests.** `tests/test_release_workflow.py`.

### D11 — Installation recovery (DIST-09)

- **Choice.** Installers are transactional where the format is (NSIS, MSI,
  dpkg, rpm); an interrupted install is re-run. The host refuses to start a
  second copy on one profile and joins the running one. The Check stage and
  Diagnostics name a broken component; the remedy for a damaged installation is
  reinstalling, which never touches data. Updates keep a rollback copy (D8).
- **Tests.** Smoke-test restart; `tests/test_desktop_update.py` rollback.

### D12 — Uninstallation and data retention (DIST-09)

- **Choice.** Windows: the uninstaller asks whether to also remove Raiker data,
  defaulting to **No**; silent uninstalls and updates always keep data; it
  stops the host and removes the background registration through
  `raiker-app uninstall`. macOS: moving `Raiker.app` to the Bin keeps data;
  removing it is **Settings → Account → Delete my account** before removing the
  app, or deleting the folder the guide names. Linux: `apt remove`/`dnf remove`
  keep every user's data (a system package cannot know each user's profile).
  External model runtimes and their models, workspaces the owner attached, and
  backups on external drives are never removed. Erasing an instance also removes
  its keyring item.
- **Tests.** `desktop-package.yml` uninstall steps assert the application is
  gone and data is kept; `tests/test_os_keystore.py` keyring removal.

## Known limitations

- No signed release exists yet: Apple Developer ID, notarisation credentials,
  an Authenticode certificate, a Linux GPG key and the release Ed25519 key are
  repository secrets the release owner must add.
- Unsigned test builds are refused by Gatekeeper on a Mac that downloads them,
  and Windows SmartScreen warns about them; they are for testing.
- `.deb`, `.rpm` and `.msi` installations are updated by installing the new
  package, not in place.
- The app key is not yet in the OS key store (D6).
- Intel Macs are not a supported desktop target. The release matrix ships
  macOS Apple-silicon artifacts only; the headless payload remains separately
  documented below where applicable.
- The update channel URL must serve files directly (no redirects), so GitHub
  Release download links cannot be pinned as a channel.
