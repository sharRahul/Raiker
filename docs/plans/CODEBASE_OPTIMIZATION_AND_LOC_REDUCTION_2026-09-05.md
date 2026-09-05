# Raiker Codebase Optimization and LOC-Reduction Pass — 2026-09-05

## Scope

This pass reviews `main` at commit `cf3007c5f2c0a7c54f740a85c9db67ffda7c3e7a` specifically for **safe simplification**: reducing handwritten source lines, reducing oversized-file length, removing duplicated sources of truth, lowering maintenance cost, and making future changes require fewer edits.

It follows the generic static reviews in:

- `docs/plans/GENERIC_STATIC_CODE_REVIEW_2026-09-05.md`
- `docs/plans/GENERIC_STATIC_CODE_REVIEW_THIRD_PASS_2026-09-05.md`

This is not a request to minify code. Security, authority, approval, cryptographic, persistence, destructive-action and fail-closed logic must remain explicit enough to audit. A shorter implementation is an improvement only when it has **fewer independent representations of the same rule** and equivalent or stronger tests.

## Executive conclusion

Raiker can become substantially smaller and easier to maintain without removing product capability. The best reductions are concentrated in five areas:

1. **Generate frontend API contracts/client code from the backend contract** instead of maintaining `api.ts`, `apiTypes.ts`, Python request schemas and backend DTO projections independently.
2. **Decompose the two largest Python integration modules** — `raiker/storage/sqlite.py` (~568 KB) and `raiker/control/dashboard.py` (~400 KB) — while deduplicating repeated CRUD/projection boilerplate.
3. **Create shared lifecycle/transport primitives** for providers, model operations and managed local runtimes.
4. **Replace duplicated registries and string tables with one typed source of truth** for tools, capabilities, reason codes and provider metadata.
5. **Compress historical inline commentary and repeated test setup**, preserving invariants while moving issue-history out of executable files.

A realistic target should be set only after a `cloc` baseline is captured, but the sampled hotspots support a working goal of **meaningfully reducing handwritten production/test LOC rather than merely moving it between files**. The highest-value changes can plausibly remove several thousand handwritten lines while also fixing contract drift and reducing defect surface.

---

# Optimization rules

## OR-01 — Optimize handwritten sources of truth, not generated output

Measure separately:

- handwritten production LOC;
- handwritten test LOC;
- generated LOC;
- comments/docstrings;
- SQL/migrations;
- docs.

A generated TypeScript client may still contain many lines, but if it replaces thousands of manually maintained endpoint/type declarations, maintenance complexity has fallen. Generated artifacts should preferably be build outputs rather than manually edited repository sources.

## OR-02 — No security compression without invariant tests

Do **not** shorten authority, approval, credential, DLP, path-containment, destructive-delete or sandbox rules by replacing readable checks with clever generic code unless tests prove all existing refusal paths remain intact.

## OR-03 — Splitting a file is not LOC reduction

Splitting `sqlite.py` or `dashboard.py` is still worthwhile because it reduces local cognitive load and merge conflicts, but report that separately from actual line deletion.

## OR-04 — Prefer one typed registry over repeated switch/list/map structures

If a tool/provider/capability is described in four places, the goal is not four shorter descriptions. The goal is one authoritative declaration consumed by four projections.

## OR-05 — Keep comments about *why the invariant exists*, not the entire bug history

At the enforcement point, retain concise rationale such as:

> Invariant: a cached SQLCipher connection is never shared for query work across live threads.

Move or delete historical narrative already preserved in Git history/issues/PRs. Long incident reconstructions should not make every future reader traverse dozens of lines before reaching the code.

---

# Findings and recommendations

## OPT-01 — Generate frontend API types from FastAPI/OpenAPI

**Priority: P0/P1 — Effort: Medium — LOC reduction: Very High — Risk: Low/Medium with contract tests**

### Evidence

`apps/web/src/lib/apiTypes.ts` is approximately 94 KB and states that its interfaces mirror backend DTOs. The backend also carries request models in `raiker/api/schemas.py` and response/view structures in `raiker/control/dtos.py` and `raiker/control/dashboard.py`.

This is a multi-source contract: backend fields can change while TypeScript is still hand-edited separately.

