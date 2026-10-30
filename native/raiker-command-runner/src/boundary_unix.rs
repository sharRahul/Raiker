//! The Linux and macOS boundaries.
//!
//! Neither platform needs a bespoke launcher: both ship a kernel-backed sandbox
//! that takes a policy and an argv list. What this module owns is generating
//! that policy from the same launch contract Windows uses, **measuring** whether
//! the mechanism actually works on this host, and refusing rather than degrading
//! when it does not.
//!
//! * **Linux** — `bubblewrap`. `--unshare-net` removes the network namespace, so
//!   egress is denied by the kernel rather than by a rule. bwrap builds an empty
//!   root, so the system paths a dynamic loader needs are bound read-only
//!   explicitly; without them nothing execs at all. `.git` is bound read-only
//!   and `.raiker` is covered by a tmpfs, so the command sees an empty directory
//!   instead of Raiker's own state.
//! * **macOS** — `sandbox-exec` with a generated profile: deny by default,
//!   `(deny network*)`, reads allowed where the loader needs them, writes only
//!   under the workspace, `.raiker` denied outright and `.git` read-only.
//!
//! Process-tree containment differs, and the difference is reported rather than
//! smoothed over. On Linux `--unshare-pid` makes bwrap pid 1 of the namespace,
//! so every descendant dies with it; the runner sits outside the namespace and
//! kills bwrap. On macOS there is no equivalent — a child that calls `setsid()`
//! leaves the process group and survives — so the probe's descendant
//! observation reports `unenforced` there, and `process_tree_stop` is false.

use crate::policy::{LaunchPolicy, NetworkPolicy};
use crate::selftest::{self, SelfTest};
use serde_json::{Value, json};
use std::path::{Path, PathBuf};
use std::process::Command;

/// Nothing to revoke: neither bubblewrap nor Seatbelt writes anything durable
/// outside the process. The Windows boundary needs this because its filesystem
/// grant is an ACE on the owner's repository; these two carry their policy in
/// the launch itself.
pub fn revoke_workspace_grant(_workspace: &Path) -> Result<(), String> {
    Ok(())
}

