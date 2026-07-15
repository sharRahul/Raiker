from pathlib import Path

from raiker.memory.jobs import run_one_memory_job
from raiker.storage.sqlite import SQLiteStore


def test_memory_job_is_idempotent_and_completes(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    first = store.enqueue_memory_job("integrity_scan", "daily")
    assert store.enqueue_memory_job("integrity_scan", "daily") == first
    result = run_one_memory_job(store=store, workspace_root=tmp_path)
    assert result is not None and result["job_id"] == first
    with store.connect() as connection:
        assert connection.execute("SELECT status FROM memory_jobs WHERE job_id = ?", (first,)).fetchone()["status"] == "completed"


def test_memory_job_dead_letters_after_attempt_budget(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    job_id = store.enqueue_memory_job("reconcile", "broken", max_attempts=1)
    job = store.claim_memory_job("2100-01-01T00:00:00Z")
    assert job is not None and job["job_id"] == job_id
    assert store.finish_memory_job(job_id, "simulated failure")
    with store.connect() as connection:
        assert connection.execute("SELECT status FROM memory_jobs WHERE job_id = ?", (job_id,)).fetchone()["status"] == "dead_letter"


def test_memory_job_rate_limit_is_enforced(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    assert store.consume_memory_job_rate_limit("reconcile", limit_per_minute=1)
    assert not store.consume_memory_job_rate_limit("reconcile", limit_per_minute=1)
