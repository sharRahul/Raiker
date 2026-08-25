from pathlib import Path

from scripts.validate_markdown_links import missing_links


def test_validates_files_directories_fragments_and_external_links(tmp_path: Path) -> None:
    target = tmp_path / "target.md"
    target.write_text("# Target heading\n", encoding="utf-8")
    source = tmp_path / "source.md"
    source.write_text(
        "[file](target.md) [heading](target.md#target-heading) "
        "[external](https://example.com) [local](#same-page)\n",
        encoding="utf-8",
    )
    assert missing_links([tmp_path]) == []


def test_reports_missing_file_and_heading(tmp_path: Path) -> None:
    target = tmp_path / "target.md"
    target.write_text("# Present\n", encoding="utf-8")
    source = tmp_path / "source.md"
    source.write_text("[file](missing.md) [heading](target.md#absent)\n", encoding="utf-8")
    failures = missing_links([source])
    assert len(failures) == 2
    assert "missing.md" in failures[0]
    assert "#absent" in failures[1]
