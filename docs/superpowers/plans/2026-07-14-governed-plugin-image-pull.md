# Governed Plugin Image Pull Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow an owner-approved, allowlisted Docker image to be pulled for the sandboxed plugin runtime without building, running, or importing plugin code.

**Architecture:** Add one Tier-4 capability and executor. The executor accepts one exact image reference, checks it is in the existing image allowlist and its parsed registry is in a new owner registry allowlist, then invokes only `docker pull <reference>` with bounded output. Docker’s daemon owns the actual network connection, so the code validates the registry name but does not claim to firewall daemon egress.

**Tech Stack:** Python 3.11, SQLite-backed governance, Docker CLI, pytest, Svelte/Vite.

## Global Constraints

- No image builds, Dockerfiles, archive extraction, dependency installation, image execution, or host-side plugin import.
- Empty image or registry allowlists deny by default.
- Use argv commands only; output and registry credentials never enter artifacts/events.
- The capability is gated, threat-model acknowledged, and approval-required through the existing authority path.
- Public image URLs receive a fixed deployment version query to invalidate stale browser cache.

---

### Task 1: Asset cache invalidation

**Files:**
- Modify: `apps/web/index.html`, `apps/web/src/lib/components/Logo.svelte`, `apps/web/src/lib/views/LoginView.svelte`

- [ ] **Step 1: Replace each public image/icon URL with the same versioned URL**

```text
/raiker-mark.png?v=20260714
/raiker-hero.png?v=20260714
/favicon-32x32.png?v=20260714
```

- [ ] **Step 2: Run the production build**

Run: `npm run build` from `apps/web`.
Expected: Vite completes successfully and copies public assets unchanged.

### Task 2: Write failing governed image-pull tests

**Files:**
- Create: `tests/test_phase_4_plugin_image_pull.py`

**Interfaces:**
- Produces expected capability name `plugin_sandbox_image_pull_cap` and executor class `PluginSandboxImagePullExecutor`.

- [ ] **Step 1: Add failing tests for registration, disabled gate, missing image/allowlists, rejected registry, hardened pull argv, Docker absence, and non-zero exit**

```python
result = authority.route_action(_action(principal.principal_id, image="registry.example/raiker:1"), principal)
assert result.error == "image_registry_not_allowed"
```

- [ ] **Step 2: Run the focused test file**

Run: `pytest tests/test_phase_4_plugin_image_pull.py -q`
Expected: FAIL because the capability and executor do not exist.

### Task 3: Implement the smallest governed executor

**Files:**
- Modify: `raiker/runtime/executors/tier4_plugins.py`
- Modify: `raiker/runtime/executors/__init__.py`
- Modify: `raiker/phase_gates.py`
- Modify: `raiker/runtime/authority/activation.py`
- Modify: `raiker/runtime/authority/router.py`
- Modify: `raiker/policy/config.py`
- Modify: `raiker/control/service.py`

**Interfaces:**
- Consumes: `container_image_allowlist()`, `run_command()`, `ExecutionResult`, and `GovernedAction`.
- Produces: `plugin_image_registry_allowlist()` and `PluginSandboxImagePullExecutor.execute()`.

- [ ] **Step 1: Parse and validate the exact registry host**

```python
def _image_registry(image: str) -> str:
    first = image.split("/", 1)[0]
    return first if "." in first or ":" in first or first == "localhost" else "docker.io"
```

- [ ] **Step 2: Fail closed before spawning unless the image and registry are owner-allowlisted**

```python
if image not in container_image_allowlist():
    return self._failed(action, "image_not_allowed")
if _image_registry(image) not in plugin_image_registry_allowlist():
    return self._failed(action, "image_registry_not_allowed")
```

- [ ] **Step 3: Pull with the sole permitted command and metadata-only artifacts**

```python
result = self._runner(["docker", "pull", image], timeout=300.0,
                      max_output_bytes=200_000, allowlist=frozenset({"docker"}), cwd=self._workspace_root)
```

- [ ] **Step 4: Register the capability everywhere the existing plugin runtime is registered**

Add `plugin_sandbox_image_pull_cap` to the Tier-4 gate, activation requirements, router map, default policy approvals, dangerous-cap set, real executor set, and registry.

- [ ] **Step 5: Run the focused test file**

Run: `pytest tests/test_phase_4_plugin_image_pull.py -q`
Expected: PASS.

### Task 4: Document the boundary and verify

**Files:**
- Create: `docs/threat-models/plugin-sandbox-image-pull.md`
- Modify: `docs/IMPLEMENTATION_STATUS.md`
- Modify: `docs/RUNTIME_EXECUTORS_SPEC.md`
- Modify: `docs/HANDOFF.md`

- [ ] **Step 1: State the daemon-egress limitation and non-goals**

Document that Docker daemon registry routing/mirrors must be constrained by operator configuration; the executor enforces only exact reference and registry-name policy.

- [ ] **Step 2: Run relevant regression checks**

Run: `pytest tests/test_phase_4_plugin_image_pull.py tests/test_phase_4_plugin_sandboxed_runtime.py tests/test_executor_default_registry.py -q`, `ruff check raiker tests`, and from `apps/web`: `npm run check`, `npm run lint`, `npm test -- --run`, `npm run build`.

- [ ] **Step 3: Commit and push `main`**

Run: `git add` for the changed files, `git commit -m "feat: govern plugin sandbox image pulls"`, then `git push origin main`.
