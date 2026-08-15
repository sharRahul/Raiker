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
    let scratch = workspace.join(".raiker").join("command-probe");
    let _ = std::fs::create_dir_all(&scratch);
    let masked = scratch.join("state");
    let _ = std::fs::write(&masked, b"raiker-probe-state");

    let test = SelfTest {
        nonce: format!("raiker-probe-{}", std::process::id()),
        inside_path: workspace.join(".raiker-probe-inside.tmp"),
        outside_paths: outside_targets(&workspace),
        masked_read_path: masked.clone(),
        connect_address: probe_destination(),
        spawn_grandchild: true,
    };
    let outside = selftest::attempt(&test);

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
        profile_name: format!("raiker.probe.{}", std::process::id()),
    };
    let argv = vec![
        current.to_string_lossy().into_owned(),
        "--selftest".to_owned(),
        test.to_value().to_string(),
    ];
    let arguments = match boundary_arguments(&policy, &argv) {
        Ok(value) => value,
        Err(reason) => return unavailable(&reason),
    };
    let output = Command::new(which(tool).expect("probed above"))
        .args(arguments)
        .output();
    let _ = std::fs::remove_file(&masked);
    let _ = std::fs::remove_dir_all(&scratch);
    let Ok(output) = output else {
        return unavailable("native_sandbox_launch_failed");
    };
    let text = String::from_utf8_lossy(&output.stdout);
    let Ok(inside) = serde_json::from_str::<Value>(text.trim()) else {
        return unavailable("native_sandbox_probe_no_output");
    };

    // The namespace is torn down when bwrap exits, so a descendant that
    // survived would have had to escape it. On macOS a `setsid()` grandchild
    // does exactly that, which is what this observation is here to expose.
    let marker = test.inside_path.with_extension("grandchild");
    let descendant = !marker.exists() || std::fs::remove_file(&marker).is_ok();
    let relay = inside.get("nonce").and_then(Value::as_str) == Some(test.nonce.as_str());
    let inside_write = allowed(&inside, "inside_write");
    let escape = folded_escape(&inside, &outside);
    let masked_read = selftest::verdict(
        allowed(&inside, "masked_read"),
        allowed(&outside, "masked_read"),
    );
    let network = selftest::verdict(reached(&inside), reached(&outside));
    let descendant_enforced = descendant && !cfg!(target_os = "macos");

    json!({
        "platform": platform(),
        "boundary": mechanism,
        "available": relay && inside_write && escape == "enforced",
        "reason": Value::Null,
        "network": network,
        "process_tree_stop": descendant_enforced,
        "pty": false,
        "concurrent_runs": false,
        "observations": {
            "relay": if relay { "enforced" } else { "unenforced" },
            "workspace_write": if inside_write { "enforced" } else { "unenforced" },
            "escape_write": escape,
            "masked_read": masked_read,
            "egress": network,
            "descendant_reaped": if descendant_enforced { "enforced" } else { "unenforced" },
        },
        "connect_destination": test.connect_address,
    })
}

pub fn launch(policy: &LaunchPolicy, argv: &[String]) -> Result<i32, String> {
    if policy.pty {
        return Err("native_sandbox_pty_unsupported".into());
    }
    let (_, tool) = mechanism();
    let executable = which(tool).ok_or("native_sandbox_artifact_missing")?;
    let arguments = boundary_arguments(policy, argv)?;
    let mut command = Command::new(executable);
    command.args(arguments);
    bound_child(&mut command, policy);
    let mut child = command
        .spawn()
        .map_err(|_| "native_sandbox_launch_failed".to_owned())?;

    // The boundary's own deadline. Raiker keeps an outer timer, but a wedged
    // relay must not be able to leave a command running past its bound — and on
    // macOS, where there is no parent-death signal, this is the only bound.
    let pid = child.id() as i32;
    let deadline = policy.deadline_seconds;
    std::thread::spawn(move || {
        std::thread::sleep(std::time::Duration::from_secs(deadline));
        // Negative pid: the whole process group, not just the launcher.
        unsafe { libc::kill(-pid, libc::SIGKILL) };
        unsafe { libc::kill(pid, libc::SIGKILL) };
    });

    let status = child
        .wait()
        .map_err(|_| "native_sandbox_launch_failed".to_owned())?;
    Ok(status.code().unwrap_or(1))
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
    unsafe {
        command.pre_exec(move || {
            let procs = libc::rlimit {
                rlim_cur: processes,
                rlim_max: processes,
            };
            libc::setrlimit(libc::RLIMIT_NPROC, &procs);
            let address_space = libc::rlimit {
                rlim_cur: memory,
                rlim_max: memory,
            };
            libc::setrlimit(libc::RLIMIT_AS, &address_space);
            #[cfg(target_os = "linux")]
            libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGKILL);
            Ok(())
        });
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
    std::env::var("PATH").ok().and_then(|paths| {
        paths.split(':').find_map(|directory| {
            let candidate = Path::new(directory).join(tool);
            candidate
                .is_file()
                .then(|| candidate.to_string_lossy().into_owned())
        })
    })
}

