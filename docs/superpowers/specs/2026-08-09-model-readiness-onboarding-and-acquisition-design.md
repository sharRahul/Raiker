# Model Readiness, Onboarding, and Acquisition Design

**Roadmap item:** BUG-69 — A new user's first message fails with a raw reason code

**Related defect:** BUG-48 — setup wizard remainder

**Status:** Approved design, pending implementation

**Date:** 2026-08-09

## Purpose

Raiker currently treats a concrete configured model name as proof that its provider is
usable. FIXED-116 made Ollama `gemma4:31b-cloud` the preferred first-run selection, but
an absent or stopped Ollama service is still shown as ready. The first attempted turn
then fails with `provider_error_unclassified`. The same false readiness can affect every
model-backed surface, not only Chat.

BUG-69 closes this as one product-wide contract. A provider/model pair becomes usable
only after Raiker has proved that the exact pair is reachable. Workbench, Chat, Build,
Tasks, schedules, and background work consume the same readiness state. First run guides
the owner to a working hosted or local provider. Models can install or connect local
runtimes, discover existing GGUF libraries, acquire models from Hugging Face, convert
supported weights locally, and deploy a selected model without silently copying files,
accepting licences, executing repository code, or widening network access.

## Goals

- Define one server-owned readiness contract for an exact provider, profile, and model.
- Disable every model-backed action until its selected pair is ready.
- Show one shared no-model dialog with a direct Models setup action on every surface.
- Run first-start provider setup after owner registration and keep it resumable/skippable.
- Support hosted credentials, an existing local runtime, and owner-approved installation.
- Automate the official Ollama installer with explicit consent; never bundle it.
- Direct the owner through LM Studio's official installer, or explicitly invoke its
  published `llmster` installer, without redistributing proprietary binaries.
- Discover models through Ollama, LM Studio, supported third-party libraries, and
  owner-approved folders without scanning the whole machine.
- Deploy existing GGUF files in place through a Raiker-managed llama.cpp runtime by
  default, with explicit LM Studio and Ollama import alternatives.
- Search Hugging Face, compare downloadable GGUF variants, download exact revisions,
  and optionally convert supported Safetensors repositories locally.
- Preserve provider policy, vault encryption, owner authority, model licences, source
  provenance, and fail-closed behavior.

## Non-goals

- Certifying that a model licence permits a particular use.
- Accepting Hugging Face gated-repository terms for the owner.
- Redistributing LM Studio or its desktop installer.
- Silently installing software, downloading weights, moving models, or consuming disk.
- A blind whole-disk or network-drive search for model files.
- Executing Hugging Face repository Python code or enabling `trust_remote_code`.
- Converting every architecture published on Hugging Face.
- Loading pickle-based weights as part of the conversion path.
- Treating file presence, saved credentials, or a configured model name as readiness.
- Silently switching to a hosted provider when a local provider stops.

## Considered approaches

### Server-owned readiness plus shared UI gate — selected

The API probes exact provider/model pairs, persists bounded health observations, and
returns one readiness DTO consumed by all surfaces. The browser never invents health
from configuration. Local discovery and acquisition feed the same catalogue, and every
deployment must pass the same probe before selection becomes actionable. This creates
one honest boundary and supports non-browser clients.

### Browser-only checks — rejected

Each composer could call the existing model-list endpoint before submitting. This would
duplicate behavior, miss schedules and background execution, create race conditions,
and leave API/CLI callers able to submit work against a known-unready provider.

### Start a turn and translate the failure — rejected

Mapping the raw reason code would improve the transcript but still allow doomed tasks
and schedules to be created. It would also count an absent provider as set up and make
the owner's first interaction a failure instead of an onboarding decision.

## Scope and delivery order

BUG-69 is implemented as four ordered increments. Each increment is independently
testable, but the defect is not closed until all four ship.

1. **Readiness contract and cross-surface gate.** Correct the false ready state and stop
   all model-backed submission paths before a doomed request is created.
2. **First-run and Models onboarding.** Guide the owner through hosted connection or
   local runtime setup using the same readiness proof.
3. **Local discovery and deployment.** Index existing libraries and run approved GGUF
   files through a managed local runtime.
4. **Hugging Face acquisition and conversion.** Download existing GGUF first; expose
   bounded local conversion only when no suitable GGUF is available.

