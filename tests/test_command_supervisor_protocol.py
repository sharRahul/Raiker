from __future__ import annotations

import json

import pytest

from raiker.execution.commands.supervisor_protocol import (
    AuthenticationFailed,
    FrameTooLarge,
    ReplayRejected,
    SupervisorCodec,
)


def test_authenticated_frame_round_trip() -> None:
    codec = SupervisorCodec(b"k" * 32)
    encoded = codec.encode("start", {"run_id": "cmd_1", "argv": ["npm", "test"]})
    decoded = codec.decode(encoded)
    assert decoded.kind == "start"
    assert decoded.payload["run_id"] == "cmd_1"
    assert decoded.version == 1


def test_tampered_frame_is_rejected_before_json_is_trusted() -> None:
    codec = SupervisorCodec(b"k" * 32)
    encoded = bytearray(codec.encode("status", {"run_id": "cmd_1"}))
    encoded[-1] ^= 1
    with pytest.raises(AuthenticationFailed):
        codec.decode(bytes(encoded))


def test_nonce_replay_is_rejected() -> None:
    codec = SupervisorCodec(b"k" * 32)
    encoded = codec.encode("attach", {"run_id": "cmd_1"})
    codec.decode(encoded)
    with pytest.raises(ReplayRejected):
        codec.decode(encoded)


def test_length_prefix_is_bounded_and_exact() -> None:
    codec = SupervisorCodec(b"k" * 32, max_frame_bytes=64)
    with pytest.raises(FrameTooLarge):
        codec.encode("start", {"data": "x" * 100})

    valid = SupervisorCodec(b"k" * 32).encode("status", {})
    length = int.from_bytes(valid[:4], "big")
    assert length == len(valid) - 4
    with pytest.raises(ValueError, match="supervisor_frame_length_invalid"):
        SupervisorCodec(b"k" * 32).decode(valid[:-1])


def test_payload_uses_canonical_json() -> None:
    codec = SupervisorCodec(b"k" * 32, nonce_factory=lambda: "nonce-fixed")
    frame = codec.encode("status", {"z": 1, "a": 2})
    body = json.loads(frame[4:])
    assert list(body["payload"]) == ["a", "z"]
