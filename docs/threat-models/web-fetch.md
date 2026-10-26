# Threat model — web read (`web_fetch`)

`web_fetch` is the capability behind **both** the `web_fetch` and `web_search`
tools — one switch over "may the agent read the open internet". It is the point
at which **untrusted external text enters a turn**, which makes it the most
security-relevant read Raiker offers.

Unlike most acting capabilities the gate ships **on**: a reachable web read is
the point of the feature, and an agent that cannot read a library's documentation
guesses from training instead. The default decision mode still withholds.

## What the capability does

The model-facing path is `raiker/runtime/web_access.py` → `WebAccessService`. In
order, on every call:

1. the `web_fetch` capability gate (disabled ⇒ fail closed);
2. the per-capability decision mode — **default `ask` withholds**, `deny` blocks,
   and **`auto` withholds too**, because reaching the open internet on a model's
   say-so is never low-risk;
3. the owner's **flagged sites** (`RAIKER_WEB_EGRESS_BLACKLIST` plus the rules
   stored in Settings → Web access), empty by default and testable against a
   host without contacting it. **Owner's decision, 2026-10-25: a flagged site is
   read, with an alert, never refused.** The result opens with a *Raiker alert*
   line the model is told to pass on, and the row shows it. Plain `http` (a *not
   encrypted* alert), a URL with credentials (removed, with an alert), a page the
   injection scanner flagged before, and instruction-shaped text are alerted the
   same way;
4. the **address guard**, which still refuses: only `http` and `https`, and
   every address the name resolves to must be public; the built-in names
   (`localhost`, `*.local`, metadata hosts) are always refused;
5. every redirect hop (bounded at `MAX_REDIRECTS = 3`) re-checked against 3 and
   4, with the connection **pinned** to an address that already passed, or, for
   a name this machine cannot resolve, sent through the owner's `HTTPS_PROXY`
   unpinned (BUG-353, FIXED-1220).

Bounds: 400 000 bytes fetched, 20 000 characters delivered (a `question` reads
up to 400 000 characters of the page and delivers only the passages that bear on
it, within the same cap), 15-second timeout. `web_search` with depth `extended`
reads its top three results through this same path, each alerted on its own.

## Assets

| Asset | Why it matters |
|---|---|
| The private network the host sits on | A fetch is an outbound request originated *from inside* the owner's network |
| Cloud instance metadata endpoints | The classic SSRF target; a token there is a full compromise |
| The turn's instruction authority | Fetched text that is treated as instruction is a prompt-injection foothold |
| The owner's IP and request pattern | Every fetch discloses them to the destination |

## Trust boundaries

The destination is **chosen by a model**, and the content returned is **written
by a stranger**. Both are untrusted. The guard treats them as two separate
problems: where the request may go, and what the response may do.

## Threats and what stops them

