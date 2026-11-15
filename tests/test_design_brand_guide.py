"""BUG-348 DW-06 — a brand guide PDF's colours and fonts fill a new design system."""

from __future__ import annotations

import base64
from pathlib import Path

from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.design.imports import parse_brand_guide
from tests.minimal_pdf import minimal_pdf


def test_colours_are_named_by_their_line_or_the_caption_above() -> None:
    parsed = parse_brand_guide("acme.pdf", "Ocean Blue HEX #1A73E8\nSunset\n#FF7043\nCharcoal: #222")
    assert parsed["variables"]["colors"] == {"ocean-blue": "#1a73e8", "sunset": "#ff7043", "charcoal": "#222222"}


def test_rgb_values_are_read_and_a_repeated_colour_is_kept_once() -> None:
    parsed = parse_brand_guide("g.pdf", "Leaf RGB 10, 200, 30\nAccent #0ac81e again")
    assert parsed["variables"]["colors"] == {"leaf": "#0ac81e"}


def test_labelled_fonts_are_read_by_role() -> None:
    parsed = parse_brand_guide("g.pdf", "Heading font: Playfair Display\nBody typeface: Inter, sans-serif")
    assert parsed["variables"]["fonts"] == {"heading": "Playfair Display", "body": "Inter"}


def test_a_guide_with_nothing_to_read_says_so() -> None:
    parsed = parse_brand_guide("words.pdf", "Our brand is friendly and bold.")
    assert parsed["found"] == 0
    assert parsed["skipped"] and "no #hex" in parsed["skipped"][0]["reason"]


def test_the_route_reads_a_real_pdf_and_refuses_anything_else(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    token = client.post("/api/auth/register", json={"username": "owner", "password": "a-long-password-1"}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    pdf = minimal_pdf(["Ocean blue #1144aa", "Heading font: Inter"])
    response = client.post(
        "/api/design/systems/brand-guide",
        json={"filename": "brand.pdf", "data_base64": base64.b64encode(pdf).decode()},
        headers=h,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["format"] == "pdf"
    assert body["variables"]["colors"] == {"ocean-blue": "#1144aa"}
    assert body["variables"]["fonts"] == {"heading": "Inter"}
    refused = client.post(
        "/api/design/systems/brand-guide",
        json={"filename": "brand.pdf", "data_base64": base64.b64encode(b"not a pdf at all").decode()},
        headers=h,
    )
    assert refused.status_code == 422
