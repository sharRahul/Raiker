"""The other half of the code map: where a name is *used*, not declared.

The README's known limit said the map "finds declarations, not every reference"
and had "no reference or call-graph search". That left every *what would break
if I change this* question falling back to a guessed grep pattern.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from raiker.graph.codemap_service import CodeMapService
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.codemap_tools import code_map_references


@pytest.fixture()
def repository(tmp_path: Path) -> Path:
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "core.py").write_text("def widget_total(a, b):\n    return a + b\n")
    (package / "use.py").write_text(
        "from pkg.core import widget_total\n"
        "\n"
        "print(widget_total(1, 2))\n"
        "handler = widget_total\n"
        "# widget_total_extra is a different name\n"
    )
    return tmp_path


@pytest.fixture()
def service(repository: Path) -> CodeMapService:
    built = CodeMapService(repository, SQLiteStore(repository), principal_id="local_user")
    built.build()
    return built


def test_every_use_site_is_returned_with_its_line(service: CodeMapService) -> None:
    result = service.references("widget_total")
    assert result["status"] == "success"
    assert [(row["path"], row["line"]) for row in result["results"]] == [
        ("pkg/use.py", 1),
        ("pkg/use.py", 3),
        ("pkg/use.py", 4),
    ]


def test_the_declaration_itself_is_not_reported_as_a_reference(
    service: CodeMapService,
) -> None:
    """Otherwise the answer to "what uses this" always contains the definition."""
    assert all(row["path"] != "pkg/core.py" for row in service.references("widget_total")["results"])


def test_the_declaration_is_reported_separately(service: CodeMapService) -> None:
    declarations = service.references("widget_total")["declarations"]
    assert declarations[0]["qualified_name"] == "pkg.core.widget_total"
    assert declarations[0]["path"] == "pkg/core.py"


def test_a_longer_name_that_merely_contains_the_query_does_not_match(
    service: CodeMapService,
) -> None:
    """Word-bounded: `widget_total_extra` is a different symbol."""
    assert all(
        "widget_total_extra" not in row["text"] for row in service.references("widget_total")["results"]
    )


def test_free_text_is_refused_rather_than_matched_loosely(service: CodeMapService) -> None:
    assert service.references("widget total")["error"]["type"] == "invalid_symbol_name"


def test_an_unknown_name_returns_nothing_rather_than_failing(
    service: CodeMapService,
) -> None:
    assert service.references("nothing_declared_here")["count"] == 0


def test_the_result_limit_is_bounded_and_the_bound_is_named(
    service: CodeMapService,
) -> None:
    result = service.references("widget_total", limit=1)
    assert result["count"] == 1
    assert result["scan_status"] == "partial"
    assert "max_results" in result["limits_hit"]


def test_a_complete_scan_reports_itself_as_complete(service: CodeMapService) -> None:
    result = service.references("widget_total")
    assert result["scan_status"] == "indexed"
    assert result["limits_hit"] == []


def test_the_result_is_labelled_untrusted_repository_data(service: CodeMapService) -> None:
    assert service.references("widget_total")["trust_label"] == "untrusted_repository_data"


def test_a_repository_without_a_map_says_so(tmp_path: Path) -> None:
    service = CodeMapService(tmp_path, SQLiteStore(tmp_path), principal_id="local_user")
    assert service.references("anything")["error"]["type"] == "code_map_not_built"


def test_the_tool_wrapper_reaches_the_service(repository: Path) -> None:
    store = SQLiteStore(repository)
    CodeMapService(repository, store, principal_id="local_user").build()
    result = code_map_references(repository, "widget_total", store=store, principal_id="local_user")
    assert result["count"] == 3


def test_the_tool_is_offered_to_the_model_and_delegable() -> None:
    from raiker.agents.orchestration import DELEGABLE_TOOLS
    from raiker.models.tool_call_validation import default_tool_specs

    spec = next(s for s in default_tool_specs() if s.name == "code_map_references")
    assert spec.parameters["required"] == ["name"]
    assert "code_map_references" in DELEGABLE_TOOLS
