#![cfg(windows)]
//! Production refusal contracts for the unqualified restricted-account boundary.
//! Historical mechanism tests live in the non-shipped unit-test module.
//! Requires a host where the owner ran
//! `--setup-account`. Skipped elsewhere: without the account there is nothing
//! to measure, and these tests must not create one themselves.

use std::path::PathBuf;
use std::process::Command;

// These cases mutate one machine-wide account pool and inspect its grants.
// Keep cases apart; the overlap case still launches concurrent runs itself.
static ACCOUNT_TEST: std::sync::Mutex<()> = std::sync::Mutex::new(());

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

#[test]
fn account_status_reports_each_dedicated_logon_policy_without_mutating_it() {
    let _account_test = ACCOUNT_TEST.lock().unwrap();
    let Some(_) = configured() else { return };
    let output = Command::new(runner())
        .arg("--account-status")
        .output()
        .unwrap();
    let status: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    let policies = status["logon_policy"]["accounts"]
        .as_array()
        .expect("account status must expose read-only policy evidence");
    assert_eq!(policies.len(), 4);
    for account in policies {
        assert_eq!(account["dedicated"], true, "{account}");
        assert!(
            account["sid"]
                .as_str()
                .is_some_and(|sid| sid.starts_with("S-1-5-21-"))
        );
        if account["reason"].is_null() {
            assert!(account["network_denied"].is_boolean());
            assert!(account["remote_interactive_denied"].is_boolean());
            assert_eq!(
                account["verified"],
                account["network_denied"] == true && account["remote_interactive_denied"] == true
            );
        } else {
            assert!(account["network_denied"].is_null());
            assert!(account["remote_interactive_denied"].is_null());
            assert_eq!(account["verified"], false);
        }
    }
}

struct Copy(PathBuf, PathBuf);

impl Drop for Copy {
    fn drop(&mut self) {
        use std::os::windows::fs::MetadataExt;
        let Ok(metadata) = std::fs::symlink_metadata(&self.0) else {
            return;
        };
        // Never follow a replaced copy root or remove anything outside the
        // resolved, explicitly selected disposable sandbox base.
        if metadata.file_attributes() & 0x400 != 0 {
            return;
        }
        let Ok(resolved) = self.0.canonicalize() else {
            return;
        };
        if resolved.parent() == Some(self.1.as_path()) {
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }
}

fn copy_under(base: &std::path::Path, name: &str) -> Copy {
    let path = base.join(format!("{name}-{}", std::process::id()));
    std::fs::create_dir(&path).unwrap();
    Copy(path, base.canonicalize().unwrap())
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

const REFUSAL: &str = "native_sandbox_account_profile_isolation_unavailable";

fn assert_refused(output: &std::process::Output) {
    assert!(
        !output.status.success(),
        "an unqualified boundary executed a command"
    );
    assert!(
        String::from_utf8_lossy(&output.stderr).contains(REFUSAL),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
}

#[test]
fn production_execution_refuses_before_grants_or_process_side_effects() {
    let _account_test = ACCOUNT_TEST.lock().unwrap();
    let Some(base) = configured() else { return };
    let copy = copy_under(&base, "production-refusal");
    let before = Command::new("icacls").arg(&copy.0).output().unwrap();
    let output = run(
        &copy,
        &[
            r"C:\Windows\System32\cmd.exe",
            "/c",
            "echo unsafe> should-not-exist.txt",
        ],
    );
    assert_refused(&output);
    assert!(!copy.0.join("should-not-exist.txt").exists());
    let after = Command::new("icacls").arg(&copy.0).output().unwrap();
    assert_eq!(
        before.stdout, after.stdout,
        "refusal changed the copy's ACL"
    );
}

#[test]
fn production_probe_reports_unavailable_without_claiming_isolation() {
    let _account_test = ACCOUNT_TEST.lock().unwrap();
    let Some(_) = configured() else { return };
    let output = Command::new(runner())
        .args(["--probe", "--workspace"])
        .arg(std::env::temp_dir())
        .output()
        .unwrap();
    let report: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(report["boundary"], "restricted_account");
    assert_eq!(report["available"], false);
    assert_eq!(report["reason"], REFUSAL);
    assert_eq!(report["account_status"]["execution_available"], false);
    let gaps = report["account_status"]["isolation_gaps"]
        .as_array()
        .unwrap();
    assert!(gaps.iter().any(|gap| gap == "persistent_account_profile"));
    assert!(gaps.iter().any(|gap| gap == "explicit_descendant_acl"));
    assert!(
        !report["observations"]
            .as_object()
            .is_some_and(|rows| rows.values().any(|value| value == "enforced"))
    );
}

#[test]
fn hostile_explicit_descendants_do_not_enable_production_account_reuse() {
    let _account_test = ACCOUNT_TEST.lock().unwrap();
    let Some(base) = configured() else { return };
    let first = copy_under(&base, "hostile-first");
    let second = copy_under(&base, "hostile-second");
    let retained = first.0.join("retained");
    std::fs::create_dir(&retained).unwrap();
    std::fs::write(retained.join("secret.txt"), "cross-copy-secret").unwrap();
    let grant = Command::new("icacls")
        .arg(&retained)
        .args(["/grant", "RaikerSandbox:(OI)(CI)(F)"])
        .output()
        .unwrap();
    assert!(
        grant.status.success(),
        "failed to construct explicit descendant fixture"
    );
    let output = run(
        &second,
        &[
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            &format!(
                "Get-Content -LiteralPath '{}'",
                retained.join("secret.txt").display()
            ),
        ],
    );
    assert_refused(&output);
    assert!(!String::from_utf8_lossy(&output.stdout).contains("cross-copy-secret"));
}

#[test]
fn production_executable_cannot_enable_the_test_only_diagnostic_path() {
    let _account_test = ACCOUNT_TEST.lock().unwrap();
    let Some(base) = configured() else { return };
    let copy = copy_under(&base, "no-diagnostic-optin");
    let policy = copy.0.join("policy.json");
    std::fs::write(&policy, serde_json::json!({"workspace_root": copy.0, "cwd": copy.0, "profile_name": "raiker.refusal"}).to_string()).unwrap();
    let output = Command::new(runner())
        .env("RAIKER_ACCOUNT_TEST_DIAGNOSTIC", "1")
        .args(["--policy"])
        .arg(&policy)
        .args([
            "--",
            r"C:\Windows\System32\cmd.exe",
            "/c",
            "echo unsafe> should-not-exist.txt",
        ])
        .output()
        .unwrap();
    assert_refused(&output);
    assert!(!copy.0.join("should-not-exist.txt").exists());
}
