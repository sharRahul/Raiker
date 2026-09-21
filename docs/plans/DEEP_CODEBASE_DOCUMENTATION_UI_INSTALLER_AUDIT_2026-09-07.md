# Raiker Deep Codebase, Documentation, UI, Installer and Competitive Audit — 2026-09-07

## Status and authority

**Follow-up 2026-09-08.** The focused continuation closed the Models,
global-web-read, environment and composer items recorded in the linked plans,
plus the memory-write capability regression found live. The broader audit's
remaining installer, canvas and architecture work retains the status recorded
below; the newly observed Ollama cloud-chat failure is tracked as BUG-285.

This is the **current-status audit** for Raiker at `main` commit
`ea2f48e70bfa7e68685f9865e9face17d820a61c`.

Older files in `docs/plans/` remain valuable historical evidence. Where an older
plan's status table conflicts with current source or with a later verified
implementation record, **this audit supersedes the old status, not the old
analysis**. Historical plans should not be rewritten to pretend later work had
already happened.

This review is evidence-bound. A plan item is called implemented only when the
current repository contains the corresponding source/test contract or a later
verified closure record that is consistent with current source. A green badge,
comment, or `Done` label by itself is not implementation evidence.

## Scope reviewed

The review covered:

- Python backend/API/runtime, authority, executors, storage, models, memory and
  release/package paths;
- Rust native sandbox runner and its CI coverage;
- Svelte web shell, route registry, hub/tab structure and representative
  page-specific implementation;
- authentication/bootstrap and first-launch/model-setup concepts;
- installer/release generation for Windows, Debian, AppImage and macOS;
- all workflow definitions under `.github/workflows/` and the latest `main`
  workflow results visible during this review;
- every top-level plan artifact currently under `docs/plans/`, with detailed
  re-verification of plans that carry current implementation/security/UI status;
- the existing screenshot evidence catalogue under `docs/plans/screenshots/`;
- current published security/agent patterns from OpenAI Codex, Anthropic Claude
  Code, GitHub Copilot coding agents and Cursor.

This remains a static/repository audit. It is **not** a substitute for a fresh
manual live-provider run, clean-machine installer test, penetration test,
resource-exhaustion campaign, or cross-platform visual capture run.

---

# Executive verdict

Raiker is substantially beyond a prototype. Its strongest architectural choice
is that governance, approvals, auditability and runtime posture are treated as
product primitives instead of being bolted onto a chat UI. The repository also
shows unusually good attention to failure semantics, immutable approvals,
SQLCipher posture, native boundary testing, model/runtime distinctions and
honest UI states.

The product is **not yet uniformly at the same assurance level at every
execution boundary**. The highest-value remaining work is not adding more
visible features. It is making the strongest runtime invariants mechanically
unavoidable, tightening release/install reproducibility, simplifying owner-facing
control language, and keeping documentation/evidence synchronized with the
actual product.

## Overall assessment

| Area | Assessment | Key reason |
|---|---|---|
| Governance / approval architecture | **Strong** | Real gates, decision modes, immutable approval relay, re-governance and audit evidence are first-class |
| API/browser hardening | **Strong with one important gap** | Loopback/auth/security headers/CSP are good; body limit still trusts declared length |
| Process / sandbox consistency | **Needs P0/P1 consolidation** | Some paths still rely on caller discipline; MCP stdio inherits ambient environment |
| MCP / extension isolation | **Partial** | Local/remote MCP is governed, but remote network classification and monitor-health semantics are weaker than the strongest boundary |
| Web product architecture | **Strong foundations** | Chat/Build/Design peer model, lazy secondary routes, project continuity, composed hubs and shared composer are real |
| Design workspace | **Open product gap** | Still prompt/research → image generation, not persistent canvas/selection/variation editing |
| Permissions UX | **Security-correct, cognitively dense** | Availability and behaviour are distinct but still easy for owners to conflate |
| Installer | **Needs redesign on Linux/macOS** | Debian/macOS install system-wide paths and depend on host Python rather than carrying a fully owned runtime |
| Release engineering | **Good controls, incomplete reproducibility** | Signed/unsigned policy and repeat-build proof are strong; Python resolution and appimagetool source are not release-locked |
| CI | **Green baseline and broad tests** | Python, Rust, web, licensing and phase gates run; security/supply-chain gates can go further |
| Documentation | **High detail, material status drift** | Several plans correctly preserve history but contain contradictory or obsolete current-status sections/paths |
| Screenshot evidence | **Stale location/content** | Existing catalogue contains old Models IA and unnecessary 4K/8K variants |

## Highest-priority findings

1. **P0 — Make governed execution mechanically exclusive.** Side-effecting
   executors should require an unforgeable runtime-issued authority context;
   caller convention is not enough.
