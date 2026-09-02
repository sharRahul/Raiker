# Settings Signed Update and Restart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Add a Settings software-updates page that checks the pinned signed GitHub release channel on owner request and, for a supported packaged installation, applies a verified update using an external helper before safely restarting Raiker.

**Architecture:** Preserve the existing signed-channel/update verifier as the only download/apply authority. Add a one-time, authenticated update handoff plan that the host validates and passes to a short-lived external `raiker-app` helper. The helper waits for the host to exit at a safe boundary, re-verifies release metadata/artifact, creates the existing recovery point and atomic swap, then restarts only through the registered lifecycle/service mechanism. Source checkouts, unsigned installations, unpinned channels, or non-restartable hosts remain explicitly unavailable.

**Tech Stack:** Python 3.12, FastAPI, existing `raiker.app.installation` / `updater` / `update` / service lifecycle modules, Svelte 5, pytest, Vitest.

## Global Constraints

- Never use `git pull`, `git checkout`, a source archive, or an arbitrary URL as an update mechanism.
- A Settings read is local-only; an update check is explicit and reaches only the pinned HTTPS signed channel.
- The running web-server process must not replace its own installation tree. The helper must be independently runnable after the host exits.
- Verify signatures and bounded artifact constraints again in the helper immediately before apply. A route's prior successful check is not authorization to skip verification.
- No automatic update/restart. The owner confirms version, channel/provenance, work interruption risk, and recovery behavior.
- Do not offer “Update and restart” for a source checkout, unsigned build, missing channel, no available release, running work without a second confirmation, or a host that cannot be restarted by a known registered lifecycle owner.

---

### Task 1: Define an authenticated one-time update handoff contract

**Files:**
- Create: `raiker/app/update_handoff.py`
- Modify: `raiker/app/installation.py`
- Modify: `raiker/api/routes_updates.py`
- Modify: `raiker/api/schemas.py`
- Test: `tests/test_update_handoff.py`
- Test: `tests/test_api_updates.py`

1. Write failing tests for a handoff request from source checkout, unsigned build, unpinned channel, stale/no offered release, non-restartable host, and an authenticated viable signed package. Assert status reads/checks still make no unexpected outbound request.
2. Define a minimal handoff record stored under the existing workspace state root: random one-time id, principal id, target version, pinned-channel fingerprint, creation/expiry time, expected install root, and restart lifecycle descriptor. Do not store release URLs, private keys, bearer tokens, or browser/session credentials.
3. Protect the record against tampering using an installation/workspace-local secret independent of HTTP request data; consume it atomically before applying so replay is rejected.
4. Add `POST /api/host/update/apply` returning an honest status DTO: `queued`, `not_supported`, `confirmation_required`, or a stable refusal reason. It validates current update status, checks work-in-flight through `HostControl`, creates the one-time handoff, and starts only the fixed known helper command.
5. Add explicit confirmation semantics: first request with waiting work returns affected work; only `confirm_interrupt=true` may queue the handoff.
6. Run `pytest tests/test_update_handoff.py tests/test_api_updates.py -q`.
7. Commit: `git add raiker/app/update_handoff.py raiker/app/installation.py raiker/api/routes_updates.py raiker/api/schemas.py tests/test_update_handoff.py tests/test_api_updates.py && git commit -m "Add verified update handoff contract"`.

### Task 2: Implement the external apply-and-restart helper

**Files:**
- Modify: `apps/api/launcher.py`
- Modify: `raiker/app/updater.py`
- Modify: `raiker/app/update.py`
- Modify: `raiker/app/service.py`
- Test: `tests/test_update_handoff.py`
- Test: `tests/test_signed_updates.py`
- Test: `tests/test_installation_provenance.py`

