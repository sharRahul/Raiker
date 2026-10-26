"""Contract cases, one module per domain; :data:`CASES` is all of them."""

from tests.contract_cases.auth import CASES as AUTH
from tests.contract_cases.base import merge
from tests.contract_cases.design import CASES as DESIGN
from tests.contract_cases.extensions import CASES as EXTENSIONS
from tests.contract_cases.github import CASES as GITHUB
from tests.contract_cases.goals import CASES as GOALS
from tests.contract_cases.governance import CASES as GOVERNANCE
from tests.contract_cases.host import CASES as HOST
from tests.contract_cases.library import CASES as LIBRARY
from tests.contract_cases.memory import CASES as MEMORY
from tests.contract_cases.models import CASES as MODELS
from tests.contract_cases.projects import CASES as PROJECTS
from tests.contract_cases.read_models import CASES as READ_MODELS
from tests.contract_cases.remote_access import CASES as REMOTE_ACCESS
from tests.contract_cases.sessions import CASES as SESSIONS

CASES = merge(READ_MODELS, AUTH, SESSIONS, PROJECTS, MEMORY, MODELS, GOVERNANCE, EXTENSIONS, HOST, GITHUB, DESIGN, GOALS, LIBRARY, REMOTE_ACCESS)