2. **P1 — Sanitize MCP stdio process environments.** Current MCP `Popen` does
   not pass a constructed environment and therefore inherits the Raiker process
   environment.
3. **P1 — Classify remote MCP network reach explicitly.** The remote transport
   validates scheme/host but intentionally does not use the shared public/private
   destination policy.
4. **P1 — Enforce request-body limits on bytes actually received.** Keep
   `Content-Length` only as an early rejection optimization.
5. **P1 — Redesign Linux/macOS packaging around an app-owned runtime.** The
   normal installer should not require a pre-existing host Python installation.
6. **P1 — Lock release dependency/tool inputs.** Use `uv.lock` (or an exported,
   hashed constraints artifact) for release wheel resolution and pin/checksum
   external build tools rather than a mutable `continuous` download.
7. **P1 — Complete the Design workspace only when the runtime exists.** Do not
   add inert canvas/edit controls; implement persistent asset/version/selection
   semantics first.
8. **P1 — Replace screenshot history with current practical-resolution evidence.**
   Canonical captures are now mobile + 1080p only; 4K/8K are retired.
9. **P2 — Add dedicated security gates.** CodeQL/SAST, secret scanning,
   dependency/advisory review and release provenance should be explicit parts of
   the repository's merge/release assurance.
10. **P2 — Reduce contract/document duplication.** Generate ordinary frontend
    API types/operations from the backend contract and make `docs/plans/README.md`
    the current-status entry point.

---

# 1. Codebase architecture and engineering critique

## What is especially good

### 1.1 Governance is a runtime concern, not prompt wording

The authority/router/executor architecture, capability-gate model, approval
relay and audit/checkpoint concepts are the correct direction for an agent that
can cause side effects. This is a meaningful differentiator from products that
mostly expose an approval prompt around a generic shell.

Preserve these invariants:

- approval content is bound to the action that eventually executes;
- execution re-checks current posture rather than trusting an old approval;
- action outcomes are recorded as evidence, not inferred from UI state;
- models/tools/memory/retrieved content do not originate authority;
- failure is explicit rather than silently downgraded to a weaker path.

### 1.2 The codebase tests platform assumptions that normally remain comments

The main CI tests SQLCipher FTS5 availability and memory-security posture, runs
Python unit/integration checks, ruff, mypy and compilation, and builds/tests the
Rust native runner on Linux and Windows. That is substantially better than a
single-language unit-test workflow.

### 1.3 The web shell is now a real product shell

`web/src/lib/nav.ts` establishes one route registry, explicit Work modes
`Chat | Build | Design`, compatibility aliases for old routes/tabs, and a
separation between frequent work destinations and less-frequent management
surfaces. `routeComponents.ts` keeps the primary work surfaces ready while lazy
loading secondary administration pages. This is a healthy balance between
perceived speed and bundle cost.

### 1.4 The product often chooses honest absence over fake controls

The current Design implementation is a good example: it does not expose
variation/outpaint/edit controls that have no governed backend. That should
remain a product rule across all pages.

## Architecture risks and recommendations

### ARC-01 — Authority exclusivity still needs a mechanical type boundary

**Priority: P0**

The older security review's central concern remains the right architectural
question: can any future API route, scheduled worker, plugin or helper reach a
side-effecting executor without passing the same authority/reference monitor?

Recommendation:

```text
human/policy decision
       ↓
RuntimeAuthority
       ↓ issues opaque AuthorityContext
side-effecting executor.execute(action, authority_context)
       ↓
receipt/outcome
```

Ordinary action dictionaries, booleans and caller comments must not be able to
manufacture the authority context. Add a repository-wide CI invariant that
cross-checks every registered side-effecting executor/tool/connector against the
governed registry.

### ARC-02 — Converge process execution on one launcher

**Priority: P1**

Shell/process, MCP stdio, plugins and future code runtimes should share one
process-launch primitive controlling:

- minimal/sanitized environment;
- filesystem roots;
- network class/policy;
- process tree and cancellation;
- CPU/memory/PID/time/output budgets;
- scoped credential loans;
- audit metadata.

Current MCP stdio still calls `subprocess.Popen` without `env=`, so it inherits
ambient process variables. That is exactly the kind of boundary drift a common
launcher prevents.

### ARC-03 — Unify egress classification without making every network path identical

**Priority: P1**

Raiker does not need one allowlist for every use case. It does need one typed
classification vocabulary: local/private, public, provider, connector,
owner-explicit private endpoint, etc. Each executor can then apply a different
policy to the same destination facts.

Remote MCP currently treats an owner-added URL as authorization and validates
scheme/netloc. That may be a legitimate product decision, but it should be
represented as an explicit `private_network_grant`/endpoint trust class rather
than being an implicit exception to normal SSRF reasoning.