### Change

Make the FastAPI/OpenAPI schema the contract source and generate TypeScript types during development/CI.

Recommended shape:

```text
FastAPI schemas / response models
        ↓ OpenAPI
scripts/generate_web_api_types.py or npm codegen
        ↓
apps/web/src/lib/generated/api-schema.ts
```

`generated/` should be treated as machine-owned. If generated files are committed, CI must regenerate and fail on diff. If they are not committed, `npm build/test` must generate them deterministically.

### Remove

- most manually mirrored interfaces from `apiTypes.ts`;
- local duplicate response interfaces in `api.ts` where the same backend schema exists;
- schema drift tests that only compensate for manual mirroring, replacing them with generation-diff tests.

### Acceptance

- no handwritten frontend interface for an ordinary JSON API response that OpenAPI can express;
- special streaming/event contracts remain explicit if OpenAPI cannot accurately represent them;
- frontend build fails if generated contract is stale.

---

## OPT-02 — Generate ordinary REST endpoint wrappers; keep only special transports handwritten

**Priority: P1 — Effort: Medium/High — LOC reduction: Very High — Risk: Medium**

### Evidence

`apps/web/src/lib/api.ts` is approximately 95 KB. It contains a good common `request()`, `requestBlob()`, `withQuery()` and `postJson()` core, followed by a very large handwritten catalogue of one-line/tiny endpoint wrappers and local response types.

### Change

Split the client into:

```text
api/core.ts                 # auth headers, instance path, ApiError, request primitives
api/generated.ts            # generated ordinary JSON REST operations
api/auth.ts                 # session adoption/cookie/CSRF behavior
api/streaming.ts            # SSE/stream-specific behavior
api/files.ts                # Blob/download special cases
```

Generate ordinary REST operations from OpenAPI. Preserve custom code only where Raiker has real semantics beyond a normal request: session adoption, CSRF, SSE, streamed prompt handling, binary downloads, retry/resume semantics.

### Expected result

`api.ts` should stop being an endpoint catalogue and become a small public facade. This should remove a large fraction of handwritten frontend networking code.

---

## OPT-03 — Introduce one strict request base model

**Priority: P1 — Effort: Low — LOC reduction: Small/Medium — Risk: Low**

### Evidence

`raiker/api/schemas.py` repeatedly declares:

```python
model_config = ConfigDict(extra="forbid")
```

and variants of the same configuration.

### Change

Create explicit bases, for example:

```python
class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

class StrictModelRequest(StrictRequest):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())
```

Use dataclasses only when FastAPI/Pydantic validation is genuinely unnecessary. Prefer one request-model system unless there is a measured reason to mix dataclasses and Pydantic models.

### Benefit

Small direct LOC reduction, but larger semantic reduction: input-validation posture becomes inherited instead of repeated.

---

## OPT-04 — Centralize API dependencies and common refusal mapping

**Priority: P1 — Effort: Low/Medium — LOC reduction: Medium — Risk: Low**

### Evidence

Route modules repeatedly reconstruct versions of:

```python
workspace = request.app.state.workspace_root
store = SQLiteStore(workspace)
AuthMiddleware(workspace).authenticate(request)
_require_human(principal)
```

and repeatedly translate `ValueError`/`KeyError`/domain exceptions into small `{reason_code: ...}` HTTP envelopes.

### Change

Create `raiker/api/dependencies.py` with typed dependencies:

```text
workspace(request)
store(request)
authenticated(request)
human_principal(...)
elevated_human(...)
```

Create a small domain-error translation layer for stable reason-code exceptions rather than repeating `try/except → HTTPException` blocks.

Do not hide authorization logic in decorators that make the call site ambiguous. The route signature should still say which authority it requires.

### Expected reduction

Dozens of local `_ws`, `_auth`, `_service`, `_operation_service`, `_library_service`, `_require_human` helpers can disappear or become imports.

---

## OPT-05 — Replace repetitive DTO `to_dict()` implementations with one serialization strategy

**Priority: P1 — Effort: Medium — LOC reduction: Medium/High — Risk: Medium**

### Evidence

