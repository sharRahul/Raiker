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
catalogue-only access is not presented as executable access.

Models can open official Ollama and LM Studio setup sources, pull Ollama models,
index GGUF files only beneath owner-approved roots, and deploy complete GGUFs to
a managed `llama-server` bound to `127.0.0.1`. Hugging Face choices are pinned
to immutable revisions and downloaded into collision-safe snapshots. Optional
Safetensors conversion is explicit and runs in a networkless, digest-pinned,
resource-bounded container with read-only source weights.
