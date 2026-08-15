"""Native helpers that travel in the wheel.

One file lives here per platform directory: `raiker-command-runner`, the binary
that builds the operating-system boundary a governed command runs inside, plus
the `digest.json` recorded when it was built.

This module is empty on purpose, and it must not be deleted.
``[tool.setuptools.packages.find]`` is ``find``, not ``find_namespace``: without
an ``__init__.py`` setuptools never discovers `raiker.native`, the declared
package data applies to nothing, and every installed Raiker reports
`native_sandbox_artifact_missing` while every developer machine passes.

Populate it with ``python scripts/build_native_runner.py``.
"""
