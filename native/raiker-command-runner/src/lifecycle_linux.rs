//! Identify a live process in a bubblewrap PID namespace without trusting a
//! namespace-local PID as a host PID. A pidfd pins the selected identity.

use std::collections::HashMap;
use std::os::fd::{AsRawFd, FromRawFd, OwnedFd};
use std::path::Path;

#[derive(Debug)]
struct Process {
    parent: u32,
    namespace_pid: u32,
    depth: usize,
    started: u64,
}

fn process(pid: u32) -> Option<Process> {
    let path = Path::new("/proc").join(pid.to_string());
    let status = std::fs::read_to_string(path.join("status")).ok()?;
    let mut parent = None;
    let mut namespace = Vec::new();
    for line in status.lines() {
        if let Some(value) = line.strip_prefix("PPid:") {
            parent = value.trim().parse().ok();
        }
        if let Some(value) = line.strip_prefix("NSpid:") {
            namespace = value
                .split_whitespace()
                .map(str::parse)
                .collect::<Result<_, _>>()
                .ok()?;
        }
    }
    let stat = std::fs::read_to_string(path.join("stat")).ok()?;
    // The command name is parenthesized and may itself contain spaces or ')'.
    let fields = stat
        .rsplit_once(')')?
        .1
        .split_whitespace()
        .collect::<Vec<_>>();
    Some(Process {
        parent: parent?,
        namespace_pid: *namespace.last()?,
        depth: namespace.len(),
        started: fields.get(19)?.parse().ok()?,
    })
}

fn is_descendant(pid: u32, root: u32, processes: &HashMap<u32, Process>) -> bool {
    let mut current = pid;
    for _ in 0..128 {
        if current == root {
            return true;
        }
        let Some(entry) = processes.get(&current) else {
            return false;
        };
        if entry.parent == current || entry.parent == 0 {
            return false;
        }
        current = entry.parent;
    }
    false
}

/// Return a pinned live descendant only when the namespace PID maps uniquely
/// under the specific bubblewrap process and its start time remains stable.
pub fn find_live_descendant(root: u32, namespace_pid: u32) -> Option<OwnedFd> {
    let processes: HashMap<u32, Process> = std::fs::read_dir("/proc")
        .ok()?
        .filter_map(Result::ok)
        .filter_map(|entry| entry.file_name().to_str()?.parse::<u32>().ok())
        .filter_map(|pid| process(pid).map(|value| (pid, value)))
        .collect();
    let candidates: Vec<_> = processes
        .iter()
        .filter(|(pid, item)| {
            item.depth >= 2
                && item.namespace_pid == namespace_pid
                && is_descendant(**pid, root, &processes)
        })
        .collect();
    if candidates.len() != 1 {
        return None;
    }
    let (&pid, initial) = candidates[0];
    let raw = unsafe { libc::syscall(libc::SYS_pidfd_open, pid, 0) };
    if raw < 0 {
        return None;
    }
    let handle = unsafe { OwnedFd::from_raw_fd(raw as i32) };
    let fresh = process(pid)?;
    if fresh.started != initial.started || fresh.namespace_pid != namespace_pid || !is_live(&handle)
    {
        return None;
    }
    Some(handle)
}

fn is_live(handle: &OwnedFd) -> bool {
    let mut fd = libc::pollfd {
        fd: handle.as_raw_fd(),
        events: libc::POLLIN,
        revents: 0,
    };
    unsafe { libc::poll(&mut fd, 1, 0) == 0 }
}

pub fn exited(handle: &OwnedFd, timeout_ms: i32) -> bool {
    let mut fd = libc::pollfd {
        fd: handle.as_raw_fd(),
        events: libc::POLLIN,
        revents: 0,
    };
    unsafe { libc::poll(&mut fd, 1, timeout_ms) == 1 && fd.revents & libc::POLLIN != 0 }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn current_process_identity_has_a_host_namespace_pid() {
        let pid = std::process::id();
        let current = process(pid).expect("current process must be readable");
        assert_eq!(current.namespace_pid, pid);
        assert!(current.started > 0);
    }

    #[test]
    fn pidfd_observes_real_process_termination() {
        let mut child = std::process::Command::new("/bin/sleep")
            .arg("30")
            .spawn()
            .unwrap();
        let raw = unsafe { libc::syscall(libc::SYS_pidfd_open, child.id(), 0) };
        assert!(raw >= 0, "pidfd_open is required for this security test");
        let handle = unsafe { OwnedFd::from_raw_fd(raw as i32) };
        assert!(is_live(&handle));
        child.kill().unwrap();
        assert!(exited(&handle, 5_000));
        child.wait().unwrap();
    }
}
