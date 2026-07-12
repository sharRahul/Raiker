from __future__ import annotations

import importlib

import pytest

import raiker.auth.passwords as pw


def test_argon2_hash_and_verify() -> None:
    if not pw.ARGON2_AVAILABLE:
        pytest.skip("argon2 not installed")
    encoded, algo = pw.hash_password("correct horse battery staple")
    assert algo == "argon2id"
    # argon2 encoded string embeds the parameters
    assert "argon2id" in encoded
    assert "m=19456" in encoded
    assert "t=2" in encoded
    assert "p=1" in encoded
    assert pw.verify_password("correct horse battery staple", encoded, algo) is True
    assert pw.verify_password("wrong", encoded, algo) is False


def test_scrypt_fallback(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(pw, "ARGON2_AVAILABLE", False)
    encoded, algo = pw.hash_password("hunter2")
    assert algo == "scrypt"
    assert encoded.startswith("scrypt$131072$8$1$")
    assert pw.verify_password("hunter2", encoded, "scrypt") is True
    assert pw.verify_password("nope", encoded, "scrypt") is False


def test_verify_never_raises_on_garbage() -> None:
    assert pw.verify_password("x", "not-a-hash", "argon2id") is False
    assert pw.verify_password("x", "scrypt$bad", "scrypt") is False


def test_needs_rehash() -> None:
    if pw.ARGON2_AVAILABLE:
        assert pw.needs_rehash("scrypt$1$2$3$a$b", "scrypt") is True
        assert pw.needs_rehash("$argon2id$...", "argon2id") is False


def test_module_reimportable() -> None:
    importlib.reload(pw)
