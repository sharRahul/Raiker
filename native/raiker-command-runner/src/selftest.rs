//! The child the probe runs, inside the boundary and again outside it.
//!
//! A boundary is only proven by what a process inside it cannot do. But "the
//! write failed" and "the connection failed" are equally produced by a
//! read-only target, an air-gapped host, or no route at all — so every
//! observation is taken **twice**: once inside the boundary and once outside
//! it, by this same code. Only `outside succeeded and inside failed` is
//! evidence. `outside failed` is `indeterminate`, and an indeterminate
//! observation never turns a capability on.
//!
//! Running the probe child from the runner's own binary keeps the measurement
//! honest in a second way: there is no separate helper to go missing, and the
//! child is subject to exactly the boundary a real command would get.

use serde_json::{Value, json};
use std::io::Write;
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::time::Duration;

/// What the probe child is asked to attempt. Every path and address is named
/// by the caller: a probe that chooses its own targets can pick one that fails
/// for an unrelated reason and call the boundary proven.
pub struct SelfTest {
    pub nonce: String,
    pub inside_path: PathBuf,
    pub outside_paths: Vec<PathBuf>,
    pub masked_read_path: PathBuf,
    pub connect_address: String,
    pub spawn_grandchild: bool,
}

impl SelfTest {
    pub fn from_value(value: &Value) -> Option<SelfTest> {
        Some(SelfTest {
            nonce: value.get("nonce")?.as_str()?.to_owned(),
            inside_path: PathBuf::from(value.get("inside_path")?.as_str()?),
            outside_paths: value
                .get("outside_paths")?
                .as_array()?
                .iter()
                .filter_map(Value::as_str)
                .map(PathBuf::from)
                .collect(),
            masked_read_path: PathBuf::from(value.get("masked_read_path")?.as_str()?),
            connect_address: value.get("connect_address")?.as_str()?.to_owned(),
            spawn_grandchild: value
                .get("spawn_grandchild")
                .and_then(Value::as_bool)
                .unwrap_or(false),
        })
    }

    pub fn to_value(&self) -> Value {
        json!({
            "nonce": self.nonce,
            "inside_path": self.inside_path.to_string_lossy(),
            "outside_paths": self.outside_paths.iter()
                .map(|path| path.to_string_lossy().into_owned())
                .collect::<Vec<_>>(),
            "masked_read_path": self.masked_read_path.to_string_lossy(),
            "connect_address": self.connect_address,
            "spawn_grandchild": self.spawn_grandchild,
        })
    }
}

/// Run every attempt and report what happened, without side effects beyond the
/// attempts themselves. This never fails: a refusal is the measurement, not an
/// error.
pub fn attempt(test: &SelfTest) -> Value {
    json!({
        // Observation 0. When this runs inside the boundary it is printed
        // through the relay the runner set up, so a boundary that silently
        // drops output cannot pass the probe.
        "nonce": test.nonce,
        "inside_write": write_probe(&test.inside_path),
        "outside_writes": test.outside_paths.iter()
            .map(|path| write_probe(path))
            .collect::<Vec<_>>(),
        "masked_read": read_probe(&test.masked_read_path),
        "connect": connect_probe(&test.connect_address),
    })
}

/// The probe child: detach a grandchild, take every measurement, print the
/// result for the parent to read back.
pub fn run(test: &SelfTest) -> Value {
    if test.spawn_grandchild {
        spawn_grandchild(test);
    }
    let result = attempt(test);
    let mut stdout = std::io::stdout();
    let _ = writeln!(stdout, "{result}");
    let _ = stdout.flush();
    result
}

/// The grandchild exists to prove containment reaches descendants, which is the
/// invariant — not merely the first executable.
///
/// It **detaches itself** — a new process group on Windows, `setsid()` on
/// POSIX. A grandchild left in the child's process group proves nothing: a
/// process-group kill removes it on every platform, so the observation would
/// pass on macOS, which is precisely the host whose weaker posture it exists to
/// expose.
fn spawn_grandchild(test: &SelfTest) {
    let marker = test.inside_path.with_extension("grandchild");
    let Ok(current) = std::env::current_exe() else {
        return;
    };
    let mut command = std::process::Command::new(current);
    command
        .arg("--linger")
        .arg(marker.to_string_lossy().to_string());
    // The grandchild must not inherit the relay pipes. If it did, it would hold
    // the write end open for its whole lifetime and the parent's read would
    // block long after the child had exited — a hang that looks like a wedged
    // boundary and is really a leaked handle.
    command
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null());
    detach(&mut command);
    let _ = command.spawn();
}

