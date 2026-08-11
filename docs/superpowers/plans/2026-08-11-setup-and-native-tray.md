# Setup and Native Tray Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the model-only setup screen with a resumable first-run wizard and ship a real native tray controller backed by a self-contained Windows application bundle.

**Architecture:** Account creation remains the authentication boundary. After login, an owner-scoped setup state machine records model, privacy, backup, and completion choices. The packaged desktop host launches the API and native pystray process together; the tray exchanges a one-time bootstrap secret for a narrowly scoped host-control session and calls the same authenticated host routes as the web UI.

**Tech Stack:** Python, FastAPI, SQLite migrations, cryptography, Svelte 5, pystray, Pillow, PyInstaller one-directory bundle, WiX, pytest, Vitest, Playwright.

## Global Constraints

- Setup choices are owner-scoped, resumable, and truthful; never mark backup complete until a restorable snapshot succeeds.
- Provider credentials enter through existing vault-backed UI routes and never enter setup-state rows, logs, query strings, or tray arguments.
- Tray authority is limited to host read/pause/resume/restart/quit and cannot read conversations, files, credentials, or approvals.
- The packaged app must contain its Python runtime and dependencies; WiX must install that bundle instead of copying the source tree.

---

### Task 1: Replace model-only persistence with a complete setup state

**Files:**
- Modify: `raiker/models/setup.py`
- Modify: `raiker/storage/migrations.py`
- Modify: `raiker/storage/sqlite.py`
- Modify: `raiker/api/schemas.py`
- Create: `raiker/api/routes_setup.py`
- Modify: `raiker/api/app.py`
- Modify: `tests/test_model_setup_state.py`
- Create: `tests/test_setup_state.py`

- [ ] Add failing tests for owner isolation, valid stage transitions, resume after restart, skip semantics, invalid enum rejection, and migration of existing `model_setup_state` rows.

```python
def test_setup_state_resumes_for_owner(client, owner_headers):
    saved = client.put("/api/setup", headers=owner_headers, json={"stage": "privacy", "privacy_mode": "local_first"})
    assert saved.status_code == 200
    assert client.get("/api/setup", headers=owner_headers).json()["stage"] == "privacy"
```

- [ ] Run `python -m pytest tests/test_model_setup_state.py tests/test_setup_state.py -q` and verify the new tests fail.
- [ ] Add `SETUP_STATE_MIGRATION_ID` and an owner-keyed table containing `status`, `stage`, `selected_profile_id`, `selected_model`, `privacy_mode`, `backup_status`, `backup_target`, `completed_at`, and timestamps. Migrate legacy rows without losing selected model data.
- [ ] Define immutable setup models and enums in `raiker/models/setup.py`; accept only known stage transitions and validate model profile/model pairs through the existing registry.
- [ ] Implement authenticated `GET /api/setup` and `PUT /api/setup`. Keep `/api/model-setup` as a compatibility adapter for one release so existing clients do not break.
- [ ] Backfill existing owners as complete only when their legacy model state was complete; a fresh owner starts at the welcome stage after account creation.
- [ ] Run the focused tests and verify they pass.

### Task 2: Implement real encrypted local backup

**Files:**
- Create: `raiker/app/backup.py`
- Modify: `raiker/auth/app_key.py`
- Modify: `raiker/storage/migrations.py`
- Modify: `raiker/storage/sqlite.py`
- Modify: `raiker/api/routes_setup.py`
- Create: `tests/test_setup_backup.py`

- [ ] Add failing tests asserting a snapshot contains the encrypted database and required metadata, excludes raw provider secrets and application keys, round-trips into a disposable workspace, and does not update setup state when writing fails.
- [ ] Run `python -m pytest tests/test_setup_backup.py -q` and verify failure.
- [ ] Derive a backup-encryption key from a separate per-instance backup secret, store that secret with restrictive local permissions, and never serialize it into the backup archive.
- [ ] Create snapshots with a temporary name, fsync, verify manifest/checksum, then atomically rename. Encrypt catalog metadata that could reveal local paths.
- [ ] Add `POST /api/setup/backup/validate` and `POST /api/setup/backup/create` for local-folder targets. Reject cloud labels because no cloud backup connector exists.
- [ ] Mark `backup_status="verified"` and persist `backup_target` only after a successful create-and-verify cycle.
- [ ] Run the focused tests and verify they pass.

### Task 3: Build the first-run wizard UI