### ARC-04 — Security-critical monitoring cannot be merely best-effort

**Priority: P1/P2**

`McpConnectorExecutor._observe()` currently swallows all monitor/storage
exceptions. That is appropriate for optional telemetry but not for a monitor
that can drive containment or auto-pause decisions.

Split:

- ordinary telemetry → may fail open;
- security containment health → autonomous execution degrades to Ask/Pause when
  unhealthy.

### ARC-05 — Frontend/backend contract duplication is still a maintainability tax

**Priority: P2**

The optimization plan's recommendation remains sound: ordinary FastAPI request
and response contracts should generate TypeScript types/operations. Keep custom
handwritten code for session/CSRF/streaming/blob semantics only.

This is not just LOC reduction. It removes a class of “backend is correct but
one page still assumes the old field” defects.

---

# 2. Security-plan re-verification

The 2026-09-05 security review is a strong historical review but its summary
must no longer be read as current status.

| Finding | 2026-09-07 re-verification | Current action |
|---|---|---|
| CR-01 governance exclusivity | **Not proven closed** | P0 typed authority-context/invariant test |
| CR-02 MCP stdio ambient environment | **Open** | Pass sanitized/app-owned environment to MCP subprocesses |
| CR-03 connector `enforce_modes=False` | **Appears closed** | No current repository search hit; retain negative regression test |
| CR-04 hosted embedding DLP/classification | **Not re-proven closed** | Keep destination-aware trusted classification as release invariant |
| CR-05 bare plugin ambient network | **Not re-proven closed** | Prefer isolated runtime; dangerous developer path explicit |
| CR-06 body-size enforcement | **Open** | Count cumulative ASGI body bytes, including chunked/understated requests |
| CR-07 Content Security Policy | **Closed** | Current security middleware emits a restrictive CSP; preserve it |
| CR-08 remote MCP SSRF/network class | **Open by design** | Make private/public endpoint authority explicit and testable |
| CR-09 general interpreters in command allowlist | **Needs stronger boundary semantics** | Interpreter/script execution must be treated as arbitrary code, not “safe command” parsing |
| CR-10 MCP monitor fail-open | **Open** | Separate optional telemetry from containment health |
| CR-11 recipient normalization | **Not re-proven closed** | Canonical typed destinations; unresolved destination fails closed |
| CR-12 CI security/supply chain | **Partially closed** | Licensing now generates SPDX SBOM and release has read permissions; dedicated SAST/advisory/provenance gates remain |
| CR-13 attachment downstream semantic safety | **Not re-proven closed** | Continue invariant tests for provenance/injection/DLP on every model-bound chunk |

### Additional security/documentation defect

The current `raiker/runtime/executors/mcp.py` module-level documentation still
states remote HTTP/SSE transport is out of scope even though the same module now
contains a real HTTP transport path. Security documentation inside a boundary
module must describe current behavior; stale “out of scope” statements are
particularly dangerous because reviewers use them to set trust assumptions.

---

# 3. Web UI — page-by-page review

The current first-class navigation exposes 17 destinations, plus locked/
bootstrap/first-launch states and hub subpanels. The comments below review the
current product contract, not only whether a Svelte component renders.

## 3.1 Home

**Assessment: Strong / minor refinement.**

Home has become a work dashboard rather than decorative landing chrome. Preserve
running/standing/scheduled/attention/continue information. The start-work area
should keep `Chat | Build | Design` equally discoverable and should not drift
back toward an administration dashboard.

## 3.2 Chat

**Assessment: Strongest general Work surface.**

The shared composer, model/context identity, tools/research, attachments,
approvals and source/evidence behavior are coherent. Main future work should be
conversation quality and typed outputs, not more permanent composer buttons.

## 3.3 Build

**Assessment: Strong, now materially beyond the older page-by-page status.**

The later visual verification records the artifact pane and project continuity
as implemented. The older page verification saying the workbench third pane is
still open is stale.

Keep the work object dominant: Changes / Preview / Terminal / Runs. Remaining
Build gaps belong in actual execution semantics (sandbox completeness,
terminal/runtime durability), not another UI panel.

## 3.4 Design

**Assessment: Foundation good; product workspace incomplete.**

Current source honestly implements iterative prompt/image history plus a
separate governed research turn. It also explicitly states that generated
images are not yet filed into the selected Project.

Required next product layer:

- persistent Project-owned assets;
- versions/history;
- canvas state;
- selected object/region/mask;
- edit/inpaint/outpaint;
- variations/reference assets;
- compare/revert;
- inspector that reflects real runtime capabilities.

Do not ship canvas controls until the corresponding action is governed and
persisted.

## 3.5 Threads

**Assessment: Correct.**

Treat it as global work/history aggregation with search, not a separate
“search product.” Longer-term, project filtering and cross-surface history
should remain consistent with the Project object.

