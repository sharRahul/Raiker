# Feature coverage

> runtime_enablement_candidate: completed
> controlled_runtime_mode_activation: implemented
> local_single_user_production_hardening: implemented
> production_ready_local_single_user_runtime: ready

| Area | Status | Notes |
|---|---|---|
| Terminal client and loopback dashboard | implemented_verified | Share the governed backend |
| Turn transparency in the transcript | implemented_verified | One line per tool call in proposal order — icon, tool in the owner's language, and what it acted on — with pending, waiting, failed and refused states; the phrase is resolved server-side under the durable event's own redaction, so a row can never say more than the audit log. Shown live and not retained (BUG-215) |
| Model reasoning in the transcript | implemented_verified | The provider's own extended thinking, collapsed above the answer and absent when a turn produced none; the request spelling is negotiated with the model rather than declared. Shown live and not retained (BUG-215) |
| In-product user guide | implemented_verified | Fifteen sections served read-only from the install (`docs/guide/`), deep-linkable, reached from each page's own link; a build shipping no guide reports it rather than showing an empty list |
| Model profiles and universal readiness | implemented_verified | Exact owner/profile/model/endpoint evidence gates Workbench, Chat, Build, Design, Tasks, and Schedule; hosted checks include a bounded execution preflight |
| Model destination authorization | implemented_verified | An off-machine model is reached only through the owner's saved connection, at that connection's own origin ([ADR-0004](../adr/ADR-0004-connection-bound-model-authorization.md)); `RAIKER_MODEL_EGRESS_ALLOWLIST` is retired and ignored |
| Model dial-time address guard | implemented_verified | Each new connection resolves once and every answer is classified against the connection's class (hosted public, home lab private, local loopback, link-local only by opt-in, metadata never); the passing address is pinned and TLS keeps the name. A proxied hosted request is resolved by the proxy and is not pinned (FIXED-1021 to FIXED-1030) |
| Local model acquisition | implemented_verified | First-run setup, official Ollama/LM Studio sources, Ollama pull, approved-root GGUF discovery, and managed loopback llama.cpp deployment |
| Hugging Face acquisition and conversion | implemented_policy_gated | Immutable GGUF-first snapshots; gated/licence review; explicit Safetensors conversion in a digest-pinned networkless worker |
| Policy, approvals, audit | implemented_verified | Approval resolution executes fourteen capabilities — the complete set is `EXECUTABLE_ON_APPROVAL` (`raiker/approvals/execution.py`), each relayed and re-governed at execution time; metadata-only for every other capability, including `process` and `network` |
| Checkpoint capture | implemented_verified | A pre-image is captured before every approved mutation, automatically |
| Checkpoint rewind | implemented_approval_required | `POST /api/checkpoints/{id}/restore`, `/checkpoints restore <id> --confirm` and the Chat/Build rewind control raise an ordinary approval for `checkpoint_restore_execution`, which recomputes the plan and captures its own pre-image first. No model tool proposes a restore |
| Audit export | implemented_policy_gated | `POST /api/audit/export` (Observability → Audit log → Export) runs `audit_export`: the owner's own records, redacted as on screen, listed and downloadable, and itself audited. `telemetry_export` sends the same record to an owner-named OTLP collector |
| Per-turn machine identity | implemented_verified | Embedded Ed25519 issuer; broker verifies workspace/owner/session/turn/audience before policy or credentials; actions name the machine proposer and human authorizer separately |
| Local runtime executors | implemented_policy_gated | Gate and decision mode checked per action |
| Memory MVP | implemented_verified | Proposal decisions, scope/expiry changes, forget/purge, and owner-scoped history are governed |
| Build workspace (coding surface) | implemented_policy_gated | Composer modes set real decision modes; repository references grant nothing and fail closed. Turns bind to their target, tasks get their own worktree with commit provenance, and a review validator checks the exact patch |
| Design workspace | implemented_policy_gated | Images through the `image_generation` gate and a saved provider connection; structured documents, typed versioned operations, design systems, agent proposals applied only by owner acceptance, validation, export and Build handoff. Remaining gaps are BUG-348 |
| Repository code map | implemented_policy_gated | Local, derived symbol index behind `code_map_indexing`; built on connect and on request, refreshed for the paths an approved write touched, returned to the model as coordinates and carried into the turn as untrusted context |
| Scheduled background agents | implemented_policy_gated | One governed turn per cycle; unknown cadences refused |
| SSH/Daytona execution | implemented_approval_required | `remote_execution_cap` and `cloud_execution_cap`: owner profile, pinned host key, cumulative cost ceiling and env-only credential references; no local-to-remote fallback. Both are relayed by an approval; the supervisor install/upgrade lifecycle and live remote proof remain open (BUG-194) |
| Hooks | implemented_policy_gated | Twenty lifecycle events, all emitted and derived from call sites by test; `command`, bounded tool-free `prompt`, `http` (behind the owner's hook egress allowlist) and Raiker `builtin` handlers; an owner off switch; per-rule "can decide" vs "observes only". `ConfigChange` intercepts authenticated settings writes with changed-key metadata only and cannot veto the kill switch. Twenty of external coding assistant's thirty-one events and three of its five handler types — see [reference compatibility](REFERENCE_PLATFORM_COMPATIBILITY.md#25-extensibility--hooks) |
| Plugins | implemented_policy_gated | Manifest validation, supply-chain checks and a stated signature level; contributes hook rules, skills (installed inactive) and MCP-server *offers*, each behind its own declared permission; revocation deletes what was contributed. Brokered read-only tool use (`plugin_execution_cap`); an entrypoint runs only when owner-allowlisted and digest-pinned (`plugin_runtime_cap`), in a no-network container when one is set up (`plugin_sandboxed_runtime_cap`) |
| Channels | implemented_policy_gated | Pairing, enable switch, sender allowlist, inbound secret, 60/min per sender, signed outbound, owner-stored routing, tool-free side questions, interrupt/steer, and exact single-use owner approval response. Channel content is structurally data and cannot raise authority (FIXED-298). |
| Semantic memory retrieval | implemented_policy_gated | Hybrid retrieval runs lexical, vector and graph legs and names which found each hit. The default vector space is a feature-hashing bag-of-tokens embedding with no model, so a paraphrase is recalled only through shared words (MEM-10) |
| MCP client | implemented_policy_gated | Negotiates revision `2026-07-28` (accepts `2025-06-18`, `2025-03-26`, `2024-11-05`); the bounded `initialize` / `tools/list` / `tools/call` session over `stdio` or Raiker's own `http` client. Streamable-HTTP sessions, OAuth and `server/discover` are not implemented |
| Sensitive domains | disabled_deferred | Finance, investment, medical, pregnancy, CCTV, home-security and hardware domains fail closed without an executor |

Strict non-allow blocking, role revoke governed, and capability gate per action
are enforced. Of the 70 declared capabilities, 50 have a real executor (`REAL_EXECUTOR_CAPABILITIES`). The detailed current posture is [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md); reconciled with the code on 2026-10-20.

## Personal-agent coverage boundary

The [target architecture](../plans/PERSONAL_AUTONOMOUS_AGENT_SPEC.md) reuses current
Chat/Build, tasks/routines, memory, models and governed connectors. Dedicated
goals, standing intents, aggregate goal budgets and workflow-level outcome
verification are contract_only target design, not shipped feature checkmarks.
Interactive browser control remains disabled_deferred under ADD-23. PAA-01–11
in the [delivery plan](../plans/PERSONAL_AUTONOMOUS_AGENT_SPEC.md) define
what must land and be evidenced before extending this matrix.
