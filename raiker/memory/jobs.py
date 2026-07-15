"""Bounded owner-started execution of idempotent hybrid-memory maintenance jobs."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from raiker.memory.integrity import inspect_memory_integrity
from raiker.storage.sqlite import SQLiteStore


def run_one_memory_job(*, store: SQLiteStore, workspace_root: str | Path) -> dict[str, object] | None:
    lease_until = (datetime.now(UTC) + timedelta(minutes=5)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    job = store.claim_memory_job(lease_until)
    if job is None:
        return None
    try:
        result: dict[str, object]
        if job["job_type"] == "reconcile":
            result = dict(store.reconcile_memory_projections())
        elif job["job_type"] == "integrity_scan":
            result = inspect_memory_integrity(store=store, workspace_root=workspace_root).__dict__
        else:
            raise ValueError("unsupported_memory_job")
    except Exception as error:
        store.finish_memory_job(str(job["job_id"]), str(error))
        raise
    store.finish_memory_job(str(job["job_id"]))
    return {"job_id": str(job["job_id"]), "job_type": str(job["job_type"]), "result": result}
