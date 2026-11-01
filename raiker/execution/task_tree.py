"""A session's task tree: the disposable copy its file tools and commands share.

Commands already ran in a per-session copy (:mod:`raiker.execution.workspaces`).
File tools wrote the real project. The two then disagreed: a test run did not
see the edit just made, and a formatter's output was invisible to the next
read. A task tree puts both on one tree. Once a session has a copy covering a
path -- or, for a project turn, as soon as anything writes inside the project
-- every read and write of that path goes to the copy, and the project changes
only when the owner applies the reviewed change set.

Addresses do not change. A path is resolved, confined and named against the
*real* project exactly as before (so policy, approvals, checkpoints and the
names the model sees are unaffected); only the file actually opened moves into
the copy. A copy path handed back in (a resolved path from an earlier call) is
translated to its real twin first, so it is confined by the same rules.

The copy is writable by sandboxed commands, so it may hold links a command
planted. A file tool never follows one: every component between the copy root
and the target is checked, and a link or reparse point refuses the call
(``task_copy_link``). This is a path check, not a pinned handle; a command
racing the tool could still swap a component between the check and the open.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path
from typing import Any

from raiker.execution.workspaces import (
    TaskWorkspace,
    TaskWorkspaceRegistry,
    WorkspaceError,
    _path_is_link_like,
)
from raiker.tools.filesystem import FilesystemSafetyError
from raiker.tools.path_authority import PathAuthority, ResolvedPath


def _within(outer: Path, inner: Path) -> bool:
    return inner == outer or outer in inner.parents


class TaskTree:
    """Maps real project paths to this session's copy, creating it on write."""

    def __init__(
        self, registry: TaskWorkspaceRegistry, owner_principal_id: str, session_id: str
    ) -> None:
        self.registry = registry
        self.owner_principal_id = owner_principal_id
        self.session_id = session_id

    @classmethod
    def for_session(
        cls, registry: TaskWorkspaceRegistry, session_id: str | None
    ) -> TaskTree | None:
        """The tree of a session recorded by an earlier turn, if it has one."""
        if not session_id:
            return None
        owner = registry.session_owner(session_id)
        return None if owner is None else cls(registry, owner, session_id)

    def _copies(self) -> list[TaskWorkspace]:
        return [w for _, w in self.registry.session_copies(self.owner_principal_id, self.session_id)]

    def to_copy(self, real: Path, *, create: bool) -> Path:
        """Where *real* lives in this task's tree; *real* itself when outside it."""
        owner, session = self.owner_principal_id, self.session_id
        workspace = self.registry.covering(owner, session, real)
        if workspace is None and create:
            root = self.registry.bound_root(owner, session)
            if root is not None and _within(root.resolve(), real):
                try:
                    _, workspace = self.registry.acquire(owner, session, root)
                except WorkspaceError as exc:
                    raise FilesystemSafetyError(exc.reason_code) from None
        if workspace is None:
            return real
        relative = real.relative_to(workspace.source.resolve())
        mapped = workspace.root / relative
        _refuse_links(workspace.root, mapped)
        return mapped

    def to_real(self, path: Path) -> Path:
        """The real twin of a path inside one of this session's copies."""
        resolved = path.resolve(strict=False)
        for workspace in self._copies():
            root = workspace.root.resolve()
            if _within(root, resolved):
                return workspace.source.resolve() / resolved.relative_to(root)
        return path

    def copy_roots(self) -> list[tuple[Path, Path]]:
        """``(real source, copy root)`` for each live copy."""
        return [(w.source.resolve(), w.root) for w in self._copies()]


def _refuse_links(copy_root: Path, target: Path) -> None:
    current = target
    while current != copy_root and copy_root in current.parents:
        if _path_is_link_like(current):
            raise FilesystemSafetyError("task_copy_link")
        current = current.parent


class TaskTreeAuthority(PathAuthority):
    """A :class:`PathAuthority` whose files live in the session's task copy."""

    def __init__(self, base: PathAuthority, tree: TaskTree) -> None:
        super().__init__(base.workspace_root, base.roots[1:])
        self.base = base
        self.tree = tree

    def _resolve(self, requested: str | Path, *, for_write: bool) -> ResolvedPath:
        candidate = Path(requested)
        if candidate.is_absolute():
            candidate = self.tree.to_real(candidate)
        resolved = super()._resolve(candidate, for_write=for_write)
        return dataclasses.replace(
            resolved, path=self.tree.to_copy(resolved.path, create=for_write)
        )


