"""Build the desktop application an owner installs (DESK-12, DIST-01).

Two layers, run in order by :func:`build_app` (``scripts/build_desktop_app.py``):

1. **The frozen host** — PyInstaller turns the service, its package data, the
   governed-command runner and the built web app into one directory with its
   own interpreter (``desktop-dist/Raiker/``). Nothing on the owner's machine
   needs Python.
2. **The desktop package** — the pinned electron-builder wraps the Electron
   window around that directory (``desktop/electron-builder.yml``) and produces
   this platform's installers.

Between them the build writes the provenance record the running product reads
(:func:`raiker.app.desktop_release.desktop_record`) and runs the frozen host
through :mod:`raiker.app.desktop_smoke`, so a host that cannot start is never
packaged. After them it writes a schema-1 manifest per installer and
``SHA256SUMS``.

``python scripts/build_desktop.py`` still builds only the frozen host.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

#: electron-builder is fetched by exact version, never a range: the package an
#: owner installs must not change because a builder release did.
ELECTRON_BUILDER = "electron-builder@26.17.0"


def pyinstaller_command(
    *, source_root: Path, web_assets: Path, out_dir: Path, platform_name: str = sys.platform
) -> list[str]:
    separator = ";" if platform_name == "win32" else ":"
    entry = source_root / "raiker" / "app" / "launcher.py"
    return [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        *(["--windowed"] if platform_name == "win32" else []),
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
        # Raiker's own package data — model profiles, the icon, the built-in
        # skills, the governed-command runner under `raiker/native/` — is read
        # from beside the modules at start. PyInstaller follows imports, not data
        # files, so without this the frozen host stopped on its first read of
        # `raiker/config/model-profiles.json` and never served.
        "--collect-data",
        "raiker",
        # Executors, providers and routes are resolved by name at run time.
        "--collect-submodules",
        "raiker",
        # DIST-08 — keyring finds its Keychain and Secret Service backends
        # through package entry points, which live in its distribution metadata.
        *(
            []
            if platform_name == "win32"
            else ["--collect-submodules", "keyring", "--copy-metadata", "keyring"]
        ),
        # Nothing in Raiker uses pkg_resources, and PyInstaller's runtime hook
        # for it fails against current setuptools on macOS before the host can
        # start (`pkg_resources has no attribute NullProvider`).
        "--exclude-module",
        "pkg_resources",
        "--add-data",
        f"{web_assets}{separator}web",
        # The in-app Guide reads `docs/guide` beside the package
        # (`raiker.guide.guide_root`); a frozen host carries it there too.
        "--add-data",
        f"{source_root / 'docs' / 'guide'}{separator}docs/guide",
        str(entry),
    ]


def freeze_host(*, source_root: Path, web_assets: Path, out_dir: Path) -> int:
    if not (source_root / "raiker" / "app" / "launcher.py").is_file():
        raise SystemExit("source root does not contain raiker/app/launcher.py")
    if not (web_assets / "index.html").is_file():
        raise SystemExit("web assets do not contain index.html")
    out_dir.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(  # noqa: S603 - argv is fixed and paths are explicit
        pyinstaller_command(source_root=source_root, web_assets=web_assets, out_dir=out_dir),
        check=False,
    )
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    """Freeze only the host (``scripts/build_desktop.py``)."""
    parser = argparse.ArgumentParser(description="Build Raiker's host as a self-contained directory.")
    parser.add_argument("--source-root", default=".")
    parser.add_argument("--web-assets", default="web/dist")
    parser.add_argument("--out", default="desktop-dist")
    args = parser.parse_args(argv)
    return freeze_host(
        source_root=Path(args.source_root).resolve(),
        web_assets=Path(args.web_assets).resolve(),
        out_dir=Path(args.out).resolve(),
    )


def host_executable(host_dir: Path, platform_name: str = sys.platform) -> Path:
    return host_dir / ("Raiker.exe" if platform_name == "win32" else "Raiker")


def builder_command(
    *, target_id: str, version: str, npx: str = "npx"
) -> list[str]:
    from raiker.app.desktop_release import desktop_target

    target = desktop_target(target_id)
    return [
        npx,
        "--yes",
        ELECTRON_BUILDER,
        "--config",
        "electron-builder.yml",
        *target.builder_args,
        "--publish",
        "never",
        f"-c.extraMetadata.version={version}",
    ]


def builder_environment(*, target_id: str, signed: bool, environ: dict[str, str]) -> dict[str, str]:
    """The environment electron-builder runs in.

    Names follow from the target alone. An unsigned build turns off identity
    discovery outright, so a developer machine with a certificate in its
    keychain cannot produce a build whose record says unsigned that is in fact
    signed — or the reverse.
    """
    from raiker.app.desktop_release import suffix

    env = dict(environ)
    env["RAIKER_TARGET"] = target_id
    env["RAIKER_ARTIFACT_SUFFIX"] = suffix(signed=signed)
    if not signed:
        env["CSC_IDENTITY_AUTO_DISCOVERY"] = "false"
        for name in ("CSC_LINK", "CSC_KEY_PASSWORD", "WIN_CSC_LINK", "WIN_CSC_KEY_PASSWORD",
                     "APPLE_API_KEY", "APPLE_API_KEY_ID", "APPLE_API_ISSUER"):
            env.pop(name, None)
    return env


def build_app(argv: list[str] | None = None) -> int:
    from raiker.app.desktop_release import (
        DESKTOP_TARGETS,
        artifact_names,
        current_desktop_target,
        desktop_record,
        write_checksums,
        write_manifests,
        write_record,
    )
    from raiker.app.release import _key_from_env, public_key_of

    here = current_desktop_target()
    parser = argparse.ArgumentParser(
        description="Build Raiker's desktop installers for this machine's platform."
    )
    parser.add_argument("--version", default="0.0.0")
    parser.add_argument("--target", default=None, help="Defaults to this machine's target.")
    parser.add_argument("--channel", default="stable")
    parser.add_argument("--commit", default=None)
    parser.add_argument("--signed", action="store_true",
                        help="Platform signing identities are configured. Set only by the release workflow.")
    parser.add_argument("--source-root", default=".")
    parser.add_argument("--web-assets", default="web/dist")
    parser.add_argument("--out", default="desktop-release", help="Where the installers are collected.")
    parser.add_argument(
        "--channel-url", default="",
        help="HTTPS URL of the signed desktop-<channel>.json this build checks by default.",
    )
    parser.add_argument("--skip-freeze", action="store_true", help="Reuse desktop-dist/Raiker.")
    parser.add_argument("--skip-smoke", action="store_true", help="Do not start the frozen host.")
    args = parser.parse_args(argv)

    target_id = args.target or (here.target_id if here else "")
    known = {target.target_id for target in DESKTOP_TARGETS}
    if target_id not in known:
        parser.error(f"unknown or unsupported target {target_id!r}; choose one of {sorted(known)}")
    source_root = Path(args.source_root).resolve()
    host_root = source_root / "desktop-dist"
    host_dir = host_root / "Raiker"

    if not args.skip_freeze:
        shutil.rmtree(host_dir, ignore_errors=True)
        code = freeze_host(
            source_root=source_root, web_assets=Path(args.web_assets).resolve(), out_dir=host_root
        )
        if code != 0:
            return code
    release_key = _key_from_env("RAIKER_RELEASE_SIGNING_KEY")
    update_channel = (
        {"url": args.channel_url, "public_key": public_key_of(release_key).hex(), "channel": args.channel}
        if args.channel_url and release_key is not None and args.signed
        else None
    )
    write_record(
        host_dir,
        desktop_record(
            version=args.version,
            target_id=target_id,
            channel=args.channel,
            signed=bool(args.signed),
            commit=args.commit,
            update_channel=update_channel,
        ),
    )
    if not args.skip_smoke:
        from raiker.app.desktop_smoke import SmokeFailure, run

        try:
            for line in run(host_executable(host_dir), expect_signed=bool(args.signed)):
                print(f"[smoke] {line}", flush=True)
        except SmokeFailure as failure:
            print(f"[smoke] FAIL {failure}", file=sys.stderr)
            return 1

    desktop = source_root / "desktop"
    shutil.rmtree(desktop / "release", ignore_errors=True)
    # The shell's own TypeScript, compiled from this checkout: packaging never
    # reuses a `dist/` left over from another build.
    npm = shutil.which("npm") or "npm"
    built = subprocess.run([npm, "run", "build"], cwd=desktop, check=False)  # noqa: S603 - fixed argv
    if built.returncode != 0:
        return built.returncode
    npx = shutil.which("npx") or "npx"
    completed = subprocess.run(  # noqa: S603 - pinned tool, fixed argv
        builder_command(target_id=target_id, version=args.version, npx=npx),
        cwd=desktop,
        env=builder_environment(target_id=target_id, signed=bool(args.signed), environ=dict(os.environ)),
        check=False,
    )
    if completed.returncode != 0:
        return completed.returncode

    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    names = list(artifact_names(args.version, target_id, signed=bool(args.signed)).values())
    for name in names:
        produced = desktop / "release" / name
        if not produced.is_file():
            print(f"refused: electron-builder did not produce {name}", file=sys.stderr)
            return 1
        shutil.copy2(produced, out_dir / name)
    artifacts = write_manifests(
        out_dir,
        version=args.version,
        target_id=target_id,
        signed=bool(args.signed),
        channel=args.channel,
        private_key=release_key,
    )
    published = names + [a.manifest_path.name for a in artifacts] + [
        a.signature_path.name for a in artifacts if a.signature_path is not None
    ]
    checksums = write_checksums(out_dir, names, name=f"SHA256SUMS-{target_id}.txt")
    (out_dir / f"desktop-{target_id}.json").write_text(
        json.dumps(
            {
                "version": args.version,
                "target": target_id,
                "signed": bool(args.signed),
                "commit": args.commit,
                "artifacts": [
                    {"name": a.path.name, "sha256": a.sha256, "size": a.path.stat().st_size}
                    for a in artifacts
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"target": target_id, "published": published, "checksums": checksums.name}, indent=2))
    return 0
