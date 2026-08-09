# Troubleshooting

Raiker refuses with a **named reason code** rather than failing vaguely. Each
one has a specific fix. Since the Models sign-in dialog now prints the fix
alongside the code, this table is the complete reference.

## Connecting a model

Three codes that used to block a first-time setup no longer occur when you
connect a provider through the app — configuring it is your authorization, the
endpoint you configured is authorised with it, and the vault key provisions
itself. They remain below because they can still appear for a provider you have
**not** configured, or one you explicitly revoked.

| Reason code | Meaning | Fix |
|---|---|---|
| `provider_requires_explicit_policy_approval` | You have configured no provider, or you explicitly turned this one off | Connect the provider in **Models**. If you previously turned **Hosted models** off in Permissions, turn it back on — an explicit revocation outranks a saved connection. |
| `hosted_provider_requires_explicit_policy` | Same, for hosted providers | As above |
| `private_network_provider_requires_explicit_policy` | Same, for a home-lab endpoint | As above, via **Home-lab models** |
| `model_egress_denied:<host>` | That host is not the endpoint of any provider you configured | Connect the provider whose endpoint it is, or pre-authorise it with `RAIKER_MODEL_EGRESS_ALLOWLIST=<host>` |
| `model_egress_denied:no_allowlist` | An off-machine endpoint with no configured connection and no environment allowlist | Connect the provider, or set `RAIKER_MODEL_EGRESS_ALLOWLIST` |
| `connector_vault_key_invalid` | The stored key is not a valid Fernet key | Settings → Security & sign-in → Generate key |
| `connector_vault_key_unset` | Only on a **read**: credentials exist but the key is gone, so they cannot be decrypted | Restore the key, or clear and re-enter the affected credentials. Writes provision a key automatically; reads deliberately do not, because minting a new key would hide a real problem. |
| `hosted_api_key_missing` | Hosted provider needs a key | Paste it into the sign-in dialog |
| `provider_api_key_missing:<VAR>` | Key absent from dialog and environment | Paste it, or set `<VAR>` before starting |
| `model_name_not_configured` | No model pinned on the profile | **Choose model…** on the provider card |
| `missing_endpoint` / `missing_endpoint_env:<VAR>` | No endpoint configured | Use **Advanced: custom endpoint**, or set `<VAR>` |
| `openrouter_requires_https` | OpenRouter needs HTTPS | Remove or fix the custom endpoint |
| `unknown_provider:<name>` | Unrecognised provider in a profile | Fix the profile in `config/model-profiles.json` |
| `test_provider_not_available` | Raiker ships no mock provider | Pick a real backend |
| `model_not_checked` / `model_readiness_expired` | No fresh proof exists for this exact profile, model, and endpoint | Open **Models**, choose the model, and press **Check again**. |
| `local_runtime_unreachable` / `local_runtime_missing` | The selected Ollama, LM Studio, or llama.cpp service is stopped or absent | Start/install the named runtime, pull or load the exact model, then check again. |
| `local_model_missing` / `provider_model_missing` | The provider is reachable but its catalogue does not contain the exact selection | Pull, load, or choose a listed model. |
| `provider_execution_refused` | A hosted catalogue succeeded, but a one-token execution preflight was refused, commonly because of account access or billing | Review the provider credential, model entitlement, and API credit, then check again. |
| `model_unavailable: provider_error_unclassified` | A legacy or mid-turn provider failure that could not be classified | Return to **Models** and run the readiness check. BUG-69 prevents this from being a fresh user's first action. |
| `model_unavailable: provider_stream_failed` | The provider stream ended in an error the adapter wrapped into one code. Reproducibly emitted by any turn that calls `web_fetch` while Web fetch is at **Allow** | If the turn used `web_fetch`, set Web fetch back to `ask` — **BUG-72**. Otherwise retry; the underlying error is not currently logged |

**How egress is decided.** Configuring a provider authorises that profile's own
endpoint — that host, and nothing else. There is no blanket opening, and no
in-app control that widens egress to an arbitrary host: to reach a host that
belongs to no configured provider you still set `RAIKER_MODEL_EGRESS_ALLOWLIST`
in the process environment.

## Capabilities and runtime

