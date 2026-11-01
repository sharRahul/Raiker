#![cfg(target_os = "macos")]
//! The sandbox-account boundary, measured on a host where the owner ran
//! `sudo raiker-command-runner --setup-account`. Skipped elsewhere: without
//! the account there is nothing to measure, and these tests must not create
//! one themselves. CI sets `RAIKER_REQUIRE_ACCOUNT_SANDBOX` after setup, so
//! there a missing account fails instead of skipping.

use std::path::{Path, PathBuf};
use std::process::{Command, Output};
use std::time::{Duration, Instant};

/// The account serves one run at a time, and a run's deadline includes its
/// wait for the account. Run in parallel, these tests queued behind each other
/// and timed out (`native_sandbox_account_busy`) on the slower Intel runner;
/// that is the designed behaviour, not what these tests measure.
fn serial() -> std::sync::MutexGuard<'static, ()> {
    static ACCOUNT: std::sync::Mutex<()> = std::sync::Mutex::new(());
    ACCOUNT
        .lock()
        .unwrap_or_else(std::sync::PoisonError::into_inner)
}

fn runner() -> &'static str {
    env!("CARGO_BIN_EXE_raiker-command-runner")
}

fn configured() -> Option<PathBuf> {
    let output = Command::new(runner())
        .arg("--account-status")
        .output()
        .ok()?;
    let status: serde_json::Value = serde_json::from_slice(&output.stdout).ok()?;
    if status["configured"] != true {
        if std::env::var_os("RAIKER_REQUIRE_ACCOUNT_SANDBOX").is_some() {
            panic!("the account sandbox is required here but not configured: {status}");
        }
        return None;
    }
    Some(PathBuf::from(status["base"].as_str()?))
}

struct Copy(PathBuf);

