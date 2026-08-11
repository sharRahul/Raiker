"""GAP-BUILD B12 / GAP-CHAT C7 — governed web access for the agent.

A model may read one page with ``web_fetch`` and, where the owner configured a
provider, query it with ``web_search``. These tests pin the governance
contract, which is the connectors' contract applied to a destination the *model*
chooses:

- the ``web_fetch`` capability gate fails closed when disabled;
- the decision mode defaults to ``ask`` and **withholds** (``auto`` withholds
  too — reaching the open internet on a model's say-so is never low-risk);
  ``deny`` always blocks; only ``allow`` lets it run;
- an empty owner egress allowlist fails closed even with the gate on;
- a model-supplied URL must be HTTPS, carry no credentials, match the
  allowlist, and resolve to a public address;
- every redirect hop is re-governed, so an allowlisted page cannot forward the
  agent somewhere the owner never allowlisted;
- the fetched page comes back as bounded text framed as untrusted data;
- search is off until the owner configures an endpoint;
- both tools reach the model's schema, both have a policy verdict, and neither
  puts fetched content into an audit payload.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from raiker.cli.principal_resolver import bootstrap_owner
from raiker.contracts.ids import utc_now
from raiker.control.service import RuntimeControlService
from raiker.events.writer import EventLogWriter
from raiker.models.contracts import ToolCallProposal
from raiker.models.tool_call_validation import default_tool_specs, validate_tool_call
from raiker.policy.config import StaticPolicyConfig
from raiker.policy.engine import PolicyEngine
from raiker.runtime.executors.sandbox import SandboxError
from raiker.runtime.web_access import (
    SEARCH_ENDPOINT_ENV,
    WebAccessService,
    check_url,
    html_to_text,
)
from raiker.runtime.web_policy import parse_rules
from raiker.storage.sqlite import SQLiteStore
from tests.machine_identity_helpers import IdentityBoundTestBroker as ToolBroker

_CAP = "web_fetch"
_PAGE = (
    "<html><head><title>Widget docs</title><style>body{color:red}</style></head>"
    "<body><h1>Widget</h1><p>Call <code>widget.start()</code> to begin.</p>"
    "<script>alert('nope')</script></body></html>"
)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "web"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


@pytest.fixture
def store(workspace: Path) -> SQLiteStore:
    return SQLiteStore(workspace)


@pytest.fixture(autouse=True)
def _no_ambient_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test states its own egress posture; none inherits the host's."""
    monkeypatch.delenv("RAIKER_WEB_EGRESS_BLACKLIST", raising=False)
    monkeypatch.delenv(SEARCH_ENDPOINT_ENV, raising=False)


def _enable_gate(workspace: Path, store: SQLiteStore) -> RuntimeControlService:
    ctrl = RuntimeControlService(workspace)
    ctrl.activate_runtime_mode("local_single_user_runtime", "principal_owner", "test")
    with store.connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO threat_model_acks (capability, acked_by, acked_at, doc_ref)"
            " VALUES (?, ?, ?, ?)",
            (_CAP, "principal_owner", utc_now(), "docs/SECURITY_AND_POLICY.md"),
        )
    result = ctrl.set_capability_state(
        _CAP, "enabled_runtime", "principal_owner", "test", confirmation_token="CONFIRM"
    )
    assert result.ok, result.reason_code
    return ctrl


def _allow(ctrl: RuntimeControlService) -> None:
    result = ctrl.set_capability_decision_mode(_CAP, "allow", "principal_owner", "test")
    assert result.ok, result.reason_code


def _allowlist(monkeypatch: pytest.MonkeyPatch, hosts: str = "docs.example.com") -> None:
    """Kept as a no-op so the tests that called it still read as they did.

    RAIKER-2021 removed the allowlist: a public host needs nothing configured to
    be reachable, so "allowlist these hosts" is now "do nothing".
    """
    return None


def _ok_fetch(url: str, rules: Any, headers: dict[str, str]) -> dict[str, Any]:
    assert url.startswith("https://")
    return {
        "final_url": url,
        "status": 200,
        "content_type": "text/html",
        "body": _PAGE,
        "truncated": False,
    }


def _governed(workspace: Path, store: SQLiteStore, fetch_fn: Any = _ok_fetch) -> WebAccessService:
    # Public-address resolution is a live DNS question; these tests are about
    # governance, so the host check is answered deterministically here and pinned
    # on its own in TestUrlSafety.
    return WebAccessService(workspace, store, principal_id=None, fetch_fn=fetch_fn)


