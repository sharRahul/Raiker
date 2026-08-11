from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

import httpx

from apps.web.e2e.fixtures.stub_model import MODEL_ID, serve

TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": name,
            "description": name,
            "parameters": {"type": "object", "additionalProperties": True},
        },
    }
    for name in ("read_file", "list_directory", "write_file")
]


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


@contextmanager
def running_stub() -> Iterator[str]:
    port = _free_port()
    thread = threading.Thread(target=serve, args=(port,), daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}/v1"
    for _ in range(100):
        try:
            if httpx.get(f"{base}/models", timeout=0.1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.01)
    else:
        raise AssertionError("stub model did not start")
    yield base


def _completion(base: str, prompt: str, *, messages: list[dict[str, str]] | None = None) -> dict:
    response = httpx.post(
        f"{base}/chat/completions",
        json={
            "model": MODEL_ID,
            "stream": False,
            "messages": messages or [{"role": "user", "content": prompt}],
            "tools": TOOL_SPECS,
        },
        timeout=2,
    )
    response.raise_for_status()
    return response.json()


def _calls(response: dict) -> list[dict]:
    return response["choices"][0]["message"].get("tool_calls", [])


def test_stub_catalogue_and_deterministic_batch_shapes() -> None:
    with running_stub() as base:
        models = httpx.get(f"{base}/models", timeout=2).json()
        assert [item["id"] for item in models["data"]] == [MODEL_ID]

        refusal_then_read = _calls(
            _completion(base, "Read ../escape.md and list the workspace.")
        )
        assert [call["function"]["name"] for call in refusal_then_read] == [
            "read_file",
            "list_directory",
        ]

        three_writes = _calls(_completion(base, "Write one.md, two.md and three.md."))
        assert [call["function"]["name"] for call in three_writes] == [
            "write_file",
            "write_file",
            "write_file",
        ]
        assert all(
            set(json.loads(call["function"]["arguments"])) == {"path", "text"}
            for call in three_writes
        )

        refusal_then_writes = _calls(
            _completion(
                base,
                "Run the batch: read ../escape.md, then write one.md and three.md.",
            )
        )
        assert [call["function"]["name"] for call in refusal_then_writes] == [
            "read_file",
            "write_file",
            "write_file",
        ]


def test_stub_answers_after_tool_results_and_streams_valid_sse() -> None:
    with running_stub() as base:
        follow_up = _completion(
            base,
            "",
            messages=[
                {"role": "user", "content": "Read ../escape.md and list the workspace."},
                {"role": "tool", "tool_call_id": "call_outside", "content": "policy refused"},
                {"role": "tool", "tool_call_id": "call_list", "content": "README.md"},
            ],
        )
        assert "policy refused that one call" in follow_up["choices"][0]["message"]["content"]

        with httpx.stream(
            "POST",
            f"{base}/chat/completions",
            json={
                "model": MODEL_ID,
                "stream": True,
                "messages": [{"role": "user", "content": "Write one.md, two.md and three.md."}],
                "tools": TOOL_SPECS,
            },
            timeout=2,
        ) as response:
            response.raise_for_status()
            body = response.read().decode()
        assert "data: {" in body
        assert '"tool_calls"' in body
        assert body.rstrip().endswith("data: [DONE]")
