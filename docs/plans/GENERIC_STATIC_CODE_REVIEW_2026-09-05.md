# Raiker Generic Static Code Review — 2026-09-05

## Review target

This review examines the code on `main` at commit `cf3007c5f2c0a7c54f740a85c9db67ffda7c3e7a`.

It is intentionally separate from the security/compliance assessment and the security-specific code review. This document focuses on generic software-engineering quality: correctness, reliability, lifecycle/resource management, concurrency, architecture, maintainability, performance, API consistency, test coverage and release/build engineering.

This is a static review, not a claim that every line in the repository was manually inspected and not a runtime/profiling exercise. Findings below are limited to issues supported by concrete implementation evidence in the reviewed `main` tree.

## Third-pass continuation

A deeper third-pass review has now been completed and is recorded in:

`docs/plans/GENERIC_STATIC_CODE_REVIEW_THIRD_PASS_2026-09-05.md`

That companion extends this review with **GCR-19 through GCR-47**, including a P0 destructive-cleanup/data-loss finding, model-operation state races, durable-job/restart gaps, model-library shard-indexing defects, managed-runtime concurrency, provider protocol edge cases, OAuth refresh races, event-log atomicity, scheduler/watcher observability, frontend contract generation and release reproducibility.

The combined generic review therefore currently contains **47 findings**. The third-pass remediation order should be used when prioritising implementation because it incorporates the newer data-integrity findings.

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

The largest issues found in this first generic pass are:

1. multiple `ModelRouter` code paths construct providers differently, causing configuration inconsistency and leaked clients;
2. multi-instance execution shares module-global command workspace state;
3. mounted Raiker instances are built as FastAPI sub-applications with their own lifespan workers, but mounted sub-app lifespans do not run under FastAPI;
4. instance creation is non-transactional and mutates the live route table from a synchronous worker thread;
5. `SQLiteStore` performs bootstrap/migration work in every constructor while hot request paths repeatedly construct stores;
6. prompt submit and prompt streaming have duplicated orchestration with differing error semantics;
7. frontend CI is path-filtered so backend API contract changes can bypass frontend type/build/E2E checks.

The third pass adds more urgent correctness issues; see the companion document above before implementing this backlog.

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

That path does not use `self.connection_resolver` and therefore does not see a saved endpoint/API key/workspace value held in the model connection vault.

### Impact

A profile can validate differently in `launch()` than it does in real `achat()`, `astream()`, `aembed()`, health or catalogue operations. A provider that works during actual execution may be reported as missing configuration during launch, or launch may validate a different endpoint than execution uses.

### Recommendation

Route all provider construction/validation through one helper. If launch only validates, introduce a transport-free `validate_profile_configuration()` path rather than constructing a live provider.

---

## GCR-02 — Provider clients can leak during validation

**Severity: High — Priority: P1 — Confidence: High**

`select_profile()` calls `self._factory(profile).create(profile)` only to validate it and discards the returned provider. `launch()` similarly constructs a provider and does not close it.

OpenAI-compatible and Anthropic providers create an owned `httpx.AsyncClient` in `__post_init__` when no client is supplied. Their normal async execution methods close that client in `finally`, but these validation paths do not.

Repeated model selection/launch validation can therefore create unclosed async clients and connection pools.

**Recommendation:** do not construct network transports for configuration validation. If construction is required, make provider ownership an async context manager and close it deterministically.

---

## GCR-03 — Reasoning settings can be validated against the wrong model profile

**Severity: Medium/High — Priority: P1 — Confidence: High**

`ModelRouter.set_reasoning()` resolves the profile as:

```python
self.registry.resolve_profile_id(self.active_profile_id)
if self.active_profile_id
else self.registry.list_profiles()[0]
```

`active_profile_id` is only set by `select_profile()`. The normal gateway/default-model resolution path can run without that method having been called. The first shipped registry profile is currently a llama.cpp profile without reasoning support.

Therefore an owner using a different selected/default model can have reasoning controls evaluated against the first registry entry rather than the model that will execute the turn.

**Recommendation:** make reasoning settings explicitly profile-scoped or resolve them against the same selected/default target that the turn will use.

---

## GCR-04 — `generate(..., context=...)` ignores `context`

