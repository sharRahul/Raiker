#![cfg(windows)]
//! Unqualified account mechanism fixtures, compiled ONLY in the Rust test binary.
//! These deliberately bypass the production refusal to retain measured subset
//! evidence, including the hostile descendant leak. They do not qualify execution.
//! The restricted-account mechanisms, measured on a host where the owner ran
//! `--setup-account`. Skipped elsewhere: without the account there is nothing
//! to measure, and these tests must not create one themselves.

use std::path::PathBuf;
use std::process::Command;

// These cases mutate one machine-wide account pool and inspect its grants.
// Keep cases apart; the overlap case still launches concurrent runs itself.
static ACCOUNT_TEST: std::sync::Mutex<()> = std::sync::Mutex::new(());

fn runner_command() -> Command {
    let mut command = Command::new(std::env::current_exe().unwrap());
    command.args([
        "--exact",
        "boundary::account::diagnostic_tests::diagnostic_child",
        "--nocapture",
        "--",
    ]);
    command.env("RAIKER_ACCOUNT_TEST_DIAGNOSTIC", "1");
    command
}

#[test]
fn diagnostic_child() {
    if std::env::var_os("RAIKER_ACCOUNT_TEST_DIAGNOSTIC").is_none() {
        return;
    }
    let arguments: Vec<String> = std::env::args()
        .skip_while(|arg| arg != "--")
        .skip(1)
        .collect();
    let code = match crate::dispatch(&arguments) {
        Ok(code) => code,
        Err(reason) => {
            eprintln!("{reason}");
            1
        }
    };
    std::process::exit(code);
}

fn json_output(output: &[u8]) -> Option<serde_json::Value> {
    String::from_utf8_lossy(output)
        .lines()
        .find_map(|line| serde_json::from_str(line).ok())
}

fn configured() -> Option<PathBuf> {
    let output = runner_command().arg("--account-status").output().ok()?;
    let status: serde_json::Value = json_output(&output.stdout)?;
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
    let output = runner_command().arg("--account-status").output().unwrap();
    let status: serde_json::Value = json_output(&output.stdout).unwrap();
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
    runner_command()
        .arg("--policy")
        .arg(&policy)
        .arg("--")
        .args(argv)
        .output()
        .unwrap()
}

