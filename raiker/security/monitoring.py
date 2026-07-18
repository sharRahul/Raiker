"""Redacted, opt-in local credential and runtime-health monitoring."""
from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from raiker.auth.vault_key_file import vault_status
from raiker.memory.policy import MemorySensitivity, classify_memory_sensitivity
from raiker.runtime.executors.sandbox import get_url
from raiker.storage.sqlite import SQLiteStore

MONITOR_SOURCE = "security_monitor"
HIBP_HOST = "api.pwnedpasswords.com"
_SENSITIVE = {MemorySensitivity.CREDENTIAL_LIKE, MemorySensitivity.SECRET_LIKE}


@dataclass(frozen=True)
class SecurityFinding:
    code: str
    severity: str
    summary: str


class SecurityMonitor:
    def __init__(
        self,
        store: SQLiteStore,
        workspace_root: str | Path,
        *,
        http_get: Callable[[str], str] | None = None,
    ) -> None:
        self._store = store
        self._workspace = Path(workspace_root).resolve()
        self._http_get = http_get or self._get_hibp_range

    def scan_configured_paths(self, principal_id: str) -> list[SecurityFinding]:
        findings: list[SecurityFinding] = []
        for path in self._configured_paths():
            try:
                text = path.read_text(encoding="utf-8", errors="replace")[:200_000]
            except OSError:
                continue
            label = classify_memory_sensitivity(text)
            subject = path.relative_to(self._workspace).as_posix()
            if label in _SENSITIVE:
                finding = self._open(
                    principal_id,
                    subject,
                    "local_sensitive_pattern",
                    "high",
                    f"Credential-like content detected in configured file '{subject}'.",
                    {"path": subject, "sensitivity": label.value},
                )
                if finding is not None:
                    findings.append(finding)
            else:
                self._recover(principal_id, subject, "local_sensitive_pattern")
        return findings

    def check_password_breach(
        self, principal_id: str, password: str, *, enabled: bool
    ) -> SecurityFinding | None:
        allowlist = self._breach_allowlist()
        if not enabled or HIBP_HOST not in allowlist or not password:
            return None
        digest = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
        prefix, suffix = digest[:5], digest[5:]
        response = self._http_get(f"https://{HIBP_HOST}/range/{prefix}")
        count = next(
            (int(parts[1]) for line in response.splitlines() if (parts := line.split(":", 1)) and parts[0] == suffix and len(parts) == 2 and parts[1].isdigit()),
            0,
        )
        if count:
            return self._open(
                principal_id,
                "account_credential",
                "breach_match",
                "high",
                "A credential appears in a breach corpus. Replace it now.",
                {"match_count": count},
            )
        self._recover(principal_id, "account_credential", "breach_match")
        return None

    def check_vault_health(self, principal_id: str) -> SecurityFinding | None:
        return self.observe_health(
            principal_id, "vault", healthy=vault_status(self._workspace) == "configured_valid"
        )

    def observe_health(self, principal_id: str, name: str, *, healthy: bool) -> SecurityFinding | None:
        subject, code = f"health:{name}", f"health_{name}_unhealthy"
        if healthy:
            self._recover(principal_id, subject, code)
            return None
        return self._open(
            principal_id,
            subject,
            code,
            "medium",
            f"Runtime health check failed: {name} needs attention.",
            {"check": name},
        )

    def _open(
        self, principal_id: str, subject: str, code: str, severity: str, summary: str, detail: dict[str, object]
    ) -> SecurityFinding | None:
        previous = self._store.get_security_monitor_state(principal_id, MONITOR_SOURCE, subject, code)
        if previous and previous["state"] == "open":
            return None
        finding_id = self._store.insert_security_finding(
            principal_id=principal_id, source=MONITOR_SOURCE, severity=severity, code=code,
            summary=summary, redacted_detail=detail, subject_id=subject,
        )
        self._store.insert_notification(
            principal_id=principal_id, kind="security_alert", title="Security finding", body=summary,
            finding_id=finding_id, subject_id=subject,
        )
        self._store.set_security_monitor_state(
            principal_id, MONITOR_SOURCE, subject, code, state="open", finding_id=finding_id
        )
        return SecurityFinding(code=code, severity=severity, summary=summary)

    def _recover(self, principal_id: str, subject: str, code: str) -> None:
        previous = self._store.get_security_monitor_state(principal_id, MONITOR_SOURCE, subject, code)
        if not previous or previous["state"] != "open":
            return
        finding_id = previous.get("finding_id")
        if isinstance(finding_id, str):
            self._store.set_security_finding_state(finding_id, principal_id, "resolved")
        self._store.insert_notification(
            principal_id=principal_id, kind="security_recovered", title="Security check recovered",
            body=f"Security check recovered: {subject}.", finding_id=finding_id if isinstance(finding_id, str) else None,
            subject_id=subject,
        )
        self._store.set_security_monitor_state(
            principal_id, MONITOR_SOURCE, subject, code, state="resolved", finding_id=finding_id if isinstance(finding_id, str) else None
        )

    def _configured_paths(self) -> list[Path]:
        raw = os.environ.get("RAIKER_SECURITY_SCAN_PATHS", "")
        paths: list[Path] = []
        for value in (part.strip() for part in raw.split(os.pathsep)):
            if not value:
                continue
            candidate = (self._workspace / value).resolve()
            try:
                candidate.relative_to(self._workspace)
            except ValueError:
                continue
            if candidate.is_file():
                paths.append(candidate)
        return paths

    @staticmethod
    def _breach_allowlist() -> frozenset[str]:
        raw = os.environ.get("RAIKER_SECURITY_BREACH_EGRESS_ALLOWLIST", "")
        return frozenset(part.strip() for part in raw.split(",") if part.strip())

    def _get_hibp_range(self, url: str) -> str:
        return str(get_url(url, egress_allowlist=self._breach_allowlist())["body_text"])