/// The system paths a dynamic loader needs. bwrap starts from an empty root, so
/// omitting these does not produce a stricter sandbox — it produces one where
/// nothing can exec at all.
const SYSTEM_READ_ONLY: [&str; 4] = ["/usr", "/etc", "/opt", "/nix"];
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
    let mut arguments = vec!["-p".to_owned(), macos_profile(policy)];
    arguments.extend(argv.iter().cloned());
    Ok(arguments)
}

/// Deny by default, then allow exactly what a program needs to start.
///
/// `(allow file-read*)` is broad on purpose: the write boundary is what this
/// sandbox enforces, and a read allow-list narrow enough to be interesting is
/// also narrow enough to stop `dyld` resolving a framework. `.raiker` is denied
/// for reads as well, because that is the invariant.
pub fn macos_profile(policy: &LaunchPolicy) -> String {
    let root = policy.workspace_root.to_string_lossy();
    let mut profile = String::from("(version 1)\n(deny default)\n(deny network*)\n");
    profile.push_str("(allow process-exec* process-fork signal sysctl-read mach-lookup)\n");
    profile.push_str("(allow file-read* file-read-metadata)\n");
    profile.push_str(&format!("(allow file-write* (subpath \"{root}\"))\n"));
    profile.push_str("(allow file-write* (subpath \"/private/tmp\") (subpath \"/dev\"))\n");
    for relative in &policy.deny_paths {
        let path = policy.workspace_root.join(relative);
        profile.push_str(&format!(
            "(deny file* (subpath \"{}\"))\n",
            path.to_string_lossy()
        ));
    }
    for relative in &policy.readonly_paths {
        let path = policy.workspace_root.join(relative);
        profile.push_str(&format!(
            "(deny file-write* (subpath \"{}\"))\n",
            path.to_string_lossy()
        ));
    }
    profile
}

fn outside_targets(workspace: &Path) -> Vec<PathBuf> {
    let mut targets = Vec::new();
    if let Some(parent) = workspace.parent() {
        targets.push(parent.join(".raiker-probe-escape.tmp"));
    }
    if let Ok(home) = std::env::var("HOME") {
        targets.push(PathBuf::from(home).join(".raiker-probe-escape.tmp"));
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
    for line in text.lines().skip(1) {
        let fields: Vec<&str> = line.split_whitespace().collect();
        if fields.len() > 2 && fields[1] == "00000000" {
            let raw = u32::from_str_radix(fields[2], 16).ok()?;
            let octets = raw.to_le_bytes();
            return Some(format!(
                "{}.{}.{}.{}",
                octets[3], octets[2], octets[1], octets[0]
            ));
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
        let profile = macos_profile(&sample());
        assert!(profile.contains("(deny default)"));
        assert!(profile.contains("(deny network*)"));
        assert!(profile.contains("(deny file* (subpath \"/ws/.raiker\"))"));
        // The loader has to be able to read, or nothing starts.
        assert!(profile.contains("(allow file-read*"));
    }

    #[test]
    fn the_probe_destination_is_never_loopback() {
        let destination = probe_destination();
        assert!(!destination.starts_with("127."));
        assert!(destination.ends_with(":9"));
    }
}
