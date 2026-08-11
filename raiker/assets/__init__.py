"""Files Raiker ships as part of itself, resolved the same way everywhere.

The application icon had three different answers depending on who asked. The
native tray drew a rounded rectangle with PIL rather than using the icon at all,
so the tray Raiker showed in the system menu bar was not the icon the product
ships. The installer looked for ``assets/icons/raiker.png`` — a name that has
never existed in this repository — and, finding nothing, wrote a **zero-byte**
``raiker.png`` into the AppImage, which is why a Linux install showed a blank
square in its launcher.

One resolver, one file, three consumers. It looks in the wheel first so a frozen
or installed build needs no repository, falls back to the source tree, and lets
``RAIKER_ICON_PATH`` override both for a build that brands its own.
"""
from __future__ import annotations

import os
from pathlib import Path

ICON_FILENAME = "raiker-icon.png"


def icon_path() -> Path | None:
    """The application icon, or ``None`` when no readable copy exists."""
    override = os.environ.get("RAIKER_ICON_PATH", "").strip()
    candidates = [
        *( [Path(override)] if override else [] ),
        Path(__file__).resolve().parent / ICON_FILENAME,
        Path(__file__).resolve().parents[2] / "assets" / "icons" / ICON_FILENAME,
    ]
    return next((path for path in candidates if path.is_file()), None)
