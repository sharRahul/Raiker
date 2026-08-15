//! The launch contract Raiker hands the runner.
//!
//! The contract arrives as a JSON file rather than as command-line arguments:
//! argv is visible to every process on the host, and a boundary description is
//! not something a governed runtime should broadcast. The file is read once and
//! the runner never writes it.

use serde_json::Value;
use std::path::PathBuf;

/// What the child is allowed to reach on the network.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum NetworkPolicy {
    /// No capability, no route. This is the default and the only value a
    /// command receives unless the owner granted filtered egress.
    Denied,
    /// Egress is permitted only through this loopback proxy address. The
    /// boundary — not the child — is what makes the proxy the single route.
    Proxy(String),
}

#[derive(Debug, Clone)]
pub struct LaunchPolicy {
    pub workspace_root: PathBuf,
    pub cwd: PathBuf,
    /// Workspace-relative paths the child may not read or write at all.
    pub deny_paths: Vec<String>,
    /// Workspace-relative paths the child may read but never write.
    pub readonly_paths: Vec<String>,
    pub network: NetworkPolicy,
    pub pty: bool,
    pub max_processes: u32,
    pub max_memory_bytes: u64,
    /// The boundary's own timeout. Raiker keeps its outer timer, but a wedged
    /// relay must not be able to leave a command running past its bound, and on
    /// a platform with no parent-death signal this is what bounds it at all.
    pub deadline_seconds: u64,
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
    if !cwd.starts_with(&workspace_root) {
        return Err("runner_policy_cwd_outside_workspace");
    }
    let profile_name = object
        .get("profile_name")
        .and_then(Value::as_str)
        .filter(|name| !name.is_empty() && name.len() <= 64)
        .ok_or("runner_policy_profile_name_required")?
        .to_owned();

    let network = match object.get("network").and_then(Value::as_str) {
        None | Some("none") => NetworkPolicy::Denied,
        Some(other) => match other.strip_prefix("proxy:") {
            Some(address) if !address.is_empty() => NetworkPolicy::Proxy(address.to_owned()),
            _ => return Err("runner_policy_network_invalid"),
        },
    };

    Ok(LaunchPolicy {
        workspace_root,
        cwd,
        deny_paths: string_list(object.get("deny_paths")),
        readonly_paths: string_list(object.get("readonly_paths")),
        network,
        pty: object.get("pty").and_then(Value::as_bool).unwrap_or(false),
        max_processes: bounded(object.get("max_processes"), 64, 1, 4096) as u32,
        max_memory_bytes: bounded(
            object.get("max_memory_bytes"),
            2 * 1024 * 1024 * 1024,
            64 * 1024 * 1024,
            32u64 * 1024 * 1024 * 1024,
        ),
        deadline_seconds: bounded(object.get("deadline_seconds"), 300, 1, 86_400),
        profile_name,
    })
}

fn string_list(value: Option<&Value>) -> Vec<String> {
    value
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(Value::as_str)
                .filter(|item| !item.is_empty() && !item.contains(".."))
                .map(str::to_owned)
                .collect()
        })
        .unwrap_or_default()
}

fn bounded(value: Option<&Value>, default: u64, low: u64, high: u64) -> u64 {
    value
        .and_then(Value::as_u64)
        .unwrap_or(default)
        .clamp(low, high)
}

#[cfg(test)]
mod tests {
    use super::*;

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
    fn traversal_entries_never_enter_the_path_lists() {
        let text = minimal().replace(
            "\"profile_name\"",
            "\"deny_paths\":[\".raiker\",\"../etc\"],\"profile_name\"",
        );
        assert_eq!(parse(&text).unwrap().deny_paths, vec![".raiker".to_owned()]);
    }
}
