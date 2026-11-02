//! Terminals for the Windows restricted account, through a pseudo-console.
//!
//! `CreateProcessWithLogonW` cannot attach a pseudo-console: the attribute
//! list that carries one is not among its parameters, and a pseudo-console
//! is built in its creator's context. So a terminal run starts a broker as
//! the account instead of the command: this runner, in `--conpty-host` mode.
//! The broker creates the pseudo-console as the account, starts the command
//! attached to it, and relays bytes both ways over the stdio pipes the
//! owner-side runner gave it. Everything stays inside the run's Job Object:
//! the broker was assigned to it suspended, and the console host and the
//! command are its descendants.
//!
//! The broker's binary is a copy of the runner placed where only the account
//! may read and run it ([`broker_path`]), deleted when the run ends.

use super::*;
use std::io::{Read, Write};
use windows_sys::Win32::System::Console::{COORD, ClosePseudoConsole, CreatePseudoConsole, HPCON};
use windows_sys::Win32::System::Threading::{
    CreateProcessW, DeleteProcThreadAttributeList, EXTENDED_STARTUPINFO_PRESENT, INFINITE,
    InitializeProcThreadAttributeList, LPPROC_THREAD_ATTRIBUTE_LIST, STARTUPINFOEXW,
    UpdateProcThreadAttribute, WaitForSingleObject,
};

/// `PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE`.
const PSEUDOCONSOLE_ATTRIBUTE: usize = 0x0002_0016;

/// The terminal's size until the owner's view resizes it (not yet relayed).
pub const COLUMNS: i16 = 120;
pub const ROWS: i16 = 30;

/// `--conpty-host -- <argv…>`, running as the account: the command on a
/// pseudo-console, its terminal relayed over this process's stdio.
pub fn host(argv: &[String]) -> Result<i32, String> {
    if argv.is_empty() {
        return Err("runner_arguments_invalid".into());
    }
    let failure = "native_sandbox_pty_unavailable";
    let (input_read, input_write) = anonymous_pipe().ok_or(failure)?;
    let (output_read, output_write) = anonymous_pipe().ok_or(failure)?;
    let mut console: HPCON = 0;
    let created = unsafe {
        CreatePseudoConsole(
            COORD {
                X: COLUMNS,
                Y: ROWS,
            },
            input_read,
            output_write,
            0,
            &mut console,
        )
    };
    // The console host holds its own duplicates of these ends.
    unsafe {
        CloseHandle(input_read);
        CloseHandle(output_write);
    }
    if created != 0 {
        unsafe {
            CloseHandle(input_write);
            CloseHandle(output_read);
        }
        return Err(format!("{failure}:{created:#x}"));
    }
    let child = match start_attached(argv, console) {
        Ok(child) => child,
        Err(reason) => {
            unsafe {
                ClosePseudoConsole(console);
                CloseHandle(input_write);
                CloseHandle(output_read);
            }
            return Err(reason);
        }
    };
    // Terminal output to our stdout, until the console host closes it.
    let output = output_read as usize;
    let reader = std::thread::spawn(move || {
        let mut source = unsafe { File::from_raw_handle(output as RawHandle) };
        let mut stdout = std::io::stdout();
        let mut buffer = [0u8; 4096];
        loop {
            match source.read(&mut buffer) {
                Ok(0) | Err(_) => break,
                Ok(count) => {
                    if stdout.write_all(&buffer[..count]).is_err() {
                        break;
                    }
                    let _ = stdout.flush();
                }
            }
        }
    });
    // Our stdin to the terminal's input. Not joined: stdin may never close.
    let input = input_write as usize;
    std::thread::spawn(move || {
        let mut sink = unsafe { File::from_raw_handle(input as RawHandle) };
        let _ = std::io::copy(&mut std::io::stdin(), &mut sink);
    });
    unsafe { WaitForSingleObject(child, INFINITE) };
    let mut code: u32 = 1;
    unsafe { GetExitCodeProcess(child, &mut code) };
    unsafe { CloseHandle(child) };
    // Closing the console makes the host flush and close the output pipe.
    unsafe { ClosePseudoConsole(console) };
    let _ = reader.join();
    Ok(code as i32)
}