## Architecture

### Exact model readiness

A focused model-readiness service owns probing and normalization. Its key is
`(owner_principal_id, profile_id, model, endpoint_fingerprint)`. The endpoint
fingerprint is derived from redacted connection configuration so changing an endpoint
or credential invalidates prior readiness without storing a secret.

The public state is one of:

- `not_configured`: no concrete model or required connection exists;
- `checking`: an owner-visible probe is in progress;
- `ready`: the provider answered and exposed or accepted the exact model;
- `runtime_missing`: the local runtime executable is absent;
- `runtime_stopped`: the executable exists but its loopback service is not ready;
- `model_missing`: the provider is reachable but the selected model is unavailable;
- `policy_blocked`: provider policy prevents the probe or use;
- `authentication_failed`: the saved credential was refused;
- `unreachable`: the endpoint did not answer within the bounded timeout;
- `unsupported`: the selected model/runtime combination cannot be used;
- `stale`: the last successful probe no longer satisfies the freshness window.

Every result carries profile/model identity, checked time, expiry time, plain-language
summary, stable reason code, remediation action, and a redacted evidence summary. It
never carries a credential, full endpoint with secrets, model content, or provider
response body.

Local loopback providers are probed at startup, after install/start/pull/import, after
selection, and when a model-backed action asks for readiness. Hosted providers are
probed only after explicit connection/testing or when their cached result is stale;
Raiker does not create background billable inference. A non-billable catalogue or
provider-supported health call is preferred. The submission boundary always rechecks
the stored state's identity and freshness and may perform one bounded non-billable
probe. A stopped runtime immediately invalidates readiness.

`configured` continues to mean configuration exists. `ready` alone means usable. The
Models setup counter counts ready providers, and composers list configured choices with
their readiness rather than filtering failures out of sight.

### Shared submission boundary

One browser component and one server guard enforce the contract.

The shared browser guard wraps model-backed actions in Workbench, Chat, Build, Tasks,
schedule creation, and background-agent creation. With no ready selection, the primary
action is disabled. Activating its adjacent explanation, selecting an unready model, or
arriving at a stale selection opens a dialog that states:

> No model is ready. Set up or start a provider before Raiker can run this work.

The dialog names the selected provider when one exists, explains its current state, and
offers **Set up models** (`#/models`) plus **Check again** where a probe is possible.
There is no raw reason code in the main copy; it remains available in a details region.

The server rejects stale or unready submissions with a structured
`model_not_ready` response containing the same state and remediation. This applies to
prompt creation, Build turns, task creation that requests execution, schedules, and
background agents. Draft text, attachments, task fields, and schedule fields remain in
the browser when the dialog opens. Read-only navigation and creation of a deliberately
unscheduled non-agent task remain available because they do not invoke a model.

### First-run onboarding

After the first owner completes registration, Raiker opens a resumable setup flow before
the Workbench. Existing owners are not forced back into it. The flow can be skipped,
but the product remains honestly disabled and every model-backed surface reopens the
shared setup dialog until a model is ready.

The steps are:

1. Explain local versus hosted privacy, connectivity, cost, and storage.
2. Detect already-running supported providers and existing configured credentials.
3. Offer **Connect hosted provider**, **Use existing local runtime**, **Install local
   runtime**, and **Choose model files already on this device**.
4. Configure or acquire an exact model.
5. Run the readiness probe and show its evidence.
6. Select the ready pair and finish into Workbench.

The wizard and Models page use the same components and APIs. Models remains the place to
repeat installation, connection, discovery, download, import, and repair later.

### Runtime installation and lifecycle

Installation is a governed host action with an explicit review screen showing vendor,
official source URL, version when known, download size when known, destination,
privilege requirement, terms link, and requested commands. The owner confirms before
download and again before an elevation boundary. Progress, cancellation, failure, and
retry are visible and audited without recording command secrets.

- **Ollama:** download the official platform installer at runtime, verify the vendor
  source and available signature/checksum, launch it with owner consent, then detect the
  CLI/service. Raiker does not bundle the installer. Installed models are listed through
  Ollama's API; pulls use its streaming API with progress and cancellation.
- **LM Studio desktop:** open the vendor's official download/install experience. Raiker
  does not download or redistribute the proprietary desktop binary.
