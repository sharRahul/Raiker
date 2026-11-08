"""CI-5 — RELEASE_EVIDENCE.md is written from the run's outputs, and refuses gaps."""

from __future__ import annotations

from pathlib import Path

from scripts.release_evidence import main, render


def _release(directory: Path, *, complete: bool) -> None:
    (directory / "Raiker-1.2.3-windows-x86_64-setup.exe").write_bytes(b"setup")
    (directory / "Raiker-1.2.3-windows-x86_64-setup.exe.manifest.json.sig").write_bytes(b"sig")
    (directory / "Raiker-1.2.3-linux-x86_64.AppImage").write_bytes(b"appimage")
    names = ["desktop-beta.json", "desktop-beta.json.sig", "raiker-1.2.3.spdx.json", "release-public-key.txt",
             "release-provenance.json"]
    for name in names if complete else names[:-1]:
        (directory / name).write_text("x", encoding="utf-8")


def test_the_record_names_the_run_signing_and_every_installer_digest(tmp_path: Path) -> None:
    _release(tmp_path, complete=True)
    text = render(tmp_path, version="1.2.3", channel="beta", signing="require-except-macos",
                  environ={"GITHUB_REPOSITORY": "o/r", "GITHUB_RUN_ID": "42", "GITHUB_SHA": "abc"})
    assert "https://github.com/o/r/actions/runs/42" in text and "`abc`" in text
    assert "self-signed beta certificate" in text and "macOS is built unsigned" in text
    assert "| `Raiker-1.2.3-windows-x86_64-setup.exe` |" in text and "| yes |" in text
    assert "| `Raiker-1.2.3-linux-x86_64.AppImage` |" in text and "| no |" in text
    assert "**missing**" not in text


def test_a_missing_output_fails_the_release(tmp_path: Path) -> None:
    _release(tmp_path, complete=False)
    code = main(["--dir", str(tmp_path), "--version", "1.2.3", "--channel", "beta",
                 "--signing", "require", "--out", str(tmp_path / "RELEASE_EVIDENCE.md")])
    assert code == 1
    assert "Signed provenance: **missing**" in (tmp_path / "RELEASE_EVIDENCE.md").read_text(encoding="utf-8")
