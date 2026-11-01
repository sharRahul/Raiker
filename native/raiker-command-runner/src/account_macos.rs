//! The dedicated-account boundary for macOS.
//!
//! Seatbelt holds the filesystem and network boundary but cannot contain a
//! process tree: XNU has no PID namespace, so a command that double-forks and
//! calls `setsid()` leaves the run, and `RLIMIT_AS` is neither accepted nor
//! enforced, so memory is unbounded. Polling the runner's children cannot
//! close this — the grandchild is reparented to `launchd` between two polls.
//!
//! What holds is ownership. Every command runs as `_raikersandbox`, a hidden
//! role account that owns nothing, *and* inside the same Seatbelt profile as
//! before. Every process a run starts, detached or not, belongs to that
//! account, so:
//!
//! * **stopping a run** is killing every process of the account, which reaches every
//!   one of its processes and nothing else;
//! * **memory** is the sum of `ri_phys_footprint` over the account's
//!   processes, polled by the account-side runner, and the run is stopped
//!   past its limit;
//! * **process count** is `RLIMIT_NPROC`, which counts per user — exact here,
//!   because an account is used by one run at a time.
//!
//! There is a small pool of such accounts ([`POOL_SIZE`]: `_raikersandbox`,
//! `_raikersandbox1`, …). A run takes whichever is free, holding that
//! account's lock (which no account can open) for its whole life, so "all of
//! the account's processes" is always exactly one run's tree, and runs in
//! different copies overlap instead of queueing behind each other.
//!
//! Setup is one-time and owner-approved (`sudo raiker-command-runner
//! --setup-account`). It creates the account and group, installs this runner
//! root-owned at [`INSTALLED_RUNNER`], creates the copy base [`COPIES`]
//! (owner-owned, `0700`, searchable by the account through one ACL entry), and
//! writes one `sudoers` drop-in that lets the owner — and only the owner — run
//! exactly two commands as a pool account: the installed runner's
//! `--account-run` and `--account-stop` modes. No helper daemon and no Developer ID signature
//! are needed, and the owner gains nothing: the account holds less than the
//! owner already does.
//!
//! Launching needs no elevation. The owner-side runner grants the account the
//! one copy the run is in (an inheritable ACL entry), writes the launch payload
//! into it, and starts `sudo -n -u _raikersandbox <installed runner>
//! --account-run <payload>`. The account-side runner reads and deletes the
//! payload, starts `sandbox-exec` with the run's profile, and supervises it.
//! When it ends the owner side kills whatever the account still has running and
//! takes the copy's grant back.

use super::*;
use std::ffi::CString;
use std::fs;
use std::io::Write as _;
use std::os::unix::fs::{MetadataExt, OpenOptionsExt, PermissionsExt};
use std::time::{Duration, Instant};

pub const ACCOUNT: &str = "_raikersandbox";
pub const BASE: &str = "/Library/RaikerSandbox";
pub const INSTALLED_RUNNER: &str = "/Library/RaikerSandbox/bin/raiker-command-runner";
pub const COPIES: &str = "/Library/RaikerSandbox/copies";
/// How many accounts runs are spread over. Each serves one run at a time.
pub const POOL_SIZE: usize = 4;
const SUDOERS: &str = "/etc/sudoers.d/raiker-sandbox";
const SUDO: &str = "/usr/bin/sudo";
const CHMOD: &str = "/bin/chmod";
const FIND: &str = "/usr/bin/find";
const DSCL: &str = "/usr/bin/dscl";
const VISUDO: &str = "/usr/sbin/visudo";
const PKILL: &str = "/usr/bin/pkill";
/// Role accounts live below 500 on macOS, where they stay off the login
/// window. The range is searched for an id no user or group already holds.
const ID_RANGE: std::ops::RangeInclusive<u32> = 400..=499;
/// `PROC_UID_ONLY` from `<sys/proc_info.h>`; libc does not export it.
const PROC_UID_ONLY: u32 = 4;
/// How often the account-side runner measures the run's memory.
const SUPERVISE_INTERVAL: Duration = Duration::from_millis(50);

/// Everything the account can do inside a copy, granted on the copy's folders
/// with inheritance so files the run creates carry it too.
const ACCOUNT_DIRECTORY_RIGHTS: &str = "list,add_file,search,delete,add_subdirectory,delete_child,readattr,writeattr,readextattr,writeextattr,readsecurity,file_inherit,directory_inherit";
const ACCOUNT_FILE_RIGHTS: &str =
    "read,write,append,execute,delete,readattr,writeattr,readextattr,writeextattr,readsecurity";
/// The owner keeps full access to what the account creates (it is owned by the
/// account), so the change set can be reviewed, applied and deleted.
const OWNER_DIRECTORY_RIGHTS: &str = "list,add_file,search,delete,add_subdirectory,delete_child,readattr,writeattr,readextattr,writeextattr,readsecurity,writesecurity,chown,file_inherit,directory_inherit";

// ── Status ─────────────────────────────────────────────────────────────────

struct Account {
    name: String,
    uid: u32,
}

/// The name of pool account *index*: the first keeps the original name, so a
/// host set up before the pool keeps its account.
pub fn member_name(index: usize) -> String {
    if index == 0 {
        ACCOUNT.to_owned()
    } else {
        format!("{ACCOUNT}{index}")
    }
}

fn member_lock(index: usize) -> String {
    if index == 0 {
        format!("{COPIES}/.account.lock")
    } else {
        format!("{COPIES}/.account{index}.lock")
    }
}

fn lookup(name: &str) -> Option<Account> {
    let c_name = CString::new(name).ok()?;
    let entry = unsafe { libc::getpwnam(c_name.as_ptr()) };
    if entry.is_null() {
        return None;
    }
    let entry = unsafe { &*entry };
    Some(Account {
        name: name.to_owned(),
        uid: entry.pw_uid,
    })
}

/// Every pool account, or `None` if any is missing.
fn members() -> Option<Vec<Account>> {
    (0..POOL_SIZE)
        .map(|index| lookup(&member_name(index)))
        .collect()
}

