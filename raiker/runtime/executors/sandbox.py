from __future__ import annotations

import fnmatch
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any


class SandboxError(Exception):
    pass


ALLOWED_SHELL_COMMANDS: frozenset[str] = frozenset({
    "ls", "cat", "head", "tail", "echo", "pwd", "which",
    "git", "python", "pip", "node", "npm",
    "diff", "grep", "find", "sort", "wc", "uniq",
})


def check_command_allowlist(command: Sequence[str], allowlist: frozenset[str]) -> None:
    """The full command policy, raised as a :class:`SandboxError`.

    RAIKER-2023: this used to be a one-line check on the binary's basename, which
    said nothing about the *arguments*. `git -c core.sshCommand=… push` and
    `find . -exec sh {} ;` both pass a basename allowlist and both run a program
    of the caller's choosing. :mod:`raiker.runtime.command_policy` parses the
    whole argv — including any string that will itself be read as shell source —
    and refuses chaining, pipes, redirection, substitution, expansion, globbing,
    interpreters, per-binary escape flags, and any path outside the workspace.
    """
    from raiker.runtime.command_policy import CommandRejected, validate_command

    try:
        validate_command(command, workspace_root=_command_workspace(), allowlist=allowlist)
    except CommandRejected as exc:
        raise SandboxError(exc.reason_code) from None


_COMMAND_WORKSPACE: Path | None = None


def set_command_workspace(root: str | Path | None) -> None:
    """Name the directory a governed command may touch.

    Set by the executors, which know the workspace; kept here because
    ``check_command_allowlist`` is reached through call sites that do not carry
    it. Unset, containment falls back to the process working directory, which is
    the workspace for every path Raiker actually launches commands from.
    """
    global _COMMAND_WORKSPACE
    _COMMAND_WORKSPACE = Path(root).resolve() if root else None


def _command_workspace() -> Path:
    return _COMMAND_WORKSPACE or Path.cwd().resolve()


def run_command(
    command: Sequence[str],
    *,
    timeout: float = 30.0,
    max_output_bytes: int = 100_000,
    allowlist: frozenset[str] | None = None,
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
    stdin_text: str | None = None,
) -> dict[str, Any]:
    if allowlist is not None:
        set_command_workspace(cwd)
        check_command_allowlist(command, allowlist)
    # A child gets a constructed environment, never the host's. Inheriting it
    # would hand every command every credential the host holds — including the
    # git token this runtime lends for exactly one command at a time.
    from raiker.runtime.command_policy import sandbox_environment

    child_env = sandbox_environment(workspace_root=cwd or Path.cwd(), extra=env)
    launch_command = _portable_command(command)
    try:
        proc = subprocess.run(
            launch_command,
            capture_output=True,
            text=False,
            timeout=timeout,
            cwd=cwd,
            env=child_env,
            input=stdin_text.encode("utf-8") if stdin_text is not None else None,
        )
    except subprocess.TimeoutExpired:
        raise SandboxError(f"command_timeout:{timeout}s") from None
    except FileNotFoundError:
        raise SandboxError(f"command_not_found:{command[0]}") from None
    except OSError as exc:
        raise SandboxError(f"command_failed:{exc}") from None

    stdout_len = len(proc.stdout)
    stderr_len = len(proc.stderr)
    return {
        "returncode": proc.returncode,
        "stdout_bytes": stdout_len,
        "stderr_bytes": stderr_len,
        "stdout": proc.stdout[:max_output_bytes].decode("utf-8", errors="replace"),
        "stderr": proc.stderr[:max_output_bytes].decode("utf-8", errors="replace"),
        "truncated": stdout_len > max_output_bytes or stderr_len > max_output_bytes,
    }


def _portable_command(command: Sequence[str]) -> Sequence[str]:
    """Keep the small governed read surface usable on native Windows.

    Policy validation always runs against the owner's original argv first, so
    this fixed adapter cannot widen what was approved. Windows has no `cat`
    executable; use Raiker's interpreter only as an implementation detail for
    reading the already-contained file arguments.
    """
    if os.name != "nt" or not command or command[0].lower() != "cat":
        return command
    reader = (
        "import pathlib,sys;"
        "out=sys.stdout.buffer;"
        "[out.write(pathlib.Path(name).read_bytes()) for name in sys.argv[1:]]"
    )
    return (sys.executable, "-c", reader, *command[1:])


