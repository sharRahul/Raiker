use raiker_command_protocol::{Codec, instance_key_from_hex, unix_time};
use serde_json::json;
use std::env;
use std::io::{self, Read, Write};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // The environment carries the key as lowercase hex; the MAC is keyed on the
    // decoded bytes. Keying on the hex text would authenticate nothing against
    // the Python side, and no protocol vector would catch it because vectors
    // fix the key.
    let key = instance_key_from_hex(&env::var("RAIKER_COMMAND_SUPERVISOR_KEY")?)?;
    let mut input = Vec::new();
    io::stdin().read_to_end(&mut input)?;
    let now = unix_time();
    let mut decoder = Codec::new(&key)?;
    let request = decoder.decode(&input, now)?;
    let encoder = Codec::new(&key)?;
    let response = encoder.encode(
        "accepted",
        &format!("{}-response", request.nonce),
        now,
        json!({"kind": request.kind, "accepted": true}),
    )?;
    io::stdout().write_all(&response)?;
    Ok(())
}