1. Write failing helper tests that it consumes a valid handoff once; waits for the specific host PID to exit; rechecks channel metadata/signature/version; invokes the existing bounded download/atomic apply; retains recovery state; and restarts through the recorded registered service lifecycle.
2. Extend `raiker-app update` with a private, fixed-shape `--handoff <id>` path. It must resolve the workspace, validate/consume the record, and never accept arbitrary shell commands, paths, URLs, or restart arguments from the HTTP route.
3. Launch this helper detached from the host with inherited output redirected to a bounded workspace update log. On Windows, use the documented process flags appropriate for no visible helper console. Do not use `shell=True`.
4. Request the host to stop at its normal safe boundary only after the helper is successfully launched. The helper has a bounded wait; on timeout it records failure and leaves the current installation unchanged.
5. Reuse `check_for_update` and `download_and_apply` so metadata/artifact verification, size bounds, staging, atomic replacement, and recovery point behavior remain single-sourced. Enhance their interfaces only when necessary to expose structured helper outcome data.
6. Restart only through an installed registered service/lifecycle plan. If the service restart fails, retain the recovery point and record a recoverable failure with the exact command-free remediation.
7. Ensure rollback continues to work and adds a test that a failed verification/apply leaves the old installation runnable.
8. Run `pytest tests/test_update_handoff.py tests/test_signed_updates.py tests/test_installation_provenance.py -q`.
9. Commit: `git add apps/api/launcher.py raiker/app/updater.py raiker/app/update.py raiker/app/service.py tests/test_update_handoff.py tests/test_signed_updates.py tests/test_installation_provenance.py && git commit -m "Apply signed updates through external restart helper"`.

### Task 3: Add Settings → Software updates UI

**Files:**
- Create: `apps/web/src/lib/views/settings/SoftwareUpdates.svelte`
- Modify: `apps/web/src/lib/views/SettingsView.svelte`
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/apiTypes.ts`
- Test: `apps/web/src/lib/views/settings/SoftwareUpdates.test.ts`
- Test: `apps/web/src/lib/views/SettingsView.test.ts`

1. Write component tests for: source checkout (unavailable and no apply button); signed unpinned installation; explicit check button; available version/channel/provenance; recovery-point display; non-restartable host; idle confirmation; waiting-work second confirmation; and queued-update reconnect wording.
2. Add typed API calls for local status, explicit check, and apply handoff. Do not call the update check during Settings mount.
3. Render the new System section named “Software updates.” It should explain the current installation provenance, pinned channel/fingerprint, last explicit check, offered version, recovery points, and why an unavailable state cannot apply updates.
4. Make “Check for updates” the only egress action. On an available, restartable signed build, show “Update and restart” plus a confirmation dialog naming the version, channel, recovery point expectation, and any interrupted work.
5. After a queued handoff, disable controls and explain that Raiker will briefly disconnect while the verified external helper applies the update and restarts the registered service. Do not report success until the reloaded UI obtains a new status/version.
6. Keep `HostControl` as a compact status surface; replace its manual CLI-only advice with a link to `#/settings?tab=software-updates` when updates are applicable.
7. Run `npm test -- --run src/lib/views/settings/SoftwareUpdates.test.ts src/lib/views/SettingsView.test.ts src/lib/components/HostControl.test.ts` from `apps/web`.
8. Commit: `git add apps/web/src/lib/views/settings/SoftwareUpdates.svelte apps/web/src/lib/views/SettingsView.svelte apps/web/src/lib/api.ts apps/web/src/lib/apiTypes.ts apps/web/src/lib/views/settings/SoftwareUpdates.test.ts apps/web/src/lib/views/SettingsView.test.ts apps/web/src/lib/components/HostControl.svelte apps/web/src/lib/components/HostControl.test.ts && git commit -m "Add Settings software update controls"`.

### Task 4: Verify real lifecycle safety and release-state regressions

**Files:**
- Test: `tests/test_api_updates.py`
- Test: `tests/test_update_handoff.py`
- Test: `tests/test_signed_updates.py`
- Test: `apps/web/src/lib/views/settings/SoftwareUpdates.test.ts`

1. Run `pytest tests/test_api_updates.py tests/test_update_handoff.py tests/test_signed_updates.py tests/test_installation_provenance.py -q`.
2. Run `npm test -- --run src/lib/views/settings/SoftwareUpdates.test.ts src/lib/views/SettingsView.test.ts src/lib/components/HostControl.test.ts` from `apps/web`.
3. In an isolated signed-package fixture, verify one successful update handoff: request confirmation, stop host, helper re-verifies/applies, service restarts, API reports the new version, and the old version appears as a recovery point.
4. In this source checkout, manually verify the UI states “source checkout” and offers no network/apply path.
5. Commit any verification-only corrections as `git commit -m "Verify signed update restart lifecycle"`.

## Plan Review

- [ ] Source checkouts and unsigned packages cannot update themselves through Settings.
- [ ] Every package update is pinned-channel verified twice and has a recovery point before replacement.
- [ ] The HTTP server never overwrites its own running tree.
- [ ] Restart is limited to an existing registered lifecycle mechanism and in-flight work requires a second owner confirmation.
