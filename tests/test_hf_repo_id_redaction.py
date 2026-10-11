"""BUG-328 — a public Hugging Face repository name is not a secret.

The trending list carries each repository as ``repo_id`` (``owner/name``). The
generic ``_id`` rule spares only Raiker's own record ids, so a long hyphenated
repository name tripped the high-entropy fallback and was shown as
``[REDACTED_SECRET]`` — a model the owner could see the downloads of and never
choose. It is now read as the model id it is; credential shapes still redact.
"""

from __future__ import annotations

from raiker.api.redaction import is_identifier_field, is_model_field, redact_response_body

LONG_REPO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def test_a_long_repository_name_survives_the_response_redactor() -> None:
    body = {"items": [{"repo_id": LONG_REPO, "downloads": 5_134_275, "likes": 1_124}]}
    assert redact_response_body(body) == body


def test_repo_id_is_a_model_field_not_a_record_id() -> None:
    assert is_model_field("repo_id") and is_model_field("repo_ids")
    assert not is_identifier_field("repo_id")
    assert is_identifier_field("task_id")


def test_a_credential_under_repo_id_still_redacts() -> None:
    token = "hf_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7"
    redacted = redact_response_body({"repo_id": token, "note": f"use {token} here"})
    assert redacted["repo_id"] == "[REDACTED_TOKEN]"
    # Found with BUG-328: a Hugging Face token is 37 characters, under the
    # generic fallback's 40, and no pattern knew its shape — anywhere.
    assert token not in redacted["note"]
