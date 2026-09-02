"""The updater handoff never changes the live tree before its host exits."""

from __future__ import annotations

from pathlib import Path


def test_handoff_waits_then_applies_and_restarts(monkeypatch, tmp_path: Path) -> None:
    from raiker.app.installation import ChannelConfig, Installation
    from raiker.app.update import ChannelUpdate, UpdateResult
    from raiker.app.update_handoff import apply_after_host_exit

    calls: list[object] = []
    installation = Installation(
        version="1.0.0", target="windows-x86_64", packaged=True, signed=True,
        channel="stable", commit=None, built_at=None, installer_formats=(),
        install_root=tmp_path / "install", note="",
    )
    status = type("Status", (), {
        "state": "available",
        "available": ChannelUpdate(
            channel="stable", version="2.0.0", target="windows-x86_64",
            artifact="release.zip", sha256="a" * 64, manifest="release.json",
            signature="release.sig", signed=True, released_at="now",
        ),
    })()
    monkeypatch.setattr("raiker.app.update_handoff.wait_for_exit", lambda pid: calls.append(("wait", pid)))
    monkeypatch.setattr("raiker.app.update_handoff.detect_installation", lambda: installation)
    monkeypatch.setattr("raiker.app.update_handoff.check_for_update", lambda *_args, **_kwargs: status)
    monkeypatch.setattr(
        "raiker.app.update_handoff.read_channel_config",
        lambda _workspace: ChannelConfig("https://releases.example/stable.json", b"x" * 32, "stable"),
    )
    monkeypatch.setattr(
        "raiker.app.update_handoff.download_and_apply",
        lambda *_args, **_kwargs: calls.append("apply") or UpdateResult("2.0.0", tmp_path, tmp_path, "a" * 64),
    )
    monkeypatch.setattr("raiker.app.update_handoff.subprocess.Popen", lambda command, **_kwargs: calls.append(tuple(command)))

    assert apply_after_host_exit(tmp_path, parent_pid=42, restart_command=["raiker-app"]) == 0
    assert calls == [("wait", 42), "apply", ("raiker-app", "--workspace", str(tmp_path))]


def test_handoff_does_not_restart_when_recheck_is_not_available(monkeypatch, tmp_path: Path) -> None:
    from raiker.app.installation import Installation
    from raiker.app.update_handoff import apply_after_host_exit

    installation = Installation(
        version="1.0.0", target="windows-x86_64", packaged=True, signed=True,
        channel="stable", commit=None, built_at=None, installer_formats=(),
        install_root=tmp_path / "install", note="",
    )
    monkeypatch.setattr("raiker.app.update_handoff.wait_for_exit", lambda _pid: None)
    monkeypatch.setattr("raiker.app.update_handoff.detect_installation", lambda: installation)
    monkeypatch.setattr(
        "raiker.app.update_handoff.check_for_update",
        lambda *_args, **_kwargs: type("Status", (), {"state": "up_to_date", "available": None})(),
    )

    assert apply_after_host_exit(tmp_path, parent_pid=42, restart_command=["raiker-app"]) == 2
