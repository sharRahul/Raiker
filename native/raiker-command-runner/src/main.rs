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
//! * `--egress-bridge <socket> <port> -- <argv>` — Linux only, started by the
//!   boundary *inside* the sandbox: forwards the namespace's loopback port to
//!   Raiker's egress proxy socket, the command's only network route.
//! * `--setup-account [--owner-uid <uid>]`, `--reset-account`,
//!   `--account-status` — the dedicated sandbox account (Windows: elevated;
//!   macOS: as root, once, with the owner's approval).
//! * `--account-run <handoff>` — macOS only, started by `sudo` *as* the
//!   sandbox account: reads the run's handoff, starts Seatbelt and supervises
//!   the run's memory and lifetime.
//! * `--setup-wsl --linux-runner <file> [--rootfs <tar>]`, `--reset-wsl`,
//!   `--wsl-status`, `--probe --boundary wsl` — Windows only: Raiker's own
//!   WSL2 distribution, where the Linux runner is the boundary.
//! * `--linger <marker>` — the probe's detached grandchild, which exists to
//!   prove containment reaches descendants and not merely the first executable.

#[cfg(target_os = "linux")]
#[path = "egress_bridge_linux.rs"]
mod egress_bridge;
#[cfg(target_os = "linux")]
mod lifecycle_linux;
mod policy;
#[cfg(target_os = "linux")]
mod seccomp_linux;
mod selftest;
// Pure path and policy logic for the WSL2 backend: used on Windows, and
// unit-tested everywhere.
#[cfg(any(windows, test))]
#[cfg_attr(not(windows), allow(dead_code))]
mod wsl_paths;

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
            #[cfg(target_os = "macos")]
            if named(arguments, "--boundary").as_deref() == Some("seatbelt") {
                println!("{}", boundary::probe_kernel_sandbox(Path::new(&workspace)));
                return Ok(0);
            }
            #[cfg(windows)]
            if named(arguments, "--boundary").as_deref() == Some("wsl") {
                println!("{}", boundary::wsl::probe());
                return Ok(0);
            }
            #[cfg(windows)]
            if named(arguments, "--boundary").as_deref() == Some("appcontainer") {
                println!("{}", boundary::probe_appcontainer(Path::new(&workspace)));
                return Ok(0);
            }
            println!("{}", boundary::probe(Path::new(&workspace)));
            return Ok(0);
        }
        Some("--revoke-grant") => {
            let workspace =
                named(arguments, "--workspace").ok_or("runner_probe_workspace_required")?;
            boundary::revoke_workspace_grant(Path::new(&workspace))?;
            return Ok(0);
        }
        #[cfg(target_os = "macos")]
        Some("--setup-account") => {
            let owner = match named(arguments, "--owner-uid") {
                Some(text) => Some(text.parse().map_err(|_| "runner_arguments_invalid")?),
                None => None,
            };
            println!("{}", boundary::account::setup(owner)?);
            return Ok(0);
        }
        #[cfg(target_os = "macos")]
        Some("--reset-account") => {
            boundary::account::reset()?;
            return Ok(0);
        }
        #[cfg(target_os = "macos")]
        Some("--account-status") => {
            println!("{}", boundary::account::status());
            return Ok(0);
        }
        #[cfg(target_os = "macos")]
        Some("--account-stop") => {
            if arguments.len() != 1 {
                return Err("runner_arguments_invalid".into());
            }
            return boundary::account::account_stop();
        }
        #[cfg(target_os = "macos")]
        Some("--account-run") => {
            let handoff = arguments.get(1).ok_or("runner_arguments_invalid")?;
            if arguments.len() != 2 {
                return Err("runner_arguments_invalid".into());
            }
            return boundary::account::account_run(Path::new(handoff));
        }
        #[cfg(windows)]
        Some("--setup-wsl") => {
            let runner = named(arguments, "--linux-runner").ok_or("runner_arguments_invalid")?;
            let rootfs = named(arguments, "--rootfs").map(PathBuf::from);
            println!(
                "{}",
                boundary::wsl::setup(rootfs.as_deref(), Path::new(&runner))?
            );
            return Ok(0);
        }
        #[cfg(windows)]
        Some("--reset-wsl") => {
            boundary::wsl::reset()?;
            return Ok(0);
        }
        #[cfg(windows)]
        Some("--wsl-status") => {
            println!("{}", boundary::wsl::status());
            return Ok(0);
        }
        #[cfg(windows)]
        Some("--setup-account") => {
            println!("{}", boundary::account::setup()?);
            return Ok(0);
        }
        #[cfg(windows)]
        Some("--harden-account-logon") => {
            if arguments.len() != 1 {
                return Err("runner_arguments_invalid".into());
            }
            println!("{}", boundary::account::harden_logon()?);
            return Ok(0);
        }
        #[cfg(windows)]
        Some("--reset-account") => {
            boundary::account::reset()?;
            return Ok(0);
        }
        #[cfg(windows)]
        Some("--conpty-host") => {
            if arguments.get(1).map(String::as_str) != Some("--") {
                return Err("runner_arguments_invalid".into());
            }
            return boundary::conpty::host(&arguments[2..]);
        }
        #[cfg(windows)]
        Some("--account-status") => {
            println!("{}", boundary::account::status());
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
        #[cfg(target_os = "linux")]
        Some("--nproc-limit") => {
            let limit: libc::rlim_t = arguments
                .get(1)
                .and_then(|text| text.parse().ok())
                .ok_or("runner_arguments_invalid")?;
            if arguments.get(2).map(String::as_str) != Some("--") || arguments.len() < 4 {
                return Err("runner_arguments_invalid".into());
            }
            return boundary::exec_with_process_limit(limit, &arguments[3..]);
        }
        #[cfg(target_os = "linux")]
        Some("--egress-bridge") => {
            let socket = arguments.get(1).ok_or("runner_arguments_invalid")?;
            let port: u16 = arguments
                .get(2)
                .and_then(|text| text.parse().ok())
                .ok_or("runner_arguments_invalid")?;
            if arguments.get(3).map(String::as_str) != Some("--") {
                return Err("runner_arguments_invalid".into());
            }
            return egress_bridge::run(Path::new(socket), port, &arguments[4..]);
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
    policy::validate_filesystem_paths(&launch)?;
    // A copy in the sandbox account's base runs as that account (macOS);
    // everything else keeps plain Seatbelt.
    #[cfg(target_os = "macos")]
    if boundary::account::owns(&launch) {
        return boundary::account::launch(&launch, &text, argv);
    }
    // A copy inside Raiker's WSL distribution runs there, under the Linux
    // runner (Windows, opt-in).
    #[cfg(windows)]
    if boundary::wsl::owns(&launch) {
        return boundary::wsl::launch(&launch, &text, argv);
    }
    boundary::launch(&launch, argv)
}

fn named(arguments: &[String], flag: &str) -> Option<String> {
    arguments
        .iter()
        .position(|argument| argument == flag)
        .and_then(|index| arguments.get(index + 1))
        .cloned()
}

#[cfg(test)]
mod tests {
    use super::dispatch;

    #[test]
    fn dispatch_refuses_a_missing_workspace_before_launch() {
        let directory = std::env::temp_dir().join(format!(
            "raiker-dispatch-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&directory).unwrap();
        let workspace = directory.join("missing");
        let policy = serde_json::json!({
            "workspace_root": workspace,
            "cwd": workspace,
            "profile_name": "raiker.cmd.test"
        });
        let policy_path = directory.join("policy.json");
        std::fs::write(&policy_path, policy.to_string()).unwrap();
        let arguments = vec![
            "--policy".into(),
            policy_path.to_string_lossy().into_owned(),
            "--".into(),
            "nonexistent-executable".into(),
        ];
        assert_eq!(
            dispatch(&arguments).unwrap_err(),
            "runner_policy_workspace_unreadable"
        );
        std::fs::remove_dir_all(directory).unwrap();
    }
}
