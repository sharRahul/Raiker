# SPDX-License-Identifier: Apache-2.0
"""Retain verified phonemizer sources beside a personal voice-enabled package."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from importlib import metadata
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]


def download_source(record: dict[str, Any], destination: Path, client: httpx.Client) -> Path:
    name = record["name"]
    if not isinstance(name, str) or Path(name).name != name or not name.endswith(".tar.gz"):
        raise ValueError("voice_source_name_invalid")
    target = destination / name
    temporary = target.with_suffix(".partial")
    digest = hashlib.sha256()
    size = 0
    try:
        with client.stream("GET", record["url"]) as response:
            response.raise_for_status()
            with temporary.open("wb") as output:
                for chunk in response.iter_bytes(128 * 1024):
                    size += len(chunk)
                    if size > record["size"]:
                        raise ValueError("voice_source_size_mismatch")
                    digest.update(chunk)
                    output.write(chunk)
        if size != record["size"] or digest.hexdigest() != record["sha256"]:
            raise ValueError("voice_source_digest_mismatch")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    notices = ROOT / "docs/licensing/voice"
    catalogue = json.loads((notices / "runtime-sources.json").read_text())
    with httpx.Client(timeout=httpx.Timeout(30, read=180), follow_redirects=True) as client:
        for record in catalogue["sources"]:
            download_source(record, args.out, client)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    archive = args.out / f"raiker-{commit}-source.tar.gz"
    temporary = archive.with_suffix(".partial")
    try:
        with temporary.open("wb") as output:
            subprocess.run(["git", "archive", "--format=tar.gz", "--prefix=raiker-source/", commit],
                           cwd=ROOT, stdout=output, check=True)
        temporary.replace(archive)
    finally:
        temporary.unlink(missing_ok=True)
    for name in ("README.md", "GPL-3.0.txt", "espeakng-loader-MIT.txt", "runtime-sources.json"):
        shutil.copyfile(notices / name, args.out / name)
    shutil.copyfile(ROOT / "requirements/voice.txt", args.out / "voice-requirements.txt")
    record = {"source_commit": commit, "sources": catalogue["sources"],
              "raiker_source": {"name": archive.name, "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}}
    (args.out / "SOURCE_EVIDENCE.json").write_text(json.dumps(record, indent=2) + "\n")
    from raiker.app.desktop_build import voice_runtime_pins
    from scripts.licensing_check import (
        distribution_license,
        package_lock_components,
        python_components,
        write_sbom,
    )

    runtime = []
    for name, expected in voice_runtime_pins(ROOT):
        distribution = metadata.distribution(name)
        if distribution.version != expected:
            raise ValueError(f"voice runtime mismatch: {name}")
        licence = distribution_license(distribution)
        if name == "espeakng-loader":
            licence = "MIT"  # Pinned wrapper source LICENSE is retained alongside GPL native-library sources.
        elif name == "phonemizer":
            licence = "GPL-3.0"  # Retained wheel licence and pinned corresponding source.
        elif not licence:
            for file in distribution.files or []:
                if file.name.upper() == "LICENSE":
                    text = Path(str(distribution.locate_file(file))).read_text(errors="replace")
                    if "MIT License" in text:
                        licence = "MIT"
                        break
        runtime.append({"name": name, "version": expected, "license": licence})
    runtime.append({"name": "espeak-ng", "version": "1.52.0", "license": "GPL-3.0"})
    (args.out / "VOICE_RUNTIME_INVENTORY.json").write_text(json.dumps(runtime, indent=2) + "\n")
    base = python_components(ROOT) + package_lock_components(ROOT)
    seen = {str(component["name"]).lower().replace("_", "-") for component in base}
    write_sbom(args.out / "personal-voice.spdx.json", base + [item for item in runtime if item["name"] not in seen])
    print(f"Verified {len(catalogue['sources'])} upstream sources and archived Raiker {commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