/// Measure what this host actually enforces, against the real workspace.
///
/// The presence of `bwrap` on `PATH` proves nothing: `--unshare-user` fails
/// outright where unprivileged user namespaces are restricted, which is the
/// default on several current distributions. So the probe launches a child
/// through the real boundary and reads back what it could do.
pub fn probe(workspace: &Path) -> Value {
    let (mechanism, tool) = mechanism();
    let Ok(workspace) = workspace.canonicalize() else {
        return unavailable("native_sandbox_workspace_unreadable");
    };
    if which(tool).is_none() {
        return unavailable("native_sandbox_artifact_missing");
    }
    let Ok(current) = std::env::current_exe() else {
        return unavailable("native_sandbox_runner_unreadable");
    };
    let nonce = selftest::probe_nonce();
    let parent = workspace.join(".raiker");
    if std::fs::create_dir_all(&parent).is_err() {
        return unavailable("native_sandbox_probe_storage_unavailable");
    }
    let scratch = parent.join(&nonce);
    if std::fs::create_dir(&scratch).is_err() {
        return unavailable("native_sandbox_probe_storage_unavailable");
    }
    let masked = scratch.join("state");
    if std::fs::write(&masked, b"raiker-probe-state").is_err() {
        let _ = std::fs::remove_dir(&scratch);
        return unavailable("native_sandbox_probe_storage_unavailable");
    }

    let test = SelfTest {
        nonce: nonce.clone(),
        inside_path: workspace.join(format!(".{nonce}-inside.tmp")),
        outside_paths: outside_targets(&workspace, &nonce),
        masked_read_path: masked.clone(),
        connect_address: probe_destination(),
        // macOS has no verified descendant reaper yet; starting a detached
        // probe child there would leave it running after every status check.
        spawn_grandchild: cfg!(target_os = "linux"),
        hold_for_probe: cfg!(target_os = "linux"),
    };
    let outside = selftest::attempt(&test);
    if test.hold_for_probe {
        // The host control must not be mistaken for a sandbox escape.
        selftest::remove_probe_writes(&test);
    }

    let policy = LaunchPolicy {
        workspace_root: workspace.clone(),
        cwd: workspace.clone(),
        deny_paths: vec![".raiker".to_owned()],
        readonly_paths: vec![".git".to_owned()],
        network: NetworkPolicy::Denied,
        pty: false,
        max_processes: 32,
        max_memory_bytes: 1024 * 1024 * 1024,
        deadline_seconds: 60,
        max_cpu_seconds: 60,
        profile_name: format!("raiker.probe.{}", std::process::id()),
    };
    let argv = vec![
        current.to_string_lossy().into_owned(),
        "--selftest".to_owned(),
        test.to_value().to_string(),
    ];
    let arguments = match boundary_arguments(&policy, &argv) {
        Ok(value) => value,
        Err(reason) => {
            let _ = std::fs::remove_file(&masked);
            let _ = std::fs::remove_dir(&scratch);
            selftest::remove_probe_writes(&test);
            return unavailable(&reason);
        }
    };
    #[cfg(target_os = "linux")]
    let measured = capture_linux(
        &which(tool).expect("probed above"),
        &arguments,
        &test,
        &outside,
    );
    #[cfg(not(target_os = "linux"))]
    let measured = Command::new(which(tool).expect("probed above"))
        .args(arguments)
        .output()
        .ok()
        .and_then(|output| serde_json::from_slice::<Value>(&output.stdout).ok())
        .map(|inside| (inside, "indeterminate", None));
    let _ = std::fs::remove_file(&masked);
    let _ = std::fs::remove_dir(&scratch);
    selftest::remove_probe_writes(&test);
    let Some((inside, descendant, host_escape)) = measured else {
        return unavailable("native_sandbox_probe_no_output");
    };

    // A marker file does not prove that the descendant started or terminated.
    // Cleanup is best effort; the verdict remains indeterminate until the
    // probe observes the actual descendant process through its lifecycle.
    let marker = test.inside_path.with_extension("grandchild");
    let _ = std::fs::remove_file(&marker);
    let relay = inside.get("nonce").and_then(Value::as_str) == Some(test.nonce.as_str());
    let inside_write = allowed(&inside, "inside_write");
    let escape = host_escape.unwrap_or_else(|| folded_escape(&inside, &outside));
    let masked_read = selftest::verdict(
        allowed(&inside, "masked_read"),
        allowed(&outside, "masked_read"),
    );
    let network = selftest::verdict(reached(&inside), reached(&outside));
    let seccomp = seccomp_verdict(&inside, &outside);

    json!({
        "platform": platform(),
        "boundary": mechanism,
        // The broker still passes the original project as the workspace.
        // A verified OS boundary is not a disposable project snapshot.
        "available": false,
        "reason": if relay && inside_write && escape == "enforced"
            && masked_read == "enforced" && network == "enforced" && descendant == "enforced"
            && (!cfg!(target_os = "linux") || seccomp == "enforced") {
            "native_disposable_workspace_required"
        } else {
            "native_sandbox_not_enforced"
        },
        "network": network,
        "process_tree_stop": descendant == "enforced" && relay,
        "pty": false,
        "concurrent_runs": false,
        "observations": {
            "relay": if relay { "enforced" } else { "unenforced" },
            "workspace_write": if inside_write { "enforced" } else { "unenforced" },
            "escape_write": escape,
            "masked_read": masked_read,
            "egress": network,
            "seccomp": seccomp,
            "descendant_reaped": if relay { descendant } else { "indeterminate" },
        },
        "connect_destination": test.connect_address,
    })
}

#[cfg(target_os = "linux")]
fn capture_linux(
    tool: &str,
    arguments: &[String],
    test: &SelfTest,
    outside: &Value,
) -> Option<(Value, &'static str, Option<&'static str>)> {
    use std::io::{BufRead, BufReader};
    use std::os::fd::AsRawFd;
    use std::process::Stdio;

    let mut arguments = arguments.to_vec();
    let filter = linux_filter(&mut arguments).ok()?;
    let mut command = Command::new(tool);
    command
        .args(arguments)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null());
    inherit_linux_filter(&mut command, &filter);
    let mut child = command.spawn().ok()?;
    drop(filter);
    let stdout = child.stdout.take()?;
    let (send, receive) = std::sync::mpsc::channel();
    std::thread::spawn(move || {
        let mut line = String::new();
        let _ = BufReader::new(stdout).read_line(&mut line);
        let _ = send.send(line);
    });
    let inside = receive
        .recv_timeout(std::time::Duration::from_secs(30))
        .ok()
        .and_then(|line| serde_json::from_str::<Value>(&line).ok());
    let handle = inside
        .as_ref()
        .and_then(|value| u32::try_from(value.get("descendant_pid")?.as_u64()?).ok())
        .and_then(|pid| crate::lifecycle_linux::find_live_descendant(child.id(), pid));
    let escape = host_escape_verdict(test, outside);
    // Test actual cancellation of the supervisor; keep the self-test parent
    // blocked until that point so the observed descendant is still its child.
    let _ = child.kill();
    drop(child.stdin.take());
    let _ = child.wait();
    let verdict = match handle {
        Some(handle) if crate::lifecycle_linux::exited(&handle, 5_000) => "enforced",
        Some(handle) => {
            // Clean up the trusted test child even when containment failed.
            unsafe {
                libc::syscall(
                    libc::SYS_pidfd_send_signal,
                    handle.as_raw_fd(),
                    libc::SIGKILL,
                    0,
                    0,
                )
            };
            "unenforced"
        }
        None => "indeterminate",
    };
    inside.map(|value| (value, verdict, Some(escape)))
}

