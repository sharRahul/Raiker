"""GAP-BUILD B10 — language intelligence over the repository Build points at.

The code map answers *where is this declared* and *where is it used*. B10 named
the three questions it does not answer, and these are the tests for the answers:
an outline of one file that is right the instant after an edit, an exact-name
definition lookup that does not return `ConfigLoader` for `Config`, and a
parse-level diagnostic that closes the edit → verify loop without a command
approval.

The property tested hardest here is the honesty contract on ``diagnostics``: a
file whose language this runtime cannot parse must come back under
``unsupported``, never as clean. A tool that reports "no problems" about a file
it did not open is worse than no tool, because it is trusted the same and is
wrong.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from raiker.contracts.ids import utc_now
from raiker.graph.codemap_service import CodeMapService
from raiker.graph.language_service import LanguageIntelligenceService
from raiker.storage.sqlite import SQLiteStore
from raiker.tools.language_tools import diagnostics, document_symbols, find_definition


@pytest.fixture()
def repository(tmp_path: Path) -> Path:
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "core.py").write_text(
        '"""Core widgets."""\n'
        "\n"
        "WIDGET_LIMIT = 10\n"
        "\n"
        "\n"
        "class Widget:\n"
        '    """One widget."""\n'
        "\n"
        "    def total(self, a, b):\n"
        "        return a + b\n"
        "\n"
        "\n"
        "def widget_total(a, b):\n"
        "    return a + b\n"
    )
    (package / "other.py").write_text("class Widget:\n    pass\n")
    (package / "use.py").write_text(
        "from pkg.core import Widget, widget_total\n"
        "\n"
        "print(widget_total(1, 2))\n"
    )
    (package / "broken.py").write_text("def oops(:\n    pass\n")
    (package / "data.json").write_text('{"a": 1,}\n')
    (package / "ui.ts").write_text("export const x: number = 1;\n")
    return tmp_path


@pytest.fixture()
def service(repository: Path) -> LanguageIntelligenceService:
    # The code map is what `find_definition` reads; the other two parse directly.
    CodeMapService(repository, SQLiteStore(repository), principal_id="local_user").build()
    return LanguageIntelligenceService(
        repository, SQLiteStore(repository), principal_id="local_user"
    )


class TestDocumentSymbols:
    def test_it_outlines_one_file_with_line_ranges(
        self, service: LanguageIntelligenceService
    ) -> None:
        result = service.document_symbols("pkg/core.py")
        assert result["status"] == "success"
        named = {symbol["name"]: symbol for symbol in result["symbols"]}
        assert "Widget" in named
        assert "widget_total" in named
        assert named["Widget"]["kind"] == "class"
        assert named["Widget"]["line_start"] == 6
        assert named["total"]["parent"] == "pkg.core.Widget"

    def test_it_reports_what_the_file_imports(
        self, service: LanguageIntelligenceService
    ) -> None:
        result = service.document_symbols("pkg/use.py")
        assert any("pkg.core" in edge["target"] for edge in result["imports"])

    def test_it_follows_an_edit_without_an_index_rebuild(
        self, service: LanguageIntelligenceService, repository: Path
    ) -> None:
        """The property that makes this language intelligence and not a cache.

        An outline that needs the index rebuilt before it is right is useless to
        an agent, because the agent's own edit is precisely what invalidated it.
        """
        (repository / "pkg" / "core.py").write_text("def only_this(x):\n    return x\n")
        result = service.document_symbols("pkg/core.py")
        assert [symbol["name"] for symbol in result["symbols"]] == ["only_this"]

    def test_a_path_outside_the_repository_is_refused(
        self, service: LanguageIntelligenceService
    ) -> None:
        result = service.document_symbols("../../../etc/passwd")
        assert result["status"] == "failed"
        assert result["error"]["type"] == "outside_repository"

    def test_a_file_with_no_extractor_says_so(
        self, service: LanguageIntelligenceService, repository: Path
    ) -> None:
        (repository / "notes.txt").write_text("hello\n")
        result = service.document_symbols("notes.txt")
        assert result["error"]["type"] == "unsupported_language"

    def test_results_are_labelled_untrusted(
        self, service: LanguageIntelligenceService
    ) -> None:
        assert service.document_symbols("pkg/core.py")["trust_label"] == (
            "untrusted_repository_data"
        )


class TestFindDefinition:
    def test_it_matches_the_exact_name(self, service: LanguageIntelligenceService) -> None:
        result = service.find_definition("widget_total")
        assert result["count"] == 1
        assert result["definitions"][0]["path"] == "pkg/core.py"
        assert result["definitions"][0]["kind"] == "function"

    def test_a_name_declared_twice_returns_both_candidates(
        self, service: LanguageIntelligenceService
    ) -> None:
        """`Widget` is declared in two modules, and neither is guessed away."""
        paths = {row["path"] for row in service.find_definition("Widget")["definitions"]}
        assert paths == {"pkg/core.py", "pkg/other.py"}

    def test_the_file_that_asked_ranks_a_declaration_it_imports_first(
        self, service: LanguageIntelligenceService
    ) -> None:
        """"Which of the two did I mean" is what a ranked text search cannot answer."""
        result = service.find_definition("Widget", from_path="pkg/use.py")
        assert result["definitions"][0]["path"] == "pkg/core.py"

    def test_a_substring_of_another_name_is_not_a_definition(
        self, service: LanguageIntelligenceService, repository: Path
    ) -> None:
        (repository / "pkg" / "more.py").write_text("def widget_total_extra():\n    pass\n")
        CodeMapService(repository, SQLiteStore(repository), principal_id="local_user").build()
        paths = {row["path"] for row in service.find_definition("widget_total")["definitions"]}
        assert paths == {"pkg/core.py"}

    def test_an_unknown_name_says_so_rather_than_guessing(
        self, service: LanguageIntelligenceService
    ) -> None:
        result = service.find_definition("no_such_symbol")
        assert result["status"] == "success"
        assert result["count"] == 0
        assert "code_map_search" in result["note"]


class TestDiagnostics:
    def test_a_syntax_error_comes_back_with_its_coordinate(
        self, service: LanguageIntelligenceService
    ) -> None:
        result = service.diagnostics(["pkg/broken.py"])
        assert result["count"] == 1
        problem = result["diagnostics"][0]
        assert problem["path"] == "pkg/broken.py"
        assert problem["line"] == 1
        assert problem["severity"] == "error"
        assert problem["source"] == "python-ast"

    def test_a_clean_file_is_reported_as_checked(
        self, service: LanguageIntelligenceService
    ) -> None:
        result = service.diagnostics(["pkg/use.py"])
        assert result["count"] == 0
        assert result["checked"] == ["pkg/use.py"]

    def test_malformed_json_is_a_problem_too(
        self, service: LanguageIntelligenceService
    ) -> None:
        result = service.diagnostics(["pkg/data.json"])
        assert result["count"] == 1
        assert result["diagnostics"][0]["source"] == "json"

    def test_a_language_with_no_parser_is_unsupported_and_never_clean(
        self, service: LanguageIntelligenceService
    ) -> None:
        """The contract that makes this tool safe to trust.

        There is no TypeScript parser on this runtime. Reporting the file as
        having no problems would be a claim nothing established, so it is
        reported as not checked — and it is absent from `checked`, which is the
        list the tool's own description tells the model to read.
        """
        result = service.diagnostics(["pkg/ui.ts"])
        assert result["checked"] == []
        assert result["count"] == 0
        assert [item["path"] for item in result["unsupported"]] == ["pkg/ui.ts"]
        assert "not checked" in result["note"].lower()

    def test_a_missing_file_is_skipped_with_its_reason(
        self, service: LanguageIntelligenceService
    ) -> None:
        result = service.diagnostics(["pkg/nope.py"])
        assert result["skipped"] == [{"path": "pkg/nope.py", "reason": "file_not_found"}]

    def test_a_path_outside_the_repository_is_skipped_not_read(
        self, service: LanguageIntelligenceService
    ) -> None:
        result = service.diagnostics(["../../../etc/passwd"])
        assert [item["reason"] for item in result["skipped"]] == ["outside_repository"]
        assert result["checked"] == []

    def test_it_needs_at_least_one_path(self, service: LanguageIntelligenceService) -> None:
        assert service.diagnostics([])["error"]["type"] == "missing_argument:paths"

    def test_many_files_are_bounded_and_say_so(
        self, service: LanguageIntelligenceService, repository: Path
    ) -> None:
        from raiker.graph.language_service import MAX_DIAGNOSTIC_FILES

        paths = []
        for index in range(MAX_DIAGNOSTIC_FILES + 5):
            name = f"pkg/gen_{index}.py"
            (repository / name).write_text("x = 1\n")
            paths.append(name)
        result = service.diagnostics(paths)
        assert result["truncated"] is True
        assert len(result["checked"]) == MAX_DIAGNOSTIC_FILES


class TestGovernance:
    def test_every_tool_fails_closed_when_the_gate_is_off(self, repository: Path) -> None:
        """The gate is `language_intelligence`, and turning it off stops all three.

        An owner who says no writes a row, and that row wins over the shipped
        default — the same resolution the code map beside it keeps.
        """
        store = SQLiteStore(repository)
        now = utc_now()
        store.upsert_capability_gate_state(
            {
                "capability": "language_intelligence",
                "state": "disabled",
                "created_at": now,
                "updated_at": now,
            }
        )
        for result in (
            document_symbols(repository, "pkg/core.py", store=store, principal_id="local_user"),
            find_definition(repository, "Widget", store=store, principal_id="local_user"),
            diagnostics(repository, ["pkg/core.py"], store=store, principal_id="local_user"),
        ):
            assert result["status"] == "denied"
            assert result["error"]["type"] == "language_intelligence_gate_disabled"
            assert "Permissions" in result["error"]["message"]

    def test_it_is_not_the_code_map_gate(self, repository: Path) -> None:
        """One switch meaning two subsystems is the defect this codebase keeps finding.

        The code map *writes a derived index of the owner's machine*; these only
        parse a file `read_file` would already open. An owner must be able to
        have one without the other.
        """
        from raiker.graph.codemap_service import CAPABILITY as CODE_MAP_CAPABILITY
        from raiker.graph.language_service import CAPABILITY as LANGUAGE_CAPABILITY

        assert LANGUAGE_CAPABILITY != CODE_MAP_CAPABILITY

    def test_the_tools_are_registered_against_that_capability(self) -> None:
        from raiker.runtime.authority.router import CAPABILITY_GATE_MAP

        for tool in ("document_symbols", "find_definition", "diagnostics"):
            assert CAPABILITY_GATE_MAP[tool] == "language_intelligence"

    def test_they_are_read_shaped_and_need_no_approval(self) -> None:
        from raiker.models.tool_registry import TOOL_DEFINITIONS

        registry = {definition.name: definition for definition in TOOL_DEFINITIONS}
        for tool in ("document_symbols", "find_definition", "diagnostics"):
            assert registry[tool].read_shaped is True
            assert registry[tool].requires_approval is False
            assert registry[tool].model_exposed is True