`raiker/control/dtos.py` and `raiker/control/dashboard.py` contain many frozen dataclasses with handwritten `to_dict()` methods. Many simply call `asdict(self)`; others manually convert nested tuples/views.

### Change

Choose one of these approaches:

1. Pydantic response models with `model_dump(mode="json")`; or
2. frozen dataclasses plus a single tested `view_to_dict()` serializer that recursively handles dataclasses, tuples and mappings.

Prefer the first if these objects are API contracts because it also feeds OpenAPI generation.

### Important constraint

Do not use a magical serializer that can accidentally expose private fields. API response objects should be dedicated projection types, not storage/domain objects.

### Result

Remove hundreds of repetitive projection lines and make frontend generation practical.

---

## OPT-06 — Break `sqlite.py` into domain stores, then deduplicate only proven CRUD patterns

**Priority: P1 — Effort: High — LOC reduction: High potential; module-length reduction: Critical — Risk: High if done in one step**

### Evidence

`raiker/storage/sqlite.py` is approximately 568 KB and contains connection/security bootstrap, migrations/backfills, FTS maintenance, account/session state, projects, memory, models, tasks, connectors, telemetry, approvals, execution and many other domains.

It also has repeated patterns such as:

```python
with self.connect() as connection:
    rows = connection.execute(...).fetchall()
return [dict(row) for row in rows]
```

### Two-stage refactor

#### Stage A — structural split, no behavior change

```text
raiker/storage/
  core.py                 # Paths, connect, transaction, cache/bootstrap boundary
  accounts.py
  sessions.py
  memory.py
  projects.py
  models.py
  tasks.py
  connectors.py
  approvals.py
  telemetry.py
  execution.py
  search.py
```

Keep `SQLiteStore` temporarily as a compatibility facade/composition root so call sites need not change at once.

#### Stage B — deduplicate safe query boilerplate

Add small helpers such as `_fetch_one`, `_fetch_all`, `_execute`, `_transaction` only where behavior is identical. Avoid a generic ORM-like layer that hides SQL or transaction boundaries.

### Target

- `sqlite.py` becomes a thin connection/composition facade rather than the domain implementation;
- no individual storage domain module should become another multi-thousand-line monolith;
- total storage LOC should fall, not merely be redistributed.

---

## OPT-07 — Replace individual migration constant imports with a migration registry

**Priority: P1 — Effort: Medium — LOC reduction: Medium/High — Risk: Medium**

### Evidence

`sqlite.py` imports a very large list of `*_MIGRATION_ID` and `*_SQL` constants from `raiker/storage/migrations.py`; `migrations.py` itself is approximately 146 KB.

### Change

Represent ordinary migrations as data:

```python
@dataclass(frozen=True)
class Migration:
    id: str
    sql: str

MIGRATIONS = (
    Migration("...", "..."),
    ...
)
```

For migrations requiring Python logic, use an optional callable or keep an explicit named migration function.

The bootstrap should iterate a registry rather than manually importing and wiring every constant.

### Benefit

Reduces import/wiring boilerplate, makes ordering visible, and prevents every new migration from lengthening `sqlite.py` in multiple places.

### Constraint

Historical migration behavior must remain immutable once released.

---

## OPT-08 — Decompose `dashboard.py` by read-model domain and remove embedded API DTO duplication

**Priority: P1 — Effort: High — LOC reduction: Medium/High; module-length reduction: Critical — Risk: Medium**

### Evidence

`raiker/control/dashboard.py` is approximately 400 KB and combines a large number of view dataclasses with cross-domain query/build logic. The file contains many repeated `asdict()` projections and long comments attached to individual view fields.

### Change

```text
raiker/control/views/
  sessions.py
  memory.py
  models.py
  mcp.py
  projects.py
  security.py
  tasks.py

raiker/control/read_models/
  sessions.py
  memory.py
  models.py
  ...
```

Use the response-model strategy from OPT-05 so the view layer also becomes the OpenAPI source.

### Do not

Replace `dashboard.py` with a single new `DashboardRepository` monolith. The point is domain ownership, not file renaming.

---

## OPT-09 — Introduce a shared async provider HTTP transport

**Priority: P1 — Effort: Medium — LOC reduction: Medium — Risk: Medium**

### Evidence

