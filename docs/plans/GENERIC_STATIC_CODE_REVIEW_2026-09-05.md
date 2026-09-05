# Raiker Generic Static Code Review — 2026-09-05

## Review target

This review examines the code on `main` at commit `cf3007c5f2c0a7c54f740a85c9db67ffda7c3e7a`.

It is intentionally separate from the security/compliance assessment and the security-specific code review. This document focuses on generic software-engineering quality: correctness, reliability, lifecycle/resource management, concurrency, architecture, maintainability, performance, API consistency, test coverage and release/build engineering.

This is a static review, not a claim that every line in the repository was manually inspected and not a runtime/profiling exercise. Findings below are limited to issues supported by concrete implementation evidence in the reviewed `main` tree.

## Severity / priority

- **High** — likely functional failure, cross-instance corruption/race, significant resource/lifecycle defect, or major correctness inconsistency.
- **Medium** — material maintainability/performance/reliability issue or behavior likely to drift/fail under scale or uncommon conditions.
- **Low** — cleanup/API quality/diagnostic issue that should be fixed but is unlikely to cause immediate failure.

Priority:

- **P0** — release-blocking correctness/data-integrity issue.
- **P1** — should be addressed in the next engineering cycle.
- **P2** — important hardening/refactor/test work.
- **P3** — cleanup/maturity.

---

# Executive assessment

Raiker has unusually strong explanatory comments, extensive tests, explicit fail-closed paths, typed domain contracts and a clear attempt to centralize governance. The generic engineering risk is now mostly **complexity concentration and lifecycle inconsistency** rather than lack of structure.

The largest issues found are:

1. multiple `ModelRouter` code paths construct providers differently, causing configuration inconsistency and leaked clients;
2. multi-instance execution shares module-global command workspace state;
3. mounted Raiker instances are built as FastAPI sub-applications with their own lifespan workers, but mounted sub-app lifespans do not run under FastAPI;
4. instance creation is non-transactional and mutates the live route table from a synchronous worker thread;
5. `SQLiteStore` performs bootstrap/migration work in every constructor while hot request paths repeatedly construct stores;
6. prompt submit and prompt streaming have duplicated orchestration with differing error semantics;
7. frontend CI is path-filtered so backend API contract changes can bypass frontend type/build/E2E checks.

## Finding summary

| ID | Severity | Priority | Finding |
|---|---|---:|---|
| GCR-01 | High | P1 | `ModelRouter.launch()` ignores the configured connection resolver |
| GCR-02 | High | P1 | `ModelRouter.select_profile()` and `launch()` can leak provider HTTP clients |
| GCR-03 | Medium/High | P1 | `ModelRouter.set_reasoning()` validates against the first registry profile rather than the active/default runtime profile |
| GCR-04 | Medium | P2 | `ModelRouter.generate()` accepts `context` but ignores it |
| GCR-05 | Medium | P1 | `run_coro()` blocks an already-running event loop and creates a thread pool per call |
| GCR-06 | High | P0/P1 | Module-global command workspace creates a cross-instance/concurrency race |
| GCR-07 | High | P1 | Mounted Raiker instances do not receive their own FastAPI lifespan workers |
| GCR-08 | High | P1 | Instance creation can leave a partially created/mounted instance when account registration fails |
| GCR-09 | High | P1 | Instance registry/routing mutation is non-atomic and performed from a sync route worker thread |
| GCR-10 | Medium/High | P1 | `SQLiteStore` bootstraps on every construction; hot paths construct several stores per request |
| GCR-11 | Medium | P2 | `sqlite.py` has become a large persistence/migration god module |
| GCR-12 | Medium | P2 | Prompt submit and stream paths duplicate orchestration and already expose different error semantics |
| GCR-13 | Medium | P2 | API redaction middleware buffers almost every JSON API response in full |
| GCR-14 | Medium | P2 | Provider calls do not reuse an app/router-scoped HTTP client/connection pool |
| GCR-15 | Medium | P2 | Frontend CI does not run for backend/API contract-only changes |
| GCR-16 | Low/Medium | P2 | Version metadata is split between hard-coded `0.0.0`, FastAPI `0.1.0`, and release input versions |
| GCR-17 | Low | P3 | Model registry lookup normalization differs between `resolve`, `profiles_for_provider`, and `find` |
| GCR-18 | Low | P3 | Public method parameters exist that are unused (`health_timeout`, `context`) and weaken API clarity |