- **LM Studio headless (`llmster`):** show and, after explicit consent, invoke the
  vendor-published platform installer. After installation, use `lms` to list, download,
  load, unload, and start the loopback server.
- **llama.cpp:** acquire an official release or supported package-manager installation
  under its MIT licence. Raiker manages `llama-server` as a child service bound to
  `127.0.0.1`, with an explicit model path, bounded context, resource settings, logs,
  readiness, restart, and stop controls.

Raiker never silently falls back from a failed installation to another runtime.

### Local model discovery

The local model-library service uses source adapters:

- Ollama `/api/tags` for Ollama-owned models;
- `lms ls --json`, or the local LM Studio REST API, for LM Studio-owned models;
- supported third-party library adapters for their documented indexes or model roots;
- llama.cpp and Hugging Face caches where their configured/standard location is detected;
- owner-added folders selected through a native directory picker.

Detected standard directories are offered for approval; they are not scanned until the
owner approves each root. Raiker never scans an entire drive, network share, backup
root, workspace, or home directory by default. The owner can pause, remove, or rescan a
root and can see which files it contributed.

The indexer follows no directory symlink outside an approved root. It reads bounded
GGUF headers and filesystem metadata only. It recognizes single files, split shards,
multimodal projector companions, and incomplete sets. Stored records contain source
adapter, owner-approved root ID, canonical path encrypted at rest, size, modification
time, bounded fingerprint, architecture, model role, parameter/quantization metadata,
context facts, embedded source/licence metadata, and validation state. It never stores
tensor data in the database.

### Local deployment

Discovery never moves a file. The owner chooses a deployment:

- **Use in place with managed llama.cpp — default.** Launch the exact existing GGUF or
  a llama.cpp router over an approved model directory. This avoids duplicate storage.
- **Use through LM Studio.** Reuse an LM Studio-owned entry, or preview
  `lms import --dry-run` and then explicitly choose hard link, symbolic link, or copy.
  A move is never offered as the default.
- **Import into Ollama.** Generate a reviewable Modelfile and use Ollama's supported
  create path. Show projected additional storage and preserve source provenance.

Before launch, Raiker checks file completeness, available memory/disk, runtime support,
and owner-selected context/resource limits. Model weights are untrusted data: launch is
isolated to the local runtime boundary, repository code is not executed, invalid models
fail as findings, and crashes cannot make the pair ready. Only a successful exact-model
probe exposes the selection to model-backed actions.

### Hugging Face catalogue and acquisition

Models adds a Hugging Face source with search and direct repository URL input. A token,
when needed, is encrypted in the existing vault and never placed in logs, browser
storage, commands, screenshots, or model context.

The catalogue shows repository owner, exact revision, update time, architecture,
parameters, modalities, context metadata, licence identifier/text link, gated status,
available GGUF files, quantization, shard set, file size, cache reuse, and estimated
RAM/VRAM/disk fit. Unknown facts remain unknown.

The default ordering is:

1. publisher-provided or repository-provided complete GGUF variants;
2. local conversion from supported Safetensors only when no suitable GGUF exists;
3. download-only for files the owner wants to retain without deployment.

Every download begins with a dry run. The owner chooses exact revision, files,
destination library, and intended runtime and sees download bytes, cached bytes,
temporary conversion space, final space, and available disk. Downloads use the official
Hugging Face client, retain its revision-aware cache, resume safely, verify expected
file metadata, expose progress/cancel/retry, and never mutate cached source files.

Gated repositories open the official browser acceptance page. Raiker waits for the
owner to return with authorized access and never submits acceptance or personal data.
Unknown/custom licences require acknowledgement; Raiker records the source and the
owner's acknowledgement but makes no legal-use judgement.

### Local conversion and quantization

The conversion worker is version-pinned, no-network after acquisition, resource-bounded,
and isolated from the workspace and credentials. It receives a read-only source snapshot
and one writable output directory. It never enables `trust_remote_code`, imports Python
from the model repository, or accepts pickle `.bin` weights. Only architectures
supported by the pinned reviewed llama.cpp converter are eligible.

The pipeline is:

