"""GCR-15 — the web job runs for the contracts the web client reads.

The web job used to live in its own workflow triggered on `web/**` alone, so a
backend-only change to an API route or a read DTO could merge without the client
ever being compiled against it and without the mocked end-to-end suite being run.

It is now a job in `.github/workflows/ci.yml`, which runs on every pull request
and every push to `main` with no path filter — so every module the contract
checker reads, and every route, triggers it by construction. These tests hold
that: a path filter added back to CI would have to cover the checker's modules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

from scripts.check_api_contract import DTO_MODULES

WORKFLOW = Path(".github/workflows/ci.yml")


def _workflow() -> dict[str, Any]:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _triggers() -> dict[str, list[str]]:
    # `on:` parses as the boolean True in YAML 1.1, which is what PyYAML
    # implements. Reading it by that key rather than by the string is the
    # honest way to say so; the cast is because the mapping is keyed by that
    # boolean and nothing else in the file is.
    on = cast(dict[Any, Any], _workflow())[True]
    # No `paths` filter means every change triggers it: "**".
    return {name: list((config or {}).get("paths") or ["**"]) for name, config in on.items()}


def _covered(path: str, paths: set[str]) -> bool:
    if "**" in paths or path in paths:
        return True
    parts = path.split("/")
    return any("/".join(parts[:depth]) + "/**" in paths for depth in range(1, len(parts)))


def test_both_triggers_watch_the_same_paths() -> None:
    """A pull request and a push to main must be guarded by the same rule.

    Two lists that are meant to be identical and are maintained separately
    become one list and one stale list.
    """
    triggers = _triggers()
    assert triggers["pull_request"] == triggers["push"]


def test_every_dto_module_the_contract_check_reads_triggers_the_web_job() -> None:
    paths = set(_triggers()["pull_request"])
    for module in DTO_MODULES:
        as_file = f"{module.replace('.', '/')}.py"
        assert _covered(as_file, paths), f"{module} can change without the web client being built ({as_file})"


def test_the_api_routes_trigger_the_web_job() -> None:
    """The routes are the other half of the contract: names, shapes and status
    codes the client branches on, none of which the field comparison sees."""
    assert _covered("raiker/api/routes_code_files.py", set(_triggers()["pull_request"]))


def test_the_web_app_itself_still_triggers_it() -> None:
    assert _covered("web/src/App.svelte", set(_triggers()["pull_request"]))


def test_the_job_still_compiles_and_runs_the_client() -> None:
    """The trigger is only worth widening if the job does the thing the
    contract check cannot."""
    steps = {step.get("name", ""): step for step in _workflow()["jobs"]["web"]["steps"]}
    assert "Build" in steps
    assert any("test:e2e:mocked" in str(step.get("run", "")) for step in steps.values())
