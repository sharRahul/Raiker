"""The Skills API: authentication, validation, and owner isolation.

These exercise the HTTP surface the Skills tab talks to. The point of most of
them is the refusal path — an unauthenticated call, a malformed document, an
unsupported import host — because that is what makes the tab's promises real.
"""

from __future__ import annotations

import base64
import io
import zipfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner

DOCUMENT = """---
name: tidy-imports
description: Sort and dedupe imports. Use when asked to tidy imports.
---

# Tidy imports

Sort them.
"""


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def app(workspace: Path) -> FastAPI:
    return create_app(workspace)


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture
def headers(client: TestClient) -> dict[str, str]:
    resp = client.post("/api/auth/session", json={"as_principal": None})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def _upload(
    client: TestClient, headers: dict[str, str], filename: str, data: bytes
) -> Response:
    return client.post(
        "/api/skills",
        headers=headers,
        json={"filename": filename, "data_base64": base64.b64encode(data).decode("ascii")},
    )


class TestAuthentication:
    def test_listing_requires_a_token(self, client: TestClient) -> None:
        assert client.get("/api/skills").status_code == 401

    def test_uploading_requires_a_token(self, client: TestClient) -> None:
        resp = client.post(
            "/api/skills", json={"filename": "x.md", "data_base64": "eA=="}
        )
        assert resp.status_code == 401


class TestListing:
    def test_built_in_skills_are_present(self, client: TestClient, headers: dict[str, str]) -> None:
        resp = client.get("/api/skills", headers=headers)
        assert resp.status_code == 200, resp.text
        names = {skill["name"] for skill in resp.json()["skills"]}
        assert {"algorithm-creator", "mcp-builder", "skill-creator"} <= names

    def test_the_stored_document_is_not_in_the_list(
        self, client: TestClient, headers: dict[str, str]
    ) -> None:
        skill = client.get("/api/skills", headers=headers).json()["skills"][0]
        assert "skill_md" not in skill
        assert "bundle" not in skill
        assert skill["checksum"] and skill["active"] is True


class TestUpload:
    def test_a_valid_document_installs(self, client: TestClient, headers: dict[str, str]) -> None:
        resp = _upload(client, headers, "tidy.md", DOCUMENT.encode("utf-8"))
        assert resp.status_code == 200, resp.text
        assert resp.json()["skill"]["name"] == "tidy-imports"

    def test_a_valid_bundle_installs(self, client: TestClient, headers: dict[str, str]) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("tidy-imports/SKILL.md", DOCUMENT)
            archive.writestr("tidy-imports/reference.md", "detail")
        resp = _upload(client, headers, "tidy-imports.skill", buffer.getvalue())
        assert resp.status_code == 200, resp.text
        assert resp.json()["skill"]["file_count"] == 2

    def test_a_document_without_a_description_is_422(
        self, client: TestClient, headers: dict[str, str]
    ) -> None:
        resp = _upload(client, headers, "bad.md", b"---\nname: x\n---\nbody\n")
        assert resp.status_code == 422
        assert resp.json()["detail"]["reason_code"] == "skill_missing_description"

    def test_a_zip_escaping_its_directory_is_422(
        self, client: TestClient, headers: dict[str, str]
    ) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("../escape/SKILL.md", DOCUMENT)
        resp = _upload(client, headers, "evil.skill", buffer.getvalue())
        assert resp.status_code == 422
        assert resp.json()["detail"]["reason_code"] == "skill_unsafe_member_path"

    def test_an_executable_is_refused(self, client: TestClient, headers: dict[str, str]) -> None:
        resp = _upload(client, headers, "payload.exe", b"MZ\x90\x00")
        assert resp.status_code == 422
        assert resp.json()["detail"]["reason_code"] == "skill_unsupported_file_type"

    def test_invalid_base64_is_400(self, client: TestClient, headers: dict[str, str]) -> None:
        resp = client.post(
            "/api/skills", headers=headers, json={"filename": "x.md", "data_base64": "!!!"}
        )
        assert resp.status_code == 400