1. pin and record the repository commit;
2. dry-run the exact filtered Safetensors/config/tokenizer download;
3. check source, temporary, and final disk requirements;
4. download and validate the immutable source snapshot;
5. convert to a high-precision GGUF;
6. quantize to the owner-selected supported format;
7. validate GGUF metadata, shard/projector completeness, and output fingerprint;
8. register source-to-output provenance;
9. deploy using the normal local deployment path;
10. run the exact-model readiness probe;
11. offer owner-approved cleanup of intermediate files.

The selection UI describes Q4_K_M as the balanced recommendation, with larger quality/
resource alternatives such as Q5_K_M, Q8_0, and high precision only when the converter
supports them. Estimates are calculated from actual source/variant metadata. Unsupported
architectures say why conversion is unavailable and keep existing GGUF/download-only
options visible.

## API and persistence contract

New focused contracts cover:

- list/read/refresh exact model readiness;
- start/cancel an explicit readiness check;
- read first-run setup state and complete/skip/resume a step;
- detect runtime installations and control permitted local lifecycle actions;
- list/add/remove/rescan approved model-library roots;
- list discovered local models and their validation/deployment state;
- preview/start/cancel runtime install, pull, import, download, conversion, and cleanup;
- search/read Hugging Face repositories and variants;
- stream bounded operation progress; and
- select a model only with an exact ready result.

Long operations use durable job rows with typed state, progress, redacted source,
requested output, timestamps, cancellation state, bounded failure reason, and owning
principal. Restart recovery marks abandoned child processes honestly and resumes only
downloads supported by the underlying client. Install and conversion jobs cannot be
started by an AI-agent principal.

Readiness observations and discovery records are owner/workspace scoped. File paths are
never returned outside the authorized owner session. Credential and endpoint changes,
runtime stop, model deletion, file fingerprint change, or deployment change invalidates
the affected ready state.

## Error handling

All errors provide plain-language copy, a stable reason code in details, and one safe
next action. Required cases include absent runtime, stopped runtime, missing model,
unsupported architecture, incomplete shards/projector, insufficient disk/RAM, policy
denial, invalid credential, gated access pending, unknown licence, download checksum or
revision mismatch, cancelled job, conversion failure, runtime crash, and stale probe.

`provider_error_unclassified` never appears as transcript text. Unknown provider
exceptions map to a provider-named unavailable response and retain a correlation ID for
Diagnostics. No failure silently changes provider, starts a billable call, deletes a
download, or removes an original model.

## User experience

Models gains consistent **Providers**, **On this device**, and **Hugging Face** setup
entry points while retaining the current provider cards and pricing/routing controls.

- Provider cards distinguish `Preferred`, `Configured`, and `Ready`.
- The setup meter counts ready providers only.
- Every model picker shows a readiness badge and keeps unready choices visible with a
  repair action.
- Downloads and conversions have progress, pause/cancel where supported, retry, disk
  accounting, and a persistent operation history.
- Local libraries show their approved root, source application, deployment runtime, and
  whether use is in place, linked, copied, or imported.
- All dialogs preserve keyboard focus, have screen-reader status announcements, work at
  existing responsive breakpoints, and support light/dark/system themes.

## Security, privacy, and legal boundaries

- Network access is explicit and limited to official/vendor endpoints required for the
  chosen install or download.
- Installer source and planned command are shown before consent; elevation is separate.
- Vendor binaries are not bundled. LM Studio binaries are never redistributed.
- Hugging Face tokens stay encrypted and are passed in process memory, not arguments.
- Repository code is data, never executable input.
- Conversion has no network and no access to the workspace, vault, or unrelated models.
- Discovery scans only approved roots and bounded headers.
- Original model files and caches are immutable unless the owner explicitly approves a
  documented import or cleanup operation.
- Model licence presentation is informational. The owner accepts repository terms and
  decides permitted use; Raiker records provenance and acknowledgement.
- Downloaded model weights remain subject to their own licences regardless of runtime.

## Testing strategy

### Unit and integration tests

Tests follow red-green-refactor and cover:

- every readiness state, transition, freshness rule, and invalidation trigger;
- exact model/endpoint binding and secret-free serialization;
- configured-versus-ready counts and model-picker projection;
- server rejection for every model-backed submission surface;
- draft/attachment/form preservation when setup is required;
- first-owner wizard start, skip, resume, finish, and existing-owner behavior;
- official-source installer preview, consent, cancellation, and prohibited redistribution;
- Ollama and LM Studio inventory/start/pull/import adapters;
- approved-root boundaries, symlinks, GGUF header limits, shards, projector files,
  duplicate detection, invalid files, and removal/rescan;