**Severity: Medium — Priority: P2 — Confidence: High**

`ModelRouter.generate(provider, model, prompt, context=None)` accepts a context parameter but simply calls:

```python
self.chat(provider, model, [ModelMessage(role="user", content=prompt)]).text
```

The supplied context is unused.

This API is misleading: a caller can supply context believing it affects generation when it has no effect.

**Recommendation:** either remove the parameter or define and test its projection into messages.

---

## GCR-05 — `run_coro()` blocks an active event-loop thread

**Severity: Medium — Priority: P1 — Confidence: High**

When no loop is running, `run_coro()` correctly uses `asyncio.run()`. When called from a thread already running an event loop, it creates a one-worker `ThreadPoolExecutor`, submits `asyncio.run(coro)` to that thread and immediately waits on `.result()`.

The coroutine no longer conflicts with the active event loop, but the caller's event-loop thread is still synchronously blocked until it completes. A new thread pool is also created and destroyed on every such call.

**Recommendation:** request-path code should remain async end-to-end. Keep a sync bridge only at truly synchronous process boundaries, not inside ASGI execution.

---

## GCR-06 — Command validation uses process-global workspace state

**Severity: High — Priority: P0/P1 — Confidence: High**

`raiker/runtime/executors/sandbox.py` stores command-policy workspace state in module global `_COMMAND_WORKSPACE`. `run_command()` calls `set_command_workspace(cwd)` immediately before `check_command_allowlist()`, while the validator later reads `_command_workspace()`.

This is not thread-local or request-local. With multiple mounted Raiker instances or concurrent command execution, one command can overwrite the workspace used to validate another command.

**Impact:** incorrect allow/deny decisions and cross-instance path validation using the wrong workspace root.

**Recommendation:** delete the global. Pass `workspace_root` directly through `check_command_allowlist()` / `validate_command()` and every caller.

---

## GCR-07 — Mounted instance lifespans are not application lifecycle management

**Severity: High — Priority: P1 — Confidence: High**

Each secondary instance is created by recursively calling `create_app(workspace, ...)` and mounted with Starlette `Mount`. The `create_app()` lifespan is responsible for starting that workspace's task scheduler, approval continuation worker, attached-root watcher and runtime shutdown cleanup.

FastAPI documents that lifespan events run only for the main application, not mounted sub-applications. Therefore using a mounted child FastAPI app as the lifecycle owner does not start the child lifespan workers.

**Impact:** secondary instances can serve requests while their scheduler, approval continuation loop, telemetry cadence and attached-root watcher are not managed as intended.

**Recommendation:** introduce a parent-owned `InstanceRuntime` lifecycle manager. Mounted ASGI routing should only route requests; the root lifespan should explicitly start/stop each instance's runtime services.

---

## GCR-08 — Instance creation is not transactional

**Severity: High — Priority: P1 — Confidence: High**

The `/api/instances` route first calls `create_and_mount_instance()` and only afterwards calls `AccountService(workspace).register(...)` when initial account data was provided.

`create_and_mount_instance()` creates the directory, appends the name to `instances.json`, constructs/mounts the FastAPI child and then returns.

If account registration fails, the route returns an error but does not unmount the route, remove the registry entry or remove the newly created workspace. A retry can then fail with `instance_already_exists` even though the original request reported failure.

**Recommendation:** validate/register in a staged workspace first, then atomically publish the registry entry and mount. On any failure, roll back all staged state.

---

## GCR-09 — Instance registry and route mutation are race-prone

**Severity: High — Priority: P1 — Confidence: High**

`instances.json` is updated with a read-modify-`write_text` flow without a per-registry lock or atomic temp-file replace. Concurrent creates can lose names or expose a partially written JSON file.

The instance route itself is a synchronous FastAPI handler, so it may execute in the framework threadpool. `_mount_instance()` directly mutates `app.router.routes` while the application can concurrently route requests.

**Recommendation:** serialize instance creation in a root-runtime manager, persist registry updates with atomic replace/transactional storage, and perform live route publication through one event-loop-owned path.

---

## GCR-10 — `SQLiteStore` bootstraps on every construction

**Severity: Medium/High — Priority: P1 — Confidence: High**

