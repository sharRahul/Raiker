from __future__ import annotations

import difflib
import os
import re
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from raiker.contracts.ids import utc_now
from raiker.runtime.git_credential import CREDENTIAL_HOSTS, credential_config
from raiker.tools.filesystem import (
    PROTECTED_WORKSPACE_DIRS,
    resolve_workspace_path,
)

_ALLOWED = {"status", "diff", "log"}

# B11 — a governed git write never runs the repository's own hooks. A commit or a
# branch switch would otherwise execute whatever `.git/hooks` contains, which is
# workspace content the agent may itself have written: an un-governed code path
# reached through a governed one. Pointing `core.hooksPath` at a directory that
# does not exist is the portable way to disable them for a single invocation.
_NO_HOOKS = ("-c", "core.hooksPath=raiker-no-such-hooks")
# Signing is the same argument: a configured `commit.gpgsign` would block the
# commit on an interactive passphrase prompt this process can never answer.
_NO_SIGN = ("-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false")
# Used only when the repository has no identity of its own. An owner who has
# configured `user.name`/`user.email` keeps theirs.
_FALLBACK_NAME = "Raiker agent"
_FALLBACK_EMAIL = "agent@raiker.local"

_MAX_DIFF_BYTES = 200_000
_MAX_PREVIEW_FILES = 200
_WRITE_TIMEOUT = 30

# Everything a branch name may not be. `git check-ref-format` is the authority
# and is consulted as well; these are the shapes that are refused before a
# subprocess is spawned at all.
_BRANCH_REJECT_PREFIXES = ("-", "refs/")


# ── BUG-66: which repository the git tools operate in ────────────────────────
#
# Build lets an owner connect a repository that is a *folder inside* the
# workspace, and every git tool runs in the repository the owner picked, never
# the workspace root by default. Resolution happens at call time rather than when
# the broker is built, because the owner can change the selection between turns.


def selected_repository_subpath(store: Any, owner_principal_id: str | None) -> str | None:
    """The workspace-relative folder of the repository selected in Build, if any.

    A GitHub-kind repository is a coordinate rather than a folder, so it selects
    nothing here: the git tools stay on the workspace root and `github_read` is
    the surface that reaches the remote.
    """
    if store is None or not owner_principal_id:
        return None
    try:
        rows = store.list_code_repos(owner_principal_id)
    except Exception:  # noqa: BLE001 — a storage failure must not lose the tool
        return None
    for row in rows:
        if not row.get("selected") or str(row.get("kind", "")) != "local":
            continue
        subpath = str(row.get("local_subpath") or "").strip()
        return subpath or None
    return None


def resolve_repository_root(workspace_root: str | Path, subpath: str | None = None) -> Path:
    """The directory the git tools run in: the selected repository, or the workspace.

    Containment is unchanged — the stored sub-path goes through the same
    workspace check every other path read uses — and anything that fails it
    falls back to the workspace root rather than widening the tools' reach.
    """
    root = resolve_workspace_path(workspace_root, ".")
    if not subpath:
        return root
    try:
        candidate = resolve_workspace_path(workspace_root, subpath)
    except Exception:  # noqa: BLE001 — an escaping or malformed sub-path is not fatal
        return root
    return candidate if candidate.is_dir() else root


def repository_label(workspace_root: str | Path, repo_root: str | Path) -> str:
    """How the owner names this repository: its workspace-relative path.

    The workspace itself is named ``.`` rather than an absolute path, because the
    label is shown in an approval and stored in the durable record, and neither
    needs the host's directory layout.
    """
    root = resolve_workspace_path(workspace_root, ".")
    resolved = Path(repo_root).resolve()
    try:
        relative = resolved.relative_to(root).as_posix()
    except ValueError:
        return resolved.name
    return relative or "."


#: Names that mark an environment variable as a credential. A local git command
#: never needs one, and a child of git — a filter, a hook-like `fsmonitor`, a
#: helper — would inherit whatever the host process holds (ADD-27 GH-24).
_SECRET_NAME_PARTS = ("TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL", "API_KEY", "PRIVATE_KEY")
_DROPPED_NAMES = frozenset({"SSH_AUTH_SOCK", "GIT_ASKPASS", "SSH_ASKPASS", "GH_ENTERPRISE_TOKEN"})

#: Applied to every local git command: a repository's own `core.fsmonitor`
#: names a program git runs on `status`, which would make a read a way to run
#: code. Turning it off costs only speed on very large trees.
_NO_FSMONITOR = ("-c", "core.fsmonitor=false")


def local_git_environment(source: dict[str, str] | None = None) -> dict[str, str]:
    """The host environment without anything that looks like a credential.

    Not the empty, workspace-homed environment a push or a sandboxed command
    gets: a local command keeps ``HOME`` so the owner's own ``user.name`` and
    ``user.email`` still sign their commits. What it loses is every token,
    secret, password and key variable, the SSH agent socket and any askpass
    program, and it can never prompt.
    """
    base = dict(os.environ if source is None else source)
    kept = {
        name: value
        for name, value in base.items()
        if name not in _DROPPED_NAMES
        and not name.startswith("RAIKER_")
        and not any(part in name.upper() for part in _SECRET_NAME_PARTS)
    }
    kept["GIT_TERMINAL_PROMPT"] = "0"
    return kept


def run_git(
    repo_root: str | Path,
    subcommand: str,
    args: list[str] | None = None,
    *,
    max_bytes: int = 200_000,
) -> dict[str, Any]:
    if subcommand not in _ALLOWED:
        return {
            "status": "denied",
            "error": {"type": "git_subcommand_denied", "subcommand": subcommand},
        }
    root = resolve_workspace_path(repo_root, ".")
    command = ["git", "-C", str(root), *_NO_FSMONITOR, subcommand, *(args or [])]
    proc = subprocess.run(
        command, check=False, capture_output=True, text=True, timeout=10,
        env=local_git_environment(),
    )
    output = (proc.stdout + proc.stderr)[:max_bytes]
    return {
        "status": "success" if proc.returncode == 0 else "failed",
        "returncode": proc.returncode,
        "output": output,
        "truncated": len(proc.stdout + proc.stderr) > max_bytes,
    }


