# Getting Started

> Part of the Raiker documentation set. See also: [Core Concepts](core-concepts.md),
> [Capabilities](../RUNTIME_EXECUTORS_SPEC.md), [Implementation](../IMPLEMENTATION_STATUS.md).

Raiker is a **security-first AI agent**: it can connect to any backend LLM —
local (llama.cpp / Ollama / LM Studio), home-lab (vLLM), or hosted API
(Anthropic / OpenAI / Gemini / OpenRouter) — and every capability it can perform
is **governed, default-disabled, and fail-closed**. Nothing runs until you, the
human owner, explicitly turn it on.

This page gets you from a clean checkout to your first governed action.

## 1. Install

```bash
python3 -m pip install -e ".[dev]"
# If Ed25519 plugin-signature verification panics on import, also:
python3 -m pip install cffi
```

Raiker targets Python 3.11+. The `[dev]` extra pulls pytest, ruff, and mypy.

## 2. Bootstrap the owner

The first human principal is the **owner** — the only role that can activate
runtime modes and enable capabilities.

```bash
raiker /bootstrap-owner --display "Your Name"
```

This creates the owner principal, the `runtime_gate_manager` role, and the
initial audit events. There is a `--force-recover` break-glass path if you ever
need to re-bootstrap.

## 3. Point Raiker at a model

Local models need no keys:

```bash
raiker /model use --provider ollama --model gemma4:31b-cloud
```

For a hosted provider, set the owner egress allowlist and the provider key, then
select a hosted profile — see [Platform & Integrations](../CONTRACTS.md) and
`docs/threat-models/hosted-models.md` for the full flow.

## 4. Turn on a capability (governed)

Every capability ships **disabled**. Enabling one is a deliberate, audited,
human-only act. For example, to allow local file writes:

```bash
raiker /runtime-mode activate local_single_user_runtime
raiker /capability-gate enable file_write_execution --state enabled_runtime --confirm <token>
```

Higher-risk capabilities additionally require a recorded **threat-model
acknowledgement** before they can be enabled.

## 5. Choose how the AI may act on it

Once a capability is enabled, its **decision mode** controls how AI-proposed
actions are treated — `ask` (the default), `deny`, `allow`, or `auto`:

```bash
raiker /capability-mode file_write_execution auto
```

`ask` means every AI-proposed action waits for your approval; `auto` lets Raiker
decide by risk; `allow` runs without prompting (critical-risk actions
still require you). See [Core Concepts › Decision modes](core-concepts.md#decision-modes).

## 6. Run

```bash
raiker --prompt "summarize the changes in the last commit"
```

Every action flows through the governed path (authority → policy → broker →
executor), and every step is written to the append-only event log. Approval
resolution is metadata-only — approving an action records a decision; it does
not itself execute anything.

## Where to go next

- **[Core Concepts](core-concepts.md)** — the governance model, principals,
  runtime modes, capability gates, decision modes, and the governed action path.
- **[Capabilities](../RUNTIME_EXECUTORS_SPEC.md)** — what Raiker can actually do
  today and what is still fail-closed.
- **[Implementation](../IMPLEMENTATION_STATUS.md)** — the control ledger of what is
  built, verified, or deferred.

## In this section

- [Installation](getting-started-installation.md)
- [Bootstrap the Owner](getting-started-bootstrap-owner.md)
- [Connect a Model](getting-started-connect-a-model.md)
- [Your First Governed Action](getting-started-first-action.md)
