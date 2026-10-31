#![cfg(target_os = "macos")]

use std::path::{Path, PathBuf};
use std::process::{Command, Output};

struct Fixture {
    root: PathBuf,
    outside: PathBuf,
}

impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.outside);
        let _ = std::fs::remove_dir_all(&self.root);
    }
}

fn run(runner: &Path, policy: &Path, argv: &[&str]) -> Output {
    Command::new(runner)
        .arg("--policy")
        .arg(policy)
        .arg("--")
        .args(argv)
        .output()
        .unwrap()
}

#[test]
fn seatbelt_probe_measures_real_filesystem_controls_without_claiming_availability() {
    let name = format!(
        "raiker-seatbelt-probe-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    );
    let temp = std::fs::canonicalize(std::env::temp_dir()).unwrap();
    let root = temp.join(&name);
    std::fs::create_dir(&root).unwrap();
    let fixture = Fixture {
        root,
        outside: temp.join(format!("{name}-outside")),
    };
    let runner = fixture.root.join("runner");
    std::fs::copy(env!("CARGO_BIN_EXE_raiker-command-runner"), &runner).unwrap();
    let output = Command::new(&runner)
        .arg("--probe")
        .arg("--workspace")
        .arg(&fixture.root)
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let report: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(report["boundary"], "seatbelt", "{report}");
    for property in ["relay", "workspace_write", "escape_write", "masked_read"] {
        assert_eq!(report["observations"][property], "enforced", "{report}");
    }
    assert_eq!(report["available"], false, "{report}");
}

#[test]
fn seatbelt_allows_workspace_reads_but_denies_outside_reads_and_writes() {
    let name = format!(
        "raiker-seatbelt-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    );
    let temp = std::fs::canonicalize(std::env::temp_dir()).unwrap();
    let root = temp.join(&name);
    std::fs::create_dir(&root).unwrap();
    let fixture = Fixture {
        root,
        outside: temp.join(format!("{name}-outside")),
    };
    let inside = fixture.root.join("inside.txt");
    std::fs::write(&inside, "workspace control").unwrap();
    std::fs::write(&fixture.outside, "outside private data").unwrap();
    assert_eq!(
        std::fs::read_to_string(&fixture.outside).unwrap(),
        "outside private data"
    );
    let runner = fixture.root.join("runner");
    std::fs::copy(env!("CARGO_BIN_EXE_raiker-command-runner"), &runner).unwrap();
    let policy = fixture.root.join("policy.json");
    std::fs::write(
        &policy,
        serde_json::json!({
            "workspace_root": fixture.root, "cwd": fixture.root,
            "profile_name": "raiker.seatbelt.test", "deadline_seconds": 15,
            "max_processes": 4096
        })
        .to_string(),
    )
    .unwrap();
    let inside_path = inside.to_str().unwrap();
    let outside_path = fixture.outside.to_str().unwrap();
    let allowed = run(&runner, &policy, &["/bin/cat", inside_path]);
    assert!(
        allowed.status.success(),
        "sandboxed control failed: {}",
        String::from_utf8_lossy(&allowed.stderr)
    );
    assert_eq!(
        String::from_utf8_lossy(&allowed.stdout),
        "workspace control"
    );
    let denied_read = run(&runner, &policy, &["/bin/cat", outside_path]);
    assert!(
        !denied_read.status.success(),
        "sandbox read outside the workspace"
    );
    assert!(!String::from_utf8_lossy(&denied_read.stdout).contains("outside private data"));
    let denied_write = run(
        &runner,
        &policy,
        &[
            "/bin/sh",
            "-c",
            "printf changed > \"$1\"",
            "test",
            outside_path,
        ],
    );
    assert!(
        !denied_write.status.success(),
        "sandbox wrote outside the workspace"
    );
    assert_eq!(
        std::fs::read_to_string(&fixture.outside).unwrap(),
        "outside private data"
    );
}
