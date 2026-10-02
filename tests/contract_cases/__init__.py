"""Contract cases, one module per domain; :data:`CASES` is all of them."""

from tests.contract_cases.auth import CASES as AUTH
from tests.contract_cases.base import merge
from tests.contract_cases.governance import CASES as GOVERNANCE
from tests.contract_cases.memory import CASES as MEMORY
from tests.contract_cases.models import CASES as MODELS
from tests.contract_cases.projects import CASES as PROJECTS
from tests.contract_cases.read_models import CASES as READ_MODELS
from tests.contract_cases.sessions import CASES as SESSIONS

CASES = merge(READ_MODELS, AUTH, SESSIONS, PROJECTS, MEMORY, MODELS, GOVERNANCE)
