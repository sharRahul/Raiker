# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
import importlib.metadata
import json
import re
import subprocess
import tarfile
import tomllib
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UNKNOWN = {"", "UNKNOWN", "NOASSERTION", "UNLICENSED", "NONE"}
LICENSE_ALIASES = {
    "Apache License 2.0": "Apache-2.0",
    "Apache Software License": "Apache-2.0",
    "BSD License": "BSD-3-Clause",
    "MIT License": "MIT",
    "Python Software Foundation License": "Python-2.0",
    "PSFL": "Python-2.0",
    "PSF": "Python-2.0",
    "PSF-2.0": "Python-2.0",
    "zlib/libpng": "Zlib",
    "Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
}


def normalize_license(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    lower = value.lower()
    if "mit license" in lower or "(mit)" in lower:
        return "MIT"
    return LICENSE_ALIASES.get(value, value)


def classify_license(value: str | None, policy: dict[str, list[str]]) -> str:
    value = normalize_license(value)
    if value is None or value.upper() in UNKNOWN:
        return "unknown"
    choices = [choice.strip(" ()") for choice in re.split(r"\s+OR\s+", value, flags=re.IGNORECASE)]
    if any(choice in policy["permitted"] for choice in choices):
        return "permitted"
    if any(choice in policy["prohibited"] for choice in choices):
        return "prohibited"
    if any(choice in policy["review"] for choice in choices):
        return "review"
    return "unknown"


def load_policy(root: Path) -> dict[str, Any]:
    return json.loads((root / "docs/licensing/LICENSE_POLICY.json").read_text(encoding="utf-8"))


def package_lock_components(root: Path) -> list[dict[str, str | None]]:
    lock = json.loads((root / "apps/web/package-lock.json").read_text(encoding="utf-8"))
    components: list[dict[str, str | None]] = []
    for location, package in sorted(lock["packages"].items()):
        name = package.get("name") or (location.rsplit("node_modules/", 1)[-1] if location else "raiker-web")
        components.append({"name": name, "version": package.get("version"), "license": package.get("license")})
    return components


def python_components(root: Path) -> list[dict[str, str | None]]:
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    names = {re.split(r"[<>=!~;[ ]", requirement, maxsplit=1)[0].lower().replace("_", "-") for requirement in project["dependencies"] + project["optional-dependencies"]["dev"]}
    distributions = {
        distribution.metadata["Name"].lower().replace("_", "-"): distribution
        for distribution in importlib.metadata.distributions()
        if "Name" in distribution.metadata
    }
    pending = list(names)
    resolved: set[str] = set()
    components: list[dict[str, str | None]] = []
    while pending:
        name = pending.pop()
        if name in resolved or name not in distributions:
            continue
        resolved.add(name)
        distribution = distributions[name]
        metadata = distribution.metadata
        if "License-Expression" in metadata:
            license_value = metadata["License-Expression"]
        elif "License" in metadata:
            license_value = metadata["License"]
        else:
            license_value = None
        if not license_value:
            classifiers = metadata.get_all("Classifier") or []
            license_value = next((item.rsplit("::", 1)[-1].strip() for item in classifiers if item.startswith("License ::")), None)
        components.append({"name": metadata["Name"], "version": metadata["Version"], "license": normalize_license(license_value)})
        for requirement in metadata.get_all("Requires-Dist") or []:
            if ";" in requirement and "extra ==" in requirement.split(";", 1)[1]:
                continue
            dependency = re.split(r"[<>=!~;[ ]", requirement, maxsplit=1)[0].lower().replace("_", "-")
            if dependency:
                pending.append(dependency)
    return sorted(components, key=lambda component: str(component["name"]).lower())


def check_project_files(root: Path) -> list[str]:
    errors: list[str] = []
    if not (root / "LICENSE").read_text(encoding="utf-8").startswith("                                 Apache License\n"):
        errors.append("LICENSE is not the Apache License 2.0 text")
    if not (root / "NOTICE").is_file() or not (root / "DCO").is_file() or not (root / "CONTRIBUTING.md").is_file():
        errors.append("required root licensing files are missing")
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    if project.get("license") != "Apache-2.0":
        errors.append("pyproject.toml must declare Apache-2.0")
    for relative in (Path("package.json"), Path("apps/web/package.json")):
        manifest = json.loads((root / relative).read_text(encoding="utf-8"))
        if manifest.get("license") != "Apache-2.0":
            errors.append(f"{relative} must declare Apache-2.0")
    return errors


def check_headers(root: Path) -> list[str]:
    paths = [*sorted((root / "scripts").rglob("*.py")), root / "tests/test_licensing_checks.py"]
    return [f"missing SPDX header: {path.relative_to(root)}" for path in paths if not path.read_text(encoding="utf-8").startswith("# SPDX-License-Identifier: Apache-2.0\n")]


# Sentinel phrase for a stale MIT licence claim, assembled from fragments so
# this checker — itself a tracked first-party file — does not match its own scan.
_STALE_MIT_MARKER = "Released under the " + "MIT License"


def check_stale_mit(root: Path) -> list[str]:
    tracked = subprocess.run(["git", "ls-files"], cwd=root, check=True, capture_output=True, text=True).stdout.splitlines()
    exclusions = {"docs/licensing/APACHE_2_RELICENSING_AUDIT.md"}
    errors: list[str] = []
    for relative in tracked:
        if relative in exclusions or relative.endswith(".lock") or relative == "LICENSE":
            continue
        path = root / relative
        if path.is_file() and b"\x00" not in path.read_bytes() and _STALE_MIT_MARKER in path.read_text(encoding="utf-8", errors="ignore"):
            errors.append(f"stale first-party MIT claim: {relative}")
    return errors


def check_distributions(dist_dir: Path) -> list[str]:
    errors: list[str] = []
    archives = list(dist_dir.glob("*"))
    if not any(archive.suffix == ".whl" for archive in archives):
        errors.append("no wheel found for licence validation")
    if not any(archive.suffixes[-2:] == [".tar", ".gz"] for archive in archives):
        errors.append("no source distribution found for licence validation")
    for archive in archives:
        if archive.suffix == ".whl":
            with zipfile.ZipFile(archive) as bundle:
                names = bundle.namelist()
                metadata = next((name for name in names if name.endswith(".dist-info/METADATA")), "")
                if not any(name.endswith("LICENSE") for name in names) or not any(name.endswith("NOTICE") for name in names):
                    errors.append(f"wheel missing licence material: {archive.name}")
                if "License-Expression: Apache-2.0" not in bundle.read(metadata).decode("utf-8"):
                    errors.append(f"wheel metadata missing Apache-2.0: {archive.name}")
        elif archive.suffixes[-2:] == [".tar", ".gz"]:
            with tarfile.open(archive) as bundle:
                names = bundle.getnames()
                if not any(name.endswith("/LICENSE") for name in names) or not any(name.endswith("/NOTICE") for name in names):
                    errors.append(f"sdist missing licence material: {archive.name}")
    return errors


def write_sbom(path: Path, components: list[dict[str, str | None]]) -> None:
    packages = []
    for index, component in enumerate(components, start=1):
        license_value = normalize_license(component["license"]) or "NOASSERTION"
        packages.append({"SPDXID": f"SPDXRef-Package-{index}", "name": component["name"], "versionInfo": component["version"], "downloadLocation": "NOASSERTION", "filesAnalyzed": False, "licenseConcluded": license_value, "licenseDeclared": license_value, "supplier": "NOASSERTION"})
    payload: dict[str, Any] = {"spdxVersion": "SPDX-2.3", "dataLicense": "CC0-1.0", "SPDXID": "SPDXRef-DOCUMENT", "name": "raiker-dependencies", "documentNamespace": "https://github.com/sharRahul/Raiker/sbom", "creationInfo": {"creators": ["Tool: scripts/licensing_check.py"]}, "packages": packages}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def has_exception(component: dict[str, str | None], policy: dict[str, Any]) -> bool:
    license_value = normalize_license(component["license"])
    return any(
        exception["component"] == component["name"] and exception["license"] == license_value
        for exception in policy["exceptions"]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Raiker licensing and produce an SPDX JSON SBOM.")
    parser.add_argument("--sbom", type=Path)
    parser.add_argument("--dist-dir", type=Path)
    args = parser.parse_args()
    policy = load_policy(ROOT)
    components = [*python_components(ROOT), *package_lock_components(ROOT)]
    errors = [*check_project_files(ROOT), *check_headers(ROOT), *check_stale_mit(ROOT)]
    for component in components:
        status = classify_license(component["license"], policy)
        print(f"{status}: {component['name']} {component['version']} ({component['license'] or 'NOASSERTION'})")
        if status != "permitted" and not has_exception(component, policy):
            errors.append(f"{status} dependency licence: {component['name']} ({component['license'] or 'NOASSERTION'})")
    if args.dist_dir:
        errors.extend(check_distributions(args.dist_dir))
    if args.sbom:
        write_sbom(args.sbom, components)
        print(f"Wrote SPDX JSON SBOM: {args.sbom}")
    if errors:
        print("Licensing check failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("Licensing check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
