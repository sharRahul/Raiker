"""Several of a provider's models stay offered, not just the selected default.

Selecting a default used to be the only thing that put a model into a picker,
so a provider serving six could offer exactly one of them and changing which
one meant going back to the Models page.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.api.sessions import ApiSessionStore
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.storage.sqlite import SQLiteStore

PROFILE = "chatgpt-codex-subscription"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "available"
    root.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=root)
    return root


@pytest.fixture
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(workspace))


@pytest.fixture
def headers(workspace: Path) -> dict[str, str]:
    token, _ = ApiSessionStore(workspace).create_session("principal_owner")
    return {"Authorization": f"Bearer {token}"}


def test_several_models_from_one_provider_stay_offered(
    workspace: Path, client: TestClient, headers: dict[str, str]
) -> None:
    response = client.put(
        f"/api/models/{PROFILE}/available-models",
        json={"models": ["gpt-5.6-sol", "gpt-5.6-luna", "gpt-5.4"]},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["models"] == ["gpt-5.6-sol", "gpt-5.6-luna", "gpt-5.4"]
    stored = SQLiteStore(workspace).list_configured_models("principal_owner")
    assert sorted(model for profile_id, model in stored if profile_id == PROFILE) == [
        "gpt-5.4",
        "gpt-5.6-luna",
        "gpt-5.6-sol",
    ]


def test_writing_the_list_again_replaces_it(
    client: TestClient, headers: dict[str, str]
) -> None:
    client.put(
        f"/api/models/{PROFILE}/available-models",
        json={"models": ["gpt-5.6-sol", "gpt-5.4"]},
        headers=headers,
    )

    response = client.put(
        f"/api/models/{PROFILE}/available-models",
        json={"models": ["gpt-5.4"]},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["models"] == ["gpt-5.4"]


def test_an_unknown_profile_and_an_oversized_list_are_refused(
    client: TestClient, headers: dict[str, str]
) -> None:
    unknown = client.put(
        "/api/models/not-a-profile/available-models",
        json={"models": ["x"]},
        headers=headers,
    )
    assert unknown.status_code == 404
    assert unknown.json()["detail"]["reason_code"] == "unknown_model_profile"

    # A router serving four hundred models must not be pourable into every
    # picker in the app.
    too_many = client.put(
        f"/api/models/{PROFILE}/available-models",
        json={"models": [f"model-{index}" for index in range(200)]},
        headers=headers,
    )
    assert too_many.status_code == 400
    assert too_many.json()["detail"]["reason_code"] == "too_many_available_models"


def test_the_list_is_owner_scoped(client: TestClient) -> None:
    assert (
        client.put(
            f"/api/models/{PROFILE}/available-models", json={"models": ["gpt-5.4"]}
        ).status_code
        == 401
    )
