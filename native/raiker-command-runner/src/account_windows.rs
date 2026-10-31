//! The restricted-account boundary for Windows builds.
//!
//! AppContainer holds the filesystem boundary but blocks ordinary toolchains:
//! they stat every ancestor from the drive root, and a drive root grants an
//! AppContainer nothing (measured: Node `EPERM: lstat 'C:\'`, MSYS `0xC0000142`,
//! Git and virtualenv Python failing). A dedicated standard local account is an
//! ordinary principal, so those tools start; the owner's profile and other
//! users' files stay out of reach because Windows grants one standard user
//! nothing of another's.
//!
//! Setup is a one-time, owner-approved, elevated step (`--setup-account`):
//! the `RaikerSandbox` user and `RaikerSandboxUsers` group, the task-copy base
//! `C:\RaikerSandbox` (granted only that group), an outbound firewall block for
//! the account, an inherited deny for the group on every other fixed drive's
//! root, and the account password sealed with DPAPI for the owner. Launching
//! needs no elevation: `CreateProcessWithLogonW`, suspended, assigned to a Job
//! Object with UI restrictions, then resumed.
//!
//! What this does not yet cover, and says so: Windows Firewall does not filter
//! loopback, so local services remain reachable; and an *explicit* allow on a
//! folder below a denied drive root outranks the inherited deny. The probe
//! measures both rather than assuming them.

use super::*;
use std::fs;
use windows_sys::Win32::NetworkManagement::NetManagement::{
    LOCALGROUP_INFO_1, LOCALGROUP_MEMBERS_INFO_3, NetLocalGroupAdd, NetLocalGroupAddMembers,
    NetLocalGroupDel, NetUserAdd, NetUserDel, UF_DONT_EXPIRE_PASSWD, UF_PASSWD_CANT_CHANGE,
    UF_SCRIPT, USER_INFO_1, USER_PRIV_USER,
};
use windows_sys::Win32::Security::Cryptography::{
    BCRYPT_USE_SYSTEM_PREFERRED_RNG, BCryptGenRandom, CRYPT_INTEGER_BLOB,
    CRYPTPROTECT_UI_FORBIDDEN, CryptProtectData, CryptUnprotectData,
};
use windows_sys::Win32::Security::{
    GetSecurityDescriptorDacl, LookupAccountNameW, SID_NAME_USE, TOKEN_ELEVATION, TokenElevation,
};
use windows_sys::Win32::Storage::FileSystem::{GetDriveTypeW, GetLogicalDrives};
use windows_sys::Win32::System::JobObjects::{
    JOB_OBJECT_UILIMIT_DESKTOP, JOB_OBJECT_UILIMIT_DISPLAYSETTINGS, JOB_OBJECT_UILIMIT_EXITWINDOWS,
    JOB_OBJECT_UILIMIT_GLOBALATOMS, JOB_OBJECT_UILIMIT_HANDLES, JOB_OBJECT_UILIMIT_READCLIPBOARD,
    JOB_OBJECT_UILIMIT_SYSTEMPARAMETERS, JOB_OBJECT_UILIMIT_WRITECLIPBOARD,
    JOBOBJECT_BASIC_UI_RESTRICTIONS, JobObjectBasicUIRestrictions,
};
use windows_sys::Win32::System::SystemInformation::GetSystemWindowsDirectoryW;
use windows_sys::Win32::System::Threading::{
    CreateProcessWithLogonW, LOGON_WITH_PROFILE, STARTUPINFOW,
};

pub const ACCOUNT: &str = "RaikerSandbox";
pub const GROUP: &str = "RaikerSandboxUsers";
const FIREWALL_RULE: &str = "RaikerSandboxBlockOutbound";
const DRIVE_FIXED: u32 = 3;
const NERR_SUCCESS: u32 = 0;
const NERR_USER_EXISTS: u32 = 2224;
const NERR_GROUP_EXISTS: u32 = 2223;
const ERROR_ALIAS_EXISTS: u32 = 1379;
const ERROR_MEMBER_IN_ALIAS: u32 = 1378;
const NERR_USER_NOT_FOUND: u32 = 2221;
const NERR_GROUP_NOT_FOUND: u32 = 2220;
const ERROR_NO_SUCH_ALIAS: u32 = 1376;