`anthropic_messages.py` (~29 KB) and `openai_compatible.py` (~30 KB) independently implement:

- `httpx.AsyncClient` creation/ownership;
- `aclose()`;
- request dispatch;
- timeout/HTTP exception translation;
- status/error mapping;
- response JSON validation;
- health/list-model scaffolding.

The provider-specific message and stream protocols are legitimately different; transport lifecycle is not.

### Change

Create a small `ProviderHttpTransport` used by provider adapters:

```text
request(method, url/path, headers, ...)
stream(...)
json_object(response)
close()
```

Give it provider-specific status mapping as a callback rather than subclassing a deep inheritance tree.

### Keep provider-local

- request payload shape;
- tool-call mapping;
- streaming protocol parser;
- reasoning semantics;
- provider-specific model metadata.

This can remove repeated infrastructure without forcing Anthropic and OpenAI protocols into one abstraction.

---

## OPT-10 — Share managed-local-runtime process/slot lifecycle

**Priority: P1/P2 — Effort: Medium — LOC reduction: Medium — Risk: Medium**

### Evidence

`ManagedLlamaRuntime` and `ManagedMlxRuntime` separately implement nearly the same:

- slot tables;
- process dictionaries;
- `_alive()`;
- slot selection;
- loopback server launch;
- terminate/wait/kill cleanup;
- status projection.

Their command construction and model-path validation differ.

### Change

Create a tested `ManagedSlotRuntime` lifecycle primitive with injected:

- slot definitions;
- model validator;
- argv builder;
- status metadata.

This also gives one place to implement the locking required by GCR-28.

### Benefit

LOC reduction and correctness remediation reinforce each other rather than creating two separate fixes.

---

## OPT-11 — Create a model-operation worker harness

**Priority: P1 — Effort: Medium — LOC reduction: Medium — Risk: Medium**

### Evidence

Hugging Face downloads, conversion, Ollama pull, llama.cpp deployment and MLX deployment repeat variations of:

```text
mark running
check cancellation
perform work
check cancellation
complete
except → fail/cancel
```

### Change

Build a small operation context/harness that owns **state transition mechanics**, not domain work:

```python
with operation_worker(service, owner, operation_id, phase="...") as op:
    op.check_cancelled()
    ... domain work ...
    op.check_cancelled()
```

For async workers provide the corresponding async form.

### Critical requirement

Implement this together with GCR-20/GCR-21 state-machine CAS rules. Do not merely abstract the current lost-update behavior.

---

## OPT-12 — Replace giant provider-readiness exception ladders with a typed classifier

**Priority: P2 — Effort: Medium — LOC reduction: Medium — Risk: Medium**

### Evidence

`ProviderCatalogueProbe.check()` contains two large exception-classification ladders: catalogue check and execution preflight. Many branches repeat state construction, provider labels and remediation formatting.

### Change

Create a pure classifier:

```text
classify_provider_failure(exc, profile, stage) → ReadinessFailure
```

where `ReadinessFailure` carries state, reason code and remediation template.

Keep the special workspace/quota/model cases explicit. The goal is one classification table/function, not hiding exceptions behind generic text.

### Benefit

Shorter readiness code and one place to fix edge-case gaps such as GCR-30.

---

## OPT-13 — Create one typed tool-definition registry

**Priority: P1 — Effort: High — LOC reduction: High — Risk: High; requires strong invariant tests**

### Evidence

Tool identity and behavior are represented across multiple locations: tool specs/projection, the broker executor map, capability classification, result-content redaction sets, authority/capability mapping, tool presentation and MCP projection.

`ToolBroker` contains a very large executor dictionary with one lambda/adapter per tool, while additional sets such as `_CONTENT_RESULT_TOOLS` separately describe audit treatment.

### Change

Define one typed declaration per built-in tool:

```python
@dataclass(frozen=True)
class ToolDefinition:
    name: str
    spec: ToolSpec
    capability: str
    handler: ToolHandler
    result_policy: ResultAuditPolicy
    projection: ProjectionPolicy
```

Then derive:

- model tool specs;
- broker dispatch;
- capability lookup;
- metadata/content audit handling;
- presentation defaults.

MCP tools remain dynamic declarations projected into the same runtime shape.