#[cfg(target_os = "linux")]
fn host_escape_verdict(test: &SelfTest, outside: &Value) -> &'static str {
    let control = outside
        .get("outside_writes")
        .and_then(Value::as_array)
        .is_some_and(|entries| {
            entries
                .iter()
                .any(|entry| entry.get("allowed").and_then(Value::as_bool) == Some(true))
        });
    let mut uncertain = false;
    for path in &test.outside_paths {
        match std::fs::read(path) {
            Ok(bytes) if bytes == test.nonce.as_bytes() => return "unenforced",
            Ok(_) => uncertain = true,
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => {}
            Err(_) => uncertain = true,
        }
    }
    if control && !uncertain {
        "enforced"
    } else {
        "indeterminate"
    }
}

pub fn launch(policy: &LaunchPolicy, argv: &[String]) -> Result<i32, String> {
    if policy.pty {
        return Err("native_sandbox_pty_unsupported".into());
    }
    let (_, tool) = mechanism();
    let deadline = std::time::Instant::now()
        .checked_add(std::time::Duration::from_secs(policy.deadline_seconds))
        .ok_or("native_sandbox_deadline_invalid")?;
    let executable = which(tool).ok_or("native_sandbox_artifact_missing")?;
    let arguments = boundary_arguments(policy, argv)?;
    #[cfg(target_os = "linux")]
    let mut arguments = arguments;
    #[cfg(target_os = "linux")]
    let filter = linux_filter(&mut arguments)?;
    let mut command = Command::new(executable);
    command.args(arguments);
    #[cfg(target_os = "linux")]
    inherit_linux_filter(&mut command, &filter);
    bound_child(&mut command, policy);
    let mut child = command.spawn().map_err(|error| {
        format!(
            "native_sandbox_launch_failed:{}",
            error.raw_os_error().unwrap_or(0)
        )
    })?;
    #[cfg(target_os = "linux")]
    drop(filter);

    // Keep the child unreaped until the deadline decision. A detached watchdog
    // using only its numeric PID could otherwise target a reused PID after an
    // early exit. Polling and termination live in the same owner thread.
    let pid = child.id() as i32;
    loop {
        match child.try_wait() {
            Ok(Some(status)) => return Ok(status.code().unwrap_or(1)),
            Ok(None) => {}
            // A wait error can mean the child was already reaped elsewhere.
            // Its numeric PID is no longer a reliable target in that case.
            Err(_) => return Err("native_sandbox_wait_failed".into()),
        }
        let remaining = deadline.saturating_duration_since(std::time::Instant::now());
        if remaining.is_zero() {
            unsafe { libc::kill(-pid, libc::SIGKILL) };
            unsafe { libc::kill(pid, libc::SIGKILL) };
            let status = child
                .wait()
                .map_err(|_| "native_sandbox_launch_failed".to_owned())?;
            return Ok(status.code().unwrap_or(1));
        }
        std::thread::sleep(remaining.min(std::time::Duration::from_millis(20)));
    }
}

#[cfg(target_os = "linux")]
fn linux_filter(arguments: &mut Vec<String>) -> Result<std::fs::File, String> {
    use std::os::fd::AsRawFd;
    let filter = crate::seccomp_linux::filter()
        .map_err(|_| "native_sandbox_seccomp_unavailable".to_owned())?;
    let position = arguments
        .iter()
        .position(|arg| arg == "--")
        .ok_or("native_sandbox_arguments_invalid")?;
    arguments.splice(
        position..position,
        ["--seccomp".to_owned(), filter.as_raw_fd().to_string()],
    );
    Ok(filter)
}

#[cfg(target_os = "linux")]
fn inherit_linux_filter(command: &mut Command, filter: &std::fs::File) {
    use std::os::fd::AsRawFd;
    use std::os::unix::process::CommandExt;
    let fd = filter.as_raw_fd();
    unsafe {
        command.pre_exec(move || {
            if libc::fcntl(fd, libc::F_SETFD, 0) < 0 {
                return Err(std::io::Error::last_os_error());
            }
            Ok(())
        });
    }
}