/// `C:\` — the drive Windows itself is on, where the task copies live.
fn system_drive() -> Result<PathBuf, String> {
    let mut buffer = [0u16; 260];
    let length = unsafe { GetSystemWindowsDirectoryW(buffer.as_mut_ptr(), buffer.len() as u32) };
    if length < 3 {
        return Err("native_sandbox_account_system_drive_unknown".into());
    }
    Ok(PathBuf::from(String::from_utf16_lossy(&buffer[..3])))
}

pub fn base() -> Result<PathBuf, String> {
    Ok(system_drive()?.join("RaikerSandbox"))
}

fn credential_path() -> Result<PathBuf, String> {
    let data = std::env::var_os("ProgramData")
        .map(PathBuf::from)
        .unwrap_or(system_drive()?.join("ProgramData"));
    Ok(data.join("Raiker").join("sandbox-account.dat"))
}

/// Whether the account boundary is set up for this owner.
pub fn status() -> Value {
    let base = base().ok();
    let sid = account_sid(GROUP).ok();
    let password = credential().is_ok();
    let configured = base.as_ref().is_some_and(|path| path.is_dir()) && sid.is_some() && password;
    json!({
        "configured": configured,
        "account": ACCOUNT,
        "base": base.map(|path| path.to_string_lossy().into_owned()),
        "group_present": sid.is_some(),
        "credential_readable": password,
    })
}

fn elevated() -> bool {
    let mut token: HANDLE = null_mut();
    if unsafe { OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &mut token) } == 0 {
        return false;
    }
    let mut elevation = TOKEN_ELEVATION { TokenIsElevated: 0 };
    let mut size = 0u32;
    let ok = unsafe {
        GetTokenInformation(
            token,
            TokenElevation,
            &mut elevation as *mut _ as *mut c_void,
            size_of::<TOKEN_ELEVATION>() as u32,
            &mut size,
        )
    };
    unsafe { CloseHandle(token) };
    ok != 0 && elevation.TokenIsElevated != 0
}

/// The owner's one-time, elevated setup. Idempotent: each step is skipped
/// when already in place, so a repeated setup repairs rather than duplicates.
pub fn setup() -> Result<Value, String> {
    if !elevated() {
        return Err("native_sandbox_account_setup_requires_elevation".into());
    }
    let owner = current_user_sid_text()?;
    ensure_group()?;
    let password = random_password()?;
    let created = ensure_user(&password)?;
    if created || credential().is_err() {
        // A fresh password is set only with a fresh account or a missing
        // credential; otherwise the stored one keeps working.
        if !created {
            set_password(&password)?;
        }
        store_credential(&password, &owner)?;
    }
    add_member()?;
    let group = account_sid(GROUP)?;
    let account_text = sid_text(account_sid(ACCOUNT)?.as_ptr() as PSID)?;
    create_base(&owner, &account_text)?;
    firewall_block(&account_text)?;
    let denied = deny_other_drives(group.as_ptr() as PSID)?;
    Ok(json!({
        "configured": true,
        "base": base()?.to_string_lossy(),
        "denied_drives": denied,
        "firewall_rule": FIREWALL_RULE,
    }))
}

/// Undo everything setup did. Elevated; best effort per step, all attempted.
pub fn reset() -> Result<(), String> {
    if !elevated() {
        return Err("native_sandbox_account_setup_requires_elevation".into());
    }
    let mut failures = Vec::new();
    if let Ok(group) = account_sid(GROUP) {
        for drive in other_fixed_drives()? {
            if set_entry(&drive, group.as_ptr() as PSID, 0, REVOKE_ACCESS, false).is_err() {
                failures.push(format!("drive:{}", drive.display()));
            }
        }
    }
    let _ = powershell(&format!(
        "Remove-NetFirewallRule -Name '{FIREWALL_RULE}' -ErrorAction SilentlyContinue"
    ));
    if let Ok(path) = base()
        && path.exists()
        && fs::remove_dir_all(&path).is_err()
    {
        failures.push("base".into());
    }
    if let Ok(path) = credential_path() {
        let _ = fs::remove_file(path);
    }
    let user = wide(ACCOUNT);
    let code = unsafe { NetUserDel(null(), user.as_ptr()) };
    if code != NERR_SUCCESS && code != NERR_USER_NOT_FOUND {
        failures.push(format!("user:{code}"));
    }
    let group = wide(GROUP);
    let code = unsafe { NetLocalGroupDel(null(), group.as_ptr()) };
    if code != NERR_SUCCESS && code != NERR_GROUP_NOT_FOUND && code != ERROR_NO_SUCH_ALIAS {
        failures.push(format!("group:{code}"));
    }
    if failures.is_empty() {
        Ok(())
    } else {
        Err(format!(
            "native_sandbox_account_reset_incomplete:{}",
            failures.join(",")
        ))
    }
}