## 3.6 Tasks

**Assessment: Functionally strong, creation UX still denser than Work composer.**

Keep recurrence/background/run timing progressive. The instruction should be
the dominant input and model/project/recurrence details should appear only when
needed.

## 3.7 Projects

**Assessment: Project continuity is implemented; artifact ownership still has gaps.**

The old “Project as persistent context is partial” statement is superseded for
Chat/Build/Design surface switching. However, Design images are not yet
Project-owned artifacts, so Project cannot yet be described as the universal
container for every Work output.

## 3.8 Approvals

**Assessment: Product/security strength.**

Preserve risk ordering, pending/approved/executed/denied separation, immutable
proposal detail, diff/patch context, partial narrowing where supported and
execution receipts. Do not simplify this page by hiding the difference between
“approved” and “actually executed.”

## 3.9 Messaging

**Assessment: Security semantics stronger than presentation.**

External content being untrusted and unable to create authority is the correct
core rule. Continue moving host/env/secret wiring into Advanced/Troubleshooting.
The primary view should answer connected / needs attention / add channel.

## 3.10 Memory

**Assessment: Feature-rich and substantially implemented; IA remains dense.**

The memory reliability plan is now mostly a record of completed work. Preserve
provenance, expiry, proposals, forget/purge semantics, citations and search
integrity. UI should continue separating everyday memories from indexing/source
administration.

## 3.11 Knowledge Map

**Assessment: Correct spatial archetype.**

Graph interaction, filters, inspector and saved positions are the right shape.
Avoid converting it into repeated cards/tables.

## 3.12 Permissions

**Assessment: Security-correct, UX partial.**

Current source has real capability state, decision mode, bulk tightening,
step-up and threat-model acknowledgement. The confusing part is conceptual:
`availability` and `decision mode` are two different questions but can look like
competing answers.

Recommended owner language:

```text
Can Raiker use this capability?
Off | On

When Raiker wants to use it
Ask me | Allow | Automatic | Never
```

Keep technical terms such as principal/runtime resolution in Advanced details.
Never remove the underlying distinction merely to simplify the UI.

## 3.13 Models

**Assessment: IA implemented; catalogue completeness must remain evidence-bound.**

Current route registry has the intended five panels:

```text
Overview | My models | Add model | Runtime & routing | Usage
```

Old screenshot evidence showing Local/Hosted/Hugging Face/Activity/Routing/
Pricing is obsolete. The later verification records MODEL-09/MODEL-14 closure;
therefore the old page-by-page “Models must be reopened” paragraph is not
current status. Continue to enforce one owner-level model inventory with
surface/project defaults only; add a contract test proving search can reach all
compatible models returned by connected provider/runtime discovery.

## 3.14 Extensions

**Assessment: Composed hub is implemented; lifecycle security remains ongoing.**

The older page verification saying Extensions is still category-tab first is
superseded. Current navigation establishes an Overview before Connectors/MCP/
Skills/Hooks/Plugins. Continue using “Needs attention / Connected / Available”
as the owner model and keep raw protocol/runtime details deeper.

## 3.15 Observability

**Assessment: Functionally strong, intentionally operational.**

Overview/Sessions/Activity/Checkpoints/Work/Notifications is a reasonable
specialist hub. Focus on evidence quality, correlation and drill-through rather
than flattening the whole hub into one decorative dashboard.

## 3.16 Guide

**Assessment: Important product surface; needs stronger automated coverage.**

The Guide is part of the runtime UX because Raiker exposes non-trivial authority
and privacy concepts. Keep links anchored to current control names and add a
route/content smoke test so renamed Settings/Permissions concepts cannot leave
stale guidance.

## 3.17 Settings

**Assessment: Mostly correct.**

Current sections cover General, Notifications, Personalisation, Security,
Privacy, Account, Web access, Git credential, Runtime and Updates. Continue
keeping rarely used host wiring in advanced areas. Settings should describe
policy and user choices, not become the primary runtime-debugging console.

## 3.18 Locked/bootstrap/auth state

**Assessment: Strong fail-closed boundary.**

Keep runtime/store/bootstrap failures distinct from bad credentials. Do not
mount the workspace before bootstrap and authenticated-session checks have
succeeded.

## 3.19 First launch/model setup

**Assessment: Security foundation good; onboarding should teach value before infrastructure.**

Target sequence:

```text
Create/unlock owner
→ verify protected runtime/store
→ explain Chat | Build | Design
→ connect one recommended model path
→ select default
→ enter work
```

Backup, deep privacy configuration and full Permissions should be recommended
post-onboarding rather than equal blocking wizard stages. Provider connection
and model selection are different concepts and should remain different.

---

# 4. Installer and packaging review