### Why high value

Every new tool should require one primary declaration, not edits in several registries. This reduces both LOC and omission defects.

### Safety constraint

Authority must remain external to the tool definition. A tool declaration must never be able to grant itself authority.

---

## OPT-14 — Put provider display metadata in the profile registry instead of code mappings

**Priority: P2 — Effort: Low/Medium — LOC reduction: Small/Medium — Risk: Low**

### Evidence

`readiness.py` carries `_provider_label()` as a hardcoded mapping while model profiles already carry provider/profile metadata.

### Change

Add safe presentation metadata such as `display_name` to the profile/provider registry and consume it in readiness/UI projections.

Apply the same rule to other purely descriptive repeated provider tables. Do not move runtime security policy into display configuration.

---

## OPT-15 — Compress historical BUG/FIXED narratives inside executable files

**Priority: P1/P2 — Effort: Medium — LOC reduction: Very High — Risk: Low if invariants are preserved**

### Evidence

Large modules such as `sqlite.py`, `dashboard.py`, provider adapters and `release.yml` contain extensive multi-paragraph histories of previous bugs, measurements and implementation evolution. These are useful records, but much of the material explains *how the code arrived here* rather than *what invariant current code must preserve*.

Examples in the reviewed samples include multi-dozen-line blocks explaining SQLCipher cache history/memory-security incidents and multi-paragraph provider reasoning compatibility history.

### Change

Adopt a comment policy:

- keep **invariant + non-obvious reason + failure mode** near code;
- keep external protocol facts that are required to maintain compatibility;
- remove chronology such as “before BUG-X this did Y, then BUG-Z changed it...” when Git history/PR already preserves it;
- where a long operational explanation remains necessary, put it in a focused existing guide/spec and link with one line rather than copying it into multiple files.

Example:

```python
# Invariant: cached SQLCipher connections are thread-affine; never close a
# connection owned by another live worker. Exited-thread handles may be reaped.
```

### Important

Do **not** strip comments around security boundaries simply to hit a LOC target. This pass recommends deleting history, not deleting rationale.

---

## OPT-16 — Consolidate repeated Playwright setup into fixtures/page objects

**Priority: P2 — Effort: Medium — LOC reduction: Medium/High — Risk: Low**

### Evidence

The E2E suite already has useful helpers such as `hosted-provider`, but individual live specs still repeat host constants, sign-in/account-bootstrap flows, browser/context setup, model/provider selection, turn submission, capability activation and screenshot-path plumbing.

### Change

Expand shared fixtures around product actions rather than DOM implementation details:

```text
ownerPage
modelsPage.connectProvider(...)
modelsPage.selectModel(...)
chat.runTurn(...)
capabilities.enable(...)
captureEvidence(...)
```

Use table-driven tests only where scenarios truly differ by data (for example multiple hosted providers following the same connect/select/check flow).

### Do not

Collapse semantically different safety tests into one opaque parameterized loop. Test names and failure location must remain clear.

---

## OPT-17 — Use backend factories/builders in Python tests instead of repeated full object construction

**Priority: P2 — Effort: Medium — LOC reduction: Medium — Risk: Low**

### Change

Create small test factories for high-frequency objects:

- principals/users/sessions;
- prompt envelopes;
- model profiles/readiness rows;
- tool actions/results;
- approvals;
- tasks;
- connector manifests.

Factories should expose meaningful defaults and require explicit values for authority/security-sensitive fields. This reduces fixture noise without hiding the exact security posture being tested.

---

## OPT-18 — Extract shared reason-code/envelope types instead of repeating string dictionaries

**Priority: P2 — Effort: Medium — LOC reduction: Medium — Risk: Medium**

### Evidence

Stable reason codes appear as constants in `control/dtos.py`, literal exception messages, `{reason_code: ...}` response bodies and frontend branching.

### Change

Create a backend reason-code catalogue using `StrEnum` or constants grouped by domain. Generate the frontend union from OpenAPI/schema where useful.

Prefer domain exceptions that carry `reason_code` over `ValueError("literal_reason")` when the error crosses a layer boundary.

### Benefit

Fewer repeated strings, fewer mappings, and less defensive frontend code.

---

