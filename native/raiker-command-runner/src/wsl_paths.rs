//! The pure half of the WSL2 backend: names, paths and policy rewriting.
//!
//! Kept free of Windows calls so it is unit-tested on every platform; the
//! process half is `wsl_windows.rs`.
//!
//! The design removes the two risky parts of running in WSL by configuration
//! rather than by measurement alone. Raiker uses its **own** distribution,
//! never the owner's, configured with:
//!
//! * `[interop] enabled=false` — WSL does not register its `binfmt_misc`
//!   handler, so nothing in the distribution can start a Windows program.
//!   Hiding `/init` would not do this: the handler is registered with the
//!   fix-binary flag and keeps working inside any mount namespace.
//! * `[automount] enabled=false` — no `/mnt/c`: the Windows drives are not in
//!   the distribution at all, so no path needs converting to `/mnt/<drive>`.
//!
//! Task copies therefore live on the distribution's own disk, and Windows
//! reaches them as `\\wsl.localhost\RaikerSandbox\var\lib\raiker\copies\…`.

use serde_json::{Value, json};

pub const DISTRO: &str = "RaikerSandbox";
pub const RUN_USER: &str = "raiker";
pub const LINUX_RUNNER: &str = "/opt/raiker/raiker-command-runner";
pub const LINUX_COPIES: &str = "/var/lib/raiker/copies";
pub const LINUX_POLICIES: &str = "/var/lib/raiker/policies";

/// `/etc/wsl.conf` for Raiker's distribution, exactly.
pub fn wsl_conf() -> String {
    format!(
        "# Written by raiker-command-runner --setup-wsl. Raiker's own distribution:\n\
         # no Windows programs (interop), no Windows drives (automount).\n\
         [boot]\n\
         systemd=false\n\
         [automount]\n\
         enabled=false\n\
         mountFsTab=false\n\
         [interop]\n\
         enabled=false\n\
         appendWindowsPath=false\n\
         [user]\n\
         default={RUN_USER}\n"
    )
}

/// The Windows path of the copy base, as `std::fs` and Python see it.
pub fn windows_copies() -> String {
    format!(
        r"\\wsl.localhost\{DISTRO}{}",
        LINUX_COPIES.replace('/', r"\")
    )
}

/// The Windows path of a file in the policies folder.
pub fn windows_policy(name: &str) -> String {
    format!(
        r"\\wsl.localhost\{DISTRO}{}\{name}",
        LINUX_POLICIES.replace('/', r"\")
    )
}

/// A Windows path into Raiker's distribution, as the Linux path it names.
///
/// Accepts the `\\wsl.localhost\` and legacy `\\wsl$\` forms, with or without
/// the `\\?\UNC\` prefix `canonicalize` adds. Anything else — another
/// distribution, a drive path, `..`, a component Linux would read
/// differently — is `None`.
pub fn to_linux_path(windows: &str) -> Option<String> {
    let rest = ["\\\\?\\UNC\\", "\\\\"]
        .iter()
        .find_map(|prefix| windows.strip_prefix(prefix))?;
    let mut parts = rest.split('\\');
    let host = parts.next()?;
    if !host.eq_ignore_ascii_case("wsl.localhost") && !host.eq_ignore_ascii_case("wsl$") {
        return None;
    }
    if !parts.next()?.eq_ignore_ascii_case(DISTRO) {
        return None;
    }
    let mut linux = String::new();
    for part in parts {
        if part.is_empty() {
            continue;
        }
        if part == "."
            || part == ".."
            || part
                .chars()
                .any(|character| character.is_control() || matches!(character, '/' | ':'))
        {
            return None;
        }
        linux.push('/');
        linux.push_str(part);
    }
    if linux.is_empty() { None } else { Some(linux) }
}

/// Whether a Linux path is a copy directly in the base.
pub fn is_copy(linux: &str) -> bool {
    linux
        .strip_prefix(LINUX_COPIES)
        .and_then(|rest| rest.strip_prefix('/'))
        .is_some_and(|name| !name.is_empty() && !name.contains('/'))
}

/// The run's policy with its paths in Linux form.
///
/// Toolchain mounts name Windows folders, which do not exist in the
/// distribution, so any are refused rather than dropped. Downloads stay off:
/// Raiker's proxy listens on a Windows socket the distribution's network
/// namespace cannot reach.
pub fn translate_policy(text: &str) -> Result<String, &'static str> {
    let mut value: Value = serde_json::from_str(text).map_err(|_| "runner_policy_invalid_json")?;
    let object = value.as_object_mut().ok_or("runner_policy_invalid_json")?;
    let root = object
        .get("workspace_root")
        .and_then(Value::as_str)
        .and_then(to_linux_path)
        .ok_or("native_sandbox_wsl_workspace_outside_base")?;
    if !is_copy(&root) {
        return Err("native_sandbox_wsl_workspace_outside_base");
    }
    let cwd = object
        .get("cwd")
        .and_then(Value::as_str)
        .and_then(to_linux_path)
        .ok_or("runner_policy_cwd_outside_workspace")?;
    if cwd != root && !cwd.starts_with(&format!("{root}/")) {
        return Err("runner_policy_cwd_outside_workspace");
    }
    if object
        .get("toolchain_paths")
        .and_then(Value::as_array)
        .is_some_and(|paths| !paths.is_empty())
    {
        return Err("native_sandbox_wsl_toolchain_unsupported");
    }
    match object.get("network").and_then(Value::as_str) {
        None | Some("none") => {}
        Some(_) => return Err("native_sandbox_wsl_downloads_unsupported"),
    }
    if object.contains_key("proxy_socket") {
        return Err("native_sandbox_wsl_downloads_unsupported");
    }
    object.insert("workspace_root".into(), json!(root));
    object.insert("cwd".into(), json!(cwd));
    object.insert("toolchain_paths".into(), json!([]));
    Ok(value.to_string())
}

/// What the run user sees of WSL's interop and drives, from the probe script
/// (`interop_script`). Enforced only when no interop handler is registered
/// and enabled, no drive is mounted, and no interop socket is named.
pub fn interop_verdict(report: &str) -> &'static str {
    let mut sections = report.split("--\n");
    let binfmt = sections.next().unwrap_or("");
    let mounts = sections.next().unwrap_or("");
    let socket = sections.next().unwrap_or("");
    if binfmt.lines().any(|line| line.trim() == "enabled")
        || mounts.lines().any(|line| !line.trim().is_empty())
        || !socket.trim().is_empty()
    {
        "unenforced"
    } else {
        "enforced"
    }
}

