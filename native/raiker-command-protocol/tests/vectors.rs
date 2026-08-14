use raiker_command_protocol::{Codec, ProtocolError, instance_key_from_hex};
use serde_json::{Value, json};

const NOW: u64 = 1_800_000_000;

/// The one file both implementations authenticate against.
///
/// Two codecs that each pass their own tests can still be unable to speak to
/// each other — which is exactly what happened here: Python's `json.dumps`
/// escapes non-ASCII by default and Rust's `serde_json` does not, so every
/// frame carrying real program output failed authentication across the pair.
/// A shared vector file is the only test that could have caught it, and it only
/// catches it if the vectors contain non-ASCII.
const VECTORS: &str = include_str!("../../../tests/vectors/supervisor_protocol.json");

fn unhex_bytes(value: &str) -> Vec<u8> {
    (0..value.len())
        .step_by(2)
        .map(|index| u8::from_str_radix(&value[index..index + 2], 16).expect("hex"))
        .collect()
}

#[test]
fn shared_vectors_encode_and_decode_byte_for_byte() {
    let document: Value = serde_json::from_str(VECTORS).expect("vector document");
    let key = instance_key_from_hex(document["key_hex"].as_str().expect("key")).expect("key bytes");
    let now = document["now"].as_u64().expect("now");

    for vector in document["vectors"].as_array().expect("vectors") {
        let kind = vector["kind"].as_str().expect("kind");
        let nonce = vector["nonce"].as_str().expect("nonce");
        let issued_at = vector["issued_at"].as_u64().expect("issued_at");
        let payload = vector["payload"].clone();
        let expected = unhex_bytes(vector["frame_hex"].as_str().expect("frame_hex"));

        let codec = Codec::new(&key).expect("codec");
        let encoded = codec
            .encode(kind, nonce, issued_at, payload.clone())
            .unwrap_or_else(|_| panic!("encode {kind}/{nonce}"));
        assert_eq!(encoded, expected, "frame bytes differ for {kind}/{nonce}");

        let mut decoder = Codec::new(&key).expect("codec");
        let decoded = decoder
            .decode(&expected, now)
            .unwrap_or_else(|_| panic!("decode {kind}/{nonce}"));
        assert_eq!(decoded.kind, kind);
        assert_eq!(decoded.nonce, nonce);
        assert_eq!(decoded.payload, payload);
    }
}

#[test]
fn a_float_payload_is_refused_rather_than_serialised() {
    let mut codec = Codec::new(&[3_u8; 32]).unwrap();
    assert_eq!(
        codec.encode("status", "nonce-float", NOW, json!({"cost": 1.5})),
        Err(ProtocolError::ContractInvalid)
    );
    let _ = &mut codec;
}

#[test]
fn a_hex_key_shorter_than_thirty_two_bytes_is_refused() {
    assert_eq!(
        instance_key_from_hex("00112233"),
        Err(ProtocolError::ContractInvalid)
    );
}

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
