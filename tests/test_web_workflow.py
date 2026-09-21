"""GCR-15 — the web job runs for the contracts the web client reads.

`.github/workflows/web.yml` used to trigger on `web/**` alone, so a backend-only
change to an API route or a read DTO could merge without the client ever being
compiled against it and without the mocked end-to-end suite being run.

Half of that closed in the Python job: `scripts/check_api_contract.py` derives a
field-for-field comparison between the backend dataclasses and the TypeScript
mirror, so a dropped field fails there (GCR-42 / FIXED-575). What it cannot see
is everything past the field names — a contract that matches exactly while the
page reading it no longer builds.

These hold the trigger against the checker's own module list. A DTO module added
to the checker but not to the trigger is a module whose change can still reach
`main` without the client being built, and it fails here rather than silently.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

from scripts.check_api_contract import DTO_MODULES

WORKFLOW = Path(".github/workflows/web.yml")


def _workflow() -> dict[str, Any]:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _triggers() -> dict[str, list[str]]:
    # `on:` parses as the boolean True in YAML 1.1, which is what PyYAML
    # implements. Reading it by that key rather than by the string is the
    # honest way to say so; the cast is because the mapping is keyed by that
    # boolean and nothing else in the file is.
    on = cast(dict[Any, Any], _workflow())[True]
    return {name: list(config["paths"]) for name, config in on.items()}


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
        package_glob = f"{module.split('.')[0]}/{module.split('.')[1]}/**"
        covered = as_file in paths or package_glob in paths
        assert covered, f"{module} can change without the web client being built ({as_file})"


def test_the_api_routes_trigger_the_web_job() -> None:
    """The routes are the other half of the contract: names, shapes and status
    codes the client branches on, none of which the field comparison sees."""
    assert "raiker/api/**" in set(_triggers()["pull_request"])


def test_the_web_app_itself_still_triggers_it() -> None:
    assert "web/**" in set(_triggers()["pull_request"])


def test_the_job_still_compiles_and_runs_the_client() -> None:
    """The trigger is only worth widening if the job does the thing the
    contract check cannot."""
    steps = {step.get("name", ""): step for step in _workflow()["jobs"]["web"]["steps"]}
    assert "Build" in steps
    assert any("test:e2e:mocked" in str(step.get("run", "")) for step in steps.values())
