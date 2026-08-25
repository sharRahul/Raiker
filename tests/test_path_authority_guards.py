"""The three guards that used to spell out "inside the workspace".

Their job here is to agree. Policy decides before execution and the executor
decides again at the moment of the write; if those two ever disagree about an
attached root, a turn is either refused after being allowed or allowed after
being refused. The checkpoint key is the third: it has to name a file outside
the workspace without losing the ability to restore it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from raiker.checkpoints.capture import CheckpointCaptureService
from raiker.contracts.ids import new_id, utc_now
from raiker.contracts.models import ToolAction, User
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.filesystem import (
    FilesystemSafetyError,
    resolve_workspace_path,
    resolve_writable_workspace_path,
)
from raiker.tools.path_authority import (
    AuthorityRoot,
    PathAuthority,
    decode_root_path,
    encode_root_path,
)

OWNER = "principal_owner"


@pytest.fixture()
def store(tmp_path: Path) -> SQLiteStore:
    store = SQLiteStore(tmp_path)
    now = utc_now()
    store.insert_user(User("user_owner", "Owner", None, True, now, now))
    store.insert_principal(OWNER, "human", "Owner", delegated_by_user_id="user_owner")
    return store


def _external(tmp_path: Path) -> Path:
    external = tmp_path / "external"
    external.mkdir(exist_ok=True)
    return external


def _authority(workspace: Path, external: Path, *, writable: bool = True) -> PathAuthority:
    return PathAuthority(
        workspace,
        roots=(AuthorityRoot("granted-abc", external, writable=writable, label="repo"),),
    )


def test_existing_callers_are_unchanged_without_an_authority(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("x", encoding="utf-8")

    assert resolve_workspace_path(tmp_path, "a.md") == (tmp_path / "a.md").resolve()
    with pytest.raises(FilesystemSafetyError, match="protected_workspace_path"):
        resolve_writable_workspace_path(tmp_path, ".raiker/secrets")
    with pytest.raises(FilesystemSafetyError, match="outside_workspace"):
        resolve_workspace_path(tmp_path, "../escape.md")


def test_policy_and_executor_agree_about_an_attached_root(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    external = _external(tmp_path)
    authority = _authority(workspace, external)
    engine = PolicyEngine(StaticPolicyConfig(workspace_root=workspace), authority=authority)
    action = ToolAction(
        new_id("act_"), "write_file", {"path": str(external / "src/main.py")}, "medium", False
    )

    inside, reasons = engine._path_arguments_inside_workspace(action)  # noqa: SLF001

    assert inside is True
    assert reasons == []
    assert resolve_writable_workspace_path(
        workspace, external / "src/main.py", authority=authority
    ) == (external / "src/main.py").resolve()


def test_policy_and_executor_agree_about_a_refusal(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    engine = PolicyEngine(StaticPolicyConfig(workspace_root=workspace))
    action = ToolAction(
        new_id("act_"), "write_file", {"path": str(tmp_path / "elsewhere.md")}, "medium", False
    )

    inside, _reasons = engine._path_arguments_inside_workspace(action)  # noqa: SLF001

    assert inside is False
    with pytest.raises(FilesystemSafetyError):
        resolve_writable_workspace_path(workspace, tmp_path / "elsewhere.md")


def test_checkpoint_key_names_the_root_for_an_attached_file(
    tmp_path: Path, store: SQLiteStore
) -> None:
    external = _external(tmp_path)
    (external / "a.md").write_text("before", encoding="utf-8")
    authority = _authority(store.paths.workspace_root, external)
    capture = CheckpointCaptureService(store, authority=authority)

    pre = capture.snapshot_path(str(external / "a.md"), "file_write_execution")

    assert pre is not None
    assert pre.workspace_path == "granted-abc:a.md"
    assert pre.data == b"before"


def test_checkpoint_key_stays_bare_for_a_workspace_file(store: SQLiteStore) -> None:
    (store.paths.workspace_root / "a.md").write_text("before", encoding="utf-8")

    pre = CheckpointCaptureService(store).snapshot_path("a.md", "file_write_execution")

    assert pre is not None
    # Unchanged on purpose: existing checkpoints are keyed this way and must
    # stay restorable without a data migration.
    assert pre.workspace_path == "a.md"


def test_a_stored_key_round_trips_back_to_its_file(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    external = _external(tmp_path)
    authority = _authority(workspace, external)

    attached = authority.resolve_read(external / "src/a.md")
    workspace_file = authority.resolve_read("notes/b.md")

    assert encode_root_path(attached) == "granted-abc:src/a.md"
    assert encode_root_path(workspace_file) == "notes/b.md"
    assert decode_root_path(authority, "granted-abc:src/a.md") == (external / "src/a.md").resolve()
    assert decode_root_path(authority, "notes/b.md") == (workspace / "notes/b.md").resolve()


def test_an_unknown_root_in_a_stored_key_decodes_to_nothing(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    authority = PathAuthority(workspace)

    # A checkpoint written while a folder was attached, read back after it was
    # revoked. Restoring it must decline rather than guess at a path.
    assert decode_root_path(authority, "granted-gone:src/a.md") is None
