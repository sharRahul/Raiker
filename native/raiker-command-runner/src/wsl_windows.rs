//! The WSL2 backend for Windows: Linux toolchains under Bubblewrap and seccomp.
//!
//! Optional. The restricted account already runs Windows toolchains; this
//! adds Linux ones. Raiker runs the **Linux** runner inside its own
//! distribution ([`wsl_paths::DISTRO`]), so the boundary is the one the Linux
//! CI measures — Bubblewrap, seccomp, a private network namespace — and this
//! module only has to get a run there and back:
//!
//! * `--setup-wsl --rootfs <tar> --linux-runner <file>` imports the
//!   distribution, writes its `wsl.conf` (no interop, no drives), creates the
//!   run user, and installs the Linux runner root-owned. No elevation: WSL
//!   distributions are per user.
//! * A policy whose workspace is a copy under
//!   `\\wsl.localhost\RaikerSandbox\var\lib\raiker\copies` is rewritten in
//!   Linux form, written into the distribution, and run with
//!   `wsl.exe -d RaikerSandbox -u raiker --exec <linux runner> --policy …`.
//! * `--probe --boundary wsl` runs the Linux runner's own probe in the
//!   distribution and adds one observation, `windows_interop`.
//!
//! GitHub's hosted Windows runners cannot run WSL2 (no nested
//! virtualisation), so this backend's evidence comes from an owner's machine,
//! never from the release gate. It stays opt-in.

use super::*;
use crate::wsl_paths::{self, DISTRO, LINUX_COPIES, LINUX_POLICIES, LINUX_RUNNER, RUN_USER};
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};
use windows_sys::Win32::System::SystemInformation::GetSystemWindowsDirectoryW;

/// `wsl.exe` from the Windows directory, never from `PATH`.
fn wsl_exe() -> Result<PathBuf, String> {
    let mut buffer = [0u16; 260];
    let length =
        unsafe { GetSystemWindowsDirectoryW(buffer.as_mut_ptr(), buffer.len() as u32) } as usize;
    if length == 0 || length >= buffer.len() {
        return Err("native_sandbox_wsl_unavailable".into());
    }
    let path = PathBuf::from(String::from_utf16_lossy(&buffer[..length]))
        .join("System32")
        .join("wsl.exe");
    if path.is_file() {
        Ok(path)
    } else {
        Err("native_sandbox_wsl_unavailable".into())
    }
}

/// `wsl.exe` prints UTF-16LE when its output is not a console.
fn decode(bytes: &[u8]) -> String {
    if bytes.len() >= 2 && bytes.len().is_multiple_of(2) && bytes[1] == 0 {
        let (pairs, _) = bytes.as_chunks::<2>();
        let units: Vec<u16> = pairs.iter().map(|pair| u16::from_le_bytes(*pair)).collect();
        String::from_utf16_lossy(&units)
    } else {
        String::from_utf8_lossy(bytes).into_owned()
    }
}

fn distro_present() -> bool {
    let Ok(wsl) = wsl_exe() else { return false };
    Command::new(wsl)
        .args(["--list", "--quiet"])
        .output()
        .is_ok_and(|output| {
            decode(&output.stdout)
                .lines()
                .any(|line| line.trim().trim_matches('\0').eq_ignore_ascii_case(DISTRO))
        })
}

/// A shell command in the distribution as `user`, stdout returned.
fn in_distro(user: &str, script: &str, input: Option<&[u8]>) -> Result<Vec<u8>, String> {
    let mut child = Command::new(wsl_exe()?)
        .args([
            "-d", DISTRO, "-u", user, "--cd", "/", "--exec", "/bin/sh", "-c", script,
        ])
        .stdin(if input.is_some() {
            Stdio::piped()
        } else {
            Stdio::null()
        })
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|_| "native_sandbox_wsl_unavailable")?;
    if let (Some(bytes), Some(mut stdin)) = (input, child.stdin.take()) {
        stdin
            .write_all(bytes)
            .map_err(|_| "native_sandbox_wsl_unavailable")?;
    }
    let output = child
        .wait_with_output()
        .map_err(|_| "native_sandbox_wsl_unavailable")?;
    if output.status.success() {
        Ok(output.stdout)
    } else {
        Err("native_sandbox_wsl_command_failed".into())
    }
}

