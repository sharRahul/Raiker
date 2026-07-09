# Session Handoff — pick up here

> Purpose: let any builder (Claude, Codex, or human) resume the Raiker goal
> without re-deriving state. Read this + `docs/IMPLEMENTATION_STATUS.md` first.
> Update this file at the end of every working session.

## Goal

Make Raiker a secure AI product that combines an AI assistant, a governed AI agent, and an extensible agent platform.

As an assistant, Raiker should help users understand, reason, decide, and communicate through a polished conversational experience. As an agent, Raiker should be able to plan tasks, gather context, use tools, execute approved actions, verify outcomes, and explain what it did. As a platform, Raiker should provide the governed runtime foundation for models, tools, plugins, interfaces, memory, approvals, audit events, checkpoints, and integrations.

Raiker must support user-owned model choice across LLM backends — local models such as llama.cpp, Ollama, and LM Studio; home-lab runtimes such as vLLM; private-network providers; and hosted API providers such as Anthropic, OpenAI, Gemini, and OpenRouter. No model, interface, plugin, or capability should bypass governance. Every action must remain policy-aware, observable, auditable, approval-driven where required, human-governed, user-controlled, and fail-closed by design.

Be mind full of token usage if needed do it in batches. Keep committing after every phase and then push to origin main before the token limit is ended for the session. Plan and implement it in such a way that anyone can pick it up after your session token are over even though the goal is not complete. In next session review where you are and then start from next phase.

## State as of 2026-07-07 (session end) — web app rebuild

> **Web UI rebuilt from scratch (open in PR #104, branch
> `claude/raiker-web-ui-redesign-2u052u`; frontend-only, no backend behaviour
> change).** The old `apps/web` dashboard is replaced by a professional pastel UI:
> - **Design:** one design-token set in `apps/web/src/app.css` (iris/mint/peach/
>   rose/sky accents), **dark + light + system themes** (default follows
>   `prefers-color-scheme`; explicit choice persisted in `localStorage` — the
>   bearer token stays memory-only). Shield-R logo + inline SVG icon set; no
>   external fonts/CDNs (fully offline). Nav grouped Work / Governance / System.
> - **Surfaces (full capability + settings coverage):** Chat (SSE turn stream;
>   the gather→plan→act→verify detail is tucked behind a per-turn disclosure so
>   background machinery never crowds the view), Approvals (metadata-only),
>   Tasks, Sessions, Capabilities, Models, Checkpoints, Audit log, Diagnostics,
>   Settings.
> - **Capabilities page:** per-owner request, the **Ask/Allow/Auto/Deny decision
>   mode** is the primary inline control on every capability; implementation-status
>   badges (Implemented/Deferred/Disabled) were removed. To make inline modes
>   robust the decision mode now rides on the single `/api/capability-gates` read
>   (new `decision_mode` field on `CapabilityGateView` — the only backend change),
>   avoiding a 53-request fan-out that tripped the 120/min API rate limit.
> - **Plain-English UI:** raw internal identifiers (`shell_execution`, `write_file`,
>   `policy_decision`, runtime-mode codes, gate-state codes) are humanised for
>   display; the "Raiker" product name is kept. Literal strings that are meant to
>   be read/typed verbatim (`[REDACTED]`, `127.0.0.1`, CLI commands) stay as code.
>
> **Web app + server health check (2026-07-07, this session):** stood up
> `raiker-web` against a bootstrapped-owner workspace and verified end to end.
> - **All good:** `/api/health` + SPA index 200; all read endpoints
>   (capability-gates, runtime-mode, diagnostics, models, approvals, tasks,
>   events, checkpoints, sessions, runtime-readiness) return 200; owner session
>   mint + decision-mode writes work; **no browser console errors across all ten
>   views**; `npm run lint`/`check`/`test` (57 vitest) + `build` green; full
>   `pytest`, `ruff`, `mypy raiker apps tests`, and all five validators pass.
> - **One issue found and fixed:** the browser auto-requested `/favicon.ico` and
>   got a 404 (no favicon bundled, no `<link rel="icon">`). Added
>   `apps/web/public/favicon.svg` (shield-R) + the icon link in `index.html`;
>   console is now clean. `favicon.ico` still 404s if requested directly, but
>   browsers use the linked SVG so it is never requested.
> - **Known web-app limitations (by design, NOT bugs — do not "fix"):**
>   1. **Chat needs a running local model server.** With no reachable model,
>      prompts fail closed with `model_unavailable: provider_connection_failed`
>      (Raiker never fabricates output). Point it at llama.cpp/Ollama/LM Studio and
>      select a profile (`/model use …`) first.
>   2. **API rate limit is 120 req/min per IP** (`RateLimitMiddleware`). The UI is
>      designed to stay well under it; a burst of rapid manual refreshes can still
>      surface `429 rate_limited` (shown honestly). Keep new views single-request
>      where possible (see the `decision_mode`-on-gates change above).
>   3. **No secret/credential store (deferred).** Settings shows redaction posture
>      only; provider API keys are read from the owner's env and never displayed.
>   4. Single-user, loopback-only (`127.0.0.1`); approval resolution is
>      metadata-only (records a decision, never executes).

## State as of 2026-07-06 (session end)

