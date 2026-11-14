# SPDX-License-Identifier: Apache-2.0
"""Small, safe boundary around Codex App Server's JSON-RPC stdio protocol.

Codex owns ChatGPT OAuth tokens and runs the browser or device-code flow.
Raiker receives only the signed-in state, subscription plan, model
identifiers, and — for the owner who started a sign-in — the address and
one-time code that sign-in needs. The PKCE verifier, the access and refresh
tokens, and the account's identity never leave the Codex process.

Protocol notes (checked against ``codex app-server generate-json-schema`` for
codex-cli 0.169):

* ``initialize`` is followed by the client's ``initialized`` notification.
* ``account/login/start`` takes ``{"type": "chatgpt"}`` (browser, a callback on
  ``127.0.0.1:1455``) or ``{"type": "chatgptDeviceCode"}`` (a code typed at the
  verification page — the flow Hermes Agent uses, which works when the callback
  port is busy or the browser is on another device).
* ``account/login/completed`` reports success or a failure reason;
  ``account/rateLimits/updated`` carries the subscription's limit windows.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shutil
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from raiker.models.exceptions import (
    ProviderConfigurationError,
    ProviderConnectionError,
    ProviderResponseValidationError,
    ProviderTimeoutError,
)
from raiker.models.subscription_limits import LimitWindow, parse_windows

_REQUEST_TIMEOUT_SECONDS = 15.0
#: How long a running turn may be silent. A reasoning model can think for well
#: over a minute before its first visible delta; the request timeout above is
#: for control requests and was killing those turns (FIXED-1393).
_TURN_IDLE_TIMEOUT_SECONDS = 300.0

#: An explicit launcher, for an install Raiker cannot find on its own.
CODEX_PATH_ENV = "RAIKER_CODEX_PATH"

LoginMethod = Literal["browser", "device_code"]


@dataclass(frozen=True)
class CodexAccountStatus:
    signed_in: bool
    plan_type: str | None
    #: Why the last owner-started sign-in failed, as Codex said it, if it did.
    login_error: str | None = None


@dataclass(frozen=True)
class CodexLogin:
    login_id: str
    method: LoginMethod = "browser"
    #: The page the owner opens: the OAuth page for ``browser``, the
    #: verification page for ``device_code``.
    url: str | None = None
    #: The one-time code the owner types on the verification page.
    user_code: str | None = None


@dataclass(frozen=True)
class CodexModel:
    model: str
    display_name: str | None


def _launcher_directories() -> list[Path]:
    """Where npm, Homebrew and user installs put ``codex`` outside a GUI PATH.

    A desktop app started from the dock or Start menu does not inherit the
    login shell's PATH, so a Codex installed with ``npm i -g @openai/codex``
    was reported as missing even though the terminal found it (FIXED-1392).
    """
    home = Path.home()
    candidates = [
        home / ".npm-global" / "bin",
        home / ".local" / "bin",
        home / ".volta" / "bin",
        home / ".bun" / "bin",
        home / ".cargo" / "bin",
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
    ]
    prefix = os.environ.get("NPM_CONFIG_PREFIX")
    if prefix:
        candidates.insert(0, Path(prefix) / ("" if os.name == "nt" else "bin"))
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.insert(0, Path(appdata) / "npm")
        local = os.environ.get("LOCALAPPDATA")
        if local:
            candidates.append(Path(local) / "Programs" / "codex")
    nvm = home / ".nvm" / "versions" / "node"
    with contextlib.suppress(OSError):
        if nvm.is_dir():
            candidates.extend(sorted((child / "bin" for child in nvm.iterdir()), reverse=True))
    return candidates


def resolve_codex_command() -> tuple[str, ...]:
    """Resolve the Codex launcher without invoking a shell.

    A Windows desktop install commonly exposes ``codex.ps1`` first on
    ``PATH``.  ``CreateProcess`` does not resolve PowerShell scripts, so
    call PowerShell explicitly when a cmd/exe shim is unavailable.
    """
    explicit = os.environ.get(CODEX_PATH_ENV, "").strip()
    if explicit:
        return explicit, "app-server", "--stdio"
    names = ("codex.exe", "codex.cmd", "codex")
    for name in names:
        executable = shutil.which(name)
        if executable is not None:
            return executable, "app-server", "--stdio"
    search = os.pathsep.join(str(directory) for directory in _launcher_directories())
    for name in names:
        executable = shutil.which(name, path=search)
        if executable is not None:
            return executable, "app-server", "--stdio"
    if os.name == "nt":
        script = shutil.which("codex.ps1")
        shell = shutil.which("pwsh") or shutil.which("powershell")
        if script is not None and shell is not None:
            return shell, "-NoProfile", "-File", script, "app-server", "--stdio"
    return "codex", "app-server", "--stdio"


def _deny(message_id: Any) -> bytes:
    return (
        json.dumps(
            {"id": message_id, "error": {"code": -32000, "message": "raiker_codex_tool_request_denied"}},
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def _https_url(value: object, reason: str) -> str:
    if not isinstance(value, str):
        raise ProviderResponseValidationError(reason)
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ProviderResponseValidationError(reason)
    return value


class CodexAppServerClient:
    """A one-process-at-a-time JSON-RPC client for read/login model actions."""

    def __init__(
        self,
        *,
        command: Sequence[str] | None = None,
        open_browser: Callable[[str], Any] | None = None,
        timeout_seconds: float = _REQUEST_TIMEOUT_SECONDS,
        turn_timeout_seconds: float = _TURN_IDLE_TIMEOUT_SECONDS,
    ) -> None:
        self.command = tuple(command or resolve_codex_command())
        # The owner's own browser opens the sign-in page (the UI receives the
        # address). A host that has a browser of its own may still pass one.
        self.open_browser = open_browser
        self.timeout_seconds = timeout_seconds
        self.turn_timeout_seconds = turn_timeout_seconds
        self._process: asyncio.subprocess.Process | None = None
        self._next_id = 1
        self._lock = asyncio.Lock()
        self._initialized = False
        self._workdir: tempfile.TemporaryDirectory[str] | None = None
        # BUG-254 — the last limit windows this subscription volunteered. Empty
        # until Codex has said something, which is the honest state.
        self.last_limit_windows: tuple[LimitWindow, ...] = ()
        self.pending_login_id: str | None = None
        self.login_error: str | None = None

    @staticmethod
    def _default_command() -> tuple[str, ...]:
        return resolve_codex_command()

    async def _start(self) -> None:
        if self._process is not None:
            return
        executable = self.command[0] if self.command else ""
        if not executable or not (shutil.which(executable) or Path(executable).is_file()):
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

    def _note(self, message: Mapping[str, Any]) -> None:
        """Keep what a notification says that Raiker is allowed to know."""
        method = message.get("method")
        params = message.get("params")
        if not isinstance(params, Mapping):
            return
        if method == "account/login/completed":
            login_id = params.get("loginId")
            if self.pending_login_id is not None and login_id not in (None, self.pending_login_id):
                return
            self.pending_login_id = None
            if params.get("success") is True:
                self.login_error = None
            else:
                error = params.get("error")
                self.login_error = error[:200] if isinstance(error, str) and error else "login_failed"
        elif method == "account/rateLimits/updated":
            windows = _windows_from_snapshot(params.get("rateLimits"))
            if windows:
                self.last_limit_windows = windows

    async def _send(self, payload: Mapping[str, Any]) -> None:
        process = self._process
        if process is None or process.stdin is None:
            raise ProviderConnectionError("codex_app_server_unavailable")
        process.stdin.write((json.dumps(payload, separators=(",", ":")) + "\n").encode())
        await process.stdin.drain()

    async def _read(self, timeout: float) -> dict[str, Any]:
        process = self._process
        if process is None or process.stdin is None or process.stdout is None:
            raise ProviderConnectionError("codex_app_server_unavailable")
        try:
            raw = await asyncio.wait_for(process.stdout.readline(), timeout)
        except TimeoutError as exc:
            raise ProviderTimeoutError("codex_app_server_timeout") from exc
        if not raw:
            raise ProviderConnectionError("codex_app_server_closed")
        try:
            message = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProviderResponseValidationError("codex_app_server_invalid_json") from exc
        if not isinstance(message, dict):
            raise ProviderResponseValidationError("codex_app_server_invalid_response")
        if "method" in message and "id" in message:
            # Raiker does not delegate App Server tool/permission requests.
            # Explicitly deny them rather than leaving a blocked Codex child
            # waiting for an answer it cannot get.
            process.stdin.write(_deny(message["id"]))
            await process.stdin.drain()
            return {}
        if "method" in message:
            self._note(message)
        return message

    async def _request_running(
        self, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        payload: dict[str, Any] = {"id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        await self._send(payload)
        while True:
            message = await self._read(self.timeout_seconds)
            if message.get("id") != request_id or "method" in message:
                # Notifications belong to Codex's own lifecycle; `_read` kept
                # the two Raiker reads. Nothing else is actioned.
                continue
            if "error" in message:
                error = message.get("error")
                detail = str(error.get("message", "")) if isinstance(error, Mapping) else ""
                if method == "account/login/start" and (
                    "error sending request" in detail or "failed to request device code" in detail
                ):
                    # Codex itself could not reach ChatGPT's sign-in service:
                    # a network or proxy problem on this device, not a refusal.
                    raise ProviderConnectionError("codex_login_service_unreachable")
                raise ProviderConnectionError(f"codex_app_server_request_failed:{method}")
            result = message.get("result")
            if not isinstance(result, dict):
                raise ProviderResponseValidationError("codex_app_server_invalid_response")
            return result

    async def _ensure_ready(self) -> None:
        if self._process is None:
            await self._start()
        if not self._initialized:
            await self._request_running(
                "initialize",
                {"clientInfo": {"name": "raiker", "title": "Raiker", "version": "1"}},
            )
            # The protocol's handshake ends with the client's notification;
            # without it a strict server refuses everything that follows.
            await self._send({"method": "initialized"})
            self._initialized = True

    async def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        async with self._lock:
            await self._ensure_ready()
            return await self._request_running(method, params)

    async def account_status(self) -> CodexAccountStatus:
        result = await self._request("account/read", {})
        account = result.get("account")
        if not isinstance(account, dict) or account.get("type") != "chatgpt":
            return CodexAccountStatus(signed_in=False, plan_type=None, login_error=self.login_error)
        plan_type = account.get("planType")
        self.login_error = None
        return CodexAccountStatus(
            signed_in=True,
            plan_type=plan_type if isinstance(plan_type, str) else None,
        )

    async def start_chatgpt_login(self, method: LoginMethod = "browser") -> CodexLogin:
        """Start a sign-in and return what the owner needs to finish it.

        A browser sign-in whose local callback cannot listen (another Codex is
        signing in, or the port is taken) falls back to the device code, which
        needs no callback at all.
        """
        if self.pending_login_id is not None:
            with contextlib.suppress(Exception):
                await self.cancel_login()
        self.login_error = None
        if method == "browser":
            try:
                result = await self._request("account/login/start", {"type": "chatgpt"})
            except ProviderConnectionError:
                method = "device_code"
            else:
                login_id = result.get("loginId")
                if result.get("type") != "chatgpt" or not isinstance(login_id, str) or not login_id:
                    raise ProviderResponseValidationError("codex_app_server_login_invalid")
                auth_url = _https_url(result.get("authUrl"), "codex_app_server_login_url_invalid")
                self.pending_login_id = login_id
                if self.open_browser is not None:
                    self.open_browser(auth_url)
                return CodexLogin(login_id=login_id, method="browser", url=auth_url)
        result = await self._request("account/login/start", {"type": "chatgptDeviceCode"})
        login_id = result.get("loginId")
        user_code = result.get("userCode")
        if (
            result.get("type") != "chatgptDeviceCode"
            or not isinstance(login_id, str)
            or not login_id
            or not isinstance(user_code, str)
            or not user_code
            or len(user_code) > 64
        ):
            raise ProviderResponseValidationError("codex_app_server_login_invalid")
        url = _https_url(result.get("verificationUrl"), "codex_app_server_login_url_invalid")
        self.pending_login_id = login_id
        return CodexLogin(login_id=login_id, method="device_code", url=url, user_code=user_code)

    async def cancel_login(self) -> None:
        login_id, self.pending_login_id = self.pending_login_id, None
        if login_id is not None and self._process is not None:
            await self._request("account/login/cancel", {"loginId": login_id})

    async def list_model_entries(self) -> list[CodexModel]:
        cursor: str | None = None
        models: list[CodexModel] = []
        seen: set[str] = set()
        while True:
            result = await self._request("model/list", {"cursor": cursor, "includeHidden": False})
            data = result.get("data")
            if not isinstance(data, list):
                raise ProviderResponseValidationError("codex_app_server_model_list_invalid")
            for item in data:
                if isinstance(item, dict) and item.get("hidden") is False:
                    model = item.get("model") or item.get("id")
                    if isinstance(model, str) and model and model not in seen:
                        seen.add(model)
                        label = item.get("displayName")
                        models.append(
                            CodexModel(
                                model=model,
                                display_name=label[:80] if isinstance(label, str) and label else None,
                            )
                        )
            cursor = result.get("nextCursor")
            if cursor is None:
                return models
            if not isinstance(cursor, str) or not cursor:
                raise ProviderResponseValidationError("codex_app_server_model_cursor_invalid")

    async def list_models(self) -> list[str]:
        return [entry.model for entry in await self.list_model_entries()]

    def _turn_directory(self) -> str:
        """An empty private directory for Codex's own working directory.

        Codex is asked for text only, with a read-only sandbox; pointing it at
        the host's working directory still let it read whatever was there.
        """
        if self._workdir is None:
            self._workdir = tempfile.TemporaryDirectory(prefix="raiker-codex-")
        return self._workdir.name

    async def complete_chat(self, *, model: str, prompt: str, effort: str | None) -> str:
        """Run one text-only, read-only Codex turn and return agent text.

        Any server request for tool execution or permissions is denied on the
        stdio channel.  Raiker's own governed tool loop remains the only path
        that can change the workspace.
        """
        async with self._lock:
            await self._ensure_ready()
            started = await self._request_running(
                "thread/start",
                {
                    "model": model,
                    "cwd": self._turn_directory(),
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
            text: list[str] = []
            while True:
                message = await self._read(self.turn_timeout_seconds)
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
                    # Older servers attached the windows to the turn itself.
                    legacy = parse_windows(params.get("rateLimits", params.get("rate_limits")))
                    if legacy:
                        self.last_limit_windows = legacy
                    completed = params.get("turn")
                    if isinstance(completed, dict) and completed.get("status") == "failed":
                        raise ProviderConnectionError("codex_app_server_turn_failed")
                    return "".join(text)

    async def aclose(self) -> None:
        process, self._process = self._process, None
        self._initialized = False
        workdir, self._workdir = self._workdir, None
        if process is not None:
            if process.returncode is None:
                process.terminate()
                with contextlib.suppress(ProcessLookupError, TimeoutError):
                    await asyncio.wait_for(process.wait(), timeout=2.0)
            if process.returncode is None:
                process.kill()
                with contextlib.suppress(ProcessLookupError):
                    await process.wait()
        if workdir is not None:
            with contextlib.suppress(OSError):
                workdir.cleanup()


def _windows_from_snapshot(raw: object) -> tuple[LimitWindow, ...]:
    """Read ``account/rateLimits/updated``'s primary and secondary windows."""
    if not isinstance(raw, Mapping):
        return ()
    shaped: dict[str, dict[str, Any]] = {}
    for key in ("primary", "secondary"):
        window = raw.get(key)
        if not isinstance(window, Mapping):
            continue
        entry: dict[str, Any] = {"used_percent": window.get("usedPercent")}
        minutes = window.get("windowDurationMins")
        if minutes is not None:
            entry["window_minutes"] = minutes
        resets_at = window.get("resetsAt")
        if isinstance(resets_at, (int, float)) and not isinstance(resets_at, bool):
            entry["resets_in_seconds"] = max(0, int(resets_at - time.time()))
        shaped[key] = entry
    return parse_windows(shaped)


