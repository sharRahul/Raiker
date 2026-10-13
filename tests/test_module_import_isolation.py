"""Every module under ``raiker`` imports on its own (BUG-326).

The app, the CLI and the test suite each import something first that happens to
break an import cycle, so a cycle is invisible until a new script imports the
"wrong" module first — ``import raiker.runtime.orchestrator`` failed on
``models.connections`` ↔ ``runtime.executors`` for exactly that reason. Each
module is imported in a fresh interpreter, several at a time.
"""

from __future__ import annotations

import os
import pkgutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import raiker

# One interpreter imports this many modules, each after clearing every
# ``raiker`` module the previous one loaded, so each still starts from nothing.
_BATCH = 24

_RUNNER = """
import importlib, sys, traceback
failures = []
for name in sys.argv[1:]:
    for loaded in [m for m in sys.modules if m == "raiker" or m.startswith("raiker.")]:
        del sys.modules[loaded]
    try:
        importlib.import_module(name)
    except BaseException:
        failures.append(name + ": " + traceback.format_exc().strip().splitlines()[-1])
print("\\n".join(failures))
sys.exit(1 if failures else 0)
"""


def _modules() -> list[str]:
    return sorted(module.name for module in pkgutil.walk_packages(raiker.__path__, "raiker."))


def _run(batch: list[str]) -> str:
    result = subprocess.run(
        [sys.executable, "-c", _RUNNER, *batch],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    return result.stdout.strip() if result.returncode else ""


def test_every_module_imports_first() -> None:
    modules = _modules()
    assert "raiker.runtime.orchestrator" in modules
    batches = [modules[i : i + _BATCH] for i in range(0, len(modules), _BATCH)]
    with ThreadPoolExecutor(max_workers=max(2, os.cpu_count() or 2)) as pool:
        failures = [report for report in pool.map(_run, batches) if report]
    assert not failures, "\n".join(failures)
