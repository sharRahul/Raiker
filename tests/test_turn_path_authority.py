"""The turn's write boundary follows the project it is running in.

Everything before this is inert in the product: the resolver knows an attached
project has an extra root, and the executor that actually writes does not. This
suite is the wire between them, plus the reporting bug the wire exposes —
`relative_to(workspace_root)` raises rather than refuses once a resolved path
can legitimately be outside the workspace, so a *successful* write would crash
while naming itself.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import new_id
from raiker.control.dashboard import DashboardService
from raiker.control.project_roots import authority_for_project
from raiker.runtime.authority.models import Principal, RiskLevelValue
from raiker.runtime.authority.router import GovernedAction
from raiker.runtime.executors import build_default_executor_registry
from raiker.runtime.executors.tier1_files import FileWriteExecutor

OWNER = "principal_owner"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


class _Attached:
    def __init__(self, service: DashboardService, project_id: str, root: Path) -> None:
        self.service = service
        self.project_id = project_id
        self.root = root

    @property
    def row(self) -> dict[str, Any]:
        row = self.service.store.load_project(self.project_id)
        assert row is not None
        return row

    def authority(self) -> Any:
        return authority_for_project(
            self.row,
            self.service.store.list_brain_source_grants(OWNER),
            self.service.workspace_root,
        )


def _attach(workspace: Path, external: Path, *, writable: bool = True) -> _Attached:
    external.mkdir(parents=True, exist_ok=True)
    service = DashboardService(workspace)
    created = service.create_project("Alpha", OWNER)
    attached = service.attach_project_folder(
        created.data["project_id"], str(external), OWNER, writable=writable
    )
    assert attached.ok, attached.reason_code
    return _Attached(service, created.data["project_id"], external.resolve())


def _principal(service: DashboardService) -> Principal:
    raw = service.store.get_principal(OWNER)
    assert raw is not None
    return Principal(**raw)


def _write(path: str, text: str = "x") -> GovernedAction:
    return GovernedAction(
        action_id=new_id("act_"),
        principal_id=OWNER,
        action_type="write_file",
        tool_or_service_name="write_file",
        arguments={"path": path, "text": text},
        risk_level=RiskLevelValue.LOW,
    )


class TestWritingIntoAnAttachedRoot:
    def test_a_build_turn_can_write_into_its_attached_project(
        self, tmp_path: Path, workspace: Path
    ) -> None:
        attached = _attach(workspace, tmp_path / "repo")
        executor = FileWriteExecutor(workspace, authority=attached.authority())

        result = executor.execute(
            _write(str(attached.root / "src/new.py"), "print('x')"),
            _principal(attached.service),
        )

        assert result.ok, result.reason_code
        assert (attached.root / "src/new.py").read_text(encoding="utf-8") == "print('x')"

    def test_the_result_names_the_file_without_raising(
        self, tmp_path: Path, workspace: Path
    ) -> None:
        attached = _attach(workspace, tmp_path / "repo")
        executor = FileWriteExecutor(workspace, authority=attached.authority())

        result = executor.execute(
            _write(str(attached.root / "a.md")), _principal(attached.service)
        )

        assert result.ok, result.reason_code
        assert str(result.artifacts["path"]).endswith("a.md")

    def test_editing_a_file_in_an_attached_root_names_it_too(
        self, tmp_path: Path, workspace: Path
    ) -> None:
        attached = _attach(workspace, tmp_path / "repo")
        target = attached.root / "a.md"
        target.write_text("alpha\n", encoding="utf-8")
        executor = FileWriteExecutor(workspace, authority=attached.authority())
        action = GovernedAction(
            action_id=new_id("act_"),
            principal_id=OWNER,
            action_type="edit_file",
            tool_or_service_name="edit_file",
            arguments={"path": str(target), "old_text": "alpha", "new_text": "beta"},
            risk_level=RiskLevelValue.LOW,
        )

        result = executor.execute(action, _principal(attached.service))

        assert result.ok, result.reason_code
        assert target.read_text(encoding="utf-8") == "beta\n"
        assert str(result.artifacts["path"]).endswith("a.md")

    def test_a_read_only_attachment_still_refuses_the_write(
        self, tmp_path: Path, workspace: Path
    ) -> None:
        attached = _attach(workspace, tmp_path / "repo", writable=False)
        executor = FileWriteExecutor(workspace, authority=attached.authority())

        result = executor.execute(
            _write(str(attached.root / "a.md")), _principal(attached.service)
        )

        assert result.ok is False
        assert "root_not_writable" in (result.reason_code or "")

    def test_the_attached_roots_protected_directories_are_still_protected(
        self, tmp_path: Path, workspace: Path
    ) -> None:
        attached = _attach(workspace, tmp_path / "repo")
        executor = FileWriteExecutor(workspace, authority=attached.authority())

        result = executor.execute(
            _write(str(attached.root / ".git/config")), _principal(attached.service)
        )

        assert result.ok is False
        assert "protected_workspace_path" in (result.reason_code or "")


class TestWithoutAnAttachedProject:
    def test_a_turn_without_an_attached_project_is_unchanged(
        self, tmp_path: Path, workspace: Path
    ) -> None:
        service = DashboardService(workspace)
        executor = FileWriteExecutor(workspace)

        result = executor.execute(
            _write(str(tmp_path / "escape.md")), _principal(service)
        )

        assert result.ok is False
        assert "outside_workspace" in (result.reason_code or "")

    def test_a_workspace_write_still_reports_a_relative_path(
        self, tmp_path: Path, workspace: Path
    ) -> None:
        service = DashboardService(workspace)
        executor = FileWriteExecutor(workspace)

        result = executor.execute(_write("notes/a.md"), _principal(service))

        assert result.ok, result.reason_code
        assert Path(str(result.artifacts["path"])).as_posix() == "notes/a.md"


class TestRegistryWiring:
    def test_the_registry_hands_its_authority_to_the_file_executors(
        self, tmp_path: Path, workspace: Path
    ) -> None:
        attached = _attach(workspace, tmp_path / "repo")
        registry = build_default_executor_registry(
            workspace, attached.service.store, authority=attached.authority()
        )

        executor = registry.get("file_write_execution")
        assert executor is not None
        result = executor.execute(
            _write(str(attached.root / "b.md")), _principal(attached.service)
        )

        assert result.ok, result.reason_code
        assert (attached.root / "b.md").is_file()

    def test_a_registry_without_an_authority_is_workspace_only(
        self, tmp_path: Path, workspace: Path
    ) -> None:
        service = DashboardService(workspace)
        registry = build_default_executor_registry(workspace, service.store)

        executor = registry.get("file_write_execution")
        assert executor is not None
        result = executor.execute(_write(str(tmp_path / "escape.md")), _principal(service))

        assert result.ok is False
        assert "outside_workspace" in (result.reason_code or "")
