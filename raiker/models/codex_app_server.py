"""Small, safe boundary around Codex App Server's JSON-RPC stdio protocol.

Codex owns ChatGPT OAuth tokens and opens the browser flow.  Raiker receives
only the signed-in state, subscription plan, and model identifiers it needs to
offer a governed model choice.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shutil
import webbrowser
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from raiker.models.exceptions import (
    ProviderConfigurationError,
    ProviderConnectionError,
    ProviderResponseValidationError,
    ProviderTimeoutError,
)

_REQUEST_TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True)
class CodexAccountStatus:
    signed_in: bool
    plan_type: str | None


@dataclass(frozen=True)
class CodexLogin:
    login_id: str


class CodexAppServerClient:
    """A one-process-at-a-time JSON-RPC client for read/login model actions."""

    def __init__(
        self,
        *,
        command: Sequence[str] | None = None,
        open_browser: Callable[[str], Any] = webbrowser.open,
        timeout_seconds: float = _REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        self.command = tuple(command or self._default_command())
        self.open_browser = open_browser
        self.timeout_seconds = timeout_seconds
        self._process: asyncio.subprocess.Process | None = None
        self._next_id = 1
        self._lock = asyncio.Lock()
        self._initialized = False

    @staticmethod
    def _default_command() -> tuple[str, ...]:
        """Resolve the Codex launcher without invoking a shell.

        A Windows desktop install commonly exposes ``codex.ps1`` first on
        ``PATH``.  ``CreateProcess`` does not resolve PowerShell scripts, so
        call PowerShell explicitly when a cmd/exe shim is unavailable.
        """
        for name in ("codex.exe", "codex.cmd", "codex"):
            executable = shutil.which(name)
            if executable is not None:
                return executable, "app-server", "--stdio"
        if os.name == "nt":
            script = shutil.which("codex.ps1")
            shell = shutil.which("pwsh") or shutil.which("powershell")
            if script is not None and shell is not None:
                return shell, "-NoProfile", "-File", script, "app-server", "--stdio"
        return "codex", "app-server", "--stdio"

    async def _start(self) -> None:
        if self._process is not None:
            return
        if not self.command or not shutil.which(self.command[0]):
            raise ProviderConfigurationError("codex_app_server_not_installed")
        try:
            self._process = await asyncio.create_subprocess_exec(
                *self.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except OSError as exc:
            raise ProviderConnectionError("codex_app_server_unavailable") from exc

    async def _request_running(
        self, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        process = self._process
        if process is None or process.stdin is None or process.stdout is None:
            raise ProviderConnectionError("codex_app_server_unavailable")
        request_id = self._next_id
        self._next_id += 1
        payload: dict[str, Any] = {"id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        try:
            process.stdin.write((json.dumps(payload, separators=(",", ":")) + "\n").encode())
            await process.stdin.drain()
            while True:
                raw = await asyncio.wait_for(process.stdout.readline(), self.timeout_seconds)
                if not raw:
                    raise ProviderConnectionError("codex_app_server_closed")
                message = json.loads(raw)
                if "method" in message and "id" in message:
                    # Raiker does not delegate App Server tool/permission
                    # requests.  Explicitly deny them rather than leaving a
                    # blocked Codex child waiting for an answer it cannot get.
                    process.stdin.write(
                        (
                            json.dumps(
                                {
                                    "id": message["id"],
                                    "error": {
                                        "code": -32000,
                                        "message": "raiker_codex_tool_request_denied",
                                    },
                                },
                                separators=(",", ":"),
                            )
                            + "\n"
                        ).encode()
                    )
                    await process.stdin.drain()
                    continue
                if message.get("id") != request_id:
                    # Notifications belong to Codex's own lifecycle. This
                    # short-lived client has no authority to action them.
                    continue
                if "error" in message:
                    raise ProviderConnectionError("codex_app_server_request_failed")
                result = message.get("result")
                if not isinstance(result, dict):
                    raise ProviderResponseValidationError("codex_app_server_invalid_response")
                return result
        except TimeoutError as exc:
            raise ProviderTimeoutError("codex_app_server_timeout") from exc
        except json.JSONDecodeError as exc:
            raise ProviderResponseValidationError("codex_app_server_invalid_json") from exc

    async def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        async with self._lock:
            if self._process is None:
                await self._start()
            if not self._initialized:
                await self._request_running(
                    "initialize", {"clientInfo": {"name": "Raiker", "version": "1"}}
                )
                self._initialized = True
            return await self._request_running(method, params)

    async def account_status(self) -> CodexAccountStatus:
        result = await self._request("account/read", {})
        account = result.get("account")
        if not isinstance(account, dict) or account.get("type") != "chatgpt":
            return CodexAccountStatus(signed_in=False, plan_type=None)
        plan_type = account.get("planType")
        return CodexAccountStatus(
            signed_in=True,
            plan_type=plan_type if isinstance(plan_type, str) else None,
        )

    async def start_chatgpt_login(self) -> CodexLogin:
        result = await self._request("account/login/start", {"type": "chatgpt"})
        login_id = result.get("loginId")
        auth_url = result.get("authUrl")
        if result.get("type") != "chatgpt" or not isinstance(login_id, str) or not login_id:
            raise ProviderResponseValidationError("codex_app_server_login_invalid")
        if not isinstance(auth_url, str):
            raise ProviderResponseValidationError("codex_app_server_login_url_invalid")
        parsed = urlparse(auth_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ProviderResponseValidationError("codex_app_server_login_url_invalid")
        self.open_browser(auth_url)
        return CodexLogin(login_id=login_id)

    async def list_models(self) -> list[str]:
        cursor: str | None = None
        models: list[str] = []
        while True:
            result = await self._request("model/list", {"cursor": cursor, "includeHidden": False})
            data = result.get("data")
            if not isinstance(data, list):
                raise ProviderResponseValidationError("codex_app_server_model_list_invalid")
            for item in data:
                if isinstance(item, dict) and item.get("hidden") is False:
                    model = item.get("model") or item.get("id")
                    if isinstance(model, str) and model and model not in models:
                        models.append(model)
            cursor = result.get("nextCursor")
            if cursor is None:
                return models
            if not isinstance(cursor, str) or not cursor:
                raise ProviderResponseValidationError("codex_app_server_model_cursor_invalid")

    async def complete_chat(self, *, model: str, prompt: str, effort: str | None) -> str:
        """Run one text-only, read-only Codex turn and return agent text.

        Any server request for tool execution or permissions is denied on the
        stdio channel.  Raiker's own governed tool loop remains the only path
        that can change the workspace.
        """
        async with self._lock:
            if self._process is None:
                await self._start()
            if not self._initialized:
                await self._request_running(
                    "initialize", {"clientInfo": {"name": "Raiker", "version": "1"}}
                )
                self._initialized = True
            started = await self._request_running(
                "thread/start",
                {
                    "model": model,
                    "cwd": os.getcwd(),
                    "approvalPolicy": "untrusted",
                    "sandbox": "read-only",
                    "ephemeral": True,
                },
            )
            thread = started.get("thread")
            thread_id = thread.get("id") if isinstance(thread, dict) else None
            if not isinstance(thread_id, str) or not thread_id:
                raise ProviderResponseValidationError("codex_app_server_thread_invalid")
            turn = await self._request_running(
                "turn/start",
                {
                    "threadId": thread_id,
                    "input": [{"type": "text", "text": prompt, "text_elements": []}],
                    "model": model,
                    **({"effort": effort} if effort else {}),
                },
            )
            turn_data = turn.get("turn")
            turn_id = turn_data.get("id") if isinstance(turn_data, dict) else None
            if not isinstance(turn_id, str) or not turn_id:
                raise ProviderResponseValidationError("codex_app_server_turn_invalid")
            process = self._process
            if process is None or process.stdin is None or process.stdout is None:
                raise ProviderConnectionError("codex_app_server_unavailable")
            text: list[str] = []
            try:
                while True:
                    raw = await asyncio.wait_for(process.stdout.readline(), self.timeout_seconds)
                    if not raw:
                        raise ProviderConnectionError("codex_app_server_closed")
                    message = json.loads(raw)
                    if "method" in message and "id" in message:
                        process.stdin.write(
                            (
                                json.dumps(
                                    {
                                        "id": message["id"],
                                        "error": {
                                            "code": -32000,
                                            "message": "raiker_codex_tool_request_denied",
                                        },
                                    },
                                    separators=(",", ":"),
                                )
                                + "\n"
                            ).encode()
                        )
                        await process.stdin.drain()
                        continue
                    params = message.get("params")
                    if not isinstance(params, dict):
                        continue
                    method = message.get("method")
                    if (
                        method == "item/agentMessage/delta"
                        and params.get("threadId") == thread_id
                        and params.get("turnId") == turn_id
                    ):
                        delta = params.get("delta")
                        if isinstance(delta, str):
                            text.append(delta)
                    if method == "turn/completed" and params.get("threadId") == thread_id:
                        return "".join(text)
            except TimeoutError as exc:
                raise ProviderTimeoutError("codex_app_server_timeout") from exc
            except json.JSONDecodeError as exc:
                raise ProviderResponseValidationError("codex_app_server_invalid_json") from exc

    async def aclose(self) -> None:
        process, self._process = self._process, None
        self._initialized = False
        if process is None:
            return
        if process.returncode is None:
            process.terminate()
            with contextlib.suppress(ProcessLookupError, TimeoutError):
                await asyncio.wait_for(process.wait(), timeout=2.0)
        if process.returncode is None:
            process.kill()
            with contextlib.suppress(ProcessLookupError):
                await process.wait()


class CodexSubscriptionSessions:
    """Keeps an App Server alive only while an owner completes browser login."""

    def __init__(self, client_factory: Callable[[], CodexAppServerClient] = CodexAppServerClient) -> None:
        self._client_factory = client_factory
        self._clients: dict[str, CodexAppServerClient] = {}
        self._lock = asyncio.Lock()

    async def _client(self, principal_id: str) -> CodexAppServerClient:
        async with self._lock:
            return self._clients.setdefault(principal_id, self._client_factory())

    async def status(self, principal_id: str) -> CodexAccountStatus:
        client = await self._client(principal_id)
        status = await client.account_status()
        if status.signed_in:
            async with self._lock:
                self._clients.pop(principal_id, None)
            await client.aclose()
        return status

    async def start_login(self, principal_id: str) -> CodexLogin:
        return await (await self._client(principal_id)).start_chatgpt_login()

    async def disconnect(self, principal_id: str) -> None:
        async with self._lock:
            client = self._clients.pop(principal_id, None)
        if client is not None:
            await client.aclose()
