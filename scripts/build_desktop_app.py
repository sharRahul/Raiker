# SPDX-License-Identifier: Apache-2.0
"""Build this platform's Raiker desktop installers (see raiker/app/desktop_build.py)."""
from __future__ import annotations

from raiker.app.desktop_build import build_app

if __name__ == "__main__":
    raise SystemExit(build_app())