pub fn status() -> Value {
    let present = distro_present();
    let conf = present
        && in_distro("root", "test ! -s /etc/fstab && cat /etc/wsl.conf", None)
            .is_ok_and(|bytes| bytes == wsl_paths::wsl_conf().as_bytes());
    let runner = present
        && in_distro(
            "root",
            &format!("test -x {LINUX_RUNNER} && test \"$(stat -c %u {LINUX_RUNNER})\" = 0"),
            None,
        )
        .is_ok();
    let bubblewrap = present && in_distro("root", "test -x /usr/bin/bwrap", None).is_ok();
    json!({
        "configured": present && conf && runner && bubblewrap,
        "distribution": DISTRO,
        "base": wsl_paths::windows_copies(),
        "distribution_present": present,
        "wsl_conf_current": conf,
        "runner_installed": runner,
        "bubblewrap_present": bubblewrap,
    })
}

/// Import and configure Raiker's distribution. Idempotent.
pub fn setup(rootfs: Option<&Path>, linux_runner: &Path) -> Result<Value, String> {
    let wsl = wsl_exe()?;
    if !distro_present() {
        let rootfs = rootfs.ok_or("native_sandbox_wsl_rootfs_required")?;
        let local = std::env::var_os("LOCALAPPDATA")
            .map(PathBuf::from)
            .ok_or("native_sandbox_wsl_setup_failed")?
            .join("Raiker")
            .join("wsl");
        std::fs::create_dir_all(&local).map_err(|_| "native_sandbox_wsl_setup_failed")?;
        let status = Command::new(&wsl)
            .arg("--import")
            .arg(DISTRO)
            .arg(&local)
            .arg(rootfs)
            .args(["--version", "2"])
            .status()
            .map_err(|_| "native_sandbox_wsl_setup_failed")?;
        if !status.success() {
            return Err("native_sandbox_wsl_import_failed".into());
        }
    }
    let runner = std::fs::read(linux_runner).map_err(|_| "native_sandbox_wsl_runner_unreadable")?;
    // Linux runners are ELF; refusing anything else keeps a Windows runner
    // from being installed by mistake.
    if !runner.starts_with(b"\x7fELF") {
        return Err("native_sandbox_wsl_runner_unreadable".into());
    }
    let configure = format!(
        "set -e\n\
         id -u {RUN_USER} >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin {RUN_USER}\n\
         mkdir -p /opt/raiker {LINUX_COPIES} {LINUX_POLICIES}\n\
         chown root:root /opt/raiker && chmod 0755 /opt/raiker\n\
         chown {RUN_USER}:{RUN_USER} {LINUX_COPIES} {LINUX_POLICIES}\n\
         chmod 0700 {LINUX_COPIES} {LINUX_POLICIES}\n\
         install -o root -g root -m 0644 /dev/null /etc/fstab\n\
         command -v bwrap >/dev/null 2>&1 || (apt-get update -qq && apt-get install -y -qq bubblewrap) >/dev/null 2>&1 || true\n\
         cat > /etc/wsl.conf <<'RAIKER_WSL_CONF'\n{}RAIKER_WSL_CONF\n",
        wsl_paths::wsl_conf()
    );
    in_distro("root", &configure, None).map_err(|_| "native_sandbox_wsl_setup_failed")?;
    in_distro(
        "root",
        &format!(
            "cat > {LINUX_RUNNER}.new && chown root:root {LINUX_RUNNER}.new \
             && chmod 0755 {LINUX_RUNNER}.new && mv -f {LINUX_RUNNER}.new {LINUX_RUNNER}"
        ),
        Some(&runner),
    )
    .map_err(|_| "native_sandbox_wsl_runner_install_failed")?;
    // wsl.conf is read when the distribution starts.
    let _ = Command::new(&wsl).args(["--terminate", DISTRO]).status();
    let report = status();
    if report["bubblewrap_present"] != true {
        return Err("native_sandbox_wsl_bubblewrap_missing".into());
    }
    Ok(report)
}

/// Unregister the distribution, and with it every copy inside it.
pub fn reset() -> Result<(), String> {
    if !distro_present() {
        return Ok(());
    }
    let status = Command::new(wsl_exe()?)
        .args(["--unregister", DISTRO])
        .status()
        .map_err(|_| "native_sandbox_wsl_reset_failed")?;
    if status.success() {
        Ok(())
    } else {
        Err("native_sandbox_wsl_reset_failed".into())
    }
}

