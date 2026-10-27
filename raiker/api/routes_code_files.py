"""Browsing and reading the repository Build is pointed at (B13).

Build could run a coding turn against a connected repository and give the owner
no way to *look* at it. Reading the result of a change meant leaving the app, so
the one thing a coding session does constantly — open a file and read it — was
the one thing the workspace could not do.

These are the two reads that fix it, and they are deliberately only reads:

* ``GET /api/code/repos/{repo_id}/browse`` — one directory at a time, the same
  shape ``/api/projects/{id}/browse`` answers, so the explorer component does not
  care which kind of root it is over.
* ``GET /api/code/repos/{repo_id}/file`` — one bounded text file.
* ``GET /api/code/repos/{repo_id}/target`` — the execution target a Build turn
  here would use, and its fingerprint (BR-D02).
* ``GET`` / ``POST /api/code/repos/{repo_id}/review`` — the exact-patch review
  of the current working-tree change, stored by the patch's fingerprint
  (BR-D04). The POST computes and stores a review; it changes no file.
* ``GET /api/code/repos/{repo_id}/changes`` — the working tree's own uncommitted
  changes (the Build artifact pane), read through the *same* helpers the commit proposal is
  built from, so what Build shows as "Changes" and what a commit would record
  cannot describe different change sets.

**Nothing here writes, and nothing here is a new boundary.** Every path is
resolved through the very :class:`~raiker.tools.path_authority.PathAuthority` a
turn writes through, and then re-checked against the repository's own root, so a
repository reference cannot become a workspace-wide file browser. Content comes
back through :func:`raiker.tools.filesystem.read_file`, the same bounded read the
agent's own ``read_file`` tool performs — a binary file, a missing file and an
oversize file each get the answer they already get there, rather than a second
opinion written for the browser.

A GitHub repository is a coordinate, not a checkout: there is nothing on this
machine to walk, and saying so is the honest answer rather than an empty tree.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status

from raiker.api.dependencies import authenticate as _auth
from raiker.api.dependencies import refusal
from raiker.api.dependencies import workspace_path as _ws
from raiker.api.schemas import ModelPatchReviewRequest, serialize_dto
from raiker.api.sessions import ApiSession
from raiker.api.wire.code import (
    CodeRepoBrowseView,
    CodeRepoChangesView,
    CodeRepoDiagnosticsView,
    CodeRepoFileView,
    CodeRepoModelReviewView,
    CodeRepoProvenanceView,
    CodeRepoPullRequestsView,
    CodeRepoReviewView,
    CodeRepoTargetView,
    ModelPatchReview,
    PatchReview,
    PatchReviewSummary,
    PullRequestReceipt,
)
from raiker.api.wire.projects import ProjectBrowseEntry
from raiker.knowledge.extractors import resolve_extractable_media_type
from raiker.knowledge.reconcile import IGNORED_DIRECTORY_NAMES
from raiker.runtime.authority.models import Principal
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.filesystem import FilesystemSafetyError, read_file
from raiker.tools.path_authority import PathAuthority

router = APIRouter()

#: Largest number of children one browse answers with, matching the project
#: explorer's cap so the two roots behave identically at scale.
MAX_BROWSE_ENTRIES = 500

#: How many changed files one `changes` read answers with, and how much diff it
#: carries. A working tree with a regenerated lockfile in it can produce tens of
#: thousands of diff lines, and a pane nobody can scroll to the end of is a pane
#: that hides the change it exists to show. Past either cap the answer says it
#: stopped rather than growing.
MAX_CHANGED_FILES = 200
MAX_CHANGES_DIFF_CHARS = 200_000

#: Largest file the viewer will render. Above this the answer states the size
#: rather than streaming a megabyte into a read-only pane nobody will scroll.
MAX_VIEW_BYTES = 400_000


def _not_found(reason_code: str) -> HTTPException:
    """404 for everything the caller may not see, so an id cannot be probed."""
    return refusal(status.HTTP_404_NOT_FOUND, reason_code)


def _bad_request(reason_code: str) -> HTTPException:
    return refusal(status.HTTP_400_BAD_REQUEST, reason_code)


def _names_its_own_root(supplied: str) -> bool:
    """True when a path sent to a *relative* parameter names a root of its own.

    Asked of what the caller sent, before separators are trimmed: stripping the
    leading slash off ``/etc/passwd`` leaves something that looks relative and
    would then resolve under the repository. ``PureWindowsPath`` carries the
    drive and UNC spellings on every platform, so the answer does not depend on
    where Raiker is running.
    """
    return supplied.startswith("/") or bool(PureWindowsPath(supplied).drive)


def _owned_repo(request: Request, repo_id: str, principal_id: str) -> dict[str, Any]:
    repo = SQLiteStore(_ws(request)).load_code_repo(principal_id, repo_id)
    if repo is None:
        raise _not_found("repo_not_found")
    return repo


def _repo_root(request: Request, repo: dict[str, Any]) -> Path | None:
    """Where this repository is on disk, or ``None`` when there is nothing to walk.

    A GitHub repository has no checkout, and a local folder the owner has since
    moved or deleted has no directory. Both answer ``None`` so the caller states
    it rather than rendering an empty tree as "no files".
    """
    subpath = repo.get("local_subpath")
    if not subpath:
        return None
    workspace = _ws(request).resolve()
    candidate = (workspace / str(subpath)).resolve()
    if candidate != workspace and workspace not in candidate.parents:
        return None
    return candidate if candidate.is_dir() else None


def _resolved_target(
    request: Request, root: Path, supplied: str
) -> Path:
    """*supplied*, resolved inside *root* — through the authority, then re-checked.

    Two independent checks on purpose. The authority is the boundary a turn
    writes through, so the browser cannot be looser than the agent; the second
    check is what keeps a *repository* reference from becoming a workspace-wide
    file browser, which the authority alone would happily allow.
    """
    relative = (supplied or "").strip().replace("\\", "/").strip("/")
    if _names_its_own_root(supplied or "") or ".." in PurePosixPath(relative).parts:
        raise _bad_request("outside_workspace")
    try:
        resolved = PathAuthority(_ws(request)).resolve_read(
            root / relative if relative else root
        )
    except FilesystemSafetyError as exc:
        raise _bad_request(str(exc)) from exc
    if resolved.path != root and root not in resolved.path.parents:
        raise _bad_request("outside_repository")
    return resolved.path


def _missing_view(repo: dict[str, Any]) -> CodeRepoBrowseView:
    kind = cast(Literal["local", "github"], str(repo.get("kind", "local")))
    answer: CodeRepoBrowseView = {
        "path": "",
        "parent": None,
        "entries": [],
        "truncated": False,
        "root_kind": kind,
        "root_label": str(repo.get("label", "")),
        "root_missing": True,
        # Two different absences, and the interface says which. A coordinate was
        # never on this machine; a folder that was is a problem to fix.
        "reason_code": "repo_not_checked_out" if kind == "github" else "repo_folder_missing",
    }
    return answer


@router.get("/api/code/repos/{repo_id}/browse")
async def browse_code_repo(
    repo_id: str,
    request: Request,
    path: str = "",
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    repo = _owned_repo(request, repo_id, auth_data[0].principal_id)
    root = _repo_root(request, repo)
    if root is None:
        return serialize_dto(_missing_view(repo))
    target = _resolved_target(request, root, path)
    if not target.is_dir():
        raise _not_found("directory_not_found")
    children = [
        child
        for child in sorted(
            target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())
        )
        if child.name not in IGNORED_DIRECTORY_NAMES
    ]
    relative = target.relative_to(root).as_posix() if target != root else ""
    answer: CodeRepoBrowseView = {
        "path": relative,
        "parent": (
            Path(relative).parent.as_posix().replace(".", "") if relative else None
        ),
        "entries": [_entry(child, root) for child in children[:MAX_BROWSE_ENTRIES]],
        "truncated": len(children) > MAX_BROWSE_ENTRIES,
        "root_kind": cast(Literal["local", "github"], str(repo.get("kind", "local"))),
        "root_label": str(repo.get("label", "")),
        "root_missing": False,
    }
    return serialize_dto(answer)


def _entry(child: Path, root: Path) -> ProjectBrowseEntry:
    is_directory = child.is_dir()
    answer: ProjectBrowseEntry = {
        "name": child.name,
        "relative_path": child.relative_to(root).as_posix(),
        "is_directory": is_directory,
        "size_bytes": 0 if is_directory else _size(child),
        "media_type": (
            ""
            if is_directory
            else (resolve_extractable_media_type(child.name, "") or "")
        ),
        # The repository explorer has no index behind it: these are files on
        # disk, not managed documents, and inventing an index state would
        # describe a projection that does not exist.
        "index_state": None,
    }
    return answer


def _size(child: Path) -> int:
    try:
        return int(child.stat().st_size)
    except OSError:
        return 0


@router.get("/api/code/repos/{repo_id}/file")
async def read_code_repo_file(
    repo_id: str,
    request: Request,
    path: str = "",
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """One bounded text file, or a stated reason it cannot be shown."""
    if not (path or "").strip():
        raise _bad_request("path_required")
    repo = _owned_repo(request, repo_id, auth_data[0].principal_id)
    root = _repo_root(request, repo)
    if root is None:
        raise _not_found(
            "repo_not_checked_out"
            if str(repo.get("kind")) == "github"
            else "repo_folder_missing"
        )
    target = _resolved_target(request, root, path)
    if not target.exists():
        raise _not_found("file_not_found")
    if not target.is_file():
        raise _bad_request("not_a_file")
    relative = target.relative_to(root).as_posix()
    size = _size(target)
    if size > MAX_VIEW_BYTES:
        # Refused with the number in it. "Too large" without the size is a dead
        # end; the size is what tells the owner whether to open it elsewhere.
        answer_0: CodeRepoFileView = {
            "path": relative,
            "text": "",
            "truncated": True,
            "size_bytes": size,
            "readable": False,
            "reason_code": "file_too_large",
        }
        return serialize_dto(answer_0)
    result = read_file(_ws(request), target, max_bytes=MAX_VIEW_BYTES)
    if result.get("status") != "success":
        error = result.get("error") or {}
        answer_1: CodeRepoFileView = {
            "path": relative,
            "text": "",
            "truncated": False,
            "size_bytes": size,
            "readable": False,
            "reason_code": str(error.get("type") or "unreadable"),
        }
        return serialize_dto(answer_1)
    answer_2: CodeRepoFileView = {
        "path": relative,
        "text": str(result.get("text", "")),
        "truncated": bool(result.get("truncated")),
        "size_bytes": size,
        "readable": True,
        "reason_code": "",
    }
    return serialize_dto(answer_2)


@router.get("/api/code/repos/{repo_id}/changes")
async def read_code_repo_changes(
    repo_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """What has changed in this repository's working tree, and not yet been committed.

    the Build artifact pane asks Build's third pane to be *the object of work*. For a coding
    turn that object is the change: which files moved, and what the diff says.
    Until now the only diff Build could show was a *proposed* one, attached to
    an approval — so once a change was applied, the workspace had nothing to
    show for it, and the owner went to a terminal to find out what the turn had
    actually done.

    Built from :func:`raiker.tools.git.working_tree_changes` and
    :func:`raiker.tools.git.working_tree_diff` rather than from a second git
    invocation of its own. That is the point: those two functions are what a
    commit proposal is assembled from, so this pane and the commit it leads to
    describe one change set. A pane that ran its own `git diff` could disagree
    with the commit, and the owner would have no way to tell which was right.

    Read-only, and bounded in both directions: at most
    :data:`MAX_CHANGED_FILES` entries, at most
    :data:`MAX_CHANGES_DIFF_CHARS` of diff, each truncation stated.
    """
    from raiker.tools.git import (  # noqa: PLC0415
        GitWorkingTreeDiffUnavailable,
        working_tree_changes,
        working_tree_diff,
    )

    repo = _owned_repo(request, repo_id, auth_data[0].principal_id)
    root = _repo_root(request, repo)
    if root is None:
        answer_0: CodeRepoChangesView = {
            "entries": [],
            "diff": "",
            "truncated": False,
            "diff_truncated": False,
            "root_missing": True,
            "reason_code": (
                "repo_not_checked_out"
                if str(repo.get("kind")) == "github"
                else "repo_folder_missing"
            ),
        }
        return serialize_dto(answer_0)
    if not (root / ".git").exists():
        # Not a failure: a plain folder is a perfectly good place to work, it
        # just has no history to compare against. Saying which of the two it is
        # keeps "no changes" from meaning "no version control".
        answer_1: CodeRepoChangesView = {
            "entries": [],
            "diff": "",
            "truncated": False,
            "diff_truncated": False,
            "root_missing": False,
            "reason_code": "not_a_git_repository",
        }
        return serialize_dto(answer_1)

    entries = working_tree_changes(root)
    truncated = len(entries) > MAX_CHANGED_FILES
    entries = entries[:MAX_CHANGED_FILES]
    reason_code = None
    try:
        diff = working_tree_diff(root, entries) if entries else ""
    except GitWorkingTreeDiffUnavailable:
        diff = ""
        reason_code = "git_diff_native_sandbox_required"
    diff_truncated = len(diff) > MAX_CHANGES_DIFF_CHARS
    answer_2: CodeRepoChangesView = {
        "entries": [
            {
                "path": entry["path"],
                "previous_path": entry.get("previous_path", ""),
                "state": entry["state"],
                "unstaged": bool(entry.get("unstaged")),
            }
            for entry in entries
        ],
        "diff": diff[:MAX_CHANGES_DIFF_CHARS],
        "truncated": truncated,
        "diff_truncated": diff_truncated,
        "root_missing": False,
        "reason_code": reason_code,
    }
    return serialize_dto(answer_2)


@router.get("/api/code/repos/{repo_id}/diagnostics")
async def read_code_repo_diagnostics(
    repo_id: str,
    request: Request,
    path: str = "",
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """Parse-level problems for one open file (GAP-BUILD B10).

    The workspace could show an owner a file and not tell them it no longer
    parses, which is the one thing they most want to know about a file the agent
    just edited. This is the same read the agent's own ``diagnostics`` tool
    performs, through the same service and the same ``language_intelligence``
    gate, so the browser and the model see one answer rather than two.

    A file whose language this runtime cannot parse comes back with
    ``checked: false``. The UI must say *not checked* for it — never *no
    problems* — for the same reason the tool does.
    """
    if not (path or "").strip():
        raise _bad_request("path_required")
    repo = _owned_repo(request, repo_id, auth_data[0].principal_id)
    root = _repo_root(request, repo)
    if root is None:
        raise _not_found(
            "repo_not_checked_out"
            if str(repo.get("kind")) == "github"
            else "repo_folder_missing"
        )
    # Resolved and contained the same way the file read above is, so this cannot
    # become a second, weaker path boundary.
    target = _resolved_target(request, root, path)
    if not target.is_file():
        raise _not_found("file_not_found")
    relative = target.relative_to(root).as_posix()

    from raiker.graph.language_service import LanguageIntelligenceService

    service = LanguageIntelligenceService(
        _ws(request),
        SQLiteStore(_ws(request)),
        principal_id=auth_data[0].principal_id,
        # This route is looking at *this* connected repository, which is not
        # necessarily the one a turn would index, and it has already resolved and
        # contained the root above. Naming it here keeps the two answers about
        # one file identical rather than depending on the owner's current
        # repository selection.
        repository_root=root,
    )
    result = service.diagnostics([relative])
    if result.get("status") != "success":
        error = result.get("error") or {}
        answer_0: CodeRepoDiagnosticsView = {
            "path": relative,
            "checked": False,
            "available": False,
            "reason_code": str(error.get("type") or "diagnostics_unavailable"),
            "reason": str(error.get("message") or ""),
            "diagnostics": [],
        }
        return serialize_dto(answer_0)
    checked = relative in (result.get("checked") or [])
    unsupported = result.get("unsupported") or []
    answer_1: CodeRepoDiagnosticsView = {
        "path": relative,
        "checked": checked,
        "available": True,
        "reason_code": "" if checked else "language_not_parseable",
        "reason": (
            ""
            if checked
            else str(unsupported[0].get("reason", "")) if unsupported else "This file was not checked."
        ),
        "diagnostics": result.get("diagnostics") or [],
    }
    return serialize_dto(answer_1)


@router.get("/api/code/repos/{repo_id}/target")
async def read_code_repo_target(
    repo_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """BR-D02 — where a Build turn on this repository would actually run.

    The folder, repository identity, branch, commit and command environment,
    with the fingerprint the turn is bound to. Read-only; a GitHub coordinate
    answers ``remote_only`` and a moved folder ``folder_missing`` rather than
    pretending the workspace root is the target.
    """
    from raiker.control.build_target import delegation_summary, describe_target  # noqa: PLC0415

    principal_id = auth_data[0].principal_id
    repo = _owned_repo(request, repo_id, principal_id)
    store = SQLiteStore(_ws(request))
    target = describe_target(store, _ws(request), principal_id, repo)
    answer: CodeRepoTargetView = cast(CodeRepoTargetView, target)
    answer["authority"] = cast(Any, delegation_summary(store, principal_id, target))
    return serialize_dto(answer)


def _current_patch(request: Request, repo: dict[str, Any]) -> tuple[str, str | None]:
    """The full working-tree diff for *repo*, or the reason there is none."""
    from raiker.tools.git import (  # noqa: PLC0415
        GitWorkingTreeDiffUnavailable,
        working_tree_changes,
        working_tree_diff,
    )

    root = _repo_root(request, repo)
    if root is None:
        return "", (
            "repo_not_checked_out" if str(repo.get("kind")) == "github" else "repo_folder_missing"
        )
    if not (root / ".git").exists():
        return "", "not_a_git_repository"
    entries = working_tree_changes(root)
    try:
        return (working_tree_diff(root, entries) if entries else ""), None
    except GitWorkingTreeDiffUnavailable:
        return "", "git_diff_native_sandbox_required"


def _review_answer(
    fingerprint: str,
    diff: str,
    review: dict[str, Any] | None,
    reused: bool,
    reason: str | None,
    previous: dict[str, Any] | None = None,
) -> CodeRepoReviewView:
    summary: PatchReviewSummary | None = None
    if review is None and previous is not None:
        summary = {
            "fingerprint": str(previous.get("fingerprint") or ""),
            "reviewed_at": str(previous.get("reviewed_at") or ""),
            "findings": len(previous.get("findings") or []),
            "counts": dict(previous.get("counts") or {}),
        }
    answer: CodeRepoReviewView = {
        "fingerprint": fingerprint,
        "has_changes": bool(diff),
        "review": cast(PatchReview, review) if review is not None else None,
        "reused": reused,
        "reason_code": reason,
        "previous": summary,
    }
    return answer


def _signed_view(
    store: SQLiteStore, principal_id: str, repo_id: str, review: dict[str, Any] | None
) -> tuple[dict[str, Any] | None, Any]:
    """BR-D05 — *review* without its signature bytes, and its verified signature state."""
    from raiker.review.review_attestation import public_attestation, verify_review  # noqa: PLC0415

    if review is None:
        return None, None
    state = verify_review(store, owner_principal_id=principal_id, repo_id=repo_id, review=review)
    shown = {key: value for key, value in review.items() if key != "attestation"}
    return shown, public_attestation(review, state)


def _attester(request: Request, store: SQLiteStore, principal_id: str, repo_id: str, kind: str) -> Any:
    from raiker.review.review_attestation import attest_review  # noqa: PLC0415

    def attest(review: dict[str, Any]) -> dict[str, Any]:
        return attest_review(
            _ws(request), store, owner_principal_id=principal_id, repo_id=repo_id,
            kind=kind,  # type: ignore[arg-type]
            review=review,
        )

    return attest


def _record_review(request: Request, principal_id: str, repo_id: str, review: dict[str, Any], reused: bool) -> None:
    """BR-D04 — audit that a review was taken or reused. Counts only, never content."""
    import contextlib  # noqa: PLC0415

    from raiker.events.types import make_event  # noqa: PLC0415
    from raiker.events.writer import EventLogWriter  # noqa: PLC0415

    store = SQLiteStore(_ws(request))
    session_id = f"sess_inbox_{principal_id}"
    with contextlib.suppress(Exception):
        store.create_session(session_id, str(_ws(request)), title="Inbox")
        EventLogWriter(store).append(
            make_event(
                session_id=session_id,
                turn_id=None,
                event_type="patch_review_completed",
                actor="code_review",
                payload={
                    "principal_id": principal_id,
                    "repo_id": repo_id,
                    "fingerprint": str(review.get("fingerprint") or ""),
                    "counts": dict(review.get("counts") or {}),
                    "new": sum(1 for item in review.get("findings") or [] if item.get("since") == "new"),
                    "resolved": len(review.get("resolved") or []),
                    "reused": reused,
                },
            )
        )


@router.get("/api/code/repos/{repo_id}/review")
async def read_code_repo_review(
    repo_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """BR-D04 — the stored review of the current patch, if one was taken."""
    from raiker.review.patch_review import (  # noqa: PLC0415
        latest_review,
        load_review,
        patch_fingerprint,
    )

    principal_id = auth_data[0].principal_id
    repo = _owned_repo(request, repo_id, principal_id)
    diff, reason = _current_patch(request, repo)
    fingerprint = patch_fingerprint(diff) if diff else ""
    store = SQLiteStore(_ws(request))
    review = (
        load_review(store, owner_principal_id=principal_id, repo_id=repo_id, fingerprint=fingerprint)
        if diff
        else None
    )
    previous = (
        latest_review(store, owner_principal_id=principal_id, repo_id=repo_id, exclude=fingerprint)
        if diff and review is None
        else None
    )
    shown, attestation = _signed_view(store, principal_id, repo_id, review)
    answer = _review_answer(fingerprint, diff, shown, review is not None, reason, previous)
    answer["attestation"] = attestation
    if diff:
        from raiker.review.model_review import load_model_review  # noqa: PLC0415

        reading = load_model_review(
            store, owner_principal_id=principal_id, repo_id=repo_id, fingerprint=fingerprint
        )
        shown_reading, model_attestation = _signed_view(store, principal_id, repo_id, reading)
        answer["model_review"] = cast(ModelPatchReview, shown_reading) if shown_reading is not None else None
        answer["model_attestation"] = model_attestation
    return serialize_dto(answer)


@router.post("/api/code/repos/{repo_id}/review")
async def review_code_repo_patch(
    repo_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """BR-D04 — review the exact current patch, once per patch.

    Reviewing a patch that already has a stored review returns that review with
    ``reused: true``: the same finding is never raised twice for the same
    change. Nothing in the working tree changes.
    """
    from raiker.review.patch_review import patch_fingerprint, review_once  # noqa: PLC0415

    principal_id = auth_data[0].principal_id
    repo = _owned_repo(request, repo_id, principal_id)
    diff, reason = _current_patch(request, repo)
    if not diff:
        empty = _review_answer("", diff, None, False, reason or "no_changes")
        return serialize_dto(empty)
    from raiker.review.patch_review import parse_findings  # noqa: PLC0415

    store = SQLiteStore(_ws(request))
    root = _repo_root(request, repo)

    def validator(files: list[str]) -> list[dict[str, Any]]:
        return parse_findings(_ws(request), store, principal_id, root, files)

    review, reused = review_once(
        store, owner_principal_id=principal_id, repo_id=repo_id, diff=diff, validator=validator,
        attest=_attester(request, store, principal_id, repo_id, "patch"),
    )
    _record_review(request, principal_id, repo_id, review, reused)
    shown, attestation = _signed_view(store, principal_id, repo_id, review)
    answer = _review_answer(patch_fingerprint(diff), diff, shown, reused, None)
    answer["attestation"] = attestation
    return serialize_dto(answer)


def _model_for_review(router: Any, default: tuple[str, str], body: ModelPatchReviewRequest) -> tuple[str, str]:
    """The ``(provider, model)`` the owner chose for this review, or their selection.

    A profile is named by its id, as a turn names it. An unknown or test-only
    profile, or a placeholder model, is refused rather than replaced with
    another model the owner did not choose.
    """
    from raiker.models.registry import RegistryError, profile_with_model  # noqa: PLC0415

    if not body.model_profile:
        # The owner's selection may still be a catalogue placeholder: that is
        # no model to send a patch to, and is said rather than tried.
        if not default[1] or "<" in default[1] or ">" in default[1]:
            raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "model_review_model_required")
        return default
    try:
        profile = router.registry.resolve_profile_id(body.model_profile)
    except RegistryError:
        raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "model_review_profile_unknown") from None
    if bool(profile.raw.get("test_only", False)):
        raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "model_review_profile_unknown")
    model = (body.model or profile.model or "").strip()
    if not model or "<" in model or ">" in model:
        raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "model_review_model_required")
    if model != profile.model and not router.registry.find(profile.provider, model):
        router.registry.register(profile_with_model(profile, model))
    return router.registry.turn_token(profile), model


def _record_model_review(
    request: Request, principal_id: str, repo_id: str, review: dict[str, Any], reused: bool
) -> None:
    """BR-D04 — audit a model reading: which model, which patch, counts. Never content."""
    import contextlib  # noqa: PLC0415

    from raiker.events.types import make_event  # noqa: PLC0415
    from raiker.events.writer import EventLogWriter  # noqa: PLC0415

    store = SQLiteStore(_ws(request))
    session_id = f"sess_inbox_{principal_id}"
    with contextlib.suppress(Exception):
        store.create_session(session_id, str(_ws(request)), title="Inbox")
        EventLogWriter(store).append(
            make_event(
                session_id=session_id,
                turn_id=None,
                event_type="patch_model_review_completed",
                actor="code_review",
                payload={
                    "principal_id": principal_id,
                    "repo_id": repo_id,
                    "fingerprint": str(review.get("fingerprint") or ""),
                    "provider": str(review.get("provider") or ""),
                    "model": str(review.get("model") or ""),
                    "counts": dict(review.get("counts") or {}),
                    "reused": reused,
                },
            )
        )


@router.post("/api/code/repos/{repo_id}/review/model")
async def model_review_code_repo_patch(
    repo_id: str,
    body: ModelPatchReviewRequest,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """BR-D04 — ask a connected model to read the exact current patch, once per patch and model.

    The patch is credential-redacted and framed as untrusted data, no tools are
    offered, and the reading is stored by the patch fingerprint and the model.
    Its findings are marked as the model's and never decide whether a turn is
    verified. The request reaches the provider only through the owner's own
    router: their gates and saved connections apply.
    """
    from raiker.events.writer import EventLogWriter  # noqa: PLC0415
    from raiker.models.contracts import ModelMessage  # noqa: PLC0415
    from raiker.models.exceptions import ModelProviderError, safe_error  # noqa: PLC0415
    from raiker.models.owner_runtime import owner_model_runtime  # noqa: PLC0415
    from raiker.models.registry import RegistryError  # noqa: PLC0415
    from raiker.review.model_review import (  # noqa: PLC0415
        MAX_OUTPUT_TOKENS,
        build_model_review,
        load_model_review,
        review_messages,
        save_model_review,
    )
    from raiker.review.patch_review import patch_fingerprint  # noqa: PLC0415

    principal_id = auth_data[0].principal_id
    repo = _owned_repo(request, repo_id, principal_id)
    diff, reason = _current_patch(request, repo)
    if not diff:
        empty: CodeRepoModelReviewView = {
            "fingerprint": "",
            "has_changes": False,
            "model_review": None,
            "reused": False,
            "reason_code": reason or "no_changes",
        }
        return serialize_dto(empty)
    store = SQLiteStore(_ws(request))
    fingerprint = patch_fingerprint(diff)
    router, default = owner_model_runtime(store, principal_id, EventLogWriter(store))
    provider, model = _model_for_review(router, default, body)
    stored = load_model_review(
        store, owner_principal_id=principal_id, repo_id=repo_id, fingerprint=fingerprint,
        provider=provider, model=model,
    )
    if stored is not None:
        _record_model_review(request, principal_id, repo_id, stored, True)
        shown_stored, stored_attestation = _signed_view(store, principal_id, repo_id, stored)
        reused: CodeRepoModelReviewView = {
            "fingerprint": fingerprint,
            "has_changes": True,
            "model_review": cast(ModelPatchReview, shown_stored),
            "reused": True,
            "reason_code": None,
            "model_attestation": stored_attestation,
        }
        return serialize_dto(reused)
    raw_messages, _truncated = review_messages(diff)
    messages = [ModelMessage(role=item["role"], content=item["content"]) for item in raw_messages]
    try:
        response = await router.achat(provider, model, messages, None, max_tokens=MAX_OUTPUT_TOKENS)
    except RegistryError:
        raise refusal(status.HTTP_422_UNPROCESSABLE_CONTENT, "model_review_profile_unknown") from None
    except ModelProviderError as exc:
        raise refusal(
            status.HTTP_502_BAD_GATEWAY, f"model_review_provider_error:{safe_error(str(exc))}"
        ) from None
    try:
        review = build_model_review(diff, provider=provider, model=model, answer=response.text)
    except ValueError:
        raise refusal(status.HTTP_502_BAD_GATEWAY, "model_review_unreadable") from None
    review = _attester(request, store, principal_id, repo_id, "model")(review)
    if not save_model_review(store, owner_principal_id=principal_id, repo_id=repo_id, review=review):
        again = load_model_review(
            store, owner_principal_id=principal_id, repo_id=repo_id, fingerprint=fingerprint,
            provider=provider, model=model,
        )
        review = again or review
    _record_model_review(request, principal_id, repo_id, review, False)
    shown_review, model_attestation = _signed_view(store, principal_id, repo_id, review)
    answer: CodeRepoModelReviewView = {
        "fingerprint": fingerprint,
        "has_changes": True,
        "model_review": cast(ModelPatchReview, shown_review),
        "reused": False,
        "reason_code": None,
        "model_attestation": model_attestation,
    }
    return serialize_dto(answer)


@router.get("/api/code/repos/{repo_id}/pull-requests")
async def read_code_repo_pull_requests(
    repo_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """BR-12 — receipts for the pull requests Raiker opened on this repository.

    Each receipt is what GitHub said when the pull request was read back after
    it was created. Evidence only: nothing reads a receipt to allow anything.
    """
    from raiker.control.build_target import _github_repository, describe_target  # noqa: PLC0415
    from raiker.github.delegations import credential_owner  # noqa: PLC0415
    from raiker.github.receipts import list_receipts  # noqa: PLC0415

    principal_id = auth_data[0].principal_id
    repo = _owned_repo(request, repo_id, principal_id)
    store = SQLiteStore(_ws(request))
    repository = _github_repository(describe_target(store, _ws(request), principal_id, repo)) or None
    receipts = (
        list_receipts(store, credential_owner(store, principal_id), repository=repository)
        if repository
        else []
    )
    answer: CodeRepoPullRequestsView = {
        "repository": repository,
        "receipts": [cast(PullRequestReceipt, row) for row in receipts],
        "reason_code": None if repository else "not_a_github_repository",
    }
    return serialize_dto(answer)


@router.get("/api/code/repos/{repo_id}/provenance")
async def read_code_repo_provenance(
    repo_id: str,
    request: Request,
    auth_data: tuple[ApiSession, Principal] = Depends(_auth),
) -> dict[str, Any]:
    """BR-D05 — recent commits and whether each says, provably, that Raiker made it.

    ``recorded`` means the commit's trailers name a session and turn this
    account's Raiker holds; ``unrecorded`` means they claim Raiker and nothing
    here backs them. Evidence only — nothing reads it to decide anything.
    """
    from raiker.control.build_provenance import read_provenance  # noqa: PLC0415

    repo = _owned_repo(request, repo_id, auth_data[0].principal_id)
    root = _repo_root(request, repo)
    reason: str | None = None
    commits: list[dict[str, Any]] = []
    if root is None:
        reason = "repo_not_checked_out" if str(repo.get("kind")) == "github" else "repo_folder_missing"
    elif not (root / ".git").exists():
        reason = "not_a_git_repository"
    else:
        commits = read_provenance(
            SQLiteStore(_ws(request)), root, user_id=auth_data[1].delegated_by_user_id
        )
    answer: CodeRepoProvenanceView = {
        "commits": cast(Any, commits),
        "reason_code": reason,
    }
    return serialize_dto(answer)
