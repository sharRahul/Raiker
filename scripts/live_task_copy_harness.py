# SPDX-License-Identifier: Apache-2.0
"""Leave a session's sandbox copy the way a sandboxed command would (BD-3, BD-4).

The live Build review needs a copy with changes in it. Producing one through a
real command needs a host whose native sandbox is enforced; this harness writes
the same on-disk state the command backend leaves, through the same registry,
so the review, Apply, Overwrite and Discard are exercised against the running
host exactly as they are after a real command.

    python scripts/live_task_copy_harness.py <workspace> <owner_principal> <session> <mode>

``mode`` is ``changes`` (one modified, one created, one deleted file) or
``conflict`` (the same, plus an owner edit to the modified file in the
project after the copy was taken). The project folder is ``beta-demo`` in the
workspace and is created fresh each call. Prints the copy's id.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from raiker.execution.commands.backends.native import task_workspace_registry


def main(argv: list[str]) -> int:
    workspace, owner, session, mode = Path(argv[0]).resolve(), argv[1], argv[2], argv[3]
    project = workspace / "beta-demo"
    registry = task_workspace_registry(workspace)
    for key, held_session, _copy in registry.entries(owner):
        if held_session == session:
            registry.release(owner, key)
    if project.exists():
        shutil.rmtree(project)
    project.mkdir()
    (project / "main.py").write_bytes(b"print('v1')\n")
    (project / "old.txt").write_bytes(b"old\n")
    key, copy = registry.acquire(owner, session, project)
    (copy.root / "main.py").write_bytes(b"print('v2 from the copy')\n")
    (copy.root / "old.txt").unlink()
    (copy.root / "new.py").write_bytes(b"x = 1\n")
    if mode == "conflict":
        (project / "main.py").write_bytes(b"print('owner edit')\n")
    print(key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
