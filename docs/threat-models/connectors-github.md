# Threat Model — GitHub Connector (web-app task 4)

> Status marker: runtime_enablement_candidate — real executor, default-ask
> decision mode, owner env-only credential, owner egress allowlist,
> metadata-only events.
>
> **2026-10-12.** This page described a read-only slice. The connector has
> since gained approval-gated writes (`github_write`: `create_comment`,
> `create_pull_request`, B11), described below. Its credential is still the
> environment variable only; it does **not** use the Git push credential broker.
> The accepted [GitHub connection specification](../architecture/GITHUB_CONNECTION_SPEC.md)
> (DEC-21b as amended) plans to move it onto the shared broker for credential
> selection and lending (ADD-27 GH-56) without changing its gate or approvals.

Per-capability threat model required by
[`docs/architecture/RUNTIME_EXECUTORS_SPEC.md`](../architecture/RUNTIME_EXECUTORS_SPEC.md) before
`connector_github_runtime` may join `REAL_EXECUTOR_CAPABILITIES`. This is the
**reference slice** for Task 4 (governed service connectors); Gmail / Calendar /
Slack replicate the same store-nothing-new pattern.

## What this capability is

A model may read one GitHub **issue** or **pull request** through a brokered
tool, `github_read(resource, repo, number)`. The fetched content is returned to
the model as **untrusted data, never instructions**.

It may also **propose** one of two writes through `github_write(operation, repo,
…)`: `create_comment` on an issue or pull request, or `create_pull_request`
from a pushed head to a base. `github_write` is high risk, approval-required and
not delegable; it runs only when `route_action` dispatches an approved action
(or, outside the router, when the gate is on and the decision mode allows it),
and its artifacts are metadata only — repository, number, comment or PR id and
URL, never the body. Other modifications (merge, close, labels, reviews, branch
or repository changes) are not implemented and fail closed.

Two surfaces, one governance:

1. **Chat-path tool** (`raiker/runtime/connectors.py::GithubConnectorService`,
   brokered as `github_read`): enforces, in order — the
   `connector_github_runtime` gate (disabled ⇒ fail closed), the per-capability
   decision mode (**default `ask` ⇒ the read is withheld**; `deny` ⇒ blocked;
   `auto` withholds too, because a network read carrying the owner token's repo
   scope off-machine is never low-risk), the owner credential
   (`RAIKER_GITHUB_TOKEN` unset ⇒ fail closed), the owner egress allowlist
   (`api.github.com` absent from `RAIKER_CONNECTOR_EGRESS_ALLOWLIST` ⇒ fail
   closed), and validated request components.
2. **Governed-action executor**
   (`raiker/runtime/executors/connectors.py::GithubConnectorExecutor`, operation
   `read`): the activation anchor for the gate. Reached only through
   `route_action` (which applies the gate, decision mode, and approval flow);
   artifacts are **metadata only** — resource, repo, number, title, state, and
   content length — never the fetched body.

## Boundaries enforced (fail-closed)