class CodexSubscriptionSessions:
    """Keeps an App Server alive only while an owner completes a sign-in.

    The process that started a sign-in is the one listening for its browser
    callback or polling its device code, so it must outlive the request that
    started it and be the one later reads ask.
    """

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

    async def passive_status(self, principal_id: str) -> CodexAccountStatus | None:
        """Poll an owner-started login, never start a sidecar from a page read."""
        async with self._lock:
            client = self._clients.get(principal_id)
            if client is None:
                return None
            # Disconnect waits for this in-flight read. Do not check membership
            # then call status(), which could recreate a just-revoked client.
            account = await client.account_status()
            if account.signed_in:
                self._clients.pop(principal_id, None)
                await client.aclose()
            return account

    async def start_login(self, principal_id: str, method: LoginMethod = "browser") -> CodexLogin:
        return await (await self._client(principal_id)).start_chatgpt_login(method)

    async def cancel_login(self, principal_id: str) -> None:
        """Stop an owner-started sign-in and the process that was waiting on it."""
        async with self._lock:
            client = self._clients.pop(principal_id, None)
        if client is not None:
            with contextlib.suppress(Exception):
                await client.cancel_login()
            await client.aclose()

    async def disconnect(self, principal_id: str) -> None:
        await self.cancel_login(principal_id)
