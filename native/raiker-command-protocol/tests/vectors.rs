use raiker_command_protocol::{Codec, ProtocolError};
use serde_json::json;

const NOW: u64 = 1_800_000_000;

#[test]
fn authenticated_frame_round_trips() {
    let key = [7_u8; 32];
    let mut codec = Codec::new(&key).unwrap();
    let encoded = codec
        .encode("start", "nonce-1", NOW, json!({"run_id": "cmd_1"}))
        .unwrap();
    let decoded = codec.decode(&encoded, NOW).unwrap();
    assert_eq!(decoded.kind, "start");
    assert_eq!(decoded.payload["run_id"], "cmd_1");
}

#[test]
fn tamper_and_replay_fail_closed() {
    let key = [8_u8; 32];
    let mut codec = Codec::new(&key).unwrap();
    let encoded = codec
        .encode("attach", "nonce-2", NOW, json!({"run_id": "cmd_2"}))
        .unwrap();
    codec.decode(&encoded, NOW).unwrap();
    assert_eq!(
        codec.decode(&encoded, NOW),
        Err(ProtocolError::ReplayRejected)
    );

    let mut tampered = encoded;
    let last = tampered.len() - 1;
    tampered[last] ^= 1;
    let mut fresh = Codec::new(&key).unwrap();
    assert_eq!(
        fresh.decode(&tampered, NOW),
        Err(ProtocolError::AuthenticationFailed)
    );
}

#[test]
fn frame_length_and_clock_are_bounded() {
    let key = [9_u8; 32];
    let codec = Codec::new(&key).unwrap().with_limits(64, 10);
    assert_eq!(
        codec.encode("start", "nonce-3", NOW, json!({"data": "x".repeat(100)})),
        Err(ProtocolError::FrameTooLarge)
    );

    let mut codec = Codec::new(&key).unwrap().with_limits(1024, 10);
    let encoded = codec.encode("status", "nonce-4", NOW, json!({})).unwrap();
    assert_eq!(
        codec.decode(&encoded, NOW + 11),
        Err(ProtocolError::Expired)
    );
}
