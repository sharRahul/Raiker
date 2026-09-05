"""The applications-menu entry, and what an uninstall from a checkout leaves.

Raiker registered a *background service* and called that desktop integration.
It is not the same thing: after a source install there was no icon in the
applications menu, none in the Start Menu, none in Spotlight, and the only way
into a product whose entire surface is a browser page was a terminal.

Every per-platform entry is asserted on every platform, for the reason
`test_app_lifecycle.py` gives about the service definitions: the `.desktop` file
generated on a Linux CI runner is the exact artefact that would be written on a
user's machine, and a test that only ran on the matching platform would never
notice it break.
"""

from __future__ import annotations

import plistlib
from pathlib import Path

import pytest

from raiker.app import desktop_entry
from raiker.app.desktop_entry import (
    LINUX_ENTRY,
    MACOS_BUNDLE,
    WINDOWS_ENTRY,
    WINDOWS_SHORTCUT,
    entry_plan,
    install,
    status,
    uninstall,
)
from raiker.app.uninstall import apply_uninstall, build_artefacts, plan_uninstall

ICON = Path("/opt/raiker/raiker-icon.png")


# ── the entry, per platform ──────────────────────────────────────────────


def test_linux_writes_a_desktop_entry_the_menu_will_accept(tmp_path: Path) -> None:
    plan = entry_plan(os_name="linux", home=tmp_path, icon=ICON)
    body = next(iter(plan.files.values()))

    assert plan.label == LINUX_ENTRY
    assert plan.path is not None
    assert plan.path.parent == tmp_path / ".local" / "share" / "applications"
    assert body.startswith("[Desktop Entry]\n")
    assert "Type=Application" in body
    assert f"Icon={ICON}" in body
    # A launcher that opens a terminal window is not a launcher.
    assert "Terminal=false" in body
    # Some desktops refuse a non-executable entry and others show it inertly,
    # which is the worse of the two failures.
    assert plan.path in plan.executable


