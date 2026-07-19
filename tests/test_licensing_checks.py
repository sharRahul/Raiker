# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from scripts.check_dco import has_dco_signoff
from scripts.licensing_check import classify_license


def test_license_classifier_accepts_permitted_dual_license() -> None:
    policy = {"permitted": ["Apache-2.0", "MIT"], "review": [], "prohibited": []}

    assert classify_license("Apache-2.0 OR MIT", policy) == "permitted"


def test_license_classifier_rejects_unknown_and_prohibited_licenses() -> None:
    policy = {"permitted": ["MIT"], "review": [], "prohibited": ["GPL-3.0-only"]}

    assert classify_license(None, policy) == "unknown"
    assert classify_license("GPL-3.0-only", policy) == "prohibited"


def test_dco_signoff_requires_a_valid_trailer() -> None:
    assert has_dco_signoff("Change\n\nSigned-off-by: Example Person <person@example.test>\n")
    assert not has_dco_signoff("Change\n\nSigned-off-by: Example Person\n")
