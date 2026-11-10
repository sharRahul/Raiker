# RAIKER.md global and nested instructions: design for owner review

**Status:** expanded proposal; implementation not yet approved.
**Date:** 2026-11-10. The owner requested global and nested scope, replacing
our earlier root-only proposal. The review-on-change policy below is proposed.

## Recommended behavior and alternatives

Raiker discovers applicable `RAIKER.md` files, lets the owner review their exact
revisions once, and automatically reuses those reviewed revisions on Build
turns. Changed or newly discovered rules require review before affected work.
Existing encrypted owner/project instructions remain supported.

| Approach | Benefit | Tradeoff |
|---|---|---|
| **Reviewed global/root/nested hierarchy (recommended)** | Portable files and automatic reuse; repository/agent edits cannot activate standing rules by themselves | Each new or changed revision needs owner review |
| Enabled hierarchy with automatic live reload | Fewer interruptions and familiar edit/reload workflow | Pulls, dependencies and agent edits can alter future instructions without review |
| Root-only files | Smaller feature | Does not meet the requested global/nested scope; superseded |

This changes [the earlier repository-file decision](../architecture/REFERENCE_PLATFORM_COMPATIBILITY.md#37-project-instructions-are-owner-records-not-repository-files),
while preserving the rule that instruction text never grants capabilities.

## Locations and account isolation

| Level | Location | Applies to |
|---|---|---|
| Global | `<Raiker data folder>/.raiker/user-instructions/<resolved user id>/RAIKER.md` | That Raiker account's Build projects in this data folder |
| Project | `<resolved project root>/RAIKER.md` | All paths in that project |
| Nested | `<resolved project root>/<subdirectory>/RAIKER.md` | That directory and descendants |

Global means account-wide, not shared across users or all data folders on a PC.
Settings shows the signed-in owner's actual path and can create/open a starter
file. Ordinary repository tools cannot edit this protected application folder.
Only the exact filename `RAIKER.md` is recognized, including on Windows.
File-based discovery is enabled by the owner per project; global rules apply
to those enabled projects. Existing projects stay unchanged until the owner
chooses **Use file instructions**, which can also enable nested discovery when
there is no root file. Discovering a file does not approve its contents.

Project ownership, session binding, canonical root and live attached-folder
grants are checked through `resolve_project_root`. Unknown owner mappings fail
closed; no unfiltered project lookup or selected-repository fallback. No files
are implicitly read from parent directories outside the granted project.

No automatic aliases for AGENTS.md/CLAUDE.md/GEMINI.md, imports, @file expansion,
network fetches, executable directives, environment expansion or frontmatter.
Remote-only/rootless projects cannot acquire local repository rules by guessing.

## Hierarchy, discovery and precedence

1. At the beginning of a Build turn, discover the global and project-root files.
2. For an explicit working directory or a file action, inspect only the chain
   from project root to the directory/file's parent; never recursively scan siblings.
3. Before the first action in a new subtree, reconcile that chain. Unreviewed
   rules pause the affected action with a review route. Newly applicable
   approved rules must reach the model before it replans work in that scope;
   do not execute an action planned without them or create an endless retry loop.
4. File guidance applies global, project root, then outer-to-inner directories.
   Nearest rules win conflicts only within their scope. For multi-file work,
   keep each target's applicable chain labelled; do not apply one sibling's rules
   to another or merge conflicting scoped rules as universal instructions.
5. Read the authorized source project, not a disposable task copy. Agent-proposed
   RAIKER.md changes activate only after Apply changes the source and the owner
   reviews the new revision. Applying code is not approval of standing rules.

Authority, highest first: system/runtime/governance; current owner's request;
existing encrypted owner/project instructions; reviewed file guidance; ordinary
external/workspace data. Markdown cannot enable tools, access credentials,
grant network/filesystem rights, weaken the sandbox, approve actions, activate
skills or make a test count as passed. Mentioned commands use normal governed tools.

Use explicitly labelled subordinate instruction sources, separate from direct
user requests and untrusted workspace data. Existing owner instructions are
currently mixed into a blanket data-only wrapper; separate owner guidance,
reviewed file rules and project metadata instead of repeating that ambiguity.
Never present repository text as system policy.

This hierarchy initially applies to Build and explicitly project-bound Build
goals. Ordinary account-wide Chat, Design and ambiguous channels do not guess a
project. Their existing owner settings continue to apply. Global non-Build
assistant preferences remain in owner settings; this is not full product parity.

## Safe reads, limits and context

- Pin and validate the complete path and opened regular-file handle. Reject
  links/junctions/reparse points, devices, pipes, directories and multiple hard
  links. Resolve-then-open alone is insufficient. Unsupported containment
  contributes no text and names the reason.
- Require UTF-8 (optional BOM), no NULs, at most 8,192 raw bytes and 4,000 decoded
  characters per file. Read one byte beyond the limit to detect oversize; reject
  the whole file rather than loading a prefix. Empty files add no instructions.
- Limit an enabled hierarchy to 32 directory levels, 16 files and 32 KiB raw /
  16,000 decoded characters. An exceeded limit gives an actionable refusal,
  not silently omitted deeper rules. Existing projects without this feature
  do not acquire a new depth restriction.
- Hash exactly the safely read bytes. Apply the existing secret redactor to
  preview and provider projection; review includes its projection version.
- Budget sources once. Include whole eligible projections or state omission.
  If applicable instructions do not fit, pause the affected file action with
  remediation, rather than claim the rules loaded or silently truncate them.

## Owner review, reload and lifecycle

Settings manages the global file; Project settings manages project/nested rules.
Show each scope, redacted preview, counts, digest and state. Review/use and
Disable are authenticated owner actions, never model tools.

Review binds owner, source kind, project where applicable, root/grant identity,
relative path, digest and projection version. Other users, copied projects,
moved/reattached roots and ancestor projects do not inherit approvals. Batch
review rereads and compares every displayed file/root before activating it;
changed bytes conflict instead of approving unseen content.

At each new turn, safely reread and compare. Changed, missing, disabled,
revoked, unsafe or invalid files do not fall back to stale copied rules. Disable
clears review; restoring bytes after Disable does not automatically reactivate.
Loaded instructions are fixed snapshots for that turn, not rewritten mid-call.
Live tool/root revocation still applies separately to each action. New subtrees
follow the reconciliation rule above.

Project deletion removes project/nested review records but not global rules.
Backup/restore respects existing disabled/revoked-state contracts. No restoration
may give another account copied instruction authority.

## Visibility and privacy

Build's context view lists actual loaded scopes/revisions and omitted/review-
required files. Distinguish absent, disabled, approved, changed, unsafe,
unreadable, invalid, oversized and root-unavailable states. Provider-visible
provenance uses Global RAIKER.md or project-relative paths, not absolute host
paths. The authenticated local owner may see their global path to edit it.

Events/hooks contain safe scope, revision IDs, counts and reason codes, never
rule text, credentials or absolute paths. Budget-excluded sources are not
reported as loaded. Discovery/review/disable require no provider call.

## Implementation and acceptance plan

1. Safe hierarchy discovery on the canonical owner/project roots and shared
   pinned-read primitives, deterministic path-scoped ordering and limits.
2. Owner-scoped review persistence, authenticated preview/review/disable, no
   model-facing activation tool and no authority expansion.
3. Explicit instruction/data prompt boundaries across provider adapters,
   context budgeting, compaction and metadata-only disclosure.
4. Settings/Project review controls and Build visibility with accessible
   changed/unsafe/oversized states and useful recovery actions.
5. Regressions for global account separation, nested/sibling/multi-target
   scope, grant revocation, edits/moves/delete/disable, review races, task-copy
   proposals, unsafe paths/hardlinks, limits, budgets and prompt precedence.
6. Real UI/model test of an approved hierarchy, changed revision, harmless
   output convention and absent unreviewed/revoked text. Update guides,
   compatibility decisions and beta ledgers with exact results.

## References and review decision

[Claude Code memory](https://code.claude.com/docs/en/memory) distinguishes
instruction scopes and guidance from enforced configuration.
[Gemini CLI GEMINI.md](https://geminicli.com/docs/cli/gemini-md/) documents its
named Markdown context convention. These are examples, not claims that Raiker
matches every loading algorithm or permission behavior of another product.

The owner requested the expanded scope. The detailed reviewed-revision policy,
account-scoped global location and nested activation contract above are ready
for approval; no implementation is claimed by this proposal.