There is no evidence of a large product-owned multi-page installer wizard to
review page-by-page in the same way as the web app. The meaningful installer
review is therefore by **platform stage and dependency contract**: what gets
installed, where, what the host must already have, upgrade/uninstall behavior,
signing and first-run launch.

## 4.1 Windows MSI

**Assessment: Best-aligned current installer.**

Per-user installation under the user profile is compatible with the product's
local-owner model. Keep installation free from compiler/dev/test dependencies.
Validate on a clean Windows VM with no developer toolchain and prove repair,
upgrade and uninstall behavior.

## 4.2 Debian package

**Assessment: Needs packaging cleanup.**

The current builder installs under `/opt` and creates a launcher under
`/usr/local/bin`; package installation therefore needs elevated system-package
rights despite the release code describing installers generally as per-user.
It also depends on host Python/Python venv support.

Recommendations:

- stop describing all installer targets as per-user;
- let the package own files through normal package paths rather than mutating
  `/usr/local` in post-install logic;
- bundle an app-owned runtime or explicitly document/verify the distro-runtime
  contract;
- fresh-container/VM test with no previously installed Raiker/Python tooling;
- verify uninstall removes only package-owned files and never user workspace data.

## 4.3 AppImage

**Assessment: Distribution shape is appropriate; runtime ownership incomplete.**

An AppImage should behave as a portable application. Requiring a host Python at
first run weakens that promise. Prefer carrying the runtime required to execute
Raiker and keep mutable user state under XDG user locations.

## 4.4 macOS pkg

**Assessment: Signing/notarization path is good; dependency model needs redesign.**

The package writes under `/usr/local` and assumes host `python3`. Modern macOS
must not be treated as a guaranteed Python runtime. Bundle an app-owned runtime,
keep secrets/workspace state in user-owned locations, and test a clean machine
with no Homebrew/Python.

## 4.5 Installer acceptance suite to add

Every release target should prove:

1. clean install on a machine without developer tooling;
2. offline launch after installer download;
3. only runtime dependencies are installed — never dev/test/build dependencies;
4. no `.env`, provider credential or build secret is bundled;
5. application runtime/files are owned by the installer manifest;
6. user workspace/key material is outside files removed by uninstall;
7. upgrade preserves user state and replaces app/runtime atomically enough to
   recover from interruption;
8. uninstall does not delete user projects/history unless separately and
   explicitly requested;
9. signed/notarized state is visible and verifiable;
10. launch proves SQLCipher/native runner/model-provider setup behaves exactly
    as the packaged build expects.

---

# 5. CI, supply chain and release review

## 5.1 Current workflow health at the audited main commit

The latest visible runs for the audited `main` head were successful for:

- CI;
- Web UI;
- Licensing;
- Phase Status Validation.

Release is manual by design and therefore is not a normal green-on-every-push
check. That is a reasonable release policy.

## 5.2 Workflow strengths

- GitHub Actions dependencies are pinned to immutable commit SHAs.
- Python CI runs tests, lint, typing and source compilation.
- SQLCipher FTS5 and memory-security assumptions are checked explicitly.
- Rust native runner is formatted/linted/tested on Linux and Windows.
- Web uses `npm ci`, lint, Svelte/type check, unit tests, build and mocked
  Playwright e2e.
- Licensing generates an SPDX SBOM and validates built distributions.
- Release has an explicit signed-vs-unsigned honesty rule and prevents an
  unsigned test build from being published as a release.
- Release pins the build clock and compares two same-input payload builds.

## 5.3 Workflow/release gaps

### CI-01 — Explicit least privilege should be universal

`licensing.yml` and `release.yml` already declare `contents: read`; the ordinary
CI, Web and phase-status workflows should do the same. This audit branch adds
that declaration.

### CI-02 — Security validation should be a merge gate, not an occasional review

Add, as repository settings/licensing permit:

- CodeQL/SAST for Python/JavaScript-TypeScript/Rust-relevant surfaces;
- secret scanning / push protection;
- dependency review on PRs;
- advisory/malware/high-critical dependency policy;
- container/image scanning for shipped execution images;
- optional fuzz/negative boundary jobs for URLs, paths, recipients and approval
  replay.

### CI-03 — SBOM should be retained with the artifact

The licensing workflow generates SPDX but does not currently make the SBOM a
release/publicly inspectable artifact in the reviewed workflow. Carry the SBOM
through release, bind it to artifact digest/version and publish it beside the
installer.

### REL-01 — Python release dependency resolution is not locked to `uv.lock`

The repo contains `uv.lock`, but release currently executes `pip wheel .` from
lower-bounded project metadata. The same checkout can therefore resolve a
newer dependency on a later date.

Recommendation: export a release constraints/requirements set from the lock,
including hashes where practical, and build wheels from that exact resolved set.