**Files:**
- Create: `apps/web/src/lib/views/SetupView.svelte`
- Create: `apps/web/src/lib/views/SetupView.test.ts`
- Modify: `apps/web/src/lib/views/ModelSetupView.svelte`
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/apiTypes.ts`
- Modify: `apps/web/src/App.svelte`
- Modify: `apps/web/src/lib/nav.ts`

- [ ] Add failing component tests for Welcome, Model, Privacy, Backup, and Finish; keyboard focus; error recovery; resume; and narrow/wide layouts. Assert skipping Backup explicitly records `skipped` and does not claim protection.
- [ ] Run `npm test -- --run src/lib/views/SetupView.test.ts` from `apps/web` and verify failure.
- [ ] Implement a five-stage wizard using existing Manrope/Source Serif/JetBrains fonts, spacing, buttons, cards, and status tokens. Use a compact horizontal progress bar on narrow screens and a left progress rail on wide screens.
- [ ] Reuse current provider/model controls and vault-backed API calls instead of duplicating credential storage. Show Local-first and Balanced privacy choices with exact behavioral summaries.
- [ ] Add a validated local folder field for browser/source installs. When the native host exposes a folder picker, use it; otherwise label the fallback honestly as a path field.
- [ ] Redirect incomplete authenticated owners to setup, allow later return from Settings, and prevent setup routes from appearing as ordinary workspace navigation.
- [ ] Run the component test, `npm run check`, and `npm run lint`; verify all pass.

### Task 4: Add scoped tray bootstrap authentication

**Files:**
- Create: `raiker/app/tray_auth.py`
- Create: `raiker/api/routes_tray.py`
- Modify: `raiker/api/auth.py`
- Modify: `raiker/storage/migrations.py`
- Modify: `raiker/storage/sqlite.py`
- Modify: `raiker/api/app.py`
- Create: `tests/test_tray_auth.py`
- Modify: `tests/test_api_host.py`

- [ ] Add failing tests for one-time exchange, expiry, replay rejection, host-control access, and denial on conversation, task, credential, approval, and file routes.

```python
token = exchange_tray_bootstrap(client, bootstrap_secret)
assert client.get("/api/host", headers=bearer(token)).status_code == 200
assert client.get("/api/sessions", headers=bearer(token)).status_code == 403
assert exchange_tray_bootstrap(client, bootstrap_secret).status_code == 401
```

- [ ] Run the focused tests and verify failure.
- [ ] Generate a 256-bit bootstrap secret in memory at desktop launch and deliver it to the tray over an inherited pipe or restrictive-permission temporary file, never a command-line argument.
- [ ] Store only a digest with expiry and used-at state. Add an exchange endpoint that returns a short-lived `host_control` session.
- [ ] Extend authentication scope checks so `host_control` can call only explicitly tagged host routes. Existing `control` and `elevated` scopes retain their behavior.
- [ ] Run `python -m pytest tests/test_tray_auth.py tests/test_api_host.py tests/test_routes_auth.py -q` and verify it passes.

### Task 5: Implement the native tray process

**Files:**
- Create: `raiker/app/tray.py`
- Modify: `apps/api/launcher.py`
- Modify: `pyproject.toml`
- Modify: `tests/test_app_lifecycle.py`
- Create: `tests/test_tray.py`

- [ ] Add failing unit tests for Running, Paused, and Degraded menus; Open Raiker; Pause/Resume; Restart; Quit; API-unreachable recovery; and icon disposal on host exit.
- [ ] Run `python -m pytest tests/test_tray.py tests/test_app_lifecycle.py -q` and verify failure.
- [ ] Add `pystray` and `Pillow` runtime dependencies and a `raiker-tray` entry point.
- [ ] Build menu labels from the existing `/api/host` view. Calls must use the scoped session and existing host routes; `Open Raiker` opens the loopback UI URL.
- [ ] Start the tray only in desktop mode, coordinate shutdown through the host lifecycle controller, and keep headless `raiker-web` free of GUI imports.
- [ ] Use the existing Raiker icon assets, with generated state overlays that remain legible in Windows light and dark trays.
- [ ] Run focused tests and verify they pass.

### Task 6: Package a self-contained Windows application

**Files:**
- Create: `scripts/build_desktop.py`
- Modify: `scripts/build_installer.py`
- Modify: `.github/workflows/release.yml`
- Modify: `pyproject.toml`
- Modify: `tests/test_release_pipeline.py`
- Modify: `docs/DESKTOP_DISTRIBUTION_DESIGN.md`

- [ ] Add failing release tests asserting Windows installer input contains a frozen executable, Python runtime, web assets, icon, license/notice, and tray dependencies; assert source-only payloads are rejected.
- [ ] Run `python -m pytest tests/test_release_pipeline.py -q` and verify failure.
- [ ] Add PyInstaller to release dependencies and implement a deterministic one-directory build for `raiker-app`, including `apps/web/dist` and package data.
- [ ] Change the WiX builder to install the frozen directory and create Start Menu/uninstall entries. Do not describe the result as self-contained until the frozen executable smoke test passes on a clean Windows runner.
- [ ] Update release workflow artifact names, checksums, SBOM inputs, and smoke tests. Launch the installed app, poll `/api/health`, exercise tray bootstrap, then shut it down.
- [ ] Run focused release tests, `python scripts/build_desktop.py --help`, and `python scripts/build_installer.py --help`; verify success.

### Task 7: Live wizard and tray acceptance

**Files:**
- Create: `apps/web/e2e/setup-tray-live.spec.ts`

- [ ] Add Playwright assertions for account-to-setup redirect, all five stages, provider credential entry through the UI, model selection, privacy choice, backup create/skip truthfulness, completion, and resume after browser reload.
- [ ] Launch the packaged desktop build, verify the native tray exists through the tray process integration probe, and use Playwright to verify its Open action reaches the authenticated UI.
- [ ] Capture screenshots at 1440×1000 and 390×844 for Welcome, Model, Privacy, Backup, Finish, and completed Settings state. Inspect every image for clipping, overflow, contrast, stale navigation labels, and secret exposure.
- [ ] Run `npm run test:e2e:live -- setup-tray-live.spec.ts` from `apps/web` and verify it passes.