> **This session — part 8 (default gate posture flip: integrated = enabled):**
> Reversed the foundational "every capability gate ships disabled by default"
> invariant per owner directive. Now **integrated capabilities (those in
> `REAL_EXECUTOR_CAPABILITIES`, 29 of them) default to `enabled_runtime`**;
> capabilities that are not integrated yet (no real executor) stay `disabled` and
> fail closed. Implemented in `raiker/phase_gates.py::default_capability_gates()`
> (flips the real-executor set to `ENABLED_RUNTIME` via `replace`; lazy import of
> `REAL_EXECUTOR_CAPABILITIES` to avoid a cycle).
> - **Safety model (unchanged floors):** there is NO runtime-mode master switch on
>   the execution path — the gate is the per-capability switch — but enabling it
>   does not let an AI act unattended. AI-proposed actions still hit the
>   per-capability **decision mode (default `ask`)**, the **critical-risk human
>   floor**, **PolicyEngine hard-denies**, and **executor-level env allowlists**
>   (model egress / plugin / container image), which are independent of the gate and
>   remain fail-closed. Human principals self-authorize (the UX win: no enable-dance
>   for integrated caps).
> - **Readiness redefined:** `get_runtime_readiness`'s `dangerous_capabilities_disabled`
>   / `production_ready` now check only the **not-yet-integrated** dangerous caps
>   (integrated-and-enabled is the norm). Two validators updated in lockstep
>   (`validate_runtime_enablement_readiness.py`, `validate_local_single_user_runtime.py`):
>   integrated caps must be enabled, non-integrated must be disabled.
> - **Tests (26 updated):** ~14 "gate_disabled_blocks" acceptance tests now
>   explicitly `disable_capability(...)` first (default is enabled); ~12
>   default-disabled invariant tests updated to the new posture (integrated enabled,
>   non-integrated disabled; `subagents`/`multi_agent_teams` flip to enabled in the
>   phase-3 governance surfaces). Full suite **1230 passed**; ruff + mypy (incl.
>   `tests/`) clean; all five validators pass.
> - **Docs:** canonical posture statements updated (`IMPLEMENTATION_STATUS`,
>   `README` ×2, `SECURITY_ARCHITECTURE` ×2, `RUNTIME_EXECUTORS_SPEC`). **Follow-up
>   (not done):** a broader sweep of ~15 remaining spec/historical/guide docs still
>   says "disabled by default" in places — update opportunistically; the truthfulness
>   validators pass, but those prose mentions are now stale.