| Threat | Mitigation | Where |
|---|---|---|
| SSRF to loopback, the LAN, or a cloud metadata service | `resolve_public_addresses` requires every resolved address to be public; `is_global` alone is not trusted, because an IPv4-mapped IPv6 address can defeat it, so the mapped form is unwrapped first | `raiker/runtime/web_policy.py` |
| DNS rebinding — the name passes, then resolves elsewhere for the real request | The connection is **pinned** to an address that already passed (`pinned_https_opener`), so the name cannot change between check and request | `web_access.py`, `web_policy.py` |
| A redirect to a private address | urllib's automatic redirect following is **disabled** — `redirect_request` returns `None` so the 3xx surfaces as an error the service handles, and each hop goes back through `check_url` | `web_access.py` |
| A plaintext or credential-bearing URL | `check_web_read` reads plain `http` with a *not encrypted* alert and strips userinfo before the request, with an alert; any scheme other than `http` and `https` is refused (`web_url_invalid`) | `web_access.py` |
| A flagged site being read at all | By the owner's decision it is read; the alert names the rule that matched and is shown on the row and in the content the model must pass on, so the owner sees every read of a site they flagged | `web_access.py`, `ToolActivity.svelte` |
| A proxy route bypassing the guard | Only a name this machine cannot resolve takes the proxy; the flagged-site rules still apply to it, a resolvable name is always pinned, and a literal private address never reaches the proxy | `web_policy.py` |
| Prompt injection in the page | The response is framed as **untrusted data, never instruction**. Additionally: scripts, styles and comments are dropped; elements no visitor could see (`hidden`, `display:none`, zero-size, off-screen, `aria-hidden`) are removed *and counted*; zero-width and bidirectional characters are stripped; a line shaped like a conversation role marker is defanged. What was removed is reported alongside the page | `raiker/runtime/web_sanitize.py` |
| A page persuades the agent to act | Nothing fetched raises a turn's authority. Every subsequent action still passes its own gate, decision mode and approval. The advisory injection scanner names the exact URL that carried the attempt — it reports, it never blocks | `raiker/security/` |
| Content leaking into the audit log | Broker events drop the content; the executor-side artifacts are byte counts | `raiker/tools/broker.py` |
| An unbounded page exhausting memory or context | 400 000-byte read cap, 20 000-character delivery cap, 15-second timeout | `web_access.py` |
| Emptying the flagged list opening the guard | The address guard is **not owner-editable and has no allow path**. Flagged-site rules and the address guard are separate controls | `web_access.py` |

## Residual risk, stated plainly

- **Nothing stops the agent reading a public page the owner would rather it did
  not.** Flagging a site makes every read of it visible; it does not prevent
  one (owner's decision, 2026-10-25). The decision mode is the control that
  stops a read, by asking first. The flagged list replaced a blocklist, which
  replaced an allowlist; the trade is documented in
  [§3.8](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#38-a-blocklist-plus-an-address-guard-instead-of-an-allowlist).
- **The injection scanner is a fixed pattern set, not a classifier.** It names a
  suspicious source and raises a finding; it never blocks. The control that
  actually stops a hijack is the deny-by-default tool gate, not the scan.
- **`web_search` shares this capability and this gate.** With no
  `RAIKER_WEB_SEARCH_ENDPOINT` configured, search goes to a keyless public
  endpoint (`html.duckduckgo.com`), so the query text reaches a third party.
  Results are untrusted data under the same alerts and address guard.
- **Behind a proxy the address guard cannot check what it cannot resolve.** A
  name this machine cannot resolve goes to the owner's proxy unpinned; the proxy
  resolves it, so a name that points at the proxy's own network is the proxy's
  to refuse. Only names reach the proxy, never a literal private address.
- **A second, weaker egress implementation exists in the tree.**
  `WebFetchExecutor` (`raiker/runtime/executors/tier2_web.py`) reaches the network
  through `sandbox.fetch_url` with a hard-coded four-host allowlist
  (`api.github.com`, `raw.githubusercontent.com`, `pypi.org`,
  `files.pythonhosted.org`) and **none** of the guards above — no HTTPS
  requirement, no public-address check, no redirect re-governance, no pinning. It
  returns byte counts only, never content. **Nothing in the product routes to it**
  — the model's `web_fetch` goes through the broker to `WebAccessService`, and
  `web_fetch` is not in `EXECUTABLE_ON_APPROVAL` — so it is exercised only by
  `tests/test_vertical_slice_e2e.py`. It is nevertheless registered in the default
  executor registry, which means a future caller reaching it by capability name
  would get the weaker path. Tracked in
  [the backlog](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#5-prioritised-backlog).

## Evidence

- `raiker/runtime/web_access.py`, `raiker/runtime/web_policy.py`,
  `raiker/runtime/web_sanitize.py`, `raiker/tools/web_tools.py`
- [`../KNOWN_LIMITS.md`](../architecture/KNOWN_LIMITS.md) — the owner-facing statement of the same boundaries
- [`../OWASP_GENAI_SECURITY_MAPPING.md`](../architecture/OWASP_GENAI_SECURITY_MAPPING.md) — LLM01 prompt injection, LLM05 improper output handling
