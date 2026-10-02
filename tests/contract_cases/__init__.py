"""Contract cases, one module per domain; :data:`CASES` is all of them."""

from tests.contract_cases.auth import CASES as AUTH
from tests.contract_cases.base import merge
from tests.contract_cases.read_models import CASES as READ_MODELS

CASES = merge(READ_MODELS, AUTH)