---

# Detailed findings

## GCR-01 — `ModelRouter.launch()` ignores saved connection configuration

**Severity: High — Priority: P1 — Confidence: High**

### Evidence

Normal provider creation goes through `ModelRouter._factory(profile)`, which resolves the owner-configured connection with `connection_resolver(profile.profile_id)` and passes it to `ModelProviderFactory`.

`ModelRouter.launch()` instead calls:

```python
ModelProviderFactory(policy=self.runtime_policy).create(profile)
```

That path does **not** pass the resolved connection.

### Impact

A profile whose endpoint/API key/workspace configuration is stored in Raiker's connection store may work through `achat`, `astream`, `aembed`, etc. but fail the `launch()` validation path as if it were unconfigured. This creates two answers to the same question: “can this profile run?”

### Recommendation

Make all provider construction/validation go through one method. Prefer a validation method that does not allocate transport resources:

```text
resolve profile -> resolve connection -> validate policy/config -> construct provider only when executing
```

### Acceptance tests

- saved connection only, no matching environment variables;
- `launch()` and `achat()` must agree on whether the provider is configured;
- endpoint/key/workspace-id overrides must resolve identically in every router method.

---

## GCR-02 — provider objects/HTTP clients can leak in `select_profile()` and `launch()`

**Severity: High — Priority: P1 — Confidence: High**

### Evidence

`AsyncOpenAICompatibleProvider.__post_init__()` creates an `httpx.AsyncClient` when no client is supplied and marks itself as the owner. Most async router methods correctly close providers in `finally` blocks.

However:

- `ModelRouter.select_profile()` calls `self._factory(profile).create(profile)` only for validation and discards the returned provider without closing it;
- `ModelRouter.launch()` also constructs a provider and discards it without closing it.

### Impact

Repeated profile selection/launch validation can leave unclosed `httpx.AsyncClient` instances and associated connection-pool resources. At minimum this can cause warnings and resource accumulation; at scale it can consume sockets/file descriptors.

### Recommendation

Do not instantiate a live transport merely to validate configuration. Split `ModelProviderFactory.create()` into:

- `validate(profile, connection, policy)` — pure/no transport;
- `create(...)` — constructs the provider only when needed.

If construction remains necessary, make those router methods async and close the provider deterministically.

---

## GCR-03 — reasoning settings can be validated against the wrong model profile

**Severity: Medium/High — Priority: P1 — Confidence: High**

### Evidence

`ModelRouter.set_reasoning()` chooses:

```python
self.registry.resolve_profile_id(self.active_profile_id)
if self.active_profile_id
else self.registry.list_profiles()[0]
```

`active_profile_id` is only set by `select_profile()`. Elsewhere, Raiker resolves a default/current provider from persisted owner selection without necessarily calling `select_profile()`.

The first built-in registry profile is currently the first local llama.cpp profile, not a general representation of the owner's selected/default provider.

### Impact

If the actual selected/default model supports reasoning but the first registry profile does not, `set_reasoning()` can reject a valid setting. The reverse can also happen if registry ordering changes.

### Recommendation

Track the resolved active profile explicitly or resolve the current provider/model through the same persisted-selection path used for turn execution. Never use registry position as runtime state.

---

## GCR-04 — `generate(..., context=...)` ignores `context`

**Severity: Medium — Priority: P2 — Confidence: High**

`ModelRouter.generate(provider, model, prompt, context=None)` accepts a `context` parameter but calls `chat()` with only a single user message containing `prompt`.

### Impact

Callers can reasonably believe supplied context influences generation when it is silently ignored. This is an API-contract correctness problem even if current callers do not rely on it.

### Recommendation

Either remove the parameter or define exactly how context is serialized into `ModelMessage` objects and test it.

---

## GCR-05 — synchronous async bridge blocks the active event loop

**Severity: Medium — Priority: P1 — Confidence: High**

### Evidence

`raiker/runtime/async_bridge.py::run_coro()` does this when called from a thread that already owns a running event loop:

```python
with ThreadPoolExecutor(max_workers=1) as pool:
    return pool.submit(asyncio.run, coro).result()
```

