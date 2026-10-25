# Threat Model — Git Push (`git_push_execution`, BUG-67)

> Status marker: implemented and integrated. `git_push` is live. It is
> deliberately **not** part of `git_write_execution` (see
> [git-write.md](git-write.md)): a branch and a commit stay on this machine,
> a push does not.

Per-capability threat model for letting the agent publish what it committed.
Before this, B11 let the agent create a branch and record a commit on it and
stopped there: the branch existed only locally, so `github_write` could not open
a pull request for a head GitHub had never seen. The gap that closed is narrow on
purpose — one branch, to one remote, fast-forward only — and everything below is
what keeps it narrow.

## What this capability is

`git_push` is a model-proposable tool. It is high risk and approval-required, it
maps to the capability `git_push_execution` (Permissions → Network → **Git
push**), and it is carried out by
`raiker/runtime/executors/tier1_git.py::GitPushExecutor` through the Workstream A
approval relay — so the capability gate, the decision mode, policy review, and a
posture check on the approving session all apply again at execution time.

Like the local git writes, it is a **proposal first and a mutation second**, and
the two halves are the same computation:

1. `proposed_push_snapshot` (`raiker/tools/git.py`) computes what the push would
   send and **touches neither the repository nor the network**. Asking the remote
   for its refs would be egress performed before the owner approved any, so the
   preview states what this machine last knew.
2. `push_branch` re-derives that snapshot before running anything. A repository,
   an allowlist or a credential that moved between the approval and the execution
   fails closed with a named reason.

The owner sees the repository, the remote and its host, the branch, whether the
remote has ever seen that branch, and the commits it does not have — by subject,
not by count alone.

## Why it is its own capability

An owner who lets the agent change their repository has not thereby let it
publish to the world. A commit is local and reversible in git; a push carries
repository content off the machine under the owner's credential and nothing
brings it back. Folding it into `git_write_execution` would have made those one
decision. It is Tier 2 rather than Tier 1 for the reason every other Tier-2
capability is: it reaches the network.

## Boundaries enforced (fail-closed)