## OPT-19 — Reduce workflow duplication with reusable setup, but do not move YAML lines into opaque shell scripts just to win LOC

**Priority: P3 — Effort: Medium — LOC reduction: Small/Medium — Risk: Low**

### Evidence

`release.yml` is approximately 22 KB and repeats checkout/runtime setup/build preparation also present in other workflows. It also contains large inline Python/bash blocks.

### Change

Use a small number of reusable composite actions/workflow-call jobs for genuinely repeated setup:

- checkout + Python setup;
- web setup/build;
- package/test preparation.

Move substantial release logic to tested Python only where it is real product/release logic, not just to shorten YAML. Keep signing commands visible where platform-specific review matters.

---

## OPT-20 — Keep generated/static registries as data when behavior is table-driven

**Priority: P2 — Effort: Medium — LOC reduction: Medium — Risk: Medium**

Candidate areas include:

- provider presentation metadata;
- capability metadata that is not enforcement code;
- local runtime slot declarations;
- model/profile facts;
- ordinary migration metadata;
- UI navigation/page metadata;
- repeated status→label/remediation maps.

A rule with executable side effects or security semantics should remain code. A declaration that is repeatedly switched over should become data.

---

# Module-length reduction targets

These are **maintainability targets, not automatic CI failures on day one**.

| Current hotspot | Current approximate size | Target shape |
|---|---:|---|
| `raiker/storage/sqlite.py` | ~568 KB | connection/composition facade; domain stores below it |
| `raiker/control/dashboard.py` | ~400 KB | domain read-model modules + response models |
| `apps/web/src/lib/api.ts` | ~95 KB | small core/facade + generated ordinary REST client |
| `apps/web/src/lib/apiTypes.ts` | ~94 KB | generated contract; near-zero handwritten API types |
| `raiker/storage/migrations.py` | ~146 KB | immutable migration modules/registry; no giant import wiring |
| provider adapters | ~29–30 KB each for major providers | protocol-specific code on shared transport |
| `.github/workflows/release.yml` | ~22 KB | shorter declarative orchestration, tested release logic in code |

Suggested soft thresholds for new handwritten files:

- Python/TypeScript: warning around 800–1,000 LOC;
- investigate at ~1,500 LOC;
- prohibit new multi-thousand-line files without explicit design review;
- Svelte components: split when a component owns multiple independent screens/workflows rather than enforcing a numerical threshold alone.

---

# Where LOC reduction should **not** be the goal

Do not optimize these primarily for line count:

1. runtime authority and capability decisions;
2. critical approval binding/replay checks;
3. path containment and deletion guards;
4. credential and secret handling;
5. SQLCipher/key lifecycle;
6. command/sandbox boundary enforcement;
7. DLP/egress decisions;
8. event integrity/checkpoint restore validation;
9. parser/archive/attachment limits;
10. state-transition compare-and-swap checks introduced to fix concurrency defects.

For these areas, clarity and independently testable checks are more valuable than shortness.

---

# Recommended implementation order — priority then effort

## Wave 0 — establish the baseline

**P0 / Low effort**

Before changing code, add a reproducible measurement command/script that reports:

```text
handwritten production LOC by language
test LOC
comment/docstring LOC
generated LOC
largest 30 source files
Python function/class complexity
frontend bundle size
```

Exclude `.git`, build outputs, model files, generated outputs and documentation from the production-LOC number.

Suggested tools: `cloc` or `tokei`, Ruff complexity rules/Radon where useful, TypeScript/Svelte build statistics.

Store a machine-readable baseline artifact in CI rather than hand-maintaining numbers in README.

## Wave 1 — low-risk removal of duplication

1. OPT-03 strict request base model.
2. OPT-04 shared API dependencies/refusal translation.
3. OPT-05 common response-model serialization strategy.
4. OPT-14 provider display metadata from registry.
5. OPT-15 compact historical inline narratives.
6. OPT-16 Playwright fixtures for repeated setup.

These can produce immediate net line deletion without redesigning core runtime behavior.

## Wave 2 — contract generation

1. OPT-01 generated TypeScript API types.
2. OPT-02 generated ordinary REST client wrappers.
3. OPT-18 generated/shared reason-code contracts.

