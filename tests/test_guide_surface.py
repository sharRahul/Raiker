"""The user guide as a product surface (BUG-208 slice A).

The guide existed as eight documents the product could not reach, which is why
23,236 characters of the same material were compiled into 53 components. These
cover the read side that makes moving it possible, and the one property that
matters beyond "it works": a slug never becomes an arbitrary path.
"""
from pathlib import Path

import pytest

from raiker.guide import SLUG_PATTERN, guide_root, list_sections, read_section


def test_the_guide_ships_with_the_source_tree() -> None:
    root = guide_root()
    assert root is not None, "docs/guide should resolve from a source checkout"
    assert (root / "getting-started.md").is_file()


def test_sections_are_offered_in_reading_order() -> None:
    slugs = [section.slug for section in list_sections()]
    assert slugs[:3] == ["getting-started", "connecting-a-model", "working-in-chat"]
    # The guide's own contents page would be a list inside the product's list.
    assert "readme" not in slugs


def test_each_section_names_itself_from_its_own_heading() -> None:
    sections = {section.slug: section for section in list_sections()}
    # Read from the document, so a guide edit cannot leave the product
    # describing a page as it used to be.
    assert sections["connecting-a-model"].title == "Connecting a model"
    assert sections["troubleshooting"].summary != ""


def test_a_summary_is_prose_and_never_a_code_line() -> None:
    # `getting-started` opens with a fenced install block. Walking into it made
    # the section list describe the page as "git clone https://…".
    for section in list_sections():
        assert not section.summary.startswith(("git ", "python ", "npm ", "$", "cd ")), section.slug


def test_a_section_returns_its_markdown() -> None:
    found = read_section("getting-started")
    assert found is not None
    section, markdown = found
    assert section.slug == "getting-started"
    assert markdown.lstrip().startswith("#")


@pytest.mark.parametrize(
    "slug",
    [
        "../../README",
        "../SECURITY",
        "getting-started/../../../etc/passwd",
        "/etc/passwd",
        "getting_started",
        "Getting-Started",
        "",
        ".",
    ],
)
def test_a_slug_never_becomes_an_arbitrary_path(slug: str) -> None:
    # The alphabet cannot describe anything but a guide page, so traversal is
    # refused before a path is built rather than sanitised afterwards.
    assert read_section(slug) is None


def test_the_slug_alphabet_accepts_every_shipped_section() -> None:
    for section in list_sections():
        assert SLUG_PATTERN.match(section.slug), section.slug


def test_an_install_without_a_guide_reports_none_rather_than_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A build that shipped no guide must be distinguishable from one whose guide
    # is empty: the surface says "not bundled" instead of "nothing to read".
    monkeypatch.setenv("RAIKER_GUIDE_DIR", str(tmp_path))
    assert guide_root() is None
    assert list_sections() == []
    assert read_section("getting-started") is None
