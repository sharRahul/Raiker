#![cfg(windows)]
//! Native launch must reject a missing or mismatched Linux runner pin even
//! when Python's earlier enforcement proof was cached. No distro setup here.

use std::path::PathBuf;
use std::process::Command;

#[test]
fn recognized_wsl_copies_still_require_the_expected_runner_pin() {
    let runner = env!("CARGO_BIN_EXE_raiker-command-runner");
    let output = Command::new(runner).arg("--wsl-status").output().unwrap();
    let status: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    if status["configured"] != true {
        assert!(
            std::env::var_os("RAIKER_REQUIRE_WSL_SANDBOX").is_none(),
            "WSL sandbox required but not configured: {status}"
        );
        return;
    }
    let base = PathBuf::from(status["base"].as_str().unwrap());
    let nonce = format!(
        "{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    );
    let copy = base.join(format!("pin-policy-{nonce}"));
    std::fs::create_dir(&copy).unwrap();
    let copy = ScopedCopy(copy, base.canonicalize().unwrap());
    std::fs::write(copy.0.join("seed.txt"), "pin-test-only").unwrap();
    let policy = std::env::temp_dir().join(format!("raiker-wsl-pin-{nonce}.json"));
    let policy = ScopedPolicy(policy);
    for expected in [None, Some("0".repeat(64))] {
        let mut document = serde_json::json!({
            "workspace_root": copy.0, "cwd": copy.0,
            "profile_name": "raiker.wsl.pin-test", "deadline_seconds": 10,
        });
        if let Some(expected) = expected {
            document["wsl_runner_sha256"] = serde_json::json!(expected);
        }
        std::fs::write(&policy.0, document.to_string()).unwrap();
        let refused = Command::new(runner)
            .arg("--policy")
            .arg(&policy.0)
            .args(["--", "cat", "seed.txt"])
            .output()
            .unwrap();
        assert!(!refused.status.success());
        assert!(
            refused.stdout.is_empty(),
            "a missing pin executed the child"
        );
        assert!(
            String::from_utf8_lossy(&refused.stderr).contains("native_sandbox_wsl_runner_mismatch"),
            "{}",
            String::from_utf8_lossy(&refused.stderr)
        );
    }
}

struct ScopedCopy(PathBuf, PathBuf);

impl Drop for ScopedCopy {
    fn drop(&mut self) {
        use std::os::windows::fs::MetadataExt;
        let Ok(metadata) = std::fs::symlink_metadata(&self.0) else {
            return;
        };
        let Ok(resolved) = self.0.canonicalize() else {
            return;
        };
        if metadata.file_attributes() & 0x400 == 0 && resolved.parent() == Some(self.1.as_path()) {
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }
}

struct ScopedPolicy(PathBuf);

impl Drop for ScopedPolicy {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.0);
    }
}
