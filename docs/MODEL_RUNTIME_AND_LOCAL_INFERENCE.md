# Models and local inference

Raiker does not bundle a model. Configure a supported local OpenAI-compatible
server, then select a profile with `/model use <profile_id>`.

Local profiles are preferred. Hosted profiles require explicit policy, egress
allowlisting, an environment-provided credential, and applicable budget policy.
Raiker never silently falls back from local to hosted or to a test provider.

Model responses are untrusted proposals. Tool calls are validated and routed
through policy and RuntimeAuthority before any executor can act. Use `/models`,
`/model current`, `/model health`, and `/model capabilities` to inspect the
configured model surface.


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