def test_the_linux_exec_line_survives_a_path_with_a_space(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`Exec` is a command line, not an argv list, and paths have spaces in them."""
    spacey = "/opt/my apps/raiker-app"
    monkeypatch.setattr(desktop_entry.shutil, "which", lambda _: spacey)
    plan = entry_plan(os_name="linux", home=tmp_path, icon=None)
    exec_line = next(
        line for line in next(iter(plan.files.values())).splitlines() if line.startswith("Exec=")
    )
    assert exec_line == f"Exec='{spacey}'"


def test_a_percent_in_a_path_is_escaped_for_freedesktop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`%` opens a field code in a `.desktop` Exec line; a literal one is `%%`."""
    monkeypatch.setattr(desktop_entry.shutil, "which", lambda _: "/opt/100%/raiker-app")
    plan = entry_plan(os_name="linux", home=tmp_path, icon=None)
    body = next(iter(plan.files.values()))
    assert "/opt/100%%/raiker-app" in body


def test_macos_writes_a_bundle_whose_plist_actually_parses(tmp_path: Path) -> None:
    plan = entry_plan(os_name="macos", home=tmp_path, icon=ICON)
    plist = next(path for path in plan.files if path.name == "Info.plist")
    parsed = plistlib.loads(plan.files[plist].encode("utf-8"))

    assert plan.path == tmp_path / "Applications" / MACOS_BUNDLE
    assert parsed["CFBundleExecutable"] == "Raiker"
    assert parsed["CFBundleIdentifier"] == "com.raiker.launcher"
    # The launcher is not the application: what the owner wants on screen is the
    # browser page, and the host already has a tray icon.
    assert parsed["LSUIElement"] is True
    runner = next(path for path in plan.files if path.name == "Raiker" and path.parent.name == "MacOS")
    assert runner in plan.executable


def test_windows_writes_a_start_menu_entry_and_asks_for_a_real_shortcut(tmp_path: Path) -> None:
    plan = entry_plan(os_name="windows", home=tmp_path, icon=ICON)
    script = next(iter(plan.files))

    assert script.name == WINDOWS_ENTRY
    assert script.parent.name == "Programs"
    assert plan.files[script].startswith("@echo off\r\n")
    # The .cmd works with no help; the .lnk is what makes it look like an
    # application, and PowerShell is how you write one without a COM dependency.
    activation = plan.described_activation()
    assert "powershell" in activation
    assert WINDOWS_SHORTCUT in activation
    assert str(ICON) in activation


def test_an_unknown_platform_says_so_rather_than_writing_something_hopeful(
    tmp_path: Path,
) -> None:
    plan = entry_plan(os_name="posix", home=tmp_path)
    assert not plan.supported
    assert plan.files == {}
    assert "raiker-app" in plan.note


# ── install, status, uninstall ───────────────────────────────────────────


@pytest.mark.parametrize("os_name", ["linux", "macos", "windows"])
def test_install_then_uninstall_leaves_nothing_behind(tmp_path: Path, os_name: str) -> None:
    plan = entry_plan(os_name=os_name, home=tmp_path, icon=None)

    assert not status(os_name=os_name, home=tmp_path).installed
    result = install(plan, activate=False)
    assert result.ok
    assert status(os_name=os_name, home=tmp_path).installed

    uninstall(plan)
    assert not status(os_name=os_name, home=tmp_path).installed
    assert plan.path is not None and not plan.path.exists()


def test_uninstall_removes_the_windows_shortcut_the_activation_created(
    tmp_path: Path,
) -> None:
    """The `.lnk` is written by PowerShell, so no `files` entry names it.

    Without being named explicitly it would survive an uninstall — a Start Menu
    icon pointing at a launcher that is gone, which is worse than no icon.
    """
    plan = entry_plan(os_name="windows", home=tmp_path, icon=None)
    install(plan, activate=False)
    shortcut = next(iter(plan.files)).with_name(WINDOWS_SHORTCUT)
    shortcut.write_text("pretend this is a shortcut", encoding="utf-8")

    uninstall(plan)
    assert not shortcut.exists()


def test_uninstalling_a_launcher_that_is_not_there_is_not_an_error(tmp_path: Path) -> None:
    result = uninstall(entry_plan(os_name="linux", home=tmp_path, icon=None))
    assert result.ok
    assert "no launcher to remove" in result.message


# ── the launcher is part of an uninstall ─────────────────────────────────


def test_uninstall_removes_the_launcher_alongside_the_registration(tmp_path: Path) -> None:
    home = tmp_path / "home"
    workspace = tmp_path / "ws"
    workspace.mkdir()
    entry = entry_plan(os_name="linux", home=home, icon=None)
    install(entry, activate=False)

    plan = plan_uninstall(workspace, os_name="linux", home=home, detect_source=False)
    assert plan.launcher_installed
    assert "Removed: the freedesktop application entry" in "\n".join(plan.describe())

    apply_uninstall(plan, workspace, os_name="linux", home=home)
    assert entry.path is not None and not entry.path.exists()


# ── a source checkout ────────────────────────────────────────────────────


def _checkout(root: Path) -> Path:
    """A directory shaped like an editable install of Raiker."""
    (root / ".git").mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname='raiker'\n", encoding="utf-8")
    for relative in ("apps/web/dist", "apps/web/node_modules", "build", "raiker.egg-info"):
        directory = root / relative
        directory.mkdir(parents=True)
        (directory / "payload").write_bytes(b"x" * 4096)
    (root / ".venv").mkdir()
    return root


def test_a_checkout_install_names_what_pip_uninstall_would_leave(tmp_path: Path) -> None:
    """`pip uninstall raiker` removes a link and leaves gigabytes of directory."""
    checkout = _checkout(tmp_path / "src")
    plan = plan_uninstall(
        tmp_path / "ws", os_name="linux", home=tmp_path / "home", checkout=checkout
    )
    lines = "\n".join(plan.describe())

    assert {artefact.label for artefact in plan.build_artefacts} == {
        "the built dashboard",
        "the dashboard's downloaded packages",
        "the Python build tree",
        "the editable-install metadata",
    }
    # The advice that was already there stays: an editable install registers the
    # package too, so removing it is still the right thing to say.
    assert "pip uninstall raiker" in lines
    assert str(checkout) in lines
    assert str(checkout / ".venv") in lines


def test_the_checkout_is_never_removed_and_neither_are_its_artefacts_by_default(
    tmp_path: Path,
) -> None:
    """Safe is the operative word.

    The build directories live in the owner's own repository. Deleting out of a
    git checkout because Raiker happens to be running from it exceeds anything
    "uninstall Raiker" can be read to mean, so the plan reports them and stops.
    """
    checkout = _checkout(tmp_path / "src")
    plan = plan_uninstall(
        tmp_path / "ws", os_name="linux", home=tmp_path / "home", checkout=checkout
    )
    assert not plan.remove_build_artefacts
    assert "Kept: the dashboard's downloaded packages" in "\n".join(plan.describe())

    apply_uninstall(plan, tmp_path / "ws", os_name="linux", home=tmp_path / "home")
    assert (checkout / "apps" / "web" / "node_modules").is_dir()
    assert (checkout / ".git").is_dir()
    assert (checkout / ".venv").is_dir()


def test_asking_for_the_artefacts_removes_them_and_still_keeps_the_checkout(
    tmp_path: Path,
) -> None:
    checkout = _checkout(tmp_path / "src")
    plan = plan_uninstall(
        tmp_path / "ws",
        os_name="linux",
        home=tmp_path / "home",
        checkout=checkout,
        remove_build_artefacts=True,
    )
    assert "Removed: the dashboard's downloaded packages" in "\n".join(plan.describe())

    apply_uninstall(plan, tmp_path / "ws", os_name="linux", home=tmp_path / "home")
    assert not (checkout / "apps" / "web" / "node_modules").exists()
    assert not (checkout / "build").exists()
    # Still the owner's directory, and still their virtual environment.
    assert (checkout / ".git").is_dir()
    assert (checkout / ".venv").is_dir()
    assert (checkout / "pyproject.toml").is_file()


def test_a_wheel_install_reports_no_checkout_and_no_artefacts(tmp_path: Path) -> None:
    assert build_artefacts(None) == []
    plan = plan_uninstall(
        tmp_path / "ws", os_name="linux", home=tmp_path / "home", detect_source=False
    )
    assert plan.source_checkout is None
    assert plan.build_artefacts == []
