"""A malformed tool call goes back to the model to correct, a bounded number of times.

Found by BD-5: Qwen3-8B sent `edit_file` without `old_text`, and the whole turn
ended on "the requested tool call was invalid" when one more try would have
fixed it.
"""

from __future__ import annotations

import json
from pathlib import Path

from raiker.models.contracts import ModelResponse, ToolCallProposal
from raiker.runtime.orchestrator import MAX_CALL_CORRECTIONS
from tests.test_model_tool_call_loop import FakeRouter, _envelope, _events, _handle, _orchestrator

BAD = ToolCallProposal("call_bad", "read_file", {})
GOOD = ToolCallProposal("call_good", "list_directory", {"path": "."})
DONE = ModelResponse(text="Listed it.", tool_calls=[], finish_reason="stop")


def _calls(*proposals: ToolCallProposal) -> ModelResponse:
    return ModelResponse(text="", tool_calls=list(proposals), finish_reason="tool_calls")


def test_the_model_is_told_why_and_its_corrected_call_runs(tmp_path: Path) -> None:
    router = FakeRouter([_calls(BAD), _calls(GOOD), DONE])
    orchestrator = _orchestrator(tmp_path, router)
    envelope = _envelope("list the folder")
    response = _handle(orchestrator, envelope)

    events = _events(orchestrator, envelope.session_id)
    assert events.count("model_tool_call_rejected") == 1
    assert "tool_completed" in events
    assert response.status == "completed"
    assert "invalid" not in response.message

    told = next(m for m in router.seen_messages[1] if m.role == "tool" and m.tool_call_id == "call_bad")
    payload = json.loads(told.content)
    assert payload["reason"] == "missing_argument:path"
    assert payload["required_arguments"] == ["path"]


def test_a_valid_call_beside_a_bad_one_did_not_run_and_says_so(tmp_path: Path) -> None:
    router = FakeRouter([_calls(GOOD, BAD), DONE])
    orchestrator = _orchestrator(tmp_path, router)
    envelope = _envelope("list the folder")
    _handle(orchestrator, envelope)

    assert "tool_started" not in _events(orchestrator, envelope.session_id)
    results = {m.tool_call_id: json.loads(m.content) for m in router.seen_messages[1] if m.role == "tool"}
    assert results["call_good"]["status"] == "not_run"
    assert results["call_bad"]["status"] == "error"


def test_corrections_are_bounded_and_the_turn_then_says_the_call_was_invalid(tmp_path: Path) -> None:
    router = FakeRouter([_calls(BAD)])
    orchestrator = _orchestrator(tmp_path, router)
    envelope = _envelope("read it")
    response = _handle(orchestrator, envelope)

    assert _events(orchestrator, envelope.session_id).count("model_tool_call_rejected") == MAX_CALL_CORRECTIONS + 1
    assert router.calls == MAX_CALL_CORRECTIONS + 1
    assert "requested tool call was invalid" in response.message


def test_an_output_limit_before_any_answer_is_not_reported_as_done(tmp_path: Path) -> None:
    from raiker.runtime.orchestrator import OUTPUT_LIMIT_BEFORE_ANSWER

    router = FakeRouter([ModelResponse(text="", tool_calls=[], finish_reason="length")])
    orchestrator = _orchestrator(tmp_path, router)
    response = _handle(orchestrator, _envelope("fix it"))
    assert response.status == "failed"
    assert response.message == OUTPUT_LIMIT_BEFORE_ANSWER


def test_a_cut_off_answer_is_kept_and_says_so(tmp_path: Path) -> None:
    from raiker.runtime.orchestrator import OUTPUT_LIMIT_CUT_OFF

    router = FakeRouter([ModelResponse(text="Here is the first half", tool_calls=[], finish_reason="length")])
    orchestrator = _orchestrator(tmp_path, router)
    response = _handle(orchestrator, _envelope("explain"))
    assert response.message.startswith("Here is the first half")
    assert OUTPUT_LIMIT_CUT_OFF in response.message


def test_managed_local_slots_leave_room_for_a_thinking_model() -> None:
    profiles = json.loads(Path("raiker/config/model-profiles.json").read_text(encoding="utf-8"))
    items = profiles.get("profiles", profiles)
    local = [p for p in (items if isinstance(items, list) else items.values()) if p.get("provider") in ("llama.cpp", "mlx")]
    assert local and all(int(p["max_tokens"]) >= 8192 for p in local)
