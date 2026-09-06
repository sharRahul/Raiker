# Raiker Generic Static Code Review — Third Pass — 2026-09-05

## Review target

This is a deeper third-pass static review of `main` at commit `cf3007c5f2c0a7c54f740a85c9db67ffda7c3e7a`.

It is a companion to `docs/plans/GENERIC_STATIC_CODE_REVIEW_2026-09-05.md`. The first generic pass recorded GCR-01 through GCR-18. This pass deliberately hunts a different layer of defects: data-integrity failures, state-machine races, crash/restart behavior, background-job durability, process/thread lifecycle, indexing correctness, provider protocol edge cases, connector concurrency, persistence atomicity, frontend/backend contract drift, and release reproducibility.

This remains a static review. It is not a runtime stress test, profiler run, fuzzing campaign, or proof that no additional defects exist. Findings are included only where the reviewed `main` implementation provides concrete evidence.

## Status — 2026-09-06

Eleven of the forty-seven are closed here, taken in the order this document's own
remediation table gives — priority first, then effort. Every entry below keeps
its original analysis; a closed one carries a **Status** line naming the
[`FIXED_ITEMS.md`](FIXED_ITEMS.md) record that closed it, so the evidence and the
finding stay together.

The 2026-09-06 pass also closed the four first-pass findings this document's
remediation order puts next — GCR-01, GCR-02, GCR-03 and GCR-06 — plus GCR-04 and
GCR-18, which live in the same two methods. Their records are
[FIXED-430](FIXED_ITEMS.md#fixed-430--five-surfaces-asked-would-this-model-run-by-building-one-and-dropping-it),
[FIXED-431](FIXED_ITEMS.md#fixed-431--a-reasoning-setting-judged-against-whichever-profile-was-first-in-the-file),
[FIXED-432](FIXED_ITEMS.md#fixed-432--two-commands-running-at-once-could-be-judged-against-each-others-workspace)
and
[FIXED-434](FIXED_ITEMS.md#fixed-434--two-public-parameters-that-changed-nothing);
the findings themselves are marked closed in
[`GENERIC_STATIC_CODE_REVIEW_2026-09-05.md`](GENERIC_STATIC_CODE_REVIEW_2026-09-05.md).

| Closed | What it was | Record |
|---|---|---|
| GCR-19 | The P0: a failed conversion's cleanup boundary was a shared library directory | [FIXED-420](FIXED_ITEMS.md#fixed-420--a-failed-conversions-cleanup-could-delete-every-model-beside-it) |
| GCR-20, GCR-23 | Non-CAS lifecycle writes; a cancellation could be overwritten by the worker it cancelled | [FIXED-421](FIXED_ITEMS.md#fixed-421--a-cancellation-could-be-overwritten-by-the-worker-it-cancelled) |
| GCR-21 | Retry accepted any state and was not a claim | [FIXED-422](FIXED_ITEMS.md#fixed-422--retry-checked-the-kind-and-the-payload-and-never-the-state) |
| GCR-22 | Initial Hugging Face download ran in the request path | [FIXED-423](FIXED_ITEMS.md#fixed-423--a-multi-gigabyte-download-ran-inside-the-request-that-asked-for-it) |
| GCR-27 | Same-named GGUF shards in two folders indexed as one model | [FIXED-424](FIXED_ITEMS.md#fixed-424--two-models-one-folder-apart-were-indexed-as-one) |
| GCR-30 | `health()` could raise instead of returning `ProviderHealth` | [FIXED-425](FIXED_ITEMS.md#fixed-425--a-method-whose-contract-was-to-return-health-raised-instead) |
| GCR-31 | The thinking-budget clamp clamped upward, past the limit | [FIXED-426](FIXED_ITEMS.md#fixed-426--a-thinking-budget-that-left-the-answer-nothing) |
| GCR-38, GCR-39 | Host-tick passes suppressed in silence; one task's exception skipped the rest of its batch | [FIXED-427](FIXED_ITEMS.md#fixed-427--a-background-pass-could-fail-every-fifteen-seconds-in-silence) |
| GCR-46 | A storage failure was reported as a model the owner never chose | [FIXED-433](FIXED_ITEMS.md#fixed-433--a-database-raiker-could-not-read-was-reported-as-a-model-the-owner-never-chose) |

**Still open, and next by the same order:** GCR-08 (transactional instance
creation), GCR-28 (local runtime slot concurrency), GCR-33 (OAuth refresh
single-flight), GCR-40 (event dual-write recovery), GCR-24/25 (a cancellable
conversion subprocess and an app-owned durable job runner), GCR-26, GCR-41, and
the P2 architecture work below them.

## Executive judgement

The deeper review changes the generic engineering risk assessment in one important way: there are now **several correctness and data-integrity issues that should be fixed before broad refactoring**.

The most serious newly identified issue is the model-conversion cleanup path. A failed or cancelled conversion stores its shared output directory as the operation's cleanup destination, and the cleanup endpoint recursively deletes that directory. If the directory already contains successful converted models, cleaning up one failed conversion can delete unrelated artifacts.

The second major theme is **state transition correctness**. Model-operation state is generally implemented as `load → replace → save` without compare-and-swap semantics. Cancellation, progress, completion, retry and concurrent workers can therefore overwrite one another. Similar lifecycle risks appear in managed local runtimes, OAuth refresh, event dual-writes, background workers and process/thread caches.

The third theme is **durability mismatch**: a number of operations are represented as durable database rows but execution is still attached to an in-process FastAPI background task or process-global object. A durable record does not by itself make execution restart-safe.

---

# Third-pass finding summary

| ID | Severity | Priority | Finding |
|---|---|---:|---|
| GCR-19 | Critical/High | P0 | Conversion partial-file cleanup can recursively delete unrelated models in a shared output directory — **Closed 2026-09-05 ([FIXED-420](FIXED_ITEMS.md#fixed-420--a-failed-conversions-cleanup-could-delete-every-model-beside-it))** |
| GCR-20 | High | P1 | Model-operation transitions are non-CAS and can lose cancellation or overwrite concurrent state — **Closed 2026-09-05 ([FIXED-421](FIXED_ITEMS.md#fixed-421--a-cancellation-could-be-overwritten-by-the-worker-it-cancelled))** |
| GCR-21 | High | P1 | Model-operation Retry can requeue non-terminal/running/completed work and dispatch a duplicate worker — **Closed 2026-09-05 ([FIXED-422](FIXED_ITEMS.md#fixed-422--retry-checked-the-kind-and-the-payload-and-never-the-state))** |
| GCR-22 | Medium/High | P1 | Initial Hugging Face download runs synchronously while retry uses a background worker — **Closed 2026-09-05 ([FIXED-423](FIXED_ITEMS.md#fixed-423--a-multi-gigabyte-download-ran-inside-the-request-that-asked-for-it))** |
| GCR-23 | High | P1 | Initial Hugging Face download can overwrite a concurrent cancel with `complete` — **Closed 2026-09-05 ([FIXED-421](FIXED_ITEMS.md#fixed-421--a-cancellation-could-be-overwritten-by-the-worker-it-cancelled))** |
| GCR-24 | Medium/High | P1 | Long model conversion is effectively non-cancellable during a subprocess that may run for hours |
| GCR-25 | Medium/High | P1 | Durable model-operation rows are executed by in-process background tasks; no startup recovery wiring was identified in the reviewed lifespan |
| GCR-26 | Medium/High | P1 | Conversion source fingerprint hashes names and sizes, not file contents |
| GCR-27 | High | P1 | GGUF shard grouping can merge same-named shards from different directories — **Closed 2026-09-05 ([FIXED-424](FIXED_ITEMS.md#fixed-424--two-models-one-folder-apart-were-indexed-as-one))** |
| GCR-28 | High | P1 | Managed llama.cpp/MLX runtime slot allocation and process maps are unsynchronized across concurrent deploys |
| GCR-29 | Medium | P2 | Managed llama.cpp custom-port launch can report the wrong endpoint |
| GCR-30 | Medium | P1/P2 | Provider `health()` can raise quota/workspace exceptions instead of returning `ProviderHealth` — **Closed 2026-09-05 ([FIXED-425](FIXED_ITEMS.md#fixed-425--a-method-whose-contract-was-to-return-health-raised-instead))** |
| GCR-31 | Medium/High | P1 | Anthropic budgeted-thinking clamp can produce an invalid budget equal to or larger than available output capacity — **Closed 2026-09-05 ([FIXED-426](FIXED_ITEMS.md#fixed-426--a-thinking-budget-that-left-the-answer-nothing))** |
| GCR-32 | Medium | P2 | Anthropic thinking-shape negotiation cache is process-global and keyed only by model name |
| GCR-33 | Medium/High | P1 | Concurrent OAuth refresh can race when providers rotate refresh tokens |
| GCR-34 | Medium | P2 | Connector response truncation occurs before JSON parsing and silently changes a large JSON result into a string |
| GCR-35 | Medium | P2 | Conversation-history budget can discard all history when the newest exchange alone exceeds the budget |
| GCR-36 | Medium | P2 | Conversation-history read failures silently become an empty conversation context |
| GCR-37 | Medium | P2 | SQLite connection cache uses recyclable numeric thread IDs as connection ownership identity |
| GCR-38 | Medium/High | P1 | Scheduler top-level work passes suppress unexpected exceptions without recording worker health — **Closed 2026-09-05 ([FIXED-427](FIXED_ITEMS.md#fixed-427--a-background-pass-could-fail-every-fifteen-seconds-in-silence))** |
| GCR-39 | Medium/High | P1 | One unexpected scheduled-task exception aborts the remainder of the claimed scheduler batch — **Closed 2026-09-05 ([FIXED-427](FIXED_ITEMS.md#fixed-427--a-background-pass-could-fail-every-fifteen-seconds-in-silence))** |
| GCR-40 | High | P1 | Event JSONL append and database index update are not atomic; integrity verification is blind to unindexed orphan lines |
| GCR-41 | Medium/High | P1/P2 | Release artifact reproducibility is undermined by unpinned dependency resolution and mutable external build-tool downloads |
| GCR-42 | Medium | P2 | Frontend API types are manually duplicated from backend DTOs instead of generated from the source contract |
| GCR-43 | Medium | P2 | `raiker/control/dashboard.py` is a ~400 KB multi-domain integration/god module |
| GCR-44 | Medium | P2 | API redaction buffering also copies large binary attachment preview/download responses |
| GCR-45 | Medium | P2 | Model-profile configuration resolution depends on process current working directory before packaged resources |
| GCR-46 | Medium | P2 | Configured-model storage failures are silently treated as “no configured model,” changing fallback/readiness behavior — **Closed 2026-09-06 ([FIXED-433](FIXED_ITEMS.md#fixed-433--a-database-raiker-could-not-read-was-reported-as-a-model-the-owner-never-chose))** |
| GCR-47 | Medium | P2 | Attached-root watcher can suppress cycle-level failures without updating any project health state |

---

# Detailed findings

## GCR-19 — Conversion cleanup can recursively delete unrelated models

**Severity: Critical/High — Priority: P0 — Confidence: High**

**Status: Closed 2026-09-05 — [FIXED-420](FIXED_ITEMS.md#fixed-420--a-failed-conversions-cleanup-could-delete-every-model-beside-it).**

### Evidence

`start_model_conversion()` persists the conversion payload with:

```python
"source": str(source),
"output": str(output),
"destination": str(output),
```

Here `output` is the approved model-library output **directory**, not a unique operation-owned directory.

`ModelOperationService.partial_files()` later takes `payload["destination"]` as the cleanup target. For a directory it recursively enumerates everything under that target and reports all of it as the operation's partial files.

`delete_partial_files()` then performs:

```python
if target.is_dir():
    shutil.rmtree(target)
else:
    target.unlink()
```

The only containment check is that the target is under an approved model-library root. It does not prove the directory or its existing contents were created by the failed operation.

`ModelConversionService` itself writes operation-specific files into the supplied shared output directory: `<source>-<revision>.bf16.gguf`, `<source>-<revision>.<quant>.gguf`, and provenance JSON.

### Failure scenario

1. `/models/converted` already contains one or more successful converted models.
2. A second conversion targets `/models/converted` and fails or is cancelled.
3. The operation becomes terminal and offers **Delete partial files**.
4. `partial_files()` identifies `/models/converted` itself as the cleanup target.
5. The confirmed cleanup calls `shutil.rmtree('/models/converted')`.
6. Previously successful, unrelated converted models are deleted with the failed operation's files.

### Required remediation

- Never persist a shared library directory as an operation-owned cleanup target.
- Persist the exact intermediate, result and provenance filenames produced by this operation, or allocate a unique staging directory per operation.
- Cleanup must delete only paths cryptographically/structurally bound to that operation.
- Before deletion, revalidate that each candidate remains inside the approved root and remains the exact path captured for that operation.
- Prefer staging + atomic move into the final library only after successful conversion.

### Required regression test

Create an output directory containing an unrelated successful model, start/fail another conversion into the same directory, invoke partial cleanup, and prove the unrelated files remain byte-for-byte intact.

---

## GCR-20 — Model-operation state transitions can overwrite each other

**Severity: High — Priority: P1 — Confidence: High**

**Status: Closed 2026-09-05 — [FIXED-421](FIXED_ITEMS.md#fixed-421--a-cancellation-could-be-overwritten-by-the-worker-it-cancelled).**

### Evidence

`ModelOperationService.running()`, `progress()`, `complete()`, `fail()`, `cancel()`, `cancelled()` and `retry()` all follow the same broad pattern:

1. load the operation row;
2. construct a replacement dataclass;
3. save the whole updated operation.

There is no expected-current-state/version argument visible in these service methods. `progress()` explicitly writes `state="running"`, while `cancel()` writes `state="cancel_requested"`.

### Failure scenario

A worker and a Cancel request race:

- request A reads state `running`;
- Cancel reads `running` and stores `cancel_requested`;
- request A stores its already-computed progress replacement with `state="running"`;
- the cancellation is lost.

The same class of race exists for completion/failure/retry.

### Required remediation

Implement the operation lifecycle as an atomic state machine in storage:

```text
queued -> running -> complete
                 -> failed
                 -> cancel_requested -> cancelled
failed/cancelled -> queued   (explicit retry only)
```

Each transition should be an `UPDATE ... WHERE operation_id=? AND state IN (...)` (or version/CAS update) and fail when the expected state has changed.

### Tests

Run progress, completion, cancellation and retry from racing workers and assert there is one legal terminal outcome and no lost cancellation.

---

## GCR-21 — Retry can dispatch duplicate/non-terminal work

**Severity: High — Priority: P1 — Confidence: High**

**Status: Closed 2026-09-05 — [FIXED-422](FIXED_ITEMS.md#fixed-422--retry-checked-the-kind-and-the-payload-and-never-the-state).**

`ModelOperationService.retry()` checks only that the kind is retryable and a payload exists. It does not require the current state to be `failed` or `cancelled`.

The API retry route calls `service.retry(...)` and immediately dispatches the worker by operation kind.

Consequently a retry against a running or even successfully completed retryable operation can requeue the row and start the work again. For downloads/conversions/deployments this can create duplicate expensive operations and conflicting writes.

**Fix:** only permit Retry from explicitly retryable terminal states, and claim the retry atomically so two simultaneous Retry requests cannot both dispatch.

---

## GCR-22 — Initial Hugging Face download blocks the request path

**Severity: Medium/High — Priority: P1 — Confidence: High**

**Status: Closed 2026-09-05 — [FIXED-423](FIXED_ITEMS.md#fixed-423--a-multi-gigabyte-download-ran-inside-the-request-that-asked-for-it).**

There is already a background worker `_run_hugging_face_download()` used when a failed operation is retried. However, the initial `/api/hugging-face/download` route performs `HuggingFaceService.download()` synchronously inside the request, rescans the model library and completes the durable operation before returning.

A multi-gigabyte snapshot can therefore occupy a request worker for the entire download and makes initial execution materially different from retry execution.

**Fix:** start the durable operation and dispatch the same worker used by Retry. Initial and retry behavior should be one implementation.

---

## GCR-23 — Initial Hugging Face download can lose cancellation

**Severity: High — Priority: P1 — Confidence: High**

**Status: Closed 2026-09-05 — [FIXED-421](FIXED_ITEMS.md#fixed-421--a-cancellation-could-be-overwritten-by-the-worker-it-cancelled).**

The initial download path writes `running`, performs the complete blocking snapshot download, rescans, and then calls `complete()` without checking `cancel_requested()`.

A concurrent Cancel can therefore set the row to `cancel_requested`, after which the request path writes `complete`. Combined with GCR-20's non-CAS updates, the final state can contradict the user's cancellation.

The retry worker at least checks cancellation before and after the blocking download, so the two paths already have different lifecycle semantics.

**Fix:** unify initial/retry workers and use atomic state transitions. For truly responsive cancellation, the underlying download also needs an interruptible execution mechanism.

---

## GCR-24 — Conversion can be unresponsive to Cancel for hours

**Severity: Medium/High — Priority: P1 — Confidence: High**

`_run_model_conversion()` checks cancellation immediately before and immediately after `service.convert(preview)`.

`DockerConversionRunner.run()` performs two blocking `subprocess.run()` calls. `ConversionIsolation.timeout_seconds` is six hours, and there is no cancellation handle checked while either subprocess is executing.

So a Cancel request can remain `cancel_requested` until a potentially multi-hour conversion step exits.

**Fix:** use `Popen`/managed process handles (or an equivalent cancellable job abstraction), persist the child/container identity, poll the cancellation flag, terminate the process tree/container on cancellation, and distinguish cancellation from conversion failure.

---

## GCR-25 — Durable model-operation rows do not make the workers durable

**Severity: Medium/High — Priority: P1 — Confidence: Medium/High**

Pull, conversion, deploy and retry execution are dispatched through FastAPI `BackgroundTasks` or in-process runtime objects. If the host process exits, the executable work disappears even though the operation row survives.

`ModelOperationService` contains `recover_abandoned()`, but no call to it was identified in the reviewed `create_app()` lifespan/startup path. That lifespan starts scheduler, approval-continuation and attached-root-watcher workers, but no model-operation worker/recovery loop was visible.

This creates a durability mismatch: the UI can retain a durable `running`/`queued` record for work whose process no longer exists.

**Fix:** make model operations owned by an application job runner with atomic claims/leases. On startup, reclaim or explicitly fail/requeue abandoned jobs. Persist enough worker identity to distinguish running, recoverable and abandoned work.

---

## GCR-26 — Conversion source fingerprint does not fingerprint source bytes

**Severity: Medium/High — Priority: P1 — Confidence: High**

`_source_fingerprint()` hashes:

- the declared revision;
- each relative filename;
- each file's byte size.

It does **not** hash file contents.

A source file can be modified while keeping the same path and byte length and produce the exact same source fingerprint. This makes the provenance record unsuitable as a content-integrity fingerprint.

**Fix:** hash the content of every source file included in the conversion, or use verified immutable per-file digests from a trusted manifest and bind those digests into the fingerprint.

---

## GCR-27 — GGUF shards from different directories can be merged into one model

**Severity: High — Priority: P1 — Confidence: High**

**Status: Closed 2026-09-05 — [FIXED-424](FIXED_ITEMS.md#fixed-424--two-models-one-folder-apart-were-indexed-as-one).**

`ModelLibraryService._index_root()` groups a sharded GGUF by `match.group("base")`. For a shard name such as `model-00001-of-00002.gguf`, the directory path is not included in that group key.

Therefore:

```text
root/A/model-00001-of-00002.gguf
root/A/model-00002-of-00002.gguf
root/B/model-00001-of-00002.gguf
root/B/model-00002-of-00002.gguf
```

are candidates for one shared `model` group rather than two directory-scoped models.

The code also takes the expected total from the first shard and does not visibly require every grouped shard to declare the same total.

**Impact:** wrong primary path, incorrect shard count/size/completeness, metadata from one model attached to files from another.

**Fix:** group on `(relative_parent_directory, base_name)` and require consistent declared shard totals before a set can be complete.

---

## GCR-28 — Managed local runtime slot allocation is not concurrency-safe

**Severity: High — Priority: P1 — Confidence: High**

`ManagedLlamaRuntime` and `ManagedMlxRuntime` keep `_processes` and `_model_paths` mutable dictionaries and choose a free slot by reading those maps. There is no lock/async serialization around `start()`, slot selection, stop, or map mutation.

The runtime objects live on `app.state` and background/synchronous routes can invoke deployments concurrently.

Two concurrent deployments can both observe the same slot as free, launch separate processes and then overwrite the single map entry. One process can become orphaned/untracked while both contend for the same port.

**Fix:** make slot reservation/start/stop atomic under a lock or actor/supervisor, reserve a slot before launching, and roll back the reservation on launch failure.

---

## GCR-29 — Custom llama.cpp port can be reported incorrectly

**Severity: Medium — Priority: P2 — Confidence: High**

`ManagedLlamaRuntime.start()` permits an explicit port. `_assign_slot()` maps a non-declared custom port onto the first logical slot and launches with `bound_port = port`.

`status()` does not retain that bound port. It reports:

```python
f"http://127.0.0.1:{slot.port}/v1"
```

using the declared slot port.

A runtime launched on a custom port such as 9000 can therefore report the first slot's standard endpoint (8080).

**Fix:** store the actual bound port/endpoint with the running process, or refuse ports outside the declared slot table.

---

## GCR-30 — Provider health contract can unexpectedly raise

**Severity: Medium — Priority: P1/P2 — Confidence: High**

**Status: Closed 2026-09-05 — [FIXED-425](FIXED_ITEMS.md#fixed-425--a-method-whose-contract-was-to-return-health-raised-instead).**

Both OpenAI-compatible and Anthropic provider `health()` implementations catch a selected list of provider exceptions and return `ProviderHealth`.

Their shared status classification can also raise other expected provider-domain exceptions such as quota exhaustion and workspace-required/invalid-workspace errors. Those classes are not included in the reviewed health catch lists.

Therefore a method whose interface normally returns `ProviderHealth` can instead propagate a normal provider-state exception.

**Fix:** define one complete provider-domain exception classification for health and test every status-mapper output against it.

---

## GCR-31 — Anthropic thinking budget clamp can create an impossible request

**Severity: Medium/High — Priority: P1 — Confidence: High**

**Status: Closed 2026-09-05 — [FIXED-426](FIXED_ITEMS.md#fixed-426--a-thinking-budget-that-left-the-answer-nothing).**

For the budgeted reasoning spelling, the code calculates:

```python
limit = request.max_tokens or self.max_tokens
budget_tokens = max(1024, min(budget, limit - 512))
```

The comment says the thinking budget must leave room for the answer. But if `limit == 1024`, this expression returns `1024`, leaving no room. For other small limits the hard `1024` floor can similarly exceed the available reasoning portion.

**Fix:** validate the total token budget before request construction. If the model requires a minimum thinking budget plus reserved answer tokens, either raise a clear configuration error or increase the request limit deliberately; never clamp upward beyond the available budget.

---

## GCR-32 — Anthropic thinking negotiation leaks across profiles/endpoints

**Severity: Medium — Priority: P2 — Confidence: High**

The negotiation result is stored in module-global:

```python
_NEGOTIATED_THINKING: dict[str, str]
```

and keyed only by model id.

Different Raiker instances, different Anthropic-compatible endpoints, or different provider configurations using the same model string therefore share one process-wide observed shape. A result learned from one endpoint can alter requests sent to another.

**Fix:** key negotiation by provider/profile + normalized endpoint + model/API version, and give the cache an explicit lifecycle/size bound.

---

## GCR-33 — OAuth refresh is vulnerable to refresh-token rotation races

**Severity: Medium/High — Priority: P1 — Confidence: High**

When a connector credential is expired, each invocation can independently call `_refresh_oauth()`. The refresh routine reads the same stored refresh token, performs an HTTP refresh and then overwrites the vault entry. There is no per-credential single-flight/lock/version check.

For providers that rotate refresh tokens, two simultaneous requests can both use token R0. The first refresh may invalidate R0 and store R1; the second can then fail or, depending on provider behavior, write stale/inconsistent credential state.

**Fix:** serialize refresh per `(principal, connector)`, reload/version-check the credential after acquiring the refresh lease, and perform the vault update with compare-and-swap semantics.

---

## GCR-34 — Connector truncation changes response type silently

**Severity: Medium — Priority: P2 — Confidence: High**

Both async and sync connector invocation paths do:

```python
raw = response.content[:200_000]
try:
    result = json.loads(raw)
except ...:
    result = raw.decode(... )[:20_000]
```

A perfectly valid JSON response larger than 200 KB is cut in the middle, fails JSON parsing, and is returned as a short string. The caller is not told that the source response was truncated or that a structured response became unstructured.

**Fix:** enforce an explicit response-size contract. Parse complete JSON only within the supported cap; if the upstream body exceeds the cap, return a typed `response_too_large`/truncated result with metadata rather than silently changing its type.

---

## GCR-35 — One oversized newest exchange can remove all conversation history

**Severity: Medium — Priority: P2 — Confidence: High**

`conversation_messages()` walks exchanges newest-to-oldest and does:

```python
if used + cost > char_budget:
    break
```

If the single newest completed exchange exceeds the entire history budget, `kept` remains empty and the loop stops. Older short exchanges that would fit are never considered.

**Fix:** handle an oversized newest exchange explicitly: truncate/summarize it to a safe size or skip only that exchange and continue evaluating older entries, depending on intended semantics.

---

## GCR-36 — History storage failure silently turns a follow-up into a first-turn-like request

**Severity: Medium — Priority: P2 — Confidence: High**

`conversation_messages()` catches every exception from `store.list_turns(...)` and returns `[]` with no diagnostic/event.

That keeps a provider call alive, but it changes semantic behavior: a database/read problem becomes “there was no prior conversation.” The model can then answer a follow-up without the conversation context while neither operator nor user is told why.

**Fix:** distinguish “no history” from “history unavailable.” At minimum emit a health/audit diagnostic and surface degraded context; for Build/high-consequence turns consider failing the context assembly instead of silently proceeding.

---

## GCR-37 — SQLite cached connection ownership relies on recyclable thread IDs

**Severity: Medium — Priority: P2 — Confidence: Medium/High**

The SQLCipher connection cache key is:

```python
(workspace_root, threading.get_ident())
```

and cached connections use `check_same_thread=False` so shutdown/invalidation can close them from another thread.

Thread identifiers are numeric identities that can be reused after a thread exits. `connect()` looks up the current numeric key before orphan reaping. If a new worker receives a recycled ID, it can match a connection created by an exited worker and reuse its connection/session state.

**Fix:** make connection ownership thread-local or key by a non-recyclable lifetime token/weak `Thread` identity, with a separate central registry only for shutdown/invalidation.

---

## GCR-38 — Scheduler failures are suppressed without worker-health evidence

**Severity: Medium/High — Priority: P1 — Confidence: High**

**Status: Closed 2026-09-05 — [FIXED-427](FIXED_ITEMS.md#fixed-427--a-background-pass-could-fail-every-fifteen-seconds-in-silence).**

The root FastAPI lifespan loops through scheduler work with separate blocks such as:

```python
with suppress(Exception):
    await scheduler.run_due()
```

and likewise suppresses unexpected exceptions from approval continuation, model-capacity refresh and telemetry delivery.

Isolation between passes is good, but the outer suppression records no log entry, error counter, degraded health state or retry reason. A systemic scheduler bug can fail every 15 seconds while the host appears healthy.

**Fix:** keep pass isolation but catch-and-record exceptions. Maintain scheduler subsystem health (`last_success`, `last_error_class`, consecutive failures), log bounded diagnostics, and expose degraded state to health/dashboard.

---

## GCR-39 — One scheduled-task exception aborts the remainder of the batch

**Severity: Medium/High — Priority: P1 — Confidence: High**

**Status: Closed 2026-09-05 — [FIXED-427](FIXED_ITEMS.md#fixed-427--a-background-pass-could-fail-every-fifteen-seconds-in-silence).**

`TaskScheduler.run_due()` claims a collection of due tasks, then iterates them without a per-task `try/except` around the full turn execution. A provider/storage/runtime exception from one `AgentGateway.submit_prompt_async()` therefore escapes `run_due()`.

The outer lifespan catches/suppresses that exception (GCR-38), which protects the host but stops processing the remaining tasks in the already-returned batch.

**Fix:** contain failures per claimed task, transition that task to a stated failure/retry state, and continue the rest of the batch. Add a test where the first claimed task throws and the second still executes exactly once.

---

## GCR-40 — Event JSONL and database index can diverge permanently

**Severity: High — Priority: P1 — Confidence: High**

`EventLogWriter.append()` performs two different persistence writes while holding the session lock:

1. append and flush the serialized event to the JSONL file;
2. call `store.index_event(...)` to record offset/hash/index metadata in SQLCipher.

These are not one atomic transaction. If the file append succeeds and the database index write fails, the JSONL contains an orphan event that the database does not know about.

The reviewed integrity verifier starts from `store.list_session_events_for_integrity(session_id)` and then reads each indexed line by stored offset. It does not scan the JSONL for lines absent from the database. Therefore that orphan is invisible to the integrity result itself.

A subsequent append also obtains `prev_hash` from the database, not from the orphan line, so the physical JSONL and indexed hash-chain view can diverge.

**Fix options:**

- make SQLCipher the authoritative append store and derive/export JSONL;
- use an append journal/outbox with reconciliation on startup;
- record pending index intent before file append and finalize atomically enough to recover;
- extend integrity/recovery to detect extra/unindexed JSONL lines.

Fault-injection tests should fail immediately after file flush and immediately before/inside index commit.

---

## GCR-41 — Release reproducibility has mutable dependency/tool inputs

**Severity: Medium/High — Priority: P1/P2 — Confidence: High**

The release code carefully normalizes archive timestamps and uses `SOURCE_DATE_EPOCH`, but the build inputs are not fully reproducible:

- Python runtime/dev dependencies are broad version ranges rather than a hash-locked release constraints set.
- The release workflow runs `pip install -e ".[dev]"` and `pip wheel .` at release time, allowing the resolver result to change as registries change.
- Linux `appimagetool` is fetched from the GitHub `continuous` release URL without a pinned artifact digest.

Two builds of the same source commit at different dates can therefore contain different dependency wheels or build-tool bytes even though the ZIP metadata is deterministic.

**Fix:** generate target-specific hash-locked constraints/wheel manifests, use those exact artifacts in release builds, pin external build tools by immutable version + SHA-256, and record the resolved dependency/tool manifest in the release provenance.

---

## GCR-42 — Frontend contracts are manually mirrored instead of generated

**Severity: Medium — Priority: P2 — Confidence: High**

`apps/web/src/lib/apiTypes.ts` is roughly 94 KB and explicitly states that the interfaces “mirror the backend DTOs; the backend remains the source of truth.” `apps/web/src/lib/api.ts` is also roughly 95 KB.

A backend test guards selected fields the UI reads, but this is still a manually maintained duplicate contract. Combined with GCR-15 (web CI does not run for backend-only API changes), the system can drift in field type, nullability, enum values or request shapes even when each side type-checks independently.

**Fix:** generate TypeScript types/client contracts from the FastAPI OpenAPI/JSON Schema (or another canonical shared schema), and make contract generation/diff a backend CI gate.

---

## GCR-43 — Dashboard control layer has become a ~400 KB integration hub

**Severity: Medium — Priority: P2 — Confidence: High**

`raiker/control/dashboard.py` is about 399 KB and imports/coordinates models, execution profiles, policy, tasks, connectors, memory, code repositories, hooks, security monitoring, model facts, files and other domains.

This is larger than a normal service boundary and creates a high-conflict integration surface: unrelated features modify the same module, domain invariants are difficult to isolate, and tests must instantiate a broad dependency graph.

This complements GCR-11 (`sqlite.py`, approximately 568 KB): storage and dashboard read/control logic are both accumulating platform-wide responsibilities.

**Fix:** split dashboard behavior into domain read-model/services (`models`, `tasks`, `connections`, `projects`, `memory`, `extensions`, etc.) behind a thin compatibility facade. Do not rewrite behavior while splitting; characterization tests should precede movement.

---

## GCR-44 — Redaction middleware duplicates large binary response bodies

**Severity: Medium — Priority: P2 — Confidence: High**

GCR-13 identified that `RedactionMiddleware` buffers almost every `/api` response. The deeper pass found that this includes binary attachment preview/download routes because only a small fixed set of API paths are exempted.

PDF/image preview and attachment download already hold complete bytes to construct a `Response`. The redaction middleware then appends body chunks into a `bytearray`, converts it to `bytes`, attempts JSON parsing, and emits the raw body when it is not JSON.

For documents up to the attachment cap, this creates avoidable extra memory copies and prevents streaming semantics even though binary bytes cannot be JSON-redacted.

**Fix:** make redaction content-type aware. Only buffer JSON responses that actually require field redaction; pass through known binary/media/export responses directly, with redaction applied at their structured metadata/source stage.

---

## GCR-45 — Built-in model profile selection depends on current working directory

**Severity: Medium — Priority: P2 — Confidence: High**

`ModelProfileRegistry.load()` defaults to `config/model-profiles.json`. `_config_path()` resolves an existing relative path/current-working-directory candidate before the repository/package fallback or packaged resource.

For an installed desktop application, current working directory is incidental process state, not a configuration boundary. Starting Raiker from a directory that happens to contain `config/model-profiles.json` can therefore select that file instead of the packaged built-in registry.

This also makes behavior differ between launch methods and can accidentally pick up stale checkout/config files.

**Fix:** make built-in registry resolution package-resource deterministic. If overrides are supported, require an explicit override path/config setting/environment variable and report it as the source.

---

## GCR-46 — Configured-model read errors are treated as an absent choice

**Severity: Medium — Priority: P2 — Confidence: High**

**Status: Closed 2026-09-06 — [FIXED-433](FIXED_ITEMS.md#fixed-433--a-database-raiker-could-not-read-was-reported-as-a-model-the-owner-never-chose).** The fix is the one proposed: `configured_model_store_unavailable` is a distinct outcome from an absent pin, raised by the single reader all three call sites now share, and readiness reports it as its own `configuration_unreadable` state rather than resolving a model it cannot know.

Both `AgentGateway._configured_model()` and `ModelReadinessService._configured_model()` catch broad exceptions from the configured-model store and return `None`.

For placeholder profiles, `None` means the profile can disappear from fallback resolution/readiness as if the owner never configured it. A storage failure therefore changes model selection rather than surfacing a degraded configuration state.

**Fix:** distinguish `configured_model_missing` from `configured_model_store_unavailable`. The former can return `None`; the latter should create a named degraded/error result and must not silently rewrite the effective model/fallback chain.

---

## GCR-47 — Attached-root watcher can lose cycle-level failure observability

**Severity: Medium — Priority: P2 — Confidence: High**

`AttachedRootWatcher.run()` wraps each `_cycle(stop)` in `with suppress(Exception)`. Project-specific `_reconcile()` failures are recorded in `WatchState`, which is good. But exceptions that occur before a project-specific reconcile can record failure — for example while enumerating indexed roots or setting up the cycle — are swallowed at the outer level with no watcher-wide degraded state.

The loop continues, but the interface can keep the last project `WatchState` without knowing the watcher itself is repeatedly failing before it reaches those projects.

**Fix:** add watcher subsystem health independent of per-project scan state and record/log every unexpected cycle-level exception with consecutive-failure/backoff information.

---

# Cross-cutting conclusions from all three generic passes

## 1. Make durable state transitions atomic

A recurring source of defects is a persisted object with an in-memory `load → modify → save` lifecycle. For operations, tasks, approvals, schedules and other long-running work, prefer storage-owned atomic transition methods with expected-state/version conditions.

Every durable workflow should answer these questions mechanically:

- who owns the claim now?
- which states may transition to which states?
- what happens if two callers transition at once?
- what proves a worker is still alive?
- what happens after process restart?
- how is cancellation prevented from being overwritten?

## 2. Separate operation-owned artifacts from shared roots

Never use a shared model-library/project/output directory as an operation's deletion boundary. A destructive cleanup must enumerate an operation-owned manifest or unique staging directory.

## 3. Application lifecycle should own long-running resources

Provider clients, background jobs, schedulers, watchers, managed local model processes and connector refresh coordination should have explicit app/instance lifecycle ownership. Process globals and incidental FastAPI `BackgroundTasks` are appropriate for small ephemeral work, not durable platform subsystems.

## 4. Treat failure visibility as part of correctness

Best-effort components may continue after failure, but “continue” and “pretend nothing failed” are different choices. Scheduler/watcher/history failures should result in bounded diagnostics and a degraded state that the owner/operator can inspect.

## 5. Reduce duplicated sources of truth

The deeper review found several duplicated contracts/state resolvers:

- backend DTOs vs manually mirrored TypeScript interfaces;
- multiple model-target/configured-model resolution paths;
- initial vs retry Hugging Face execution;
- provider creation/validation paths;
- dashboard-wide cross-domain orchestration;
- file event log vs SQL event index.

Where two paths are meant to mean the same thing, make one implementation authoritative.

---

# Updated remediation order — priority first, then effort

The order below combines the new third-pass findings with the most important first-pass generic findings. P0/P1 correctness/data-integrity work precedes architecture cleanup.

| Order | Finding | Priority | Effort | Recommended action |
|---:|---|---:|---|---|
| 1 | GCR-19 conversion cleanup data loss | **P0** | Low-Medium | Stop directory-wide deletion; persist exact operation-owned artifacts/staging dir — **Closed** |
| 2 | GCR-20 operation CAS/state machine | P1 | Medium | Atomic expected-state transitions — **Closed** |
| 3 | GCR-21 retry state validation | P1 | Low | Retry only failed/cancelled and atomically claim — **Closed** |
| 4 | GCR-23 HF cancel overwrite | P1 | Low-Medium after GCR-20 | Unify worker + CAS completion — **Closed** |
| 5 | GCR-01 provider launch configuration | P1 | Low | Route validation through `_factory(profile)` — **Closed** |
| 6 | GCR-02 provider client leak | P1 | Low | Avoid constructing transport for validation or close it deterministically — **Closed** |
| 7 | GCR-03 reasoning profile mismatch | P1 | Low | Resolve actual selected/default profile — **Closed** |
| 8 | GCR-27 GGUF shard grouping | P1 | Low-Medium | Include relative parent + validate shard totals — **Closed** |
| 9 | GCR-30 provider health exception completeness | P1/P2 | Low | Complete health classification tests — **Closed** |
| 10 | GCR-31 Anthropic budget clamp | P1 | Low | Validate minimum reasoning/output budget — **Closed** |
| 11 | GCR-06 global command workspace | P0/P1 | Medium | Pass workspace explicitly; remove mutable global — **Closed** |
| 12 | GCR-08 transactional instance creation | P1 | Medium | Stage/register then publish/mount atomically |
| 13 | GCR-28 local runtime concurrency | P1 | Medium | Atomic slot supervisor |
| 14 | GCR-33 OAuth refresh single-flight | P1 | Medium | Per-credential lease/CAS refresh |
| 15 | GCR-38 scheduler health visibility | P1 | Low-Medium | Record/log pass failures and degraded health — **Closed** |
| 16 | GCR-39 per-task scheduler containment | P1 | Low-Medium | Catch/land failures per claimed task — **Closed** |
| 17 | GCR-40 event dual-write recovery | P1 | Medium-High | Journal/reconcile or choose one authoritative store |
| 18 | GCR-22 initial HF background execution | P1 | Medium | Use one durable worker for initial/retry — **Closed** |
| 19 | GCR-24 cancellable conversion | P1 | Medium-High | Managed process/container handle + cancellation |
| 20 | GCR-25 durable operation runner/recovery | P1 | High | App-owned job leases/restart recovery |
| 21 | GCR-26 content-valid provenance fingerprint | P1 | Medium | Hash source content/trusted file digests |
| 22 | GCR-41 reproducible dependency/tool inputs | P1/P2 | Medium | Hash-locked constraints + pinned build tools |
| 23 | GCR-07 instance lifecycle manager | P1 | Medium-High | Parent-owned lifecycle for mounted instances |
| 24 | GCR-09 instance registry/router serialization | P1 | Medium | Atomic registry + serialized route changes |
| 25 | GCR-10 bootstrap hot-path cost | P1 | Medium | Bootstrap once per workspace/schema lifecycle |
| 26 | GCR-05 sync/async bridge blocking | P1 | Medium | Async all the way through request path |
| 27 | GCR-34 explicit connector response-size contract | P2 | Low-Medium | Reject/type truncated responses explicitly |
| 28 | GCR-35/GCR-36 history degradation behavior | P2 | Low-Medium | Preserve usable context + surface degraded history |
| 29 | GCR-44 content-type-aware redaction | P2 | Medium | Do not buffer binary API responses |
| 30 | GCR-42 generated frontend contracts | P2 | Medium | Generate TS/OpenAPI types and run contract CI |
| 31 | GCR-45 deterministic config source | P2 | Low-Medium | Explicit override, packaged default |
| 31a | GCR-46 configured-model store failure | P2 | Low | Name the unreadable store; never resolve a model from it — **Closed** |
| 32 | GCR-43 dashboard decomposition | P2 | High | Characterize then split by domain |
| 33 | GCR-11 storage decomposition | P2 | High | Repositories/migration runner over smaller core |

---

# Required third-pass regression/fault-injection suite

Before closing these findings, add tests that deliberately exercise the failures rather than only happy paths:

1. failed conversion cleanup with unrelated files in the same output root;
2. cancel vs progress/complete races for every model operation kind;
3. two concurrent Retry requests;
4. host restart during queued/running pull, download, deploy and conversion;
5. two simultaneous local model deployments competing for one slot;
6. same GGUF shard basename in two subdirectories;
7. Anthropic reasoning with small `max_tokens` and negotiated budgeted thinking;
8. all provider status-mapper exception classes through `health()`;
9. concurrent rotating OAuth refresh;
10. connector JSON body just below, equal to and above response cap;
11. oversized newest conversation exchange with older history that fits;
12. injected history-store exception and explicit degraded-state assertion;
13. scheduler batch where first task throws and second succeeds;
14. injected exception in each scheduler pass with health/log assertion;
15. event writer failure after JSONL flush but before SQL index commit;
16. event integrity check with an unindexed extra JSONL line;
17. repeated same-commit release builds using an offline locked dependency/tool set;
18. backend DTO/schema change that must trigger/regenerate frontend contracts.

---

# Final third-pass assessment

Raiker's main codebase has strong defensive intent, broad tests and unusually explicit implementation rationale. The deeper review nevertheless found that the next quality step should not be adding more abstraction first. It should be **closing correctness seams around destructive cleanup, atomic state transitions, durable-worker ownership, concurrency and authoritative sources of truth**.

The most urgent rule is:

> **A persisted operation may modify or delete only artifacts it can prove it owns, and no concurrent or restarted worker may overwrite a newer human/system state transition.**

Once GCR-19 through the core P1 lifecycle findings are closed with adversarial tests, the larger decomposition work (`sqlite.py`, dashboard control, frontend API contracts) becomes substantially safer to undertake.