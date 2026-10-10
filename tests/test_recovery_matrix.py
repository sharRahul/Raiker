"""DEC-24 step 3 — the recovery matrix names code that exists and does what it says."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from raiker.recovery_matrix import RECOVERY_MATRIX, recovery_matrix_view


def _resolve(anchor: str) -> object:
    module_name, _, qualname = anchor.partition(":")
    target: object = importlib.import_module(module_name)
    for part in qualname.split("."):
        target = getattr(target, part)
    return target


@pytest.mark.parametrize("anchor", sorted({a for row in RECOVERY_MATRIX for a in row.anchors}))
def test_every_anchor_names_real_code(anchor: str) -> None:
    assert callable(_resolve(anchor)), anchor


def test_every_row_answers_every_question() -> None:
    subsystems = [row.subsystem for row in RECOVERY_MATRIX]
    assert len(subsystems) == len(set(subsystems))
    for row in recovery_matrix_view():
        for field, value in row.items():
            assert value, f"{row['subsystem']}: {field} is empty"


def test_the_matrix_is_served_to_the_owner_only(tmp_path: Path) -> None:
    from raiker.api.app import create_app
    from raiker.cli.principal_resolver import bootstrap_owner

    bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
    client = TestClient(create_app(tmp_path))
    assert client.get("/api/diagnostics/recovery").status_code in (401, 403)
    token = client.post("/api/auth/session", json={"as_principal": None}).json()["token"]
    answer = client.get("/api/diagnostics/recovery", headers={"Authorization": f"Bearer {token}"})
    assert answer.status_code == 200, answer.text
    assert [row["subsystem"] for row in answer.json()["rows"]] == [r.subsystem for r in RECOVERY_MATRIX]
