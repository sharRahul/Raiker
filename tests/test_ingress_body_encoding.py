"""DEC-25 — an encoded request body is refused, by name, before it is read.

No route decompresses a request body. A gzip body would reach a JSON parser as
bytes it cannot read, and the byte cap would be counting the compressed size of
whatever a later decoder expanded. So the one remaining DEC-25 path — incoming
decompression — is closed at ingress rather than left for a route to inherit.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from fastapi.testclient import TestClient

from raiker.api.app import create_app


def test_a_gzip_body_is_refused_with_its_reason(tmp_path: Path) -> None:
    client = TestClient(create_app(workspace_root=tmp_path))
    response = client.post(
        "/api/auth/login",
        content=gzip.compress(json.dumps({"username": "a", "password": "b"}).encode()),
        headers={"Content-Type": "application/json", "Content-Encoding": "gzip"},
    )
    assert response.status_code == 415
    assert response.json()["reason_code"] == "request_body_encoding_unsupported"


def test_identity_is_an_ordinary_body(tmp_path: Path) -> None:
    client = TestClient(create_app(workspace_root=tmp_path))
    response = client.post(
        "/api/auth/login",
        json={"username": "nobody", "password": "wrong-password-1"},
        headers={"Content-Encoding": "identity"},
    )
    assert response.status_code != 415
