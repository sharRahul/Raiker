# Troubleshooting

Raiker refuses with a **named reason code** rather than failing vaguely. Each
one has a specific fix. Since the Models sign-in dialog now prints the fix
alongside the code, this table is the complete reference.

## Connecting a model

| Reason code | Meaning | Fix |
|---|---|---|
| `provider_requires_explicit_policy_approval` | The provider's runtime gate is off | Permissions → **Hosted models** (or **Home-lab models**) → Turn on |
| `hosted_provider_requires_explicit_policy` | Hosted access not enabled for your account | Permissions → **Hosted models** |
| `private_network_provider_requires_explicit_policy` | Private-network access not enabled | Permissions → **Home-lab models** |
| `model_egress_denied:no_allowlist` | No host is allowlisted for model egress | Restart with `RAIKER_MODEL_EGRESS_ALLOWLIST=<host>` |
| `model_egress_denied:<host>` | That host is not allowlisted | Add it to `RAIKER_MODEL_EGRESS_ALLOWLIST` and restart |
| `connector_vault_key_unset` | No vault key, so no credential can be encrypted | Settings → Security & Login → Generate key → Save key |
| `connector_vault_key_invalid` | The stored key is not a valid Fernet key | Same place; regenerate |
| `hosted_api_key_missing` | Hosted provider needs a key | Paste it into the sign-in dialog |
| `provider_api_key_missing:<VAR>` | Key absent from dialog and environment | Paste it, or set `<VAR>` before starting |
| `model_name_not_configured` | No model pinned on the profile | **Choose model…** on the provider card |
| `missing_endpoint` / `missing_endpoint_env:<VAR>` | No endpoint configured | Use **Advanced: custom endpoint**, or set `<VAR>` |
| `openrouter_requires_https` | OpenRouter needs HTTPS | Remove or fix the custom endpoint |
| `unknown_provider:<name>` | Unrecognised provider in a profile | Fix the profile in `config/model-profiles.json` |
| `test_provider_not_available` | Raiker ships no mock provider | Pick a real backend |

**Why the egress allowlist is not editable in the app.** It is the last boundary
before bytes leave your machine. If a browser session could widen it, a
compromised session could widen its own egress. It stays process configuration
on purpose.

## Capabilities and runtime

| Symptom | Cause | Fix |
|---|---|---|
| A surface says "enable it in Capabilities" but the gate **is** on | The gate is at `enabled_policy_gated`, not `enabled_runtime` | Settings → General → Runtime mode → activate a mode, then turn the gate on again |
| **Turn on** is missing entirely | Deferred capability — no governed executor exists | Nothing to do. Observability → Diagnostics lists all deferred capabilities |
| `Confirm change` stays greyed out | Reason, confirmation token, or threat-model tick missing | The confirmation token is **any phrase you type** — it records intent, it is not a credential |
| `disabled_by_capability_gate` from an API call | Gate off for your account | Permissions → find the capability → Turn on |

## Chat and turns

| Symptom | Cause |
|---|---|
| "No model is selected yet, so the runtime will refuse the turn" | Choose a profile in Models, or the Chat model selector |
| Raiker forgets what you said one message ago | **Known defect BUG-02** — prior turns are not sent to the model. Restate context in each turn. |
| Reply shows `# heading` and `\|table\|` as raw text | **Known defect BUG-03** — markdown is not rendered |
| Part of a reply reads `***REDACTED***` | **Known defect BUG-04** — over-broad redaction can wipe prose containing "secret", "token", or "password" |
| "Context capacity is not configured for this model" | That profile has no documented context window. Honest, not an error. |
| An approved file write produced no file | By design — approval is metadata-only (`executes_action: false`). See BUG-06. |
| `provider_connection_failed` | The provider was unreachable — check network, endpoint, and the fallback sequence |

## Server and session

| Symptom | Fix |
|---|---|
| Reload returns you to the lock screen | Expected. The bearer token is in memory only, never `localStorage`. |
| `Refusing to bind to non-loopback host … without --allow-public` | Add `--allow-public` **and** set `RAIKER_OWNER_TOKEN` |
| Dashboard is blank or stale | `npm --prefix apps/web run build`, then restart `raiker-web` |
| Backend change has no effect | Restart `raiker-web` — Python is not hot-reloaded |
| Too many device sessions listed | Settings → Security & Login → revoke individually, or change your password to sign out all other devices |

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
