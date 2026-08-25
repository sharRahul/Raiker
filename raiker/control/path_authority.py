"""Which roots a scope may touch, and what a path inside one is called.

Confinement used to be a single question — "is this inside the workspace?" —
asked in three places that each spelled it out. A project can now have a root
that is a folder the owner already had, so the question becomes "is this inside
exactly one of the roots this scope was granted, and may that root be written?"

Constructed with no extra roots this is workspace-only and answers exactly as
the bare check it replaces. That is deliberate and load-bearing: every existing
call site adopts it without changing meaning, and attached roots are additive
rather than a rewrite of the boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from raiker.tools.filesystem import PROTECTED_WORKSPACE_DIRS, FilesystemSafetyError

#: The root id every workspace path carries. Kept as a plain word rather than a
#: grant-style id so a stored checkpoint key for a workspace file stays exactly
#: the bare relative path it has always been.
WORKSPACE_ROOT_ID = "workspace"


@dataclass(frozen=True)
class AuthorityRoot:
    """One place a scope may reach, and whether it may write there."""

    root_id: str
    path: Path
    writable: bool
    label: str


@dataclass(frozen=True)
class ResolvedPath:
    """A path that landed inside exactly one root, and what to call it."""

    path: Path
    root_id: str
    relative: str
    display: str
    writable: bool


class PathAuthority:
    """The one answer to "may this scope touch this path, and what is it called"."""

    def __init__(
        self, workspace_root: str | Path, roots: tuple[AuthorityRoot, ...] = ()
    ) -> None:
        workspace = Path(workspace_root).resolve()
        self._roots: tuple[AuthorityRoot, ...] = (
            AuthorityRoot(WORKSPACE_ROOT_ID, workspace, writable=True, label="workspace"),
            *(
                AuthorityRoot(root.root_id, root.path.resolve(), root.writable, root.label)
                for root in roots
            ),
        )

    @property
    def workspace_root(self) -> Path:
        return self._roots[0].path

    def resolve_read(self, requested: str | Path) -> ResolvedPath:
        return self._resolve(requested, for_write=False)

    def resolve_write(self, requested: str | Path) -> ResolvedPath:
        return self._resolve(requested, for_write=True)

    def _resolve(self, requested: str | Path, *, for_write: bool) -> ResolvedPath:
        candidate = Path(requested)
        workspace = self.workspace_root
        resolved = (
            candidate.resolve(strict=False)
            if candidate.is_absolute()
            else (workspace / candidate).resolve(strict=False)
        )
        matched = self._match(resolved)
        if matched is None:
            # The reason code is unchanged from the single-root era on purpose:
            # callers and tests already read "outside_workspace" as "refused",
            # and inventing a second word for the same refusal would only make
            # existing handling miss it.
            raise FilesystemSafetyError("outside_workspace")
        relative_parts = resolved.relative_to(matched.path).parts
        if for_write:
            if not relative_parts:
                raise FilesystemSafetyError("protected_workspace_path")
            if not matched.writable:
                raise FilesystemSafetyError("root_not_writable")
        # Protected directories are protected in *every* root. Attaching a
        # repository protects its `.git` for precisely the reason the
        # workspace's own is protected: those are the files that record and
        # constrain the agent, not ordinary content it may edit.
        if relative_parts and relative_parts[0] in PROTECTED_WORKSPACE_DIRS:
            raise FilesystemSafetyError("protected_workspace_path")
        relative = "/".join(relative_parts)
        display = (
            relative
            if matched.root_id == WORKSPACE_ROOT_ID
            else f"{matched.label}/{relative}" if relative else matched.label
        )
        return ResolvedPath(resolved, matched.root_id, relative, display, matched.writable)

    def _match(self, resolved: Path) -> AuthorityRoot | None:
        """The closest root containing *resolved*, or nothing.

        Longest match wins so a root nested inside another names the file once,
        by its nearest root, rather than by whichever happened to be checked
        first.
        """
        matched: AuthorityRoot | None = None
        for root in self._roots:
            try:
                resolved.relative_to(root.path)
            except ValueError:
                continue
            if matched is None or len(root.path.parts) > len(matched.path.parts):
                matched = root
        return matched
