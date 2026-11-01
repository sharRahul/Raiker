//! The one network route inside a Linux sandbox: loopback to Raiker's proxy.
//!
//! `--unshare-net` leaves the command a network namespace with only `lo`. To
//! allow-listed downloads the runner bind-mounts itself and the host proxy's
//! Unix socket into the sandbox and starts there as
//! `--egress-bridge <socket> <port> -- <argv>`: it listens on `127.0.0.1:<port>`
//! inside the namespace, starts the command, and copies each accepted
//! connection to the socket. Nothing else is reachable — there is no route and
//! no resolver — so the proxy outside, which resolves and checks every
//! destination itself, is the only way out. The bridge carries bytes and makes
//! no decision; a connection it forwards still has to authenticate to the proxy.

use std::io::{Read, Write};
use std::net::{Shutdown, TcpListener, TcpStream};
use std::os::unix::net::UnixStream;
use std::os::unix::process::ExitStatusExt;
use std::path::Path;
use std::process::Command;

/// Where the bridge and the socket appear inside the sandbox.
pub const RUNNER_INSIDE: &str = "/run/raiker/runner";
pub const SOCKET_INSIDE: &str = "/run/raiker/egress.sock";

pub fn run(socket: &Path, port: u16, argv: &[String]) -> Result<i32, String> {
    if argv.is_empty() {
        return Err("runner_arguments_invalid".into());
    }
    let listener = TcpListener::bind(("127.0.0.1", port))
        .map_err(|_| "native_sandbox_egress_bridge_bind_failed".to_owned())?;
    let socket = socket.to_path_buf();
    std::thread::spawn(move || {
        for incoming in listener.incoming() {
            let Ok(client) = incoming else { continue };
            let socket = socket.clone();
            std::thread::spawn(move || forward(client, &socket));
        }
    });
    let status = Command::new(&argv[0])
        .args(&argv[1..])
        .status()
        .map_err(|error| {
            format!(
                "native_sandbox_launch_failed:{}",
                error.raw_os_error().unwrap_or(0)
            )
        })?;
    Ok(status
        .code()
        .unwrap_or_else(|| 128 + status.signal().unwrap_or(1)))
}

fn forward(client: TcpStream, socket: &Path) {
    let Ok(upstream) = UnixStream::connect(socket) else {
        let _ = client.shutdown(Shutdown::Both);
        return;
    };
    let (Ok(client_read), Ok(upstream_write)) = (client.try_clone(), upstream.try_clone()) else {
        return;
    };
    let outbound = std::thread::spawn(move || copy(client_read, upstream_write));
    copy(upstream, client);
    let _ = outbound.join();
}

/// Copy until either side closes, then close the other's write half.
fn copy<R: Read, W: Write + HalfClose>(mut from: R, mut to: W) {
    let mut buffer = [0u8; 64 * 1024];
    loop {
        match from.read(&mut buffer) {
            Ok(0) | Err(_) => break,
            Ok(read) => {
                if to.write_all(&buffer[..read]).is_err() {
                    break;
                }
            }
        }
    }
    to.close_write();
}

trait HalfClose {
    fn close_write(&mut self);
}

impl HalfClose for TcpStream {
    fn close_write(&mut self) {
        let _ = self.shutdown(Shutdown::Write);
    }
}

impl HalfClose for UnixStream {
    fn close_write(&mut self) {
        let _ = self.shutdown(Shutdown::Write);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::unix::net::UnixListener;

    #[test]
    fn a_loopback_connection_reaches_the_socket_and_back() {
        let directory = std::env::temp_dir().join(format!("raiker-bridge-{}", std::process::id()));
        std::fs::create_dir_all(&directory).unwrap();
        let path = directory.join("egress.sock");
        let _ = std::fs::remove_file(&path);
        let server = UnixListener::bind(&path).unwrap();
        std::thread::spawn(move || {
            let (mut stream, _) = server.accept().unwrap();
            let mut request = [0u8; 4];
            stream.read_exact(&mut request).unwrap();
            stream.write_all(b"pong").unwrap();
        });
        let listener = TcpListener::bind(("127.0.0.1", 0)).unwrap();
        let port = listener.local_addr().unwrap().port();
        let socket = path.clone();
        std::thread::spawn(move || {
            let (client, _) = listener.accept().unwrap();
            forward(client, &socket);
        });
        let mut client = TcpStream::connect(("127.0.0.1", port)).unwrap();
        client.write_all(b"ping").unwrap();
        let mut reply = [0u8; 4];
        client.read_exact(&mut reply).unwrap();
        assert_eq!(&reply, b"pong");
        std::fs::remove_dir_all(directory).unwrap();
    }
}