/// The pool account this process runs as (the account side), if any.
fn current_member() -> Option<Account> {
    let uid = unsafe { libc::getuid() };
    if unsafe { libc::geteuid() } != uid {
        return None;
    }
    (0..POOL_SIZE)
        .filter_map(|index| lookup(&member_name(index)))
        .find(|member| member.uid == uid)
}

/// Whether the installed runner is this runner, byte for byte. The `sudoers`
/// rule names the installed path, so a Raiker update that is not followed by
/// setup would otherwise run an older account side.
fn installed_runner_current() -> bool {
    let Ok(current) = std::env::current_exe().and_then(fs::read) else {
        return false;
    };
    fs::read(INSTALLED_RUNNER).is_ok_and(|installed| installed == current)
}

fn root_owned_file(path: &str) -> bool {
    fs::symlink_metadata(path).is_ok_and(|metadata| {
        metadata.is_file() && metadata.uid() == 0 && metadata.mode() & 0o022 == 0
    })
}

/// Whether the account boundary is set up for the user running this.
pub fn status() -> Value {
    let owner = unsafe { libc::getuid() };
    let present = (0..POOL_SIZE)
        .filter(|index| lookup(&member_name(*index)).is_some())
        .count();
    let copies = fs::symlink_metadata(COPIES).ok();
    let copies_owned = copies
        .as_ref()
        .is_some_and(|metadata| metadata.is_dir() && metadata.uid() == owner);
    let installed =
        root_owned_file(INSTALLED_RUNNER) && ancestors_root_owned(Path::new(INSTALLED_RUNNER));
    let current = installed && installed_runner_current();
    let sudoers = root_owned_file(SUDOERS);
    json!({
        "configured": present == POOL_SIZE && copies_owned && installed && current && sudoers,
        "account": ACCOUNT,
        "pool_size": POOL_SIZE,
        "base": COPIES,
        "account_present": present == POOL_SIZE,
        "accounts_present": present,
        "copies_owned_by_owner": copies_owned,
        "runner_installed": installed,
        "runner_current": current,
        "sudoers_present": sudoers,
    })
}

/// Every directory above `path` is root-owned and not group- or
/// world-writable, so nobody but root can replace what `sudoers` names.
fn ancestors_root_owned(path: &Path) -> bool {
    path.ancestors().skip(1).all(|ancestor| {
        fs::symlink_metadata(ancestor).is_ok_and(|metadata| {
            !metadata.file_type().is_symlink()
                && metadata.uid() == 0
                && metadata.mode() & 0o022 == 0
        })
    })
}

// ── Setup and reset (root) ─────────────────────────────────────────────────

fn command_succeeds(program: &str, arguments: &[&str], failure: &str) -> Result<(), String> {
    let status = Command::new(program)
        .args(arguments)
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status()
        .map_err(|_| failure.to_owned())?;
    if status.success() {
        Ok(())
    } else {
        Err(failure.to_owned())
    }
}

fn used_ids(path: &str, attribute: &str) -> Result<Vec<u32>, String> {
    let output = Command::new(DSCL)
        .args([".", "-list", path, attribute])
        .output()
        .map_err(|_| "native_sandbox_account_directory_unreadable")?;
    if !output.status.success() {
        return Err("native_sandbox_account_directory_unreadable".into());
    }
    Ok(parse_id_list(&String::from_utf8_lossy(&output.stdout)))
}

fn parse_id_list(text: &str) -> Vec<u32> {
    text.lines()
        .filter_map(|line| line.split_whitespace().last()?.parse().ok())
        .collect()
}

fn free_id(used_users: &[u32], used_groups: &[u32]) -> Option<u32> {
    ID_RANGE
        .clone()
        .find(|id| !used_users.contains(id) && !used_groups.contains(id))
}

fn ensure_account(name: &str) -> Result<Account, String> {
    if let Some(existing) = lookup(name) {
        return Ok(existing);
    }
    let id = free_id(
        &used_ids("/Users", "UniqueID")?,
        &used_ids("/Groups", "PrimaryGroupID")?,
    )
    .ok_or("native_sandbox_account_no_free_id")?;
    let id_text = id.to_string();
    let group = format!("/Groups/{name}");
    let user = format!("/Users/{name}");
    let failure = "native_sandbox_account_create_failed";
    for arguments in [
        vec![".", "-create", &group],
        vec![".", "-create", &group, "PrimaryGroupID", &id_text],
        vec![".", "-create", &group, "RealName", "Raiker sandbox"],
        vec![".", "-create", &group, "Password", "*"],
        vec![".", "-create", &user],
        vec![".", "-create", &user, "UniqueID", &id_text],
        vec![".", "-create", &user, "PrimaryGroupID", &id_text],
        vec![".", "-create", &user, "RealName", "Raiker sandbox"],
        vec![".", "-create", &user, "UserShell", "/usr/bin/false"],
        vec![".", "-create", &user, "NFSHomeDirectory", "/var/empty"],
        vec![".", "-create", &user, "Password", "*"],
        vec![".", "-create", &user, "IsHidden", "1"],
    ] {
        command_succeeds(DSCL, &arguments, failure)?;
    }
    lookup(name).ok_or_else(|| failure.to_owned())
}

/// The user the `sudoers` rule is for: `--owner-uid`, else the user who ran
/// `sudo`. Never root — root needs no rule, and a rule for root would mean the
/// owner was not identified.
fn owner_uid(requested: Option<u32>) -> Result<u32, String> {
    let uid = requested
        .or_else(|| std::env::var("SUDO_UID").ok()?.parse().ok())
        .ok_or("native_sandbox_account_owner_unknown")?;
    if uid == 0 {
        return Err("native_sandbox_account_owner_unknown".into());
    }
    let entry = unsafe { libc::getpwuid(uid) };
    if entry.is_null() {
        return Err("native_sandbox_account_owner_unknown".into());
    }
    Ok(uid)
}

fn owner_gid(uid: u32) -> Result<u32, String> {
    let entry = unsafe { libc::getpwuid(uid) };
    if entry.is_null() {
        return Err("native_sandbox_account_owner_unknown".into());
    }
    Ok(unsafe { (*entry).pw_gid })
}

