from __future__ import annotations

import json
import secrets
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class MemorySecurityProbeResult:
    supported: bool
    reason_code: str
    sqlcipher_version: str | None
    checked_at: str


def _checked_at() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def probe_memory_security(
    workspace_root: str | Path, *, timeout_seconds: float = 10.0
) -> MemorySecurityProbeResult:
    """Test SQLCipher page locking in a disposable child process.

    Some Windows SQLCipher builds terminate the process after VirtualLock fails.
    The resident server must therefore interpret the child's exit status rather
    than trying the pragma against a production connection.
    """

    probe_parent = Path(workspace_root).resolve() / ".raiker" / "runtime" / "probes"
    probe_parent.mkdir(parents=True, exist_ok=True)
    checked_at = _checked_at()
    with tempfile.TemporaryDirectory(prefix="sqlcipher-", dir=probe_parent) as raw_dir:
        payload = json.dumps(
            {"database": str(Path(raw_dir) / "probe.db"), "key": secrets.token_hex(32)}
        )
        try:
            completed = subprocess.run(
                [sys.executable, "-m", "raiker.storage.sqlcipher_probe_worker"],
                input=payload,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return MemorySecurityProbeResult(False, "probe_timeout", None, checked_at)
        except OSError:
            return MemorySecurityProbeResult(False, "probe_unavailable", None, checked_at)

    if completed.returncode != 0:
        unsigned_code = completed.returncode & 0xFFFFFFFF
        reason = "host_crash" if unsigned_code == 0xC00000FD else "probe_failed"
        return MemorySecurityProbeResult(False, reason, None, checked_at)
    try:
        result = json.loads(completed.stdout)
    except (json.JSONDecodeError, TypeError):
        return MemorySecurityProbeResult(False, "invalid_probe_result", None, checked_at)
    supported = result.get("status") == "supported"
    version = str(result.get("sqlcipher_version") or "") or None
    return MemorySecurityProbeResult(
        supported,
        "supported" if supported else "probe_failed",
        version,
        checked_at,
    )