fn ensure_group() -> Result<(), String> {
    let mut name = wide(GROUP);
    let mut comment = wide("Raiker task sandbox: granted only the task copies.");
    let info = LOCALGROUP_INFO_1 {
        lgrpi1_name: name.as_mut_ptr(),
        lgrpi1_comment: comment.as_mut_ptr(),
    };
    let code = unsafe { NetLocalGroupAdd(null(), 1, &info as *const _ as *const u8, null_mut()) };
    match code {
        NERR_SUCCESS | NERR_GROUP_EXISTS | ERROR_ALIAS_EXISTS => Ok(()),
        other => Err(format!("native_sandbox_account_group_failed:{other}")),
    }
}

fn ensure_user(password: &str) -> Result<bool, String> {
    let mut name = wide(ACCOUNT);
    let mut secret = wide(password);
    let mut comment = wide("Runs Raiker's sandboxed build commands. Not for sign-in.");
    let info = USER_INFO_1 {
        usri1_name: name.as_mut_ptr(),
        usri1_password: secret.as_mut_ptr(),
        usri1_password_age: 0,
        usri1_priv: USER_PRIV_USER,
        usri1_home_dir: null_mut(),
        usri1_comment: comment.as_mut_ptr(),
        usri1_flags: UF_SCRIPT | UF_DONT_EXPIRE_PASSWD | UF_PASSWD_CANT_CHANGE,
        usri1_script_path: null_mut(),
    };
    let code = unsafe { NetUserAdd(null(), 1, &info as *const _ as *const u8, null_mut()) };
    secret.iter_mut().for_each(|unit| *unit = 0);
    match code {
        NERR_SUCCESS => Ok(true),
        NERR_USER_EXISTS => Ok(false),
        other => Err(format!("native_sandbox_account_user_failed:{other}")),
    }
}

fn set_password(password: &str) -> Result<(), String> {
    // `net user` is the documented administrative interface; the password
    // travels on its command line only inside this elevated setup process.
    let system = system_drive()?
        .join("Windows")
        .join("System32")
        .join("net.exe");
    let status = std::process::Command::new(system)
        .args(["user", ACCOUNT, password])
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status()
        .map_err(|_| "native_sandbox_account_password_failed")?;
    if status.success() {
        Ok(())
    } else {
        Err("native_sandbox_account_password_failed".into())
    }
}

fn add_member() -> Result<(), String> {
    let group = wide(GROUP);
    let mut member = wide(ACCOUNT);
    let info = LOCALGROUP_MEMBERS_INFO_3 {
        lgrmi3_domainandname: member.as_mut_ptr(),
    };
    let code = unsafe {
        NetLocalGroupAddMembers(null(), group.as_ptr(), 3, &info as *const _ as *const u8, 1)
    };
    match code {
        NERR_SUCCESS | ERROR_MEMBER_IN_ALIAS => Ok(()),
        other => Err(format!("native_sandbox_account_membership_failed:{other}")),
    }
}

/// A SID buffer for a local account or group name.
fn account_sid(name: &str) -> Result<Vec<u8>, String> {
    let wide_name = wide(name);
    let mut sid_size = 0u32;
    let mut domain_size = 0u32;
    let mut kind: SID_NAME_USE = 0;
    unsafe {
        LookupAccountNameW(
            null(),
            wide_name.as_ptr(),
            null_mut(),
            &mut sid_size,
            null_mut(),
            &mut domain_size,
            &mut kind,
        )
    };
    if sid_size == 0 {
        return Err("native_sandbox_account_missing".into());
    }
    let mut sid = vec![0u8; sid_size as usize];
    let mut domain = vec![0u16; domain_size as usize];
    let ok = unsafe {
        LookupAccountNameW(
            null(),
            wide_name.as_ptr(),
            sid.as_mut_ptr() as PSID,
            &mut sid_size,
            domain.as_mut_ptr(),
            &mut domain_size,
            &mut kind,
        )
    };
    if ok == 0 {
        return Err("native_sandbox_account_missing".into());
    }
    Ok(sid)
}

