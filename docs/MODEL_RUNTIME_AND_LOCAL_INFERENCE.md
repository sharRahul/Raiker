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
