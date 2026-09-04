"""BUG-226 — the `http` hook handler, behind a named, revocable egress grant.

[The Claude Code hooks reference](https://code.claude.com/docs/en/hooks)
documents five handler types. Raiker shipped three and refused `http`,
`mcp_tool` and `agent` at parse time — for a reason rather than an omission:
**a hook has no implicit network access.** The entry that raised this said
`http` would follow "only once a hook can be given a named, revocable egress
grant". These tests are that grant's contract:

* **Empty by default.** A workspace that never set the variable grants nothing,
  so adding an `http` rule cannot on its own make a request leave the machine.
* **Named and revocable in one place.** Clearing the variable revokes every
  `http` rule at once, without editing a hooks file — which is what revocable
  has to mean when rules live in five files across four scopes.
* **A refusal is stated, never silent.** The rule parses, matches, and refuses
  with the host in the reason, and the Hooks page reads the same fact.
* **A hook still cannot permit anything.** Authority is the owner's opt-in and
  `combine` honours only `deny` and `ask`, so a remote responder can make an
  action stricter and can never make one allowed.
* **It reveals no more than a `prompt` handler already does** — the same
  bounded, redacted event body, from the same function.

`mcp_tool` and `agent` stay refused, and that is asserted here too: closing one
of three must not quietly open the other two.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from raiker.hooks.contracts import HANDLER_TYPES, HookConfigError, HookHandler, HookInput
from raiker.hooks.decision import HandlerDecision, combine
from raiker.hooks.handlers.http import (
    HttpHookError,
    egress_granted,
    event_body,
    hook_egress_allowlist,
    run_http,
)

_URL = "https://hooks.internal.example.com/raiker"


def _handler(**overrides: Any) -> HookHandler:
    return HookHandler(
        id=overrides.pop("id", "notify"),
        type="http",
        url=overrides.pop("url", _URL),
        timeout_ms=overrides.pop("timeout_ms", 5000),
        decision_authority=overrides.pop("decision_authority", False),
    )


def _input() -> HookInput:
    return HookInput(
        event_name="PreToolUse",
        tool_name="shell",
        tool_input={"command": "ls"},
        context={"api_key": "sk-live-should-never-travel", "_model": "internal-only"},
    )


class _Response:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self._body = body
        self.status = status

    def read(self, _limit: int) -> bytes:
        return self._body

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


def _stub_urlopen(
    monkeypatch: pytest.MonkeyPatch, body: str, *, status: int = 200
) -> list[dict[str, Any]]:
    """Capture what the handler sent, and answer with *body*."""
    import urllib.request

    sent: list[dict[str, Any]] = []

    def fake_urlopen(request: Any, timeout: float = 0) -> _Response:
        sent.append(
            {
                "url": request.full_url,
                "data": request.data.decode("utf-8"),
                "headers": dict(request.headers),
            }
        )
        return _Response(body.encode("utf-8"), status)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return sent


class TestTheGrantIsTheAuthorization:
    def test_the_allowlist_is_empty_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("RAIKER_HOOK_EGRESS_ALLOWLIST", raising=False)
        assert hook_egress_allowlist() == frozenset()
        assert egress_granted(_URL) is False

    def test_a_rule_without_a_grant_refuses_and_names_the_host(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("RAIKER_HOOK_EGRESS_ALLOWLIST", raising=False)
        with pytest.raises(HttpHookError) as raised:
            run_http(_handler(), _input())
        assert "hooks.internal.example.com" in str(raised.value)

    def test_a_granted_host_is_reached(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RAIKER_HOOK_EGRESS_ALLOWLIST", "hooks.internal.example.com")
        sent = _stub_urlopen(monkeypatch, json.dumps({"decision": "no_decision"}))

        run_http(_handler(), _input())

        assert sent and sent[0]["url"] == _URL

    def test_a_glob_grants_a_port_range_the_way_the_channel_allowlist_does(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("RAIKER_HOOK_EGRESS_ALLOWLIST", "127.0.0.1:*")
        assert egress_granted("http://127.0.0.1:9099/hook") is True
        assert egress_granted("http://127.0.0.2:9099/hook") is False

    def test_clearing_the_variable_revokes_every_rule_at_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("RAIKER_HOOK_EGRESS_ALLOWLIST", "hooks.internal.example.com")
        assert egress_granted(_URL) is True
        monkeypatch.setenv("RAIKER_HOOK_EGRESS_ALLOWLIST", "")
        assert egress_granted(_URL) is False

    def test_a_non_http_scheme_is_never_granted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("RAIKER_HOOK_EGRESS_ALLOWLIST", "*")
        assert egress_granted("file:///etc/passwd") is False
        assert egress_granted("ftp://host/x") is False
        assert egress_granted(None) is False


class TestWhatLeaves:
    def test_it_reveals_no_more_than_a_prompt_handler(self) -> None:
        """The same function builds both, so the rule cannot drift apart."""
        from raiker.hooks.handlers.prompt import _event_data

        assert _event_data(_input()) == event_body(_input(), limit=12_000)

    def test_a_credential_in_the_event_is_redacted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("RAIKER_HOOK_EGRESS_ALLOWLIST", "hooks.internal.example.com")
        sent = _stub_urlopen(monkeypatch, json.dumps({"decision": "no_decision"}))

        run_http(_handler(), _input())

        assert "sk-live-should-never-travel" not in sent[0]["data"]

    def test_the_runtimes_own_private_context_never_leaves(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("RAIKER_HOOK_EGRESS_ALLOWLIST", "hooks.internal.example.com")
        sent = _stub_urlopen(monkeypatch, json.dumps({"decision": "no_decision"}))

        run_http(_handler(), _input())

        assert "internal-only" not in sent[0]["data"]

    def test_the_request_carries_no_identity(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RAIKER_HOOK_EGRESS_ALLOWLIST", "hooks.internal.example.com")
        sent = _stub_urlopen(monkeypatch, json.dumps({"decision": "no_decision"}))

        run_http(_handler(), _input())

        headers = {key.lower(): value for key, value in sent[0]["headers"].items()}
        assert "authorization" not in headers
        assert "cookie" not in headers


class TestWhatComesBack:
    def test_a_decision_object_is_read(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RAIKER_HOOK_EGRESS_ALLOWLIST", "hooks.internal.example.com")
        _stub_urlopen(
            monkeypatch,
            json.dumps({"decision": "deny", "decision_reason": "change freeze"}),
        )
        output = run_http(_handler(decision_authority=True), _input())

        assert output.decision == "deny"
        assert output.decision_reason == "change freeze"

    def test_an_answer_that_is_not_a_decision_decides_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("RAIKER_HOOK_EGRESS_ALLOWLIST", "hooks.internal.example.com")
        _stub_urlopen(monkeypatch, "thanks")
        assert run_http(_handler(), _input()).decision == "no_decision"

    def test_an_outage_is_not_a_policy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A 500 must not become a deny: inferring one would let a responder's
        outage block every action the rule matches."""
        import urllib.error
        import urllib.request

        monkeypatch.setenv("RAIKER_HOOK_EGRESS_ALLOWLIST", "hooks.internal.example.com")

        def fake_urlopen(request: Any, timeout: float = 0) -> None:
            raise urllib.error.HTTPError(_URL, 500, "boom", {}, None)  # type: ignore[arg-type]

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        with pytest.raises(HttpHookError) as raised:
            run_http(_handler(decision_authority=True), _input())
        assert "hook_http_status:500" in str(raised.value)

    def test_a_remote_responder_can_never_permit_anything(self) -> None:
        """`combine` honours deny and ask; an `allow` from any handler — remote
        or local — is simply not a decision the aggregate can reach."""
        assert combine([HandlerDecision("project", "allow", True)]) == "no_decision"
        assert combine([HandlerDecision("project", "deny", True)]) == "deny"

    def test_without_the_owners_opt_in_it_is_advisory(self) -> None:
        assert combine([HandlerDecision("project", "deny", False)]) == "no_decision"


