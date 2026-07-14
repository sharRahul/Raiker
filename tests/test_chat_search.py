from pathlib import Path

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.dashboard import DashboardService

OWNER = "principal_rahul"


def service(tmp_path: Path) -> tuple[DashboardService, Path]:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    bootstrap_owner("rahul", "Rahul", workspace_root=workspace)
    return DashboardService(workspace), workspace


def test_search_matches_turn_text_and_returns_title(tmp_path: Path) -> None:
    dashboard, workspace = service(tmp_path)
    dashboard.store.create_session("sess_alpha", str(workspace), title="Release notes")
    dashboard.store.insert_turn("sess_alpha", "turn_alpha", "Find the migration plan")

    assert [item.title for item in dashboard.search_sessions("migration", None)] == ["Release notes"]