fn anonymous_pipe() -> Option<(HANDLE, HANDLE)> {
    let mut read: HANDLE = null_mut();
    let mut write: HANDLE = null_mut();
    if unsafe { CreatePipe(&mut read, &mut write, null(), 0) } == 0 {
        return None;
    }
    Some((read, write))
}

/// Start *argv* attached to *console*; returns its process handle.
fn start_attached(argv: &[String], console: HPCON) -> Result<HANDLE, String> {
    let failure = "native_sandbox_pty_unavailable";
    let mut size = 0usize;
    unsafe { InitializeProcThreadAttributeList(null_mut(), 1, 0, &mut size) };
    let mut storage = vec![0u8; size];
    let list = storage.as_mut_ptr() as LPPROC_THREAD_ATTRIBUTE_LIST;
    if unsafe { InitializeProcThreadAttributeList(list, 1, 0, &mut size) } == 0 {
        return Err(failure.into());
    }
    let attached = unsafe {
        UpdateProcThreadAttribute(
            list,
            0,
            PSEUDOCONSOLE_ATTRIBUTE,
            console as *const c_void,
            size_of::<HPCON>(),
            null_mut(),
            null(),
        )
    };
    if attached == 0 {
        unsafe { DeleteProcThreadAttributeList(list) };
        return Err(failure.into());
    }
    let mut startup: STARTUPINFOEXW = unsafe { std::mem::zeroed() };
    startup.StartupInfo.cb = size_of::<STARTUPINFOEXW>() as u32;
    // Standard handles left empty on purpose: with `STARTF_USESTDHANDLES`
    // and none given, the command uses the pseudo-console rather than the
    // broker's own redirected pipes.
    startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES;
    startup.lpAttributeList = list;
    let mut command_line = wide(&command_line_for(argv));
    let mut information: PROCESS_INFORMATION = unsafe { std::mem::zeroed() };
    let created = unsafe {
        CreateProcessW(
            null(),
            command_line.as_mut_ptr(),
            null(),
            null(),
            0,
            EXTENDED_STARTUPINFO_PRESENT,
            null(),
            null(),
            &startup.StartupInfo,
            &mut information,
        )
    };
    unsafe { DeleteProcThreadAttributeList(list) };
    if created == 0 {
        let code = std::io::Error::last_os_error().raw_os_error().unwrap_or(0);
        return Err(format!("native_sandbox_launch_failed:{code}"));
    }
    unsafe { CloseHandle(information.hThread) };
    Ok(information.hProcess)
}

/// Where a run's broker binary goes: a folder under the base that the owner
/// controls and the account may only read and execute. One file per run.
pub fn broker_path(base: &Path, owner_sid: &str, account_sid: &str) -> Result<PathBuf, String> {
    let failure = "native_sandbox_pty_broker_unavailable";
    let folder = base.join(".broker");
    if !folder.exists() {
        std::fs::create_dir(&folder).map_err(|_| failure.to_owned())?;
    }
    restrict_folder(
        &folder,
        &format!(
            "D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;{owner_sid})(A;OICI;0x1200a9;;;{account_sid})"
        ),
    )?;
    let current = std::env::current_exe().map_err(|_| failure.to_owned())?;
    let path = folder.join(format!(
        "runner-{}-{}.exe",
        std::process::id(),
        selftest::probe_nonce()
    ));
    std::fs::copy(&current, &path).map_err(|_| failure.to_owned())?;
    Ok(path)
}

fn restrict_folder(path: &Path, sddl: &str) -> Result<(), String> {
    let failure = "native_sandbox_pty_broker_unavailable";
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
        return Err(failure.into());
    }
    let mut present = 0i32;
    let mut defaulted = 0i32;
    let mut acl: *mut ACL = null_mut();
    unsafe {
        windows_sys::Win32::Security::GetSecurityDescriptorDacl(
            descriptor,
            &mut present,
            &mut acl,
            &mut defaulted,
        )
    };
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
        Err(failure.into())
    }
}