# ── B11: the governed write path ─────────────────────────────────────────────
#
# `git_branch` and `git_commit` are proposals first and mutations second. Each
# has a *snapshot* function, which computes exactly what the mutation would do
# and never touches the repository, and an *execute* function, which the
# approval relay reaches only after a human approved that snapshot. The pair is
# deliberate: the transcript, the approval inbox and the executor all read the
# same computation, so what the owner approved is what runs.


def _git(
    root: Path, args: list[str], *, timeout: int = _WRITE_TIMEOUT
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *_NO_FSMONITOR, *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=local_git_environment(),
    )


def _failed(error_type: str, **detail: Any) -> dict[str, Any]:
    return {"status": "failed", "error": {"type": error_type, **detail}}


def _git_output(proc: subprocess.CompletedProcess[str]) -> str:
    return (proc.stdout + proc.stderr).strip()[:4_000]


def _repository(repo_root: str | Path) -> tuple[Path, dict[str, Any] | None]:
    """Resolve the selected repository, or the refusal that explains why not."""
    root = resolve_workspace_path(repo_root, ".")
    proc = _git(root, ["rev-parse", "--is-inside-work-tree"], timeout=10)
    if proc.returncode != 0 or proc.stdout.strip() != "true":
        return root, _failed("not_a_git_repository", path=str(root))
    return root, None


def _busy_reason(root: Path) -> str | None:
    """Name the in-progress git operation that makes a write unsafe, if any."""
    git_dir_proc = _git(root, ["rev-parse", "--git-dir"], timeout=10)
    if git_dir_proc.returncode != 0:
        return None
    git_dir = Path(git_dir_proc.stdout.strip())
    if not git_dir.is_absolute():
        git_dir = root / git_dir
    for marker, name in (
        ("MERGE_HEAD", "merge"),
        ("CHERRY_PICK_HEAD", "cherry_pick"),
        ("REVERT_HEAD", "revert"),
        ("BISECT_LOG", "bisect"),
        ("rebase-merge", "rebase"),
        ("rebase-apply", "rebase"),
    ):
        if (git_dir / marker).exists():
            return name
    return None


def current_branch(root: Path) -> str:
    """The checked-out branch, or an empty string on a detached or unborn HEAD."""
    proc = _git(root, ["symbolic-ref", "--quiet", "--short", "HEAD"], timeout=10)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _head_commit(root: Path) -> str:
    proc = _git(root, ["rev-parse", "--short", "HEAD"], timeout=10)
    return proc.stdout.strip() if proc.returncode == 0 else ""


_STATUS_WORDS = {
    "A": "added",
    "M": "modified",
    "D": "deleted",
    "R": "renamed",
    "C": "copied",
    "T": "type changed",
    "U": "unmerged",
    "?": "untracked",
}


def _is_protected(path: str) -> bool:
    """True for a path inside a directory a governed mutation may never touch.

    The Raiker workspace *contains* its own substrate: `.raiker/` holds the
    encrypted store, the audit log, the vault key and the hook definitions, and
    `.git/` holds the hooks that run on the next commit. A commit that swept the
    working tree would otherwise write the owner's key material into git
    history, which is the opposite of what approving a commit was for.
    """
    head = path.replace("\\", "/").split("/", 1)[0]
    return head in PROTECTED_WORKSPACE_DIRS


def _porcelain(root: Path, paths: list[str] | None) -> list[dict[str, str]]:
    """Working-tree changes as `{path, state, code}`, in git's own order."""
    args = ["status", "--porcelain", "--untracked-files=all"]
    if paths:
        args = [*args, "--", *paths]
    proc = _git(root, args)
    if proc.returncode != 0:
        return []
    entries: list[dict[str, str]] = []
    for line in proc.stdout.splitlines():
        if len(line) < 4:
            continue
        index_state, worktree_state, path = line[0], line[1], line[3:]
        # A rename is reported as `old -> new`, and **both** paths have to be
        # committed: staging only the new one records the addition and leaves the
        # old file's deletion behind, which is a half-recorded rename the owner
        # was told was one change.
        previous = ""
        if " -> " in path:
            previous, path = (part.strip('"') for part in path.split(" -> ", 1))
        path = path.strip('"')
        if _is_protected(path):
            continue
        code = index_state if index_state not in (" ", "?") else worktree_state
        entries.append(
            {
                "path": path,
                "previous_path": previous,
                "state": _STATUS_WORDS.get(code, "changed"),
                "code": (index_state + worktree_state).strip() or code,
                # Whether the working tree still differs from the index for this
                # path. A change the owner already staged needs no `git add`, and
                # asking for one would fail: the source half of a staged rename
                # matches neither the working tree nor the index any more.
                "unstaged": "yes" if worktree_state != " " else "",
            }
        )
    return entries


def working_tree_changes(root: Path) -> list[dict[str, str]]:
    """Every uncommitted change in *root*, as the commit proposal sees them.

    A public name for :func:`_porcelain`, added when Build's artifact pane
    needed the same list (the Build artifact pane). It delegates rather than reimplementing for
    one reason: the pane that shows "Changes" and the commit that records them
    have to describe one change set. A second `git status` written for the
    browser could disagree with the proposal, and nothing in the interface would
    say which of the two was right.
    """
    return _porcelain(root, None)


def working_tree_diff(root: Path, entries: list[dict[str, str]]) -> str:
    """The complete diff those *entries* represent, tracked and untracked alike.

    The public half of :func:`_commit_diff`, for the same reason as above.
    """
    return _commit_diff(root, entries)


def _entry_paths(entries: list[dict[str, str]]) -> list[str]:
    """Every path a commit of *entries* records, renames counted at both ends."""
    paths: list[str] = []
    for entry in entries:
        if entry.get("previous_path"):
            paths.append(entry["previous_path"])
        paths.append(entry["path"])
    return paths


