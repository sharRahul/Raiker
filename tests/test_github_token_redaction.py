"""ADD-27 GH-15 — every GitHub token shape is redacted by its own rule.

Only `ghp_` and `github_pat_` had explicit patterns; OAuth (`gho_`), App user
(`ghu_`), refresh (`ghr_`) and installation (`ghs_`) tokens relied on the
40-character entropy fallback. GitHub began issuing installation tokens in a
stateless `ghs_APPID_JWT` form on 2026-04-27, which carries dots and is not 40
characters, so the fallback could not be relied on.
"""

from __future__ import annotations

import pytest

from raiker.context.redaction import redact_text

SHAPES = {
    "personal": "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8",
    "oauth": "gho_" + "16C7e42F292c6912E7710c838347Ae178B4a",
    "app_user": "ghu_" + "Zx9Yw8Vu7Ts6Rq5Po4Nm3Lk2Ji1Hg0Fe9Dc8",
    "refresh": "ghr_" + "1B4a2e77838347a7E420ce178F2E7c6912E1",
    "installation_classic": "ghs_" + "16C7e42F292c6912E7710c838347Ae178B4a",
    "installation_stateless": (
        "ghs_1234567_eyJhbGciOiJSUzI1NiJ9.eyJpc3MiOiIxMjM0NTY3In0.c2lnbmF0dXJlLXZhbHVlLWhlcmU"
    ),
    "short_and_odd": "ghs_shortButReal-1234.x",
}


@pytest.mark.parametrize("kind", sorted(SHAPES))
def test_each_github_token_shape_is_redacted(kind: str) -> None:
    token = SHAPES[kind]
    redacted, _ = redact_text(f"remote: Invalid username or password for {token} here")
    assert token not in redacted
    # Nothing recognisable of the token is left behind either.
    assert token[4:16] not in redacted


def test_ordinary_words_with_the_letters_are_left_alone() -> None:
    text = "the ghost_writer and gh_pages branches"
    assert redact_text(text)[0] == text
