from __future__ import annotations

import fnmatch
import subprocess
from collections.abc import Sequence
from pathlib import Path


class SandboxError(Exception):
    pass


ALLOWED_SHELL_COMMANDS: frozenset[str] = frozenset({
    "ls", "cat", "head", "tail", "echo", "pwd", "which",
    "git", "python", "pip", "node", "npm",
    "diff", "grep", "find", "sort", "wc", "uniq",
})


def check_command_allowlist(command: Sequence[str], allowlist: frozenset[str]) -> None:
    if not command:
        raise SandboxError("empty_command")
    base = Path(command[0]).name
    if base not in allowlist:
        raise SandboxError(f"command_not_allowed:{base}")


def run_command(
    command: Sequence[str],
    *,
    timeout: float = 30.0,
    max_output_bytes: int = 100_000,
    allowlist: frozenset[str] | None = None,
    cwd: str | Path | None = None,
) -> dict:
    if allowlist is not None:
        check_command_allowlist(command, allowlist)
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=False,
            timeout=timeout,
            cwd=cwd,
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
        "truncated": stdout_len > max_output_bytes or stderr_len > max_output_bytes,
    }


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