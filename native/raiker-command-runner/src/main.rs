//! `raiker-command-runner` — the OS boundary a governed command actually runs in.
//!
//! Raiker's Python runtime decides *whether* a command may run: the capability
//! gate, the approval or standing grant, the argv policy, the constructed
//! environment, and the redaction of everything that comes back. None of that
//! is an operating-system boundary. This binary is.
//!
//! It takes a launch contract and an argv list, builds the strongest boundary
//! the host can actually prove, launches the command inside it, and relays the
//! child's streams unchanged. It never falls back: a boundary that cannot be
//! built is a named refusal on stderr and exit code 91, so the runtime can
//! report why rather than quietly running the command on the host.
//!
//! Modes:
//!
//! * `--policy <file> -- <argv>` — run a command inside the boundary.
//! * `--probe --workspace <path>` — measure what this host actually enforces,
//!   against the real workspace, with a control arm for every observation.
//! * `--revoke-grant --workspace <path>` — remove the workspace grant. Called by
//!   environment reset and uninstall, because a durable machine-wide ACE with no
//!   removal path would outlive Raiker itself.
//! * `--selftest <json>` — the probe's child. Run inside the boundary and again
//!   outside it; the difference is the measurement.
//! * `--linger <marker>` — the probe's detached grandchild, which exists to
//!   prove containment reaches descendants and not merely the first executable.

mod policy;
mod selftest;

#[cfg(unix)]
#[path = "boundary_unix.rs"]
mod boundary;
#[cfg(windows)]
#[path = "boundary_windows.rs"]
mod boundary;

use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::exit;

/// Distinct from any plausible child exit code: the boundary failed, the
/// command did not run.
const RUNNER_FAILURE_EXIT: i32 = 91;

fn main() {
    let arguments: Vec<String> = std::env::args().skip(1).collect();
    match dispatch(&arguments) {
        Ok(code) => exit(code),
        Err(reason) => {
            // The relayed child streams are closed by the time this runs, so a
            // boundary failure can never be mistaken for program output by the
            // redactor that reads it. stderr, deliberately: stdout is the
            // command's.
            let line = serde_json::json!({"raiker_runner_error": reason});
            let mut stderr = std::io::stderr();
            let _ = writeln!(stderr, "{line}");
            let _ = stderr.flush();
            exit(RUNNER_FAILURE_EXIT);
        }
    }
}

fn dispatch(arguments: &[String]) -> Result<i32, String> {
    match arguments.first().map(String::as_str) {
        Some("--probe") => {
            let workspace =
                named(arguments, "--workspace").ok_or("runner_probe_workspace_required")?;
            println!("{}", boundary::probe(Path::new(&workspace)));
            return Ok(0);
        }
        Some("--revoke-grant") => {
            let workspace =
                named(arguments, "--workspace").ok_or("runner_probe_workspace_required")?;
            boundary::revoke_workspace_grant(Path::new(&workspace))?;
            return Ok(0);
        }
        Some("--selftest") => {
            let value: serde_json::Value =
                serde_json::from_str(arguments.get(1).ok_or("runner_arguments_invalid")?)
                    .map_err(|_| "runner_arguments_invalid")?;
            let test = selftest::SelfTest::from_value(&value).ok_or("runner_arguments_invalid")?;
            selftest::run(&test);
            return Ok(0);
        }
        Some("--linger") => {
            selftest::linger(Path::new(
                arguments.get(1).ok_or("runner_arguments_invalid")?,
            ));
            return Ok(0);
        }
        _ => {}
    }

    let separator = arguments
        .iter()
        .position(|argument| argument == "--")
        .ok_or("runner_arguments_invalid")?;
    let argv = &arguments[separator + 1..];
    if argv.is_empty() {
        return Err("runner_arguments_invalid".into());
    }
    let path = named(&arguments[..separator], "--policy").ok_or("runner_policy_required")?;
    let text =
        std::fs::read_to_string(PathBuf::from(path)).map_err(|_| "runner_policy_unreadable")?;
    let launch = policy::parse(&text)?;
    boundary::launch(&launch, argv)
}

fn named(arguments: &[String], flag: &str) -> Option<String> {
    arguments
        .iter()
        .position(|argument| argument == flag)
        .and_then(|index| arguments.get(index + 1))
        .cloned()
}
