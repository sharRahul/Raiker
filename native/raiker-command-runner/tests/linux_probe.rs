#![cfg(target_os = "linux")]

use std::path::PathBuf;
use std::process::Command;

fn output_after_transient_exec_busy(command: &mut Command) -> std::process::Output {
    for attempt in 0..10 {
        match command.output() {
            Ok(output) => return output,
            Err(error) if error.raw_os_error() == Some(libc::ETXTBSY) && attempt < 9 => {
                std::thread::sleep(std::time::Duration::from_millis(50));
            }
            Err(error) => panic!("could not execute test command: {error}"),
        }
    }
    unreachable!()
}

struct Workspace(PathBuf);

impl Drop for Workspace {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

#[test]
fn bubblewrap_probe_observes_descendant_exit_and_host_write_protection() {
    let path = std::env::temp_dir().join(format!(
        "raiker-linux-probe-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir(&path).unwrap();
    let workspace = Workspace(path);
    let runner = workspace.0.join("runner");
    std::fs::copy(env!("CARGO_BIN_EXE_raiker-command-runner"), &runner).unwrap();
    let output = output_after_transient_exec_busy(
        Command::new(&runner)
            .args(["--probe", "--workspace"])
            .arg(&workspace.0),
    );
    assert!(output.status.success(), "probe did not exit successfully");
    let report: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(report["boundary"], "bubblewrap", "{report}");
    assert_eq!(
        report["observations"]["descendant_reaped"], "enforced",
        "{report}"
    );
    assert_eq!(
        report["observations"]["escape_write"], "enforced",
        "{report}"
    );
    assert_eq!(report["observations"]["seccomp"], "enforced", "{report}");
    assert_eq!(report["process_tree_stop"], true, "{report}");
    assert_eq!(report["available"], false, "{report}");
}

#[test]
fn bubblewrap_memory_limit_blocks_an_allocation_that_the_host_control_allows() {
    let path = std::env::temp_dir().join(format!(
        "raiker-linux-memory-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir(&path).unwrap();
    let workspace = Workspace(path);
    let runner = workspace.0.join("runner");
    std::fs::copy(env!("CARGO_BIN_EXE_raiker-command-runner"), &runner).unwrap();
    let python = "/usr/bin/python3";
    let program = "try:\n x = bytearray(100 * 1024 * 1024)\n print('allocated')\nexcept MemoryError:\n print('limited')\n";
    let control = Command::new(python).args(["-c", program]).output().unwrap();
    assert!(control.status.success());
    assert_eq!(String::from_utf8_lossy(&control.stdout).trim(), "allocated");
    let policy = serde_json::json!({
        "workspace_root": workspace.0,
        "cwd": workspace.0,
        "profile_name": "raiker.memory.test",
        "max_memory_bytes": 64 * 1024 * 1024,
        "max_processes": 4096,
        "deadline_seconds": 15
    });
    let policy_path = workspace.0.join("policy.json");
    std::fs::write(&policy_path, policy.to_string()).unwrap();
    let output = output_after_transient_exec_busy(
        Command::new(&runner)
            .arg("--policy")
            .arg(policy_path)
            .arg("--")
            .args([python, "-c", program]),
    );
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "limited");
}

#[test]
fn bubblewrap_respects_a_stricter_inherited_memory_limit() {
    use std::os::unix::process::CommandExt;

    let path = std::env::temp_dir().join(format!(
        "raiker-linux-inherited-limit-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir(&path).unwrap();
    let workspace = Workspace(path);
    let runner = workspace.0.join("runner");
    std::fs::copy(env!("CARGO_BIN_EXE_raiker-command-runner"), &runner).unwrap();
    let policy = serde_json::json!({
        "workspace_root": workspace.0, "cwd": workspace.0,
        "profile_name": "raiker.inherited.test", "deadline_seconds": 15,
        "max_memory_bytes": 1024 * 1024 * 1024, "max_processes": 4096
    });
    let policy_path = workspace.0.join("policy.json");
    std::fs::write(&policy_path, policy.to_string()).unwrap();
    let mut command = Command::new(&runner);
    command.arg("--policy").arg(policy_path).arg("--").args([
        "/usr/bin/python3",
        "-c",
        "print('started')",
    ]);
    unsafe {
        command.pre_exec(|| {
            let limit = libc::rlimit {
                rlim_cur: 256 * 1024 * 1024,
                rlim_max: 256 * 1024 * 1024,
            };
            if libc::setrlimit(libc::RLIMIT_AS, &limit) != 0 {
                return Err(std::io::Error::last_os_error());
            }
            Ok(())
        });
    }
    let output = output_after_transient_exec_busy(&mut command);
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "started");
}

#[test]
fn bubblewrap_hides_host_etc_files_with_a_readable_host_control() {
    let sensitive = "/etc/hostname";
    assert!(
        std::fs::read_to_string(sensitive).is_ok(),
        "host control cannot read {sensitive}"
    );
    let path = std::env::temp_dir().join(format!(
        "raiker-linux-host-read-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir(&path).unwrap();
    let workspace = Workspace(path);
    let runner = workspace.0.join("runner");
    std::fs::copy(env!("CARGO_BIN_EXE_raiker-command-runner"), &runner).unwrap();
    let policy = serde_json::json!({
        "workspace_root": workspace.0, "cwd": workspace.0,
        "profile_name": "raiker.hostread.test", "deadline_seconds": 15,
        "max_processes": 4096
    });
    let policy_path = workspace.0.join("policy.json");
    std::fs::write(&policy_path, policy.to_string()).unwrap();
    let program = "from pathlib import Path\np = Path('/etc/hostname')\nprint('exposed' if p.exists() else 'hidden')";
    let output = output_after_transient_exec_busy(
        Command::new(&runner)
            .arg("--policy")
            .arg(policy_path)
            .arg("--")
            .args(["/usr/bin/python3", "-c", program]),
    );
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "hidden");
}

#[test]
fn bubblewrap_returns_promptly_when_a_command_finishes_before_its_deadline() {
    use std::time::{Duration, Instant};
    let path = std::env::temp_dir().join(format!(
        "raiker-linux-early-exit-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir(&path).unwrap();
    let workspace = Workspace(path);
    let runner = workspace.0.join("runner");
    std::fs::copy(env!("CARGO_BIN_EXE_raiker-command-runner"), &runner).unwrap();
    let policy = serde_json::json!({
        "workspace_root": workspace.0, "cwd": workspace.0,
        "profile_name": "raiker.early.test", "deadline_seconds": 30,
        "max_processes": 4096
    });
    let policy_path = workspace.0.join("policy.json");
    std::fs::write(&policy_path, policy.to_string()).unwrap();
    let started = Instant::now();
    let output = output_after_transient_exec_busy(
        Command::new(&runner)
            .arg("--policy")
            .arg(policy_path)
            .arg("--")
            .args(["/usr/bin/python3", "-c", "print('completed')"]),
    );
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "completed");
    assert!(started.elapsed() < Duration::from_secs(10));
}

#[test]
fn bubblewrap_deadline_stops_a_command_that_remains_live_in_the_control() {
    use std::time::{Duration, Instant};
    let path = std::env::temp_dir().join(format!(
        "raiker-linux-deadline-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir(&path).unwrap();
    let workspace = Workspace(path);
    let runner = workspace.0.join("runner");
    std::fs::copy(env!("CARGO_BIN_EXE_raiker-command-runner"), &runner).unwrap();
    let program = "while True: pass";
    let mut control = Command::new("/usr/bin/python3")
        .args(["-c", program])
        .spawn()
        .unwrap();
    std::thread::sleep(Duration::from_millis(100));
    let was_running = control.try_wait().unwrap().is_none();
    let _ = control.kill();
    let _ = control.wait();
    assert!(
        was_running,
        "the outside control terminated before its deadline"
    );
    let policy = serde_json::json!({
        "workspace_root": workspace.0, "cwd": workspace.0,
        "profile_name": "raiker.deadline.test", "deadline_seconds": 1,
        "max_processes": 4096
    });
    let policy_path = workspace.0.join("policy.json");
    std::fs::write(&policy_path, policy.to_string()).unwrap();
    let started = Instant::now();
    let output = output_after_transient_exec_busy(
        Command::new(&runner)
            .arg("--policy")
            .arg(policy_path)
            .arg("--")
            .args(["/usr/bin/python3", "-c", program]),
    );
    let elapsed = started.elapsed();
    assert!(
        !output.status.success(),
        "deadline must terminate the command"
    );
    assert!(
        elapsed >= Duration::from_millis(700) && elapsed < Duration::from_secs(10),
        "unexpected deadline timing: {elapsed:?}; stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
}

#[test]
fn bubblewrap_cpu_limit_terminates_cpu_intensive_code_before_wall_deadline() {
    use std::time::{Duration, Instant};
    let path = std::env::temp_dir().join(format!(
        "raiker-linux-cpu-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir(&path).unwrap();
    let workspace = Workspace(path);
    let runner = workspace.0.join("runner");
    std::fs::copy(env!("CARGO_BIN_EXE_raiker-command-runner"), &runner).unwrap();
    let program = "while True: pass";
    let mut control = Command::new("/usr/bin/python3")
        .args(["-c", program])
        .spawn()
        .unwrap();
    std::thread::sleep(Duration::from_millis(100));
    let was_running = control.try_wait().unwrap().is_none();
    let _ = control.kill();
    let _ = control.wait();
    assert!(
        was_running,
        "the outside control terminated before its deadline"
    );
    let policy = serde_json::json!({
        "workspace_root": workspace.0, "cwd": workspace.0,
        "profile_name": "raiker.cpu.test", "deadline_seconds": 15, "max_cpu_seconds": 1,
        "max_processes": 4096
    });
    let policy_path = workspace.0.join("policy.json");
    std::fs::write(&policy_path, policy.to_string()).unwrap();
    let started = Instant::now();
    let output = output_after_transient_exec_busy(
        Command::new(&runner)
            .arg("--policy")
            .arg(policy_path)
            .arg("--")
            .args(["/usr/bin/python3", "-c", program]),
    );
    let elapsed = started.elapsed();
    assert!(
        !output.status.success(),
        "CPU limit must terminate the command"
    );
    assert!(
        elapsed >= Duration::from_millis(500) && elapsed < Duration::from_secs(10),
        "unexpected CPU-limit timing: {elapsed:?}; stderr: {}",
        String::from_utf8_lossy(&output.stderr)
    );
}

#[test]
fn bubblewrap_process_limit_denies_forks_that_the_host_control_allows() {
    let uid = unsafe { libc::getuid() };
    assert_ne!(uid, 0, "RLIMIT_NPROC is not enforced for root");
    let program = "import os, time\nchildren=[]\nlimited=False\nfor i in range(40):\n try:\n  pid=os.fork()\n except OSError:\n  limited=True\n  break\n if pid == 0:\n  time.sleep(1.5)\n  os._exit(0)\n children.append(pid)\nfor pid in children: os.waitpid(pid, 0)\nprint('limited' if limited else 'complete')\n";
    let control = Command::new("/usr/bin/python3")
        .args(["-c", program])
        .output()
        .unwrap();
    assert!(control.status.success());
    assert_eq!(
        String::from_utf8_lossy(&control.stdout).trim(),
        "complete",
        "outside control cannot create the required children"
    );

    let path = std::env::temp_dir().join(format!(
        "raiker-linux-process-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir(&path).unwrap();
    let workspace = Workspace(path);
    let runner = workspace.0.join("runner");
    std::fs::copy(env!("CARGO_BIN_EXE_raiker-command-runner"), &runner).unwrap();
    let policy_path = workspace.0.join("policy.json");
    // RLIMIT_NPROC accounting can include processes not visible in this PID
    // namespace. Find the smallest bounded threshold that starts the control,
    // rather than assuming /proc contains the complete user-wide count.
    let mut minimum = None;
    for limit in (16..=1024u32).step_by(16) {
        let policy = serde_json::json!({"workspace_root": workspace.0, "cwd": workspace.0,
            "profile_name": "raiker.process.test", "deadline_seconds": 15,
            "max_processes": limit});
        std::fs::write(&policy_path, policy.to_string()).unwrap();
        let control = output_after_transient_exec_busy(
            Command::new(&runner)
                .arg("--policy")
                .arg(&policy_path)
                .arg("--")
                .args(["/usr/bin/python3", "-c", "print('ready')"]),
        );
        if control.status.success() && String::from_utf8_lossy(&control.stdout).trim() == "ready" {
            minimum = Some(limit);
            break;
        }
    }
    let limit = minimum.expect("no process limit allowed the sandbox control to start") + 8;
    let policy = serde_json::json!({"workspace_root": workspace.0, "cwd": workspace.0,
        "profile_name": "raiker.process.test", "deadline_seconds": 15,
        "max_processes": limit});
    std::fs::write(&policy_path, policy.to_string()).unwrap();
    let output = output_after_transient_exec_busy(
        Command::new(&runner)
            .arg("--policy")
            .arg(policy_path)
            .arg("--")
            .args(["/usr/bin/python3", "-c", program]),
    );
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(
        String::from_utf8_lossy(&output.stdout).trim(),
        "limited",
        "process limit was not enforced"
    );
}