/// Printed by the run user, outside the sandbox, so it sees what any process
/// in the distribution would: each interop handler's state (newer WSL
/// registers `WSLInterop-late`), any mount under `/mnt`, the interop socket.
pub const INTEROP_SCRIPT: &str = "cat /proc/sys/fs/binfmt_misc/WSLInterop* 2>/dev/null; \
     echo --; ls -A /mnt 2>/dev/null; echo --; printf %s \"$WSL_INTEROP\"";

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_configuration_turns_off_interop_and_drives() {
        let conf = wsl_conf();
        for line in [
            "[interop]\nenabled=false\nappendWindowsPath=false",
            "[automount]\nenabled=false\nmountFsTab=false",
            "default=raiker",
        ] {
            assert!(conf.contains(line), "{conf}");
        }
    }

    #[test]
    fn only_paths_into_raikers_distribution_translate() {
        let copy = r"\\wsl.localhost\RaikerSandbox\var\lib\raiker\copies\task1";
        assert_eq!(
            to_linux_path(copy).as_deref(),
            Some("/var/lib/raiker/copies/task1")
        );
        assert_eq!(
            to_linux_path(r"\\?\UNC\wsl$\raikersandbox\var\lib\raiker\copies\a\b").as_deref(),
            Some("/var/lib/raiker/copies/a/b")
        );
        for refused in [
            r"C:\RaikerSandbox\task1",
            r"\\wsl.localhost\Ubuntu\var\lib\raiker\copies\task1",
            r"\\server\RaikerSandbox\var",
            r"\\wsl.localhost\RaikerSandbox\var\..\etc",
            r"\\wsl.localhost\RaikerSandbox\var\a:b",
            r"\\wsl.localhost\RaikerSandbox",
        ] {
            assert_eq!(to_linux_path(refused), None, "{refused}");
        }
        assert_eq!(
            to_linux_path(&windows_copies()).as_deref(),
            Some(LINUX_COPIES)
        );
    }

    #[test]
    fn a_copy_is_a_direct_child_of_the_base() {
        assert!(is_copy("/var/lib/raiker/copies/task1"));
        assert!(!is_copy("/var/lib/raiker/copies"));
        assert!(!is_copy("/var/lib/raiker/copies/task1/sub"));
        assert!(!is_copy("/var/lib/raiker/copiesX/task1"));
    }

    #[test]
    fn the_policy_is_rewritten_in_linux_form_or_refused() {
        let root = r"\\wsl.localhost\RaikerSandbox\var\lib\raiker\copies\t1";
        let policy = json!({
            "workspace_root": root, "cwd": format!(r"{root}\src"),
            "deny_paths": [".raiker"], "profile_name": "raiker.cmd.x",
        });
        let translated: Value =
            serde_json::from_str(&translate_policy(&policy.to_string()).unwrap()).unwrap();
        assert_eq!(translated["workspace_root"], "/var/lib/raiker/copies/t1");
        assert_eq!(translated["cwd"], "/var/lib/raiker/copies/t1/src");
        assert_eq!(translated["deny_paths"], json!([".raiker"]));

        let mut downloads = policy.clone();
        downloads["network"] = json!("proxy:127.0.0.1:3128");
        assert_eq!(
            translate_policy(&downloads.to_string()),
            Err("native_sandbox_wsl_downloads_unsupported")
        );
        let mut toolchain = policy.clone();
        toolchain["toolchain_paths"] = json!([r"C:\Python313"]);
        assert_eq!(
            translate_policy(&toolchain.to_string()),
            Err("native_sandbox_wsl_toolchain_unsupported")
        );
        let mut outside = policy.clone();
        outside["workspace_root"] = json!(r"C:\work");
        assert_eq!(
            translate_policy(&outside.to_string()),
            Err("native_sandbox_wsl_workspace_outside_base")
        );
        let mut sibling = policy;
        sibling["cwd"] = json!(r"\\wsl.localhost\RaikerSandbox\var\lib\raiker\copies\t10");
        assert_eq!(
            translate_policy(&sibling.to_string()),
            Err("runner_policy_cwd_outside_workspace")
        );
    }

    #[test]
    fn interop_is_enforced_only_with_no_handler_drive_or_socket() {
        assert_eq!(interop_verdict("--\n--\n"), "enforced");
        assert_eq!(
            interop_verdict("disabled\ninterpreter /init\n--\n--\n"),
            "enforced"
        );
        assert_eq!(
            interop_verdict("enabled\ninterpreter /init\nflags: PF\n--\n--\n"),
            "unenforced"
        );
        assert_eq!(interop_verdict("--\nc\n--\n"), "unenforced");
        assert_eq!(interop_verdict("--\n--\n/run/WSL/1_interop"), "unenforced");
    }
}
