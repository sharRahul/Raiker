"""Owner review of a session's disposable copy: list, promote exactly, discard."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.execution.commands.backends.native import task_workspace_registry

OWNER = "principal_owner"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    (ws / "app").mkdir()
    (ws / "app" / "main.py").write_text("print('v1')\n", encoding="utf-8")
    (ws / "app" / "old.txt").write_text("old\n", encoding="utf-8")
    return ws


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


@pytest.fixture
def headers(client: TestClient) -> dict[str, str]:
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _task_copy(workspace: Path, owner: str = OWNER) -> tuple[str, Path]:
    """What a sandboxed command leaves behind in its session's copy."""
    key, copy = task_workspace_registry(workspace).acquire(
        owner, "sess_build", workspace / "app"
    )
    (copy.root / "main.py").write_text("print('v2')\n", encoding="utf-8")
    (copy.root / "old.txt").unlink()
    (copy.root / "new.py").write_text("x = 1\n", encoding="utf-8")
    return key, copy.root


def _review(client: TestClient, headers: dict[str, str]) -> str:
    [view] = client.get("/api/command-workspaces", headers=headers).json()["workspaces"]
    return str(view["review_revision"])


@pytest.mark.parametrize("side", ["copy", "project"])
def test_same_paths_with_changed_bytes_require_a_new_review(
    client: TestClient, headers: dict[str, str], workspace: Path, side: str,
) -> None:
    key, root = _task_copy(workspace)
    revision = _review(client, headers)
    target = root if side == "copy" else workspace / "app"
    (target / "main.py").write_text("different unseen bytes\n", encoding="utf-8")
    refused = client.post(
        f"/api/command-workspaces/{key}/promote",
        json={"created": ["new.py"], "modified": ["main.py"], "deleted": ["old.txt"],
              "review_revision": revision, "overwrite": ["main.py"] if side == "project" else []},
        headers=headers,
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"]["reason_code"] == "workspace_review_stale"
    assert not (workspace / "app/new.py").exists()
    assert root.exists()


def test_apply_without_a_revision_is_refused(
    client: TestClient, headers: dict[str, str], workspace: Path,
) -> None:
    key, _ = _task_copy(workspace)
    refused = client.post(
        f"/api/command-workspaces/{key}/promote",
        json={"created": ["new.py"], "modified": ["main.py"], "deleted": ["old.txt"]},
        headers=headers,
    )
    assert refused.status_code == 422
    assert (workspace / "app/main.py").read_text() == "print('v1')\n"


def test_review_revision_cannot_be_reused_for_another_copy(
    client: TestClient, headers: dict[str, str], workspace: Path,
) -> None:
    _task_copy(workspace)
    revision = _review(client, headers)
    key, second = task_workspace_registry(workspace).acquire(OWNER, "other_session", workspace / "app")
    (second.root / "main.py").write_text("print('v2')\n")
    (second.root / "old.txt").unlink()
    (second.root / "new.py").write_text("x = 1\n")
    refused = client.post(
        f"/api/command-workspaces/{key}/promote",
        json={"created": ["new.py"], "modified": ["main.py"], "deleted": ["old.txt"],
              "review_revision": revision}, headers=headers,
    )
    assert refused.status_code == 409
    assert refused.json()["detail"]["reason_code"] == "workspace_review_stale"
    assert (workspace / "app/main.py").read_text() == "print('v1')\n"


def test_opening_a_diff_from_an_old_revision_requires_refresh(
    client: TestClient, headers: dict[str, str], workspace: Path,
) -> None:
    key, root = _task_copy(workspace)
    revision = _review(client, headers)
    (root / "main.py").write_text("new unseen text\n")
    refused = client.get(f"/api/command-workspaces/{key}/diff",
                         params={"path": "main.py", "review_revision": revision}, headers=headers)
    assert refused.status_code == 409
    assert refused.json()["detail"]["reason_code"] == "workspace_review_stale"


def test_the_owner_sees_what_the_task_changed_before_anything_reaches_the_project(
    client: TestClient, headers: dict[str, str], workspace: Path
) -> None:
    key, _ = _task_copy(workspace)

    listed = client.get("/api/command-workspaces", headers=headers)

    assert listed.status_code == 200, listed.text
    [view] = listed.json()["workspaces"]
    assert view["workspace_id"] == key
    assert view["session_id"] == "sess_build"
    assert view["source"] == "app"
    assert (view["created"], view["modified"], view["deleted"]) == (
        ["new.py"], ["main.py"], ["old.txt"]
    )
    assert (workspace / "app" / "main.py").read_text(encoding="utf-8") == "print('v1')\n"


def test_promotion_applies_exactly_the_reviewed_change_set_and_audits_it(
    client: TestClient, headers: dict[str, str], workspace: Path
) -> None:
    key, root = _task_copy(workspace)

    promoted = client.post(
        f"/api/command-workspaces/{key}/promote",
        json={"created": ["new.py"], "modified": ["main.py"], "deleted": ["old.txt"],
              "review_revision": _review(client, headers)},
        headers=headers,
    )

    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["modified"] == ["main.py"]
    assert (workspace / "app" / "main.py").read_text(encoding="utf-8") == "print('v2')\n"
    assert (workspace / "app" / "new.py").exists()
    assert not (workspace / "app" / "old.txt").exists()
    assert not root.exists()
    assert client.get("/api/command-workspaces", headers=headers).json()["workspaces"] == []
    events = list((workspace / ".raiker").rglob("*.jsonl"))
    assert any("task_workspace_promoted" in path.read_text(encoding="utf-8") for path in events)


def test_a_change_made_after_the_review_makes_the_review_stale(
    client: TestClient, headers: dict[str, str], workspace: Path
) -> None:
    key, root = _task_copy(workspace)
    revision = _review(client, headers)
    (root / "late.py").write_text("unreviewed\n", encoding="utf-8")

    refused = client.post(
        f"/api/command-workspaces/{key}/promote",
        json={"created": ["new.py"], "modified": ["main.py"], "deleted": ["old.txt"],
              "review_revision": revision},
        headers=headers,
    )

    assert refused.status_code == 409
    assert refused.json()["detail"]["reason_code"] == "workspace_review_stale"
    assert not (workspace / "app" / "late.py").exists()
    assert not (workspace / "app" / "new.py").exists()


def test_an_owner_edit_after_the_snapshot_is_a_conflict_and_nothing_is_written(
    client: TestClient, headers: dict[str, str], workspace: Path
) -> None:
    key, _ = _task_copy(workspace)
    (workspace / "app" / "main.py").write_text("owner edit\n", encoding="utf-8")

    refused = client.post(
        f"/api/command-workspaces/{key}/promote",
        json={"created": ["new.py"], "modified": ["main.py"], "deleted": ["old.txt"],
              "review_revision": _review(client, headers)},
        headers=headers,
    )

    assert refused.status_code == 409
    assert refused.json()["detail"]["reason_code"] == "workspace_promotion_conflict"
    assert (workspace / "app" / "main.py").read_text(encoding="utf-8") == "owner edit\n"
    assert (workspace / "app" / "old.txt").exists()


def test_the_listing_names_conflicts_and_an_overwrite_applies_them(
    client: TestClient, headers: dict[str, str], workspace: Path
) -> None:
    """BD-4 — the owner sees the conflict first, then chooses Overwrite."""
    key, _ = _task_copy(workspace)
    (workspace / "app" / "main.py").write_text("owner edit\n", encoding="utf-8")
    [view] = client.get("/api/command-workspaces", headers=headers).json()["workspaces"]
    assert view["conflicts"] == ["main.py"]
    body = {"created": ["new.py"], "modified": ["main.py"], "deleted": ["old.txt"],
            "review_revision": view["review_revision"]}

    unseen = client.post(
        f"/api/command-workspaces/{key}/promote",
        json={**body, "overwrite": ["new.py"]},
        headers=headers,
    )
    assert unseen.status_code == 409
    assert unseen.json()["detail"]["reason_code"] == "workspace_review_stale"
    assert (workspace / "app" / "main.py").read_text(encoding="utf-8") == "owner edit\n"

    applied = client.post(
        f"/api/command-workspaces/{key}/promote",
        json={**body, "overwrite": ["main.py"]},
        headers=headers,
    )
    assert applied.status_code == 200, applied.text
    assert (workspace / "app" / "main.py").read_text(encoding="utf-8") == "print('v2')\n"
    events = "".join(path.read_text(encoding="utf-8") for path in (workspace / ".raiker").rglob("*.jsonl"))
    assert "task_workspace_promoted" in events and '"overwritten":["main.py"]' in events.replace(" ", "")


def test_discard_throws_the_copy_away_and_leaves_the_project(
    client: TestClient, headers: dict[str, str], workspace: Path
) -> None:
    key, root = _task_copy(workspace)

    discarded = client.post(f"/api/command-workspaces/{key}/discard", headers=headers)

    assert discarded.status_code == 200, discarded.text
    assert not root.exists()
    assert (workspace / "app" / "main.py").read_text(encoding="utf-8") == "print('v1')\n"
    assert (workspace / "app" / "old.txt").exists()


def test_another_principals_copy_reads_as_missing(
    client: TestClient, headers: dict[str, str], workspace: Path
) -> None:
    key, root = _task_copy(workspace, owner="principal_other")

    assert client.get("/api/command-workspaces", headers=headers).json()["workspaces"] == []
    missing = client.post(f"/api/command-workspaces/{key}/discard", headers=headers)
    assert missing.status_code == 404
    assert root.exists()
    malformed = client.post("/api/command-workspaces/..%2F..%2Fx/discard", headers=headers)
    assert malformed.status_code == 404


def test_each_changed_file_reads_as_a_unified_diff_against_the_project(
    client: TestClient, headers: dict[str, str], workspace: Path
) -> None:
    key, root = _task_copy(workspace)
    (root / "blob.bin").write_bytes(b"\x00\x01")
    revision = _review(client, headers)

    def diff(path: str) -> dict[str, object]:
        answer = client.get(
            f"/api/command-workspaces/{key}/diff",
            params={"path": path, "review_revision": revision}, headers=headers
        )
        assert answer.status_code == 200, answer.text
        return dict(answer.json())

    modified = diff("main.py")
    assert modified["status"] == "modified"
    assert "-print('v1')" in str(modified["diff"]) and "+print('v2')" in str(modified["diff"])
    assert str(diff("new.py")["diff"]).startswith("--- /dev/null")
    assert "-old" in str(diff("old.txt")["diff"])
    assert diff("blob.bin")["binary"] is True
    # Only what the review lists: an unchanged file, or a way out, reads as missing.
    for path in ("unchanged.txt", "../outside.txt"):
        refused = client.get(
            f"/api/command-workspaces/{key}/diff",
            params={"path": path, "review_revision": revision}, headers=headers
        )
        assert refused.status_code == 404
