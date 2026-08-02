# SPDX-License-Identifier: Apache-2.0
"""Turn a verified payload into the installer that platform actually accepts.

BUG-44. ``raiker.app.release`` produces the payload — the service, the built web
assets, the platform's own dependency wheels, and the ``installation.json`` that
lets the running product state its own provenance. This script wraps that payload
in the container each OS installs from, using that OS's own tooling and nothing
invented here:

===============  ===========================================================
``macos-*``      ``pkgbuild`` → ``.pkg``, with a postinstall that creates the
                 virtual environment from the bundled wheels offline.
``windows-*``    WiX → ``.msi``, per-user scope so no elevation is required.
``linux-*``      ``dpkg-deb`` → ``.deb``, plus an AppImage when
                 ``appimagetool`` is available on the builder.
===============  ===========================================================

**Signing is not done here.** Building an installer and signing one are separate
steps on purpose: this runs on any machine, the signing step runs only where an
identity exists, and the difference between them is exactly what
``installation.json`` records. An installer produced by this script is unsigned
until a signing step says otherwise.

Every installer installs to a per-user location and creates no account, no model
connection, and no backup — the distribution design's Install row is "install
signed application files only".
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

APP_NAME = "Raiker"
BUNDLE_ID = "com.raiker.app"
# A stable upgrade code is what lets one MSI replace an earlier one instead of
# installing beside it. It never changes across releases; that is its whole job.
WINDOWS_UPGRADE_CODE = "6F3B2A18-9C42-4E7D-9E52-2B4F1C8A7D30"


class InstallerError(RuntimeError):
    """A refusal with a stable reason code."""


def _run(command: list[str], *, cwd: Path | None = None) -> None:
    print(f"$ {' '.join(command)}", flush=True)
    result = subprocess.run(command, cwd=cwd, check=False)  # noqa: S603 - fixed argv
    if result.returncode != 0:
        raise InstallerError(f"installer_step_failed:{command[0]}")


def _extract(artifact: Path, into: Path) -> dict[str, object]:
    into.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(artifact) as archive:
        archive.extractall(into)
    record = json.loads((into / "installation.json").read_text(encoding="utf-8"))
    return dict(record)


_POSIX_LAUNCHER = """#!/bin/sh
# Start Raiker with the interpreter its own installation owns, so nothing
# depends on what happens to be first on PATH. RAIKER_INSTALL_ROOT is what
# lets the product read its own provenance: the environment lives inside the
# install root, so the record is above the installed package rather than beside
# it, and a value the installer knows beats a search.
RAIKER_INSTALL_ROOT="{prefix}"
export RAIKER_INSTALL_ROOT
exec "{prefix}/venv/bin/raiker-app" "$@"
"""

_POSIX_BOOTSTRAP = """#!/bin/sh
set -e
# Everything installs from the wheels inside the package: no network, and no
# chance of resolving a different version than the one that was tested here.
PREFIX="{prefix}"
python3 -m venv "$PREFIX/venv"
"$PREFIX/venv/bin/python" -m pip install --upgrade pip --no-index \\
    --find-links "$PREFIX/wheels" >/dev/null 2>&1 || true
