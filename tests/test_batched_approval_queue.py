"""ADD-02 — a batched turn is walked one decision at a time.

B4 made independent reads run concurrently and B2 made a parked turn resume, but
between them a batch of *mutations* still stopped dead at the first one: the
calls behind it were dropped with an event and the owner had no way to get them
back except by re-prompting. A model that proposes three edits in one batch was
therefore a model that got one edit.

These tests cover the queue that closes that: the remainder of the batch is
parked with the turn, drained one call at a time on resume, re-governed per call
rather than inheriting the first decision, and a refusal skips its own call
instead of abandoning the ones behind it.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from raiker.api.app import create_app
from raiker.cli.principal_resolver import bootstrap_owner
from raiker.models.contracts import ModelResponse, ToolCallProposal
from raiker.runtime.turn_suspension import (
    deserialize_messages,
    deserialize_pending_calls,
    serialize_pending_calls,
)
from raiker.storage.sqlite import SQLiteStore
from tests.test_turn_resume_after_approval import (  # reuse the B2 harness verbatim
    ScriptedRouter,
    _envelope,
    _event_types,
    _orchestrator,
    _park_turn,
)

__all__ = ["headers", "scripted_model", "workspace"]

# Re-exported so the fixtures the B2 suite defines are available here too.
from tests.test_turn_resume_after_approval import (  # noqa: E402
    headers,
    scripted_model,
    workspace,
)


def _write(name: str, text: str) -> ToolCallProposal:
    return ToolCallProposal(
        call_id=f"call_{name}",
        tool_name="write_file",
        arguments={"path": f"{name}.md", "text": text},
    )


def _read(name: str, path: str) -> ToolCallProposal:
    return ToolCallProposal(
        call_id=f"call_{name}", tool_name="read_file", arguments={"path": path}
    )


def _three_writes() -> list[ToolCallProposal]:
    return [_write("one", "# One\n"), _write("two", "# Two\n"), _write("three", "# Three\n")]


class TestTheBatchIsParkedNotDropped:
    def test_the_calls_behind_the_boundary_are_queued_with_the_turn(
        self, tmp_path: Path
    ) -> None:
        router = ScriptedRouter([
            ModelResponse(text="Writing all three.", tool_calls=_three_writes())
        ])
        orchestrator = _orchestrator(tmp_path, router)
        envelope = _envelope("Write three files")

        response = asyncio.run(orchestrator.ahandle(envelope))

        assert response.status == "needs_approval"
        assert response.approval is not None
        assert response.approval["queue_position"] == 1
        assert response.approval["queue_total"] == 3
        assert response.approval["queued_calls"] == 2
        assert "decision 1 of 3" in str(response.approval["message"])

        row = SQLiteStore(tmp_path).load_suspended_turn(
            str(response.approval["approval_id"])
        )
        assert row is not None
        queued = deserialize_pending_calls(row["pending_calls_json"])
        # In the order the model proposed them — a queue that reorders the
        # model's own plan would change the work the owner is approving.
        assert [call.call_id for call in queued] == ["call_two", "call_three"]
        assert row["queue_position"] == 1
        assert row["queue_total"] == 3

    def test_the_queue_is_evidence_not_a_silent_drop(self, tmp_path: Path) -> None:
        router = ScriptedRouter([
            ModelResponse(text="Writing all three.", tool_calls=_three_writes())
        ])
        orchestrator = _orchestrator(tmp_path, router)
        envelope = _envelope("Write three files")
        asyncio.run(orchestrator.ahandle(envelope))

        types = _event_types(orchestrator, envelope.session_id)
        assert "model_tool_calls_queued" in types
        # The calls are held, not lost, so the drop event must *not* fire: an
        # owner reading the log has to be able to tell the two apart.
        assert "model_tool_calls_dropped" not in types

    def test_the_queue_carries_no_conversation_content(self, tmp_path: Path) -> None:
        router = ScriptedRouter([
            ModelResponse(
                text="Writing the confidential merger memo.",
                tool_calls=[
                    _write("one", "# One\n"),
                    _write("two", "acquisition price is 4.2 billion"),
                ],
            )
        ])
        orchestrator = _orchestrator(tmp_path, router)
        envelope = _envelope("Write the merger memo")
        asyncio.run(orchestrator.ahandle(envelope))

        path = orchestrator.writer.path_for_session(envelope.session_id)
        log = path.read_text(encoding="utf-8")
        queued = [
            json.loads(line)
            for line in log.splitlines()
            if json.loads(line)["event_type"] == "model_tool_calls_queued"
        ]
        assert queued
        assert set(queued[0]["payload"]) - {"client"} == {
            "proposed", "queued", "queue_position", "queue_total", "reason"
        }
        assert "4.2 billion" not in json.dumps(queued[0])

    def test_a_single_call_batch_still_reads_as_one_decision(self, tmp_path: Path) -> None:
        router = ScriptedRouter([
            ModelResponse(text="One file.", tool_calls=[_write("one", "# One\n")])
        ])
        orchestrator = _orchestrator(tmp_path, router)

        response = asyncio.run(orchestrator.ahandle(_envelope("Write one file")))

        assert response.approval is not None
        assert response.approval["queue_total"] == 1
        assert response.approval["queued_calls"] == 0
        # No batch, so no batch language: an owner deciding one action should not
        # be told it is "decision 1 of 1".
        assert "decision" not in str(response.approval["message"]).lower()


class TestReadsBeforeTheBoundaryAreKept:
    def test_a_completed_read_survives_into_the_parked_conversation(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "notes.md").write_text("# Notes\n", encoding="utf-8")
        router = ScriptedRouter([
            ModelResponse(
                text="Reading, then writing.",
                tool_calls=[_read("notes", "notes.md"), _write("one", "# One\n")],
            )
        ])
        orchestrator = _orchestrator(tmp_path, router)
        envelope = _envelope("Read the notes then write the report")

        response = asyncio.run(orchestrator.ahandle(envelope))

        assert response.approval is not None
        row = SQLiteStore(tmp_path).load_suspended_turn(
            str(response.approval["approval_id"])
        )
        assert row is not None
        parked = deserialize_messages(str(row["messages_json"]))
        # The read really ran, so its result belongs in the transcript the model
        # resumes into. Without this the model wakes into a conversation where
        # its own completed work never happened.
        tool_results = [m for m in parked if m.role == "tool"]
        assert [m.tool_call_id for m in tool_results] == ["call_notes"]
        assert parked[-1].role == "assistant"
        assert parked[-1].tool_calls[0].call_id == "call_one"
        # And the budget it already spent is carried, not refunded.
        assert row["tool_calls_made"] == 1


class TestTheQueueIsDrainedOnResume:
    def test_resuming_lands_on_the_next_decision_not_on_the_model(
        self, workspace: Path, headers: dict[str, str], scripted_model: ScriptedRouter
    ) -> None:
        router = ScriptedRouter([
            ModelResponse(text="Writing all three.", tool_calls=_three_writes()),
            ModelResponse(text="This must not be reached yet."),
        ])
        scripted_model.responses = router.responses
        approval_id, _envelope_used = _park_turn(workspace, scripted_model)
        client = TestClient(create_app(workspace))
        calls_before = scripted_model.calls

        resolved = client.post(
            f"/api/approvals/{approval_id}/resolve",
            json={"approve": True, "reason": "ship it"},
            headers=headers,
        )
        assert resolved.status_code == 200, resolved.text
        assert resolved.json()["resume"]["queued_calls"] == 2

        resumed = client.post(f"/api/approvals/{approval_id}/resume", headers=headers)
        assert resumed.status_code == 200, resumed.text
        body = resumed.json()

        # The turn stopped at the *second* call in the batch, and it did so
        # without asking the model anything: the model already proposed this
        # call, so paying for a round trip to hear it again is pure waste.
        assert body["status"] == "needs_approval"
        assert body["approval"]["queue_position"] == 2
        assert body["approval"]["queue_total"] == 3
        assert body["approval"]["queued_calls"] == 1
        assert scripted_model.calls == calls_before
        assert (workspace / "one.md").read_text(encoding="utf-8") == "# One\n"

    def test_the_whole_batch_can_be_walked_to_the_end(
        self, workspace: Path, headers: dict[str, str], scripted_model: ScriptedRouter
    ) -> None:
        router = ScriptedRouter([
            ModelResponse(text="Writing all three.", tool_calls=_three_writes()),
            ModelResponse(text="All three files are written."),
        ])
        scripted_model.responses = router.responses
        approval_id, _envelope_used = _park_turn(workspace, scripted_model)
        client = TestClient(create_app(workspace))

        body: dict[str, Any] = {}
        for expected_position in (1, 2, 3):
            resolved = client.post(
                f"/api/approvals/{approval_id}/resolve",
                json={"approve": True, "reason": "ship it"},
                headers=headers,
            )
            assert resolved.status_code == 200, resolved.text
            assert resolved.json()["resume"]["queue_position"] == expected_position
            resumed = client.post(f"/api/approvals/{approval_id}/resume", headers=headers)
            assert resumed.status_code == 200, resumed.text
            body = resumed.json()
            approval = body.get("approval")
            if approval is None:
                break
            approval_id = str(approval["approval_id"])

        assert body["status"] == "completed"
        for name, text in (("one", "# One\n"), ("two", "# Two\n"), ("three", "# Three\n")):
            assert (workspace / f"{name}.md").read_text(encoding="utf-8") == text

    def test_a_rejection_still_walks_the_rest_of_the_batch(
        self, workspace: Path, headers: dict[str, str], scripted_model: ScriptedRouter
    ) -> None:
        router = ScriptedRouter([
            ModelResponse(text="Writing all three.", tool_calls=_three_writes()),
            ModelResponse(text="Understood — I skipped the first file."),
        ])
        scripted_model.responses = router.responses
        approval_id, _envelope_used = _park_turn(workspace, scripted_model)
        client = TestClient(create_app(workspace))

        rejected = client.post(
            f"/api/approvals/{approval_id}/resolve",
            json={"approve": False, "reason": "not that one"},
            headers=headers,
        )
        assert rejected.status_code == 200, rejected.text
        resumed = client.post(f"/api/approvals/{approval_id}/resume", headers=headers)
        assert resumed.status_code == 200, resumed.text
        body = resumed.json()

        # Rejecting one call is a decision about that call. The two behind it are
        # still the owner's to make, so the turn presents the next one rather
        # than treating the refusal as a verdict on the whole batch.
        assert body["status"] == "needs_approval"
        assert body["approval"]["queue_position"] == 2
        assert not (workspace / "one.md").exists()

    def test_a_policy_refusal_inside_the_queue_skips_only_its_own_call(
        self, workspace: Path, headers: dict[str, str], scripted_model: ScriptedRouter
    ) -> None:
        router = ScriptedRouter([
            ModelResponse(
                text="Writing, reading, writing.",
                tool_calls=[
                    _write("one", "# One\n"),
                    # Outside the workspace: the policy engine refuses this on
                    # its own terms, with no approval to make.
                    _read("outside", "../escape.md"),
                    _write("three", "# Three\n"),
                ],
            ),
            ModelResponse(text="Two files written; the read was refused."),
        ])
        scripted_model.responses = router.responses
        approval_id, _envelope_used = _park_turn(workspace, scripted_model)
        client = TestClient(create_app(workspace))

        client.post(
            f"/api/approvals/{approval_id}/resolve",
            json={"approve": True, "reason": "ship it"},
            headers=headers,
        )
        resumed = client.post(f"/api/approvals/{approval_id}/resume", headers=headers)
        assert resumed.status_code == 200, resumed.text
        body = resumed.json()

        # ADD-02's rule: the refusal is reported against its own call and the
        # queue carries on to the third, which still needs its own decision.
        assert body["status"] == "needs_approval"
        assert body["approval"]["tool_name"] == "write_file"
        assert body["approval"]["queue_position"] == 3
        assert not (workspace / "escape.md").exists()

    def test_a_refused_call_does_not_make_the_whole_turn_read_as_failed(
        self, workspace: Path, headers: dict[str, str], scripted_model: ScriptedRouter
    ) -> None:
        router = ScriptedRouter([
            ModelResponse(
                text="Writing, then reading somewhere I should not.",
                tool_calls=[_write("one", "# One\n"), _read("outside", "../escape.md")],
            ),
            ModelResponse(text="One file written; the read was outside the workspace."),
        ])
        scripted_model.responses = router.responses
        approval_id, _envelope_used = _park_turn(workspace, scripted_model)
        client = TestClient(create_app(workspace))

        client.post(
            f"/api/approvals/{approval_id}/resolve",
            json={"approve": True, "reason": "ship it"},
            headers=headers,
        )
        resumed = client.post(f"/api/approvals/{approval_id}/resume", headers=headers)
        assert resumed.status_code == 200, resumed.text
        body = resumed.json()

        # The turn answered. A call policy refused along the way is reported as
        # its own refusal — it must not become the verdict on everything the turn
        # went on to do correctly.
        assert body["status"] == "completed"
        assert "outside the workspace" in body["message"]


class TestQueueMetadataReachesTheOwner:
    def test_the_approvals_list_places_each_decision_in_its_batch(
        self, workspace: Path, headers: dict[str, str], scripted_model: ScriptedRouter
    ) -> None:
        scripted_model.responses = [
            ModelResponse(text="Writing all three.", tool_calls=_three_writes())
        ]
        approval_id, _envelope_used = _park_turn(workspace, scripted_model)
        client = TestClient(create_app(workspace))

        listed = client.get("/api/approvals?status_filter=pending", headers=headers)
        assert listed.status_code == 200, listed.text
        rows = {row["approval_id"]: row for row in listed.json()}
        assert rows[approval_id]["queue_position"] == 1
        assert rows[approval_id]["queue_total"] == 3

        detail = client.get(f"/api/approvals/{approval_id}", headers=headers)
        assert detail.status_code == 200, detail.text
        assert detail.json()["approval"]["queue_total"] == 3

    def test_an_approval_with_no_parked_turn_is_a_batch_of_one(
        self, workspace: Path, headers: dict[str, str], scripted_model: ScriptedRouter
    ) -> None:
        scripted_model.responses = [
            ModelResponse(text="One file.", tool_calls=[_write("one", "# One\n")])
        ]
        approval_id, _envelope_used = _park_turn(workspace, scripted_model)
        client = TestClient(create_app(workspace))

        listed = client.get("/api/approvals?status_filter=pending", headers=headers)
        row = next(r for r in listed.json() if r["approval_id"] == approval_id)
        assert (row["queue_position"], row["queue_total"]) == (1, 1)


class TestQueueSerialisationFailsSoft:
    @pytest.mark.parametrize(
        "raw", ["", None, "not json", '{"call_id": "x"}', "[3]", '[{"call_id": ""}]']
    )
    def test_an_unreadable_queue_drains_to_nothing(self, raw: str | None) -> None:
        # Deliberately softer than the conversation: a queue that cannot be read
        # costs the calls behind a decision, but failing the resume outright
        # would throw away the decision the owner already made.
        assert deserialize_pending_calls(raw) == []

    def test_a_queue_round_trips_exactly(self) -> None:
        calls = _three_writes()[1:]
        restored = deserialize_pending_calls(serialize_pending_calls(calls))
        assert [(c.call_id, c.tool_name, c.arguments) for c in restored] == [
            (c.call_id, c.tool_name, c.arguments) for c in calls
        ]


def _bootstrapped(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    bootstrap_owner("owner", "Owner", workspace_root=ws)
    return ws


class TestTheQueueColumnsAreBackwardsCompatible:
    def test_a_row_written_without_a_queue_reads_as_one_of_one(
        self, tmp_path: Path
    ) -> None:
        store = SQLiteStore(_bootstrapped(tmp_path))
        store.insert_suspended_turn({
            "approval_id": "appr_legacy",
            "session_id": "sess_legacy",
            "turn_id": "turn_legacy",
            "request_id": "req_legacy",
            "principal_id": "principal_owner",
            "action_id": "act_legacy",
            "tool_name": "write_file",
            "call_id": "call_legacy",
            "prompt_text": "write it",
            "messages_json": "[]",
            "options_json": "{}",
            "client_json": "{}",
            "tool_calls_made": 0,
        })

        row = store.load_suspended_turn("appr_legacy")
        assert row is not None
        assert row["pending_calls_json"] == "[]"
        assert (row["queue_position"], row["queue_total"]) == (1, 1)
        assert store.suspended_turn_queue_positions(["appr_legacy"]) == {
            "appr_legacy": (1, 1)
        }

    def test_positions_are_looked_up_in_one_pass(self, tmp_path: Path) -> None:
        store = SQLiteStore(_bootstrapped(tmp_path))
        assert store.suspended_turn_queue_positions([]) == {}
        assert store.suspended_turn_queue_positions(["appr_missing"]) == {}