The coroutine runs on another thread, but `.result()` synchronously blocks the caller — including the event-loop thread — until completion. It also constructs/destroys a new thread pool for every call.

### Impact

If used from FastAPI/ASGI async execution, long provider or I/O operations can stall unrelated requests on that event loop. Repeated calls also pay thread creation overhead.

### Recommendation

Prefer async all the way through web paths. Keep a synchronous bridge only at true sync boundaries (CLI/process entry points). Where a sync interface is unavoidable, use an app-owned worker/executor rather than a per-call `ThreadPoolExecutor`.

---

## GCR-06 — module-global command workspace races across workspaces/instances

**Severity: High — Priority: P0/P1 — Confidence: High**

### Evidence

`raiker/runtime/executors/sandbox.py` stores command validation scope in module-global state:

```python
_COMMAND_WORKSPACE: Path | None = None
```

`run_command()` calls `set_command_workspace(cwd)` and then `check_command_allowlist()`, which reads `_command_workspace()`.

Raiker supports multiple mounted instances/workspaces inside one process. Concurrent command execution can therefore overwrite this global between calls.

### Impact

Command A for workspace A and command B for workspace B can validate path arguments against the wrong workspace root under concurrency. Even without exploitation, this can produce nondeterministic false accepts/false rejects.

### Recommendation

Delete `_COMMAND_WORKSPACE`. Pass `workspace_root` explicitly through `check_command_allowlist()` into `validate_command()`. Security/correctness scope must be request/execution-local, never process-global.

### Acceptance test

Run two command validations concurrently against different temporary workspaces with barriers that force interleaving. Each must always use its own root across thousands of iterations.

---

## GCR-07 — mounted instances do not receive their `create_app()` lifespan workers

**Severity: High — Priority: P1 — Confidence: High**

### Evidence

`_mount_instance()` creates another full `FastAPI` application with `create_app(...)` and mounts it beneath `/instances/<name>`.

Every `create_app()` defines a lifespan that starts:

- task scheduler tick worker;
- explicit-continuation worker;
- attached-root watcher;
- runtime shutdown/connection cleanup.

FastAPI's documented behavior is that lifespan startup/shutdown is executed for the main application, **not mounted sub-applications**.

### Impact

Mounted instances can serve request routes but their own scheduled work, approval continuation wakeups, model-capacity refresh, telemetry cadence and attached-root watching may never start. Their lifespan cleanup also does not run as designed.

### Recommendation

Do not rely on mounted sub-app lifespan for per-instance background services. Introduce an application-level instance runtime manager that starts/stops workers explicitly for every registered workspace, or use routing that shares the parent lifespan manager.

### Acceptance tests

Create a secondary instance under a live host and prove its scheduler/watcher executes independently without manually invoking its lifespan.

---

## GCR-08 — instance creation is not transactional

**Severity: High — Priority: P1 — Confidence: High**

### Evidence

`routes_instances.create_instance()` first calls `create_and_mount_instance()` and only afterwards attempts:

```python
AccountService(workspace).register(...)
```

If account registration raises `AuthError`, the route returns HTTP 422 but there is no rollback of:

- the created workspace directory;
- the instance registry entry;
- the already-mounted route/sub-app.

### Impact

The API reports failure but leaves a real partially created instance. A retry with the same name can then return `instance_already_exists`, forcing manual cleanup and creating state that contradicts the original response.

### Recommendation

Treat instance creation as a transaction/staged operation:

1. validate account inputs/password policy before committing instance state;
2. create into a temporary/staging directory;
3. bootstrap/register account;
4. atomically publish registry entry;
5. mount/activate only after success;
6. rollback all filesystem/registry state on failure.

---

## GCR-09 — live instance registry and route-table mutation are race-prone

**Severity: High — Priority: P1 — Confidence: High**

### Evidence

`create_and_mount_instance()` performs a read-modify-write on `instances.json`:

```text
read names -> append name -> write_text(json.dumps(names))
```

with no lock and no atomic replacement.

It then mutates `app.router.routes` by inserting a new `Mount` at runtime.

The `/api/instances` handler is declared with normal `def`, so FastAPI executes it through a worker thread. The route table can therefore be mutated from a worker thread while the main event loop is routing requests.

### Impact