def fetch_url(
    url: str,
    *,
    egress_allowlist: frozenset[str] | None = None,
    max_bytes: int = 200_000,
    timeout: float = 15.0,
) -> dict:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if not parsed.netloc:
        raise SandboxError(f"invalid_url:{url}")
    if egress_allowlist is not None:
        allowed = any(
            fnmatch.fnmatch(parsed.netloc, pattern)
            for pattern in egress_allowlist
        )
        if not allowed:
            raise SandboxError(f"egress_denied:{parsed.netloc}")
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = resp.read(max_bytes + 1)
    except Exception as exc:
        raise SandboxError(f"fetch_failed:{exc}") from None
    truncated = len(data) > max_bytes
    body = data[:max_bytes]
    return {
        "status": resp.status if hasattr(resp, "status") else 200,
        "body_bytes": len(body),
        "truncated": truncated,
    }


_DEFAULT_EGRESS_ALLOWLIST: frozenset[str] = frozenset({
    "api.github.com",
    "raw.githubusercontent.com",
    "pypi.org",
    "files.pythonhosted.org",
})


def default_egress_allowlist() -> frozenset[str]:
    return _DEFAULT_EGRESS_ALLOWLIST


def channel_egress_allowlist() -> frozenset[str]:
    """Owner-controlled outbound host allowlist for channel delivery.

    Read from ``RAIKER_CHANNEL_EGRESS_ALLOWLIST`` (comma-separated host globs,
    e.g. ``hooks.slack.com,127.0.0.1:*``). Defaults to **empty** so a channel
    cannot reach the network until the owner explicitly allowlists a host —
    fail-closed by default even when the gate is on. Model-proposed URLs are
    untrusted and can only resolve to allowlisted hosts.
    """
    raw = os.environ.get("RAIKER_CHANNEL_EGRESS_ALLOWLIST", "")
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def connector_egress_allowlist() -> frozenset[str]:
    """Owner-controlled outbound host allowlist for service connectors.

    Read from ``RAIKER_CONNECTOR_EGRESS_ALLOWLIST`` (comma-separated host globs,
    e.g. ``api.github.com``). Defaults to **empty** so a connector cannot reach
    the network until the owner explicitly allowlists a host — fail-closed by
    default even when the connector's capability gate is on. Connector hosts are
    built from validated components (never a model-supplied raw URL), so this is
    a second, independent egress boundary.
    """
    raw = os.environ.get("RAIKER_CONNECTOR_EGRESS_ALLOWLIST", "")
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


# `web_egress_allowlist()` was removed in RAIKER-2021. The agent's own web reads
# are governed by `raiker.runtime.web_policy` instead: an owner *blocklist*
# (`RAIKER_WEB_EGRESS_BLACKLIST` plus the rules stored in the app) over public
# destinations, and a non-editable address guard that refuses every private,
# loopback and link-local address. The connector and channel allowlists above are
# untouched — those hosts are built from validated components rather than chosen
# by a model, and they answer to a different question.


