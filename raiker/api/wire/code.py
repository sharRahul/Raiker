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


class PatchReview(TypedDict):
    fingerprint: str
    files: int
    added_lines: int
    truncated: bool
    findings: list[PatchReviewFinding]
    counts: dict[str, int]
    reviewed_at: str


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


class CommitProvenance(TypedDict):
    """BR-D05 — one recent commit, and what its Raiker trailers prove here."""

    commit: str
    subject: str
    committed_at: str
    provenance: Literal["recorded", "unrecorded", "none"]
    session_id: str | None
    turn_id: str | None


class CodeRepoProvenanceView(TypedDict):
    commits: list[CommitProvenance]
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
