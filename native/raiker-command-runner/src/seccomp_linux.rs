//! Bubblewrap consumes classic BPF instructions from an inherited file handle.
//! This denies a bounded set of kernel-administration and isolation-escape
//! syscalls; it is one layer, not a substitute for the namespace boundary.

use std::fs::File;
use std::io::{Seek, SeekFrom, Write};
use std::os::fd::FromRawFd;

#[repr(C)]
struct Instruction {
    code: u16,
    jt: u8,
    jf: u8,
    k: u32,
}

fn instruction(code: u16, jt: u8, jf: u8, k: u32) -> Instruction {
    Instruction { code, jt, jf, k }
}

pub fn filter() -> std::io::Result<File> {
    #[cfg(target_arch = "x86_64")]
    const AUDIT_ARCH: Option<u32> = Some(0xc000_003e);
    #[cfg(target_arch = "aarch64")]
    const AUDIT_ARCH: Option<u32> = Some(0xc000_00b7);
    #[cfg(not(any(target_arch = "x86_64", target_arch = "aarch64")))]
    const AUDIT_ARCH: Option<u32> = None;
    let audit_arch = AUDIT_ARCH
        .ok_or_else(|| std::io::Error::other("native_sandbox_seccomp_arch_unsupported"))?;

    const LOAD_WORD_ABS: u16 = 0x20;
    const JUMP_EQUAL: u16 = 0x15;
    const RETURN: u16 = 0x06;
    const KILL_PROCESS: u32 = 0x8000_0000;
    const ERRNO: u32 = 0x0005_0000;
    const ALLOW: u32 = 0x7fff_0000;
    let mut program = vec![
        instruction(LOAD_WORD_ABS, 0, 0, 4),
        instruction(JUMP_EQUAL, 1, 0, audit_arch),
        instruction(RETURN, 0, 0, KILL_PROCESS),
        instruction(LOAD_WORD_ABS, 0, 0, 0),
    ];
    #[cfg(target_arch = "x86_64")]
    {
        // x32 shares the x86-64 audit architecture but has its own syscall
        // numbering. Refuse that ABI rather than letting it bypass the list.
        program.push(instruction(0x45, 0, 1, 0x4000_0000));
        program.push(instruction(RETURN, 0, 0, ERRNO | libc::ENOSYS as u32));
    }
    // clone3 stores its flags behind a pointer that classic BPF cannot inspect.
    // ENOSYS lets libc retry ordinary clone for compatible thread creation.
    program.push(instruction(JUMP_EQUAL, 0, 1, libc::SYS_clone3 as u32));
    program.push(instruction(RETURN, 0, 0, ERRNO | libc::ENOSYS as u32));
    // Ordinary clone exposes flags directly. Reject namespace creation while
    // still allowing process and thread creation without namespace flags.
    const CLONE_NAMESPACE_FLAGS: u32 = 0x7e02_0000;
    program.push(instruction(JUMP_EQUAL, 0, 3, libc::SYS_clone as u32));
    program.push(instruction(LOAD_WORD_ABS, 0, 0, 16));
    program.push(instruction(0x45, 0, 1, CLONE_NAMESPACE_FLAGS));
    program.push(instruction(RETURN, 0, 0, ERRNO | libc::EPERM as u32));
    program.push(instruction(LOAD_WORD_ABS, 0, 0, 0));
    for syscall in [
        libc::SYS_mount,
        libc::SYS_umount2,
        libc::SYS_pivot_root,
        libc::SYS_ptrace,
        libc::SYS_bpf,
        libc::SYS_perf_event_open,
        libc::SYS_keyctl,
        libc::SYS_add_key,
        libc::SYS_request_key,
        libc::SYS_unshare,
        libc::SYS_setns,
        libc::SYS_userfaultfd,
        libc::SYS_open_by_handle_at,
        libc::SYS_reboot,
        libc::SYS_swapon,
        libc::SYS_swapoff,
        libc::SYS_init_module,
        libc::SYS_finit_module,
        libc::SYS_delete_module,
        libc::SYS_kexec_load,
        libc::SYS_personality,
    ] {
        program.push(instruction(JUMP_EQUAL, 0, 1, syscall as u32));
        program.push(instruction(RETURN, 0, 0, ERRNO | libc::EPERM as u32));
    }
    program.push(instruction(RETURN, 0, 0, ALLOW));
    let raw = unsafe { libc::memfd_create(c"raiker-seccomp".as_ptr(), libc::MFD_CLOEXEC) };
    if raw < 0 {
        return Err(std::io::Error::last_os_error());
    }
    let mut file = unsafe { File::from_raw_fd(raw) };
    let bytes = unsafe {
        std::slice::from_raw_parts(
            program.as_ptr().cast::<u8>(),
            program.len() * std::mem::size_of::<Instruction>(),
        )
    };
    file.write_all(bytes)?;
    file.seek(SeekFrom::Start(0))?;
    Ok(file)
}
