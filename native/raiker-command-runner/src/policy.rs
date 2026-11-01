//! The launch contract Raiker hands the runner.
//!
//! The contract arrives as a JSON file rather than as command-line arguments:
//! argv is visible to every process on the host, and a boundary description is
//! not something a governed runtime should broadcast. The file is read once and
//! the runner never writes it.

use serde_json::Value;
use std::path::{Component, Path, PathBuf};

/// What the child is allowed to reach on the network.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum NetworkPolicy {
    /// No capability, no route. This is the default and the only value a
    /// command receives unless the owner granted filtered egress.
    Denied,
    /// Egress is permitted only to Raiker's proxy on `127.0.0.1:port`. The
    /// boundary -- not the child -- is what makes the proxy the single route.
    /// On Linux the proxy listens on `socket` outside the sandbox and a bridge
    /// inside the network namespace forwards the loopback port to it.
    Proxy { port: u16, socket: Option<PathBuf> },
}

#[derive(Debug, Clone)]
pub struct LaunchPolicy {
    pub workspace_root: PathBuf,
    pub cwd: PathBuf,
    /// Workspace-relative paths the child may not read or write at all.
    pub deny_paths: Vec<String>,
    /// Workspace-relative paths the child may read but never write.
    pub readonly_paths: Vec<String>,
    /// Absolute folders outside the workspace holding a toolchain the
    /// command runs (an interpreter's install prefix), mounted read-only.
    /// Linux only; the other boundaries already read system installs.
    #[cfg_attr(windows, allow(dead_code))]
    pub toolchain_paths: Vec<PathBuf>,
    pub network: NetworkPolicy,
    pub pty: bool,
    pub max_processes: u32,
    pub max_memory_bytes: u64,
    /// The boundary's own timeout. Raiker keeps its outer timer, but a wedged
    /// relay must not be able to leave a command running past its bound, and on
    /// a platform with no parent-death signal this is what bounds it at all.
    pub deadline_seconds: u64,
    pub max_cpu_seconds: u64,
    /// The **per-run** AppContainer profile name (Windows) or namespace label
    /// (Linux/macOS). Per run, not stable: a predictable container name would
    /// let any local process enter a container the workspace already trusts.
    pub profile_name: String,
}

pub fn parse(text: &str) -> Result<LaunchPolicy, &'static str> {
    let value: Value = serde_json::from_str(text).map_err(|_| "runner_policy_invalid_json")?;
    let object = value.as_object().ok_or("runner_policy_invalid_json")?;

    let workspace_root = PathBuf::from(
        object
            .get("workspace_root")
            .and_then(Value::as_str)
            .ok_or("runner_policy_workspace_root_required")?,
    );
    let cwd = PathBuf::from(
        object
            .get("cwd")
            .and_then(Value::as_str)
            .ok_or("runner_policy_cwd_required")?,
    );
    if !workspace_root.is_absolute()
        || workspace_root
            .components()
            .any(|part| part == Component::ParentDir)
        || !policy_path_text_safe(&workspace_root)
    {
        return Err("runner_policy_workspace_root_invalid");
    }
    if !cwd.is_absolute()
        || cwd.components().any(|part| part == Component::ParentDir)
        || !policy_path_text_safe(&cwd)
        || !cwd.starts_with(&workspace_root)
    {
        return Err("runner_policy_cwd_outside_workspace");
    }
    let profile_name = object
        .get("profile_name")
        .and_then(Value::as_str)
        .filter(|name| !name.is_empty() && name.len() <= 64)
        .ok_or("runner_policy_profile_name_required")?
        .to_owned();

    let network = match object.get("network") {
        None => NetworkPolicy::Denied,
        Some(value) => match value.as_str().ok_or("runner_policy_network_invalid")? {
            "none" => NetworkPolicy::Denied,
            other => {
                // Only loopback: the proxy runs beside Raiker, never elsewhere.
                let port = other
                    .strip_prefix("proxy:127.0.0.1:")
                    .and_then(|text| text.parse::<u16>().ok())
                    .filter(|port| *port != 0)
                    .ok_or("runner_policy_network_invalid")?;
                let socket = match object.get("proxy_socket") {
                    None => None,
                    Some(value) => {
                        let path = PathBuf::from(
                            value.as_str().ok_or("runner_policy_proxy_socket_invalid")?,
                        );
                        if !path.is_absolute()
                            || path.components().any(|part| part == Component::ParentDir)
                            || !policy_path_text_safe(&path)
                        {
                            return Err("runner_policy_proxy_socket_invalid");
                        }
                        Some(path)
                    }
                };
                NetworkPolicy::Proxy { port, socket }
            }
        },
    };
    let pty = match object.get("pty") {
        None => false,
        Some(value) => value.as_bool().ok_or("runner_policy_pty_invalid")?,
    };

    let deadline_seconds = bounded(object.get("deadline_seconds"), 300, 1, 86_400)?;
    let max_cpu_seconds = bounded(object.get("max_cpu_seconds"), deadline_seconds, 1, 86_400)?;
    let toolchain_paths = toolchain_paths(object.get("toolchain_paths"), &workspace_root)?;
    Ok(LaunchPolicy {
        workspace_root,
        cwd,
        deny_paths: string_list(object.get("deny_paths"))?,
        readonly_paths: string_list(object.get("readonly_paths"))?,
        toolchain_paths,
        network,
        pty,
        max_processes: bounded(object.get("max_processes"), 64, 1, 4096)? as u32,
        max_memory_bytes: bounded(
            object.get("max_memory_bytes"),
            2 * 1024 * 1024 * 1024,
            64 * 1024 * 1024,
            32u64 * 1024 * 1024 * 1024,
        )?,
        deadline_seconds,
        max_cpu_seconds,
        profile_name,
    })
}

