# Connecting a model

Raiker will not talk to any model until you say so, and a hosted provider needs
four separate permissions. This is the fail-closed design working as intended —
but the order matters, and doing it out of order produces refusals that look
like faults. Follow the four steps below.

> **Local models (llama.cpp, Ollama, LM Studio) skip steps 1–3.** Start the
> local server, then go straight to step 4 and press **Select**. Nothing leaves
> your machine, so no gate, vault key, or allowlist is involved.

---

## Step 0 (hosted only) — allow the provider's host to be reached

The model egress allowlist is **process configuration**, not an in-app setting.
It is the last boundary before bytes leave your machine, so a browser session
can never widen it. Set it before starting the server:

```bash
export RAIKER_MODEL_EGRESS_ALLOWLIST='api.anthropic.com'
raiker-web --workspace . --no-browser
```

Comma-separated hostname globs. Common values:

| Provider | Host |
|---|---|
| Anthropic | `api.anthropic.com` |
| OpenAI | `api.openai.com` |
| Gemini | `generativelanguage.googleapis.com` |
| OpenRouter | `openrouter.ai` |
| Hugging Face | `router.huggingface.co` |
| Ollama Cloud | `ollama.com` |

Without it, connecting reports `model_egress_denied:no_allowlist`.

---

## Step 1 — activate a runtime mode

**Settings → General → Runtime mode.** The default, *Development preview*, keeps
every capability off, so gates can only reach a policy-gated state and surfaces
that require a true runtime capability stay disabled.

Choose **Local single user runtime**, press **Activate**, give a reason, and
confirm. The banner then reads *"Local single user runtime · active"*.

---

## Step 2 — set a vault key

**Settings → Security & Login → Connector Vault Key.** This Fernet key encrypts
every credential Raiker stores, so without it your API key cannot be saved at
all (`connector_vault_key_unset`).

Press **Generate key**, enter your password under *Confirm password (elevated
re-auth)*, then **Save key**. The badge flips to **Active / Valid**.

You can also generate one yourself:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

A passphrase will not work — it must be 32 random bytes as URL-safe base64.

---

## Step 3 — open the model capability gate

**Permissions.** Search for `Hosted` (or `Home-lab` for a private-network
endpoint), expand **Hosted models**, and press **Turn on**. The step-up dialog
asks for three things:

| Field | What to enter |
|---|---|
| Reason | Why you are making this change. Recorded against your principal. |
| Confirmation token | **Any phrase you type.** It is not a secret you have to obtain — it is a deliberate speed bump recording that a human intended this. |
| Threat-model acknowledgement | Tick to confirm you accept the risk. |

Without this you get `provider_requires_explicit_policy_approval`.

---

## Step 4 — connect the provider and pick a model

**Models.** Providers are grouped **On this device** (llama.cpp, Ollama, LM
Studio), **Your hosted providers** (Anthropic, OpenAI, Gemini), and **Advanced
connections** (Ollama Cloud, OpenAI-compatible, OpenRouter, Hugging Face). A
setup meter at the top tracks how many are ready.

1. Press **Connect** on the provider card.
2. Paste the API key. It is encrypted into this instance's vault and never
   returned to the browser. Use **Advanced: custom endpoint** for a proxy or a
   self-hosted gateway.
3. Press **Connect**. The card flips to **Connected**.
4. Press **Choose model…**. Raiker asks the provider for its live catalogue —
   for Anthropic that returns the current Claude models. If a provider does not
   support listing, type the model id instead.
5. Select a model and press **Use model**, then **Select** to make the profile
   active.
6. **Test** confirms the provider responds.

Chat's model selector then offers every *configured* profile — one with a pinned
model. It never lists an unconfigured provider and never accepts a free-text
model id.

---

## What each provider has cost you

Every provider card carries its own usage line: how many of its models you have
used, how many turns, and what they cost. A bar underneath shows that provider's
share of your total API spend, so it means something without you configuring a
budget. The page header totals it: *"1 of 10 providers set up · $0.0030 total
API cost"*.

Local providers show *"No API cost — runs on this machine"* instead of a bar.
A provider you have not used yet says *"Not used yet"*.

Prices come from the provider where one publishes them, from the list prices
shipped in `config/model-profiles.json` otherwise, and from your own override
above both. A model with no resolvable price reports its cost as unknown rather
than as zero. To set your own rate:

```
PUT /api/models/{profile_id}/price
{"model": "claude-opus-5", "input_per_mtok": "15", "output_per_mtok": "75"}
```

Send both rates as `null` to clear the override and fall back to the published
or shipped price.

## Fallback sequence

Below the provider grid, **Model fallback sequence** orders the backends Raiker
tries when the selected one is unavailable. Listing a hosted provider there
grants nothing on its own — each candidate is still gated by the same policy.
Point it at your local runtimes so a turn never dead-ends when a hosted API is
down.

---

## Advisor model

An optional second-opinion model, gated by `advisor_model_runtime`. Its answer
is always treated as untrusted data, never as instructions.

---

## If it still refuses

Every refusal is a named reason code with a specific fix. The sign-in dialog now
states the fix and links to the control that applies it. The full table is in
[Troubleshooting](troubleshooting.md).