/// Everything the kernel can be asked for before `exec`.
///
/// `RLIMIT_NPROC` and `RLIMIT_AS` are the same bounds the Windows Job Object
/// carries, applied by the mechanism this platform has. Without them the launch
/// contract's process and memory caps would be Windows-only fields that every
/// other platform quietly ignored.
///
/// `PR_SET_PDEATHSIG` is how the runner dies with Raiker on Linux: the kernel
/// reaps it, with no pid to watch and nothing to poll. macOS has no equivalent,
/// which is why the design says plainly that a killed Raiker can leave a
/// command running there until its deadline.
fn bound_child(command: &mut Command, policy: &LaunchPolicy) {
    use std::os::unix::process::CommandExt;
    let processes = policy.max_processes as libc::rlim_t;
    let memory = policy.max_memory_bytes as libc::rlim_t;
    let cpu = policy.max_cpu_seconds as libc::rlim_t;
    #[cfg(target_os = "linux")]
    let expected_parent = std::process::id() as libc::pid_t;
    unsafe {
        command.pre_exec(move || {
            let apply_limit = |resource, requested| -> std::io::Result<()> {
                let mut existing: libc::rlimit = std::mem::zeroed();
                if libc::getrlimit(resource, &mut existing) != 0 {
                    return Err(std::io::Error::last_os_error());
                }
                let limit = narrower_limit(&existing, requested);
                if libc::setrlimit(resource, &limit) != 0 {
                    return Err(std::io::Error::last_os_error());
                }
                Ok(())
            };
            apply_limit(libc::RLIMIT_NPROC, processes)?;
            apply_limit(libc::RLIMIT_AS, memory)?;
            apply_limit(libc::RLIMIT_CPU, cpu)?;
            #[cfg(target_os = "linux")]
            if libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGKILL) != 0 {
                return Err(std::io::Error::last_os_error());
            }
            #[cfg(target_os = "linux")]
            if libc::getppid() != expected_parent {
                return Err(std::io::Error::other("runner_parent_exited"));
            }
            Ok(())
        });
    }
}

fn narrower_limit(existing: &libc::rlimit, requested: libc::rlim_t) -> libc::rlimit {
    libc::rlimit {
        rlim_cur: existing.rlim_cur.min(requested),
        rlim_max: existing.rlim_max.min(requested),
    }
}

fn boundary_arguments(policy: &LaunchPolicy, argv: &[String]) -> Result<Vec<String>, String> {
    if cfg!(target_os = "macos") {
        macos_arguments(policy, argv)
    } else {
        linux_arguments(policy, argv)
    }
}

fn platform() -> &'static str {
    if cfg!(target_os = "macos") {
        "macos"
    } else {
        "linux"
    }
}

fn mechanism() -> (&'static str, &'static str) {
    if cfg!(target_os = "macos") {
        ("seatbelt", "sandbox-exec")
    } else {
        ("bubblewrap", "bwrap")
    }
}

fn which(tool: &str) -> Option<String> {
    let candidates: &[&str] = match tool {
        "sandbox-exec" => &["/usr/bin/sandbox-exec"],
        "bwrap" => &["/usr/bin/bwrap", "/bin/bwrap"],
        _ => return None,
    };
    candidates
        .iter()
        .find_map(|candidate| trusted_system_tool(Path::new(candidate)))
}

fn trusted_system_tool(path: &Path) -> Option<String> {
    use std::os::unix::fs::MetadataExt;

    for parent in path.parent()?.ancestors() {
        let metadata = std::fs::metadata(parent).ok()?;
        if metadata.uid() != 0 || metadata.mode() & 0o022 != 0 {
            return None;
        }
    }
    let resolved = path.canonicalize().ok()?;
    let file = std::fs::metadata(&resolved).ok()?;
    if !file.is_file() || file.mode() & 0o111 == 0 {
        return None;
    }
    for component in resolved.ancestors() {
        let metadata = std::fs::metadata(component).ok()?;
        if metadata.uid() != 0 || metadata.mode() & 0o022 != 0 {
            return None;
        }
    }
    resolved.to_str().map(str::to_owned)
}

/// The system paths a dynamic loader needs. bwrap starts from an empty root, so
/// omitting these does not produce a stricter sandbox — it produces one where
/// nothing can exec at all.
// These other trees can contain administrator or application data and are
// not necessary to start the supported system runtime. Toolchains outside
// /usr require an explicitly governed mount rather than broad host access.
const SYSTEM_READ_ONLY: [&str; 1] = ["/usr"];
const SYSTEM_LINKS: [(&str, &str); 4] = [
    ("usr/bin", "/bin"),
    ("usr/sbin", "/sbin"),
    ("usr/lib", "/lib"),
    ("usr/lib64", "/lib64"),
];

