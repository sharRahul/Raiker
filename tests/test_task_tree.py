"""The task tree: file tools and commands share one disposable copy.

An edit and the next command must see the same tree, and the project must
change only when the owner applies the reviewed copy.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from raiker.execution.commands.backends import native as native_backend
from raiker.execution.task_tree import TaskTree, TaskTreeAuthority, glob_regex
from raiker.execution.workspaces import TaskWorkspaceRegistry, WorkspaceError, diff_workspace
from raiker.runtime.executors.tier1_files import FileWriteExecutor
from raiker.tools.filesystem import (
    FilesystemSafetyError,
    glob_paths,
    grep_files,
    read_file,
    write_file_content,
)
from raiker.tools.path_authority import PathAuthority
from tests.factories import governed_action

OWNER = "owner_1"
SESSION = "ses_task"


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "ws"
    project = workspace / "proj"
    (project / "src").mkdir(parents=True)
    (project / "src" / "app.py").write_text("print('v1')\n", encoding="utf-8")
    (workspace / "notes.md").write_text("outside the project\n", encoding="utf-8")
    (workspace / ".raiker").mkdir()
    return workspace


def _tree(tmp_path: Path, workspace: Path, *, bind: bool = True) -> TaskTreeAuthority:
    registry = TaskWorkspaceRegistry(tmp_path / "copies", records=tmp_path / "records")
    if bind:
        registry.bind(OWNER, SESSION, workspace / "proj")
    return TaskTreeAuthority(PathAuthority(workspace), TaskTree(registry, OWNER, SESSION))


def test_a_write_in_the_project_lands_in_the_copy_and_reads_back(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    authority = _tree(tmp_path, workspace)

    result = write_file_content(workspace, "proj/src/app.py", "print('v2')\n", authority=authority)

    assert result["path"] == "proj/src/app.py"  # the name the model sees is unchanged
    assert (workspace / "proj" / "src" / "app.py").read_text(encoding="utf-8") == "print('v1')\n"
    read = read_file(workspace, "proj/src/app.py", authority=authority)
    assert read["text"].splitlines() == ["print('v2')"]
    [(_, copy)] = authority.tree.registry.session_copies(OWNER, SESSION)
    assert copy.source == (workspace / "proj").resolve()
    assert diff_workspace(copy).modified == ("src/app.py",)


def test_paths_outside_the_task_root_are_untouched(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    authority = _tree(tmp_path, workspace)

    write_file_content(workspace, "notes.md", "edited\n", authority=authority)

    assert (workspace / "notes.md").read_text(encoding="utf-8") == "edited\n"
    assert authority.tree.registry.session_copies(OWNER, SESSION) == []


def test_without_a_binding_reads_use_an_existing_copy_and_writes_follow_it(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    authority = _tree(tmp_path, workspace, bind=False)
    # No copy yet: the old behaviour, straight to the project.
    write_file_content(workspace, "proj/src/new.py", "x = 1\n", authority=authority)
    assert (workspace / "proj" / "src" / "new.py").exists()

    # A command takes a copy of `proj/src`; the next edit goes there.
    authority.tree.registry.acquire(OWNER, SESSION, workspace / "proj" / "src")
    write_file_content(workspace, "proj/src/new.py", "x = 2\n", authority=authority)
    assert (workspace / "proj" / "src" / "new.py").read_text(encoding="utf-8") == "x = 1\n"
    assert read_file(workspace, "proj/src/new.py", authority=authority)["text"].splitlines() == ["x = 2"]


def test_a_wider_copy_than_an_existing_one_is_refused(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    registry = TaskWorkspaceRegistry(tmp_path / "copies", records=tmp_path / "records")
    _, inner = registry.acquire(OWNER, SESSION, workspace / "proj" / "src")
    # A narrower request reuses the copy that covers it.
    assert registry.acquire(OWNER, SESSION, workspace / "proj" / "src")[1].root == inner.root
    with pytest.raises(WorkspaceError) as raised:
        registry.acquire(OWNER, SESSION, workspace / "proj")
    assert raised.value.reason_code == "task_copy_scope_conflict"


def test_a_binding_does_not_move_once_a_copy_exists(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    registry = TaskWorkspaceRegistry(tmp_path / "copies", records=tmp_path / "records")
    registry.bind(OWNER, SESSION, workspace / "proj")
    registry.acquire(OWNER, SESSION, workspace / "proj")
    registry.bind(OWNER, SESSION, workspace)
    assert registry.bound_root(OWNER, SESSION) == (workspace / "proj").resolve()
    assert registry.bound_root("someone_else", SESSION) is None


def _link_directory(link: Path, target: Path) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            check=True,
            capture_output=True,
        )
    else:
        link.symlink_to(target, target_is_directory=True)


def test_a_link_planted_in_the_copy_is_never_followed(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    secret = tmp_path / "secret"
    secret.mkdir()
    (secret / "key.txt").write_text("host secret\n", encoding="utf-8")
    authority = _tree(tmp_path, workspace)
    _, copy = authority.tree.registry.acquire(OWNER, SESSION, workspace / "proj")
    # What a sandboxed command could do inside its copy.
    _link_directory(copy.root / "src" / "out", secret)
    (workspace / "proj" / "src" / "out").mkdir()

    with pytest.raises(FilesystemSafetyError) as raised:
        read_file(workspace, "proj/src/out/key.txt", authority=authority)
    assert str(raised.value) == "task_copy_link"
    with pytest.raises(FilesystemSafetyError):
        write_file_content(workspace, "proj/src/out/key.txt", "pwned", authority=authority)
    assert (secret / "key.txt").read_text(encoding="utf-8") == "host secret\n"
    found = grep_files(workspace, "host secret", "proj", authority=authority)
    assert found["matches"] == []


def test_search_sees_the_copy_rather_than_the_stale_project(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    authority = _tree(tmp_path, workspace)
    write_file_content(workspace, "proj/src/added.py", "MARKER = 2\n", authority=authority)
    write_file_content(workspace, "proj/src/app.py", "print('v2')\n", authority=authority)

    hits = grep_files(workspace, "MARKER", ".", authority=authority)["matches"]
    assert [Path(hit["path"]).as_posix() for hit in hits] == ["proj/src/added.py"]
    assert grep_files(workspace, "v1", ".", authority=authority)["matches"] == []
    inside = grep_files(workspace, "v2", "proj/src", authority=authority)["matches"]
    assert [Path(hit["path"]).as_posix() for hit in inside] == ["proj/src/app.py"]

    listed = glob_paths(workspace, "proj/**/*.py", authority=authority)["matches"]
    assert sorted(Path(item).as_posix() for item in listed) == [
        "proj/src/added.py",
        "proj/src/app.py",
    ]


@pytest.mark.parametrize(
    ("pattern", "path", "matches"),
    (
        ("**/*.py", "a/b/c.py", True),
        ("**/*.py", "c.py", True),
        ("src/*.py", "src/a/b.py", False),
        ("src/?.py", "src/a.py", True),
        ("*.[ch]", "x.c", True),
        ("*.[!ch]", "x.c", False),
    ),
)
def test_glob_regex_follows_path_glob(pattern: str, path: str, matches: bool) -> None:
    assert bool(glob_regex(pattern).fullmatch(path)) is matches


def test_an_approved_write_after_the_turn_still_lands_in_the_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path)
    registry = TaskWorkspaceRegistry(tmp_path / "copies", records=tmp_path / "records")
    registry.bind(OWNER, SESSION, workspace / "proj")
    monkeypatch.setattr(native_backend, "task_workspace_registry", lambda *_a, **_k: registry)

    action = governed_action(
        "write_file",
        principal_id="agent_1",
        risk_level="medium",
        arguments={"path": "proj/src/app.py", "text": "print('approved')\n"},
        session_id="ses_api",
        origin_session_id=SESSION,
    )
    result = FileWriteExecutor(workspace).execute(action, principal=None)  # type: ignore[arg-type]

    assert result.ok, result.reason_code
    assert result.artifacts["path"] == "proj/src/app.py"
    assert (workspace / "proj" / "src" / "app.py").read_text(encoding="utf-8") == "print('v1')\n"
    [(_, copy)] = registry.session_copies(OWNER, SESSION)
    assert (copy.root / "src" / "app.py").read_text(encoding="utf-8") == "print('approved')\n"


def test_a_command_in_a_subfolder_runs_in_the_projects_copy(tmp_path: Path) -> None:
    from tests.test_command_backends import _installed_runner, _probe_reply, request

    workspace = _workspace(tmp_path)
    registry = TaskWorkspaceRegistry(tmp_path / "copies", records=tmp_path / "records")
    authority = TaskTreeAuthority(PathAuthority(workspace), TaskTree(registry, OWNER, SESSION))
    asked = replace(request(workspace, cwd="proj/src"), owner_principal_id=OWNER, session_id=SESSION)
    registry.bind(OWNER, SESSION, workspace / "proj")
    write_file_content(workspace, "proj/src/app.py", "print('edited')\n", authority=authority)

    directory = _installed_runner(tmp_path)
    driver = native_backend.NativeSandboxDriver(
        workspace, helper_root=directory, run_probe=_probe_reply()
    )
    launched: list[Path] = []
    policies: list[dict[str, Any]] = []

    def fake_runner(req: Any, argv: list[str], cwd: Path, *_a: Any, **_k: Any) -> Any:
        launched.append(Path(cwd))
        policies.append(json.loads(Path(argv[2]).read_text(encoding="utf-8")))
        return object()

    backend = native_backend.NativeSandboxBackend(
        driver=driver, proof=driver.probe(), workspaces=registry, runner=fake_runner
    )
    backend.start(asked)

    [(_, copy)] = registry.session_copies(OWNER, SESSION)
    assert copy.source == (workspace / "proj").resolve()
    assert launched == [copy.root]
    assert Path(policies[0]["cwd"]) == (copy.root / "src").resolve()
    # The command's tree holds the edit made before it.
    assert (copy.root / "src" / "app.py").read_text(encoding="utf-8") == "print('edited')\n"


def test_git_status_and_diff_show_the_copys_edits_git_cannot_see(tmp_path: Path) -> None:
    from raiker.execution.task_tree import pending_copy_changes

    workspace = _workspace(tmp_path)
    authority = _tree(tmp_path, workspace)
    assert pending_copy_changes(authority) == []
    write_file_content(workspace, "proj/src/app.py", "print('v2')\n", authority=authority)
    write_file_content(workspace, "proj/src/new.py", "x = 1\n", authority=authority)

    [status] = pending_copy_changes(authority)
    assert status["folder"] == "proj"
    assert (status["created"], status["modified"]) == (["proj/src/new.py"], ["proj/src/app.py"])
    assert "diff" not in status

    [narrowed] = pending_copy_changes(authority, paths=["proj/src/app.py"], with_diffs=True)
    assert narrowed["created"] == [] and narrowed["modified"] == ["proj/src/app.py"]
    assert "-print('v1')" in narrowed["diff"] and "+print('v2')" in narrowed["diff"]
    assert pending_copy_changes(authority, paths=["notes.md"]) == []
    # A plain authority has no copy, and Git's answer stands alone.
    assert pending_copy_changes(PathAuthority(workspace)) == []


def test_an_edit_approval_previews_against_the_copy(tmp_path: Path) -> None:
    """The owner approves an edit against the file it lands in: the copy's."""
    from raiker.cli.principal_resolver import bootstrap_owner
    from raiker.contracts.ids import new_id
    from raiker.contracts.models import ToolAction
    from raiker.policy.config import StaticPolicyConfig
    from raiker.policy.engine import PolicyEngine
    from raiker.storage.sqlite import SQLiteStore
    from tests.machine_identity_helpers import IdentityBoundTestBroker as ToolBroker

    workspace = tmp_path / "ws"
    (workspace / "proj" / "src").mkdir(parents=True)
    (workspace / "proj" / "src" / "app.py").write_text("print('v1')\n", encoding="utf-8")
    bootstrap_owner("owner", "Owner", workspace_root=workspace)
    authority = _tree(tmp_path, workspace)
    write_file_content(workspace, "proj/src/app.py", "print('v2')\n", authority=authority)
    broker = ToolBroker(
        workspace_root=workspace,
        policy_engine=PolicyEngine(StaticPolicyConfig(workspace)),
        store=SQLiteStore(workspace),
        principal_id="principal_owner",
    )
    broker.path_authority = authority

    preview = broker._approval_preview(
        ToolAction(
            new_id("act_"),
            "edit_file",
            {"path": "proj/src/app.py", "old_text": "v2", "new_text": "v3"},
            "medium",
            True,
        )
    )

    assert preview is not None
    assert preview["before_snapshot"] == "print('v2')\n"
    assert preview["proposed_text"] == "print('v3')\n"
    assert (workspace / "proj" / "src" / "app.py").read_text(encoding="utf-8") == "print('v1')\n"