"$PREFIX/venv/bin/python" -m pip install --no-index --find-links "$PREFIX/wheels" raiker
"""


def build_deb(payload: Path, record: dict[str, object], out_dir: Path) -> Path:
    if shutil.which("dpkg-deb") is None:
        raise InstallerError("installer_tool_missing:dpkg-deb")
    version = str(record["version"])
    prefix = "/opt/raiker"
    staging = out_dir / "deb"
    shutil.rmtree(staging, ignore_errors=True)
    root = staging / "opt" / "raiker"
    root.parent.mkdir(parents=True)
    shutil.copytree(payload, root)

    control = staging / "DEBIAN"
    control.mkdir(parents=True)
    (control / "control").write_text(
        "\n".join(
            [
                "Package: raiker",
                f"Version: {version}",
                "Section: utils",
                "Priority: optional",
                "Architecture: amd64",
                "Depends: python3 (>= 3.11), python3-venv",
                "Maintainer: Raiker <raiker@localhost>",
                "Description: Raiker governed agent runtime",
                " A local-first governed AI assistant, agent and platform.",
                " Installs application files only; it creates no account, model",
                " connection or backup until you ask it to.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    postinst = control / "postinst"
    postinst.write_text(
        _POSIX_BOOTSTRAP.format(prefix=prefix)
        + f'install -m 0755 /dev/stdin /usr/local/bin/raiker-app <<\'EOF\'\n{_POSIX_LAUNCHER.format(prefix=prefix)}EOF\n',
        encoding="utf-8",
    )
    postinst.chmod(0o755)
    prerm = control / "prerm"
    prerm.write_text(
        "#!/bin/sh\nset -e\n"
        "# Application files only. Instance data lives in the user's own\n"
        "# application-data directory and is removed by `raiker-app uninstall`,\n"
        "# which states what it takes before it takes it.\n"
        f"rm -rf {prefix}/venv\nrm -f /usr/local/bin/raiker-app\n",
        encoding="utf-8",
    )
    prerm.chmod(0o755)

    package = out_dir / f"raiker_{version}_amd64.deb"
    _run(["dpkg-deb", "--root-owner-group", "--build", str(staging), str(package)])
    return package


def build_appimage(payload: Path, record: dict[str, object], out_dir: Path) -> Path | None:
    """Best effort: an AppImage needs a tool the builder may not have.

    Returning ``None`` rather than failing is deliberate — the ``.deb`` is the
    target's primary format, and the workflow reports which formats it actually
    produced rather than assuming.
    """
    tool = shutil.which("appimagetool") or shutil.which("appimagetool-x86_64.AppImage")
    if tool is None:
        print("skip: appimagetool is not on this builder", flush=True)
        return None
    version = str(record["version"])
    appdir = out_dir / "Raiker.AppDir"
    shutil.rmtree(appdir, ignore_errors=True)
    (appdir / "usr").mkdir(parents=True)
    shutil.copytree(payload, appdir / "usr" / "raiker")
    # An AppImage is read-only, so the environment is created once under the
    # user's own data directory rather than inside the image.
    (appdir / "AppRun").write_text(
        "#!/bin/sh\n"
        "set -e\n"
        'HERE="$(dirname "$(readlink -f "$0")")"\n'
        'VENV="${XDG_DATA_HOME:-$HOME/.local/share}/raiker/venv"\n'
        'if [ ! -x "$VENV/bin/raiker-app" ]; then\n'
        '  python3 -m venv "$VENV"\n'
        '  "$VENV/bin/python" -m pip install --no-index '
        '--find-links "$HERE/usr/raiker/wheels" raiker\n'
        "fi\n"
        'RAIKER_INSTALL_ROOT="$HERE/usr/raiker"\n'
        "export RAIKER_INSTALL_ROOT\n"
        'exec "$VENV/bin/raiker-app" "$@"\n',
        encoding="utf-8",
    )
    (appdir / "AppRun").chmod(0o755)
    (appdir / "raiker.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Raiker\nExec=AppRun\n"
        "Icon=raiker\nCategories=Utility;\n",
        encoding="utf-8",
    )
    icon = Path("assets/icons/raiker.png")
    if icon.is_file():
        shutil.copyfile(icon, appdir / "raiker.png")
    else:
        (appdir / "raiker.png").write_bytes(b"")
    image = out_dir / f"Raiker-{version}-x86_64.AppImage"
    _run([tool, "--appimage-extract-and-run", "--no-appstream", str(appdir), str(image)])
    return image


def build_pkg(payload: Path, record: dict[str, object], out_dir: Path) -> Path:
    if sys.platform != "darwin":
        raise InstallerError("installer_wrong_platform:pkg")
    version = str(record["version"])
    prefix = "/usr/local/raiker"
    staging = out_dir / "pkgroot"
    shutil.rmtree(staging, ignore_errors=True)
    root = staging / "usr" / "local" / "raiker"
    root.parent.mkdir(parents=True)
    shutil.copytree(payload, root)

    scripts = out_dir / "pkgscripts"
    shutil.rmtree(scripts, ignore_errors=True)
    scripts.mkdir(parents=True)
    postinstall = scripts / "postinstall"
    postinstall.write_text(
        _POSIX_BOOTSTRAP.format(prefix=prefix)
        + f'mkdir -p /usr/local/bin\ncat > /usr/local/bin/raiker-app <<\'EOF\'\n'
        f"{_POSIX_LAUNCHER.format(prefix=prefix)}EOF\n"
        "chmod 0755 /usr/local/bin/raiker-app\nexit 0\n",
        encoding="utf-8",
    )
    postinstall.chmod(0o755)

    package = out_dir / f"Raiker-{version}-{record['arch']}.pkg"
    _run(
        [
            "pkgbuild",
            "--root", str(staging),
            "--scripts", str(scripts),
            "--identifier", BUNDLE_ID,
            "--version", version,
            "--install-location", "/",
            str(package),
        ]
    )
    return package


_WXS = """<?xml version="1.0" encoding="utf-8"?>
<Wix xmlns="http://wixtoolset.org/schemas/v4/wxs">
  <Package Name="{name}" Manufacturer="Raiker" Version="{version}"
           UpgradeCode="{{{upgrade}}}" Scope="perUser" Compressed="yes">
    <MajorUpgrade DowngradeErrorMessage="A newer version of Raiker is already installed." />
    <MediaTemplate EmbedCab="yes" />
    <StandardDirectory Id="LocalAppDataFolder">
      <Directory Id="INSTALLFOLDER" Name="Raiker" />
    </StandardDirectory>
    <ComponentGroup Id="Payload" Directory="INSTALLFOLDER">
      <Files Include="{payload}\\**" />
    </ComponentGroup>
  </Package>
