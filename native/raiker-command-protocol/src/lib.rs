use hmac::{Hmac, Mac};
use serde_json::{Map, Value};
use sha2::Sha256;
use std::collections::HashMap;
use std::fmt;
use std::time::{SystemTime, UNIX_EPOCH};

type HmacSha256 = Hmac<Sha256>;

pub const PROTOCOL_VERSION: u64 = 1;
pub const DEFAULT_MAX_FRAME_BYTES: usize = 1_048_576;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ProtocolError {
    AuthenticationFailed,
    ContractInvalid,
    Expired,
    FrameTooLarge,
    LengthInvalid,
    ReplayRejected,
    UnsupportedVersion,
}

impl fmt::Display for ProtocolError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{self:?}")
    }
}

impl std::error::Error for ProtocolError {}

#[derive(Debug, Clone, PartialEq)]
pub struct Frame {
    pub version: u64,
    pub kind: String,
    pub nonce: String,
    pub issued_at: u64,
    pub payload: Value,
}

pub struct Codec {
    key: Vec<u8>,
    max_frame_bytes: usize,
    max_clock_skew_seconds: u64,
    seen_nonces: HashMap<String, u64>,
}

impl Codec {
    pub fn new(key: &[u8]) -> Result<Self, ProtocolError> {
        if key.len() < 32 {
            return Err(ProtocolError::ContractInvalid);
        }
        Ok(Self {
            key: key.to_vec(),
            max_frame_bytes: DEFAULT_MAX_FRAME_BYTES,
            max_clock_skew_seconds: 300,
            seen_nonces: HashMap::new(),
        })
    }

    pub fn with_limits(mut self, max_frame_bytes: usize, max_clock_skew_seconds: u64) -> Self {
        self.max_frame_bytes = max_frame_bytes;
        self.max_clock_skew_seconds = max_clock_skew_seconds;
        self
    }

    pub fn encode(
        &self,
        kind: &str,
        nonce: &str,
        issued_at: u64,
        payload: Value,
    ) -> Result<Vec<u8>, ProtocolError> {
        if kind.is_empty() || nonce.is_empty() || !payload.is_object() {
            return Err(ProtocolError::ContractInvalid);
        }
        if contains_float(&payload) {
            return Err(ProtocolError::ContractInvalid);
        }
        let mut authenticated = Map::new();
        authenticated.insert("issued_at".into(), Value::from(issued_at));
        authenticated.insert("kind".into(), Value::from(kind));
        authenticated.insert("nonce".into(), Value::from(nonce));
        authenticated.insert("payload".into(), payload);
        authenticated.insert("version".into(), Value::from(PROTOCOL_VERSION));
        let canonical =
            serde_json::to_vec(&authenticated).map_err(|_| ProtocolError::ContractInvalid)?;
        let mac = sign(&self.key, &canonical)?;
        authenticated.insert("mac".into(), Value::from(hex(&mac)));
        let body =
            serde_json::to_vec(&authenticated).map_err(|_| ProtocolError::ContractInvalid)?;
        if body.len() > self.max_frame_bytes || body.len() > u32::MAX as usize {
            return Err(ProtocolError::FrameTooLarge);
        }
        let mut framed = Vec::with_capacity(body.len() + 4);
        framed.extend_from_slice(&(body.len() as u32).to_be_bytes());
        framed.extend_from_slice(&body);
        Ok(framed)
    }