- two concurrent creates can lose one registry update;
- a crash during direct `write_text` can leave invalid/truncated JSON;
- runtime route-list mutation can race with request routing;
- duplicate or partially initialized mounts can be exposed.

### Recommendation

Use a single async/application-owned instance manager with a lock. Persist registry through temp-file + `fsync` + atomic replace (or store it transactionally in SQLite), and perform routing/mount activation on the application event-loop/control path only.

---

## GCR-10 — `SQLiteStore` bootstraps on every object construction

**Severity: Medium/High — Priority: P1 — Confidence: High**

### Evidence

`SQLiteStore.__init__()` always executes:

```python
with _BOOTSTRAP_LOCK:
    self.bootstrap()
```

`bootstrap()` walks the full migration/bootstrap sequence.

Hot API paths repeatedly construct independent `SQLiteStore` objects. For example, prompt submission constructs stores in readiness checking, project/session checks, attachment bookkeeping and then again inside `AgentGateway`. `AgentGateway` itself constructs a store and performs registry upserts.

### Impact

Even if migrations are idempotent, every short-lived store object pays bootstrap checks and obtains a process-global bootstrap lock. This can serialize unrelated requests/workspaces and adds avoidable DB work to prompt latency.

### Recommendation

- bootstrap each workspace once at application/instance startup;
- make `SQLiteStore` construction cheap;
- inject/app-scope a store/repository provider into request services;
- retain explicit `ensure_bootstrapped()` for standalone CLI/test entry points;
- profile prompt latency before/after.

---

## GCR-11 — `sqlite.py` is now an architectural god module

**Severity: Medium — Priority: P2 — Confidence: High**

### Evidence

`raiker/storage/sqlite.py` imports a very large number of migration IDs/SQL blocks and domain models, owns connection caching, SQLCipher posture, bootstrap/migration orchestration, health reporting and a broad persistence API for many unrelated domains.

### Impact

This increases:

- merge-conflict probability;
- import/coupling cost;
- difficulty reasoning about transaction boundaries;
- risk of unrelated storage changes affecting each other;
- test setup cost;
- resistance to alternative storage/repository implementations.

### Recommendation

Keep one low-level encrypted connection manager, but split domain repositories and migration registration:

```text
storage/
  database.py
  migration_runner.py
  repositories/
    approvals.py
    sessions.py
    models.py
    memory.py
    tasks.py
    plugins.py
    ...
```

Prefer an ordered migration registry/table rather than one hand-maintained mega-bootstrap method.

---

## GCR-12 — prompt submit and stream orchestration are duplicated and semantically different

**Severity: Medium — Priority: P2 — Confidence: High**

### Evidence

`submit_prompt()` and `stream_prompt()` independently implement the same sequence:

- session ownership check;
- project resolution;
- envelope build;
- session/project binding;
- model readiness;
- attachment refs;
- `AgentGateway` construction;
- generated-file recording.

They already differ in error behavior:

- contract validation in non-streaming returns an `AgentResponse` dict from a normal response;
- streaming emits a final SSE event;
- readiness in non-streaming raises HTTP 409;
- streaming returns a successful `StreamingResponse` whose stream contains a failure event.

### Impact

The paths can drift further as new preconditions are added. Clients also have to understand materially different HTTP/error semantics for the same logical operation.

### Recommendation

Extract one shared `prepare_prompt_turn()` result and one error contract. Let HTTP JSON vs SSE be presentation adapters over the same preparation/outcome model.

---

## GCR-13 — redaction middleware buffers almost all JSON API responses

**Severity: Medium — Priority: P2 — Confidence: High**

### Evidence

`RedactionMiddleware` captures `http.response.start`, accumulates every `http.response.body` chunk into a `bytearray`, and only emits after `more_body=False`. Streaming endpoints require explicit exemption.

### Impact

- response latency increases because first bytes cannot leave until the full response exists;
- memory usage duplicates response bodies during serialization/redaction;
- any newly introduced streaming/SSE/download API silently stops streaming unless manually added to exemptions;
- middleware behavior grows as a path-based exception list.

### Recommendation

Prefer redaction at serialization/domain boundaries for structured API models. If middleware remains, restrict it to explicitly structured small JSON routes or enforce a bounded response size and explicit streaming response type detection.

---

## GCR-14 — provider calls discard HTTP connection pooling between operations/turns

**Severity: Medium — Priority: P2 — Confidence: High**

