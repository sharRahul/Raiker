# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path

from raiker.app.desktop_build import pyinstaller_command
from scripts.build_installer import _WXS


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
    assert "--windowed" in command
    assert "launcher.py" in joined
    assert str(tmp_path / "web") in joined
    assert "pystray" in joined
    assert "PIL" in joined
    # The frozen host must carry Raiker's own data files and lazily-resolved
    # modules, or it stops on its first read of `raiker/config` (DESK-12).
    assert command[command.index("--collect-data") + 1] == "raiker"
    assert command[command.index("--collect-submodules") + 1] == "raiker"


def test_windows_installer_adds_a_start_menu_shortcut_to_the_frozen_runtime() -> None:
    assert 'Id="ApplicationProgramsFolder"' in _WXS
    assert 'Name="Raiker"' in _WXS
    assert 'Target="[INSTALLFOLDER]desktop\\Raiker\\Raiker.exe"' in _WXS
    assert '<ComponentGroupRef Id="Payload" />' in _WXS


def test_voice_freeze_refuses_unavailable_pinned_runtime(tmp_path: Path, monkeypatch) -> None:
    import pytest

    from raiker.app import desktop_build

    (tmp_path / "raiker/app").mkdir(parents=True)
    (tmp_path / "raiker/app/launcher.py").write_text("")
    (tmp_path / "web").mkdir()
    (tmp_path / "web/index.html").write_text("")
    (tmp_path / "requirements").mkdir()
    (tmp_path / "requirements/voice.txt").write_text("test-runtime==1.0 \\\n    --hash=sha256:abc\n")

    def missing(_name):
        raise desktop_build.metadata.PackageNotFoundError

    monkeypatch.setattr(desktop_build.metadata, "version", missing)
    with pytest.raises(SystemExit, match="voice runtime missing"):
        desktop_build.freeze_host(source_root=tmp_path, web_assets=tmp_path / "web",
                                  out_dir=tmp_path / "out", bundle_voice=True)
    monkeypatch.setattr(desktop_build.metadata, "version", lambda _name: "2.0")
    with pytest.raises(SystemExit, match="voice runtime mismatch"):
        desktop_build.freeze_host(source_root=tmp_path, web_assets=tmp_path / "web",
                                  out_dir=tmp_path / "out", bundle_voice=True)
    assert not (tmp_path / "out").exists()


def test_ordinary_build_excludes_ambient_optional_voice_runtime() -> None:
    source = Path(__file__).resolve().parents[1]
    ordinary = pyinstaller_command(source_root=source, web_assets=source / "web/dist", out_dir=source / "desktop-dist")
    private = pyinstaller_command(source_root=source, web_assets=source / "web/dist", out_dir=source / "desktop-dist",
                                 bundle_voice=True)
    for module in ("kokoro_onnx", "onnxruntime", "phonemizer", "espeakng_loader"):
        assert any(ordinary[i:i + 2] == ["--exclude-module", module] for i in range(len(ordinary) - 1))
        assert any(private[i:i + 2] == ["--collect-all", module] for i in range(len(private) - 1))