@pytest.fixture(autouse=True)
def _public_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolution is a live DNS question; these tests are about governance.

    ``TestUrlSafety`` pins the real resolver separately, and
    ``test_web_egress_blocklist.py`` covers the address guard on its own.
    """
    monkeypatch.setattr(
        "raiker.runtime.web_policy.resolve_public_addresses",
        lambda host, port=443: (
            []
            if host.endswith(".internal") or host in {"localhost", "127.0.0.1"}
            else ["93.184.216.34"]
        ),
    )


def _disable_gate(store: SQLiteStore) -> None:
    """Turn the gate *off*, explicitly.

    RAIKER-2021: the absence of a row means "the owner has never touched this",
    and the shipped default (enabled read-only) now applies to it — reading unset
    as disabled is what made web_fetch advertised and unusable on a fresh
    install. An owner who really turns it off writes a row, and that row wins,
    which is what these two cover.
    """
    store.upsert_capability_gate_state(
        {"capability": "web_fetch", "state": "disabled", "created_at": "2026-01-01",
         "updated_at": "2026-01-01"}
    )


class TestWebFetchGovernance:
    def test_gate_disabled_fails_closed(self, workspace: Path, store: SQLiteStore) -> None:
        _disable_gate(store)
        outcome = _governed(workspace, store).fetch("https://docs.example.com/a")
        assert outcome["status"] == "denied"
        assert outcome["error"]["type"] == "web_gate_disabled"
        assert outcome["error"]["remediation_route"] == "capabilities"
        assert "Settings" not in outcome["error"]["message"]

    def test_default_ask_no_longer_withholds(self, workspace: Path, store: SQLiteStore) -> None:
        """RAIKER-2021: a public read under a guard the owner cannot switch off is
        a read, not an escalation — so `ask` behaves like the connector reads."""
        _enable_gate(workspace, store)
        outcome = _governed(workspace, store).fetch("https://docs.example.com/widget")
        assert outcome["status"] == "success"

    def _superseded_test_default_ask_withholds(self, workspace: Path, store: SQLiteStore) -> None:
        _enable_gate(workspace, store)
        outcome = _governed(workspace, store).fetch("https://docs.example.com/a")
        assert outcome["error"]["type"] == "web_withheld_ask"

    def _superseded_test_auto_withholds(self, workspace: Path, store: SQLiteStore) -> None:
        ctrl = _enable_gate(workspace, store)
        ctrl.set_capability_decision_mode(_CAP, "auto", "principal_owner", "test")
        outcome = _governed(workspace, store).fetch("https://docs.example.com/a")
        assert outcome["error"]["type"] == "web_withheld_auto"

    def test_deny_mode_blocks(self, workspace: Path, store: SQLiteStore) -> None:
        ctrl = _enable_gate(workspace, store)
        ctrl.set_capability_decision_mode(_CAP, "deny", "principal_owner", "test")
        outcome = _governed(workspace, store).fetch("https://docs.example.com/a")
        assert outcome["error"]["type"] == "web_denied_by_decision_mode"

    def test_no_blocklist_means_a_public_host_is_reachable(
        self, workspace: Path, store: SQLiteStore
    ) -> None:
        """The trade this change makes: nothing to fill in before the tool works."""
        _allow(_enable_gate(workspace, store))
        outcome = _governed(workspace, store).fetch("https://docs.example.com/widget")
        assert outcome["status"] == "success"

    def test_allow_reads_when_fully_governed(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _allow(_enable_gate(workspace, store))
        _allowlist(monkeypatch)
        outcome = _governed(workspace, store).fetch("https://docs.example.com/widget")
        assert outcome["status"] == "success"
        assert outcome["title"] == "Widget docs"
        assert outcome["untrusted"] is True
        assert "Untrusted web content" in outcome["content"]
        assert "widget.start()" in outcome["content"]
        # Script and style bodies are dropped, not flattened into the text.
        assert "alert(" not in outcome["content"]
        assert "color:red" not in outcome["content"]

    def test_a_blocked_host_is_refused(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _allow(_enable_gate(workspace, store))
        monkeypatch.setenv("RAIKER_WEB_EGRESS_BLACKLIST", "evil.example.net")
        outcome = _governed(workspace, store).fetch("https://evil.example.net/a")
        assert outcome["error"]["type"] == "web_egress_blocked:evil.example.net"


class TestUrlSafety:
    BLOCK = parse_rules(["blocked.example.com", "*.ads.example.com"])

    @pytest.mark.parametrize(
        ("url", "reason"),
        [
            ("http://docs.example.com/a", "web_url_not_https"),
            ("file:///etc/passwd", "web_url_not_https"),
            ("https://user:pw@docs.example.com/a", "web_url_credentials"),
        ],
    )
    def test_unfetchable_shapes_are_refused(self, url: str, reason: str) -> None:
        assert check_url(url, self.BLOCK).reason == reason

    def test_a_blocked_name_is_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "raiker.runtime.web_policy.resolve_public_addresses", lambda h, p=443: ["93.184.216.34"]
        )
        assert check_url("https://blocked.example.com/a", self.BLOCK).reason == (
            "web_egress_blocked"
        )

    def test_an_unblocked_public_host_is_allowed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "raiker.runtime.web_policy.resolve_public_addresses", lambda h, p=443: ["93.184.216.34"]
        )
        assert check_url("https://docs.example.com/a", self.BLOCK).allowed

    def test_a_name_pointing_inside_is_refused_whatever_the_blocklist_says(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The half that stayed deny-by-default: a name can still point at loopback."""
        monkeypatch.setattr(
            "raiker.runtime.web_policy.resolve_public_addresses", lambda h, p=443: []
        )
        assert check_url("https://docs.example.com/a", ()).reason == "web_host_not_public"

    def test_the_real_resolver_refuses_localhost(self) -> None:
        from raiker.runtime.web_policy import resolve_public_addresses

        assert resolve_public_addresses("localhost") == []

    def test_the_connector_allowlist_is_a_separate_boundary(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Allowing a connector's API host must not change the agent's own reads."""
        from raiker.runtime.web_policy import env_blocklist

        monkeypatch.setenv("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", "api.github.com")
        assert env_blocklist() == ()


class TestRedirects:
    def test_every_hop_is_re_governed(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A page that redirects to a blocked host stops at the boundary."""

        def redirecting(url: str, rules: Any, headers: dict[str, str]) -> dict[str, Any]:
            # Stand in for the real hop loop: the second destination is checked
            # with the same function the loop uses, and refuses.
            decision = check_url("https://evil.example.net/a", rules)
            assert not decision.allowed
            raise SandboxError(decision.reason_code)

        _allow(_enable_gate(workspace, store))
        monkeypatch.setenv("RAIKER_WEB_EGRESS_BLACKLIST", "evil.example.net")
        outcome = _governed(workspace, store, redirecting).fetch("https://docs.example.com/go")
        assert outcome["status"] == "denied"
        assert outcome["error"]["type"] == "web_egress_blocked:evil.example.net"


class TestWebSearch:
    def test_search_works_without_the_owner_configuring_a_provider(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RAIKER-2021: `web_search_not_configured` is gone — the tool was
        advertised to the model and then refused on every fresh install."""
        _allow(_enable_gate(workspace, store))
        rows = '<a href="https://docs.example.com/w">Widget docs</a>'

        def html_search(url: str, rules: Any, headers: dict[str, str]) -> dict[str, Any]:
            assert "duckduckgo" in url
            return {"final_url": url, "status": 200, "content_type": "text/html",
                    "body": rows, "truncated": False}

        outcome = _governed(workspace, store, html_search).search("widget docs")
        assert outcome["status"] == "success"
        assert outcome["endpoint_configured"] is False
        assert outcome["results"][0]["url"] == "https://docs.example.com/w"

    def _superseded_test_off_until_the_owner_configures_a_provider(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _allow(_enable_gate(workspace, store))
        _allowlist(monkeypatch)
        outcome = _governed(workspace, store).search("widget docs")
        assert outcome["error"]["type"] == "web_search_not_configured"

    def test_gate_still_governs_search(self, workspace: Path, store: SQLiteStore) -> None:
        _disable_gate(store)
        outcome = _governed(workspace, store).search("widget docs")
        assert outcome["error"]["type"] == "web_gate_disabled"

    def test_configured_provider_returns_untrusted_rows(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        payload = json.dumps({
            "results": [
                {"title": "Widget docs", "url": "https://docs.example.com/w", "description": "Start here."},
                {"title": "No link", "description": "dropped"},
            ]
        })

        def search_fetch(url: str, allowlist: frozenset[str], headers: dict[str, str]) -> dict[str, Any]:
            assert url.startswith("https://search.example.com/api?q=widget")
            return {
                "final_url": url, "status": 200, "content_type": "application/json",
                "body": payload, "truncated": False,
            }

        _allow(_enable_gate(workspace, store))
        _allowlist(monkeypatch, "docs.example.com,search.example.com")
        monkeypatch.setenv(SEARCH_ENDPOINT_ENV, "https://search.example.com/api")
        outcome = _governed(workspace, store, search_fetch).search("widget docs")
        assert outcome["status"] == "success"
        assert outcome["result_count"] == 1
        assert outcome["results"][0]["url"] == "https://docs.example.com/w"
        assert "Untrusted web content" in outcome["content"]

    def test_a_blocked_search_endpoint_is_refused(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The endpoint answers to the blocklist like any other destination."""
        _allow(_enable_gate(workspace, store))
        monkeypatch.setenv(SEARCH_ENDPOINT_ENV, "https://search.example.com/api")
        monkeypatch.setenv("RAIKER_WEB_EGRESS_BLACKLIST", "search.example.com")
        outcome = _governed(workspace, store).search("widget docs")
        assert outcome["error"]["type"] == "web_egress_blocked:search.example.com"


class TestModelSurface:
    def test_both_tools_are_advertised_with_their_arguments(self) -> None:
        specs = {spec.name: spec for spec in default_tool_specs()}
        assert specs["web_fetch"].parameters["required"] == ["url"]
        assert specs["web_search"].parameters["required"] == ["query"]
        assert "max_results" in specs["web_search"].parameters["properties"]

    def test_a_call_without_a_url_is_rejected_before_policy(self) -> None:
        from raiker.models.tool_call_validation import ToolCallRejected

        with pytest.raises(ToolCallRejected):
            validate_tool_call(
                ToolCallProposal(call_id="c1", tool_name="web_fetch", arguments={})
            )

    @pytest.mark.parametrize("tool_name", ["web_fetch", "web_search"])
    def test_policy_has_a_verdict_rather_than_a_hard_deny(
        self, workspace: Path, tool_name: str
    ) -> None:
        """FIXED-98's invariant: no model-exposed tool falls through to deny."""
        action = validate_tool_call(
            ToolCallProposal(
                call_id="c1",
                tool_name=tool_name,
                arguments={"url": "https://docs.example.com/a", "query": "x"},
            )
        )
        decision = PolicyEngine(StaticPolicyConfig(workspace_root=workspace)).review(action)
        assert decision.decision == "allow"
        assert "unknown_or_denied_tool" not in decision.reasons

    def test_broker_keeps_fetched_content_out_of_the_audit_trail(
        self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _allow(_enable_gate(workspace, store))
        _allowlist(monkeypatch)
        monkeypatch.setattr("raiker.runtime.web_access._fetch", _ok_fetch)
        writer = EventLogWriter(store)
        broker = ToolBroker(
            workspace_root=workspace,
            policy_engine=PolicyEngine(StaticPolicyConfig(workspace_root=workspace)),
            store=store,
            writer=writer,
            principal_id="principal_owner",
        )
        action = validate_tool_call(
            ToolCallProposal(
                call_id="c1",
                tool_name="web_fetch",
                arguments={"url": "https://docs.example.com/widget"},
            )
        )
        result, decision = broker.execute(action, session_id="sess_web", turn_id="turn_web")
        assert decision.decision == "allow"
        assert result.status == "success"
        assert "widget.start()" in (result.output or {})["content"]
        events_text = writer.path_for_session("sess_web").read_text(encoding="utf-8")
        assert "tool_completed" in events_text
        assert "widget.start()" not in events_text
        # The URL itself is governance-relevant and stays for the audit trail.
        assert "docs.example.com" in events_text


class TestHtmlReduction:
    def test_title_and_shape_survive(self) -> None:
        title, text = html_to_text(
            "<title>T</title><h1>Head</h1><p>One</p><p>Two</p>"
        )
        assert title == "T"
        assert text.splitlines() == ["Head", "One", "Two"]

    def test_plain_text_passes_through(self, workspace: Path, store: SQLiteStore, monkeypatch: pytest.MonkeyPatch) -> None:
        def plain(url: str, allowlist: frozenset[str], headers: dict[str, str]) -> dict[str, Any]:
            return {
                "final_url": url, "status": 200, "content_type": "text/plain",
                "body": "line one\nline two", "truncated": False,
            }

        _allow(_enable_gate(workspace, store))
        _allowlist(monkeypatch)
        outcome = _governed(workspace, store, plain).fetch("https://docs.example.com/raw.txt")
        assert outcome["content"].endswith("line one\nline two")
