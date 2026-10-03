"""UX-MCP-02 and UX-MCP-03 — an MCP server's reach, stated before activation.

The preview is read from the code that decides each fact — the stdio launcher's
constructed environment, the endpoint policy, the client's own capabilities —
so these tests hold the preview to that code rather than to a sentence.
"""

from __future__ import annotations

import pytest

from raiker.control.dashboard_parts.extensions import _mcp_provenance, mcp_scope
from raiker.runtime.executors.mcp import mcp_stdio_env


def test_a_local_server_is_said_to_get_exactly_the_environment_it_is_started_with(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-not-for-servers")
    monkeypatch.delenv("RAIKER_MCP_ENV_ALLOWLIST", raising=False)

    scope = mcp_scope(
        transport="stdio", endpoint_url=None, auth_ref=None, template=None, tool_count=None
    )

    assert scope["environment"] == sorted(mcp_stdio_env())
    assert "ANTHROPIC_API_KEY" not in scope["environment"]
    assert scope["granted_environment"] == []
    # Nothing confines a local process's network or writes; the preview says so.
    assert scope["runs_on"] == "this_machine"
    assert scope["network"] == "unrestricted"
    assert scope["writable"] == "account"
    assert scope["working_folder"] == "workspace"
    assert scope["risk"] == "local_process"
    assert scope["tool_count"] is None


def test_a_name_the_owner_granted_is_named_as_their_grant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAIKER_MCP_ENV_ALLOWLIST", "WEATHER_TOKEN")
    monkeypatch.setenv("WEATHER_TOKEN", "x")

    scope = mcp_scope(
        transport="stdio", endpoint_url=None, auth_ref=None, template=None, tool_count=2
    )

    assert scope["granted_environment"] == ["WEATHER_TOKEN"]
    assert "WEATHER_TOKEN" in scope["environment"]


@pytest.mark.parametrize(
    ("url", "network", "encrypted", "risk"),
    [
        ("https://mcp.acme.example/v1", "public", True, "remote_service"),
        ("http://127.0.0.1:8080/mcp", "loopback", False, "own_network"),
        ("http://nas.lan/mcp", "private_network", False, "own_network"),
    ],
)
def test_a_remote_server_is_classed_by_the_endpoint_policy(
    url: str, network: str, encrypted: bool, risk: str
) -> None:
    scope = mcp_scope(
        transport="http", endpoint_url=url, auth_ref="ACME_TOKEN", template=None, tool_count=3
    )

    assert scope["network"] == network
    assert scope["encrypted"] is encrypted
    assert scope["risk"] == risk
    assert scope["token_reference"] == "ACME_TOKEN"
    assert scope["environment"] == []
    assert scope["writable"] == "none_on_this_machine"
    assert scope["required_permissions"] == ["mcp_connector_runtime"]


def test_the_client_shares_no_roots_and_reads_no_resources() -> None:
    """The preview's "no folder, no file" is the client's initialize, not copy."""
    import inspect

    import raiker.runtime.executors.mcp as mcp

    source = inspect.getsource(mcp)
    assert '"capabilities": {}' in source  # the client's own initialize
    assert '"roots"' not in source
    scope = mcp_scope(
        transport="stdio", endpoint_url=None, auth_ref=None, template="python-stdio-echo",
        tool_count=None,
    )
    assert scope["roots_shared"] is False and scope["resources_read"] is False
    assert scope["required_permissions"] == ["mcp_connector_runtime", "mcp_builder_runtime"]


def test_provenance_names_the_sample_the_plugin_or_the_owner() -> None:
    declared = [{"name": "search", "description": "Search the docs index.", "inputSchema": {}}]
    assert _mcp_provenance({"name": "s", "template": "python-stdio-echo"}, {})["source"] == (
        "raiker_sample"
    )
    offered = _mcp_provenance(
        {"name": "acme", "template": None}, {"acme": ("acme-plugin", "Acme's docs.")}
    )
    assert offered == {
        "source": "plugin",
        "source_plugin": "acme-plugin",
        "purpose": "Acme's docs.",
        "purpose_from": "plugin",
    }
    own = _mcp_provenance({"name": "mine", "template": None, "tool_schemas": declared}, {})
    # The server's own sentence, marked as the server's rather than Raiker's.
    assert own == {
        "source": "owner",
        "source_plugin": None,
        "purpose": "Search the docs index.",
        "purpose_from": "server",
    }
