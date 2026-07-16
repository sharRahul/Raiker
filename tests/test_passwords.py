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


def test_dummy_verify_uses_all_configured_account_hash_algorithms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verify_calls: list[tuple[str, str, str]] = []

    def verify_password(password: str, encoded: str, algo: str) -> bool:
        verify_calls.append((password, encoded, algo))
        return False

    monkeypatch.setattr(pw, "verify_password", verify_password)
    monkeypatch.setattr(pw, "_DUMMY_HASHES", {}, raising=False)

    pw.prepare_dummy_hashes()
    pw.spend_dummy_verify("unknown-password")

    expected_algorithms = ["scrypt", "argon2id"] if pw.ARGON2_AVAILABLE else ["scrypt"]
    assert [algo for _password, _dummy_hash, algo in verify_calls] == expected_algorithms


def test_dummy_verify_uses_scrypt_only_without_argon2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verify_calls: list[tuple[str, str, str]] = []

    def verify_password(password: str, encoded: str, algo: str) -> bool:
        verify_calls.append((password, encoded, algo))
        return False

    monkeypatch.setattr(pw, "ARGON2_AVAILABLE", False)
    monkeypatch.setattr(pw, "verify_password", verify_password)
    monkeypatch.setattr(pw, "_DUMMY_HASHES", {}, raising=False)

    pw.prepare_dummy_hashes()
    pw.spend_dummy_verify("unknown-password")

    assert len(verify_calls) == 1
    _password, dummy_hash, dummy_algo = verify_calls[0]
    assert dummy_algo == "scrypt"
    assert dummy_hash.startswith("scrypt$131072$8$1$")


def test_prepare_dummy_hashes_populates_cold_cache_before_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generated_algorithms: list[str] = []
    verify_calls: list[str] = []

    def generate_dummy_hash(algo: str) -> str:
        generated_algorithms.append(algo)
        return f"{algo}-dummy"

    def verify_password(_password: str, _encoded: str, algo: str) -> bool:
        verify_calls.append(algo)
        return False

    monkeypatch.setattr(pw, "_DUMMY_HASHES", {}, raising=False)
    monkeypatch.setattr(pw, "_generate_dummy_hash", generate_dummy_hash, raising=False)
    monkeypatch.setattr(pw, "verify_password", verify_password)

    pw.prepare_dummy_hashes()
    pw.spend_dummy_verify("unknown-password")

    expected_algorithms = ["scrypt", "argon2id"] if pw.ARGON2_AVAILABLE else ["scrypt"]
    assert generated_algorithms == expected_algorithms
    assert verify_calls == expected_algorithms


def test_verify_never_raises_on_garbage() -> None:
    assert pw.verify_password("x", "not-a-hash", "argon2id") is False
    assert pw.verify_password("x", "scrypt$bad", "scrypt") is False


def test_needs_rehash() -> None:
    if pw.ARGON2_AVAILABLE:
        assert pw.needs_rehash("scrypt$1$2$3$a$b", "scrypt") is True
        assert pw.needs_rehash("$argon2id$...", "argon2id") is False


def test_module_reimportable() -> None:
    importlib.reload(pw)
