from __future__ import annotations

from pathlib import Path

from raiker.app.desktop_build import pyinstaller_command


def test_windows_desktop_command_bundles_runtime_web_and_tray(tmp_path: Path) -> None:
    command = pyinstaller_command(
        source_root=tmp_path / "source",
        web_assets=tmp_path / "web",
        out_dir=tmp_path / "out",
        platform_name="win32",
    )

    joined = " ".join(command)
    assert "PyInstaller" in joined
    assert "--onedir" in command
    assert "apps" in joined and "launcher.py" in joined
    assert str(tmp_path / "web") in joined
    assert "pystray" in joined
    assert "PIL" in joined
