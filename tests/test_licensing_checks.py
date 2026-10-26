# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path

from scripts.licensing_check import classify_license, has_exception, load_policy, normalize_license


def test_license_classifier_accepts_permitted_dual_license() -> None:
    policy = {"permitted": ["Apache-2.0", "MIT"], "review": [], "prohibited": []}

    assert classify_license("Apache-2.0 OR MIT", policy) == "permitted"


def test_license_classifier_rejects_unknown_and_prohibited_licenses() -> None:
    policy = {"permitted": ["MIT"], "review": [], "prohibited": ["GPL-3.0-only"]}

    assert classify_license(None, policy) == "unknown"
    assert classify_license("GPL-3.0-only", policy) == "prohibited"


def test_license_classifier_normalizes_pystrays_metadata_label() -> None:
    assert normalize_license("LGPLv3") == "LGPL-3.0-only"


def test_license_classifier_normalizes_python_xlibs_metadata_label() -> None:
    assert normalize_license("LGPLv2+") == "LGPL-2.1-or-later"


def test_license_exceptions_cover_linux_tray_backend_and_build_backend_metadata() -> None:
    policy = load_policy(Path(__file__).resolve().parents[1])

    assert has_exception({"name": "python-xlib", "license": "LGPLv2+"}, policy)
    assert has_exception({"name": "setuptools", "license": None}, policy)


def test_a_bundled_zlib_licence_text_is_recognised_when_metadata_declares_none() -> None:
    """`sqlcipher3` 0.6.4 ships pysqlite's zlib licence and no licence metadata."""
    from scripts.licensing_check import license_from_text

    zlib_text = (
        "This software is provided 'as-is', without any express or implied warranty.\n"
        "1. The origin of this software must not be misrepresented; ...\n"
        "2. Altered source versions must be plainly marked as such, ...\n"
        "3. This notice may not be removed or altered from any source distribution."
    )
    assert license_from_text(zlib_text) == "Zlib"
    # One phrase short is not enough to name a licence.
    assert license_from_text(zlib_text.split("3.")[0]) is None
    assert license_from_text("Permission is hereby granted, free of charge") is None
