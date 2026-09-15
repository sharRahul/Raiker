"""One read catalogue, shared everywhere, authorised nowhere.

The claim under test is deliberately two-sided, because half of it is the part
that keeps being lost:

> **A web capability may be globally discoverable without being globally
> authorised. Tool visibility never grants network authority.**

The first half fails when a surface derives its own list and a capability
quietly disappears — most often on a Project change, which has nothing to do
with whether Raiker can read a web page. The second half fails when someone
reasons "it is in the core projection, so it must be allowed", and a projection
change becomes an authority change without anyone deciding one.

So these tests pin the catalogue *and* the gate, and specifically pin that
moving a tool into the projected core moves nothing at all.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import utc_now
from raiker.control.service import RuntimeControlService
from raiker.models.tool_projection import ALWAYS_PROJECTED
from raiker.models.tool_registry import DELEGABLE_TOOL_NAMES, MODEL_EXPOSED_TOOLS, definition
from raiker.runtime.authority.router import CAPABILITY_GATE_MAP
from raiker.runtime.read_capabilities import (
    ADMINISTRATIVE_SURFACES,
    AGENTIC_SURFACES,
    BLOCKED,
    DELEGABLE_READ_CAPABILITIES,
    EXTERNAL_READ_CAPABILITIES,
    GLOBAL_READ_CAPABILITIES,
    INTERACTIVE_CAPABILITIES,
    READY,
    read_capabilities_for,
    web_read_readiness,
)
from raiker.runtime.web_access import SEARCH_ENDPOINT_ENV, WebAccessService
from raiker.storage.sqlite import SQLiteStore

_CAP = "web_fetch"

_PAGE = (
    "<html><head><title>Widget report</title>"
    '<meta name="description" content="How the widget works.">'
    '<link rel="canonical" href="https://docs.example.com/report">'
    '<script type="application/ld+json">{"@type":"Article","name":"Widget"}</script>'
    "<style>body{color:red}</style></head>"
    "<body><h1>Widget</h1><p>Call <code>widget.start()</code> to begin, and read the "
    "surrounding chapter for the parameters it takes and the errors it raises.</p>"
    '<a href="/next">Next chapter</a><a href="https://other.example.com/x">Elsewhere</a>'
    '<a href="javascript:alert(1)">Nope</a>'
    "<table><tr><th>Name</th><th>Default</th></tr>"
    "<tr><td>retries</td><td>3</td></tr></table>"
    "<script>alert('nope')</script></body></html>"
)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "read"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def store(workspace: Path) -> SQLiteStore:
    return SQLiteStore(workspace)


@pytest.fixture(autouse=True)
def _no_ambient_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAIKER_WEB_EGRESS_BLACKLIST", raising=False)
    monkeypatch.delenv(SEARCH_ENDPOINT_ENV, raising=False)
    monkeypatch.setattr(
        "raiker.runtime.web_policy.resolve_public_addresses",
        lambda host, port=443: ["93.184.216.34"],
    )


def _enable_gate(workspace: Path, store: SQLiteStore) -> RuntimeControlService:
    ctrl = RuntimeControlService(workspace)
    ctrl.activate_runtime_mode("local_single_user_runtime", "principal_owner", "test")
    with store.connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref)"
            " VALUES (?, ?, ?, ?)",
            (_CAP, "principal_owner", utc_now(), "docs/architecture/SECURITY_AND_POLICY.md"),
        )
    assert ctrl.set_capability_state(
        _CAP, "enabled_runtime", "principal_owner", "test", confirmation_token="CONFIRM"
    ).ok
    return ctrl


def _disable_gate(store: SQLiteStore) -> None:
    store.upsert_capability_gate_state(
        {
            "capability": _CAP,
            "state": "disabled",
            "created_at": "2026-01-01",
            "updated_at": "2026-01-01",
        }
    )


def _page(url: str, rules: Any, headers: dict[str, str]) -> dict[str, Any]:
    assert url.startswith("https://")
    return {
        "final_url": url,
        "status": 200,
        "content_type": "text/html",
        "body": _PAGE,
        "truncated": False,
    }


class TestSurfaceParity:
    """Every model-backed surface sees the same catalogue."""

    @pytest.mark.parametrize(
        "surface", ["chat", "build", "design", "tasks", "schedule", "agent"]
    )
    def test_every_agentic_surface_receives_the_whole_read_set(self, surface: str) -> None:
        assert read_capabilities_for(surface) == GLOBAL_READ_CAPABILITIES
        for tool in ("web_search", "web_fetch", "web_extract", "weather_lookup"):
            assert tool in read_capabilities_for(surface)

    def test_a_subagent_receives_only_the_delegable_subset(self) -> None:
        """A bounded delegation must not widen what leaves the machine."""
        delegated = read_capabilities_for("subagent")
        assert delegated == DELEGABLE_READ_CAPABILITIES
        for tool in EXTERNAL_READ_CAPABILITIES:
            assert tool not in delegated
        # And the registry agrees, so the two cannot drift apart.
        for tool in delegated:
            assert tool in DELEGABLE_TOOL_NAMES

    @pytest.mark.parametrize("surface", ADMINISTRATIVE_SURFACES)
    def test_administrative_pages_receive_no_agentic_read_catalogue(
        self, surface: str
    ) -> None:
        """Parity applies to work surfaces; it is not a reason to add composers."""
        assert read_capabilities_for(surface) == ()

    def test_an_unknown_surface_gets_nothing_rather_than_everything(self) -> None:
        assert read_capabilities_for("not-a-surface") == ()
        assert read_capabilities_for("") == ()

    def test_the_catalogue_is_not_keyed_by_project(self) -> None:
        """WEB-DECISION-07 — a Project is work context, not a tool inventory.

        Asserted on the signature rather than on a lookup, because that is the
        thing that makes the property structural: a resolver with nowhere to put
        a project id cannot return a different catalogue for one.
        """
        import inspect

        parameters = inspect.signature(read_capabilities_for).parameters
        assert list(parameters) == ["surface"]
        # And the readiness read, which does take an owner, takes no project.
        assert "project" not in inspect.signature(web_read_readiness).parameters

    def test_the_core_projection_carries_the_external_reads(self) -> None:
        for tool in EXTERNAL_READ_CAPABILITIES:
            assert tool in ALWAYS_PROJECTED
            assert tool in MODEL_EXPOSED_TOOLS


class TestProjectionGrantsNothing:
    """The half of the claim that keeps being lost."""

    @pytest.mark.parametrize("tool", ["web_fetch", "web_extract", "weather_lookup"])
    def test_a_projected_tool_still_fails_closed_when_the_gate_is_off(
        self, workspace: Path, store: SQLiteStore, tool: str
    ) -> None:
        _disable_gate(store)
        service = WebAccessService(workspace, store, principal_id="principal_owner", fetch_fn=_page)
        if tool == "web_fetch":
            outcome = service.fetch("https://docs.example.com/report")
        elif tool == "web_extract":
            outcome = service.extract("https://docs.example.com/report")
        else:
            from raiker.runtime.weather import WeatherService

            outcome = WeatherService(
                workspace, store, principal_id="principal_owner", fetch_fn=_page
            ).lookup(location="Edinburgh")

        assert outcome["status"] == "denied"
        assert outcome["error"]["type"] == "web_gate_disabled"

    def test_every_read_tool_answers_to_a_capability_gate(self) -> None:
        for tool in EXTERNAL_READ_CAPABILITIES:
            spec = definition(tool)
            assert spec is not None, tool
            assert spec.capability == "web_fetch", tool
            assert CAPABILITY_GATE_MAP.get(tool) == "web_fetch", tool

    def test_the_interactive_class_is_not_in_the_read_set(self) -> None:
        """`web_fetch` being on by default must not imply a browser."""
        for capability in INTERACTIVE_CAPABILITIES:
            assert capability not in GLOBAL_READ_CAPABILITIES
            assert capability not in ALWAYS_PROJECTED

    def test_discovering_a_tool_returns_a_schema_and_nothing_else(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        """A search that returned a tool grants precisely nothing."""
        from raiker.models.tool_projection import search_tools

        _disable_gate(store)
        found = search_tools("read a page and run a command")
        tools = found["tools"]
        assert isinstance(tools, list) and tools
        # What comes back is schemas — name, description, parameters — and
        # nothing that could be an authorisation.
        for spec in tools:
            assert set(spec) <= {"name", "description", "parameters", "type", "function"}

        # The gate is untouched by that search, and the executor still refuses.
        # Discovery and authority are different systems, and these are the lines
        # that prove they stayed that way.
        outcome = WebAccessService(
            workspace, store, principal_id="principal_owner", fetch_fn=_page
        ).extract("https://docs.example.com/report")
        assert outcome["status"] == "denied"
        assert outcome["error"]["type"] == "web_gate_disabled"


class TestReadiness:
    """Readiness and authority are separate fields, not one grey row."""

    def test_a_permitted_capability_reads_ready(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        _enable_gate(workspace, store)
        rows = {
            row.tool: row for row in web_read_readiness(workspace, store, "principal_owner")
        }
        assert set(rows) == {"web_fetch", "web_search", "web_extract", "weather_lookup"}
        for row in rows.values():
            assert row.available is True
            assert row.ready is True
            assert row.state == READY
            assert row.checked_at

    def test_a_disabled_gate_reads_blocked_rather_than_unavailable(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        """Blocked and unavailable send the owner to different screens."""
        _disable_gate(store)
        rows = {
            row.tool: row for row in web_read_readiness(workspace, store, "principal_owner")
        }
        for row in rows.values():
            assert row.available is True  # the build has it; it is not missing
            assert row.ready is False
            assert row.state == BLOCKED
            assert row.remediation_route == "capabilities"

    def test_deny_mode_reads_blocked_too(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        ctrl = _enable_gate(workspace, store)
        assert ctrl.set_capability_decision_mode(
            _CAP, "deny", "principal_owner", "test"
        ).ok
        rows = {
            row.tool: row for row in web_read_readiness(workspace, store, "principal_owner")
        }
        assert rows["web_search"].state == BLOCKED
        assert rows["web_search"].reason_code == "web_denied_by_decision_mode"

    def test_search_names_its_provider(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _enable_gate(workspace, store)
        rows = {
            row.tool: row for row in web_read_readiness(workspace, store, "principal_owner")
        }
        assert rows["web_search"].provider == "built-in default"

        monkeypatch.setenv(SEARCH_ENDPOINT_ENV, "https://search.example.com/api")
        rows = {
            row.tool: row for row in web_read_readiness(workspace, store, "principal_owner")
        }
        assert rows["web_search"].provider == "owner-configured endpoint"

    def test_readiness_serialises_without_empty_fields(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        _enable_gate(workspace, store)
        payload = web_read_readiness(workspace, store, "principal_owner")[0].to_dict()
        assert payload["state"] == READY
        assert "reason_code" not in payload


class TestWebExtract:
    """A parser over the bounded fetch, never a second client."""

    def _service(self, workspace: Path, store: SQLiteStore) -> WebAccessService:
        _enable_gate(workspace, store)
        return WebAccessService(
            workspace, store, principal_id="principal_owner", fetch_fn=_page
        )

    def test_main_content_uses_the_same_safe_fetch_boundary(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        result = self._service(workspace, store).extract(
            "https://docs.example.com/report", mode="main_content"
        )
        assert result["status"] == "success"
        assert result["untrusted"] is True
        assert "widget.start()" in result["content"]
        assert result["final_url"] == "https://docs.example.com/report"
        assert result["fetched_at"].endswith("Z")

    def test_static_extraction_never_carries_page_script(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        result = self._service(workspace, store).extract(
            "https://docs.example.com/report", mode="main_content"
        )
        assert "alert(" not in result["content"]
        assert "color:red" not in result["content"]

    def test_links_are_resolved_bounded_and_source_preserving(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        result = self._service(workspace, store).extract(
            "https://docs.example.com/report", mode="links"
        )
        urls = [link["url"] for link in result["links"]]
        assert "https://docs.example.com/next" in urls
        assert "https://other.example.com/x" in urls
        # A `javascript:` href is not a destination anything may follow, and
        # returning one invites a later caller to try.
        assert not any(url.startswith("javascript:") for url in urls)
        assert result["final_url"] == "https://docs.example.com/report"

    def test_link_extraction_is_capped_and_says_so(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        from raiker.runtime.web_extract import MAX_LINKS

        many = "<html><body>" + "".join(
            f'<a href="/p{index}">p{index}</a>' for index in range(MAX_LINKS + 25)
        ) + "</body></html>"

        def _many(url: str, rules: Any, headers: dict[str, str]) -> dict[str, Any]:
            return {
                "final_url": url, "status": 200, "content_type": "text/html",
                "body": many, "truncated": False,
            }

        _enable_gate(workspace, store)
        result = WebAccessService(
            workspace, store, principal_id="principal_owner", fetch_fn=_many
        ).extract("https://docs.example.com/index", mode="links")

        assert result["link_count"] == MAX_LINKS
        assert result["truncation"]["truncated"] is True
        assert f"links_capped_at_{MAX_LINKS}" in result["truncation"]["notes"]

    def test_tables_come_back_as_bounded_rows(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        result = self._service(workspace, store).extract(
            "https://docs.example.com/report", mode="tables"
        )
        assert result["tables"] == [[["Name", "Default"], ["retries", "3"]]]

    def test_metadata_and_structured_data_are_read_not_inferred(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        service = self._service(workspace, store)
        meta = service.extract("https://docs.example.com/report", mode="metadata")
        assert meta["metadata"]["description"] == "How the widget works."
        assert meta["metadata"]["canonical_url"] == "https://docs.example.com/report"

        structured = service.extract(
            "https://docs.example.com/report", mode="structured_data"
        )
        assert structured["structured_data"] == [{"@type": "Article", "name": "Widget"}]

    def test_an_unknown_mode_is_refused_by_name(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        result = self._service(workspace, store).extract(
            "https://docs.example.com/report", mode="everything"
        )
        assert result["status"] == "failed"
        assert result["error"]["type"] == "web_extract_unknown_mode:everything"

    def test_a_rejected_url_never_reaches_the_parser(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        result = self._service(workspace, store).extract("http://docs.example.com/report")
        assert result["status"] == "denied"
        assert result["error"]["type"] == "web_url_not_https"


class TestBrowserEscalation:
    """A typed statement about a page, not a request for authority."""

    def test_a_browser_rendered_page_returns_static_content_insufficient(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        shell = (
            "<html><head><title>App</title></head><body><div id='root'></div>"
            "<script src='/bundle.js'></script></body></html>"
        )

        def _shell(url: str, rules: Any, headers: dict[str, str]) -> dict[str, Any]:
            return {
                "final_url": url, "status": 200, "content_type": "text/html",
                "body": shell, "truncated": False,
            }

        _enable_gate(workspace, store)
        result = WebAccessService(
            workspace, store, principal_id="principal_owner", fetch_fn=_shell
        ).extract("https://app.example.com/", mode="main_content")

        insufficient = result["static_content_insufficient"]
        assert insufficient["reason_code"] == "static_content_insufficient"
        assert "built in the browser" in insufficient["detail"]
        # The sentence that has to be there: this result authorises nothing.
        assert "does not authorise one" in insufficient["browser_escalation"]

    def test_no_browser_capability_is_implied_by_web_fetch_being_on(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        _enable_gate(workspace, store)
        rows = {row.tool for row in web_read_readiness(workspace, store, "principal_owner")}
        assert "browser_automation" not in rows
        assert "browser_automation" not in MODEL_EXPOSED_TOOLS


class TestDesignIntegration:
    """Design researches through the read set; the image model does not."""

    def test_design_is_a_real_prompt_surface(self) -> None:
        from raiker.contracts.models import PROMPT_SURFACES, normalize_prompt_surface

        assert "design" in PROMPT_SURFACES
        assert normalize_prompt_surface("design") == "design"

    def test_a_design_turn_gets_the_research_protocol_and_the_same_tools(self) -> None:
        from raiker.runtime.orchestrator import _system_messages

        messages = _system_messages("design")
        assert len(messages) == 2
        assert "researching visual references" in messages[1]
        # It is told to read rather than recall, which is the whole difference
        # between a reference and a plausible sentence about one.
        assert "Do not describe a reference from memory" in messages[1]

    def test_image_generation_never_receives_a_web_or_browser_capability(self) -> None:
        """The arrow that is deliberately absent from the architecture."""
        import inspect

        from raiker.runtime.executors import tier2_image

        source = inspect.getsource(tier2_image)
        for forbidden in ("web_fetch", "web_search", "web_extract", "browser"):
            assert forbidden not in source

    def test_the_image_tool_answers_to_its_own_gate_not_the_web_one(self) -> None:
        from raiker.runtime.executors import REAL_EXECUTOR_CAPABILITIES

        assert "image_generation" in REAL_EXECUTOR_CAPABILITIES
        assert CAPABILITY_GATE_MAP.get("image_generation", "image_generation") != "web_fetch"


class TestCatalogueShape:
    def test_the_agentic_surface_list_and_the_administrative_one_do_not_overlap(
        self,
    ) -> None:
        assert not set(AGENTIC_SURFACES) & set(ADMINISTRATIVE_SURFACES)

    def test_the_api_answers_with_the_same_contract(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        """The page and the runtime must not derive the catalogue separately."""
        _enable_gate(workspace, store)
        payload = {
            "capabilities": list(GLOBAL_READ_CAPABILITIES),
            "surfaces": {
                surface: list(read_capabilities_for(surface)) for surface in AGENTIC_SURFACES
            },
        }
        assert json.loads(json.dumps(payload))["surfaces"]["chat"] == list(
            GLOBAL_READ_CAPABILITIES
        )