/// Whether this run is a copy in Raiker's distribution.
pub fn owns(policy: &LaunchPolicy) -> bool {
    policy
        .workspace_root
        .to_str()
        .and_then(wsl_paths::to_linux_path)
        .is_some_and(|linux| wsl_paths::is_copy(&linux))
}

/// The translated policy, written into the distribution, removed on drop.
struct PolicyFile {
    windows: PathBuf,
    linux: String,
}

impl PolicyFile {
    fn write(text: &str) -> Result<PolicyFile, String> {
        let name = format!("{}.json", selftest::probe_nonce());
        let windows = PathBuf::from(wsl_paths::windows_policy(&name));
        std::fs::write(&windows, text).map_err(|_| "native_sandbox_wsl_policy_unwritable")?;
        Ok(PolicyFile {
            windows,
            linux: format!("{LINUX_POLICIES}/{name}"),
        })
    }
}

impl Drop for PolicyFile {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.windows);
    }
}

/// Run `argv` (Linux argv) in the copy the policy names.
///
/// A terminal run passes through: the Linux runner sees pipes from `wsl.exe`
/// and opens the terminal itself inside the distribution.
pub fn launch(policy: &LaunchPolicy, policy_text: &str, argv: &[String]) -> Result<i32, String> {
    if status()["configured"] != true {
        return Err("native_sandbox_wsl_unconfigured".into());
    }
    let translated = wsl_paths::translate_policy(policy_text)?;
    let file = PolicyFile::write(&translated)?;
    let deadline = Instant::now()
        .checked_add(Duration::from_secs(policy.deadline_seconds))
        .ok_or("native_sandbox_deadline_invalid")?;
    let mut child = Command::new(wsl_exe()?)
        .args([
            "-d",
            DISTRO,
            "-u",
            RUN_USER,
            "--cd",
            "/",
            "--exec",
            LINUX_RUNNER,
        ])
        .arg("--policy")
        .arg(&file.linux)
        .arg("--")
        .args(argv)
        .spawn()
        .map_err(|error| {
            format!(
                "native_sandbox_launch_failed:{}",
                error.raw_os_error().unwrap_or(0)
            )
        })?;
    loop {
        match child.try_wait() {
            Ok(Some(status)) => return Ok(status.code().unwrap_or(1)),
            Ok(None) => {}
            Err(_) => return Err("native_sandbox_wait_failed".into()),
        }
        if Instant::now() >= deadline {
            // The Linux runner keeps the same deadline; this is the backstop.
            // Its command line names this run's policy file, and its namespace
            // dies with it (PR_SET_PDEATHSIG), so only this run is stopped.
            let _ = in_distro(
                "root",
                &format!("pkill -9 -f -- '--policy {}'", file.linux),
                None,
            );
            let _ = child.kill();
            let _ = child.wait();
            return Ok(137);
        }
        std::thread::sleep(Duration::from_millis(20));
    }
}

/// The Linux runner's probe, in a scratch copy, plus the interop check.
pub fn probe() -> Value {
    match measure() {
        Ok(value) => value,
        Err(reason) => unavailable(&reason),
    }
}

fn measure() -> Result<Value, String> {
    if status()["configured"] != true {
        return Err("native_sandbox_wsl_unconfigured".into());
    }
    let scratch = format!("{LINUX_COPIES}/probe-{}", selftest::probe_nonce());
    let output = in_distro(
        RUN_USER,
        &format!(
            "mkdir {scratch} && {LINUX_RUNNER} --probe --workspace {scratch}; rm -rf {scratch}"
        ),
        None,
    )?;
    let mut report: Value =
        serde_json::from_slice(&output).map_err(|_| "native_sandbox_probe_no_output")?;
    let interop = in_distro(RUN_USER, wsl_paths::INTEROP_SCRIPT, None)
        .map(|bytes| wsl_paths::interop_verdict(&String::from_utf8_lossy(&bytes)))
        .unwrap_or("indeterminate");
    report["platform"] = json!("windows");
    report["boundary"] = json!("wsl_bubblewrap");
    report["observations"]["windows_interop"] = json!(interop);
    if interop != "enforced" {
        report["reason"] = json!("native_sandbox_not_enforced");
    }
    report["account_base"] = json!(wsl_paths::windows_copies());
    Ok(report)
}