fn root_directory(path: &str) -> Result<(), String> {
    let failure = "native_sandbox_account_base_unsafe";
    match fs::symlink_metadata(path) {
        Ok(metadata) if metadata.file_type().is_symlink() || !metadata.is_dir() => {
            return Err(failure.into());
        }
        Ok(_) => {}
        Err(_) => fs::create_dir(path).map_err(|_| failure.to_owned())?,
    }
    let c_path = CString::new(path).map_err(|_| failure.to_owned())?;
    if unsafe { libc::lchown(c_path.as_ptr(), 0, 0) } != 0 {
        return Err(failure.into());
    }
    fs::set_permissions(path, fs::Permissions::from_mode(0o755)).map_err(|_| failure.to_owned())
}

fn install_runner() -> Result<(), String> {
    let failure = "native_sandbox_account_runner_install_failed";
    let current = std::env::current_exe().map_err(|_| failure.to_owned())?;
    let staging = format!("{INSTALLED_RUNNER}.new");
    let _ = fs::remove_file(&staging);
    fs::copy(&current, &staging).map_err(|_| failure.to_owned())?;
    let c_path = CString::new(staging.as_str()).map_err(|_| failure.to_owned())?;
    if unsafe { libc::lchown(c_path.as_ptr(), 0, 0) } != 0 {
        return Err(failure.into());
    }
    fs::set_permissions(&staging, fs::Permissions::from_mode(0o755))
        .map_err(|_| failure.to_owned())?;
    fs::rename(&staging, INSTALLED_RUNNER).map_err(|_| failure.to_owned())
}

/// The copy base: the owner's, closed to everyone else, searchable by the
/// account so it can reach the one copy it is granted — and list nothing.
fn create_copies(owner: u32) -> Result<(), String> {
    let failure = "native_sandbox_account_base_unsafe";
    match fs::symlink_metadata(COPIES) {
        Ok(metadata) if metadata.file_type().is_symlink() || !metadata.is_dir() => {
            return Err(failure.into());
        }
        Ok(_) => {}
        Err(_) => fs::create_dir(COPIES).map_err(|_| failure.to_owned())?,
    }
    let c_path = CString::new(COPIES).map_err(|_| failure.to_owned())?;
    if unsafe { libc::lchown(c_path.as_ptr(), owner, owner_gid(owner)?) } != 0 {
        return Err(failure.into());
    }
    fs::set_permissions(COPIES, fs::Permissions::from_mode(0o700))
        .map_err(|_| failure.to_owned())?;
    for index in 0..POOL_SIZE {
        let entry = format!("user:{} allow search", member_name(index));
        // Repeated setup must not stack duplicate entries.
        let _ = command_succeeds(CHMOD, &["-a", &entry, COPIES], failure);
        command_succeeds(CHMOD, &["+a", &entry, COPIES], failure)?;
        // One lock per account, which no account can open: it gives the
        // account to one run at a time.
        let path = member_lock(index);
        let lock = fs::OpenOptions::new()
            .create(true)
            .truncate(false)
            .write(true)
            .mode(0o600)
            .open(&path)
            .map_err(|_| failure.to_owned())?;
        drop(lock);
        let c_lock = CString::new(path).map_err(|_| failure.to_owned())?;
        if unsafe { libc::lchown(c_lock.as_ptr(), owner, owner_gid(owner)?) } != 0 {
            return Err(failure.into());
        }
    }
    Ok(())
}

pub fn sudoers_rule(owner: u32) -> String {
    let accounts = (0..POOL_SIZE)
        .map(member_name)
        .collect::<Vec<_>>()
        .join(", ");
    format!(
        "# Raiker command sandbox: written by `raiker-command-runner --setup-account`,\n\
         # removed by `--reset-account`. The owner may run exactly these two programs\n\
         # as a sandbox account, which owns nothing; never as anyone else.\n\
         Runas_Alias RAIKER_SANDBOX = {accounts}\n\
         Defaults>RAIKER_SANDBOX env_reset, !use_pty, !lecture\n\
         #{owner} ALL=(RAIKER_SANDBOX) NOPASSWD: {INSTALLED_RUNNER} --account-run *, {INSTALLED_RUNNER} --account-stop\n"
    )
}

fn write_sudoers(owner: u32) -> Result<(), String> {
    let failure = "native_sandbox_account_sudoers_failed";
    // A name containing '.' is ignored by `#includedir`, so the staging file
    // is never live, even for a moment.
    let staging = "/etc/sudoers.d/.raiker-sandbox.new";
    let _ = fs::remove_file(staging);
    let mut file = fs::OpenOptions::new()
        .create_new(true)
        .write(true)
        .mode(0o440)
        .open(staging)
        .map_err(|_| failure.to_owned())?;
    file.write_all(sudoers_rule(owner).as_bytes())
        .map_err(|_| failure.to_owned())?;
    drop(file);
    if command_succeeds(VISUDO, &["-c", "-f", staging], failure).is_err() {
        let _ = fs::remove_file(staging);
        return Err(failure.into());
    }
    fs::rename(staging, SUDOERS).map_err(|_| failure.to_owned())
}

/// The owner's one-time setup, as root. Idempotent: a repeated setup repairs
/// and refreshes the installed runner rather than duplicating anything.
pub fn setup(requested_owner: Option<u32>) -> Result<Value, String> {
    if unsafe { libc::geteuid() } != 0 {
        return Err("native_sandbox_account_setup_requires_elevation".into());
    }
    let owner = owner_uid(requested_owner)?;
    let accounts = (0..POOL_SIZE)
        .map(|index| ensure_account(&member_name(index)))
        .collect::<Result<Vec<_>, _>>()?;
    root_directory(BASE)?;
    root_directory(&format!("{BASE}/bin"))?;
    install_runner()?;
    create_copies(owner)?;
    write_sudoers(owner)?;
    Ok(json!({
        "configured": true,
        "account": ACCOUNT,
        "account_uid": accounts[0].uid,
        "accounts": accounts.iter().map(|member| json!({"name": member.name, "uid": member.uid})).collect::<Vec<_>>(),
        "owner_uid": owner,
        "base": COPIES,
        "runner": INSTALLED_RUNNER,
        "sudoers": SUDOERS,
    }))
}