fn linux_arguments(policy: &LaunchPolicy, argv: &[String]) -> Result<Vec<String>, String> {
    if policy.network != NetworkPolicy::Denied {
        // `--share-net` alone would give the command the host's whole network.
        // Filtered egress needs the proxy to be the only reachable address,
        // which is a separate namespace build and is not claimed here.
        return Err("filtered_egress_namespace_unsupported".into());
    }
    let root = policy.workspace_root.to_string_lossy().into_owned();
    let mut arguments: Vec<String> = [
        "--unshare-user",
        "--unshare-ipc",
        "--unshare-pid",
        "--unshare-uts",
        "--unshare-cgroup",
        "--unshare-net",
        "--die-with-parent",
        "--new-session",
    ]
    .iter()
    .map(|flag| (*flag).to_owned())
    .collect();

    for path in SYSTEM_READ_ONLY {
        if Path::new(path).exists() {
            arguments.push("--ro-bind".to_owned());
            arguments.push(path.to_owned());
            arguments.push(path.to_owned());
        }
    }
    for (target, link) in SYSTEM_LINKS {
        if Path::new(link).is_symlink() || !Path::new(link).exists() {
            arguments.push("--symlink".to_owned());
            arguments.push(target.to_owned());
            arguments.push(link.to_owned());
        } else {
            arguments.push("--ro-bind".to_owned());
            arguments.push(link.to_owned());
            arguments.push(link.to_owned());
        }
    }
    arguments.push("--proc".to_owned());
    arguments.push("/proc".to_owned());
    arguments.push("--dev".to_owned());
    arguments.push("/dev".to_owned());
    arguments.push("--tmpfs".to_owned());
    arguments.push("/tmp".to_owned());

    arguments.push("--bind".to_owned());
    arguments.push(root.clone());
    arguments.push(root);
    for relative in &policy.readonly_paths {
        let path = policy.workspace_root.join(relative);
        if path.exists() {
            let text = path.to_string_lossy().into_owned();
            arguments.push("--ro-bind".to_owned());
            arguments.push(text.clone());
            arguments.push(text);
        }
    }
    for relative in &policy.deny_paths {
        arguments.push("--tmpfs".to_owned());
        arguments.push(
            policy
                .workspace_root
                .join(relative)
                .to_string_lossy()
                .into_owned(),
        );
    }
    // The per-run profile name doubles as the namespace hostname, so `ps` and a
    // core dump inside the sandbox name the run they belong to.
    arguments.push("--hostname".to_owned());
    arguments.push(sanitised_hostname(&policy.profile_name));
    arguments.push("--chdir".to_owned());
    arguments.push(policy.cwd.to_string_lossy().into_owned());
    arguments.push("--".to_owned());
    arguments.extend(argv.iter().cloned());
    Ok(arguments)
}

/// A hostname is not a free-form string: bounded length, and no separators.
fn sanitised_hostname(name: &str) -> String {
    name.chars()
        .map(|character| {
            if character.is_ascii_alphanumeric() {
                character
            } else {
                '-'
            }
        })
        .take(63)
        .collect()
}

fn macos_arguments(policy: &LaunchPolicy, argv: &[String]) -> Result<Vec<String>, String> {
    if policy.network != NetworkPolicy::Denied {
        return Err("filtered_egress_seatbelt_unsupported".into());
    }
    let mut arguments = vec!["-p".to_owned(), macos_profile(policy)?];
    arguments.extend(argv.iter().cloned());
    Ok(arguments)
}

/// Deny by default, then allow exactly what a program needs to start.
///
/// Read access is limited to the workspace and common system runtime paths.
/// This initial allowlist is not yet verified on macOS and may prevent some
/// toolchains from starting; macOS remains unavailable until real tests pass.
pub fn macos_profile(policy: &LaunchPolicy) -> Result<String, String> {
    let root = seatbelt_path(&policy.workspace_root)?;
    let mut profile = String::from("(version 1)\n(deny default)\n(deny network*)\n");
    profile.push_str("(allow process-exec* process-fork signal sysctl-read mach-lookup)\n");
    profile.push_str("(allow file-read* (subpath \"/System/Library\") (subpath \"/usr/lib\") (subpath \"/usr/bin\") (subpath \"/usr/sbin\") (subpath \"/usr/share\") (subpath \"/bin\") (subpath \"/sbin\") (subpath \"/private/var/db/dyld\") (literal \"/dev/null\") (literal \"/dev/random\") (literal \"/dev/urandom\") (literal \"/dev/zero\"))\n");
    profile.push_str(&format!("(allow file-read* (subpath \"{root}\"))\n"));
    profile.push_str(&format!("(allow file-write* (subpath \"{root}\"))\n"));
    profile.push_str("(allow file-write* (literal \"/dev/null\"))\n");
    for relative in &policy.deny_paths {
        let path = policy.workspace_root.join(relative);
        profile.push_str(&format!(
            "(deny file* (subpath \"{}\"))\n",
            seatbelt_path(&path)?
        ));
    }
    for relative in &policy.readonly_paths {
        let path = policy.workspace_root.join(relative);
        profile.push_str(&format!(
            "(deny file-write* (subpath \"{}\"))\n",
            seatbelt_path(&path)?
        ));
    }
    Ok(profile)
}

fn seatbelt_path(path: &Path) -> Result<&str, String> {
    let value = path.to_str().ok_or("native_sandbox_seatbelt_unsafe_path")?;
    if value
        .chars()
        .any(|character| character.is_control() || matches!(character, '"' | '\\'))
    {
        return Err("native_sandbox_seatbelt_unsafe_path".into());
    }
    Ok(value)
}

