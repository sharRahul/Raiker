"""Contract tests for the local Codex App Server boundary."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from raiker.models.codex_app_server import CodexAppServerClient
from raiker.models.contracts import ModelCapabilities, ModelMessage, ModelRequest
from raiker.models.providers.codex_app_server import AsyncCodexAppServerProvider


def _server_script(tmp_path: Path) -> Path:
    script = tmp_path / "fake_codex_server.py"
    script.write_text(
        """import json, sys
for raw in sys.stdin:
    request = json.loads(raw)
    method = request[\"method\"]
    if method == \"initialize\":
        result = {\"userAgent\": \"fake\"}
    elif method == \"account/read\":
        result = {\"requiresOpenaiAuth\": True, \"account\": {\"type\": \"chatgpt\", \"email\": \"owner@example.test\", \"planType\": \"plus\"}}
    elif method == \"model/list\":
        result = {\"data\": [{\"id\": \"gpt-5.6\", \"model\": \"gpt-5.6\", \"displayName\": \"GPT 5.6\", \"description\": \"Subscription model\", \"hidden\": False, \"isDefault\": True, \"defaultReasoningEffort\": \"medium\", \"supportedReasoningEfforts\": []}], \"nextCursor\": None}
    elif method == \"account/login/start\":
        result = {\"type\": \"chatgpt\", \"loginId\": \"login_1\", \"authUrl\": \"https://auth.example.test/login?state=secret\"}
    elif method == \"thread/start\":
        result = {\"thread\": {\"id\": \"thread_1\"}}
    elif method == \"turn/start\":
        result = {\"turn\": {\"id\": \"turn_1\"}}
        print(json.dumps({\"id\": request[\"id\"], \"result\": result}), flush=True)
        print(json.dumps({\"method\": \"item/agentMessage/delta\", \"params\": {\"threadId\": \"thread_1\", \"turnId\": \"turn_1\", \"itemId\": \"item_1\", \"delta\": \"Hello\"}}), flush=True)
        print(json.dumps({\"method\": \"turn/completed\", \"params\": {\"threadId\": \"thread_1\", \"turn\": {\"id\": \"turn_1\"}}}), flush=True)
        continue
    else:
        result = {}
    print(json.dumps({\"id\": request[\"id\"], \"result\": result}), flush=True)
""",
        encoding="utf-8",
    )
    return script


def test_account_and_model_reads_expose_no_identity_or_token(tmp_path: Path) -> None:
    async def run() -> None:
        client = CodexAppServerClient(command=(sys.executable, str(_server_script(tmp_path))))
        try:
            account = await client.account_status()
            assert account.signed_in is True
            assert account.plan_type == "plus"
            assert not hasattr(account, "email")
            assert await client.list_models() == ["gpt-5.6"]
        finally:
            await client.aclose()

    asyncio.run(run())


def test_login_opens_the_codex_owned_url_without_returning_it(tmp_path: Path) -> None:
    opened: list[str] = []

    async def run() -> None:
        client = CodexAppServerClient(
            command=(sys.executable, str(_server_script(tmp_path))),
            open_browser=opened.append,
        )
        try:
            login = await client.start_chatgpt_login()
            assert login.login_id == "login_1"
            assert not hasattr(login, "auth_url")
        finally:
            await client.aclose()

    asyncio.run(run())
    assert opened == ["https://auth.example.test/login?state=secret"]


def test_chat_collects_only_agent_text_from_the_app_server(tmp_path: Path) -> None:
    async def run() -> None:
        client = CodexAppServerClient(command=(sys.executable, str(_server_script(tmp_path))))
        try:
            assert await client.complete_chat(model="gpt-5.6", prompt="hello", effort="high") == "Hello"
        finally:
            await client.aclose()

    asyncio.run(run())


def test_provider_adapts_codex_models_and_text_only_chat(tmp_path: Path) -> None:
    async def run() -> None:
        provider = AsyncCodexAppServerProvider(
            profile_id="chatgpt-codex-subscription",
            model="gpt-5.6",
            capabilities=ModelCapabilities(supports_streaming=True),
            client_factory=lambda: CodexAppServerClient(
                command=(sys.executable, str(_server_script(tmp_path)))
            ),
        )
        try:
            assert [model.id for model in await provider.list_models()] == ["gpt-5.6"]
            response = await provider.chat(
                ModelRequest(
                    "chatgpt-codex-subscription",
                    "chatgpt-codex",
                    "gpt-5.6",
                    [ModelMessage("user", "hello")],
                    tool_call_mode="text_json",
                )
            )
            assert response.text == "Hello"
            assert response.tool_calls == []
        finally:
            await provider.aclose()

    asyncio.run(run())