class TestLifecycle:
    def test_rename_activate_download_delete(
        self, client: TestClient, headers: dict[str, str]
    ) -> None:
        skill_id = _upload(client, headers, "tidy.md", DOCUMENT.encode("utf-8")).json()["skill_id"]

        renamed = client.put(f"/api/skills/{skill_id}", headers=headers, json={"name": "tidy-up"})
        assert renamed.status_code == 200, renamed.text
        assert renamed.json()["name"] == "tidy-up"

        off = client.put(f"/api/skills/{skill_id}/active", headers=headers, json={"active": False})
        assert off.status_code == 200 and off.json()["active"] is False
        listed = {s["skill_id"]: s for s in client.get("/api/skills", headers=headers).json()["skills"]}
        assert listed[skill_id]["active"] is False

        download = client.get(f"/api/skills/{skill_id}/download", headers=headers)
        assert download.status_code == 200
        assert download.headers["content-type"] == "application/zip"
        assert "tidy-up.skill" in download.headers["content-disposition"]
        with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
            assert archive.namelist() == ["tidy-up/SKILL.md"]

        assert client.delete(f"/api/skills/{skill_id}", headers=headers).status_code == 200
        assert client.get(f"/api/skills/{skill_id}/download", headers=headers).status_code == 404

    def test_renaming_onto_a_taken_name_is_422(
        self, client: TestClient, headers: dict[str, str]
    ) -> None:
        client.get("/api/skills", headers=headers)  # seeds the shipped skills
        skill_id = _upload(client, headers, "tidy.md", DOCUMENT.encode("utf-8")).json()["skill_id"]
        resp = client.put(f"/api/skills/{skill_id}", headers=headers, json={"name": "mcp-builder"})
        assert resp.status_code == 422
        assert resp.json()["detail"]["reason_code"] == "skill_rename_failed"

    def test_unknown_skill_is_404(self, client: TestClient, headers: dict[str, str]) -> None:
        resp = client.delete("/api/skills/skl_missing", headers=headers)
        assert resp.status_code == 404


class TestBuild:
    def test_raiker_can_build_a_skill(self, client: TestClient, headers: dict[str, str]) -> None:
        resp = client.post(
            "/api/skills/build",
            headers=headers,
            json={
                "name": "release-notes",
                "description": "Draft release notes. Use when cutting a release.",
                "body": "# Release notes\n\nSummarise the diff.",
            },
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["skill"]["source"] == "built"

    def test_a_bad_name_is_refused(self, client: TestClient, headers: dict[str, str]) -> None:
        resp = client.post(
            "/api/skills/build",
            headers=headers,
            json={"name": "Not A Slug", "description": "x", "body": "y"},
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["reason_code"] == "skill_invalid_name"


class TestImport:
    def test_an_unsupported_host_is_refused_without_reaching_it(
        self, client: TestClient, headers: dict[str, str]
    ) -> None:
        for path in ("/api/skills/verify", "/api/skills/import"):
            resp = client.post(path, headers=headers, json={"url": "https://example.com/SKILL.md"})
            assert resp.status_code == 422, path
            assert resp.json()["detail"]["reason_code"] == "skill_unsupported_source"

    def test_a_binary_archive_url_is_refused(
        self, client: TestClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No network: the fetch is never reached, because a `.skill` URL is
        # refused before egress on the text-only read boundary.
        resp = client.post(
            "/api/skills/import",
            headers=headers,
            json={"url": "https://raw.githubusercontent.com/o/r/main/x.skill"},
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["reason_code"] == "skill_archive_url_unsupported"

    def test_a_verified_document_is_reported_but_not_stored(
        self, client: TestClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import raiker.runtime.executors.sandbox as sandbox

        monkeypatch.setattr(
            sandbox,
            "get_url",
            lambda url, **kwargs: {"status": 200, "body_text": DOCUMENT, "truncated": False},
        )
        url = "https://raw.githubusercontent.com/o/r/main/skills/tidy/SKILL.md"
        verified = client.post("/api/skills/verify", headers=headers, json={"url": url})
        assert verified.status_code == 200, verified.text
        body = verified.json()
        assert body["verified"] is True and body["name"] == "tidy-imports"
        assert body["already_installed"] is False
        names = {s["name"] for s in client.get("/api/skills", headers=headers).json()["skills"]}
        assert "tidy-imports" not in names

    def test_an_imported_document_is_stored_with_its_source(
        self, client: TestClient, headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import raiker.runtime.executors.sandbox as sandbox

        monkeypatch.setattr(
            sandbox,
            "get_url",
            lambda url, **kwargs: {"status": 200, "body_text": DOCUMENT, "truncated": False},
        )
        resp = client.post(
            "/api/skills/import",
            headers=headers,
            json={"url": "https://github.com/o/r/blob/main/skills/tidy/SKILL.md"},
        )
        assert resp.status_code == 200, resp.text
        skill = resp.json()["skill"]
        assert skill["source"] == "url"
        assert skill["source_ref"].startswith("https://raw.githubusercontent.com/")