    pub fn decode(&mut self, framed: &[u8], now: u64) -> Result<Frame, ProtocolError> {
        if framed.len() < 4 {
            return Err(ProtocolError::LengthInvalid);
        }
        let length = u32::from_be_bytes(framed[..4].try_into().expect("four bytes")) as usize;
        if length > self.max_frame_bytes {
            return Err(ProtocolError::FrameTooLarge);
        }
        if length != framed.len() - 4 {
            return Err(ProtocolError::LengthInvalid);
        }
        let mut value: Map<String, Value> = serde_json::from_slice(&framed[4..])
            .map_err(|_| ProtocolError::AuthenticationFailed)?;
        let supplied = value
            .remove("mac")
            .and_then(|item| item.as_str().map(str::to_owned))
            .ok_or(ProtocolError::AuthenticationFailed)?;
        let canonical =
            serde_json::to_vec(&value).map_err(|_| ProtocolError::AuthenticationFailed)?;
        verify(&self.key, &canonical, &supplied)?;

        let version = value
            .get("version")
            .and_then(Value::as_u64)
            .ok_or(ProtocolError::ContractInvalid)?;
        if version != PROTOCOL_VERSION {
            return Err(ProtocolError::UnsupportedVersion);
        }
        let kind = value
            .get("kind")
            .and_then(Value::as_str)
            .ok_or(ProtocolError::ContractInvalid)?
            .to_owned();
        let nonce = value
            .get("nonce")
            .and_then(Value::as_str)
            .ok_or(ProtocolError::ContractInvalid)?
            .to_owned();
        let issued_at = value
            .get("issued_at")
            .and_then(Value::as_u64)
            .ok_or(ProtocolError::ContractInvalid)?;
        let payload = value
            .get("payload")
            .filter(|item| item.is_object())
            .cloned()
            .ok_or(ProtocolError::ContractInvalid)?;
        if now.abs_diff(issued_at) > self.max_clock_skew_seconds {
            return Err(ProtocolError::Expired);
        }
        if contains_float(&payload) {
            return Err(ProtocolError::ContractInvalid);
        }
        // A nonce older than the skew window can no longer be replayed
        // successfully, so remembering it is pure growth driven by the peer.
        let horizon = now.saturating_sub(self.max_clock_skew_seconds);
        self.seen_nonces.retain(|_, seen_at| *seen_at >= horizon);
        if self.seen_nonces.insert(nonce.clone(), issued_at).is_some() {
            return Err(ProtocolError::ReplayRejected);
        }
        Ok(Frame {
            version,
            kind,
            nonce,
            issued_at,
            payload,
        })
    }
}

/// Floats are outside the canonical form. The shortest round-trip
/// representation of a float is not identical in Rust and Python, so a payload
/// carrying one could authenticate on the sender and fail on the receiver — a
/// failure that would look like tampering. Refusing them keeps "the MAC
/// disagreed" a statement about the key, never about number formatting.
fn contains_float(value: &Value) -> bool {
    match value {
        Value::Number(number) => {
            number.as_f64().is_some() && number.as_i64().is_none() && number.as_u64().is_none()
        }
        Value::Array(items) => items.iter().any(contains_float),
        Value::Object(entries) => entries.values().any(contains_float),
        _ => false,
    }
}

/// Decode the lowercase-hex instance key both implementations share.
///
/// The environment carries text, so the key is hex on the wire and raw bytes in
/// the MAC. Keying on the hex text instead would silently produce a different
/// MAC from the Python side, which authenticates nothing and is invisible to
/// any vector that fixes the key.
pub fn instance_key_from_hex(value: &str) -> Result<Vec<u8>, ProtocolError> {
    let key = unhex(value.trim()).ok_or(ProtocolError::ContractInvalid)?;
    if key.len() < 32 {
        return Err(ProtocolError::ContractInvalid);
    }
    Ok(key)
}

pub fn unix_time() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

fn sign(key: &[u8], body: &[u8]) -> Result<Vec<u8>, ProtocolError> {
    let mut mac = HmacSha256::new_from_slice(key).map_err(|_| ProtocolError::ContractInvalid)?;
    mac.update(body);
    Ok(mac.finalize().into_bytes().to_vec())
}

fn verify(key: &[u8], body: &[u8], supplied_hex: &str) -> Result<(), ProtocolError> {
    let supplied = unhex(supplied_hex).ok_or(ProtocolError::AuthenticationFailed)?;
    let mut mac =
        HmacSha256::new_from_slice(key).map_err(|_| ProtocolError::AuthenticationFailed)?;
    mac.update(body);
    mac.verify_slice(&supplied)
        .map_err(|_| ProtocolError::AuthenticationFailed)
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|byte| format!("{byte:02x}")).collect()
}

fn unhex(value: &str) -> Option<Vec<u8>> {
    if !value.len().is_multiple_of(2) {
        return None;
    }
    (0..value.len())
        .step_by(2)
        .map(|index| u8::from_str_radix(&value[index..index + 2], 16).ok())
        .collect()
}
