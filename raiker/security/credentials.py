"""Owner-scoped credential lifecycle metadata; never credential values."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from raiker.contracts.ids import utc_now
from raiker.storage.sqlite import SQLiteStore

WARNING_DAYS = 75
OVERDUE_DAYS = 90


@dataclass(frozen=True)
class CredentialLifecycleView:
    credential_id: str
    provider: str
    verified_at: str | None
    due_at: str
    status: str

    def to_dict(self) -> dict[str, str | None]:
        return {
            "credential_id": self.credential_id,
            "provider": self.provider,
            "verified_at": self.verified_at,
            "due_at": self.due_at,
            "status": self.status,
        }


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


class CredentialLifecycle:
    def __init__(self, store: SQLiteStore, *, clock: Callable[[], str] = utc_now) -> None:
        self._store = store
        self._clock = clock

    def record_verified(
        self, principal_id: str, provider: str, verified_at: str | None = None
    ) -> CredentialLifecycleView:
        at = verified_at or self._clock()
        row = self._store.upsert_credential_lifecycle(
            principal_id,
            provider.strip(),
            verified_at=at,
            due_at=(_parse(at) + timedelta(days=OVERDUE_DAYS)).isoformat().replace("+00:00", "Z"),
            status="current",
        )
        return self._view(row)

    def verify_replacement(self, principal_id: str, provider: str) -> CredentialLifecycleView:
        provider = provider.strip()
        if not provider or not self._store.has_connector_credential(principal_id, provider):
            raise ValueError("credential_not_configured")
        return self.record_verified(principal_id, provider)

    def list(self, principal_id: str) -> list[CredentialLifecycleView]:
        return [self._view(row) for row in self._store.list_credential_lifecycle(principal_id)]

    def _view(self, row: dict[str, object]) -> CredentialLifecycleView:
        verified_at = str(row["verified_at"] or row["rotated_at"])
        age_days = (_parse(self._clock()) - _parse(verified_at)).days
        status = "overdue" if age_days >= OVERDUE_DAYS else "warning" if age_days >= WARNING_DAYS else "current"
        return CredentialLifecycleView(
            credential_id=str(row["credential_id"]),
            provider=str(row["provider"]),
            verified_at=verified_at,
            due_at=str(row["due_at"]),
            status=status,
        )
