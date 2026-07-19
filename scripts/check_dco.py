# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
import re
import subprocess

_SIGNOFF = re.compile(r"^Signed-off-by:\s+[^<\n]+\s+<[^>\n]+>$", re.MULTILINE | re.IGNORECASE)


def has_dco_signoff(message: str) -> bool:
    return bool(_SIGNOFF.search(message))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate DCO trailers in a commit range.")
    parser.add_argument("--range", required=True, dest="commit_range")
    args = parser.parse_args()
    commits = subprocess.run(
        ["git", "log", "--format=%H%x00%B%x00", args.commit_range],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split("\x00")
    failures = [commits[index] for index in range(0, len(commits) - 1, 2) if not has_dco_signoff(commits[index + 1])]
    if failures:
        print("DCO sign-off missing:")
        print("\n".join(f"- {commit}" for commit in failures))
        return 1
    print("DCO sign-off check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