> **This session — part 7 (agentic loop wiring: default-ask retrieval augmentation):**
> Wired embed+search+resolve into the turn as **retrieval-augmented generation**,
> governed **default-ask** (owner's explicit choice — not default-off). New
> `RetrievalAugmentor` (`raiker/runtime/retrieval.py`), constructed by
> `RuntimeOrchestrator` from the broker's store, runs at `CONTEXT_READY`. It adds
> **no new governance surface** — it reuses the `vector_embedding_runtime` gate +
> decision mode: gate disabled → no-op (default turn unchanged, nothing emitted);
> gate enabled + mode `ask` (default) → **withheld** (emits
> `retrieval_augmentation` `decision=ask, augmented=false`, no injection); mode
> `allow`/`auto` → embeds the prompt locally, searches local vectors, injects the
> top-k previews as an untrusted-data system message into the model prompt. Event
> stays metadata-only (`decision`/`augmented`/`count`/`vector_ids`); preview text
> reaches the model prompt (the point of RAG) but never the event payload. New
> event type `retrieval_augmentation` registered in `EVENT_TYPES` + `EVENT_CATALOG`.
> - **Honest note on "not default-off":** the *behaviour* is default-ask as
>   requested. It still sits behind the standing `vector_embedding_runtime` gate
>   (default-disabled), which is the universal fail-closed capability invariant —
>   not special to this feature. Enabling that gate is the one-time owner step;
>   thereafter each turn's auto-retrieval is default-ask.
> - Evidence: `tests/test_retrieval_augmentation.py` (8 tests: gate-disabled no-op,
>   default-ask withheld, deny, allow-injects, empty-store, + 3 orchestrator turn
>   tests asserting the event + whether the preview reached the model prompt).
> - Full suite **1230 passed**; ruff + mypy (incl. `tests/`) clean; validators pass.
> - **RAG loop is now complete end-to-end:** embed → store → search → resolve →
>   (default-ask) inject into the turn. Possible next: expose retrieval toggles/
>   status in the web dashboard; provider-space (semantic) retrieval as an
>   egress-gated extension; a CLI to inspect/preview retrieval decisions.

> **This session — part 6 (resolve vector_id → content: `vector_get` read):**
> Added the read half so ranked ids from `search` become usable. `vector_get` is a
> governed **read tool** (`raiker/tools/vector_tools.py`), registered in the
> `ToolBroker` and the PolicyEngine read allowlist (`allowed_read_actions`) + the
> agent `DELEGABLE_TOOLS` set — it mirrors `memory_get`. It resolves a `vector_id`
> to the stored 120-char `content_preview` + metadata via new
> `SQLiteStore.get_vector_record`; it never returns the raw embedding vector, and
> fails closed `missing_argument` / `not_found`. **Design boundary (documented):**
> the vector table only persists a bounded preview, so `vector_get` returns that;
> and as a *read* its output is auditable like `read_file`/`memory_get` — the
> deliberate counterpart to the metadata-only *executor* path (embed/search).
> Evidence: `tests/test_vector_get_read.py` (direct + through-broker allow/notfound).
> - This completes the RAG data plumbing: **embed → store → search → resolve**.
>   **Next (the remaining ordered item): wire it into the agentic loop** —
>   retrieval-augmented turns. That is architecturally significant (auto-injecting
>   retrieved content into the model turn touches governance/default-ask/audit), so
>   scope/design it with the owner before building.
> - Full suite **1222 passed**; ruff + mypy (incl. `tests/`) clean; validators pass.

> **This session — part 5 (vector retrieval: close the embed→store→retrieve loop):**
> Added a `search` operation to `vector_embedding_runtime` (no new capability, no
> new gate) so the local embeddings the agent creates become usable for retrieval
> (RAG). `search` embeds the query with the same local hashing model
> (`raiker.vector.embed_text`), ranks stored vectors by cosine via the existing
> in-memory `VectorIndex`, and returns the top-k as `{vector_id, score}` pairs.
> - **Same-space only:** new store method `SQLiteStore.list_vector_embeddings(
>   embedding_model, scope=None)` returns just the local-model vectors (uncapped,
>   `embedding IS NOT NULL`); provider-model (`model_provider_runtime`) vectors are
>   never ranked (cross-space cosine is meaningless). Read-only — writes nothing.
> - **Metadata-only / read-only:** artifacts are `count` + `results`
>   (`{vector_id, score}`) + `embedding_model` + `content_redacted=true`. The query
>   text, source text, and stored previews never enter events. Fail-closed:
>   `missing_argument:query`, `query_too_long`, `invalid_argument:top_k` (1–100),
>   `invalid_argument:scope`. Distinct from `semantic_memory_runtime` (memory store).
> - Evidence: `tests/test_phase_6_vector_embedding_runtime.py` search tests
>   (exact-match ranks first ~1.0 w/o leaking query; top_k honored; other embedding
>   models excluded; empty corpus → 0; missing-query / bad-top_k fail closed).
> - Full suite **1217 passed**; ruff + mypy (incl. `tests/`) clean; all validators
>   pass. Branch restarted from merged `main` (PR #100); this is a **new PR**.
> - **Next natural step:** wire embed+search into the agentic loop (retrieval-
>   augmented turns), and/or a governed "get preview by vector_id" read so retrieved
>   ids resolve to content for the human. Provider-space (semantic) search would be
>   an egress-gated extension of `model_provider_runtime`.

> **This session — part 4 (make hosted providers usable: OpenRouter/OpenAI):**
> Fixed a real latent gap so a human/agent can actually use OpenRouter, OpenAI,
> Gemini (and every OpenAI-compatible provider) from any entry point.
> `ModelProfileRegistry.resolve(provider, model)` required an *exact* model match,
> but those providers ship a placeholder `<model>` — so the direct
> `ModelRouter.achat`/`aembed` path failed with `unknown_model_profile` unless the
> CLI/gateway pre-registered a concrete-model profile. This also broke part-3's
> `model_provider_runtime` default embedder (it calls `router.aembed(provider,
> model)` → resolve) before it ever reached the egress/key checks. `resolve` now
> falls back to a provider's placeholder profile and fills in the concrete model
> (exact match still wins; unknown providers still fail closed). Provider policy
> (gate + egress allowlist + API key) is unchanged — still enforced by the factory.
> Evidence: `tests/test_model_registry_resolve_fallback.py` (6 tests).
> - Verified the **governed human config flow** end-to-end offline: with the
>   `hosted_model_runtime` gate enabled, `/model use --provider openrouter --model
>   openai/gpt-4o-mini` and `--provider openai --model gpt-4o-mini` both select
>   successfully through the real gate-derived-policy path.
> - **Live turn for OpenRouter/OpenAI is NOT verifiable from the cloud session:**
>   this environment's egress proxy denies `openrouter.ai` and `api.openai.com`
>   (403 CONNECT, org policy — `anthropic.com` is on the allowlist, which is why
>   the part-2 Anthropic turn worked). This is infra policy, not a Raiker bug, and
>   must not be routed around. To live-verify: run on a machine where those hosts
>   are reachable (owner's local machine), or have an admin add them to the cloud
>   session egress policy. Anthropic (`anthropic-hosted`) remains the one
>   `implemented_verified` hosted provider.
> - Full suite **1211 passed**; ruff + mypy (incl. `tests/`) clean; all validators pass.

> **This session — part 3 (next real executor: `model_provider_runtime`):**
> promoted `model_provider_runtime` from a fail-closed stub to a **real,
> egress-gated, provider-backed embedding executor** (`ModelProviderExecutor` in
> `raiker/runtime/executors/models_runtime.py`; the stub left `tier3_core.py`). It
> calls a real LLM provider's embedding endpoint via `ModelRouter.aembed` and
> persists the returned **semantic** vector to the shared `vector_records` table
> (`embedding_model=<provider>:<model>`), complementing the local hashing
> embedding. Layered fail-closed gating: owner egress allowlist
> (`RAIKER_MODEL_EGRESS_ALLOWLIST`, empty = closed, checked before any call) +
> hosted/private gate state (`provider_runtime_policy_from_gates`) + API-key from
> owner env only (never from args, never in events). `operation: embed` only.
> Provider client is **injectable** (`embedder=`) so tests exercise the governed
> persistence path with no live provider/credentials/network.
> - Enabling now requires threat-model ack + confirmation token (added to
>   `_DANGEROUS_CAPS` and `activation.py` `threat_ack/human_confirm`); doc
>   `docs/threat-models/model-provider.md`.
> - Registered in `REAL_EXECUTOR_CAPABILITIES` + default registry. Lockstep test
>   updates: removed `model_provider_runtime` from
>   `test_executor_default_registry.py::_SENSITIVE`; the "no-executor deferred cap"
>   examples in `test_security_regression_ui.py` + `test_api_m5_security_settings.py`
>   now use `hardware_operator_runtime` (a durable no-executor domain); fixed the
>   sibling assertion in `test_phase_6_vector_embedding_runtime.py`. Docs updated:
>   `IMPLEMENTATION_STATUS.md`, `RUNTIME_EXECUTORS_SPEC.md`,
>   `guide/capabilities-deferred.md`, and the vector-embedding threat model.
>   Evidence: `tests/test_phase_7_model_provider_runtime.py` (8 tests).
> - Full suite **1205 passed**; ruff + mypy clean on changed sources; all five
>   validators pass.
> - **Honest limit:** only `embed` is implemented; generation/chat stays in the
>   gateway/provider layer. **Next real-executor targets:** live hosted-provider
>   verification (evidence only — run one governed `anthropic-hosted` turn with an
>   operator key), then the remaining graph/semantic promotions.

> **This session — part 2 (next real executor: `vector_embedding_runtime`):**
> promoted the Tier-3 `vector_embedding_runtime` from a fail-closed stub to a
> **real, local-only executor** (next target named in the handoff). It computes a
> **deterministic local embedding** via the hashing trick
> (`raiker/vector/embed_text` + `LOCAL_EMBEDDING_MODEL = "raiker-local-hash-v1"`)
> — no model download, no network, no external call — and persists a real 384-d
> vector to the existing `vector_records` table (added an `embedding` JSON column
> + `embedding` field on the `VectorRecord` contract; reused the existing
> `insert_vector_record`/`list_vector_records`). `action`: `embed` (default) /
> `list`; fail-closed codes `missing_argument:text`, `text_too_long`,
> `invalid_argument:scope_or_sensitivity`, `unknown_action:<op>`. Artifacts are
> metadata-only (vector_id/model/dims/hash); **source text never enters events**
> (a 120-char preview is stored locally only, like reminder titles).
> - Registered in `REAL_EXECUTOR_CAPABILITIES` + `build_default_executor_registry`
>   (needs the store). Gate still ships **disabled**; enabling needs runtime mode
>   + confirmation token (Tier-3, no threat-ack, matching graph/semantic siblings).
> - **Honest scope:** lexical feature-hashing embedding, NOT learned semantics.
>   The provider-backed `model_provider_runtime` (semantic embeddings/generation
>   via an LLM provider) stays **fail-closed** until its own egress-gated slice.
> - Lockstep updates: `activation.py` note; removed vector_embedding from the
>   no-executor examples in `tests/test_executor_default_registry.py::_SENSITIVE`,
>   `tests/test_security_regression_ui.py`, `tests/test_api_m5_security_settings.py`
>   (all now use `model_provider_runtime` as the still-fail-closed example);
>   `docs/threat-models/vector-embedding.md` (new); `RUNTIME_EXECUTORS_SPEC.md`;
>   `IMPLEMENTATION_STATUS.md`. Evidence:
>   `tests/test_phase_6_vector_embedding_runtime.py` (7 tests).
> - Full suite **1197 passed**; ruff + mypy clean on changed sources; all five
>   validators pass.
> - **Next real-executor target:** `model_provider_runtime` (provider-backed,
>   egress-gated — reuse the `hosted_model_runtime` egress-allowlist pattern), then
>   the remaining graph/semantic promotions and live hosted-provider verification.

> **This session — part 1 (decision-mode API + human-in-control audit):** verified the
> per-capability decision-mode surface is complete and human-controlled, and
> closed the gaps found.
>
> - **`/ask`, `/allow`, `/auto`, `/deny` REST routes already existed** and are
>   wired in (`raiker/api/routes_control.py` — `GET /api/capability-modes/{cap}`
>   + four setters `.../{ask,allow,auto,deny}`). They had **no API-level test
>   coverage** (only the service layer was tested); added
>   `tests/test_api_decision_modes.py` (12 tests): default `ask`, owner sets all
>   four modes + round-trip, permissive-requires-executor `403`, `deny` always
>   selectable, AI principal refused `403` (mode unchanged), auth required.
> - **Default is `ask`** for every capability (`DEFAULT_DECISION_MODE`), confirmed.
> - **`/approve` is NOT the same function as `/allow`, so it was kept** (per the
>   task's own "if it serves the same function" condition). `/approve <id>` /
>   `/deny <id>` (approval inbox, `routes_approvals.py` `/resolve`) resolve **one
>   pending action**; `/allow` (canonical decision mode `allow`) sets a **standing
>   per-capability policy**. They are near-opposites (one is the human-in-control
>   gate, the other relaxes prompting), so merging them would be wrong. Documented
>   the distinction in `DECISION_MODES_SPEC.md` and the command reference.
> - **Naming: canonical mode is `allow`** (`always_allow` kept as a legacy alias).
>   Aligned CLI `/capability-mode` help + `use-raiker-command-reference.md` +
>   `DECISION_MODES_SPEC.md` to say `allow`. **Fixed a pre-existing broken test**:
>   the earlier rename commit (`68a1ddd`) changed the enum value to `allow` but
>   left `test_phase_5_decision_modes.py::test_owner_can_set_mode_ai_cannot`
>   asserting the old `always_allow` read-back — it was failing on `main`; now
>   asserts canonical `allow`.
> - Full suite **1190 passed, 1 warning**; ruff + mypy clean on changed sources;
>   all five `scripts/validate_*.py` pass.
> - **Still open toward "full-fledged AI agent" (next real-executor targets,
>   unchanged):** `vector_embedding_runtime`, `model_provider_runtime`, the
>   graph/semantic runtimes; live hosted-provider verification (evidence only).

## State as of 2026-07-05 (session end)

> **Where this session's work lives (read first):** Phase 4 slices 14–16 (plugin
> code runtime) merged via PR #95; doc-accuracy fixes merged via PR #96/#97;
> **Phase 5 slice 1 — capability decision modes (`ask`/`deny`/`allow`/
> `auto`)** merged via PR #98. The current in-flight branch
> `claude/handoff-document-review-jusao0` (restarted from `origin/main` after #98
> merged) carries **two things in one PR**: (1) the first **real Tier-6 executor**
> `reminder_runtime` (local-only reminder store — create/list; every other Tier-6
> domain stays fail-closed), and (2) the **start of the `docs/*` migration** into
> the Claude-Code-style IA (`docs/README.md` home + `docs/getting-started.md` +
> `docs/core-concepts.md`; remaining sections still point at existing detailed
> docs).
>
> This is part of the prioritized program (A–E): (A) Tier-6/remaining executors —
> **reminder + calendar + email all done** (local-only: reminders, calendar
> events, email drafts; email never sends). Next real-executor targets:
> `vector_embedding_runtime`, `model_provider_runtime`, and the graph/semantic
> runtimes; the remaining sensitive Tier-6 domains
> (finance/investment/medical/pregnancy/cctv/home-security/hardware) stay
> **fail-closed** until real integrations + threat models exist — no fake
> executors. (B) live provider verification; (C) reach/multi-user surface;
> (D) security hardening; (E) plugin-runtime remainder.
>
> **Docs guide (Claude-Code-style IA) — COMPLETE with sub-sections:** the seven
> section pages now live under **`docs/guide/`** (moved from `docs/`), each with
> an index + focused child pages (26 child pages total), plus a machine-readable
> **`docs/guide/manifest.json`** nav tree the future web Docs/Help panel can
> render. `docs/README.md` is the home/index and points into `guide/`. Canonical
> detailed specs stay at the `docs/` root as the source of truth (validators pin
> those paths, so they must NOT move). **Next docs step (planned, not done):** an
> `apps/web` "Raiker Docs / Help" panel — a read-only `GET /api/docs` +
> `/api/docs/{slug}` serving the manifest + rendered markdown, and a Svelte view.
>
> **Email `send` behavior (updated this session):** `email_runtime`'s `send` no
> longer hard-refuses. It now marks a draft `queued_for_send` (requires
> `draft_id`; `transmitted=false`) so a human sends it — and because the gate
> defaults to the `ask` decision mode, an AI-proposed `send` asks the human
> first. Raiker still never transmits (no SMTP/connector). See
> `docs/threat-models/email.md`.
>
> **How the local Tier-6 pattern works (reuse for future local domains):** a
> table migration + store insert/list methods + a small executor with
> `create`/`list` (metadata-only artifacts, content never in events) + threat
> model + register in `REAL_EXECUTOR_CAPABILITIES` + default registry. When
> promoting a domain that other tests assert is "unenableable/no-executor", also
> update: `scripts/validate_runtime_enablement_readiness.py`
> (`must_not_have_default_executor`), `tests/test_executor_default_registry.py`
> (`_SENSITIVE`), and `tests/test_security_regression_ui.py`
> (`SENSITIVE_DOMAIN_CAPS`).
>
> **Environment unblock (still relevant):** the "Ed25519/cffi bindings panic on
> import" blocker is a **missing `cffi`** (`ModuleNotFoundError: No module named
> '_cffi_backend'`). Fix locally with `pip install cffi` after
> `pip install -e ".[dev]"`. CI's fresh-runner install pulls `cffi` transitively.
> This session's runtime uses `/usr/local/bin/python3` (3.11); `pip install -e
> ".[dev]"` then `pip install cffi` gives a green full suite.

Previous pushed anchors (earlier sessions): slice 13 merge `deaab72`, slice 8
`c8ce3d5`, slice 7 `c571c9c`; config cwd fallback `29ec83a`.

Full suite green after reminder/calendar/email + docs work: **1178 passed, 1
warning** (decision modes +9, reminder +7, calendar/email +8); ruff clean, mypy
clean on changed
sources (remaining mypy output is environmental missing-stub noise for
`pytest`/`fastapi`/`httpx`/`cryptography` plus one pre-existing
`test_runtime_authority.py` item), and all five `scripts/validate_*.py`
validators passed.

- **Phase 4 slices 1–8 done.** Real governed executors now include
  `hosted_model_runtime` + `private_network_model_runtime` (slice 7): the
  production `ModelRouter` derives provider policy from the persisted
  capability gates, and every off-machine provider construction re-checks the
  owner egress allowlist `RAIKER_MODEL_EGRESS_ALLOWLIST` (empty = fail
  closed). See `docs/threat-models/hosted-models.md`.
- **Provider breadth (slice 8):** native Anthropic Messages adapter
  (`raiker/models/providers/anthropic_messages.py`, raw httpx, no SDK),
  hosted profiles `anthropic-hosted` (claude-opus-4-8), `openai-hosted`,
  `gemini-hosted-openai-compatible`; generic `hosted_api_key_missing`
  fail-closed check for all remote-hosted profiles.
- **E2E verified on a real local model:** `/model use --provider ollama
  --model gemma4:31b-cloud` + `raiker --prompt` completed a live gateway turn
  (events + checkpoint persisted). Use `gemma4:31b-cloud` for future manual
  Ollama testing (owner preference — faster).
- `anthropic-hosted` is **live-verified** (2026-07-06, operator key): a governed
  turn ran through the real path (gate enabled via control plane → gate-derived
  policy → owner egress allowlist enforced) and returned `finish_reason=stop`
  (usage input=29/output=17); the egress guard was confirmed fail-closed
  (`model_egress_denied` when the host is not allowlisted). `openai-hosted` /
  `gemini-hosted-openai-compatible` remain offline/mock-verified
  (`implemented_unverified`) until an operator supplies their keys.
- **Config packaging follow-up complete:** `ModelProfileRegistry.load()` and
  `ConnectorRegistry.load()` keep workspace-local `config/` overrides, then
  fall back to bundled `raiker.config` JSON resources. The wheel now includes
  `raiker/config/model-profiles.json` and
  `raiker/config/channel-connectors.json`; focused tests cover foreign cwd,
  packaged-resource fallback, and resource drift.
- **Ollama tool calls enabled and live-verified:** `ollama-local-openai-compatible`
  now advertises native OpenAI tool calls with text-JSON fallback
  (`supports_tool_calls=true`, `tool_call_mode=native_or_text_json`). Live
  localhost validation against `qwen3.5:9b` returned a native `list_directory`
  tool call, and Raiker's provider factory parsed the arguments as
  `{"path": "."}`.
- **Web dashboard parity for hosted models complete:** `/api/models`,
  `apps/web` Models, and Security Settings now surface hosted/private model
  gate state, off-machine profile count, and whether
  `RAIKER_MODEL_EGRESS_ALLOWLIST` is configured. The UI remains read-only for
  this status and never displays allowlist values or API keys.
- **Plugin manifest install slice complete:** `plugin_install` is now a real
  governed executor for local manifest validation + install-record creation
  only. It requires the integrated gate (default enabled, re-enable if disabled), `local_single_user_runtime`, a
  human `runtime_gate_manager`, confirmation token, and
  `docs/threat-models/plugins.md` ack. It verifies checksum, requires a
  signature presence marker, allows only safe read-only permissions, and writes
  `plugin_install_records`.
- **Plugin brokered read-only execution slice complete:** `plugin_execution_cap`
  is now a real governed executor only for installed plugins invoking
  `read_file`, `list_directory`, `glob`, or `grep` through `ToolBroker` and
  `PolicyEngine`. It requires `docs/threat-models/plugin-execution.md` ack and
  records `plugin_execution_records`. It does not import plugin code, run
  scripts, start processes, open network connections, write files, or activate
  hooks/MCP/LSP/monitors/panels.
- **Plugin revocation slice complete (slice 10):** `plugin_revocation_cap` is now
  a real governed executor and the fail-closed off-switch for the install/
  execution slices. A HUMAN `runtime_gate_manager` revokes an installed plugin
  (requires the integrated gate (default enabled, re-enable if disabled), `local_single_user_runtime`, a
  `docs/threat-models/plugin-revocation.md` ack, and a confirmation token). It
  flips the latest install record's status `installed` → `revoked` via
  `SQLiteStore.revoke_plugin_install_record` (never deletes records, edits
  permissions, or runs plugin code). After revocation, `plugin_execution_cap`
  fails closed with `plugin_revoked` before any broker call. Second revocation
  is an idempotent no-op (`plugin_already_revoked`). Runtime artifacts stay
  metadata-only (no reason label or permission payload leaked). Evidence:
  `tests/test_phase_4_plugin_revocation_runtime.py`.
- **Plugin dependency controls slice complete (slice 11):** the governed
  `plugin_install` path now validates declared manifest `dependencies` statically
  and fails closed before writing an install record. Each dependency must be an
  exact `(plugin_id, version)` pin (ranges/wildcards/`latest` → `dependency_unpinned`)
  and each dependency plugin id must be on the owner allowlist
  `RAIKER_PLUGIN_DEPENDENCY_ALLOWLIST` (comma-separated; empty = fail closed for
  any declared dependency → `dependency_not_allowlisted`). A dependency-free
  manifest is unaffected. Pure static validation in `raiker/plugins/dependencies.py`
  wired through `plan_plugin_registration`; no download, transitive resolution, or
  install. Evidence: `tests/test_phase_4_plugin_dependency_controls.py`.
- **Plugin signature verification slice complete (slice 12):** the governed
  `plugin_install` path now cryptographically verifies the manifest `signature`
  when the owner sets `RAIKER_PLUGIN_SIGNING_KEY` — the `signature` must be a
  valid HMAC-SHA256 over the canonical manifest body (same body the checksum
  covers) or the install fails closed (`signature_invalid` /
  `no_signature_in_manifest`, no record written). With no key set, the presence
  marker remains for local dev (unchanged, existing tests green). Trust-model
  limit: symmetric owner-held key (integrity + authenticity), complemented by the
  asymmetric Ed25519 scheme in slice 13.
  `raiker/plugins/verify.py` (`plugin_signing_key`, `expected_plugin_signature`,
  upgraded `verify_plugin_signature`). Evidence:
  `tests/test_phase_4_plugin_signature_verification.py`.
- **Ed25519 asymmetric signature verification slice complete (slice 13):** the
  governed `plugin_install` path now also verifies an asymmetric supply-chain
  signature when the owner sets `RAIKER_PLUGIN_ED25519_PUBLIC_KEY` (hex 32-byte
  public key) — the manifest `supply_chain.ed25519_signature` must be a valid
  Ed25519 signature (hex) over the same canonical body the checksum/HMAC cover,
  verified against that owner-trusted public key, or the install fails closed
  (`asymmetric_signature_invalid` / `no_asymmetric_signature_in_manifest` /
  `asymmetric_public_key_invalid` / `asymmetric_backend_unavailable` — never fails
  open) and writes no record. Unset → skipped (`asymmetric_not_configured`), so
  existing manifests are unaffected. Author signs off-machine with a private key
  Raiker never holds; owner configures only the trusted public key. HMAC and
  Ed25519 are enforced independently. `raiker/plugins/verify.py`
  (`plugin_ed25519_public_key`, `ed25519_signature_hex`,
  `verify_plugin_asymmetric_signature`, wired into `validate_supply_chain`);
  `cryptography>=41` added to `pyproject.toml` dependencies. Evidence:
  `tests/test_phase_4_plugin_asymmetric_signature.py`.
- **Plugin code runtime slice complete (slice 14, done this session):** the first
  capability that runs **arbitrary plugin code**. `plugin_runtime_cap` is a real
  governed executor (`PluginRuntimeExecutor` in
  `raiker/runtime/executors/tier4_plugins.py`) that runs an installed plugin's
  declared entrypoint as a **bounded subprocess** through the shared sandbox
  (`run_command`): interpreter allowlist (`python3`/`python`/`node`),
  workspace-scoped script path, default 30s / max 120s timeout, 200 KB output
  caps, argv-only (no shell). It fails closed unless the plugin has a non-revoked
  `installed` record **and** the owner names it in `RAIKER_PLUGIN_RUNTIME_ALLOWLIST`
  (empty = fail closed) — the owner grant, not the manifest, authorizes code
  execution (install still only records safe read-only perms). Fail-closed reason
  codes: `plugin_not_installed`, `plugin_revoked`,
  `plugin_runtime_not_allowlisted`, `interpreter_not_allowed:*`,
  `outside_workspace:entrypoint`, `entrypoint_not_found`, `too_many_args`,
  `plugin_runtime_sandbox:*`, `plugin_runtime_exit:<code>`. Artifacts are
  metadata-only (`output_redacted=true`); stdout/stderr never leak into events.
  Every attempt writes a `plugin_execution_records` row (new id prefix `plgrt_`).
  **Isolation limit (honest):** posture equals `shell_execution`/`process_execution`
  — separate process + resource/timeout bounds, but **no** in-process import
  isolation and **no** network-namespace jail (ambient host network); the
  `container_execution_cap` path is the stronger-isolation option. Threat model:
  `docs/threat-models/plugin-runtime.md`. Evidence:
  `tests/test_phase_4_plugin_runtime.py`.
- **Per-plugin runtime scope (slice 15, done this session):** extends
  `plugin_runtime_cap` (no new capability). `RAIKER_PLUGIN_RUNTIME_SCOPES`
  (`<plugin_id>:<subpath>`, comma-separated) narrows a plugin's entrypoint reach
  to `<workspace>/<subpath>` so the owner grant is not all-or-nothing
  (`entrypoint_outside_plugin_scope`; escaping subpath →`plugin_scope_invalid`;
  no entry → slice-14 behavior). `plugin_runtime_scopes()` +
  `_check_plugin_scope`. It constrains which entrypoint path may run, not the
  subprocess's own OS-level filesystem access.
- **Sandboxed network-isolated plugin runtime (slice 16, done this session):**
  new capability `plugin_sandboxed_runtime_cap` (`PluginSandboxedRuntimeExecutor`
  in `raiker/runtime/executors/tier4_plugins.py`). Runs the entrypoint **inside a
  container** with `--network none`, read-only rootfs, dropped caps, and only the
  single entrypoint file bind-mounted read-only at `/plugin` (workspace never
  mounted). Reuses the owner plugin allowlist + per-plugin scopes and adds an
  owner image requirement: `RAIKER_PLUGIN_RUNTIME_IMAGE` must be set **and** in
  `container_image_allowlist()` (`RAIKER_CONTAINER_IMAGE_ALLOWLIST`). Fail-closed
  codes add `plugin_runtime_image_unset`, `image_not_allowed`, `plugin_sandbox:*`
  (e.g. `docker_unavailable`), `plugin_sandbox_exit:<code>`. Injectable `runner`
  for daemon-free tests (mirrors `ContainerExecutionExecutor`). Metadata-only
  artifacts (`network_isolated=true`). Threat model:
  `docs/threat-models/plugin-sandboxed-runtime.md`. Evidence:
  `tests/test_phase_4_plugin_sandboxed_runtime.py`. **Still deferred:**
  in-process import isolation of plugin code in the host, and image build/pull
  management.

## How a user turns on a hosted provider (for reference / docs work)

1. `/runtime-mode activate local_single_user_runtime` (human owner).
2. Record a threat-model ack for `hosted_model_runtime`
   (`docs/threat-models/hosted-models.md`) and enable the gate with a
   confirmation token.
3. Set `RAIKER_MODEL_EGRESS_ALLOWLIST` to the provider host
   (`api.anthropic.com` / `api.openai.com` / `openrouter.ai` /
   `generativelanguage.googleapis.com`) and the provider key env
   (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `OPENROUTER_API_KEY` / `GEMINI_API_KEY`).
4. Select a concrete model:
   - `/model use anthropic-hosted` (concrete model in the profile), or
   - `/model use --provider openai --model gpt-4o-mini`, or
   - `/model use --provider openrouter --model openai/gpt-4o-mini`, or
   - `/model use --provider gemini --model gemini-2.0-flash`.
   These providers ship a placeholder `<model>`; the concrete model is supplied at
   selection time. `ModelProfileRegistry.resolve(provider, model)` now falls back
   to the provider's placeholder profile (filling in the model), so the CLI, the
   gateway turn path, and the direct `ModelRouter.achat`/`aembed` path are all
   consistent. Provider policy (gate + egress allowlist + API key) is still
   enforced by the provider factory regardless of how the model is selected.

## Next work, in priority order

> Completed items from earlier sessions were removed from this list to keep it
> actionable (config path resolution, `anthropic-hosted` live verification, Ollama
> tool-call support, the slice-7/8 web dashboard parity, and the web-app rebuild
> are all done — see the state sections above and `IMPLEMENTATION_STATUS.md`).

1. **Open hosted-provider verification (evidence only).** `anthropic-hosted` is
   `implemented_verified`. `openai-hosted` / `gemini-hosted-openai-compatible`
   remain to verify with a governed live turn when their operator keys are
   available (this cloud session's egress proxy blocks those hosts).
2. **Plugin runtime promotion (Tier 4).** Completed so far: `plugin_install`,
   brokered read-only `plugin_execution_cap`, `plugin_revocation_cap` (the
   off-switch, slice 10), install-time dependency controls (slice 11), HMAC
   manifest signature verification (slice 12), asymmetric Ed25519 signature
   verification (slice 13), **bounded-subprocess plugin code runtime
   `plugin_runtime_cap` (slice 14)**, **per-plugin filesystem scopes (slice 15)**,
   and **network-isolated container runtime `plugin_sandboxed_runtime_cap`
   (slice 16)** — slices 14–16 done this session. Plugin code now runs either as a
   bounded subprocess (ambient network) or fully network-isolated inside an
   owner-allowlisted container, both gated on the owner plugin allowlist +
   interpreter allowlist + workspace/subpath-scoped entrypoint. Still deferred, in
   likely-next order: (a) **in-process import isolation** of plugin code in the
   host (both runtimes execute out-of-process; there is still no governed path to
   `import` a plugin module into Raiker itself); (b) **image build/pull
   management** for the sandboxed runtime (owner currently supplies + allowlists
   the image out of band) and per-plugin **network egress** allowlisting for the
   bare-subprocess runtime; (c) plugin **hooks/MCP/LSP/monitors/panels**
   activation (each its own threat-model → executor → validator/guard-test →
   tests slice). Follow the slice discipline below for each.
3. **Web app follow-ups (optional, non-blocking).** The rebuild (PR #104) is
   complete and green. Nice-to-haves if revisited: a live model-reachability
   indicator on the Models page (the CLI has `/model health`; the web read
   deliberately does not probe the network), and surfacing retrieval/RAG toggles
   once that loop is exposed. None are required for the app to be usable.

## Slice discipline (repeat every slice)

Threat-model doc → real executor (fail closed on every missing precondition)
→ activation requirements → validator + guard-test updated in lockstep →
acceptance tests (executes-when-governed AND fails-closed-when-disabled) →
update `docs/IMPLEMENTATION_STATUS.md` + `docs/RUNTIME_EXECUTORS_SPEC.md` →
run `pytest`, `ruff check .`, `mypy raiker apps tests`, and all four
`scripts/validate_*.py` → commit → push to `origin/main`.