fn outside_targets(workspace: &Path, nonce: &str) -> Vec<PathBuf> {
    let mut targets = Vec::new();
    if let Some(parent) = workspace.parent() {
        targets.push(parent.join(format!(".{nonce}-escape.tmp")));
    }
    if let Ok(home) = std::env::var("HOME") {
        targets.push(PathBuf::from(home).join(format!(".{nonce}-escape.tmp")));
    }
    targets
}

/// The default gateway on a closed port: off this machine, so the namespace
/// governs it, but never off the local network. A product whose posture is "no
/// network by default" must not make an undisclosed outbound connection from
/// its own readiness check.
fn probe_destination() -> String {
    format!(
        "{}:9",
        default_gateway().unwrap_or_else(|| "192.168.0.1".into())
    )
}

fn default_gateway() -> Option<String> {
    let text = std::fs::read_to_string("/proc/net/route").ok()?;
    parse_default_gateway(&text)
}

fn parse_default_gateway(text: &str) -> Option<String> {
    for line in text.lines().skip(1) {
        let fields: Vec<&str> = line.split_whitespace().collect();
        if fields.len() > 2 && fields[1] == "00000000" {
            let raw = u32::from_str_radix(fields[2], 16).ok()?;
            let octets = raw.to_le_bytes();
            return Some(std::net::Ipv4Addr::from(octets).to_string());
        }
    }
    None
}

fn allowed(value: &Value, key: &str) -> bool {
    value
        .get(key)
        .and_then(|entry| entry.get("allowed"))
        .and_then(Value::as_bool)
        .unwrap_or(false)
}

fn seccomp_verdict(inside: &Value, outside: &Value) -> &'static str {
    let observation = |value: &Value, name: &str| {
        value
            .get("seccomp_control")
            .and_then(|entry| entry.get(name))
            .and_then(Value::as_bool)
            .unwrap_or(false)
    };
    let personality = selftest::verdict(
        observation(inside, "personality_allowed"),
        observation(outside, "personality_allowed"),
    );
    let unshare = selftest::verdict(
        observation(inside, "unshare_allowed"),
        observation(outside, "unshare_allowed"),
    );
    match (personality, unshare) {
        ("unenforced", _) | (_, "unenforced") => "unenforced",
        ("enforced", "enforced") => "enforced",
        _ => "indeterminate",
    }
}

fn reached(value: &Value) -> bool {
    value
        .get("connect")
        .and_then(|entry| entry.get("reached"))
        .and_then(Value::as_bool)
        .unwrap_or(false)
}

fn folded_escape(inside: &Value, outside: &Value) -> &'static str {
    let empty = Vec::new();
    let inside_list = inside
        .get("outside_writes")
        .and_then(Value::as_array)
        .unwrap_or(&empty);
    let outside_list = outside
        .get("outside_writes")
        .and_then(Value::as_array)
        .unwrap_or(&empty);
    let control = outside_list.iter().any(|entry| {
        entry
            .get("allowed")
            .and_then(Value::as_bool)
            .unwrap_or(false)
    });
    let contained = inside_list.iter().all(|entry| {
        !entry
            .get("allowed")
            .and_then(Value::as_bool)
            .unwrap_or(false)
    });
    selftest::verdict(!contained, control)
}