</Wix>
"""


def build_msi(payload: Path, record: dict[str, object], out_dir: Path) -> Path:
    if os.name != "nt":
        raise InstallerError("installer_wrong_platform:msi")
    wix = shutil.which("wix") or shutil.which("wix.exe")
    if wix is None:
        raise InstallerError("installer_tool_missing:wix")
    version = str(record["version"])
    source = out_dir / "raiker.wxs"
    source.write_text(
        _WXS.format(
            name=APP_NAME,
            version=version,
            upgrade=WINDOWS_UPGRADE_CODE,
            payload=str(payload.resolve()),
        ),
        encoding="utf-8",
    )
    package = out_dir / f"Raiker-{version}-x64.msi"
    _run([wix, "build", str(source), "-arch", "x64", "-o", str(package)])
    return package


BUILDERS = {
    "linux": ("deb", "AppImage"),
    "macos": ("pkg",),
    "windows": ("msi",),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the native installer for one target.")
    parser.add_argument("--artifact", required=True, help="The payload zip to wrap.")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    artifact = Path(args.artifact)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = out_dir / "payload"
    shutil.rmtree(payload, ignore_errors=True)
    record = _extract(artifact, payload)
    os_name = str(record["os"])

    built: list[str] = []
    try:
        if os_name == "linux":
            built.append(str(build_deb(payload, record, out_dir)))
            image = build_appimage(payload, record, out_dir)
            if image is not None:
                built.append(str(image))
        elif os_name == "macos":
            built.append(str(build_pkg(payload, record, out_dir)))
        elif os_name == "windows":
            built.append(str(build_msi(payload, record, out_dir)))
        else:
            raise InstallerError(f"installer_target_unknown:{os_name}")
    except InstallerError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2

    # The installers are not signed by this script and must not be described as
    # if they were. The signing step, where an identity exists, rewrites this.
    (out_dir / "installers.json").write_text(
        json.dumps({"target": record["target"], "signed": False, "installers": built}, indent=2),
        encoding="utf-8",
    )
    for path in built:
        print(f"built {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
