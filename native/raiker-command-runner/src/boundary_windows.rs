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
    CloseHandle, ERROR_ALREADY_EXISTS, GENERIC_ALL, HANDLE, HLOCAL, LocalFree,
};
use windows_sys::Win32::Security::Authorization::{
    ConvertSidToStringSidW, ConvertStringSecurityDescriptorToSecurityDescriptorW, DENY_ACCESS,
    EXPLICIT_ACCESS_W, GetNamedSecurityInfoW, NO_MULTIPLE_TRUSTEE, REVOKE_ACCESS, SDDL_REVISION_1,
    SE_FILE_OBJECT, SET_ACCESS, SetEntriesInAclW, SetNamedSecurityInfoW, TRUSTEE_IS_SID,
    TRUSTEE_IS_UNKNOWN, TRUSTEE_W,
};
use windows_sys::Win32::Security::DeriveCapabilitySidsFromName;
use windows_sys::Win32::Security::Isolation::{
    CreateAppContainerProfile, DeleteAppContainerProfile, DeriveAppContainerSidFromAppContainerName,
};
use windows_sys::Win32::Security::{
    ACCESS_ALLOWED_ACE, ACL, CONTAINER_INHERIT_ACE, DACL_SECURITY_INFORMATION, EqualSid, GetAce,
    GetTokenInformation, INHERITED_ACE, OBJECT_INHERIT_ACE, PSECURITY_DESCRIPTOR, PSID,
    SECURITY_ATTRIBUTES, SECURITY_CAPABILITIES, SID_AND_ATTRIBUTES, TOKEN_QUERY, TOKEN_USER,
    TokenUser,
};
use windows_sys::Win32::Storage::FileSystem::{
    FILE_GENERIC_EXECUTE, FILE_GENERIC_READ, FILE_GENERIC_WRITE,
};
use windows_sys::Win32::System::JobObjects::{
    AssignProcessToJobObject, CreateJobObjectW, JOB_OBJECT_LIMIT_ACTIVE_PROCESS,
    JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION, JOB_OBJECT_LIMIT_JOB_MEMORY,
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
    JobObjectExtendedLimitInformation, SetInformationJobObject,
};
use windows_sys::Win32::System::Pipes::CreatePipe;
use windows_sys::Win32::System::Threading::{
    CREATE_SUSPENDED, CreateProcessW, DeleteProcThreadAttributeList, EXTENDED_STARTUPINFO_PRESENT,
    GetCurrentProcess, GetExitCodeProcess, INFINITE, InitializeProcThreadAttributeList,
    OpenProcessToken, PROCESS_INFORMATION, ResumeThread, STARTF_USESTDHANDLES, STARTUPINFOEXW,
    UpdateProcThreadAttribute, WaitForSingleObject,
};

const PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES: usize = 0x0002_0009;
const HANDLE_FLAG_INHERIT: u32 = 0x0000_0001;
/// `SE_GROUP_ENABLED`, which windows-sys exposes only under `SystemServices`.
const SID_ATTRIBUTE_ENABLED: u32 = 4;
/// `PROTECTED_DACL_SECURITY_INFORMATION`. Setting it converts the object's
/// inherited entries into explicit ones and stops inheritance at that object.
const PROTECTED_DACL: u32 = 0x8000_0000;
const ACE_TYPE_ALLOWED: u8 = 0;
const ACE_TYPE_DENIED: u8 = 1;

