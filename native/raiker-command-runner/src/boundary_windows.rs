//! The Windows boundary: an AppContainer, one capability grant, and a Job Object.
//!
//! Three mechanisms, because they answer three separate questions.
//!
//! * **AppContainer** answers *what may this process reach off-machine*. A
//!   profile launched with **no network capability** holds neither
//!   `internetClient` nor `internetClientServer`, and the Windows Filtering
//!   Platform drops its egress. That enforcement is applied by the Windows
//!   Defender Firewall service — with the service stopped it is not applied at
//!   all, which is why [`probe`] measures egress instead of asserting it.
//! * **One capability grant** answers *what may it reach in the filesystem*. An
//!   AppContainer SID has no rights anywhere except what `ALL APPLICATION
//!   PACKAGES` already grants — read and execute under `%SystemRoot%` and
//!   `%ProgramFiles%`, which is what lets a system binary start at all. Raiker
//!   grants the workspace **once** to a capability derived from a stable name,
//!   and every per-run container carries that capability.
//! * **The Job Object** answers *what happens to its children*. Descendants
//!   join the job, killing the job kills the tree, and the job dies with this
//!   process.
//!
//! Two things are deliberately *not* done per run. The profile is per run — a
//! predictable container name would let any local process enter a container the
//! workspace already trusts. The **grant** is not: an inheritable ACE rewrites
//! the security descriptor of every file in the repository, so doing it twice
//! per command would race the command that is writing in it and would leave the
//! grant behind whenever a runner was killed between the two writes.
//!
//! Granting a capability is acceptable for one reason, and it is worth being
//! precise about which: not because a capability SID is unforgeable — it is
//! derived from its name, so any local process can request it — but because
//! such a process already runs as the owner, already holds the owner's token,
//! and therefore already has the workspace. The ACE grants nothing beyond the
//! ambient authority.
//!
//! Nothing here falls back. Every failure is a named reason the runtime can
//! show, because a boundary that silently degraded to host execution would be
//! worse than one that refused.

use crate::policy::{LaunchPolicy, NetworkPolicy};
use crate::selftest::{self, SelfTest};
use serde_json::{Value, json};
use std::ffi::c_void;
use std::fs::File;
use std::io::Write;
use std::os::windows::io::{FromRawHandle, RawHandle};
use std::path::{Path, PathBuf};
use std::ptr::{null, null_mut};

use windows_sys::Win32::Foundation::{
    CloseHandle, ERROR_ALREADY_EXISTS, GENERIC_ALL, HANDLE, HLOCAL, LocalFree, WAIT_OBJECT_0,
    WAIT_TIMEOUT,
};
use windows_sys::Win32::Security::Authorization::{
    ConvertSidToStringSidW, ConvertStringSecurityDescriptorToSecurityDescriptorW,
    ConvertStringSidToSidW, DENY_ACCESS, EXPLICIT_ACCESS_W, GetNamedSecurityInfoW,
    NO_MULTIPLE_TRUSTEE, REVOKE_ACCESS, SDDL_REVISION_1, SE_FILE_OBJECT, SET_ACCESS,
    SetEntriesInAclW, SetNamedSecurityInfoW, TRUSTEE_IS_SID, TRUSTEE_IS_UNKNOWN, TRUSTEE_W,
};
use windows_sys::Win32::Security::DeriveCapabilitySidsFromName;
use windows_sys::Win32::Security::Isolation::{
    CreateAppContainerProfile, DeleteAppContainerProfile, DeriveAppContainerSidFromAppContainerName,
};
use windows_sys::Win32::Security::{
    ACCESS_ALLOWED_ACE, ACL, CONTAINER_INHERIT_ACE, DACL_SECURITY_INFORMATION, EqualSid, GetAce,
    GetSecurityDescriptorControl, GetTokenInformation, INHERITED_ACE, OBJECT_INHERIT_ACE,
    PSECURITY_DESCRIPTOR, PSID, SECURITY_ATTRIBUTES, SECURITY_CAPABILITIES, SID_AND_ATTRIBUTES,
    TOKEN_QUERY, TOKEN_USER, TokenUser,
};
use windows_sys::Win32::Storage::FileSystem::{
    FILE_GENERIC_EXECUTE, FILE_GENERIC_READ, FILE_GENERIC_WRITE,
};
use windows_sys::Win32::System::JobObjects::{
    AssignProcessToJobObject, CreateJobObjectW, IsProcessInJob, JOB_OBJECT_LIMIT_ACTIVE_PROCESS,
    JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION, JOB_OBJECT_LIMIT_JOB_MEMORY,
    JOB_OBJECT_LIMIT_JOB_TIME, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION, JobObjectExtendedLimitInformation,
    SetInformationJobObject,
};
use windows_sys::Win32::System::Pipes::CreatePipe;
use windows_sys::Win32::System::Threading::{
    CREATE_SUSPENDED, CreateProcessW, DeleteProcThreadAttributeList, EXTENDED_STARTUPINFO_PRESENT,
    GetCurrentProcess, GetExitCodeProcess, INFINITE, InitializeProcThreadAttributeList,
    OpenProcess, OpenProcessToken, PROCESS_INFORMATION, ResumeThread, STARTF_USESTDHANDLES,
    STARTUPINFOEXW, TerminateProcess, UpdateProcThreadAttribute, WaitForSingleObject,
};

const PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES: usize = 0x0002_0009;
const PROC_THREAD_ATTRIBUTE_HANDLE_LIST: usize = 0x0002_0002;
const HANDLE_FLAG_INHERIT: u32 = 0x0000_0001;
/// `SE_GROUP_ENABLED`, which windows-sys exposes only under `SystemServices`.
const SID_ATTRIBUTE_ENABLED: u32 = 4;
/// `PROTECTED_DACL_SECURITY_INFORMATION`. Setting it converts the object's
/// inherited entries into explicit ones and stops inheritance at that object.
const PROTECTED_DACL: u32 = 0x8000_0000;
const ACE_TYPE_ALLOWED: u8 = 0;
const ACE_TYPE_DENIED: u8 = 1;
// File write/append/EA/attribute, delete-child, delete, WRITE_DAC, WRITE_OWNER.
const READONLY_DENY_MASK: u32 = 0x000d_0156;
// READONLY_DENY_MASK plus GENERIC_WRITE and GENERIC_ALL.
const WRITE_LIKE: u32 = 0x500d_0156;
const SYNCHRONIZE_RIGHT: u32 = 0x0010_0000;
const DELETE_RIGHT: u32 = 0x0001_0000;
const FILE_DELETE_CHILD_RIGHT: u32 = 0x0000_0040;

unsafe extern "system" {
    fn SetHandleInformation(handle: HANDLE, mask: u32, flags: u32) -> i32;
}

#[path = "account_windows.rs"]
pub mod account;

// ---------------------------------------------------------------------------
// Public entry points
// ---------------------------------------------------------------------------

/// Measure what this host actually enforces, against the real workspace.
///
/// Every observation is taken twice — once inside the boundary and once outside
/// it — because a refusal on its own is not evidence. An air-gapped host refuses
/// to connect; a read-only target refuses to be written. Only *outside
/// succeeded and inside failed* means the boundary did something.
pub fn probe(workspace: &Path) -> Value {
    // Once the owner has set up the restricted account, that is the boundary
    // Windows builds run in, so it is the one measured.
    if account::status()["configured"] == true {
        return account::probe();
    }
    probe_appcontainer(workspace)
}