`SQLiteStore.__init__()` calls `self.bootstrap()` under process-global `_BOOTSTRAP_LOCK`. Bootstrap performs schema/migration checks.

The application architecture constructs `SQLiteStore` frequently. Prompt handling alone can instantiate stores for session ownership, project resolution, readiness, attachment references, generated files and `AgentGateway`; control/read routes follow the same pattern.

Even when migrations are idempotent, repeated constructor-time bootstrap adds lock contention, SQL work and coupling between an ordinary repository object and global schema lifecycle.

**Recommendation:** bootstrap a workspace once in application/instance lifecycle, record the schema version, and make normal repository/store construction cheap. Keep an explicit defensive schema check only where needed.

---

## GCR-11 — `sqlite.py` is a persistence god module

**Severity: Medium — Priority: P2 — Confidence: High**

`raiker/storage/sqlite.py` coordinates SQLCipher connection caching, encryption posture, schema bootstrap, a very large migration catalogue and persistence methods for many unrelated domains.

The broad migration import list itself demonstrates how many product domains depend on one module. This increases change conflict, test setup cost and the chance that a local storage change affects unrelated features.

**Recommendation:** retain one low-level SQLCipher connection/migration core, but move domain persistence behind repositories such as `TaskRepository`, `ModelRepository`, `MemoryRepository`, `ApprovalRepository`, etc. The migration runner should also be its own component.

---

## GCR-12 — Prompt JSON and SSE routes duplicate orchestration

**Severity: Medium — Priority: P2 — Confidence: High**

`submit_prompt()` and `stream_prompt()` both independently perform session ownership checks, project resolution, envelope building, project binding, readiness checks, attachment recording, gateway construction and generated-file recording.

They already expose different failure semantics: a non-stream readiness failure is HTTP 409, while streaming returns a successful SSE response containing a final failure event; validation is likewise represented differently.

Some differences are transport-appropriate, but preparation/business orchestration should not be duplicated.

**Recommendation:** create a shared `PromptTurnService.prepare()` result and small transport adapters for JSON vs SSE error/event representation.

---

## GCR-13 — API redaction middleware buffers nearly every API response

**Severity: Medium — Priority: P2 — Confidence: High**

`RedactionMiddleware` captures the response start and accumulates every body chunk for almost every `/api` path, only emitting after the final body chunk. A manually maintained exemption list exists for SSE and some exports.

**Impact:** streaming semantics are opt-out rather than natural; new streaming/binary endpoints can accidentally be buffered, memory use scales with response size, and every new special route requires remembering another exemption.

**Recommendation:** redact structured response DTOs before serialization where possible. Middleware should be content-type/size aware and should not buffer unknown or streaming bodies by default.

---

## GCR-14 — Provider connection pools are recreated per operation

**Severity: Medium — Priority: P2 — Confidence: High**

`ModelRouter` creates a provider for each chat, stream, embed, health and model-list call and then closes it. Without an injected client, each provider creates its own `httpx.AsyncClient`.

This is lifecycle-correct for the normal async methods but loses HTTP keep-alive/HTTP2 connection reuse and repeatedly builds pools/TLS connections.

**Recommendation:** own provider HTTP clients at app/instance/provider-manager scope, keyed by endpoint/credential/config lifecycle, and close them during instance shutdown or connection mutation.

---

## GCR-15 — Backend API changes can bypass frontend CI

**Severity: Medium — Priority: P2 — Confidence: High**

`.github/workflows/web.yml` is triggered only when `apps/web/**` or the workflow itself changes. It runs lint, Svelte/TypeScript checks, tests, build and mocked Playwright.

A backend-only change to API routes, DTOs or schema can therefore merge without running the frontend compilation/E2E suite even though the web client consumes those contracts.

**Recommendation:** include backend contract-producing paths in the web workflow trigger, or add a dedicated contract workflow driven from generated OpenAPI/schema output.

---

## GCR-16 — Version metadata has multiple independent values

**Severity: Low/Medium — Priority: P2 — Confidence: High**

The Python package declares `0.0.0`; the web package declares `0.0.0`; prompt client metadata also uses `0.0.0`; FastAPI reports `0.1.0`; and release workflow version is supplied separately through `workflow_dispatch`.