/// Undo setup. The copies are left in place: they can hold changes the owner
/// has not reviewed, and the owner's access entry lets them delete them.
pub fn reset() -> Result<(), String> {
    if unsafe { libc::geteuid() } != 0 {
        return Err("native_sandbox_account_setup_requires_elevation".into());
    }
    let mut failures = Vec::new();
    // The rule goes first, so nothing new can start as the account.
    if fs::remove_file(SUDOERS).is_err() && fs::symlink_metadata(SUDOERS).is_ok() {
        failures.push("sudoers");
    }
    for index in 0..POOL_SIZE {
        let name = member_name(index);
        if lookup(&name).is_none() {
            continue;
        }
        let _ = command_succeeds(PKILL, &["-9", "-u", &name], "");
        for path in [format!("/Users/{name}"), format!("/Groups/{name}")] {
            if command_succeeds(DSCL, &[".", "-delete", &path], "").is_err() {
                failures.push("account");
            }
        }
    }
    if fs::remove_file(INSTALLED_RUNNER).is_err() && fs::symlink_metadata(INSTALLED_RUNNER).is_ok()
    {
        failures.push("runner");
    }
    let _ = fs::remove_dir(format!("{BASE}/bin"));
    if failures.is_empty() {
        Ok(())
    } else {
        Err(format!(
            "native_sandbox_account_reset_incomplete:{}",
            failures.join(",")
        ))
    }
}

// ── Owner side: one run ────────────────────────────────────────────────────

/// Machine-wide exclusive hold on one pool account, for one whole run.
struct AccountLock {
    file: fs::File,
    account: Account,
}

impl AccountLock {
    /// The first free account; waits while every one is in use.
    fn acquire(deadline: Instant) -> Result<AccountLock, String> {
        use std::os::fd::AsRawFd;
        let members = members().ok_or("native_sandbox_account_unconfigured")?;
        let mut files = Vec::with_capacity(POOL_SIZE);
        for index in 0..POOL_SIZE {
            files.push(
                fs::OpenOptions::new()
                    .read(true)
                    .write(true)
                    .open(member_lock(index))
                    .map_err(|_| "native_sandbox_account_lock_unavailable")?,
            );
        }
        let mut pool: Vec<(fs::File, Account)> = files.into_iter().zip(members).collect();
        loop {
            for index in 0..pool.len() {
                let fd = pool[index].0.as_raw_fd();
                if unsafe { libc::flock(fd, libc::LOCK_EX | libc::LOCK_NB) } == 0 {
                    let (file, account) = pool.swap_remove(index);
                    return Ok(AccountLock { file, account });
                }
            }
            if Instant::now() >= deadline {
                return Err("native_sandbox_account_busy".into());
            }
            std::thread::sleep(Duration::from_millis(50));
        }
    }
}

impl Drop for AccountLock {
    fn drop(&mut self) {
        use std::os::fd::AsRawFd;
        unsafe { libc::flock(self.file.as_raw_fd(), libc::LOCK_UN) };
    }
}

/// Every process the account owns, and nothing else, stopped by the installed
/// runner's `--account-stop` running as the account. Run before a run (a
/// crashed Raiker can leave one behind) and after it.
fn stop_account_processes(name: &str) -> Result<(), String> {
    let output = Command::new(SUDO)
        .args(["-n", "-u", name, INSTALLED_RUNNER, "--account-stop"])
        .current_dir("/")
        .stdin(std::process::Stdio::null())
        .output()
        .map_err(|_| "native_sandbox_account_stop_failed")?;
    if output.status.success() {
        return Ok(());
    }
    let detail: String = String::from_utf8_lossy(&output.stderr)
        .lines()
        .next()
        .unwrap_or("")
        .chars()
        .filter(|character| !character.is_control())
        .take(160)
        .collect();
    Err(format!(
        "native_sandbox_account_stop_failed:{}:{detail}",
        output.status.code().unwrap_or(-1)
    ))
}

/// `--account-stop`, started by `sudo` as the account.
pub fn account_stop() -> Result<i32, String> {
    let account = current_member().ok_or("native_sandbox_account_identity_mismatch")?;
    if kill_account_processes(account.uid) {
        Ok(0)
    } else {
        Err("native_sandbox_account_processes_survived".into())
    }
}

/// Kill every process of `uid` except this one and its parent, until none
/// is left. Run *as* the account, so it can signal them.
///
/// Not `kill(-1)`: measured on macOS 15 CI, that also kills the `sudo`
/// process this runs under — its monitor is signalable by the target user —
/// so the owner side saw `sudo` die by signal and could not tell a stop from
/// a failure. Listing by uid and sparing the parent keeps `sudo` alive to
/// report. Each round stops before it kills, so a process forking during
/// the round is frozen rather than racing; the per-user process limit bounds
/// how many rounds that can take.
fn kill_account_processes(uid: u32) -> bool {
    let spared = [std::process::id() as i32, unsafe { libc::getppid() }];
    for _ in 0..50 {
        let targets: Vec<i32> = account_pids(uid)
            .into_iter()
            .filter(|pid| !spared.contains(pid))
            .collect();
        if targets.is_empty() {
            return true;
        }
        for pid in &targets {
            unsafe { libc::kill(*pid, libc::SIGSTOP) };
        }
        for pid in &targets {
            unsafe { libc::kill(*pid, libc::SIGKILL) };
        }
        std::thread::sleep(Duration::from_millis(10));
    }
    account_pids(uid)
        .into_iter()
        .all(|pid| spared.contains(&pid))
}

fn account_has_processes(uid: u32) -> bool {
    !account_pids(uid).is_empty()
}

/// The account's access to one copy, taken back when dropped.
///
/// Folders get inheritable entries so what the run creates carries them;
/// existing files get a file entry. Links are skipped: `find -type` never
/// follows them, so a link a previous run planted cannot redirect a grant.
struct CopyGrant {
    root: PathBuf,
    account: String,
}