/// Absolute, plain, never the root, and never the workspace or anything
/// holding it: a toolchain mount adds a read-only system tree, it does not
/// re-expose the project the copy exists to keep out of reach.
fn toolchain_paths(value: Option<&Value>, workspace: &Path) -> Result<Vec<PathBuf>, &'static str> {
    let Some(value) = value else {
        return Ok(Vec::new());
    };
    let entries = value.as_array().ok_or("runner_policy_toolchain_invalid")?;
    if entries.len() > 16 {
        return Err("runner_policy_toolchain_invalid");
    }
    let mut paths = Vec::new();
    for entry in entries {
        let path = PathBuf::from(entry.as_str().ok_or("runner_policy_toolchain_invalid")?);
        if !path.is_absolute()
            || path.components().count() < 3
            || path.components().any(|part| part == Component::ParentDir)
            || !policy_path_text_safe(&path)
            || workspace.starts_with(&path)
            || path.starts_with(workspace)
        {
            return Err("runner_policy_toolchain_invalid");
        }
        paths.push(path);
    }
    Ok(paths)
}

fn policy_path_text_safe(path: &Path) -> bool {
    let text = path.to_string_lossy();
    !text
        .chars()
        .any(|character| character.is_control() || character == '"')
        && (cfg!(windows) || !text.contains('\\'))
}

/// Check the current filesystem state immediately before boundary construction.
/// This does not pin directory handles and therefore does not eliminate races.
pub fn validate_filesystem_paths(policy: &LaunchPolicy) -> Result<(), &'static str> {
    let root_metadata = std::fs::symlink_metadata(&policy.workspace_root)
        .map_err(|_| "runner_policy_workspace_unreadable")?;
    if is_link(&root_metadata) || !root_metadata.is_dir() {
        return Err("runner_policy_workspace_invalid");
    }
    let root = std::fs::canonicalize(&policy.workspace_root)
        .map_err(|_| "runner_policy_workspace_unreadable")?;
    if root.parent().is_none() {
        return Err("runner_policy_workspace_root_forbidden");
    }
    let cwd = std::fs::canonicalize(&policy.cwd).map_err(|_| "runner_policy_cwd_unreadable")?;
    if !cwd.starts_with(&root) || !cwd.is_dir() {
        return Err("runner_policy_cwd_outside_workspace");
    }
    let relative_cwd = policy
        .cwd
        .strip_prefix(&policy.workspace_root)
        .map_err(|_| "runner_policy_cwd_outside_workspace")?;
    check_no_links(
        &policy.workspace_root,
        relative_cwd,
        "runner_policy_cwd_link",
    )?;
    for path in policy.deny_paths.iter().chain(policy.readonly_paths.iter()) {
        check_no_links(
            &policy.workspace_root,
            Path::new(path),
            "runner_policy_protected_path_link",
        )?;
    }
    Ok(())
}

