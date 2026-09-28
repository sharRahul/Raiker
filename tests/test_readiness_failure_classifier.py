"""OPT-12 — provider refusals are classified by one pure table, per probe stage.

``ProviderCatalogueProbe.check`` carried two exception ladders, eighteen
branches between them, each building its own state, code, summary and repair.
They are now ``classify_provider_failure``, which reads no provider message, no
network and no store — so every refusal can be checked here on its own.
"""

from __future__ import annotations

import pytest

from raiker.models import exceptions as provider_errors
from raiker.models.readiness import (
    ModelReadinessState,
    ProbeStage,
    ReadinessFailure,
    classify_provider_failure,
)

CATALOGUE, EXECUTION = ProbeStage.CATALOGUE, ProbeStage.EXECUTION


def _classify(error: Exception, stage: ProbeStage, *, local: bool = False) -> ReadinessFailure:
    return classify_provider_failure(
        error, stage=stage, label="Anthropic", model="claude-haiku-4-5", local_only=local
    )


@pytest.mark.parametrize(
    ("error", "stage", "local", "state", "reason"),
    [
        (provider_errors.ProviderAuthenticationError(), CATALOGUE, False,
         ModelReadinessState.AUTHENTICATION_FAILED, "provider_authentication_failed"),
        (provider_errors.ProviderPolicyError(), CATALOGUE, False,
         ModelReadinessState.POLICY_BLOCKED, "provider_policy_blocked"),
        (provider_errors.ProviderConfigurationError(), CATALOGUE, False,
         ModelReadinessState.NOT_CONFIGURED, "provider_not_configured"),
        (provider_errors.ProviderConfigurationError(), CATALOGUE, True,
         ModelReadinessState.RUNTIME_MISSING, "local_runtime_missing"),
        (provider_errors.ProviderConnectionError(), CATALOGUE, False,
         ModelReadinessState.UNREACHABLE, "provider_unreachable"),
        (provider_errors.ProviderTimeoutError(), CATALOGUE, True,
         ModelReadinessState.RUNTIME_STOPPED, "local_runtime_unreachable"),
        (provider_errors.ProviderModelNotFoundError(), CATALOGUE, True,
         ModelReadinessState.MODEL_MISSING, "local_model_missing"),
        (provider_errors.ProviderConnectionError(), EXECUTION, False,
         ModelReadinessState.UNREACHABLE, "provider_execution_refused"),
        (provider_errors.ProviderUnsupportedCapabilityError(), EXECUTION, False,
         ModelReadinessState.UNSUPPORTED, "provider_execution_probe_unsupported"),
        (provider_errors.ProviderQuotaExhaustedError(), CATALOGUE, False,
         ModelReadinessState.QUOTA_EXHAUSTED, "provider_quota_exhausted"),
        (provider_errors.ProviderQuotaExhaustedError(), EXECUTION, False,
         ModelReadinessState.QUOTA_EXHAUSTED, "provider_quota_exhausted"),
    ],
)
def test_each_refusal_has_its_own_state_and_reason(
    error: Exception, stage: ProbeStage, local: bool, state: ModelReadinessState, reason: str
) -> None:
    failure = _classify(error, stage, local=local)
    assert (failure.state, failure.reason_code) == (state, reason)


def test_the_repair_names_the_provider_and_the_model() -> None:
    failure = _classify(provider_errors.ProviderModelNotFoundError(), EXECUTION)
    assert failure.summary == "Anthropic lists claude-haiku-4-5, but cannot execute it."
    assert failure.remediation == "Choose a currently executable model, then check again."


def test_policy_is_a_catalogue_answer_and_unclassified_at_execution() -> None:
    # The execution ladder never had a policy branch; a policy refusal there is
    # answered as an unclassified execution failure, exactly as before.
    failure = _classify(provider_errors.ProviderPolicyError(), EXECUTION)
    assert failure.reason_code == "provider_execution_probe_failed"


@pytest.mark.parametrize(
    ("stage", "reason"),
    [(CATALOGUE, "provider_probe_failed"), (EXECUTION, "provider_execution_probe_failed")],
)
def test_an_unexpected_error_is_still_a_classified_answer(stage: ProbeStage, reason: str) -> None:
    failure = _classify(RuntimeError("sk-ant-secret leaked in a message"), stage)
    assert failure.reason_code == reason
    assert failure.state is ModelReadinessState.UNREACHABLE
    # No provider text reaches the public result.
    assert "sk-ant" not in failure.summary + failure.remediation


def test_a_workspace_refusal_names_the_field_rather_than_the_key() -> None:
    failure = _classify(provider_errors.ProviderWorkspaceRequiredError(), CATALOGUE)
    assert failure.reason_code == "provider_workspace_required"
    assert "The key itself is fine." in failure.remediation