This is the highest-value source-of-truth reduction because future API additions stop creating parallel Python + TypeScript maintenance work.

## Wave 3 — correctness-aligned shared primitives

1. OPT-11 model-operation worker harness **with GCR-20/GCR-21 atomic transition fixes**.
2. OPT-10 shared local-runtime lifecycle **with GCR-28 locking**.
3. OPT-09 shared provider HTTP transport **with existing provider error tests expanded**.
4. OPT-12 readiness failure classifier **with GCR-30 coverage**.

## Wave 4 — large structural decomposition

1. OPT-07 migration registry.
2. OPT-06 storage domain split + measured CRUD dedupe.
3. OPT-08 dashboard/read-model decomposition.
4. OPT-13 typed tool-definition registry.

Do these after the correctness fixes and contract tests provide a stable safety net.

## Wave 5 — lower-yield cleanup

- OPT-17 backend test builders.
- OPT-19 workflow reuse.
- OPT-20 remaining table-driven metadata.

---

# Required measurement gates

For every simplification PR, record:

```text
handwritten LOC before → after
largest touched file before → after
tests before → after
coverage or equivalent contract-test count
public API/schema diff
mypy/ruff/pytest result
web typecheck/unit/e2e result where applicable
```

A refactor that moves 1,000 lines into another handwritten file scores **0 LOC reduction**. A refactor that replaces 1,000 manual lines with a 100-line generator and deterministic generated output scores as a maintenance reduction and must separately report generated LOC.

---

# Suggested acceptance targets

These are directional targets to validate after the baseline rather than promises made without `cloc` evidence.

### Target A — frontend contract surface

- ordinary REST response/request types: generated;
- ordinary REST wrappers: generated;
- handwritten `api` code limited to authentication, streaming, binary transfers and Raiker-specific orchestration;
- no backend response field added solely by manually updating TypeScript.

### Target B — storage

- `SQLiteStore` no longer owns every domain method;
- adding a new task/model/connector feature does not require editing a half-megabyte central file;
- repeated query boilerplate decreases while transaction boundaries remain obvious.

### Target C — control/read models

- no 400 KB dashboard module;
- one response-model strategy feeds both runtime serialization and OpenAPI;
- domain read models can be tested without constructing unrelated dashboard services.

### Target D — runtime/tool definitions

- adding a normal built-in tool requires one primary typed declaration plus its handler/tests, not edits to several unrelated name lists;
- authority remains a separate mandatory execution boundary.

### Target E — comments/tests

- executable files explain current invariants, not full issue chronology;
- repeated browser setup lives in fixtures;
- test scenario intent remains explicit.

---

# Practical reduction estimate

A precise percentage should **not** be claimed until Wave 0 establishes the repository baseline. Based on the reviewed hotspots, however, the largest removable handwritten surfaces are clearly large enough that this effort should target **thousands of lines, not dozens**.

The likely order of reduction contribution is:

1. frontend API types/client generation;
2. historical-comment compaction;
3. storage/dashboard projection and CRUD boilerplate;
4. shared route dependencies and response serialization;
5. test fixtures/builders;
6. provider/runtime/model-operation shared lifecycle code;
7. registry/table consolidation.

The primary success metric should be:

> **How many independent places must a developer correctly change to add or modify one capability?**

If a refactor reduces total LOC but still requires a feature to be declared in the backend DTO, TypeScript interface, endpoint wrapper, broker list, capability list and audit list separately, Raiker is shorter but not simpler.

---

# Final recommendation

Do not begin by manually trimming `sqlite.py` or `dashboard.py`. Begin by removing duplicated contracts and boilerplate, while the third-pass correctness findings are fixed. Then decompose the two monoliths with tests already protecting the public contracts.

The preferred convergence is:

```text
Authoritative typed domain declarations
        ↓
backend API / OpenAPI
        ↓
generated frontend contracts + ordinary client

Domain storage modules ← shared connection/transaction core
Domain read models     ← shared response-model serialization
Provider adapters      ← shared transport, provider-specific protocol
Model workers          ← shared atomic operation lifecycle
Tool handlers          ← typed tool registry + external authority gate
```

This approach reduces code length because duplicated descriptions disappear, not because important behavior is hidden.