fn check_no_links(root: &Path, relative: &Path, reason: &'static str) -> Result<(), &'static str> {
    let mut path = root.to_path_buf();
    for part in relative.components() {
        path.push(part.as_os_str());
        match std::fs::symlink_metadata(&path) {
            Ok(metadata) if is_link(&metadata) => return Err(reason),
            Ok(_) => {}
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => break,
            Err(_) => return Err("runner_policy_path_unreadable"),
        }
    }
    Ok(())
}

fn is_link(metadata: &std::fs::Metadata) -> bool {
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        const FILE_ATTRIBUTE_REPARSE_POINT: u32 = 0x400;
        metadata.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT != 0
    }
    #[cfg(not(windows))]
    {
        metadata.file_type().is_symlink()
    }
}

fn string_list(value: Option<&Value>) -> Result<Vec<String>, &'static str> {
    let Some(value) = value else {
        return Ok(Vec::new());
    };
    let items = value.as_array().ok_or("runner_policy_path_list_invalid")?;
    items
        .iter()
        .map(|item| {
            let text = item.as_str().ok_or("runner_policy_path_list_invalid")?;
            let path = Path::new(text);
            if text.is_empty()
                || text.contains(':')
                || text.contains('\\')
                || !policy_path_text_safe(path)
                || !path
                    .components()
                    .all(|part| matches!(part, Component::Normal(_)))
            {
                return Err("runner_policy_path_list_invalid");
            }
            Ok(text.to_owned())
        })
        .collect()
}

fn bounded(value: Option<&Value>, default: u64, low: u64, high: u64) -> Result<u64, &'static str> {
    let Some(value) = value else {
        return Ok(default);
    };
    let number = value.as_u64().ok_or("runner_policy_limit_invalid")?;
    if !(low..=high).contains(&number) {
        return Err("runner_policy_limit_invalid");
    }
    Ok(number)
}