### REL-02 — `appimagetool` is downloaded from a mutable `continuous` release

That defeats historical input reproducibility and adds a supply-chain trust
edge. Pin a reviewed version/digest and verify checksum/signature before use.

### REL-03 — Add provenance/attestation

Generate SLSA-compatible provenance or GitHub artifact attestations that bind:

```text
source commit + workflow + locked dependency set + SBOM + artifact digest + signing identity
```

The current “build twice in one job” check should remain; provenance solves a
different question.

---

# 6. Competitive best-practice review

This comparison is about patterns worth adopting, not cloning another product.
Raiker's goal should be to exceed the field on **governed agency + owner
control + evidence** while matching mature platforms on isolation, developer
experience and release discipline.

## OpenAI Codex

Current OpenAI material describes sandboxing and approval policy as separate
but complementary controls: constrained writable paths/network boundaries plus
review when an action crosses those boundaries. OpenAI also emphasizes managed
configuration and agent-native telemetry.

**Raiker is in line:** approval/governance/evidence model, bounded workspaces,
explicit model/tool authority.

**Raiker is behind:** universal execution-boundary consistency, default network
isolation for every subprocess class, and dedicated security-agent/scanning
integration in CI.

## Anthropic Claude Code

Anthropic's published sandbox design emphasizes that effective agent sandboxing
needs **both filesystem and network isolation**, enforced with OS-level
primitives and covering subprocesses. Claude Code's direction also reduces
approval fatigue by making safe work autonomous inside a hard boundary.

**Raiker is in line:** explicit approval modes, workspace containment,
governance before side effects.

**Raiker is behind:** MCP/plugin/process paths should all inherit the same
filesystem + network boundary automatically; current MCP stdio environment and
remote MCP exception make the boundary less uniform.

## GitHub Copilot coding agents

GitHub's current coding-agent material combines ephemeral/firewalled execution
with CodeQL, secret scanning and dependency validation on generated code.

**Raiker is in line:** native/container execution options, auditability,
checks/tests before work is accepted.

**Raiker is behind:** automatic security validation is not yet a first-class
merge gate in this repo; the user should not need a manual security review to
get baseline secret/dependency/static analysis on every change.

## Cursor

Cursor's current agent security docs distinguish approval policy from sandbox
policy, block arbitrary sandbox network access by default in run modes, protect
sensitive paths and keep MCP calls approval-aware. Cursor also exposes security
review automation as a normal development workflow.

**Raiker is in line:** explicit modes, protected/governed actions, MCP lifecycle,
strong owner control.

**Raiker is behind:** permissions language is more technical than it needs to
be, execution/network boundaries are less uniform across every extension path,
and security-review automation should be easier to invoke and gate.

## Competitive recommendation

Do **not** respond by adding more modes or visible policy widgets. The strongest
competitive move is:

> **A smaller number of owner-visible controls backed by stronger, universal
> technical boundaries and richer evidence.**

That means one authority path, one process-boundary vocabulary, one egress
classification layer, one model catalogue, one Work-project context, one
screenshot/evidence source of truth and one release input set.

---

# 7. Documentation review of `docs/plans/**`

## 7.1 Current plan corpus strengths

The planning corpus is unusually evidence-oriented: many entries name root
causes, code paths, acceptance conditions and fixed records rather than vague
roadmap bullets. Keep that discipline.

The problem is **status duplication**. Multiple large documents each contain a
current-status table, and a later fix updates one file but not every older
summary that made the same statement.

## 7.2 Document-by-document disposition

