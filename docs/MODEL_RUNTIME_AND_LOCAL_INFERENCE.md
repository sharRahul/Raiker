# Models and local inference

> **Corrected 2026-08-23.** Profiles live in **one** file:
> `raiker/config/model-profiles.json`, which is packaged with the wheel and
> resolved through `raiker.config` as a package resource
> (`raiker/models/registry.py::_BUILTIN_CONFIG_RESOURCES`), so an install with no
> repository root beside the package reads the same bytes a checkout does. This
> banner used to describe two copies that had to be kept identical, naming the
> same path twice and citing a test that no longer exists; the duplication was
> removed and the warning outlived it.

Raiker does not bundle a model. Configure a supported local OpenAI-compatible
server, then select a profile with `/model use <profile_id>`.

Local profiles are preferred. Hosted profiles require explicit policy, egress
allowlisting, an environment-provided credential, and applicable budget policy.
Raiker never silently falls back from local to hosted or to a test provider.

Model responses are untrusted proposals. Tool calls are validated and routed
through policy and RuntimeAuthority before any executor can act. Use `/models`,
`/model current`, `/model health`, and `/model capabilities` to inspect the
configured model surface.

## Provider adapters, and where their contracts are defined

**Three adapters ship** in `raiker/models/providers/`, alongside the
`AsyncModelProvider` protocol in `base.py`. Each speaks a documented wire
protocol; where a claim here is about a provider's behaviour rather than
Raiker's, the provider's own documentation is the source.

| Adapter | Serves | Vendor reference |
|---|---|---|
| `anthropic_messages.py` | Anthropic | [Messages API](https://docs.claude.com/en/api/messages), [extended thinking](https://docs.claude.com/en/docs/build-with-claude/extended-thinking), [models](https://docs.claude.com/en/docs/about-claude/models/overview) |
| `openai_compatible.py` | OpenAI, Gemini, OpenRouter, Hugging Face Inference Providers, Ollama, Ollama Cloud, LM Studio, vLLM, and any owner-supplied OpenAI-compatible endpoint | [OpenAI Chat Completions](https://platform.openai.com/docs/api-reference/chat), [Gemini OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai), [OpenRouter](https://openrouter.ai/docs), [Hugging Face Inference Providers](https://huggingface.co/docs/inference-providers/index), [Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md), [LM Studio server](https://lmstudio.ai/docs/app/api/endpoints/openai), [vLLM OpenAI server](https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html) |
| `llama_cpp_server.py` | A managed local `llama-server` | [llama.cpp server](https://github.com/ggml-org/llama.cpp/tree/master/tools/server) |

**There is no mock or test provider, and a profile that claims to be one is
refused.** This document previously listed a fourth `mock` adapter for
"deterministic offline testing"; no such adapter exists, and
`AsyncProviderFactory.create` rejects `provider` of `mock` or `test`, and any
profile carrying `test_only`, with `test_provider_not_available`. A profile whose
`default_state` is `enabled_for_tests_only` is refused with
`test_only_profile_not_runnable`. This matters beyond tidiness: a provider that
answers without a real model would let every readiness gate pass over an
endpoint that proves nothing.

The accepted `provider` values are exactly: `anthropic`, `openai`, `gemini`,
`openrouter`, `huggingface`, `ollama`, `ollama-cloud`, `lm-studio`,
`lm-studio-remote`, `llama-cpp`, `llama.cpp`, `llama-cpp-server`, `vllm` and
`openai-compatible`. Anything else fails closed with
`unknown_provider:<name>`. Thirteen profiles ship in
`raiker/config/model-profiles.json` across ten of those families.

Model acquisition additionally reads the
[Hugging Face Hub](https://huggingface.co/docs/hub/index) for revision-pinned
GGUF downloads, and the [GGUF format](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md)
for local file discovery.

**Shipped list prices are unverified defaults.**
`raiker/config/model-profiles.json` seeds a price only for the models whose
published rate is recorded there, each stamped with an `as_of` date. Check them
against your provider's current pricing page and override anything that has
moved; an unpriced model reports its cost as unknown rather than as zero.


## Readiness and model acquisition

A selected model becomes usable only after fresh evidence proves the exact
owner/profile/model/endpoint tuple. Local checks verify health and catalogue
presence; hosted checks add a bounded one-token execution preflight so
catalogue-only access is not presented as executable access. That preflight
distinguishes an exhausted account from an unreachable one: a provider that
answers the catalogue and then refuses to run the model for lack of credit or
quota is reported as `quota_exhausted`, because rotating the key or fixing the
network would repair neither.

The gate judges the chain the runtime will actually try — the selected model
followed by the owner's ordered fallback sequence — so a configured, ready
fallback keeps work moving and an unprobed one cannot be reached silently.

## Several local models at once

The managed llama.cpp runtime ships **four slots** — `raiker-local-llama-cpp`
through `raiker-local-llama-cpp-4` — each an ordinary profile with its own
loopback port (8080-8083) and its own served model name. Deploying a second GGUF
starts a second server rather than replacing the first, so Chat, Build, Tasks,
and Schedule can each run a different local model. A full pool refuses; it never
evicts a model another surface may be mid-turn on.

Four is a judgement, not a limit of the design: each slot is a resident process
holding weights in memory. Ollama and LM Studio serve many models from one
endpoint and are unaffected by this bound.

## A default model per surface

Chat, Build, Tasks, and Schedule each remember the model they were last set to
(`GET`/`PUT /api/surface-models`). A surface with no preference falls back to the
global model. This is a preference only: the turn it produces still names an
exact profile and model, and readiness judges that pair, so remembering a choice
can never make an unproven model runnable. Tasks and schedules additionally
capture the model onto the task itself, so a scheduled run keeps the model
chosen when it was scheduled.

## Acquisition

Models can open official Ollama and LM Studio setup sources, pull Ollama models,
index GGUF files only beneath owner-approved roots, and deploy complete GGUFs to
a managed `llama-server` bound to `127.0.0.1`. Hugging Face choices are pinned
to immutable revisions and downloaded into collision-safe snapshots. Optional
Safetensors conversion is explicit and runs in a networkless, digest-pinned,
resource-bounded container with read-only source weights.

The Hub cannot be browsed exhaustively, so the Hugging Face surface is
search-first. It opens on the most-downloaded GGUF repositories rather than an
empty box; that listing is the same unauthenticated read as a search and
downloads nothing.
