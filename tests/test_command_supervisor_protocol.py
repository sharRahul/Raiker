from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from raiker.execution.commands.supervisor_protocol import (
    AuthenticationFailed,
    FrameTooLarge,
    ReplayRejected,
    SupervisorCodec,
    instance_key_from_hex,
    instance_key_to_hex,
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


# --- Shared cross-language wire vectors -------------------------------------
#
# Two codecs that each pass their own tests can still be unable to speak to each
# other. That is not hypothetical here: `json.dumps` escapes non-ASCII by
# default and Rust's `serde_json` does not, so before RAIKER-2033 every frame
# carrying real program output authenticated on one side and failed on the
# other. Only a vector file both implementations read can catch that, and only
# if the vectors contain non-ASCII — so they do.
VECTORS = json.loads(
    (Path(__file__).resolve().parent / "vectors" / "supervisor_protocol.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize("vector", VECTORS["vectors"], ids=lambda item: item["nonce"])
def test_shared_wire_vectors_encode_and_decode_byte_for_byte(
    vector: dict[str, Any],
) -> None:
    key = instance_key_from_hex(VECTORS["key_hex"])
    now = float(VECTORS["now"])
    codec = SupervisorCodec(
        key,
        nonce_factory=lambda: str(vector["nonce"]),
        clock=lambda: now,
    )
    encoded = codec.encode(str(vector["kind"]), dict(vector["payload"]))
    assert encoded.hex() == vector["frame_hex"]

    decoder = SupervisorCodec(key, clock=lambda: now)
    decoded = decoder.decode(bytes.fromhex(str(vector["frame_hex"])))
    assert decoded.kind == vector["kind"]
    assert decoded.nonce == vector["nonce"]
    assert decoded.payload == vector["payload"]


def test_non_ascii_output_is_authenticated_over_utf8_not_escaped_ascii() -> None:
    """The frame carries the code point, not its escape.

    Before RAIKER-2033 this side wrote \u00e9 while the Rust codec wrote the
    two UTF-8 bytes, so the two MACs disagreed on every frame carrying real
    program output and nothing authenticated.
    """
    codec = SupervisorCodec(b"k" * 32, nonce_factory=lambda: "nonce-fixed")
    body = codec.encode("output", {"data": "café ✓"})[4:]
    assert "café ✓".encode() in body
    assert b"caf\\u00e9" not in body


def test_a_float_payload_is_refused_rather_than_serialised() -> None:
    codec = SupervisorCodec(b"k" * 32)
    with pytest.raises(ValueError, match="supervisor_frame_float_unsupported"):
        codec.encode("status", {"cost": 1.5})


def test_the_instance_key_is_hex_on_the_wire_and_bytes_in_the_mac() -> None:
    key = bytes(range(32))
    assert instance_key_from_hex(instance_key_to_hex(key)) == key
    with pytest.raises(ValueError, match="supervisor_instance_key_too_short"):
        instance_key_from_hex("00112233")


def test_the_nonce_set_does_not_grow_past_the_clock_skew_window() -> None:
    clock = {"now": 1_800_000_000.0}
    codec = SupervisorCodec(b"k" * 32, clock=lambda: clock["now"], max_clock_skew_seconds=10)
    for index in range(5):
        codec.decode(
            SupervisorCodec(
                b"k" * 32, nonce_factory=lambda index=index: f"n{index}", clock=lambda: clock["now"]
            ).encode("status", {})
        )
    clock["now"] += 60
    codec.decode(
        SupervisorCodec(
            b"k" * 32, nonce_factory=lambda: "fresh", clock=lambda: clock["now"]
        ).encode("status", {})
    )
    assert list(codec._seen_nonces) == ["fresh"]
