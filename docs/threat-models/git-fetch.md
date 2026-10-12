# Threat Model — Git Fetch and Clone (`git_fetch_execution`, ADD-27 GH-23)

> Status marker: implemented and integrated, 2026-10-12. Default off; Tier 2;
> approval-required; part of the [GitHub connection](../architecture/GITHUB_CONNECTION_SPEC.md)
> work (DEC-21b as amended).

Per-capability threat model for letting the agent bring a repository's history
onto this machine: `git_fetch` updates the remote-tracking branches of the
selected repository, and `git_clone` creates a new checkout of a GitHub
repository named `owner/name`. Neither merges, checks out over existing work or
pushes anything.

## What this capability is

Two model-proposable tools, both high risk and approval-required, both mapped
to `git_fetch_execution` (Permissions → Git → **Git fetch**) and carried out by
`raiker/runtime/executors/tier1_git.py::GitFetchExecutor` through the approval
relay. The proposal (`proposed_fetch_snapshot`, `proposed_clone_snapshot` in
`raiker/tools/git.py`) is computed without touching the network and names the
remote, the address git will contact, the transport and — for a clone — the
folder it would create.

## Why it is its own capability

A fetch is egress: it tells GitHub this machine is asking, and for a private
repository it spends the owner's credential. It is also *ingress* of content
written by someone else, which a repository can turn into code execution if
git is allowed to follow submodules, run hooks or call an fsmonitor. Neither
property belongs to `git_write_execution` (local) or `git_push_execution`
(outbound).

## Boundaries enforced (fail-closed)

| Control | Mechanism |
|---|---|
| Governed entry only | `git_fetch`, `git_clone` and `git_fetch_execution` are approval-required and reach the executor only through `route_action`; `git_fetch_execution` is in `EXECUTABLE_ON_APPROVAL` |
| No model-supplied URL | A clone takes `owner/name`, validated, and the address is built here (`https://github.com/owner/name.git`, or `git@github.com:owner/name.git` with a selected SSH key). A fetch uses a remote the repository already has |
| Host rules shared with the push | The resolved address must be GitHub over HTTPS or SSH as `git` on the right port, without a credential in it, and the host must be on `RAIKER_CONNECTOR_EGRESS_ALLOWLIST` (exact match), checked at proposal and at execution |
| Credential only under a fetch grant | The owner's credential is lent only when a grant covers *fetch* for that repository; otherwise the fetch is anonymous and a private repository is refused `fetch_authentication_required`. A push grant does not cover a fetch |
| Nothing fetched runs | `core.hooksPath` to a missing path, `core.fsmonitor=false`, `protocol.file.allow=never`, `protocol.ext.allow=never`, `--no-recurse-submodules`, `submodule.recurse=false`, `transfer.fsckObjects=true` |
| No inherited credential | An empty `credential.helper` first, then Raiker's host-scoped helper; the child runs in the constructed sandbox environment, never the host's |
| A clone creates, never overwrites | The destination must be inside the workspace and must not exist |
| Bounded | 180 s wall clock; output scrubbed of the lent token |

## Residual risks / non-goals

- **Fetched content is untrusted.** A later read of the files puts them in
  front of the model as data; their instructions are not authority (§11 of the
  specification).
- **Large repositories** can fill the disk within the time bound; the general
  disk checks apply, not a per-clone quota.
- **Submodules** are never cloned. A repository that needs them has to be set
  up by the owner.