def _untracked_diff(root: Path, path: str) -> str:
    """A unified diff for a file git does not track yet, or `""` if it cannot be read."""
    try:
        target = root / path
        if not target.is_file() or target.stat().st_size > _MAX_DIFF_BYTES:
            return ""
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    return "".join(
        difflib.unified_diff(
            [], text.splitlines(keepends=True), fromfile="/dev/null", tofile=f"b/{path}"
        )
    )


def _commit_diff(root: Path, entries: list[dict[str, str]]) -> str:
    """The complete diff of what a commit would record, tracked and untracked alike.

    Scoped to the proposal's own paths rather than to the whole tree, so the
    preview and the execution describe one and the same change set.
    """
    tracked_paths = _entry_paths([e for e in entries if e["state"] != "untracked"])
    parts: list[str] = []
    if tracked_paths:
        tracked = _git(root, ["diff", "HEAD", "--", *tracked_paths])
        if tracked.returncode == 0:
            parts.append(tracked.stdout)
    for entry in entries:
        if entry["state"] == "untracked":
            parts.append(_untracked_diff(root, entry["path"]))
    return "".join(parts)


def _identity_args(root: Path) -> list[str]:
    """A committer identity only when the repository does not already have one."""
    args: list[str] = []
    if not _git(root, ["config", "--get", "user.name"], timeout=10).stdout.strip():
        args += ["-c", f"user.name={_FALLBACK_NAME}"]
    if not _git(root, ["config", "--get", "user.email"], timeout=10).stdout.strip():
        args += ["-c", f"user.email={_FALLBACK_EMAIL}"]
    return args


def _valid_branch_name(root: Path, name: str) -> bool:
    if not name or name.startswith(_BRANCH_REJECT_PREFIXES) or name.strip() != name:
        return False
    return _git(root, ["check-ref-format", "--branch", name], timeout=10).returncode == 0


def _branch_exists(root: Path, name: str) -> bool:
    return (
        _git(root, ["show-ref", "--verify", "--quiet", f"refs/heads/{name}"], timeout=10).returncode
        == 0
    )


