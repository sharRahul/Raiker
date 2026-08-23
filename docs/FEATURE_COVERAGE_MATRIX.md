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
| In-product user guide | implemented_verified | Eight sections served read-only from the install, deep-linkable, reached from each page's own link; a build shipping no guide reports it rather than showing an empty list |
| Model profiles and universal readiness | implemented_verified | Exact owner/profile/model/endpoint evidence gates Workbench, Chat, Build, Tasks, and Schedule; hosted checks include a bounded execution preflight |
| Local model acquisition | implemented_verified | First-run setup, official Ollama/LM Studio sources, Ollama pull, approved-root GGUF discovery, and managed loopback llama.cpp deployment |
| Hugging Face acquisition and conversion | implemented_policy_gated | Immutable GGUF-first snapshots; gated/licence review; explicit Safetensors conversion in a digest-pinned networkless worker |
| Policy, approvals, audit | implemented_verified | Approval resolution executes approved file mutations and eleven other capabilities besides — the complete set is `EXECUTABLE_ON_APPROVAL` (`raiker/approvals/execution.py`), each relayed and re-governed at execution time; metadata-only for every other capability, including `process` and `network` |
| Checkpoint capture | implemented_verified | A pre-image is captured before every approved mutation, automatically |
| Checkpoint rewind | implemented_read_only | `CheckpointRestoreExecutor` exists, is registered and is tested, and **no route, command or tool proposes a restore** — every owner surface computes a preflight and performs nothing |
| Audit export | implemented_read_only | `raiker/events/export.py` produces a redacted export manifest into the store; **no REST route surfaces it** |
| Per-turn machine identity | implemented_verified | Embedded Ed25519 issuer; broker verifies workspace/owner/session/turn/audience before policy or credentials; actions name the machine proposer and human authorizer separately |
| Local runtime executors | implemented_policy_gated | Gate and decision mode checked per action |
| Memory MVP | implemented_verified | Proposal decisions, scope/expiry changes, forget/purge, and owner-scoped history are governed |
| Build workspace (coding surface) | implemented_policy_gated | Composer modes set real decision modes; repository references grant nothing and fail closed |
| Repository code map | implemented_policy_gated | Local, derived symbol index behind `code_map_indexing`; built on connect and on request, refreshed for the paths an approved write touched, returned to the model as coordinates and carried into the turn as untrusted context |
| Scheduled background agents | implemented_policy_gated | One governed turn per cycle; unknown cadences refused |
| SSH/Daytona execution | implemented_approval_required | Owner profile and env-only credential references; no local-to-remote fallback. Both are relayed by an approval; the supervisor install/upgrade lifecycle and live remote proof remain open (BUG-194) |
| Hooks | implemented_policy_gated | Sixteen lifecycle events, all emitted, derived from the call sites by test; `command` and `builtin` handlers; an owner off switch; per-rule "can decide" vs "observes only". Sixteen of the thirty-one events and one of the five handler types the reference format documents — see [reference compatibility](REFERENCE_PLATFORM_COMPATIBILITY.md#25-extensibility--hooks) |
| Plugins | implemented_policy_gated | Manifest validation, supply-chain checks and a stated signature level; contributes hook rules, skills (installed inactive) and MCP-server *offers*, each behind its own declared permission; revocation deletes what was contributed. No plugin code executes |
| Channels | implemented_policy_gated | Pairing, enable switch, sender allowlist, inbound secret, 60/min per sender, signed outbound delivery. An inbound message is untrusted content with a named sender and never becomes work on its own; routing modes and approval relay are not built (BUG-225) |
| Semantic memory retrieval | implemented_policy_gated | Hybrid retrieval runs lexical, vector and graph legs and names which found each hit. The default vector space is a feature-hashing bag-of-tokens embedding with no model, so a paraphrase is recalled only through shared words (MEM-10) |
| Sensitive domains | disabled_deferred | Finance, medical, CCTV, hardware, and similar domains fail closed without an executor |

Strict non-allow blocking, role revoke governed, and capability gate per action
are enforced. The detailed current posture is [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).