def wrap_authority(authority: Any, tree: TaskTree | None, workspace_root: str | Path) -> Any:
    """*authority* reading and writing through *tree*; unchanged without one."""
    if tree is None or isinstance(authority, TaskTreeAuthority):
        return authority
    return TaskTreeAuthority(authority or PathAuthority(workspace_root), tree)


def authority_for_action(
    authority: Any, workspace_root: str | Path, session_id: str | None
) -> Any:
    """The authority an executor uses for an action of *session_id*.

    An approved write can execute long after its turn ended, with no turn
    authority at all; the session's recorded binding and copies still decide
    where the file lives, so an approval cannot write around the task tree.
    """
    if isinstance(authority, TaskTreeAuthority) or not session_id:
        return authority
    from raiker.execution.commands.backends.native import task_workspace_registry

    tree = TaskTree.for_session(task_workspace_registry(workspace_root), session_id)
    return wrap_authority(authority, tree, workspace_root)


def _copy_files(copy_root: Path, *, directories: bool = False) -> list[Path]:
    """Regular files (and folders, if asked) under *copy_root*, never through a link."""
    found: list[Path] = []
    pending = [copy_root]
    while pending:
        directory = pending.pop()
        try:
            children = list(directory.iterdir())
        except OSError:
            continue
        for child in children:
            if _path_is_link_like(child):
                continue
            if child.is_dir():
                pending.append(child)
                if directories:
                    found.append(child)
            elif child.is_file():
                found.append(child)
    return found


def overlay_files(authority: Any, base: Path, real_files: list[Path]) -> list[Path]:
    """*real_files* under *base* with every copied subtree read from its copy.

    *base* is the real folder searched. A copy whose source is inside it
    replaces that subtree; a copy containing *base* has already moved *base*
    itself, so the caller searched the copy and nothing changes.
    """
    if not isinstance(authority, TaskTreeAuthority):
        return real_files
    real_base = authority.tree.to_real(base).resolve()
    if real_base != base.resolve():
        # *base* is inside a copy: list it without following planted links.
        return _copy_files(base)
    files = list(real_files)
    for source, copy_root in authority.tree.copy_roots():
        if source == real_base or not _within(real_base, source):
            continue
        files = [path for path in files if not _within(source, path.resolve())]
        files.extend(_copy_files(copy_root))
    return files


def overlay_glob(
    authority: Any, workspace_root: Path, pattern: str, real_matches: dict[str, Path]
) -> dict[str, Path]:
    """*real_matches* (display name -> real path) with copied subtrees answered
    from their copies; a copied entry maps to its file in the copy."""
    if not isinstance(authority, TaskTreeAuthority):
        return real_matches
    matcher = glob_regex(pattern)
    matches = dict(real_matches)
    for source, copy_root in authority.tree.copy_roots():
        if not _within(workspace_root, source):
            continue
        matches = {
            name: path for name, path in matches.items() if not _within(source, path.resolve())
        }
        prefix = source.relative_to(workspace_root).as_posix()
        for path in _copy_files(copy_root, directories=True):
            relative = path.relative_to(copy_root).as_posix()
            display = relative if prefix == "." else f"{prefix}/{relative}"
            if matcher.fullmatch(display):
                matches[display + ("/" if path.is_dir() else "")] = path
    return matches


_GLOB_TOKEN = re.compile(r"\*\*/|\*\*|\*|\?|\[[^\]]*\]|[^*?\[]+")


def glob_regex(pattern: str) -> re.Pattern[str]:
    """A ``Path.glob`` pattern as an anchored regex over ``/``-joined paths."""
    parts: list[str] = []
    for piece in _GLOB_TOKEN.findall(pattern.replace("\\", "/")):
        if piece == "**/":
            parts.append("(?:[^/]+/)*")
        elif piece == "**":
            parts.append(".*")
        elif piece == "*":
            parts.append("[^/]*")
        elif piece == "?":
            parts.append("[^/]")
        elif piece.startswith("["):
            body = piece[1:-1]
            parts.append("[^" + re.escape(body[1:]) + "]" if body.startswith("!") else "[" + re.escape(body) + "]")
        else:
            parts.append(re.escape(piece))
    return re.compile("".join(parts) + "/?")
