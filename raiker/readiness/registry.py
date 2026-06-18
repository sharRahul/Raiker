from __future__ import annotations

from typing import Any, Protocol, TypeVar


class ReadinessRecord(Protocol):
    @property
    def readiness_id(self) -> str: ...

    @property
    def blockers(self) -> tuple[str, ...]: ...

    @property
    def required_gates(self) -> tuple[str, ...]: ...


T = TypeVar("T", bound=ReadinessRecord)


def sort_readiness_records(records: list[T]) -> list[T]:
    return sorted(records, key=lambda record: record.readiness_id)


def get_readiness_by_id(records: list[T], readiness_id: str) -> T | None:
    for record in records:
        if record.readiness_id == readiness_id:
            return record
    return None


def summarize_readiness_records(
    records: list[T],
    *,
    latest_key: str,
    count_key: str,
    metadata_only_key: str,
) -> dict[str, Any]:
    latest = sort_readiness_records(records)[-1]
    return {
        metadata_only_key: True,
        count_key: len(records),
        latest_key: latest.readiness_id,
        "metadata_only": True,
        "blocker_count": len(latest.blockers),
        "required_gate_count": len(latest.required_gates),
    }


def render_readiness_records(records: dict[str, Any]) -> list[str]:
    return [f"{key}: {value}" for key, value in records.items()]
