#![cfg(windows)]
//! The restricted-account boundary, measured on a host where the owner ran
//! `--setup-account`. Skipped elsewhere: without the account there is nothing
//! to measure, and these tests must not create one themselves.

use std::path::PathBuf;
use std::process::Command;

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

fn copy_under(base: &std::path::Path, name: &str) -> Copy {
    let path = base.join(format!("{name}-{}", std::process::id()));
    std::fs::create_dir(&path).unwrap();
    Copy(path)
}

fn run(copy: &Copy, argv: &[&str]) -> std::process::Output {
    let policy = copy.0.join("policy.json");
    std::fs::write(
        &policy,
        serde_json::json!({
            "workspace_root": copy.0, "cwd": copy.0,
            "profile_name": "raiker.account.test", "deadline_seconds": 60
        })
        .to_string(),
    )
    .unwrap();
    Command::new(runner())
        .arg("--policy")
        .arg(&policy)
        .arg("--")
        .args(argv)
        .output()
        .unwrap()
}

#[test]
fn the_account_probe_measures_every_filesystem_and_process_control_enforced() {
    let Some(_) = configured() else { return };
    let output = Command::new(runner())
        .args(["--probe", "--workspace"])
        .arg(std::env::temp_dir())
        .output()
        .unwrap();
    let report: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(report["boundary"], "restricted_account", "{report}");
    for property in [
        "relay",
        "workspace_write",
        "escape_write",
        "masked_read",
        "descendant_reaped",
    ] {
        assert_eq!(report["observations"][property], "enforced", "{report}");
    }
    // Egress is proven only where the unsandboxed control reaches the gateway.
    assert_ne!(report["observations"]["egress"], "unenforced", "{report}");
}

#[test]
fn ordinary_toolchains_start_as_the_account_inside_the_copy() {
    let Some(base) = configured() else { return };
    let copy = copy_under(&base, "toolchains");
    let cmd = std::env::var("ComSpec").unwrap_or_else(|_| r"C:\Windows\System32\cmd.exe".into());
    let written = run(&copy, &[&cmd, "/c", "echo inside> made.txt && whoami"]);
    assert!(
        written.status.success(),
        "{}",
        String::from_utf8_lossy(&written.stderr)
    );
    assert!(copy.0.join("made.txt").exists());
    let user = String::from_utf8_lossy(&written.stdout).to_lowercase();
    assert!(user.contains("raikersandbox"), "ran as {user}");
    let git = r"C:\Program Files\Git\cmd\git.exe";
    if std::path::Path::new(git).exists() {
        let init = run(&copy, &[git, "init", "-q", "repo"]);
        assert!(
            init.status.success(),
            "{}",
            String::from_utf8_lossy(&init.stderr)
        );
    }
}

#[test]
fn the_account_cannot_write_the_owners_profile_or_a_copy_outside_its_base() {
    let Some(base) = configured() else { return };
    let copy = copy_under(&base, "escape");
    let profile =
        std::env::temp_dir().join(format!("raiker-account-escape-{}", std::process::id()));
    let cmd = std::env::var("ComSpec").unwrap_or_else(|_| r"C:\Windows\System32\cmd.exe".into());
    let target = profile.to_string_lossy().into_owned();
    let attempt = run(&copy, &[&cmd, "/c", &format!("echo x> \"{target}\"")]);
    assert!(
        !profile.exists(),
        "the account wrote into the owner's profile"
    );
    let _ = attempt;
    // A workspace outside the base is refused before anything starts.
    let outside =
        std::env::temp_dir().join(format!("raiker-account-outside-{}", std::process::id()));
    std::fs::create_dir_all(&outside).unwrap();
    let policy = outside.join("policy.json");
    std::fs::write(
        &policy,
        serde_json::json!({"workspace_root": outside, "cwd": outside, "profile_name": "raiker.x"})
            .to_string(),
    )
    .unwrap();
    let refused = Command::new(runner())
        .arg("--policy")
        .arg(&policy)
        .args(["--", &cmd, "/c", "echo"])
        .output()
        .unwrap();
    let _ = std::fs::remove_dir_all(&outside);
    // Outside the base the AppContainer boundary applies instead; it must not
    // run as the account.
    assert!(
        !String::from_utf8_lossy(&refused.stdout)
            .to_lowercase()
            .contains("raikersandbox")
    );
}

#[test]
fn a_run_cannot_touch_another_sessions_copy() {
    let Some(base) = configured() else { return };
    let mine = copy_under(&base, "mine");
    let theirs = copy_under(&base, "theirs");
    std::fs::write(theirs.0.join("secret.txt"), "other session").unwrap();
    let cmd = std::env::var("ComSpec").unwrap_or_else(|_| r"C:\Windows\System32\cmd.exe".into());
    let target = theirs.0.join("planted.txt").to_string_lossy().into_owned();
    let read = theirs.0.join("secret.txt").to_string_lossy().into_owned();
    let attempt = run(
        &mine,
        &[
            &cmd,
            "/c",
            &format!("type \"{read}\" & echo x> \"{target}\""),
        ],
    );
    assert!(
        !theirs.0.join("planted.txt").exists(),
        "a run wrote into another copy"
    );
    assert!(
        !String::from_utf8_lossy(&attempt.stdout).contains("other session"),
        "a run read another copy"
    );
    // Its own copy stays writable, and the grant is gone once the run ends.
    let own = run(&mine, &[&cmd, "/c", "echo ok> own.txt"]);
    assert!(own.status.success() && mine.0.join("own.txt").exists());
}
