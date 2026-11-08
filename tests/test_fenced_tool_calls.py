"""BD-5 — a small model's ``raiker:<tool>`` fence is read as the call it meant."""

from __future__ import annotations

from raiker.models.providers.llama_cpp_server import _parse_text_json_tool_calls


def test_fenced_calls_become_proposals_and_answer_blocks_never_do() -> None:
    text = (
        "Let me look.\n"
        "```raiker:read_file path=test_stats.py offset=1 limit=100```\n"
        '```raiker:table {"caption": "not a call"}```\n'
        '```raiker:write_file path=stats.py text="def average(values):\n    return sum(values) / len(values)\n"```'
    )
    calls = _parse_text_json_tool_calls(text)
    assert [call.tool_name for call in calls] == ["read_file", "write_file"]
    assert calls[0].arguments == {"path": "test_stats.py", "offset": 1, "limit": 100}
    assert calls[1].arguments["text"] == "def average(values):\n    return sum(values) / len(values)\n"


def test_a_real_newline_inside_a_fence_is_kept() -> None:
    text = '```raiker:write_file path=a.py text="x = 1\ny = 2"```'
    (call,) = _parse_text_json_tool_calls(text)
    assert call.arguments["text"] == "x = 1\ny = 2"


def test_the_json_form_still_works_and_plain_prose_is_no_call() -> None:
    assert _parse_text_json_tool_calls('{"tool": "read_file", "arguments": {"path": "a"}}')[0].tool_name == "read_file"
    assert _parse_text_json_tool_calls("No tools needed here.") == []
