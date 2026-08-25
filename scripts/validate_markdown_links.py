# SPDX-License-Identifier: Apache-2.0
"""Validate repository-relative links in Markdown files and directories."""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import unquote

LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")


def _slug(heading: str) -> str:
    value = heading.strip().replace("`", "").replace("*", "")
    value = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"[^\w\s-]", "", value.lower(), flags=re.UNICODE)
    return value.replace(" ", "-")


def _files(inputs: list[Path]) -> list[Path]:
    found: set[Path] = set()
    for item in inputs:
        if item.is_dir():
            found.update(item.rglob("*.md"))
        elif item.suffix.lower() == ".md":
            found.add(item)
    return sorted(found)


def missing_links(inputs: list[Path]) -> list[str]:
    failures: list[str] = []
    for source in _files(inputs):
        text = source.read_text(encoding="utf-8")
        for raw in LINK.findall(text):
            destination = raw.strip().split(maxsplit=1)[0].strip("<>")
            if destination.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path_text, _, fragment = unquote(destination).partition("#")
            target = (source.parent / path_text).resolve()
            if not target.exists():
                failures.append(f"{source}: missing {destination}")
                continue
            if fragment and target.is_file() and target.suffix.lower() == ".md":
                headings = {
                    _slug(line.lstrip("#").strip())
                    for line in target.read_text(encoding="utf-8").splitlines()
                    if line.startswith("#")
                }
                if fragment.lower() not in headings:
                    failures.append(f"{source}: missing heading #{fragment} in {target}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    failures = missing_links(args.paths)
    for failure in failures:
        print(failure)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
