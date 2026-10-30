#![cfg(windows)]

use std::path::PathBuf;
use std::process::{Command, Stdio};

struct ProbeWorkspace {
    path: PathBuf,
    runner: PathBuf,
}

struct CleanupDirectory(PathBuf);

impl Drop for CleanupDirectory {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

impl Drop for ProbeWorkspace {
    fn drop(&mut self) {
        // The probe grants an AppContainer capability on this workspace.
        // Revoke it even when an assertion fails before removing our directory.
        let _ = Command::new(&self.runner)
            .args(["--revoke-grant", "--workspace"])
            .arg(&self.path)
            .status();
        let _ = std::fs::remove_dir_all(&self.path);
    }
}

#[test]
fn real_appcontainer_probe_observes_descendant_exit_and_requires_disposable_workspace() {
    let path = std::env::temp_dir().join(format!(
        "raiker-real-probe-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir(&path).unwrap();
    let workspace = ProbeWorkspace {
        runner: path.join("runner.exe"),
        path,
    };
    std::fs::copy(
        env!("CARGO_BIN_EXE_raiker-command-runner"),
        &workspace.runner,
    )
    .unwrap();
    let output = Command::new(&workspace.runner)
        .args(["--probe", "--workspace"])
        .arg(&workspace.path)
        .output()
        .unwrap();
    assert!(output.status.success(), "probe did not exit successfully");
    let report: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(report["boundary"], "appcontainer", "{report}");
    assert_eq!(report["descendant_start"]["state"], "started", "{report}");
    assert_eq!(
        report["observations"]["descendant_reaped"], "enforced",
        "{report}"
    );
    assert_eq!(report["process_tree_stop"], true, "{report}");
    assert_eq!(report["available"], false, "{report}");
    for property in ["relay", "workspace_write", "escape_write", "masked_read"] {
        assert_eq!(report["observations"][property], "enforced", "{report}");
    }
    // Egress is proven only when the unsandboxed control reaches the gateway.
    // Hosted runners drop that packet, so there it stays indeterminate and the
    // probe must not report the boundary as fully enforced. It may never be
    // measured as unenforced.
    match report["observations"]["egress"].as_str() {
        Some("enforced") => assert_eq!(
            report["reason"], "native_disposable_workspace_required",
            "{report}"
        ),
        Some("indeterminate") => {
            assert_eq!(report["reason"], "native_sandbox_not_enforced", "{report}")
        }
        _ => panic!("egress not contained: {report}"),
    }
    let revoke = Command::new(&workspace.runner)
        .args(["--revoke-grant", "--workspace"])
        .arg(&workspace.path)
        .status()
        .unwrap();
    assert!(revoke.success(), "workspace ACL revocation failed");
}

#[test]
fn selftest_hold_keeps_parent_alive_until_its_control_pipe_closes() {
    use std::io::BufRead;

    let root = std::env::temp_dir().join(format!(
        "raiker-probe-hold-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir(&root).unwrap();
    let payload = serde_json::json!({
        "nonce": "hold-control",
        "inside_path": root.join("inside"),
        "outside_paths": [],
        "masked_read_path": root.join("missing"),
        "connect_address": "127.0.0.1:9",
        "spawn_grandchild": false,
        "hold_for_probe": true
    });
    let mut child = Command::new(env!("CARGO_BIN_EXE_raiker-command-runner"))
        .arg("--selftest")
        .arg(payload.to_string())
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .unwrap();
    let mut response = String::new();
    std::io::BufReader::new(child.stdout.take().unwrap())
        .read_line(&mut response)
        .unwrap();
    assert_eq!(
        serde_json::from_str::<serde_json::Value>(&response).unwrap()["nonce"],
        "hold-control"
    );
    assert!(
        child.try_wait().unwrap().is_none(),
        "control process did not stay alive"
    );
    drop(child.stdin.take());
    assert!(child.wait().unwrap().success());
    std::fs::remove_dir(root).unwrap();
}

#[test]
fn appcontainer_denies_protected_and_outside_files_with_a_readable_workspace_control() {
    let parent = std::env::temp_dir().join(format!(
        "raiker-windows-files-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir(&parent).unwrap();
    let _parent_cleanup = CleanupDirectory(parent.clone());
    let path = parent.join("workspace");
    std::fs::create_dir(&path).unwrap();
    let workspace = ProbeWorkspace {
        runner: path.join("runner.exe"),
        path,
    };
    std::fs::copy(
        env!("CARGO_BIN_EXE_raiker-command-runner"),
        &workspace.runner,
    )
    .unwrap();
    let inside = workspace.path.join("inside.txt");
    let outside = parent.join("outside.txt");
    let protected = workspace.path.join(".raiker");
    let git = workspace.path.join(".git");
    std::fs::create_dir(&protected).unwrap();
    std::fs::create_dir(&git).unwrap();
    std::fs::write(&inside, "allowed control").unwrap();
    std::fs::write(&outside, "outside private").unwrap();
    std::fs::write(protected.join("secret"), "internal private").unwrap();
    assert_eq!(
        std::fs::read_to_string(&outside).unwrap(),
        "outside private"
    );
    assert_eq!(
        std::fs::read_to_string(protected.join("secret")).unwrap(),
        "internal private"
    );
    let policy = workspace.path.join("policy.json");
    std::fs::write(
        &policy,
        serde_json::json!({
            "workspace_root": workspace.path, "cwd": workspace.path,
            "profile_name": format!("raiker.files.{}", std::process::id()),
            "deny_paths": [".raiker"], "readonly_paths": [".git"], "deadline_seconds": 15
        })
        .to_string(),
    )
    .unwrap();
    let write_target = parent.join("outside-write.txt");
    std::fs::write(&write_target, "control").unwrap();
    std::fs::remove_file(&write_target).unwrap();
    let launch = |payload: &serde_json::Value| {
        Command::new(&workspace.runner)
            .arg("--policy")
            .arg(&policy)
            .arg("--")
            .arg(&workspace.runner)
            .arg("--selftest")
            .arg(payload.to_string())
            .output()
            .unwrap()
    };
    let run = |read_path: &std::path::Path, writes: Vec<PathBuf>| {
        let payload = serde_json::json!({
            "nonce": "windows-files-control",
            "inside_path": workspace.path.join(format!("probe-write-{}", writes.len())),
            "outside_paths": writes,
            "masked_read_path": read_path,
            "connect_address": "invalid",
            "spawn_grandchild": false
        });
        let output = launch(&payload);
        assert!(
            output.status.success(),
            "sandboxed control failed: {}",
            String::from_utf8_lossy(&output.stderr)
        );
        serde_json::from_slice::<serde_json::Value>(&output.stdout).unwrap()
    };
    let control = run(&inside, vec![]);
    assert_eq!(control["masked_read"]["allowed"], true, "{control}");
    for path in [outside.clone(), protected.join("secret")] {
        let denied = run(&path, vec![]);
        assert_eq!(denied["masked_read"]["allowed"], false, "{denied}");
    }
    let write = run(&inside, vec![write_target.clone()]);
    assert_eq!(write["outside_writes"][0]["allowed"], false, "{write}");
    assert!(
        !write_target.exists(),
        "sandbox created a host file outside workspace"
    );
    let git_target = git.join("sandbox-write");
    std::fs::write(&git_target, "owner control").unwrap();
    std::fs::remove_file(&git_target).unwrap();
    let git_write = run(&inside, vec![git_target.clone()]);
    assert_eq!(
        git_write["outside_writes"][0]["allowed"], false,
        "{git_write}"
    );
    assert!(
        !git_target.exists(),
        "sandbox wrote to protected Git metadata"
    );
    // Adversarial control: a grant to every AppContainer cannot be withheld by
    // a capability deny, so the runner must refuse rather than launch.
    let grant = Command::new("icacls")
        .arg(&git)
        .args(["/grant", "*S-1-15-2-1:(OI)(CI)(M)"])
        .output()
        .unwrap();
    assert!(
        grant.status.success(),
        "failed to construct the adversarial ACL control"
    );
    let refused = launch(&serde_json::json!({
        "nonce": "windows-files-shared",
        "inside_path": workspace.path.join("probe-write-shared"),
        "outside_paths": [git_target.clone()],
        "masked_read_path": inside,
        "connect_address": "invalid",
        "spawn_grandchild": false
    }));
    assert!(!refused.status.success(), "shared .git was not refused");
    assert!(
        String::from_utf8_lossy(&refused.stderr)
            .contains("native_sandbox_protected_path_shared_with_app_packages"),
        "{}",
        String::from_utf8_lossy(&refused.stderr)
    );
    assert!(!git_target.exists(), "sandbox wrote to shared Git metadata");
    std::fs::write(&git_target, "owner still writes").unwrap();
    std::fs::remove_file(git_target).unwrap();
    assert_eq!(
        std::fs::read_to_string(&outside).unwrap(),
        "outside private"
    );
    drop(workspace);
    std::fs::remove_file(outside).unwrap();
    std::fs::remove_dir(parent).unwrap();
}