fn random_password() -> Result<String, String> {
    let mut bytes = [0u8; 48];
    let status = unsafe {
        BCryptGenRandom(
            null_mut(),
            bytes.as_mut_ptr(),
            bytes.len() as u32,
            BCRYPT_USE_SYSTEM_PREFERRED_RNG,
        )
    };
    if status != 0 {
        return Err("native_sandbox_account_random_failed".into());
    }
    // Mixed classes satisfy the local complexity policy; the length is the strength.
    const ALPHABET: &[u8] = b"ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
    let mut password: String = bytes
        .iter()
        .map(|byte| ALPHABET[*byte as usize % ALPHABET.len()] as char)
        .collect();
    password.push_str("aA9!");
    Ok(password)
}

fn store_credential(password: &str, owner: &str) -> Result<(), String> {
    let path = credential_path()?;
    let directory = path
        .parent()
        .ok_or("native_sandbox_account_credential_failed")?;
    fs::create_dir_all(directory).map_err(|_| "native_sandbox_account_credential_failed")?;
    // Only the owner, SYSTEM and Administrators may read the sealed blob.
    restrict(
        directory,
        &format!("D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;{owner})"),
    )?;
    let mut plain = password.as_bytes().to_vec();
    let input = CRYPT_INTEGER_BLOB {
        cbData: plain.len() as u32,
        pbData: plain.as_mut_ptr(),
    };
    let mut output = CRYPT_INTEGER_BLOB {
        cbData: 0,
        pbData: null_mut(),
    };
    let ok = unsafe {
        CryptProtectData(
            &input,
            null(),
            null(),
            null(),
            null(),
            CRYPTPROTECT_UI_FORBIDDEN,
            &mut output,
        )
    };
    plain.iter_mut().for_each(|byte| *byte = 0);
    if ok == 0 {
        return Err("native_sandbox_account_credential_failed".into());
    }
    let sealed =
        unsafe { std::slice::from_raw_parts(output.pbData, output.cbData as usize) }.to_vec();
    unsafe { LocalFree(output.pbData as HLOCAL) };
    fs::write(&path, sealed).map_err(|_| "native_sandbox_account_credential_failed".into())
}

fn credential() -> Result<String, String> {
    let mut sealed =
        fs::read(credential_path()?).map_err(|_| "native_sandbox_account_not_configured")?;
    let input = CRYPT_INTEGER_BLOB {
        cbData: sealed.len() as u32,
        pbData: sealed.as_mut_ptr(),
    };
    let mut output = CRYPT_INTEGER_BLOB {
        cbData: 0,
        pbData: null_mut(),
    };
    let ok = unsafe {
        CryptUnprotectData(
            &input,
            null_mut(),
            null(),
            null(),
            null(),
            CRYPTPROTECT_UI_FORBIDDEN,
            &mut output,
        )
    };
    if ok == 0 {
        return Err("native_sandbox_account_credential_unreadable".into());
    }
    let bytes =
        unsafe { std::slice::from_raw_parts(output.pbData, output.cbData as usize) }.to_vec();
    unsafe { LocalFree(output.pbData as HLOCAL) };
    String::from_utf8(bytes).map_err(|_| "native_sandbox_account_credential_unreadable".into())
}

/// Replace a directory's DACL with the given protected SDDL.
fn restrict(path: &Path, sddl: &str) -> Result<(), String> {
    let text = wide(sddl);
    let mut descriptor: PSECURITY_DESCRIPTOR = null_mut();
    if unsafe {
        ConvertStringSecurityDescriptorToSecurityDescriptorW(
            text.as_ptr(),
            SDDL_REVISION_1,
            &mut descriptor,
            null_mut(),
        )
    } == 0
    {
        return Err("native_sandbox_account_acl_failed".into());
    }
    let mut present = 0i32;
    let mut defaulted = 0i32;
    let mut acl: *mut ACL = null_mut();
    unsafe { GetSecurityDescriptorDacl(descriptor, &mut present, &mut acl, &mut defaulted) };
    let target = wide(&path.to_string_lossy());
    let written = unsafe {
        SetNamedSecurityInfoW(
            target.as_ptr(),
            SE_FILE_OBJECT,
            DACL_SECURITY_INFORMATION | PROTECTED_DACL,
            null_mut(),
            null_mut(),
            acl,
            null(),
        )
    };
    unsafe { LocalFree(descriptor as HLOCAL) };
    if written == 0 {
        Ok(())
    } else {
        Err("native_sandbox_account_acl_failed".into())
    }
}

