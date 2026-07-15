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


def test_memory_job_metrics_report_queue_worker_and_error_state(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path)
    completed = store.enqueue_memory_job("integrity_scan", "completed")
    assert run_one_memory_job(store=store, workspace_root=tmp_path) is not None
    dead_letter = store.enqueue_memory_job("reconcile", "dead-letter", max_attempts=1)
    claimed = store.claim_memory_job("2100-01-01T00:00:00Z")
    assert claimed is not None and claimed["job_id"] == dead_letter
    assert store.finish_memory_job(dead_letter, "simulated failure")
    store.enqueue_memory_job("reconcile", "queued")
    metrics = store.memory_job_metrics()
    assert completed
    assert metrics["queue_depth"] == 1
    assert metrics["completed_count"] == 1
    assert metrics["dead_letter_count"] == 1
    assert metrics["running_count"] == 0
    assert metrics["average_completion_latency_ms"] >= 0