| Symptom | Cause | Fix |
|---|---|---|
| A surface says "enable it in Capabilities" but the gate **is** on | The gate is at `enabled_policy_gated`, not `enabled_runtime` | Turn it on again from **Permissions** and pick the runtime level. If it still will not go, the agent runtime itself is disabled — Settings → Runtime configuration → Enable |
| `activation_blocked: runtime_mode_not_active` | The agent runtime is disabled. It no longer names one of five modes — there is one runtime | Settings → Runtime configuration → **Enable agent runtime** |
| **Turn on** is missing entirely | Deferred capability — no governed executor exists | Nothing to do. Observability → Diagnostics lists all deferred capabilities |
| `Confirm change` stays greyed out | Reason, confirmation token, or threat-model tick missing | The confirmation token is **any phrase you type** — it records intent, it is not a credential |
| `disabled_by_capability_gate` from an API call | Gate off for your account | Permissions → find the capability → Turn on |

## Chat and turns

| Symptom | Cause |
|---|---|
| "No model is selected yet, so the runtime will refuse the turn" | Choose a profile in Models, or the Chat model selector |
| Raiker forgets what you said one message ago | **Fixed.** Prior completed turns of the session are replayed to the model, bounded by the model's context window. A turn with no reply is skipped, and other chats are never mixed in. |
| Reply shows `# heading` and `\|table\|` as raw text | **Fixed** (FIXED-06). Replies render as Markdown, with each code block labelled by language and carrying a keyboard-reachable **Copy code**. Your own prompts are deliberately shown exactly as typed. |
| Part of a reply reads `[REDACTED_TOKEN]` or `[REDACTED_EMAIL]` | Working as intended — the response layer masks the matched span of anything credential-shaped. Prose that merely *mentions* a secret is left alone (**fixed**, FIXED-07). |
| "Context capacity is not configured for this model" | That profile has no documented context window. Honest, not an error. |
| An approved file write produced no file | **Fixed** (FIXED-08). An approved `write_file`/`edit_file`/`apply_patch` is carried out once, re-governed at execution time and checkpointed first. If it still records only, one of `approval_execution_relay` or the target's own capability is off in Permissions, and the approval detail says so before you decide. |
| An approved **network** or **process** action produced nothing | By design — those two keep metadata-only resolution (`executes_action: false`). The parked turn still continues, with an honest "approved, but not executed" result. |
| `provider_connection_failed` | The provider was unreachable — check network, endpoint, and the fallback sequence |

## Server and session

| Symptom | Fix |
|---|---|
| Reload returns you to the lock screen | Expected. The bearer token is in memory only, never `localStorage`. |
| `Refusing to bind to non-loopback host … without --allow-public` | Add `--allow-public` **and** set `RAIKER_OWNER_TOKEN` |
| Dashboard is blank or stale | `npm --prefix apps/web run build`, then restart `raiker-web` |
| Backend change has no effect | Restart `raiker-web` — Python is not hot-reloaded |
| Too many device sessions listed | Settings → Security & sign-in → revoke individually, or change your password to sign out all other devices |

## Environment variables

| Variable | Purpose |
|---|---|
| `RAIKER_MODEL_EGRESS_ALLOWLIST` | Hosts model providers may be reached on. Empty = every off-machine provider fails closed. |
| `RAIKER_CONNECTOR_EGRESS_ALLOWLIST` | Hosts service connectors may be reached on |
| `RAIKER_CONNECTOR_VAULT_KEY` | Overrides the workspace vault key file |
| `RAIKER_OWNER_TOKEN` | Required with `--allow-public` |
| `RAIKER_WEB_UI_DIR` | Alternative dashboard build directory |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `HF_TOKEN`, `OLLAMA_API_KEY` | Provider keys, if you prefer the environment over the vault |

## Where to look next

- **Observability → Diagnostics** — runtime mode, readiness checks, per-profile
  provider status, configuration gaps, deferred capabilities.
- **Observability → Audit log** — every governed step, filterable.
- **[To be fixed](../plans/TO_BE_FIXED.md)** — known defects with reproductions.
- **[Live manual test plan](../plans/RAIKER_LIVE_MANUAL_TEST_PLAN.md)** — what
  was verified working, with screenshots.
