"""TOOL-72 / TOOL-126 — a turn offers a connection; it connects nothing."""

from __future__ import annotations

from pathlib import Path

from raiker.models.tool_call_validation import default_tool_specs, risk_for_tool
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.connection_tools import suggest_connection


def test_a_service_is_named_from_the_catalogue(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    result = suggest_connection("gmail", "To read the invoice you mentioned.", store=store, principal_id="p")
    assert result["status"] == "success"
    assert result["connector_id"] == "gmail" and result["service"] == "Gmail"
    assert result["href"] == "#/connections?add=gmail"
    assert result["connected"] is False
    by_name = suggest_connection("Google Calendar", "To find a free hour.", store=store, principal_id="p")
    assert by_name["connector_id"] == "gcal"


def test_unknown_or_empty_arguments_are_named(tmp_path: Path) -> None:
    unknown = suggest_connection("Myspace", "why")
    assert unknown["error"]["type"] == "unknown_service" and "Gmail" in unknown["error"]["services"]
    assert suggest_connection("", "why")["error"]["type"] == "missing_argument:service"
    assert suggest_connection("gmail", " ")["error"]["type"] == "missing_argument:reason"


def test_it_is_low_risk_and_needs_no_approval() -> None:
    assert risk_for_tool("suggest_connection") == "low"
    spec = {s.name: s for s in default_tool_specs()}["suggest_connection"]
    assert spec.parameters["required"] == ["service", "reason"]