| Document | Disposition after this audit |
|---|---|
| `CODEBASE_OPTIMIZATION_AND_LOC_REDUCTION_2026-09-05.md` | Historical analysis + active architecture recommendations. Paths such as old `apps/web` references must not be treated as current. Contract generation and module decomposition remain useful. |
| `CODEBASE_SECURITY_CODE_REVIEW_2026-09-05.md` | Historical findings. Use the re-verification table in this audit for current status. |
| the environment-context plan | Implementation-plan history; later records say core time/weather work closed. Re-run contract tests before reopening. |
| `FIXED_ITEMS.md` | Evidence ledger. Keep append-only in spirit; not a current-priority list. |
| `GAP_BUILD_CHAT.md` | Useful gap ledger but contains stale old source paths and narrative statements that predate closures. Status table is more authoritative than old prose. |
| `GENERIC_STATIC_CODE_REVIEW_2026-09-05.md` | Historical static-review evidence; closed rows stay historical. |
| `GENERIC_STATIC_CODE_REVIEW_THIRD_PASS_2026-09-05.md` | Valuable, but internally contradictory: its “still open” prose names some findings that its own later table marks closed. Treat row-level closure + this audit as current. GCR-41/42/43 remain especially relevant. |
| the global model-catalogue review | Architectural invariant remains correct. Later implementation records supersede its “not reliably yet” current-state paragraph. Keep owner-level catalogue contract as regression target. |
| the global web-read plan | Later closure record says global read parity/readiness work landed. Preserve as design/acceptance history. |
| `GOVERNANCE_ENTRY_PATHS.md` | High-value architecture inventory. Should ultimately be generated/validated against executor/tool registries to prevent drift. |
| `LIVE_TEST_ROUNDS.md` | Evidence history, not current product spec. Keep environment/date/provider context with every round. |
| `MEMORY_RELIABILITY_PLAN.md` | Mostly completed reliability ledger; good evidence. Future memory scaling work should be new entries rather than reopening closed history. |
| the Models review | Historical review; current five-panel IA is implemented. Use global-catalogue contract tests for regression. |
| `PAGE_BY_PAGE_IMPLEMENTATION_VERIFICATION_2026-09-07.md` | **Removed 2026-09-13**, its last open item — Design's canvas workspace — having closed as [FIXED-491](FIXED_ITEMS.md#fixed-491--design-was-a-one-shot-generator-so-most-of-its-composer-had-nothing-to-reach). It was superseded as current status by this audit long before that; what it verified now lives in the `FIXED_ITEMS.md` entries it produced, and its reasoning in git history. |
| `PILLAR_MAP.md` | Useful executive dependency map. Must reference current ledgers rather than duplicate detailed statuses. |
| `RAIKER_LIVE_MANUAL_TEST_PLAN.md` | Active verification procedure. Add the new canonical screenshot path/resolutions and clean installer scenarios. |
| `SECURITY_COMPLIANCE_GAP_ASSESSMENT_2026-09-05.md` | Mapping evidence; must not imply certification or current control effectiveness solely from implementation. Revalidate when release boundary changes. |
| `TO_BE_ADDED.md` | Future/differentiator ledger. Good distinction between proposals and defects, but proposals must not outrank closing P0/P1 boundary gaps. |
| `TO_BE_FIXED.md` | Defect backlog. Should remain the canonical unresolved-defect ledger; status summaries elsewhere should link to it rather than duplicate it. |
| `UNIFIED_COMPOSER_REDESIGN_2026-09-06.md` | **Removed 2026-09-21**, complete. COMPOSER-01 through COMPOSER-20 all closed; the two image controls COMPOSER-09 lists that are still absent — outpaint and reference images — are absent *by* that document's own acceptance test 19, which says an action that reaches no runtime path is omitted rather than shipped inert. The records are FIXED-454, FIXED-455, FIXED-461, FIXED-470, FIXED-471, FIXED-478, FIXED-479, FIXED-491 and FIXED-540. |
| `VISUAL_UI_UX_REVIEW_2026-09-06.md` | **Removed 2026-09-15**, complete. 4K/8K was cancelled by product decision rather than left as a gap; the Design canvas closed 2026-09-13 ([FIXED-491](FIXED_ITEMS.md#fixed-491--design-was-a-one-shot-generator-so-most-of-its-composer-had-nothing-to-reach)) and the typed output channel — its last item — on 2026-09-15 ([FIXED-545](FIXED_ITEMS.md#fixed-545--a-turn-could-only-answer-in-prose)). |
| the adaptive-shell design | Design intent/history. Current route/nav source is the implementation truth. |
| the adaptive-shell implementation plan | Implementation history. Completed shell work should not be carried as active backlog. |
| `screenshots/` under `docs/plans` | **Legacy evidence only.** It contains stale Models IA and 4K/8K variants. New canonical location is `docs/screenshots/`. |

## 7.3 Documentation governance rule

Going forward, use four roles only:

```text
docs/plans/README.md       current status + links
docs/plans/TO_BE_FIXED.md current defects
docs/plans/TO_BE_ADDED.md future/differentiators
docs/plans/FIXED_ITEMS.md closure/evidence history
```

Topic-specific reviews remain immutable-ish evidence documents. They may gain a
small “superseded/current status” banner, but should not each maintain a full
parallel backlog.

---

# 8. Implementation verification — direct answer

## Correctly implemented / verified in current source or later closure

- Chat / Build / Design are first-class peer Work modes.
- Shared composer foundation and reduced permanent composer chrome.
- Build artifact/work pane (later visual verification supersedes the older open
  status).
- Project continuity across primary Work surfaces.
- Models five-panel information architecture.
- Extensions composed Overview-first hub.
- current time/weather/read-capability work recorded as closed by later
  verification rather than the older open paragraph.
- CSP browser hardening.
- immutable-SHA GitHub Actions usage.
- broad Python/Rust/web quality checks.
- SPDX licensing/SBOM generation.
- signed/unsigned release policy and same-input repeat-build digest comparison.

## Partially implemented / correct foundation but incomplete target

- Design: first-class route, research and image generation are real; persistent
  canvas/edit/version Project workspace is not.
- Permissions: backend/security model is real; owner-facing mental model remains
  more complex than necessary.
- Tasks: execution semantics are strong; creation UX remains more form-like than
  shared-composer grammar.
- Project: Work context is persistent, but not every generated artifact (notably
  current Design images) is Project-owned.
- installer portability: artifacts are buildable/signed, but Linux/macOS still
  rely on host/runtime assumptions that should belong to the app.
- security CI: SBOM/licensing exists, but SAST/secret/dependency/provenance
  coverage is not yet the class-leading baseline.

## Not correctly complete / reopen or retain as active gap

- mechanical authority-only access to every side-effecting executor;
- MCP stdio ambient environment isolation;
- explicit remote MCP destination trust/network class;
- fail-safe security-monitor health semantics;
- actual streamed request-body byte limiting;
- fully release-locked Python dependency resolution;
- pinned/checksummed AppImage build tool;
- current screenshot evidence for every route/tab at the new canonical path;
- Design persistent canvas/editing workspace.

---

# 9. Screenshot policy and evidence status

The old catalogue under `docs/plans/screenshots/` is retained only as historical
evidence. It must not be used to represent the current product because it still
contains the pre-redesign Models panels such as Hosted/Local/Hugging Face/
Pricing/Routing.

The canonical location is now:

```text
docs/screenshots/pages/
```

Only two practical viewport classes are required:

```text
mobile  390×844
1080p   1920×1080
```

Both light and dark remain useful because theme regressions are real product
regressions. 4K and 8K capture classes are retired; layout should remain fluid,
but committed evidence does not need those files.

The live sweep is updated by this audit branch to write to the new location and
to stop generating 4K/8K.

**Important:** this repository audit did not have a running authenticated Raiker
instance from which to truthfully regenerate current PNGs, and the latest Web UI
workflow exposed no screenshot artifact to reuse. Therefore stale images were
**not** copied into the new directory and labelled current. Run the live sweep
against a current instance and commit the generated mobile/1080p light/dark
captures before treating screenshot refresh as complete.

---

# 10. Priority/effort execution order

Following the repository's priority-before-effort rule:

| Order | Item | Priority | Effort |
|---:|---|---:|---|
| 1 | Sanitize MCP stdio environment through common launcher | P1 | Low |
| 2 | Enforce actual received request-body bytes | P1 | Low-Medium |
| 3 | Pin release dependency set to `uv.lock`/hashed constraints | P1 | Low-Medium |
| 4 | Pin/checksum appimagetool | P1 | Low |
| 5 | Mechanical authority-context invariant | **P0** | Medium |
| 6 | Explicit remote MCP public/private endpoint trust class | P1 | Medium |
| 7 | Split telemetry failure from containment-health failure | P1 | Medium |
| 8 | Bundle app-owned Python/runtime for macOS/AppImage; rationalize Debian package ownership | P1 | Medium-High |
| 9 | Fresh-machine installer acceptance matrix | P1 | Medium |
| 10 | Design Project asset/version/runtime foundation | P1 | High |
| 11 | Design persistent canvas/editing UX | P1/P2 | High |
| 12 | CodeQL/secret/dependency/container security gates | P2 | Medium |
| 13 | Release provenance + publish SBOM/attestations | P2 | Medium |
| 14 | Generate frontend API contracts/ordinary wrappers | P2 | Medium |
| 15 | Simplify Permissions owner language | P2 | Medium |
| 16 | Regenerate canonical mobile/1080p screenshot catalogue from live app | P2 | Low once live host exists |

The P0 authority invariant remains the highest **release-significance** item even
though the first four P1 tasks are cheaper and can land safely before its larger
refactor.

---

# 11. External reference set used for competitive comparison

Checked 2026-09-07:

- OpenAI — Running Codex safely at OpenAI:
  https://openai.com/index/running-codex-safely/
- OpenAI — Codex sandbox/network safety overview:
  https://openai.com/index/introducing-upgrades-to-codex/
- Anthropic — Making Claude Code more secure and autonomous with sandboxing:
  https://www.anthropic.com/engineering/claude-code-sandboxing
- GitHub — Application card: GitHub Copilot Agents:
  https://docs.github.com/en/copilot/responsible-use/agents
- GitHub — Risks and mitigations for GitHub Copilot cloud agent:
  https://docs.github.com/en/copilot/concepts/agents/cloud-agent/risks-and-mitigations
- Cursor — Agent Security:
  https://prod.cursor.com/docs/agent/security
- Cursor — Run Modes:
  https://prod.cursor.com/docs/agent/security/run-modes

These references are comparison inputs, not claims that Raiker should reproduce
another platform's exact UI or permission model.