unsafe extern "system" {
    fn SetHandleInformation(handle: HANDLE, mask: u32, flags: u32) -> i32;
}

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
    let workspace = match workspace.canonicalize() {
        Ok(path) => strip_verbatim(&path),
        Err(_) => return unavailable("native_sandbox_workspace_unreadable"),
    };
    let scratch = workspace.join(".raiker").join("command-probe");
    let _ = std::fs::create_dir_all(&scratch);
    let test = SelfTest {
        nonce: format!("raiker-probe-{}", std::process::id()),
        inside_path: workspace.join(".raiker-probe-inside.tmp"),
        outside_paths: outside_targets(&workspace),
        masked_read_path: workspace
            .join(".raiker")
            .join("command-probe")
            .join("state"),
        connect_address: probe_destination(),
        spawn_grandchild: true,
    };
    let _ = std::fs::write(&test.masked_read_path, b"raiker-probe-state");

    // The control arm. Whatever the boundary does, these are what this token
    // can do without one.
    let outside = selftest::attempt(&test);
    let inside = match run_inside(&workspace, &test) {
        Ok(value) => value,
        Err(reason) => {
            let _ = std::fs::remove_file(&test.masked_read_path);
            return unavailable(&reason);
        }
    };
    let _ = std::fs::remove_file(&test.masked_read_path);
    let _ = std::fs::remove_dir_all(&scratch);

    let relay = inside.get("nonce").and_then(Value::as_str) == Some(test.nonce.as_str());
    let inside_write = allowed(&inside, "inside_write");
    let escape = folded_escape(&inside, &outside);
    let masked = selftest::verdict(
        allowed(&inside, "masked_read"),
        allowed(&outside, "masked_read"),
    );
    let network = selftest::verdict(reached(&inside), reached(&outside));
    let descendant = inside
        .get("descendant_reaped")
        .and_then(Value::as_bool)
        .unwrap_or(false);

    json!({
        "platform": "windows",
        "boundary": "appcontainer",
        "available": relay && inside_write && escape == "enforced",
        "reason": Value::Null,
        "network": network,
        "process_tree_stop": descendant,
        "pty": false,
        "concurrent_runs": false,
        "observations": {
            "relay": if relay { "enforced" } else { "unenforced" },
            "workspace_write": if inside_write { "enforced" } else { "unenforced" },
            "escape_write": escape,
            "masked_read": masked,
            "egress": network,
            "descendant_reaped": if descendant { "enforced" } else { "unenforced" },
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

    let information = start_process(
        policy,
        argv,
        capability,
        container,
        [stdin.child, stdout.child, stderr.child],
    )?;
    let job = create_job(policy)?;
    if unsafe { AssignProcessToJobObject(job, information.hProcess) } == 0 {
        unsafe { CloseHandle(information.hProcess) };
        unsafe { CloseHandle(job) };
        return Err("native_sandbox_job_object_failed".into());
    }
    unsafe { ResumeThread(information.hThread) };
    unsafe { CloseHandle(information.hThread) };

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

    // The boundary's own deadline. Raiker keeps an outer timer, but a wedged
    // relay must not be able to leave a command running past its bound.
    let deadline_job = job as usize;
    let deadline = policy.deadline_seconds;
    std::thread::spawn(move || {
        std::thread::sleep(std::time::Duration::from_secs(deadline));
        unsafe { CloseHandle(deadline_job as HANDLE) };
    });

    unsafe { WaitForSingleObject(information.hProcess, INFINITE) };
    let _ = out.join();
    let _ = err.join();
    let mut code: u32 = 0;
    unsafe { GetExitCodeProcess(information.hProcess, &mut code) };
    unsafe { CloseHandle(information.hProcess) };
    Ok(code as i32)
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
    unsafe { InitializeProcThreadAttributeList(null_mut(), 1, 0, &mut attribute_size) };
    let mut storage = vec![0u8; attribute_size];
    let list = storage.as_mut_ptr() as *mut c_void;
    if unsafe { InitializeProcThreadAttributeList(list, 1, 0, &mut attribute_size) } == 0 {
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

fn create_job(policy: &LaunchPolicy) -> Result<HANDLE, String> {
    let job = unsafe { CreateJobObjectW(null(), null()) };
    if job.is_null() {
        return Err("native_sandbox_job_object_failed".into());
    }
    let mut limits: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = unsafe { std::mem::zeroed() };
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        | JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION
        | JOB_OBJECT_LIMIT_ACTIVE_PROCESS
        | JOB_OBJECT_LIMIT_JOB_MEMORY;
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
        if path.exists() && !has_explicit_ace(&path, capability.dacl_sid, ACE_TYPE_DENIED)? {
            set_entry(&path, capability.dacl_sid, GENERIC_ALL, DENY_ACCESS, true)?;
        }
    }
    for relative in &policy.readonly_paths {
        let path = policy.workspace_root.join(relative);
        if path.exists() && !has_explicit_ace(&path, capability.dacl_sid, ACE_TYPE_ALLOWED)? {
            set_entry(
                &path,
                capability.dacl_sid,
                FILE_GENERIC_READ | FILE_GENERIC_EXECUTE,
                SET_ACCESS,
                true,
            )?;
        }
    }
    if !has_explicit_ace(
        &policy.workspace_root,
        capability.dacl_sid,
        ACE_TYPE_ALLOWED,
    )? {
        set_entry(
            &policy.workspace_root,
            capability.dacl_sid,
            FILE_GENERIC_READ | FILE_GENERIC_WRITE | FILE_GENERIC_EXECUTE,
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
    // Observation 5: the grandchild detached itself, so only the Job Object can
    // have taken it. `capture_in_container` closes the job before returning.
    let marker = test.inside_path.with_extension("grandchild");
    let reaped = !marker.exists() || std::fs::remove_file(&marker).is_ok();
    container.delete();
    let mut value = captured?;
    value["descendant_reaped"] = Value::Bool(reaped);
    Ok(value)
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
    let information = start_process(
        policy,
        argv,
        capability,
        container,
        [stdin.child, stdout.child, stderr.child],
    )?;
    let job = create_job(policy)?;
    unsafe { AssignProcessToJobObject(job, information.hProcess) };
    unsafe { ResumeThread(information.hThread) };
    unsafe { CloseHandle(information.hThread) };
    stdin.close_child();
    stdout.close_child();
    stderr.close_child();
    stdin.close_parent();
    stderr.close_parent();

    let handle = stdout.parent as usize;
    let reader = std::thread::spawn(move || {
        let mut source = unsafe { File::from_raw_handle(handle as RawHandle) };
        let mut text = String::new();
        let _ = std::io::Read::read_to_string(&mut source, &mut text);
        text
    });
    unsafe { WaitForSingleObject(information.hProcess, 30_000) };
    unsafe { CloseHandle(information.hProcess) };
    // Close the job *before* draining: closing it is what kills the detached
    // grandchild, and until that happens anything the grandchild still holds
    // keeps the read alive.
    unsafe { CloseHandle(job) };
    std::thread::sleep(std::time::Duration::from_millis(400));
    let text = reader.join().unwrap_or_default();
    serde_json::from_str::<Value>(text.trim())
        .map_err(|_| "native_sandbox_probe_no_output".to_owned())
}

fn outside_targets(workspace: &Path) -> Vec<PathBuf> {
    // Paths the owner's own token can write, so a refusal inside the boundary
    // means containment rather than an unwritable target.
    let mut targets = Vec::new();
    if let Some(parent) = workspace.parent() {
        targets.push(parent.join(".raiker-probe-escape.tmp"));
    }
    if let Ok(profile) = std::env::var("USERPROFILE") {
        targets.push(PathBuf::from(profile).join(".raiker-probe-escape.tmp"));
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
    let output = std::process::Command::new("route")
        .args(["print", "-4", "0.0.0.0"])
        .output()
        .ok()?;
    let text = String::from_utf8_lossy(&output.stdout);
    text.lines()
        .filter(|line| line.trim_start().starts_with("0.0.0.0"))
        .filter_map(|line| line.split_whitespace().nth(2).map(str::to_owned))
        .find(|candidate| candidate.parse::<std::net::Ipv4Addr>().is_ok())
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