class TestTheOtherTwoStayRefused:
    def test_http_is_a_handler_type_and_the_other_two_are_not(self) -> None:
        assert "http" in HANDLER_TYPES
        assert "mcp_tool" not in HANDLER_TYPES
        assert "agent" not in HANDLER_TYPES

    @pytest.mark.parametrize("handler_type", ["mcp_tool", "agent"])
    def test_a_rule_naming_one_is_refused_at_parse_time(self, handler_type: str) -> None:
        with pytest.raises(HookConfigError) as raised:
            HookHandler(id="x", type=handler_type)
        assert "unsupported_handler_type" in str(raised.value)

    def test_an_http_handler_without_a_url_is_refused_at_parse_time(self) -> None:
        with pytest.raises(HookConfigError) as raised:
            HookHandler(id="x", type="http")
        assert "http_handler_requires_url" in str(raised.value)

    def test_an_http_handler_with_a_file_url_is_refused_at_parse_time(self) -> None:
        with pytest.raises(HookConfigError) as raised:
            HookHandler(id="x", type="http", url="file:///etc/passwd")
        assert "http_handler_requires_http_url" in str(raised.value)


class TestTheRuleReadsTheGrantLive:
    def test_the_hooks_page_reports_a_rule_the_grant_does_not_cover(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from raiker.cli.principal_resolver import bootstrap_owner
        from raiker.control.dashboard import DashboardService

        bootstrap_owner("owner", "Owner", workspace_root=tmp_path)
        (tmp_path / "config").mkdir(exist_ok=True)
        (tmp_path / "config" / "hooks.json").write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "hooks": {
                        "PreToolUse": [
                            {
                                "matcher": "shell",
                                "handlers": [
                                    {"id": "notify", "type": "http", "url": _URL}
                                ],
                            }
                        ]
                    },
                }
            )
        )

        monkeypatch.delenv("RAIKER_HOOK_EGRESS_ALLOWLIST", raising=False)
        refused = DashboardService(tmp_path).list_hooks()
        handler = refused["rules"][0]["handlers"][0]
        assert handler["target"] == _URL
        assert handler["available"] is False
        assert handler["unavailable_reason"] == "egress_not_granted"

        # Revocable without touching the file, so the page has to read it live.
        monkeypatch.setenv("RAIKER_HOOK_EGRESS_ALLOWLIST", "hooks.internal.example.com")
        granted = DashboardService(tmp_path).list_hooks()
        assert granted["rules"][0]["handlers"][0]["available"] is True