impl CopyGrant {
    fn apply(root: &Path, account: &str) -> Result<CopyGrant, String> {
        let owner = unsafe { libc::getuid() };
        let owner_name = user_name(owner).ok_or("native_sandbox_account_owner_unknown")?;
        let grant = CopyGrant {
            root: root.to_owned(),
            account: account.to_owned(),
        };
        let directory_entry = format!("user:{account} allow {ACCOUNT_DIRECTORY_RIGHTS}");
        let file_entry = format!("user:{account} allow {ACCOUNT_FILE_RIGHTS}");
        let owner_entry = format!("user:{owner_name} allow {OWNER_DIRECTORY_RIGHTS}");
        let root_text = root.to_str().ok_or("native_sandbox_account_grant_failed")?;
        let failure = "native_sandbox_account_grant_failed";
        // Owner entry first: if the account entry then fails, nothing the
        // owner cannot clean up has been created.
        command_succeeds(CHMOD, &["+a", &owner_entry, root_text], failure)?;
        command_succeeds(
            FIND,
            &[
                root_text,
                "-type",
                "d",
                "-exec",
                CHMOD,
                "+a",
                &directory_entry,
                "{}",
                "+",
            ],
            failure,
        )?;
        command_succeeds(
            FIND,
            &[
                root_text,
                "-type",
                "f",
                "-exec",
                CHMOD,
                "+a",
                &file_entry,
                "{}",
                "+",
            ],
            failure,
        )?;
        Ok(grant)
    }
}

impl Drop for CopyGrant {
    fn drop(&mut self) {
        let Some(root) = self.root.to_str() else {
            return;
        };
        let account = &self.account;
        let directory_entry = format!("user:{account} allow {ACCOUNT_DIRECTORY_RIGHTS}");
        let file_entry = format!("user:{account} allow {ACCOUNT_FILE_RIGHTS}");
        // The copy's own folder is what matters: without its entry the account
        // cannot reach anything below it. Entries on files the account itself
        // created cannot be removed by the owner, and need not be.
        let _ = command_succeeds(CHMOD, &["-a", &directory_entry, root], "");
        let _ = command_succeeds(
            FIND,
            &[
                root,
                "-mindepth",
                "1",
                "-type",
                "d",
                "-user",
                &unsafe { libc::getuid() }.to_string(),
                "-exec",
                CHMOD,
                "-a",
                &directory_entry,
                "{}",
                "+",
            ],
            "",
        );
        let _ = command_succeeds(
            FIND,
            &[
                root,
                "-type",
                "f",
                "-user",
                &unsafe { libc::getuid() }.to_string(),
                "-exec",
                CHMOD,
                "-a",
                &file_entry,
                "{}",
                "+",
            ],
            "",
        );
    }
}

fn user_name(uid: u32) -> Option<String> {
    let entry = unsafe { libc::getpwuid(uid) };
    if entry.is_null() {
        return None;
    }
    let name = unsafe { std::ffi::CStr::from_ptr((*entry).pw_name) };
    name.to_str().ok().map(str::to_owned)
}

/// What the account side needs, handed over in a file inside the copy that
/// the account side deletes before the command starts.
fn payload(policy_text: &str, argv: &[String]) -> Value {
    let environment: Vec<(String, String)> = std::env::vars().collect();
    json!({
        "policy": policy_text,
        "argv": argv,
        "environment": environment,
        "owner_pid": std::process::id(),
    })
}

/// Whether this run belongs to the account boundary: its workspace is a copy
/// in the account's base. Such a run never falls back to plain Seatbelt; if
/// the account is not set up, it is refused.
pub fn owns(policy: &LaunchPolicy) -> bool {
    policy
        .workspace_root
        .canonicalize()
        .is_ok_and(|root| root.parent() == Some(Path::new(COPIES)))
}

/// Run `argv` as the account in the copy `policy` names.
///
/// A terminal run needs nothing extra here: the runner's stdio is the
/// terminal Raiker opened, `sudo` passes it through (`!use_pty`), and the
/// account side starts the command in a session of its own.
pub fn launch(policy: &LaunchPolicy, policy_text: &str, argv: &[String]) -> Result<i32, String> {
    if status()["configured"] != true {
        return Err("native_sandbox_account_unconfigured".into());
    }
    let root = policy
        .workspace_root
        .canonicalize()
        .map_err(|_| "runner_policy_workspace_unreadable")?;
    // A copy is a direct child of the base, so its grant covers it and
    // nothing beside it.
    if root.parent() != Some(Path::new(COPIES)) {
        return Err("native_sandbox_account_workspace_outside_base".into());
    }
    let deadline = Instant::now()
        .checked_add(Duration::from_secs(policy.deadline_seconds))
        .ok_or("native_sandbox_deadline_invalid")?;
    let lock = AccountLock::acquire(deadline)?;
    let account = &lock.account;
    // Whatever a crashed run left behind is stopped before this one starts,
    // so the account's processes are only ever this run's.
    stop_account_processes(&account.name)?;
    let _grant = CopyGrant::apply(&root, &account.name)?;
    let handoff = root.join(format!(".raiker-launch-{}.json", selftest::probe_nonce()));
    let _handoff = Handoff::write(&handoff, &payload(policy_text, argv), &account.name)?;
    let mut child = Command::new(SUDO)
        .args(["-n", "-u", &account.name, INSTALLED_RUNNER, "--account-run"])
        .arg(&handoff)
        // The owner's working folder is not the account's to enter.
        .current_dir("/")
        .spawn()
        .map_err(|error| {
            format!(
                "native_sandbox_launch_failed:{}",
                error.raw_os_error().unwrap_or(0)
            )
        })?;
    let outcome = loop {
        match child.try_wait() {
            Ok(Some(status)) => break Ok(status.code().unwrap_or(1)),
            Ok(None) => {}
            Err(_) => break Err("native_sandbox_wait_failed".to_owned()),
        }
        if Instant::now() >= deadline {
            // The account side enforces the same deadline; this is the backstop
            // for an account side that stopped answering.
            let _ = stop_account_processes(&account.name);
            let _ = child.kill();
            let _ = child.wait();
            break Ok(137);
        }
        std::thread::sleep(Duration::from_millis(20));
    };
    // Every descendant, detached or not, is the account's: this is the stop.
    stop_account_processes(&account.name)?;
    if account_has_processes(account.uid) {
        return Err("native_sandbox_account_processes_survived".into());
    }
    outcome
}