### Evidence

`ModelRouter._factory()` does not supply a shared `httpx.AsyncClient`. Provider construction therefore creates a new client, and normal router methods close it after each operation.

### Impact

Every chat/list-models/health/embed operation can pay fresh connection/TLS pool setup instead of reusing keep-alive connections. This is particularly costly for hosted providers and repeated readiness/model-list probes.

### Recommendation

Own one or more provider HTTP clients at the application/instance lifecycle and inject them into `ModelProviderFactory`. Close them in the main instance runtime manager at shutdown.

This should be addressed together with GCR-02 so client ownership is unambiguous.

---

## GCR-15 — backend contract changes can bypass frontend CI

**Severity: Medium — Priority: P2 — Confidence: High**

### Evidence

`.github/workflows/web.yml` runs lint/type-check/unit/build/mocked Playwright only when changed paths match:

- `apps/web/**`
- `.github/workflows/web.yml`

Changes under `raiker/api/**`, API schemas/contracts, response models or backend route behavior do not trigger this workflow unless a web file also changes.

The main Python CI does not run the frontend build/type/E2E suite.

### Impact

A backend-only PR can merge an API shape/behavior change that compiles and passes Python tests while breaking the checked-in frontend client at runtime.

### Recommendation

Trigger web contract checks for backend contract surfaces, at minimum:

- `raiker/api/**`
- shared contracts/schemas consumed by web;
- generated/openapi contract artifacts if introduced.

Better: add a small always-on contract job that generates/validates the OpenAPI/client boundary, leaving expensive Playwright runs path-filtered if necessary.

---

## GCR-16 — version metadata is split across unrelated constants

**Severity: Low/Medium — Priority: P2 — Confidence: High**

### Evidence

Current sources contain several independent versions:

- Python project version: `0.0.0` in `pyproject.toml`;
- web package version: `0.0.0`;
- REST/web `ClientMetadata.version`: `0.0.0`;
- FastAPI application version: `0.1.0`;
- release workflow accepts an externally supplied `X.Y.Z` and writes it into installation provenance.

### Impact

Package metadata, API diagnostics/audit events and installed-release provenance can report different versions for the same build. This makes bug reports, compatibility checks and telemetry harder to correlate.

### Recommendation

Define one build-version source. Generate Python package metadata, web build constant, API client metadata, FastAPI version and installation record from it during build/release. Development builds can use `0.0.0+<git-sha>` or another explicit dev identifier.

---

## GCR-17 — model-provider normalization differs between registry methods

**Severity: Low — Priority: P3 — Confidence: High**

### Evidence

`ModelProfileRegistry.resolve()` and `profiles_for_provider()` map the alias `llama-cpp` to canonical `llama.cpp`.

`ModelProfileRegistry.find()` only replaces `_` with `-` and does not apply the same alias mapping.

### Impact

The same provider spelling can resolve successfully through one registry method and return no result through another.

### Recommendation

Create one `_normalize_provider()` function and use it in every registry lookup.

---

## GCR-18 — stale/unused public method parameters reduce contract clarity

**Severity: Low — Priority: P3 — Confidence: High**

Examples:

- `ModelRouter.default_provider(*, health_timeout=1.0)` never reads `health_timeout`;
- `ModelRouter.generate(..., context=None)` never reads `context`.

These are small individually but indicate API surfaces retaining historical intent after implementation changed.

### Recommendation

Enable/extend linting for unused arguments where practical, remove stale parameters, or implement/document the intended behavior.

---

# Positive engineering observations

The review also found practices worth preserving:

- provider methods generally use `try/finally` to close owned provider clients;
- FastAPI routes use typed request schemas and explicit domain error translation;
- `SQLiteStore` has deliberate connection caching, dead-thread eviction and shutdown cleanup rather than opening a new SQLCipher handle for every statement;
- model registry loading validates required fields and endpoint policy before constructing profiles;
- prompt paths perform explicit session ownership and project-scope checks;
- Python CI runs tests, Ruff, mypy and compile checks; native Rust runs fmt, Clippy, tests and builds on Linux and Windows;
- web CI runs lint, Svelte type checking, unit tests, build and mocked Playwright;
- comments frequently explain *why* a non-obvious decision exists, not merely what a line does.

---

# Recommended remediation order

