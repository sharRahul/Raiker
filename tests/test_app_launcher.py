"""``raiker-app``: starting Raiker the way each operating system expects.

The launcher's whole job is to be right on a machine that is not this one, so
every platform decision is tested by asking for that platform explicitly rather
than by whatever the test runner happens to be running on.
"""

from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest

from apps.api.launcher import (
    DEFAULT_PORT,
    _ensure_standard_streams,
    _resolve_ui_dir,
    choose_port,
    default_workspace,
    detect_os,
    main,
    port_is_free,
    raiker_is_running,
)

# ── platform detection ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("system", "expected"),
    [
        ("Windows", "windows"),
        ("Darwin", "macos"),
        ("Linux", "linux"),
        ("FreeBSD", "posix"),
        ("SunOS", "posix"),
    ],
)
def test_every_platform_resolves_to_a_supported_family(
    monkeypatch: pytest.MonkeyPatch, system: str, expected: str
) -> None:
    """An unrecognised POSIX box is supported, not refused: it has a home
    directory and a loopback interface, which is all the launcher needs."""
    monkeypatch.setattr("platform.system", lambda: system)
    assert detect_os() == expected


# ── where data lives ────────────────────────────────────────────────────────


def test_windows_data_goes_under_localappdata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAIKER_HOME", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\ada\AppData\Local")
    assert default_workspace("windows").name == "Raiker"
    assert "AppData" in str(default_workspace("windows"))


def test_macos_data_goes_under_application_support(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAIKER_HOME", raising=False)
    resolved = default_workspace("macos")
    assert resolved.parts[-3:] == ("Library", "Application Support", "Raiker")


def test_linux_data_follows_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("RAIKER_HOME", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    assert default_workspace("linux") == tmp_path / "share" / "raiker"


def test_linux_falls_back_to_local_share_without_xdg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAIKER_HOME", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    assert default_workspace("linux").parts[-3:] == (".local", "share", "raiker")


def test_raiker_home_overrides_every_platform(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Someone keeping their data on an encrypted volume should not have to
    move a whole platform convention to do it."""
    monkeypatch.setenv("RAIKER_HOME", str(tmp_path / "vault"))
    for name in ("windows", "macos", "linux", "posix"):
        assert default_workspace(name) == tmp_path / "vault"


# ── ports ───────────────────────────────────────────────────────────────────


def test_a_free_port_is_used_as_is(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("apps.api.launcher.port_is_free", lambda port, host="127.0.0.1": True)
    assert choose_port(DEFAULT_PORT) == (DEFAULT_PORT, False)


def test_an_already_running_raiker_is_joined_rather_than_fought(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two hosts over one encrypted workspace is a data-integrity problem, and
    the person who started the app wants the app — not a second copy of it."""
    monkeypatch.setattr("apps.api.launcher.port_is_free", lambda port, host="127.0.0.1": False)
    monkeypatch.setattr(
        "apps.api.launcher.raiker_is_running", lambda port, host="127.0.0.1", timeout=1.0: True
    )
    assert choose_port(DEFAULT_PORT) == (DEFAULT_PORT, True)


def test_a_port_held_by_something_else_moves_to_the_next_free_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Never hand the owner a URL belonging to someone else's server."""
    monkeypatch.setattr(
        "apps.api.launcher.port_is_free",
        lambda port, host="127.0.0.1": port != DEFAULT_PORT,
    )
    monkeypatch.setattr(
        "apps.api.launcher.raiker_is_running", lambda port, host="127.0.0.1", timeout=1.0: False
    )
    assert choose_port(DEFAULT_PORT) == (DEFAULT_PORT + 1, False)


def test_no_free_port_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("apps.api.launcher.port_is_free", lambda port, host="127.0.0.1": False)
    monkeypatch.setattr(
        "apps.api.launcher.raiker_is_running", lambda port, host="127.0.0.1", timeout=1.0: False
    )
    with pytest.raises(OSError, match="No free port"):
        choose_port(DEFAULT_PORT)


def test_a_bound_port_reads_as_unavailable() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as held:
        held.bind(("127.0.0.1", 0))
        held.listen(1)
        assert port_is_free(held.getsockname()[1]) is False


def test_a_closed_port_is_not_mistaken_for_a_raiker() -> None:
    """Anything that is not a confirmed Raiker health response is not Raiker."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        closed_port = probe.getsockname()[1]
    assert raiker_is_running(closed_port, timeout=0.2) is False


# ── the command itself ──────────────────────────────────────────────────────


def test_print_paths_reports_the_platform_and_directory_without_starting_anything(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("RAIKER_HOME", str(tmp_path / "data"))
    assert main(["--print-paths"]) == 0
    out = capsys.readouterr().out
    assert "platform:" in out
    assert str(tmp_path / "data") in out
    # Nothing was created and nothing was served.
    assert not (tmp_path / "data").exists()


def test_frozen_launcher_resolves_the_bundled_web_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundled = tmp_path / "bundle"
    (bundled / "web").mkdir(parents=True)
    (bundled / "web" / "index.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(sys, "_MEIPASS", str(bundled), raising=False)

    assert _resolve_ui_dir() == bundled / "web"


def test_windowed_launcher_supplies_null_standard_streams(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "stdin", None)
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    opened = _ensure_standard_streams()
    try:
        assert sys.stdin is not None
        assert sys.stdout is not None
        assert sys.stderr is not None
    finally:
        for stream in opened:
            stream.close()


def test_joining_a_running_host_opens_the_browser_and_exits_successfully(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    opened: list[str] = []

    def record(url: str, os_name: str | None = None) -> bool:
        opened.append(url)
        return True

    monkeypatch.setenv("RAIKER_HOME", str(tmp_path / "data"))
    monkeypatch.setattr("apps.api.launcher.choose_port", lambda preferred: (preferred, True))
    monkeypatch.setattr("apps.api.launcher.open_browser", record)

    assert main([]) == 0
    assert opened == [f"http://127.0.0.1:{DEFAULT_PORT}/"]


def test_an_unwritable_data_directory_is_reported_rather_than_crashed_through(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("", encoding="utf-8")
    monkeypatch.setenv("RAIKER_HOME", str(blocker / "raiker"))

    assert main([]) == 2
    assert "RAIKER_HOME" in capsys.readouterr().err
