from __future__ import annotations

from typing import Any

import pytest

from raiker.models import providers
from raiker.models.contracts import ModelMessage, ToolSpec
from raiker.models.providers import LlamaCppServerProvider, ProviderConnectionError
from raiker.models.tool_call_validation import default_tool_specs


def test_non_local_endpoint_rejected_without_allow_remote() -> None:
    with pytest.raises(ProviderConnectionError):
        LlamaCppServerProvider(endpoint="http://example.com:8080")


def test_local_endpoint_allowed() -> None:
    provider = LlamaCppServerProvider(endpoint="http://127.0.0.1:8080")
    assert provider.endpoint == "http://127.0.0.1:8080"


def test_chat_parses_native_tool_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_post(endpoint: str, path: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        captured["path"] = path
        captured["payload"] = payload
        return {
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "function": {
                                    "name": "list_directory",
                                    "arguments": "{\"path\": \".\"}",
                                },
                            }
                        ],
                    },
                }
            ]
        }

    monkeypatch.setattr(providers.llama_cpp_server, "_http_post_json", fake_post)
    provider = LlamaCppServerProvider()
    response = provider.chat(
        [ModelMessage(role="user", content="list files")],
        default_tool_specs(),
    )
    assert captured["path"] == "/v1/chat/completions"
    assert captured["payload"]["tool_choice"] == "auto"
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].tool_name == "list_directory"
    assert response.tool_calls[0].arguments == {"path": "."}
    assert response.finish_reason == "tool_calls"


def test_chat_parses_plain_text(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(endpoint: str, path: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        return {"choices": [{"finish_reason": "stop", "message": {"content": "hello there"}}]}

    monkeypatch.setattr(providers.llama_cpp_server, "_http_post_json", fake_post)
    provider = LlamaCppServerProvider()
    response = provider.chat([ModelMessage(role="user", content="hi")])
    assert response.text == "hello there"
    assert response.tool_calls == []
    assert response.finish_reason == "stop"


def test_text_json_tool_call_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(endpoint: str, path: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": '{"tool": "read_file", "arguments": {"path": "a.txt"}}'},
                }
            ]
        }

    monkeypatch.setattr(providers.llama_cpp_server, "_http_post_json", fake_post)
    provider = LlamaCppServerProvider(tool_call_mode="text_json")
    response = provider.chat([ModelMessage(role="user", content="read a.txt")], [ToolSpec("read_file", "")])
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].tool_name == "read_file"
    assert response.tool_calls[0].arguments == {"path": "a.txt"}


def test_health_uses_health_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, Any] = {}

    def fake_get(endpoint: str, path: str, timeout: float) -> bool:
        calls["path"] = path
        return True

    monkeypatch.setattr(providers.llama_cpp_server, "_http_get_ok", fake_get)
    assert LlamaCppServerProvider().health() is True
    assert calls["path"] == "/health"


def test_unreachable_server_raises_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(endpoint: str, path: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        raise ProviderConnectionError("connection_failed")

    monkeypatch.setattr(providers.llama_cpp_server, "_http_post_json", boom)
    with pytest.raises(ProviderConnectionError):
        LlamaCppServerProvider().chat([ModelMessage(role="user", content="hi")])
