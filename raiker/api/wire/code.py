# SPDX-License-Identifier: Apache-2.0
"""Build's repositories: connecting, selecting and forgetting one, and the code map."""

from __future__ import annotations

from typing import Literal, NotRequired

from typing_extensions import TypedDict

from raiker.api.wire.projects import ProjectBrowseEntry
from raiker.graph.codemap_service import CodeMapSummary
from raiker.graph.language_service import Diagnostic


class CodeMapRebuilt(CodeMapSummary):
    ok: bool


class LocalRepoConnected(TypedDict):
    """A workspace folder referenced as a repository, and its map if one was built."""

    ok: bool
    repo_id: str
    kind: Literal["local"]
    local_subpath: str
    code_map: CodeMapSummary | None


class GithubRepoConnected(TypedDict):
    """A GitHub coordinate recorded. Nothing was fetched."""

    ok: bool
    repo_id: str
    kind: Literal["github"]
    label: str
    branch: str | None


class CodeRepoSelected(TypedDict):
    ok: bool
    selected_repo_id: str | None
    code_map: CodeMapSummary | None


class CodeRepoDisconnected(TypedDict):
    ok: bool
    repo_id: str


class CodeRepoBrowseView(TypedDict):
    """B13 — one directory of the repository Build is pointed at.

    The same entry shape as a project's tree, so one explorer serves both;
    ``index_state`` is always null here. ``reason_code`` says why there is
    nothing to show when ``root_missing``.
    """

    path: str
    parent: str | None
    entries: list[ProjectBrowseEntry]
    truncated: bool
    root_kind: Literal["local", "github"]
    root_label: str
    root_missing: bool
    reason_code: NotRequired[str]


class CodeRepoFileView(TypedDict):
    """One bounded text file, or the reason it cannot be shown."""

    path: str
    text: str
    truncated: bool
    size_bytes: int
    readable: bool
    reason_code: str


class CodeRepoChangeEntry(TypedDict):
    path: str
    #: The old name of a rename; "" otherwise.
    previous_path: str
    #: Git's own word for it: modified, added, deleted, renamed, untracked.
    state: str
    unstaged: bool


class CodeRepoChangesView(TypedDict):
    """The working tree's uncommitted state, from the helpers a commit is built from."""

    entries: list[CodeRepoChangeEntry]
    diff: str
    truncated: bool
    diff_truncated: bool
    root_missing: bool
    reason_code: str | None


class CodeRepoDiagnosticsView(TypedDict):
    """B10 — parse-level problems for one file; ``checked`` false means not looked at."""

    path: str
    checked: bool
    available: bool
    reason_code: str
    reason: str
    diagnostics: list[Diagnostic]


class TargetDelegation(TypedDict):
    """BR-01 — one active repository delegation a Build turn here would act under."""

    delegation_id: str
    operations: list[str]
    branch_pattern: str | None
    allow_pull_request: bool
    expires_at: str
    actions_left: int | None


class TargetAuthority(TypedDict):
    """What a Build turn on this target may do unprompted, beyond asking you."""

    repository: str | None
    delegations: list[TargetDelegation]
    git_credential: bool


class CodeRepoTargetView(TypedDict):
    """BR-D02 — the execution target a Build turn on this repository would use."""

    repo_id: str | None
    repo_kind: str
    label: str
    state: Literal["ready", "folder_missing", "remote_only", "no_repository"]
    host: Literal["this_computer", "remote"]
    folder: str
    folder_exists: bool
    git: bool
    branch: str
    head: str
    #: The repository's identity: its GitHub coordinate, credential-free remote, or folder.
    identity: str
    environment: str
    code_placement: str
    code_placement_reason: str
    fingerprint: str
    #: BR-01 — the delegations and Git credential a turn here would act under.
    authority: NotRequired[TargetAuthority]


class PatchReviewFinding(TypedDict):
    """BR-D04 — one deterministic finding on an exact patch."""

    finding_id: str
    rule: str
    severity: Literal["high", "medium", "low", "info"]
    category: str
    title: str
    evidence: str
    next_step: str
    confidence: Literal["high", "medium", "low"]
    path: str | None
    line: int | None
    #: Against the repository's previous review: ``new`` or ``still_present``;
    #: null for the first review (and for reviews stored before this existed).
    since: NotRequired[Literal["new", "still_present"] | None]
    #: ``model`` for a selected model's reading (a claim nothing checked).
    source: NotRequired[Literal["model"]]
    #: BR-11 — how many reviews in a row have raised this finding, this one included.
    reviews_present: NotRequired[int]