#[test]
fn ordinary_toolchains_start_as_the_account_inside_the_copy() {
    let _account_test = ACCOUNT_TEST.lock().unwrap();
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
    let _account_test = ACCOUNT_TEST.lock().unwrap();
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
    let refused = runner_command()
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
    let _account_test = ACCOUNT_TEST.lock().unwrap();
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

#[test]
fn a_grant_left_on_another_copy_is_revoked_before_a_run_starts() {
    let _account_test = ACCOUNT_TEST.lock().unwrap();
    let Some(base) = configured() else { return };
    let mine = copy_under(&base, "fresh");
    let stale = copy_under(&base, "stale");
    // What a crashed run would leave behind: the account's entry on its copy.
    let planted = Command::new("icacls")
        .arg(&stale.0)
        .args(["/grant", "RaikerSandbox:(OI)(CI)(M)"])
        .output()
        .unwrap();
    assert!(
        planted.status.success(),
        "failed to construct the stale grant"
    );
    let cmd = std::env::var("ComSpec").unwrap_or_else(|_| r"C:\Windows\System32\cmd.exe".into());
    let target = stale.0.join("planted.txt").to_string_lossy().into_owned();
    let run = run(&mine, &[&cmd, "/c", &format!("echo x> \"{target}\"")]);
    assert!(
        !stale.0.join("planted.txt").exists(),
        "a stale grant let a run write another copy"
    );
    let acl = Command::new("icacls").arg(&stale.0).output().unwrap();
    assert!(
        !String::from_utf8_lossy(&acl.stdout).contains("RaikerSandbox:"),
        "the stale grant survived: {}",
        String::from_utf8_lossy(&acl.stdout)
    );
    let _ = run;
}

#[test]
fn the_unqualified_account_leaks_explicit_descendants_and_requires_production_refusal() {
    assert_eq!(
        super::require_task_isolation().unwrap_err(),
        "native_sandbox_account_profile_isolation_unavailable"
    );
    let _account_test = ACCOUNT_TEST.lock().unwrap();
    let Some(base) = configured() else { return };
    let first = copy_under(&base, "descendant-first");
    let second = copy_under(&base, "descendant-second");
    let powershell = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe";
    let planted = run(
        &first,
        &[
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "New-Item retained -ItemType Directory | Out-Null; Set-Content retained/secret.txt cross-copy-secret; & C:/Windows/System32/icacls.exe retained /grant ($env:USERNAME + ':(OI)(CI)(F)'); exit $LASTEXITCODE",
        ],
    );
    assert!(
        planted.status.success(),
        "failed to construct descendant grant: {}",
        String::from_utf8_lossy(&planted.stderr)
    );
    let target = first.0.join("retained").join("secret.txt");
    let attempted = run(
        &second,
        &[
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            &format!("Get-Content -LiteralPath '{}'", target.display()),
        ],
    );
    assert!(
        String::from_utf8_lossy(&attempted.stdout).contains("cross-copy-secret"),
        "the known unsafe descendant case changed; reassess the production refusal"
    );
}

fn spawn(copy: &Copy, label: &str, deadline: u64, argv: &[&str]) -> std::process::Child {
    let policy = std::env::temp_dir().join(format!(
        "raiker-account-{label}-{}.json",
        std::process::id()
    ));
    std::fs::write(
        &policy,
        serde_json::json!({
            "workspace_root": copy.0, "cwd": copy.0,
            "profile_name": format!("raiker.account.{label}"), "deadline_seconds": deadline
        })
        .to_string(),
    )
    .unwrap();
    runner_command()
        .arg("--policy")
        .arg(&policy)
        .arg("--")
        .args(argv)
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .unwrap()
}

#[test]
fn runs_in_two_copies_overlap_on_different_accounts_and_stay_apart() {
    let _account_test = ACCOUNT_TEST.lock().unwrap();
    let Some(base) = configured() else { return };
    let ping = r"C:\Windows\System32\PING.EXE";
    let cmd = r"C:\Windows\System32\cmd.exe";
    let first = copy_under(&base, "overlap-a");
    let second = copy_under(&base, "overlap-b");
    std::fs::write(first.0.join("secret.txt"), "first copy").unwrap();
    // Long enough to outlast two first logons on a fresh host (each new pool
    // account builds its profile then); stopped once the checks are done.
    let mut long = spawn(&first, "long", 300, &[ping, "-n", "240", "127.0.0.1"]);
    std::thread::sleep(std::time::Duration::from_secs(2));

    // Same copy: the same account, beside the long run.
    let same = spawn(&first, "same", 30, &[cmd, "/c", "whoami"])
        .wait_with_output()
        .unwrap();
    assert!(
        same.status.success(),
        "{}",
        String::from_utf8_lossy(&same.stderr)
    );
    assert!(
        long.try_wait().unwrap().is_none(),
        "the same-copy run waited for the long run instead of overlapping it"
    );

    // Another copy: another pool account, also beside the long run, and it
    // cannot read the first copy, whose account is not its own.
    let target = first.0.join("secret.txt");
    let other = spawn(
        &second,
        "other",
        30,
        &[
            cmd,
            "/c",
            &format!("whoami & type \"{}\"", target.display()),
        ],
    )
    .wait_with_output()
    .unwrap();
    let other_out = String::from_utf8_lossy(&other.stdout).to_lowercase();
    let same_out = String::from_utf8_lossy(&same.stdout).to_lowercase();
    assert!(
        long.try_wait().unwrap().is_none(),
        "the other copy waited for the long run instead of overlapping it"
    );
    assert!(same_out.contains("raikersandbox"), "{same_out}");
    assert!(other_out.contains("raikersandbox"), "{other_out}");
    assert_ne!(
        same_out
            .lines()
            .find(|line| line.contains("raikersandbox"))
            .unwrap(),
        other_out
            .lines()
            .find(|line| line.contains("raikersandbox"))
            .unwrap()
    );
    assert!(!other_out.contains("first copy"), "{other_out}");
    // Stopping the runner closes its kill-on-close job, ending the anchor.
    long.kill().unwrap();
    let _ = long.wait();
}

fn run_limited(copy: &Copy, limits: serde_json::Value, argv: &[&str]) -> std::process::Output {
    let policy = copy.0.join("policy.json");
    let mut document = serde_json::json!({
        "workspace_root": copy.0, "cwd": copy.0,
        "profile_name": "raiker.account.limits", "deadline_seconds": 60
    });
    for (key, value) in limits.as_object().unwrap() {
        document[key] = value.clone();
    }
    std::fs::write(&policy, document.to_string()).unwrap();
    runner_command()
        .arg("--policy")
        .arg(&policy)
        .arg("--")
        .args(argv)
        .output()
        .unwrap()
}

#[test]
fn the_job_memory_limit_stops_an_allocation_past_it_and_not_one_inside_it() {
    let _account_test = ACCOUNT_TEST.lock().unwrap();
    let Some(base) = configured() else { return };
    let copy = copy_under(&base, "memory");
    let powershell = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe";
    let allocate = [
        powershell,
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        "$ErrorActionPreference = 'Stop'; $a = New-Object byte[] (768MB); [Array]::Clear($a, 0, $a.Length); 'allocated'",
    ];
    // Control arm: the same allocation inside a larger limit succeeds.
    let roomy = run_limited(
        &copy,
        serde_json::json!({"max_memory_bytes": 2u64 << 30}),
        &allocate,
    );
    assert!(
        String::from_utf8_lossy(&roomy.stdout).contains("allocated"),
        "control arm failed: {}",
        String::from_utf8_lossy(&roomy.stderr)
    );
    let tight = run_limited(
        &copy,
        serde_json::json!({"max_memory_bytes": 384u64 << 20}),
        &allocate,
    );
    assert!(
        !String::from_utf8_lossy(&tight.stdout).contains("allocated"),
        "an allocation past the job's memory limit succeeded"
    );
}

#[test]
fn the_job_process_limit_stops_a_child_past_it_and_not_one_inside_it() {
    let _account_test = ACCOUNT_TEST.lock().unwrap();
    let Some(base) = configured() else { return };
    let copy = copy_under(&base, "processes");
    let cmd = r"C:\Windows\System32\cmd.exe";
    let child = [
        cmd,
        "/c",
        r"C:\Windows\System32\whoami.exe && echo child-ran",
    ];
    let roomy = run_limited(&copy, serde_json::json!({"max_processes": 8}), &child);
    assert!(
        String::from_utf8_lossy(&roomy.stdout).contains("child-ran"),
        "control arm failed: {}",
        String::from_utf8_lossy(&roomy.stderr)
    );
    // One process: `cmd` itself. Its child cannot start.
    let tight = run_limited(&copy, serde_json::json!({"max_processes": 1}), &child);
    assert!(
        !String::from_utf8_lossy(&tight.stdout).contains("child-ran"),
        "a child past the job's process limit started"
    );
}

/// The loopback filter is installed by setup from this version on; a machine
/// set up earlier has none until the owner runs setup again. Where the account
/// is required (CI runs setup fresh) it is measured; elsewhere it is skipped.
fn freshly_set_up() -> Option<PathBuf> {
    std::env::var_os("RAIKER_REQUIRE_ACCOUNT_SANDBOX").and(configured())
}

fn connects(copy: &Copy, port: u16) -> bool {
    let powershell = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe";
    let script = format!(
        "try {{ $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1', {port}); exit 0 }} catch {{ exit 3 }}"
    );
    run(
        copy,
        &[
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            &script,
        ],
    )
    .status
    .code()
        == Some(0)
}

fn free_port_in(ports: std::ops::RangeInclusive<u16>) -> std::net::TcpListener {
    ports
        .into_iter()
        .find_map(|port| std::net::TcpListener::bind(("127.0.0.1", port)).ok())
        .expect("a free port in the range")
}

#[test]
fn the_account_reaches_the_proxy_and_port_zero_servers_but_no_fixed_port_service() {
    let _account_test = ACCOUNT_TEST.lock().unwrap();
    let Some(base) = freshly_set_up() else { return };
    let copy = copy_under(&base, "loopback");
    // Owner listeners: the proxy range, a fixed port where services such as
    // Raiker (8765) or Ollama (11434) listen, and a port-0 server.
    let proxy = free_port_in(47300..=47363);
    let fixed = free_port_in(40000..=40100);
    let ephemeral = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let port = |listener: &std::net::TcpListener| listener.local_addr().unwrap().port();
    assert!(
        connects(&copy, port(&proxy)),
        "the proxy range must stay reachable"
    );
    assert!(
        !connects(&copy, port(&fixed)),
        "a fixed-port local service was reachable"
    );
    // The dynamic range stays open for the account's own port-0 servers; a
    // host service there is the stated gap.
    assert!(
        connects(&copy, port(&ephemeral)),
        "the dynamic range must stay reachable"
    );
}