fn create_base(owner: &str, account: &str) -> Result<(), String> {
    let path = base()?;
    fs::create_dir_all(&path).map_err(|_| "native_sandbox_account_base_failed")?;
    // The account gets no standing access to the base or any copy in it: only
    // read-attributes on the base itself (toolchains stat every ancestor), not
    // inherited. Each launch grants it the one copy it runs in (`CopyGrant`),
    // so a command cannot reach another session's copy.
    restrict(
        &path,
        &format!(
            "D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;{owner})(A;;0x100080;;;{account})"
        ),
    )
}

/// Modify on exactly one copy, for exactly one run; revoked on every exit.
struct CopyGrant {
    root: PathBuf,
    sid: Vec<u8>,
}

impl CopyGrant {
    fn apply(root: &Path) -> Result<CopyGrant, String> {
        let sid = account_sid(ACCOUNT)?;
        set_entry(root, sid.as_ptr() as PSID, 0x0013_01bf, SET_ACCESS, false)?;
        Ok(CopyGrant {
            root: root.to_path_buf(),
            sid,
        })
    }
}

impl Drop for CopyGrant {
    fn drop(&mut self) {
        let _ = set_entry(
            &self.root,
            self.sid.as_ptr() as PSID,
            0,
            REVOKE_ACCESS,
            false,
        );
    }
}

fn powershell(script: &str) -> Result<(), String> {
    let program = system_drive()?
        .join("Windows")
        .join("System32")
        .join("WindowsPowerShell")
        .join("v1.0")
        .join("powershell.exe");
    let status = std::process::Command::new(program)
        .args(["-NoProfile", "-NonInteractive", "-Command", script])
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status()
        .map_err(|_| "native_sandbox_account_firewall_failed")?;
    if status.success() {
        Ok(())
    } else {
        Err("native_sandbox_account_firewall_failed".into())
    }
}

fn firewall_block(account_sid: &str) -> Result<(), String> {
    // Arguments are constants and a SID string Windows produced; nothing here
    // comes from a command or a workspace.
    powershell(&format!(
        "Remove-NetFirewallRule -Name '{FIREWALL_RULE}' -ErrorAction SilentlyContinue; \
         New-NetFirewallRule -Name '{FIREWALL_RULE}' -DisplayName 'Raiker sandbox: block outbound' \
         -Direction Outbound -Action Block -Profile Any -LocalUser 'D:(A;;CC;;;{account_sid})' | Out-Null"
    ))
}

fn other_fixed_drives() -> Result<Vec<PathBuf>, String> {
    let system = system_drive()?;
    let mask = unsafe { GetLogicalDrives() };
    let mut drives = Vec::new();
    for index in 0..26u32 {
        if mask & (1 << index) == 0 {
            continue;
        }
        let root = PathBuf::from(format!("{}:\\", (b'A' + index as u8) as char));
        let wide_root = wide(&root.to_string_lossy());
        if unsafe { GetDriveTypeW(wide_root.as_ptr()) } == DRIVE_FIXED
            && !root
                .to_string_lossy()
                .eq_ignore_ascii_case(&system.to_string_lossy())
        {
            drives.push(root);
        }
    }
    Ok(drives)
}

fn deny_other_drives(group: PSID) -> Result<Vec<String>, String> {
    let mut denied = Vec::new();
    for drive in other_fixed_drives()? {
        if !has_explicit_ace(&drive, group, ACE_TYPE_DENIED)? {
            eprintln!(
                "Protecting {} from the sandbox account (this can take a while)...",
                drive.display()
            );
            set_entry(&drive, group, GENERIC_ALL, DENY_ACCESS, false)?;
        }
        denied.push(drive.to_string_lossy().into_owned());
    }
    Ok(denied)
}