| Control | Mechanism |
|---|---|
| Governed entry only | `git_push` is in `approval_required_actions`; `git_push_execution` is in `EXECUTABLE_ON_APPROVAL` and is reached only through `ApprovalExecutionRelay` → `route_action`. An AI may propose; only a human decision publishes. |
| Its own owner switch | `CAPABILITY_GATE_MAP` maps `git_push` to `git_push_execution`, separate from `git_write_execution`. With it off, resolution returns to metadata-only and the detail view says so **before** the decision. |
| Owner egress allowlist | The remote's host must be on `RAIKER_CONNECTOR_EGRESS_ALLOWLIST` (empty ⇒ fail closed), checked at proposal *and* at execution. Refused as `push_egress_denied`, naming the host. |
| Owner credential | The credential the owner selected in **Settings → GitHub** — a vault token (`github_token`, RAIKER-2022), the legacy `RAIKER_GITHUB_TOKEN`, the gh CLI's sign-in, a saved Git credential, an SSH key, or a GitHub App sign-in or installation token minted for this one repository — is checked against its GitHub account and lent by `GitCredentialBroker` to one command under an owner grant: *once* (300 s) or *for the conversation that proposed it* (3600 s), narrowed to operation, repository and branch, consumed or expired on its own ([FIXED-882](../plans/FIXED_ITEMS.md#fixed-882--a-push-proposal-ignored-the-token-stored-in-settings-was-bug-334), [FIXED-883](../plans/FIXED_ITEMS.md#fixed-883--a-this-session-git-grant-was-not-tied-to-any-session-was-bug-335)). An agent's push without a per-step approval runs only under a repository delegation, re-validated before each step. No credential is refused as `push_credential_unset`. The gate being on is not a substitute for any of these. |
| Only the host the credential belongs to | The credential is a GitHub credential (`CREDENTIAL_HOSTS`: `github.com`, `www.github.com`). A remote on any other host is refused as `unsupported_remote_host` rather than having the owner's token sent to it, and the helper itself answers no other host. |
| HTTPS or governed SSH, and only a remote git will really contact | The URL is read with `git remote get-url --push`, so `pushurl` and `url.<base>.insteadOf` rewrites are resolved: what is checked is the address git will contact, not the one the config file spells. SSH is allowed only to `github.com:22` or `ssh.github.com:443` as `git`, with the selected key, `IdentitiesOnly`, no agent and GitHub's pinned host keys; plaintext HTTP is refused, and a remote URL carrying its own credential is refused as `remote_url_has_credentials` — it would be used *instead of* the governed one and would ride past every check. |
| Never forces, never deletes, sends what was approved | The refspec is written out in full (`<approved-sha>:refs/heads/<branch>`), the commit recorded with the approval, so nothing committed afterwards rides along and a moved target refuses `push_target_changed` ([FIXED-884](../plans/FIXED_ITEMS.md#fixed-884--a-push-sent-the-branch-as-it-was-when-it-ran-not-the-commits-that-were-approved-was-bug-336)); and a branch name can neither be read as an option nor move a ref it does not name. `--force`, `--force-with-lease`, `--delete` and `--mirror` are not reachable from the tool. A non-fast-forward is reported as `push_rejected_non_fast_forward`, not resolved by overwriting. |
| The credential never reaches the command line | The token is passed in the child process's environment and read by an inline credential helper, so it is absent from the process table and from any captured command string. Git's output is scrubbed of the token before it is returned or stored. |
| No inherited credential | An **empty** `credential.helper` is configured first, clearing whatever the host has set, so a system keychain cannot quietly supply a different account's credential than the one the owner governed. |
| No interactive block | `GIT_TERMINAL_PROMPT=0` and empty `GIT_ASKPASS`/`SSH_ASKPASS`: a push that cannot authenticate fails with a reason instead of holding the process until its wall-clock cap. |
| Repository hooks never run | `-c core.hooksPath=raiker-no-such-hooks`. `.git/hooks/pre-push` is workspace content the agent may itself have written; running it would make a governed push an un-governed code-execution path. |
| The repository is the one the owner picked | Resolved through `resolve_repository_root` against the selected code repository, falling back to the workspace root, using the same containment check every other path read uses (FIXED-110). The approval names it. |
| Refuses what it cannot honour | Named, machine-readable refusals for: not a git repository, a detached HEAD, an unknown branch, no remote, an unknown remote, every URL case above, a missing allowlist entry or credential, nothing to push, a rejected push, a refused credential, and a timeout. |
| Not a decision when it is a refusal | A proposal whose own precondition check failed returns that reason to the model instead of raising an approval (FIXED-112). Refusing earlier is strictly more fail-closed: a call that never reaches an approval never reaches an executor. |
| Bounded | The push is wall-clock capped at 120 s; the preview lists at most 50 commits and says when it truncated. |
| No committed credential leaves | The preview reads the added lines of every outgoing commit (up to 200) and matches them against the published key shapes CI fails on (`raiker/security/secret_shapes.py`). A match refuses `outgoing_commits_contain_credentials` before the owner is asked, naming path, line, rule and a fingerprint, never the value; only a dated, unexpired entry in the repository's own `.github/secret-scan-exceptions.json` excuses one (TOOL-30, [FIXED-1196](../plans/FIXED_ITEMS.md#fixed-1196--a-push-could-publish-a-committed-credential-tool-30)). |

## Residual risks / non-goals

- **A push cannot be undone by Raiker.** The approval says so in as many words —
  "it leaves this machine and git cannot take it back — undo it on the remote" —
  rather than implying a rewind. The checkpoint store holds pre-images of file
  mutations; a published ref is not one of them.
- **What landed is read back, not assumed.** After the push the remote's ref is
  read back under the same loan; the receipt says *confirmed* only when it is the
  approved commit.
- **The commit range is what this machine last knew.** The preview is computed
  without contacting the remote, deliberately. If someone else pushed to that
  branch since the last fetch, the count shown can be stale — the push then fails
  closed as `push_rejected_non_fast_forward` rather than overwriting their work.
- **One forge.** Only GitHub.com remotes are pushable, under the methods the
  [GitHub connection specification](../architecture/GITHUB_CONNECTION_SPEC.md)
  describes; other forges are separate adapters.
- **One branch, no tags, no deletes.** Pushing tags, deleting a remote branch,
  and pushing to a ref other than the branch's own name are not implemented and
  are not reachable from the tool.
- **The credential's scope is the owner's to choose.** Raiker never narrows a
  personal token: a token with write access to every repository the owner
  can reach will have that access on any push the owner approves. Scoping the
  token to the repositories in play is the owner's control, not Raiker's.