#[cfg(windows)]
fn detach(command: &mut std::process::Command) {
    use std::os::windows::process::CommandExt;
    // CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS. Breakaway from the Job
    // Object is deliberately *not* requested: the job must refuse it, and the
    // observation is that the job takes this process anyway.
    command.creation_flags(0x0000_0200 | 0x0000_0008);
}

#[cfg(unix)]
fn detach(command: &mut std::process::Command) {
    use std::os::unix::process::CommandExt;
    unsafe {
        command.pre_exec(|| {
            libc::setsid();
            Ok(())
        });
    }
}

/// The grandchild body: touch a marker so the parent can prove it started, then
/// outlive its parent. If it is still alive after the runner stops, containment
/// did not cover descendants.
pub fn linger(marker: &Path) {
    let _ = std::fs::write(marker, b"alive");
    std::thread::sleep(Duration::from_secs(600));
}

fn write_probe(path: &Path) -> Value {
    match std::fs::write(path, b"raiker-probe") {
        Ok(()) => {
            let _ = std::fs::remove_file(path);
            json!({"allowed": true, "error": Value::Null})
        }
        Err(error) => json!({"allowed": false, "error": error.kind().to_string()}),
    }
}

fn read_probe(path: &Path) -> Value {
    match std::fs::read(path) {
        Ok(_) => json!({"allowed": true, "error": Value::Null}),
        Err(error) => json!({"allowed": false, "error": error.kind().to_string()}),
    }
}

/// Did a packet reach the destination?
///
/// The destination is a **closed** port on the default gateway, so a working
/// network answers `ConnectionRefused` — the connection failed, but the packet
/// arrived and came back. That is the signal, not `Ok`. A boundary that drops
/// egress answers something else entirely: permission denied, unreachable, or
/// nothing at all until the timeout.
///
/// Reading this as "did connect succeed" would have made the control arm fail
/// on every correctly-configured network, which is exactly what it did the
/// first time it ran.
fn connect_probe(address: &str) -> Value {
    // A resolved socket address, never a hostname: DNS failure is not evidence
    // of a network boundary, and this observation must not be able to pass for
    // the wrong reason.
    let parsed: Result<SocketAddr, _> = address.parse();
    let Ok(target) = parsed else {
        return json!({"allowed": false, "reached": false, "error": "address_invalid"});
    };
    match TcpStream::connect_timeout(&target, Duration::from_secs(4)) {
        Ok(_) => json!({"allowed": true, "reached": true, "error": Value::Null}),
        Err(error) => json!({
            "allowed": false,
            "reached": error.kind() == std::io::ErrorKind::ConnectionRefused,
            "error": error.kind().to_string(),
        }),
    }
}

/// Fold an inside result and its outside control arm into one of the three
/// answers the product is allowed to show.
///
/// `enforced` needs both halves. Without the control arm, an air-gapped host
/// and an unwritable target both look exactly like a working boundary — which
/// is how a green row gets published for a boundary that does not exist.
pub fn verdict(inside_allowed: bool, outside_allowed: bool) -> &'static str {
    match (outside_allowed, inside_allowed) {
        (true, false) => "enforced",
        (true, true) => "unenforced",
        (false, _) => "indeterminate",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_refusal_without_a_control_arm_is_indeterminate_not_proof() {
        assert_eq!(verdict(false, false), "indeterminate");
        assert_eq!(verdict(true, false), "indeterminate");
    }

    #[test]
    fn only_outside_succeeding_and_inside_failing_is_enforcement() {
        assert_eq!(verdict(false, true), "enforced");
        assert_eq!(verdict(true, true), "unenforced");
    }

    #[test]
    fn a_hostname_is_refused_because_dns_failure_is_not_evidence() {
        assert_eq!(connect_probe("example.com:443")["error"], "address_invalid");
        assert_eq!(connect_probe("example.com:443")["reached"], false);
    }
}
