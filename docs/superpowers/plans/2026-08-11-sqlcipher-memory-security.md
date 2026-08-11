# SQLCipher Memory Security Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable SQLCipher key-bearing page locking only after a sacrificial child process proves the host can do it, with truthful health and Settings UI state.

**Architecture:** A small worker opens a disposable encrypted database and enables `cipher_memory_security`; a parent probe interprets exit status, timeout, and Windows crash codes. `SQLiteStore` resolves `auto`, `on`, or `off` before opening production databases and never retries unsafe memory locking in-process after a failed probe.

**Tech Stack:** Python, sqlcipher3-wheels, subprocess, FastAPI health models, Svelte Settings UI, pytest, Vitest.

## Global Constraints

- The probe must use a fresh random key and temporary database, never the Raiker application key or production path.
- Probe stdout and stderr must not contain keys; return only structured reason codes.
- A crash, timeout, missing SQLCipher, privilege failure, or unknown result resolves to disabled.

---

### Task 1: Specify child-process outcomes

**Files:**
- Create: `raiker/storage/sqlcipher_probe.py`
- Create: `raiker/storage/sqlcipher_probe_worker.py`
- Modify: `tests/test_sqlcipher_memory_security.py`

- [ ] Add failing tests that patch `subprocess.run` and assert the parent maps zero exit to `supported`, timeout to `probe_timeout`, Windows stack overflow `0xC00000FD` to `host_crash`, and every other nonzero exit to `probe_failed`.

```python
def test_probe_maps_windows_stack_overflow(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: CompletedProcess(a, -1073741571))
    result = probe_memory_security(tmp_path)
    assert result.supported is False
    assert result.reason_code == "host_crash"
```

- [ ] Run `python -m pytest tests/test_sqlcipher_memory_security.py -q` and verify the new tests fail because the probe module does not exist.
- [ ] Implement an immutable `MemorySecurityProbeResult(supported, reason_code, sqlcipher_version, checked_at)` and `probe_memory_security(workspace_root, timeout_seconds=10.0)` that launches `sys.executable -m raiker.storage.sqlcipher_probe_worker`, passes a random key over stdin, uses a disposable directory, captures output, and returns fail-closed reason codes.
- [ ] Implement the worker so it opens a disposable SQLCipher database, issues the key pragma, enables `cipher_memory_security`, creates and reads one row, prints a credential-free JSON success record, closes the connection, and exits.
- [ ] Run the focused pytest command and verify it passes.

### Task 2: Resolve `auto`, `on`, and `off` before opening keyed pages

**Files:**
- Modify: `raiker/storage/sqlite.py`
- Modify: `tests/test_sqlcipher_memory_security.py`

- [ ] Add failing tests for unset/`auto`, explicit `off`, explicit `on` with successful probe, and explicit `on` with failed probe. Assert the production connection never executes the ON pragma after a failed result.

```python
@pytest.mark.parametrize("value", [None, "", "auto"])
def test_auto_uses_cached_probe(value, monkeypatch, tmp_path):
    monkeypatch.setattr(sqlite, "probe_memory_security", lambda root: supported_probe())
    assert sqlite.resolve_memory_security(tmp_path, configured=value).enabled is True
```

- [ ] Run the focused test and verify the new assertions fail against the tuple-returning resolver.
- [ ] Replace the tuple cache with a process-local posture object containing `configured_mode`, `effective`, `reason_code`, `probe_status`, `sqlcipher_version`, and `checked_at`. Cache by resolved workspace and configured mode.
- [ ] Make `_open_keyed()` apply the effective pragma immediately after the key pragma and before any production query. Explicit `off` bypasses probing; explicit `on` still requires a successful probe and reports `required_but_unavailable` instead of risking the resident process.
- [ ] Remove the in-process reopen-on-memory-error path and retain one deterministic open attempt.
- [ ] Run `python -m pytest tests/test_sqlcipher_memory_security.py -q` and verify it passes.

### Task 3: Expose truthful health and Settings controls

**Files:**
- Modify: `raiker/api/routes_control.py`
- Modify: `apps/web/src/lib/apiTypes.ts`
- Modify: `apps/web/src/lib/views/settings/SecurityLogin.svelte`
- Modify: `apps/web/src/lib/views/settings/SecurityLogin.test.ts`
- Modify: `tests/test_sqlcipher_memory_security.py`

- [ ] Add API tests asserting `/api/health` or the existing store-health payload exposes configured mode, effective state, probe status, and a human-safe reason code without environment values or probe stderr.
- [ ] Add a component test for Supported, Disabled by user, and Unavailable on this host cards.
- [ ] Run the focused Python and web tests and verify the new assertions fail.
- [ ] Extend the existing health response and TypeScript types with the posture fields.
- [ ] Add a compact security card using existing Settings typography, spacing, and status tokens. Explain that Raiker remains encrypted at rest when page locking is unavailable, and show the configuration source without rendering secrets.
- [ ] Run `python -m pytest tests/test_sqlcipher_memory_security.py -q` and `npm test -- --run src/lib/views/settings/SecurityLogin.test.ts` from `apps/web`; verify both pass.

### Task 4: Validate the Windows failure mode safely

**Files:**
- Modify: `tests/test_sqlcipher_memory_security.py`

- [ ] Run only the parent probe in an isolated Python process and record the reason code; do not enable the pragma in the server process.
- [ ] Start Raiker with the resulting automatic posture and verify a normal encrypted store read/write succeeds.
- [ ] Run `python -m pytest tests/test_sqlcipher_memory_security.py tests/test_api_core.py -q` and verify it passes.
- [ ] Run `python -m ruff check raiker/storage/sqlcipher_probe.py raiker/storage/sqlcipher_probe_worker.py raiker/storage/sqlite.py tests/test_sqlcipher_memory_security.py` and verify it passes.
