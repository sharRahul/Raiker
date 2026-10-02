"""The OpenAPI document, its TypeScript and the route inventory are current.

OPT-01/OPT-02 Stage A. ``scripts/api_contract.py`` derives three committed files
from the running app; a route or view changed without regenerating them would
leave the browser compiled against a contract the server no longer has.
"""

from __future__ import annotations

from scripts.api_contract import VERIFIED, build_app, contracts, main, render_inventory


def test_the_generated_contract_files_are_current() -> None:
    assert main(["--check"]) == 0, "run `python -m scripts.api_contract`"


def test_the_inventory_accounts_for_every_api_operation() -> None:
    rows = contracts(build_app())
    assert len(rows) > 300
    assert {row.status for row in rows} <= {"verified", "eligible", "deferred", "special"}
    assert sum(row.status == "verified" for row in rows) == len(VERIFIED)


def test_a_streamed_answer_is_never_described_as_json() -> None:
    rows = {(row.method, row.path): row for row in contracts(build_app())}
    assert rows[("POST", "/api/prompts/stream")].status == "special"


def test_the_inventory_states_its_counts() -> None:
    text = render_inventory(build_app())
    assert "verified" in text and "deferred" in text
