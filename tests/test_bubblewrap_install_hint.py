"""RU-04 — Linux names the one package that installs its command sandbox."""

from __future__ import annotations

import pytest

from raiker.api.routes_commands import bubblewrap_install_command


@pytest.mark.parametrize(
    ("release", "expected"),
    [
        ('ID=ubuntu\nID_LIKE=debian\n', "sudo apt install bubblewrap"),
        ('ID="fedora"\n', "sudo dnf install bubblewrap"),
        ("ID=linuxmint\nID_LIKE=\"ubuntu debian\"\n", "sudo apt install bubblewrap"),
        ("ID=rocky\nID_LIKE=\"rhel centos fedora\"\n", "sudo dnf install bubblewrap"),
        ("ID=arch\n", "sudo pacman -S bubblewrap"),
        ("ID=opensuse-tumbleweed\nID_LIKE=\"opensuse suse\"\n", "sudo zypper install bubblewrap"),
        ("ID=alpine\n", "sudo apk add bubblewrap"),
    ],
)
def test_the_install_line_follows_the_distribution(release: str, expected: str) -> None:
    assert bubblewrap_install_command(release) == expected


def test_an_unknown_distribution_names_no_command() -> None:
    assert bubblewrap_install_command("ID=plan9\n") is None
    assert bubblewrap_install_command("") is None