struct Handoff(PathBuf);

impl Handoff {
    fn write(path: &Path, value: &Value, account: &str) -> Result<Handoff, String> {
        let failure = "native_sandbox_account_handoff_failed";
        let mut file = fs::OpenOptions::new()
            .create_new(true)
            .write(true)
            .mode(0o600)
            .open(path)
            .map_err(|_| failure.to_owned())?;
        let handoff = Handoff(path.to_owned());
        file.write_all(value.to_string().as_bytes())
            .map_err(|_| failure.to_owned())?;
        let entry = format!("user:{account} allow read,delete");
        let text = path.to_str().ok_or(failure)?;
        command_succeeds(CHMOD, &["+a", &entry, text], failure)?;
        Ok(handoff)
    }
}

impl Drop for Handoff {
    fn drop(&mut self) {
        // Normally already gone: the account side deletes it before the
        // command starts. This covers a run that never got that far.
        let _ = fs::remove_file(&self.0);
    }
}

// ── Account side ───────────────────────────────────────────────────────────

/// `--account-run <handoff>`, started by `sudo` as the account.
pub fn account_run(handoff: &Path) -> Result<i32, String> {
    let account = current_member().ok_or("native_sandbox_account_identity_mismatch")?;
    // The handoff must sit directly in a copy directly in the base.
    let copy = handoff
        .parent()
        .ok_or("native_sandbox_account_handoff_invalid")?;
    if copy.parent() != Some(Path::new(COPIES))
        || !handoff
            .file_name()
            .and_then(|name| name.to_str())
            .is_some_and(|name| name.starts_with(".raiker-launch-") && name.ends_with(".json"))
    {
        return Err("native_sandbox_account_handoff_invalid".into());
    }
    let text = fs::read_to_string(handoff).map_err(|_| "native_sandbox_account_handoff_invalid")?;
    fs::remove_file(handoff).map_err(|_| "native_sandbox_account_handoff_invalid")?;
    let value: Value =
        serde_json::from_str(&text).map_err(|_| "native_sandbox_account_handoff_invalid")?;
    let policy_text = value["policy"]
        .as_str()
        .ok_or("native_sandbox_account_handoff_invalid")?;
    let policy = crate::policy::parse(policy_text)?;
    crate::policy::validate_filesystem_paths(&policy)?;
    let root = policy
        .workspace_root
        .canonicalize()
        .map_err(|_| "runner_policy_workspace_unreadable")?;
    if root != copy {
        return Err("native_sandbox_account_workspace_outside_base".into());
    }
    let argv: Vec<String> = value["argv"]
        .as_array()
        .ok_or("native_sandbox_account_handoff_invalid")?
        .iter()
        .map(|item| item.as_str().map(str::to_owned))
        .collect::<Option<_>>()
        .ok_or("native_sandbox_account_handoff_invalid")?;
    if argv.is_empty() {
        return Err("runner_arguments_invalid".into());
    }
    let environment: Vec<(String, String)> = value["environment"]
        .as_array()
        .ok_or("native_sandbox_account_handoff_invalid")?
        .iter()
        .filter_map(|pair| {
            Some((
                pair.get(0)?.as_str()?.to_owned(),
                pair.get(1)?.as_str()?.to_owned(),
            ))
        })
        .collect();
    let owner_pid = value["owner_pid"]
        .as_u64()
        .and_then(|pid| i32::try_from(pid).ok())
        .ok_or("native_sandbox_account_handoff_invalid")?;

    let sandbox_exec = which("sandbox-exec").ok_or("native_sandbox_artifact_missing")?;
    let mut command = Command::new(sandbox_exec);
    command.args(macos_arguments(&policy, &argv)?);
    command.env_clear();
    command.envs(account_environment(environment, &account.name));
    command.current_dir(&policy.cwd);
    bound_account_child(&mut command, &policy);
    let mut child = command.spawn().map_err(|error| {
        format!(
            "native_sandbox_launch_failed:{}",
            error.raw_os_error().unwrap_or(0)
        )
    })?;
    let deadline = Instant::now()
        .checked_add(Duration::from_secs(policy.deadline_seconds))
        .ok_or("native_sandbox_deadline_invalid")?;
    loop {
        if let Ok(Some(status)) = child.try_wait() {
            return Ok(status.code().unwrap_or(1));
        }
        let over_memory = account_footprint(account.uid) > policy.max_memory_bytes;
        let owner_gone = unsafe { libc::kill(owner_pid, 0) } != 0
            && std::io::Error::last_os_error().raw_os_error() == Some(libc::ESRCH);
        if over_memory || owner_gone || Instant::now() >= deadline {
            // Every process of the account except this one and its `sudo`.
            kill_account_processes(account.uid);
            let _ = child.wait();
            if over_memory {
                let line = json!({"raiker_runner_notice": "native_sandbox_memory_limit_exceeded"});
                let _ = writeln!(std::io::stderr(), "{line}");
            }
            return Ok(137);
        }
        std::thread::sleep(SUPERVISE_INTERVAL);
    }
}

/// The run's environment, as Raiker built it, with the identity variables
/// naming the account rather than the owner.
fn account_environment(environment: Vec<(String, String)>, name: &str) -> Vec<(String, String)> {
    let mut merged: Vec<(String, String)> = environment
        .into_iter()
        .filter(|(name, _)| {
            !matches!(
                name.as_str(),
                "USER" | "LOGNAME" | "SUDO_USER" | "SUDO_UID" | "SUDO_GID" | "SUDO_COMMAND"
            )
        })
        .collect();
    merged.push(("USER".into(), name.into()));
    merged.push(("LOGNAME".into(), name.into()));
    merged
}