/// Run one governed command as the sandbox account.
pub fn launch(policy: &LaunchPolicy, argv: &[String]) -> Result<i32, String> {
    let base = base()?;
    let root = strip_verbatim(
        &policy
            .workspace_root
            .canonicalize()
            .map_err(|_| "runner_policy_workspace_unreadable")?,
    );
    // A copy is a direct child of the base, so its grant covers it and nothing
    // beside it.
    if root.parent() != Some(base.as_path()) {
        return Err("native_sandbox_account_workspace_outside_base".into());
    }
    let password = credential()?;
    let _grant = CopyGrant::apply(&root)?;
    let job = create_job(policy)?;
    restrict_ui(job)?;
    let descriptor = PipeDescriptor::build(
        &current_user_sid_text()?,
        &sid_text(account_sid(ACCOUNT)?.as_ptr() as PSID)?,
    )?;
    let stdin = Pipe::create(&descriptor, PipeEnd::Write)?;
    let stdout = Pipe::create(&descriptor, PipeEnd::Read)?;
    let stderr = Pipe::create(&descriptor, PipeEnd::Read)?;

    let mut startup: STARTUPINFOW = unsafe { std::mem::zeroed() };
    startup.cb = size_of::<STARTUPINFOW>() as u32;
    startup.dwFlags = STARTF_USESTDHANDLES;
    startup.hStdInput = stdin.child;
    startup.hStdOutput = stdout.child;
    startup.hStdError = stderr.child;
    let user = wide(ACCOUNT);
    let domain = wide(".");
    let mut secret = wide(&password);
    let mut command_line = wide(&command_line_for(argv));
    let directory = wide(&policy.cwd.to_string_lossy());
    let mut information: PROCESS_INFORMATION = unsafe { std::mem::zeroed() };
    // A null environment is built from the sandbox account's own profile, so
    // no variable of the owner's — token, path or home — reaches the command.
    let created = unsafe {
        CreateProcessWithLogonW(
            user.as_ptr(),
            domain.as_ptr(),
            secret.as_ptr(),
            LOGON_WITH_PROFILE,
            null(),
            command_line.as_mut_ptr(),
            CREATE_SUSPENDED | 0x0000_0400,
            null(),
            directory.as_ptr(),
            &startup,
            &mut information,
        )
    };
    secret.iter_mut().for_each(|unit| *unit = 0);
    if created == 0 {
        let code = std::io::Error::last_os_error().raw_os_error().unwrap_or(0);
        unsafe { CloseHandle(job) };
        return Err(format!("native_sandbox_launch_failed:{code}"));
    }
    assign_and_resume(job, &information)?;
    stdin.close_child();
    stdout.close_child();
    stderr.close_child();
    let out = pump(stdout.parent as usize, true);
    let err = pump(stderr.parent as usize, false);
    let stdin_parent = stdin.parent as usize;
    std::thread::spawn(move || {
        let mut sink = unsafe { File::from_raw_handle(stdin_parent as RawHandle) };
        let _ = std::io::copy(&mut std::io::stdin(), &mut sink);
    });
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

/// No reaching the owner's windows, clipboard, desktop or session settings.
fn restrict_ui(job: HANDLE) -> Result<(), String> {
    let limits = JOBOBJECT_BASIC_UI_RESTRICTIONS {
        UIRestrictionsClass: JOB_OBJECT_UILIMIT_HANDLES
            | JOB_OBJECT_UILIMIT_READCLIPBOARD
            | JOB_OBJECT_UILIMIT_WRITECLIPBOARD
            | JOB_OBJECT_UILIMIT_SYSTEMPARAMETERS
            | JOB_OBJECT_UILIMIT_DISPLAYSETTINGS
            | JOB_OBJECT_UILIMIT_GLOBALATOMS
            | JOB_OBJECT_UILIMIT_DESKTOP
            | JOB_OBJECT_UILIMIT_EXITWINDOWS,
    };
    let set = unsafe {
        SetInformationJobObject(
            job,
            JobObjectBasicUIRestrictions,
            &limits as *const _ as *const c_void,
            size_of::<JOBOBJECT_BASIC_UI_RESTRICTIONS>() as u32,
        )
    };
    if set == 0 {
        unsafe { CloseHandle(job) };
        return Err("native_sandbox_job_object_failed".into());
    }
    Ok(())
}

/// Measure this boundary the way the AppContainer probe does: every
/// observation twice, inside as the sandbox account and outside as the owner.
pub fn probe() -> Value {
    match measure() {
        Ok(value) => value,
        Err(reason) => unavailable(&reason),
    }
}

fn measure() -> Result<Value, String> {
    let nonce = selftest::probe_nonce();
    let scratch = base()?.join(&nonce);
    fs::create_dir(&scratch).map_err(|_| "native_sandbox_probe_storage_unavailable")?;
    let outcome = measure_in(&scratch, &nonce);
    let _ = fs::remove_dir_all(&scratch);
    outcome
}

fn measure_in(scratch: &Path, nonce: &str) -> Result<Value, String> {
    // The runner is copied into the copy area: the account cannot read the
    // install directory, any more than it can read the owner's other files.
    let current = std::env::current_exe().map_err(|_| "native_sandbox_runner_unreadable")?;
    let child = scratch.join("runner.exe");
    fs::copy(&current, &child).map_err(|_| "native_sandbox_runner_unreadable")?;
    // Owner-only targets: the owner's temp folder stands for the profile, and
    // every denied drive root for the data drives.
    let owner_temp = strip_verbatim(
        &std::env::temp_dir()
            .canonicalize()
            .map_err(|_| "native_sandbox_probe_storage_unavailable")?,
    );
    let masked = owner_temp.join(format!("{nonce}-masked"));
    fs::write(&masked, b"raiker-probe-state")
        .map_err(|_| "native_sandbox_probe_storage_unavailable")?;
    let mut outside_paths = vec![owner_temp.join(format!("{nonce}-escape.tmp"))];
    outside_paths.extend(
        other_fixed_drives()?
            .into_iter()
            .map(|drive| drive.join(format!(".{nonce}-escape.tmp"))),
    );
    let test = SelfTest {
        nonce: nonce.to_owned(),
        inside_path: scratch.join(format!(".{nonce}-inside.tmp")),
        outside_paths,
        masked_read_path: masked.clone(),
        connect_address: probe_destination(),
        spawn_grandchild: true,
        hold_for_probe: false,
    };
    let outside = selftest::attempt(&test);
    selftest::remove_probe_writes(&test);
    let policy = scratch.join("policy.json");
    fs::write(
        &policy,
        json!({
            "workspace_root": scratch, "cwd": scratch,
            "profile_name": format!("raiker.probe.{}", std::process::id()),
            "deadline_seconds": 60, "max_processes": 32,
        })
        .to_string(),
    )
    .map_err(|_| "native_sandbox_probe_storage_unavailable")?;
    let output = std::process::Command::new(&current)
        .arg("--policy")
        .arg(&policy)
        .arg("--")
        .arg(&child)
        .arg("--selftest")
        .arg(test.to_value().to_string())
        .output()
        .map_err(|_| "native_sandbox_probe_failed")?;
    let _ = fs::remove_file(&masked);
    selftest::remove_probe_writes(&test);
    let inside: Value = String::from_utf8_lossy(&output.stdout)
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
    // The runner closed the job when the command exited: a descendant still
    // alive afterwards escaped it.
    let descendant = match inside.get("descendant_pid").and_then(Value::as_u64) {
        Some(pid) => descendant_verdict(pid as u32),
        None => "indeterminate",
    };
    let enforced = relay
        && inside_write
        && escape == "enforced"
        && masked_read == "enforced"
        && network == "enforced"
        && descendant == "enforced";
    Ok(json!({
        "platform": "windows",
        "boundary": "restricted_account",
        "available": false,
        "reason": if enforced { "native_disposable_workspace_required" } else { "native_sandbox_not_enforced" },
        "network": network,
        "process_tree_stop": descendant == "enforced",
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
        "account_base": base()?.to_string_lossy(),
    }))
}

fn descendant_verdict(pid: u32) -> &'static str {
    const SYNCHRONIZE: u32 = 0x0010_0000;
    let handle = unsafe { OpenProcess(SYNCHRONIZE, 0, pid) };
    if handle.is_null() {
        // Gone, or not ours to open. Only a process we can observe exiting
        // proves anything, so an unopenable one is not counted as enforced.
        let code = std::io::Error::last_os_error().raw_os_error().unwrap_or(0);
        return if code == 87 {
            "enforced"
        } else {
            "indeterminate"
        };
    }
    let running = unsafe { WaitForSingleObject(handle, 5_000) } == WAIT_TIMEOUT;
    if running {
        unsafe { TerminateProcess(handle, 1) };
    }
    unsafe { CloseHandle(handle) };
    if running { "unenforced" } else { "enforced" }
}
