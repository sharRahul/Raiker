"""DESK-03 / DESK-09 / DESK-11 — the desktop window is the default way in.

``raiker-app`` opens Raiker's own window when one is installed and says why when
it falls back to the browser; a desktop shell that starts the host learns its URL
from a ready file; and a host without a display keeps running without a tray.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from raiker.app import desktop_shell, launcher, tray
from raiker.app.desktop_shell import SHELL_ENV, ShellCommand, find_shell, unavailable_reason

URL = "http://127.0.0.1:8765/"


def _source_checkout(root: Path, platform: str = "linux") -> Path:
    desktop = root / "desktop"
    electron = desktop / "node_modules" / "electron" / "dist"
    binary = {
        "win32": electron / "electron.exe",
        "darwin": electron / "Electron.app" / "Contents" / "MacOS" / "Electron",
    }.get(platform, electron / "electron")
    binary.parent.mkdir(parents=True)
    binary.write_text("")
    (desktop / "dist").mkdir()
    (desktop / "dist" / "main.js").write_text("")
    return binary


@pytest.mark.parametrize("platform", ["linux", "win32", "darwin"])
def test_a_built_source_checkout_opens_electron_with_the_shell_directory(
    tmp_path: Path, platform: str
) -> None:
    binary = _source_checkout(tmp_path, platform)
    command = find_shell(URL, environ={}, platform=platform, repository_root=tmp_path)
    assert command == ShellCommand(
        (str(binary), str(tmp_path / "desktop"), "--raiker-url", URL), "source checkout"
    )


def test_an_unbuilt_checkout_has_no_window_and_says_how_to_build_it(tmp_path: Path) -> None:
    binary = _source_checkout(tmp_path)
    (tmp_path / "desktop" / "dist" / "main.js").unlink()
    assert find_shell(URL, environ={}, repository_root=tmp_path) is None
    assert binary.is_file()
    assert "npm --prefix desktop" in unavailable_reason(environ={})


def test_the_override_names_the_executable_and_must_exist(tmp_path: Path) -> None:
    shell = tmp_path / "Raiker"
    assert find_shell(URL, environ={SHELL_ENV: str(shell)}) is None
    assert "does not name a file" in unavailable_reason(environ={SHELL_ENV: str(shell)})
    shell.write_text("")
    assert find_shell(URL, environ={SHELL_ENV: str(shell)}) == ShellCommand(
        (str(shell), "--raiker-url", URL), SHELL_ENV
    )


@pytest.mark.parametrize(
    ("platform", "shell_path"),
    [
        ("linux", Path("opt/Raiker/raiker")),
        ("win32", Path("Raiker/Raiker.exe")),
        ("darwin", Path("Raiker.app/Contents/MacOS/Raiker")),
    ],
)
def test_a_packaged_host_finds_the_shell_that_carries_it(
    tmp_path: Path, platform: str, shell_path: Path
) -> None:
    shell = tmp_path / shell_path
    shell.parent.mkdir(parents=True)
    shell.write_text("")
    resources = shell.parent.parent / "Resources" if platform == "darwin" else shell.parent / "resources"
    host = resources / "host" / ("Raiker.exe" if platform == "win32" else "Raiker")
    host.parent.mkdir(parents=True)
    host.write_text("")
    command = find_shell(URL, environ={}, platform=platform, frozen_executable=host)
    assert command == ShellCommand((str(shell), "--raiker-url", URL), "packaged")


def test_a_frozen_host_outside_a_shell_has_no_window(tmp_path: Path) -> None:
    host = tmp_path / "Raiker" / "Raiker"
    host.parent.mkdir(parents=True)
    host.write_text("")
    assert find_shell(URL, environ={}, frozen_executable=host) is None


def test_open_raiker_prefers_the_window(monkeypatch: pytest.MonkeyPatch) -> None:
    launched: list[ShellCommand] = []
    browsed: list[str] = []
    command = ShellCommand(("shell", "--raiker-url", URL), "test")
    monkeypatch.setattr(desktop_shell, "find_shell", lambda url: command)
    def launch(cmd: ShellCommand) -> bool:
        launched.append(cmd)
        return True

    def browse(url: str, os_name: str | None = None) -> bool:
        browsed.append(url)
        return True

    monkeypatch.setattr(desktop_shell, "launch", launch)
    monkeypatch.setattr(launcher, "open_browser", browse)
    assert launcher.open_raiker(URL) == "window"
    assert launched == [command]
    assert browsed == []


def test_open_raiker_falls_back_to_the_browser_and_says_why(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    browsed: list[str] = []

    def browse(url: str, os_name: str | None = None) -> bool:
        browsed.append(url)
        return True

    monkeypatch.setattr(launcher, "open_browser", browse)
    assert launcher.open_raiker(URL) == "browser"
    assert browsed == [URL]
    assert "instead of the Raiker window" in capsys.readouterr().out


def test_browser_flag_skips_the_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(desktop_shell, "find_shell", lambda url: pytest.fail("window looked up"))
    monkeypatch.setattr(launcher, "open_browser", lambda url, os_name=None: True)
    assert launcher.open_raiker(URL, browser=True) == "browser"


def test_the_ready_file_is_written_whole(tmp_path: Path) -> None:
    ready = tmp_path / "ready.json"
    launcher.write_ready_file(ready, URL, 8765, joined=True)
    record = json.loads(ready.read_text(encoding="utf-8"))
    assert record["url"] == URL
    assert record["port"] == 8765
    assert record["joined"] is True
    assert list(tmp_path.iterdir()) == [ready]


def test_joining_a_running_host_writes_the_ready_file_without_opening_anything(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(launcher, "choose_port", lambda preferred, **_: (preferred, True))
    monkeypatch.setattr(launcher, "open_raiker", lambda *a, **k: pytest.fail("opened a window"))
    ready = tmp_path / "ready.json"
    code = launcher.main(
        ["--workspace", str(tmp_path / "ws"), "--no-browser", "--ready-file", str(ready)]
    )
    assert code == 0
    assert json.loads(ready.read_text(encoding="utf-8"))["joined"] is True


def test_readiness_waits_for_the_host_rather_than_a_fixed_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter([False, False, True])
    monkeypatch.setattr(launcher, "raiker_is_running", lambda port, timeout=1.0: next(answers))
    assert launcher.wait_until_ready(8765, timeout=5, interval=0) is True
    monkeypatch.setattr(launcher, "raiker_is_running", lambda port, timeout=1.0: False)
    assert launcher.wait_until_ready(8765, timeout=0.05, interval=0) is False


def test_a_host_without_a_display_keeps_running_without_a_tray(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class DisplayNameError(Exception):
        pass

    # pystray's X11 backend raises while importing on a machine with no display.
    monkeypatch.delitem(sys.modules, "pystray", raising=False)
    import builtins

    real_import = builtins.__import__

    def failing_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "pystray":
            raise DisplayNameError('Bad display name ""')
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", failing_import)
    tray._run_native_tray("http://127.0.0.1:1", "secret")
    assert "No system tray here (DisplayNameError)" in capsys.readouterr().out