/// `RLIMIT_NPROC` counts per user, which is exactly one run here; CPU time is
/// per process as before. Memory is the supervisor's footprint sum.
fn bound_account_child(command: &mut Command, policy: &LaunchPolicy) {
    use std::os::unix::process::CommandExt;
    // The account side itself is one of the account's processes.
    let processes = policy.max_processes.saturating_add(1) as libc::rlim_t;
    let cpu = policy.max_cpu_seconds as libc::rlim_t;
    let terminal = policy.pty;
    unsafe {
        command.pre_exec(move || {
            for (resource, requested) in [(libc::RLIMIT_NPROC, processes), (libc::RLIMIT_CPU, cpu)]
            {
                let mut existing: libc::rlimit = std::mem::zeroed();
                if libc::getrlimit(resource, &mut existing) != 0 {
                    return Err(std::io::Error::last_os_error());
                }
                let limit = narrower_limit(&existing, requested);
                if libc::setrlimit(resource, &limit) != 0 {
                    return Err(std::io::Error::last_os_error());
                }
            }
            if terminal {
                // A session of its own, without a controlling terminal: the
                // command reads and writes the terminal it was handed, but
                // XNU refuses `TIOCSTI` from a process whose controlling
                // terminal it is not, so it cannot type into the owner's
                // input (Bubblewrap's `--new-session` on Linux).
                if libc::setsid() < 0 {
                    return Err(std::io::Error::last_os_error());
                }
            } else {
                // Its own process group, so a stray terminal signal reaches
                // the run and not this supervisor.
                libc::setpgid(0, 0);
            }
            Ok(())
        });
    }
}

fn account_pids(uid: u32) -> Vec<i32> {
    let mut pids = vec![0i32; 4096];
    let bytes = unsafe {
        libc::proc_listpids(
            PROC_UID_ONLY,
            uid,
            pids.as_mut_ptr() as *mut libc::c_void,
            (pids.len() * size_of::<i32>()) as libc::c_int,
        )
    };
    if bytes <= 0 {
        return Vec::new();
    }
    pids.truncate(bytes as usize / size_of::<i32>());
    pids.retain(|pid| *pid > 0);
    pids
}

/// The account's physical footprint: the figure Activity Monitor shows as
/// Memory, summed over every process the account has.
fn account_footprint(uid: u32) -> u64 {
    account_pids(uid)
        .into_iter()
        .map(|pid| {
            let mut info: libc::rusage_info_v2 = unsafe { std::mem::zeroed() };
            let result = unsafe {
                libc::proc_pid_rusage(
                    pid,
                    libc::RUSAGE_INFO_V2,
                    &mut info as *mut _ as *mut libc::rusage_info_t,
                )
            };
            if result == 0 {
                info.ri_phys_footprint
            } else {
                0
            }
        })
        .sum()
}

// ── Probe ──────────────────────────────────────────────────────────────────

pub fn probe() -> Value {
    match measure() {
        Ok(value) => value,
        Err(reason) => unavailable(&reason),
    }
}

fn measure() -> Result<Value, String> {
    let accounts = members().ok_or("native_sandbox_account_unconfigured")?;
    let nonce = selftest::probe_nonce();
    let scratch = Path::new(COPIES).join(&nonce);
    fs::create_dir(&scratch).map_err(|_| "native_sandbox_probe_storage_unavailable")?;
    let outcome = measure_in(&scratch, &nonce, &accounts);
    let _ = fs::remove_dir_all(&scratch);
    outcome
}

fn measure_in(scratch: &Path, nonce: &str, accounts: &[Account]) -> Result<Value, String> {
    let current = std::env::current_exe().map_err(|_| "native_sandbox_runner_unreadable")?;
    // The selftest runs inside Seatbelt, which reads only the copy and the
    // system: the runner is copied in like any program the copy holds.
    let child = scratch.join("runner");
    fs::copy(&current, &child).map_err(|_| "native_sandbox_runner_unreadable")?;
    // `.raiker` inside the copy stands for Raiker's state (masked); the
    // owner's temporary folder and home for everything outside the copy.
    let state = scratch.join(".raiker");
    fs::create_dir(&state).map_err(|_| "native_sandbox_probe_storage_unavailable")?;
    let masked = state.join("state");
    fs::write(&masked, b"raiker-probe-state")
        .map_err(|_| "native_sandbox_probe_storage_unavailable")?;
    let mut outside_paths = vec![Path::new(COPIES).join(format!(".{nonce}-escape.tmp"))];
    if let Some(home) = user_home(unsafe { libc::getuid() }) {
        outside_paths.push(home.join(format!(".{nonce}-escape.tmp")));
    }
    // A listener on this host's own outward address answers the outside arm
    // on any network; held open until both arms have run.
    let listener = local_listener();
    let connect_address = listener
        .as_ref()
        .map(|(_, address)| address.clone())
        .unwrap_or_else(probe_destination);
    let test = SelfTest {
        nonce: nonce.to_owned(),
        inside_path: scratch.join(format!(".{nonce}-inside.tmp")),
        outside_paths,
        masked_read_path: masked.clone(),
        connect_address,
        spawn_grandchild: true,
        hold_for_probe: false,
        loopback_address: None,
    };
    let outside = selftest::attempt(&test);
    selftest::remove_probe_writes(&test);
    let policy = json!({
        "workspace_root": scratch, "cwd": scratch,
        "deny_paths": [".raiker"], "readonly_paths": [".git"],
        "profile_name": format!("raiker.probe.{}", std::process::id()),
        "deadline_seconds": 60, "max_processes": 32,
    })
    .to_string();
    let parsed = crate::policy::parse(&policy)?;
    let argv = vec![
        child.to_string_lossy().into_owned(),
        "--selftest".to_owned(),
        test.to_value().to_string(),
    ];
    // Through the real launch path, stdout captured.
    let output = launch_captured(&parsed, &policy, &argv)?;
    drop(listener);
    selftest::remove_probe_writes(&test);
    let inside: Value = String::from_utf8_lossy(&output)
        .lines()
        .find_map(|line| serde_json::from_str(line).ok())
        .ok_or("native_sandbox_probe_no_output")?;
    let relay = inside.get("nonce").and_then(Value::as_str) == Some(nonce);
    let inside_write = allowed(&inside, "inside_write");
    let escape = folded_escape(&inside, &outside);
    let masked_read = selftest::verdict(
        allowed(&inside, "masked_read"),
        allowed(&outside, "masked_read"),
    );
    let network = selftest::verdict(reached(&inside), reached(&outside));
    // The run is over: a descendant still alive escaped it.
    let descendant = match inside.get("descendant_pid").and_then(Value::as_u64) {
        Some(pid) => descendant_verdict(pid as i32, accounts),
        None => "indeterminate",
    };
    let enforced = relay
        && inside_write
        && escape == "enforced"
        && masked_read == "enforced"
        && network == "enforced"
        && descendant == "enforced";
    Ok(json!({
        "platform": "macos",
        "boundary": "macos_account",
        "available": false,
        "reason": if enforced { "native_disposable_workspace_required" } else { "native_sandbox_not_enforced" },
        "network": network,
        "process_tree_stop": descendant == "enforced",
        "resource_limits": "account_footprint",
        "descendant_start": inside.get("descendant_start"),
        "pty": false,
        "concurrent_runs": false,
        "observations": {
            "relay": if relay { "enforced" } else { "unenforced" },
            "workspace_write": if inside_write { "enforced" } else { "unenforced" },
            "escape_write": escape,
            "masked_read": masked_read,
            "egress": network,
            "descendant_reaped": descendant,
        },
        "connect_destination": test.connect_address,
        "account_base": COPIES,
    }))
}

