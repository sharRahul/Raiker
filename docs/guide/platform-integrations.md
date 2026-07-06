# Platform & Integrations

> Part of the Raiker documentation set. See also: [Use Raiker](use-raiker.md),
> [Core Concepts](core-concepts.md), [Capabilities](../RUNTIME_EXECUTORS_SPEC.md).

Raiker is backend-agnostic: you choose the LLM, and every off-machine
integration is governed by an owner allowlist and fails closed by default.

## Model backends

The choice of model belongs to you. Raiker speaks to:

- **Local runtimes** — llama.cpp, Ollama, LM Studio. No API key; nothing leaves
  the machine. Modern Ollama models (e.g. `qwen3`, `gemma4`) support native tool
  calls; Raiker uses them with a text-JSON fallback.
- **Home-lab** — vLLM and other private-network endpoints via
  `private_network_model_runtime`.
- **Hosted APIs** — Anthropic (native Messages adapter), OpenAI, Gemini, and
  OpenRouter via `hosted_model_runtime`.

Select one with `/model use --provider <p> --model <m>`.

### Turning on a hosted provider (governed)

Hosted/off-machine access is fail-closed until the owner opts in:

1. `/runtime-mode activate local_single_user_runtime`.
2. Record the threat-model acknowledgement for `hosted_model_runtime`
   (`docs/threat-models/hosted-models.md`) and enable the gate with a
   confirmation token.
3. Set the egress allowlist `RAIKER_MODEL_EGRESS_ALLOWLIST` (empty = fail closed)
   and the provider key env (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` /
   `GEMINI_API_KEY` / `OPENROUTER_API_KEY`).
4. `/model use anthropic-hosted` (or another hosted profile).

Every off-machine provider construction re-checks the same egress allowlist in
the provider factory, so a model-proposed endpoint can never bypass it. Provider
keys and allowlist values are never displayed in the UI or events.

## Channels

The reference channel (`external_channel_runtime` + `channel_approval_relay`) is
a single-owner outbound bridge with a connector auth model and an owner egress
allowlist (`RAIKER_CHANNEL_EGRESS_ALLOWLIST`, empty = fail closed). Inbound
content is treated as untrusted. See `CHANNELS_SPEC.md`.

## Execution environments

- **Local sandbox** — `shell_execution` / `process_execution` run through a
  bounded subprocess sandbox (timeouts, output caps, command allowlist).
- **Containers** — `container_execution_cap` runs an owner-allowlisted image with
  `--network none`, read-only rootfs, dropped capabilities, and resource limits.
- **Plugins** — installed plugins can run brokered read-only tools, a bounded
  subprocess (`plugin_runtime_cap`), or a fully network-isolated container
  (`plugin_sandboxed_runtime_cap`); all gated on an owner plugin allowlist and
  signed manifests (HMAC + Ed25519). See `PLUGIN_SYSTEM_SPEC.md` and
  `EXECUTION_ENVIRONMENTS_SPEC.md`.
- **Remote / cloud** — `remote_execution_cap` / `cloud_execution_cap` remain
  fail-closed by design pending real isolation + egress + secret handling
  (`docs/threat-models/remote-cloud.md`).

## Local personal-data integrations

`reminder_runtime`, `calendar_runtime`, and `email_runtime` are **local-only**:
they persist reminders, calendar events, and email drafts in the workspace with
no network, no external sync, and no delivery (email never sends). External
calendar sync and email delivery are deferred connector work with their own
threat models.

## Where to go next

- **[Capabilities](../RUNTIME_EXECUTORS_SPEC.md)** — the authoritative per-capability
  catalog of what executes today.
- **[Implementation](../IMPLEMENTATION_STATUS.md)** — build/verify/deferred ledger.

## In this section

- [Model Backends](platform-integrations-model-backends.md)
- [Execution Environments](platform-integrations-execution-environments.md)
- [Plugins](platform-integrations-plugins.md)
- [Channels](platform-integrations-channels.md)
