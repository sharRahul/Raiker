# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from scripts.licensing_check import classify_license


def test_license_classifier_accepts_permitted_dual_license() -> None:
    policy = {"permitted": ["Apache-2.0", "MIT"], "review": [], "prohibited": []}

    assert classify_license("Apache-2.0 OR MIT", policy) == "permitted"


def test_license_classifier_rejects_unknown_and_prohibited_licenses() -> None:
    policy = {"permitted": ["MIT"], "review": [], "prohibited": ["GPL-3.0-only"]}

    assert classify_license(None, policy) == "unknown"
    assert classify_license("GPL-3.0-only", policy) == "prohibited"
