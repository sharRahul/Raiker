# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path

import pytest

from scripts import build_installer


@pytest.mark.parametrize(
    ("arch", "debian_arch", "appimage_arch"),
    [("x86_64", "amd64", "x86_64"), ("arm64", "arm64", "aarch64")],
)
def test_linux_installers_use_native_architecture_names(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    arch: str,
    debian_arch: str,
    appimage_arch: str,
) -> None:
    payload = tmp_path / "payload"
    payload.mkdir()
    (payload / "version.txt").write_text("1.2.3", encoding="utf-8")
    record: dict[str, object] = {"version": "1.2.3", "arch": arch}
    commands: list[list[str]] = []

    monkeypatch.setattr(build_installer.shutil, "which", lambda _name: "tool")
    monkeypatch.setattr(build_installer, "_run", lambda command: commands.append(command))

    deb = build_installer.build_deb(payload, record, tmp_path / "deb-out")
    image = build_installer.build_appimage(payload, record, tmp_path / "image-out")

    control = tmp_path / "deb-out" / "deb" / "DEBIAN" / "control"
    assert f"Architecture: {debian_arch}" in control.read_text(encoding="utf-8")
    assert deb.name == f"raiker_1.2.3_{debian_arch}.deb"
    assert image is not None
    assert image.name == f"Raiker-1.2.3-{appimage_arch}.AppImage"
    assert any("--appimage-extract-and-run" in command for command in commands)