- llama.cpp in-place lifecycle, readiness, crash, stop, and cleanup;
- Hugging Face search, dry run, revision pinning, filtered download, resume, gated access,
  licence display, token redaction, and disk checks;
- conversion architecture allowlist, no repository-code execution, Safetensors-only
  source, network isolation, quantization, validation, provenance, and cleanup;
- API authorization proving AI agents cannot install, download, import, or convert;
- responsive, keyboard, screen-reader, theme, and no-raw-reason-code UI behavior.

### Live acceptance

Live Playwright verification starts a real `raiker-web` and covers:

1. a pristine workspace with no ready provider across Workbench, Chat, Build, Tasks,
   schedule, and background-agent entry points;
2. the shared setup dialog and first-run flow;
3. Anthropic connected through the UI and a genuine ready turn;
4. OpenRouter connected through the UI and a genuine ready turn;
5. local Ollama `gemma4:31b-cloud` detected, selected, and used;
6. Ollama stopped after readiness, proving every surface disables honestly;
7. LM Studio/llmster detection and catalogue behavior where installed, with an official
   stub boundary only for unavailable host-specific installation cases;
8. an owner-approved GGUF folder indexed and deployed in place through llama.cpp;
9. a small permissively licensed Hugging Face GGUF dry-run/download/deploy flow; and
10. a small supported Safetensors fixture converted and validated without repository
    code or network access during conversion.

Screenshots are stored under `docs/plans/screenshots/working/` and indexed in the
existing documentation structure. Credentials supplied for acceptance are entered only
through the UI and never written to source, fixtures, logs, screenshots, shell history
artifacts, or commits.

## Documentation contract

Implementation updates, in each file's existing structure:

- `docs/plans/TO_BE_FIXED.md` — expand and close BUG-69 with all evidence; record any
  newly found defect that cannot be fixed in the same run;
- `docs/plans/RAIKER_LIVE_MANUAL_TEST_PLAN.md` and `docs/WEB_APP_LIVE_TEST.md` — new
  first-run, cross-surface, local discovery, and Hugging Face live results;
- `docs/plans/screenshots/README.md` — visual evidence index;
- `README.md` and `docs/guide/` — honest first-run and model setup instructions;
- `docs/ARCHITECTURE.md` and `docs/MODEL_RUNTIME_AND_LOCAL_INFERENCE.md` — readiness,
  library, deployment, and conversion architecture;
- `docs/API_AND_CONTRACT_SCHEMAS.md` — readiness, job, discovery, and acquisition DTOs;
- `docs/SECURITY_AND_POLICY.md`, `docs/THREAT_MODEL.md`, and
  `docs/OWASP_GENAI_SECURITY_MAPPING.md` — installer, model supply-chain, token,
  untrusted weights, conversion, and filesystem boundaries;
- `docs/FEATURE_COVERAGE_MATRIX.md` and `docs/IMPLEMENTATION_STATUS.md` — shipped state;
- release/third-party notices where required by installed open-source tooling.

## Completion criteria

BUG-69 is complete only when:

- exact readiness, not configuration, controls every model-backed surface;
- a pristine owner cannot submit doomed work and sees one actionable setup dialog;
- first-run setup can produce a ready hosted or local model and remains reusable in
  Models;
- Ollama and LM Studio installation paths follow the approved legal boundary;
- approved local libraries and arbitrary approved GGUF folders can be discovered;
- a discovered GGUF can be deployed in place and used through a healthy local runtime;
- Hugging Face can search, dry-run, download existing GGUF, and deploy it;
- supported Safetensors can be converted locally without executing repository code;
- all raw provider errors are translated and correlated safely;
- focused and full Python/web tests, lint, type checks, and production build pass;
- Anthropic, OpenRouter, Ollama, local GGUF, and Hugging Face live scenarios pass with
  reviewed screenshots;
- relevant documentation contains no stale configured-equals-ready claim;
- changes are committed and pushed to `origin/main`; and
- GitHub workflows for the pushed commit are green.
