"""OPT-03 — one strict request base, inherited rather than repeated.

Sixty-nine request models each declared ``extra="forbid"`` for themselves, and
sixteen did not — so whether an API refused a misspelled field depended on
whether the person who wrote that route remembered to. The posture is now the
base class's, and this test is what makes forgetting impossible.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil

import pytest
from pydantic import BaseModel, ValidationError

import raiker.api
from raiker.api.schemas import (
    ChannelEnabledRequest,
    LocalModelDeployRequest,
    SetModelSelectionRequest,
    StrictModelRequest,
    StrictRequest,
)


def _api_models() -> list[type[BaseModel]]:
    found: dict[str, type[BaseModel]] = {}
    for info in pkgutil.iter_modules(raiker.api.__path__, prefix="raiker.api."):
        module = importlib.import_module(info.name)
        for _, value in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(value, BaseModel)
                and value.__module__ == module.__name__
                and value not in (StrictRequest, StrictModelRequest)
            ):
                found[f"{value.__module__}.{value.__qualname__}"] = value
    return list(found.values())


def test_every_pydantic_model_under_the_api_inherits_the_strict_base() -> None:
    models = _api_models()
    # The walk found the models it exists to check, not an empty package.
    assert len(models) > 80
    lenient = sorted(
        f"{model.__module__}.{model.__qualname__}"
        for model in models
        if not issubclass(model, StrictRequest)
    )
    assert lenient == [], f"request models that silently ignore unknown fields: {lenient}"


def test_the_base_refuses_a_field_the_route_never_reads() -> None:
    # Before OPT-03 this model had no config at all, so a misspelled
    # ``enabeld`` was dropped and the request succeeded doing nothing.
    with pytest.raises(ValidationError):
        ChannelEnabledRequest.model_validate({"enabled": True, "enabeld": False})
    with pytest.raises(ValidationError):
        LocalModelDeployRequest.model_validate({"profile": "local"})
    assert LocalModelDeployRequest.model_validate({}).profile_id is None


def test_model_prefixed_fields_keep_their_namespace_and_stay_strict() -> None:
    assert issubclass(SetModelSelectionRequest, StrictModelRequest)
    assert SetModelSelectionRequest.model_config.get("protected_namespaces") == ()
    assert SetModelSelectionRequest.model_config.get("extra") == "forbid"
