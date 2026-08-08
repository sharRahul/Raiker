# Threat Model — Git Writes (`git_write_execution`, B11)

> Status marker: implemented and integrated. `git_branch` and `git_commit` are
> live; a push and a pull-request *send* are separate capabilities — the
> outward half is `github_write` under the existing
> `connector_github_runtime` gate (see
> [connectors-github.md](connectors-github.md)), and there is no push path yet.

Per-capability threat model for letting the agent change the repository it is
working in. Before B11, Raiker's git surface was `status`, `diff` and `log`: the
agent could read a repository and describe a change it could neither commit nor
propose. The gap that closed is narrow on purpose — a branch and a commit — and
everything below is what keeps it narrow.

## What this capability is

`git_branch` and `git_commit` are model-proposable tools. Both are high risk and
approval-required, both map to the single capability `git_write_execution`
(Permissions → Workspace → **Git writes**), and both are carried out by
`raiker/runtime/executors/tier1_git.py::GitWriteExecutor` through the
Workstream A approval relay — so the target is re-governed at execution time
under its own gate, decision mode, policy review, and a posture check on the
approving session.

Each tool is a **proposal first and a mutation second**, and the two halves are
the same computation:

1. `proposed_branch_snapshot` / `proposed_commit_snapshot`
   (`raiker/tools/git.py`) compute exactly what the mutation would do and touch
   nothing — no staging, no index change, no ref written. The transcript, the
   Approvals inbox (`preview_kind: "git_change"`) and the executor all read this
   same function, so what the owner approved is what runs.
2. `create_branch` / `create_commit` re-derive that snapshot before mutating. A
   repository that moved between the approval and the execution fails closed
   with a named reason rather than recording something the owner never saw.

For a commit the owner sees the exact file list with each file's state and the
whole diff, including files git does not track yet (built with `difflib` against
empty, because `git diff` has nothing to say about them). For a branch there is
no diff to show, so the preview states the two refs it moves between rather than
pretending otherwise.

## Boundaries enforced (fail-closed)

| Control | Mechanism |
|---|---|
| Governed entry only | Both tools are in `approval_required_actions`; `git_write_execution` is in `EXECUTABLE_ON_APPROVAL` and is reached only through `ApprovalExecutionRelay` → `route_action`. An AI may propose; only a human decision executes. |
| One owner switch | `CAPABILITY_GATE_MAP` maps both tools to `git_write_execution`, so "may the agent change my repository" is one control the owner can see and turn off. With it off, resolution returns to metadata-only and the detail view says so **before** the decision. |
| The workspace's own state is never committed | `_is_protected` drops anything under `PROTECTED_WORKSPACE_DIRS` (`.raiker/`, `.git/`) from every proposal, and a path naming one is refused as `protected_workspace_path`. `.raiker/` holds the vault key, the encrypted store and the audit log; a commit that swept the working tree would write the owner's key material into git history. |
| The commit is the reviewed change set | Execution stages the snapshot's own path list — never `git add --all` — and commits path-limited (`git commit -- <paths>`), so neither an unrelated file nor whatever the owner had staged for themselves can ride along. |
| Repository hooks never run | Every invocation carries `-c core.hooksPath=raiker-no-such-hooks`. `.git/hooks` is workspace content the agent may itself have written; running it on commit would make a governed write an un-governed code-execution path. |
| No interactive block | `-c commit.gpgsign=false` / `tag.gpgsign=false`: a configured signing key would otherwise block the commit on a passphrase prompt this process can never answer. |
| The owner's identity is kept | A committer identity is supplied *only* when the repository has none (`Raiker agent <agent@raiker.local>`). A configured `user.name`/`user.email` is never overridden. |
| Workspace-scoped | The repository is resolved with `resolve_workspace_path`, and every model-supplied path is re-resolved against the workspace root; a path that escapes it is refused as `path_outside_repository`. |
| Refuses what it cannot honour | Named, machine-readable refusals for: not a git repository, a branch name `git check-ref-format` rejects, a branch that exists, an unknown base, an in-progress merge/rebase/cherry-pick/revert/bisect, an empty message, and nothing to commit. |
| Uncommitted work is not moved silently | A branch created *from a named base* moves the working tree, so it is refused while there are uncommitted changes. Without a base there is nothing to move to, and the proposal states how many files it carries across. |
| Bounded | Subprocesses are wall-clock capped; the preview diff is capped at 200 KB and says when it truncated. |

## Residual risks / non-goals

- **A commit is not checkpointed.** The checkpoint store holds pre-images of
  *file* mutations; git history is not one of them. The approval notice says so
  in as many words — "It is git history rather than a checkpointed file write,
  so undo it in git" — rather than promising a rewind the runtime cannot
  perform.
- **No push.** The agent can commit on a branch it cannot publish. `github_write`
  opens a pull request through the connector, so it is only useful for a branch
  that already exists on the remote. A governed push is a separate capability
  with its own credential and egress question; it is tracked as **BUG-67**.
- **Repository-root scoped.** Like the existing `git_status` / `git_diff` /
  `git_log` reads, the write tools operate on the workspace root's repository.
  A repository connected as a sub-folder of the workspace is not reachable by
  either the read or the write tools; tracked as **BUG-66**.
- **A commit message is model-authored text.** It is recorded verbatim in git
  history. It is bounded and never interpreted as an instruction, but it is not
  redacted — the owner reads it in the approval before it is written.
- **Out of scope.** Merge, rebase, reset, cherry-pick, tag, remote management,
  and history rewriting are not implemented and fail closed as
  `unknown_git_operation`.
