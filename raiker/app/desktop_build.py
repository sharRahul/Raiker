from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def pyinstaller_command(
    *, source_root: Path, web_assets: Path, out_dir: Path, platform_name: str = sys.platform
) -> list[str]:
    separator = ";" if platform_name == "win32" else ":"
    entry = source_root / "apps" / "api" / "launcher.py"
    return [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--name",
        "Raiker",
        "--paths",
        str(source_root),
        "--distpath",
        str(out_dir),
        "--workpath",
        str(out_dir / ".work"),
        "--specpath",
        str(out_dir / ".spec"),
        "--collect-all",
        "pystray",
        "--collect-all",
        "PIL",
        "--add-data",
        f"{web_assets}{separator}web",
        str(entry),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Raiker as a self-contained desktop app.")
    parser.add_argument("--source-root", default=".")
    parser.add_argument("--web-assets", default="apps/web/dist")
    parser.add_argument("--out", default="desktop-dist")
    args = parser.parse_args(argv)
    source_root = Path(args.source_root).resolve()
    web_assets = Path(args.web_assets).resolve()
    out_dir = Path(args.out).resolve()
    if not (source_root / "apps" / "api" / "launcher.py").is_file():
        parser.error("source root does not contain apps/api/launcher.py")
    if not (web_assets / "index.html").is_file():
        parser.error("web assets do not contain index.html")
    out_dir.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(  # noqa: S603 - argv is fixed and paths are explicit
        pyinstaller_command(source_root=source_root, web_assets=web_assets, out_dir=out_dir),
        check=False,
    )
    return completed.returncode

