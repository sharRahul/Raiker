"""Containment as a set of roots rather than one.

The property that matters most here is the boring one: an authority with no
grants must behave exactly as the bare workspace check it replaces. Everything
else in this feature is additive on top of that, and if it is not true then
eleven existing call sites changed meaning without anyone deciding to.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.tools.filesystem import FilesystemSafetyError
from raiker.tools.path_authority import (
    WORKSPACE_ROOT_ID,
    AuthorityRoot,
    PathAuthority,
)


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    return workspace


def test_no_grants_matches_current_confinement(tmp_path: Path) -> None:
    authority = PathAuthority(_workspace(tmp_path))

    resolved = authority.resolve_read("notes/a.md")

    assert resolved.root_id == WORKSPACE_ROOT_ID
    assert resolved.relative == "notes/a.md"
    assert resolved.display == "notes/a.md"
    with pytest.raises(FilesystemSafetyError, match="outside_workspace"):
        authority.resolve_read("../escape.md")


def test_the_workspace_root_itself_is_never_writable(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)

    with pytest.raises(FilesystemSafetyError, match="protected_workspace_path"):
        PathAuthority(workspace).resolve_write(workspace)


def test_write_into_a_writable_attached_root(tmp_path: Path) -> None:
    external = tmp_path / "external"
    external.mkdir()
    authority = PathAuthority(
        _workspace(tmp_path),
        roots=(AuthorityRoot("granted-abc", external, writable=True, label="repo"),),
    )

    resolved = authority.resolve_write(external / "src/main.py")

    assert resolved.root_id == "granted-abc"
    assert resolved.relative == "src/main.py"
    assert resolved.display == "repo/src/main.py"


def test_write_into_a_read_only_attached_root_fails_closed(tmp_path: Path) -> None:
    external = tmp_path / "external"
    external.mkdir()
    authority = PathAuthority(
        _workspace(tmp_path),
        roots=(AuthorityRoot("granted-abc", external, writable=False, label="repo"),),
    )

    with pytest.raises(FilesystemSafetyError, match="root_not_writable"):
        authority.resolve_write(external / "src/main.py")
    # Reading it is still allowed: the Knowledge Map's grants work this way.
    assert authority.resolve_read(external / "src/main.py").root_id == "granted-abc"


@pytest.mark.parametrize("protected", [".git", ".raiker"])
def test_protected_directories_are_refused_inside_every_root(
    tmp_path: Path, protected: str
) -> None:
    external = tmp_path / "external"
    (external / protected).mkdir(parents=True)
    authority = PathAuthority(
        _workspace(tmp_path),
        roots=(AuthorityRoot("granted-abc", external, writable=True, label="repo"),),
    )

    with pytest.raises(FilesystemSafetyError, match="protected_workspace_path"):
        authority.resolve_write(external / protected / "hooks/pre-commit")


def test_a_path_outside_every_root_fails_closed(tmp_path: Path) -> None:
    authority = PathAuthority(_workspace(tmp_path))

    with pytest.raises(FilesystemSafetyError, match="outside_workspace"):
        authority.resolve_read(tmp_path / "elsewhere/a.md")


def test_the_most_specific_root_wins(tmp_path: Path) -> None:
    outer = tmp_path / "outer"
    inner = outer / "inner"
    inner.mkdir(parents=True)
    authority = PathAuthority(
        _workspace(tmp_path),
        roots=(
            AuthorityRoot("granted-outer", outer, writable=True, label="outer"),
            AuthorityRoot("granted-inner", inner, writable=True, label="inner"),
        ),
    )

    # Nested roots must name a file once, and by its closest root, or the same
    # file would carry two identities depending on iteration order.
    assert authority.resolve_read(inner / "a.md").root_id == "granted-inner"
    assert authority.resolve_read(outer / "b.md").root_id == "granted-outer"


def test_a_relative_path_is_still_workspace_relative(tmp_path: Path) -> None:
    external = tmp_path / "external"
    external.mkdir()
    workspace = _workspace(tmp_path)
    authority = PathAuthority(
        workspace, roots=(AuthorityRoot("granted-abc", external, writable=True, label="repo"),)
    )

    # Attaching a root must not change what a bare relative path means.
    assert authority.resolve_read("a.md").path == (workspace / "a.md").resolve()
