from __future__ import annotations

import pyotp

from raiker.auth import mfa


def test_generate_and_verify_totp() -> None:
    secret = mfa.generate_secret()
    code = pyotp.TOTP(secret).now()
    assert mfa.verify_totp(secret, code) is True
    assert mfa.verify_totp(secret, "000000") is False


def test_provisioning_uri() -> None:
    secret = mfa.generate_secret()
    uri = mfa.provisioning_uri(secret, "alice")
    assert uri.startswith("otpauth://totp/")
    assert "issuer=Raiker" in uri
    assert secret in uri


def test_seed_encrypted_with_app_key_no_vault(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # MFA must not depend on the connector vault key being set.
    monkeypatch.delenv("RAIKER_CONNECTOR_VAULT_KEY", raising=False)
    secret = mfa.generate_secret()
    blob = mfa.encrypt_secret(tmp_path, secret)
    assert isinstance(blob, bytes) and blob != secret.encode()
    assert mfa.decrypt_secret(tmp_path, blob) == secret


def test_backup_codes() -> None:
    codes = mfa.generate_backup_codes(5)
    assert len(codes) == 5
    hashed = mfa.hash_backup_codes(codes)
    ok, new_hashed = mfa.consume_backup_code(hashed, codes[0])
    assert ok is True
    # used code cannot be consumed again
    again, _ = mfa.consume_backup_code(new_hashed, codes[0])
    assert again is False
    # unknown code rejected
    bad, _ = mfa.consume_backup_code(new_hashed, "ffffffff")
    assert bad is False