#[cfg(test)]
mod tests {
    #[test]
    fn a_toolchain_mount_is_a_plain_system_tree_never_the_workspace() {
        let parse = |toolchains: serde_json::Value| {
            let workspace = if cfg!(windows) {
                r"C:\work\copy"
            } else {
                "/work/copy"
            };
            parse(
                &serde_json::json!({
                    "workspace_root": workspace, "cwd": workspace,
                    "profile_name": "raiker.cmd.t", "toolchain_paths": toolchains,
                })
                .to_string(),
            )
        };
        let (good, root, holding, inside) = if cfg!(windows) {
            (r"C:\opt\py", r"C:\", r"C:\work", r"C:\work\copy\venv")
        } else {
            ("/opt/py/x64", "/", "/work", "/work/copy/venv")
        };
        assert_eq!(
            parse(serde_json::json!([good])).unwrap().toolchain_paths,
            vec![PathBuf::from(good)]
        );
        for bad in [root, holding, inside, "relative/path"] {
            assert!(parse(serde_json::json!([bad])).is_err(), "{bad}");
        }
    }

    use super::*;

    #[cfg(unix)]
    #[test]
    fn the_host_filesystem_root_cannot_be_the_workspace() {
        let policy = parse(r#"{"workspace_root":"/","cwd":"/","profile_name":"root"}"#).unwrap();
        assert_eq!(
            validate_filesystem_paths(&policy),
            Err("runner_policy_workspace_root_forbidden")
        );
    }

    #[cfg(windows)]
    #[test]
    fn a_windows_drive_root_cannot_be_the_workspace() {
        let current = std::env::current_dir().unwrap();
        let root = current.ancestors().last().unwrap();
        let json = serde_json::json!({
            "workspace_root": root, "cwd": root, "profile_name": "root"
        });
        let policy = parse(&json.to_string()).unwrap();
        assert_eq!(
            validate_filesystem_paths(&policy),
            Err("runner_policy_workspace_root_forbidden")
        );
    }

    fn minimal() -> String {
        let root = if cfg!(windows) { "C:\\ws" } else { "/ws" };
        format!(
            r#"{{"workspace_root":"{root}","cwd":"{root}","profile_name":"raiker.cmd.test"}}"#,
            root = root.replace('\\', "\\\\")
        )
    }

    #[test]
    fn defaults_deny_the_network_and_the_pty() {
        let policy = parse(&minimal()).unwrap();
        assert_eq!(policy.network, NetworkPolicy::Denied);
        assert!(!policy.pty);
    }

    #[test]
    fn a_cwd_outside_the_workspace_is_refused() {
        let text = minimal().replace(r#""cwd":"C:\\ws""#, r#""cwd":"C:\\other""#);
        let text = text.replace(r#""cwd":"/ws""#, r#""cwd":"/other""#);
        assert_eq!(
            parse(&text).unwrap_err(),
            "runner_policy_cwd_outside_workspace"
        );
    }

    #[test]
    fn a_malformed_network_value_is_refused_rather_than_defaulted() {
        let text = minimal().replace(
            "\"profile_name\"",
            "\"network\":\"proxy:\",\"profile_name\"",
        );
        assert_eq!(parse(&text).unwrap_err(), "runner_policy_network_invalid");
    }

    #[test]
    fn the_proxy_must_be_on_loopback() {
        let with = |value: &str| {
            minimal().replace(
                "\"profile_name\"",
                &format!("\"network\":\"{value}\",\"profile_name\""),
            )
        };
        assert_eq!(
            parse(&with("proxy:127.0.0.1:3128")).unwrap().network,
            NetworkPolicy::Proxy {
                port: 3128,
                socket: None
            }
        );
        for refused in [
            "proxy:10.0.0.5:3128",
            "proxy:127.0.0.1:0",
            "proxy:127.0.0.1:x",
        ] {
            assert_eq!(
                parse(&with(refused)).unwrap_err(),
                "runner_policy_network_invalid"
            );
        }
    }

    #[test]
    fn a_relative_proxy_socket_is_refused() {
        let text = minimal().replace(
            "\"profile_name\"",
            "\"network\":\"proxy:127.0.0.1:3128\",\"proxy_socket\":\"egress.sock\",\"profile_name\"",
        );
        assert_eq!(
            parse(&text).unwrap_err(),
            "runner_policy_proxy_socket_invalid"
        );
    }

    #[test]
    fn traversal_entries_are_rejected_instead_of_dropped() {
        let text = minimal().replace(
            "\"profile_name\"",
            "\"deny_paths\":[\".raiker\",\"../etc\"],\"profile_name\"",
        );
        assert_eq!(parse(&text).unwrap_err(), "runner_policy_path_list_invalid");
    }

    #[test]
    fn cwd_with_parent_traversal_is_rejected() {
        let root = if cfg!(windows) { r"C:\ws" } else { "/ws" };
        let text = serde_json::json!({
            "workspace_root": root,
            "cwd": format!("{root}/../outside"),
            "profile_name": "raiker.cmd.test"
        })
        .to_string();
        assert_eq!(
            parse(&text).unwrap_err(),
            "runner_policy_cwd_outside_workspace"
        );
    }

    #[test]
    fn absolute_protected_path_is_rejected() {
        let text = minimal().replace(
            "\"profile_name\"",
            "\"deny_paths\":[\"/outside\"],\"profile_name\"",
        );
        assert_eq!(parse(&text).unwrap_err(), "runner_policy_path_list_invalid");
    }

    #[test]
    fn invalid_network_type_is_rejected() {
        let text = minimal().replace("\"profile_name\"", "\"network\":false,\"profile_name\"");
        assert_eq!(parse(&text).unwrap_err(), "runner_policy_network_invalid");
    }

    #[test]
    fn invalid_limits_are_rejected_instead_of_widened() {
        let text = minimal().replace("\"profile_name\"", "\"max_processes\":0,\"profile_name\"");
        assert_eq!(parse(&text).unwrap_err(), "runner_policy_limit_invalid");
        let cpu = minimal().replace("\"profile_name\"", "\"max_cpu_seconds\":0,\"profile_name\"");
        assert_eq!(parse(&cpu).unwrap_err(), "runner_policy_limit_invalid");
    }

    #[test]
    fn non_boolean_pty_is_rejected() {
        let text = minimal().replace("\"profile_name\"", "\"pty\":\"yes\",\"profile_name\"");
        assert_eq!(parse(&text).unwrap_err(), "runner_policy_pty_invalid");
    }

    #[test]
    fn malformed_protected_path_lists_are_rejected() {
        for invalid in [
            r#"[".raiker", 12]"#,
            r#"[".raiker", ""]"#,
            r#"["foo\\bar"]"#,
        ] {
            let text = minimal().replace(
                "\"profile_name\"",
                &format!("\"deny_paths\":{invalid},\"profile_name\""),
            );
            assert_eq!(parse(&text).unwrap_err(), "runner_policy_path_list_invalid");
        }
    }

    #[test]
    fn relative_workspace_is_rejected() {
        let text = serde_json::json!({
            "workspace_root": "workspace",
            "cwd": "workspace",
            "profile_name": "raiker.cmd.test"
        })
        .to_string();
        assert_eq!(
            parse(&text).unwrap_err(),
            "runner_policy_workspace_root_invalid"
        );
    }

    #[test]
    fn missing_workspace_is_not_a_valid_launch_boundary() {
        let root = std::env::temp_dir().join(format!(
            "raiker-missing-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let text = serde_json::json!({
            "workspace_root": root,
            "cwd": root,
            "profile_name": "raiker.cmd.test"
        })
        .to_string();
        let policy = parse(&text).unwrap();
        assert_eq!(
            validate_filesystem_paths(&policy).unwrap_err(),
            "runner_policy_workspace_unreadable"
        );
    }

    #[test]
    fn existing_workspace_and_cwd_are_accepted() {
        let root = std::env::temp_dir().join(format!(
            "raiker-path-valid-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let cwd = root.join("project");
        std::fs::create_dir_all(&cwd).unwrap();
        let text = serde_json::json!({
            "workspace_root": root,
            "cwd": cwd,
            "deny_paths": [".raiker"],
            "readonly_paths": [".git"],
            "profile_name": "raiker.cmd.test"
        })
        .to_string();
        assert!(validate_filesystem_paths(&parse(&text).unwrap()).is_ok());
        std::fs::remove_dir_all(root).unwrap();
    }

    #[cfg(unix)]
    #[test]
    fn symlinked_cwd_and_protected_path_are_refused() {
        use std::os::unix::fs::symlink;

        let root = std::env::temp_dir().join(format!(
            "raiker-path-check-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        let workspace = root.join("workspace");
        let outside = root.join("outside");
        std::fs::create_dir_all(&workspace).unwrap();
        std::fs::create_dir_all(&outside).unwrap();
        symlink(&outside, workspace.join("escape")).unwrap();
        let text = serde_json::json!({
            "workspace_root": workspace,
            "cwd": workspace.join("escape"),
            "deny_paths": ["escape"],
            "profile_name": "raiker.cmd.test"
        })
        .to_string();
        let mut policy = parse(&text).unwrap();
        assert_eq!(
            validate_filesystem_paths(&policy).unwrap_err(),
            "runner_policy_cwd_outside_workspace"
        );
        policy.cwd = workspace.clone();
        assert_eq!(
            validate_filesystem_paths(&policy).unwrap_err(),
            "runner_policy_protected_path_link"
        );
        std::fs::remove_dir_all(root).unwrap();
    }
}
