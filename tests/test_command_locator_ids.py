"""An ID-shaped number in a command's folder is not secret material (found by BD-5).

Build's test run in `bd5-stats-1794142515/` was refused as
`command_secret_pattern_rejected` because the folder name looks like a phone
number. A credential in that folder's path is still refused.
"""

from __future__ import annotations

from raiker.context.redaction import redact_text
from raiker.execution.commands.store import _carries_secret

LOCATOR = {"locator_value": True}


def test_an_id_shaped_folder_is_not_a_secret() -> None:
    assert not _carries_secret("bd5-stats-1794142515", LOCATOR)
    assert not _carries_secret(r"C:\work\release-555-123-4567\src", LOCATOR)


def test_a_credential_in_the_path_is_still_a_secret() -> None:
    token = "ghp_" + "a1B2c3D4e5" * 4
    assert _carries_secret(f"/srv/{token}/repo", LOCATOR)
    assert _carries_secret(f"/srv/{token}/run-1794142515", LOCATOR)


def test_free_text_and_logs_still_mask_the_number() -> None:
    assert _carries_secret("call 555-123-4567", {})
    assert redact_text("bd5-stats-1794142515", locator_value=True)[0] == "bd5-stats-[REDACTED_ID]"


def _item(content: str, exact: tuple[str, ...]) -> str:
    from raiker.context.gatherer import ContextGatherer

    return ContextGatherer()._make_item(
        source_type="project_context",
        trust_level="user_prompt",
        sensitivity="normal",
        provenance={"origin": "project_context"},
        title="Project context",
        content=content,
        exact=exact,
    ).content


def test_the_model_is_told_the_repository_folder_as_it_is_named() -> None:
    text = "The selected repository is the folder bd5-stats-1794142515/. Call 555-123-4567."
    told = _item(text, ("bd5-stats-1794142515",))
    assert "bd5-stats-1794142515/" in told
    # Anything else in the item is still redacted.
    assert "555-123-4567" not in told


def test_a_repository_path_holding_a_credential_is_not_passed_through() -> None:
    token = "ghp_" + "a1B2c3D4e5" * 4
    told = _item(f"The selected repository is the folder {token}/.", (token,))
    assert token not in told
