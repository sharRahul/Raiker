from __future__ import annotations

import pytest

from raiker.tools.filesystem import (
    FilesystemSafetyError,
    glob_paths,
    grep_files,
    list_directory,
    read_file,
)


def test_read_file_success_missing_binary_and_denial(tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "bin.dat").write_bytes(b"a\x00b")
    assert read_file(tmp_path, "a.txt")["text"] == "hello"
    assert read_file(tmp_path, "missing.txt")["error"]["type"] == "not_found"
    assert read_file(tmp_path, "bin.dat")["error"]["type"] == "binary_file"
    with pytest.raises(FilesystemSafetyError):
        read_file(tmp_path, "../outside.txt")


def test_list_directory_sorted_and_denial(tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    (tmp_path / "a").mkdir()
    assert list_directory(tmp_path, ".")["entries"] == ["a/", "b.txt"]
    with pytest.raises(FilesystemSafetyError):
        list_directory(tmp_path, "../")


def test_glob_and_grep_bounded(tmp_path) -> None:  # type: ignore[no-untyped-def]
    for index in range(5):
        (tmp_path / f"f{index}.txt").write_text(f"needle {index}\n", encoding="utf-8")
    assert glob_paths(tmp_path, "*.txt", max_results=2)["truncated"] is True
    result = grep_files(tmp_path, "needle", ".", max_results=3)
    assert len(result["matches"]) == 3
    assert result["truncated"] is True