/// The AppContainer measurement, regardless of account setup.
pub fn probe_appcontainer(workspace: &Path) -> Value {
    let workspace = match workspace.canonicalize() {
        Ok(path) => strip_verbatim(&path),
        Err(_) => return unavailable("native_sandbox_workspace_unreadable"),
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
    let test = SelfTest {
        nonce: nonce.clone(),
        inside_path: workspace.join(format!(".{nonce}-inside.tmp")),
        outside_paths: outside_targets(&workspace, &nonce),
        masked_read_path: scratch.join("state"),
        connect_address: probe_destination(),
        spawn_grandchild: true,
        hold_for_probe: false,
    };
    if std::fs::write(&test.masked_read_path, b"raiker-probe-state").is_err() {
        let _ = std::fs::remove_dir(&scratch);
        return unavailable("native_sandbox_probe_storage_unavailable");
    }

    // The control arm. Whatever the boundary does, these are what this token
    // can do without one.
    let outside = selftest::attempt(&test);
    let inside = run_inside(&workspace, &test);
    let _ = std::fs::remove_file(&test.masked_read_path);
    let _ = std::fs::remove_dir(&scratch);
    selftest::remove_probe_writes(&test);
    let inside = match inside {
        Ok(value) => value,
        Err(reason) => return unavailable(&reason),
    };

    let relay = inside.get("nonce").and_then(Value::as_str) == Some(test.nonce.as_str());
    let inside_write = allowed(&inside, "inside_write");
    let escape = folded_escape(&inside, &outside);
    let masked = selftest::verdict(
        allowed(&inside, "masked_read"),
        allowed(&outside, "masked_read"),
    );
    let network = selftest::verdict(reached(&inside), reached(&outside));
    let descendant = match inside.get("descendant_reaped").and_then(Value::as_str) {
        Some("enforced") if relay => "enforced",
        Some("unenforced") if relay => "unenforced",
        _ => "indeterminate",
    };

    json!({
        "platform": "windows",
        "boundary": "appcontainer",
        // The current broker passes the original workspace to the runner.
        // Do not expose an executable boundary until disposable workspaces
        // prevent autonomous code from writing directly to the owner's files.
        "available": false,
        "reason": if relay && inside_write && escape == "enforced"
            && masked == "enforced" && network == "enforced" && descendant == "enforced" {
            "native_disposable_workspace_required"
        } else {
            "native_sandbox_not_enforced"
        },
        "network": network,
        "process_tree_stop": descendant == "enforced",
        "descendant_start": inside.get("descendant_start"),
        "pty": false,
        "concurrent_runs": false,
        "observations": {
            "relay": if relay { "enforced" } else { "unenforced" },
            "workspace_write": if inside_write { "enforced" } else { "unenforced" },
            "escape_write": escape,
            "masked_read": masked,
            "egress": network,
            "descendant_reaped": descendant,
        },
        "connect_destination": test.connect_address,
    })
}

/// Run one governed command inside the boundary and relay its streams.
pub fn launch(policy: &LaunchPolicy, argv: &[String]) -> Result<i32, String> {
    if policy.pty {
        return Err("native_sandbox_pty_unsupported".into());
    }
    if policy.network != NetworkPolicy::Denied {
        // Reaching a loopback proxy from an AppContainer needs a loopback
        // exemption, which needs elevation. Claiming filtered egress without
        // that is exactly the kind of green row this boundary exists to avoid.
        return Err("filtered_egress_windows_unsupported".into());
    }
    // Task copies under the restricted account's base run as that account,
    // where ordinary toolchains work; anything else keeps the AppContainer.
    if let Ok(base) = account::base()
        && strip_verbatim(&policy.workspace_root).starts_with(&base)
    {
        return account::launch(policy, argv);
    }
    let capability = Capability::derive(&capability_name(&policy.workspace_root))?;
    ensure_workspace_grant(policy, &capability)?;
    let container = AppContainer::create(&policy.profile_name)?;
    let outcome = run_in_container(policy, argv, &capability, &container);
    container.delete();
    outcome
}

// ---------------------------------------------------------------------------
// Boundary construction
// ---------------------------------------------------------------------------

fn run_in_container(
    policy: &LaunchPolicy,
    argv: &[String],
    capability: &Capability,
    container: &AppContainer,
) -> Result<i32, String> {
    let owner = current_user_sid_text()?;
    let descriptor = PipeDescriptor::build(&owner, &container.text)?;
    let stdin = Pipe::create(&descriptor, PipeEnd::Write)?;
    let stdout = Pipe::create(&descriptor, PipeEnd::Read)?;
    let stderr = Pipe::create(&descriptor, PipeEnd::Read)?;

    let job = create_job(policy)?;
    let information = match start_process(
        policy,
        argv,
        capability,
        container,
        [stdin.child, stdout.child, stderr.child],
    ) {
        Ok(information) => information,
        Err(reason) => {
            unsafe { CloseHandle(job) };
            return Err(reason);
        }
    };
    assign_and_resume(job, &information)?;

    // The parent must let go of the child's ends or the reader threads never
    // see end-of-file and the command appears to hang after it has exited.
    stdin.close_child();
    stdout.close_child();
    stderr.close_child();

    // Handles cross the thread boundary as integers: a raw pointer is not
    // `Send`, and a marker wrapper would hide that these three are the only
    // handles the pumps ever touch.
    let out = pump(stdout.parent as usize, true);
    let err = pump(stderr.parent as usize, false);
    let stdin_parent = stdin.parent as usize;
    std::thread::spawn(move || {
        let mut sink = unsafe { File::from_raw_handle(stdin_parent as RawHandle) };
        let _ = std::io::copy(&mut std::io::stdin(), &mut sink);
    });

    // Closing the job kills descendants both on normal completion and timeout.
    // Do this before joining the output pumps: descendants can hold pipes open.
    let timeout_ms = (policy.deadline_seconds * 1000) as u32;
    let wait = wait_and_close_job(job, information.hProcess, timeout_ms);
    let _ = out.join();
    let _ = err.join();
    let mut code: u32 = 0;
    let got_exit = unsafe { GetExitCodeProcess(information.hProcess, &mut code) };
    unsafe { CloseHandle(information.hProcess) };
    if wait == WAIT_TIMEOUT {
        return Err("native_sandbox_deadline_exceeded".into());
    }
    if wait != WAIT_OBJECT_0 || got_exit == 0 {
        return Err("native_sandbox_wait_failed".into());
    }
    Ok(code as i32)
}

fn wait_and_close_job(job: HANDLE, process: HANDLE, timeout_ms: u32) -> u32 {
    let wait = unsafe { WaitForSingleObject(process, timeout_ms) };
    unsafe { CloseHandle(job) };
    if wait != WAIT_OBJECT_0 {
        unsafe { WaitForSingleObject(process, INFINITE) };
    }
    wait
}

fn start_process(
    policy: &LaunchPolicy,
    argv: &[String],
    capability: &Capability,
    container: &AppContainer,
    handles: [HANDLE; 3],
) -> Result<PROCESS_INFORMATION, String> {
    let mut attributes: Vec<SID_AND_ATTRIBUTES> = capability
        .token_sids
        .iter()
        .map(|sid| SID_AND_ATTRIBUTES {
            Sid: *sid,
            Attributes: SID_ATTRIBUTE_ENABLED,
        })
        .collect();
    let mut capabilities = SECURITY_CAPABILITIES {
        AppContainerSid: container.raw,
        Capabilities: attributes.as_mut_ptr(),
        CapabilityCount: attributes.len() as u32,
        Reserved: 0,
    };

    let mut attribute_size: usize = 0;
    unsafe { InitializeProcThreadAttributeList(null_mut(), 2, 0, &mut attribute_size) };
    let mut storage = vec![0u8; attribute_size];
    let list = storage.as_mut_ptr() as *mut c_void;
    if unsafe { InitializeProcThreadAttributeList(list, 2, 0, &mut attribute_size) } == 0 {
        return Err("native_sandbox_attribute_list_failed".into());
    }
    let updated = unsafe {
        UpdateProcThreadAttribute(
            list,
            0,
            PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES,
            &mut capabilities as *mut _ as *mut c_void,
            size_of::<SECURITY_CAPABILITIES>(),
            null_mut(),
            null(),
        )
    };
    if updated == 0 {
        unsafe { DeleteProcThreadAttributeList(list) };
        return Err("native_sandbox_appcontainer_unavailable".into());
    }
    let handles_updated = unsafe {
        UpdateProcThreadAttribute(
            list,
            0,
            PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
            handles.as_ptr() as *const c_void,
            size_of::<[HANDLE; 3]>(),
            null_mut(),
            null(),
        )
    };
    if handles_updated == 0 {
        unsafe { DeleteProcThreadAttributeList(list) };
        return Err("native_sandbox_handle_list_failed".into());
    }

    let mut startup: STARTUPINFOEXW = unsafe { std::mem::zeroed() };
    startup.StartupInfo.cb = size_of::<STARTUPINFOEXW>() as u32;
    startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES;
    startup.StartupInfo.hStdInput = handles[0];
    startup.StartupInfo.hStdOutput = handles[1];
    startup.StartupInfo.hStdError = handles[2];
    startup.lpAttributeList = list;

    let mut command_line = wide(&command_line_for(argv));
    let directory = wide(&policy.cwd.to_string_lossy());
    let mut environment = wide_environment(container);
    let mut information: PROCESS_INFORMATION = unsafe { std::mem::zeroed() };
    let created = unsafe {
        CreateProcessW(
            null(),
            command_line.as_mut_ptr(),
            null(),
            null(),
            1,
            EXTENDED_STARTUPINFO_PRESENT | CREATE_SUSPENDED | 0x0000_0400,
            environment.as_mut_ptr() as *const c_void,
            directory.as_ptr(),
            &startup.StartupInfo,
            &mut information,
        )
    };
    unsafe { DeleteProcThreadAttributeList(list) };
    if created == 0 {
        let code = std::io::Error::last_os_error().raw_os_error().unwrap_or(0);
        // ERROR_ACCESS_DENIED means the container cannot read the executable —
        // an interpreter under the user profile, typically. That is real and
        // correctable, so it gets its own reason rather than a generic failure.
        return Err(if code == 5 {
            "native_sandbox_executable_unreachable".into()
        } else {
            format!("native_sandbox_launch_failed:{code}")
        });
    }
    Ok(information)
}

fn pump(handle: usize, to_stdout: bool) -> std::thread::JoinHandle<()> {
    std::thread::spawn(move || {
        let mut source = unsafe { File::from_raw_handle(handle as RawHandle) };
        if to_stdout {
            let mut sink = std::io::stdout();
            let _ = std::io::copy(&mut source, &mut sink);
            let _ = sink.flush();
        } else {
            let mut sink = std::io::stderr();
            let _ = std::io::copy(&mut source, &mut sink);
            let _ = sink.flush();
        }
    })
}

/// `CREATE_UNICODE_ENVIRONMENT` is set above, so this block is UTF-16.
///
/// `TEMP`/`TMP` point at the container's own package directory. Most toolchains
/// fail outright without a writable temp, and the alternative — a temp inside
/// the workspace — would drop build scratch into the owner's repository.
fn wide_environment(container: &AppContainer) -> Vec<u16> {
    let temp = container.package_directory();
    let _ = std::fs::create_dir_all(&temp);
    let mut entries: Vec<(String, String)> = std::env::vars()
        .filter(|(name, value)| {
            // An entry whose value is empty writes `NAME=` followed by the NUL
            // that also terminates the block, and `CreateProcessW` answers that
            // with ERROR_ENVVAR_NOT_FOUND rather than with anything that names
            // the real problem. Raiker's constructed environment contains one
            // such variable by design (`GIT_ASKPASS=`), so this is not a
            // hypothetical.
            !name.is_empty() && !value.is_empty() && !name.starts_with('=')
        })
        .filter(|(name, _)| !matches!(name.to_ascii_uppercase().as_str(), "TEMP" | "TMP"))
        .collect();
    entries.push(("TEMP".to_owned(), temp.to_string_lossy().into_owned()));
    entries.push(("TMP".to_owned(), temp.to_string_lossy().into_owned()));
    // A Unicode environment block must be sorted case-insensitively by name.
    entries.sort_by_key(|(name, _)| name.to_uppercase());

    let mut block: Vec<u16> = Vec::new();
    for (name, value) in entries {
        block.extend(wide(&format!("{name}={value}")));
    }
    block.push(0);
    block
}

// The process is created suspended. Never resume it without job containment,
// and terminate it on every failure so a suspended process cannot leak.
fn assign_and_resume(job: HANDLE, information: &PROCESS_INFORMATION) -> Result<(), String> {
    if unsafe { AssignProcessToJobObject(job, information.hProcess) } == 0 {
        unsafe { TerminateProcess(information.hProcess, 1) };
        unsafe { CloseHandle(information.hThread) };
        unsafe { CloseHandle(information.hProcess) };
        unsafe { CloseHandle(job) };
        return Err("native_sandbox_job_object_failed".into());
    }
    if unsafe { ResumeThread(information.hThread) } == u32::MAX {
        unsafe { TerminateProcess(information.hProcess, 1) };
        unsafe { CloseHandle(information.hThread) };
        unsafe { CloseHandle(information.hProcess) };
        unsafe { CloseHandle(job) };
        return Err("native_sandbox_resume_failed".into());
    }
    unsafe { CloseHandle(information.hThread) };
    Ok(())
}

fn create_job(policy: &LaunchPolicy) -> Result<HANDLE, String> {
    let job = unsafe { CreateJobObjectW(null(), null()) };
    if job.is_null() {
        return Err("native_sandbox_job_object_failed".into());
    }
    let mut limits: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = unsafe { std::mem::zeroed() };
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        | JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION
        | JOB_OBJECT_LIMIT_ACTIVE_PROCESS
        | JOB_OBJECT_LIMIT_JOB_MEMORY
        | JOB_OBJECT_LIMIT_JOB_TIME;
    limits.BasicLimitInformation.PerJobUserTimeLimit = (policy.max_cpu_seconds * 10_000_000) as i64;
    limits.BasicLimitInformation.ActiveProcessLimit = policy.max_processes;
    limits.JobMemoryLimit = policy.max_memory_bytes as usize;
    let set = unsafe {
        SetInformationJobObject(
            job,
            JobObjectExtendedLimitInformation,
            &mut limits as *mut _ as *const c_void,
            size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
        )
    };
    if set == 0 {
        unsafe { CloseHandle(job) };
        return Err("native_sandbox_job_object_failed".into());
    }
    Ok(job)
}

// ---------------------------------------------------------------------------
// The capability and the workspace grant
// ---------------------------------------------------------------------------

struct Capability {
    /// Named by the resource's DACL: the `S-1-15-3-…` capability SID.
    dacl_sid: PSID,
    /// Carried by the launching token.
    token_sids: Vec<PSID>,
    /// Kept for diagnostics only; see `derive`.
    _group_sid: PSID,
}

impl Capability {
    /// `DeriveCapabilitySidsFromName` returns two arrays, and putting them the
    /// wrong way round fails *silently*: the launch succeeds and every file
    /// access is denied.
    ///
    /// An AppContainer access check is not an ordinary one. Beyond the usual
    /// group match it additionally requires the DACL to name the package SID,
    /// `ALL APPLICATION PACKAGES`, `ALL RESTRICTED APPLICATION PACKAGES`, or
    /// one of the token's `S-1-15-3-…` capability SIDs. A grant to the
    /// `S-1-5-32-…` group SID alone can satisfy the ordinary check and still
    /// fail that restriction — so the resource is granted to the capability
    /// SID, and the token receives both.
    fn derive(name: &str) -> Result<Capability, String> {
        let wide_name = wide(name);
        let mut group_sids: *mut PSID = null_mut();
        let mut group_count: u32 = 0;
        let mut sids: *mut PSID = null_mut();
        let mut count: u32 = 0;
        let derived = unsafe {
            DeriveCapabilitySidsFromName(
                wide_name.as_ptr(),
                &mut group_sids,
                &mut group_count,
                &mut sids,
                &mut count,
            )
        };
        if derived == 0 || group_count == 0 || count == 0 {
            return Err("native_sandbox_capability_unavailable".into());
        }
        Ok(Capability {
            dacl_sid: unsafe { *sids },
            token_sids: vec![unsafe { *sids }],
            _group_sid: unsafe { *group_sids },
        })
    }
}

/// The capability name is derived from the workspace path so two workspaces
/// never share a grant, and is stable so the expensive one-time propagation
/// happens once.
fn capability_name(workspace: &Path) -> String {
    let text = workspace.to_string_lossy().to_lowercase();
    let mut hash: u64 = 0xcbf2_9ce4_8422_2325;
    for byte in text.as_bytes() {
        hash ^= u64::from(*byte);
        hash = hash.wrapping_mul(0x0000_0100_0000_01b3);
    }
    format!("raikerWorkspace{hash:016x}")
}

/// Establish, and on every launch re-verify, the filesystem shape of the
/// boundary.
///
/// The workspace grant is written once — it is inheritable, so applying it
/// rewrites the security descriptor of every file in the repository, which is
/// not something to do twice per command. The **protected paths** are checked
/// every launch, because what keeps `.raiker` out of reach is an *explicit* ACE
/// on `.raiker` itself (an explicit ACE is evaluated before an inherited one),
/// and that is state which drifts: a `.raiker` created after setup, or deleted
/// and recreated, carries only the inherited allow.
fn ensure_workspace_grant(policy: &LaunchPolicy, capability: &Capability) -> Result<(), String> {
    // Protected paths first, and their DACLs are **protected** — inheritance is
    // stopped at the object.
    //
    // Relying on ACE ordering here does not work. Both the workspace allow and
    // the `.raiker` deny are inheritable, so a file underneath `.raiker` ends up
    // holding two *inherited* entries whose order is decided by the order the
    // two parents were written in, not by which parent is nearer. Measured on a
    // real workspace, the allow landed first and the sandboxed child read
    // Raiker's own state. Protecting the DACL removes the question: `.raiker`
    // and `.git` inherit nothing, so what they say is the whole answer.
    for relative in &policy.deny_paths {
        let path = policy.workspace_root.join(relative);
        if path.exists() && !deny_ace_is_safe(&path, capability.dacl_sid)? {
            set_entry(&path, capability.dacl_sid, 0, REVOKE_ACCESS, true)?;
            set_entry(&path, capability.dacl_sid, GENERIC_ALL, DENY_ACCESS, true)?;
            if !deny_ace_is_safe(&path, capability.dacl_sid)? {
                return Err("native_sandbox_deny_acl_unverified".into());
            }
        }
    }
    for relative in &policy.readonly_paths {
        let path = policy.workspace_root.join(relative);
        if path.exists() && !readonly_ace_is_safe(&path, capability.dacl_sid)? {
            set_entry(&path, capability.dacl_sid, 0, REVOKE_ACCESS, true)?;
            set_entry(
                &path,
                capability.dacl_sid,
                FILE_GENERIC_READ | FILE_GENERIC_EXECUTE,
                SET_ACCESS,
                true,
            )?;
            set_entry(
                &path,
                capability.dacl_sid,
                READONLY_DENY_MASK,
                DENY_ACCESS,
                true,
            )?;
            if !readonly_ace_is_safe(&path, capability.dacl_sid)? {
                return Err("native_sandbox_readonly_acl_unverified".into());
            }
        }
    }
    // The capability deny above does not bind a grant made to every package:
    // Windows ignores capability SIDs in deny entries during the AppContainer
    // check, so `ALL APPLICATION PACKAGES:(M)` on `.git` was measured to let the
    // sandbox write there. Such a path cannot be protected; refuse the launch.
    for (relative, rights) in policy
        .deny_paths
        .iter()
        .map(|path| (path, !SYNCHRONIZE_RIGHT))
        .chain(policy.readonly_paths.iter().map(|path| (path, WRITE_LIKE)))
    {
        let path = policy.workspace_root.join(relative);
        if path.exists() && granted_to_all_packages(&path, rights)? {
            return Err("native_sandbox_protected_path_shared_with_app_packages".into());
        }
    }
    if !has_explicit_ace(
        &policy.workspace_root,
        capability.dacl_sid,
        ACE_TYPE_ALLOWED,
    )? {
        // DELETE and FILE_DELETE_CHILD: toolchains write atomically by
        // rename, which needs delete on the source. The broker only ever
        // passes a disposable task copy here, never the owner's project.
        set_entry(
            &policy.workspace_root,
            capability.dacl_sid,
            FILE_GENERIC_READ
                | FILE_GENERIC_WRITE
                | FILE_GENERIC_EXECUTE
                | DELETE_RIGHT
                | FILE_DELETE_CHILD_RIGHT,
            SET_ACCESS,
            false,
        )?;
    }
    // The runner launches itself as the probe's child, so the container has to
    // be able to read this binary. It lives in Raiker's own install directory,
    // never in the owner's data.
    if let Ok(current) = std::env::current_exe()
        && let Some(directory) = current.parent()
        && !has_explicit_ace(directory, capability.dacl_sid, ACE_TYPE_ALLOWED)?
    {
        set_entry(
            directory,
            capability.dacl_sid,
            FILE_GENERIC_READ | FILE_GENERIC_EXECUTE,
            SET_ACCESS,
            false,
        )?;
    }
    Ok(())
}

/// Remove the workspace grant. Called by environment reset and uninstall: a
/// durable machine-wide ACE with no removal path would outlive Raiker itself.
pub fn revoke_workspace_grant(workspace: &Path) -> Result<(), String> {
    let capability = Capability::derive(&capability_name(workspace))?;
    set_entry(workspace, capability.dacl_sid, 0, REVOKE_ACCESS, false)
}

/// A deny ACE is only useful if it is protected, inheritable, covers full
/// access, and appears before any allow that might satisfy the access check.
fn deny_ace_is_safe(path: &Path, sid: PSID) -> Result<bool, String> {
    const DACL_PROTECTED: u16 = 0x1000;
    const FILE_ALL_ACCESS: u32 = 0x001f_01ff;
    let wide_path = wide(&path.to_string_lossy());
    let mut acl: *mut ACL = null_mut();
    let mut descriptor: PSECURITY_DESCRIPTOR = null_mut();
    let read = unsafe {
        GetNamedSecurityInfoW(
            wide_path.as_ptr(),
            SE_FILE_OBJECT,
            DACL_SECURITY_INFORMATION,
            null_mut(),
            null_mut(),
            &mut acl,
            null_mut(),
            &mut descriptor,
        )
    };
    if read != 0 {
        return Err("native_sandbox_acl_grant_failed".into());
    }
    let mut control = 0u16;
    let mut revision = 0u32;
    let control_ok =
        unsafe { GetSecurityDescriptorControl(descriptor, &mut control, &mut revision) } != 0;
    let mut denies_self = false;
    let mut denies_children = false;
    if control_ok && control & DACL_PROTECTED != 0 && !acl.is_null() {
        for index in 0..unsafe { (*acl).AceCount } {
            let mut ace: *mut c_void = null_mut();
            if unsafe { GetAce(acl, index as u32, &mut ace) } == 0 {
                break;
            }
            let entry = ace as *const ACCESS_ALLOWED_ACE;
            let kind = unsafe { (*entry).Header.AceType };
            // Only deny entries are permitted ahead of the target deny. This
            // conservatively rejects noncanonical or unsupported ACL entries.
            if kind != ACE_TYPE_DENIED {
                break;
            }
            let entry_sid = unsafe { std::ptr::addr_of!((*entry).SidStart) } as PSID;
            if unsafe { EqualSid(entry_sid, sid) } == 0 {
                continue;
            }
            let mask = unsafe { (*entry).Mask };
            let flags = unsafe { (*entry).Header.AceFlags };
            let inherit = (CONTAINER_INHERIT_ACE | OBJECT_INHERIT_ACE) as u8;
            let full = mask & GENERIC_ALL != 0 || mask & FILE_ALL_ACCESS == FILE_ALL_ACCESS;
            if flags & (INHERITED_ACE as u8) == 0 && full {
                // Windows may split one inheritable generic ACE into a
                // direct mapped ACE and an inherit-only generic ACE.
                denies_self |= flags & 0x08 == 0; // INHERIT_ONLY_ACE
                denies_children |= flags & inherit == inherit;
            }
        }
    }
    unsafe { LocalFree(descriptor as HLOCAL) };
    Ok(control_ok && control & DACL_PROTECTED != 0 && denies_self && denies_children)
}

/// True when an allow entry for `ALL APPLICATION PACKAGES` or `ALL RESTRICTED
/// APPLICATION PACKAGES` on this path grants any of `rights`, explicitly or by
/// inheritance. Every AppContainer satisfies those SIDs, so no capability deny
/// can withhold what they grant.
fn granted_to_all_packages(path: &Path, rights: u32) -> Result<bool, String> {
    let packages = [well_known_sid("S-1-15-2-1")?, well_known_sid("S-1-15-2-2")?];
    let wide_path = wide(&path.to_string_lossy());
    let mut acl: *mut ACL = null_mut();
    let mut descriptor: PSECURITY_DESCRIPTOR = null_mut();
    let read = unsafe {
        GetNamedSecurityInfoW(
            wide_path.as_ptr(),
            SE_FILE_OBJECT,
            DACL_SECURITY_INFORMATION,
            null_mut(),
            null_mut(),
            &mut acl,
            null_mut(),
            &mut descriptor,
        )
    };
    if read != 0 {
        for sid in packages {
            unsafe { LocalFree(sid as HLOCAL) };
        }
        return Err("native_sandbox_acl_grant_failed".into());
    }
    // A null DACL grants everyone everything.
    let mut granted = acl.is_null();
    if !acl.is_null() {
        for index in 0..unsafe { (*acl).AceCount } {
            let mut ace: *mut c_void = null_mut();
            if unsafe { GetAce(acl, index as u32, &mut ace) } == 0 {
                granted = true;
                break;
            }
            let entry = ace as *const ACCESS_ALLOWED_ACE;
            let flags = unsafe { (*entry).Header.AceFlags };
            if unsafe { (*entry).Header.AceType } != ACE_TYPE_ALLOWED || flags & 0x08 != 0 {
                continue;
            }
            let entry_sid = unsafe { std::ptr::addr_of!((*entry).SidStart) } as PSID;
            if packages
                .iter()
                .any(|sid| unsafe { EqualSid(entry_sid, *sid) } != 0)
                && unsafe { (*entry).Mask } & rights != 0
            {
                granted = true;
                break;
            }
        }
    }
    unsafe { LocalFree(descriptor as HLOCAL) };
    for sid in packages {
        unsafe { LocalFree(sid as HLOCAL) };
    }
    Ok(granted)
}

fn well_known_sid(text: &str) -> Result<PSID, String> {
    let mut sid: PSID = null_mut();
    if unsafe { ConvertStringSidToSidW(wide(text).as_ptr(), &mut sid) } == 0 {
        return Err("native_sandbox_acl_grant_failed".into());
    }
    Ok(sid)
}

/// A read-only allow is insufficient when another SID grants writes. Require
/// an inheritable capability deny ahead of every allow as well as the read grant.
fn readonly_ace_is_safe(path: &Path, sid: PSID) -> Result<bool, String> {
    const DACL_PROTECTED: u16 = 0x1000;
    let wide_path = wide(&path.to_string_lossy());
    let mut acl: *mut ACL = null_mut();
    let mut descriptor: PSECURITY_DESCRIPTOR = null_mut();
    let read = unsafe {
        GetNamedSecurityInfoW(
            wide_path.as_ptr(),
            SE_FILE_OBJECT,
            DACL_SECURITY_INFORMATION,
            null_mut(),
            null_mut(),
            &mut acl,
            null_mut(),
            &mut descriptor,
        )
    };
    if read != 0 {
        return Err("native_sandbox_acl_grant_failed".into());
    }
    let mut control = 0u16;
    let mut revision = 0u32;
    let control_ok =
        unsafe { GetSecurityDescriptorControl(descriptor, &mut control, &mut revision) } != 0;
    let mut found = false;
    let mut unsafe_allow = false;
    let mut leading_denies = true;
    let mut deny_self = 0u32;
    let mut deny_children = 0u32;
    if control_ok && control & DACL_PROTECTED != 0 && !acl.is_null() {
        for index in 0..unsafe { (*acl).AceCount } {
            let mut ace: *mut c_void = null_mut();
            if unsafe { GetAce(acl, index as u32, &mut ace) } == 0 {
                unsafe_allow = true;
                break;
            }
            let entry = ace as *const ACCESS_ALLOWED_ACE;
            let kind = unsafe { (*entry).Header.AceType };
            if kind != ACE_TYPE_DENIED {
                leading_denies = false;
            }
            if kind != ACE_TYPE_ALLOWED && kind != ACE_TYPE_DENIED {
                continue;
            }
            let entry_sid = unsafe { std::ptr::addr_of!((*entry).SidStart) } as PSID;
            if unsafe { EqualSid(entry_sid, sid) } == 0 {
                continue;
            }
            let mask = unsafe { (*entry).Mask };
            let flags = unsafe { (*entry).Header.AceFlags };
            let inherit = (CONTAINER_INHERIT_ACE | OBJECT_INHERIT_ACE) as u8;
            if kind == ACE_TYPE_DENIED {
                if leading_denies && flags & (INHERITED_ACE as u8) == 0 {
                    if flags & 0x08 == 0 {
                        deny_self |= mask;
                    }
                    if flags & inherit == inherit {
                        deny_children |= mask;
                    }
                }
                continue;
            }
            unsafe_allow |= mask & WRITE_LIKE != 0;
            let required = FILE_GENERIC_READ | FILE_GENERIC_EXECUTE;
            found |= flags & (INHERITED_ACE as u8) == 0
                && flags & inherit == inherit
                && mask & required == required;
        }
    }
    unsafe { LocalFree(descriptor as HLOCAL) };
    Ok(control_ok
        && control & DACL_PROTECTED != 0
        && found
        && !unsafe_allow
        && deny_self & READONLY_DENY_MASK == READONLY_DENY_MASK
        && deny_children & READONLY_DENY_MASK == READONLY_DENY_MASK)
}

/// True when this exact path carries an **explicit** (non-inherited) ACE of the
/// given type for the SID. Inherited entries deliberately do not count: an
/// inherited allow on `.raiker` is exactly the drift this guards against.
fn has_explicit_ace(path: &Path, sid: PSID, ace_type: u8) -> Result<bool, String> {
    let wide_path = wide(&path.to_string_lossy());
    let mut acl: *mut ACL = null_mut();
    let mut descriptor: PSECURITY_DESCRIPTOR = null_mut();
    let read = unsafe {
        GetNamedSecurityInfoW(
            wide_path.as_ptr(),
            SE_FILE_OBJECT,
            DACL_SECURITY_INFORMATION,
            null_mut(),
            null_mut(),
            &mut acl,
            null_mut(),
            &mut descriptor,
        )
    };
    if read != 0 {
        return Err("native_sandbox_acl_grant_failed".into());
    }
    let mut found = false;
    if !acl.is_null() {
        let count = unsafe { (*acl).AceCount };
        for index in 0..count {
            let mut ace: *mut c_void = null_mut();
            if unsafe { GetAce(acl, index as u32, &mut ace) } == 0 {
                continue;
            }
            let header = ace as *const ACCESS_ALLOWED_ACE;
            let kind = unsafe { (*header).Header.AceType };
            let flags = unsafe { (*header).Header.AceFlags };
            if kind != ace_type || flags & (INHERITED_ACE as u8) != 0 {
                continue;
            }
            let entry_sid = unsafe { std::ptr::addr_of!((*header).SidStart) } as PSID;
            if unsafe { EqualSid(entry_sid, sid) } != 0 {
                found = true;
                break;
            }
        }
    }
    unsafe { LocalFree(descriptor as HLOCAL) };
    Ok(found)
}

fn set_entry(path: &Path, sid: PSID, access: u32, mode: i32, protect: bool) -> Result<(), String> {
    let wide_path = wide(&path.to_string_lossy());
    let mut existing: *mut ACL = null_mut();
    let mut descriptor: PSECURITY_DESCRIPTOR = null_mut();
    let read = unsafe {
        GetNamedSecurityInfoW(
            wide_path.as_ptr(),
            SE_FILE_OBJECT,
            DACL_SECURITY_INFORMATION,
            null_mut(),
            null_mut(),
            &mut existing,
            null_mut(),
            &mut descriptor,
        )
    };
    if read != 0 {
        return Err("native_sandbox_acl_grant_failed".into());
    }
    let mut entry: EXPLICIT_ACCESS_W = unsafe { std::mem::zeroed() };
    entry.grfAccessPermissions = access;
    entry.grfAccessMode = mode;
    entry.grfInheritance = CONTAINER_INHERIT_ACE | OBJECT_INHERIT_ACE;
    entry.Trustee = TRUSTEE_W {
        pMultipleTrustee: null_mut(),
        MultipleTrusteeOperation: NO_MULTIPLE_TRUSTEE,
        TrusteeForm: TRUSTEE_IS_SID,
        TrusteeType: TRUSTEE_IS_UNKNOWN,
        ptstrName: sid as *mut u16,
    };
    let mut updated: *mut ACL = null_mut();
    let merged = unsafe { SetEntriesInAclW(1, &entry, existing, &mut updated) };
    if merged != 0 {
        unsafe { LocalFree(descriptor as HLOCAL) };
        return Err("native_sandbox_acl_grant_failed".into());
    }
    let information = if protect {
        DACL_SECURITY_INFORMATION | PROTECTED_DACL
    } else {
        DACL_SECURITY_INFORMATION
    };
    let written = unsafe {
        SetNamedSecurityInfoW(
            wide_path.as_ptr() as *mut u16,
            SE_FILE_OBJECT,
            information,
            null_mut(),
            null_mut(),
            updated,
            null_mut(),
        )
    };
    unsafe { LocalFree(updated as HLOCAL) };
    unsafe { LocalFree(descriptor as HLOCAL) };
    if written != 0 {
        return Err("native_sandbox_acl_grant_failed".into());
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// The per-run AppContainer
// ---------------------------------------------------------------------------

struct AppContainer {
    raw: PSID,
    text: String,
    name: String,
}

impl AppContainer {
    fn create(name: &str) -> Result<AppContainer, String> {
        let wide_name = wide(name);
        let display = wide("Raiker governed command");
        let description = wide("Raiker runs one governed command in this AppContainer.");
        let mut sid: PSID = null_mut();
        let created = unsafe {
            CreateAppContainerProfile(
                wide_name.as_ptr(),
                display.as_ptr(),
                description.as_ptr(),
                null(),
                0,
                &mut sid,
            )
        };
        if created != 0 {
            // A profile left behind by a killed runner is reused rather than
            // treated as an error; the startup sweep removes the strays.
            let already = created as u32 == (0x8007_0000 | ERROR_ALREADY_EXISTS);
            if !already {
                return Err("native_sandbox_appcontainer_unavailable".into());
            }
            if unsafe { DeriveAppContainerSidFromAppContainerName(wide_name.as_ptr(), &mut sid) }
                != 0
            {
                return Err("native_sandbox_appcontainer_unavailable".into());
            }
        }
        let text = sid_text(sid)?;
        Ok(AppContainer {
            raw: sid,
            text,
            name: name.to_owned(),
        })
    }

    /// The container's own writable temp.
    ///
    /// `LOCALAPPDATA` is absent from the constructed environment a governed
    /// command runs with — that environment is deliberately minimal — so the
    /// profile root is derived rather than read. Without the fallback the
    /// resulting path is relative, `TEMP` points nowhere, and the failure
    /// surfaces as an unrelated launch error.
    fn package_directory(&self) -> PathBuf {
        let root = std::env::var("LOCALAPPDATA")
            .or_else(|_| {
                std::env::var("USERPROFILE").map(|home| {
                    PathBuf::from(home)
                        .join("AppData")
                        .join("Local")
                        .to_string_lossy()
                        .into_owned()
                })
            })
            .unwrap_or_else(|_| std::env::temp_dir().to_string_lossy().into_owned());
        PathBuf::from(root)
            .join("Packages")
            .join(&self.name)
            .join("AC")
            .join("Temp")
    }

    /// Deletion fails while any handle into the package directory is open, so
    /// it is retried briefly. A profile that still will not go is left for the
    /// startup sweep rather than reported as cleaned up.
    fn delete(&self) {
        let wide_name = wide(&self.name);
        for _ in 0..5 {
            if unsafe { DeleteAppContainerProfile(wide_name.as_ptr()) } == 0 {
                return;
            }
            std::thread::sleep(std::time::Duration::from_millis(120));
        }
    }
}

// ---------------------------------------------------------------------------
// Probe plumbing
// ---------------------------------------------------------------------------

fn run_inside(workspace: &Path, test: &SelfTest) -> Result<Value, String> {
    let current = std::env::current_exe().map_err(|_| "native_sandbox_runner_unreadable")?;
    let policy = LaunchPolicy {
        workspace_root: workspace.to_path_buf(),
        cwd: workspace.to_path_buf(),
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
    let capability = Capability::derive(&capability_name(workspace))?;
    ensure_workspace_grant(&policy, &capability)?;
    let container = AppContainer::create(&policy.profile_name)?;

    let argv = vec![
        current.to_string_lossy().into_owned(),
        "--selftest".to_owned(),
        test.to_value().to_string(),
    ];
    let captured = capture_in_container(&policy, &argv, &capability, &container);
    // Removing a marker does not prove the descendant started or terminated.
    // Keep this observation indeterminate until the process itself is tracked.
    let marker = test.inside_path.with_extension("grandchild");
    let _ = std::fs::remove_file(&marker);
    container.delete();
    captured
}

fn capture_in_container(
    policy: &LaunchPolicy,
    argv: &[String],
    capability: &Capability,
    container: &AppContainer,
) -> Result<Value, String> {
    let owner = current_user_sid_text()?;
    let descriptor = PipeDescriptor::build(&owner, &container.text)?;
    let stdin = Pipe::create(&descriptor, PipeEnd::Write)?;
    let stdout = Pipe::create(&descriptor, PipeEnd::Read)?;
    let stderr = Pipe::create(&descriptor, PipeEnd::Read)?;
    let job = create_job(policy)?;
    let information = match start_process(
        policy,
        argv,
        capability,
        container,
        [stdin.child, stdout.child, stderr.child],
    ) {
        Ok(information) => information,
        Err(reason) => {
            unsafe { CloseHandle(job) };
            return Err(reason);
        }
    };
    assign_and_resume(job, &information)?;
    stdin.close_child();
    stdout.close_child();
    stderr.close_child();
    stdin.close_parent();
    stderr.close_parent();

    let handle = stdout.parent as usize;
    let (send, receive) = std::sync::mpsc::channel();
    std::thread::spawn(move || {
        use std::io::BufRead;
        let source = unsafe { File::from_raw_handle(handle as RawHandle) };
        let mut source = std::io::BufReader::new(source);
        let mut text = String::new();
        let _ = source.read_line(&mut text);
        let _ = send.send(text);
    });
    let parent_wait = unsafe { WaitForSingleObject(information.hProcess, 30_000) };
    let mut parent_exit = 0u32;
    let exit_known = parent_wait == WAIT_OBJECT_0
        && unsafe { GetExitCodeProcess(information.hProcess, &mut parent_exit) } != 0;
    unsafe { CloseHandle(information.hProcess) };
    let text = if parent_wait == WAIT_OBJECT_0 {
        receive.recv_timeout(std::time::Duration::from_secs(2)).ok()
    } else {
        None
    };
    let mut result = text.and_then(|text| serde_json::from_str::<Value>(text.trim()).ok());
    let descendant = result
        .as_ref()
        .and_then(|value| live_job_descendant(job, value));
    unsafe { CloseHandle(job) };
    let verdict = match descendant {
        Some(process) => {
            let stopped = unsafe { WaitForSingleObject(process, 2_000) } == WAIT_OBJECT_0;
            unsafe { CloseHandle(process) };
            if stopped { "enforced" } else { "unenforced" }
        }
        None => "indeterminate",
    };
    if !exit_known {
        return Err("native_sandbox_probe_wait_failed".to_owned());
    }
    if parent_exit != 0 {
        return Err(format!("native_sandbox_probe_exit_{parent_exit:08x}"));
    }
    let Some(ref mut value) = result else {
        return Err("native_sandbox_probe_no_output".to_owned());
    };
    value["descendant_reaped"] = json!(verdict);
    Ok(result.expect("checked above"))
}

// Establish a positive control on the exact process before closing the job.
// Membership prevents an unrelated process with a reused PID from counting.
fn live_job_descendant(job: HANDLE, value: &Value) -> Option<HANDLE> {
    let pid = u32::try_from(value.get("descendant_pid")?.as_u64()?).ok()?;
    const SYNCHRONIZE_AND_QUERY_LIMITED: u32 = 0x0010_1000;
    let process = unsafe { OpenProcess(SYNCHRONIZE_AND_QUERY_LIMITED, 0, pid) };
    if process.is_null() {
        return None;
    }
    let mut member = 0;
    let valid = unsafe { IsProcessInJob(process, job, &mut member) } != 0
        && member != 0
        && unsafe { WaitForSingleObject(process, 0) } == WAIT_TIMEOUT;
    if !valid {
        unsafe { CloseHandle(process) };
        return None;
    }
    Some(process)
}

fn outside_targets(workspace: &Path, nonce: &str) -> Vec<PathBuf> {
    // Paths the owner's own token can write, so a refusal inside the boundary
    // means containment rather than an unwritable target.
    let mut targets = Vec::new();
    if let Some(parent) = workspace.parent() {
        targets.push(parent.join(format!(".{nonce}-escape.tmp")));
    }
    if let Ok(profile) = std::env::var("USERPROFILE") {
        targets.push(PathBuf::from(profile).join(format!(".{nonce}-escape.tmp")));
    }
    targets
}

/// The default gateway on a closed port: off this machine, so the AppContainer
/// network capability governs it, but never off the local network. A product
/// whose posture is "no network by default" must not make an undisclosed
/// outbound connection from its own readiness check.
fn probe_destination() -> String {
    format!(
        "{}:9",
        default_gateway().unwrap_or_else(|| "192.168.0.1".into())
    )
}

fn default_gateway() -> Option<String> {
    let output = std::process::Command::new(system_route_program()?)
        .args(["print", "-4", "0.0.0.0"])
        .output()
        .ok()?;
    let text = String::from_utf8_lossy(&output.stdout);
    text.lines()
        .filter(|line| line.trim_start().starts_with("0.0.0.0"))
        .filter_map(|line| line.split_whitespace().nth(2).map(str::to_owned))
        .find(|candidate| candidate.parse::<std::net::Ipv4Addr>().is_ok())
}

fn system_route_program() -> Option<PathBuf> {
    use std::os::windows::ffi::OsStringExt;
    use windows_sys::Win32::System::SystemInformation::GetSystemDirectoryW;
    let mut buffer = vec![0u16; 32_768];
    let length = unsafe { GetSystemDirectoryW(buffer.as_mut_ptr(), buffer.len() as u32) } as usize;
    if length == 0 || length >= buffer.len() {
        return None;
    }
    let mut directory = PathBuf::from(std::ffi::OsString::from_wide(&buffer[..length]));
    directory.push("route.exe");
    directory.is_file().then_some(directory)
}

/// Whether the connect attempt's packet reached the destination — a refusal
/// from a closed port counts, a dropped packet does not. See
/// `selftest::connect_probe`.
fn reached(value: &Value) -> bool {
    value
        .get("connect")
        .and_then(|entry| entry.get("reached"))
        .and_then(Value::as_bool)
        .unwrap_or(false)
}

fn allowed(value: &Value, key: &str) -> bool {
    value
        .get(key)
        .and_then(|entry| entry.get("allowed"))
        .and_then(Value::as_bool)
        .unwrap_or(false)
}

/// The escape observation folds several targets: containment must hold for all
/// of them, and the control arm must have succeeded for at least one, or the
/// answer is indeterminate rather than proof.
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
        "platform": "windows",
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

// ---------------------------------------------------------------------------
// Small Win32 helpers
// ---------------------------------------------------------------------------

struct PipeDescriptor(usize);

impl PipeDescriptor {
    /// The pipes name the run's container SID.
    ///
    /// This is defensive rather than known-necessary: an inherited handle is
    /// access-checked when it is opened here, not when it is inherited, so the
    /// relay may well work without it. It costs nothing and the failure it
    /// would prevent is silent. What actually *proves* the relay works is probe
    /// observation 0 — so do not drop that observation on the strength of this.
    fn build(owner_sid: &str, container_sid: &str) -> Result<PipeDescriptor, String> {
        let sddl = format!("D:(A;;GA;;;{owner_sid})(A;;GA;;;{container_sid})");
        let text = wide(&sddl);
        let mut descriptor: PSECURITY_DESCRIPTOR = null_mut();
        let converted = unsafe {
            ConvertStringSecurityDescriptorToSecurityDescriptorW(
                text.as_ptr(),
                SDDL_REVISION_1,
                &mut descriptor,
                null_mut(),
            )
        };
        if converted == 0 {
            return Err("native_sandbox_pipe_descriptor_failed".into());
        }
        Ok(PipeDescriptor(descriptor as usize))
    }
}

enum PipeEnd {
    Read,
    Write,
}

struct Pipe {
    parent: HANDLE,
    child: HANDLE,
    child_closed: std::cell::Cell<bool>,
    parent_closed: std::cell::Cell<bool>,
}

impl Pipe {
    fn create(descriptor: &PipeDescriptor, parent_end: PipeEnd) -> Result<Pipe, String> {
        let attributes = SECURITY_ATTRIBUTES {
            nLength: size_of::<SECURITY_ATTRIBUTES>() as u32,
            lpSecurityDescriptor: descriptor.0 as PSECURITY_DESCRIPTOR,
            bInheritHandle: 1,
        };
        let mut read: HANDLE = null_mut();
        let mut write: HANDLE = null_mut();
        if unsafe { CreatePipe(&mut read, &mut write, &attributes, 0) } == 0 {
            return Err("native_sandbox_pipe_failed".into());
        }
        let (parent, child) = match parent_end {
            PipeEnd::Read => (read, write),
            PipeEnd::Write => (write, read),
        };
        // Only the child's end is inheritable, so `bInheritHandles` cannot hand
        // the command anything else this process happens to hold.
        unsafe { SetHandleInformation(parent, HANDLE_FLAG_INHERIT, 0) };
        Ok(Pipe {
            parent,
            child,
            child_closed: std::cell::Cell::new(false),
            parent_closed: std::cell::Cell::new(false),
        })
    }

    fn close_child(&self) {
        if !self.child_closed.replace(true) {
            unsafe { CloseHandle(self.child) };
        }
    }

    fn close_parent(&self) {
        if !self.parent_closed.replace(true) {
            unsafe { CloseHandle(self.parent) };
        }
    }
}

fn sid_text(sid: PSID) -> Result<String, String> {
    let mut buffer: *mut u16 = null_mut();
    if unsafe { ConvertSidToStringSidW(sid, &mut buffer) } == 0 {
        return Err("native_sandbox_sid_unreadable".into());
    }
    let mut length = 0usize;
    while unsafe { *buffer.add(length) } != 0 {
        length += 1;
    }
    let text = String::from_utf16_lossy(unsafe { std::slice::from_raw_parts(buffer, length) });
    unsafe { LocalFree(buffer as HLOCAL) };
    Ok(text)
}

fn current_user_sid_text() -> Result<String, String> {
    let mut token: HANDLE = null_mut();
    if unsafe { OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &mut token) } == 0 {
        return Err("native_sandbox_token_unavailable".into());
    }
    let mut size: u32 = 0;
    unsafe { GetTokenInformation(token, TokenUser, null_mut(), 0, &mut size) };
    let mut buffer = vec![0u8; size as usize];
    let ok = unsafe {
        GetTokenInformation(
            token,
            TokenUser,
            buffer.as_mut_ptr() as *mut c_void,
            size,
            &mut size,
        )
    };
    unsafe { CloseHandle(token) };
    if ok == 0 {
        return Err("native_sandbox_token_unavailable".into());
    }
    let user = buffer.as_ptr() as *const TOKEN_USER;
    sid_text(unsafe { (*user).User.Sid })
}

/// `canonicalize` returns a `\\?\` path, which several Win32 security calls do
/// not accept.
fn strip_verbatim(path: &Path) -> PathBuf {
    let text = path.to_string_lossy();
    PathBuf::from(text.strip_prefix(r"\\?\").unwrap_or(&text).to_string())
}

fn wide(value: &str) -> Vec<u16> {
    value.encode_utf16().chain(std::iter::once(0)).collect()
}

/// Rebuild a command line that `CommandLineToArgvW` parses back into exactly
/// this argv. Raiker validated the argv list; a quoting bug here would hand the
/// child a different command than the owner approved.
fn command_line_for(argv: &[String]) -> String {
    argv.iter()
        .map(|argument| quote(argument))
        .collect::<Vec<_>>()
        .join(" ")
}

fn quote(argument: &str) -> String {
    if !argument.is_empty() && !argument.contains([' ', '\t', '\n', '\u{b}', '"']) {
        return argument.to_owned();
    }
    let mut quoted = String::from("\"");
    let mut backslashes = 0usize;
    for character in argument.chars() {
        match character {
            '\\' => {
                backslashes += 1;
                quoted.push('\\');
            }
            '"' => {
                quoted.extend(std::iter::repeat_n('\\', backslashes + 1));
                quoted.push('"');
                backslashes = 0;
            }
            other => {
                backslashes = 0;
                quoted.push(other);
            }
        }
    }
    quoted.extend(std::iter::repeat_n('\\', backslashes));
    quoted.push('"');
    quoted
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn route_program_is_resolved_from_the_windows_system_directory() {
        let path = system_route_program().expect("system route.exe unavailable");
        assert!(path.is_absolute());
        assert_eq!(path.file_name().unwrap(), "route.exe");
        assert_eq!(
            path.parent()
                .unwrap()
                .file_name()
                .unwrap()
                .to_string_lossy()
                .to_lowercase(),
            "system32"
        );
    }

    #[test]
    fn workspace_capability_grant_is_removed_by_revocation() {
        let directory = std::env::temp_dir().join(selftest::probe_nonce());
        std::fs::create_dir(&directory).unwrap();
        let capability = Capability::derive(&capability_name(&directory)).unwrap();
        set_entry(
            &directory,
            capability.dacl_sid,
            FILE_GENERIC_READ,
            SET_ACCESS,
            false,
        )
        .unwrap();
        assert!(has_explicit_ace(&directory, capability.dacl_sid, ACE_TYPE_ALLOWED).unwrap());
        revoke_workspace_grant(&directory).unwrap();
        assert!(!has_explicit_ace(&directory, capability.dacl_sid, ACE_TYPE_ALLOWED).unwrap());
        std::fs::remove_dir(directory).unwrap();
    }

    #[test]
    fn readonly_acl_does_not_accept_a_write_capable_allow() {
        let directory = std::env::temp_dir().join(selftest::probe_nonce());
        std::fs::create_dir(&directory).unwrap();
        let capability = Capability::derive(&capability_name(&directory)).unwrap();
        set_entry(
            &directory,
            capability.dacl_sid,
            FILE_GENERIC_READ | FILE_GENERIC_WRITE,
            SET_ACCESS,
            true,
        )
        .unwrap();
        assert!(has_explicit_ace(&directory, capability.dacl_sid, ACE_TYPE_ALLOWED).unwrap());
        assert!(!readonly_ace_is_safe(&directory, capability.dacl_sid).unwrap());
        set_entry(
            &directory,
            capability.dacl_sid,
            FILE_GENERIC_READ | FILE_GENERIC_EXECUTE,
            SET_ACCESS,
            true,
        )
        .unwrap();
        assert!(!readonly_ace_is_safe(&directory, capability.dacl_sid).unwrap());
        set_entry(
            &directory,
            capability.dacl_sid,
            READONLY_DENY_MASK,
            DENY_ACCESS,
            true,
        )
        .unwrap();
        assert!(readonly_ace_is_safe(&directory, capability.dacl_sid).unwrap());
        std::fs::remove_dir(directory).unwrap();
    }

    #[test]
    fn protected_acl_does_not_accept_a_partial_deny() {
        let directory = std::env::temp_dir().join(selftest::probe_nonce());
        std::fs::create_dir(&directory).unwrap();
        let capability = Capability::derive(&capability_name(&directory)).unwrap();
        set_entry(
            &directory,
            capability.dacl_sid,
            FILE_GENERIC_READ,
            DENY_ACCESS,
            true,
        )
        .unwrap();
        assert!(has_explicit_ace(&directory, capability.dacl_sid, ACE_TYPE_DENIED).unwrap());
        assert!(!deny_ace_is_safe(&directory, capability.dacl_sid).unwrap());
        set_entry(&directory, capability.dacl_sid, 0, REVOKE_ACCESS, true).unwrap();
        set_entry(
            &directory,
            capability.dacl_sid,
            GENERIC_ALL,
            DENY_ACCESS,
            true,
        )
        .unwrap();
        assert!(deny_ace_is_safe(&directory, capability.dacl_sid).unwrap());
        std::fs::remove_dir(directory).unwrap();
    }

    #[test]
    fn failed_job_assignment_never_resumes_the_child() {
        let marker = std::env::temp_dir().join(format!("{}.txt", selftest::probe_nonce()));
        let mut command = wide(&format!("cmd.exe /c echo ran > \"{}\"", marker.display()));
        let mut startup: STARTUPINFOEXW = unsafe { std::mem::zeroed() };
        startup.StartupInfo.cb =
            size_of::<windows_sys::Win32::System::Threading::STARTUPINFOW>() as u32;
        let mut information: PROCESS_INFORMATION = unsafe { std::mem::zeroed() };
        let created = unsafe {
            CreateProcessW(
                null(),
                command.as_mut_ptr(),
                null(),
                null(),
                0,
                CREATE_SUSPENDED,
                null(),
                null(),
                &startup.StartupInfo,
                &mut information,
            )
        };
        assert_ne!(created, 0, "could not create suspended control process");
        assert_eq!(
            assign_and_resume(null_mut(), &information).unwrap_err(),
            "native_sandbox_job_object_failed"
        );
        std::thread::sleep(std::time::Duration::from_millis(200));
        assert!(!marker.exists(), "child ran after job assignment failed");
    }

    #[test]
    fn deadline_closes_the_job_and_terminates_the_running_process() {
        let mut command = wide("cmd.exe /c for /l %i in (1,1,1000000000) do @rem");
        let mut startup: STARTUPINFOEXW = unsafe { std::mem::zeroed() };
        startup.StartupInfo.cb =
            size_of::<windows_sys::Win32::System::Threading::STARTUPINFOW>() as u32;
        let mut information: PROCESS_INFORMATION = unsafe { std::mem::zeroed() };
        assert_ne!(
            unsafe {
                CreateProcessW(
                    null(),
                    command.as_mut_ptr(),
                    null(),
                    null(),
                    0,
                    CREATE_SUSPENDED,
                    null(),
                    null(),
                    &startup.StartupInfo,
                    &mut information,
                )
            },
            0
        );
        let policy = LaunchPolicy {
            workspace_root: PathBuf::from("C:\\"),
            cwd: PathBuf::from("C:\\"),
            deny_paths: vec![],
            readonly_paths: vec![],
            network: NetworkPolicy::Denied,
            pty: false,
            max_processes: 32,
            max_memory_bytes: 1024 * 1024 * 1024,
            deadline_seconds: 1,
            max_cpu_seconds: 1,
            profile_name: "test".to_owned(),
        };
        let job = create_job(&policy).unwrap();
        assign_and_resume(job, &information).unwrap();
        assert_eq!(
            unsafe { WaitForSingleObject(information.hProcess, 50) },
            WAIT_TIMEOUT
        );
        let other_job = create_job(&policy).unwrap();
        let report = json!({"descendant_pid": information.dwProcessId});
        assert!(live_job_descendant(other_job, &report).is_none());
        unsafe { CloseHandle(other_job) };
        let descendant =
            live_job_descendant(job, &report).expect("live child must be observed in its own job");
        assert_eq!(
            wait_and_close_job(job, information.hProcess, 50),
            WAIT_TIMEOUT
        );
        assert_eq!(
            unsafe { WaitForSingleObject(descendant, 2_000) },
            WAIT_OBJECT_0
        );
        unsafe { CloseHandle(descendant) };
        assert_eq!(
            unsafe { WaitForSingleObject(information.hProcess, 0) },
            WAIT_OBJECT_0
        );
        unsafe { CloseHandle(information.hProcess) };
    }

    #[test]
    fn job_cpu_time_limit_terminates_a_busy_process() {
        let mut command = wide("cmd.exe /c for /l %i in (1,1,1000000000) do @rem");
        let mut startup: STARTUPINFOEXW = unsafe { std::mem::zeroed() };
        startup.StartupInfo.cb =
            size_of::<windows_sys::Win32::System::Threading::STARTUPINFOW>() as u32;
        let mut information: PROCESS_INFORMATION = unsafe { std::mem::zeroed() };
        assert_ne!(
            unsafe {
                CreateProcessW(
                    null(),
                    command.as_mut_ptr(),
                    null(),
                    null(),
                    0,
                    CREATE_SUSPENDED,
                    null(),
                    null(),
                    &startup.StartupInfo,
                    &mut information,
                )
            },
            0
        );
        let policy = LaunchPolicy {
            workspace_root: PathBuf::from("C:\\"),
            cwd: PathBuf::from("C:\\"),
            deny_paths: vec![],
            readonly_paths: vec![],
            network: NetworkPolicy::Denied,
            pty: false,
            max_processes: 32,
            max_memory_bytes: 1024 * 1024 * 1024,
            deadline_seconds: 15,
            max_cpu_seconds: 1,
            profile_name: "test".to_owned(),
        };
        let job = create_job(&policy).unwrap();
        assign_and_resume(job, &information).unwrap();
        let live = unsafe { WaitForSingleObject(information.hProcess, 50) };
        let terminated = unsafe { WaitForSingleObject(information.hProcess, 10_000) };
        unsafe { CloseHandle(job) };
        unsafe { CloseHandle(information.hProcess) };
        assert_eq!(live, WAIT_TIMEOUT, "positive control must start alive");
        assert_eq!(
            terminated, WAIT_OBJECT_0,
            "job CPU limit did not stop the process"
        );
    }

    #[test]
    fn job_process_limit_refuses_a_second_process() {
        fn suspended_loop() -> PROCESS_INFORMATION {
            let mut command = wide("cmd.exe /c for /l %i in (1,1,1000000000) do @rem");
            let mut startup: STARTUPINFOEXW = unsafe { std::mem::zeroed() };
            startup.StartupInfo.cb =
                size_of::<windows_sys::Win32::System::Threading::STARTUPINFOW>() as u32;
            let mut information: PROCESS_INFORMATION = unsafe { std::mem::zeroed() };
            assert_ne!(
                unsafe {
                    CreateProcessW(
                        null(),
                        command.as_mut_ptr(),
                        null(),
                        null(),
                        0,
                        CREATE_SUSPENDED,
                        null(),
                        null(),
                        &startup.StartupInfo,
                        &mut information,
                    )
                },
                0
            );
            information
        }
        let policy = LaunchPolicy {
            workspace_root: PathBuf::from("C:\\"),
            cwd: PathBuf::from("C:\\"),
            deny_paths: vec![],
            readonly_paths: vec![],
            network: NetworkPolicy::Denied,
            pty: false,
            max_processes: 1,
            max_memory_bytes: 1024 * 1024 * 1024,
            deadline_seconds: 15,
            max_cpu_seconds: 15,
            profile_name: "test".to_owned(),
        };
        let job = create_job(&policy).unwrap();
        let first = suspended_loop();
        assign_and_resume(job, &first).unwrap();
        let live = unsafe { WaitForSingleObject(first.hProcess, 50) };
        let second = suspended_loop();
        // Use a duplicate job handle: failure closes the handle passed to the
        // helper, while the original remains valid to terminate the first job.
        let mut duplicate: HANDLE = null_mut();
        assert_ne!(
            unsafe {
                windows_sys::Win32::Foundation::DuplicateHandle(
                    GetCurrentProcess(),
                    job,
                    GetCurrentProcess(),
                    &mut duplicate,
                    0,
                    0,
                    windows_sys::Win32::Foundation::DUPLICATE_SAME_ACCESS,
                )
            },
            0
        );
        let result = assign_and_resume(duplicate, &second);
        if result.is_ok() {
            unsafe { CloseHandle(duplicate) };
        }
        unsafe { CloseHandle(job) };
        let first_exited = unsafe { WaitForSingleObject(first.hProcess, 5_000) };
        unsafe { CloseHandle(first.hProcess) };
        if result.is_ok() {
            unsafe { WaitForSingleObject(second.hProcess, 5_000) };
            unsafe { CloseHandle(second.hProcess) };
        }
        assert_eq!(live, WAIT_TIMEOUT, "positive control must be running");
        assert_eq!(result.unwrap_err(), "native_sandbox_job_object_failed");
        assert_eq!(
            first_exited, WAIT_OBJECT_0,
            "closing the job must reap the first process"
        );
    }

    #[test]
    fn a_plain_argument_is_not_quoted() {
        assert_eq!(
            command_line_for(&["git".into(), "status".into()]),
            "git status"
        );
    }

    #[test]
    fn spaces_and_quotes_round_trip_through_the_windows_rules() {
        assert_eq!(quote("a b"), "\"a b\"");
        assert_eq!(quote("a\"b"), "\"a\\\"b\"");
        assert_eq!(quote("C:\\ws\\"), "C:\\ws\\");
        assert_eq!(quote("C:\\a b\\"), "\"C:\\a b\\\\\"");
    }

    #[test]
    fn the_capability_name_is_stable_and_workspace_specific() {
        let one = capability_name(Path::new("C:\\ws\\one"));
        assert_eq!(one, capability_name(Path::new("C:\\WS\\ONE")));
        assert_ne!(one, capability_name(Path::new("C:\\ws\\two")));
        assert!(one.starts_with("raikerWorkspace"));
    }

    #[test]
    fn the_probe_destination_is_never_loopback() {
        let destination = probe_destination();
        assert!(!destination.starts_with("127."));
        assert!(destination.ends_with(":9"));
    }
}
