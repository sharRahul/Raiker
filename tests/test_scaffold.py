from __future__ import annotations

import raiker
from raiker.cli.main import main


def test_package_imports() -> None:
    assert raiker.__version__ == "0.0.0"


def test_cli_status_starts_and_exits(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["--prompt", "/help"]) == 0
    out = capsys.readouterr().out
    assert "Raiker terminal client" in out
    assert "/channels" in out
