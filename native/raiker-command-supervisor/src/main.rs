use raiker_command_protocol::{Codec, unix_time};
use serde_json::json;
use std::env;
use std::io::{self, Read, Write};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let key_text = env::var("RAIKER_COMMAND_SUPERVISOR_KEY")?;
    if key_text.as_bytes().len() < 32 {
        return Err("RAIKER_COMMAND_SUPERVISOR_KEY must contain at least 32 bytes".into());
    }
    let mut input = Vec::new();
    io::stdin().read_to_end(&mut input)?;
    let now = unix_time();
    let mut decoder = Codec::new(key_text.as_bytes())?;
    let request = decoder.decode(&input, now)?;
    let encoder = Codec::new(key_text.as_bytes())?;
    let response = encoder.encode(
        "accepted",
        &format!("{}-response", request.nonce),
        now,
        json!({"kind": request.kind, "accepted": true}),
    )?;
    io::stdout().write_all(&response)?;
    Ok(())
}