def get_url(
    url: str,
    *,
    egress_allowlist: frozenset[str] | None = None,
    headers: dict[str, str] | None = None,
    max_bytes: int = 200_000,
    timeout: float = 15.0,
) -> dict:
    """GET ``url`` only if its host matches ``egress_allowlist``.

    An empty/absent allowlist denies all egress (fail closed). Unlike
    :func:`fetch_url`, this returns the (bounded) decoded response body so a
    read connector can hand the external content back as untrusted data. Request
    headers (e.g. an ``Authorization`` bearer from owner env) are sent verbatim
    but are never returned or logged by this function.
    """
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise SandboxError(f"invalid_url:{url}")
    if not egress_allowlist:
        raise SandboxError("egress_denied:no_allowlist")
    if not any(fnmatch.fnmatch(parsed.netloc, pattern) for pattern in egress_allowlist):
        raise SandboxError(f"egress_denied:{parsed.netloc}")
    import urllib.error
    import urllib.request
    request = urllib.request.Request(  # noqa: S310 - scheme checked above
        url, method="GET", headers=headers or {},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:  # noqa: S310
            data = resp.read(max_bytes + 1)
            status_code = resp.status if hasattr(resp, "status") else 200
    except urllib.error.HTTPError as exc:
        # Surface the HTTP status (404/403/...) without leaking the body.
        raise SandboxError(f"http_error:{exc.code}") from None
    except Exception as exc:
        raise SandboxError(f"fetch_failed:{type(exc).__name__}") from None
    truncated = len(data) > max_bytes
    body = data[:max_bytes]
    return {
        "status": status_code,
        "body_bytes": len(body),
        "body_text": body.decode("utf-8", errors="replace"),
        "truncated": truncated,
    }


def post_url(
    url: str,
    payload: bytes,
    *,
    egress_allowlist: frozenset[str] | None = None,
    content_type: str = "application/json",
    max_bytes: int = 64_000,
    timeout: float = 10.0,
) -> dict:
    """POST ``payload`` to ``url`` only if its host matches ``egress_allowlist``.

    An empty/absent allowlist denies all egress (fail closed). Returns
    response-size metadata only — never the response body.
    """
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise SandboxError(f"invalid_url:{url}")
    if not egress_allowlist:
        raise SandboxError("egress_denied:no_allowlist")
    if not any(fnmatch.fnmatch(parsed.netloc, pattern) for pattern in egress_allowlist):
        raise SandboxError(f"egress_denied:{parsed.netloc}")
    import urllib.request
    request = urllib.request.Request(  # noqa: S310 - scheme checked above
        url, data=payload, method="POST", headers={"Content-Type": content_type},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:  # noqa: S310
            data = resp.read(max_bytes + 1)
            status_code = resp.status if hasattr(resp, "status") else 200
    except Exception as exc:
        raise SandboxError(f"delivery_failed:{type(exc).__name__}") from None
    return {"status": status_code, "sent_bytes": len(payload), "response_bytes": len(data[:max_bytes])}


def post_json_rpc(
    url: str,
    payload: dict[str, object],
    *,
    headers: dict[str, str] | None = None,
    max_bytes: int = 200_000,
    timeout: float = 15.0,
) -> dict:
    """POST a JSON-RPC ``payload`` to an owner-added MCP endpoint.

    Returns status, the bounded response body text, and the response headers
    (lower-cased) — the latter so the caller can carry an ``Mcp-Session-Id``
    across requests. Only the URL scheme is validated; the request goes to the
    owner-supplied host because *the owner adding the URL is the authorization*
    (monitored, not allowlist-blocked — see the Security Philosophy). Request
    headers (e.g. an owner bearer token) are sent verbatim and are never
    returned or logged by this function. An HTTP error still returns its body,
    since an MCP server may deliver a JSON-RPC error with a non-2xx status.
    """
    import json as _json
    import urllib.error
    import urllib.request
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise SandboxError("mcp_remote_invalid_endpoint")
    body = _json.dumps(payload).encode("utf-8")
    merged = {"Content-Type": "application/json", "Accept": "application/json"}
    merged.update(headers or {})
    request = urllib.request.Request(  # noqa: S310 - scheme checked above
        url, data=body, method="POST", headers=merged,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:  # noqa: S310
            data = resp.read(max_bytes + 1)
            status_code = resp.status if hasattr(resp, "status") else 200
            resp_headers = {str(k).lower(): str(v) for k, v in resp.headers.items()}
    except urllib.error.HTTPError as exc:
        data = exc.read(max_bytes + 1) if hasattr(exc, "read") else b""
        status_code = exc.code
        resp_headers = {
            str(k).lower(): str(v) for k, v in (exc.headers.items() if exc.headers else [])
        }
    except Exception:
        raise SandboxError("mcp_remote_unreachable") from None
    truncated = len(data) > max_bytes
    return {
        "status": status_code,
        "body_text": data[:max_bytes].decode("utf-8", errors="replace"),
        "headers": resp_headers,
        "truncated": truncated,
    }


def post_json_url(
    url: str,
    payload: dict[str, object],
    *,
    egress_allowlist: frozenset[str] | None = None,
    headers: dict[str, str] | None = None,
    max_bytes: int = 200_000,
    timeout: float = 15.0,
) -> dict:
    """POST JSON ``payload`` to ``url`` only if its host matches ``egress_allowlist``.

    An empty/absent allowlist denies all egress (fail closed). Like
    :func:`get_url`, this returns the (bounded) decoded response body so a
    connector write can return the external result as untrusted data. Request
    headers (e.g. an ``Authorization`` bearer from owner env) are sent verbatim
    but are never returned or logged by this function.
    """
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise SandboxError(f"invalid_url:{url}")
    if not egress_allowlist:
        raise SandboxError("egress_denied:no_allowlist")
    if not any(fnmatch.fnmatch(parsed.netloc, pattern) for pattern in egress_allowlist):
        raise SandboxError(f"egress_denied:{parsed.netloc}")
    import json as _json
    import urllib.error
    import urllib.request
    body_bytes = _json.dumps(payload).encode("utf-8")
    merged = dict(headers or {})
    merged.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(  # noqa: S310 - scheme checked above
        url, data=body_bytes, method="POST", headers=merged,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:  # noqa: S310
            data = resp.read(max_bytes + 1)
            status_code = resp.status if hasattr(resp, "status") else 200
    except urllib.error.HTTPError as exc:
        raise SandboxError(f"http_error:{exc.code}") from None
    except Exception as exc:
        raise SandboxError(f"fetch_failed:{type(exc).__name__}") from None
    truncated = len(data) > max_bytes
    body = data[:max_bytes]
    return {
        "status": status_code,
        "body_bytes": len(body),
        "body_text": body.decode("utf-8", errors="replace"),
        "truncated": truncated,
    }