| Control | Mechanism |
|---|---|
| Gate off ⇒ nothing runs | `connector_github_runtime` state read from the persisted control plane; absent/disabled ⇒ `connector_gate_disabled`. |
| Default `ask` withholds | Decision mode `ask` (the default) and `auto` return `connector_withheld:*` without contacting GitHub; only an explicit owner `allow` lets standing reads run. `deny` ⇒ `connector_denied_by_decision_mode`. |
| Owner credential, env only | The token comes from `RAIKER_GITHUB_TOKEN` — never from tool arguments, the prompt, or the UI. Unset ⇒ `connector_not_configured`. |
| Owner egress allowlist | `api.github.com` must be on `RAIKER_CONNECTOR_EGRESS_ALLOWLIST` (empty ⇒ deny). Absent ⇒ `connector_egress_denied`. A second, independent boundary on top of the fixed host. |
| No SSRF via model input | The model never supplies a URL. `resource` (`issue`, `pull_request`, and since TOOL-20 – TOOL-29 `checks`, `workflow_runs`, `run_jobs`, `commits`, `file`, `branches`, `tags`, `releases`, `search_code`, `issues`, `search_issues`, `issue_comments`, `review_comments`, `account`, and since the third round `collaborators`, `teams`, `sub_issues`), `repo` (`owner/name`), `number` (positive int), `ref` (branch-shaped) and `path` (no `..`, a bounded character set) are validated and the request URL is **built server-side** against the fixed host. Bad inputs ⇒ `unsupported_resource` / `invalid_repo` / `invalid_number` / `invalid_ref` / `invalid_path`. |
| Narrow tokens per read | An App installation token is minted per operation: CI reads ask for `checks: read` and `actions: read` (`read_checks`), history and file reads for `contents: read` (`fetch`). |
| Writes stay narrow | `update_pull_request` (TOOL-26) sends only a title and body as one PATCH under approval; state, base branch and merging are not reachable, and a branch-scoped delegation cannot cover it ([FIXED-1199](../plans/FIXED_ITEMS.md#fixed-1199--a-pull-request-raiker-opened-could-not-be-corrected-tool-26)). The second round adds three writes, each asked first: a reply in a review thread, GitHub's *Update branch* (a merge commit, treated as a push and never covered by a delegation), and re-running a run's failed jobs under a token narrowed to `actions: write` ([FIXED-1208](../plans/FIXED_ITEMS.md#fixed-1208--review-comments-could-not-be-read-or-answered-tool-27) to [FIXED-1210](../plans/FIXED_ITEMS.md#fixed-1210--a-failed-ci-run-could-not-be-re-run-from-a-turn-tool-21)). The third round adds `resolve_review_thread`, asked first: it calls GitHub's GraphQL endpoint on the same fixed host, with two fixed query documents (find the thread holding a REST comment id, then resolve that thread); the model supplies only the repository, the number and the comment id, never a query, a thread id or a URL, and both calls run under the one approval ([FIXED-1231](../plans/FIXED_ITEMS.md#fixed-1231--a-review-thread-could-be-answered-but-not-resolved-tool-27)). |
| Searches stay in the repository | `search_code` and `search_issues` add `repo:owner/name` to the owner's query on the server, so a search never reaches past the named repository; queries are at most 256 characters. |
| Bounded read | Response capped at 200 KB fetched; the returned body is truncated to 20 000 chars; a single GET, no following redirects to other hosts (the allowlist is re-checked only at the top-level URL — see residual risks). |
| Untrusted output | The content is wrapped as an untrusted-data block before it reaches the model; assistant/tool content is never instruction authority (existing runtime invariant). |
| No data leakage in audit | Broker events and stored tool actions drop the fetched `content` field; executor artifacts are metadata-only. The token never appears in arguments, URLs, events, or artifacts. Governance-relevant non-secret identifiers (`repo`, `resource`, `number`) are kept for the audit trail. |
| AI principals | Capability gate + `route_action` block non-human principals from enabling the gate or raising the decision mode; enabling is human `runtime_gate_manager` only. |

## Activation requirements

Enabling `connector_github_runtime` requires a HUMAN `runtime_gate_manager`, the
agent runtime switched on, the registered executor, a `threat_model_acks`
row referencing this document, and a human confirmation token. A *working* read
additionally requires the owner credential (`RAIKER_GITHUB_TOKEN`), the host on
`RAIKER_CONNECTOR_EGRESS_ALLOWLIST`, and the decision mode raised to `allow` —
none of which enabling the gate grants. The read-only **Connections** web
surface (`GET /api/connections`) reports each of these preconditions honestly so
the owner can see exactly what is still fail-closed.

## Residual risks & non-goals

- A read sends the owner's token to GitHub and pulls repo content onto the
  machine; that content is subject to GitHub's data handling and the token's
  scope. The default-ask decision mode exists so this never happens without a
  standing owner decision; the egress allowlist bounds *where* the request can
  go. Scope the token to the minimum needed (read-only, specific repos).
- `urllib` may follow HTTP redirects; a redirect target is not re-checked
  against the allowlist by `get_url`. GitHub's REST API does not redirect
  cross-host for these endpoints, and the request URL is server-built against
  `api.github.com`, so this is low-risk today — but broadening the connector to
  attacker-influenced hosts must add per-hop allowlist enforcement first.
- A malicious/compromised repository could return adversarial issue/PR text. It
  is labelled untrusted data and cannot execute anything by itself; every action
  the model proposes afterwards still flows through the broker, policy, and
  approvals.
- Out of scope: modifications beyond a comment or a pull request,
  listing/searching, other GitHub resources, and other connectors
  (Gmail/Calendar/Slack — same pattern, separate slices). OAuth and GitHub App
  tokens are not used by this connector today (it uses an owner-provided
  environment token only); they are planned under the
  [GitHub connection specification](../architecture/GITHUB_CONNECTION_SPEC.md),
  where a sign-in or App installation grants no connector authority by itself.