Following the existing priority/effort rule:

| Order | Finding | Priority | Effort | Recommendation |
|---:|---|---:|---|---|
| 1 | GCR-01 launch connection mismatch | P1 | Low | Route launch validation through `_factory(profile)`/pure validator |
| 2 | GCR-02 provider client leak | P1 | Low-Medium | Pure validation or deterministic close |
| 3 | GCR-03 reasoning-profile mismatch | P1 | Low-Medium | Resolve actual active/default profile |
| 4 | GCR-08 partial instance creation | P1 | Medium | Stage + rollback instance creation |
| 5 | GCR-06 global command workspace | P0/P1 | Medium | Pass workspace explicitly; add concurrency test |
| 6 | GCR-07 sub-app lifespan gap | P1 | Medium | Parent-owned instance runtime manager |
| 7 | GCR-09 instance registry/router race | P1 | Medium | Locked transactional registry + event-loop activation |
| 8 | GCR-10 repeated store bootstrap | P1 | Medium | Bootstrap once + inject store/repositories |
| 9 | GCR-05 async bridge blocking | P1 | Medium | Async web paths; app-owned sync bridge only where needed |
| 10 | GCR-12 prompt path duplication | P2 | Medium | Shared prompt preparation/outcome contract |
| 11 | GCR-15 backend/frontend CI gap | P2 | Low-Medium | Expand workflow triggers/contract job |
| 12 | GCR-14 provider client pooling | P2 | Medium | Instance-scoped shared AsyncClient |
| 13 | GCR-13 redaction buffering | P2 | Medium | Move redaction toward serialization boundary |
| 14 | GCR-16 version unification | P2 | Low-Medium | Single generated build version |
| 15 | GCR-11 split storage monolith | P2 | High | Incremental repository/migration refactor |
| 16 | GCR-04/GCR-17/GCR-18 API cleanup | P3 | Low | Remove/implement stale APIs and normalize provider names |

---

# Tests to add before closing this review

1. **Cross-workspace command concurrency test** — two instances validate/run commands simultaneously and never exchange workspace roots.
2. **Instance creation rollback test** — force first-account registration failure; assert no directory, registry entry or route survives.
3. **Concurrent instance creation test** — create two names concurrently; both registry entries persist exactly once.
4. **Mounted-instance worker test** — secondary instance scheduler/watcher demonstrably runs under the parent host architecture.
5. **Provider launch parity test** — saved connection only; launch/readiness/chat all agree.
6. **Provider lifecycle test** — repeated selection/launch produces no unclosed-client warnings/resources.
7. **Reasoning profile test** — selected hosted reasoning model while registry first entry is non-reasoning; setting applies to selected profile.
8. **Prompt parity contract test** — JSON and streaming paths use the same preparation error code/status model.
9. **Store bootstrap benchmark/test** — prove ordinary request service construction does not replay migration/bootstrap work.
10. **Backend→web contract CI test** — backend schema-only fixture change must trigger or fail a web contract check.

---

# Architectural recommendation

The next refactor should not be a broad rewrite. Four focused boundaries would remove most of the findings:

### 1. `InstanceRuntime`

Own per-workspace store bootstrap, scheduler, watcher, model clients and shutdown. The parent FastAPI app manages these explicitly instead of relying on mounted sub-app lifespan.

### 2. `ProviderManager`

Own model connection resolution, pure validation, provider construction, shared `httpx` clients, active profile and reasoning state. `ModelRouter` becomes routing/orchestration rather than lifecycle management.

### 3. `Database` + domain repositories

Bootstrap/migrate once; expose narrow repositories (`sessions`, `tasks`, `approvals`, `memory`, etc.) rather than constructing a monolithic `SQLiteStore` throughout route helpers.

### 4. `PromptTurnService`

One preparation/execution contract for JSON and SSE surfaces, with transport-specific rendering only at the edge.

These boundaries can be introduced incrementally without changing Raiker's external behavior.

---

# Review limitation

This document is a static source review of `main` at the stated commit. It does not replace runtime profiling, load/concurrency testing, browser E2E against a real host, native sandbox review, dependency analysis or fuzzing. The highest-confidence next step is to write failing regression tests for GCR-01, GCR-02, GCR-06, GCR-07, GCR-08 and GCR-09 before changing implementation.