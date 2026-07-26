# Connecting a model

Connecting a provider is one step: paste your API key. That act is your
authorization — Raiker does not then ask you to satisfy a separate switch, a
separate allowlist, and a separate key before it will use what you just
configured.

This follows the project's stated posture (`docs/HANDOFF.md` → "Security
posture"): Raiker is **owner-authoritative and monitored, not
prevention-by-restriction**. Every turn is still policy-checked, audited, and
stoppable; what changed is that you are not made to prove a choice you already
made.

> **Local models (llama.cpp, Ollama, LM Studio)**: start the local server, press
> **Choose model…**, then **Select**. Nothing leaves your machine.

---

## Connect a hosted provider

**Models** → the provider's card → **Connect** → paste the key → **Connect**.

That is the whole flow. Behind it:

| What used to be required | What happens now |
|---|---|
| Turn on the **Hosted models** capability gate first | A saved connection is the authorization. The gate remains, and turning it **off** still revokes access. |
| Add the host to `RAIKER_MODEL_EGRESS_ALLOWLIST` and restart | The endpoint on the profile you configured is authorised — that host and no other. The environment variable still works for pre-authorising hosts before you configure them. |
| Generate a vault key in Settings first | The key is generated on first use at `0600`. Settings still owns viewing, rotating, and clearing it. |

Then press **Choose model…** — Raiker asks the provider for its live catalogue —
pick a model, and **Use model**.

### What is still refused

Consent by configuration is scoped, not a blanket opening:

- A provider you have **not** configured still fails closed.
- Configuring Anthropic authorises `api.anthropic.com`. It does not authorise
  any other host.
- A capability gate you **explicitly** turn off wins over a saved connection.
  Revocation is absolute, or the control would be theatre.
- Deferred dangerous domains — remote and cloud execution, finance, medical,
  pregnancy, CCTV, home security, hardware — have no governed executor and stay
  unavailable regardless.
- Critical actions still stop for approval, and the STOP switch still halts work
  at a safe boundary.

### Signing in with Google

**OpenAI** and **Gemini** cards offer a sign-in link. It opens the provider's own
console — where Google, Microsoft, and Apple sign-in all work — so you can create
an API key, which you then paste into Raiker.

**A ChatGPT subscription does not include API access.** ChatGPT Plus and Pro are
billed separately from the OpenAI API, and no subscription grants a third-party
application API access on your behalf. If you have Plus or Pro and no API
credit, calls will fail with a quota error however you signed in. The dialog says
this up front so it is not discovered through a 401.

Anthropic issues API keys only — there is no account sign-in to connect.

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