impl Drop for Copy {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

fn copy_under(base: &Path, name: &str) -> Copy {
    let path = base.join(format!(
        "{name}-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir(&path).unwrap();
    Copy(path)
}

/// The policy lives beside the copy's owner, never in the copy: the runner
/// reads it as the owner before anything runs as the account.
fn run(copy: &Copy, memory: u64, argv: &[&str]) -> Output {
    let policy = std::env::temp_dir().join(format!(
        "raiker-account-policy-{}.json",
        copy.0.file_name().unwrap().to_string_lossy()
    ));
    std::fs::write(
        &policy,
        serde_json::json!({
            "workspace_root": copy.0, "cwd": copy.0,
            "profile_name": "raiker.account.test", "deadline_seconds": 30,
            "max_memory_bytes": memory, "max_processes": 64
        })
        .to_string(),
    )
    .unwrap();
    let output = Command::new(runner())
        .arg("--policy")
        .arg(&policy)
        .arg("--")
        .args(argv)
        .output()
        .unwrap();
    let _ = std::fs::remove_file(&policy);
    output
}

const GIB: u64 = 1024 * 1024 * 1024;

#[test]
fn the_account_probe_measures_every_control_enforced_including_descendants() {
    let _serial = serial();
    let Some(_) = configured() else { return };
    let output = Command::new(runner())
        .args(["--probe", "--workspace"])
        .arg(std::env::temp_dir())
        .output()
        .unwrap();
    let report: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(report["boundary"], "macos_account", "{report}");
    for property in [
        "relay",
        "workspace_write",
        "escape_write",
        "masked_read",
        "egress",
        "descendant_reaped",
    ] {
        assert_eq!(report["observations"][property], "enforced", "{report}");
    }
    assert_eq!(report["process_tree_stop"], true, "{report}");
}

#[test]
fn a_command_runs_as_the_account_and_writes_only_its_copy() {
    let _serial = serial();
    let Some(base) = configured() else { return };
    let copy = copy_under(&base, "identity");
    std::fs::write(copy.0.join("input.txt"), "from the owner").unwrap();
    let output = run(
        &copy,
        2 * GIB,
        &[
            "/bin/sh",
            "-c",
            "id -un; cat input.txt; printf made > made.txt; printf edited > input.txt",
        ],
    );
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(
        output.status.success(),
        "{stdout} {}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(stdout.starts_with("_raikersandbox\n"), "{stdout}");
    assert!(stdout.contains("from the owner"), "{stdout}");
    // The owner reads, changes and deletes what the account made: the change
    // set can be reviewed, applied and discarded.
    assert_eq!(
        std::fs::read_to_string(copy.0.join("made.txt")).unwrap(),
        "made"
    );
    assert_eq!(
        std::fs::read_to_string(copy.0.join("input.txt")).unwrap(),
        "edited"
    );
    std::fs::write(copy.0.join("made.txt"), "owner").unwrap();
    // No handoff is left in the copy for the change set to pick up.
    assert!(!std::fs::read_dir(&copy.0).unwrap().any(|entry| {
        entry
            .unwrap()
            .file_name()
            .to_string_lossy()
            .starts_with(".raiker-launch-")
    }),);
}

#[test]
fn another_copy_is_out_of_reach_during_a_run_and_the_grant_ends_with_it() {
    let _serial = serial();
    let Some(base) = configured() else { return };
    let mine = copy_under(&base, "mine");
    let other = copy_under(&base, "other");
    std::fs::write(other.0.join("secret.txt"), "another session").unwrap();
    let target = other.0.join("secret.txt");
    let output = run(
        &mine,
        2 * GIB,
        &[
            "/bin/sh",
            "-c",
            "cat \"$1\" || exit 7",
            "probe",
            target.to_str().unwrap(),
        ],
    );
    assert_eq!(
        output.status.code(),
        Some(7),
        "{}",
        String::from_utf8_lossy(&output.stdout)
    );
    assert!(!String::from_utf8_lossy(&output.stdout).contains("another session"));
    // After the run the account has no entry on the copy it was granted.
    let listing = Command::new("/bin/ls")
        .arg("-led")
        .arg(&mine.0)
        .output()
        .unwrap();
    assert!(
        !String::from_utf8_lossy(&listing.stdout).contains("_raikersandbox allow list"),
        "{}",
        String::from_utf8_lossy(&listing.stdout)
    );
}

#[test]
fn a_detached_descendant_does_not_outlive_its_run() {
    let _serial = serial();
    let Some(base) = configured() else { return };
    let copy = copy_under(&base, "detached");
    // Double fork, new session, and outlive the parent: the case Seatbelt
    // alone cannot stop.
    let output = run(
        &copy,
        2 * GIB,
        &[
            "/usr/bin/perl",
            "-e",
            "if (fork() == 0) { POSIX::setsid(); if (fork() == 0) { open(my $f, '>', 'pid'); print $f $$; close($f); sleep 120; exit } exit } sleep 1; print \"started\\n\";",
            "-MPOSIX",
        ],
    );
    assert!(
        String::from_utf8_lossy(&output.stdout).contains("started"),
        "{} {}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    let pid: i32 = std::fs::read_to_string(copy.0.join("pid"))
        .unwrap()
        .trim()
        .parse()
        .unwrap();
    // Control arm: the descendant really existed, as the account's process.
    let end = Instant::now() + Duration::from_secs(5);
    loop {
        let alive = unsafe { libc_kill(pid, 0) } == 0
            || std::io::Error::last_os_error().raw_os_error() == Some(1);
        if !alive {
            break;
        }
        assert!(
            Instant::now() < end,
            "detached descendant {pid} survived the run"
        );
        std::thread::sleep(Duration::from_millis(50));
    }
}

#[test]
fn memory_past_the_limit_stops_the_run_and_under_it_completes() {
    let _serial = serial();
    let Some(base) = configured() else { return };
    let copy = copy_under(&base, "memory");
    // Touch 600 MB so it counts as footprint, then hold it.
    let allocate = [
        "/usr/bin/perl",
        "-e",
        "my $x = 'a' x (600*1024*1024); sleep 3; print \"survived\\n\";",
    ];
    let control = run(&copy, 2 * GIB, &allocate);
    assert!(
        String::from_utf8_lossy(&control.stdout).contains("survived"),
        "control arm: {}",
        String::from_utf8_lossy(&control.stderr)
    );
    let limited = run(&copy, 256 * 1024 * 1024, &allocate);
    assert!(!String::from_utf8_lossy(&limited.stdout).contains("survived"));
    assert_eq!(limited.status.code(), Some(137));
    assert!(
        String::from_utf8_lossy(&limited.stderr).contains("native_sandbox_memory_limit_exceeded")
    );
}

#[test]
fn a_copy_outside_the_base_never_runs_as_the_account() {
    let _serial = serial();
    let Some(_) = configured() else { return };
    let outside =
        std::env::temp_dir().join(format!("raiker-account-outside-{}", std::process::id()));
    std::fs::create_dir_all(&outside).unwrap();
    let copy = Copy(std::fs::canonicalize(&outside).unwrap());
    let output = run(&copy, 2 * GIB, &["/usr/bin/id", "-un"]);
    assert!(!String::from_utf8_lossy(&output.stdout).contains("_raikersandbox"));
}

unsafe extern "C" {
    #[link_name = "kill"]
    fn libc_kill(pid: i32, signal: i32) -> i32;
}
