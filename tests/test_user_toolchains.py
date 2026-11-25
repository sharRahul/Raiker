"""An interpreter a toolchain manager installed in the home folder can run in the sandbox.

One install folder below a recognised store, read-only, and only when nothing in
it looks like a credential; the home folder itself stays out of reach.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from raiker.execution.commands import sandboxed_program, user_toolchains
from raiker.execution.commands.backends import native


def _uv_python(home: Path) -> Path:
    install = home / ".local" / "share" / "uv" / "python" / "cpython-3.12.8-linux-x86_64-gnu"
    (install / "bin").mkdir(parents=True)
    (install / "lib").mkdir()
    (install / "lib" / "os.py").write_text("# stdlib\n", encoding="utf-8")
    interpreter = install / "bin" / "python3"
    interpreter.write_text("", encoding="utf-8")
    return interpreter


def test_the_install_folder_is_the_one_below_the_store(tmp_path: Path) -> None:
    interpreter = _uv_python(tmp_path)
    prefix = user_toolchains.install_prefix(interpreter, tmp_path)
    assert prefix == interpreter.parent.parent
    assert user_toolchains.reachable_prefix(interpreter, tmp_path) == prefix


def test_anything_else_in_the_home_is_not_an_install(tmp_path: Path) -> None:
    other = tmp_path / "bin" / "python3"
    other.parent.mkdir()
    other.write_text("", encoding="utf-8")
    assert user_toolchains.install_prefix(other, tmp_path) is None
    # The store itself, with no version folder between, is not one either.
    store = tmp_path / ".pyenv" / "versions"
    store.mkdir(parents=True)
    assert user_toolchains.install_prefix(store / "python", tmp_path) is None


@pytest.mark.parametrize("secret", [".npmrc", "credentials.toml", "id_ed25519", "server.pem"])
def test_an_install_holding_a_credential_is_refused(tmp_path: Path, secret: str) -> None:
    interpreter = _uv_python(tmp_path)
    prefix = interpreter.parent.parent
    (prefix / "etc").mkdir()
    (prefix / "etc" / secret).write_text("token\n", encoding="utf-8")
    assert user_toolchains.refusal(prefix) == "user_toolchain_holds_credentials"
    assert user_toolchains.reachable_prefix(interpreter, tmp_path) is None


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privilege on Windows")
def test_an_install_linking_out_of_itself_is_refused(tmp_path: Path) -> None:
    interpreter = _uv_python(tmp_path)
    notes = tmp_path / "notes"
    notes.mkdir()
    os.symlink(notes, interpreter.parent.parent / "lib" / "notes")
    assert user_toolchains.refusal(interpreter.parent.parent) == "user_toolchain_link_leaves_install"


def test_the_sandbox_finds_a_home_toolchain_interpreter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    interpreter = _uv_python(home)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(sandboxed_program.sys, "platform", "linux")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    monkeypatch.setattr(sandboxed_program.shutil, "which", lambda name, path=None: str(interpreter))
    found = sandboxed_program.sandbox_interpreter("python3", str(interpreter.parent), workspace)
    assert found == interpreter.absolute()


def test_a_plain_home_interpreter_is_still_passed_over(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    loose = home / "bin" / "python3"
    loose.parent.mkdir(parents=True)
    loose.write_text("", encoding="utf-8")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(sandboxed_program.sys, "platform", "linux")
    monkeypatch.setattr(sandboxed_program.shutil, "which", lambda name, path=None: str(loose))
    with pytest.raises(FileNotFoundError):
        sandboxed_program.sandbox_interpreter("python3", str(loose.parent), tmp_path / "ws")


def test_linux_mounts_only_the_install_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    interpreter = _uv_python(home)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(native.sys, "platform", "linux")
    mounts = native.toolchain_mounts(interpreter, tmp_path / "ws")
    assert mounts == [str(interpreter.parent.parent)]


def test_windows_and_macos_run_a_cached_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    interpreter = _uv_python(home)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(user_toolchains, "needs_copy", lambda: True)
    base = tmp_path / "sandbox-base"
    first = sandboxed_program._reachable_interpreter(interpreter, base)
    assert base / "toolchains" in first.parents
    assert first.name == "python3" and (first.parent.parent / "lib" / "os.py").is_file()
    # Reused, not copied again.
    assert sandboxed_program._reachable_interpreter(interpreter, base) == first