/// [`launch`] with the command's stdout returned instead of relayed.
fn launch_captured(
    policy: &LaunchPolicy,
    policy_text: &str,
    argv: &[String],
) -> Result<Vec<u8>, String> {
    // The probe re-enters this runner's own launch mode, so its stdout can be
    // captured without a second code path through the boundary.
    let current = std::env::current_exe().map_err(|_| "native_sandbox_runner_unreadable")?;
    let file = policy.workspace_root.join(".raiker").join("policy.json");
    fs::write(&file, policy_text).map_err(|_| "native_sandbox_probe_storage_unavailable")?;
    let output = Command::new(current)
        .arg("--policy")
        .arg(&file)
        .arg("--")
        .args(argv)
        .stdin(std::process::Stdio::null())
        .output()
        .map_err(|_| "native_sandbox_probe_failed")?;
    let _ = fs::remove_file(&file);
    Ok(output.stdout)
}

fn user_home(uid: u32) -> Option<PathBuf> {
    let entry = unsafe { libc::getpwuid(uid) };
    if entry.is_null() {
        return None;
    }
    let home = unsafe { std::ffi::CStr::from_ptr((*entry).pw_dir) };
    home.to_str().ok().map(PathBuf::from)
}

/// After the run: `ESRCH` means the descendant is gone. `EPERM` means a
/// process exists that the owner may not signal — the account's, since the
/// pid was the account's descendant a moment ago — so containment failed.
fn descendant_verdict(pid: i32, accounts: &[Account]) -> &'static str {
    let end = Instant::now() + Duration::from_secs(5);
    loop {
        if unsafe { libc::kill(pid, 0) } != 0
            && std::io::Error::last_os_error().raw_os_error() == Some(libc::ESRCH)
        {
            return "enforced";
        }
        if Instant::now() >= end {
            break;
        }
        std::thread::sleep(Duration::from_millis(50));
    }
    // The probe ran as whichever account was free: any of them still holding
    // the descendant means containment failed.
    if let Some(holder) = accounts
        .iter()
        .find(|account| account_pids(account.uid).contains(&pid))
    {
        let _ = stop_account_processes(&holder.name);
        "unenforced"
    } else {
        // Reused by someone else's process: not proof either way.
        "indeterminate"
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_sudoers_rule_names_only_the_account_and_two_programs() {
        let rule = sudoers_rule(501);
        let grants: Vec<&str> = rule
            .lines()
            .filter(|line| !line.starts_with('#') || line.starts_with("#501"))
            .collect();
        assert_eq!(
            grants,
            [
                "Runas_Alias RAIKER_SANDBOX = \
                 _raikersandbox, _raikersandbox1, _raikersandbox2, _raikersandbox3",
                "Defaults>RAIKER_SANDBOX env_reset, !use_pty, !lecture",
                "#501 ALL=(RAIKER_SANDBOX) NOPASSWD: \
                 /Library/RaikerSandbox/bin/raiker-command-runner --account-run *, \
                 /Library/RaikerSandbox/bin/raiker-command-runner --account-stop",
            ]
        );
        assert!(!rule.contains("(ALL)") && !rule.contains("root"));
    }

    #[test]
    fn a_free_id_is_unused_by_any_user_or_group() {
        let users = parse_id_list("_www 70\nnobody -2\n_raikerold 400\n");
        let groups = parse_id_list("staff 20\n_other 401\n");
        assert_eq!(free_id(&users, &groups), Some(402));
        let full: Vec<u32> = ID_RANGE.collect();
        assert_eq!(free_id(&full, &[]), None);
    }

    #[test]
    fn the_account_environment_names_the_account_not_the_owner() {
        let merged = account_environment(
            vec![
                ("USER".into(), "owner".into()),
                ("SUDO_UID".into(), "501".into()),
                ("PATH".into(), "/usr/bin".into()),
            ],
            "_raikersandbox2",
        );
        assert!(merged.contains(&("USER".into(), "_raikersandbox2".into())));
        assert!(merged.contains(&("PATH".into(), "/usr/bin".into())));
        assert!(
            !merged
                .iter()
                .any(|(name, value)| name == "USER" && value == "owner")
        );
        assert!(!merged.iter().any(|(name, _)| name == "SUDO_UID"));
    }

    #[test]
    fn the_pool_keeps_the_original_account_first_and_names_each_lock() {
        assert_eq!(member_name(0), ACCOUNT);
        assert_eq!(member_name(3), "_raikersandbox3");
        let mut locks: Vec<String> = (0..POOL_SIZE).map(member_lock).collect();
        assert_eq!(locks[0], format!("{COPIES}/.account.lock"));
        locks.sort();
        locks.dedup();
        assert_eq!(locks.len(), POOL_SIZE);
    }
}
