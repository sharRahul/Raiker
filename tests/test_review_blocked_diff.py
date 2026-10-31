"""A refused diff must never be reported as a clean review."""

from pathlib import Path

import pytest

from raiker.review.workflow import CodeReviewWorkflow, ReviewError


def test_review_propagates_refused_diff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "raiker.review.workflow.run_git",
        lambda *args, **kwargs: {
            "status": "denied", "error": {"type": "git_diff_argument_denied"}
        },
    )
    with pytest.raises(ReviewError, match="git_diff_argument_denied"):
        CodeReviewWorkflow(emit_events=False)._git_diff(tmp_path, path_filter=None, cached=False)


def test_cli_says_the_diff_could_not_be_collected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from raiker.cli.commands import handle_review

    def refused(*args: object, **kwargs: object) -> None:
        raise ReviewError("git_diff_argument_denied")

    monkeypatch.setattr(CodeReviewWorkflow, "review", refused)
    assert handle_review("/review", workspace_root=tmp_path) == (
        "Review unavailable: the Git diff could not be collected."
    )
