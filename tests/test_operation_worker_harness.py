"""OPT-11 — one harness owns the state mechanics of every model-operation worker."""

from __future__ import annotations

import ast
import asyncio
import inspect
from pathlib import Path

import pytest

from raiker.api import routes_models
from raiker.models.local_operations import (
    ModelOperationRequest,
    ModelOperationService,
    OperationCancelled,
    OperationWorker,
    run_operation,
    run_operation_async,
)
from raiker.storage.sqlite import SQLiteStore

OWNER = "owner"


def _operation(tmp_path: Path) -> tuple[ModelOperationService, str]:
    service = ModelOperationService(SQLiteStore(tmp_path))
    operation = service.start(
        OWNER,
        ModelOperationRequest(kind="pull", target="tiny", confirmed=True),
        payload={"model": "tiny"},
    )
    return service, operation.operation_id


def _run(service: ModelOperationService, operation_id: str, work, then=None) -> None:  # type: ignore[no-untyped-def]
    run_operation(
        service, OWNER, operation_id, phase="working", failure_code="job_failed", work=work, then=then
    )


def test_a_finished_job_completes_and_then_runs_its_follow_up(tmp_path: Path) -> None:
    service, operation_id = _operation(tmp_path)
    followed: list[str] = []

    _run(service, operation_id, lambda op: None, then=lambda: followed.append("rescan"))

    assert service.require(OWNER, operation_id).state == "complete"
    assert followed == ["rescan"]


def test_a_job_cancelled_before_it_was_claimed_never_runs(tmp_path: Path) -> None:
    service, operation_id = _operation(tmp_path)
    service.cancel(OWNER, operation_id)  # queued → cancelled at once
    ran: list[bool] = []

    _run(service, operation_id, lambda op: ran.append(True))

    assert ran == []
    assert service.require(OWNER, operation_id).state == "cancelled"


def test_a_cancellation_point_settles_cancelled_and_undoes_what_was_started(
    tmp_path: Path,
) -> None:
    service, operation_id = _operation(tmp_path)
    undone: list[str] = []

    def work(op: OperationWorker) -> None:
        op.on_abort(lambda: undone.append("stop slot"))
        service.cancel(OWNER, operation_id)  # the owner presses Cancel mid-job
        op.check_cancelled()
        pytest.fail("the cancellation point must stop the job")

    _run(service, operation_id, work)

    row = service.require(OWNER, operation_id)
    assert row.state == "cancelled"
    assert row.error_code is None
    assert undone == ["stop slot"]


def test_a_failure_exposes_only_its_bounded_code(tmp_path: Path) -> None:
    service, operation_id = _operation(tmp_path)
    undone: list[str] = []

    def work(op: OperationWorker) -> None:
        op.on_abort(lambda: undone.append("cleanup"))
        raise RuntimeError("/home/owner/secret/path did something")

    _run(service, operation_id, work)

    row = service.require(OWNER, operation_id)
    assert (row.state, row.error_code) == ("failed", "job_failed")
    assert undone == ["cleanup"]


def test_a_cancel_after_the_last_check_is_still_the_owners_decision(tmp_path: Path) -> None:
    service, operation_id = _operation(tmp_path)

    _run(service, operation_id, lambda op: service.cancel(OWNER, operation_id) and None)

    assert service.require(OWNER, operation_id).state == "cancelled"


def test_the_async_form_settles_the_same_way(tmp_path: Path) -> None:
    service, operation_id = _operation(tmp_path)

    async def work(op: OperationWorker) -> None:
        op.progress(completed_bytes=5, total_bytes=10, phase="pulling")
        raise OperationCancelled

    asyncio.run(
        run_operation_async(
            service, OWNER, operation_id, phase="pulling", failure_code="job_failed", work=work
        )
    )

    assert service.require(OWNER, operation_id).state == "cancelled"


def test_no_worker_settles_an_operation_by_hand() -> None:
    """The five workers name their failure code and leave the transitions to the harness."""
    tree = ast.parse(inspect.getsource(routes_models))
    workers = {
        "_run_hugging_face_download",
        "_run_local_deployment",
        "_run_mlx_deployment",
        "_run_model_conversion",
        "_pull_ollama_model",
    }
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in workers:
            found.add(node.name)
            called = {
                call.func.attr
                for call in ast.walk(node)
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
            }
            assert not called & {"running", "complete", "fail", "cancelled"}, node.name
    assert found == workers
