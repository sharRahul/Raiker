# Threat model — generic network execution (`network_execution`)

`network_execution` is a gated egress capability with a registered executor and
**no reachable caller**. This document says so plainly rather than leaving the
gate undocumented, because an owner looking at a capability named "network" in
**Permissions** deserves to know exactly what turning it on would and would not
enable.

## Status

| Question | Answer |
|---|---|
| Has a real executor? | **Yes** — `NetworkExecutor`, `raiker/runtime/executors/tier2_web.py`, registered in `REAL_EXECUTOR_CAPABILITIES` |
| Reachable by a model? | **No.** `CAPABILITY_GATE_MAP` maps the action type `network` to it, but there is **no `network` tool** in `TOOL_DEFINITIONS`, so no model can propose one |
| Executed on approval? | **No.** It is not in `EXECUTABLE_ON_APPROVAL`; a `network` approval records the decision and executes nothing |
| Reachable by any product route? | **No** route, CLI command or orchestrator path constructs a `GovernedAction` with this action type |
| Exercised where? | `tests/test_vertical_slice_e2e.py` only |

The owner-facing consequence: **enabling this gate changes nothing about what the
agent can do.** The web read the agent actually performs answers to `web_fetch`
(see [`web-fetch.md`](web-fetch.md)), not to this.

## What the executor would do if reached

`NetworkExecutor.execute` requires a `url` argument and calls
`raiker.runtime.executors.sandbox.fetch_url` with `default_egress_allowlist()`:

- the host must glob-match one of four hard-coded entries — `api.github.com`,
  `raw.githubusercontent.com`, `pypi.org`, `files.pythonhosted.org` — or the call
  fails with `egress_denied:<host>`;
- bounds are `max_bytes` (default 200 000) and `timeout` (default 15 s);
- artifacts are `url`, `body_bytes` and `truncated`. **No response content is
  returned or logged**, which is the single most important property of this path.

## Threats and what stops them

| Threat | Mitigation | Where |
|---|---|---|
| Arbitrary egress on a model's say-so | The capability is not reachable from any tool; there is nothing for a model to call | `raiker/models/tool_registry.py` |
| An approval quietly performing a network request | `network_execution` is deliberately excluded from `EXECUTABLE_ON_APPROVAL`, and the approval detail says resolution is metadata-only | `raiker/approvals/execution.py` |
| Response content reaching the model or the log | The executor returns byte counts and a truncation flag, never a body | `tier2_web.py` |
| Unbounded transfer | `max_bytes` and `timeout` bounds | `sandbox.fetch_url` |

## Residual risk, stated plainly

This is the honest part, and it is why the capability is documented rather than
quietly left off the list:

- **`fetch_url` has none of `web_fetch`'s address guard.** It does not require
  HTTPS, does not reject credentials in the URL, does not check that resolved
  addresses are public, does not pin the connection, and lets `urllib` follow
  redirects freely. The four-host allowlist is the *only* control, and it is
  matched against `parsed.netloc` with `fnmatch` before the request — so a
  redirect from an allowlisted host to any other host is followed unchecked.
- **The allowlist is hard-coded, not owner-editable.** It is not read from
  `RAIKER_CONNECTOR_EGRESS_ALLOWLIST` or from any setting, so the owner can
  neither narrow nor widen it.
- **Two egress implementations is one too many.** `web_fetch` and
  `network_execution` share `tier2_web.py` and behave identically; the guarded
  path lives elsewhere. The right resolution is to remove the unreachable
  executors and the capability, or to route them through `WebAccessService`.
  Tracked in
  [the prioritised backlog](../REFERENCE_PLATFORM_COMPATIBILITY.md#5-prioritised-backlog);
  it is a **candidate for removal**, not a feature to complete.

Until then the accurate statement is the one at the top: the gate is real,
policy-reviewed and audited like every other, and nothing reaches it.

## Evidence

- `raiker/runtime/executors/tier2_web.py`, `raiker/runtime/executors/sandbox.py`
- `raiker/models/tool_registry.py` (no `network` tool),
  `raiker/approvals/execution.py` (not relayed)
- [`web-fetch.md`](web-fetch.md) — the path that *is* reachable