def _ref_exists(root: Path, ref: str) -> bool:
    return _git(root, ["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], timeout=10).returncode == 0


def proposed_branch_snapshot(
    repo_root: str | Path, name: str, base: str | None = None
) -> dict[str, Any]:
    """What creating branch *name* would do — computed without touching the repository.

    Fail-closed on every case a later execution could not honour: no repository,
    a name git itself would reject, a branch that already exists, an unknown
    base, an operation already in progress, and — only when a *base* is named,
    because that is the case that moves the working tree — uncommitted changes.
    """
    root, refusal = _repository(repo_root)
    if refusal is not None:
        return refusal
    name = (name or "").strip()
    if not _valid_branch_name(root, name):
        return _failed("invalid_branch_name", name=name)
    if _branch_exists(root, name):
        return _failed("branch_exists", name=name)
    busy = _busy_reason(root)
    if busy is not None:
        return _failed("repository_busy", operation=busy)
    base_ref = (base or "").strip()
    if base_ref and not _ref_exists(root, base_ref):
        return _failed("unknown_base_ref", base=base_ref)
    dirty = _porcelain(root, None)
    if base_ref and dirty:
        return _failed("working_tree_dirty", file_count=len(dirty), base=base_ref)
    return {
        "status": "success",
        "name": name,
        "base": base_ref or None,
        "current_branch": current_branch(root),
        "head": _head_commit(root),
        "uncommitted_files": len(dirty),
    }


def create_branch(
    repo_root: str | Path, name: str, base: str | None = None
) -> dict[str, Any]:
    """Create branch *name* and check it out. Re-validates everything first."""
    snapshot = proposed_branch_snapshot(repo_root, name, base)
    if snapshot["status"] != "success":
        return snapshot
    root = resolve_workspace_path(repo_root, ".")
    args = [*_NO_HOOKS, "switch", "--create", snapshot["name"]]
    if snapshot["base"]:
        args.append(str(snapshot["base"]))
    proc = _git(root, args)
    if proc.returncode != 0:
        return _failed("git_command_failed", command="switch", output=_git_output(proc))
    return {
        "status": "success",
        "branch": snapshot["name"],
        "base": snapshot["base"],
        "previous_branch": snapshot["current_branch"],
        "head": _head_commit(root),
    }


def _normalise_paths(root: Path, paths: Any) -> tuple[list[str] | None, dict[str, Any] | None]:
    """Workspace-confined, repository-relative paths — or the refusal that names one."""
    if paths is None:
        return None, None
    if isinstance(paths, str):
        paths = [paths]
    if not isinstance(paths, list):
        return None, _failed("invalid_paths")
    cleaned: list[str] = []
    for raw in paths:
        candidate = str(raw).strip()
        if not candidate:
            continue
        try:
            resolved = resolve_workspace_path(root, candidate)
        except Exception:
            return None, _failed("path_outside_repository", path=candidate)
        try:
            relative = resolved.relative_to(root).as_posix()
        except ValueError:
            return None, _failed("path_outside_repository", path=candidate)
        if _is_protected(relative):
            return None, _failed("protected_workspace_path", path=relative)
        cleaned.append(relative)
    return (cleaned or None), None


def proposed_commit_snapshot(
    repo_root: str | Path, message: str, paths: Any = None
) -> dict[str, Any]:
    """Exactly what committing would record — the file list and the complete diff.

    Nothing is staged and nothing is written: the index is left as the owner had
    it, so a rejected proposal costs the repository nothing.
    """
    root, refusal = _repository(repo_root)
    if refusal is not None:
        return refusal
    text = (message or "").strip()
    if not text:
        return _failed("empty_commit_message")
    selected, path_error = _normalise_paths(root, paths)
    if path_error is not None:
        return path_error
    busy = _busy_reason(root)
    if busy is not None:
        return _failed("repository_busy", operation=busy)
    entries = _porcelain(root, selected)
    if not entries:
        return _failed("nothing_to_commit", paths=selected or [])
    diff = _commit_diff(root, entries)
    truncated = len(diff) > _MAX_DIFF_BYTES
    return {
        "status": "success",
        "message": text,
        "subject": text.splitlines()[0],
        "branch": current_branch(root) or "(detached HEAD)",
        "head": _head_commit(root),
        "paths": selected or [],
        # The complete change set, which the execution stages verbatim. `files`
        # below is the same list bounded for display; committing from the bound
        # would silently drop everything past it.
        "commit_paths": _entry_paths(entries),
        # The complete entry list the execution stages from. `files` below is the
        # same list bounded for display; staging from the bound would silently
        # drop everything past it.
        "entries": entries,
        "files": entries[:_MAX_PREVIEW_FILES],
        "file_count": len(entries),
        "diff": diff[:_MAX_DIFF_BYTES],
        "truncated": truncated,
    }


def create_commit(
    repo_root: str | Path, message: str, paths: Any = None
) -> dict[str, Any]:
    """Stage the proposed change set and record one commit. Re-validates first."""
    snapshot = proposed_commit_snapshot(repo_root, message, paths)
    if snapshot["status"] != "success":
        return snapshot
    root = resolve_workspace_path(repo_root, ".")
    # Exactly the paths the owner was shown — not `--all`, which would sweep
    # `.raiker/` (the vault key, the audit log, the encrypted store) into the
    # commit, and not the index, which the owner may have staged for themselves.
    staging: list[str] = list(snapshot["commit_paths"])
    to_add = [entry["path"] for entry in snapshot["entries"] if entry.get("unstaged")]
    if to_add:
        staged = _git(root, [*_NO_HOOKS, "add", "--", *to_add])
        if staged.returncode != 0:
            return _failed("git_command_failed", command="add", output=_git_output(staged))
    # A path-limited commit records only these paths, whatever else happens to
    # be staged. It is the all-or-nothing property the approval promised.
    commit_args = [
        *_NO_HOOKS,
        *_NO_SIGN,
        *_identity_args(root),
        "commit",
        "--message",
        str(snapshot["message"]),
        "--",
        *staging,
    ]
    proc = _git(root, commit_args)
    if proc.returncode != 0:
        return _failed("git_command_failed", command="commit", output=_git_output(proc))
    return {
        "status": "success",
        "commit": _head_commit(root),
        "branch": current_branch(root) or "(detached HEAD)",
        "subject": str(snapshot["subject"]),
        "files": list(snapshot["files"]),
        "file_count": int(snapshot["file_count"]),
    }


# ── BUG-67: the governed push ────────────────────────────────────────────────
#
# A branch and a commit are local: the machine keeps them and the owner can undo
# them in git. A push is a different question — it carries repository content off
# the machine with the owner's credential, and nothing brings it back. So it sits
# behind its own capability (`git_push_execution`) rather than inside
# `git_write_execution`, and behind the same two boundaries every other egress
# path answers to: the owner's connector egress allowlist and the owner's own
# credential. Neither is model-supplied, and both are checked again at execution.

GIT_PUSH_TOKEN_ENV = "RAIKER_GITHUB_TOKEN"
#: Where the owner gives a push its credential. A refusal names this rather than
#: an environment variable: the vault is the supported home (RAIKER-2022), and
#: the variable is only one more way of filling it.
GIT_CREDENTIAL_SETTING = "Settings → GitHub"
# The token above is a GitHub credential. Sending it to another forge because a
# remote happens to be HTTPS would be a credential leak dressed up as a feature,
# so a push is only offered for the host the credential belongs to — and the
# same list is what the credential helper below will answer for, so the check
# above the push and the check inside the child cannot drift apart.
GIT_PUSH_CREDENTIAL_HOSTS: frozenset[str] = frozenset(CREDENTIAL_HOSTS)
_PUSH_TIMEOUT = 120
_MAX_PREVIEW_COMMITS = 50
# The value the inline credential helper reads. It is passed in the child's
# environment rather than on the command line, so the token never appears in the
# process table or in a captured command string.
_PUSH_TOKEN_VAR = "RAIKER_GIT_PUSH_TOKEN"


def _credential_args() -> list[str]:
    """The ``-c`` pairs that install the host-scoped credential helper."""
    return [item for value in credential_config(_PUSH_TOKEN_VAR) for item in ("-c", value)]


def push_egress_allowlist() -> frozenset[str]:
    """The owner's connector egress allowlist — the hosts a push may reach."""
    from raiker.runtime.executors.sandbox import connector_egress_allowlist

    return connector_egress_allowlist()


def _push_credential(lent: str | None = None) -> str:
    """The credential a push may use: only what the broker lent for this command.

    Reading ``RAIKER_GITHUB_TOKEN`` here as well let a host that still exported
    it push with no grant at all (ADD-27 GH-13). The broker now treats that
    variable as one more source of the owner's token and lends it under the same
    grant as the vault's, so this function has nothing to fall back to.
    """
    return (lent or "").strip()


def _remote_names(root: Path) -> list[str]:
    proc = _git(root, ["remote"], timeout=10)
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _remote_url(root: Path, remote: str) -> str:
    """The URL a *push* to *remote* would really use.

    ``--push`` because a remote may carry a separate `pushurl`, and `get-url`
    resolves `url.<base>.insteadOf` rewrites — so what is checked below is the
    address git will contact rather than the address the config file spells.
    """
    proc = _git(root, ["remote", "get-url", "--push", remote], timeout=10)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _upstream_remote(root: Path, branch: str) -> str:
    """The remote *branch* already tracks, or ``""`` when it tracks nothing."""
    proc = _git(
        root, ["config", "--get", f"branch.{branch}.remote"], timeout=10
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _tracking_ref(root: Path, remote: str, branch: str) -> str:
    """The local record of where the remote branch was, or ``""`` if there is none.

    Deliberately local. Asking the remote would be egress performed *before* the
    owner approved any, so the preview says what this machine last knew and the
    execution finds out the truth.
    """
    ref = f"refs/remotes/{remote}/{branch}"
    return ref if _git(root, ["rev-parse", "--verify", "--quiet", ref], timeout=10).returncode == 0 else ""


def _count(root: Path, selection: list[str]) -> int:
    proc = _git(root, ["rev-list", "--count", *selection], timeout=15)
    try:
        return int(proc.stdout.strip())
    except ValueError:
        return 0


def _branch_sha(root: Path, branch: str) -> str:
    """The full commit *branch* points at, or ``""``."""
    proc = _git(root, ["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}^{{commit}}"], timeout=10)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _commit_lines(root: Path, selection: list[str]) -> list[str]:
    proc = _git(
        root,
        ["log", "--oneline", "--no-decorate", f"-n{_MAX_PREVIEW_COMMITS}", *selection],
        timeout=15,
    )
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _outgoing(remote: str, branch: str, tracking: str) -> list[str]:
    """The commits a push would send, as rev-list arguments.

    For a branch the remote already has, that is everything past its last known
    position. For a branch it has never seen there is no such position, and
    counting every commit on the branch would tell the owner a fork of `main`
    carries its whole history — so what is counted is what no ref on that remote
    already reaches.
    """
    if tracking:
        return [f"{tracking}..{branch}"]
    return [branch, "--not", f"--remotes={remote}"]


def _redact_token(text: str, lent: str | None = None) -> str:
    """Remove the credential from anything git said.

    Belt and braces with the redactor's own registry: this catches the exact
    value in *this* command's output, and ``remember_secret`` catches it
    everywhere else for as long as the loan lasts.
    """
    token = _push_credential(lent)
    return text.replace(token, "***") if token else text


_SCP_REMOTE = re.compile(r"^(?P<user>[A-Za-z0-9._-]+)@(?P<host>[A-Za-z0-9.-]+):(?P<path>[^/].*)$")


def parse_remote(url: str) -> dict[str, Any]:
    """The transport, host, port, user and path of a remote URL git will contact.

    HTTPS (``https://github.com/owner/repo.git``) and SSH, in both spellings git
    accepts (``git@github.com:owner/repo.git`` and
    ``ssh://git@ssh.github.com:443/owner/repo.git``). Anything else is reported
    with ``transport`` ``""`` so the caller can name it.
    """
    value = (url or "").strip()
    scp = _SCP_REMOTE.match(value)
    if scp and "://" not in value:
        return {"transport": "ssh", "host": scp.group("host").lower(), "port": None,
                "user": scp.group("user"), "path": scp.group("path")}
    parsed = urlsplit(value)
    if parsed.scheme == "ssh" and parsed.hostname:
        return {"transport": "ssh", "host": parsed.hostname.lower(), "port": parsed.port,
                "user": parsed.username or "", "path": parsed.path.lstrip("/")}
    if parsed.scheme in ("https", "http") and parsed.hostname:
        return {"transport": parsed.scheme, "host": parsed.hostname.lower(), "port": parsed.port,
                "user": parsed.username or "", "password": parsed.password or "",
                "netloc": parsed.netloc, "path": parsed.path.lstrip("/")}
    return {"transport": "", "host": "", "scheme": parsed.scheme or "ssh"}


def proposed_push_snapshot(
    repo_root: str | Path,
    remote: str | None = None,
    branch: str | None = None,
    *,
    credential: str | None = None,
    credential_configured: bool | None = None,
    credential_method: str | None = None,
) -> dict[str, Any]:
    """Exactly what pushing would send — computed without touching the network.

    *credential_configured* is the broker's answer to "does the owner hold a
    credential for this?", which is all a proposal needs: the value itself is
    lent only at execution, under a grant. A preview that read only the legacy
    environment variable refused every push for an owner whose token was in the
    vault (BUG-334).

    Fail-closed on every case a later execution could not honour: no repository,
    a detached or unknown branch, an unknown remote, a remote this process holds
    no credential for, a host the owner has not allowlisted, and a branch with
    nothing on it the remote does not already have.
    """
    root, refusal = _repository(repo_root)
    if refusal is not None:
        return refusal
    branch_name = (branch or "").strip() or current_branch(root)
    if not branch_name:
        return _failed("detached_head")
    if not _valid_branch_name(root, branch_name) or not _branch_exists(root, branch_name):
        return _failed("unknown_branch", branch=branch_name)
    remotes = _remote_names(root)
    if not remotes:
        return _failed("no_remote_configured")
    remote_name = (
        (remote or "").strip()
        or _upstream_remote(root, branch_name)
        or ("origin" if "origin" in remotes else remotes[0])
    )
    if remote_name not in remotes:
        return _failed("unknown_remote", remote=remote_name, remotes=remotes)
    url = _remote_url(root, remote_name)
    from raiker.github.hosts import SSH_TRANSPORT_HOSTS, transport_allowed

    remote_parts = parse_remote(url)
    transport = remote_parts["transport"]
    if transport == "ssh":
        # ADD-27 GH-22 — SSH to GitHub, as the `git` user, on the port each
        # GitHub SSH host answers on. The key is the owner's selected one, lent
        # with Raiker's pinned host keys; nothing in the user's SSH config is read.
        host = str(remote_parts["host"])
        if host not in SSH_TRANSPORT_HOSTS:
            return _failed("unsupported_remote_host", host=host, credential=GIT_CREDENTIAL_SETTING)
        port = remote_parts.get("port")
        if remote_parts.get("user") != "git" or (port is not None and port != SSH_TRANSPORT_HOSTS[host]):
            return _failed("unsupported_remote_url", remote=remote_name, scheme="ssh")
    elif transport in ("https", "http"):
        host = str(remote_parts["host"])
        if transport != "https":
            return _failed("insecure_remote_url", remote=remote_name, host=host)
        if remote_parts.get("user") or remote_parts.get("password"):
            # A credential baked into the remote URL would be used instead of the
            # owner's governed one, and would be pushed past every check below.
            return _failed("remote_url_has_credentials", remote=remote_name, host=host)
        if host not in GIT_PUSH_CREDENTIAL_HOSTS:
            return _failed("unsupported_remote_host", host=host, credential=GIT_CREDENTIAL_SETTING)
    else:
        return _failed("unsupported_remote_url", remote=remote_name, scheme=str(remote_parts.get("scheme")))
    if not transport_allowed(host, push_egress_allowlist()):
        return _failed("push_egress_denied", host=host)
    if credential_method is not None:
        # The selected credential has to be the kind this remote authenticates
        # with: a token for HTTPS, a key for SSH. Neither stands in for the other.
        if (transport == "ssh") != (credential_method == "ssh"):
            return _failed(
                "push_credential_wrong_method", transport=transport,
                credential=GIT_CREDENTIAL_SETTING,
            )
        available = True
    else:
        available = (
            bool(_push_credential(credential)) if credential_configured is None else credential_configured
        )
    if not available:
        return _failed("push_credential_unset", credential=GIT_CREDENTIAL_SETTING)
    tracking = _tracking_ref(root, remote_name, branch_name)
    creates_remote_branch = not tracking
    selection = _outgoing(remote_name, branch_name, tracking)
    ahead = _count(root, selection)
    behind = _count(root, [f"{branch_name}..{tracking}"]) if tracking else 0
    if tracking and ahead == 0:
        return _failed("nothing_to_push", remote=remote_name, branch=branch_name)
    commits = _commit_lines(root, selection)
    return {
        "status": "success",
        "remote": remote_name,
        "remote_url": url,
        "transport": transport,
        "host": host,
        "branch": branch_name,
        "head": _head_commit(root),
        # The commit this push would send, in full. It is what an approval is
        # bound to (BUG-336): the push sends this commit and nothing newer.
        "head_sha": _branch_sha(root, branch_name),
        "creates_remote_branch": creates_remote_branch,
        "commit_count": ahead,
        "behind": behind,
        "commits": commits,
        "truncated": ahead > len(commits),
    }


#: What an approval of a push is bound to (BUG-336): the remote and the URL git
#: will contact, the branch, and the commit the owner saw at its head.
PUSH_BINDING_FIELDS: tuple[str, ...] = ("remote", "remote_url", "branch", "head_sha")


def push_target_changes(snapshot: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    """The fields of *expected* the repository no longer matches, in a stable order."""
    return [
        field
        for field in PUSH_BINDING_FIELDS
        if str(expected.get(field) or "") != str(snapshot.get(field) or "")
    ]


def push_branch(
    repo_root: str | Path,
    remote: str | None = None,
    branch: str | None = None,
    *,
    credential: str | None = None,
    expected: dict[str, Any] | None = None,
    ssh_command: str | None = None,
) -> dict[str, Any]:
    """Push the proposed branch to the proposed remote. Re-validates everything first.

    Never forces and never deletes: the refspec is written out in full so a
    branch name can neither be read as an option nor move a ref it does not name.

    The source of the refspec is the commit the snapshot found, not the branch
    name, so a commit made while this function runs cannot ride along. With
    *expected* — the binding recorded when the owner was asked — a remote, URL,
    branch or head that moved since then refuses ``push_target_changed`` instead
    of publishing something the approval never showed (BUG-336).
    """
    snapshot = proposed_push_snapshot(
        repo_root, remote, branch, credential=credential,
        credential_method="ssh" if ssh_command else ("token" if _push_credential(credential) else None),
    )
    if snapshot["status"] != "success":
        return snapshot
    if expected is not None:
        changed = push_target_changes(snapshot, expected)
        if changed:
            return _failed("push_target_changed", changed=changed,
                           remote=str(snapshot["remote"]), branch=str(snapshot["branch"]))
    root = resolve_workspace_path(repo_root, ".")
    remote_name = str(snapshot["remote"])
    branch_name = str(snapshot["branch"])
    head_sha = str(snapshot["head_sha"])
    if not head_sha:
        return _failed("unknown_branch", branch=branch_name)
    # RAIKER-2023: a constructed environment, not the host's. A push inheriting
    # `os.environ` handed the child every credential the host held, which is the
    # opposite of lending one for a single command.
    environment = _lend_environment(root, credential, ssh_command)
    args = [
        "git",
        "-C",
        str(root),
        *_NO_HOOKS,
        # An empty helper first clears whatever the host has configured, so a
        # system keychain cannot quietly supply a different account's credential
        # than the one the owner governed; the entries after it install Raiker's
        # helper against the credential's own hosts, so a redirect or a rewrite
        # that sends git elsewhere is never offered this token.
        *_credential_args(),
        "push",
        remote_name,
        f"{head_sha}:refs/heads/{branch_name}",
    ]
    try:
        proc = subprocess.run(
            args, check=False, capture_output=True, text=True,
            timeout=_PUSH_TIMEOUT, env=environment,
        )
    except subprocess.TimeoutExpired:
        return _failed("push_timed_out", remote=remote_name, branch=branch_name)
    output = _redact_token(_git_output(proc), credential)
    if proc.returncode != 0:
        lowered = output.lower()
        if "non-fast-forward" in lowered or "fetch first" in lowered or "rejected" in lowered:
            return _failed("push_rejected_non_fast_forward", remote=remote_name,
                           branch=branch_name, output=output)
        if "authentication failed" in lowered or "403" in lowered or "denied" in lowered:
            return _failed("push_authentication_failed", remote=remote_name,
                           branch=branch_name, output=output)
        return _failed("git_command_failed", command="push", output=output)
    if snapshot["creates_remote_branch"] and not _upstream_remote(root, branch_name):
        # A commit as the refspec's source sets no upstream, which
        # `--set-upstream` did for a branch name; record it the same way.
        _git(root, ["config", f"branch.{branch_name}.remote", remote_name], timeout=10)
        _git(root, ["config", f"branch.{branch_name}.merge", f"refs/heads/{branch_name}"], timeout=10)
    return {
        "status": "success",
        "remote": remote_name,
        "host": str(snapshot["host"]),
        "branch": branch_name,
        "head": head_sha[:7],
        "head_sha": head_sha,
        "commit_count": int(snapshot["commit_count"]),
        "created_remote_branch": bool(snapshot["creates_remote_branch"]),
        "output": output,
        # GH-54 — what the remote says the branch is now, read back under the
        # same loan: git reporting success is not the same as the ref landing.
        "receipt": read_back_ref(
            root, remote_name, branch_name, expected_sha=head_sha,
            credential=credential, ssh_command=ssh_command,
        ),
    }


def _lend_environment(root: Path, credential: str | None, ssh_command: str | None) -> dict[str, str]:
    from raiker.runtime.command_policy import sandbox_environment

    return sandbox_environment(
        workspace_root=root,
        extra={
            _PUSH_TOKEN_VAR: _push_credential(credential),
            # No terminal, no GUI prompt: a push that cannot authenticate must
            # fail with a reason rather than block this process for its cap.
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "",
            "SSH_ASKPASS": "",
            # Over SSH, the selected key and the pinned host keys only. The
            # variable outranks any `core.sshCommand` a repository sets.
            **({"GIT_SSH_COMMAND": ssh_command} if ssh_command else {}),
        },
    )


_READ_BACK_TIMEOUT = 30


def read_back_ref(
    repo_root: str | Path,
    remote_name: str,
    branch_name: str,
    *,
    expected_sha: str,
    credential: str | None = None,
    ssh_command: str | None = None,
) -> dict[str, Any]:
    """Ask the remote what ``refs/heads/<branch>`` points at (ADD-27 GH-54).

    The receipt says whether it is the commit just pushed. It never fails the
    push — that already happened — it only says whether it was confirmed.
    """
    root = resolve_workspace_path(repo_root, ".")
    checked_at = utc_now()
    args = [
        "git", "-C", str(root), *_NO_HOOKS, *_credential_args(),
        "ls-remote", "--refs", remote_name, f"refs/heads/{branch_name}",
    ]
    try:
        proc = subprocess.run(
            args, check=False, capture_output=True, text=True,
            timeout=_READ_BACK_TIMEOUT, env=_lend_environment(root, credential, ssh_command),
        )
    except (subprocess.TimeoutExpired, OSError):
        return {"verified": False, "remote_sha": None, "reason": "read_back_failed", "checked_at": checked_at}
    if proc.returncode != 0:
        return {"verified": False, "remote_sha": None, "reason": "read_back_failed", "checked_at": checked_at}
    remote_sha = ""
    for line in (proc.stdout or "").splitlines():
        sha, _, ref = line.partition("\t")
        if ref.strip() == f"refs/heads/{branch_name}":
            remote_sha = sha.strip()
            break
    verified = bool(remote_sha) and remote_sha == expected_sha
    reason = None if verified else ("remote_ref_missing" if not remote_sha else "remote_ref_differs")
    return {"verified": verified, "remote_sha": remote_sha or None, "reason": reason, "checked_at": checked_at}


# ── ADD-27 GH-23: governed fetch and clone ──────────────────────────────────
#
# Bringing a repository's history onto this machine is network egress like a
# push, so it answers to its own capability (`git_fetch_execution`), the same
# host rules, and the owner's decision. What it must never do is run what it
# fetched: no submodule is followed, no hook runs, the `file` and `ext`
# transports are off, an fsmonitor is ignored and every object is checked. A
# clone's address is built here from `owner/name`; a model never supplies a URL.

_FETCH_TIMEOUT = 180
_SAFE_TRANSFER = (
    "-c", "protocol.file.allow=never",
    "-c", "protocol.ext.allow=never",
    "-c", "transfer.fsckObjects=true",
    "-c", "submodule.recurse=false",
    "-c", "fetch.recurseSubmodules=false",
)
_GITHUB_REPOSITORY = re.compile(r"^(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/(?P<name>[A-Za-z0-9._-]{1,100})$")


def _transport_refusal(url: str, remote_name: str, credential_method: str | None) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """The checks a push makes on where git will go, shared with fetch."""
    from raiker.github.hosts import SSH_TRANSPORT_HOSTS, transport_allowed

    parts = parse_remote(url)
    transport = parts["transport"]
    host = str(parts.get("host") or "")
    if transport == "ssh":
        port = parts.get("port")
        if host not in SSH_TRANSPORT_HOSTS:
            return _failed("unsupported_remote_host", host=host, credential=GIT_CREDENTIAL_SETTING), parts
        if parts.get("user") != "git" or (port is not None and port != SSH_TRANSPORT_HOSTS[host]):
            return _failed("unsupported_remote_url", remote=remote_name, scheme="ssh"), parts
        if credential_method != "ssh":
            return _failed("fetch_credential_wrong_method", transport="ssh",
                           credential=GIT_CREDENTIAL_SETTING), parts
    elif transport in ("https", "http"):
        if transport != "https":
            return _failed("insecure_remote_url", remote=remote_name, host=host), parts
        if parts.get("user") or parts.get("password"):
            return _failed("remote_url_has_credentials", remote=remote_name, host=host), parts
        if host not in GIT_PUSH_CREDENTIAL_HOSTS:
            return _failed("unsupported_remote_host", host=host, credential=GIT_CREDENTIAL_SETTING), parts
    else:
        return _failed("unsupported_remote_url", remote=remote_name, scheme=str(parts.get("scheme"))), parts
    if not transport_allowed(host, push_egress_allowlist()):
        return _failed("fetch_egress_denied", host=host), parts
    return None, parts


def _fetch_url(root: Path, remote: str) -> str:
    proc = _git(root, ["remote", "get-url", remote], timeout=10)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def proposed_fetch_snapshot(
    repo_root: str | Path, remote: str | None = None, *, credential_method: str | None = None
) -> dict[str, Any]:
    """Where a fetch would go and with what — computed without touching the network."""
    from raiker.runtime.git_credential import repository_key

    root, refusal = _repository(repo_root)
    if refusal is not None:
        return refusal
    remotes = _remote_names(root)
    if not remotes:
        return _failed("no_remote_configured")
    branch = current_branch(root)
    remote_name = (
        (remote or "").strip()
        or (_upstream_remote(root, branch) if branch else "")
        or ("origin" if "origin" in remotes else remotes[0])
    )
    if remote_name not in remotes:
        return _failed("unknown_remote", remote=remote_name, remotes=remotes)
    url = _fetch_url(root, remote_name)
    refused, parts = _transport_refusal(url, remote_name, credential_method)
    if refused is not None:
        return refused
    return {
        "status": "success",
        "remote": remote_name,
        "remote_url": url,
        "transport": parts["transport"],
        "host": parts["host"],
        "repository_key": repository_key(url),
    }


def _transfer_environment(root: Path, credential: str | None, ssh_command: str | None) -> dict[str, str]:
    from raiker.runtime.command_policy import sandbox_environment

    return sandbox_environment(
        workspace_root=root,
        extra={
            _PUSH_TOKEN_VAR: _push_credential(credential),
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "",
            "SSH_ASKPASS": "",
            **({"GIT_SSH_COMMAND": ssh_command} if ssh_command else {}),
        },
    )


def _transfer_failure(proc: subprocess.CompletedProcess[str], output: str, **detail: Any) -> dict[str, Any]:
    lowered = output.lower()
    if "authentication failed" in lowered or "could not read username" in lowered or "permission denied" in lowered:
        return _failed("fetch_authentication_required", **detail)
    if "not found" in lowered or "does not exist" in lowered:
        return _failed("fetch_repository_not_found", **detail)
    if "host key verification failed" in lowered:
        return _failed("ssh_host_key_mismatch", **detail)
    return _failed("git_command_failed", output=output, **detail)


def fetch_remote(
    repo_root: str | Path,
    remote: str | None = None,
    *,
    credential: str | None = None,
    ssh_command: str | None = None,
) -> dict[str, Any]:
    """Fetch *remote* into its remote-tracking refs. Nothing is merged or checked out."""
    snapshot = proposed_fetch_snapshot(
        repo_root, remote, credential_method="ssh" if ssh_command else None
    )
    if snapshot["status"] != "success":
        return snapshot
    root = resolve_workspace_path(repo_root, ".")
    args = [
        "git", "-C", str(root), *_NO_HOOKS, *_NO_FSMONITOR, *_SAFE_TRANSFER,
        *_credential_args(), "fetch", "--no-recurse-submodules", "--no-write-fetch-head",
        str(snapshot["remote"]),
    ]
    try:
        proc = subprocess.run(
            args, check=False, capture_output=True, text=True, timeout=_FETCH_TIMEOUT,
            env=_transfer_environment(root, credential, ssh_command),
        )
    except subprocess.TimeoutExpired:
        return _failed("fetch_timed_out", remote=snapshot["remote"])
    output = _redact_token(_git_output(proc), credential)
    if proc.returncode != 0:
        return _transfer_failure(proc, output, remote=snapshot["remote"])
    updated = [line.strip() for line in output.splitlines() if "->" in line]
    return {**snapshot, "updated_refs": updated[:50], "output": output}


def proposed_clone_snapshot(
    workspace_root: str | Path,
    repository: str,
    path: str | None = None,
    *,
    credential_method: str | None = None,
) -> dict[str, Any]:
    """What cloning ``owner/name`` would create, and where — without touching the network."""
    from raiker.github.hosts import transport_allowed

    match = _GITHUB_REPOSITORY.match((repository or "").strip())
    if match is None or match.group("name") in (".", ".."):
        return _failed("invalid_repository", repository=repository)
    owner, name = match.group("owner"), match.group("name")
    if name.endswith(".git"):
        name = name[: -len(".git")]
    target = (path or name).strip()
    try:
        destination = resolve_workspace_path(workspace_root, target)
    except Exception:  # noqa: BLE001 — every refusal from the containment check is one named reason
        return _failed("clone_destination_outside_workspace", path=target)
    if destination.exists():
        return _failed("clone_destination_exists", path=target)
    if credential_method == "ssh":
        url, host, transport = f"git@github.com:{owner}/{name}.git", "github.com", "ssh"
    else:
        url, host, transport = f"https://github.com/{owner}/{name}.git", "github.com", "https"
    if not transport_allowed(host, push_egress_allowlist()):
        return _failed("fetch_egress_denied", host=host)
    return {
        "status": "success",
        "repository": f"{owner}/{name}",
        "repository_key": f"github.com/{owner.lower()}/{name.lower()}",
        "remote_url": url,
        "transport": transport,
        "host": host,
        "destination": str(destination),
        "path": target,
    }


def clone_repository(
    workspace_root: str | Path,
    repository: str,
    path: str | None = None,
    *,
    credential: str | None = None,
    ssh_command: str | None = None,
) -> dict[str, Any]:
    """Clone a GitHub repository into the workspace. No submodule is followed, no hook runs."""
    snapshot = proposed_clone_snapshot(
        workspace_root, repository, path, credential_method="ssh" if ssh_command else None
    )
    if snapshot["status"] != "success":
        return snapshot
    destination = Path(str(snapshot["destination"]))
    destination.parent.mkdir(parents=True, exist_ok=True)
    args = [
        "git", *_NO_HOOKS, *_NO_FSMONITOR, *_SAFE_TRANSFER, *_credential_args(),
        "clone", "--no-recurse-submodules", "--origin", "origin", "--",
        str(snapshot["remote_url"]), str(destination),
    ]
    try:
        proc = subprocess.run(
            args, check=False, capture_output=True, text=True, timeout=_FETCH_TIMEOUT,
            env=_transfer_environment(destination.parent, credential, ssh_command),
            cwd=str(destination.parent),
        )
    except subprocess.TimeoutExpired:
        return _failed("fetch_timed_out", repository=snapshot["repository"])
    output = _redact_token(_git_output(proc), credential)
    if proc.returncode != 0:
        return _transfer_failure(proc, output, repository=snapshot["repository"])
    return {**snapshot, "head": _head_commit(destination), "output": output}
