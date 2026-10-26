"""A short description of a browser, for the owner's list of signed-in devices.

BUG-358. It is what the browser *says* it is (``User-Agent``), reduced to "Chrome
on Windows" so the owner can tell their sessions apart. It identifies nothing:
any client can send any string, so it is shown as reported, never used to
decide anything, and never treated as proof of which device a session is on.
"""

from __future__ import annotations

_BROWSERS = (
    ("Edg/", "Edge"),
    ("OPR/", "Opera"),
    ("Firefox/", "Firefox"),
    ("Chrome/", "Chrome"),
    ("Safari/", "Safari"),
)
_SYSTEMS = (
    ("Windows", "Windows"),
    ("iPhone", "iPhone"),
    ("iPad", "iPad"),
    ("Android", "Android"),
    ("Mac OS X", "macOS"),
    ("Macintosh", "macOS"),
    ("CrOS", "ChromeOS"),
    ("Linux", "Linux"),
)


def describe(user_agent: str | None) -> str | None:
    """``"Chrome on Windows"``, or None when nothing recognisable was sent."""
    if not user_agent:
        return None
    text = user_agent[:512]
    if text.startswith("raiker"):
        return "Raiker app"
    browser = next((name for marker, name in _BROWSERS if marker in text), None)
    system = next((name for marker, name in _SYSTEMS if marker in text), None)
    if browser and system:
        return f"{browser} on {system}"
    return browser or system
