"""FIXED-192 — one application icon, resolved the same way everywhere.

The tray drew its own rounded rectangle, so the mark in the system tray was not
the mark the product ships; the AppImage build looked for a filename that has
never existed here and wrote a zero-byte icon instead of failing.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from raiker.app.tray import TRAY_ICON_SIZE, tray_image
from raiker.assets import ICON_FILENAME, icon_path


def test_the_icon_ships_inside_the_package() -> None:
    """Not only in the repository — a wheel has no `assets/` directory."""
    packaged = Path(__file__).resolve().parents[1] / "raiker" / "assets" / ICON_FILENAME
    assert packaged.is_file()
    assert packaged.stat().st_size > 0


def test_the_resolver_finds_the_shipped_icon() -> None:
    resolved = icon_path()
    assert resolved is not None
    assert resolved.name == ICON_FILENAME


def test_an_override_wins_over_the_shipped_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """So a build can brand its own without patching the package."""
    branded = tmp_path / "branded.png"
    branded.write_bytes(b"not really a png, but it is a file")
    monkeypatch.setenv("RAIKER_ICON_PATH", str(branded))
    assert icon_path() == branded


def test_a_missing_override_falls_through_rather_than_failing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAIKER_ICON_PATH", "/nowhere/at/all.png")
    assert icon_path() is not None


def test_the_tray_uses_the_shipped_icon_at_tray_size() -> None:
    image_module = pytest.importorskip("PIL.Image")
    draw_module = pytest.importorskip("PIL.ImageDraw")
    image = tray_image(image_module, draw_module)
    assert image.size == TRAY_ICON_SIZE
    assert image.mode == "RGBA"


def test_the_tray_still_starts_when_no_icon_can_be_read(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A tray with a placeholder is still a tray; no tray removes Pause and Quit."""
    image_module = pytest.importorskip("PIL.Image")
    draw_module = pytest.importorskip("PIL.ImageDraw")
    unreadable = tmp_path / "broken.png"
    unreadable.write_bytes(b"definitely not an image")
    monkeypatch.setenv("RAIKER_ICON_PATH", str(unreadable))
    assert tray_image(image_module, draw_module).size == TRAY_ICON_SIZE