This makes diagnostic/support output and compatibility metadata depend on which surface is read rather than one build identity.

**Recommendation:** generate runtime/web/API version metadata from one build/version source and include commit/build identity separately.

---

## GCR-17 — Provider-name normalization is inconsistent

**Severity: Low — Priority: P3 — Confidence: High**

`ModelProfileRegistry.resolve()` normalizes underscores/hyphens and aliases `llama-cpp` to `llama.cpp`. `profiles_for_provider()` performs the alias too, but `find()` only replaces underscores with hyphens.

A provider name can therefore resolve in one method and not be found in another.

**Recommendation:** one `_normalize_provider()` helper for all registry lookups.

---

## GCR-18 — Unused public parameters make contracts misleading

**Severity: Low — Priority: P3 — Confidence: High**

Examples identified:

- `ModelRouter.default_provider(*, health_timeout=1.0)` never uses `health_timeout` and performs no health check.
- `ModelRouter.generate(..., context=None)` does not use `context` (also GCR-04).

Public parameters imply supported behavior and create false assumptions in callers/tests.

**Recommendation:** remove unused parameters or implement the documented semantics, with deprecation where external callers may exist.

---

# Positive engineering observations

The review also found implementation practices worth preserving:

- extensive fail-closed validation and stable reason codes;
- clear comments explaining non-obvious invariants and prior failure modes;
- immutable-SHA GitHub Actions in reviewed workflows;
- strong Python lint/type/test gates and Rust fmt/clippy/test gates;
- mocked web E2E in CI and a deliberately separate live suite;
- explicit resource/time/output bounds in many execution surfaces;
- deterministic release archive construction and deliberate signing posture;
- strong approval replay/TOCTOU handling documented in the security review;
- thread-aware SQLCipher connection cache with bounded process-wide population;
- explicit scheduler exactly-once/resume intent and per-task owner revalidation.

These controls should be maintained while fixing the findings above.

---

# Architectural refactor direction

The findings do **not** justify a wholesale rewrite. Four incremental boundaries would remove much of the observed complexity:

1. **InstanceRuntime** — owns one workspace's store bootstrap, scheduler, watchers, managed model runtimes, command service and shutdown.
2. **ProviderManager** — owns provider configuration validation, pooled clients and lifecycle; `ModelRouter` chooses models rather than owning transport creation.
3. **Domain repositories** — split persistence operations out of `SQLiteStore` while retaining one SQLCipher/migration core.
4. **PromptTurnService** — owns prompt preparation/readiness/project/session/attachment orchestration; HTTP JSON and SSE become adapters.

Each extraction should be characterization-test driven and behavior-preserving.

---

# Original generic remediation order

For historical context, the first pass recommended:

1. GCR-01 — unify provider validation/construction.
2. GCR-02 — eliminate leaked provider clients.
3. GCR-03 — bind reasoning controls to the actual selected profile.
4. GCR-08 — make instance creation transactional.
5. GCR-06 — remove global command-workspace state.
6. GCR-07 — introduce a parent-owned instance lifecycle manager.
7. GCR-09 — serialize/atomically persist instance registration.
8. GCR-10 — bootstrap each workspace once.

**Superseded for prioritisation:** use the combined priority/effort table in `GENERIC_STATIC_CODE_REVIEW_THIRD_PASS_2026-09-05.md`, because GCR-19 and newer data-integrity/lifecycle findings now precede several of these items.

---

# Review limitations / next verification stage

Static review cannot confirm timing-dependent races or production performance. The next verification stage should add:

- concurrent instance creation tests;
- concurrent commands across two workspaces;
- provider client/resource leak tests;
- event-loop responsiveness tests around sync bridges;
- store bootstrap profiling under concurrent API requests;
- mounted-instance scheduler/watcher integration tests using a real lifespan server;
- API/OpenAPI ↔ TypeScript contract diff checks;
- fault injection around store/database errors and lifecycle cleanup;
- native sandbox stress/escape review and long-running process tests;
- release/install smoke tests on real target artifacts.

The third-pass companion adds a larger adversarial/fault-injection suite for the newly identified operation, scheduler, event-log and concurrency defects.