class ModelPatchReview(TypedDict):
    """BR-D04 — one connected model's reading of an exact patch, stored by patch and model."""

    fingerprint: str
    provider: str
    model: str
    findings: list[PatchReviewFinding]
    counts: dict[str, int]
    truncated: bool
    reviewed_at: str


class ResolvedFinding(TypedDict):
    """A finding the previous review raised that this patch no longer has."""

    rule: str
    title: str
    severity: str
    path: str | None
    line: int | None


class PatchReview(TypedDict):
    fingerprint: str
    files: int
    added_lines: int
    truncated: bool
    findings: list[PatchReviewFinding]
    counts: dict[str, int]
    reviewed_at: str
    previous_fingerprint: NotRequired[str | None]
    resolved: NotRequired[list[ResolvedFinding]]


class PatchReviewSummary(TypedDict):
    """The repository's latest review of an earlier patch than the current one."""

    fingerprint: str
    reviewed_at: str
    findings: int
    counts: dict[str, int]


class ReviewAttestationView(TypedDict):
    """BR-D05 — whether a stored review is exactly what this installation signed.

    ``verified``: signed here and unchanged; ``invalid``: the review or its
    signature was changed after it was taken; ``unknown_key``: signed by a key
    this installation does not hold; ``unsigned``: taken before reviews were
    signed. Evidence only — no state grants or blocks anything.
    """

    state: Literal["verified", "invalid", "unknown_key", "unsigned"]
    key_id: str | None
    signed_at: str | None


class CodeRepoReviewView(TypedDict):
    """The review of the working tree's current patch, if one has been taken.

    ``fingerprint`` is the current patch's; ``review`` is null until the owner
    asks for one. ``reused`` says the stored review of this same patch was
    returned instead of a second, duplicate set of findings.
    """

    fingerprint: str
    has_changes: bool
    review: PatchReview | None
    reused: bool
    reason_code: str | None
    #: When the current patch has no review yet: the latest review this
    #: repository has, of an earlier patch — so the owner can see it is stale.
    previous: PatchReviewSummary | None
    #: The latest selected-model reading of this exact patch, if one was asked for.
    model_review: NotRequired[ModelPatchReview | None]
    #: BR-D05 — the signature state of ``review`` and of ``model_review``.
    attestation: NotRequired[ReviewAttestationView | None]
    model_attestation: NotRequired[ReviewAttestationView | None]


class CodeRepoModelReviewView(TypedDict):
    """BR-D04 — the answer to asking a model to read the current patch."""

    fingerprint: str
    has_changes: bool
    model_review: ModelPatchReview | None
    reused: bool
    reason_code: str | None
    model_attestation: NotRequired[ReviewAttestationView | None]


class CommitProvenance(TypedDict):
    """BR-D05 — one recent commit, and what its Raiker trailers prove here."""

    commit: str
    subject: str
    committed_at: str
    provenance: Literal["recorded", "unrecorded", "none"]
    session_id: str | None
    turn_id: str | None
    #: BR-D05 — Git's verdict on the commit's own signature (``%G?``).
    signature: Literal["good", "untrusted", "bad", "expired", "revoked", "unverifiable", "none"]


class CodeRepoProvenanceView(TypedDict):
    commits: list[CommitProvenance]
    reason_code: str | None


class PullRequestReceipt(TypedDict):
    """BR-12 — what GitHub confirmed about a pull request Raiker opened."""

    receipt_id: str
    repository: str
    number: int
    url: str
    head_branch: str
    base_branch: str
    head_sha: str
    state: str
    #: ``confirmed``: read back from GitHub and it matches the request;
    #: ``mismatch``: GitHub answered with a different head, base or number;
    #: ``unconfirmed``: the read-back failed, so only the create response is known.
    confirmation: Literal["confirmed", "mismatch", "unconfirmed"]
    session_id: str | None
    turn_id: str | None
    created_at: str
    confirmed_at: str | None


class CodeRepoPullRequestsView(TypedDict):
    """The pull requests Raiker opened on this repository's GitHub identity, newest first."""

    repository: str | None
    receipts: list[PullRequestReceipt]
    reason_code: str | None


class CodeRepoWorktreeCreated(TypedDict):
    """BR-03 — a task worktree on a new owned branch, connected as its own repository."""

    ok: bool
    repo_id: str
    label: str
    local_subpath: str
    branch: str
    base: str


class CodeRepoWorktreeRemoved(TypedDict):
    ok: bool
    repo_id: str
    branch: str
