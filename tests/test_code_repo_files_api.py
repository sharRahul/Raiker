"""Browsing and reading the repository Build is pointed at (B13).

These two routes are the only path by which a browser can see the *contents* of
a connected repository, so the tests below are mostly about what they refuse.
The rule they encode: a repository reference is a window onto one folder, never
a workspace-wide file browser, and a file that cannot be shown says which of the
reasons applies rather than coming back empty.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.routes_code_files import MAX_VIEW_BYTES
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.control.dashboard import DashboardService

OWNER = "principal_owner"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


@pytest.fixture
def headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/auth/session", json={"as_principal": None})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.fixture
def repo_id(workspace: Path) -> str:
    root = workspace / "project"
    (root / "src").mkdir(parents=True)
    # Written with newline="" so the bytes on disk are the bytes asserted.
    # Text mode rewrites "\n" as "\r\n" on Windows, which turned a
    # byte-exact read-back into a platform difference rather than a finding.
    (root / "src" / "main.py").write_text("print('hello')\n", encoding="utf-8", newline="")
    (root / "README.md").write_text("# Alpha\n", encoding="utf-8", newline="")
    (root / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00binary")
    (root / "node_modules").mkdir()
    # Something outside the repository but inside the workspace: the second
    # containment check is the only thing that stops the explorer reaching it.
    (workspace / "secret.txt").write_text("not the repository's\n", encoding="utf-8", newline="")
    result = DashboardService(workspace).connect_local_repo(
        str(root), owner_principal_id=OWNER
    )
    assert result.ok, result.reason_code
    return str(result.data["repo_id"])


class TestAuthentication:
    def test_every_route_requires_authentication(
        self, client: TestClient, repo_id: str
    ) -> None:
        assert client.get(f"/api/code/repos/{repo_id}/browse").status_code == 401
        assert (
            client.get(f"/api/code/repos/{repo_id}/file", params={"path": "README.md"})
            .status_code
            == 401
        )
        # the Build artifact pane's's working-tree read is the third, and it answers about a
        # repository's uncommitted state — which is exactly as private as its
        # files. This client has never opened a session, which is what makes the
        # assertion mean anything: a fixture that had would carry its cookie.
        assert client.get(f"/api/code/repos/{repo_id}/changes").status_code == 401


class TestBrowse:
    def test_root_lists_directories_first_and_hides_ignored_names(
        self, client: TestClient, headers: dict[str, str], repo_id: str
    ) -> None:
        body = client.get(
            f"/api/code/repos/{repo_id}/browse", headers=headers
        ).json()
        names = [entry["name"] for entry in body["entries"]]
        assert names == ["src", "logo.png", "README.md"]
        assert body["root_missing"] is False
        assert body["parent"] is None

    def test_a_subdirectory_names_its_parent(
        self, client: TestClient, headers: dict[str, str], repo_id: str
    ) -> None:
        body = client.get(
            f"/api/code/repos/{repo_id}/browse",
            params={"path": "src"},
            headers=headers,
        ).json()
        assert body["path"] == "src"
        assert body["parent"] == ""
        assert [entry["relative_path"] for entry in body["entries"]] == ["src/main.py"]

    @pytest.mark.parametrize(
        "path", ["../secret.txt", "/etc/passwd", "src/../../secret.txt"]
    )
    def test_a_path_out_of_the_repository_is_refused(
        self, client: TestClient, headers: dict[str, str], repo_id: str, path: str
    ) -> None:
        response = client.get(
            f"/api/code/repos/{repo_id}/browse",
            params={"path": path},
            headers=headers,
        )
        assert response.status_code == 400, response.text

    def test_an_unknown_repository_is_a_404(
        self, client: TestClient, headers: dict[str, str]
    ) -> None:
        response = client.get("/api/code/repos/repo_nope/browse", headers=headers)
        assert response.status_code == 404
        assert response.json()["detail"]["reason_code"] == "repo_not_found"

    def test_a_github_coordinate_says_it_has_no_checkout(
        self, workspace: Path, client: TestClient, headers: dict[str, str]
    ) -> None:
        connected = DashboardService(workspace).connect_github_repo(
            "octo", "cat", None, owner_principal_id=OWNER
        )
        assert connected.ok, connected.reason_code
        body = client.get(
            f"/api/code/repos/{connected.data['repo_id']}/browse", headers=headers
        ).json()
        assert body["root_missing"] is True
        assert body["reason_code"] == "repo_not_checked_out"
        assert body["entries"] == []


class TestReadFile:
    def test_a_text_file_comes_back_whole(
        self, client: TestClient, headers: dict[str, str], repo_id: str
    ) -> None:
        body = client.get(
            f"/api/code/repos/{repo_id}/file",
            params={"path": "src/main.py"},
            headers=headers,
        ).json()
        assert body["readable"] is True
        assert body["text"] == "print('hello')\n"
        assert body["truncated"] is False

    def test_a_binary_file_says_so_rather_than_coming_back_empty(
        self, client: TestClient, headers: dict[str, str], repo_id: str
    ) -> None:
        body = client.get(
            f"/api/code/repos/{repo_id}/file",
            params={"path": "logo.png"},
            headers=headers,
        ).json()
        assert body["readable"] is False
        assert body["reason_code"] == "binary_file"
        assert body["text"] == ""

    def test_an_oversize_file_is_refused_with_its_size(
        self, workspace: Path, client: TestClient, headers: dict[str, str], repo_id: str
    ) -> None:
        big = workspace / "project" / "big.txt"
        big.write_text("x" * (MAX_VIEW_BYTES + 10), encoding="utf-8")
        body = client.get(
            f"/api/code/repos/{repo_id}/file",
            params={"path": "big.txt"},
            headers=headers,
        ).json()
        assert body["readable"] is False
        assert body["reason_code"] == "file_too_large"
        assert body["size_bytes"] == MAX_VIEW_BYTES + 10

    def test_a_directory_is_not_a_file(
        self, client: TestClient, headers: dict[str, str], repo_id: str
    ) -> None:
        response = client.get(
            f"/api/code/repos/{repo_id}/file", params={"path": "src"}, headers=headers
        )
        assert response.status_code == 400
        assert response.json()["detail"]["reason_code"] == "not_a_file"

    def test_a_path_outside_the_repository_cannot_be_read(
        self, client: TestClient, headers: dict[str, str], repo_id: str
    ) -> None:
        response = client.get(
            f"/api/code/repos/{repo_id}/file",
            params={"path": "../secret.txt"},
            headers=headers,
        )
        assert response.status_code == 400, response.text

    def test_an_empty_path_is_refused_rather_than_listing_the_root(
        self, client: TestClient, headers: dict[str, str], repo_id: str
    ) -> None:
        response = client.get(f"/api/code/repos/{repo_id}/file", headers=headers)
        assert response.status_code == 400
        assert response.json()["detail"]["reason_code"] == "path_required"

    def test_another_accounts_repository_is_not_visible(
        self, workspace: Path, client: TestClient, headers: dict[str, str]
    ) -> None:
        root = workspace / "other"
        root.mkdir()
        (root / "a.txt").write_text("theirs\n", encoding="utf-8", newline="")
        theirs = DashboardService(workspace).connect_local_repo(
            str(root), owner_principal_id="principal_someone_else"
        )
        assert theirs.ok, theirs.reason_code
        response = client.get(
            f"/api/code/repos/{theirs.data['repo_id']}/file",
            params={"path": "a.txt"},
            headers=headers,
        )
        assert response.status_code == 404
        assert response.json()["detail"]["reason_code"] == "repo_not_found"


class TestDiagnostics:
    """B10 — the workspace says whether the file it is showing still parses.

    The route is the same service and the same ``language_intelligence`` gate the
    agent's own ``diagnostics`` tool goes through, so the browser and the model
    cannot disagree about one file.
    """

    def test_it_requires_authentication(self, client: TestClient, repo_id: str) -> None:
        assert (
            client.get(
                f"/api/code/repos/{repo_id}/diagnostics", params={"path": "README.md"}
            ).status_code
            == 401
        )

    def test_a_clean_file_is_reported_as_checked_and_empty(
        self, client: TestClient, headers: dict[str, str], repo_id: str
    ) -> None:
        body = client.get(
            f"/api/code/repos/{repo_id}/diagnostics",
            params={"path": "src/main.py"},
            headers=headers,
        ).json()
        assert body["checked"] is True
        assert body["diagnostics"] == []

    def test_a_broken_file_reports_its_coordinate(
        self, client: TestClient, headers: dict[str, str], repo_id: str, workspace: Path
    ) -> None:
        (workspace / "project" / "src" / "broken.py").write_text(
            "def oops(:\n", encoding="utf-8", newline=""
        )
        body = client.get(
            f"/api/code/repos/{repo_id}/diagnostics",
            params={"path": "src/broken.py"},
            headers=headers,
        ).json()
        assert body["checked"] is True
        assert body["diagnostics"][0]["line"] == 1
        assert body["diagnostics"][0]["severity"] == "error"

    def test_a_language_with_no_parser_is_not_checked_rather_than_clean(
        self, client: TestClient, headers: dict[str, str], repo_id: str, workspace: Path
    ) -> None:
        """The contract the whole surface rests on.

        Reporting an unparsed file as having no problems is a claim nothing
        established, and it is trusted exactly as much as a real one.
        """
        (workspace / "project" / "src" / "ui.ts").write_text(
            "export const x = 1;\n", encoding="utf-8", newline=""
        )
        body = client.get(
            f"/api/code/repos/{repo_id}/diagnostics",
            params={"path": "src/ui.ts"},
            headers=headers,
        ).json()
        assert body["checked"] is False
        assert body["reason_code"] == "language_not_parseable"
        assert body["diagnostics"] == []

    def test_it_cannot_reach_outside_the_repository(
        self, client: TestClient, headers: dict[str, str], repo_id: str
    ) -> None:
        """The same second containment check the file read keeps."""
        response = client.get(
            f"/api/code/repos/{repo_id}/diagnostics",
            params={"path": "../secret.txt"},
            headers=headers,
        )
        assert response.status_code in (400, 403, 404)

    def test_a_missing_file_is_not_found(
        self, client: TestClient, headers: dict[str, str], repo_id: str
    ) -> None:
        assert (
            client.get(
                f"/api/code/repos/{repo_id}/diagnostics",
                params={"path": "src/nope.py"},
                headers=headers,
            ).status_code
            == 404
        )


class TestWorkingTreeChanges:
    """the Build artifact pane — the third pane's `Changes` tab, and what it must never claim.

    The property that matters is not "it lists files". It is that this read and
    the commit proposal describe **one** change set: they call the same two
    helpers, so a pane cannot show a change the commit would not record, or miss
    one it would. A second `git status` written for the browser could disagree
    with the proposal, and nothing in the interface would say which was right.
    """

    def _git(self, root: Path, *args: str) -> None:
        import subprocess

        subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
            env={
                "GIT_AUTHOR_NAME": "T",
                "GIT_AUTHOR_EMAIL": "t@example.test",
                "GIT_COMMITTER_NAME": "T",
                "GIT_COMMITTER_EMAIL": "t@example.test",
                "PATH": __import__("os").environ.get("PATH", ""),
                "HOME": str(root),
            },
        )

    def test_a_folder_with_no_history_says_so_rather_than_no_changes(
        self, client: TestClient, headers: dict[str, str], repo_id: str
    ) -> None:
        """"No changes" and "no version control" are different answers."""
        response = client.get(f"/api/code/repos/{repo_id}/changes", headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["entries"] == []
        assert body["reason_code"] == "not_a_git_repository"
        assert body["root_missing"] is False

    def test_it_reports_the_same_change_set_a_commit_would_record(
        self, client: TestClient, headers: dict[str, str], repo_id: str, workspace: Path
    ) -> None:
        from raiker.tools.git import working_tree_changes, working_tree_diff

        root = workspace / "project"
        self._git(root, "init", "--quiet")
        self._git(root, "add", "README.md")
        self._git(root, "commit", "--quiet", "-m", "first")
        (root / "README.md").write_text("# Alpha\nnow with a line\n", encoding="utf-8", newline="")
        (root / "NEW.md").write_text("brand new\n", encoding="utf-8", newline="")

        response = client.get(f"/api/code/repos/{repo_id}/changes", headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()

        paths = {entry["path"] for entry in body["entries"]}
        assert "README.md" in paths
        assert "NEW.md" in paths
        assert body["reason_code"] is None

        # The same functions the commit proposal is built from, so the pane and
        # the commit cannot describe different change sets.
        expected = working_tree_changes(root)
        assert paths == {entry["path"] for entry in expected}
        assert body["diff"] == working_tree_diff(root, expected)
        # A tracked edit and an untracked addition both reach the diff — the
        # second is the one a plain `git diff` would silently omit.
        assert "now with a line" in body["diff"]
        assert "brand new" in body["diff"]

    def test_both_kinds_of_truncation_are_stated(
        self, client: TestClient, headers: dict[str, str], repo_id: str,
        workspace: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A pane nobody can scroll to the end of hides the change it exists to show."""
        import raiker.api.routes_code_files as routes

        root = workspace / "project"
        self._git(root, "init", "--quiet")
        for index in range(4):
            (root / f"f{index}.txt").write_text(f"line {index}\n", encoding="utf-8", newline="")
        monkeypatch.setattr(routes, "MAX_CHANGED_FILES", 2)
        monkeypatch.setattr(routes, "MAX_CHANGES_DIFF_CHARS", 10)

        body = client.get(f"/api/code/repos/{repo_id}/changes", headers=headers).json()
        assert len(body["entries"]) == 2
        assert body["truncated"] is True
        assert len(body["diff"]) == 10
        assert body["diff_truncated"] is True

    def test_a_repository_with_no_checkout_says_which_absence_it_is(
        self, client: TestClient, headers: dict[str, str], workspace: Path
    ) -> None:
        result = DashboardService(workspace).connect_github_repo(
            "octo", "widget", None, owner_principal_id=OWNER
        )
        assert result.ok, result.reason_code
        body = client.get(
            f"/api/code/repos/{result.data['repo_id']}/changes", headers=headers
        ).json()
        assert body["root_missing"] is True
        assert body["reason_code"] == "repo_not_checked_out"

    def test_an_unknown_id_is_hidden_rather_than_refused(
        self, client: TestClient, headers: dict[str, str]
    ) -> None:
        # 404 rather than 403, so an id cannot be probed for existence.
        assert (
            client.get("/api/code/repos/repo_nope/changes", headers=headers).status_code
            == 404
        )
