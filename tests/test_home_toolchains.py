"""rustup and nvm installs in the owner's home, mounted on governed terms.

Only their own program folders are mounted, read-only: never `~/.cargo`
(credentials and registry cache), never `~/.npmrc` or the rest of the home.
"""

from __future__ import annotations

from pathlib import Path

from raiker.execution.commands.home_toolchains import governed, with_path_entry


def _rustup_home(home: Path) -> Path:
    (home / ".cargo" / "bin").mkdir(parents=True)
    (home / ".cargo" / "credentials.toml").write_text("token = 'x'\n", encoding="utf-8")
    (home / ".rustup" / "toolchains" / "stable-x86_64-unknown-linux-gnu").mkdir(parents=True)
    cargo = home / ".cargo" / "bin" / "cargo"
    cargo.write_text("proxy", encoding="utf-8")
    return cargo


def test_a_rustup_proxy_mounts_its_bin_and_toolchains_but_never_cargo_home(tmp_path: Path) -> None:
    home = tmp_path / "home"
    cargo = _rustup_home(home)
    install = governed(cargo, home)
    assert install is not None
    assert install.mounts == (str(home / ".cargo" / "bin"), str(home / ".rustup"))
    assert str(home / ".cargo") not in install.mounts
    assert install.environment["RUSTUP_HOME"] == str(home / ".rustup")
    assert install.environment["RUSTUP_AUTO_INSTALL"] == "0"


def test_a_cargo_bin_program_that_is_not_a_proxy_is_not_mounted(tmp_path: Path) -> None:
    home = tmp_path / "home"
    _rustup_home(home)
    other = home / ".cargo" / "bin" / "cargo-something"
    other.write_text("installed with cargo install", encoding="utf-8")
    assert governed(other, home) is None


def test_without_rustup_toolchains_nothing_is_mounted(tmp_path: Path) -> None:
    home = tmp_path / "home"
    cargo = _rustup_home(home)
    (home / ".rustup" / "toolchains" / "stable-x86_64-unknown-linux-gnu").rmdir()
    (home / ".rustup" / "toolchains").rmdir()
    assert governed(cargo, home) is None


def test_an_nvm_node_mounts_only_its_version(tmp_path: Path) -> None:
    home = tmp_path / "home"
    prefix = home / ".nvm" / "versions" / "node" / "v22.11.0"
    (prefix / "bin").mkdir(parents=True)
    node = prefix / "bin" / "node"
    node.write_text("node", encoding="utf-8")
    (home / ".npmrc").write_text("//registry/:_authToken=x\n", encoding="utf-8")
    install = governed(node, home)
    assert install is not None
    assert install.mounts == (str(prefix),)
    assert install.path_entry == str(prefix / "bin")


def test_anything_else_in_a_home_stays_out_of_reach(tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / "bin").mkdir(parents=True)
    tool = home / "bin" / "node"
    tool.write_text("node", encoding="utf-8")
    assert governed(tool, home) is None
    odd = home / ".nvm" / "versions" / "node" / "latest" / "bin"
    odd.mkdir(parents=True)
    (odd / "node").write_text("node", encoding="utf-8")
    assert governed(odd / "node", home) is None


def test_the_install_comes_first_on_the_path() -> None:
    environment = {"PATH": "/usr/bin"}
    with_path_entry(environment, "/home/u/.cargo/bin")
    assert environment["PATH"].split(":" if ":" in environment["PATH"] else ";")[0] == "/home/u/.cargo/bin"
