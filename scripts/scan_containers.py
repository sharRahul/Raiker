# SPDX-License-Identifier: Apache-2.0
"""Fail a change that weakens a container Raiker builds (DEC-24 step 7).

Raiker runs owner commands and its egress proxy in containers it builds from
the ``Containerfile``/``Dockerfile`` definitions in this repository. Each one is
read here, without a network and without a container engine, for the five
properties the sandbox and proxy depend on:

* **every base image is pinned by digest** (``FROM image@sha256:…``) — a tag is
  whatever its publisher points it at today, so a rebuild could run code
  nobody reviewed;
* **the image ends as a non-root user** — the last ``USER`` names someone other
  than ``root``/``0``, so a command that escapes its working directory still
  lands as nobody in particular;
* **nothing is added from a URL** — ``ADD http…`` fetches an unpinned,
  unverified file at build time;
* **nothing is piped into a shell** — ``curl … | sh`` runs whatever the server
  sent;
* **no credential-shaped value is baked in** — an ``ENV``/``ARG`` named like a
  token, key, secret or password with a value assigned ends up in every layer.

This checks the definitions, not the images' contents: vulnerability scanning
of the built images is a separate step that needs a pinned scanner and its own
reviewed exception policy.

    python scripts/scan_containers.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_NAMES = re.compile(r"(?:^|/)(?:Containerfile|Dockerfile)(?:\.[\w.-]+)?$")
_FROM = re.compile(r"^FROM\s+(?:--platform=\S+\s+)?(\S+)", re.IGNORECASE)
_USER = re.compile(r"^USER\s+(\S+)", re.IGNORECASE)
_ADD_URL = re.compile(r"^ADD\s+(?:--\S+\s+)*https?://", re.IGNORECASE)
_PIPE_SHELL = re.compile(r"\|\s*(?:sudo\s+)?(?:ba|z|da)?sh\b")
_SECRET_ASSIGN = re.compile(
    r"^(?:ENV|ARG)\s+\w*(?:TOKEN|SECRET|PASSWORD|PASSWD|API_KEY|PRIVATE_KEY)\w*\s*[= ]\s*\S",
    re.IGNORECASE,
)
_ROOT_USERS = {"root", "0", "0:0", "root:root"}


@dataclass(frozen=True)
class Problem:
    path: str
    line: int
    rule: str
    detail: str

    def describe(self) -> str:
        return f"{self.path}:{self.line}: {self.rule} — {self.detail}"


def instructions(text: str) -> list[tuple[int, str]]:
    """Logical instructions with their first line number; continuations joined."""
    out: list[tuple[int, str]] = []
    buffer: list[str] = []
    start = 0
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not buffer and (not line or line.startswith("#")):
            continue
        if not buffer:
            start = number
        if line.endswith("\\"):
            buffer.append(line[:-1].strip())
            continue
        buffer.append(line)
        out.append((start, " ".join(part for part in buffer if part)))
        buffer = []
    if buffer:
        out.append((start, " ".join(buffer)))
    return out


def scan_definition(path: str, text: str) -> list[Problem]:
    problems: list[Problem] = []
    stages: set[str] = set()
    last_user: tuple[int, str] | None = None
    saw_from = False
    for number, instruction in instructions(text):
        match = _FROM.match(instruction)
        if match:
            saw_from = True
            image = match.group(1)
            alias = re.search(r"\s+AS\s+(\S+)\s*$", instruction, re.IGNORECASE)
            if image.lower() not in stages and image != "scratch" and "@sha256:" not in image:
                problems.append(Problem(path, number, "base_not_pinned", f"{image} is not pinned by @sha256 digest"))
            if alias:
                stages.add(alias.group(1).lower())
            last_user = None  # each stage starts as its base image's user
            continue
        match = _USER.match(instruction)
        if match:
            last_user = (number, match.group(1))
            continue
        if _ADD_URL.match(instruction):
            problems.append(Problem(path, number, "add_from_url", "ADD fetches a URL at build time; COPY a verified file instead"))
        if instruction.upper().startswith("RUN") and _PIPE_SHELL.search(instruction):
            problems.append(Problem(path, number, "pipe_to_shell", "a download is piped into a shell"))
        if _SECRET_ASSIGN.match(instruction):
            problems.append(Problem(path, number, "credential_in_image", "a credential-shaped ENV/ARG has a value baked in"))
    if not saw_from:
        problems.append(Problem(path, 1, "no_base_image", "no FROM instruction"))
    elif last_user is None:
        problems.append(Problem(path, 1, "runs_as_root", "the final stage never sets a non-root USER"))
    elif last_user[1].lower() in _ROOT_USERS:
        problems.append(Problem(path, last_user[0], "runs_as_root", f"the final USER is {last_user[1]}"))
    return problems


def definitions(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True
    ).stdout.decode("utf-8", "replace")
    return sorted(name for name in out.split("\0") if name and _NAMES.search(name))


def main() -> int:
    names = definitions(ROOT)
    problems = [
        problem
        for name in names
        for problem in scan_definition(name, (ROOT / name).read_text(encoding="utf-8"))
    ]
    for problem in problems:
        print(problem.describe(), file=sys.stderr)
    if problems:
        return 1
    print(f"Containers: {len(names)} definition(s) pinned, non-root and fetch-free.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
