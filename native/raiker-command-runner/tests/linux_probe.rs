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
    let runner_dir = Workspace(workspace.0.with_extension("runner-dir"));
    std::fs::create_dir(&runner_dir.0).unwrap();
    let runner = runner_dir.0.join("runner");
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
fn bubblewrap_never_executes_a_fake_helper_from_path() {
    use std::os::unix::fs::PermissionsExt;
    let path = std::env::temp_dir().join(format!(
        "raiker-linux-fake-bwrap-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir(&path).unwrap();
    let workspace = Workspace(path);
    let fake_dir = workspace.0.join("fake-bin");
    std::fs::create_dir(&fake_dir).unwrap();
    let fake = fake_dir.join("bwrap");
    std::fs::write(
        &fake,
        "#!/bin/sh\nprintf launched > \"$RAIKER_FAKE_MARKER\"\n",
    )
    .unwrap();
    std::fs::set_permissions(&fake, std::fs::Permissions::from_mode(0o755)).unwrap();
    let marker = workspace.0.join("fake-launched");
    let runner = workspace.0.join("runner");
    std::fs::copy(env!("CARGO_BIN_EXE_raiker-command-runner"), &runner).unwrap();
    let policy = serde_json::json!({
        "workspace_root": workspace.0, "cwd": workspace.0,
        "profile_name": "raiker.fake.test", "deadline_seconds": 15,
        "max_processes": 4096
    });
    let policy_path = workspace.0.join("policy.json");
    std::fs::write(&policy_path, policy.to_string()).unwrap();
    let output = output_after_transient_exec_busy(
        Command::new(&runner)
            .arg("--policy")
            .arg(policy_path)
            .arg("--")
            .args(["/usr/bin/python3", "-c", "print('sandbox started')"])
            .env("PATH", &fake_dir)
            .env("RAIKER_FAKE_MARKER", &marker),
    );
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(
        String::from_utf8_lossy(&output.stdout).trim(),
        "sandbox started"
    );
    assert!(!marker.exists(), "fake Bubblewrap ran on the host");
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
fn bubblewrap_hides_host_configuration_and_local_software_with_host_controls() {
    let sensitive = "/etc/hostname";
    assert!(
        std::fs::read_to_string(sensitive).is_ok(),
        "host control cannot read {sensitive}"
    );
    assert!(
        std::path::Path::new("/usr/local/bin").is_dir(),
        "host local software control missing"
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
    let program = "from pathlib import Path\nprint(' '.join('exposed' if Path(p).exists() else 'hidden' for p in ['/etc/hostname', '/usr/local/bin']))";
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
        "hidden hidden"
    );
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

#[test]
fn filtered_egress_reaches_only_the_proxy_socket_from_inside_the_namespace() {
    use std::io::{Read, Write};
    use std::os::unix::net::UnixListener;
    let path = std::env::temp_dir().join(format!(
        "raiker-linux-egress-{}-{}",
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
    // Outside the workspace, as Raiker places it: the sandbox sees it only
    // through the bridge's bind mount.
    let socket_dir = std::env::temp_dir().join(format!("rk-egress-test-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&socket_dir);
    std::fs::create_dir(&socket_dir).unwrap();
    let socket = socket_dir.join("egress.sock");
    let listener = UnixListener::bind(&socket).unwrap();
    std::thread::spawn(move || {
        for stream in listener.incoming() {
            let mut stream = stream.unwrap();
            let mut request = [0u8; 4];
            if stream.read_exact(&mut request).is_ok() {
                let _ = stream.write_all(b"pong");
            }
        }
    });
    // Through the bridge the proxy answers; a direct connection anywhere else
    // has no route. The second address is a public resolver: an unsandboxed
    // control would reach it or time out, never fail with "unreachable".
    let program = concat!(
        "import socket\n",
        "s = socket.create_connection(('127.0.0.1', 3128), timeout=5)\n",
        "s.sendall(b'ping')\n",
        "print(s.recv(4).decode())\n",
        "try:\n",
        "    socket.create_connection(('1.1.1.1', 443), timeout=3)\n",
        "    print('direct-reached')\n",
        "except OSError as error:\n",
        "    print('direct-refused', error.errno)\n",
    );
    let policy = serde_json::json!({
        "workspace_root": workspace.0,
        "cwd": workspace.0,
        "profile_name": "raiker.egress.test",
        "max_processes": 4096,
        "network": "proxy:127.0.0.1:3128",
        "proxy_socket": socket,
        "deadline_seconds": 20
    });
    let policy_path = workspace.0.join("policy.json");
    std::fs::write(&policy_path, policy.to_string()).unwrap();
    let output = output_after_transient_exec_busy(
        Command::new(&runner)
            .arg("--policy")
            .arg(policy_path)
            .arg("--")
            .args(["/usr/bin/python3", "-c", program]),
    );
    let _ = std::fs::remove_dir_all(&socket_dir);
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(
        output.status.success(),
        "{stdout}\n{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let lines: Vec<&str> = stdout.lines().collect();
    assert_eq!(lines[0], "pong", "{stdout}");
    assert!(lines[1].starts_with("direct-refused"), "{stdout}");
}

#[test]
fn an_interactive_run_sees_a_terminal_inside_bubblewrap() {
    use std::io::Read;
    use std::os::fd::FromRawFd;
    use std::process::Stdio;
    let path = std::env::temp_dir().join(format!(
        "raiker-linux-pty-{}-{}",
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
        "workspace_root": workspace.0,
        "cwd": workspace.0,
        "profile_name": "raiker.pty.test",
        "pty": true,
        "max_processes": 4096,
        "deadline_seconds": 15
    });
    let policy_path = workspace.0.join("policy.json");
    std::fs::write(&policy_path, policy.to_string()).unwrap();
    let (mut master, mut slave) = (0, 0);
    let opened = unsafe {
        libc::openpty(
            &mut master,
            &mut slave,
            std::ptr::null_mut(),
            std::ptr::null(),
            std::ptr::null(),
        )
    };
    assert_eq!(opened, 0);
    let stdio = |fd: i32| unsafe { Stdio::from_raw_fd(libc::dup(fd)) };
    // A test running in parallel may fork while the runner copy is still
    // open for writing; exec then fails with ETXTBSY until that child execs.
    let mut attempts = 0;
    let mut child = loop {
        let spawned = Command::new(&runner)
            .arg("--policy")
            .arg(&policy_path)
            .arg("--")
            .args([
                "/usr/bin/python3",
                "-c",
                "import os; print('tty', os.isatty(0), os.isatty(1))",
            ])
            .stdin(stdio(slave))
            .stdout(stdio(slave))
            .stderr(stdio(slave))
            .spawn();
        match spawned {
            Err(error) if error.raw_os_error() == Some(libc::ETXTBSY) && attempts < 20 => {
                attempts += 1;
                std::thread::sleep(std::time::Duration::from_millis(50));
            }
            other => break other.unwrap(),
        }
    };
    unsafe { libc::close(slave) };
    let status = child.wait().unwrap();
    let mut file = unsafe { std::fs::File::from_raw_fd(master) };
    let mut output = Vec::new();
    let mut buffer = [0u8; 4096];
    // Reading the master after the slave closes ends with EIO, not EOF.
    while let Ok(read) = file.read(&mut buffer) {
        if read == 0 {
            break;
        }
        output.extend_from_slice(&buffer[..read]);
    }
    let text = String::from_utf8_lossy(&output);
    assert!(status.success(), "{text}");
    assert!(text.contains("tty True True"), "{text}");
}

#[test]
fn a_toolchain_outside_usr_runs_only_when_its_prefix_is_mounted() {
    let stamp = format!(
        "{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    );
    let workspace = Workspace(std::env::temp_dir().join(format!("raiker-linux-toolchain-{stamp}")));
    std::fs::create_dir(&workspace.0).unwrap();
    // A prefix outside `/usr`, as a hosted runner's Python is.
    let prefix = Workspace(std::env::temp_dir().join(format!("raiker-linux-prefix-{stamp}")));
    std::fs::create_dir_all(prefix.0.join("bin")).unwrap();
    let interpreter = prefix.0.join("bin").join("python");
    std::fs::copy("/usr/bin/python3", &interpreter).unwrap();
    let runner = workspace.0.join("runner");
    std::fs::copy(env!("CARGO_BIN_EXE_raiker-command-runner"), &runner).unwrap();
    let run = |toolchains: serde_json::Value| {
        let policy = serde_json::json!({
            "workspace_root": workspace.0, "cwd": workspace.0,
            "profile_name": "raiker.toolchain.test", "deadline_seconds": 15,
            "max_processes": 4096, "toolchain_paths": toolchains,
        });
        let policy_path = workspace.0.join("policy.json");
        std::fs::write(&policy_path, policy.to_string()).unwrap();
        output_after_transient_exec_busy(
            Command::new(&runner)
                .arg("--policy")
                .arg(&policy_path)
                .arg("--")
                .arg(&interpreter)
                .args(["-c", "print('ran')"]),
        )
    };
    let without = run(serde_json::json!([]));
    assert!(!without.status.success(), "an unmounted toolchain ran");
    let with = run(serde_json::json!([prefix.0]));
    assert!(
        with.status.success(),
        "{}",
        String::from_utf8_lossy(&with.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&with.stdout).trim(), "ran");
}

#[test]
fn a_small_process_allowance_still_launches_beside_the_users_other_processes() {
    let stamp = format!(
        "{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    );
    let workspace = Workspace(std::env::temp_dir().join(format!("raiker-linux-nproc-{stamp}")));
    std::fs::create_dir(&workspace.0).unwrap();
    // More of this user's processes than the run is allowed: the limit counts
    // them all, so an absolute limit would stop bwrap from forking at all.
    let holders: Vec<_> = (0..12)
        .map(|_| Command::new("/usr/bin/sleep").arg("30").spawn().unwrap())
        .collect();
    let runner = workspace.0.join("runner");
    std::fs::copy(env!("CARGO_BIN_EXE_raiker-command-runner"), &runner).unwrap();
    let policy = serde_json::json!({
        "workspace_root": workspace.0, "cwd": workspace.0,
        "profile_name": "raiker.nproc.test", "deadline_seconds": 15, "max_processes": 8,
    });
    let policy_path = workspace.0.join("policy.json");
    std::fs::write(&policy_path, policy.to_string()).unwrap();
    let output = output_after_transient_exec_busy(
        Command::new(&runner)
            .arg("--policy")
            .arg(&policy_path)
            .arg("--")
            .args(["/usr/bin/echo", "ran"]),
    );
    for mut holder in holders {
        let _ = holder.kill();
        let _ = holder.wait();
    }
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&output.stdout).trim(), "ran");
}

#[test]
fn the_process_allowance_still_stops_a_run_that_forks_past_it() {
    let stamp = format!(
        "{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    );
    let workspace = Workspace(std::env::temp_dir().join(format!("raiker-linux-fork-{stamp}")));
    std::fs::create_dir(&workspace.0).unwrap();
    let runner = workspace.0.join("runner");
    std::fs::copy(env!("CARGO_BIN_EXE_raiker-command-runner"), &runner).unwrap();
    let policy = serde_json::json!({
        "workspace_root": workspace.0, "cwd": workspace.0,
        "profile_name": "raiker.fork.test", "deadline_seconds": 15, "max_processes": 6,
    });
    let policy_path = workspace.0.join("policy.json");
    std::fs::write(&policy_path, policy.to_string()).unwrap();
    let script = "import subprocess\nstarted = 0\nfor _ in range(20):\n    try:\n        subprocess.Popen(['/usr/bin/sleep', '3'])\n        started += 1\n    except OSError:\n        pass\nprint(started)\n";
    let output = output_after_transient_exec_busy(
        Command::new(&runner)
            .arg("--policy")
            .arg(&policy_path)
            .arg("--")
            .args(["/usr/bin/python3", "-c", script]),
    );
    let started: u32 = String::from_utf8_lossy(&output.stdout)
        .trim()
        .parse()
        .unwrap_or_else(|_| panic!("{}", String::from_utf8_lossy(&output.stderr)));
    assert!(started < 20, "the run started all {started} children");
}

#[test]
fn a_cgroup_scope_bounds_the_memory_of_the_whole_run_not_each_process() {
    let runtime = format!("/run/user/{}/bus", unsafe { libc::getuid() });
    if !std::path::Path::new(&runtime).exists()
        || !std::path::Path::new("/usr/bin/systemd-run").exists()
    {
        eprintln!("no user manager: the rlimits are the bounds on this host");
        return;
    }
    let stamp = format!(
        "{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    );
    let workspace = Workspace(std::env::temp_dir().join(format!("raiker-linux-cgroup-{stamp}")));
    std::fs::create_dir(&workspace.0).unwrap();
    let runner = workspace.0.join("runner");
    std::fs::copy(env!("CARGO_BIN_EXE_raiker-command-runner"), &runner).unwrap();
    // Three children, each holding 160 MB at once: under any one process's
    // limit, over a 320 MB limit for the run.
    let script = "import subprocess, sys\nchild = \"import time; b = b'x' * (160 << 20); time.sleep(3)\"\nprocs = [subprocess.Popen([sys.executable, '-c', child]) for _ in range(3)]\nprint(sum(p.wait() == 0 for p in procs))\n";
    let run = |memory: u64| {
        let policy = serde_json::json!({
            "workspace_root": workspace.0, "cwd": workspace.0,
            "profile_name": "raiker.cgroup.test", "deadline_seconds": 30,
            "max_processes": 16, "max_memory_bytes": memory,
        });
        let policy_path = workspace.0.join("policy.json");
        std::fs::write(&policy_path, policy.to_string()).unwrap();
        let output = output_after_transient_exec_busy(
            Command::new(&runner)
                .arg("--policy")
                .arg(&policy_path)
                .arg("--")
                .args(["/usr/bin/python3", "-c", script]),
        );
        String::from_utf8_lossy(&output.stdout)
            .trim()
            .parse::<u32>()
            .unwrap_or(0)
    };
    assert_eq!(run(2 << 30), 3, "control arm: three children fit in 2 GB");
    assert!(
        run(320 << 20) < 3,
        "the run held more memory than its limit"
    );
}