fn unavailable(reason: &str) -> Value {
    json!({
        "platform": platform(),
        "boundary": "none",
        "available": false,
        "reason": reason,
        "network": "indeterminate",
        "process_tree_stop": false,
        "pty": false,
        "concurrent_runs": false,
        "observations": {},
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::policy;

    #[test]
    fn linux_default_gateway_uses_little_endian_route_bytes() {
        let route = "Iface Destination Gateway Flags\neth0 00000000 0102A8C0 0003\n";
        assert_eq!(parse_default_gateway(route).as_deref(), Some("192.168.2.1"));
    }

    #[test]
    fn seccomp_requires_both_controlled_syscalls_to_be_blocked() {
        let outside =
            json!({"seccomp_control": {"personality_allowed": true, "unshare_allowed": true}});
        let partial =
            json!({"seccomp_control": {"personality_allowed": false, "unshare_allowed": true}});
        let denied =
            json!({"seccomp_control": {"personality_allowed": false, "unshare_allowed": false}});
        assert_eq!(seccomp_verdict(&partial, &outside), "unenforced");
        assert_eq!(seccomp_verdict(&denied, &outside), "enforced");
        assert_eq!(seccomp_verdict(&denied, &denied), "indeterminate");
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn host_escape_requires_a_control_and_observes_real_host_writes() {
        let root = std::env::temp_dir().join(selftest::probe_nonce());
        std::fs::create_dir(&root).unwrap();
        let target = root.join("outside");
        let test = SelfTest {
            nonce: "probe-identity".into(),
            inside_path: root.join("inside"),
            outside_paths: vec![target.clone()],
            masked_read_path: root.join("masked"),
            connect_address: "127.0.0.1:9".into(),
            spawn_grandchild: false,
            hold_for_probe: true,
        };
        let failed_control = json!({"outside_writes": [{"allowed": false}]});
        let passed_control = json!({"outside_writes": [{"allowed": true}]});
        assert_eq!(host_escape_verdict(&test, &failed_control), "indeterminate");
        assert_eq!(host_escape_verdict(&test, &passed_control), "enforced");
        std::fs::write(&target, test.nonce.as_bytes()).unwrap();
        assert_eq!(host_escape_verdict(&test, &passed_control), "unenforced");
        std::fs::write(&target, b"unrelated content").unwrap();
        assert_eq!(host_escape_verdict(&test, &passed_control), "indeterminate");
        std::fs::remove_file(target).unwrap();
        std::fs::remove_dir(root).unwrap();
    }

    fn sample() -> policy::LaunchPolicy {
        policy::parse(
            r#"{"workspace_root":"/ws","cwd":"/ws","profile_name":"raiker.cmd.test",
                "deny_paths":[".raiker"],"readonly_paths":[".git"]}"#,
        )
        .unwrap()
    }

    #[test]
    fn the_run_names_its_own_namespace() {
        let arguments = linux_arguments(&sample(), &["echo".into()]).unwrap();
        assert!(arguments.contains(&"--hostname".to_owned()));
        assert_eq!(sanitised_hostname("raiker.cmd.ab_12"), "raiker-cmd-ab-12");
        assert_eq!(sanitised_hostname(&"x".repeat(200)).len(), 63);
    }

    #[test]
    fn the_linux_boundary_binds_the_system_paths_a_loader_needs() {
        let arguments = linux_arguments(&sample(), &["echo".into(), "hi".into()]).unwrap();
        // Without these bwrap builds an empty root and nothing execs at all —
        // a "sandbox" that refuses every command is not a stricter one.
        assert!(arguments.contains(&"--proc".to_owned()));
        assert!(arguments.contains(&"--dev".to_owned()));
        assert!(
            arguments
                .windows(2)
                .any(|pair| pair[0] == "--tmpfs" && pair[1] == "/tmp")
        );
        assert!(arguments.contains(&"--unshare-net".to_owned()));
        for forbidden in ["/etc", "/opt", "/nix"] {
            assert!(
                !arguments.windows(3).any(|triple| {
                    triple[0] == "--ro-bind" && triple[1] == forbidden && triple[2] == forbidden
                }),
                "host tree must not be exposed: {forbidden}"
            );
        }
        assert_eq!(arguments.last().unwrap(), "hi");
    }

    #[test]
    fn raiker_state_is_masked_and_git_is_read_only() {
        // The read-only bind is only emitted for a path that exists — binding a
        // missing one is a bwrap error, not a stricter sandbox — so this test
        // has to give it a real directory rather than a plausible string.
        let root = std::env::temp_dir().join(format!("raiker-bwrap-{}", std::process::id()));
        std::fs::create_dir_all(root.join(".git")).expect("git dir");
        let text = format!(
            r#"{{"workspace_root":"{root}","cwd":"{root}","profile_name":"raiker.cmd.test",
                "deny_paths":[".raiker"],"readonly_paths":[".git"]}}"#,
            root = root.to_string_lossy()
        );
        let policy = policy::parse(&text).unwrap();
        let arguments = linux_arguments(&policy, &["echo".into()]).unwrap();
        let masked = root.join(".raiker").to_string_lossy().into_owned();
        let git = root.join(".git").to_string_lossy().into_owned();
        let _ = std::fs::remove_dir_all(&root);

        assert!(
            arguments
                .windows(2)
                .any(|pair| pair[0] == "--tmpfs" && pair[1] == masked)
        );
        assert!(
            arguments
                .windows(3)
                .any(|three| three[0] == "--ro-bind" && three[1] == git)
        );
    }

    #[test]
    fn a_network_grant_is_refused_rather_than_widened_to_the_host() {
        let policy = policy::parse(
            r#"{"workspace_root":"/ws","cwd":"/ws","profile_name":"raiker.cmd.test",
                "network":"proxy:127.0.0.1:9","deny_paths":[]}"#,
        )
        .unwrap();
        assert_eq!(
            linux_arguments(&policy, &["echo".into()]).unwrap_err(),
            "filtered_egress_namespace_unsupported"
        );
    }

    #[test]
    fn the_macos_profile_denies_by_default_and_protects_raiker_state() {
        let profile = macos_profile(&sample()).unwrap();
        assert!(profile.contains("(deny default)"));
        assert!(profile.contains("(deny network*)"));
        assert!(profile.contains("(deny file* (subpath \"/ws/.raiker\"))"));
        assert!(!profile.contains("(allow file-read* file-read-metadata)"));
        assert!(!profile.contains("(allow file-write* (subpath \"/private/tmp\")"));
        assert!(profile.contains("(subpath \"/System/Library\")"));
        assert!(profile.contains("(allow file-read* (subpath \"/ws\"))"));
    }

    #[test]
    fn resource_bounds_never_raise_existing_soft_or_hard_limits() {
        let existing = libc::rlimit {
            rlim_cur: 128,
            rlim_max: 256,
        };
        let bounded = narrower_limit(&existing, 4096);
        assert_eq!(bounded.rlim_cur, 128);
        assert_eq!(bounded.rlim_max, 256);
        let bounded = narrower_limit(&existing, 64);
        assert_eq!(bounded.rlim_cur, 64);
        assert_eq!(bounded.rlim_max, 64);
    }

    #[test]
    fn the_macos_profile_refuses_policy_injection_in_paths() {
        use std::os::unix::ffi::OsStringExt;

        let mut policy = sample();
        policy.workspace_root = PathBuf::from("/tmp/work\") (allow file-read*) ;");
        assert_eq!(
            macos_arguments(&policy, &["echo".into()]).unwrap_err(),
            "native_sandbox_seatbelt_unsafe_path"
        );
        let mut policy = sample();
        policy.workspace_root = PathBuf::from(std::ffi::OsString::from_vec(vec![b'/', 0xff]));
        assert_eq!(
            macos_arguments(&policy, &["echo".into()]).unwrap_err(),
            "native_sandbox_seatbelt_unsafe_path"
        );
        let mut policy = sample();
        policy.readonly_paths = vec!["folder\nname".into()];
        assert_eq!(
            macos_arguments(&policy, &["echo".into()]).unwrap_err(),
            "native_sandbox_seatbelt_unsafe_path"
        );
        let mut policy = sample();
        policy.deny_paths = vec!["folder\\name".into()];
        assert_eq!(
            macos_arguments(&policy, &["echo".into()]).unwrap_err(),
            "native_sandbox_seatbelt_unsafe_path"
        );
    }

    #[test]
    fn seatbelt_launcher_is_not_selected_from_an_untrusted_path() {
        const CHILD: &str = "RAIKER_SEATBELT_RESOLUTION_TEST";
        if std::env::var_os(CHILD).is_some() {
            assert!(which("sandbox-exec").is_none_or(|path| path == "/usr/bin/sandbox-exec"));
            return;
        }
        let directory = std::env::temp_dir().join(selftest::probe_nonce());
        std::fs::create_dir(&directory).unwrap();
        std::fs::write(directory.join("sandbox-exec"), b"untrusted").unwrap();
        let output = Command::new(std::env::current_exe().unwrap())
            .args([
                "--exact",
                "boundary::tests::seatbelt_launcher_is_not_selected_from_an_untrusted_path",
            ])
            .env(CHILD, "1")
            .env("PATH", &directory)
            .output()
            .unwrap();
        std::fs::remove_dir_all(&directory).unwrap();
        assert!(
            output.status.success(),
            "{}",
            String::from_utf8_lossy(&output.stderr)
        );
    }

    #[test]
    fn trusted_helper_refuses_a_symlink_in_a_writable_directory() {
        use std::os::unix::fs::symlink;
        let directory = std::env::temp_dir().join(selftest::probe_nonce());
        std::fs::create_dir(&directory).unwrap();
        let link = directory.join("tool");
        symlink("/usr/bin/true", &link).unwrap();
        assert!(trusted_system_tool(&link).is_none());
        std::fs::remove_dir_all(&directory).unwrap();
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn bubblewrap_launcher_is_not_selected_from_an_untrusted_path() {
        const CHILD: &str = "RAIKER_BWRAP_RESOLUTION_TEST";
        if std::env::var_os(CHILD).is_some() {
            assert!(
                which("bwrap").is_none_or(|path| path == "/usr/bin/bwrap" || path == "/bin/bwrap")
            );
            return;
        }
        let directory = std::env::temp_dir().join(selftest::probe_nonce());
        std::fs::create_dir(&directory).unwrap();
        std::fs::write(directory.join("bwrap"), b"untrusted").unwrap();
        let output = Command::new(std::env::current_exe().unwrap())
            .args([
                "--exact",
                "boundary::tests::bubblewrap_launcher_is_not_selected_from_an_untrusted_path",
            ])
            .env(CHILD, "1")
            .env("PATH", &directory)
            .output()
            .unwrap();
        std::fs::remove_dir_all(&directory).unwrap();
        assert!(
            output.status.success(),
            "{}",
            String::from_utf8_lossy(&output.stderr)
        );
    }

    #[test]
    fn the_probe_destination_is_never_loopback() {
        let destination = probe_destination();
        assert!(!destination.starts_with("127."));
        assert!(destination.ends_with(":9"));
    }
}
